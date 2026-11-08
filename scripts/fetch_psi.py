"""Download NEA air quality (PSI, PM2.5, PM10) by region from data.gov.sg.

Usage:
    uv run scripts/fetch_psi.py                       # 2016-03-09 (first day) to yesterday
    uv run scripts/fetch_psi.py --start 2026-01-01

Output:
    data/raw/psi/YYYY-MM-DD.json.gz    raw pages per day (gitignored cache)
    data/psi/psi_YYYY.parquet          one row per hour per region, one column per measure (committed)
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from dgs import REPO_ROOT, day_range, fetch_days

FIRST_DAY = date(2016, 3, 9)
RAW_DIR = REPO_ROOT / "data" / "raw" / "psi"
OUT_DIR = REPO_ROOT / "data" / "psi"


def pages_to_rows(pages: list[dict]) -> list[dict]:
    rows = []
    for page in pages:
        for item in page.get("items", []):
            by_region: dict[str, dict] = {}
            for measure, regions in item.get("readings", {}).items():
                for region, value in regions.items():
                    by_region.setdefault(region, {})[measure] = value
            for region, values in by_region.items():
                rows.append({"timestamp": item["timestamp"], "region": region, **values})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, default=FIRST_DAY)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    print(f"Fetching PSI {args.start} to {args.end}")
    results = fetch_days("psi", {}, day_range(args.start, args.end), RAW_DIR, args.workers)
    rows = [row for day in sorted(results) for row in pages_to_rows(results[day])]
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Singapore")
    for column in frame.columns.difference(["timestamp", "region"]):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.drop_duplicates(["timestamp", "region"]).sort_values(["timestamp", "region"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for year, part in frame.groupby(frame["timestamp"].dt.year):
        part.reset_index(drop=True).to_parquet(OUT_DIR / f"psi_{year}.parquet", index=False)
    missing_days = len(day_range(args.start, args.end)) - len(results)
    print(f"Done: {len(frame):,} rows, measures: {', '.join(frame.columns.difference(['timestamp', 'region']))}")
    print(f"Days with no data: {missing_days}")


if __name__ == "__main__":
    main()
