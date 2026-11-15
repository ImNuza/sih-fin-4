"""Paths, tasks and run budgets for the hazard models."""

from __future__ import annotations

from dataclasses import dataclass

from dgs import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"
PROC_DIR = DATA_DIR / "processed"
OUTPUT_DIR = REPO_ROOT / "ml" / "output"
FEATURE_DIR = OUTPUT_DIR / "features"
MODEL_DIR = OUTPUT_DIR / "models"
TARIFF_PATH = REPO_ROOT / "api" / "default_tariff.json"
OPTUNA_DB = OUTPUT_DIR / "optuna.db"
LEADERBOARD_PATH = OUTPUT_DIR / "leaderboard.csv"
BACKTEST_PATH = OUTPUT_DIR / "backtest_yearly.csv"
REPORT_PATH = OUTPUT_DIR / "report.md"

SEED = 42
WORK_START_HOUR, WORK_END_HOUR = 7, 19
# A WBGT station-day with fewer 15-minute readings than this is a partial day.
MIN_WBGT_READINGS_PER_DAY = 48
# Days left out between a training fold and its validation fold, so one haze episode
# cannot sit on both sides of the split.
EMBARGO_DAYS = 14
# Climate indices are published about a month late, so a month's features use older values.
CLIMATE_INDEX_LAGS_MONTHS = (2, 3, 4, 6)
# Horizon 0 rebuilds a day from same-day ERA5 with no past readings of the target. It is used to
# fill in history (heat before 2025, rain at gauges with gaps). Horizons 1 and up are forecasts.
RECONSTRUCTION = 0
BACKTEST_PRODUCT_KEYS = ("cooked_food", "fresh_produce", "packaged_food")
# Payout errors in the leaderboard are for one customer on this tier and product.
REPORT_TIER_KEY = "tier_2"
REPORT_PRODUCT_KEY = "cooked_food"


@dataclass(frozen=True)
class DailyTask:
    """A daily hazard reading to predict, per region or per station."""

    name: str
    hazard_key: str
    unit: str
    target: str
    horizons: tuple[int, ...]
    test_start: str
    description: str


@dataclass(frozen=True)
class SeasonalTask:
    """Trigger days per region per month: what the premium and the capital depend on."""

    name: str
    hazard_key: str
    target: str
    test_start: str
    description: str


DAILY_TASKS = {
    "haze": DailyTask(
        name="haze",
        hazard_key="haze",
        unit="region",
        target="psi_max",
        horizons=(1, 7),
        test_start="2023-01-01",
        description="Highest 24-hour PSI of the day in the region (NEA, from Apr 2014)",
    ),
    "rain": DailyTask(
        name="rain",
        hazard_key="rain",
        unit="station",
        target="rain_max_60min_mm",
        horizons=(RECONSTRUCTION, 1),
        test_start="2023-01-01",
        description="Wettest 60 minutes of the day at the gauge, mm (MSS, from 2014)",
    ),
    "heat": DailyTask(
        name="heat",
        hazard_key="heat",
        unit="station",
        target="hours_ge_32",
        horizons=(RECONSTRUCTION, 1),
        test_start="2026-05-01",
        description="Hours with WBGT at 32°C or more at the station (NEA, from Jan 2025)",
    ),
}

SEASONAL_TASKS = {
    "haze_season": SeasonalTask(
        name="haze_season",
        hazard_key="haze",
        target="trigger_days",
        test_start="2023-01-01",
        description="Days a month with the region's 24-hour PSI in the first payout band",
    ),
    "rain_season": SeasonalTask(
        name="rain_season",
        hazard_key="rain",
        target="trigger_days",
        test_start="2023-01-01",
        description="Days a month a typical gauge in the region has a wettest hour in the "
        "first payout band",
    ),
}


@dataclass(frozen=True)
class Budget:
    trials: int
    folds: int
    timeout_seconds: int | None  # None runs every trial, however long the search takes
    max_train_rows: int | None


BUDGETS = {
    "smoke": Budget(trials=2, folds=2, timeout_seconds=60, max_train_rows=20_000),
    "standard": Budget(trials=40, folds=4, timeout_seconds=None, max_train_rows=None),
    "full": Budget(trials=150, folds=5, timeout_seconds=3600, max_train_rows=None),
}
