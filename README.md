# sih-fin-4

Climate-risk insurance for vulnerable households, outdoor workers and SMEs in Singapore.

Built for the Singapore-India Hackathon 2026, FinTech / InsurTech track. Income Insurance asked for insurance against heat, rain, haze and flood for people who are hit hardest by them. Our deliverable is a product proposal. This repo holds the data work and analysis behind it, built only on real, public Singapore government data.

## What's here so far

- NEA data from data.gov.sg, already committed:
  - Heat stress (WBGT), every 15 minutes, from 16 Jan 2025.
  - Rainfall per gauge, summed per hour, from 2 Dec 2016.
  - Haze (24-hour PSI and PM2.5) by region, hourly, from 9 Mar 2016.
- An analysis of how often each peril happens, how long it lasts and how much of Singapore it covers at once. Start with [`docs/notes/climate-data-findings-2026-11-09.md`](docs/notes/climate-data-findings-2026-11-09.md), or open the team report [`docs/reports/fin4-climate-data-findings-2026-11-09.html`](docs/reports/fin4-climate-data-findings-2026-11-09.html) in a browser.
- A pricing API (`api/`) for the cover. A customer says where they work and what they sell, and gets Tier 1 to 4, each with a weekly premium and a payout. For a given day it scores the loss from 0% to 100% of normal sales and works out the payout. An admin panel lets the team change every weight, band, product, tier and load, and saves each change as a new version.
- A 3D risk map (`api/map/`, served at `/map/`) over Singapore: hawker centres sized by their real stall counts, heat, rain, haze and flood layers from the committed NEA history, HDB blocks and OneMap streets for the city view, a day simulator, and a "Live now" mode that prices today from the NEA real-time APIs. Both views: what an SME owner pays and what the insurer carries: come from the same pricing engine.
- The platform site (`api/site/`, served at `/`): a landing page, a login page and role-based dashboards. A stallholder registers with their hawker centre and product, sees their live risk and quote, and starts a cover; an insurer selects their organisation, signs in and gets the portfolio desk: policies in force, accumulation, the tariff desk, the data dashboard and the map in insurer view.
- A dashboard (`app/`) to explore the data and try trigger and price ideas. It runs locally, and a hosted copy updates from `main` (see `deploy/README.md`).

## Quick start

You need [uv](https://docs.astral.sh/uv/) and a free data.gov.sg API key (sign in at [data.gov.sg](https://data.gov.sg), then API keys).

```bash
git clone https://github.com/ImNuza/sih-fin-4.git
cd sih-fin-4
uv sync
uv run streamlit run app/app.py   # dashboard on http://localhost:8501
```

The data is already committed, so the dashboard and the analysis scripts run without a key. Only the dashboard's "Live now" tab and the fetch scripts need one:

```bash
cp .env.example .env              # then put your key in DATA_GOV_SG_API_KEY
uv run scripts/fetch_wbgt.py      # heat readings to data/wbgt/
uv run scripts/fetch_psi.py       # haze readings to data/psi/
uv run scripts/fetch_rainfall.py  # rain per hour to data/rainfall/
uv run scripts/fetch_psi_history.py      # 24-hour PSI by region from Apr 2014 to data/psi/
uv run scripts/fetch_mss_daily.py        # MSS daily station records from 1980 (no key, ~2 h)
uv run scripts/fetch_era5.py             # ERA5 hourly from 1980 via Open-Meteo (no key, ~1 h)
uv run scripts/fetch_climate_indices.py  # monthly ENSO and IOD indices from NOAA (no key)
uv run scripts/heat_stats.py      # heat stats and charts
uv run scripts/hazard_stats.py    # haze and rain stats, and the heat/rain/haze comparison
```

Run one fetch script at a time. The data.gov.sg rate limit is strict (see `AGENTS.md`).

To run the pricing API and the admin panel:

```bash
uv run scripts/region_hazard_readings.py   # only after the data changes
ADMIN_USERNAME=admin ADMIN_PASSWORD=choose-one uv run uvicorn api.main:app --reload
```

The API docs are on http://localhost:8000/docs, the admin panel is on http://localhost:8000/admin/ and the risk map is on http://localhost:8000/map/. The main endpoints:

| Endpoint | What it does |
|---|---|
| `GET /api/options` | Regions, products, tiers and hazards to choose from. |
| `POST /api/quote` | Product and one place in (a region, a latitude and longitude, a hawker centre or a postcode); weekly premium and payout of every tier out. A place is priced from its nearest NEA stations, blended with its region by credibility. A hawker is charged its centre's price, a shop its postcode area's price, and a platform worker its region's price. |
| `POST /api/assess` | Product, tier and the day's readings in, loss score and payout out. |
| `GET /api/map/static` | Geography, exposure and hazard stats the map draws (from `scripts/build_map_static.py`). |
| `GET /api/map/quotes` | Quotes for every region and every hawker centre at once, with the per-hazard loss-day split. A centre's quote is the price a stall there is charged. |
| `GET /api/map/buildings` | HDB block footprints near hawker centres for the city view (nominal heights). |
| `GET /api/map/live` | Today's NEA readings and each hawker centre's live loss score (needs the API key). |
| `GET /api/map/day` | What NEA recorded on one past day, and each hawker centre's loss score from its own readings. |
| `GET /api/map/burn` | One business's last ten years: what it lost and what the cover would have paid, at the price it is charged. |
| `POST /api/auth/register`, `/login`, `/logout`, `GET /api/auth/me` | Accounts and sessions; roles `sme` and `insurer`. |
| `GET`, `POST`, `DELETE /api/policies` | A stallholder's cover, priced server-side; an insurer lists every policy. |
| `POST /api/assistant/chat` | The SafeDay assistant: one chat on every page that answers from the platform's own numbers (needs `DEEPSEEK_API_KEY`, `XAI_API_KEY` or `OPENAI_API_KEY`; keyword answers without). |
| `POST /api/assistant/listen`, `/speak` | The assistant's voice: Whisper writes down a recording in the chat's language; a neural voice reads a reply (Singapore English and Tamil voices). |
| `GET /api/insurer/portfolio` | The insurer's book: policies, premium and payout exposure by region. |
| `POST /api/insurer/payout-runs` | Assess every policy for one date and pay what its readings give (insurer login). A policy pays the daily amount it was sold with, and stops paying when the term of its latest application ends. |
| `GET`, `PUT /api/admin/tariff` | Read or save the tariff (admin login). |
| `POST /api/admin/preview` | Price an unsaved tariff (admin login). |

To rebuild the map's static bundle after a data change:

```bash
uv run scripts/fetch_geo.py           # hawker centres and planning areas to data/raw/geo/
uv run scripts/build_map_static.py    # bundle to data/processed/map_static.json
```

The starting weights and bands in `api/default_tariff.json` are assumptions for the team to agree. Premiums come from NEA history (haze, rain, heat) at a place's nearest stations, blended with its region. Flood and closure orders have no history in the repo yet, so they are priced at the assumed days a year set in the tariff.

Every payout, live score and replay reads a place's readings the same way (`api/readings.py`): haze is the region's highest 24-hour PSI of the day, rain is the middle value of the 3 nearest rain gauges that reported (the nearest gauge and any other within 5 km), and heat is the nearest WBGT station that reported on the same terms. A station that did not report is skipped, never read as 0. If no gauge reported, rain uses the MSS daily record; if there is still no reading, the payout waits for data and a later run pays it.

To tune the hazard models and run the payout back-test (on a machine with an NVIDIA GPU; see
[`ml/README.md`](ml/README.md)):

```bash
uv run --group ml python -m ml.run_all
```

## Layout

```
api/              Pricing API, admin panel (api/admin/) and the first tariff.
ml/               Hazard models: features, tuning, payout back-test. Output in ml/output/.
app/              Streamlit dashboard.
deploy/           Hosted copy: deploy script and systemd timer.
scripts/          Data download and analysis scripts.
data/wbgt/        NEA WBGT readings, one Parquet file per month.
data/psi/         NEA PSI and PM2.5 by region, one Parquet file per year.
data/rainfall/    NEA rainfall per gauge per hour, one Parquet file per month.
data/psi/psi_history_24hr.parquet   NEA Historical 24-hr PSI by region, from Apr 2014.
data/mss_daily/   MSS daily station records from 1980.
data/era5/        ERA5 hourly reanalysis at the five PSI region centres from 1980.
data/climate_indices/   Monthly ENSO (ONI) and Indian Ocean Dipole (DMI).
data/processed/   Tables made by the analysis scripts.
docs/figures/     Charts made by the analysis scripts.
docs/reports/     HTML reports for the team, with the script that builds them.
docs/notes/       Findings, meeting notes and the hackathon overview.
docs/reference/   How to use the data.gov.sg API.
docs/resources/   Team research and reference documents.
tests/            Tests for the pricing API (uv run pytest).
```

## Contributing

Read [`AGENTS.md`](AGENTS.md) first. It has the project rules for people and AI coding agents alike: data rules, code style and the git workflow. In short: real data only, no redundant code, and rebase on `main` before every push.

## Data and licence

The code is released under the [MIT Licence](LICENSE).

The weather data contains information from NEA datasets accessed from data.gov.sg, which is made available under the terms of the [Singapore Open Data Licence version 1.0](https://data.gov.sg/open-data-licence).

Third-party documents in `docs/` (the hackathon problem statements and sample policy wordings) belong to their owners and are not covered by the MIT Licence.
