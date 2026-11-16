"""Charts of the model results for the pitch: which algorithm won, by how much, and at what cost.

Usage:
    uv run --group ml python -m ml.plots

Reads  ml/results/leaderboard.csv, ml/results/model_notes.md, ml/results/confusion_metrics.csv,
       ml/results/models/index.csv
Writes docs/figures/ml_rain_models.png        the rain rebuild, the model in the product: every
                                              algorithm against the simple guess
       docs/figures/ml_rain_payout_days.png   the rain rebuild's precision, recall and accuracy
                                              on payout days, per algorithm
       docs/figures/ml_rain_tuning.png        how far tuning moved each algorithm on the rain
                                              rebuild, worst to best trial
       docs/figures/ml_all_jobs.png           every job: the chosen model against the best
                                              simple guess, on one scale
       docs/figures/ml_energy_per_answer.png  energy per answer: this product against an LLM
The timings behind the energy chart were measured on 16 Nov 2026 (see ENERGY_ROWS).
"""

from __future__ import annotations

import re

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from heat_stats import BAR, FIG_DIR, GRID, INK, INK_2, MUTED, SURFACE, style_axes  # noqa: E402
from ml.config import REPO_ROOT  # noqa: E402

RESULTS_DIR = REPO_ROOT / "ml" / "results"
OTHER = "#c3c2b7"       # algorithms that were not chosen: a de-emphasis tone, labelled directly
LLM = "#eb6834"         # the comparison series in the energy chart (categorical slot 2)
BASELINES = ("climatology", "persistence")
SHIPPED = ("heat_h0_regression", "rain_h0_regression")
RAIN_JOBS = ("rain_h0_regression", "rain_h0_classification")
METRIC = {
    "regression": ("test_rmse", False, "error (RMSE), lower is better"),
    "classification": ("test_average_precision", True, "average precision, higher is better"),
    "count": ("test_poisson_deviance", False, "Poisson deviance, lower is better"),
}
JOB_LABELS = {
    "heat_h0": "Heat rebuild", "heat_h1": "Heat tomorrow", "rain_h0": "Rain rebuild",
    "rain_h1": "Rain tomorrow", "haze_h1": "Haze tomorrow", "haze_h7": "Haze next week",
    "haze_season": "Haze days next month", "rain_season": "Rain days next month",
}
KIND_LABELS = {"regression": "reading", "classification": "payout day?", "count": "count"}
ALGORITHM_LABELS = {
    "linear": "Linear", "random_forest": "Random forest", "hist_gbm": "Gradient boosting",
    "xgboost": "XGBoost", "lightgbm": "LightGBM", "catboost": "CatBoost", "mlp": "Neural net",
    "climatology": "Same-month average", "persistence": "Same as last reading",
}
# Measured on an Apple M5 laptop (16 GB) on 16 Nov 2026, except the cloud figure. Power is an
# assumption stated on the chart: 20 W for CPU work, 30 W with the GPU busy. The cloud figure
# is Google's published median energy for a Gemini Apps text prompt (technical report,
# August 2025). Each row: label, seconds, watts, ours.
ENERGY_ROWS = [
    ("One model prediction\n(heat rebuild, with its features)", 4.8e-6, 20, True),
    ("One dashboard answer\n(46 years and 4 outlooks for a stall)", 0.0152, 20, True),
    ("Rebuilding every centre's history since 1980,\nonce, for the whole product", 15.0, 20, True),
    ("One answer from a local 8B LLM\n(qwen3:8b on the same laptop)", 7.6, 30, False),
    ("One cloud LLM prompt\n(Google's median, 2025)", None, None, False),
]
CLOUD_PROMPT_WH = 0.24
SECONDS_PER_HOUR = 3600


def job_label(job: str) -> str:
    stem, kind = job.rsplit("_", 1)
    return f"{JOB_LABELS[stem]} ({KIND_LABELS[kind]})"


def load() -> tuple[pd.DataFrame, dict[str, str]]:
    board = pd.read_csv(RESULTS_DIR / "leaderboard.csv")
    board = board[board["status"] == "ok"]
    chosen = pd.read_csv(RESULTS_DIR / "models" / "index.csv")
    return board, dict(zip(chosen["job"], chosen["model"]))


def best_baseline(rows: pd.DataFrame, column: str, higher: bool) -> float:
    scores = rows[rows["model"].isin(BASELINES)][column]
    return float(scores.max() if higher else scores.min())


def bar_chart(ax: plt.Axes, rows: pd.DataFrame, chosen: str, column: str, higher: bool) -> None:
    learned = rows[~rows["model"].isin(BASELINES)].sort_values(column, ascending=not higher)
    learned = learned.iloc[::-1]
    colours = [BAR if m == chosen else OTHER for m in learned["model"]]
    bars = ax.barh(range(len(learned)), learned[column], color=colours, height=0.55)
    ax.set_yticks(range(len(learned)))
    ax.set_yticklabels([ALGORITHM_LABELS[m] for m in learned["model"]])
    for bar, value in zip(bars, learned[column]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f" {score_text(value, higher)}", va="center", ha="left", color=INK_2, fontsize=9)
    guess = best_baseline(rows, column, higher)
    ax.axvline(guess, color=INK, linewidth=1)
    ax.text(guess, -0.75, f" simple guess {score_text(guess, higher)}", color=INK, fontsize=9,
            va="center", ha="left")
    ax.set_ylim(-1.1, len(learned) - 0.4)
    ax.set_xlim(0, max(learned[column].max(), guess) * 1.25)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)


def score_text(value: float, higher: bool) -> str:
    """Scores that run 0 to 1 (average precision) read as percentages; errors keep their unit."""
    return f"{value:.0%}" if higher else f"{value:.3g}"


def plot_rain_models(board: pd.DataFrame, chosen: dict[str, str]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=SURFACE)
    titles = {
        "rain_h0_regression": "The reading: error in mm of the wettest hour",
        "rain_h0_classification": "Payout day or not: average precision",
    }
    labels = {
        "rain_h0_regression": "Error on the test years (RMSE), mm, lower is better",
        "rain_h0_classification": "Average precision on the test years, higher is better",
    }
    for ax, job in zip(axes, RAIN_JOBS):
        style_axes(ax)
        rows = board[board["job"] == job]
        column, higher, _ = METRIC[job.rsplit("_", 1)[1]]
        bar_chart(ax, rows, chosen[job], column, higher)
        ax.set_title(titles[job], loc="left", color=INK, fontsize=11, fontweight="bold")
        ax.set_xlabel(labels[job], color=INK_2)
    fig.suptitle("The rain rebuild, the model in the product: every algorithm against the simple "
                 "guess", x=0.01, ha="left", color=INK, fontsize=12)
    fig.text(0.01, 0.01, "Blue: the model chosen on its validation score, before the test years "
             "were seen. Black line: the same-month average. Source: ml/results/leaderboard.csv.",
             color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(FIG_DIR / "ml_rain_models.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def skill_ratio(score: float, guess: float, higher: bool) -> float:
    """Times better than the simple guess: 1 is the same, 2 is twice as good."""
    return score / guess if higher else guess / score


def plot_all_jobs(board: pd.DataFrame, chosen: dict[str, str]) -> None:
    points = []
    for job, rows in board.groupby("job"):
        column, higher, _ = METRIC[job.rsplit("_", 1)[1]]
        guess = best_baseline(rows, column, higher)
        for _, row in rows[~rows["model"].isin(BASELINES)].iterrows():
            points.append({
                "job": job, "model": row["model"],
                "ratio": skill_ratio(float(row[column]), guess, higher),
                "chosen": row["model"] == chosen[job],
            })
    table = pd.DataFrame(points)
    order = table[table["chosen"]].sort_values("ratio")["job"].tolist()
    fig, ax = plt.subplots(figsize=(11, 6.2), facecolor=SURFACE)
    style_axes(ax)
    for y, job in enumerate(order):
        rows = table[table["job"] == job]
        others = rows[~rows["chosen"]]
        ax.scatter(others["ratio"], [y] * len(others), s=46, color=OTHER, zorder=2)
        pick = rows[rows["chosen"]].iloc[0]
        ax.scatter([pick["ratio"]], [y], s=80, color=BAR, zorder=3, edgecolor=SURFACE,
                   linewidth=1.5)
        tag = ALGORITHM_LABELS[pick["model"]] + ("  (in the product)" if job in SHIPPED else "")
        ax.text(rows["ratio"].max() * 1.12, y, tag, va="center", ha="left", color=INK_2, fontsize=9)
    ax.axvline(1, color=INK, linewidth=1)
    ax.text(1, -0.9, " same as the simple guess", color=INK, fontsize=9, va="center")
    ax.set_ylim(-1.3, len(order) - 0.4)
    ax.set_xscale("log")
    ax.set_xlim(0.3, 30)
    ax.set_xticks([0.5, 1, 2, 5, 10, 20])
    ax.set_xticklabels(["0.5×", "1×", "2×", "5×", "10×", "20×"])
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([job_label(j) for j in order])
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel("Times better than the simple guess on the test years (log scale)", color=INK_2)
    ax.set_title("Every job: the chosen model (blue) and the other six algorithms (grey)",
                 loc="left", color=INK, fontsize=12, fontweight="bold")
    fig.text(0.01, 0.01, "Simple guess: the same-month average, or the last reading, whichever "
             "did better. Left of the line, the guess wins. Source: ml/results/leaderboard.csv.",
             color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG_DIR / "ml_all_jobs.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def tuning_table() -> pd.DataFrame:
    """Best, median and worst validation score per algorithm and job, from model_notes.md."""
    text = (RESULTS_DIR / "model_notes.md").read_text()
    rows = []
    model = None
    for line in text.splitlines():
        heading = re.match(r"^## (\w+)$", line)
        if heading:
            model = heading.group(1)
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if model and len(cells) == 9 and cells[2].isdigit():
            rows.append({"model": model, "job": cells[0], "best": float(cells[3]),
                         "median": float(cells[4]), "worst": float(cells[5])})
    return pd.DataFrame(rows)


def plot_rain_tuning(chosen: dict[str, str]) -> None:
    tuning = tuning_table()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=SURFACE)
    titles = {
        "rain_h0_regression": "The reading: validation error, best to worst trial",
        "rain_h0_classification": "Payout day or not: precision across the trials",
    }
    for ax, job in zip(axes, RAIN_JOBS):
        style_axes(ax)
        _, higher, _ = METRIC[job.rsplit("_", 1)[1]]
        rows = tuning[tuning["job"] == job].sort_values("best", ascending=higher)
        rows = rows.reset_index(drop=True)
        for y, row in rows.iterrows():
            colour = BAR if row["model"] == chosen[job] else OTHER
            low, high = sorted((row["best"], row["worst"]))
            ax.plot([low, high], [y, y], color=colour, linewidth=2, solid_capstyle="round",
                    zorder=2)
            ax.scatter([row["median"]], [y], s=64, color=colour, zorder=3, edgecolor=SURFACE,
                       linewidth=1.5)
            ax.text(high, y, f"  {score_text(row['best'], higher)} to "
                    f"{score_text(row['worst'], higher)}", va="center", ha="left", color=INK_2,
                    fontsize=8.5)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([ALGORITHM_LABELS[m] for m in rows["model"]])
        lows = rows[["best", "worst"]].min(axis=1)
        highs = rows[["best", "worst"]].max(axis=1)
        if higher:
            ax.set_xlim(lows.min() * 0.9, 1.15)
            ax.set_xticks([0.8, 0.9, 1.0])
            ax.set_xticklabels(["80%", "90%", "100%"])
        else:
            ax.set_xlim(lows.min() * 0.9, highs.max() * 1.3)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_title(titles[job], loc="left", color=INK, fontsize=11, fontweight="bold")
        ax.set_xlabel("Score across the 40 tuning trials (dot: median trial)", color=INK_2)
    fig.suptitle("What tuning did on the rain rebuild: 40 Optuna trials per algorithm, "
                 "time-ordered folds", x=0.01, ha="left", color=INK, fontsize=12)
    fig.text(0.01, 0.01, "A short bar means the algorithm barely cares about its settings; a long "
             "one means tuning mattered. Source: ml/results/model_notes.md.",
             color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(FIG_DIR / "ml_rain_tuning.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def plot_rain_payout_days(chosen: dict[str, str]) -> None:
    metrics = pd.read_csv(RESULTS_DIR / "confusion_metrics.csv")
    rows = metrics[(metrics["job"] == "rain_h0_classification")
                   & ~metrics["model"].isin(BASELINES)]
    always_no = float(rows["always_no_accuracy"].iloc[0])
    panels = (
        ("precision", "Precision: flagged days that really paid"),
        ("recall", "Recall: payout days caught"),
        ("accuracy", "Accuracy: all days called right"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.4), facecolor=SURFACE)
    for ax, (column, title) in zip(axes, panels):
        style_axes(ax)
        ordered = rows.sort_values(column).reset_index(drop=True)
        pick = chosen["rain_h0_classification"]
        colours = [BAR if m == pick else OTHER for m in ordered["model"]]
        bars = ax.barh(range(len(ordered)), ordered[column], color=colours, height=0.55)
        for bar, value in zip(bars, ordered[column]):
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f" {value:.1%}",
                    va="center", ha="left", color=INK_2, fontsize=9)
        ax.set_yticks(range(len(ordered)))
        ax.set_yticklabels([ALGORITHM_LABELS[m] for m in ordered["model"]])
        ax.set_xlim(0, 1.22)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_title(title, loc="left", color=INK, fontsize=10.5, fontweight="bold")
        if column == "accuracy":
            ax.axvline(always_no, color=INK, linewidth=1)
            ax.text(always_no, -0.75, f"always \"no\": {always_no:.1%} ", color=INK, fontsize=9,
                    va="center", ha="right")
            ax.set_ylim(-1.1, len(ordered) - 0.4)
    fig.suptitle("Rain rebuild, payout day or not: how each algorithm did on the test years "
                 "(2023 on, 72,239 gauge-days)", x=0.01, ha="left", color=INK, fontsize=12)
    fig.text(0.01, 0.01, "Blue: XGBoost, the model in the product. A payout day is a gauge-day "
             "whose wettest work hour reached 20 mm. Source: ml/results/confusion_metrics.csv.",
             color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG_DIR / "ml_rain_payout_days.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def energy_wh(seconds: float | None, watts: float | None) -> float:
    return CLOUD_PROMPT_WH if seconds is None else seconds * watts / SECONDS_PER_HOUR


def energy_label(wh: float) -> str:
    if wh >= 1e-2:
        return f"{wh:.2g} Wh"
    if wh >= 1e-5:
        return f"{wh * 1e6:.2g} µWh"
    return f"{wh * 1e9:.2g} nWh"


def plot_energy() -> None:
    rows = [(label, energy_wh(seconds, watts), ours) for label, seconds, watts, ours in ENERGY_ROWS]
    rows = rows[::-1]
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
    style_axes(ax)
    colours = [BAR if ours else LLM for _, _, ours in rows]
    bars = ax.barh(range(len(rows)), [wh for _, wh, _ in rows], color=colours, height=0.55)
    for bar, (_, wh, _) in zip(bars, rows):
        ax.text(wh * 1.3, bar.get_y() + bar.get_height() / 2, energy_label(wh), va="center",
                ha="left", color=INK_2, fontsize=9)
    ax.set_xscale("log")
    ax.set_xlim(1e-8, 3)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([label for label, _, _ in rows])
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel("Energy per answer, watt-hours (log scale)", color=INK_2)
    ax.set_title("Energy per answer: this product (blue) against an LLM (orange)",
                 loc="left", color=INK, fontsize=12, fontweight="bold")
    swatches = [plt.Rectangle((0, 0), 1, 1, color=BAR), plt.Rectangle((0, 0), 1, 1, color=LLM)]
    ax.legend(handles=swatches, labels=["Payung's models, offline", "A large language model"],
              loc="upper right", frameon=False, labelcolor=INK_2)
    ratio = CLOUD_PROMPT_WH / energy_wh(*ENERGY_ROWS[1][1:3])
    fig.text(0.01, 0.01, f"Measured on an Apple M5 laptop on 16 Nov 2026, assuming 20 W for CPU "
             f"work and 30 W with the GPU busy. Cloud figure: Google, median Gemini Apps text "
             f"prompt, Aug 2025.\nOne cloud prompt is about {ratio:,.0f} dashboard answers.",
             color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(FIG_DIR / "ml_energy_per_answer.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    board, chosen = load()
    plot_rain_models(board, chosen)
    plot_rain_payout_days(chosen)
    plot_rain_tuning(chosen)
    plot_all_jobs(board, chosen)
    plot_energy()
    print(f"Wrote 5 charts to {FIG_DIR.relative_to(REPO_ROOT)}/ml_*.png")


if __name__ == "__main__":
    main()
