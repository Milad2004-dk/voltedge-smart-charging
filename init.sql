-- Databaseskema for Smart Charging. Køres automatisk af MySQL-containeren
-- første gang den starter (ER-diagram i rapportens afsnit 4).

CREATE TABLE IF NOT EXISTS charging_plans (
    plan_id              VARCHAR(36) PRIMARY KEY,
    session_id           VARCHAR(64),
    target_energy_kwh    DOUBLE,
    deadline             DATETIME,
    window_start         DATETIME,
    window_end           DATETIME,
    site_load_limit_kw   DOUBLE,
    charger_max_power_kw DOUBLE,
    status               VARCHAR(16),
    estimated_cost       DOUBLE,
    delivered_energy_kwh DOUBLE
);

CREATE TABLE IF NOT EXISTS charging_plan_slots (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    plan_id   VARCHAR(36),
    slot_start DATETIME,
    slot_end   DATETIME,
    power_kw   DOUBLE,
    FOREIGN KEY (plan_id) REFERENCES charging_plans(plan_id) ON DELETE CASCADE
);
