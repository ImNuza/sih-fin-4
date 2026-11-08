# sih-fin-4

Climate-risk insurance for vulnerable households, outdoor workers and SMEs in Singapore.

Built for the Singapore-India Hackathon 2026, FinTech / InsurTech track. Income Insurance asked for insurance against heat, rain, haze and flood for people who are hit hardest by them. Our deliverable is a product proposal. This repo holds the data work and analysis behind it, built only on real, public Singapore government data.

## What's here so far

- NEA data from data.gov.sg, already committed:
  - Heat stress (WBGT), every 15 minutes, from 16 Jan 2025.
  - Rainfall per gauge, summed per hour, from 16 Jan 2025.
  - Haze (24-hour PSI and PM2.5) by region, hourly, from 9 Mar 2016.
- An analysis of how often each peril happens, how long it lasts and how much of Singapore it covers at once. Start with [`docs/notes/climate-data-findings-2026-11-09.md`](docs/notes/climate-data-findings-2026-11-09.md), or open the team report [`docs/reports/fin4-climate-data-findings-2026-11-09.html`](docs/reports/fin4-climate-data-findings-2026-11-09.html) in a browser.
- A local dashboard (`app/`) to explore the data and try trigger and price ideas.

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

## Layout

```
app/              Streamlit dashboard.
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
```

## Contributing

Read [`AGENTS.md`](AGENTS.md) first. It has the project rules for people and AI coding agents alike: data rules, code style and the git workflow. In short: real data only, no redundant code, and rebase on `main` before every push.

## Data and licence

The code is released under the [MIT Licence](LICENSE).

The weather data contains information from NEA datasets accessed from data.gov.sg, which is made available under the terms of the [Singapore Open Data Licence version 1.0](https://data.gov.sg/open-data-licence).

Third-party documents in `docs/` (the hackathon problem statements and sample policy wordings) belong to their owners and are not covered by the MIT Licence.
