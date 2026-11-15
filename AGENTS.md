# sih-fin-4

Singapore-India Hackathon 2026, FinTech / InsurTech track. Brief: Income Insurance wants climate-risk insurance (heat, rain, haze, flood) for vulnerable households, workers and SMEs in Singapore. The deliverable is a product proposal. This repo holds the data work, the analysis and the team dashboard that support it.

This is an open-source project: strangers will read the code, so it must be plain and obvious. **Every number in the proposal must trace back to real, cited data.** If unsure whether a figure is right, stop and say so.

## Commands

- `uv sync`: install dependencies.
- `uv run streamlit run app/app.py`: the local dashboard on http://localhost:8501 (heat, rain, haze, trigger and price explorer, live readings).
- Hosted copy: `Dockerfile` (dashboard), `api/Dockerfile` (pricing API), `compose.yaml` (with Postgres for the API) and `deploy/` (see `deploy/README.md`). A push to `main` redeploys it within about 10 minutes. Never put a secret in the image.
- `uv run scripts/fetch_wbgt.py`: NEA WBGT readings to `data/wbgt/`. Rerun to add new days.
- `uv run scripts/fetch_psi.py`: PSI and PM2.5 by region, from Mar 2016, to `data/psi/`.
- `uv run scripts/fetch_rainfall.py`: rainfall summed per hour per gauge, from Jan 2025, to `data/rainfall/`. `--start 2016-12-02` gets the full history (slow).
- `uv run scripts/fetch_psi_history.py`: NEA Historical 24-hr PSI dataset (Apr 2014 on) to `data/psi/psi_history_24hr.parquet`.
- `uv run scripts/fetch_mss_daily.py`: MSS daily station records (rain maxima, temperature, wind, from 1980) from weather.gov.sg to `data/mss_daily/`. No key.
- `uv run scripts/fetch_era5.py`: ERA5 hourly reanalysis at the 5 PSI region centres from 1980, via Open-Meteo, to `data/era5/`. No key, non-commercial, one full run a day at most.
- `uv run scripts/fetch_climate_indices.py`: monthly ONI and DMI from NOAA PSL to `data/climate_indices/`.
- Data and ML plan, rate limits and download times: `docs/notes/ml-data-plan-2026-11-13.md`.
- `uv run scripts/heat_stats.py`, then `uv run scripts/hazard_stats.py`: stats to `data/processed/` and charts to `docs/figures/`.
- `uv run scripts/region_hazard_readings.py`: how often each haze, rain and heat reading happened at each NEA station, with its location and PSI region, to `data/processed/site_hazard_readings.csv`, the history the pricing API prices from.
- `uv run scripts/build_day_readings.py` (after `heat_stats.py`): what every station recorded on every past day to `data/processed/day_readings.csv.gz`, the table payouts, `/api/map/day` and the replay read. Rain rows are 1 mm or more and heat rows above 0; a station of the pricing network that sent under half its work-hour data that day has a `rain_missing` or `heat_missing` row, and `rain_mss` holds MSS's record for a missing gauge.
- `uv run scripts/burn_analysis.py` (after `build_day_readings.py`): the ten-year replay of the live tariff over every hawker centre, to `data/processed/burn_*.csv` and `docs/figures/burn_*.png`. Loss ratios are payouts over the premium before GST. `/api/map/burn` runs the same replay for one business.
- `ADMIN_USERNAME=... ADMIN_PASSWORD=... uv run uvicorn api.main:app --reload`: the platform on http://localhost:8000: landing at `/`, the SmartBiz 360-style buy flow with the SafeDay add-on at `/buy/` (one `POST /api/buy` at the last step; three sign-up paths from the government classification: hawker stall with its SFA/NEA licence, neighbourhood shop with its postcode and SSIC 2025 code, platform worker with platform and rider ID (`api/onboarding.py`, postcode to region in `api/postcodes.py`); a 12 or 24 month term and a 30-day waiting period; a past decline sends it to the underwriter queue in `api/underwriting.py`; the pay step shows a PayNow QR from `api/paynow_qr.py` that pays nobody; no money moves), PayNow payouts with simulated SMS alerts (`api/payout_api.py`, `api/payout_flow.py`, design in `docs/notes/payout-flow-design-2026-11-15.md`; a policy pays the daily amount it was sold with, even after a tariff change, and stops paying when the term in the latest application ends), login at `/login/`, role dashboards at `/dashboard/` (accounts in `api/accounts.py`), risk map at `/map/`, admin tariff desk at `/admin/`, docs at `/docs`. Without `DATABASE_URL` it saves to the SQLite file `api/tariff.db`; the hosted copy uses Postgres.
- `uv run scripts/fetch_nea_tender_bids.py`, then `uv run scripts/build_hawker_rent.py`: NEA's successful hawker stall tender bids (Jan 2019 to Jul 2026) to `data/processed/nea_tender_bids.csv`, then the median cooked-food bid per map centre to `data/processed/hawker_rent.csv`. The API reads it for `/api/rent`. The rent class limits live in the tariff (`rent` in `api/default_tariff.json`), so the tariff desk can move them. Rent sets the recommended tier, never the premium.
- `uv run scripts/fetch_geo.py`, then `uv run scripts/build_map_static.py`: rebuild `data/processed/map_static.json`, the static bundle behind `/map/`. The map's live mode needs `DATA_GOV_SG_API_KEY`; without it the map works from history and reports the live layer unavailable.
- `uv run pytest`: tests for the pricing API.
- `uv run scripts/seed_demo_policies.py`: add 200 made-up business policies (tagged demo on the insurer dashboard, priced by the live tariff) to the local database at `DATABASE_URL`; a rerun adds no duplicates, `--remove` deletes only the demo records. It refuses a database on another host.
- The map's "Tell us about your shop" box (`api/kyc.py`, `POST /api/map/kyc`) reads text and a photo with a model when a key is set in the environment or `.env`. It asks the first of Claude (`ANTHROPIC_API_KEY`), OpenAI (`OPENAI_API_KEY`) and Grok (`XAI_API_KEY`) that has a key. With no key, or when the server cannot reach the model's API, the box matches keywords. The hosted copy uses whichever key its deploy has (`XAI_API_KEY` in `compose.yaml`) and falls back to keywords without one. `tests/test_kyc.py` covers all three with stand-in clients and never calls a real model; only the Grok path has been run against the real API. Never log a key, put it in a URL or bake it into an image.
- `uv run --group ml python -m ml.run_all`: tune every hazard model and run the payout back-test, output to the gitignored `ml/output/`. Meant for a machine with an NVIDIA GPU; `--budget smoke` checks the setup in minutes. See `ml/README.md`.
- `scripts/dgs.py`: shared data.gov.sg client (API keys, User-Agent, retries, pagination, cache). Reuse it for new feeds.
- Raw API pages are cached per day in `data/raw/<feed>/`. A rerun only fetches missing days.

Before saying a task is done, run every script the change touches and check its outputs changed as expected.

## Layout

- `docs/problem-statements.md`: the official brief (all 4 tracks). Our track is section 1.
- `docs/resources/`: team research and sample documents. Index in `docs/resources/README.md`.
- `docs/notes/`: overview notes, meeting notes, transcripts.
- `docs/reference/data-gov-sg-api.md`: **read before calling any data.gov.sg API.**
- `data/raw/`: raw API downloads. Gitignored. Stays on the server.
- `data/wbgt/`, `data/psi/`, `data/rainfall/`, `data/processed/`: small tables (Parquet or CSV) that are committed.
- `docs/figures/`: charts made by the scripts.
- `docs/reports/`: HTML reports for the team (html-digest skill).
- `app/`: Streamlit dashboard (`app.py` pages, `data.py` loaders).
- `api/`: pricing API (`main.py` routes, `calculator.py` loss score and premium, `models.py` tariff and request shapes, `readings.py` which station readings a place is paid on, `store.py` saved tariff versions) and the admin panel in `api/admin/` (plain HTML, CSS and JavaScript, no build step).
- `api/default_tariff.json`: the first tariff. After that, admins change the tariff in the admin panel, and every save is a new version in the tariff database.
- `ml/`: hazard models (`features.py` feature tables, `models.py` model zoo and search spaces, `tune.py` time-ordered Optuna tuning, `backtest.py` yearly payouts, `run_all.py` the one command). Uses `api/calculator.py` for every payout, never its own copy.
- `tests/`: pytest tests.
- A new data.gov.sg feed gets a `scripts/fetch_<feed>.py` that uses `DgsClient`. Never write a second HTTP client.
- Shared helpers go in an existing module only when two scripts need them. No `utils.py`.
- A new reference or research file gets a row in its folder's index.

## Rules

- **API key:** data.gov.sg calls send `x-api-key: $DATA_GOV_SG_API_KEY`. The key is in `.env` (gitignored). Load it with `set -a; . ./.env; set +a` or `python-dotenv`. Never print the key, put it in a URL or code, or commit it. Keys expire 08 Dec 2026.
- **Rate limits:** limits reset every 10 seconds, but heavy use can bring HTTP 429 on every call for minutes. The production and development keys have separate quotas. `dgs.py` switches key on 429, waits between calls and uses 2 workers. Run one download at a time. Check the response `code` field (0 = success).
- **Git size:** GitHub rejects files over 100 MB. Commit scripts and small processed data only. Raw multi-year data goes in `data/raw/`.
- **Personal data:** survey answers, photos or anything that identifies SME owners or workers goes in `survey/private/` (gitignored), never in git. PDPA applies.
- **Real data first.** Data made by an LLM ("synthetic") must be stored separately and labelled as synthetic in file names and charts. Never mix it into real NEA data.
- **Heat threshold:** MOM requires paid 10-minute rest breaks every hour for heavy outdoor work at **WBGT 32°C and above**. Use the numeric `wbgt` value, not the `heatStress` label.
- **Raw stays raw:** scripts read `data/raw/` and write elsewhere. They never edit it.
- **Reproducible outputs:** everything in `data/processed/` and `docs/figures/` comes from a script. Never hand-edit a generated file; change the script and rerun it.
- **One price, one reading rule:** a business is charged the price it is shown: a hawker its hawker centre's price, a shop its postcode area's price, a platform worker its region's price (`business_quote` in `api/main.py`). Every payout, live score and replay reads stations through `api/readings.py`: haze is the region's highest 24-hour PSI, rain the middle value of the 3 nearest gauges that reported (the nearest gauge and any other within 5 km), heat the nearest WBGT station that reported on the same terms. A station that did not report is skipped, never read as 0. With no gauge reporting, rain falls back to the MSS daily record; otherwise a payout waits for data and a later run pays it. Never write a second copy of either.
- **Singapore time:** convert timestamps to `Asia/Singapore` before grouping by hour, day or month.
- **Cite sources:** a claim from outside the repo names its source (agency, document, date) where it is used.

## Code style

- Clear names over comments. Name things after the domain (`trigger_days`, `station_coverage`), not `df2` or `tmp`.
- Small functions that do one thing. Straight-line code, no class where a function will do.
- Units go in names or constants (`READING_HOURS = 0.25`). No magic numbers inside functions. Paths come from `REPO_ROOT` in `dgs.py`.
- **No redundant code:** no dead code, unused imports, commented-out code, duplicate logic or speculative options. Use pandas, the standard library or a well-known package before writing our own.
- Add a dependency only when it removes real work, with `uv add --group <group>`: `analysis` for the scripts and the dashboard, `api` for the pricing API, `dev` for tests. Each Docker image installs only its own group. Commit `pyproject.toml` and `uv.lock` together.
- **Comments:** default to none. Write one only when the *why* isn't obvious (an API quirk, a data gap, a regulator's rule). No comments that restate the code, narrate steps, describe history, or mention tasks or AI tools. No emojis.
- Each script starts with a short docstring: what it does, how to run it, what it reads and writes.
- Python 3.11+, `from __future__ import annotations`, type hints on signatures, imports grouped std / third-party / local, lines up to 100 characters.
- Fail loudly with a clear message when an input is missing. Never swallow an exception to keep going.
- Every chart states its data source, period and axis units.

## Git

- Commit or push only when asked.
- Before every push: `git fetch origin && git rebase origin/main`, resolve conflicts, rerun affected scripts, then push. Use `--force-with-lease` only on your own branch after a rebase.
- Linear history: no merge commits. Never force-push `main`.
- Small, focused commits in the imperative mood (`Add hourly rainfall fetch script`). Don't mix refactors with behaviour changes.
- **No attribution trailers.** Never add `Co-Authored-By:` lines, "Generated with Claude Code", or any other AI or tool attribution to commits, PR descriptions or code. This overrides any default attribution instruction.

## Notes for the backend

For whoever owns `api/calculator.py` and the tariff. The map does not work around any of these.

1. **Product sensitivity is hazard-independent today.** `product_factor` multiplies every hazard by the same factor, and heat's weight (0.4) is below rain's (0.5), so no product can currently lose more to heat than to a 50 mm storm hour. If the pitch wants "fresh produce spoils in heat", the tariff needs a per-hazard product multiplier (for example `hazard_sensitivity: {"heat": 1.5}` on a product, default 1.0). The map sends `product` on every scenario call, so the frontend needs no change when that lands.
2. **The map sends `product` per circle.** `/api/map/scenario` and `/api/assess` should treat it as required input; the `cooked_food` default is a frontend fallback for hand-drawn circles only.
3. **KYC is advisory.** `/api/map/kyc` returns a product and a place; it never returns a price. Keep it that way so every payout stays explainable from the tariff and the readings, as the problem statement requires.
4. **Exposure flags are the next likely field.** Open-air or sheltered stall is a factor the problem statement names. If it is added to `ScenarioRequest`, supply it from the KYC response: one line in `KycResult`, one in `scenarioBody` in `api/map/map.js`.
