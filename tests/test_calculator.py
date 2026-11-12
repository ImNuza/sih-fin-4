from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from api import calculator
from api.calculator import Readings
from api.models import Tariff

DAYS = calculator.DAYS_PER_YEAR


def readings(*values: float) -> Readings:
    """One site-day for each reading."""
    return Readings(np.array(values), np.ones(len(values)))


def make_tariff(**changes) -> Tariff:
    body = {
        "hazards": [
            {
                "key": "haze",
                "label": "Haze",
                "reading": "PSI",
                "weight": 1.0,
                "scaled_by_product": True,
                "bands": [{"at_least": 101, "severity": 0.5}, {"at_least": 201, "severity": 1.0}],
                "source": "test",
            },
            {
                "key": "closure",
                "label": "Closure",
                "reading": "1 if closed",
                "weight": 1.0,
                "scaled_by_product": False,
                "bands": [{"at_least": 1, "severity": 1.0}],
                "assumed_days_per_year": 0,
                "source": "test",
            },
        ],
        "products": [
            {
                "key": "cooked_food",
                "label": "Cooked food",
                "shelf_life_days": 0.5,
                "restock_every_days": 1,
                "demand_sensitivity": 1.0,
            },
            {
                "key": "dry_goods",
                "label": "Dry goods",
                "shelf_life_days": 100,
                "restock_every_days": 10,
                "demand_sensitivity": 0.5,
            },
        ],
        "tiers": [
            {
                "key": "tier_1",
                "label": "Tier 1",
                "daily_payout_sgd": 10,
                "max_paid_days_per_year": 366,
            },
            {
                "key": "tier_2",
                "label": "Tier 2",
                "daily_payout_sgd": 20,
                "max_paid_days_per_year": 366,
            },
        ],
        "pricing": {
            "recovered_share": 0.5,
            "uncertainty_load": 0,
            "catastrophe_load": 0,
            "expense_ratio": 0,
            "gst_rate": 0,
        },
    }
    body.update(changes)
    return Tariff.model_validate(body)


def test_severity_is_the_highest_band_reached():
    haze = make_tariff().hazards[0]
    values = np.array([50, 101, 150, 201, 400])
    assert calculator.severities(haze, values).tolist() == [0, 0.5, 0.5, 1.0, 1.0]


def test_product_factor_counts_wasted_stock_in_full():
    tariff = make_tariff()
    cooked, dry = tariff.products
    assert calculator.product_factor(cooked, 0.5) == 1.0
    wasted = 10 / 100
    assert calculator.product_factor(dry, 0.5) == pytest.approx(0.5 * (wasted + (1 - wasted) * 0.5))


def test_closure_is_full_loss_for_every_product():
    day = calculator.assess(make_tariff(), "dry_goods", "tier_2", {"closure": 1})
    assert day.loss_percent == 100
    assert day.payout_sgd == 20


def test_hazards_combine_without_passing_full_loss():
    day = calculator.assess(make_tariff(), "cooked_food", "tier_1", {"haze": 150, "closure": 1})
    assert day.loss_percent == 100
    half = calculator.assess(make_tariff(), "cooked_food", "tier_1", {"haze": 150})
    assert half.loss_percent == 50
    assert half.payout_sgd == 5


def test_a_day_below_every_band_pays_nothing():
    day = calculator.assess(make_tariff(), "cooked_food", "tier_1", {"haze": 80})
    assert day.loss_percent == 0
    assert day.payout_sgd == 0


def test_premium_prices_the_average_year_from_history():
    history = {"east": {"haze": readings(50.0, 250.0)}}
    quote = calculator.quote(make_tariff(), history, "east", "cooked_food")
    loss_days = DAYS * 0.5
    assert quote.expected_loss_days == pytest.approx(loss_days, abs=0.01)
    tier_1, tier_2 = quote.tiers
    assert tier_1.yearly_premium_sgd == pytest.approx(loss_days * 10, abs=0.01)
    assert tier_2.weekly_premium_sgd > tier_1.weekly_premium_sgd


def test_days_weight_each_reading():
    history = {"east": {"haze": Readings(np.array([50.0, 250.0]), np.array([3, 1]))}}
    quote = calculator.quote(make_tariff(), history, "east", "cooked_food")
    assert quote.expected_loss_days == pytest.approx(DAYS * 0.25, abs=0.01)


def test_loads_raise_the_premium():
    pricing = {
        "recovered_share": 0.5,
        "uncertainty_load": 0.1,
        "catastrophe_load": 0.1,
        "expense_ratio": 0.2,
        "gst_rate": 0.09,
    }
    history = {"east": {"haze": readings(250.0)}}
    tier_1 = calculator.quote(make_tariff(pricing=pricing), history, "east", "cooked_food").tiers[0]
    risk_cost = DAYS * 10
    assert tier_1.yearly_premium_sgd == pytest.approx(risk_cost * 1.2 / 0.8 * 1.09, abs=0.01)


def test_yearly_cap_limits_paid_days():
    tariff = make_tariff()
    tariff.tiers[0].max_paid_days_per_year = 5
    history = {"east": {"haze": readings(250.0)}}
    tier_1 = calculator.quote(tariff, history, "east", "cooked_food").tiers[0]
    assert tier_1.expected_paid_days == 5
    assert tier_1.max_payout_per_year_sgd == 50


def test_assumed_days_replace_missing_history():
    tariff = make_tariff()
    tariff.hazards[1].assumed_days_per_year = 2
    quote = calculator.quote(tariff, {"east": {"haze": readings(50.0)}}, "east", "dry_goods")
    assert quote.expected_loss_days == 2


def test_hazard_without_history_or_assumed_days_cannot_be_priced():
    tariff = make_tariff()
    tariff.hazards[1].assumed_days_per_year = None
    with pytest.raises(calculator.MissingHistory):
        calculator.check_prices(tariff, {"east": {"haze": readings(50.0)}})


def test_unknown_keys_are_named():
    with pytest.raises(calculator.UnknownKey, match="Unknown product: fish"):
        calculator.assess(make_tariff(), "fish", "tier_1", {})


def test_higher_tier_must_pay_more():
    tiers = [
        {"key": "a", "label": "Tier 1", "daily_payout_sgd": 20, "max_paid_days_per_year": 10},
        {"key": "b", "label": "Tier 2", "daily_payout_sgd": 20, "max_paid_days_per_year": 10},
    ]
    with pytest.raises(ValidationError, match="Tier 2 must pay more a day than Tier 1"):
        make_tariff(tiers=tiers)


def test_band_levels_must_rise():
    tariff = make_tariff().model_dump()
    tariff["hazards"][0]["bands"].reverse()
    with pytest.raises(ValidationError, match="band levels must rise"):
        Tariff.model_validate(tariff)


def test_keys_must_be_unique():
    tariff = make_tariff().model_dump()
    tariff["products"][1]["key"] = "cooked_food"
    with pytest.raises(ValidationError, match="Duplicate product keys: cooked_food"):
        Tariff.model_validate(tariff)
