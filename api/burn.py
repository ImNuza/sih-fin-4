"""Per-site burn: what one business would have been paid, year by year, on real readings.

The batch version with figures is scripts/burn_analysis.py; this module answers one site
at a time for the SME dashboard and the map's time machine, from the same inputs:
data/processed/day_readings.csv.gz, data/processed/burn_site_map.json (each hawker centre's
gauge and station per year) and data/processed/burn_active_stations.json (the stations that
reported enough of each year, to place any other point the same way).
"""

from __future__ import annotations

import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path

from api import calculator
from api.models import Tariff

REPO_ROOT = Path(__file__).resolve().parent.parent
DAY_READINGS_PATH = REPO_ROOT / "data" / "processed" / "day_readings.csv.gz"
SITE_MAP_PATH = REPO_ROOT / "data" / "processed" / "burn_site_map.json"
ACTIVE_STATIONS_PATH = REPO_ROOT / "data" / "processed" / "burn_active_stations.json"
FIRST_FULL_YEAR = 2017

ActiveStations = dict[str, dict[str, list[str]]]


def load_day_table() -> dict[str, dict[str, dict[str, float]]]:
    """All historical daily readings: {day: {kind: {site: value}}}."""
    table: dict[str, dict[str, dict[str, float]]] = {}
    with gzip.open(DAY_READINGS_PATH, "rt", newline="") as file:
        for row in csv.DictReader(file):
            table.setdefault(row["day"], {}).setdefault(row["kind"], {})[row["site"]] = float(
                row["value"]
            )
    return table


def load_site_map() -> dict[str, dict]:
    return json.loads(SITE_MAP_PATH.read_text())


def load_active_stations() -> ActiveStations:
    return json.loads(ACTIVE_STATIONS_PATH.read_text())


def ranked(stations: list[dict], lat: float, lng: float) -> list[str]:
    """Station ids from nearest to farthest."""
    order = sorted(stations, key=lambda s: (s["lat"] - lat) ** 2 + (s["lng"] - lng) ** 2)
    return [s["id"] for s in order]


def nearest_active(ranked_ids: list[str], active: list[str]) -> str | None:
    reporting = set(active)
    return next((station_id for station_id in ranked_ids if station_id in reporting), None)


def point_site(
    lat: float, lng: float, region: str, map_static: dict, active: ActiveStations
) -> dict:
    """The site site_burn reads for one point: its PSI region, and per year its nearest rain
    gauge and WBGT station among those that reported enough of that year."""
    gauges = ranked(map_static["rain_stations"], lat, lng)
    stations = ranked(map_static["wbgt_stations"], lat, lng)
    by_year = {
        kind: {
            year: station_id
            for year, ids in active[kind].items()
            if (station_id := nearest_active(order, ids))
        }
        for kind, order in (("rain", gauges), ("heat", stations))
    }
    return {"region": region, "gauge_by_year": by_year["rain"], "station_by_year": by_year["heat"]}


def site_burn(
    table: dict[str, dict[str, dict[str, float]]],
    site: dict,
    tariff: Tariff,
    product_key: str,
    tier_key: str,
    takings_sgd: float,
    premium_yearly_sgd: float,
) -> dict:
    """One business through every recorded day: payouts (capped per year), losses, perils."""
    tier = calculator.find(tariff.tiers, tier_key, "tier")
    cap_sgd = tier.daily_payout_sgd * tier.max_paid_days_per_year
    years: dict[int, dict] = defaultdict(
        lambda: {"trigger_days": 0, "paid": 0.0, "lost": 0.0, "haze": 0.0, "rain": 0.0, "heat": 0.0}
    )
    for day in sorted(table):
        year = int(day[:4])
        readings_of_day = table[day]
        readings = {
            "haze": readings_of_day.get("haze", {}).get(site["region"], 0.0),
            "rain": readings_of_day.get("rain", {}).get(site["gauge_by_year"].get(str(year)), 0.0),
            "heat": readings_of_day.get("heat", {}).get(site["station_by_year"].get(str(year)), 0.0),
        }
        if readings["haze"] < 101 and readings["rain"] < 20 and readings["heat"] < 2:
            continue
        assessment = calculator.assess(tariff, product_key, tier_key, readings)
        if assessment.loss_percent <= 0:
            continue
        entry = years[year]
        room = max(0.0, cap_sgd - entry["paid"])
        paid = min(assessment.payout_sgd, room)
        entry["trigger_days"] += 1
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
            "paid_sgd": round(entry["paid"], 2),
            "est_lost_sgd": round(entry["lost"], 2),
            "premium_sgd": round(premium_yearly_sgd, 2),
            "loss_ratio": round(entry["paid"] / premium_yearly_sgd, 3),
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
            "by_hazard_sgd": {
                k: round(sum(r["by_hazard_sgd"][k] for r in rows), 2)
                for k in ("haze", "rain", "heat")
            },
        },
        "assumptions": {
            "takings_sgd_per_day": takings_sgd,
            "note": "Estimated losses are the tariff's loss score times the daily takings; "
            "heat readings exist from 2025, flood is priced at the tariff's assumed days.",
        },
    }
