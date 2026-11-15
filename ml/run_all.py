"""Tune every model on every task, write the leaderboard and report, then run the back-test.

Usage (on the GPU machine, from the repo root):
    uv run --group ml python -m ml.run_all
    uv run --group ml python -m ml.run_all --budget full
    uv run --group ml python -m ml.run_all --tasks haze heat --models xgboost catboost

Budgets: smoke (a minute per model, to check the setup), standard (40 trials, 4 folds,
up to 15 minutes per model and job), full (150 trials, 5 folds, up to an hour).
A rerun skips every job and model already in the leaderboard and resumes Optuna studies,
so a stopped run continues where it stopped. Delete ml/output/ to start again.

Writes ml/output/:
    leaderboard.csv        one row per job and model: CV score, test scores, best parameters
    report.md              the best model per job against the baselines
    models/, predictions/  fitted models (joblib) and test-year predictions (Parquet)
    optuna.db              every trial
    backtest_yearly.csv    payouts per year, product and tier (see ml/backtest.py)
"""

from __future__ import annotations

import argparse
import time
import traceback

import optuna
import pandas as pd

from ml import backtest
from ml.config import (
    BUDGETS,
    DAILY_TASKS,
    LEADERBOARD_PATH,
    OUTPUT_DIR,
    RECONSTRUCTION,
    REPORT_PATH,
    SEASONAL_TASKS,
)
from ml.metrics import TUNING_METRIC
from ml.models import MODELS
from ml.tune import build_jobs, context_for, run

BASELINES = ("climatology", "persistence")
BACKTEST_JOBS = (f"rain_h{RECONSTRUCTION}_regression", f"heat_h{RECONSTRUCTION}_regression")
REPORT_COLUMNS = {
    "regression": ["test_rmse", "test_mae", "test_r2", "test_trigger_f1", "test_band_accuracy",
                   "test_payout_mae_sgd", "test_payout_bias_pct"],
    "classification": ["test_average_precision", "test_roc_auc", "test_brier", "test_f1_at_half",
                       "test_base_rate"],
    "count": ["test_poisson_deviance", "test_mae", "test_total_bias_pct"],
}


def pick_device(choice: str) -> str:
    import torch

    if choice == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda, but PyTorch sees no CUDA GPU. Check nvidia-smi.")
    if choice == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return choice


def load_leaderboard() -> pd.DataFrame:
    return pd.read_csv(LEADERBOARD_PATH) if LEADERBOARD_PATH.exists() else pd.DataFrame()


def already_done(board: pd.DataFrame, job: str, model: str) -> bool:
    if board.empty:
        return False
    rows = board[(board["job"] == job) & (board["model"] == model)]
    return bool((rows["status"] == "ok").any())


def save_row(board: pd.DataFrame, row: dict) -> pd.DataFrame:
    # Re-read the file first: another run_all may have written rows since this one started.
    board = load_leaderboard()
    if not board.empty:
        board = board[~((board["job"] == row["job"]) & (board["model"] == row["model"]))]
    board = pd.concat([board, pd.DataFrame([row])], ignore_index=True)
    board.to_csv(LEADERBOARD_PATH, index=False)
    return board


def markdown_table(frame: pd.DataFrame) -> str:
    header = "| " + " | ".join(frame.columns) + " |"
    divider = "|" + "---|" * len(frame.columns)
    body = ["| " + " | ".join(str(value) for value in row) + " |" for row in frame.to_numpy()]
    return "\n".join([header, divider, *body])


def job_section(rows: pd.DataFrame, kind: str) -> list[str]:
    metric, direction = TUNING_METRIC[kind]
    ranked = rows.sort_values(f"test_{metric}", ascending=direction == "minimize")
    best = ranked.iloc[0]
    baselines = ranked[ranked["model"].isin(BASELINES)]
    lines = [f"Best: **{best['model']}** (test {metric} {best[f'test_{metric}']:.4g})."]
    if not baselines.empty:
        baseline = baselines.iloc[0]
        lines.append(
            f"Best baseline: {baseline['model']} ({baseline[f'test_{metric}']:.4g})."
        )
    if isinstance(best.get("top_features"), str) and best["top_features"]:
        lines.append(f"Top features: {best['top_features']}.")
    columns = ["model"] + [c for c in REPORT_COLUMNS[kind] if c in ranked.columns] + ["seconds"]
    lines += ["", markdown_table(ranked[columns].round(4))]
    return lines


def write_report(board: pd.DataFrame, device: str, budget: str) -> None:
    ok = board[board["status"] == "ok"]
    lines = [
        "# Hazard model results",
        "",
        f"Device {device}, budget {budget}. Test years are held out from training and tuning.",
        "Baselines: climatology (same month and region in the training years) and persistence",
        "(the last known reading). A model is only useful if it beats both.",
    ]
    for job, rows in ok.groupby("job", sort=False):
        lines += ["", f"## {job}", ""] + job_section(rows, rows["kind"].iloc[0])
    failed = board[board["status"] != "ok"]
    if not failed.empty:
        lines += ["", "## Failed runs", "", markdown_table(failed[["job", "model", "status"]])]
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--budget", choices=sorted(BUDGETS), default="standard")
    parser.add_argument("--tasks", nargs="+", default=[*DAILY_TASKS, *SEASONAL_TASKS])
    parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--skip-backtest", action="store_true")
    args = parser.parse_args()

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    device = pick_device(args.device)
    budget = BUDGETS[args.budget]
    print(f"Device {device}, budget {args.budget}: {budget}", flush=True)

    jobs = build_jobs(args.tasks)
    board = load_leaderboard()
    failures = []
    started = time.monotonic()
    for job in jobs:
        print(f"\n{job.key}: {len(job.frame):,} rows, {len(job.features)} features", flush=True)
        for name in args.models:
            spec = MODELS[name]
            if not spec.available(context_for(job, device)) or already_done(board, job.key, name):
                continue
            try:
                row = run(job, spec, budget, device)
            except Exception as error:
                traceback.print_exc()
                row = {"job": job.key, "task": job.task, "horizon": job.horizon,
                       "kind": job.kind, "model": name, "device": device,
                       "status": f"failed: {type(error).__name__}: {error}"}
                failures.append(f"{job.key}/{name}")
            board = save_row(board, row)
            metric, _ = TUNING_METRIC[job.kind]
            print(f"  {name:13s} {row['status'][:60]:10s} "
                  f"test {metric} {row.get(f'test_{metric}', float('nan')):.4g} "
                  f"({row.get('seconds', 0):.0f} s, {(time.monotonic() - started) / 60:.0f} min "
                  f"total)", flush=True)

    write_report(board, device, args.budget)
    print(f"\nReport: {REPORT_PATH}")
    done = set(board.loc[board["status"] == "ok", "job"]) if not board.empty else set()
    if args.skip_backtest:
        print("Back-test skipped (--skip-backtest).")
    elif set(BACKTEST_JOBS) <= done:
        backtest.main()
    else:
        print(f"Back-test skipped: it needs trained {' and '.join(BACKTEST_JOBS)}.")
    if failures:
        raise SystemExit(f"{len(failures)} model runs failed: {', '.join(failures)}. "
                         "See the tracebacks above and the leaderboard.")


if __name__ == "__main__":
    main()
