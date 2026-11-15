# Early-warning SMS (15 Nov 2026)

The evening before NEA forecasts a bad day, Payung texts each customer in that region. The text says what is forecast, gives one safety tip, and says that a forecast is not a payout. This is the product's risk-reduction element (Notion TODO "Add one risk-reduction / safer-behaviour element", P1, https://app.notion.com/p/a2decd5c15be83aeb2f601ab9482b904).

Code: `api/forecast_warning.py` (which regions to warn, who gets a text), `api/sms.py` (`warning_text`, the four languages), `api/live.py` (`fetch_day_forecast`), `api/payout_api.py` (two insurer endpoints), `api/site/payouts.js` (insurer desk card). Tests: `tests/test_forecast_warning.py`.

## Why Income wants it

Income's product lead gave one piece of closing advice in mentor session 1 (Income private session, 15 Nov 2026). Notion's automatic transcript of that session gives her words as:

> "The only thing I think you should look at is the sustainability of this product. Is it going to be something that people buy, if there's no claim they're going to terminate the product, or can you actually encourage them to continue? Are there any other value-added benefits that you can put forth such that even if it doesn't trigger a claim, they still feel that it's money's worth for them?"

Source: Notion meeting note "Safe Day Parametric Insurance Feedback Session", transcript, speaker B, https://app.notion.com/p/419ecd5c15be805199aec4b53b72a934 (summary page "Mentor session 1, 15 Nov: Income private session (Safe Day feedback)", https://app.notion.com/p/419ecd5c15be803ab6ece33f6f5c5e30). This quote is not in a repo file. The transcript is machine-made, so check the words against the recording before you put them on a slide.

The problem statement also names "bundling insurance with risk reduction or premium rewards for safer behaviour" as a direction it encourages (same Notion TODO, PS check).

A warning gives the customer value in a year with no payout. It also lowers losses: a stall that ties down its awning or covers its food the night before loses less.

## The forecast source

NEA's 24-hour forecast, data.gov.sg real-time API `twenty-four-hr-forecast`. It is on the same API and key as our readings (`docs/reference/data-gov-sg-api.md`), fetched with the existing `DgsClient` (`scripts/dgs.py`). There is no second HTTP client.

- NEA issues it a few times a day. The late-afternoon issue was at 17:31 SGT on both days we fetched (15 Nov 2026 and 12 Jun 2025).
- Each issue labels each of the 5 PSI regions (north, south, east, west, central) for three or four periods. The evening issue covers tonight (6 pm to 6 am), tomorrow morning (6 am to noon) and tomorrow afternoon (noon to 6 pm).
- It also gives one island-wide high and low temperature.
- The labels are words, such as "Thundery Showers" or "Hazy", not amounts. There is no forecast in mm, PSI or WBGT (`docs/notes/weather-forecast-sources-2026-11-13.md`).

Why this feed and not another one: its 5 regions are the regions our policies are priced and paid in, so a warning maps straight to a policy. The 2-hour forecast (47 areas) is too short for an evening-before warning. Global models are too coarse to tell one region from another (same note).

### NEA quirk

The 11 pm issue says "0 AM 13 Jun to 0 AM 14 Jun" but its `validPeriod.end` is 15 Jun 00:00 (fetched 15 Nov 2026 for 12 Jun 2025). So the code finds the forecast day from the daytime periods, not from `validPeriod`. Test: `test_the_late_night_issue_warns_for_the_day_it_covers`.

## The rule

The forecast day is the latest day that the issue's daytime periods (starting from 6 am up to before 6 pm) fall on. For the evening issue, that is tomorrow.

| Hazard | Warn when | Where |
| --- | --- | --- |
| Heavy rain | A daytime label on the forecast day has the word "Heavy" ("Heavy Showers", "Heavy Thundery Showers", "Heavy Thundery Showers with Gusty Winds", "Heavy Rain") | That region |
| Haze | A daytime label on the forecast day is "Hazy". "Slightly Hazy" does not warn. | That region |
| Heat | The island-wide forecast high is 35°C or more | Every region |

- Plain "Thundery Showers" does not warn. It is on most days in the monsoon season, and a text on most days would teach people to ignore it.
- Heavy rain tonight does not warn for tomorrow. The warning is about the trading day.

### Why 35°C for heat

NEA forecasts no WBGT, only the high temperature. Our heat trigger counts work hours at WBGT 32°C and above (`api/default_tariff.json`, first band 2 hours). We compared the island's highest MSS daily maximum temperature (`data/mss_daily/mss_daily.parquet`) with the days a WBGT station reached the first heat band (`data/processed/wbgt_station_days.parquet`, `hours_ge_32 >= 2`), 16 Jan 2025 to 31 Oct 2026, 654 days, 218 of them heat-trigger days:

| Warn when the day's maximum is at least | Days warned | Heat-trigger days caught | Warnings with no trigger day |
| --- | --- | --- | --- |
| 33°C | 446 | 96% | 53% |
| 34°C | 264 | 68% | 44% |
| 35°C | 58 | 17% | 36% |
| 36°C | 5 | 1% | 40% |

- 35°C texts on about 1 day in 11, with the lowest share of wrong warnings. 34°C catches more, but texts on 40% of days.
- This table uses the observed maximum, so it is the best case. A forecast high is less exact, and we have not tested NEA's forecast high against these days.
- The value is `HEAT_FORECAST_HIGH_C` in `api/forecast_warning.py`. It is a team choice for the pilot, not an NEA or MOM rule. Income can move it.

The scratch script for this table is not in the repo. To rerun it, join the two tables above by day and count.

## Who gets a text

- Every policy whose region is warned. A shop's region comes from its postcode, a hawker's from its centre.
- Policies in their 30-day waiting period get it too. The warning helps them prepare, and it pays nothing.
- Not a policy whose term ends on or before the forecast day (`application_profile.cover_ends`).
- Not a customer with no mobile. The text goes where the welcome text goes: the verified PayNow mobile, else the mobile given at sign-up (`payout_flow.welcome_contact`).
- At most one warning per customer per Singapore day, however often the run is called.
- In the customer's language (English, Chinese, Malay or Tamil).

The run returns counts: `sent`, `already_warned`, `not_warned`, `cover_ended`, `no_mobile`.

## The text

One tip, for the first hazard in the order rain, haze, heat. Example for heavy rain on 16 Nov:

> Payung: heavy rain forecast 16 Nov. Tie down awnings, raise stock. A forecast is not a payout; payment depends on the real reading.

| Language | Length (heavy rain only) | Length (rain, haze and heat) | SMS parts |
| --- | --- | --- | --- |
| English | 132 characters | 152 characters | 1 (160 a part, GSM-7) |
| Malay | 114 | 138 | 1 |
| Chinese | 48 | 54 | 1 (70 a part, Unicode) |
| Tamil | 135 | 163 | 3 (67 a part when split) |

- Tamil takes three parts, as the Tamil welcome text does (`tests/test_sms_texts.py`). A native speaker needs to shorten it.
- The Chinese, Malay and Tamil texts and tips need a native speaker's check before launch, as all our texts do (`api/sms.py`).
- The tips are the team's plain wording, not quoted from NEA or MOH.

| Hazard | English tip |
| --- | --- |
| Heavy rain | Tie down awnings, raise stock. |
| Haze | Keep N95 masks ready, cover food. |
| Heat | Drink water often, rest in shade. |

## How to run it

- `POST /api/insurer/forecast-warnings` (insurer login): reads NEA's latest 24-hour forecast and texts every customer it warns. Call it in the evening, after NEA's late-afternoon issue. Without `DATA_GOV_SG_API_KEY` it returns 503 with that variable name.
- `POST /api/insurer/demo-forecast-warnings` (insurer login), body `{"user_id": 1, "hazards": ["rain"]}`, optional `mobile` and `sms_language`: texts one customer tomorrow's warning now. It skips the one-a-day limit, so the demo can be shown again.
- Insurer desk, Payouts: the card "Demo: send a forecast warning now", under "Demo: pay a customer now". Its "Warn everyone from NEA's forecast" button calls the first endpoint.
- The customer sees the text on their dashboard under "Texts on your phone" within 5 seconds. Texts go to a real phone only when `TEXTBEE_API_KEY` is set (`api/sms_gateway.py`).

## Not done

- Nothing calls the run on a timer. Payout runs are also started by hand today. The hosted copy needs a timer at about 18:00 SGT, for example a systemd timer next to `deploy/systemd/`.
- We have not tested how often an NEA "Heavy" label comes before a rain trigger day, or a "Hazy" label before a PSI trigger day. That needs the forecast history (about 3,900 days of calls, `docs/notes/weather-forecast-sources-2026-11-13.md`).
- No warning for floods. PUB flood alerts are live, not forecast.
- The warning does not stop sales. The sales freeze before a storm or haze (gap B3 in `docs/notes/claim-parameters-and-exclusions-2026-11-15.md`) could read the same `warned_regions`.
