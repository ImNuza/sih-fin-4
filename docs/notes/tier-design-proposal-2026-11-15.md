# Tier, premium and payout design: proposal (15 Nov 2026)

Status: accepted. On 15 Nov the team lead accepted the recommended answers in section 6: a 30-day limit for every tier; the S142 and S128 heat stations on hold, with heat read at the next nearest station until NEA confirms them; running costs split 10% management and 15% distribution until Income gives its figure. It was built on branch `production-ready-pricing`. Sections 1 to 8 are the pre-build estimates and are left as written. Section 9 says what was built, with the final numbers.

Inputs:
- Final team decisions: `docs/notes/notion-decisions-sweep-2026-11-15.md` (Notion sweep, 15 Nov).
- Market evidence: `docs/notes/parametric-sales-research-2026-11-15.md`.
- Numbers: a replay of every recorded day (Mar 2016 to 14 Nov 2026) through `api/readings.py` and the live tariff, at all 103 hawker centres, plus the NEA historical 24-hour PSI (Apr 2014 on) so that the 2015 haze is in the sample. The first scripts were not committed; the production version goes into `scripts/` (section 7).
- Loads are the decided ones: 15% uncertainty, 10% rare event, 25% running costs, 9% GST. Payouts are 60% of premium before GST.

All figures are the median over the 103 centres unless a line says otherwise. "Loss-days" means full-payout days: a day at 24% loss is 0.24 loss-days.

## 1. What is wrong today

1. **Tier 1 can cost more than it can ever pay.** Today's price is `min(expected loss-days, cap) x daily amount x loads`. When the expected loss-days are near the cap, the loads push the yearly premium above the yearly limit. Tier 1 costs at least its S$200 limit at 59 of 103 centres (checklist item 39). Median "most it can pay / what you pay" today: Tier 1 1.0x, Tier 2 1.5x, Tier 3 1.9x, Tier 4 2.9x.
2. **The limits bind in exactly the years the cover is for.** In 2026, 9% to 19% of stalls reached 15 loss-days (Notion, tier-days check). A 2015-type haze year adds about 11 haze loss-days for cooked food (45 days at PSI 101+, 6 at 201+). With a 10 or 15 day limit, the stall stops being paid in the middle of the haze.
3. **The price and the payout read the weather differently.** The price pools the 3 nearest gauges; the payout reads the middle of the 3. The price is 13% to 22% above what the trigger pays for rain (Notion, two pages). The haze price uses Mar 2016 on, so it leaves out the 2015 haze and is too low for the catastrophe year.
4. **One heat station drives 28 centres out of line.** Station S142 recorded 120 heat-trigger days in 2026 (29 in 2025). The median station recorded about 7. S128 recorded 50. The centres next to them price 11 to 15 heat loss-days a year, against about 1 elsewhere. Either the sensor is badly placed or that area is much hotter. NEA must confirm.

## 2. What a fair price can and cannot give

- At a 60% payout target, any product pays back on average about 55% of what the customer pays (60% before GST, divided by 1.09). "Pay S$1, get S$5 back" is not true on average for any insurance. Nobody in the team decided it (Notion sweep: "5x" not found).
- What can be large is the **most it can pay**: the yearly limit divided by the yearly premium. A limit that sits above the worst year on record costs almost nothing extra, because the price already pays for every year below it.
- What sells, from the evidence (section 5): frequent visible payouts, a clear bad-year story, a price per day, and a limit that never runs out when it matters.

## 3. Recommended design

| # | Change | Why |
|---|---|---|
| R1 | **One yearly limit for every tier: 30 full-payout days.** Money limit = 30 x the daily amount: S$600 / 1,200 / 2,100 / 3,000. | The worst year on record is under 20 loss-days for cooked food at all but the S142/S128 centres. The limit then never runs out in a haze year. It adds about 2% to the price (6.17 to 6.29 loss-days). It is one number to explain: "up to 30 bad days a year". |
| R2 | **Price on the payout rule.** Expected payout = the average over the replay years of `min(that year's loss-days, the limit)`, read through `api/readings.py`, the same rule as every payout. Haze uses the PSI history from Apr 2014, so 2015 is one of the years. Heat uses its own history (Jan 2025 on) with the existing credibility blend. | One price, one reading rule, as AGENTS.md says. Removes the 13-22% rain gap. Prices the 2015 haze. The price can never pass the limit. |
| R3 | **Guardrail: no tier is offered where its yearly premium is more than half its yearly limit** (below 2x). The quote then shows "refer to underwriter" for that tier. | Stops a customer from buying cover that cannot pay back its price even in the worst year. Today it would refer the S142/S128 centres only. |
| R4 | **Show the premium in Income's five parts.** Of every S$100 before GST: expected payouts 60, reinsurance (haze) 6, management expenses 10, selling and distribution 15, expected profit 9. Then GST. | Income asked for these five parts (Q&A). Same total as today: 15% uncertainty becomes the profit and risk margin, 10% rare event becomes the reinsurance, 25% running costs splits 10 + 15. The 10 / 15 split is ours until Income gives its figure. |
| R5 | **Four proof numbers on every quote, all from that customer's own place.** See section 4. | Honest "wow": real money from real days, not a promise. MAS fair dealing asks for clear benefit and price. |
| R6 | **Keep the payout rule.** Keep partial payouts from the first unhealthy day. Do not add a minimum loss before paying. | A 24% floor halves the payout days (20 to 9 a year) and a 30% floor removes almost all haze payouts (haze share 18% to 3%). Haze is the headline peril. |

Not changed: the four daily amounts, the triggers and bands, the loads, the 30-day wait, the 12/24-month term, the rent hint.

## 4. What each customer sees (recommended design)

Median centre, 30-day limit, haze priced with 2015.

### Hawker, cooked food

| Tier | Weekly | Per day | Most it pays a year | That is | A typical year paid | 2026 haze year paid | A 2015-type year paid | Premium a year |
|---|---|---|---|---|---|---|---|---|
| 1 (S$20/day) | S$4.40 | S$0.63 | S$600 | 2.6x | S$93 | S$213 | S$320 | S$229 |
| 2 (S$40/day) | S$8.80 | S$1.25 | S$1,200 | 2.6x | S$187 | S$425 | S$640 | S$457 |
| 3 (S$70/day) | S$15.39 | S$2.19 | S$2,100 | 2.6x | S$327 | S$744 | S$1,119 | S$801 |
| 4 (S$100/day) | S$21.99 | S$3.13 | S$3,000 | 2.6x | S$467 | S$1,063 | S$1,599 | S$1,144 |

- Every centre was paid in every year from 2017 to 2026 (100% of centre-years).
- Payout days: about 18 a year in 2017-2025, 47 in 2026.
- Today's design at Tier 2: S$7.95 a week, most it pays S$600 (1.5x). The new Tier 2 costs S$0.85 a week more and can pay twice as much.

### Other customers, Tier 2 (S$40 a full day)

| Customer | Weekly | Most it pays / premium | Typical year paid | 2026 paid | Premium a year |
|---|---|---|---|---|---|
| Fresh produce stall | S$3.06 | 7.5x | S$65 | S$149 | S$159 |
| Platform worker | S$3.70 | 6.2x | S$78 | S$179 | S$192 |
| Shop, packaged food | S$0.98 | 23.4x | S$21 | S$48 | S$51 |

Shops and platform workers here are read at hawker-centre points. The live quote reads their postcode area or region.

### The proof numbers on the quote (R5)

For a Tier 2 hawker at a median centre, the quote says:

1. "S$1.25 a day. Up to S$1,200 a year: 2.6 times what you pay."
2. "A stall here would have been paid in each of the last 10 years, on about 18 days a year."
3. "In the 2026 haze, a stall here would have received S$425."
4. "In a haze like 2015, it pays about S$640. It does not run out before 30 bad days."

Each number comes from the replay at that place. The quote also keeps "In an average year about 55% of what you pay comes back as payouts" (the brief asks for honest value).

## 5. Market evidence

See section 8. In short: the recommended design lands inside every evidence-based target the research found (premium 33-45% of the limit, 55-70% loss ratio, 65-80% chance of a payout a year, which here is 100%).

## 6. Decisions for the team

1. **Yearly limit**: 30 days for all tiers (recommended), or 50 days (hawker multiple 4.4x; it doubles the most Income can owe per policy for a marketing number that no recorded year reaches).
2. **S142 and S128 heat stations**: until NEA confirms them, read heat at the next nearest station for both price and payout (recommended), or keep them and refer those centres to the underwriter.
3. **The 10 / 15 split** of running costs into management and distribution, until Income gives its figure.

## 7. Code changes after the yes

- `scripts/build_place_years.py` (new): for every hawker centre, postcode area and region, each product's loss-days per year through `api/readings.py`, haze from Apr 2014. Writes `data/processed/place_year_losses.csv`.
- `api/calculator.py`: `tier_quotes` prices `mean(min(year loss-days, limit))` from those years; the guardrail flag; the five-part build-up.
- `api/default_tariff.json`: `max_paid_days_per_year` 30 on every tier; the five-part pricing keys.
- `api/main.py`, `api/site/buy.js`: the proof numbers on the quote.
- `scripts/burn_analysis.py`: the same yearly limit and the same price, so the replay and the price agree.
- Tests: price never above half the limit; price equals the replay average to the cent at a fixed centre; a 2015-type year stays under the limit at the median centre.

## 8. Research summary

Full sources in `docs/notes/parametric-sales-research-2026-11-15.md`. How the recommended design compares:

| Evidence | Source | Recommended design |
|---|---|---|
| SEWA heat cover 2024: premium 36% of the most it pays (2.75x). 93% of members paid; a zero-payout year (2023) hurt trust. | ILO report, 2026 | Hawker premium is 38% of the limit (2.6x). Paid in 10 of 10 years at every centre. |
| Experts call a 30-40% claims ratio a rough minimum; one practitioner target is 45-70%. The "60-70% = good value" claim is not confirmed. | Microinsurance Network, "Claims ratios: how low is too low?"; MicroEnsure comment, 2017 (weak) | 60% before GST by design, about 55% of what the customer pays. |
| Payout recipients were 9-22% more likely to buy again. | Stein, World Bank WPS 7035, 2014 | About 18 payout days a year, so almost every customer sees a payout in the first months. |
| A rebate frame raised willingness to pay (151% to 165% of the fair price). | Carter, UC Davis BASIS, 2024 (Burkina Faso farmers) | Not needed: no centre had a year with no payout. |
| Income Stallholder Insurance: S$109-262 a year, "from $0.30 a day". Grab Partner Cover: S$9-29.20 a month. Both have 3 tiers. | Income and Grab product pages | Daily price on the quote (S$0.63 to S$3.13 a day for hawkers). The team decided 4 tiers (14 Nov); the evidence does not argue against it. |
| MAS Fair Dealing (FSG-G04, 30 May 2024): no unrealistic expectations. | MAS | Every proof number is a replay at the customer's place. No "5x back" claim. |

Risk to state in the pitch: hawker Tier 2 at S$457 a year is above Income's Stallholder Insurance (S$109-262). Tier 1 (S$4.40 a week) is the "few dollars a week" entry. The SmartBiz 360 add-on can share the selling cost with the main policy.

## 9. What was built

The build changed some answers above. The final choices:

- **Yearly limits per tier:** Tier 1 35 days, Tier 2 35, Tier 3 40, Tier 4 45 (S$700 / 1,400 / 2,800 / 4,500). Tier 1 is 35, not 30, because at 30 days 3 centres in Jurong crossed the half-limit guardrail (R3) on the final engine (4 in the first simulation, before the haze source fix).
- **Shares per tier:** each tier has its own five shares of the premium before GST (`premium_shares` in `api/default_tariff.json`). A policy's fixed costs do not grow with its daily amount, so a bigger tier spends a smaller share on costs.

  | Tier | Expected payouts | Reinsurance | Management | Distribution | Profit |
  |---|---|---|---|---|---|
  | 1 | 55% | 6% | 12% | 17% | 10% |
  | 2 | 60% | 6% | 10% | 15% | 9% |
  | 3 | 65% | 6% | 8% | 13% | 8% |
  | 4 | 70% | 6% | 7% | 10% | 7% |

- **Haze source:** the NEA historical 24-hour PSI file is the main source to 1 Oct 2026. The real-time feed fills the days after it and any day the history lacks.
- **Credibility removed:** the heat credibility blend in R2 was dropped. The price reads the same stations as the payout, with no blending with the region.
- **Readings file:** `scripts/build_place_years.py` writes `data/processed/place_day_readings.npz`, every priced place's readings on every recorded day (not `place_year_losses.csv` as section 7 planned).
- **On every quote:** `best_value` marks the tier sold directly with the highest cover multiple; `cost_per_sgd_of_daily_cover` is the yearly premium over the daily amount. A referred tier carries a `referral_reason`, and `POST /api/policies` answers 202.

Final numbers, cooked food, at Maxwell Food Centre:

| Tier | Weekly | Most it pays / premium |
|---|---|---|
| 1 (S$20/day) | S$4.97 | 2.7x |
| 2 (S$40/day) | S$9.11 | 3.0x |
| 3 (S$70/day) | S$14.72 | 3.7x |
| 4 (S$100/day) | S$19.53 | 4.4x, best value |

Median of the 103 centres, Tier 2: S$8.79 a week, 3.1x. No centre has a tier referred to the underwriter.
