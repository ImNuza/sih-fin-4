"""Data loading for the dashboard.

Reads the committed Parquet files. Calls the API only for the live readings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from dgs import DgsClient  # noqa: E402

DATA = REPO_ROOT / "data"
WORK_START_HOUR, WORK_END_HOUR = 7, 19
TZ = "Asia/Singapore"


def _read_all(folder: str, pattern: str) -> pd.DataFrame:
    files = sorted((DATA / folder).glob(pattern))
    if not files:
        return pd.DataFrame()
    return pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)


@st.cache_data(show_spinner="Loading heat readings...")
def wbgt_readings() -> pd.DataFrame:
    frame = _read_all("wbgt", "wbgt_*.parquet")
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(TZ)
    latest = frame.sort_values("timestamp").groupby("station_id")["station_name"].last()
    frame["station_name"] = frame["station_id"].map(latest)
    frame["day"] = frame["timestamp"].dt.tz_localize(None).dt.normalize()
    hour = frame["timestamp"].dt.hour
    frame["work_hours"] = (hour >= WORK_START_HOUR) & (hour < WORK_END_HOUR)
    return frame


@st.cache_data
def wbgt_stations() -> pd.DataFrame:
    frame = wbgt_readings()
    stations = frame.groupby("station_id").agg(
        station_name=("station_name", "last"),
        latitude=("latitude", "last"),
        longitude=("longitude", "last"),
        days=("day", "nunique"),
    )
    return stations.reset_index()


@st.cache_data
def heat_station_days(threshold: float) -> pd.DataFrame:
    """Per station per day in work hours: max WBGT and hours at or above the threshold."""
    work = wbgt_readings()
    work = work[work["work_hours"]]
    out = (
        work.assign(hit=(work["wbgt"] >= threshold) * 0.25)
        .groupby(["station_id", "day"])
        .agg(max_wbgt=("wbgt", "max"), hours_at_or_above=("hit", "sum"))
    )
    return out.reset_index()


@st.cache_data(show_spinner="Loading rain readings...")
def rain_hourly() -> pd.DataFrame:
    frame = _read_all("rainfall", "rain_hourly_*.parquet")
    if frame.empty:
        return frame
    local = frame["hour"].dt.tz_convert(TZ)
    frame["day"] = local.dt.tz_localize(None).dt.normalize()
    frame["work_hours"] = (local.dt.hour >= WORK_START_HOUR) & (local.dt.hour < WORK_END_HOUR)
    return frame


@st.cache_data
def rain_stations() -> pd.DataFrame:
    path = DATA / "rainfall" / "stations.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data
def rain_station_days(mm_per_hour: float) -> pd.DataFrame:
    rain = rain_hourly()
    work = rain[rain["work_hours"]]
    out = (
        work.assign(hit=work["rain_mm"] >= mm_per_hour)
        .groupby(["station_id", "day"])
        .agg(rain_mm=("rain_mm", "sum"), hours_at_or_above=("hit", "sum"))
    )
    return out.reset_index()


@st.cache_data(show_spinner="Loading haze readings...")
def psi_hourly() -> pd.DataFrame:
    frame = _read_all("psi", "psi_*.parquet")
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(TZ)
    frame["day"] = frame["timestamp"].dt.tz_localize(None).dt.normalize()
    return frame


@st.cache_data
def psi_region_days() -> pd.DataFrame:
    psi = psi_hourly()
    return (
        psi.groupby(["region", "day"])["psi_twenty_four_hourly"].max().reset_index(name="psi_max")
    )


@st.cache_data(ttl=600, show_spinner="Fetching live NEA readings...")
def live_readings() -> dict[str, pd.DataFrame]:
    """Latest readings from data.gov.sg. Cached for 10 minutes. The API key stays on the server."""
    client = DgsClient(max_retries=2)  # fail fast in the UI instead of waiting out a rate limit
    out: dict[str, pd.DataFrame] = {}
    body = client.get("weather", {"api": "wbgt"})
    if body:
        record = body["data"]["records"][0]
        out["wbgt"] = pd.DataFrame(
            [
                {
                    "station": r["station"]["name"],
                    "latitude": float(r["location"]["latitude"]),
                    "longitude": float(r["location"]["longitude"]),
                    "wbgt": pd.to_numeric(r.get("wbgt"), errors="coerce"),
                    "heat_stress": r.get("heatStress"),
                    "time": record["datetime"],
                }
                for r in record["item"]["readings"]
            ]
        )
    body = client.get("psi", {})
    if body:
        item = body["data"]["items"][0]
        psi = item["readings"]["psi_twenty_four_hourly"]
        out["psi"] = pd.DataFrame(
            [{"region": k, "psi_24h": v, "time": item["timestamp"]} for k, v in psi.items()]
        )
    body = client.get("rainfall", {})
    if body:
        names = {s["id"]: s for s in body["data"]["stations"]}
        reading = body["data"]["readings"][0]
        out["rain"] = pd.DataFrame(
            [
                {
                    "station": names.get(d["stationId"], {}).get("name", d["stationId"]),
                    "latitude": names.get(d["stationId"], {}).get("location", {}).get("latitude"),
                    "longitude": names.get(d["stationId"], {}).get("location", {}).get("longitude"),
                    "rain_mm_5min": d["value"],
                    "time": reading["timestamp"],
                }
                for d in reading["data"]
            ]
        )
    return out
