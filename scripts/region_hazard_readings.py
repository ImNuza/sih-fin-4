"""How often each hazard reading happened per NEA region: the history the pricing API prices from.

Usage:
    uv run scripts/region_hazard_readings.py      (run heat_stats.py and hazard_stats.py first)

Reads  data/processed/psi_daily.parquet, data/processed/wbgt_station_days.parquet
       data/rainfall/*.parquet, data/rainfall/stations.csv, data/wbgt/*.parquet
Writes data/processed/region_hazard_readings.csv   one row per hazard, region and reading, with
       the number of site-days that had it. Readings:
       haze  daily max 24-hour PSI of the region
       rain  wettest work hour of the gauge, in mm
       heat  work hours with WBGT at 32°C or more at the station
"""

from __future__ import annotations

import pandas as pd

from dgs import REPO_ROOT
from hazard_stats import load_rain

PROC_DIR = REPO_ROOT / "data" / "processed"
OUT_PATH = PROC_DIR / "region_hazard_readings.csv"
READING_DECIMALS = 2
COLUMNS = ["hazard", "region", "site", "day", "reading"]
# Label points of the five PSI regions, from regionMetadata in the NEA /psi API response.
REGION_POINTS = pd.DataFrame(
    {
        "region": ["north", "south", "east", "west", "central"],
        "latitude": [1.41803, 1.29587, 1.35735, 1.35735, 1.35735],
        "longitude": [103.82, 103.82, 103.94, 103.70, 103.82],
    }
)


def nearest_region(stations: pd.DataFrame) -> pd.Series:
    """NEA publishes no region boundaries, so each station goes to the closest label point."""
    lat = stations["latitude"].to_numpy()[:, None] - REGION_POINTS["latitude"].to_numpy()
    lon = stations["longitude"].to_numpy()[:, None] - REGION_POINTS["longitude"].to_numpy()
    closest = (lat**2 + lon**2).argmin(axis=1)
    return pd.Series(REGION_POINTS["region"].to_numpy()[closest], index=stations["station_id"])


def with_region(days: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    days["region"] = days["site"].map(nearest_region(stations))
    unplaced = sorted(days.loc[days["region"].isna(), "site"].unique())
    if unplaced:
        raise SystemExit(f"No location for stations {unplaced}. Refresh the station list.")
    return days


def haze_days() -> pd.DataFrame:
    daily = pd.read_parquet(PROC_DIR / "psi_daily.parquet")
    region_columns = [f"psi_{region}" for region in REGION_POINTS["region"]]
    days = daily.melt(
        id_vars="day", value_vars=region_columns, var_name="site", value_name="reading"
    )
    days["region"] = days["site"].str.removeprefix("psi_")
    return days.dropna(subset=["reading"]).assign(hazard="haze")


def rain_days() -> pd.DataFrame:
    rain = load_rain()
    work = rain[rain["work_hour"]]
    days = work.groupby(["station_id", "day"])["rain_mm"].max().reset_index()
    days = days.rename(columns={"station_id": "site", "rain_mm": "reading"})
    stations = pd.read_csv(REPO_ROOT / "data" / "rainfall" / "stations.csv")
    return with_region(days, stations).assign(hazard="rain")


def heat_days() -> pd.DataFrame:
    days = pd.read_parquet(PROC_DIR / "wbgt_station_days.parquet")
    days = days.rename(columns={"station_id": "site", "hours_ge_32": "reading"})
    readings = pd.concat(
        pd.read_parquet(path, columns=["station_id", "latitude", "longitude"])
        for path in sorted((REPO_ROOT / "data" / "wbgt").glob("wbgt_*.parquet"))
    )
    stations = readings.groupby("station_id")[["latitude", "longitude"]].last().reset_index()
    return with_region(days[["site", "day", "reading"]], stations).assign(hazard="heat")


def main() -> None:
    days = pd.concat([haze_days()[COLUMNS], rain_days()[COLUMNS], heat_days()[COLUMNS]])
    print(
        days.groupby(["hazard", "region"])
        .agg(sites=("site", "nunique"), first_day=("day", "min"), last_day=("day", "max"))
        .to_string()
    )
    days["reading"] = days["reading"].round(READING_DECIMALS)
    counts = days.groupby(["hazard", "region", "reading"]).size().rename("days").reset_index()
    counts.to_csv(OUT_PATH, index=False)
    print(
        f"Wrote {len(counts):,} rows ({len(days):,} site-days) to {OUT_PATH.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
