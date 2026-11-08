"""Download NEA WBGT (heat stress) readings from data.gov.sg.

Usage:
    uv run scripts/fetch_wbgt.py                 # from the first available day to yesterday
    uv run scripts/fetch_wbgt.py --start 2025-06-01 --end 2025-06-30

Output:
    data/raw/wbgt/YYYY-MM-DD.json.gz   raw API pages per day (gitignored, used as a cache)
    data/wbgt/wbgt_YYYY-MM.parquet     one row per station per 15-minute reading (committed)
"""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from dgs import REPO_ROOT, DgsClient

API_PATH = "weather"
API_PARAMS = {"api": "wbgt"}
RAW_DIR = REPO_ROOT / "data" / "raw" / "wbgt"
OUT_DIR = REPO_ROOT / "data" / "wbgt"
# NEA's WBGT history starts in early 2025. find_first_day searches from here.
SEARCH_FROM = date(2024, 12, 1)


def raw_path(day: date) -> Path:
    return RAW_DIR / f"{day.isoformat()}.json.gz"


def fetch_day(client: DgsClient, day: date) -> list[dict] | None:
    """Return the raw pages for one day, from the cache when possible."""
    path = raw_path(day)
    if path.exists():
        return json.loads(gzip.decompress(path.read_bytes()))
    pages = client.get_all_pages(API_PATH, dict(API_PARAMS, date=day.isoformat()))
    if pages is not None and day < date.today():
        path.write_bytes(gzip.compress(json.dumps(pages).encode()))
    return pages


def has_data(client: DgsClient, day: date) -> bool:
    return client.get(API_PATH, dict(API_PARAMS, date=day.isoformat())) is not None


def find_first_day(client: DgsClient, end: date) -> date:
    """Binary search for the first day that has data (assumes no data before it)."""
    low, high = SEARCH_FROM, end
    while low < high:
        middle = low + (high - low) // 2
        if has_data(client, middle):
            high = middle
        else:
            low = middle + timedelta(days=1)
    return low


def to_float(value: object) -> float | None:
    """Readings can be missing or the string "NA" when a station has a gap."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pages_to_rows(pages: list[dict]) -> list[dict]:
    rows = []
    for page in pages:
        for record in page.get("records", []):
            for reading in record["item"]["readings"]:
                rows.append(
                    {
                        "timestamp": record["datetime"],
                        "station_id": reading["station"]["id"],
                        "station_name": reading["station"]["name"],
                        "town": reading["station"].get("townCenter"),
                        "latitude": float(reading["location"]["latitude"]),
                        "longitude": float(reading["location"]["longitude"]),
                        "wbgt": to_float(reading.get("wbgt")),
                        "heat_stress": reading.get("heatStress"),
                    }
                )
    return rows


def write_months(rows: list[dict]) -> list[Path]:
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.drop_duplicates(["timestamp", "station_id"]).sort_values(
        ["timestamp", "station_id"]
    )
    month = frame["timestamp"].dt.strftime("%Y-%m")
    written = []
    for name, part in frame.groupby(month):
        path = OUT_DIR / f"wbgt_{name}.parquet"
        part.reset_index(drop=True).to_parquet(path, index=False)
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--start", type=date.fromisoformat, help="first day (default: first day with data)"
    )
    parser.add_argument("--end", type=date.fromisoformat, help="last day (default: yesterday)")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = DgsClient()
    end = args.end or date.today() - timedelta(days=1)
    start = args.start or find_first_day(client, end)
    print(f"Fetching WBGT {start} to {end}")

    rows: list[dict] = []
    missing: list[str] = []
    day = start
    while day <= end:
        pages = fetch_day(client, day)
        if pages is None:
            missing.append(day.isoformat())
        else:
            rows.extend(pages_to_rows(pages))
        if day.day == 1 or day == end:
            print(f"  {day}  rows so far: {len(rows):,}")
        day += timedelta(days=1)

    written = write_months(rows)
    print(
        f"Done: {len(rows):,} rows in {len(written)} monthly files "
        f"under {OUT_DIR.relative_to(REPO_ROOT)}"
    )
    if missing:
        print(f"Days with no data ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
