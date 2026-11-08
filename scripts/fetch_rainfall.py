"""Download NEA rainfall (5-minute, about 56 stations) from data.gov.sg and store hourly totals.

Usage:
    uv run scripts/fetch_rainfall.py                     # 2025-01-16 (as WBGT) to yesterday
    uv run scripts/fetch_rainfall.py --start 2016-12-02  # full history, about 12 pages a day

Output:
    data/raw/rainfall/YYYY-MM-DD.json.gz        raw 5-minute pages per day (gitignored cache, large)
    data/rainfall/rain_hourly_YYYY-MM.parquet   one row per station per hour (committed)
    data/rainfall/stations.csv                  station names and locations
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from dgs import REPO_ROOT, day_range, fetch_days

DEFAULT_START = date(2025, 1, 16)
RAW_DIR = REPO_ROOT / "data" / "raw" / "rainfall"
OUT_DIR = REPO_ROOT / "data" / "rainfall"


def day_to_hourly(pages: list[dict], stations: dict[str, dict]) -> pd.DataFrame:
    """Sum 5-minute rainfall (mm) to hourly totals per station; keep the wettest 5 minutes too."""
    rows = []
    for page in pages:
        for station in page.get("stations", []):
            stations[station["id"]] = {
                "station_id": station["id"],
                "station_name": station["name"],
                "latitude": station["location"]["latitude"],
                "longitude": station["location"]["longitude"],
            }
        for reading in page.get("readings", []):
            for value in reading["data"]:
                rows.append((reading["timestamp"], value["stationId"], value["value"]))
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows, columns=["timestamp", "station_id", "rain_mm"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(
        "Asia/Singapore"
    )
    frame["rain_mm"] = pd.to_numeric(frame["rain_mm"], errors="coerce")
    frame = frame.drop_duplicates(["timestamp", "station_id"])
    frame["hour"] = frame["timestamp"].dt.floor("h")
    return (
        frame.groupby(["hour", "station_id"])
        .agg(
            rain_mm=("rain_mm", "sum"),
            max_5min_mm=("rain_mm", "max"),
            readings=("rain_mm", "count"),
        )
        .reset_index()
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    print(f"Fetching rainfall {args.start} to {args.end}")
    results = fetch_days("rainfall", {}, day_range(args.start, args.end), RAW_DIR, args.workers)
    stations: dict[str, dict] = {}
    hourly = pd.concat(
        [day_to_hourly(results[day], stations) for day in sorted(results)], ignore_index=True
    )
    hourly = hourly.drop_duplicates(["hour", "station_id"]).sort_values(["hour", "station_id"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for month, part in hourly.groupby(hourly["hour"].dt.strftime("%Y-%m")):
        part.reset_index(drop=True).to_parquet(
            OUT_DIR / f"rain_hourly_{month}.parquet", index=False
        )
    pd.DataFrame(stations.values()).sort_values("station_id").to_csv(
        OUT_DIR / "stations.csv", index=False
    )
    missing_days = len(day_range(args.start, args.end)) - len(results)
    print(
        f"Done: {len(hourly):,} station-hours, {hourly['station_id'].nunique()} stations, "
        f"days with no data: {missing_days}"
    )


if __name__ == "__main__":
    main()
