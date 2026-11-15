# The pricing story, customer first (16 Nov 2026)

Todo (P0, from Income's product lead): reorder the pricing story. Start with the target customer and what they can afford, then work back to the premium, cover, benefits, risk retention and price, and end with distribution [S1]. The proposal (`docs/proposal/safeday-proposal.tex`, Section 4) now follows this order. This note is the same story on one page, with a slide outline for the deck.

Every price is from the pricing engine with the final tariff of 15 Nov (`api/default_tariff.json`), run on 16 Nov through `fastapi.testclient` on `api.main:app`: `POST /api/quote` for Maxwell Food Centre (Kim Hua Market) cooked food and for a shop at postcode 380123 selling packaged food, with and without `daily_sales_sgd`, and `GET /api/map/quotes` for the 103 centres. Monthly = yearly / 12. The bad-year figures replay every day since 1 Apr 2014 to 8 Nov 2026 at all 103 centres, as `scripts/burn_analysis.py` does, at Tier 1. Shares of rent and income are our arithmetic on the cited figures.

## The story in seven steps

**1. Who is it for, and what can they afford?**
- Hawker stalls and small shops; the pilot sells to these two only. 5,837 cooked food stalls in 103 NEA centres [S2]. Platform workers later.
- A typical hawker's income is "around the second lowest income decile" (2022), below the S$5,000 median of an average Singaporean. Median hawker age 60 [S3]. No dollar figure for hawker income was found.
- Median rent of a non-subsidised cooked food stall: S$1,450 a month in 2025 (S$1,700 at socially-conscious enterprise centres) [S4]. The S$1,250 figure is the older one, quoted for 2015 to 2024 [S3].
- Service and conservancy about S$200, table cleaning about S$520 a month [S4]. Rent and charges: about S$2,170.
- Ingredients nearly 60%, manpower about 20%, rent under 10% of operating costs (NEA survey 2023) [S3]. So running costs are above about S$14,500 a month at the median rent.
- Daily takings: no official figure found. Our rough floor: more than about S$560 a day (S$14,500 / 26 trading days).
- Platform workers: median monthly earnings about S$1,500 to S$2,500 (2023) [S5].
- The brief: "a few dollars a week or month"; Asia-Pacific microinsurance average about US$13 a year [S6]. Stall insurance starts at S$0.30 a day [S7].

| Median centre, cooked food | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Monthly price | S$47.91 | S$244.68 | S$729.71 | S$1,457.35 |
| Share of S$1,450 rent | 3.3% | 16.9% | 50.3% | 100.5% |
| Share of rent and charges (S$2,170) | 2.2% | 11.3% | 33.6% | 67.2% |
| Share of S$5,000 income | 1.0% | 4.9% | 14.6% | 29.1% |

**2. What premium fits that budget?** What a bad day costs the business sets the biggest tier it can buy; the budget decides whether it takes that tier or a smaller one.
- The buy form asks for normal sales on a weekday. A day with no sales costs those sales x the product share (`product_factor`: 1.0 cooked food, 0.112 packaged food). The suggested tier is the biggest whose daily amount is at or below that loss. Tiers above it are not offered (insurable interest). Below S$35 no tier is offered: for packaged food, sales under about S$313 a day (S$35 / 0.112). Without sales every tier the place allows is shown and none is suggested. Rent is information only.
- Engine, 16 Nov: drinks stall at Maxwell (cooked food) S$150 a day: loss S$150, Tier 1 only. Chicken rice stall at Maxwell S$500: Tier 2 (Tiers 1 and 2 offered). Busy stall S$1,500: Tier 4. Provision shop at 380123, packaged food, S$2,000: loss S$223.73, Tier 2 (Tiers 1 and 2 offered).
- Tier 1, the smallest tier: S$49.25 a month at Maxwell (S$11.37 a week, S$1.62 a day); S$37.62 to S$61.37 a month across the 103 centres. That is above "a few dollars a week". We say so.
- A packaged food shop at 380123: Tier 1 S$15.32 a month, S$3.53 a week. This meets the brief.
- S$3 a week at Maxwell would buy about S$9.23 of daily cover, a sixth of a day's median rent (S$55.77).
- Lockdown cover is S$138.73 a year (S$2.67 a week) of every Tier 1 price, 23% of the Maxwell price.
- No willingness-to-pay survey exists. The pilot must test it.

**3. What does it cover?** Haze (PSI 101/201/301), heavy rain (20/30/50 mm in the wettest work hour, middle of 3 gauges), heat (2/4/6 work hours at WBGT 32°C or more), PUB flood alert, lockdown or closure order. Up to 45 full days in any 365 days, every tier, so a 40-day lockdown is paid in full. Worst replayed year at any centre: 14.9 full days (2026); a 2015-like weather year (2015 haze plus an average year of rain and heat, no lockdown) is 16.5 at Maxwell and at most 18.9 (Jurong West Street 52 Blk 505). 30-day wait; a move up a tier restarts it for the whole cover. No trigger, no payout.

**4. What does it pay?** S$35, S$195, S$630, S$1,355 for a day with no sales; a partly bad day pays its share (a 24% haze day: S$8.40 on Tier 1). 40-day lockdown: S$1,400 / S$7,800 / S$25,200 / S$54,200. Severe haze payout (option): 40+ days at PSI 101+ in the region in a policy year pays 25 x the daily amount once (S$875 on Tier 1), costs a tenth of that a year (S$87.50), not sold May to October, 30-day wait; priced as a 5.5% chance a year. Maxwell Tier 1 proof: paid in each of the last 10 years, typical year S$103 over about 17 part days, S$378 in 2026, about S$578 in a year like 2015 (weather only; it was S$648 while the estimate wrongly counted the 2 lockdown days). The price expects S$298.22 a year, so a typical year pays back much less than the average.

**4a. Is it worth more than saving the premium?** The product lead's question: "would I rather save $10 and self-insure?" [S1]. Self-insure test (`docs/notes/value-for-money-2026-11-16.md`): a tier passes at a place when a 2015-type weather year pays more than one year's premium. Maxwell cooked food: Tier 1 fails (S$578 against S$591, 0.98), Tier 2 passes (S$3,221 against S$3,018, 1.07). Shop at 380123: Tier 1 S$56.54 against S$184 (0.31) and Tier 2 S$315 against S$939 (0.34), both fail. Across 103 centres and 81 postcode areas, 5 products, 4 tiers: 541 of 3,680 pairs pass. Cooked food Tier 1 passes at 26 of 103 centres (Tier 2 at 81, Tier 3 at 84, Tier 4 at 103). Flowers pass only on Tier 4 (5 centres, 3 areas). Fresh produce, packaged food and general goods pass nowhere: 67% to 80% of a packaged food or general goods premium's expected payout is the 2-day lockdown allowance. In 2017 to 2026 no centre had a year in which cooked food Tier 1, 2 or 3 paid back more than its premium. The cover's value is the shock: a 40-day lockdown pays 2.4 years of premium on Maxwell Tier 1, 7.6 at the shop. Options for the team, not decided: the 5% commission Income quoted (payout shares 67/70/73/75%; cooked food then passes everywhere on Tiers 2 to 4 and on Tier 1 at 96 of 103); price the lockdown by product or sell it as its own line. Proposal Section 4.6.

**5. What does Income keep, and what does it reinsure?** Income keeps local rain and heat. Haze and lockdowns hit everyone at once: 1,000 Tier 2 customers in a 40-day lockdown cost S$7.8m; all 5,837 stalls on Tier 1 cost S$8.17m, 2.7 x that book's yearly premium before GST (S$3.05m). 6% of every premium (about S$183,000 a year on the full Tier 1 book) is for reinsurance. Our assumption: buy cover for the book above a set yearly loss. The structure todo (in-house, excess layer or percentage ceded) is still open. Tier 1 replay per 1,000 stalls: normal years 17% to 33% payouts, profit S$166,300 to S$250,100; 2026 72%, loss S$35,600; 2015-like with an average year of rain, heat and lockdown 118%, loss S$277,900; 40-day lockdown 268%, loss S$1,060,300. Designed: 55%, profit S$52,300.

**6. How is the price built?** Replay every recorded day at the place, cap each year at 45 days, average, add 2 lockdown days: Maxwell 8.52 days. Yearly price = paid days x daily amount / payout share x 1.09: 8.52 x S$35 = S$298.22, / 0.55 = S$542.22, x 1.09 = S$591.02. Five parts per S$100 before GST: payouts 55/60/65/70, reinsurance 6, management 12/10/8/7, distribution 17/15/13/10, profit 10/9/8/7. Bigger tiers return more because fixed costs do not grow (cover multiple 2.7 at Tier 1 to 3.4 at Tier 4, Maxwell). Guardrail: a tier priced above half its limit is not offered at that place (no underwriter referral for price; the underwriter sees only past declines). None is, at any centre or postcode area; the highest is Tier 1 cooked food at 47%.

**7. How is it sold?** The customer pays. Only through the customer's own Income adviser (add-on to Stallholder or SmartBiz 360) or an association group scheme; a direct sale around the agent is "an absolute no-no" [S1]. Commission range quoted 5% to 20% [S1]; our distribution share is 10% to 17%. Pilot: about 300 stalls through one hawker association, hawker stalls and shops only. 12 or 24 month term, monthly price shown, paid weekly. Renewal: apply again when the term ends; upgrade restarts the wait; downgrade keeps it; re-buy after a lapse waits again and the limit counts the last 365 days; no clawback.

## Deck outline (one slide per line: title, the one number)

1. Who we built it for: hawkers, typical income in the second-lowest decile [S3].
2. What a stall pays to trade: S$1,450 median monthly rent [S4].
3. What Tier 1 costs them: S$49.25 a month at Maxwell, 3.4% of median rent.
4. Which tier: by daily sales. S$150 a day: Tier 1; S$500: Tier 2; S$1,500: Tier 4; a shop selling S$2,000 of packaged food loses about S$224: Tier 2.
5. What fits the budget: S$3.53 a week for a packaged food shop on Tier 1.
6. Honest about the gap: S$11.37 a week, above "a few dollars a week".
7. What it covers: 45 full days a year, every tier.
8. What it pays: S$35 for a day with no sales, its share on a part day.
9. Lockdown paid in full: S$1,400 for 40 days on Tier 1.
10. Severe haze payout: 25 x the daily amount, S$875 on Tier 1.
11. Proof at Maxwell: paid in each of the last 10 years.
12. Worth more than saving? Cooked food Tier 1 passes at 26 of 103 centres; the lockdown pays 2.4 years of premium.
13. What Income keeps vs reinsures: S$7.8m for 1,000 Tier 2 customers in a 40-day lockdown.
14. A bad year: 2026 haze at 72% of Tier 1 premium.
15. How the price is built: 8.52 days x S$35 / 0.55 x 1.09 = S$591.02.
16. Five parts: 10% profit at Tier 1.
17. How it is sold: adviser or association, pilot of 300 stalls.

## Open points found while doing this

- Resolved 16 Nov: the rent hint no longer picks the tier. The tier is suggested by daily sales (step 2), and rent is shown only as information. "Tier 1 is the hawker plan" is gone from the proposal.
- The self-insure test fails most tiers on weather alone (step 4a). The commission and the lockdown price are open decisions for the team lead.
- Daily sales are declared by the customer and not checked against records.
- The proposal's two screenshots (day simulator, tariff desk preview) showed the old S$20 to S$100 tiers. They were taken out; the simulator figure is now given in text from the engine (Tier 1: S$23.79 a stall, S$138,862 for 5,837 stalls on a PSI 230, 40 mm, 3 hot hours day). Retake them for the deck.
- `data/processed/burn_*.csv` still hold an older Tier 2 premium pool (about S$451 a stall). Rerun `scripts/burn_analysis.py` before quoting it.
- The sign-up pause during NEA advisories, and stopping cover when a weekly premium is not paid, are not built. The proposal says so.

## Sources

- [S1] Income product lead, Q&A and private mentoring session, 15 Nov 2026, as recorded in the team's Notion (TODO "[FROM INCOME Q&A] Reorder the pricing story", P0; "[FROM INCOME Q&A] Rework distribution"); see `docs/notes/distribution-proposal-2026-11-15.md` [S27] and `docs/notes/notion-decisions-sweep-2026-11-15.md`.
- [S2] NEA, Hawker Centres dataset, data.gov.sg.
- [S3] MSE, Response to motion on hawker culture by SMS Dr Koh Poh Koon, 13 Nov 2024, paras 24 to 26, 39, 62: https://www.mse.gov.sg/latest-news/response-to-motion-on-hawker-culture-by-senior-minister-of-state-ministry-of-sustainability-and-the-environment-dr-koh-poh-koon/ (read 16 Nov 2026). Source of the second-lowest decile, the 60% / 20% / under 10% cost split and the older S$1,250 rent.
- [S4] MSE, Written reply to PQ on average monthly costs of cooked food stalls, 8 Sep 2026, 2025 figures: https://mse.gov.sg/latest-news/written-reply-to-parliamentary-question-on-heat-preparedness-by-ms-grace-fu--minister-for-sustainability-and-the-environment- (read 16 Nov 2026).
- [S5] MOM, speech by SMS Koh on the Platform Workers Bill, 9 Sep 2024: https://mom.gov.sg/newsroom/speeches/2024/0909-speech-by-sms-koh-on-platform-workers-bill (via `docs/notes/parametric-sales-research-2026-11-15.md`).
- [S6] Problem statement, section 1: `docs/problem-statements.md`.
- [S7] Income Insurance, Stallholder Insurance brochure 2024.
- Engine: `api/default_tariff.json`, `api/main.py` (`/api/quote` with `daily_sales_sgd`, `/api/map/quotes`), `api/calculator.py`; value-for-money tables `data/processed/value_for_money*.csv` (`scripts/value_for_money.py`); renewal rules in `api/main.py` (`buy_policy`) and `docs/notes/claim-parameters-and-exclusions-2026-11-15.md`.
