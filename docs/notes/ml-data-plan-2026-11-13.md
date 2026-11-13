# Data and ML plan (13 Nov 2026)

What data exists for a model that predicts trigger days and payouts, what each source limits, how
long a download takes, and which features the model needs. Sources were checked on 13 Nov 2026.

## Rate limits

| Source | Limit | Source of the limit |
|---|---|---|
| data.gov.sg real-time APIs (WBGT, rain, PSI, temperature...) | Per 10 seconds: 6 calls with no key, 12 with a development key, 30 with a production key | guide.data.gov.sg, API rate limits |
| data.gov.sg datastore search | 4 / 8 / 20 per 10 seconds | same |
| data.gov.sg dataset downloads | 2 / 4 / 10 per 10 seconds | same |
| Open-Meteo archive (ERA5), free tier | 600 calls a minute, 5,000 an hour, 10,000 a day, 300,000 a month; non-commercial only, credit required (CC BY 4.0). A long request counts as several calls. | open-meteo.com/en/pricing |
| MSS historical daily records (weather.gov.sg) | No published limit and no key. We pause 0.2 s between files. | tested 13 Nov 2026 |
| NOAA PSL climate indices | Static text files, no limit | tested 13 Nov 2026 |

Our two data.gov.sg keys (production and development) have separate quotas, and `dgs.py` switches
between them on HTTP 429. Both keys expire 08 Dec 2026, 22:10 SGT.

There is no cap on the total amount we can download. The only limit is calls per 10 seconds.

## What we have, and how long each download takes

| Data | Period | Script | Download time |
|---|---|---|---|
| WBGT heat stress, 15 min | Jan 2025 to now | `fetch_wbgt.py` | done |
| Rainfall per gauge, hourly | Dec 2016 to now | `fetch_rainfall.py` | done (about 3 h) |
| PSI and PM2.5 by region, hourly | Mar 2016 to now | `fetch_psi.py` | done |
| **Historical 24-hr PSI by region** (data.gov.sg dataset `d_b4cf557f8750260d229c49fd768e11ed`) | **Apr 2014** to Sep 2026 | `fetch_psi_history.py` | about 10 s |
| **MSS daily records per station**: daily rain, wettest 30/60/120 min, mean/max/min temperature, wind | **1980** to Sep 2026 (some stations only) | `fetch_mss_daily.py` | about 2 h |
| **ERA5 hourly** at the 5 PSI region centres: temperature, humidity, dew point, wet-bulb, wind, sunlight, rain | **1980** to now minus 6 days | `fetch_era5.py` | about 1 h (paced to the Open-Meteo hourly cap) |
| **ENSO (ONI) and IOD (DMI)**, monthly | 1950 / 1870 to 2026 | `fetch_climate_indices.py` | about 5 s |

Results of the 13 Nov runs:

- MSS: 488,917 station-days, 95 stations, 1 Jan 1980 to 31 Oct 2026. Only 17 stations go back to
  1990 or earlier. Daily rain is filled on 98% of station-days, the wettest 60 minutes on 44% and
  maximum temperature on 30%, because most gauges record rain totals only.
- ERA5: 2,053,560 region-hours, 1 Jan 1980 to 7 Nov 2026, no missing values.

Not downloaded, on purpose:

- **data.gov.sg air temperature, humidity and wind, 1 minute, from 2016.** One day of one feed is
  58 pages and takes about 16 s. Three feeds over 10 years is about 635,000 calls. At 42 calls
  per 10 s (both keys at full quota) that is at least 42 hours, in practice 2 to 3 days with 429
  pauses. ERA5 plus MSS gives the same variables back to 1980 in about 3 hours. Download the
  1-minute feeds only for the WBGT overlap (Jan 2025 on, about 8 to 10 hours) if the WBGT
  rebuild needs station-level inputs.
- **Flood alerts and lightning.** The real-time API has no data for 2024 or April 2025 and has
  data for October 2026, so history is too short to train on. PUB "Flood Prone Areas"
  (`d_c4aed98f1533eb3a66f65dbb1a30da46`) is a yearly hectare count, not events. Flash-flood
  days must come from PUB press releases and news (for example 15 days in 2010, 23 in 2011, and
  17 Apr 2021 and 20 Apr 2025), or by email to PUB. Label them as hand-collected.
- **NASA FIRMS fire hotspots** (Sumatra and Kalimantan, a leading signal for haze). Needs a free
  MAP_KEY from firms.modaps.eosdis.nasa.gov; limit 5,000 transactions per 10 minutes.

## First finding from the new data

The Historical 24-hr PSI dataset changes the haze history. Days with a regional 24-hour PSI above
100: 2014: 9, **2015: 46 (peak 322 on 25 Sep 2015)**, 2016: 4, 2017: 1, 2019: 11, 2021: 2,
2023: 2, 2025: 1, 2026 to 30 Sep: 16. The real-time feed showed only 6 days in 2019 because it
has no data for about 85 days of that year. **2026 is not the worst year on record: 2015 was.**
The findings note and the haze premium should use the longer series.

## What the model can and cannot learn

We have no claims or sales data. Income has not shared any, and SingStat's F&B index excludes
hawker stalls and is monthly. So the model cannot learn "how much a seller lost" from data. What
it can learn from real data:

1. **Hazard model (the ML part).** For each region and day, predict the readings the tariff
   uses: the highest 24-hour PSI, rain in the wettest work hour, and work hours at WBGT 32°C or
   more. Then predict the number of trigger days per region per season.
2. **Payout from the tariff (rules, not ML).** Put each predicted or past day through
   `api/calculator.py` (`assess`) to get the loss share and the payout per tier. This keeps the
   price explainable, as MAS FEAT requires.
3. **Back-test: what we would have paid.** Run every past day since 1980 (rain, heat from ERA5),
   or since 2014 (haze), through the tariff. Per year and per tier, the output is: paid days, days
   capped, total payout, premium and loss ratio. This shows the worst year (2015 for haze) and
   the capital that the catastrophe load and reinsurance must hold.
4. **Loss labels later.** The SME survey (`survey/private/`) and any Income claims data can
   replace the assumed severities in the tariff. Keep them out of git (PDPA).

## Features

Per region (or station) per day:

| Group | Features | Source |
|---|---|---|
| Calendar | month, day of year, day of week, public holiday, monsoon phase (NE Dec to Mar, inter-monsoon Apr to May and Oct to Nov, SW Jun to Sep) | calendar; data.gov.sg public holidays |
| Place | region, station ID, latitude, longitude, distance to the nearest gauge or WBGT station | NEA station metadata |
| Recent weather (lags 1, 3, 7, 30 days) | rain total, wettest hour, max temperature, humidity, sunlight, wind speed and direction | MSS, ERA5, NEA |
| Heat | ERA5 wet-bulb, temperature, humidity, sunlight, wind; WBGT rebuilt for 1980 to 2024 from these, calibrated on the 2025-2026 overlap with real WBGT | ERA5, NEA WBGT |
| Haze | PSI lags (1, 3, 7 days), PM2.5, wind direction (SW monsoon carries Sumatra smoke), dry days in a row, ONI and DMI (lags 0 to 6 months), fire hotspots | NEA, NOAA, NASA FIRMS |
| Climate state | ONI, DMI, 30-day rain anomaly against the station's own history | NOAA, MSS |

Targets:

| Target | Type | Use |
|---|---|---|
| highest 24-hour PSI of the day per region | regression | haze severity band |
| rain in the wettest work hour at a gauge (MSS gives 60-minute maxima from 1980) | regression or band classifier | rain severity band |
| work hours at WBGT 32°C or more | count | heat severity band |
| trigger days per region per season | count (Poisson or negative binomial) | premium and capital |

Models: start with gradient-boosted trees (LightGBM or XGBoost) for the daily targets, and a
Poisson model for the seasonal counts. Both are explainable with feature importance or SHAP.
Split by time (train up to 2022, test 2023 to 2026), never at random, or the model will learn
from the same haze episode on both sides of the split.

## Data rules that still apply

- Raw files stay in `data/raw/` (gitignored). Scripts write processed tables elsewhere.
- ERA5 is a model, not a station. Say so in every chart that uses it, and report its error
  against NEA stations on the overlap.
- Credit "ERA5 by Copernicus / ECMWF via Open-Meteo (CC BY 4.0)" and "NEA / MSS" where used.
