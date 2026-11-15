"""FEAT fairness check: how far the same cover's price moves between places.

MAS's FEAT principles (2018) ask that a model does not systematically disadvantage a group, and
the brief adds that pricing "must not price out the groups that most need cover". This script
prices every product and tier with the live calculator:
    - in each of the 5 PSI regions (what the buy flow charges today);
    - at each of the 103 hawker centres, from its own nearest stations (api/calculator.quote_at).
For each product and tier it reports the cheapest, median and dearest weekly premium and the
ratio of dearest to cheapest. It then checks whether centres with lower stall rent, a rough
stand-in for poorer stallholders, pay more for the same cover: the rank correlation between
weekly premium and the median NEA rent bid, and the median premium in the lowest and highest
rent quarters. No personal data goes into any price, so the check is about place only.

Usage:
    uv run scripts/feat_price_spread.py

Reads  data/processed/site_hazard_readings.csv, data/processed/map_static.json,
       data/processed/hawker_rent.csv, api/default_tariff.json
Writes data/processed/price_spread.csv     one row per product and tier
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from dgs import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
from api import calculator  # noqa: E402
from api.main import DEFAULT_TARIFF_PATH, HISTORY_PATH, load_history  # noqa: E402
from api.models import Tariff  # noqa: E402

PROC_DIR = REPO_ROOT / "data" / "processed"
OUT_PATH = PROC_DIR / "price_spread.csv"
RENT_QUARTER = 0.25
FAR_FROM_REGION = 1.5      # a centre priced 1.5 times its region's price or more is flagged


def place_prices(tariff: Tariff, history, sites, centres: list[dict]) -> pd.DataFrame:
    rows = []
    for centre in centres:
        for product in tariff.products:
            quote = calculator.quote_at(
                tariff, history, sites, centre["lat"], centre["lng"], product.key
            )
            rows += [{"centre": centre["name"], "region": centre["region"], "product": product.key,
                      "tier": t.tier, "weekly_sgd": t.weekly_premium_sgd} for t in quote.tiers]
    return pd.DataFrame(rows)


def region_prices(tariff: Tariff, history) -> pd.DataFrame:
    rows = []
    for region in history:
        for product in tariff.products:
            quote = calculator.quote(tariff, history, region, product.key)
            rows += [{"region": region, "product": product.key, "tier": t.tier,
                      "weekly_sgd": t.weekly_premium_sgd} for t in quote.tiers]
    return pd.DataFrame(rows)


def spread_row(by_place: pd.DataFrame, by_region: pd.DataFrame, rent: pd.Series) -> dict:
    cheapest = by_place.loc[by_place["weekly_sgd"].idxmin()]
    dearest = by_place.loc[by_place["weekly_sgd"].idxmax()]
    priced = by_place.join(rent, on="centre").dropna(subset=["median_bid_sgd"])
    low_rent = priced[priced["median_bid_sgd"] <= priced["median_bid_sgd"].quantile(RENT_QUARTER)]
    high_rent = priced[
        priced["median_bid_sgd"] >= priced["median_bid_sgd"].quantile(1 - RENT_QUARTER)
    ]
    to_region = by_place["weekly_sgd"] / by_place["region"].map(
        by_region.set_index("region")["weekly_sgd"]
    )
    return {
        "region_min_weekly_sgd": by_region["weekly_sgd"].min(),
        "region_max_weekly_sgd": by_region["weekly_sgd"].max(),
        "region_max_over_min": round(by_region["weekly_sgd"].max() / by_region["weekly_sgd"].min(), 2),
        "centre_min_weekly_sgd": cheapest["weekly_sgd"],
        "centre_median_weekly_sgd": round(by_place["weekly_sgd"].median(), 2),
        "centre_max_weekly_sgd": dearest["weekly_sgd"],
        "centre_max_over_min": round(dearest["weekly_sgd"] / cheapest["weekly_sgd"], 2),
        "centre_over_region_median": round(to_region.median(), 2),
        "centre_over_region_max": round(to_region.max(), 2),
        "centres_at_least_1_5x_region": int((to_region >= FAR_FROM_REGION).sum()),
        "cheapest_centre": cheapest["centre"],
        "dearest_centre": dearest["centre"],
        "price_rent_rank_correlation": round(
            priced["weekly_sgd"].rank().corr(priced["median_bid_sgd"].rank()), 2
        ),
        "low_rent_quarter_median_weekly_sgd": round(low_rent["weekly_sgd"].median(), 2),
        "high_rent_quarter_median_weekly_sgd": round(high_rent["weekly_sgd"].median(), 2),
        "centres_with_rent": len(priced),
    }


def main() -> None:
    tariff = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
    history, sites = load_history(HISTORY_PATH)
    centres = json.loads((PROC_DIR / "map_static.json").read_text())["hawker_centres"]
    rent = pd.read_csv(PROC_DIR / "hawker_rent.csv").set_index("centre")["median_bid_sgd"]
    places, regions = place_prices(tariff, history, sites, centres), region_prices(tariff, history)
    rows = []
    for (product, tier), by_place in places.groupby(["product", "tier"]):
        by_region = regions[(regions["product"] == product) & (regions["tier"] == tier)]
        rows.append({"product": product, "tier": tier, "centres": len(by_place),
                     **spread_row(by_place.reset_index(drop=True), by_region, rent)})
    spread = pd.DataFrame(rows)
    spread.to_csv(OUT_PATH, index=False)
    columns = ["product", "tier", "region_max_over_min", "centre_min_weekly_sgd",
               "centre_max_weekly_sgd", "centre_max_over_min", "centre_over_region_median",
               "centres_at_least_1_5x_region", "price_rent_rank_correlation",
               "low_rent_quarter_median_weekly_sgd", "high_rent_quarter_median_weekly_sgd"]
    print(spread[spread["tier"] == "tier_1"][columns].to_string(index=False))
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(spread)} rows")


if __name__ == "__main__":
    main()
