# Fin 4 climate data findings (9 Nov 2026)

Source data: NEA real-time APIs on data.gov.sg. All numbers come from `scripts/heat_stats.py` and `scripts/hazard_stats.py`. Work hours are 7am to 7pm, Singapore time.

## One-line verdict

Heat is common but short. Rain is short and local. Haze is rare, but when it comes it covers the whole island and it can last weeks, as in October 2026.

## Data we used

| Peril | Measure | Period | Locations |
|---|---|---|---|
| Heat | WBGT (heat stress), every 15 minutes | 16 Jan 2025 to 7 Nov 2026 (661 days) | 8 stations at the start, 30 at the end. Trends use the 7 stations that reported all period. |
| Rain | Rainfall, every 5 minutes, summed per hour | 2 Dec 2016 to 8 Nov 2026 (27 days have no data at the source) | 37 to 90 rain gauges per day (median 62) |
| Haze | 24-hour PSI, hourly | 9 Mar 2016 to 7 Nov 2026 | 5 regions |

NEA WBGT history starts in January 2025. Other NEA feeds start in 2016.

## Heat

- WBGT reached **32°C** (the MOM rest-break level) on **22%** of days at a typical station. Somewhere in the 7-station network, it reached 32°C on **55%** of days.
- The heat is **short**. On 78% of station-days, WBGT stayed under 32°C all day. When it reached 32°C, it usually lasted under 1 hour. Only 3.2% of station-days had 2 hours or more at 32°C.
- Strong season: 22 to 26 hot days a month from April to October. 1 to 15 a month from December to March.
- Location matters. Among stations with a full year of data, Sentosa reached 32°C on 58% of days and Tuas on 0%.
- Price example from the app: the cover pays S$50 a day, up to 10 days a year. It pays when WBGT stays at 32°C or more for 2 hours at Bedok. The trigger fired about 7 days a year. The premium is about **S$11 a week**, which is above the brief's "a few dollars a week".

## Rain

Rain now covers 10 years (2 Dec 2016 to 8 Nov 2026). The 10-year numbers are close to the numbers for Jan 2025 to Nov 2026, so the first findings hold.

- A heavy hour is **20 mm or more in one hour**, in work hours. It happened on **5.1%** of days at a gauge, about 19 days a year. At 10 mm the share is 11.7%. At 30 mm it is 2.3%.
- Somewhere in Singapore, a heavy hour happened on 39% of days.
- Rain is **local**. On a day with a heavy hour, on average only **13%** of gauges had one.
- Rain is short. A gauge had on average 0.7 wet work hours (1 mm or more) per day.
- Rain has **seasons**. The share is highest in November (8.1%) and April (7.4%), and lowest in January and August (3.6%).
- Years differ less than haze does. The share went from 3.3% (2019) to 6.2% (2023) in the full years.

## Haze

- From 2016 to 2025, the 24-hour PSI was above 100 ("unhealthy") on **0 to 6 days a year**.
- **2026 is different: 39 unhealthy days**, 5 of them above 200 ("very unhealthy"). The peak was **230**.
- The main episode ran from **3 to 25 October 2026: 23 days** in a row above 100. On 17 of those days, all 5 regions were above 100. Shorter episodes came in September 2026.
- Haze is **island-wide**. On an unhealthy day, on average 3.5 of 5 regions were above 100.

## Comparison

| Peril (trigger) | Days at one location | Days anywhere | Locations hit on an event day |
|---|---|---|---|
| Heat: WBGT 32°C or more in work hours | 22% | 55% | 40% |
| Rain: an hour of 20 mm or more in work hours (2025 to 2026) | 4.8% | 36% | 14% |
| Rain: an hour of 20 mm or more in work hours (2016 to 2026) | 5.1% | 39% | 13% |
| Haze: 24-hour PSI above 100 (2025 to 2026) | 4.2% | 6.1% | 70% |
| Haze: 24-hour PSI above 100 (2016 to 2026) | 0.9% | 1.5% | 66% |

## What this may mean for our product (for discussion)

1. **Haze looks like the catastrophe peril.** It is rare, it hits almost everyone at once, and it can last weeks. That fits a parametric trigger well (PSI is public and people already act on it). It also brings the capital risk the brief warns about, so it needs a cap on payable days and reinsurance.
2. **Heat at 32°C fires too often to be a simple trigger.** A duration rule (for example 2 hours or more) or a higher level (33°C) makes it rarer. The employer rest-break cost per hot day looks small, because the heat is usually short.
3. **Rain is local, so basis risk is high.** A trigger must use the gauge nearest to the worker or shop, or people will see payouts that do not match their day.
4. **A bundle may work best.** One cover for heat, rain and haze, with a cap on payable days per season, as the brief suggests.

## Decisions for the team meeting

1. Who do we insure: outdoor and platform workers, SMEs such as hawkers, or households?
2. Which trigger, or which bundle?
3. Who pays the premium: the worker, a platform, an employer, NTUC, or a lender?

## Limits of this data

- Heat covers under 2 years. That is two hot seasons, not "decades of history".
- Rain covers 10 years, but 27 days have no data at the source.
- Haze covers 10 years, but 130 days have no data at the source.
- The prices in the app are indicative only. A real price needs a longer back-test and Income's actuaries.
