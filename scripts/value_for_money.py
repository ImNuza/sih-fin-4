"""Value for money of every Payung tier: what a customer pays a year against what the tier pays
back, and how a customer who saved the premium instead would have done.

The self-insure test compares two customers at the same place. One buys the tier every year. The
other puts the same premium aside every year and pays themself, from that pot, what the tier
would have paid ("saved the premium instead"). Each year's payout is the tier's: min(that year's
loss-days, the yearly limit) x the daily amount, from

- the model history (api/model_history.py): 46 full years, 1980 to 2025, at the hawker centre (a
  shop reads its nearest centre, as /api/model/history does). Measured NEA readings where they
  exist, rain and heat rebuilt by the trained models before that; haze is not rebuilt before
  Apr 2014, so the years before 2014 have no haze.
- the replay (calculator.paid_years over api/place_days.py): 2017 to 2026 at the place itself,
  2026 to the last day of data.

Neither history holds a closure order, which the price assumes at 2 days a year. So each place
also gets two shocks: a 40-day lockdown, and a 2015-type haze year (the quote's estimate).

Every price, payout and the offered flag come from api/calculator.py under
api/default_tariff.json; nothing is worked out twice.

Two tests per tier and place:
- offered: the tariff's rule, as the quote applies it (premium below the yearly limit and at
  most refer_above_limit_share of it).
- self_insure_pass: offered, and a 2015-type weather year pays back more than the yearly
  premium. One year of saving is one premium; if the worst weather year on record pays less, a
  customer who saved instead could have paid themself for it.
A what-if prices each tier at the payout shares a 5% selling commission would leave (Income's
quote, docs/notes/distribution-proposal-2026-11-15.md [S27]): the tier's distribution share
less 5 points goes to expected payouts. The tariff is not changed.

Usage:
    uv run scripts/value_for_money.py    (after build_place_years.py and python -m ml.serving)

Reads  data/processed/place_day_readings.npz, data/processed/site_hazard_readings.csv,
       data/processed/day_readings.csv.gz, data/processed/map_static.json,
       data/processed/model_history.npz, data/processed/hawker_rent.csv, api/default_tariff.json
Writes data/processed/value_for_money.csv          four places, every tier, the full test
       data/processed/value_for_money_places.csv   every hawker centre and postcode area, every
                                                   product and tier sold in the pilot
       data/processed/value_for_money_shares.csv   what each share of the limit would hide
       data/processed/value_for_money_tests.csv    how many places pass each test, per product
                                                   and tier
       data/processed/value_for_money_prices.csv   the cheapest tier's price by business type
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from dgs import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from api import calculator, model_history, place_days, postcodes, readings  # noqa: E402
from api.burn import load_day_table  # noqa: E402
from api.main import (  # noqa: E402
    DEFAULT_TARIFF_PATH, HISTORY_PATH, MAP_STATIC_PATH, RENT_PATH, load_rent, load_sites,
    rent_table,
)
from api.models import Quote, Tariff, TierQuote  # noqa: E402

PROC_DIR = REPO_ROOT / "data" / "processed"

MAXWELL = "Maxwell Food Centre (Kim Hua Market)"
SHOP_POSTCODE = "380123"
HAWKER_PRODUCT = "cooked_food"
SHOP_PRODUCT = "packaged_food"
# The pilot sells to hawker stalls and shops, not platform workers (api/onboarding.py).
PILOT_PRODUCTS = ("cooked_food", "fresh_produce", "flowers", "packaged_food", "general_goods")
REPLAY_YEARS = range(calculator.FIRST_FULL_YEAR, calculator.PROOF_YEAR + 1)
# The default tariff prices a closure as one 40-day lockdown every 20 years.
LOCKDOWN_DAYS = 40
# "If there is haze all next year": every day at the first unhealthy PSI band.
HAZE_ALL_YEAR_PSI = 101
DAYS_IN_YEAR = 365
ONE_IN_TEN = 0.9
MONTHS_PER_YEAR = 12
# Shares of the yearly limit tried as the stricter rule; the tariff's own is among them.
SHARES_TRIED = (1.0, 0.5, 0.45, 0.4, 0.35)
# Income quoted about 5% commission for Payung, against a usual 15% (distribution proposal, S27).
LOW_COMMISSION = 0.05
CLOSURE = "closure"


def saver(premium_sgd: float, paid_sgd: np.ndarray) -> dict:
    """The customer who saved the premium instead: the pot after every year, from the first.

    pot_ran_dry_from_starts counts the start years from which a saver's pot would have gone
    below zero at some point: a year it had to pay more than it held.
    """
    pot = np.cumsum(premium_sgd - paid_sgd)
    dry_starts = sum(
        bool((np.cumsum(premium_sgd - paid_sgd[start:]) < 0).any())
        for start in range(len(paid_sgd))
    )
    worst = int(np.argmax(paid_sgd))
    return {
        "years": len(paid_sgd),
        "premiums_sgd": round(premium_sgd * len(paid_sgd), 2),
        "payouts_sgd": round(float(paid_sgd.sum()), 2),
        "saved_instead_sgd": round(float(pot[-1]), 2),
        "lowest_pot_sgd": round(float(pot.min()), 2),
        "pot_ran_dry_from_starts": dry_starts,
        "years_paid_more_than_premium": int((paid_sgd > premium_sgd).sum()),
        "years_paid_nothing": int((paid_sgd == 0).sum()),
        "worst_year_sgd": round(float(paid_sgd[worst]), 2),
        "one_in_ten_year_sgd": round(float(np.quantile(paid_sgd, ONE_IN_TEN)), 2),
    }


def model_paid(
    history: model_history.ModelHistory, centre: str, tariff: Tariff, product: str
) -> tuple[np.ndarray, np.ndarray]:
    """Loss-days in each full model year at a centre, and the years, scored as
    model_history.centre_years scores them."""
    combined, _ = model_history.day_losses(
        history, np.array([history.row_of[centre]]), tariff, product
    )
    loss_days, years = model_history.yearly_sums(history, combined[0])
    full = years <= history.last_full_year
    return loss_days[full], years[full]


def replay_paid(
    tariff: Tariff, product: str, replay: calculator.Replay
) -> dict[str, np.ndarray]:
    """What each tier would have paid at the place in each replay year, as a payout pays."""
    losses = calculator.replay_losses(
        tariff, calculator.find(tariff.products, product, "product"), replay
    )
    out = {}
    for tier in tariff.tiers:
        paid = calculator.paid_years(losses, tier)
        out[tier.key] = np.array([paid[year][0] for year in REPLAY_YEARS])
    return out


def haze_all_year_sgd(tariff: Tariff, product: str, tier: TierQuote) -> float:
    day = calculator.assess(tariff, product, tier.tier, {"haze": HAZE_ALL_YEAR_PSI})
    paid_days = min(day.loss_percent / 100 * DAYS_IN_YEAR, tier.max_payout_per_year_sgd
                    / tier.daily_payout_sgd)
    return round(paid_days * tier.daily_payout_sgd, 2)


def low_commission_premium(tariff: Tariff, tier: TierQuote) -> float:
    """The yearly premium if selling cost LOW_COMMISSION and the rest of the distribution share
    went to expected payouts."""
    shares = calculator.find(tariff.tiers, tier.tier, "tier").premium_shares
    payouts = shares.expected_payouts + shares.distribution - LOW_COMMISSION
    return round(tier.yearly_premium_sgd * shares.expected_payouts / payouts, 2)


def tests(tariff: Tariff, tier: TierQuote) -> dict:
    """The self-insure test at today's price and at the low-commission price."""
    haze_2015 = tier.proof.haze_2015_like_sgd
    cheaper = low_commission_premium(tariff, tier)
    return {
        "haze_2015_like_sgd": haze_2015,
        "haze_2015_like_premium_multiple": round(haze_2015 / tier.yearly_premium_sgd, 2),
        "self_insure_pass": tier.offered and haze_2015 > tier.yearly_premium_sgd,
        "yearly_premium_at_5pc_commission_sgd": cheaper,
        "self_insure_pass_at_5pc_commission": tier.offered and haze_2015 > cheaper,
    }


def tier_basics(tier: TierQuote) -> dict:
    return {
        "tier": tier.tier,
        "daily_payout_sgd": tier.daily_payout_sgd,
        "monthly_premium_sgd": round(tier.yearly_premium_sgd / MONTHS_PER_YEAR, 2),
        "weekly_premium_sgd": tier.weekly_premium_sgd,
        "yearly_premium_sgd": tier.yearly_premium_sgd,
        "max_payout_per_year_sgd": tier.max_payout_per_year_sgd,
        "premium_share_of_max": round(tier.yearly_premium_sgd / tier.max_payout_per_year_sgd, 3),
        "expected_payout_sgd": round(tier.expected_paid_days * tier.daily_payout_sgd, 2),
        "offered": tier.offered,
    }


def full_rows(
    tariff: Tariff, place: str, kind: str, product: str, priced: Quote,
    replay: calculator.Replay, model_loss_days: np.ndarray, model_from: str,
) -> list[dict]:
    """The value-for-money table for one place: every tier, the shocks and both savers."""
    by_replay = replay_paid(tariff, product, replay)
    rows = []
    for tier in priced.tiers:
        premium = tier.yearly_premium_sgd
        limit_days = tier.max_payout_per_year_sgd / tier.daily_payout_sgd
        lockdown = LOCKDOWN_DAYS * tier.daily_payout_sgd
        model = saver(premium, np.minimum(model_loss_days, limit_days) * tier.daily_payout_sgd)
        replayed = saver(premium, by_replay[tier.tier])
        rows.append({
            "place": place, "kind": kind, "product": product, "model_history_from": model_from,
            **tier_basics(tier),
            "typical_year_paid_sgd": tier.proof.typical_year_paid_sgd,
            "paid_2026_sgd": tier.proof.paid_2026_sgd,
            "lockdown_40_days_sgd": round(lockdown, 2),
            **tests(tariff, tier),
            "haze_all_year_sgd": haze_all_year_sgd(tariff, product, tier),
            "lockdown_premium_years": round(lockdown / premium, 1),
            "saver_short_after_lockdown_in_year_1_sgd": round(max(lockdown - premium, 0), 2),
            "saver_short_after_2015_like_year_1_sgd": round(
                max(tier.proof.haze_2015_like_sgd - premium, 0), 2
            ),
            **{f"model_{key}": value for key, value in model.items()},
            **{f"replay_{key}": value for key, value in replayed.items()},
        })
    return rows


def place_rows(
    tariff: Tariff, name: str, kind: str, region: str, replay: calculator.Replay,
    priced: dict[str, Quote], rent: str,
) -> list[dict]:
    """One place's every product and tier, with the weather that prices them, the worst replay
    year and both tests."""
    rows = []
    for product, quote in priced.items():
        parts = quote.loss_day_parts
        worst = {key: paid.max() for key, paid in replay_paid(tariff, product, replay).items()}
        for tier in quote.tiers:
            rows.append({
                "place": name, "kind": kind, "region": region, "rent_class": rent,
                "product": product, **tier_basics(tier),
                "haze_loss_days": parts["haze"], "rain_loss_days": parts["rain"],
                "heat_loss_days": parts["heat"],
                # The closure order is not scaled by product, so it weighs most where weather
                # costs the product little.
                "closure_share_of_expected_payout": round(
                    min(parts[CLOSURE] / tier.expected_paid_days, 1.0), 3
                ),
                "replay_worst_year_premium_multiple": round(
                    worst[tier.tier] / tier.yearly_premium_sgd, 2
                ),
                "best_value": tier.best_value,
                **tests(tariff, tier),
            })
    return rows


def shares_table(places: pd.DataFrame) -> pd.DataFrame:
    """For each share of the yearly limit, the tier/place pairs it would hide (a premium over
    the share; at 1.0, at or over the whole limit), and the hawker centres that lose a tier."""
    rows = []
    for share in SHARES_TRIED:
        over = (places["premium_share_of_max"] >= share) if share == 1.0 else (
            places["premium_share_of_max"] > share)
        hidden = places[over]
        centres = hidden[hidden["kind"] == "hawker centre"]
        for product in PILOT_PRODUCTS:
            in_product = hidden[hidden["product"] == product]
            centre_tiers = centres[centres["product"] == product]
            lost = centre_tiers.groupby("place")["tier"].apply(lambda t: "+".join(sorted(t)))
            rows.append({
                "share": share,
                "product": product,
                "pairs": int((places["product"] == product).sum()),
                "pairs_hidden": len(in_product),
                "centres_losing_a_tier": int(centre_tiers["place"].nunique()),
                "areas_losing_a_tier": int(
                    in_product[in_product["kind"] == "postcode area"]["place"].nunique()
                ),
                "centres": "; ".join(f"{place} ({tiers})" for place, tiers in lost.items()),
            })
    return pd.DataFrame(rows)


def tests_table(places: pd.DataFrame) -> pd.DataFrame:
    """Per kind of place, product and tier: how many places pass each test."""
    grouped = places.groupby(["kind", "product", "tier"])
    return pd.DataFrame({
        "places": grouped.size(),
        "offered": grouped["offered"].sum(),
        "self_insure_pass": grouped["self_insure_pass"].sum(),
        "self_insure_pass_at_5pc_commission": grouped["self_insure_pass_at_5pc_commission"].sum(),
        "haze_2015_like_multiple_median": grouped["haze_2015_like_premium_multiple"].median(),
        "replay_worst_year_multiple_max": grouped["replay_worst_year_premium_multiple"].max(),
        "closure_share_median": grouped["closure_share_of_expected_payout"].median(),
    }).reset_index()


def prices_table(places: pd.DataFrame) -> pd.DataFrame:
    """The cheapest tier offered at each place, per business type and product: median, lowest
    and highest monthly and weekly price across the places."""
    offered = places[places["offered"]]
    cheapest = offered.loc[offered.groupby(["kind", "place", "product"])["yearly_premium_sgd"]
                           .idxmin()]
    rows = []
    for (kind, product), group in cheapest.groupby(["kind", "product"]):
        rows.append({
            "kind": kind, "product": product, "places": len(group),
            "cheapest_tier": "+".join(sorted(group["tier"].unique())),
            "monthly_median_sgd": round(group["monthly_premium_sgd"].median(), 2),
            "monthly_lowest_sgd": group["monthly_premium_sgd"].min(),
            "monthly_highest_sgd": group["monthly_premium_sgd"].max(),
            "weekly_median_sgd": round(group["weekly_premium_sgd"].median(), 2),
            "weekly_lowest_sgd": group["weekly_premium_sgd"].min(),
            "weekly_highest_sgd": group["weekly_premium_sgd"].max(),
            "lowest_at": group.loc[group["weekly_premium_sgd"].idxmin(), "place"],
        })
    return pd.DataFrame(rows)


def main() -> None:
    tariff = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
    static = json.loads(MAP_STATIC_PATH.read_text())
    days = place_days.PlaceDays(load_sites(HISTORY_PATH), load_day_table, place_days.PLACE_DAYS_PATH)
    rule = readings.station_rule(tariff)
    history = model_history.load()
    rents = rent_table(tariff, load_rent(RENT_PATH)).centres
    centres = {c["name"]: c for c in static["hawker_centres"]}
    by_sector = postcodes.centres_by_sector(static["hawker_centres"])

    def priced_at(region: str, lat: float, lng: float) -> tuple[calculator.Replay, dict]:
        replay = days.replay(rule, region, lat, lng)
        return replay, {p: calculator.quote(tariff, p, region, replay) for p in PILOT_PRODUCTS}

    all_rows, quotes, replays = [], {}, {}
    for name, centre in centres.items():
        replays[name], quotes[name] = priced_at(centre["region"], centre["lat"], centre["lng"])
        rent = rents[name].rent_class_label if name in rents else ""
        all_rows += place_rows(tariff, name, "hawker centre", centre["region"], replays[name],
                               quotes[name], rent)
    for sector in sorted(postcodes.SECTOR_REGION):
        point = postcodes.area_point(f"{sector}0000", by_sector, static["region_points"])
        replay, priced = priced_at(point["region"], point["lat"], point["lng"])
        all_rows += place_rows(tariff, f"postal sector {sector}", "postcode area",
                               point["region"], replay, priced, "")
    places = pd.DataFrame(all_rows)

    tier_1 = sorted(centres, key=lambda n: quotes[n][HAWKER_PRODUCT].tiers[0].yearly_premium_sgd)
    median_centre, dearest_centre = tier_1[len(tier_1) // 2], tier_1[-1]
    shop = postcodes.area_point(SHOP_POSTCODE, by_sector, static["region_points"])
    shop_replay, shop_quotes = priced_at(shop["region"], shop["lat"], shop["lng"])
    shop_centre = min(centres.values(), key=lambda c: calculator.km_between(
        shop["lat"], shop["lng"], c["lat"], c["lng"]))["name"]

    table = []
    for label, name in (("Maxwell", MAXWELL), ("median centre", median_centre),
                        ("most expensive centre", dearest_centre)):
        loss_days, years = model_paid(history, name, tariff, HAWKER_PRODUCT)
        table += full_rows(tariff, f"{name} ({label})", "hawker centre", HAWKER_PRODUCT,
                           quotes[name][HAWKER_PRODUCT], replays[name], loss_days, name)
    loss_days, years = model_paid(history, shop_centre, tariff, SHOP_PRODUCT)
    table += full_rows(tariff, f"shop at postcode {SHOP_POSTCODE} ({shop['basis']})", "shop",
                       SHOP_PRODUCT, shop_quotes[SHOP_PRODUCT], shop_replay, loss_days,
                       shop_centre)
    table = pd.DataFrame(table)

    table.to_csv(PROC_DIR / "value_for_money.csv", index=False)
    places.to_csv(PROC_DIR / "value_for_money_places.csv", index=False)
    shares = shares_table(places)
    shares.to_csv(PROC_DIR / "value_for_money_shares.csv", index=False)
    passes = tests_table(places)
    passes.to_csv(PROC_DIR / "value_for_money_tests.csv", index=False)
    prices = prices_table(places)
    prices.to_csv(PROC_DIR / "value_for_money_prices.csv", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    print(f"Model years {years[0]}-{years[-1]}; replay years {REPLAY_YEARS[0]}-{REPLAY_YEARS[-1]}")
    print(f"Median centre {median_centre}; most expensive {dearest_centre}; "
          f"shop reads {shop_centre}")
    print(table.T.to_string())
    print(shares.drop(columns="centres").to_string())
    print(passes.to_string())
    print(prices.to_string())


if __name__ == "__main__":
    main()
