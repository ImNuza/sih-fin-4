# Hazard models

Models that predict the readings the cover pays on (haze, heavy rain, heat), and a back-test of
what the cover would have paid each year. Plan and data sources:
[`docs/notes/ml-data-plan-2026-11-13.md`](../docs/notes/ml-data-plan-2026-11-13.md).

## Run it on a GPU machine

Needs an NVIDIA GPU with a recent driver (`nvidia-smi` should show CUDA 12.6 or newer), git and
[uv](https://docs.astral.sh/uv/). Linux or Windows. No API key: the data is in the repo.

```bash
git clone https://github.com/ImNuza/sih-fin-4.git && cd sih-fin-4 && git checkout ml-models
uv run --group ml python -m ml.run_all
```

The first call installs the dependencies, including a CUDA build of PyTorch (about 3 GB). The
run prints `Device cuda` when it sees the GPU. To check the setup in a few minutes first:
`uv run --group ml python -m ml.run_all --budget smoke`, then delete `ml/output/` before the
real run.

A rerun skips finished work, so a stopped run continues where it stopped. Other options:

| Option | Default | What it does |
|---|---|---|
| `--budget smoke / standard / full` | `standard` | Trials and folds per model: 2/2, 40/4, 150/5. Time cap per model and job: 1, 15, 60 minutes. |
| `--tasks ...` | all | `haze rain heat haze_season rain_season` |
| `--models ...` | all | `climatology persistence linear random_forest hist_gbm xgboost lightgbm catboost mlp` |
| `--device auto / cuda / cpu` | `auto` | `cuda` stops with an error if no GPU is found. |
| `--skip-backtest` | off | Train only. The back-test alone: `uv run --group ml python -m ml.backtest` |

Run time has not been measured on a GPU yet. The upper bound for `standard` is 14 jobs × 7 tuned
models × 15 minutes, about 24 hours. Most models end well before their cap, because the haze,
heat and monthly tables are small. Rain (212,000 rows) takes longest.

## What it trains

| Task | Unit | Target | Data | Horizons | Test years |
|---|---|---|---|---|---|
| `haze` | region | highest 24-hour PSI of the day | NEA, Apr 2014 on | 1 and 7 days ahead | 2023 on |
| `rain` | gauge | wettest 60 minutes, mm | MSS, 2014 on | rebuild (0), 1 day ahead | 2023 on |
| `heat` | WBGT station | hours at WBGT 32°C or more | NEA, Jan 2025 on | rebuild (0), 1 day ahead | May 2026 on |
| `haze_season` | region | days a month in the first haze band | NEA, 2014 on | next month | 2023 on |
| `rain_season` | region | days a month a gauge has 20 mm in an hour | MSS, 2014 on | next month | 2023 on |

Each daily task is trained twice: as a **regression** of the reading, and as a
**classification** of "the reading reaches the first payout band" (PSI 101, 20 mm, 2 hours,
from `api/default_tariff.json`). The monthly tasks are **counts** with a Poisson loss.

A **rebuild** (horizon 0) uses only same-day ERA5, place and calendar, never past readings of the
target, so it can fill in places and years with no sensor: heat before 2025 and the wettest hour
before 2014 (from the gauge's daily total). The back-test uses these rebuilds.

Features (see `ml/features.py`): past readings and their 7 and 30-day means and maxima, ERA5
daily and work-hour weather (temperature, humidity, wet-bulb, sunlight, wind, rain), rain over 3,
7 and 30 days, dry days in a row, month, day of year, monsoon phase, ENSO (ONI) and Indian Ocean
Dipole (DMI) 2 to 6 months back, region and coordinates.

Models (see `ml/models.py`): climatology and persistence baselines, linear (ridge, logistic,
Poisson), random forest, histogram gradient boosting, XGBoost, LightGBM, CatBoost and a PyTorch
network. XGBoost, CatBoost and the network use the GPU.

Tuning (see `ml/tune.py`): Optuna TPE search. Folds grow forward in time with 14 days left out
before each validation block, so a model is never scored on days before the ones it learned.
Regression is tuned on RMSE, classification on average precision (the trigger is rare), counts
on Poisson deviance.

## What comes out (`ml/output/`, not in git)

- `report.md`: per job, every model ranked on the held-out years against the baselines, with
  the top features of the best one.
- `leaderboard.csv`: all scores and the best parameters. Regression rows include the payout error
  in SGD for a Tier 2 cooked-food customer, from the real tariff.
- `backtest_yearly.csv`: per year since 1980, product and tier, the mean, 95th percentile and
  largest payout per customer, the share of customers who hit the yearly cap, the premium and the
  loss ratio. Years before 2014 have no haze.
- `models/`, `predictions/`, `optuna.db`.

## Share the results (`ml/results/`, in git)

`ml/output/` holds every fitted model and stays out of git. After a run, copy what the product
needs into `ml/results/` and push it:

```bash
uv run --group ml python -m ml.publish
git add ml/results && git commit -m "Add training results" && git push
```

`ml/results/` gets the leaderboard, the report, the back-test, the best model of each job moved
to the CPU (so the API and a laptop without a GPU can load it, up to 50 MB each), and
`confusion_matrices.md` and `.csv`: for every daily job, days per actual and predicted outcome
on the test years, both as trigger or no trigger and as the tariff's payout band.

## Limits

- No claims or sales data exists, so no model learns what a seller actually lost. The tariff's
  severities are still assumptions. The models predict the readings; the tariff turns them into
  money.
- Heat has under two years of real WBGT, so the heat rebuild for earlier years is a model of a
  model. Its test error on 2026 is the honest measure.
- ERA5 is a 25 km reanalysis, not a station. Rain at one gauge is local and hard to predict a day
  ahead; expect the rain forecast to beat climatology only a little.
- Credit "ERA5 by Copernicus / ECMWF via Open-Meteo (CC BY 4.0)" wherever results are shown.
