from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from api import calculator
from api.calculator import Replay
from api.models import PremiumShares, Tariff

DAYS = calculator.DAYS_PER_YEAR
CLEAN, HAZY = 50.0, 250.0  # PSI below every band, and at the top band (severity 1)


def replay(*years: tuple[int, int, int], unfed_years: tuple[int, ...] = ()) -> Replay:
    """Haze readings from 1 Jan of each year: (year, recorded days, hazy days first)."""
    days, haze, fed = [], [], []
    for year, recorded, hazy in years:
        first = np.datetime64(f"{year}-01-01")
        days += [first + np.timedelta64(offset, "D") for offset in range(recorded)]
        haze += [HAZY] * hazy + [CLEAN] * (recorded - hazy)
        fed += [year not in unfed_years] * recorded
    return Replay(
        days=np.array(days, dtype="datetime64[D]"),
        readings={"haze": np.array(haze)},
        fed={"haze": np.array(fed)},
    )


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
            "distribution_expense_ratio": 0,
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


def test_premium_prices_the_average_year_of_the_replay():
    quote = calculator.quote(make_tariff(), "cooked_food", "east", replay((2017, 365, 10)))
    loss_days = 10 * DAYS / 365
    assert quote.expected_loss_days == pytest.approx(loss_days, abs=0.01)
    tier_1, tier_2 = quote.tiers
    assert tier_1.yearly_premium_sgd == pytest.approx(loss_days * 10, abs=0.01)
    assert tier_2.weekly_premium_sgd > tier_1.weekly_premium_sgd


def test_a_part_year_is_annualised():
    quote = calculator.quote(make_tariff(), "cooked_food", "east", replay((2018, 100, 5)))
    assert quote.expected_loss_days == pytest.approx(5 * DAYS / 100, abs=0.01)


def test_the_limit_caps_each_year_not_the_average_year():
    tariff = make_tariff()
    tariff.tiers[0].max_paid_days_per_year = 5
    quote = calculator.quote(tariff, "cooked_food", "east", replay((2017, 365, 10), (2018, 365, 2)))
    tier_1 = quote.tiers[0]
    two_years = [min(10 * DAYS / 365, 5), 2 * DAYS / 365]
    assert tier_1.expected_paid_days == pytest.approx(sum(two_years) / 2, abs=0.01)
    assert tier_1.max_payout_per_year_sgd == 50


def test_a_year_before_a_feed_started_takes_its_average_year():
    places = replay((2016, 365, 0), (2017, 365, 10), (2018, 365, 20), unfed_years=(2016,))
    quote = calculator.quote(make_tariff(), "cooked_food", "east", places)
    fed_average = 30 * DAYS / 730
    assert quote.loss_day_parts["haze"] == pytest.approx(fed_average, abs=0.01)
    assert quote.expected_loss_days == pytest.approx(fed_average, abs=0.01)


def test_loads_raise_the_premium():
    pricing = {
        "uncertainty_load": 0.1,
        "catastrophe_load": 0.1,
        "expense_ratio": 0.2,
        "gst_rate": 0.09,
        "distribution_expense_ratio": 0.1,
    }
    quote = calculator.quote(
        make_tariff(pricing=pricing), "cooked_food", "east", replay((2017, 365, 365))
    )
    risk_cost = DAYS * 10
    assert quote.tiers[0].yearly_premium_sgd == pytest.approx(
        risk_cost * 1.2 / 0.8 * 1.09, abs=0.01
    )


def test_assumed_days_add_to_every_year():
    tariff = make_tariff()
    tariff.hazards[1].assumed_days_per_year = 2
    quote = calculator.quote(tariff, "dry_goods", "east", replay((2017, 365, 0)))
    assert quote.expected_loss_days == 2
    assert quote.loss_day_parts == {"haze": 0, "closure": 2}


def test_hazard_without_history_or_assumed_days_cannot_be_priced():
    tariff = make_tariff()
    tariff.hazards[1].assumed_days_per_year = None
    with pytest.raises(calculator.MissingHistory):
        calculator.check_prices(tariff, [replay((2017, 365, 0))])


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


def test_a_stall_is_suggested_tier_1_whatever_its_rent():
    tariff = make_tariff(rent=RENT)
    for monthly in (250, 300, 1000):
        assert calculator.centre_rent(tariff, bid_record(monthly), 0).recommended_tier == "tier_1"


def test_covers_rent_says_whether_tier_1_pays_a_days_rent():
    tariff = make_tariff(rent=RENT)
    # 250 a month over 25 days is 10 a day: Tier 1 pays exactly that.
    assert calculator.centre_rent(tariff, bid_record(250), 0).covers_rent is True
    # 1,000 a month is 40 a day, more than Tier 1 pays for a full day.
    rent = calculator.centre_rent(tariff, bid_record(1000), 0)
    assert (rent.covers_rent, rent.rent_per_day_sgd) == (False, 40)


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


def test_km_between_one_degree_of_latitude():
    assert calculator.km_between(1.0, 103.9, 2.0, 103.9) == pytest.approx(111.2, abs=0.1)


def test_a_quote_says_how_many_loss_days_each_hazard_brings():
    quote = calculator.quote(make_tariff(), "cooked_food", "east", replay((2017, 365, 10)))
    assert set(quote.loss_day_parts) == {"haze", "closure"}
    assert sum(quote.loss_day_parts.values()) == pytest.approx(quote.expected_loss_days, abs=0.02)
    assert quote.product_factor == pytest.approx(
        calculator.product_factor(make_tariff().products[0]), abs=0.001
    )


INCOME_PRICING = {"uncertainty_load": 0.15, "catastrophe_load": 0.1, "expense_ratio": 0.25,
                  "gst_rate": 0.09, "distribution_expense_ratio": 0.15}


def test_each_tier_shows_the_five_parts_of_its_premium_then_gst():
    tariff = make_tariff(pricing=INCOME_PRICING)
    quote = calculator.quote(tariff, "cooked_food", "east", replay((2017, 365, 13)))
    for tier in quote.tiers:
        steps = {step.key: step.amount_sgd for step in tier.build_up}
        assert list(steps) == [
            "expected_payouts", "reinsurance", "management", "distribution", "profit", "gst",
        ]
        assert round(sum(steps.values()), 2) == tier.yearly_premium_sgd
        before_gst = tier.yearly_premium_sgd / 1.09
        shares = {key: amount / before_gst for key, amount in steps.items() if key != "gst"}
        assert shares == pytest.approx({
            "expected_payouts": 0.60, "reinsurance": 0.06, "management": 0.10,
            "distribution": 0.15, "profit": 0.09,
        }, abs=0.001)
        assert steps["gst"] == pytest.approx(before_gst * 0.09, abs=0.01)


def test_price_per_day_and_how_many_times_the_premium_the_limit_is():
    tariff = make_tariff(pricing=INCOME_PRICING)
    tariff.tiers[0].max_paid_days_per_year = 30
    tier_1 = calculator.quote(tariff, "cooked_food", "east", replay((2017, 365, 5))).tiers[0]
    assert tier_1.price_per_day_sgd == round(tier_1.yearly_premium_sgd / 365, 2)
    assert tier_1.cover_multiple == round(300 / tier_1.yearly_premium_sgd, 1)
    assert tier_1.sold_directly


TIER_SHARES = {"expected_payouts": 0.6, "reinsurance": 0.06, "management": 0.1,
               "distribution": 0.15, "profit": 0.09}


def test_a_tier_costing_more_than_half_its_limit_is_not_sold_directly():
    tariff = make_tariff(pricing=INCOME_PRICING)
    for tier in tariff.tiers:
        tier.max_paid_days_per_year = 10
        tier.premium_shares = PremiumShares(**TIER_SHARES)
    tier_1 = calculator.quote(tariff, "cooked_food", "east", replay((2017, 365, 5))).tiers[0]
    assert tier_1.yearly_premium_sgd > 0.5 * tier_1.max_payout_per_year_sgd
    assert not tier_1.sold_directly
    tariff.pricing.refer_above_limit_share = 1.0
    tier_1 = calculator.quote(tariff, "cooked_food", "east", replay((2017, 365, 5))).tiers[0]
    assert tier_1.sold_directly


def test_a_tier_without_shares_is_sold_directly_as_before_the_guardrail():
    tariff = make_tariff(pricing=INCOME_PRICING)
    for tier in tariff.tiers:
        tier.max_paid_days_per_year = 10
    tier_1 = calculator.quote(tariff, "cooked_food", "east", replay((2017, 365, 5))).tiers[0]
    assert tier_1.yearly_premium_sgd > 0.5 * tier_1.max_payout_per_year_sgd
    assert tier_1.sold_directly


def test_a_tariff_saved_before_the_split_keeps_its_running_costs():
    pricing = {"uncertainty_load": 0.15, "catastrophe_load": 0.1, "expense_ratio": 0.12,
               "gst_rate": 0.09}
    tariff = make_tariff(pricing=pricing)
    assert tariff.pricing.distribution_expense_ratio == 0.12


def test_the_proof_replays_what_the_tier_would_have_paid_each_year():
    tariff = make_tariff(pricing=INCOME_PRICING)
    for tier in tariff.tiers:
        tier.max_paid_days_per_year = 30
    places = replay(
        (2015, 365, 40), (2017, 365, 4), (2018, 365, 0), (2019, 365, 6), (2026, 300, 50)
    )
    tier_1 = calculator.quote(tariff, "cooked_food", "east", places).tiers[0]
    proof = tier_1.proof
    assert (proof.years_replayed, proof.years_paid) == (4, 3)
    assert proof.payout_days_per_year == pytest.approx((4 + 0 + 6) / 3, abs=0.05)
    assert proof.typical_year_paid_sgd == 40
    assert proof.paid_2026_sgd == 300
    assert proof.haze_2015_like_sgd == 300
    assert proof.payback_share == pytest.approx(0.6 / 1.09, abs=0.001)


def test_no_proof_without_a_full_replay_year():
    tier_1 = calculator.quote(make_tariff(), "cooked_food", "east", replay((2026, 300, 5))).tiers[0]
    assert tier_1.proof is None


def test_local_risks_say_what_the_place_reads_next_to_its_region():
    place, region = replay((2017, 365, 20)), replay((2017, 365, 10))
    quote = calculator.quote(
        make_tariff(), "cooked_food", "east", place, region, {"haze": ["east"]}
    )
    (haze,) = quote.local_risks
    assert (haze.stations, haze.station_days, haze.credibility) == (["east"], 365, 1.0)
    assert haze.loss_days == quote.loss_day_parts["haze"] == pytest.approx(20 * DAYS / 365, 0.01)
    assert haze.region_loss_days == pytest.approx(10 * DAYS / 365, abs=0.01)
