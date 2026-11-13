"""Load the committed NEA, MSS, ERA5 and NOAA tables as tidy daily frames.

Every frame keys days by a timezone-free date in Singapore time.
"""

from __future__ import annotations

import json

import pandas as pd

from api.models import Tariff
from ml.config import (
    DATA_DIR,
    MIN_WBGT_READINGS_PER_DAY,
    PROC_DIR,
    TARIFF_PATH,
    WORK_END_HOUR,
    WORK_START_HOUR,
)
from region_hazard_readings import REGION_POINTS, nearest_region

REGIONS = list(REGION_POINTS["region"])


def load_tariff() -> Tariff:
    return Tariff.model_validate(json.loads(TARIFF_PATH.read_text()))


def require(path) -> None:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run the fetch scripts listed in README.md first.")


def era5_daily() -> pd.DataFrame:
    """One row per region and day: daily and work-hour summaries of ERA5."""
    path = DATA_DIR / "era5" / "era5_hourly.parquet"
    require(path)
    hourly = pd.read_parquet(path)
    local = hourly["time"].dt.tz_convert("Asia/Singapore")
    hourly["day"] = local.dt.tz_localize(None).dt.normalize()
    hourly["work"] = (local.dt.hour >= WORK_START_HOUR) & (local.dt.hour < WORK_END_HOUR)
    keys = ["region", "day"]
    all_day = hourly.groupby(keys).agg(
        era5_temp_max=("temperature_2m", "max"),
        era5_temp_mean=("temperature_2m", "mean"),
        era5_temp_min=("temperature_2m", "min"),
        era5_rh_mean=("relative_humidity_2m", "mean"),
        era5_dew_mean=("dew_point_2m", "mean"),
        era5_wetbulb_max=("wet_bulb_temperature_2m", "max"),
        era5_wind_mean=("wind_speed_10m", "mean"),
        era5_rain_sum=("precipitation", "sum"),
        era5_rain_max_hour=("precipitation", "max"),
    )
    work = hourly[hourly["work"]].groupby(keys).agg(
        era5_work_temp_mean=("temperature_2m", "mean"),
        era5_work_rh_mean=("relative_humidity_2m", "mean"),
        era5_work_wetbulb_mean=("wet_bulb_temperature_2m", "mean"),
        era5_work_sun_wh=("shortwave_radiation", "sum"),
        era5_work_direct_sun_wh=("direct_radiation", "sum"),
        era5_work_wind_mean=("wind_speed_10m", "mean"),
        era5_work_rain_max_hour=("precipitation", "max"),
    )
    return all_day.join(work).reset_index()


def psi_region_days() -> pd.DataFrame:
    """Highest 24-hour PSI per region and day: the 2014 history, then the real-time feed."""
    history_path = DATA_DIR / "psi" / "psi_history_24hr.parquet"
    require(history_path)
    history = pd.read_parquet(history_path)
    history["day"] = history["timestamp"].dt.tz_convert("Asia/Singapore").dt.tz_localize(None)
    history["day"] = history["day"].dt.normalize()
    history = (
        history.groupby(["region", "day"])["psi_twenty_four_hourly"].max().rename("psi_max")
    )
    realtime = pd.read_parquet(PROC_DIR / "psi_daily.parquet")
    realtime = realtime.melt(
        id_vars="day", value_vars=[f"psi_{region}" for region in REGIONS], value_name="reading"
    )
    realtime["region"] = realtime.pop("variable").str.removeprefix("psi_")
    realtime = realtime.set_index(["region", "day"])["reading"].rename("psi_max")
    return history.combine_first(realtime).dropna().reset_index()


def rain_station_locations() -> pd.DataFrame:
    stations = pd.read_csv(DATA_DIR / "rainfall" / "stations.csv")
    stations["region"] = stations["station_id"].map(nearest_region(stations))
    return stations[["station_id", "latitude", "longitude", "region"]]


def mss_station_days() -> pd.DataFrame:
    path = DATA_DIR / "mss_daily" / "mss_daily.parquet"
    require(path)
    days = pd.read_parquet(path).drop(columns=["station_name"])
    days["day"] = pd.to_datetime(days.pop("date"))
    return days.merge(rain_station_locations(), on="station_id", how="inner")


def wbgt_station_locations() -> pd.DataFrame:
    readings = pd.concat(
        pd.read_parquet(path, columns=["station_id", "latitude", "longitude"])
        for path in sorted((DATA_DIR / "wbgt").glob("wbgt_*.parquet"))
    )
    stations = readings.groupby("station_id")[["latitude", "longitude"]].last().reset_index()
    stations["region"] = stations["station_id"].map(nearest_region(stations))
    return stations


def wbgt_station_days() -> pd.DataFrame:
    days = pd.read_parquet(PROC_DIR / "wbgt_station_days.parquet")
    days = days[days["readings"] >= MIN_WBGT_READINGS_PER_DAY]
    days = days[["station_id", "day", "max_wbgt", "hours_ge_32"]].copy()
    days["day"] = pd.to_datetime(days["day"]).dt.normalize()
    return days.merge(wbgt_station_locations(), on="station_id", how="inner")


def climate_indices() -> pd.DataFrame:
    path = DATA_DIR / "climate_indices" / "climate_indices_monthly.csv"
    require(path)
    indices = pd.read_csv(path)
    indices["month"] = pd.PeriodIndex(indices["month"], freq="M")
    return indices
