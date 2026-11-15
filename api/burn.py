"""Per-site burn: what one business would have been paid, year by year, on real readings.

The batch version with figures is scripts/burn_analysis.py; this module answers one place at
a time for the SME dashboard and the map's time machine. Both read data/processed/
day_readings.csv.gz through api/readings.py, the rule every payout uses. A hazard a payout
would wait for reads 0 in a replay.
"""

from __future__ import annotations

import csv
import gzip
from collections import defaultdict
from pathlib import Path

from api import calculator, readings
from api.models import Tariff

REPO_ROOT = Path(__file__).resolve().parent.parent
DAY_READINGS_PATH = REPO_ROOT / "data" / "processed" / "day_readings.csv.gz"
FIRST_FULL_YEAR = calculator.FIRST_FULL_YEAR
# Days below the lowest band of every one of these hazards are skipped before the tariff is
# asked: they cannot pay.
BELOW_EVERY_BAND = ("haze", "rain", "heat")

DayTable = dict[str, dict[str, dict[str, float]]]


def load_day_table() -> DayTable:
    """All historical daily readings: {day: {kind: {site: value}}}."""
    table: DayTable = {}
    with gzip.open(DAY_READINGS_PATH, "rt", newline="") as file:
        for row in csv.DictReader(file):
            table.setdefault(row["day"], {}).setdefault(row["kind"], {})[row["site"]] = float(
                row["value"]
            )
    return table


def lowest_bands(tariff: Tariff) -> dict[str, float]:
    return {h.key: h.bands[0].at_least for h in tariff.hazards if h.key in BELOW_EVERY_BAND}


def site_burn(
    table: DayTable,
    where: readings.Place,
    tariff: Tariff,
    product_key: str,
    tier_key: str,
    takings_sgd: float,
    premium_yearly_sgd: float,
) -> dict:
    """One business through every recorded day: payouts (within the tier's yearly limit),
    losses, perils, from FIRST_FULL_YEAR, the first year with rain recorded all year.

    trigger_days have a loss; payout_days are the ones paid before the yearly limit ran out.
    loss_ratio is payouts over the premium before GST, as insurers and the MAS returns count it;
    premium_sgd is what the customer pays, GST included. The premium is the business's quote,
    priced on the same readings (calculator.tier_quote), so the price and this replay agree:
    the quote's proof is this replay's years.
    """
    tier = calculator.find(tariff.tiers, tier_key, "tier")
    cap_sgd = tier.daily_payout_sgd * tier.max_paid_days_per_year
    premium_before_gst = premium_yearly_sgd / (1 + tariff.pricing.gst_rate)
    lowest = lowest_bands(tariff)
    rule = readings.station_rule(tariff)
    years: dict[int, dict] = defaultdict(
        lambda: {"trigger_days": 0, "payout_days": 0, "paid": 0.0, "lost": 0.0, "haze": 0.0,
                 "rain": 0.0, "heat": 0.0}
    )
    for day in sorted(table):
        year = int(day[:4])
        day_readings = readings.day_readings_at(table[day], where, rule)
        if all(day_readings[key] < level for key, level in lowest.items()):
            continue
        assessment = calculator.assess(tariff, product_key, tier_key, day_readings)
        if assessment.loss_percent <= 0:
            continue
        entry = years[year]
        room = max(0.0, cap_sgd - entry["paid"])
        paid = min(assessment.payout_sgd, room)
        entry["trigger_days"] += 1
        entry["payout_days"] += paid > 0
        entry["paid"] += paid
        entry["lost"] += assessment.loss_percent / 100 * takings_sgd
        for part in assessment.hazards:
            if part.loss_percent > 0:
                entry[part.hazard] += paid * (
                    part.loss_percent / max(assessment.loss_percent, 0.01)
                )
    last_year = max((int(day[:4]) for day in table), default=FIRST_FULL_YEAR)
    rows = []
    for year in range(FIRST_FULL_YEAR, last_year + 1):
        entry = years[year]
        rows.append({
            "year": year,
            "trigger_days": entry["trigger_days"],
            "payout_days": entry["payout_days"],
            "paid_sgd": round(entry["paid"], 2),
            "est_lost_sgd": round(entry["lost"], 2),
            "premium_sgd": round(premium_yearly_sgd, 2),
            "loss_ratio": round(entry["paid"] / premium_before_gst, 3),
            "by_hazard_sgd": {k: round(entry[k], 2) for k in ("haze", "rain", "heat")},
        })
    paid = sum(r["paid_sgd"] for r in rows)
    lost = sum(r["est_lost_sgd"] for r in rows)
    return {
        "years": rows,
        "totals": {
            "from_year": FIRST_FULL_YEAR,
            "to_year": last_year,
            "trigger_days": sum(r["trigger_days"] for r in rows),
            "paid_sgd": round(paid, 2),
            "est_lost_sgd": round(lost, 2),
            "premium_sgd": round(premium_yearly_sgd * len(rows), 2),
            "loss_ratio": round(paid / (premium_before_gst * len(rows)), 3) if rows else 0.0,
            "by_hazard_sgd": {
                k: round(sum(r["by_hazard_sgd"][k] for r in rows), 2)
                for k in ("haze", "rain", "heat")
            },
        },
        "assumptions": {
            "takings_sgd_per_day": takings_sgd,
            "note": "Estimated losses are the tariff's loss score times the daily takings; "
            "heat readings exist from 2025, flood is priced at the tariff's assumed days. "
            "Payouts over premium (loss_ratio) use the premium before GST.",
        },
    }
