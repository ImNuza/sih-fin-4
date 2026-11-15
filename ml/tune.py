"""Tune one model on one job with Optuna and time-ordered folds, then score it on held-out years.

A job is a task, a horizon and a kind of target. Training uses only days before the task's
test start. Folds grow forward in time with an embargo before each validation block, never at
random, so a model is always scored on days after the ones it learned from.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import joblib
import numpy as np
import optuna
import pandas as pd

from ml import features as feature_tables
from ml.config import (
    DAILY_TASKS,
    EMBARGO_DAYS,
    MODEL_DIR,
    OPTUNA_DB,
    OUTPUT_DIR,
    RECONSTRUCTION,
    SEASONAL_TASKS,
    SEED,
    Budget,
)
from ml.data import load_tariff
from ml.metrics import (
    TUNING_METRIC,
    classification_metrics,
    count_metrics,
    regression_metrics,
    tuning_score,
)
from ml.models import Context, ModelSpec, predict

PREDICTION_DIR = OUTPUT_DIR / "predictions"
TOP_FEATURES = 15


@dataclass
class Job:
    key: str
    task: str
    horizon: int | None
    kind: str
    hazard_key: str
    target: str
    trigger: float
    test_start: pd.Timestamp
    frame: pd.DataFrame
    features: list[str]
    month_column: str
    persistence_column: str | None

    def labels(self, rows: pd.DataFrame) -> np.ndarray:
        values = rows[self.target].to_numpy(dtype=float)
        return (values >= self.trigger).astype(int) if self.kind == "classification" else values


def build_jobs(task_names: list[str]) -> list[Job]:
    jobs = []
    for name in task_names:
        if name in DAILY_TASKS:
            task = DAILY_TASKS[name]
            trigger = feature_tables.trigger_level(task.hazard_key)
            for horizon in task.horizons:
                frame, features = feature_tables.daily_frame(task, horizon)
                persistence = (
                    None if horizon == RECONSTRUCTION else f"{task.target}_lag{horizon}"
                )
                for kind in ("regression", "classification"):
                    jobs.append(
                        Job(
                            key=f"{name}_h{horizon}_{kind}",
                            task=name,
                            horizon=horizon,
                            kind=kind,
                            hazard_key=task.hazard_key,
                            target=task.target,
                            trigger=trigger,
                            test_start=pd.Timestamp(task.test_start),
                            frame=frame,
                            features=features,
                            month_column="month",
                            persistence_column=persistence,
                        )
                    )
        elif name in SEASONAL_TASKS:
            task = SEASONAL_TASKS[name]
            frame, features = feature_tables.seasonal_frame(task)
            jobs.append(
                Job(
                    key=f"{name}_count",
                    task=name,
                    horizon=None,
                    kind="count",
                    hazard_key=task.hazard_key,
                    target=task.target,
                    trigger=1.0,
                    test_start=pd.Timestamp(task.test_start),
                    frame=frame,
                    features=features,
                    month_column="month_of_year",
                    persistence_column="trigger_days_lag1m",
                )
            )
        else:
            raise SystemExit(f"Unknown task {name}. Choose from {[*DAILY_TASKS, *SEASONAL_TASKS]}")
    return jobs


def time_folds(days: pd.Series, folds: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window folds: train on every block before the validation block."""
    blocks = np.array_split(np.sort(days.unique()), folds + 1)
    splits = []
    for block in blocks[1:]:
        valid_start = pd.Timestamp(block[0])
        train = np.flatnonzero(days < valid_start - pd.Timedelta(days=EMBARGO_DAYS))
        valid = np.flatnonzero(days.isin(block))
        if len(train) and len(valid):
            splits.append((train, valid))
    return splits


def train_rows(job: Job, budget: Budget) -> pd.DataFrame:
    train = job.frame[job.frame["day"] < job.test_start]
    if budget.max_train_rows and len(train) > budget.max_train_rows:
        train = train.sample(budget.max_train_rows, random_state=SEED)
    return train.sort_values("day").reset_index(drop=True)


def cross_validate(
    spec: ModelSpec,
    params: dict,
    context: Context,
    job: Job,
    train: pd.DataFrame,
    splits: list[tuple[np.ndarray, np.ndarray]],
    trial: optuna.Trial | None = None,
) -> float:
    scores = []
    X, y = train[job.features], job.labels(train)
    for step, (fit_rows, valid_rows) in enumerate(splits):
        if job.kind == "classification" and len(np.unique(y[fit_rows])) < 2:
            # The earliest fold can hold no trigger day yet (heat starts in Jan 2025);
            # a classifier cannot be fitted on one class, so that fold is skipped.
            continue
        model = spec.build(params, context).fit(X.iloc[fit_rows], y[fit_rows])
        score = tuning_score(job.kind, y[valid_rows], predict(model, X.iloc[valid_rows], job.kind))
        if not np.isnan(score):
            scores.append(score)
        if trial is not None and scores:
            trial.report(float(np.mean(scores)), step)
            if trial.should_prune():
                raise optuna.TrialPruned()
    return float(np.mean(scores)) if scores else float("nan")


def search(
    spec: ModelSpec,
    context: Context,
    job: Job,
    train: pd.DataFrame,
    splits: list[tuple[np.ndarray, np.ndarray]],
    budget: Budget,
) -> tuple[dict, float, int]:
    """Best parameters, their mean validation score and the number of finished trials."""
    _, direction = TUNING_METRIC[job.kind]
    study = optuna.create_study(
        study_name=f"{job.key}/{spec.name}",
        storage=f"sqlite:///{OPTUNA_DB}",
        load_if_exists=True,
        direction=direction,
        sampler=optuna.samplers.TPESampler(seed=SEED),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1),
    )

    def objective(trial: optuna.Trial) -> float:
        params = spec.suggest(trial, job.kind)
        score = cross_validate(spec, params, context, job, train, splits, trial)
        if np.isnan(score):
            raise optuna.TrialPruned()
        return score

    finished = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    remaining = budget.trials - len(finished)
    if remaining > 0:
        study.optimize(
            objective, n_trials=remaining, timeout=budget.timeout_seconds, gc_after_trial=True
        )
    finished = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not finished:
        raise RuntimeError(f"{job.key}/{spec.name}: no trial finished within the budget")
    return study.best_params, study.best_value, len(finished)


def test_metrics(job: Job, actual: np.ndarray, predicted: np.ndarray) -> dict:
    if job.kind == "regression":
        return regression_metrics(actual, predicted, job.trigger, load_tariff(), job.hazard_key)
    if job.kind == "classification":
        return classification_metrics(actual, predicted)
    return count_metrics(actual, predicted)


def top_features(model, features: list[str]) -> list[str]:
    final_step = model.steps[-1][1] if hasattr(model, "steps") else model
    weights = getattr(final_step, "feature_importances_", None)
    if weights is None:
        weights = getattr(final_step, "coef_", None)
    if weights is None or len(np.ravel(weights)) != len(features):
        return []
    order = np.argsort(-np.abs(np.ravel(weights)))[:TOP_FEATURES]
    return [features[i] for i in order]


def context_for(job: Job, device: str) -> Context:
    return Context(
        kind=job.kind,
        device=device,
        features=job.features,
        month_column=job.month_column,
        persistence_column=job.persistence_column,
        trigger=job.trigger,
    )


def run(job: Job, spec: ModelSpec, budget: Budget, device: str) -> dict:
    """Tune, refit on all training years, score on the test years and save the model."""
    started = time.monotonic()
    context = context_for(job, device)
    train = train_rows(job, budget)
    test = job.frame[job.frame["day"] >= job.test_start]
    splits = time_folds(train["day"], budget.folds)
    if spec.suggest is None:
        params, cv_score, trials = {}, cross_validate(spec, {}, context, job, train, splits), 0
    else:
        params, cv_score, trials = search(spec, context, job, train, splits, budget)

    model = spec.build(params, context).fit(train[job.features], job.labels(train))
    actual = job.labels(test)
    predicted = predict(model, test[job.features], job.kind)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTION_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "features": job.features, "kind": job.kind, "params": params},
        MODEL_DIR / f"{job.key}__{spec.name}.joblib",
    )
    test[["day", "unit", "region"]].assign(actual=actual, predicted=predicted).to_parquet(
        PREDICTION_DIR / f"{job.key}__{spec.name}.parquet", index=False
    )
    metric_name, _ = TUNING_METRIC[job.kind]
    return {
        "job": job.key,
        "task": job.task,
        "horizon": job.horizon,
        "kind": job.kind,
        "model": spec.name,
        "status": "ok",
        "device": device,
        "trials": trials,
        f"cv_{metric_name}": cv_score,
        "train_rows": len(train),
        "test_rows": len(test),
        "test_start": job.test_start.date().isoformat(),
        **{f"test_{name}": value for name, value in test_metrics(job, actual, predicted).items()},
        "top_features": ", ".join(top_features(model, job.features)),
        "params": json.dumps(params),
        "seconds": round(time.monotonic() - started, 1),
    }
