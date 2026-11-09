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
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    print(f"Fetching rainfall {args.start} to {args.end}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    days = day_range(args.start, args.end)
    stations: dict[str, dict] = {}
    station_ids: set[str] = set()
    station_hours = 0
    days_with_data = 0
    days_done = 0
    failed_years: dict[int, str] = {}
    # One year at a time: raw pages use about 6 MB of memory per day, so 10 years at once
    # would need about 20 GB. Oldest year first, so the newest station names win in stations.csv.
    for year in sorted({day.year for day in days}):
        year_days = [day for day in days if day.year == year]
        try:
            results = fetch_days("rainfall", {}, year_days, RAW_DIR, args.workers)
        except RuntimeError as error:
            failed_years[year] = str(error)
            continue
        days_done += len(year_days)
        days_with_data += len(results)
        frames = [day_to_hourly(results[day], stations) for day in sorted(results)]
        del results
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            continue
        hourly = pd.concat(frames, ignore_index=True)
        hourly = hourly.drop_duplicates(["hour", "station_id"]).sort_values(["hour", "station_id"])
        for month, part in hourly.groupby(hourly["hour"].dt.strftime("%Y-%m")):
            part.reset_index(drop=True).to_parquet(
                OUT_DIR / f"rain_hourly_{month}.parquet", index=False
            )
        station_hours += len(hourly)
        station_ids.update(hourly["station_id"].unique())
        print(f"  {year}: {len(hourly):,} station-hours written", flush=True)

    pd.DataFrame(stations.values()).sort_values("station_id").to_csv(
        OUT_DIR / "stations.csv", index=False
    )
    print(
        f"Done: {station_hours:,} station-hours, {len(station_ids)} stations, "
        f"days with no data: {days_done - days_with_data}"
    )
    if failed_years:
        details = "\n".join(failed_years[year] for year in sorted(failed_years))
        raise RuntimeError(f"Some years did not finish. Rerun to fetch them.\n{details}")


if __name__ == "__main__":
    main()
