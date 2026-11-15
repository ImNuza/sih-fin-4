"""Build the per-day readings table behind the map's replay-a-day picker.

Usage:
    uv run scripts/build_day_readings.py      (run fetch scripts and heat_stats.py first)

Reads  data/processed/psi_daily.parquet, data/processed/wbgt_station_days.parquet
       data/rainfall/rain_hourly_*.parquet, data/mss_daily/mss_daily.parquet
       data/processed/site_hazard_readings.csv (the gauges and WBGT stations the price reads)
Writes data/processed/day_readings.csv.gz   one row per day, kind and site:
       haze          the day's highest 24-hour PSI per region
       rain          the wettest work hour per gauge, mm (rows under RAIN_KEEP_MM are left out)
       heat          work hours at WBGT 32°C or more per station (zero rows left out)
       rain_missing  a priced gauge that reported under half the work hours that day (value 1)
       heat_missing  a priced WBGT station that reported under half the work-hour readings
                     (value 1)
       rain_mss      for a missing gauge, MSS's published highest 60-minute rain that day, mm
Missing rows exist only from the first day of each feed in data/, so a day before the WBGT
network data starts reads heat as 0. A station is reporting on a day unless it has a missing
row, and a reporting station with no value row read 0. api/readings.py reads a place from these
rows, the same network the price reads, with its fallbacks: other stations within 5 km, MSS, or
waiting for data.
"""

from __future__ import annotations

import csv
import gzip

import pandas as pd

from dgs import REPO_ROOT
from hazard_stats import load_rain

PROC_DIR = REPO_ROOT / "data" / "processed"
OUT_PATH = PROC_DIR / "day_readings.csv.gz"
REGIONS = ("central", "east", "north", "south", "west")
RAIN_KEEP_MM = 1.0
WORK_HOURS = 12            # 07:00 to 19:00 SGT, as in hazard_stats.py and heat_stats.py
WBGT_READINGS_PER_HOUR = 4
MIN_REPORTED_SHARE = 0.5   # a station that sent under half its work-hour data did not report


def priced_station_ids(hazard: str) -> set[str]:
    """The stations the price reads for a hazard, so pricing and payouts read one network."""
    history = pd.read_csv(PROC_DIR / "site_hazard_readings.csv", usecols=["hazard", "site"])
    return set(history.loc[history["hazard"] == hazard, "site"])


def missing_rows(
    reported: pd.DataFrame, kind: str, stations: set[str]
) -> list[tuple[str, str, str, float]]:
    """Priced stations with no full report on each day the feed covers, a day the whole feed was
    down included. reported: day, station_id."""
    present_by_day = reported.groupby("day")["station_id"].agg(set)
    feed_days = pd.date_range(present_by_day.index.min(), present_by_day.index.max())
    return [
        (day.date().isoformat(), kind, station_id, 1)
        for day in feed_days
        for station_id in sorted(stations - present_by_day.get(day, set()))
    ]


def haze_rows() -> list[tuple[str, str, str, float]]:
    daily = pd.read_parquet(PROC_DIR / "psi_daily.parquet")
    rows = []
    for record in daily.itertuples():
        day = record.day.date().isoformat()
        for region in REGIONS:
            value = getattr(record, f"psi_{region}")
            if pd.notna(value):
                rows.append((day, "haze", region, round(float(value))))
    return rows


def rain_rows() -> list[tuple[str, str, str, float]]:
    rain = load_rain()
    work = rain[rain["work_hour"]]
    hours = work.groupby(["day", "station_id"]).size().reset_index(name="hours")
    reported = hours[hours["hours"] >= WORK_HOURS * MIN_REPORTED_SHARE]
    missing = missing_rows(reported, "rain_missing", priced_station_ids("rain"))
    wettest = work.groupby(["day", "station_id"])["rain_mm"].max().reset_index()
    wettest = wettest[wettest["rain_mm"] >= RAIN_KEEP_MM]
    values = [
        (record.day.date().isoformat(), "rain", record.station_id, round(float(record.rain_mm), 1))
        for record in wettest.itertuples()
    ]
    return values + missing + mss_rows(missing)


def mss_rows(missing: list[tuple[str, str, str, float]]) -> list[tuple[str, str, str, float]]:
    """MSS's published highest 60-minute rain for each gauge-day the live feed missed."""
    mss = pd.read_parquet(REPO_ROOT / "data" / "mss_daily" / "mss_daily.parquet")
    mss = mss.dropna(subset=["rain_max_60min_mm"])
    published = {
        (record.date.isoformat(), record.station_id): float(record.rain_max_60min_mm)
        for record in mss.itertuples()
    }
    return [
        (day, "rain_mss", station_id, round(published[(day, station_id)], 1))
        for day, _, station_id, _ in missing
        if (day, station_id) in published
    ]


def heat_rows() -> list[tuple[str, str, str, float]]:
    days = pd.read_parquet(PROC_DIR / "wbgt_station_days.parquet")
    full_readings = WORK_HOURS * WBGT_READINGS_PER_HOUR
    reported = days[days["readings"] >= full_readings * MIN_REPORTED_SHARE]
    hot = days[days["hours_ge_32"] > 0]
    values = [
        (record.day.date().isoformat(), "heat", record.station_id, float(record.hours_ge_32))
        for record in hot.itertuples()
    ]
    return values + missing_rows(reported, "heat_missing", priced_station_ids("heat"))


def main() -> None:
    rows = haze_rows() + rain_rows() + heat_rows()
    rows.sort()
    with gzip.open(OUT_PATH, "wt", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["day", "kind", "site", "value"])
        writer.writerows(rows)
    days = {row[0] for row in rows}
    print(
        f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(rows):,} rows over {len(days):,} days "
        f"({min(days)} to {max(days)}), {OUT_PATH.stat().st_size:,} bytes"
    )


if __name__ == "__main__":
    main()
