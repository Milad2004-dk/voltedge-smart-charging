"""Tests for domænelogikken (kræver ingen database)."""

from datetime import datetime

import pytest

import domain


def _price_signal(window):
    """Billig strøm om natten (00-06), dyrt i myldretiden."""
    prices = []
    cursor = window.start
    from datetime import timedelta
    while cursor < window.end:
        h = cursor.hour
        price = 0.5 if 0 <= h < 6 else (3.0 if 17 <= h < 21 else 1.5)
        prices.append((cursor, price))
        cursor += timedelta(hours=1)
    return domain.PriceSignal(prices)


def _scenario():
    window = domain.TimeWindow(datetime(2026, 5, 22, 18), datetime(2026, 5, 23, 7))
    target = domain.ChargingTarget(40.0, datetime(2026, 5, 23, 7))
    return window, target


def test_optimizer_charges_in_cheapest_hours():
    window, target = _scenario()
    profile = domain.ChargingPlanOptimizer().optimize(
        target, window, domain.LoadConstraint(11.0), 11.0, _price_signal(window)
    )
    # 40 kWh kan lades om natten til 0,5 DKK/kWh => 20 DKK
    assert profile.estimated_cost == 20.0
    assert profile.total_energy_kwh == 40.0
    assert profile.peak_power_kw <= 11.0
    for slot in profile.slots:
        assert 0 <= slot.start.hour < 6  # alt lades i den billige nat


def test_optimizer_respects_load_limit():
    window, target = _scenario()
    profile = domain.ChargingPlanOptimizer().optimize(
        target, window, domain.LoadConstraint(5.0), 11.0, _price_signal(window)
    )
    assert profile.peak_power_kw <= 5.0


def test_optimizer_raises_when_target_impossible():
    window = domain.TimeWindow(datetime(2026, 5, 22, 18), datetime(2026, 5, 22, 20))
    target = domain.ChargingTarget(100.0, datetime(2026, 5, 22, 20))
    with pytest.raises(ValueError):
        domain.ChargingPlanOptimizer().optimize(
            target, window, domain.LoadConstraint(11.0), 11.0, _price_signal(window)
        )


def test_value_object_validation():
    with pytest.raises(ValueError):
        domain.TimeWindow(datetime(2026, 5, 22, 10), datetime(2026, 5, 22, 9))
    with pytest.raises(ValueError):
        domain.ChargingTarget(0, datetime(2026, 5, 22, 10))
    with pytest.raises(ValueError):
        domain.LoadConstraint(0)


def test_aggregate_create_and_complete():
    window, target = _scenario()
    profile = domain.ChargingPlanOptimizer().optimize(
        target, window, domain.LoadConstraint(11.0), 11.0, _price_signal(window)
    )
    plan = domain.ChargingPlan.create("s1", target, window,
                                      domain.LoadConstraint(11.0), 11.0, profile)
    assert plan.status == "SCHEDULED"
    assert any(isinstance(e, domain.ChargingPlanCreated) for e in plan.events)
    assert plan.meets_target

    plan.complete(40.0)
    assert plan.status == "COMPLETED"
    assert any(isinstance(e, domain.ChargingPlanCompleted) for e in plan.events)
    with pytest.raises(ValueError):
        plan.complete(10.0)


def test_aggregate_adjust_raises_event():
    window, target = _scenario()
    opt = domain.ChargingPlanOptimizer()
    profile = opt.optimize(
        target, window, domain.LoadConstraint(11.0), 11.0, _price_signal(window)
    )
    plan = domain.ChargingPlan.create("s1", target, window,
                                      domain.LoadConstraint(11.0), 11.0, profile)

    # Nyt prissignal -> juster planen (genberegnet skema)
    new_profile = opt.optimize(
        target, window, domain.LoadConstraint(11.0), 11.0, _price_signal(window)
    )
    plan.adjust(new_profile)
    assert any(isinstance(e, domain.ChargingPlanAdjusted) for e in plan.events)

    # En afsluttet plan kan ikke justeres
    plan.complete(40.0)
    with pytest.raises(ValueError):
        plan.adjust(new_profile)
