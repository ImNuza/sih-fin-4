"""Why each model is in the comparison, and how its score moved across the hyperparameters tried.

Usage (after ml.run_all, which also calls it):
    uv run --group ml python -m ml.model_notes

For every tuned model and job it reads the Optuna trials: the best, median and worst
cross-validated score, and the hyperparameters that moved the score most (fANOVA importance,
the share of the score's variation each one explains) with the direction that helped.

Reads ml/output/leaderboard.csv and ml/output/optuna.db. Writes ml/output/model_notes.md.
"""

from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from ml.config import LEADERBOARD_PATH, OPTUNA_DB, OUTPUT_DIR, SEED
from ml.metrics import TUNING_METRIC, best_per_job
from ml.models import MODELS

MODEL_NOTES_PATH = OUTPUT_DIR / "model_notes.md"
TOP_HYPERPARAMETERS = 2
# fANOVA fits a forest to the trials; with fewer than this it reports noise.
MIN_TRIALS_FOR_IMPORTANCE = 8
# A rank correlation weaker than this between a hyperparameter and the score is no direction.
CLEAR_DIRECTION = 0.2

WHY = {
    "climatology": "Baseline. Predicts the average of the same month and region in the training "
    "years. It knows the season and nothing else, so any useful model must beat it.",
    "persistence": "Baseline for forecasts. Says tomorrow (or next week) looks like the last "
    "known reading. Haze and heat come in spells, so this is a hard baseline to beat at short "
    "horizons.",
    "linear": "Ridge regression, logistic regression or Poisson regression on scaled features. "
    "Fast, hard to overfit, and its coefficients can be read. It shows how much of the signal is "
    "a straight-line effect of the weather features.",
    "random_forest": "Averages many deep decision trees fitted on random samples. Handles "
    "thresholds and interactions (hot and still air together) with little tuning, and is robust "
    "to outliers. Saved models can be large.",
    "hist_gbm": "scikit-learn's gradient boosting on binned features. Builds trees one after "
    "another, each fixing the last one's errors, and handles missing readings natively. A strong "
    "boosted model with no extra library.",
    "xgboost": "Regularised gradient boosting, trained on the GPU here. Usually among the best "
    "models on tabular data like daily weather tables.",
    "lightgbm": "Gradient boosting that grows the most useful leaf first. The fastest boosted "
    "model on the CPU, which matters on the 212,000-row rain table.",
    "catboost": "Gradient boosting with ordered boosting, which overfits less on small tables "
    "such as heat (from January 2025 only). Trained on the GPU here and the slowest per trial.",
    "mlp": "A feed-forward neural network on standardised features, with early stopping. Tests "
    "whether a neural network adds anything over trees on tables of this size.",
}


def score_direction(direction: str) -> str:
    return "higher is better" if direction == "maximize" else "lower is better"


def effect(trials: list[optuna.trial.FrozenTrial], name: str, direction: str) -> str:
    """Which values of one hyperparameter gave better scores."""
    values = pd.Series([t.params[name] for t in trials if name in t.params])
    scores = pd.Series([t.value for t in trials if name in t.params])
    numeric = all(isinstance(v, int | float) and not isinstance(v, bool) for v in values)
    if not numeric:
        means = scores.groupby(values.astype(str)).mean()
        best = means.idxmax() if direction == "maximize" else means.idxmin()
        return f"best {best}"
    rank_correlation = values.corr(scores, method="spearman")
    if np.isnan(rank_correlation) or abs(rank_correlation) < CLEAR_DIRECTION:
        return "no clear direction"
    higher_helps = (rank_correlation > 0) == (direction == "maximize")
    return "higher helped" if higher_helps else "lower helped"


def influential(study: optuna.Study, trials: list, direction: str) -> str:
    if len(trials) < MIN_TRIALS_FOR_IMPORTANCE:
        return f"too few finished trials ({len(trials)}) to tell"
    evaluator = optuna.importance.FanovaImportanceEvaluator(seed=SEED)
    importances = optuna.importance.get_param_importances(study, evaluator=evaluator)
    return "; ".join(
        f"{name} {share:.0%}, {effect(trials, name, direction)}"
        for name, share in list(importances.items())[:TOP_HYPERPARAMETERS]
    )


def tuning_row(entry: pd.Series, chosen: set[tuple[str, str]]) -> dict:
    metric, direction = TUNING_METRIC[entry["kind"]]
    study = optuna.load_study(study_name=f"{entry['job']}/{entry['model']}",
                              storage=f"sqlite:///{OPTUNA_DB}")
    trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    scores = np.array([t.value for t in trials])
    best, worst = (scores.max(), scores.min()) if direction == "maximize" else (
        scores.min(), scores.max())
    return {
        "job": entry["job"],
        "tuned on": f"{metric}, {score_direction(direction)}",
        "trials": len(trials),
        "best CV": f"{best:.4g}",
        "median CV": f"{np.median(scores):.4g}",
        "worst CV": f"{worst:.4g}",
        "test": f"{entry[f'test_{metric}']:.4g}",
        "chosen": "yes" if (entry["job"], entry["model"]) in chosen else "",
        "most influential hyperparameters": influential(study, trials, direction),
    }


def baseline_row(entry: pd.Series, chosen: set[tuple[str, str]]) -> dict:
    metric, direction = TUNING_METRIC[entry["kind"]]
    return {
        "job": entry["job"],
        "scored on": f"{metric}, {score_direction(direction)}",
        "CV": f"{entry[f'cv_{metric}']:.4g}",
        "test": f"{entry[f'test_{metric}']:.4g}",
        "chosen": "yes" if (entry["job"], entry["model"]) in chosen else "",
    }


def markdown_table(rows: list[dict]) -> str:
    columns = list(rows[0])
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(str(row[c]) for c in columns) + " |" for row in rows]
    return "\n".join(lines)


def main() -> None:
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    board = pd.read_csv(LEADERBOARD_PATH)
    ok = board[board["status"] == "ok"]
    chosen = set(best_per_job(board)[["job", "model"]].itertuples(index=False, name=None))
    lines = [
        "# The models: why each one, and how it responded to tuning",
        "",
        "Each tuned model ran 40 Optuna trials per job. A trial is one set of hyperparameters,",
        "scored by its mean over 4 time-ordered validation folds (CV). Trials that were clearly",
        "worse than the median after the first folds were stopped early; the trials column counts",
        "only the ones that finished. The test column is the",
        "chosen hyperparameters refitted on all training years and scored on the held-out years.",
        "'Chosen' marks the model of each job with the best CV score, the one ml.publish ships.",
        "The share next to a hyperparameter is how much of the spread in CV scores it explains.",
        "A big gap between best and worst CV means the model is sensitive to its settings.",
    ]
    for name, spec in MODELS.items():
        rows = ok[ok["model"] == name].sort_values("job")
        if rows.empty:
            continue
        lines += ["", f"## {name}", "", WHY[name], ""]
        make_row = baseline_row if spec.suggest is None else tuning_row
        lines.append(markdown_table([make_row(entry, chosen) for _, entry in rows.iterrows()]))
    MODEL_NOTES_PATH.write_text("\n".join(lines) + "\n")
    print(f"Wrote {MODEL_NOTES_PATH}")


if __name__ == "__main__":
    main()
