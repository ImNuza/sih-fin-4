"""Back-test: what the cover would have paid each year since 1980, per tier and product.

Customers sit at the MSS rain gauges. For each gauge and day:
    haze  the region's highest 24-hour PSI (NEA, from Apr 2014; none before)
    rain  the gauge's wettest hour (MSS from 2014; rebuilt by the rain reconstruction model
          from the gauge's daily total and ERA5 before that)
    heat  hours with WBGT at 32°C or more, rebuilt by the heat reconstruction model from ERA5
Each day goes through the tariff (api/calculator.py), the yearly cap of paid days applies per
customer, and the premium is priced from the years with all three hazards.

Usage:
    uv run --group ml python -m ml.backtest       (after ml.run_all has trained the models)

Reads  ml/output/leaderboard.csv and the models it names, the data tables of ml.data
Writes ml/output/backtest_yearly.csv   one row per year, product and tier
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from api.calculator import find, hazard_loss, product_factor, severities, yearly_premium
from ml import data
from ml.config import (
    BACKTEST_PATH,
    BACKTEST_PRODUCT_KEYS,
    LEADERBOARD_PATH,
    MODEL_DIR,
    RECONSTRUCTION,
)
from ml.features import add_weather_calendar_place
from ml.models import predict

HAZARD_KEYS = ("haze", "rain", "heat")
FIRST_FULL_BUNDLE_YEAR = 2015


def best_model_path(job: str) -> tuple[str, object]:
    if not LEADERBOARD_PATH.exists():
        raise SystemExit(f"Missing {LEADERBOARD_PATH}. Run ml.run_all first.")
    board = pd.read_csv(LEADERBOARD_PATH)
    candidates = board[(board["job"] == job) & (board["status"] == "ok")]
    if candidates.empty:
        raise SystemExit(f"No trained model for {job} in {LEADERBOARD_PATH}.")
    best = candidates.sort_values("test_rmse").iloc[0]
    return best["model"], MODEL_DIR / f"{job}__{best['model']}.joblib"


def reconstruct(job: str, grid: pd.DataFrame) -> tuple[np.ndarray, str]:
    model_name, path = best_model_path(job)
    saved = joblib.load(path)
    return predict(saved["model"], grid[saved["features"]], saved["kind"]), model_name


def gauge_days() -> tuple[pd.DataFrame, dict[str, str]]:
    """One row per gauge and day with the three readings and where each came from."""
    gauges = data.mss_station_days().dropna(subset=["rain_daily_mm"])
    gauges = gauges.rename(columns={"station_id": "unit"}).reset_index(drop=True)
    add_weather_calendar_place(gauges, RECONSTRUCTION)

    rain_model_values, rain_model = reconstruct(f"rain_h{RECONSTRUCTION}_regression", gauges)
    measured = gauges["rain_max_60min_mm"].notna()
    gauges["rain"] = np.where(measured, gauges["rain_max_60min_mm"], rain_model_values)
    gauges["rain_measured"] = measured
    gauges["heat"], heat_model = reconstruct(f"heat_h{RECONSTRUCTION}_regression", gauges)

    haze = data.psi_region_days().rename(columns={"psi_max": "haze"})
    gauges = gauges.merge(haze, on=["region", "day"], how="left")
    gauges["year"] = gauges["day"].dt.year
    return gauges, {"rain": rain_model, "heat": heat_model}


def day_loss(gauges: pd.DataFrame, product_key: str) -> pd.DataFrame:
    """Loss share per hazard and combined, as in api.calculator.assess."""
    tariff = data.load_tariff()
    product = find(tariff.products, product_key, "product")
    factor = product_factor(product, tariff.pricing.recovered_share)
    losses = pd.DataFrame(index=gauges.index)
    for key in HAZARD_KEYS:
        hazard = find(tariff.hazards, key, "hazard")
        readings = gauges[key].to_numpy(dtype=float)
        loss = hazard_loss(hazard, severities(hazard, np.nan_to_num(readings)), factor)
        losses[key] = np.where(np.isnan(readings), 0.0, loss)
    losses["combined"] = 1 - np.prod(1 - losses[list(HAZARD_KEYS)].to_numpy(), axis=1)
    return losses


def capped_paid_days(gauges: pd.DataFrame, loss: pd.Series, cap_days: int) -> pd.Series:
    """Full-loss days paid per day, once a customer's year reaches the cap nothing more is paid."""
    running = loss.groupby([gauges["unit"], gauges["year"]]).cumsum()
    return running.clip(upper=cap_days) - (running - loss).clip(upper=cap_days)


def yearly_table(gauges: pd.DataFrame) -> pd.DataFrame:
    tariff = data.load_tariff()
    gauges = gauges.sort_values(["unit", "day"]).reset_index(drop=True)
    has_haze = gauges.groupby("year")["haze"].apply(lambda s: s.notna().any())
    rows = []
    for product_key in BACKTEST_PRODUCT_KEYS:
        losses = day_loss(gauges, product_key)
        for tier in tariff.tiers:
            paid = capped_paid_days(gauges, losses["combined"], tier.max_paid_days_per_year)
            per_customer = pd.DataFrame(
                {
                    "unit": gauges["unit"],
                    "year": gauges["year"],
                    "paid_days": paid,
                    "uncapped_days": losses["combined"],
                    **{f"{key}_loss_days": losses[key] for key in HAZARD_KEYS},
                }
            ).groupby(["year", "unit"]).sum()
            per_customer["payout_sgd"] = per_customer["paid_days"] * tier.daily_payout_sgd
            per_customer["capped"] = (
                per_customer["uncapped_days"] > tier.max_paid_days_per_year
            )
            yearly = per_customer.groupby("year").agg(
                customers=("payout_sgd", "size"),
                mean_payout_sgd=("payout_sgd", "mean"),
                p95_payout_sgd=("payout_sgd", lambda s: s.quantile(0.95)),
                max_payout_sgd=("payout_sgd", "max"),
                share_customers_capped=("capped", "mean"),
                mean_paid_days=("paid_days", "mean"),
                haze_loss_days=("haze_loss_days", "mean"),
                rain_loss_days=("rain_loss_days", "mean"),
                heat_loss_days=("heat_loss_days", "mean"),
            )
            yearly["hazards"] = np.where(
                has_haze.reindex(yearly.index).astype(bool), "haze+rain+heat", "rain+heat"
            )
            full_years = yearly[
                (yearly.index >= FIRST_FULL_BUNDLE_YEAR) & (yearly["hazards"] == "haze+rain+heat")
            ]
            premium = yearly_premium(full_years["mean_payout_sgd"].mean(), tariff.pricing)
            yearly["yearly_premium_sgd"] = premium
            yearly["loss_ratio"] = yearly["mean_payout_sgd"] / premium
            rows.append(yearly.reset_index().assign(product=product_key, tier=tier.key))
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    gauges, models = gauge_days()
    table = yearly_table(gauges)
    table["rain_model"], table["heat_model"] = models["rain"], models["heat"]
    BACKTEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(BACKTEST_PATH, index=False)
    print(f"Wrote {len(table)} rows to {BACKTEST_PATH}")
    view = table[table["product"] == BACKTEST_PRODUCT_KEYS[0]]
    for tier, rows in view.groupby("tier"):
        worst = rows.sort_values("mean_payout_sgd").iloc[-1]
        print(
            f"  {tier}: premium S${worst['yearly_premium_sgd']:.0f}/yr, worst year "
            f"{int(worst['year'])} pays S${worst['mean_payout_sgd']:.0f} per customer "
            f"(loss ratio {worst['loss_ratio']:.2f})"
        )


if __name__ == "__main__":
    main()
