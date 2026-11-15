"""Every day since 1980 at every hawker centre, with the gaps filled by the trained models.

Measured NEA and MSS readings are used wherever they exist: haze from April 2014, the wettest
rain hour from 2014, heat from 2025. Before that, ml/serving.py rebuilt rain and heat with the
trained models. This module turns those readings into money with the live tariff, so a tariff
change reprices every year at once. It needs only numpy.

Reads data/processed/model_history.npz and model_insights.json (from ml/serving.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from api import calculator
from api.models import Tariff

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = REPO_ROOT / "data" / "processed" / "model_history.npz"
INSIGHTS_PATH = REPO_ROOT / "data" / "processed" / "model_insights.json"
HAZARDS = ("haze", "rain", "heat")
MEASURED, REBUILT = 1, 2
BAD_YEAR_QUANTILE = 0.9
RECENT_YEARS = 20
# 2015 is the worst haze year on record (46 region-days above PSI 100, peak 322).
HAZE_YEAR = 2015
MONTHS = 12


@dataclass(frozen=True)
class ModelHistory:
    days: np.ndarray
    years: np.ndarray
    months: np.ndarray
    centres: list[str]
    row_of: dict[str, int]
    readings: dict[str, np.ndarray]
    sources: dict[str, np.ndarray]

    @property
    def last_full_year(self) -> int:
        last = self.days[-1].astype(object)
        return last.year if (last.month, last.day) == (12, 31) else last.year - 1


def load() -> ModelHistory:
    if not HISTORY_PATH.exists():
        raise FileNotFoundError(f"{HISTORY_PATH} is missing. Run: python -m ml.serving")
    with np.load(HISTORY_PATH, allow_pickle=False) as stored:
        days = stored["days"].astype("datetime64[D]")
        centres = [str(name) for name in stored["centres"]]
        readings = {key: stored[key] for key in HAZARDS}
        sources = {key: stored[f"{key}_source"] for key in HAZARDS}
    years = days.astype("datetime64[Y]").astype(int) + 1970
    months = days.astype("datetime64[M]").astype(int) % MONTHS + 1
    return ModelHistory(
        days, years, months, centres, {name: i for i, name in enumerate(centres)}, readings,
        sources,
    )


def load_insights() -> dict:
    if not INSIGHTS_PATH.exists():
        raise FileNotFoundError(f"{INSIGHTS_PATH} is missing. Run: python -m ml.serving")
    return json.loads(INSIGHTS_PATH.read_text())


def day_losses(
    history: ModelHistory, rows: np.ndarray, tariff: Tariff, product_key: str
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Share of a normal day's sales lost, per centre row and day, combined as assess does."""
    product = calculator.find(tariff.products, product_key, "product")
    factor = calculator.product_factor(product)
    parts = {}
    for key in HAZARDS:
        hazard = calculator.find(tariff.hazards, key, "hazard")
        values = np.nan_to_num(history.readings[key][rows])
        parts[key] = calculator.hazard_loss(hazard, calculator.severities(hazard, values), factor)
    combined = 1 - np.prod([1 - part for part in parts.values()], axis=0)
    return combined, parts


def yearly_sums(history: ModelHistory, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sum of each row's values per calendar year (last axis is days), and the years."""
    years, starts = np.unique(history.years, return_index=True)
    return np.add.reduceat(values, starts, axis=-1), years


def centre_years(
    history: ModelHistory,
    centre: str,
    tariff: Tariff,
    product_key: str,
    tier_key: str,
    premium_yearly_sgd: float,
) -> dict:
    """One centre's payout in every year since 1980, at one tier, and what it says ahead."""
    tier = calculator.find(tariff.tiers, tier_key, "tier")
    row = np.array([history.row_of[centre]])
    combined, parts = day_losses(history, row, tariff, product_key)
    loss_days, years = yearly_sums(history, combined[0])
    paid_days = np.minimum(loss_days, tier.max_paid_days_per_year)
    paid_sgd = paid_days * tier.daily_payout_sgd
    trigger_days, _ = yearly_sums(history, (combined[0] > 0).astype(float))
    hazard_days = {key: yearly_sums(history, part[0])[0] for key, part in parts.items()}
    measured = {
        key: yearly_sums(history, (history.sources[key][row[0]] == MEASURED).astype(float))[0]
        for key in HAZARDS
    }
    days_in_year, _ = yearly_sums(history, np.ones(len(history.days)))
    rows = []
    for i, year in enumerate(years):
        share = {key: hazard_days[key][i] / loss_days[i] if loss_days[i] else 0.0
                 for key in HAZARDS}
        rows.append({
            "year": int(year),
            "complete": bool(year <= history.last_full_year),
            "trigger_days": int(trigger_days[i]),
            "paid_sgd": round(float(paid_sgd[i]), 2),
            "capped": bool(loss_days[i] > tier.max_paid_days_per_year),
            "by_hazard_sgd": {key: round(float(paid_sgd[i] * share[key]), 2) for key in HAZARDS},
            "measured_share": {key: round(float(measured[key][i] / days_in_year[i]), 2)
                               for key in HAZARDS},
        })
    complete = [r for r in rows if r["complete"]]
    return {
        "years": rows,
        "since_1980": spread(complete, premium_yearly_sgd),
        "recent": spread(complete[-RECENT_YEARS:], premium_yearly_sgd),
        "haze_year": next((r for r in rows if r["year"] == HAZE_YEAR), None),
    }


def spread(rows: list[dict], premium_yearly_sgd: float) -> dict:
    """Typical, bad (1 year in 10) and worst year of a run of years."""
    paid = np.array([r["paid_sgd"] for r in rows])
    worst = rows[int(np.argmax(paid))]
    return {
        "from_year": rows[0]["year"],
        "to_year": rows[-1]["year"],
        "typical_sgd": round(float(np.median(paid)), 2),
        "average_sgd": round(float(paid.mean()), 2),
        "bad_year_sgd": round(float(np.quantile(paid, BAD_YEAR_QUANTILE)), 2),
        "worst_sgd": worst["paid_sgd"],
        "worst_year": worst["year"],
        "years": len(rows),
        "years_without_payout": int((paid == 0).sum()),
        "years_paid_more_than_premium": int((paid > premium_yearly_sgd).sum()),
        "premium_sgd": round(premium_yearly_sgd, 2),
    }


def book_years(
    history: ModelHistory,
    tariff: Tariff,
    product_key: str,
    tier_key: str,
    stalls: dict[str, int],
    premium_by_centre: dict[str, float],
) -> dict:
    """The whole market (every food stall, one policy each) back-tested year by year."""
    tier = calculator.find(tariff.tiers, tier_key, "tier")
    names = [name for name in history.centres if name in stalls]
    rows = np.array([history.row_of[name] for name in names])
    weights = np.array([stalls[name] for name in names], dtype=float)
    premiums = np.array([premium_by_centre[name] for name in names])
    combined, _ = day_losses(history, rows, tariff, product_key)
    loss_days, years = yearly_sums(history, combined)
    paid = np.minimum(loss_days, tier.max_paid_days_per_year) * tier.daily_payout_sgd
    book_paid = weights @ paid
    book_premium = float(weights @ premiums)
    day_paid = (weights @ combined) * tier.daily_payout_sgd
    worst_day = int(np.argmax(day_paid))
    complete = years <= history.last_full_year
    ratios = book_paid / book_premium
    by_month = np.bincount(history.months - 1, weights=day_paid, minlength=MONTHS)
    worst_year = int(np.argmax(np.where(complete, book_paid, -1)))
    return {
        "policies": int(weights.sum()),
        "premium_sgd": round(book_premium, 2),
        "years": [
            {"year": int(year), "complete": bool(done), "paid_sgd": round(float(p), 2),
             "loss_ratio": round(float(r), 3)}
            for year, done, p, r in zip(years, complete, book_paid, ratios)
        ],
        "average_loss_ratio": round(float(ratios[complete].mean()), 3),
        "years_losing_money": int((ratios[complete] > 1).sum()),
        "complete_years": int(complete.sum()),
        "worst_year": {
            "year": int(years[worst_year]),
            "paid_sgd": round(float(book_paid[worst_year]), 2),
            "loss_ratio": round(float(ratios[worst_year]), 3),
            "shortfall_sgd": round(max(0.0, float(book_paid[worst_year]) - book_premium), 2),
        },
        "worst_day": {
            "day": str(history.days[worst_day]),
            "paid_sgd": round(float(day_paid[worst_day]), 2),
            "share_of_centres_paying": round(float((combined[:, worst_day] > 0).mean()), 3),
        },
        "month_share": [round(float(v), 3) for v in by_month / by_month.sum()],
    }
