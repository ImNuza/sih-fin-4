# Weather forecast sources for SafeDay (13 Nov 2026)

What forecast data exists for Singapore, how fine it is, and what we can use it for. Our triggers pay on **observed** NEA readings, so forecasts are only for early warnings, for stopping people from buying cover just before a storm or a haze, and for pricing. Never for payouts.

Sources were checked on 13 Nov 2026. The NEA feeds were called directly. The forecast skill test at the end was run against our own rain gauge data.

## One-line verdict

Use NEA's own forecasts for warnings: the 2-hour forecast covers 47 named areas and the 24-hour forecast covers our 5 PSI regions. Use ECMWF and CAMS for a few days' notice of storms and haze. Global models are too coarse to tell one Singapore region from another. At one day ahead they only weakly predict our 20 mm/hour rain trigger, so they cannot be used to price by region or to decide payouts.

## Singapore is small next to a global model grid cell

Singapore's main island is roughly 50 km east to west and 27 km north to south.

| Grid | Cell size | Cells across Singapore |
|---|---|---|
| 0.25° (ECMWF open data, GFS, AIFS) | about 28 km | about 2 by 1 |
| ICON global | 13 km | about 4 by 2 |
| 0.1° (ECMWF IFS open data from 20 Oct 2026, ERA5-Land, IMERG) | about 11 km | about 5 by 3 |
| SINGV (MSS's own model) | 1.5 km | about 33 by 18 |
| NEA 2-hour forecast | 47 named areas | 47 |
| NEA 24-hour forecast | 5 regions | 5, the same regions as PSI and our pricing |

We checked this by asking Open-Meteo for the 5 PSI region points on 13 Nov 2026:
- ICON gave identical numbers for north, east and central, because all three fall in the same cell.
- GFS gave identical numbers for south and central.
- Only ECMWF at 9 km gave a different number for each region.

## NEA and MSS public forecasts (data.gov.sg)

All feeds are on `https://api-open.data.gov.sg/v2/real-time/api`, the same API and key we already use (`docs/reference/data-gov-sg-api.md`). Each one accepts `?date=` for past days.

| Feed | Endpoint | What it gives | Spatial unit | Updates | History |
|---|---|---|---|---|---|
| 2-hour forecast | `/two-hr-forecast` | Text label for the next 2 hours, such as "Cloudy" or "Heavy Thundery Showers" | 47 named areas, each with a lat/long label point | About every 30 minutes | From about **15 Mar 2016** (our probe) |
| 24-hour forecast | `/twenty-four-hr-forecast` | Island-wide temperature, humidity and wind ranges. A text label per region for each 6-hour period. | 5 regions (north, south, east, west, central) | A few times a day | From about **17 Mar 2016** (our probe) |
| 4-day outlook | `/four-day-outlook` | One island-wide forecast per day: text, temperature, humidity and wind ranges | Island-wide | Daily | From about **19 Mar 2016** (our probe) |
| Lightning | `/weather?api=lightning` | Observed strikes, not a forecast. Can serve as a lead-in warning for storms. | Point locations | Every few minutes | Not checked |
| Flood alerts | `/weather/flood-alerts` | Flood alerts. The list was empty when we checked. | Point locations | About every 2 minutes | Not checked |

Notes:
- The history start dates come from a binary search on `?date=`. It assumes there are no gaps after the first day, which we did not check.
- NEA forecasts are **text labels, not amounts**. There is no forecast in mm, PSI or WBGT. "Heavy Thundery Showers" does not mean our 20 mm/hour trigger will fire.
- The 24-hour forecast's 5 regions are the same regions our pricing API uses. A warning there maps straight to a policyholder's region.
- weather.gov.sg also publishes things with no API:
  - a fortnightly outlook and monsoon updates
  - heavy rain warnings, issued up to about 30 minutes ahead for local thunderstorms ([HR Online, Jan 2025](https://www.humanresourcesonline.net/heavy-rain-warnings-in-place-in-singapore-from-10-jan-fri-and-13-jan-2025-mon))
  - rain-area radar images at 50, 240 and 480 km ranges
  - a regional haze map
  - heat stress levels on myENV

  Only an RSS feed is offered ([weather.gov.sg](https://www.weather.gov.sg/home/)).
- MSS runs **SINGV**, a 1.5 km model built with the UK Met Office. It has 80 vertical levels, makes 36- to 48-hour forecasts with hourly output, and uses ECMWF for its boundary conditions ([HKO AvRDP report](https://avrdp.hko.gov.hk/doc/SSC-Concluding-Meeting/FInal_report_SIN.pdf), [ITSC-24 poster](https://itwg.ssec.wisc.edu/wordpress/wp-content/uploads/2023/05/oral.4p.17.chandramouli_itsc24.pdf)). We found **no public SINGV data feed**. Getting it would need a data request to MSS, which is worth asking Income about.

## Open global forecast models

| Model | Who | Open grid | Range and step | Runs a day | Licence |
|---|---|---|---|---|---|
| IFS HRES | ECMWF | 0.25° in real time. 0.1° from 20 Oct 2026, about 2 hours later. Both come from the 9 km model. | 00 and 12 UTC: 3-hourly to 144 h, then 6-hourly to 360 h. 06 and 18 UTC: to 144 h. | 4 | CC-BY-4.0 |
| IFS ENS (51 members) | ECMWF | 0.25° | Same as HRES. Includes **daily rain probability** fields. | 4 | CC-BY-4.0 |
| AIFS Single and AIFS ENS (machine learning) | ECMWF | 0.25° | 6-hourly to 360 h | 4 | CC-BY-4.0 |
| GFS | NOAA | 0.25° | Hourly to 120 h, then 3-hourly to 384 h | 4 | Open, attribution requested |
| ICON | DWD (Germany) | 13 km | Hourly to 78 h. Runs to 180 h (00 and 12 UTC) or 120 h (06 and 18 UTC). | 4 | Open (DWD open data) |
| CAMS global composition (haze) | Copernicus / ECMWF | 0.4° (about 40 km) | PM2.5 and aerosols, hourly, 5 days | 2 | Copernicus licence, free |

- **ECMWF:** opened its whole real-time catalogue under CC-BY-4.0 on 1 Oct 2025. The free online portal keeps only the last 12 runs, about 2–3 days. Copies are on AWS, Azure and Google Cloud ([ECMWF open data](https://www.ecmwf.int/en/forecasts/datasets/open-data), [ECMWF news on 9 km open data](https://www.ecmwf.int/en/about/media-centre/news/2026/9-km-free-and-open-data-offers-step-change-localised-forecasts)).
- **GFS:** from the [AWS open data registry](https://registry.opendata.aws/noaa-gfs-bdp-pds/) and [NOMADS](https://www.nco.ncep.noaa.gov/pmb/products/gfs/nomads/).
- **ICON:** from [DWD open data](https://opendata.dwd.de/) and the [pycontrails ICON guide](https://py.contrails.org/notebooks/ICON.html). The open server keeps only recent runs.
- **CAMS:** from the [ADS catalogue](https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts). CAMS is the only open model that **forecasts haze**. Haze from Indonesian fires drifts over days, so a few days' notice is realistic. We have **not** tested CAMS against NEA PSI.
- **Open-Meteo** ([docs](https://open-meteo.com/en/docs/ecmwf-api)):
  - It serves all of the above as one JSON API, including the 9 km IFS, and keeps an archive of past runs, which made the test below possible.
  - It is free for non-commercial use only. A commercial product needs its paid plan, or we fetch the raw ECMWF or NOAA files ourselves.

## Regional haze

- **ASMC (ASEAN Specialised Meteorological Centre)**, run by MSS:
  - daily regional haze maps, hotspot counts from satellites and monthly haze outlooks ([ASMC](https://asmc.asean.org/home/))
  - a WIS2 API for the haze map: `https://api.wis2.asmc.asean.org/collections/regional_haze/items/REGIONAL_HAZE_MAP` ([WIS2 page](https://wis2.asmc.asean.org/regional-haze-situation/)). We have not tested it.
- Hotspot counts plus CAMS give the earliest haze warning. ASMC's July 2026 El Niño advisory is an example of a seasonal haze warning ([advisory PDF](https://isomer-user-content.by.gov.sg/124/31cd6a40-ebc8-4046-9354-9fdf4aadf8e8/Advisory_El%20Nino%20and%20Heightened%20Haze%20Risk_July%202026.pdf)).

## WRF: a model we would run, not a data feed

- WRF 4.8.0 is current and public domain ([NCAR MMM](https://www.mmm.ucar.edu/models/wrf), [public domain notice](https://www2.mmm.ucar.edu/wrf/users/public_domain_notice.html)).
- It can run at 1 km or finer over Singapore, but it gives nothing on its own. We would need:
  - GFS or ECMWF data to start it and to feed its boundaries
  - a computing cluster
  - a meteorologist to tune it for tropical storms
- MSS already runs a better-tuned model of the same kind (SINGV, 1.5 km).
- **Verdict:** not worth it for a hackathon or for this product. If Income wants forecasts finer than a region, asking MSS for SINGV output is cheaper than running WRF.

## Long history and the future (for pricing, not forecasting)

| Dataset | Grid | Period | Use for us |
|---|---|---|---|
| ERA5 | 0.25°, hourly | 1940 to about 5 days ago | Rebuild how often extremes happened before NEA's feeds start in 2016. It has sunlight, which past WBGT needs. |
| ERA5-Land | 0.1° (9 km), hourly | 1950 to present | Same, at finer resolution over land |
| GPM IMERG | 0.1°, 30 min | Early run about 4 h late, Final run about 3 months late | Backup rain measure from satellites. Not for triggers. |
| MSS V3 climate projections | 8 km over Southeast Asia, 2 km over Singapore | To 2100 | Trend loading: how much more often heat and rain extremes happen. |

- **ERA5:** licence CC-BY ([CDS](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)).
- **ERA5-Land:** licence CC-BY ([CDS](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land)).
- **GPM IMERG:** from [NASA GPM](https://gpm.nasa.gov/data) and the [UCAR guide](https://www.climatedataguide.ucar.edu/climate-data/gpm-global-precipitation-measurement-mission).
- **MSS V3:** from the [NEA/MSE release, Jan 2024](https://www.nea.gov.sg/media/news/news/index/latest-climate-projections-for-singapore-show-intensifying-urban-heat-and-more-wet-dry-extremes). We found no public download for the gridded data.

## Test: can a forecast warn of our rain trigger?

Our rain trigger fires when any gauge records an hour of 20 mm or more between 7am and 7pm. We compared it with three global models' forecasts of rain from 7am to 7pm at the 5 PSI region points, taking the wettest point each day.
- **Period:** 16 Jan 2025 to 8 Nov 2026, 662 days. The trigger fired somewhere on the island on **35%** of them.
- **Forecasts:** Open-Meteo's archive of past runs (`previous-runs-api.open-meteo.com`, fields `precipitation_previous_day1` and `_day2`).
- **Observations:** the gauge readings from `scripts/region_hazard_readings.py`.

Best results one day ahead:

| Model, 1 day ahead | Warn when forecast work-hours rain ≥ | Days warned | Trigger days caught | Warnings that were wrong |
|---|---|---|---|---|
| ECMWF IFS 9 km | 5 mm | 241 | 52% | 49% |
| ECMWF IFS 9 km | 10 mm | 110 | 31% | 35% |
| GFS | 5 mm | 265 | 55% | 51% |
| ICON | 5 mm | 155 | 38% | 43% |
| Random warnings on 241 days, for comparison | – | 241 | 36% | 65% |

- **Some skill, but weak:** ECMWF catches about half the trigger days a day ahead, with half its warnings wrong. That beats random warnings, so it is useful for a "possible heavy rain tomorrow" message, not more.
- **Forecasts get much worse two days ahead.** ECMWF at 5 mm catches 46% with 52% wrong. At 10 mm it catches 20% with 53% wrong.
- **Global models almost never forecast 20 mm or more** a day ahead, because they smooth thunderstorms over 9–28 km cells. ECMWF did it on 14 days in 662. The trigger is too local for these models, which is why payouts must stay on gauges.
- **Not tested yet:** how well NEA's 2-hour forecast warns of trigger days. It is the most likely useful short warning. Testing it means downloading its 2016–2026 history with our production key, at least one API call per day for about 3,900 days.

## What to use, for what

| Need | Use | Why |
|---|---|---|
| "Heavy rain in your area within 2 hours" message to a vendor | NEA 2-hour forecast (47 areas) plus NEA lightning | Finest public warning, already on our API key |
| "Thundery showers in your region this afternoon" | NEA 24-hour forecast (5 regions) | Same regions as our pricing |
| Pausing new cover and upgrades before a storm (Bhoomi's sales freeze) | NEA 4-day outlook plus ECMWF ENS rain probability | ENS gives a probability, so the pause rule can be written as "pause if P(rain > x mm) ≥ y" |
| Pausing new cover before haze | ASMC hotspots and haze map, CAMS PM2.5 | Haze drifts in over days, so these give days of notice |
| Seasonal loading (El Niño haze year) | ASMC and MSS seasonal advisories | Raise the haze load before the dry season |
| Base price | 10 years of NEA readings (current), extended with ERA5 or ERA5-Land | Forecasts don't tell how often things happen over a year. History does. |
| Price trend for future years | MSS V3 projections | Official Singapore projections |
| Payouts | **Observed NEA readings only** | Forecasts miss most trigger days and smooth away the local rain |

## Open questions

- Will MSS share SINGV output (1.5 km) with Income? It is the only forecast fine enough to tell neighbourhoods apart.
- Open-Meteo is free only for non-commercial use. Production would need its paid plan, or fetching the raw ECMWF, NOAA and DWD files ourselves (free, but more work).
- How well does NEA's 2-hour forecast predict our triggers? To be tested with the production key.
- How well does CAMS predict PSI above 100 a few days ahead? To be tested against `data/processed/psi_daily.parquet`.
