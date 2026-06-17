"""Databaselag - rå SQL med mysql.connector (samme tilgang som del 2).

Her gemmes og hentes ChargingPlan-aggregatet i to tabeller:
  charging_plans (1) ---< charging_plan_slots (mange)
Forbindelsen læses fra environment variables (sat via GitHub Secrets / compose).
"""

import os

import mysql.connector

import domain

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "user": os.environ.get("DB_USER", "voltedge"),
    "password": os.environ.get("DB_PASSWORD", "voltedge"),
    "database": os.environ.get("DB_NAME", "voltedge"),
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def init_db():
    """Opret tabellerne hvis de ikke findes (idempotent)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS charging_plans (
            plan_id VARCHAR(36) PRIMARY KEY,
            session_id VARCHAR(64),
            target_energy_kwh DOUBLE,
            deadline DATETIME,
            window_start DATETIME,
            window_end DATETIME,
            site_load_limit_kw DOUBLE,
            charger_max_power_kw DOUBLE,
            status VARCHAR(16),
            estimated_cost DOUBLE,
            delivered_energy_kwh DOUBLE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS charging_plan_slots (
            id INT AUTO_INCREMENT PRIMARY KEY,
            plan_id VARCHAR(36),
            slot_start DATETIME,
            slot_end DATETIME,
            power_kw DOUBLE,
            FOREIGN KEY (plan_id) REFERENCES charging_plans(plan_id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def save_plan(plan):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO charging_plans
           (plan_id, session_id, target_energy_kwh, deadline, window_start,
            window_end, site_load_limit_kw, charger_max_power_kw, status,
            estimated_cost, delivered_energy_kwh)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (plan.plan_id, plan.session_id, plan.target.energy_kwh,
         plan.target.deadline, plan.window.start, plan.window.end,
         plan.constraint.max_power_kw, plan.charger_max_power_kw,
         plan.status, plan.profile.estimated_cost, plan.delivered_energy_kwh),
    )
    for s in plan.profile.slots:
        cur.execute(
            """INSERT INTO charging_plan_slots (plan_id, slot_start, slot_end, power_kw)
               VALUES (%s, %s, %s, %s)""",
            (plan.plan_id, s.start, s.end, s.power_kw),
        )
    conn.commit()
    cur.close()
    conn.close()


def update_plan(plan):
    """Gem ændringer (fx efter complete eller adjust)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """UPDATE charging_plans
           SET status=%s, estimated_cost=%s, delivered_energy_kwh=%s
           WHERE plan_id=%s""",
        (plan.status, plan.profile.estimated_cost,
         plan.delivered_energy_kwh, plan.plan_id),
    )
    # Skriv tidsslots på ny - en justeret plan har et nyt skema
    cur.execute("DELETE FROM charging_plan_slots WHERE plan_id=%s", (plan.plan_id,))
    for s in plan.profile.slots:
        cur.execute(
            """INSERT INTO charging_plan_slots (plan_id, slot_start, slot_end, power_kw)
               VALUES (%s, %s, %s, %s)""",
            (plan.plan_id, s.start, s.end, s.power_kw),
        )
    conn.commit()
    cur.close()
    conn.close()


def _row_to_plan(row, slot_rows):
    profile = domain.ChargingProfile(
        slots=[domain.ScheduledSlot(s["slot_start"], s["slot_end"], s["power_kw"])
               for s in slot_rows],
        estimated_cost=row["estimated_cost"],
    )
    return domain.ChargingPlan(
        session_id=row["session_id"],
        target=domain.ChargingTarget(row["target_energy_kwh"], row["deadline"]),
        window=domain.TimeWindow(row["window_start"], row["window_end"]),
        constraint=domain.LoadConstraint(row["site_load_limit_kw"]),
        charger_max_power_kw=row["charger_max_power_kw"],
        profile=profile,
        plan_id=row["plan_id"],
        status=row["status"],
        delivered_energy_kwh=row["delivered_energy_kwh"],
    )


def get_plan(plan_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM charging_plans WHERE plan_id=%s", (plan_id,))
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        return None
    cur.execute(
        "SELECT * FROM charging_plan_slots WHERE plan_id=%s ORDER BY slot_start",
        (plan_id,),
    )
    slot_rows = cur.fetchall()
    cur.close()
    conn.close()
    return _row_to_plan(row, slot_rows)


def list_plans():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM charging_plans")
    rows = cur.fetchall()
    plans = []
    for row in rows:
        cur.execute(
            "SELECT * FROM charging_plan_slots WHERE plan_id=%s ORDER BY slot_start",
            (row["plan_id"],),
        )
        plans.append(_row_to_plan(row, cur.fetchall()))
    cur.close()
    conn.close()
    return plans
