# sih-fin-4

Climate-risk insurance for vulnerable households, outdoor workers and SMEs in Singapore.

Built for the Singapore-India Hackathon 2026, FinTech / InsurTech track. Income Insurance asked for insurance against heat, rain, haze and flood for people who are hit hardest by them. Our deliverable is a product proposal. This repo holds the data work and analysis behind it, built only on real, public Singapore government data.

## What's here so far

- NEA data from data.gov.sg, already committed:
  - Heat stress (WBGT), every 15 minutes, from 16 Jan 2025.
  - Rainfall per gauge, summed per hour, from 2 Dec 2016.
  - Haze (24-hour PSI and PM2.5) by region, hourly, from 9 Mar 2016.
- An analysis of how often each peril happens, how long it lasts and how much of Singapore it covers at once. Start with [`docs/notes/climate-data-findings-2026-11-09.md`](docs/notes/climate-data-findings-2026-11-09.md), or open the team report [`docs/reports/fin4-climate-data-findings-2026-11-09.html`](docs/reports/fin4-climate-data-findings-2026-11-09.html) in a browser.
- A pricing API (`api/`) for the cover. A customer picks a region and what they sell, and gets Tier 1 to 4, each with a weekly premium and a payout. For a given day it scores the loss from 0% to 100% of normal sales and works out the payout. An admin panel lets the team change every weight, band, product, tier and load, and saves each change as a new version.
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
uv run scripts/heat_stats.py      # heat stats and charts
uv run scripts/hazard_stats.py    # haze and rain stats, and the heat/rain/haze comparison
```

Run one fetch script at a time. The data.gov.sg rate limit is strict (see `AGENTS.md`).

To run the pricing API and the admin panel:

```bash
uv run scripts/region_hazard_readings.py   # only after the data changes
ADMIN_USERNAME=admin ADMIN_PASSWORD=choose-one uv run uvicorn api.main:app --reload
```

The API docs are on http://localhost:8000/docs and the admin panel is on http://localhost:8000/admin/. The main endpoints:

| Endpoint | What it does |
|---|---|
| `GET /api/options` | Regions, products, tiers and hazards to choose from. |
| `POST /api/quote` | Region and product in, weekly premium and payout of every tier out. |
| `POST /api/assess` | Product, tier and the day's readings in, loss score and payout out. |
| `GET`, `PUT /api/admin/tariff` | Read or save the tariff (admin login). |
| `POST /api/admin/preview` | Price an unsaved tariff (admin login). |

The starting weights and bands in `api/default_tariff.json` are assumptions for the team to agree. Premiums come from NEA history per region (haze, rain, heat). Flood and closure orders have no history in the repo yet, so they are priced at the assumed days a year set in the tariff.

## Layout

```
api/              Pricing API, admin panel (api/admin/) and the first tariff.
app/              Streamlit dashboard.
deploy/           Hosted copy: deploy script and systemd timer.
scripts/          Data download and analysis scripts.
data/wbgt/        NEA WBGT readings, one Parquet file per month.
data/psi/         NEA PSI and PM2.5 by region, one Parquet file per year.
data/rainfall/    NEA rainfall per gauge per hour, one Parquet file per month.
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
