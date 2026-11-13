"""Feature tables for each task: one row per unit (region or station) and target day.

For a forecast with horizon h, every feature is known at the end of day d - h, where d is the
target day. For a reconstruction (h = 0), the features are same-day ERA5, place and calendar,
with no readings of the target at all, so the model can rebuild days and places with no sensor.
Rain reconstruction also gets the gauge's same-day total: MSS has daily totals from 1980 but the
wettest hour only from 2014, so this rebuilds the wettest hour for the earlier years.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml import data
from ml.config import (
    CLIMATE_INDEX_LAGS_MONTHS,
    RECONSTRUCTION,
    DailyTask,
    SeasonalTask,
)

ID_COLUMNS = ["day", "unit", "region"]
TARGET_LAGS_DAYS = (0, 1, 2, 6)
ROLLING_WINDOWS_DAYS = (7, 30)
ERA5_ROLLING_WINDOWS_DAYS = (3, 7, 30)
DRY_DAY_RAIN_MM = 1.0
SEASONAL_COUNT_LAGS_MONTHS = (1, 2, 3, 12)
# Monsoon phases as described by MSS: NE Dec-Mar, inter-monsoon Apr-May, SW Jun-Sep,
# inter-monsoon Oct-Nov.
MONSOON_PHASE_BY_MONTH = {
    12: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3,
}


def trigger_level(hazard_key: str) -> float:
    """The reading at which the tariff's first payout band starts."""
    hazard = next(h for h in data.load_tariff().hazards if h.key == hazard_key)
    return hazard.bands[0].at_least


def target_table(task: DailyTask) -> pd.DataFrame:
    if task.name == "haze":
        table = data.psi_region_days()
        table["unit"] = table["region"]
        return table
    if task.name == "rain":
        table = data.mss_station_days()
        table["unit"] = table["station_id"]
        return table.drop(columns=["station_id"])
    if task.name == "heat":
        table = data.wbgt_station_days()
        table["unit"] = table["station_id"]
        return table.drop(columns=["station_id"])
    raise KeyError(task.name)


def daily_grid(table: pd.DataFrame) -> pd.DataFrame:
    """Every unit gets every day between its first and last reading, so shifts are in days."""
    spans = table.groupby("unit")["day"].agg(["min", "max"])
    grid = pd.concat(
        pd.DataFrame({"unit": unit, "day": pd.date_range(row["min"], row["max"], freq="D")})
        for unit, row in spans.iterrows()
    )
    place_columns = [c for c in ("region", "latitude", "longitude") if c in table.columns]
    places = table.groupby("unit")[place_columns].first().reset_index()
    readings = table.drop(columns=place_columns)
    return grid.merge(places, on="unit").merge(readings, on=["unit", "day"], how="left")


def add_target_history(
    grid: pd.DataFrame, columns: list[str], horizon: int, trigger: float, target: str
) -> list[str]:
    """Past readings known at the end of day d - horizon."""
    by_unit = grid.groupby("unit", sort=False)
    names = []
    for column in columns:
        for lag in TARGET_LAGS_DAYS:
            name = f"{column}_lag{horizon + lag}"
            grid[name] = by_unit[column].shift(horizon + lag)
            names.append(name)
        known = by_unit[column].shift(horizon)
        for window in ROLLING_WINDOWS_DAYS:
            rolling = known.groupby(grid["unit"]).rolling(window, min_periods=1)
            grid[f"{column}_mean{window}d"] = rolling.mean().reset_index(level=0, drop=True)
            grid[f"{column}_max{window}d"] = rolling.max().reset_index(level=0, drop=True)
            names += [f"{column}_mean{window}d", f"{column}_max{window}d"]
    triggered = (by_unit[target].shift(horizon) >= trigger).astype(float)
    triggered[by_unit[target].shift(horizon).isna()] = np.nan
    grid["trigger_days_30d"] = (
        triggered.groupby(grid["unit"]).rolling(30, min_periods=1).sum()
        .reset_index(level=0, drop=True)
    )
    return names + ["trigger_days_30d"]


def era5_with_rolling() -> pd.DataFrame:
    era5 = data.era5_daily().sort_values(["region", "day"])
    by_region = era5.groupby("region", sort=False)
    for window in ERA5_ROLLING_WINDOWS_DAYS:
        era5[f"era5_rain_sum_{window}d"] = by_region["era5_rain_sum"].transform(
            lambda s, w=window: s.rolling(w, min_periods=1).sum()
        )
        era5[f"era5_temp_max_mean_{window}d"] = by_region["era5_temp_max"].transform(
            lambda s, w=window: s.rolling(w, min_periods=1).mean()
        )
        era5[f"era5_rh_mean_{window}d"] = by_region["era5_rh_mean"].transform(
            lambda s, w=window: s.rolling(w, min_periods=1).mean()
        )
    wet = era5["era5_rain_sum"] >= DRY_DAY_RAIN_MM
    spell = wet.groupby([era5["region"], wet.cumsum()]).cumcount()
    era5["era5_dry_days_in_a_row"] = np.where(wet, 0, spell)
    return era5


def add_era5(grid: pd.DataFrame, horizon: int) -> list[str]:
    era5 = era5_with_rolling()
    names = [c for c in era5.columns if c not in ("region", "day")]
    era5 = era5.rename(columns={"day": "feature_day"})
    grid["feature_day"] = grid["day"] - pd.Timedelta(days=horizon)
    merged = grid.merge(era5, on=["region", "feature_day"], how="left")
    grid[names] = merged[names].to_numpy()
    grid.drop(columns="feature_day", inplace=True)
    return names


def add_calendar(frame: pd.DataFrame) -> list[str]:
    day_of_year = frame["day"].dt.dayofyear
    frame["month"] = frame["day"].dt.month
    frame["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    frame["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    frame["day_of_week"] = frame["day"].dt.dayofweek
    frame["monsoon_phase"] = frame["month"].map(MONSOON_PHASE_BY_MONTH)
    frame["year"] = frame["day"].dt.year
    return ["month", "day_of_year_sin", "day_of_year_cos", "day_of_week", "monsoon_phase", "year"]


def add_climate_indices(frame: pd.DataFrame, month: pd.Series) -> list[str]:
    indices = data.climate_indices().set_index("month")
    names = []
    for lag in CLIMATE_INDEX_LAGS_MONTHS:
        source_month = month - lag
        for index in ("oni", "dmi"):
            name = f"{index}_lag{lag}m"
            frame[name] = source_month.map(indices[index]).to_numpy()
            names.append(name)
    return names


def add_place(frame: pd.DataFrame) -> list[str]:
    frame["region_code"] = frame["region"].map({r: i for i, r in enumerate(data.REGIONS)})
    return ["region_code"] + [c for c in ("latitude", "longitude") if c in frame.columns]


def add_weather_calendar_place(grid: pd.DataFrame, horizon: int) -> list[str]:
    """Features that need only a place and a day, so they exist for any site and year."""
    features = add_era5(grid, horizon)
    features += add_calendar(grid)
    features += add_climate_indices(grid, grid["day"].dt.to_period("M"))
    return features + add_place(grid)


def daily_frame(task: DailyTask, horizon: int) -> tuple[pd.DataFrame, list[str]]:
    """Feature table for a daily task; the target column keeps its name."""
    grid = daily_grid(target_table(task)).sort_values(["unit", "day"]).reset_index(drop=True)
    features = []
    if horizon == RECONSTRUCTION and task.name == "rain":
        features.append("rain_daily_mm")
    if horizon != RECONSTRUCTION:
        history = [task.target] + (["rain_daily_mm"] if task.name == "rain" else [])
        features += add_target_history(
            grid, history, horizon, trigger_level(task.hazard_key), task.target
        )
    features += add_weather_calendar_place(grid, horizon)
    if horizon == RECONSTRUCTION:
        # A rebuild is applied to years far outside the training years (heat trains on
        # 2025-2026 and rebuilds 1980 on), so it must not lean on the year.
        features.remove("year")
    frame = grid.dropna(subset=[task.target])
    return frame[ID_COLUMNS + features + [task.target]].reset_index(drop=True), features


def monthly_trigger_days(task: SeasonalTask) -> pd.DataFrame:
    """Trigger days per region and month. For rain, the mean over the region's gauges."""
    level = trigger_level(task.hazard_key)
    if task.hazard_key == "haze":
        days = data.psi_region_days()
        days["unit"] = days["region"]
        reading = "psi_max"
    else:
        days = data.mss_station_days().dropna(subset=["rain_max_60min_mm"])
        days["unit"] = days["station_id"]
        reading = "rain_max_60min_mm"
    days["month"] = days["day"].dt.to_period("M")
    days["triggered"] = days[reading] >= level
    per_unit = days.groupby(["region", "unit", "month"]).agg(
        trigger_days=("triggered", "sum"), days_observed=("triggered", "size")
    )
    per_region = per_unit.groupby(["region", "month"]).agg(
        trigger_days=("trigger_days", "mean"), units=("trigger_days", "size")
    )
    return per_region.reset_index()


def seasonal_frame(task: SeasonalTask) -> tuple[pd.DataFrame, list[str]]:
    counts = monthly_trigger_days(task)
    months = pd.period_range(counts["month"].min(), counts["month"].max(), freq="M")
    grid = pd.MultiIndex.from_product([data.REGIONS, months], names=["region", "month"])
    frame = counts.set_index(["region", "month"]).reindex(grid).reset_index()
    by_region = frame.groupby("region", sort=False)["trigger_days"]
    features = []
    for lag in SEASONAL_COUNT_LAGS_MONTHS:
        frame[f"trigger_days_lag{lag}m"] = by_region.shift(lag)
        features.append(f"trigger_days_lag{lag}m")
    era5 = data.era5_daily()
    era5["month"] = era5["day"].dt.to_period("M")
    era5_monthly = era5.groupby(["region", "month"]).agg(
        era5_month_rain_sum=("era5_rain_sum", "sum"),
        era5_month_temp_max=("era5_temp_max", "mean"),
        era5_month_rh_mean=("era5_rh_mean", "mean"),
    )
    era5_monthly = era5_monthly.groupby("region").shift(1).add_suffix("_lag1m").reset_index()
    frame = frame.merge(era5_monthly, on=["region", "month"], how="left")
    features += [c for c in era5_monthly.columns if c.endswith("_lag1m")]
    frame["day"] = frame["month"].dt.to_timestamp()
    frame["unit"] = frame["region"]
    frame["month_of_year"] = frame["month"].dt.month
    frame["monsoon_phase"] = frame["month_of_year"].map(MONSOON_PHASE_BY_MONTH)
    frame["year"] = frame["month"].dt.year
    features += ["month_of_year", "monsoon_phase", "year"]
    features += add_climate_indices(frame, frame["month"])
    features += add_place(frame)
    frame = frame.dropna(subset=[task.target])
    return frame[ID_COLUMNS + features + [task.target]].reset_index(drop=True), features
