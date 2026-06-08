"""Domaenelaget for Smart Charging.

Alle DDD-byggeklodser ligger samlet her, så de er nemme at finde og forklare:
  - Value objects : TimeWindow, PowerLevel, ChargingTarget, LoadConstraint, PriceSignal
  - Entity        : ChargingProfile (det beregnede ladeskema)
  - Aggregate root: ChargingPlan (samler det hele og rejser events)
  - Domain events : ChargingPlanCreated, ChargingPlanAdjusted, ChargingPlanCompleted
  - Domain service: ChargingPlanOptimizer (selve smart charging-beregningen)

Value objects er immutable (frozen=True) - de kan ikke ændres efter de er lavet.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# ----------------------------- Value objects -----------------------------

@dataclass(frozen=True)
class TimeWindow:
    """Et tidsinterval, fx fra bilen saettes til, til deadline."""
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError("TimeWindow: start skal vaere foer end")

    def hours(self):
        return (self.end - self.start).total_seconds() / 3600


@dataclass(frozen=True)
class PowerLevel:
    """En ladeeffekt i kW."""
    kw: float


@dataclass(frozen=True)
class ChargingTarget:
    """Kundens maal: hvor meget energi der skal leveres inden en deadline."""
    energy_kwh: float
    deadline: datetime

    def __post_init__(self):
        if self.energy_kwh <= 0:
            raise ValueError("ChargingTarget: energy_kwh skal vaere positiv")


@dataclass(frozen=True)
class LoadConstraint:
    """Den maksimale effekt sitet/nettet tillader."""
    max_power_kw: float

    def __post_init__(self):
        if self.max_power_kw <= 0:
            raise ValueError("LoadConstraint: max_power_kw skal vaere positiv")


@dataclass(frozen=True)
class PriceSignal:
    """Priskurven: el-prisen pr. kWh time for time.

    Gemmes som en liste af (starttidspunkt, pris). Kommer fra Energy & Grid.
    """
    prices: list  # liste af (datetime, float)

    def price_for(self, slot_start):
        for start, price in self.prices:
            if start == slot_start:
                return price
        return None


# --------------------------- Entity + skema ------------------------------

@dataclass(frozen=True)
class ScheduledSlot:
    """Et tidsslot i ladeplanen: her lades med denne effekt."""
    start: datetime
    end: datetime
    power_kw: float

    @property
    def energy_kwh(self):
        hours = (self.end - self.start).total_seconds() / 3600
        return round(self.power_kw * hours, 2)


@dataclass
class ChargingProfile:
    """Entity: det beregnede ladeskema (kan ændres ved genberegning)."""
    slots: list  # liste af ScheduledSlot
    estimated_cost: float
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def total_energy_kwh(self):
        return round(sum(s.energy_kwh for s in self.slots), 2)

    @property
    def peak_power_kw(self):
        return max((s.power_kw for s in self.slots), default=0.0)


# ----------------------------- Domain events -----------------------------

@dataclass
class ChargingPlanCreated:
    plan_id: str
    session_id: str
    estimated_cost: float


@dataclass
class ChargingPlanAdjusted:
    plan_id: str
    estimated_cost: float


@dataclass
class ChargingPlanCompleted:
    plan_id: str
    delivered_energy_kwh: float


# ----------------------------- Aggregate root ----------------------------

class ChargingPlan:
    """Aggregate root: al ændring af en ladeplan går gennem denne klasse."""

    def __init__(self, session_id, target, window, constraint,
                 charger_max_power_kw, profile, plan_id=None,
                 status="SCHEDULED", delivered_energy_kwh=0.0):
        self.plan_id = plan_id or str(uuid.uuid4())
        self.session_id = session_id
        self.target = target
        self.window = window
        self.constraint = constraint
        self.charger_max_power_kw = charger_max_power_kw
        self.profile = profile
        self.status = status
        self.delivered_energy_kwh = delivered_energy_kwh
        self.events = []

    @classmethod
    def create(cls, session_id, target, window, constraint,
               charger_max_power_kw, profile):
        plan = cls(session_id, target, window, constraint,
                   charger_max_power_kw, profile)
        plan.events.append(
            ChargingPlanCreated(plan.plan_id, session_id, profile.estimated_cost)
        )
        return plan

    def complete(self, delivered_energy_kwh):
        if self.status == "COMPLETED":
            raise ValueError("Planen er allerede afsluttet")
        self.status = "COMPLETED"
        self.delivered_energy_kwh = delivered_energy_kwh
        self.events.append(
            ChargingPlanCompleted(self.plan_id, delivered_energy_kwh)
        )

    def adjust(self, new_profile):
        # Genberegnet plan (fx ved nyt prissignal fra Energy & Grid)
        if self.status != "SCHEDULED":
            raise ValueError("Kun en planlagt plan kan justeres")
        self.profile = new_profile
        self.events.append(
            ChargingPlanAdjusted(self.plan_id, new_profile.estimated_cost)
        )

    @property
    def meets_target(self):
        return self.profile.total_energy_kwh + 0.01 >= self.target.energy_kwh


# ----------------------------- Domain service ----------------------------

class ChargingPlanOptimizer:
    """Domain service: beregner den optimale ladeplan (smart charging).

    Ide: lad i de billigste timer foerst, op til effektloftet, indtil maalet
    er naaet - uden at overskride ladestanderens og nettets graenser.
    """

    def optimize(self, target, window, constraint,
                 charger_max_power_kw, price_signal):
        # Effektloftet = det laveste af laderens og sitets graense
        ceiling_kw = min(charger_max_power_kw, constraint.max_power_kw)

        # 1) Del tidsvinduet op i timer og find prisen for hver time
        hours = []
        cursor = window.start
        while cursor < window.end:
            slot_end = min(cursor + timedelta(hours=1), window.end)
            price = price_signal.price_for(cursor)
            if price is None:
                raise ValueError(f"Prissignal mangler for {cursor}")
            length = (slot_end - cursor).total_seconds() / 3600
            hours.append({
                "start": cursor,
                "end": slot_end,
                "price": price,
                "length": length,
                "max_energy": ceiling_kw * length,
            })
            cursor = slot_end

        # 2) Er der nok kapacitet til at naa maalet?
        if sum(h["max_energy"] for h in hours) < target.energy_kwh:
            raise ValueError("Maalet kan ikke naas inden for tidsvinduet")

        # 3) Tag de billigste timer foerst
        hours.sort(key=lambda h: h["price"])

        remaining = target.energy_kwh
        chosen = []
        total_cost = 0.0
        for h in hours:
            if remaining <= 0:
                break
            energy = min(remaining, h["max_energy"])
            power = round(energy / h["length"], 2)
            chosen.append(ScheduledSlot(h["start"], h["end"], power))
            total_cost += energy * h["price"]
            remaining -= energy

        # 4) Sorter skemaet kronologisk og returner profilen
        chosen.sort(key=lambda s: s.start)
        return ChargingProfile(slots=chosen, estimated_cost=round(total_cost, 2))
