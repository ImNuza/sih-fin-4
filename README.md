# sih-fin-4

Climate-risk insurance for vulnerable households, outdoor workers and SMEs in Singapore.

Built for the Singapore-India Hackathon 2026, FinTech / InsurTech track. Income Insurance asked for insurance against heat, rain, haze and flood for people who are hit hardest by them. Our deliverable is a product proposal. This repo holds the data work and analysis behind it, built only on real, public Singapore government data.

## What's here so far

- A complete download of NEA's Wet Bulb Globe Temperature (WBGT) readings from data.gov.sg, from 16 Jan 2025 onwards.
- A first analysis of how often heat reaches the Ministry of Manpower's 32°C WBGT level, at which heavy outdoor work needs a paid 10-minute rest break every hour. See [`docs/notes/wbgt-first-look-2026-11-08.md`](docs/notes/wbgt-first-look-2026-11-08.md).

## Quick start

You need [uv](https://docs.astral.sh/uv/) and a free data.gov.sg API key (sign in at [data.gov.sg](https://data.gov.sg), then API keys).

```bash
git clone https://github.com/ImNuza/sih-fin-4.git
cd sih-fin-4
uv sync
cp .env.example .env              # then put your key in DATA_GOV_SG_API_KEY
uv run scripts/fetch_wbgt.py      # download WBGT readings to data/wbgt/
uv run scripts/heat_stats.py      # heat stats to data/processed/, charts to docs/figures/
```

The WBGT data is already committed, so `heat_stats.py` runs without a key.

## Layout

```
scripts/          Data download and analysis scripts.
data/wbgt/        NEA WBGT readings, one Parquet file per month.
data/processed/   Tables made by the analysis scripts.
docs/figures/     Charts made by the analysis scripts.
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
