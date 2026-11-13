"""Download ERA5 hourly reanalysis for the 5 PSI region centres from the Open-Meteo archive API.

NEA feeds start in 2016 and give no sunlight, which WBGT needs. ERA5 (ECMWF, 0.25 degree grid)
gives sunlight, temperature, humidity, wind and rain every hour from 1940, so it can stretch the
heat back-test to decades. It is a model, not a station: calibrate it on the NEA overlap first.

Free Open-Meteo use is non-commercial: 600 calls a minute, 5,000 an hour and 10,000 a day, where
a long request counts as several calls (one region-year of these variables is about 21). A full
run from 1980 is about 4,900 calls, so it is paced to take about an hour, once a day at most.
Data: ERA5 by Copernicus / ECMWF via Open-Meteo, CC BY 4.0.

Usage:
    uv run scripts/fetch_era5.py
    uv run scripts/fetch_era5.py --start-year 2016

Writes:
    data/raw/era5/<region>_YYYY.json.gz   raw responses (gitignored cache)
    data/era5/era5_hourly.parquet         one row per hour per region, Singapore time
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from datetime import date, timedelta

import pandas as pd
import requests

from dgs import REPO_ROOT, USER_AGENT

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FIRST_YEAR = 1980
# ERA5 is published about 5 days behind real time.
ERA5_LAG_DAYS = 6
RATE_LIMIT_PAUSE_SECONDS = 70
SECONDS_BETWEEN_CALLS = 16.0
MAX_RETRIES = 8
# Region centres as published in the NEA PSI API (regionMetadata).
REGION_CENTRES = {
    "central": (1.35735, 103.82),
    "north": (1.41803, 103.82),
    "south": (1.29587, 103.82),
    "east": (1.35735, 103.94),
    "west": (1.35735, 103.7),
}
HOURLY_VARIABLES = [
    "temperature_2m", "relative_humidity_2m", "dew_point_2m", "wet_bulb_temperature_2m",
    "wind_speed_10m", "shortwave_radiation", "direct_radiation", "precipitation",
]
RAW_DIR = REPO_ROOT / "data" / "raw" / "era5"
OUT_FILE = REPO_ROOT / "data" / "era5" / "era5_hourly.parquet"


def fetch_year(session: requests.Session, region: str, year: int, last_day: date) -> dict:
    latitude, longitude = REGION_CENTRES[region]
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{year}-01-01",
        "end_date": min(date(year, 12, 31), last_day).isoformat(),
        "hourly": ",".join(HOURLY_VARIABLES),
        "models": "era5",
        "timezone": "Asia/Singapore",
    }
    for attempt in range(MAX_RETRIES):
        time.sleep(SECONDS_BETWEEN_CALLS)
        response = session.get(ARCHIVE_URL, params=params, timeout=120)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            print(f"  rate limited at {region} {year}, waiting", flush=True)
            time.sleep(RATE_LIMIT_PAUSE_SECONDS * (attempt + 1))
            continue
        if response.status_code >= 500:
            time.sleep(min(60, 2**attempt))
            continue
        raise RuntimeError(f"{region} {year}: HTTP {response.status_code}, {response.text[:200]}")
    raise RuntimeError(f"{region} {year}: still failing after {MAX_RETRIES} tries")


def response_to_table(region: str, body: dict) -> pd.DataFrame:
    table = pd.DataFrame(body["hourly"])
    table["time"] = pd.to_datetime(table["time"]).dt.tz_localize("Asia/Singapore")
    table.insert(1, "region", region)
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start-year", type=int, default=FIRST_YEAR)
    args = parser.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    last_day = date.today() - timedelta(days=ERA5_LAG_DAYS)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    tables = []
    for year in range(last_day.year, args.start_year - 1, -1):
        for region in REGION_CENTRES:
            cache = RAW_DIR / f"{region}_{year}.json.gz"
            if cache.exists():
                body = json.loads(gzip.decompress(cache.read_bytes()))
            else:
                body = fetch_year(session, region, year, last_day)
                if year < last_day.year:
                    cache.write_bytes(gzip.compress(json.dumps(body).encode()))
            tables.append(response_to_table(region, body))
        print(f"  {year} done", flush=True)
    table = pd.concat(tables, ignore_index=True).sort_values(["region", "time"])
    table.to_parquet(OUT_FILE, index=False)
    print(
        f"{len(table)} region-hours, {table['time'].min()} to {table['time'].max()} -> {OUT_FILE}"
    )


if __name__ == "__main__":
    main()
