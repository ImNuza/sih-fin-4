"""Copy what the product needs from a training run into ml/results/, which is committed.

ml/output/ holds every fitted model and is gitignored. This keeps the scores, the confusion
matrices, the back-test and the best model of each job, moved to the CPU so they load on any
machine (the API image has no GPU). No training happens here.

Usage (on the machine that ran ml.run_all):
    uv run --group ml python -m ml.publish

The best model of each job is the one with the best cross-validated score, not the best test
score, so the test years play no part in the choice.

Reads  ml/output/: leaderboard.csv, report.md, backtest_yearly.csv, confusion.md,
       confusion_metrics.csv, predictions/, models/
Writes ml/results/: the same files, plus
       confusion_matrices.csv   one row per job, model, threshold and cell
       confusion_matrices.md    the best model of each job, readable
       models/<job>.joblib      the best model of each job
       models/index.csv         which model each file is, its validation and test score
"""

from __future__ import annotations

import shutil

import joblib
import numpy as np
import pandas as pd

from api.calculator import find, severities
from ml.config import (
    BACKTEST_PATH,
    DAILY_TASKS,
    LEADERBOARD_PATH,
    MODEL_DIR,
    OUTPUT_DIR,
    REPO_ROOT,
    REPORT_PATH,
)
from ml.confusion import CONFUSION_CSV_PATH, CONFUSION_REPORT_PATH, called_and_fired
from ml.data import load_tariff
from ml.features import trigger_level
from ml.metrics import CLASS_CUTOFF, best_per_job
from ml.tune import PREDICTION_DIR

RESULTS_DIR = REPO_ROOT / "ml" / "results"
RESULT_MODEL_DIR = RESULTS_DIR / "models"
# GitHub rejects files over 100 MB. A best model above this is listed but not copied.
MAX_MODEL_MB = 50
BYTES_PER_MB = 1_000_000


def require(path) -> None:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run: uv run --group ml python -m ml.run_all")


TRIGGER_LABELS = ["no trigger", "trigger"]
COPIED_OUTPUTS = (LEADERBOARD_PATH, REPORT_PATH, BACKTEST_PATH, CONFUSION_REPORT_PATH,
                  CONFUSION_CSV_PATH)


def trigger_label(flags: np.ndarray) -> np.ndarray:
    return np.where(flags, "trigger", "no trigger")


def band_labels(hazard_key: str, readings: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """The tariff band of each reading ('none', then 'from <level>'), and every band in order."""
    hazard = find(load_tariff().hazards, hazard_key, "hazard")
    label_of = {0.0: "none", **{band.severity: f"from {band.at_least:g}" for band in hazard.bands}}
    order = ["none"] + [f"from {band.at_least:g}" for band in hazard.bands]
    return np.array([label_of[s] for s in severities(hazard, readings)]), order


def cells(
    names: tuple[str, str, str], actual: np.ndarray, predicted: np.ndarray, labels: list[str]
) -> list[dict]:
    """Every actual-predicted pair, including the ones with no days."""
    job, model, view = names
    return [
        {"job": job, "model": model, "view": view, "actual": a, "predicted": p,
         "days": int(np.sum((actual == a) & (predicted == p)))}
        for a in labels
        for p in labels
    ]


def job_confusion(row: pd.Series) -> list[dict]:
    """Confusion cells of one model on the test years, from its saved predictions."""
    path = PREDICTION_DIR / f"{row['job']}__{row['model']}.parquet"
    if row["kind"] == "count" or not path.exists():
        return []
    predictions = pd.read_parquet(path)
    called, fired = called_and_fired(row["kind"], row["task"], predictions)
    called, fired = trigger_label(called), trigger_label(fired)
    job, model = row["job"], row["model"]
    if row["kind"] == "classification":
        names = (job, model, f"probability >= {CLASS_CUTOFF}")
        return cells(names, fired, called, TRIGGER_LABELS)
    hazard_key = DAILY_TASKS[row["task"]].hazard_key
    actual_bands, order = band_labels(hazard_key, predictions["actual"].to_numpy(dtype=float))
    predicted_bands, _ = band_labels(hazard_key, predictions["predicted"].to_numpy(dtype=float))
    level = trigger_level(hazard_key)
    return cells((job, model, f"reading >= {level:g}"), fired, called, TRIGGER_LABELS) + cells(
        (job, model, "tariff band"), actual_bands, predicted_bands, order
    )


def confusion_markdown(confusion: pd.DataFrame, best: pd.DataFrame) -> str:
    lines = [
        "# Confusion matrices on the test years",
        "",
        "Days per actual and predicted outcome, for the best model of each job. Rows are what",
        "happened, columns what the model said. 'tariff band' compares the payout band of the",
        "real and the predicted reading, so it shows payout errors directly.",
    ]
    for _, row in best.iterrows():
        rows = confusion[(confusion["job"] == row["job"]) & (confusion["model"] == row["model"])]
        for view, view_rows in rows.groupby("view", sort=False):
            order = list(dict.fromkeys(view_rows["actual"]))
            table = view_rows.pivot(index="actual", columns="predicted", values="days")
            table = table.reindex(index=order, columns=order)
            header = "| actual \\ predicted | " + " | ".join(table.columns) + " |"
            divider = "|" + "---|" * (len(table.columns) + 1)
            body = [
                f"| {actual} | " + " | ".join(str(v) for v in values) + " |"
                for actual, values in zip(table.index, table.to_numpy())
            ]
            lines += ["", f"## {row['job']} ({row['model']}), {view}", "", header, divider, *body]
    return "\n".join(lines) + "\n"


def on_cpu(model):
    """Point GPU-trained models at the CPU so they predict on machines without CUDA."""
    final_step = model.steps[-1][1] if hasattr(model, "steps") else model
    if hasattr(final_step, "device"):
        final_step.device = "cpu"
    if type(final_step).__module__.startswith("xgboost"):
        final_step.set_params(device="cpu")
    return model


def copy_best_models(best: pd.DataFrame) -> pd.DataFrame:
    RESULT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for _, row in best.iterrows():
        source = MODEL_DIR / f"{row['job']}__{row['model']}.joblib"
        size_mb = source.stat().st_size / BYTES_PER_MB
        copied = size_mb <= MAX_MODEL_MB
        if copied:
            saved = joblib.load(source)
            saved["model"] = on_cpu(saved["model"])
            joblib.dump(saved, RESULT_MODEL_DIR / f"{row['job']}.joblib", compress=3)
        else:
            print(f"  {row['job']}: {row['model']} is {size_mb:.0f} MB, over {MAX_MODEL_MB} MB, "
                  "not copied")
        index.append({"job": row["job"], "model": row["model"],
                      "cv_score_name": row["cv_score_name"], "cv_score": row[row["cv_score_name"]],
                      "score_name": row["score_name"], "score": row[row["score_name"]],
                      "source_mb": round(size_mb, 1), "copied": copied})
    table = pd.DataFrame(index)
    table.to_csv(RESULT_MODEL_DIR / "index.csv", index=False)
    return table


def main() -> None:
    require(LEADERBOARD_PATH)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    board = pd.read_csv(LEADERBOARD_PATH)
    for path in COPIED_OUTPUTS:
        if path.exists():
            shutil.copy2(path, RESULTS_DIR / path.name)
        else:
            print(f"  {path.relative_to(OUTPUT_DIR)} not found, skipped")

    ok = board[board["status"] == "ok"]
    confusion = pd.DataFrame(
        [cell for _, row in ok.iterrows() for cell in job_confusion(row)]
    )
    best = best_per_job(board)
    if not confusion.empty:
        confusion.to_csv(RESULTS_DIR / "confusion_matrices.csv", index=False)
        (RESULTS_DIR / "confusion_matrices.md").write_text(confusion_markdown(confusion, best))
    index = copy_best_models(best)
    total_mb = sum(f.stat().st_size for f in RESULTS_DIR.rglob("*") if f.is_file()) / BYTES_PER_MB
    print(f"Wrote {RESULTS_DIR.relative_to(REPO_ROOT)}: {len(best)} jobs, "
          f"{int(index['copied'].sum())} models copied, {total_mb:.0f} MB in all")
    print("Next: git add ml/results && git commit -m 'Add training results' && git push")


if __name__ == "__main__":
    main()
