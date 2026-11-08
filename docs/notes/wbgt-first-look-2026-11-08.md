# WBGT first look: how often does heat reach the MOM 32°C level? (8 Nov 2026)

Data: all NEA WBGT readings on data.gov.sg, 16 Jan 2025 to 7 Nov 2026 (661 days, 1,090,605 readings, 0.29% missing). Work hours = 7am to 7pm. Reproduce with `uv run scripts/fetch_wbgt.py` then `uv run scripts/heat_stats.py`.

Charts:
- `docs/figures/wbgt_trigger_days_by_month.png`
- `docs/figures/wbgt_trigger_share_by_station.png`

## Important data facts

- WBGT history starts **16 Jan 2025**. That is under 2 years, which is only two hot seasons.
- The station network grew from **8 stations (early 2025) to 30 (late 2026)**. For fair comparisons over time we use the **7 "core" stations** that reported on 95%+ of days: S124 Upper Changi Road North, S125 Woodlands St 13, S126 Old Chua Chu Kang Rd, S127 Stadium Rd, S128 Bishan St, S129 Bedok North St 2, S132 Jurong West St 93.
- Other NEA feeds go back much further: air temperature from May 2016, humidity from Nov 2016, wind from Dec 2016, rainfall from Dec 2016, PSI and PM2.5 from Mar 2016. **No feed has solar radiation**, which WBGT also needs.

## Findings

| Question | Answer |
|---|---|
| Days with WBGT ≥ 32°C at **any** core station (work hours) | **55%** of days |
| Days with WBGT ≥ 32°C at **one typical** station | **22%** of days |
| Same at ≥ 33°C | 20% (any core station), **4%** (one station) |
| Same at ≥ 31°C | 79% (any core station), 53% (one station) |
| Highest WBGT seen | 36.6°C |

**Heat at 32°C is common but short.** Hours at WBGT ≥ 32°C per core station-day:

| Hours | Share of station-days |
|---|---|
| 0 h | 77.8% |
| under 1 h | 13.7% |
| 1 to 2 h | 5.3% |
| 2 to 4 h | 2.9% |
| 4 h or more | 0.3% |

**Strong season.** About 22 to 26 hot days a month from April to October. Under 10 a month from November to March.

**Location matters a lot.** Among stations with a full year of data: Sentosa Palawan Green reached 32°C on 58% of days, Bishan 33%, Jurong West 14%, Upper Changi Road North 6%, Tuas Terminal Gateway 0%.

## What this means for the product (team discussion, not conclusions)

1. **"WBGT ≥ 32°C anywhere in Singapore" is not a usable trigger.** It fires on more than half of all days. That is a subsidy, not insurance, and the premium would be far too high.
2. **A trigger at one station near the insured person** fires on about 1 day in 5 at 32°C. Still frequent. Options that make it rarer: a duration rule (for example 2 or more hours at ≥ 32°C, about 3.2% of station-days, roughly 12 days a year), or a higher level (≥ 33°C, about 4% of days).
3. **The employer rest-break cost per hot day looks small.** On most days that reach 32°C, it lasts under 1 hour, which means one or two 10-minute breaks per worker. This weakens the "insure the employer's productivity loss" idea on its own. It may still work as a bundle or for long hot spells. Check with Devnavin and Income.
4. **Basis risk is real.** Readings differ widely between stations, so the trigger should use the station nearest to the worker or business, and the pitch must say how "my street was hot but my station was not" is handled.
5. **The back-test is still short.** Two hot seasons are not "decades of history". Rebuilding older WBGT from 2016+ temperature, humidity and wind (plus an outside source for sunlight) is the next data task if the team keeps heat as a trigger.
