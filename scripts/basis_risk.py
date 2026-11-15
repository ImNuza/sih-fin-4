"""Basis risk: how often a payout read from nearby stations misses a bad day, or pays a good one.

We have no sales records, so the weather at the stall stands in for a lost day. Each NEA rain
gauge and WBGT station of the pricing network takes a turn as the "stall": its own reading is
the truth, and each trigger option reads only the other stations, as a payout would for a stall
with no station of its own (leave one out). The options:
    today's payout rule   api/readings.py itself: the first reporting stations among the nearest
                          and every other within 5 km, as many as the tariff prices from (rain
                          3, median; heat 1), else the MSS record (rain)
    nearest station       the nearest station that reported
    worst of 2 nearest    the higher of the 2 nearest stations that reported
    median of 3 nearest   the middle of the 3 nearest stations that reported, at any distance
For every station-day the stall reported:
    hit          the stall had a bad day and the option paid
    missed loss  the stall had a bad day and the option did not pay (the brief's "lost income
                 with no payout")
    false alarm  the option paid on a day the stall was fine
    quiet        neither
A bad day is a reading at or above a tariff band: the first band (the day pays something) and
the top band (the day pays in full). The band levels and station counts come from the tariff, so
this script follows any change to it. Haze is not measured: the index is one PSI reading per
region, so a stall and its payout always read the same number. PUB flood has no history yet.

Usage:
    uv run scripts/basis_risk.py              (run build_day_readings.py first)

Reads  data/processed/day_readings.csv.gz, data/processed/site_hazard_readings.csv,
       data/processed/map_static.json, api/default_tariff.json
Writes data/processed/basis_risk.csv         one row per hazard, band and trigger option

Leaving a station out puts its payout station farther away than a real stall's nearest station,
so the counts are an upper bound on basis risk. The script prints both distances.
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import defaultdict
from collections.abc import Callable
from statistics import median

from dgs import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
from api.calculator import km_between  # noqa: E402
from api.models import Tariff  # noqa: E402
from api.readings import eligible, station_reading, stations_read  # noqa: E402

PROC_DIR = REPO_ROOT / "data" / "processed"
OUT_PATH = PROC_DIR / "basis_risk.csv"
HAZARDS = ("rain", "heat")
TODAYS_RULE = "today's payout rule"
OPTIONS: dict[str, Callable[[list[float]], float]] = {
    "nearest station": lambda values: values[0],
    "worst of 2 nearest": lambda values: max(values[:2]),
    "median of 3 nearest": lambda values: median(values[:3]),
}
OUTCOMES = ("hit", "missed_loss", "false_alarm", "quiet")
DAYS_PER_YEAR = 365.25

Day = dict[str, dict[str, float]]
Station = tuple[str, float, float]  # id, latitude, longitude


def outcome(stall_bad: bool, paid: bool) -> str:
    if stall_bad:
        return "hit" if paid else "missed_loss"
    return "false_alarm" if paid else "quiet"


def count_outcomes(
    days: list[Day], kind: str, stations: list[Station], threshold: float, todays_count: int
) -> dict[str, dict[str, int]]:
    """Outcome counts per option, over every day a stall reported.

    A day counts only when at least 3 other stations reported and today's rule gives a reading,
    so every option is judged on the same days. A station with no value row read 0.
    """
    others = {}
    for stall_id, lat, lng in stations:
        rest = [station for station in stations if station[0] != stall_id]
        by_distance = sorted(rest, key=lambda s: km_between(lat, lng, s[1], s[2]))
        others[stall_id] = ([s[0] for s in by_distance], eligible(rest, lat, lng))
    counts = {option: dict.fromkeys(OUTCOMES, 0) for option in (TODAYS_RULE, *OPTIONS)}
    for day in days:
        values, silent = day.get(kind, {}), day.get(f"{kind}_missing", {})
        for stall_id, (by_distance, near) in others.items():
            if stall_id in silent:
                continue
            reporting = [values.get(s, 0.0) for s in by_distance if s not in silent][:3]
            todays, _ = station_reading(day, kind, near, todays_count)
            if len(reporting) < 3 or todays is None:
                continue
            stall_bad = values.get(stall_id, 0.0) >= threshold
            counts[TODAYS_RULE][outcome(stall_bad, todays >= threshold)] += 1
            for option, read in OPTIONS.items():
                counts[option][outcome(stall_bad, read(reporting) >= threshold)] += 1
    return counts


def load_days(kind: str) -> list[Day]:
    """Every day the feed covers, with the readings, the silent stations and the MSS record."""
    days: dict[str, Day] = defaultdict(lambda: defaultdict(dict))
    kinds = {kind, f"{kind}_missing", f"{kind}_mss"}
    with gzip.open(PROC_DIR / "day_readings.csv.gz", "rt", newline="") as file:
        for row in csv.DictReader(file):
            if row["kind"] in kinds:
                days[row["day"]][row["kind"]][row["site"]] = float(row["value"])
    return [days[day] for day in sorted(days) if kind in days[day] or f"{kind}_missing" in days[day]]


def network(kind: str) -> list[Station]:
    """The stations a price and a payout read for this hazard (site_hazard_readings.csv)."""
    found: dict[str, Station] = {}
    with (PROC_DIR / "site_hazard_readings.csv").open(newline="") as file:
        for row in csv.DictReader(file):
            if row["hazard"] == kind:
                found[row["site"]] = (row["site"], float(row["latitude"]), float(row["longitude"]))
    return sorted(found.values())


def band_levels(tariff: Tariff, kind: str) -> dict[str, float]:
    hazard = next(h for h in tariff.hazards if h.key == kind)
    bands = sorted(band.at_least for band in hazard.bands)
    return {"first band (pays part of the day)": bands[0], "top band (pays the full day)": bands[-1]}


def summary_row(kind: str, band: str, threshold: float, option: str, counts: dict, days: int) -> dict:
    bad_days = counts["hit"] + counts["missed_loss"]
    good_days = counts["false_alarm"] + counts["quiet"]
    stall_years = (bad_days + good_days) / DAYS_PER_YEAR
    return {
        "hazard": kind, "band": band, "reading_at_least": threshold, "option": option, **counts,
        "missed_loss_share": round(counts["missed_loss"] / bad_days, 3),
        "false_alarm_share_of_paid": round(
            counts["false_alarm"] / max(counts["hit"] + counts["false_alarm"], 1), 3),
        "false_alarm_share_of_good_days": round(counts["false_alarm"] / good_days, 4),
        "days": days,
        "stall_years": round(stall_years, 1),
        "bad_days_per_stall_year": round(bad_days / stall_years, 2),
        "missed_losses_per_stall_year": round(counts["missed_loss"] / stall_years, 2),
        "false_alarms_per_stall_year": round(counts["false_alarm"] / stall_years, 2),
    }


def main() -> None:
    tariff = Tariff.model_validate_json((REPO_ROOT / "api" / "default_tariff.json").read_text())
    todays_counts = dict(zip(HAZARDS, stations_read(tariff), strict=True))
    rows = []
    for kind in HAZARDS:
        days, stations = load_days(kind), network(kind)
        for band, threshold in band_levels(tariff, kind).items():
            counts = count_outcomes(days, kind, stations, threshold, todays_counts[kind])
            rows += [summary_row(kind, band, threshold, option, found, len(days))
                     for option, found in counts.items()]
    with OUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['hazard']:<5} {row['reading_at_least']:>4g} {row['option']:<21} "
              f"hit {row['hit']:>6} missed {row['missed_loss']:>6} false {row['false_alarm']:>6} "
              f"missed share {row['missed_loss_share']:.1%} "
              f"missed/yr {row['missed_losses_per_stall_year']} "
              f"false/yr {row['false_alarms_per_stall_year']}")
    centres = json.loads((PROC_DIR / "map_static.json").read_text())["hawker_centres"]
    for kind in HAZARDS:
        stations = network(kind)
        left_out = median(min(km_between(a[1], a[2], b[1], b[2]) for b in stations if b != a)
                          for a in stations)
        real = median(min(km_between(c["lat"], c["lng"], s[1], s[2]) for s in stations)
                      for c in centres)
        print(f"{kind}: median km to the payout station: {left_out:.2f} left out, "
              f"{real:.2f} from a hawker centre")
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
