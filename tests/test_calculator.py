from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from api import calculator
from api.calculator import Readings, Site
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
                "sites_used": 1,
                "source": "test",
            },
            {
                "key": "closure",
                "label": "Closure",
                "reading": "1 if closed",
                "weight": 1.0,
                "scaled_by_product": False,
                "bands": [{"at_least": 1, "severity": 1.0}],
                "sites_used": 1,
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
                "gross_margin": 0.6,
                "recovered_share": 0,
                "source": "test",
            },
            {
                "key": "dry_goods",
                "label": "Dry goods",
                "shelf_life_days": 100,
                "restock_every_days": 10,
                "demand_sensitivity": 0.5,
                "gross_margin": 0.4,
                "recovered_share": 0.5,
                "source": "test",
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


def test_product_factor_is_lost_profit_plus_spoiled_stock():
    cooked, dry = make_tariff().products
    assert calculator.product_factor(cooked) == pytest.approx(1.0)
    lost_profit, spoiled_stock = 0.4 * (1 - 0.5), (10 / 100) * (1 - 0.4)
    assert calculator.product_factor(dry) == pytest.approx(0.5 * (lost_profit + spoiled_stock))


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


RENT = {
    "trading_days_per_month": 25,
    "classes": [
        {"key": "lower", "label": "Lower", "at_least_monthly_sgd": 0},
        {"key": "high", "label": "High", "at_least_monthly_sgd": 400},
    ],
    "source": "test",
}


def bid_record(median: float | None) -> calculator.BidRecord:
    bids = 0 if median is None else 3
    return calculator.BidRecord("Test Centre", median, bids, "test", None, None)


def test_rent_class_is_the_highest_limit_reached():
    tariff = make_tariff(rent=RENT)
    assert calculator.rent_class(tariff.rent, 399.99).key == "lower"
    assert calculator.rent_class(tariff.rent, 400).key == "high"


def test_recommended_tier_is_the_smallest_that_covers_a_days_rent():
    tariff = make_tariff(rent=RENT)
    # 250 a month over 25 days is 10 a day: Tier 1 pays exactly that.
    assert calculator.centre_rent(tariff, bid_record(250), 0).recommended_tier == "tier_1"
    # 300 a month is 12 a day: only Tier 2 (20) covers it.
    assert calculator.centre_rent(tariff, bid_record(300), 0).recommended_tier == "tier_2"


def test_rent_above_every_tier_picks_the_biggest_and_says_so():
    rent = calculator.centre_rent(make_tariff(rent=RENT), bid_record(1000), 0)
    assert (rent.recommended_tier, rent.covers_rent, rent.rent_per_day_sgd) == ("tier_2", False, 40)


def test_centre_with_no_bid_borrows_the_fallback_and_is_marked_estimated():
    rent = calculator.centre_rent(make_tariff(rent=RENT), bid_record(None), 500)
    assert (rent.estimated, rent.median_bid_sgd, rent.rent_class) == (True, 500, "high")


def test_tariff_without_rent_loads_the_default_classes():
    assert [c.key for c in make_tariff().rent.classes] == ["lower", "mid", "high"]


@pytest.mark.parametrize(
    "classes",
    [
        [{"key": "a", "label": "A", "at_least_monthly_sgd": 100}],
        [
            {"key": "a", "label": "A", "at_least_monthly_sgd": 0},
            {"key": "b", "label": "B", "at_least_monthly_sgd": 0},
        ],
    ],
)
def test_rent_classes_must_start_at_zero_and_rise(classes):
    with pytest.raises(ValidationError):
        make_tariff(rent={**RENT, "classes": classes})


def site(key: str, latitude: float, value_days: dict[float, int], region: str = "east") -> Site:
    values = np.array(list(value_days))
    return Site(key, region, latitude, 103.9, Readings(values, np.array(list(value_days.values()))))


def pooled(sites: list[Site]) -> Readings:
    return Readings(
        np.concatenate([s.readings.values for s in sites]),
        np.concatenate([s.readings.days for s in sites]),
    )


def test_km_between_one_degree_of_latitude():
    assert calculator.km_between(1.0, 103.9, 2.0, 103.9) == pytest.approx(111.2, abs=0.1)


def test_place_with_steady_stations_is_priced_from_its_own_station():
    stations = [site("near", 1.30, {50.0: 1000}), site("far", 1.45, {250.0: 1000})]
    history = {"east": {"haze": pooled(stations)}}
    quote = calculator.quote_at(
        make_tariff(), history, {"haze": stations}, 1.31, 103.9, "cooked_food"
    )
    (haze,) = quote.local_risks
    assert (haze.stations, haze.credibility) == (["near"], 1.0)
    assert haze.region_loss_days == pytest.approx(DAYS * 0.5, abs=0.01)
    assert quote.expected_loss_days == 0


def test_stations_that_only_differ_by_chance_get_the_region_price():
    stations = [site("a", 1.30, {50.0: 2, 250.0: 2}), site("b", 1.45, {50.0: 2, 250.0: 2})]
    history = {"east": {"haze": pooled(stations)}}
    quote = calculator.quote_at(
        make_tariff(), history, {"haze": stations}, 1.31, 103.9, "cooked_food"
    )
    assert quote.local_risks[0].credibility == 0
    assert quote.expected_loss_days == pytest.approx(DAYS * 0.5, abs=0.01)


def test_credibility_blends_station_and_region():
    """Worked by hand: within-station variance 0.25, between-station variance 0.0625, so K = 4."""
    stations = [site("a", 1.30, {50.0: 3, 250.0: 1}), site("b", 1.45, {50.0: 1, 250.0: 3})]
    tariff = make_tariff()
    assert calculator.credibility_constant(tariff.hazards[0], stations) == pytest.approx(4)
    history = {"east": {"haze": pooled(stations)}}
    quote = calculator.quote_at(tariff, history, {"haze": stations}, 1.31, 103.9, "cooked_food")
    haze = quote.local_risks[0]
    assert haze.credibility == 0.5
    assert haze.loss_days == pytest.approx(DAYS * (0.5 * 0.25 + 0.5 * 0.5), abs=0.01)


def test_a_place_reads_as_many_stations_as_its_trigger():
    tariff = make_tariff()
    tariff.hazards[0].sites_used = 2
    stations = [
        site("a", 1.30, {50.0: 10}),
        site("b", 1.32, {250.0: 10}),
        site("c", 1.45, {250.0: 10}),
    ]
    history = {"east": {"haze": pooled(stations)}}
    quote = calculator.quote_at(tariff, history, {"haze": stations}, 1.30, 103.9, "cooked_food")
    assert quote.local_risks[0].stations == ["a", "b"]
