# Value for money: every tier against saving the premium instead

Date: 16 Nov 2026. Branch `value-for-money-table`, from `production-ready-pricing`.
Todo: "[FROM INCOME Q&A] Value-for-money table" (P0, Deval).
Script: `uv run scripts/value_for_money.py`. Tables: `data/processed/value_for_money*.csv`.
Every number here comes from those tables, which the pricing engine (`api/calculator.py`, `api/default_tariff.json`) and the model history (`api/model_history.py`) produce. Nothing is typed in by hand.

## 1. Short answer

- Sky's rule (15 Nov) is in the code: a tier is not offered where its yearly premium is at or above the most it can pay in a year. The tariff's stricter share (premium at most 50% of that) also hides a tier now, instead of sending it to an underwriter.
- Neither rule hides anything today. The highest premium anywhere is 47% of the yearly limit (cooked food Tier 1 at Jurong West Street 52 Blk 505). Only a lockdown can reach the 45-day limit, so a rule on premium against the limit cannot catch the mentors' worry.
- The mentors' worry is real. On weather alone, a customer who saved the premium instead comes out ahead at every place we checked. In the replay years 2017-2026 no hawker centre had a year in which cooked food Tier 1, 2 or 3 paid back more than its premium.
- What the cover gives that savings cannot is the shock: a 40-day lockdown pays 1.9 to 9.7 years of premium at the four places in section 3, and a 2015-type haze year pays more than a year of premium on most cooked-food tiers.
- We measured a self-insure test (section 2). It fails cooked food Tier 1 at 77 of 103 centres and almost every tier of every other product. That is a design question for the team, not something to switch on quietly (section 6).

## 2. The self-insure test

The mentors asked the question in money terms:

- An SME founder shown about S$10 a week, S$265 back in an average year and S$432 in 2026 said: "I can self-insure by not paying that." (mentor note on the todo)
- Income's product lead: "Pay a premium of say $10 and my payout is $20, would I see value, or would I rather save $10 and self-insure?" (mentor note on the todo)

So we compare two customers at the same place. One buys the tier every year. The other puts the same premium aside every year and pays themself, from that pot, what the tier would have paid ("saved the premium instead"). Each year's payout is the tier's own: that year's loss-days up to the 45-day limit, times the daily amount.

We measure, per tier and place:

1. The premium against the most the tier can pay in a year (Sky's floor and the tariff's 50% share).
2. Over the 46 model years 1980-2025 and the 10 replay years 2017-2026: total premiums, total payouts, what the saver keeps, the lowest point of the saver's pot, from how many start years the pot would have run dry, how many years paid more than the premium, the 1-in-10 year and the worst year.
3. Two shocks with a fresh pot, which holds one premium after a year: a 40-day lockdown, and a 2015-type haze year. The 2015-type year is weather only: 2015's haze plus an average year of rain and heat.

**Pass rule.** A tier passes at a place when it is offered (rule 1) and a 2015-type weather year pays back more than one year's premium.

Why this line:

- One year of saving is one premium. If the worst weather year on record pays less than that, a customer who saved instead could pay themself for it from a single year's savings. The cover then adds nothing for weather that a savings pot could not.
- 2015 is the worst haze year on record: 46 region-days above PSI 100 and a peak of 322 (`api/model_history.py`). It is the only year from Apr 2014 to Nov 2026 with 40 or more unhealthy-haze days in a region (`AGENTS.md`, severe haze payout).
- The product lead's "$10 to get $20" is the cover multiple. Our 50% share is that line exactly: the most a tier pays must be at least twice its premium. The research note points the same way: "Do not go above about 50%. The buyer sees a cap that is too small" (`docs/notes/parametric-sales-research-2026-11-15.md`, section 6a; SEWA's 2024 heat cover sat at 36%). We keep 50% as the stricter share.
- We did not set the weather year at twice the premium. No tier at any place reaches that from weather alone, so it would hide the whole product.

## 3. The table

Cooked food at Maxwell, the median centre (by cooked food Tier 1 price) and the most expensive centre, and packaged food at a shop at postcode 380123. "Saved instead" is what the saver keeps at the end: total premiums less total payouts, weather only. "Paid in 2026" runs to the last day of data.

### Maxwell Food Centre (Kim Hua Market), cooked food

| | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Monthly | S$49.25 | S$252 | S$750 | S$1,498 |
| Weekly | S$11.37 | S$58.05 | S$173 | S$346 |
| Yearly | S$591 | S$3,018 | S$9,002 | S$17,978 |
| Expected payout a year | S$298 | S$1,661 | S$5,368 | S$11,545 |
| Typical year paid | S$103 | S$576 | S$1,860 | S$4,000 |
| Paid in 2026 | S$378 | S$2,106 | S$6,803 | S$14,631 |
| Most it can pay a year | S$1,575 | S$8,775 | S$28,350 | S$60,975 |
| 40-day lockdown | S$1,400 | S$7,800 | S$25,200 | S$54,200 |
| 2015-type year | S$578 | S$3,221 | S$10,407 | S$22,384 |
| Saved instead, 1980-2025 | S$16,718 | S$80,520 | S$225,635 | S$421,680 |
| Saved instead, 2017-2026 | S$4,402 | S$21,784 | S$62,877 | S$121,406 |
| Years paid more than premium, 1980-2025 | 2 | 4 | 4 | 7 |
| 1-in-10 year, 1980-2025 | S$483 | S$2,690 | S$8,692 | S$18,695 |
| Worst year, 1980-2025 | S$666 | S$3,711 | S$11,990 | S$25,788 |
| Premium / most it can pay | 38% | 34% | 32% | 30% |
| Offered (tariff rule) | yes | yes | yes | yes |
| Self-insure test | fail | pass | pass | pass |
| Self-insure test at 5% commission | pass | pass | pass | pass |

### Redhill Lane Blk 85 (Redhill Food Centre), the median centre, cooked food

| | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Monthly | S$47.91 | S$245 | S$730 | S$1,457 |
| Weekly | S$11.06 | S$56.47 | S$168 | S$336 |
| Yearly | S$575 | S$2,936 | S$8,756 | S$17,488 |
| Expected payout a year | S$290 | S$1,617 | S$5,223 | S$11,233 |
| Typical year paid | S$128 | S$712 | S$2,300 | S$4,946 |
| Paid in 2026 | S$363 | S$2,022 | S$6,533 | S$14,051 |
| Most it can pay a year | S$1,575 | S$8,775 | S$28,350 | S$60,975 |
| 40-day lockdown | S$1,400 | S$7,800 | S$25,200 | S$54,200 |
| 2015-type year | S$570 | S$3,175 | S$10,258 | S$22,064 |
| Saved instead, 1980-2025 | S$17,104 | S$83,018 | S$234,646 | S$442,794 |
| Saved instead, 2017-2026 | S$4,226 | S$20,876 | S$60,147 | S$115,912 |
| Years paid more than premium, 1980-2025 | 0 | 0 | 1 | 1 |
| 1-in-10 year, 1980-2025 | S$348 | S$1,938 | S$6,260 | S$13,463 |
| Worst year, 1980-2025 | S$510 | S$2,839 | S$9,172 | S$19,726 |
| Premium / most it can pay | 36% | 34% | 31% | 29% |
| Offered (tariff rule) | yes | yes | yes | yes |
| Self-insure test | fail | pass | pass | pass |
| Self-insure test at 5% commission | pass | pass | pass | pass |

### Jurong West Street 52 Blk 505, the most expensive centre, cooked food

| | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Monthly | S$61.37 | S$313 | S$935 | S$1,867 |
| Weekly | S$14.16 | S$72.33 | S$216 | S$431 |
| Yearly | S$736 | S$3,761 | S$11,216 | S$22,401 |
| Expected payout a year | S$372 | S$2,071 | S$6,691 | S$14,390 |
| Typical year paid | S$175 | S$975 | S$3,150 | S$6,775 |
| Paid in 2026 | S$405 | S$2,258 | S$7,297 | S$15,694 |
| Most it can pay a year | S$1,575 | S$8,775 | S$28,350 | S$60,975 |
| 40-day lockdown | S$1,400 | S$7,800 | S$25,200 | S$54,200 |
| 2015-type year | S$663 | S$3,694 | S$11,934 | S$25,667 |
| Saved instead, 1980-2025 | S$24,859 | S$122,776 | S$353,665 | S$681,396 |
| Saved instead, 2017-2026 | S$5,396 | S$26,643 | S$76,731 | S$147,800 |
| Years paid more than premium, 1980-2025 | 0 | 0 | 0 | 0 |
| 1-in-10 year, 1980-2025 | S$294 | S$1,635 | S$5,283 | S$11,363 |
| Worst year, 1980-2025 | S$512 | S$2,851 | S$9,211 | S$19,810 |
| Premium / most it can pay | 47% | 43% | 40% | 37% |
| Offered (tariff rule) | yes | yes | yes | yes |
| Self-insure test | fail | fail | pass | pass |
| Self-insure test at 5% commission | pass | pass | pass | pass |

### A shop at postcode 380123 (postal sector 38), packaged food and drinks

The model history for the shop is its nearest centre's, Sims Place Blk 49 (Sims Vista Market and Food Centre), as `/api/model/history` reads a point.

| | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Monthly | S$15.32 | S$78.23 | S$233 | S$466 |
| Weekly | S$3.53 | S$18.05 | S$53.84 | S$108 |
| Yearly | S$184 | S$939 | S$2,799 | S$5,591 |
| Expected payout a year | S$92.75 | S$517 | S$1,670 | S$3,591 |
| Typical year paid | S$11.63 | S$64.81 | S$209 | S$450 |
| Paid in 2026 | S$43.87 | S$244 | S$789 | S$1,698 |
| Most it can pay a year | S$1,575 | S$8,775 | S$28,350 | S$60,975 |
| 40-day lockdown | S$1,400 | S$7,800 | S$25,200 | S$54,200 |
| 2015-type year | S$56.54 | S$315 | S$1,018 | S$2,189 |
| Saved instead, 1980-2025 | S$7,691 | S$38,923 | S$115,021 | S$227,603 |
| Saved instead, 2017-2026 | S$1,693 | S$8,579 | S$25,383 | S$50,291 |
| Years paid more than premium, 1980-2025 | 0 | 0 | 0 | 0 |
| 1-in-10 year, 1980-2025 | S$26.61 | S$148 | S$479 | S$1,030 |
| Worst year, 1980-2025 | S$53.29 | S$297 | S$959 | S$2,063 |
| Premium / most it can pay | 12% | 11% | 10% | 9% |
| Offered (tariff rule) | yes | yes | yes | yes |
| Self-insure test | fail | fail | fail | fail |
| Self-insure test at 5% commission | fail | fail | fail | fail |

What the rows say:

- In a typical year the cover pays a fraction of what it costs: S$103 for S$591 at Maxwell Tier 1. That is how insurance works, and the product says it plainly ("Priced to return about 50 cents of every S$1 on average" on Tier 1).
- In the replay years the saver's pot never ran dry at any of the four places, from any start year. In the model years it ran dry at Maxwell from 2 of 46 start years on Tier 1 (2015 and 2016) up to 9 on Tier 4, and at Redhill from 1 start year on Tiers 3 and 4. It never ran dry at Jurong West or at the shop.
- The lockdown is the shock savings cannot meet. At Maxwell, Tier 1's S$1,400 for 40 days is 2.4 years of premium; at the shop, 7.6 years.
- The mentors' scenario "if there is haze all next year": at PSI 101 every day, cooked-food Tier 1 pays its full S$1,575, 2.7 times its premium at Maxwell. Packaged food loses less per hazy day, so the shop's Tier 1 pays S$345, 1.9 times its S$184 premium (`haze_all_year_sgd` in `value_for_money.csv`).

## 4. Across every place

3,680 tier and place pairs: 103 hawker centres and 81 postcode areas (postal sectors), each for the 5 products the pilot sells, each with 4 tiers (`value_for_money_places.csv`, `value_for_money_tests.csv`).

- **Offered by the tariff rule:** all 3,680. No centre loses a tier.
- **Replay 2017-2026:** for cooked food at the 103 centres, the worst year paid at most 0.85 of the premium on Tier 1, 0.93 on Tier 2 and 1.00 on Tier 3. Tier 4 paid more than its premium in one year at 9 centres (up to 1.08 times). The median worst year was 0.65 of the premium on Tier 1 and 0.83 on Tier 4.
- **Self-insure test passes:** 541 of 3,680 pairs.

| Cooked food | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Centres passing (of 103) | 26 | 81 | 84 | 103 |
| Postcode areas passing (of 81) | 13 | 67 | 78 | 81 |
| Centres passing at 5% commission | 96 | 103 | 103 | 103 |

Of the other products only flowers pass anywhere: Tier 4 at 5 centres and 3 postcode areas. Fresh produce, packaged food and general goods pass nowhere.

**Why the other products fail.** The closure order is priced at 2 full days a year for every product, because a closure stops all sales. Weather is scaled down by the product: packaged food loses little on a hazy day. So most of a shop's premium pays for the lockdown. The closure's share of the expected payout is 67% to 80% for packaged food and general goods, 40% to 56% for fresh produce, 34% to 49% for flowers, and a median of 24% for cooked food (`closure_share_of_expected_payout`). For a packaged-food shop Payung is mostly lockdown cover with a little weather on top.

**Which centres would lose a tier under a stricter share** (`value_for_money_shares.csv`). Only cooked food is ever hidden:

| Share of the yearly limit | Pairs hidden | Centres losing a tier | Postcode areas losing a tier |
|---|---|---|---|
| 100% (Sky's floor) | 0 | 0 | 0 |
| 50% (the tariff now) | 0 | 0 | 0 |
| 45% | 6 | 3 | 3 |
| 40% | 38 | 13 | 19 |
| 35% | 188 | 64 | 50 |

At 45% the three centres are Jurong West Street 52 Blk 505, Jurong East Ave 1 Blk 347 (Yuhua Market and Hawker Centre) and Jurong East Street 24 Blk 254 (Yuhua Village Market and Food Centre), with postal sectors 62, 63 and 64. Each loses Tier 1, its cheapest tier. The reason is the weather history: 4.22 to 4.35 rain loss-days a year against 3.39 at the median centre, 2.19 to 2.39 heat loss-days against 1.00, and the west region's haze at 1.95 against 1.78. All three are mid-rent centres. A stricter share would take the cheapest tier away from the stalls with the worst weather. The PS watch-point (MAS FEAT: do not price out those who most need cover) argues against it, so we keep 50%.

## 5. What changed in the code

- `calculator.not_offered_reason`: a tier is not offered where its premium is at or above its yearly limit, or (for a tier with premium shares) above `refer_above_limit_share` of it. The share keeps its name so saved tariffs load. A tier without shares, from an older tariff, keeps only the floor.
- `TierQuote` gains `offered` and `not_offered_reason` in place of `sold_directly`. The reason names the place's weather history and says the price never comes from the business or its owner.
- `POST /api/buy` refuses a tier not offered with 409 before saving anything. `POST /api/policies` refuses it with 409. No price referral goes to the underwriter any more. Applications referred for price before this stay in the queue and are decided as before. A past decline still goes to the underwriter.
- The buy page and the dashboard's choose-cover show only the tiers offered and say why any other is not. The atlas writes "Not offered here" in the tier table, explains it under the table, leaves the centre out of a circle's payout and premium pool, and its legend says "Not offered". A circle's card now shows the portfolio tier's monthly price per stall. No CSS or layout change.
- The assistant never suggests a tier not offered, and says why when asked.
- Bug fixed: the quote's 2015-type estimate added the 2 assumed closure days, so "We estimate a year like 2015 would pay about S$X" counted a lockdown that did not happen. It is now weather only. The lockdown keeps its own line.
- `uv run pytest -q`: 500 passed.

## 6. Decision needed

The tariff rule (Sky's floor and the 50% share) is met everywhere. The self-insure test is not. The options, with what each does to the table:

1. **Enforce the self-insure test by hiding.** Hides cooked food Tier 1 at 77 centres and nearly every tier of fresh produce, flowers, packaged food and general goods. That prices out most shops. Not recommended.
2. **Lower the selling cost to the 5% commission Income quoted** (against a usual 15%; `docs/notes/distribution-proposal-2026-11-15.md` [S27]), and pass the saving to payouts: payout shares 67%, 70%, 73% and 75%. Cooked food then passes at every centre on Tiers 2 to 4, and on Tier 1 at 96 of 103. The 7 that still fail on Tier 1 are in the central PSI region: six Ang Mo Kio centres (Ave 10 Blk 409, Blk 453A and Blk 527; Ave 4 Blk 160/162 and Blk 628; Ave 1 Blk 341) and Sembawang Hills Food Centre. Their 2015-type year pays 0.81 to 0.82 of today's premium. The 2015 haze reached 40 unhealthy days in the west, north and south regions, not the central one (`AGENTS.md`). This changes the team lead's final shares, so it is not in the tariff.
3. **Price the closure by product, or sell it as its own line.** Today a packaged-food shop pays mostly for lockdown cover. Scaling the closure by the product, or showing it as a separate price, would make the weather part honest for shops. A design call.
4. **Keep selling, and say what the cover is for.** The cover's value is the shock: a lockdown, a 2015-type year, a year at the limit. Show the saver comparison on the buy page next to the proof lines.

Our recommendation: 2 for cooked food, 3 for the other products, and 4 in every case. Keep the 50% share; do not go stricter.

## 7. Affordability line

The landing page said "From about S$3.60 a week" for every business. That is about the middle price of a packaged-food or general-goods shop, not a floor, and a cooked-food stall pays about three times as much. Tier 1, the cheapest tier at every place (`value_for_money_prices.csv`):

| Business | Places | Monthly, middle | Monthly, range | Weekly, middle | Weekly, range |
|---|---|---|---|---|---|
| Hawker, cooked food | 103 centres | S$47.91 | S$37.62 to S$61.37 | S$11.06 | S$8.68 to S$14.16 |
| Hawker, fresh produce | 103 centres | S$24.21 | S$20.65 to S$28.91 | S$5.59 | S$4.77 to S$6.67 |
| Hawker, flowers | 103 centres | S$28.08 | S$23.43 to S$34.21 | S$6.48 | S$5.41 to S$7.90 |
| Hawker, packaged food | 103 centres | S$15.63 | S$14.48 to S$17.14 | S$3.61 | S$3.34 to S$3.96 |
| Hawker, general goods | 103 centres | S$15.48 | S$14.38 to S$16.95 | S$3.57 | S$3.32 to S$3.91 |
| Shop, packaged food | 81 areas | S$15.66 | S$14.78 to S$17.14 | S$3.61 | S$3.41 to S$3.95 |
| Shop, general goods | 81 areas | S$15.51 | S$14.67 to S$16.94 | S$3.58 | S$3.38 to S$3.91 |

The lowest prices are at Changi Village Blk 2 and 3. The landing page now says: "Tier 1 at a middle-priced place: about S$16 a month (S$3.60 a week) for packaged food or general goods, S$24 to S$28 a month for fresh produce or flowers, and S$48 a month (S$11 a week) for cooked food."

Older notes still quote "Tier 1 from S$2.85 a week", from the tiers before the final numbers: `feat-fairness-check-2026-11-15.md`, `market-competitiveness-2026-11-15.md` and `notion-decisions-sweep-2026-11-15.md`. They are dated records and were left as written. Use the table above instead.

## 8. Deck pictures

From the risk atlas (`/map/`), a haze day at PSI 150 in the day simulator, saved in `docs/figures/deck/`:

- `atlas_three_areas_tier_1.png`: three what-if circles. Tier 1 cooked food per stall: S$37.62 a month at Changi Village Blk 2 and 3 (cheapest centre), S$47.91 at Redhill (median), S$61.37 at Jurong West Street 52 Blk 505 (most expensive).
- `atlas_three_areas_tier_2.png`: the same circles at Tier 2: S$192.12, S$244.68 and S$313.42 a month.
- `atlas_maxwell_tier_1_cooked_food.png`, `atlas_maxwell_tier_1_fresh_produce.png`, `atlas_maxwell_tier_1_packaged_food.png`: one circle at Maxwell, Tier 1, three products: S$49.25, S$24.69 and S$15.78 a month. The same haze day pays S$8.40, S$2.92 and S$0.94 per stall.
- `atlas_not_offered_at_share_0_45_jurong_west.png`: what a hidden tier looks like on the atlas, with the share set to 45% on a scratch database. Tier 1 reads "Not offered here" at Jurong West Street 52 Blk 505, with the reason. At the real 50% share nothing is hidden.

## 9. Limits

- The model history has no haze before Apr 2014, so its 46 years under-count haze. Maxwell Tier 1 paid an average of S$162 a year before 2014 and S$414 from 2014. The saver's lead over 1980-2025 is larger than it would be with haze.
- Neither history holds a closure order. The price assumes one 40-day lockdown every 20 years. The table shows it as a shock, not inside the yearly payouts.
- 2026 runs to the last day of data, so its premium is a full year against part of a year's payouts.
- The 5% commission is Income's spoken figure, not a written quote.

## 10. Draft Notion comment for the todo row (not posted)

Built on branch value-for-money-table (not pushed). Note: docs/notes/value-for-money-2026-11-16.md. Script: scripts/value_for_money.py.

1. Sky's rule is in the code. A tier is not offered where its premium reaches the most it can pay in a year, or passes 50% of it. The quote says why in plain words (the place's weather history, never the customer). Buy and dashboard refuse it with 409; the buy page, dashboard and atlas hide it. No more underwriter referral for price.
2. Today no tier is hidden anywhere: the highest premium is 47% of the limit (cooked food Tier 1, Jurong West St 52). A 45% share would take Tier 1 from 3 Jurong centres, the ones with the worst weather, so we keep 50%.
3. The self-insure test (a 2015-type weather year must pay back more than a year's premium) fails cooked food Tier 1 at 77 of 103 centres and almost every shop product, because 67-80% of a shop's premium is the 2-day lockdown allowance. In 2017-2026 no centre had a year in which cooked food Tier 1, 2 or 3 paid back more than its premium. The cover's value is the shock: at the four places in the table a 40-day lockdown pays 1.9 to 9.7 years of premium.
4. Maxwell cooked food Tier 1: S$49.25 a month, expected back S$298 a year, typical year S$103, 2026 so far S$378, 2015-type year S$578, lockdown S$1,400, most S$1,575. Saving the premium instead keeps S$4,402 over 2017-2026.
5. Shop at 380123, packaged food Tier 1: S$15.32 a month, typical year S$11.63, 2015-type year S$56.54, lockdown S$1,400.
6. Fixed: the "a year like 2015" estimate on every quote included 2 lockdown days. It is now weather only.
7. Landing price line corrected: Tier 1 about S$16 a month for packaged food or general goods, S$48 for cooked food (middle place).

Decision needed (Sky, team lead): (a) accept the 5% commission Income quoted, with payout shares 67/70/73/75%, so cooked food passes everywhere but Tier 1 at 7 central centres; (b) price the lockdown by product or as its own line for shops; (c) keep 50% as the share. The tiers and shares were not changed.
