# Data that needs permission (13 Nov 2026)

What we would need to ask for, why, and where to ask. Everything we use today is open: data.gov.sg feeds, ECMWF and NOAA open data, Open-Meteo. The items below fill the gaps listed in `climate-data-findings-2026-11-09.md` and `weather-forecast-sources-2026-11-13.md`.

## Needs a request

| # | Data | Gap it fills | Holder | How to ask | Notes |
|---|---|---|---|---|---|
| 1 | MSS station data from automatic weather stations (2017–2025), radar rainfall, SINGV forecasts (single run and ensemble), V3 climate runs (8 km for 1980–2014, 2 km for 1995–2014) | Rain between gauges (radar), forecasts fine enough to tell regions apart (SINGV), longer and finer history | MSS | Same email as row 2 (`sales_climo@nea.gov.sg`), asking who handles research access | A*STAR's [CAWRET testbed](https://www.a-star.edu.sg/cawret) holds these as "Official Closed – Non-Sensitive". Its request forms need a CAWRET project ID from a fixed list, so they are only open to existing CAWRET projects. V3 rain data more often than hourly needs separate permission from NEA. |
| 2 | Official NEA climate records: WBGT before Jan 2025, hourly rainfall per station before Dec 2016 | Heat history is only 22 months. A longer rain record gives better 1-in-N-year estimates. | NEA (MSS climate data) | Email `sales_climo@nea.gov.sg` | Given on data.gov.sg rainfall pages. "Fees may apply for data and report preparation." Ask for a student waiver. |
| 3 | PUB water level readings over time, and past flash-flood incident records | Flood has no history in our pricing, so it is priced at 0 days | PUB | Email the 3 contacts listed on the [PUB Water Level Sensors](https://data.gov.sg/datasets/d_31333fa5cf0834f012d840365b336610/view) dataset | The open file is only the sensor list: 328 sensors with ID, name and SVY21 x/y, no readings (downloaded 13 Nov). |
| 4 | Income's own data: Droplet trigger and claims history, the combined ratio Income wants for a micro product, its expense ratio, appetite for haze reinsurance | Back-testing against real claims, and setting our tariff loads | Income Insurance | Ask at the Income consultation (Sat 15 Nov, 12:30) or through the track mentor | Not public. See `../resources/income-insurance-fy2025-financials.md`. |

## Free sign-up, no approval

| Data | Where | Use |
|---|---|---|
| ERA5 and ERA5-Land reanalysis (weather history rebuilt from models) | [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/) account | History back to 1940 or 1950, and sunlight data to rebuild past WBGT |
| CAMS haze forecasts | [Copernicus Atmosphere Data Store](https://ads.atmosphere.copernicus.eu/) account (same login) | Haze early warning |
| GPM IMERG satellite rain | [NASA Earthdata](https://urs.earthdata.nasa.gov/) account | Backup rain data |

## Not needed for the hackathon

- **Open-Meteo commercial plan:** only for a live product. The free tier is non-commercial.
- **Platform data from Grab, foodpanda and others:** needs a business partnership, not a data request.
