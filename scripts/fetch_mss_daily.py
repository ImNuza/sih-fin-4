"""Download MSS historical daily records (rain, temperature, wind) per station from weather.gov.sg.

These are the only public station records that go back decades (from 1980 at some stations).
They are monthly CSV files with no API key. Each station is fetched newest month first, and the
search stops after MISSING_MONTHS_TO_STOP months in a row with no file.

Usage:
    uv run scripts/fetch_mss_daily.py
    uv run scripts/fetch_mss_daily.py --stations S24 S43

Reads:
    data/rainfall/*.parquet           station IDs to try (data.gov.sg and MSS share them)
Writes:
    data/raw/mss_daily/<station>_YYYYMM.csv   raw monthly files (gitignored cache)
    data/mss_daily/mss_daily.parquet          one row per station per day
"""

from __future__ import annotations

import argparse
import io
import time
from datetime import date

import pandas as pd
import requests

from dgs import REPO_ROOT, USER_AGENT

FILE_URL = "https://www.weather.gov.sg/files/dailydata/DAILYDATA_{station}_{month}.csv"
FIRST_MONTH = date(1980, 1, 1)
MISSING_MONTHS_TO_STOP = 36
SECONDS_BETWEEN_CALLS = 0.2
MAX_RETRIES = 6
RAW_DIR = REPO_ROOT / "data" / "raw" / "mss_daily"
OUT_FILE = REPO_ROOT / "data" / "mss_daily" / "mss_daily.parquet"
RAINFALL_DIR = REPO_ROOT / "data" / "rainfall"
# Column headers change spelling and encoding over the years, so columns are named by position.
COLUMNS = [
    "station_name", "year", "month", "day",
    "rain_daily_mm", "rain_max_30min_mm", "rain_max_60min_mm", "rain_max_120min_mm",
    "temp_mean_c", "temp_max_c", "temp_min_c", "wind_mean_kmh", "wind_max_kmh",
]
NUMERIC_COLUMNS = COLUMNS[4:]


def station_ids_from_rainfall() -> list[str]:
    files = sorted(RAINFALL_DIR.glob("*.parquet"))
    if not files:
        raise SystemExit(
            f"No rainfall files in {RAINFALL_DIR}. Run scripts/fetch_rainfall.py first."
        )
    ids: set[str] = set()
    for file in files:
        ids |= set(pd.read_parquet(file, columns=["station_id"])["station_id"].unique())
    return sorted(ids)


def months_newest_first() -> list[str]:
    today = date.today()
    months = []
    year, month = today.year, today.month - 1
    while (year, month) >= (FIRST_MONTH.year, FIRST_MONTH.month):
        if month == 0:
            year, month = year - 1, 12
            continue
        months.append(f"{year}{month:02d}")
        month -= 1
    return months


def download(session: requests.Session, station: str, month: str) -> bytes | None:
    """Return the CSV bytes, or None when MSS has no file for that station and month."""
    for attempt in range(MAX_RETRIES):
        time.sleep(SECONDS_BETWEEN_CALLS)
        response = session.get(FILE_URL.format(station=station, month=month), timeout=30)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            # Missing files come back as an HTML page with status 200.
            return None if response.content.lstrip().startswith(b"<") else response.content
        time.sleep(min(60, 2**attempt))
    raise RuntimeError(f"{station} {month}: HTTP {response.status_code} after {MAX_RETRIES} tries")


def fetch_station(session: requests.Session, station: str, months: list[str]) -> int:
    found = 0
    missing_in_a_row = 0
    for month in months:
        cache = RAW_DIR / f"{station}_{month}.csv"
        missing_marker = RAW_DIR / f"{station}_{month}.missing"
        if cache.exists():
            found += 1
            missing_in_a_row = 0
            continue
        if missing_marker.exists():
            content = None
        else:
            content = download(session, station, month)
            if content is None and month != months[0]:
                missing_marker.touch()
        if content is None:
            missing_in_a_row += 1
            if missing_in_a_row >= MISSING_MONTHS_TO_STOP:
                break
            continue
        cache.write_bytes(content)
        found += 1
        missing_in_a_row = 0
    return found


def read_month(file) -> pd.DataFrame:
    table = pd.read_csv(io.BytesIO(file.read_bytes()), encoding="latin-1", header=0, names=COLUMNS)
    for column in NUMERIC_COLUMNS:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    table.insert(0, "station_id", file.stem.rsplit("_", 1)[0])
    return table


def build_table() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise SystemExit(f"No MSS files in {RAW_DIR}.")
    table = pd.concat([read_month(file) for file in files], ignore_index=True)
    table["date"] = pd.to_datetime(table[["year", "month", "day"]], errors="coerce").dt.date
    table = table.dropna(subset=["date"]).drop(columns=["year", "month", "day"])
    return table.sort_values(["station_id", "date"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stations", nargs="*", help="station IDs (default: all rain gauges)")
    args = parser.parse_args()
    stations = args.stations or station_ids_from_rainfall()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    months = months_newest_first()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    for number, station in enumerate(stations, start=1):
        found = fetch_station(session, station, months)
        print(f"  {station}: {found} months ({number}/{len(stations)} stations)", flush=True)
    table = build_table()
    table.to_parquet(OUT_FILE, index=False)
    print(f"{len(table)} station-days, {table['station_id'].nunique()} stations, "
          f"{table['date'].min()} to {table['date'].max()} -> {OUT_FILE}")


if __name__ == "__main__":
    main()
