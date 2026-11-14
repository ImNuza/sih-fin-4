"""Build the per-day readings table behind the map's replay-a-day picker.

Usage:
    uv run scripts/build_day_readings.py      (run fetch scripts and heat_stats.py first)

Reads  data/processed/psi_daily.parquet, data/processed/wbgt_station_days.parquet
       data/rainfall/rain_hourly_*.parquet
Writes data/processed/day_readings.csv.gz   one row per day, kind and site:
       haze  the day's highest 24-hour PSI per region
       rain  the wettest work hour per gauge, mm (rows under RAIN_KEEP_MM are left out)
       heat  work hours at WBGT 32°C or more per station (zero rows left out)
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
    wettest = work.groupby(["day", "station_id"])["rain_mm"].max().reset_index()
    wettest = wettest[wettest["rain_mm"] >= RAIN_KEEP_MM]
    return [
        (record.day.date().isoformat(), "rain", record.station_id, round(float(record.rain_mm), 1))
        for record in wettest.itertuples()
    ]


def heat_rows() -> list[tuple[str, str, str, float]]:
    days = pd.read_parquet(PROC_DIR / "wbgt_station_days.parquet")
    hot = days[days["hours_ge_32"] > 0]
    return [
        (record.day.date().isoformat(), "heat", record.station_id, float(record.hours_ge_32))
        for record in hot.itertuples()
    ]


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
