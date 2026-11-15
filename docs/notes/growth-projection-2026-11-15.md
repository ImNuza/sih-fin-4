# Growth projection: customers, premium pool, payouts and Income's profit to 2040, per segment (15 Nov 2026)

**These are projections, not forecasts.** The market counts are cited. The uptake curves, the tier mix and the shop trade mix are assumptions, stated in section 8. The prices are today's prices from the finished pricing engine on observed NEA history. The V3 climate overlay (section 7) is a projection and is **not used for pricing**.

Notion todo (assigned to Deval, from the Ashutosh meeting, 14 Nov): "Growth projection: extrapolate premium pool, payouts and market share to 2030 / 2035 / 2040 from historical growth rates, and overlay the V3 climate scenarios." Problem-statement check on that row: fine as a projection slide, label it as projections, keep the pricing on observed NEA history.

How to read this note:
- Every number comes from `scripts/growth_projection.py` and its CSVs, or from a source tag [S1] to [S12] (list at the end).
- "Base (low to high)" gives the base uptake case, then the low and high cases.
- "Profit" is Income's underwriting result on SafeDay: premium before GST, less payouts, management and distribution. Income keeps the 6% reinsurance part and carries every payout, so a bad year shows its full hit. A real haze treaty would cut the bad-year loss and the mean profit.
- "1-in-10 bad year" and "1-in-20 bad year" are the 10th and 5th percentiles of 10,000 simulated runs. Each future year takes the weather of one real year, 2015 to 2026, with equal weight, the same year for every place and segment. With 12 equal years, the 1-in-20 bad year is a 2015-type haze year and the 1-in-10 bad year is a 2026-type haze year.
- Prices are held at today's level in real terms. No inflation is added.
- S$ m means millions of Singapore dollars.

## 1. Summary

### Pitch paragraph

SafeDay can grow from about 6,000 policies in 2027 to about 19,000 by 2035 (range 5,000 to 36,000), across hawker stalls, market stalls, neighbourhood shops and platform workers, on one pricing engine and no new technology. At today's prices that is a premium pool of about S$4.6 million a year and an expected profit for Income of about S$0.6 million a year, or S$7.3 million over 2027 to 2040 (range S$1.9 to 14.4 million). Haze years are in that figure, not left out: a 2015-type haze year turns the year into a loss of about S$3.3 million, so Income loses money in about one year in six, but over the 14 years 91% of simulated runs end in profit. SafeDay is a small, new line next to Income's S$51 million a year of general insurance underwriting profit; its value is a new customer group, a live view of its climate exposure, and a yearly price review that passes a warming climate on instead of absorbing it.

### Milestones per segment (base uptake, low to high in brackets)

| Segment | Year | Policies | Share of the segment | Premium pool, with GST | Profit, mean year | Profit, 1-in-20 bad year |
|---|---|---|---|---|---|---|
| Hawkers: cooked food | 2030 | 1,980 (677 to 3,287) | 28.7% | S$0.98 m | S$0.13 m (0.04 to 0.21) | -S$0.73 m |
| | 2035 | 2,364 (1,035 to 3,596) | 32.9% | S$1.18 m | S$0.15 m (0.07 to 0.23) | -S$0.87 m |
| | 2040 | 2,478 (1,122 to 3,754) | 33.0% | S$1.23 m | S$0.16 m (0.07 to 0.25) | -S$0.91 m |
| Hawkers: market stalls | 2030 | 254 (64 to 638) | 5.8% | S$0.04 m | S$0.006 m (0.001 to 0.014) | -S$0.03 m |
| | 2035 | 583 (170 to 1,207) | 14.3% | S$0.10 m | S$0.013 m (0.004 to 0.026) | -S$0.07 m |
| | 2040 | 563 (185 to 1,127) | 15.0% | S$0.10 m | S$0.013 m (0.004 to 0.026) | -S$0.07 m |
| Neighbourhood shops | 2030 | 723 (113 to 2,202) | 4.8% | S$0.11 m | S$0.014 m (0.002 to 0.041) | -S$0.07 m |
| | 2035 | 1,471 (365 to 3,027) | 9.7% | S$0.21 m | S$0.027 m (0.007 to 0.055) | -S$0.15 m |
| | 2040 | 1,518 (447 to 3,040) | 10.0% | S$0.22 m | S$0.029 m (0.009 to 0.058) | -S$0.16 m |
| Platform workers | 2030 | 11,659 (1,508 to 26,836) | 16.3% | S$2.51 m | S$0.32 m (0.04 to 0.74) | -S$1.77 m |
| | 2035 | 14,222 (3,217 to 28,619) | 19.9% | S$3.06 m | S$0.38 m (0.09 to 0.77) | -S$2.16 m |
| | 2040 | 14,317 (3,547 to 28,640) | 20.0% | S$3.09 m | S$0.40 m (0.10 to 0.80) | -S$2.17 m |
| **All segments** | 2030 | **14,616 (2,363 to 32,963)** | 14.9% | **S$3.65 m** | **S$0.47 m (0.09 to 1.01)** | **-S$2.61 m** |
| | 2035 | **18,640 (4,787 to 36,449)** | 19.0% | **S$4.55 m** | **S$0.57 m (0.16 to 1.08)** | **-S$3.26 m** |
| | 2040 | **18,876 (5,301 to 36,561)** | 19.2% | **S$4.63 m** | **S$0.61 m (0.19 to 1.13)** | **-S$3.31 m** |

Source: `data/processed/projection_segments.csv`. Shops by product are in section 6.2.

### Five things to say out loud

1. **The money is in platform workers, not hawkers.** Platform workers are 76% of base policies and 67% of the base premium pool in 2040. Cooked-food hawkers are the pilot, not the business.
2. **SafeDay is small for Income.** In 2040 the base premium before GST is 0.80% of Income's 2025 general insurance gross premiums (S$529.4 m [S9]). The base mean profit is 1.2% of Income's average general insurance underwriting profit of S$51.3 m a year over 2021 to 2025 [S9].
3. **Haze sets the bad years.** About 1 year in 6 is a loss. Over 2027 to 2030 alone, 22% of runs end in a loss, because one haze year costs more than the early years earn.
4. **Climate pushes payouts up, and the yearly review is what keeps the product whole.** Under V3, by 2040 expected payouts rise 48% to 105% at today's price, and the mean year becomes a loss. Repriced each year, the margin holds and the bad-year loss stays near today's (section 7).
5. **The pricing itself never uses a forecast.** Every premium here is the engine's price on observed NEA readings.

## 2. Method in five steps

1. **Market per segment, 2027 to 2040.** A cited base count, grown at its cited historical rate. With no rate, it is held flat (section 3).
2. **Uptake.** An S-curve per segment and case: the launch-year count (from the expected-impact note's year-1 cases where they exist), rising to a ceiling (section 4).
3. **Per-policy economics from the finished engine.** `calculator.quote` prices every place a business is charged at, from `api/place_days.py` replays under `api/default_tariff.json`, exactly as `POST /api/quote` does. Spot checks of Tiong Bahru Market (cooked food), the east region (platform work) and postcode 560000 (general goods) gave the same four tier prices through the API and the script. Each replay year's payout is `min(that year's loss-days, the tier's limit) x daily amount`, the quantity the price averages. Hawker centres are weighted by their cooked-food stalls; postcode areas and PSI regions equally. The tier mix is 30/40/20/10.
4. **Weather.** 10,000 runs. Each future year draws one real year, 2015 to 2026, the same year for every place and segment, so a haze year hits everyone together.
5. **V3 overlay.** Heat and rain loss-days shifted by V3's published changes, held separate from the base case, not used for pricing (section 7).

## 3. Market size per segment

| Segment | Base count | Growth a year | Source of count and rate | 2040 |
|---|---|---|---|---|
| Hawkers: cooked food | 6,665 stalls in 2026 (5,837 in 103 existing centres, 589 in 16 new, 161 in 3 replacement, 78 in 1 interim) | +0.86% | Count: NEA Hawker Centres dataset [S1]. Rate: 6,121 cooked-food stalls in NEA's 2016 list [S2] to 6,665 in 2026. A further 260 stalls are under construction [S1]; the rate covers them. | 7,509 |
| Hawkers: market stalls | 4,781 stalls at end 2025 | -1.59% | Count: 11,446 NEA hawker stalls at end 2025 [S3] less 6,665 cooked-food stalls [S1]. Rate: NEA hawker stalls, 13,440 (2015) to 11,446 (2025) [S3]. | 3,758 |
| Neighbourhood shops | about 15,200 HDB shops in 2022 | held flat | HDB press release, 19 Nov 2022 [S4] (search snippet only). No series found, so no rate. | 15,200 |
| Platform workers | 71,600 resident regular platform workers in 2025 | held flat | MOM, Labour Force in Singapore 2025, para 2.36 [S5]. MOM gives 67,200 for 2024 [S5]. One year is not a trend, so the count is held flat. | 71,600 |

Two checks. The two NEA sources do not measure the same thing: NEA's 2016 list sums to 14,058 stalls in 107 centres [S2], while SingStat gives 13,310 for 2016 [S3]. The cooked-food share of all NEA stalls was 44% in the 2016 list and is 58% now, so market stalls have fallen faster than the -1.59% used here (6,121 to 6,665 cooked, 7,937 to 4,781 other). The market-stall figure includes every non-cooked stall (lock-ups, dry goods, services), not only fresh produce. These segments are small either way.

## 4. Uptake: S-curves to a ceiling

Customers = market x share. The share follows an S-curve that starts at the launch-year share and levels off at the ceiling. The steepness is 0.5 (low), 0.7 (base) and 0.9 (high). All values are assumptions.

| Segment | Case | Launch | Launch-year customers | Ceiling share | Reason for the ceiling |
|---|---|---|---|---|---|
| Hawkers: cooked food | low / base / high | 2027 | 300 / 1,000 / 1,946 [S6] | 15% / 33% / 50% | About two-thirds of cooked-food stallholders hold some insurance (MSE, 4 Aug 2026, via [S6]). Base is half of them; high is three in four of them. |
| Hawkers: market stalls | low / base / high | 2029 / 2028 / 2028 | 1% / 2% / 4% | 5% / 15% / 30% | Second rung after the cooked-food pilot. Lower loss per day, so less need. |
| Neighbourhood shops | low / base / high | 2029 / 2027 / 2027 | 0.5% / 1% / 3% [S6] | 3% / 10% / 20% | The SmartBiz 360 add-on is new (Oct 2026), and most of its sectors are indoor [S6]. |
| Platform workers | low / base / high | 2027 | 500 / 5,000 / 14,320 [S6] | 5% / 20% / 40% | Base is the team's aim of 20% of 71,600 [S6]. Low is one association with no platform deal. |

Comparable uptake evidence, to show both ends are possible:
- SEWA's heat-index income cover in India grew from 21,000 to about 250,000 members in 2023 to 2026, with donors paying part of the premium [S7].
- ZhongAn's heat cover in China sold over 200,000 policies; PayPay's heatstroke cover in Japan passed 400,000 [S7]. Both are cheap, app-sold products.
- KB Insurance's heat and rain cover for Korean market stallholders had no subscribers ten months after launch, because nobody would carry the premium [S7]. That is the low case's warning.
- The 2027 base total, 6,152 policies, equals the expected-impact note's middle year-1 case [S6].

## 5. Per-policy economics from the pricing engine

Today's tariff, tier mix 30/40/20/10, averaged over the places each segment buys at. Every tier at every place is sold directly (no tier is above the referral guardrail). Source: `data/processed/projection_unit_economics.csv`.

| Segment (product) | Yearly premium with GST | A week | Expected payouts (engine) | Reinsurance | Management | Distribution | Profit part | GST | Profit, mean year | Profit, 2026-type year | Profit, 2015-type year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Hawkers: cooked food | S$497.07 | S$9.56 | S$285.79 | S$27.36 | S$41.62 | S$62.65 | S$38.61 | S$41.04 | S$65.87 | -S$226.13 | -S$367.90 |
| Hawkers: market stalls (fresh produce) | S$173.09 | S$3.33 | S$99.52 | S$9.53 | S$14.49 | S$21.81 | S$13.44 | S$14.29 | S$22.93 | -S$79.41 | -S$127.95 |
| Shops: general goods | S$55.19 | S$1.06 | S$31.73 | S$3.04 | S$4.62 | S$6.96 | S$4.29 | S$4.56 | S$7.25 | -S$25.65 | -S$39.15 |
| Shops: packaged food | S$57.20 | S$1.10 | S$32.89 | S$3.15 | S$4.79 | S$7.21 | S$4.44 | S$4.72 | S$7.51 | -S$26.58 | -S$40.57 |
| Shops: cooked food | S$510.72 | S$9.82 | S$293.64 | S$28.11 | S$42.76 | S$64.37 | S$39.67 | S$42.17 | S$67.11 | -S$233.84 | -S$363.10 |
| Shops: fresh produce | S$177.88 | S$3.42 | S$102.27 | S$9.79 | S$14.89 | S$22.42 | S$13.82 | S$14.69 | S$23.37 | -S$82.34 | -S$126.25 |
| Shops: flowers | S$232.23 | S$4.47 | S$133.52 | S$12.78 | S$19.44 | S$29.27 | S$18.04 | S$19.17 | S$30.51 | -S$107.31 | -S$164.87 |
| Platform workers | S$215.51 | S$4.14 | S$123.91 | S$11.86 | S$18.04 | S$27.16 | S$16.74 | S$17.79 | S$28.05 | -S$97.12 | -S$151.79 |

- The mean replay payout over 2015 to 2026 is within 0.5% of the engine's expected payout (2014 to 2026) for every segment, so the simulation and the price agree.
- "Profit, mean year" is close to the profit part plus the reinsurance part, because Income keeps the reinsurance part here.
- Per tier figures (Tier 1 to 4) are in the CSV. Cooked-food hawkers: Tier 1 S$246.26 a year, Tier 2 S$451.47, Tier 3 S$729.30, Tier 4 S$967.44.
- The 2015 replay year has haze only from the record; rain (feed from Dec 2016) and heat (feed from 2025) enter at their average, as the price does. The 2026 year runs to 8 Nov and is annualised, as the price does.

## 6. Results of the weather simulation

### 6.1 The haze-year swing

Every year other than the two haze years (2015, 2026) is a profit for every segment. So:
- About 1 future year in 6 is a loss.
- In 2040 at base uptake, all segments: a mean year makes S$0.61 m. A 2026-type year loses S$2.10 m. A 2015-type year loses S$3.31 m. The swing from a mean year to a 2015-type year is S$3.9 m, about six and a half mean years of profit.
- Per policy, cooked-food hawkers: +S$65.87 in a mean year, -S$367.90 in a 2015-type year.

### 6.2 Neighbourhood shops by product (base, low to high)

The trade mix is an assumption (section 8). Uptake is the same S-curve for every product.

| Shop product | Shops | 2030 policies | 2040 policies | 2040 premium pool | 2040 profit, mean year | 2040 profit, 1-in-20 bad year |
|---|---|---|---|---|---|---|
| General goods (40%) | 6,080 | 289 (45 to 881) | 607 (179 to 1,216) | S$0.03 m | S$0.004 m | -S$0.024 m |
| Packaged food (30%) | 4,560 | 217 (34 to 660) | 456 (134 to 912) | S$0.03 m | S$0.003 m | -S$0.018 m |
| Cooked food (15%) | 2,280 | 108 (17 to 330) | 228 (67 to 456) | S$0.12 m | S$0.015 m | -S$0.083 m |
| Fresh produce (10%) | 1,520 | 72 (11 to 220) | 152 (45 to 304) | S$0.03 m | S$0.004 m | -S$0.019 m |
| Flowers (5%) | 760 | 36 (6 to 110) | 76 (22 to 152) | S$0.02 m | S$0.002 m | -S$0.013 m |

Cooked-food shops are 15% of shop policies and over half of the shop premium pool.

### 6.3 Cumulative profit for Income (S$ m)

| Segment | Window | Mean (low to high) | Median | 1-in-10 bad run | 1-in-20 bad run | Runs ending in a loss |
|---|---|---|---|---|---|---|
| Hawkers: cooked food | 2027-2030 | 0.40 (0.13 to 0.71) | 0.52 | -0.32 | -0.62 | 22% |
| | 2027-2035 | 1.14 (0.43 to 1.86) | 1.29 | -0.26 | -0.73 | 14% |
| | 2027-2040 | 1.95 (0.79 to 3.08) | 2.06 | 0.12 | -0.44 | 9% |
| Hawkers: market stalls | 2027-2040 | 0.13 (0.04 to 0.29) | 0.14 | 0.00 | -0.05 | 10% |
| Neighbourhood shops | 2027-2040 | 0.30 (0.07 to 0.66) | 0.32 | 0.00 | -0.09 | 10% |
| Platform workers | 2027-2030 | 0.94 (0.11 to 2.39) | 1.31 | -0.75 | -1.44 | 22% |
| | 2027-2035 | 2.85 (0.48 to 6.34) | 3.20 | -0.63 | -1.81 | 14% |
| | 2027-2040 | 4.87 (0.97 to 10.38) | 5.14 | 0.32 | -1.01 | 9% |
| **All segments** | 2027-2030 | **1.38 (0.24 to 3.22)** | 1.91 | -1.08 | -2.14 | 22% |
| | 2027-2035 | **4.21 (0.95 to 8.72)** | 4.73 | -0.93 | -2.70 | 14% |
| | 2027-2040 | **7.25 (1.87 to 14.41)** | 7.67 | 0.43 | -1.55 | 9% |

Source: `data/processed/projection_cumulative.csv`. The premium pool over 2027 to 2040 is S$55.5 m at base uptake (S$14.3 m to S$110.6 m).

## 7. V3 climate overlay: projection, not used for pricing

### 7.1 What V3 publishes and how it is applied

| Input | Low (SSP1-2.6) | Medium (SSP2-4.5) | High (SSP5-8.5) | Source |
|---|---|---|---|---|
| Mean daily maximum WBGT, mid-century (2040-2059), against 30.3 C observed at the current 9 stations | 31.1 C (+0.8) | 31.3 C (+1.0) | 31.7 C (+1.4) | [S8] Table 5.4 |
| Days with WBGT of 33 C or more, mid-century, against 8 observed (cross-check only) | 75 | 87 | 113 | [S8] Table 5.6 |
| Very heavy daily rainfall (99.9th percentile), annual change, end-century (2080-2099) | about +33% | about +21% | about +26% | [S8] Figure 5.4, medians read from the chart |

V3 publishes no mid-century figure for extreme rain in the stakeholder report, so the end-century figure is ramped further out. V3 does not project haze. Haze stays at its observed frequency.

How each is applied, each change ramped in a straight line from 2020 (the middle of our 2015-2026 history) to the middle of V3's slice (2050 for heat, 2090 for rain):
- **Heat:** the WBGT shift is added to every work-hour NEA WBGT reading (S142 and S128 left out, as the price does), and the tariff's heat bands score the days again. The shift by 2040 is +0.53, +0.67 and +0.93 C. That gives 3.4, 4.5 and 7.4 times today's heat loss-days. At full mid-century (+0.8, +1.0, +1.4 C) it gives 6.2, 8.8 and 15.5 times. V3's own count of days at WBGT 33 C rises 9.4, 10.9 and 14.1 times, so the method is in line with V3.
- **Rain:** every place's wettest-hour reading is scaled up (by 2040: x1.094, x1.060, x1.074) and the engine scores the days again.
- The heat change is added on top of each year's loss-days, then the tier's yearly limit applies.

### 7.2 Effect in 2040, all segments, base uptake

| Climate | Pricing | Premium pool | Expected payouts | Profit, mean year | Profit, 1-in-10 bad year | Profit, 1-in-20 bad year |
|---|---|---|---|---|---|---|
| Observed 2015-2026 | today's price | S$4.63 m | S$2.67 m | S$0.61 m | -S$2.10 m | -S$3.31 m |
| SSP1-2.6 | today's price | S$4.63 m | S$3.95 m (+48%) | -S$0.67 m | -S$3.64 m | -S$4.59 m |
| SSP2-4.5 | today's price | S$4.63 m | S$4.25 m (+59%) | -S$0.97 m | -S$4.14 m | -S$4.89 m |
| SSP5-8.5 | today's price | S$4.63 m | S$5.47 m (+105%) | -S$2.19 m | -S$5.78 m | -S$6.10 m |
| SSP1-2.6 | yearly review | S$6.85 m (+48%) | S$3.95 m | S$0.90 m | -S$2.07 m | -S$3.02 m |
| SSP2-4.5 | yearly review | S$7.38 m (+59%) | S$4.25 m | S$0.97 m | -S$2.20 m | -S$2.95 m |
| SSP5-8.5 | yearly review | S$9.50 m (+105%) | S$5.47 m | S$1.25 m | -S$2.34 m | -S$2.66 m |

In 2030 the rise in expected payouts is smaller: +19%, +22% and +34%. Per segment and per year: `data/processed/projection_climate.csv`.

What this says:
- **At today's price, warming turns the mean year into a loss from 2031 (low and medium emissions) or 2028 (high emissions).** The 1-in-20 bad year deepens from -S$3.3 m to between -S$4.6 m and -S$6.1 m.
- **The yearly price review passes this on.** Prices are set on observed data every year, so hotter years enter the price as they are recorded. In the "yearly review" rows the price rises with the expected payout, the margin holds, and the bad-year loss stays near today's, because haze sets it.
- **The review is an upper bound on pass-through.** The real review averages all recorded years, so it lags the climate. And a price that doubles (SSP5-8.5) would push some tiers past the referral guardrail and lose customers. Neither effect is modelled.
- Per policy at full mid-century (2050, `data/processed/projection_climate_per_policy.csv`), cooked-food hawkers: expected payouts +104%, +142% and +251%; the worst replay year +41%, +57% and +97%. The tier limits cap the worst year, so it rises less than the average.

## 8. Assumptions

| # | Assumption | Value | Why | Effect if wrong |
|---|---|---|---|---|
| A1 | Uptake S-curves | Section 4 | No uptake data exists for this product | Policies scale up or down in proportion; profit per policy does not change |
| A2 | Tier mix | 30 / 40 / 20 / 10 | Middle tiers most bought | More Tier 3 and 4 raises the pool and the bad-year loss together |
| A3 | Shop trade mix | 40 / 30 / 15 / 10 / 5 (general goods, packaged food, cooked food, fresh produce, flowers) | No published HDB trade mix found | Shops are 5% of the 2040 pool; small |
| A4 | Market stalls priced as fresh produce | All 4,781 | No split of non-cooked stalls | Small segment |
| A5 | Market stalls weighted like cooked-food stalls across the 103 centres | Cooked-food stall counts | The current NEA dataset gives no market-stall count per centre | Small |
| A6 | Shops spread equally over the 81 postal sectors; platform workers over the 5 regions | Equal weights | No count per area | Area prices differ (Tier 2: general goods S$39.04 to S$67.66 a year by postal sector, platform work S$155.01 to S$233.42 by region), so another spread moves the average price |
| A7 | Shop and platform counts held flat | 15,200 and 71,600 | No multi-year series in the repo | A 1% yearly growth would add 16% (platform, from 2025) to 20% (shops, from 2022) by 2040 |
| A8 | Each replay year equally likely | 1 in 12 | 12 real years, two of them haze years | If haze is rarer than 2 in 12, the mean profit is higher |
| A9 | Prices held at today's level in real terms | No inflation | No cited inflation figure used | Money figures are in 2026 dollars |
| A10 | Income keeps the reinsurance part | 6% of premium before GST | No treaty exists yet | A treaty lowers both the mean profit and the bad-year loss |
| A11 | No lapses, no waiting period, policies counted as in force all year | | Simplicity | Lapses lower the pool |
| A12 | V3 changes ramped from 2020 | Straight line | V3 gives 20-year slices only | Our history already holds part of the baseline-to-2050 change, so this overstates the shift a little |
| A13 | Rain change at mid-century read from the end-century figure | Ramped to 2090 | No mid-century extreme-rain figure in the V3 stakeholder report | The rain effect is small next to heat |

## 9. What this does not show

- No sales data exists. Profit depends on the payout rule and the tariff, not on measured losses.
- The heat history is under two years (2025 to 2026). Heat dominates the V3 effect, so that part is the least certain.
- Flood and closure are priced at 0 days a year in the tariff and add nothing here.
- Uptake does not respond to price, payouts or a haze year. In practice a payout year may raise renewals and a quiet year may lower them ([S7]: SEWA, Caribbean LPP).

## 10. Files

- Script: `scripts/growth_projection.py` (`uv run scripts/growth_projection.py`, about 20 seconds).
- `data/processed/projection_unit_economics.csv`: per segment and tier (and the mix), premium, five parts, GST, payout per replay year 2015 to 2026, profit per policy.
- `data/processed/projection_segments.csv`: per segment, group and total, uptake case and year 2027 to 2040: market size, customers, market share, premium pool, payouts, profit mean, median, 1-in-10 and 1-in-20 bad year, share of Income's general insurance premium and underwriting profit.
- `data/processed/projection_cumulative.csv`: the same per window 2027-2030, 2027-2035, 2027-2040.
- `data/processed/projection_climate.csv`: V3 overlay, base uptake, per segment, scenario, pricing view and year, labelled "projection, not used for pricing".
- `data/processed/projection_climate_per_policy.csv`: change in the expected and worst-year payout per policy at V3's full mid-century shift.
- Figures: `docs/figures/projection_customers.png` (segment ladder), `docs/figures/projection_profit_fan.png` (profit range per segment), `docs/figures/projection_v3_overlay.png` (V3 overlay).

## Sources

- [S1] NEA, Hawker Centres dataset (GeoJSON), data.gov.sg `d_4a086da0a5553be1d89383cd90d07ecd`, read 15 Nov 2026. Field `NUMBER_OF_COOKED_FOOD_STALLS` by `STATUS`. The 5,837 also matches `data/processed/map_static.json`.
- [S2] NEA, "List of Government Markets Hawker Centres", data.gov.sg `d_68a42f09f350881996d83f9cd73ab02f`, coverage 2016, read 15 Nov 2026: 107 centres, 14,058 stalls, 6,121 cooked food, 7,937 market produce.
- [S3] SingStat Table Builder M890531, "Licensed Food Establishments (End Of Period), Annual", source SFA, series "National Environment Agency Hawker Stalls", last updated 28 May 2026, read 15 Nov 2026.
- [S4] HDB press release, 19 Nov 2022, "Supporting Heartland Shops" (about 15,200 shops), as cited in `docs/notes/distribution-proposal-2026-11-15.md` [S18], search snippet only.
- [S5] MOM, Labour Force in Singapore 2025, paragraph 2.36, as cited in `docs/notes/distribution-proposal-2026-11-15.md` [S7].
- [S6] `docs/notes/expected-impact-2026-11-15.md`, section A (year-1 cases, Assumptions A1 to A5, MSE reply of 4 Aug 2026 on stallholder insurance).
- [S7] `docs/problem-statements.md`, section 1, "Overseas" (SEWA, ZhongAn, PayPay, KB Insurance, Caribbean LPP); `docs/notes/parametric-sales-research-2026-11-15.md`.
- [S8] MSS and CCRS, Singapore's Third National Climate Change Study (V3), Stakeholder Report, Mar 2024: https://www.nea.gov.sg/docs/default-source/envision/cisr/v3-stakeholder-report.pdf . Tables 5.4 and 5.6 (mid-century 2040-2059 against 1995-2014), Figure 5.4 (end-century 2080-2099).
- [S9] MAS, General Insurance Returns 2021 to 2025, Singapore Insurance Fund, Income (NTUC Income for 2021): Table G5 Part I underwriting profit S$23.7 m, 48.8 m, 68.8 m, 74.3 m and 40.9 m (mean S$51.3 m); Table G1 gross premiums 2025 S$529.4 m. Raw files in `data/raw/mas_insurance/` (not committed). See also `docs/resources/income-insurance-fy2025-financials.md`.
