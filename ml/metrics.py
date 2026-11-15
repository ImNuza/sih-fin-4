"""Scores for each kind of target, including what a prediction error costs in payouts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_poisson_deviance,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)

from api.calculator import find, hazard_loss, product_factor, severities
from api.models import Tariff
from ml.config import REPORT_PRODUCT_KEY, REPORT_TIER_KEY

POSITIVE_FLOOR = 1e-6
CLASS_CUTOFF = 0.5

# The score each kind is tuned on, and whether higher is better.
TUNING_METRIC = {
    "regression": ("rmse", "minimize"),
    "classification": ("average_precision", "maximize"),
    "count": ("poisson_deviance", "minimize"),
}


def daily_payout_sgd(tariff: Tariff, hazard_key: str, readings: np.ndarray) -> np.ndarray:
    """What the report tier pays the report product for each day's reading of one hazard."""
    hazard = find(tariff.hazards, hazard_key, "hazard")
    product = find(tariff.products, REPORT_PRODUCT_KEY, "product")
    tier = find(tariff.tiers, REPORT_TIER_KEY, "tier")
    factor = product_factor(product)
    loss = hazard_loss(hazard, severities(hazard, readings), factor)
    return loss * tier.daily_payout_sgd


def bias_percent(actual_total: float, predicted_total: float) -> float:
    if actual_total == 0:
        return float("nan")
    return 100 * (predicted_total - actual_total) / actual_total


def regression_metrics(
    actual: np.ndarray, predicted: np.ndarray, trigger: float, tariff: Tariff, hazard_key: str
) -> dict:
    hazard = find(tariff.hazards, hazard_key, "hazard")
    fired, predicted_fired = actual >= trigger, predicted >= trigger
    actual_payout = daily_payout_sgd(tariff, hazard_key, actual)
    predicted_payout = daily_payout_sgd(tariff, hazard_key, predicted)
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": root_mean_squared_error(actual, predicted),
        "r2": r2_score(actual, predicted),
        "trigger_precision": precision_score(fired, predicted_fired, zero_division=0),
        "trigger_recall": recall_score(fired, predicted_fired, zero_division=0),
        "trigger_f1": f1_score(fired, predicted_fired, zero_division=0),
        "band_accuracy": float(
            np.mean(severities(hazard, actual) == severities(hazard, predicted))
        ),
        "payout_mae_sgd": mean_absolute_error(actual_payout, predicted_payout),
        "payout_bias_pct": bias_percent(actual_payout.sum(), predicted_payout.sum()),
    }


def classification_metrics(fired: np.ndarray, probability: np.ndarray) -> dict:
    both_classes = 0 < fired.mean() < 1
    return {
        "base_rate": float(fired.mean()),
        "average_precision": (
            average_precision_score(fired, probability) if both_classes else float("nan")
        ),
        "roc_auc": roc_auc_score(fired, probability) if both_classes else float("nan"),
        "brier": brier_score_loss(fired, probability),
        "f1_at_half": f1_score(fired, probability >= CLASS_CUTOFF, zero_division=0),
        "trigger_days_bias_pct": bias_percent(fired.sum(), probability.sum()),
    }


def count_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    return {
        "poisson_deviance": mean_poisson_deviance(actual, np.maximum(predicted, POSITIVE_FLOOR)),
        "mae": mean_absolute_error(actual, predicted),
        "rmse": root_mean_squared_error(actual, predicted),
        "total_bias_pct": bias_percent(actual.sum(), predicted.sum()),
    }


def best_per_job(board: pd.DataFrame) -> pd.DataFrame:
    """The model of each job with the best cross-validated score.

    Choosing on the validation folds keeps the test years unseen, so their score stays honest.
    """
    ok = board[board["status"] == "ok"]
    rows = []
    for job, job_rows in ok.groupby("job", sort=False):
        metric, direction = TUNING_METRIC[job_rows["kind"].iloc[0]]
        scored = job_rows.dropna(subset=[f"cv_{metric}"])
        if scored.empty:
            raise SystemExit(f"{job}: no model has a cross-validated {metric}")
        ranked = scored.sort_values(f"cv_{metric}", ascending=direction == "minimize")
        rows.append({**ranked.iloc[0].to_dict(), "score_name": f"test_{metric}",
                     "cv_score_name": f"cv_{metric}"})
    return pd.DataFrame(rows).reset_index(drop=True)


def tuning_score(kind: str, actual: np.ndarray, predicted: np.ndarray) -> float:
    if kind == "regression":
        return root_mean_squared_error(actual, predicted)
    if kind == "classification":
        if not 0 < actual.mean() < 1:
            return float("nan")
        return average_precision_score(actual, predicted)
    return mean_poisson_deviance(actual, np.maximum(predicted, POSITIVE_FLOOR))
