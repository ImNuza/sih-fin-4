"""Every day since 1980 at every hawker centre, with the gaps filled by the trained models.

Measured NEA readings are used wherever they exist: haze from April 2014, the wettest work
hour of rain from December 2016, heat from 2025. Before that, ml/serving.py rebuilt rain and
heat with the trained models and matched them to the measured readings. This module turns
those readings into money with the live tariff, so a tariff change reprices every year at
once, and reads the history forward: what the same ten days, or the next two, five or ten
years, brought in past years. It needs only numpy.

Reads data/processed/model_history.npz and model_insights.json (from ml/serving.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from api import calculator
from api.models import Tariff
from api.sms import DAY_COLOUR_FROM_PERCENT

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = REPO_ROOT / "data" / "processed" / "model_history.npz"
INSIGHTS_PATH = REPO_ROOT / "data" / "processed" / "model_insights.json"
HAZARDS = ("haze", "rain", "heat")
# Where a reading came from, as ml/serving.py writes it.
MEASURED, REBUILT, MATCHED = 1, 2, 3
BAD_YEAR_QUANTILE = 0.9
RECENT_YEARS = 20
DECADE_YEARS = 10
OUTLOOK_DAYS = 10
OUTLOOK_PERIODS = (2, 5, 10)
# 2015 is the worst haze year on record (46 region-days above PSI 100, peak 322).
HAZE_YEAR = 2015
MONTHS = 12
COLOUR_FROM_SHARE = {colour: percent / 100 for colour, percent in DAY_COLOUR_FROM_PERCENT}
COLOURS = tuple(COLOUR_FROM_SHARE)


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


def colour_days(combined: np.ndarray) -> dict[str, np.ndarray]:
    """1 where a day falls in each payout band (the dashboards' day colours), else 0."""
    flags = {}
    taken = np.zeros(combined.shape, dtype=bool)
    for colour, share in COLOUR_FROM_SHARE.items():
        in_band = (combined > 0) & (combined >= share) & ~taken
        flags[colour] = in_band.astype(float)
        taken |= in_band
    return flags


def yearly_sums(history: ModelHistory, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sum of each row's values per calendar year (last axis is days), and the years."""
    years, starts = np.unique(history.years, return_index=True)
    return np.add.reduceat(values, starts, axis=-1), years


def window_indices(history: ModelHistory, start: date, length: int) -> list[tuple[int, np.ndarray]]:
    """For each past year, the day indices of the same calendar window, when all are in the data."""
    windows = []
    last = len(history.days) - 1
    for year in np.unique(history.years):
        try:
            first = np.datetime64(start.replace(year=int(year)), "D")
        except ValueError:  # 29 February
            first = np.datetime64(f"{year}-03-01", "D")
        wanted = first + np.arange(length)
        index = np.searchsorted(history.days, wanted)
        if (history.days[np.minimum(index, last)] == wanted).all():
            windows.append((int(year), index))
    return windows


def window_outlook(
    history: ModelHistory,
    combined: np.ndarray,
    weights: np.ndarray,
    daily_payout_sgd: float,
    start: date,
    length: int,
) -> dict:
    """What the same calendar window brought in every past year, per policy on average."""
    colours = colour_days(combined)
    total_weight = weights.sum()
    rows = []
    for year, index in window_indices(history, start, length):
        window = combined[:, index]
        rows.append({
            "year": year,
            "paid_sgd": float(weights @ window.sum(axis=1)) * daily_payout_sgd / total_weight,
            "trigger_days": float(weights @ (window > 0).sum(axis=1)) / total_weight,
            **{colour: float(weights @ flags[:, index].sum(axis=1)) / total_weight
               for colour, flags in colours.items()},
        })
    if not rows:
        raise ValueError("No past year holds this window")

    def summary(part: list[dict]) -> dict:
        paid = np.array([r["paid_sgd"] for r in part])
        highest = part[int(np.argmax(paid))]
        return {
            "years_checked": len(part),
            "from_year": part[0]["year"],
            "to_year": part[-1]["year"],
            "share_years_with_payout": round(
                float(np.mean([r["trigger_days"] > 0 for r in part])), 3
            ),
            "average_trigger_days": round(float(np.mean([r["trigger_days"] for r in part])), 2),
            **{f"average_{colour}_days": round(float(np.mean([r[colour] for r in part])), 2)
               for colour in COLOURS},
            "average_paid_sgd": round(float(paid.mean()), 2),
            "highest_paid_sgd": round(highest["paid_sgd"], 2),
            "highest_year": highest["year"],
        }

    return {
        "from": start.isoformat(),
        "to": (start + timedelta(days=length - 1)).isoformat(),
        "all_years": summary(rows),
        "recent": summary(rows[-DECADE_YEARS:]),
    }


def window_sums(values: np.ndarray, length: int) -> np.ndarray:
    """Sums over every run of `length` consecutive years."""
    if len(values) < length:
        return values.sum(keepdims=True)
    cumulative = np.concatenate([[0.0], np.cumsum(values)])
    return cumulative[length:] - cumulative[:-length]


def spread(rows: list[dict], premium_yearly_sgd: float) -> dict:
    """Typical, bad (1 year in 10) and worst year of a run of years, and the day colours."""
    paid = np.array([r["paid_sgd"] for r in rows])
    worst = rows[int(np.argmax(paid))]
    colours = {colour: np.array([r[f"{colour}_days"] for r in rows]) for colour in COLOURS}
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
        **{f"typical_{colour}_days": round(float(np.median(days)), 1)
           for colour, days in colours.items()},
        **{f"bad_year_{colour}_days": round(float(np.quantile(days, BAD_YEAR_QUANTILE)), 1)
           for colour, days in colours.items()},
    }


def el_nino_split(rows: list[dict], el_nino_years: set[int]) -> dict:
    """Average payout in El Nino years against other years."""
    in_el_nino = [r["paid_sgd"] for r in rows if r["year"] in el_nino_years]
    other = [r["paid_sgd"] for r in rows if r["year"] not in el_nino_years]
    return {
        "years": sorted(y for y in el_nino_years if rows[0]["year"] <= y <= rows[-1]["year"]),
        "average_paid_sgd": round(float(np.mean(in_el_nino)), 2) if in_el_nino else None,
        "average_paid_other_sgd": round(float(np.mean(other)), 2) if other else None,
    }


def period_outlook(rows: list[dict], length: int, premium_yearly_sgd: float) -> dict:
    """What every run of `length` years in these rows paid, as a guide to the next `length`."""
    paid = window_sums(np.array([r["paid_sgd"] for r in rows]), length)
    premium = premium_yearly_sgd * length
    worst = int(np.argmax(paid))
    days = {
        key: window_sums(np.array([r[key] for r in rows], dtype=float), length)
        for key in ("trigger_days", *(f"{colour}_days" for colour in COLOURS))
    }
    return {
        "years": length,
        "basis_from_year": rows[0]["year"],
        "basis_to_year": rows[-1]["year"],
        "basis_years": len(rows),
        "windows": int(len(paid)),
        "lowest_sgd": round(float(paid.min()), 2),
        "typical_sgd": round(float(np.median(paid)), 2),
        "bad_sgd": round(float(np.quantile(paid, BAD_YEAR_QUANTILE)), 2),
        "highest_sgd": round(float(paid.max()), 2),
        "highest_from_year": rows[worst]["year"],
        "highest_to_year": rows[min(worst + length - 1, len(rows) - 1)]["year"],
        "premium_sgd": round(premium, 2),
        "windows_paid_more_than_premium": int((paid > premium).sum()),
        **{f"typical_{key}": round(float(np.median(values)), 1) for key, values in days.items()},
        **{f"highest_{key}": round(float(values.max()), 1) for key, values in days.items()},
    }


def centre_years(
    history: ModelHistory,
    centre: str,
    tariff: Tariff,
    product_key: str,
    tier_key: str,
    premium_yearly_sgd: float,
    el_nino_years: set[int],
    outlook_start: date,
) -> dict:
    """One centre's payout in every year since 1980, at one tier, and what it says ahead."""
    tier = calculator.find(tariff.tiers, tier_key, "tier")
    row = np.array([history.row_of[centre]])
    combined, parts = day_losses(history, row, tariff, product_key)
    loss_days, years = yearly_sums(history, combined[0])
    paid_days = np.minimum(loss_days, tier.max_paid_days_per_year)
    paid_sgd = paid_days * tier.daily_payout_sgd
    trigger_days, _ = yearly_sums(history, (combined[0] > 0).astype(float))
    colours = {colour: yearly_sums(history, flags[0])[0]
               for colour, flags in colour_days(combined).items()}
    hazard_days = {key: yearly_sums(history, part[0])[0] for key, part in parts.items()}
    measured = {
        key: yearly_sums(history, np.isin(history.sources[key][row[0]], (MEASURED, MATCHED))
                         .astype(float))[0]
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
            "el_nino": int(year) in el_nino_years,
            "trigger_days": int(trigger_days[i]),
            **{f"{colour}_days": int(colours[colour][i]) for colour in COLOURS},
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
        "el_nino": el_nino_split(complete, el_nino_years),
        # The outlooks read the last RECENT_YEARS years, which run hotter and wetter than the
        # decades before, so they lean towards what is coming rather than the 1980s.
        "outlooks": [
            period_outlook(complete[-RECENT_YEARS:], length, premium_yearly_sgd)
            for length in OUTLOOK_PERIODS
        ],
        "next_10_days": window_outlook(
            history, combined, np.ones(1), tier.daily_payout_sgd, outlook_start, OUTLOOK_DAYS
        ),
    }


def book_years(
    history: ModelHistory,
    tariff: Tariff,
    product_key: str,
    tier_key: str,
    stalls: dict[str, int],
    premium_by_centre: dict[str, float],
    el_nino_years: set[int],
    outlook_start: date,
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
    policies = float(weights.sum())
    colours = {colour: (weights @ yearly_sums(history, flags)[0]) / policies
               for colour, flags in colour_days(combined).items()}
    day_paid = (weights @ combined) * tier.daily_payout_sgd
    worst_day = int(np.argmax(day_paid))
    complete = years <= history.last_full_year
    ratios = book_paid / book_premium
    by_month = np.bincount(history.months - 1, weights=day_paid, minlength=MONTHS)
    worst_year = int(np.argmax(np.where(complete, book_paid, -1)))
    decade_ratios = window_sums(book_paid[complete], DECADE_YEARS) / (book_premium * DECADE_YEARS)
    in_el_nino = np.isin(years, list(el_nino_years)) & complete
    return {
        "policies": int(policies),
        "premium_sgd": round(book_premium, 2),
        "weekly_premium_per_policy_sgd": round(book_premium / policies / 52, 2),
        "years": [
            {"year": int(year), "complete": bool(done), "paid_sgd": round(float(p), 2),
             "loss_ratio": round(float(r), 3), "el_nino": int(year) in el_nino_years,
             **{f"{colour}_days": round(float(colours[colour][i]), 1) for colour in COLOURS}}
            for i, (year, done, p, r) in enumerate(zip(years, complete, book_paid, ratios))
        ],
        "average_loss_ratio": round(float(ratios[complete].mean()), 3),
        "years_losing_money": int((ratios[complete] > 1).sum()),
        "complete_years": int(complete.sum()),
        **{f"typical_{colour}_days": round(float(np.median(colours[colour][complete])), 1)
           for colour in COLOURS},
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
        "el_nino": {
            "years": sorted(int(y) for y in years[in_el_nino]),
            "average_loss_ratio": round(float(ratios[in_el_nino].mean()), 3)
            if in_el_nino.any() else None,
            "average_loss_ratio_other": round(float(ratios[complete & ~in_el_nino].mean()), 3),
        },
        "next_10_years": {
            "windows": int(len(decade_ratios)),
            "lowest_loss_ratio": round(float(decade_ratios.min()), 3),
            "typical_loss_ratio": round(float(np.median(decade_ratios)), 3),
            "highest_loss_ratio": round(float(decade_ratios.max()), 3),
            "premium_sgd": round(book_premium * DECADE_YEARS, 2),
        },
        "next_10_days": window_outlook(
            history, combined, weights, tier.daily_payout_sgd, outlook_start, OUTLOOK_DAYS
        ),
    }
