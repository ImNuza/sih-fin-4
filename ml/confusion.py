"""Confusion matrix, accuracy, precision and recall of every model on the held-out test years.

Usage (after ml.run_all, which also calls it):
    uv run --group ml python -m ml.confusion

A day counts as a trigger day when the reading reaches the tariff's first payout band.
Classification models call a trigger day when their probability is at least 0.5. Regression
models call one when their predicted reading reaches the band. Monthly count models predict a
number of days, not a yes or no, so they have no confusion matrix.

Reads ml/output/leaderboard.csv and ml/output/predictions/. Writes
ml/output/confusion_metrics.csv and ml/output/confusion.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml import features as feature_tables
from ml.config import DAILY_TASKS, LEADERBOARD_PATH, OUTPUT_DIR
from ml.metrics import CLASS_CUTOFF

PREDICTION_DIR = OUTPUT_DIR / "predictions"
CONFUSION_CSV_PATH = OUTPUT_DIR / "confusion_metrics.csv"
CONFUSION_REPORT_PATH = OUTPUT_DIR / "confusion.md"
YES_NO_KINDS = ("classification", "regression")

EXPLANATION = """\
# Confusion matrices on the test years

Each row is one model scored on the held-out test years, counting station-days (heat, rain)
or region-days (haze). A trigger day is a day whose reading reaches the first payout band, so
it is a day the policy pays.

- **TP** (true positive): a payout day the model called. **FN** (false negative): a payout
  day it missed. **FP** (false positive): a day it called that paid nothing. **TN** (true
  negative): a quiet day it left alone.
- **Accuracy** is the share of all days called right. Trigger days are rare (the base rate
  column), so a model that always says "no trigger" already scores 1 minus the base rate.
  The "always-no accuracy" column shows that bar. Accuracy alone cannot rank these models.
- **Precision** is TP / (TP + FP): of the days the model flags, how many really pay. Low
  precision means false alarms: payouts or warnings for days that never triggered.
- **Recall** is TP / (TP + FN): of the days that really pay, how many the model caught.
  Low recall means missed payout days.
- **F1** balances the two. Average precision (in report.md) ranks the models over every
  cut-off, not only 0.5, and is what the tuning maximised.

Why it matters for the insurance product:

- Horizon 0 models rebuild past days from weather data to fill in history. That history
  sets the premium. Missed trigger days (low recall) make the history look calmer than it
  was and under-price the cover. False alarms (low precision) over-price it.
- Horizon 1 and 7 models forecast the next day or week. A miss means a payout day arrives
  without warning, so reserves and customer alerts are late. A false alarm means a warning,
  or cash set aside, for a day that pays nothing.
- Payouts are made from the measured readings, never from the model, so these errors cost
  pricing accuracy and warning quality, not customers' claims.
- The 0.5 cut-off is not tuned. A lower cut-off trades precision for recall, and the right
  trade depends on whether a missed payout day or a false alarm costs more.
"""

COLUMNS = ["job", "model", "test_days", "base_rate", "TP", "FN", "FP", "TN", "accuracy",
           "always_no_accuracy", "precision", "recall", "f1", "average_precision"]


def called_and_fired(kind: str, task: str, predictions: pd.DataFrame) -> tuple[np.ndarray, ...]:
    """Days the model called a trigger, and days that really triggered."""
    predicted, actual = predictions["predicted"].to_numpy(), predictions["actual"].to_numpy()
    if kind == "classification":
        return predicted >= CLASS_CUTOFF, actual.astype(bool)
    trigger = feature_tables.trigger_level(DAILY_TASKS[task].hazard_key)
    return predicted >= trigger, actual >= trigger


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else float("nan")


def confusion_row(entry: pd.Series) -> dict:
    predictions = pd.read_parquet(PREDICTION_DIR / f"{entry['job']}__{entry['model']}.parquet")
    called, fired = called_and_fired(entry["kind"], entry["task"], predictions)
    tp, fn = int((called & fired).sum()), int((~called & fired).sum())
    fp, tn = int((called & ~fired).sum()), int((~called & ~fired).sum())
    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    return {
        "job": entry["job"],
        "model": entry["model"],
        "test_days": len(fired),
        "base_rate": fired.mean(),
        "TP": tp, "FN": fn, "FP": fp, "TN": tn,
        "accuracy": (tp + tn) / len(fired),
        "always_no_accuracy": 1 - fired.mean(),
        "precision": precision,
        "recall": recall,
        "f1": ratio(2 * precision * recall, precision + recall) if tp else 0.0,
        "average_precision": entry.get("test_average_precision", float("nan")),
    }


def markdown_table(frame: pd.DataFrame) -> str:
    header = "| " + " | ".join(frame.columns) + " |"
    divider = "|" + "---|" * len(frame.columns)
    body = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |"
            for row in frame.to_numpy()]
    return "\n".join([header, divider, *body])


def main() -> None:
    board = pd.read_csv(LEADERBOARD_PATH)
    trained = board[(board["status"] == "ok") & board["kind"].isin(YES_NO_KINDS)]
    if trained.empty:
        raise SystemExit(f"No trained classification or regression models in {LEADERBOARD_PATH}")
    table = pd.DataFrame([confusion_row(entry) for _, entry in trained.iterrows()], columns=COLUMNS)
    table = table.sort_values(["job", "f1"], ascending=[True, False])
    table.to_csv(CONFUSION_CSV_PATH, index=False)

    lines = [EXPLANATION]
    for job, rows in table.groupby("job", sort=True):
        cut_off = "probability >= 0.5" if job.endswith("classification") else (
            "predicted reading in the first payout band")
        lines += ["", f"## {job}", "", f"Trigger called when {cut_off}.", "",
                  markdown_table(rows.drop(columns="job").round(4))]
    CONFUSION_REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(table)} confusion matrices to {CONFUSION_CSV_PATH} and "
          f"{CONFUSION_REPORT_PATH}")


if __name__ == "__main__":
    main()
