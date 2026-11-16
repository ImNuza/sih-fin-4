"""Run the published models once and write the small tables the API serves.

The API image has numpy but no pandas or ML libraries, so the models run here, offline:
    heat_h0_regression   rebuilds hours at WBGT 32°C or more at every hawker centre, every day
                         since 1980, from ERA5 (real WBGT only exists from 2025), then
                         quantile-mapped to the measured 2025-2026 hours (see quantile_mapped)
    rain_h0_regression   rebuilds the wettest hour at each MSS gauge before 2014 from the
                         gauge's daily total and ERA5 (MSS has only daily totals before 2014);
                         MSS and rebuilt values are then matched to the wettest work hour that
                         NEA gauges measure from December 2016, which is what the tariff reads
    haze (resampled)     NEA's PSI record starts in April 2014. Each earlier year takes the
                         daily PSI of the measured year (2015-2025) whose Aug-Oct El Nino
                         index (ONI) is nearest its own, since El Nino drives Singapore's haze
                         (see haze_history)
Measured readings always win: a day uses the rebuilt value only when no station measured it.
The API turns these readings into money with the live tariff (api/model_history.py), so a
tariff change reprices every year without rerunning this script.

Usage:
    uv run --group ml python -m ml.serving
    uv run --group ml python -m ml.serving --haze-only   # redo haze in the existing file

Reads  ml/results/ (models, leaderboard, confusion metrics), data/ (see ml/data.py),
       data/processed/map_static.json (the hawker centres)
Writes data/processed/model_history.npz    per centre and day: haze, rain, heat and the source
                                           of each (0 none, 1 measured, 2 rebuilt by a model,
                                           3 matched, 4 resampled from a measured year)
       data/processed/model_insights.json  model scores against baselines, confusion counts,
                                           and the haze facts the dashboards quote
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from ml import data
from ml.config import PROC_DIR, RECONSTRUCTION, REPO_ROOT
from ml.features import add_weather_calendar_place, trigger_level
from ml.models import predict
from hazard_stats import load_rain

RESULTS_DIR = REPO_ROOT / "ml" / "results"
HISTORY_OUT = PROC_DIR / "model_history.npz"
INSIGHTS_OUT = PROC_DIR / "model_insights.json"
MAP_STATIC_PATH = PROC_DIR / "map_static.json"
FIRST_DAY = "1980-01-01"
CENTRES_PER_BATCH = 10
# Where a day's reading came from: nothing, measured as the tariff defines it, rebuilt by a
# model, or measured by MSS as the whole day's wettest hour and matched to work hours.
NONE, MEASURED, REBUILT, MATCHED, RESAMPLED = 0, 1, 2, 3, 4
# A gauge that sent under half its 12 work hours did not report (as build_day_readings.py).
MIN_WORK_HOURS_REPORTED = 6
# El Nino is strong when the Aug-Oct ONI averages this or more (NOAA's moderate threshold).
EL_NINO_ONI = 1.0
FIRST_FULL_HAZE_YEAR = 2015
# The last year whose haze is wholly measured; later years may stop before the haze season.
LAST_FULL_HAZE_YEAR = 2025
HAZE_SEASON_MONTHS = (8, 9, 10)
FIRST_HISTORY_YEAR = 1980
QUANTILE_STEPS = 1001
# np.interp needs strictly rising levels; equal quantiles get this much apart.
TIE_BREAK = 1e-9
BASELINES = ("climatology", "persistence")

# What each job is for, in the words the dashboards use. "live" says whether it can run on
# today's data: ERA5 arrives about five days late, so next-day weather models cannot.
JOB_ROLES = {
    "heat_h0": ("Heat rebuild", "Fills heat for 1980 to 2024, so heat payouts have 46 years of "
                "history instead of 2.", "In use before 2025, after matching its share of hot "
                "days to the measured 2025-2026 readings (9.0 rebuilt against 9.0 measured hot "
                "days in 2025): the raw scores here are before that matching."),
    "rain_h0": ("Rain rebuild", "Fills the wettest rain hour for 1980 to 2013 from each gauge's "
                "daily total.", "In use before 2014, matched to the wettest work hour NEA "
                "gauges measured from 2017."),
    "haze_h1": ("Haze tomorrow", "Forecasts tomorrow's PSI for warnings and cash planning.",
                "Not used: it does not beat 'same as today'."),
    "haze_h7": ("Haze next week", "Forecasts PSI a week ahead.",
                "Not used: it does not beat 'same as today'."),
    "heat_h1": ("Heat tomorrow", "Forecasts tomorrow's hot hours.",
                "Not live: it needs ERA5, which arrives about five days late."),
    "rain_h1": ("Rain tomorrow", "Forecasts tomorrow's wettest hour at a gauge.",
                "Not live: it needs ERA5, and a gauge's rain is hard to call a day ahead."),
    "haze_season": ("Haze days next month", "Forecasts payout days a month per region.",
                    "Not used: the long-run monthly average does as well."),
    "rain_season": ("Rain days next month", "Forecasts payout days a month per region.",
                    "Not used: the long-run monthly average does as well."),
}


def load_model(job: str) -> dict:
    path = RESULTS_DIR / "models" / f"{job}.joblib"
    if not path.exists():
        raise SystemExit(f"Missing {path}. Pull the training results (ml/results/) first.")
    return joblib.load(path)


def predict_saved(saved: dict, frame: pd.DataFrame) -> np.ndarray:
    return predict(saved["model"], frame[saved["features"]], saved["kind"])


def hawker_centres() -> pd.DataFrame:
    centres = pd.DataFrame(json.loads(MAP_STATIC_PATH.read_text())["hawker_centres"])
    return centres[["name", "lat", "lng", "region"]]


def distance_order(centres: pd.DataFrame, stations: pd.DataFrame) -> np.ndarray:
    """For each centre, station row numbers from nearest to farthest."""
    lat = centres["lat"].to_numpy()[:, None] - stations["latitude"].to_numpy()
    lng = centres["lng"].to_numpy()[:, None] - stations["longitude"].to_numpy()
    return np.argsort(lat**2 + lng**2, axis=1)


def nearest_reported(
    values: np.ndarray, sources: np.ndarray, order: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Per centre and day, the nearest station's value among those with one that day."""
    centres, days = order.shape[0], values.shape[1]
    out = np.full((centres, days), np.nan, dtype=np.float32)
    out_source = np.zeros((centres, days), dtype=np.int8)
    for centre in range(centres):
        for station in order[centre]:
            fill = np.isnan(out[centre]) & ~np.isnan(values[station])
            out[centre, fill] = values[station, fill]
            out_source[centre, fill] = sources[station, fill]
            if not np.isnan(out[centre]).any():
                break
    return out, out_source


def station_matrix(
    table: pd.DataFrame, value: str, source: str, days: pd.DatetimeIndex
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Stations (with places) and their station-by-day value and source matrices."""
    stations = table.groupby("unit")[["latitude", "longitude"]].first().reset_index()
    values = table.pivot(index="unit", columns="day", values=value).reindex(
        index=stations["unit"], columns=days
    )
    sources = table.pivot(index="unit", columns="day", values=source).reindex(
        index=stations["unit"], columns=days
    )
    return (
        stations,
        values.to_numpy(dtype=np.float32),
        sources.fillna(NONE).to_numpy(dtype=np.int8),
    )


def nea_work_hour_rain() -> pd.DataFrame:
    """The wettest work hour per NEA gauge and day, where the gauge reported enough hours."""
    rain = load_rain()
    work = rain[rain["work_hour"]]
    by_day = work.groupby(["station_id", "day"])["rain_mm"].agg(["max", "size"]).reset_index()
    by_day = by_day[by_day["size"] >= MIN_WORK_HOURS_REPORTED]
    by_day = by_day.rename(columns={"station_id": "unit", "max": "rain"})
    locations = data.rain_station_locations().rename(columns={"station_id": "unit"})
    return by_day.merge(locations, on="unit")[["unit", "day", "rain", "latitude", "longitude"]]


def rain_history(centres: pd.DataFrame, days: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Rain as the tariff reads it: the wettest work hour at the nearest gauge.

    NEA gauges give that directly from December 2016. MSS publishes the wettest 60 minutes of
    the whole day (from 2014) and the rain model rebuilds it before that. Both are mapped to
    the work-hour distribution on the station-days where both exist, so a day before 2017 pays
    as often as one after.
    """
    nea = nea_work_hour_rain()
    nea["source"] = MEASURED
    gauges = data.mss_station_days().dropna(subset=["rain_daily_mm"])
    gauges = gauges.rename(columns={"station_id": "unit"}).reset_index(drop=True)
    add_weather_calendar_place(gauges, RECONSTRUCTION)
    rebuilt = predict_saved(load_model(f"rain_h{RECONSTRUCTION}_regression"), gauges)
    published = gauges["rain_max_60min_mm"].notna()
    whole_day = np.where(published, gauges["rain_max_60min_mm"], rebuilt)
    overlap = gauges[["unit", "day"]].assign(whole_day=whole_day).merge(
        nea[["unit", "day", "rain"]], on=["unit", "day"]
    )
    gauges["rain"] = quantile_mapped(
        whole_day, overlap["whole_day"].to_numpy(), overlap["rain"].to_numpy()
    )
    gauges["source"] = np.where(published, MATCHED, REBUILT)
    print(f"  rain: {len(overlap):,} station-days to match MSS whole-day rain to work hours")

    stations, values, sources = station_matrix(nea, "rain", "source", days)
    measured, measured_source = nearest_reported(
        values, sources, distance_order(centres, stations)
    )
    stations, values, sources = station_matrix(gauges, "rain", "source", days)
    filled, filled_source = nearest_reported(values, sources, distance_order(centres, stations))
    use_measured = ~np.isnan(measured)
    rain = np.where(use_measured, measured, filled).astype(np.float32)
    return rain, np.where(use_measured, measured_source, filled_source).astype(np.int8)


def heat_history(centres: pd.DataFrame, days: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    model = load_model(f"heat_h{RECONSTRUCTION}_regression")
    rebuilt = np.empty((len(centres), len(days)), dtype=np.float32)
    for start in range(0, len(centres), CENTRES_PER_BATCH):
        batch = centres.iloc[start : start + CENTRES_PER_BATCH]
        grid = pd.DataFrame(
            {
                "unit": np.repeat(batch["name"].to_numpy(), len(days)),
                "day": np.tile(days, len(batch)),
                "region": np.repeat(batch["region"].to_numpy(), len(days)),
                "latitude": np.repeat(batch["lat"].to_numpy(), len(days)),
                "longitude": np.repeat(batch["lng"].to_numpy(), len(days)),
            }
        )
        add_weather_calendar_place(grid, RECONSTRUCTION)
        rebuilt[start : start + len(batch)] = predict_saved(model, grid).reshape(len(batch), -1)
        print(f"  heat rebuilt for {start + len(batch)}/{len(centres)} centres", flush=True)

    stations_days = data.wbgt_station_days().rename(columns={"station_id": "unit"})
    stations_days["source"] = MEASURED
    stations, values, sources = station_matrix(stations_days, "hours_ge_32", "source", days)
    measured, measured_source = nearest_reported(
        values, sources, distance_order(centres, stations)
    )
    use_measured = ~np.isnan(measured)
    matched = quantile_mapped(rebuilt, rebuilt[use_measured], measured[use_measured])
    heat = np.where(use_measured, measured, matched).astype(np.float32)
    return heat, np.where(use_measured, measured_source, REBUILT).astype(np.int8)


def quantile_mapped(values: np.ndarray, model_overlap: np.ndarray, measured_overlap: np.ndarray):
    """Give the model's values the measured distribution, keeping their order.

    The heat rebuild predicts close to the average hot hours every day, so it almost never
    reaches the 2-hour payout band (0.03% of days against 3.75% measured). Mapping each value's
    quantile on the 2025-2026 overlap to the same quantile of the measured hours keeps the
    model's ranking of days (cooler decades stay cooler) and restores how often heat pays.
    """
    shares = np.linspace(0, 1, QUANTILE_STEPS)
    model_levels = np.quantile(model_overlap, shares)
    model_levels = model_levels + np.arange(QUANTILE_STEPS) * TIE_BREAK
    return np.interp(values, model_levels, np.quantile(measured_overlap, shares))


def season_oni() -> pd.Series:
    """The Aug-Oct mean El Nino index (ONI) of each year."""
    indices = data.climate_indices().dropna(subset=["oni"])
    indices = indices[indices["month"].dt.month.isin(HAZE_SEASON_MONTHS)]
    return indices.groupby(indices["month"].dt.year)["oni"].mean()


def analog_years(years: list[int], oni: pd.Series) -> dict[int, int]:
    """For each year, the fully measured haze year whose Aug-Oct ONI is nearest its own.

    A year at or above the El Nino threshold only takes an El Nino year, and the other way
    round, so a calm year never borrows 2015's haze and 1997 never borrows a calm year's.
    """
    measured = [y for y in range(FIRST_FULL_HAZE_YEAR, LAST_FULL_HAZE_YEAR + 1) if y in oni.index]
    picks = {}
    for year in years:
        strong = oni[year] >= EL_NINO_ONI
        same_kind = [y for y in measured if (oni[y] >= EL_NINO_ONI) == strong] or measured
        picks[year] = min(same_kind, key=lambda y: abs(oni[y] - oni[year]))
    return picks


def analog_day(day: pd.Timestamp, analog: int) -> pd.Timestamp:
    """The same calendar day in the analog year; 29 February becomes the 28th."""
    return pd.Timestamp(analog, day.month, 28 if (day.month, day.day) == (2, 29) else day.day)


def haze_history(centres: pd.DataFrame, days: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Highest 24-hour PSI per centre and day: measured from April 2014, resampled before.

    A day with no PSI record before FIRST_FULL_HAZE_YEAR takes the same calendar day of its
    year's analog (analog_years). Measured days are never replaced.
    """
    psi = data.psi_region_days().pivot(index="region", columns="day", values="psi_max")
    measured = psi.reindex(columns=days)
    unmeasured = measured.isna().all(axis=0).to_numpy()
    oni = season_oni()
    years = sorted({d.year for d in days[unmeasured] if d.year < FIRST_FULL_HAZE_YEAR and d.year in oni.index})
    picks = analog_years(years, oni)
    filled = measured.copy()
    for year, analog in picks.items():
        gap = days[(days.year == year) & unmeasured]
        filled.loc[:, gap] = psi.reindex(columns=[analog_day(d, analog) for d in gap]).to_numpy()
    haze = filled.reindex(centres["region"]).to_numpy(dtype=np.float32)
    is_measured = ~np.isnan(measured.reindex(centres["region"]).to_numpy(dtype=np.float32))
    source = np.where(is_measured, MEASURED, np.where(np.isnan(haze), NONE, RESAMPLED))
    print("  haze analogs: " + ", ".join(f"{y}<-{a}" for y, a in picks.items()), flush=True)
    return haze, source.astype(np.int8)


def refill_haze() -> None:
    """Redo only the haze rows of the existing model_history.npz."""
    stored = dict(np.load(HISTORY_OUT))
    days = pd.DatetimeIndex(pd.Timestamp("1970-01-01") + pd.to_timedelta(stored["days"], unit="D"))
    centres = hawker_centres().set_index("name").loc[stored["centres"]].reset_index()
    stored["haze"], stored["haze_source"] = haze_history(centres, days)
    np.savez_compressed(HISTORY_OUT, **stored)
    shares = {label: round(float(np.mean(stored["haze_source"] == code)), 3)
              for label, code in (("none", NONE), ("measured", MEASURED), ("resampled", RESAMPLED))}
    print(f"  haze: {shares}. Wrote {HISTORY_OUT.name}")


def job_rows(board: pd.DataFrame, chosen: pd.DataFrame, metrics: pd.DataFrame) -> list[dict]:
    rows = []
    for _, pick in chosen.iterrows():
        job = pick["job"]
        stem = job.rsplit("_", 1)[0]
        kind = job.rsplit("_", 1)[1]
        name, purpose, use = JOB_ROLES[stem]
        score = pick["score_name"]
        ok = board[(board["job"] == job) & (board["status"] == "ok")]
        baselines = ok[ok["model"].isin(BASELINES)]
        higher_better = score in ("test_average_precision",)
        best_baseline = (
            baselines.loc[baselines[score].idxmax() if higher_better else baselines[score].idxmin()]
            if not baselines.empty else None
        )
        row = {
            "job": job,
            "name": name,
            "target": {"regression": "the reading", "classification": "a payout day or not",
                       "count": "payout days a month"}[kind],
            "purpose": purpose,
            "use": use,
            "model": pick["model"],
            "score_name": score.removeprefix("test_"),
            "higher_is_better": higher_better,
            "score": round(float(pick["score"]), 4),
            "baseline": None if best_baseline is None else best_baseline["model"],
            "baseline_score": (
                None if best_baseline is None else round(float(best_baseline[score]), 4)
            ),
        }
        counts = metrics[(metrics["job"] == job) & (metrics["model"] == pick["model"])]
        if not counts.empty:
            first = counts.iloc[0]
            row["confusion"] = {key: int(first[key]) for key in ("TP", "FN", "FP", "TN")}
            row["precision"] = round(float(first["precision"]), 3)
            row["recall"] = round(float(first["recall"]), 3)
        rows.append(row)
    return rows


def haze_facts() -> dict:
    """How haze behaves: how often a bad day follows a bad day, and El Nino years."""
    level = trigger_level("haze")
    psi = data.psi_region_days().sort_values(["region", "day"])
    psi["bad"] = psi["psi_max"] >= level
    psi["bad_next"] = psi.groupby("region")["bad"].shift(-1)
    bad_days = psi[psi["bad"] & psi["bad_next"].notna()]
    region_days = psi.groupby(psi["day"].dt.year)["bad"].sum() / psi["region"].nunique()
    all_indices = data.climate_indices().dropna(subset=["oni"])
    latest = all_indices.iloc[-1]
    indices = all_indices[all_indices["month"].dt.month.isin([8, 9, 10])]
    oni = indices.groupby(indices["month"].dt.year)["oni"].mean()
    el_nino_years = [int(y) for y in oni.index if y >= FIRST_HISTORY_YEAR and oni[y] >= EL_NINO_ONI]
    # 2014 starts in April. 2026 runs to November, past its haze season, so it counts.
    full_years = region_days.loc[FIRST_FULL_HAZE_YEAR:]
    el_nino = full_years[full_years.index.isin(el_nino_years)]
    other = full_years[~full_years.index.isin(el_nino_years)]
    return {
        "trigger_psi": level,
        "next_day_bad_share": round(float(bad_days["bad_next"].mean()), 3),
        "el_nino_years": el_nino_years,
        "haze_el_nino_years": [int(y) for y in el_nino.index],
        "haze_days_el_nino": round(float(el_nino.mean()), 1),
        "haze_days_other": round(float(other.mean()), 1),
        "latest_oni": round(float(latest["oni"]), 2),
        "latest_oni_month": str(latest["month"]),
        "el_nino_now": bool(latest["oni"] >= EL_NINO_ONI),
    }


def insights(last_day: pd.Timestamp) -> dict:
    board = pd.read_csv(RESULTS_DIR / "leaderboard.csv")
    chosen = pd.read_csv(RESULTS_DIR / "models" / "index.csv")
    metrics = pd.read_csv(RESULTS_DIR / "confusion_metrics.csv")
    return {
        "data_to": last_day.date().isoformat(),
        "models": job_rows(board, chosen, metrics),
        "haze": haze_facts(),
        "sources": "NEA via data.gov.sg, MSS daily records, ERA5 by Copernicus / ECMWF via "
        "Open-Meteo (CC BY 4.0), NOAA PSL climate indices.",
    }


def main() -> None:
    centres = hawker_centres()
    last_day = data.era5_daily()["day"].max()
    days = pd.date_range(FIRST_DAY, last_day, freq="D")
    print(f"{len(centres)} centres x {len(days)} days, {days[0].date()} to {days[-1].date()}")
    haze, haze_source = haze_history(centres, days)
    rain, rain_source = rain_history(centres, days)
    print("  rain done", flush=True)
    heat, heat_source = heat_history(centres, days)
    np.savez_compressed(
        HISTORY_OUT,
        days=(days - pd.Timestamp("1970-01-01")).days.to_numpy(dtype=np.int32),
        centres=centres["name"].to_numpy(dtype=str),
        haze=haze, haze_source=haze_source,
        rain=rain, rain_source=rain_source,
        heat=heat, heat_source=heat_source,
    )
    INSIGHTS_OUT.write_text(json.dumps(insights(last_day), indent=1))
    for name, source in (("haze", haze_source), ("rain", rain_source), ("heat", heat_source)):
        shares = {label: round(float(np.mean(source == code)), 3)
                  for label, code in (("none", NONE), ("measured", MEASURED),
                                      ("rebuilt", REBUILT), ("matched", MATCHED),
                                      ("resampled", RESAMPLED))}
        print(f"  {name}: {shares}")
    print(f"Wrote {HISTORY_OUT.name} ({HISTORY_OUT.stat().st_size / 1e6:.1f} MB) and "
          f"{INSIGHTS_OUT.name}")


if __name__ == "__main__":
    import sys

    refill_haze() if "--haze-only" in sys.argv[1:] else main()
