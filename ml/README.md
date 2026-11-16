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
| `--budget smoke / standard / full` | `standard` | Trials and folds per model: 2/2, 40/4, 150/5. Time cap per model and job: 1 minute, none, 60 minutes. |
| `--tasks ...` | all | `haze rain heat haze_season rain_season` |
| `--models ...` | all | `climatology persistence linear random_forest hist_gbm xgboost lightgbm catboost mlp` |
| `--device auto / cuda / cpu` | `auto` | `cuda` stops with an error if no GPU is found. |
| `--skip-backtest` | off | Train only. The back-test alone: `uv run --group ml python -m ml.backtest` |

`standard` has no time cap, so every model runs all 40 trials. On an RTX 4050 laptop GPU the
same run with a 15-minute cap took 7.2 hours, and 12 models hit the cap. Without it, CatBoost is
by far the slowest: about 8 minutes a trial on each haze classification job, about 5 hours per
job. Plan on a day or more for a run from scratch.

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
- `confusion.md`, `confusion_metrics.csv`: per daily model, the test-year confusion matrix
  (trigger day called or not), accuracy, precision, recall and F1, and what each error means for
  the product. `uv run --group ml python -m ml.confusion` rebuilds them alone.
- `model_notes.md`: why each model is in the comparison, and per job its best, median and worst
  validation score over the trials and the hyperparameters that moved it most.
  `uv run --group ml python -m ml.model_notes` rebuilds it alone.
- `models/`, `predictions/`, `optuna.db`.

## Share the results (`ml/results/`, in git)

`ml/output/` holds every fitted model and stays out of git. After a run, copy what the product
needs into `ml/results/` and push it:

```bash
uv run --group ml python -m ml.publish
git add ml/results && git commit -m "Add training results" && git push
```

`ml/results/` gets the leaderboard, the report, the back-test, `confusion.md`, `model_notes.md`,
the best model of each job moved to the CPU (so the API and a laptop without a GPU can load it,
up to 50 MB each), and `confusion_matrices.md` and `.csv`: for every daily job, days per actual
and predicted outcome on the test years, both as trigger or no trigger and as the tariff's payout
band. The best model is the one with the best validation score, so the test years play no part
in choosing it. Loading a model needs the `ml` group, and `ml.models` for the neural network.

`uv run --group ml python -m ml.plots` draws five charts from `ml/results/` into
`docs/figures/ml_*.png`: the two shipped models against every algorithm, every job against its
simple guess, the tuning spread, payout days caught against false alarms, and energy per answer
against an LLM (timings measured on 16 Nov 2026, assumptions on the chart).

## Use them in the product (`data/processed/`, in git)

The API image has numpy but no ML libraries, so the models run once, offline:

```bash
uv run --group ml python -m ml.serving
```

It writes `data/processed/model_history.npz`: every hawker centre, every day since 1980, with
haze, rain and heat and where each came from (measured, rebuilt by a model, or measured by MSS
as the whole day's wettest hour and matched to work hours). Measured readings always win. Rain
is the tariff's reading, the wettest work hour at the gauge: NEA gauges give it from December
2016, and MSS or rebuilt whole-day values before that are quantile-mapped to it. The heat
rebuild alone predicts near-average hours every day, so its values are quantile-mapped to the
measured 2025-2026 hours; on that overlap it gives 9.0 hot days for 2025 against 9.0 measured.
It also writes `model_insights.json`: each model's test score against the simple guess, its
confusion counts, the El Niño years since 1980 and the haze facts.

`api/model_history.py` turns those readings into money with the live tariff, so a tariff change
reprices every year without rerunning anything. The dashboards read it through
`/api/model/history` (one stall since 1980: each year's payout and red, yellow and green days,
the typical, bad and worst year, El Niño years against others, what every past decade paid, and
what the next ten calendar days brought in past years), `/api/model/book` (the insurer's whole
market, the same way, with the loss ratio per year) and `/api/model/insights`. Rerun
`ml.serving` after new results are published or the data is refreshed.

The outlooks are the record of those dates, not forecasts. The forecast models were tested and
held back: next-day haze does not beat persistence, next-day heat and rain need ERA5, which
arrives about five days late, and the monthly counts do no better than the monthly average. The
dashboards say so. Nothing in the product multiplies a model by a chosen number to make a
prediction; a figure Income's actuaries cannot trace to data would fail the brief's own test.

On macOS, XGBoost and LightGBM need `brew install libomp`. PyTorch and XGBoost crash when loaded
in one process there, so `ml.serving` loads neither neural network.

## Limits

- No claims or sales data exists, so no model learns what a seller actually lost. The tariff's
  severities are still assumptions. The models predict the readings; the tariff turns them into
  money.
- Heat has under two years of real WBGT, so the heat rebuild for earlier years is a model of a
  model. Its test error on 2026 is the honest measure.
- ERA5 is a 25 km reanalysis, not a station. Rain at one gauge is local and hard to predict a day
  ahead; expect the rain forecast to beat climatology only a little.
- Credit "ERA5 by Copernicus / ECMWF via Open-Meteo (CC BY 4.0)" wherever results are shown.
