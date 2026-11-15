"""Basis risk: how often a payout read from nearby stations misses a bad day, or pays a good one.

We have no sales records, so the weather at the stall stands in for a lost day. Each NEA rain
gauge and WBGT station takes a turn as the "stall": its own reading is the truth, and each
trigger option reads only the other stations, as a payout would for a stall with no station of
its own (leave one out). For every station-day the stall reported:
    hit          the stall had a bad day and the option paid
    missed loss  the stall had a bad day and the option did not pay (the brief's "lost income
                 with no payout")
    false alarm  the option paid on a day the stall was fine
    quiet        neither
A bad day is a reading at or above a tariff band: the first band (the day pays something) and
the top band (the day pays in full). The band levels come from the tariff, so this script
follows any change to it. Haze is not measured: the index is one PSI reading per region, so a
stall and its payout always read the same number. PUB flood has no history in the repo yet.

Usage:
    uv run scripts/basis_risk.py              (run build_day_readings.py first)

Reads  data/processed/day_readings.csv.gz, data/processed/map_static.json,
       api/default_tariff.json
Writes data/processed/basis_risk.csv         one row per hazard, band and trigger option

Leaving a station out puts its payout station farther away than a real stall's nearest station,
so the counts are an upper bound on basis risk. The script prints both distances.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
from collections import defaultdict
from collections.abc import Callable
from statistics import median

from dgs import REPO_ROOT

PROC_DIR = REPO_ROOT / "data" / "processed"
OUT_PATH = PROC_DIR / "basis_risk.csv"
STATION_KINDS = {"rain": "rain_stations", "heat": "wbgt_stations"}
EARTH_RADIUS_KM = 6371.0
OPTIONS: dict[str, Callable[[list[float]], float]] = {
    "nearest station (today's rule)": lambda values: values[0],
    "worst of 2 nearest": lambda values: max(values[:2]),
    "median of 3 nearest": lambda values: median(values[:3]),
}
OUTCOMES = ("hit", "missed_loss", "false_alarm", "quiet")

DAYS_PER_YEAR = 365.25

DayKind = dict[str, float]


def distance_km(a: dict, b: dict) -> float:
    d_lat, d_lng = math.radians(b["lat"] - a["lat"]), math.radians(b["lng"] - a["lng"])
    h = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(a["lat"])) * math.cos(math.radians(b["lat"]))
         * math.sin(d_lng / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def outcome(stall_bad: bool, paid: bool) -> str:
    if stall_bad:
        return "hit" if paid else "missed_loss"
    return "false_alarm" if paid else "quiet"


def count_outcomes(
    days: list[tuple[DayKind, set[str]]], stations: list[dict], threshold: float
) -> dict[str, dict[str, int]]:
    """Outcome counts per option. days: (readings by station, stations that did not report).

    A station with no reading on a day it reported read 0, as in the day table.
    """
    others_by_distance = {
        station["id"]: [o["id"] for o in sorted(stations, key=lambda o: distance_km(station, o))
                        if o["id"] != station["id"]]
        for station in stations
    }
    counts = {option: dict.fromkeys(OUTCOMES, 0) for option in OPTIONS}
    for readings, silent in days:
        for stall, others in others_by_distance.items():
            if stall in silent:
                continue
            reporting = [readings.get(o, 0.0) for o in others if o not in silent][:3]
            if len(reporting) < 3:
                continue
            stall_bad = readings.get(stall, 0.0) >= threshold
            for option, read in OPTIONS.items():
                counts[option][outcome(stall_bad, read(reporting) >= threshold)] += 1
    return counts


def load_days(kind: str) -> list[tuple[DayKind, set[str]]]:
    """Every day the feed covers: the readings and the stations that did not report."""
    values: dict[str, DayKind] = defaultdict(dict)
    silent: dict[str, set[str]] = defaultdict(set)
    with gzip.open(PROC_DIR / "day_readings.csv.gz", "rt", newline="") as file:
        for row in csv.DictReader(file):
            if row["kind"] == kind:
                values[row["day"]][row["site"]] = float(row["value"])
            elif row["kind"] == f"{kind}_missing":
                silent[row["day"]].add(row["site"])
    covered = sorted(set(values) | set(silent))
    return [(values[day], silent[day]) for day in covered]


def band_levels(hazard: dict) -> dict[str, float]:
    bands = sorted(band["at_least"] for band in hazard["bands"])
    return {"first band (pays part of the day)": bands[0], "top band (pays the full day)": bands[-1]}


def main() -> None:
    tariff = json.loads((REPO_ROOT / "api" / "default_tariff.json").read_text())
    map_static = json.loads((PROC_DIR / "map_static.json").read_text())
    hazards = {hazard["key"]: hazard for hazard in tariff["hazards"]}
    rows = []
    for kind, station_key in STATION_KINDS.items():
        days = load_days(kind)
        stations = map_static[station_key]
        for band, threshold in band_levels(hazards[kind]).items():
            for option, counts in count_outcomes(days, stations, threshold).items():
                bad_days = counts["hit"] + counts["missed_loss"]
                good_days = counts["false_alarm"] + counts["quiet"]
                stall_years = (bad_days + good_days) / DAYS_PER_YEAR
                rows.append({
                    "hazard": kind, "band": band, "reading_at_least": threshold,
                    "option": option, **counts,
                    "missed_loss_share": round(counts["missed_loss"] / bad_days, 3),
                    "false_alarm_share_of_paid": round(
                        counts["false_alarm"] / max(counts["hit"] + counts["false_alarm"], 1), 3),
                    "false_alarm_share_of_good_days": round(counts["false_alarm"] / good_days, 4),
                    "days": len(days),
                    "stall_years": round(stall_years, 1),
                    "bad_days_per_stall_year": round(bad_days / stall_years, 2),
                    "missed_losses_per_stall_year": round(counts["missed_loss"] / stall_years, 2),
                    "false_alarms_per_stall_year": round(counts["false_alarm"] / stall_years, 2),
                })
    with OUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['hazard']:<5} {row['reading_at_least']:>4g} {row['option']:<31} "
              f"hit {row['hit']:>6} missed {row['missed_loss']:>6} "
              f"false {row['false_alarm']:>6} missed share {row['missed_loss_share']:.1%}")
    for kind, station_key in STATION_KINDS.items():
        stations = map_static[station_key]
        left_out = median(min(distance_km(a, b) for b in stations if b is not a) for a in stations)
        real = median(min(distance_km(c, s) for s in stations) for c in map_static["hawker_centres"])
        print(f"{kind}: median km to the payout station: {left_out:.2f} left out, "
              f"{real:.2f} from a hawker centre")
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
