"""FastAPI-app for VoltEdge Smart Charging.

Endpoints kalder domaenet (optimering) og databasen direkte - fladt og enkelt.
"""

import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import database
import domain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voltedge")

app = FastAPI(title="VoltEdge Smart Charging API", version="1.0.0")
optimizer = domain.ChargingPlanOptimizer()


@app.on_event("startup")
def startup():
    try:
        database.init_db()
        logger.info("Database klar")
    except Exception as e:
        logger.warning("Kunne ikke opsaette database ved opstart: %s", e)


# ----------------------------- Input-modeller ----------------------------

class PricePointIn(BaseModel):
    start: datetime
    price_per_kwh: float


class CreatePlanIn(BaseModel):
    session_id: str
    target_energy_kwh: float
    deadline: datetime
    window_start: datetime
    window_end: datetime
    charger_max_power_kw: float
    site_load_limit_kw: float
    prices: list[PricePointIn]


class CompleteIn(BaseModel):
    delivered_energy_kwh: float


class AdjustIn(BaseModel):
    prices: list[PricePointIn]


# ----------------------------- Hjaelpefunktion ---------------------------

def plan_to_dict(plan):
    return {
        "plan_id": plan.plan_id,
        "session_id": plan.session_id,
        "status": plan.status,
        "target_energy_kwh": plan.target.energy_kwh,
        "estimated_cost": plan.profile.estimated_cost,
        "scheduled_energy_kwh": plan.profile.total_energy_kwh,
        "peak_power_kw": plan.profile.peak_power_kw,
        "meets_target": plan.meets_target,
        "delivered_energy_kwh": plan.delivered_energy_kwh,
        "slots": [
            {"start": s.start.isoformat(), "end": s.end.isoformat(),
             "power_kw": s.power_kw, "energy_kwh": s.energy_kwh}
            for s in plan.profile.slots
        ],
    }


# ------------------------------- Endpoints -------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "smart-charging"}


@app.post("/charging-plans", status_code=201)
def create_plan(req: CreatePlanIn):
    window = domain.TimeWindow(req.window_start, req.window_end)
    target = domain.ChargingTarget(req.target_energy_kwh, req.deadline)
    constraint = domain.LoadConstraint(req.site_load_limit_kw)
    price_signal = domain.PriceSignal([(p.start, p.price_per_kwh) for p in req.prices])
    try:
        profile = optimizer.optimize(
            target, window, constraint, req.charger_max_power_kw, price_signal
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    plan = domain.ChargingPlan.create(
        req.session_id, target, window, constraint, req.charger_max_power_kw, profile
    )
    database.save_plan(plan)
    logger.info("Plan oprettet: %s (events: %s)", plan.plan_id,
                [type(e).__name__ for e in plan.events])
    return plan_to_dict(plan)


@app.get("/charging-plans")
def list_plans():
    return [plan_to_dict(p) for p in database.list_plans()]


@app.get("/charging-plans/{plan_id}")
def get_plan(plan_id: str):
    plan = database.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Ladeplan ikke fundet")
    return plan_to_dict(plan)


@app.post("/charging-plans/{plan_id}/complete")
def complete_plan(plan_id: str, req: CompleteIn):
    plan = database.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Ladeplan ikke fundet")
    plan.complete(req.delivered_energy_kwh)
    database.update_plan(plan)
    return plan_to_dict(plan)


@app.post("/charging-plans/{plan_id}/adjust")
def adjust_plan(plan_id: str, req: AdjustIn):
    plan = database.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Ladeplan ikke fundet")
    price_signal = domain.PriceSignal([(p.start, p.price_per_kwh) for p in req.prices])
    try:
        new_profile = optimizer.optimize(
            plan.target, plan.window, plan.constraint,
            plan.charger_max_power_kw, price_signal,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    plan.adjust(new_profile)
    database.update_plan(plan)
    logger.info("Plan justeret: %s (events: %s)", plan.plan_id,
                [type(e).__name__ for e in plan.events])
    return plan_to_dict(plan)
