# Expected impact: who Payung protects, how fast it pays, and what a haze year looks like (deliverable 5)

Updated 15 Nov 2026 after Deval's commit `16ec056`: the burn numbers below come from the rebuilt burn files, and loss ratios divide by the premium before GST, as those files do.

Updated 16 Nov 2026: the haze-year numbers (sections 0, A.2, C, E and F) now use the final tariff on Deval's branch `production-ready-pricing` (commit `b9aaced`). The Notion page "Payung pricing for review: loss, payout, premium and profit" uses the same tariff, and the team's cross-check row makes that page the reference. The branch is not merged yet, so `main` still runs the old tariff. The old figure of 106.7% for 2026 came from the old tariff (Tier 2 at S$40 a day for 15 days). Do not use it. The final tariff pays S$35 a day at Tier 1 and S$195 a day at Tier 2, for up to 45 days a year. Tier 1 comes first below, because Deval's burn files and the burn report now use Tier 1, the tier a stall is suggested.

Research note for the SIH FIN-4 team, 15 Nov 2026. Payung, offered with Income Insurance. Brief: `/Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/problem-statements.md`, section 1. This note covers the first half of deliverable 5: "Expected impact in terms of improved financial protection for groups". The affordability half (premium against income) is a separate parked task. This note quotes premium values only.

This note changes no number in the product and does not edit the tariff.

How to read this note:
- All file paths are inside `/Users/dewa/Documents/Projects/SIH/sih-fin-4`.
- Every number names its source. The sources are a repo file, the script in the appendix, a Notion page title, or a published document with its date.
- "Assumption" marks a number or rule that nobody measured. Each Assumption has its reasoning next to it.
- "No source found" means we searched and found nothing.
- "Tariff" means `api/default_tariff.json` as saved on 15 Nov 2026 at 12:55.
- The appendix holds the script `impact_calc.py` and its output. Every computed number comes from it.

## 0. Summary and five warnings

| Question | Answer in one line |
|---|---|
| A. Who is protected in year 1 | Low case 800 people, middle case 6,152, high case 16,722. These are Assumptions, not forecasts. |
| B. Time to payout | Today's code: an insurer starts a run for one date, then PayNow and SMS. The design: automatic, same day. Today's alternative: days for a fast-track claim and weeks to years for a business-interruption claim. SmartBiz 360 pays nothing on a haze or heat day. |
| C. Haze year | On the final tariff, a 2026-type year pays S$375.33 a stall at Tier 1 (island average), against S$128.41 in a normal year. The island loss ratio is 71.8% in 2026 (Tier 2: 78.3%). The payout replaces 7.0% of the estimated lost sales at Tier 1 and 39.0% at Tier 2, in every year. |
| D. Say-it-back test | Not tested yet. |

Five warnings for the team:
1. **The 2026 haze-year figure must be 71.8% (Tier 1) or 78.3% (Tier 2).** Three versions were in use: 76% in the old burn analysis, 147% on the pricing page (as the cross-check row quotes it), and 106.7% in this note (Notion TODO "Cross-check that the numbers in the PPT, the proposal and the live demo all tell the same story"). All three are out of date. On the final tariff, the island loss ratio in 2026 (to 8 Nov) is 71.8% at Tier 1 (`data/processed/burn_yearly_island.csv` on branch `production-ready-pricing`, column `loss_ratio`) and 78.3% at Tier 2 (the same script at Tier 2, appendix). The pricing page, section 7.1, gives the same two values. For the ten-year figure, use 29.3% at Tier 1 and 32.0% at Tier 2 (average a year, 2017 to 2026, pricing page section 7.2). Sky should put these in the master list and the deck.
2. **The share of lost sales that a payout replaces is fixed by the maths.** The payout is `loss share x tier amount`. The estimated lost sales are `loss share x S$500`. So a Tier 1 payout always replaces S$35 / S$500 = 7% of the estimate, and a Tier 2 payout S$195 / S$500 = 39%. The 45-day limit never binds on weather alone, so the share does not change in a bad year. It does not measure real losses. Nobody has sales data (master list, section 8, limitation 1).
3. **2026 is a part year.** The day table ends on 8 Nov 2026 (`data/processed/day_readings.csv.gz`, last `day` value). The 2026 figures cover 1 Jan to 8 Nov.
4. **2026 no longer pays more than the premium pool, but a 2015-type year does.** On the final tariff, 2026 pays S$2,190,799 at Tier 1 against a pool of S$3,050,651 before GST (S$3,325,210 with GST, all 5,837 stalls at Tier 1): 71.8%. A 2015-type year (the 2015 haze plus average rain and heat) pays 104.8% at Tier 1 and 114.3% at Tier 2 (pricing page, section 7.2). That is before expenses and before reinsurance.
5. **The stall counts in the team documents disagree.** The master list says "5,837 stalls", "~6,500 cooked-food stalls" and "14,600 total". The published figures are 11,446 all-type NEA hawker stalls at end 2025 and 6,665 cooked-food stalls (section A.1). The figure 14,600 has no match in the sources we found. Do not put 14,600 on a slide.

## A. Workers, stalls and households protected in year 1

### A.1 The market, with cited figures

| Group | Figure | Source | Note |
|---|---|---|---|
| Cooked-food stalls in the 103 existing centres | 5,837 | `data/processed/map_static.json`, key `hawker_centres`, field `food_stalls`, sum over 103 centres. The file's `sources.exposure` names the NEA Hawker Centres dataset (data.gov.sg). | This is the stall base the burn analysis and the pilot use. |
| Cooked-food stalls in all 123 operating centres | 6,665 | chachacha.com.sg, "Hawker Centre Statistics Singapore (2026)", 28 Sep 2026. The page sums the NEA data.gov.sg dataset "List of Government Markets Hawker Centres". | Secondary source. We did not open the NEA dataset. The 5,837 figure is the "Existing" status only. The other 828 stalls sit in 16 new centres, 3 replacement centres and 1 interim centre. |
| Cross-check on cooked-food stalls | About 6,500 | MSE, written reply on prolonged vacancies, 24 Feb 2026: "about 130 or 2% of cooked food stalls" were vacant over six months at 31 Dec 2025. 130 / 0.02 = 6,500. | Arithmetic on rounded numbers. It agrees with 6,665. |
| All NEA hawker stalls (all types) | 11,446 | SingStat table M890531 (SFA), end 2025, as quoted by chachacha.com.sg on 28 Sep 2026. | Secondary source. Includes market stalls. |
| All hawker stalls, older figure | More than 14,000 | MSE reply on stall tender bids, stalls in 119 centres at 31 Mar 2024 (distribution note source S5, search snippet only). | This conflicts with 11,446. We do not know why. Do not use it until someone opens the reply. |
| Stallholders who hold some insurance | About two-thirds | MSE, written reply on insurance for hawkers, 4 Aug 2026 (NEA survey of cooked-food stallholders). | The reply says nothing about weather cover. |
| Neighbourhood shops (HDB) | About 15,200 | HDB press release, 19 Nov 2022, "Supporting Heartland Shops" (distribution note source S18, search snippet only). | The figure is from 2022. |
| Resident platform workers | 71,600 | MOM, Labour Force in Singapore 2025, paragraph 2.36 (distribution note source S7). Made of 36,000 private-hire drivers, 20,900 taxi drivers and 14,700 delivery workers. | Use this figure and not the NTUC 67,600 figure (distribution note, section 6, item 3). |
| Average resident household size | 3.06 persons | SingStat, Resident Households, table M810371, 2025. | National average. Not specific to hawkers or riders. |
| Policies in force on SmartBiz 360 and on Stallholder Insurance | No source found | Distribution note, channel sheets A and B. | Income must answer (distribution note, section 7, question 2). |
| Grab's share of the 71,600 | No source found | Distribution note, channel sheet C. | |

### A.2 Year-1 cases

The channels come from the distribution note (`docs/notes/distribution-proposal-2026-11-15.md`, section 1). Hawkers launch through the Stallholder Insurance add-on. Shops launch through the SmartBiz 360 add-on. Platform workers launch through one platform, with an association as the fallback.

No uptake benchmark exists for this product. The brief gives no uptake figure for any weather product. It gives one growth figure for SEWA in India: from 21,000 to about 250,000 members in 2023 to 2026 (`docs/problem-statements.md`, line 49). It also gives one failure: KB Insurance in Korea had no subscribers ten months after launch (`docs/problem-statements.md`, line 54). The three cases below are therefore Assumptions.

| Group | Low | Middle | High |
|---|---|---|---|
| Hawker stalls | 300 | 1,000 | 1,946 |
| Neighbourhood shops | 0 | 152 | 456 |
| Platform workers | 500 | 5,000 | 14,320 |
| **Policyholders (workers)** | **800** | **6,152** | **16,722** |
| **Households (one per policyholder)** | **800** | **6,152** | **16,722** |
| **Persons in those households** | **2,448** | **18,825** | **51,169** |
| Stalls as share of 5,837 | 5.1% | 17.1% | 33.3% |
| Stalls as share of 6,665 | 4.5% | 15.0% | 29.2% |
| Stalls as share of 11,446 | 2.6% | 8.7% | 17.0% |
| Shops as share of 15,200 | 0.0% | 1.0% | 3.0% |
| Platform workers as share of 71,600 | 0.7% | 7.0% | 20.0% |

All counts and shares come from the script in the appendix, section "A. Year-1 cases".

Assumptions behind the cases:

- **Assumption A1, hawkers, low (300 stalls).** This is the pilot size that the team asks Income for ("Ask: 300-stall pilot with Income", master list, section 1). It is the least we expect if Income agrees to the pilot at all. Reasoning: the distribution note warns that if the Stallholder base is under 300 policies, the pilot needs a second channel (hawker associations).
- **Assumption A2, hawkers, middle (1,000 stalls).** This is the team's draft target "1,000 stalls in year 1 via SmartBiz 360 / Stallholder add-on" (SafeDay Hackathon Plan PDF, section 14, in `/Users/dewa/Documents/Projects/SIH/whatsapp/2026-11-15 SIH FIN-4/00003068-SafeDay-Hackathon-Plan.pdf`, page 27). Reasoning: it is the only year-1 figure the team wrote down. No analysis in the repo supports it. It equals 17.1% of the 5,837 stalls.
- **Assumption A3, hawkers, high (1,946 stalls).** This is 5,837 x two-thirds x one half. Reasoning: only stallholders who already hold insurance are likely to buy an add-on, and two-thirds of cooked-food stallholders do (MSE, 4 Aug 2026). We assume half of those buy in year 1. The one-half share has no source. It is an upper bound for a first year.
- **Assumption A4, shops (0 / 152 / 456).** These are 0%, 1% and 3% of 15,200 HDB shops. Reasoning: no benchmark exists and SmartBiz 360 is new (Oct 2026). The distribution note says its sectors are mostly indoor, so only retail and food and beverage fit weather loss. Low is zero because the channel may not launch. The 1% and 3% values only show scale.
- **Assumption A5, platform workers (500 / 5,000 / 14,320).** Middle is the team's draft target "5,000 in year 1 through one platform and one association" (SafeDay Hackathon Plan, section 14). High is 20% of 71,600, which the draft sets as the three-year aim ("aim for 20% of 71,600 in 3 years"). Reasoning for high: it assumes the three-year aim arrives in year 1. Treat it as an upper bound. Low is 500, one association pilot with no platform deal. Reasoning: the distribution note calls the platform channel the weakest, and no source gives the membership of NDCA, NPHVA or NTA.
- **Assumption A6, one policy per person.** One policy covers one stallholder, one shop owner or one rider. A stall has one licence holder. Assistants and staff are not covered (distribution note, channel sheet F).
- **Assumption A7, year 1 means policies in force.** We count policies sold. We ignore the 30-day waiting period and the sale dates. A policy sold late in the year protects no one for part of the year.
- **Assumption A8, households.** "Household" means the family of a covered stallholder or rider. We count one household per policyholder. We count persons as policyholders x 3.06. Reasoning: no source gives the household size of hawkers or riders (No source found). The national average is the only published figure. Two covered people in one household would reduce the household count. We expect this to be rare, and we have no data on it.

Money that would reach stallholders (illustration, stalls only, Tier 1 on the final tariff, island-average payout per stall from section C): low case S$38,524 in a normal year and S$112,599 in a 2026-type year; middle case S$128,412 in a normal year and S$375,330 in a 2026-type year; high case S$249,890 in a normal year and S$730,391 in a 2026-type year. Source: section C.2 per-stall figures times the stalls in each case.

## B. Time to payout against today

### B.1 What Payung does today and what the design intends

| Item | What the code does today | What the design intends |
|---|---|---|
| Who starts a payout | An insurer user starts "Run payouts" for one Singapore date. The route is `POST /insurer/payout-runs`, function `run_payouts` in `api/payout_api.py`. The run assesses every policy for that date (`run_day` in `api/payout_flow.py`). | The readings decide. No person starts the run. The master list says "Same day, automatic, on the NEA reading" (section 1, row "Speed"). |
| Schedule | None. "No scheduled job for now" (`docs/notes/payout-flow-design-2026-11-15.md`, Decisions, item 3). | A scheduled run. Not built. |
| Approval | Automatic. A payout moves from assessed to approved with no click (payout-flow-design, Decisions, item 2). The insurer can still reject one with a written reason before it is sent. | The same. |
| Money | PayNow is a simulator. It settles at once in the same request (payout-flow-design, lifecycle section). No money moves. | A real PayNow transfer through a bank corporate account. Not built. |
| Message | The SMS is simulated. Example text: "Payung: S$62.40 sent to PayNow +65 ****4567 ... No claim needed." | A real SMS. Not built. |
| Missing data | The run reads the stations that reported among the nearest and every other within 5 km (rain: median of the first 3, heat: the first one), then (rain only) the MSS record (`api/readings.py`). Otherwise the policy waits as `awaiting_data` and a later run can pay it (payout-flow-design, "When a station's feed is missing"). | The same. "Late, never refused." |
| Elapsed time | Not measured. No timing log exists. No source found. | Draft target "Under 1 hour" (SafeDay Hackathon Plan, section 14, page 27). The draft SMS says "usually within the hour" (claims note, item D15). |

The claims note (`docs/notes/claim-parameters-and-exclusions-2026-11-15.md`, item D15) already says to write "designed to be automatic" until a scheduled run exists. This note agrees.

Two limits on any speed claim, from the tariff text (`api/default_tariff.json`, field `reading`):
- Heat and rain read the work hours 07:00 to 19:00. A run for the day cannot finish before 19:00.
- Haze reads the highest 24-hour PSI of the day. The day's highest value is known only at the end of the day.

So the first sensible payout time is the evening of the trigger day. The "under 1 hour" target holds only if the clock starts when the trigger window closes. It does not hold if the clock starts at the first bad reading. The Notion page "Insurance Payout Speed and Frictions" says the ILO recommends measuring from the date of the event. That page suggests the pitch line "money in your account within 24 hours of the trigger day". We recommend that line. The "under 1 hour" line is not supported by the code or by the reading rules. This is our reasoning, not a published finding.

### B.2 Today's alternative

All rows below come from the Notion page "Insurance Payout Speed and Frictions" (a .docx attached to the page, read on 15 Nov 2026). The page gives source names and no links. We checked three rows against the publisher (marked "checked").

| Claim type | Time | Source |
|---|---|---|
| Fast-track claim, Singapore (MSIG) | 92% settled within three days in 2025 | MSIG Singapore, inaugural claims report, 17 Aug 2026. Checked: msig.com.sg and reinasia.com repeat the figure. |
| Singapore industry standard | Acknowledge in 3 business days. Ask for more documents in 7 business days. Decide in 7 business days once documents are complete. Pay in 10 business days after settlement is agreed. | GIA Code of Practice (gia.org.sg). Checked for the 3-day and 7-day rules. The 10-day payment rule comes from the Notion page and we did not see it on the GIA page. |
| Property damage claim, Singapore | Typically 30 to 60 days, because an assessor must evaluate it | Notion page, citing a MoneySmart claims guide. Not checked. |
| Business interruption, large firms (UK) | More than 60% took over a year. 14% took over two years. | Notion page, citing Insurance Business on an Airmic and Marsh survey. Not checked. This is a UK corporate sample, not Singapore hawkers. |
| Major fire with business interruption | 18 to 24 months or longer | Notion page, citing Insurance Claim Recovery Support. Not checked. |
| Parametric heat cover, SEWA (India) | Two to three weeks | Notion page, citing a CGAP case study. |
| Parametric cover, fully automated (FloodFlash, UK) | 67% of claims within 48 hours. Fastest 3 hours 50 minutes. | Notion page, citing the FloodFlash annual magazine. Not checked. |

Two conflicts to settle before the deck:
1. The brief says SEWA payouts "took six to eight weeks" (`docs/problem-statements.md`, line 49). The Notion page, citing CGAP, says two to three weeks. The master list and the draft plan both use "6–8 weeks". Pick one source and name it on the slide. We cannot tell which is right from here.
2. The Airmic figure is for large UK firms. It is the only business-interruption timing on the page. Do not present it as the Singapore hawker experience. For Singapore, the page gives only property damage (30 to 60 days), the GIA rules and MSIG fast-track.

**SmartBiz 360 pays nothing on a haze or heat day.** Its business-interruption benefit needs physical damage or loss (distribution note, channel sheet A, source S1: Income Insurance, SmartBiz 360 page, "Information is correct as at 05 November 2026"). A haze day or a hot day damages nothing. So a claim for lost sales on such a day would not be paid, however long the claim takes. For hawkers, Income's Stallholder Insurance also has no weather trigger. Its closure-of-stall benefit is S$100 to S$200 a day for up to 120 days (distribution note, channel sheet B, source S3, a 2024 brochure). For most customers the comparison is therefore not "days against weeks". It is "paid on the day" against "not paid".

## C. Protection in a haze year

### C.1 What the burn analysis assumes

Source: `scripts/burn_analysis.py`.

| Setting | Value | Where in the script |
|---|---|---|
| Product | Cooked food | constant `PRODUCT` |
| Tier | Tier 1: S$35 a day, 45 paid days a year, so a limit of S$1,575 a year. Tier 2 (rerun, appendix): S$195 a day, 45 days, S$8,775. | constant `TIER` and `cap_sgd`. Tariff `tiers` on branch `production-ready-pricing`. |
| Daily takings | S$500 a day | constant `DAILY_TAKINGS_SGD`. The comment says it is the mid-point of "the triangulated S$400-800/day gross takings of a viable cooked-food stall (no official figure exists)". This is an Assumption. |
| Estimated lost sales on a trigger day | `loss share x S$500` | `entry["lost"] += loss * DAILY_TAKINGS_SGD` |
| Payout on a trigger day | `loss share x` the tier amount, limited by the limit left that year | `calculator.assess` and `paid = min(assessment.payout_sgd, room)` |
| Centres | All 103 existing centres, 5,837 cooked-food stalls | `centres = static["hawker_centres"]` |
| Premium | The cooked-food yearly premium at the tier, at each centre's own place, times its stalls | `premiums` and `premium_pool` |
| Period | 2014 to 8 Nov 2026 on the final tariff. 2014 (from 1 Apr) and 2026 are part years. Before Dec 2016 the years have haze only, and before 2025 they have no heat (pricing page, section 7.1). | `data/processed/day_readings.csv.gz` |

The premium in the burn analysis is the place premium of each centre. Since Deval's commit `16ec056`, that is also what a hawker is charged (`business_quote` in `api/main.py`), so the pool is what these stallholders would pay.

The estimated lost sales are not measured losses. They are the tariff's own loss score times the S$500 assumption. They show scale. They do not prove the payout matches a real loss.

### C.2 2026 against a normal year

Source: `data/processed/burn_yearly_island.csv` and `data/processed/burn_yearly_hero.csv` on branch `production-ready-pricing` (Tier 1), and the same files from a Tier 2 run of `scripts/burn_analysis.py` (appendix, "Rerun on the final tariff"). "Normal year" means the average of 2017 to 2025.

| Measure (cooked food, final tariff) | Normal year, island | 2026, island | Hero stall, normal | Hero stall, 2026 |
|---|---|---|---|---|
| Total paid, Tier 1 | S$749,543 (mean) | S$2,190,799 | | |
| Paid per stall, Tier 1 | S$128.41 (range S$89.65 to S$173.39) | S$375.33 | S$130.59 | S$389.69 |
| Paid per stall, Tier 2 | S$715.44 (range S$499.50 to S$966.01) | S$2,091.12 | S$727.57 | S$2,171.13 |
| Trigger days | | | 17.2 (mean) | 49 |
| Estimated lost sales, total | | S$31,297,022 | | S$5,567 |
| Share of estimated lost sales replaced | Tier 1 7.0%, Tier 2 39.0% | Tier 1 7.0%, Tier 2 39.0% | the same | the same |
| Premium before GST, Tier 1 (pool or one stall) | S$3,050,651 pool | S$3,050,651 pool | S$532.27 | S$532.27 |
| Premium before GST, Tier 2 (pool or one stall) | S$15,580,111 pool | S$15,580,111 pool | S$2,718.34 | S$2,718.34 |
| Loss ratio, Tier 1 (on the premium before GST) | 24.6% (range 17.2% to 33.2%) | 71.8% | 24.5% | 73.2% |
| Loss ratio, Tier 2 | 26.8% (range 18.7% to 36.2%) | 78.3% | 26.8% | 79.9% |
| 2026 against normal | | 2.92 times the total paid | | |

Reading the table:
- The ten-year figure for the deck is the average a year over 2017 to 2026: 29.3% at Tier 1 and 32.0% at Tier 2 (pricing page, section 7.2). The 2017 to 2025 mean leaves out 2026, so it is lower.
- The island loss ratio in a normal year (24.6% at Tier 1) sits below the Singapore general-insurance claims ratio of 49.6% that the master list quotes (MAS returns 2021 to 2025, via the master list, section 5). We did not check the MAS returns.
- The 2026 payout per stall at Tier 1 (S$375.33) is 24% of the S$1,575 yearly limit. The limit is not reached, so the share replaced is the same in every year.
- The share replaced is fixed by the tier amount over the takings assumption: S$35 / S$500 = 7% at Tier 1 and S$195 / S$500 = 39% at Tier 2. Do not describe it as a finding. It is a design property.
- 2026 was not a "bad year for the pool only". Rain and heat added to the haze. At the hero stall, 2026 paid S$193.20 for haze, S$134.75 for rain and S$63.00 for heat at Tier 1 (`burn_yearly_hero.csv` on the branch).

Burn-analysis gap found while checking: the day table takes haze from the real-time PSI feed, which has gaps. In 2019 it has data for 280 days (`data/processed/psi_yearly.csv`, column `days_with_data`). The NEA 24-hour history has all 365 days. For the south region in 2019 the burn analysis pays S$57.60 for haze (6 days). The history gives S$105.60 (11 days). The 2016 value agrees (S$19.20 in both). So the burn analysis under-counts haze in years with feed gaps. The normal-year figures above are slightly low for that reason. This check was made on the 15 Nov files. We did not repeat it on the final tariff.

### C.3 2015, haze only

On the final tariff the burn files start in 2014, so they cover 2015 directly. 2015 has haze only, because rain is recorded from Dec 2016 and heat from 2025.

| Item (cooked food, island, final tariff) | Tier 1 | Tier 2 |
|---|---|---|
| Paid, 2015 (haze only) | S$2,296,048 | S$12,792,265 |
| Paid per stall, 2015 | S$393.36 | S$2,191.58 |
| Loss ratio, 2015 (haze only) | 75.3% | 82.1% |
| Loss ratio, 2015-type year (2015 haze plus average rain and heat) | 104.8% | 114.3% |

Sources: `data/processed/burn_yearly_island.csv` on the branch (Tier 1) and the Tier 2 rerun (appendix). The 2015-type year is from the pricing page, section 7.2.

For 2015:
- It is 2015 weather under today's tariff. It is not what Payung would have paid in 2015, because the product did not exist.
- 2015 haze alone pays a little more than the whole of 2026 (S$393.36 against S$375.33 a stall at Tier 1).
- The 15 Nov version of this note estimated 2015 from the PSI history on the old tariff (S$449.56 a stall, 109.7% of the pool). Those figures are out of date. Do not use them.

## D. Percentage who pass the say-it-back test

**Not tested yet.**

What we searched:
- Notion: queries "say-it-back one-SMS explanation hawker test", "Expected impact households protected" and "Insurance Payout Speed and Frictions". We found the plan only. We found no result with a pass rate.
- Notion TODO (Dewa): "[FROM PS DOC] Expected impact (deliverable #5) ..." has status "In progress" and a blank page.
- Master list, sections 3 and 11: "One-SMS policy in EN / ZH / MS / TA with the say-it-back quiz" is under "Designed, not built". "One-SMS in 4 languages + exclusion line (Rafael)" is an open item.
- Repo: `grep` for "say-it-back", "say it back" and "one SMS" over the repo found text in `docs/` notes, `api/sms.py`, `api/map/map.js` and `api/site/index.html`. None holds a test result. No `survey/` folder exists.
- The draft plan (PDF section 14) says "Customers who understand it: Unknown. Target 90%+ pass the 'say it back' quiz." The 90% is a target. No test supports it.

Do not write any pass percentage in the proposal. Write "Not tested yet. Target 90%, to be tested in the pilot."

The test to run (it covers Rafael's one-SMS TODO and the draft plan's week-4 step "Talk to at least 10 riders and 10 hawkers"):
1. Show each person the one-SMS policy in their language (English, Chinese, Malay or Tamil). Give them one minute to read it.
2. Take the SMS away. Ask three questions: "When does Payung pay you?", "How much, at most?" and "If it rains a little and you stop work, do you get paid?" (the answer is no, from the draft plan, page 12).
3. A person passes when all three answers are right in their own words.
4. Record language, role (hawker, shop owner, rider), pass or fail, and which question failed. Keep names and photos out of git (`AGENTS.md`, rule "Personal data").
5. Report passes out of people tested, for example "7 of 10". With 10 per group the result shows direction and not a rate.
6. This is an Assumption: the pass rule (all three right) and the group size (at least 10 hawkers and 10 riders). The group size comes from the draft plan. The pass rule is ours.

## E. Impact table for the proposal

| Measure | Value | Source or Assumption |
|---|---|---|
| Hawker stalls protected, year 1 | 300 / 1,000 / 1,946 (low / middle / high) | Assumption A1 to A3 (section A.2). Market: 5,837 cooked-food stalls in 103 centres (`data/processed/map_static.json`). |
| Neighbourhood shops protected, year 1 | 0 / 152 / 456 | Assumption A4. Market: about 15,200 HDB shops (HDB press release, 19 Nov 2022). |
| Platform workers protected, year 1 | 500 / 5,000 / 14,320 | Assumption A5. Market: 71,600 (MOM Labour Force in Singapore 2025). |
| Workers, total policyholders | 800 / 6,152 / 16,722 | Sum of the three rows above (script, section A). |
| Households protected | 800 / 6,152 / 16,722 | Assumption A6 and A8. One household per policyholder. |
| Persons in those households | 2,448 / 18,825 / 51,169 | Assumption A8. Policyholders x 3.06 (SingStat, resident households 2025). |
| Time to payout, Payung today | An insurer starts a run for one date. PayNow and SMS are simulated. No time measured. | `api/payout_api.py` (`run_payouts`), payout-flow-design Decisions 1 to 3. |
| Time to payout, Payung design | Automatic, same day. Recommended line: "money within 24 hours of the trigger day". | Master list section 1. Notion page "Insurance Payout Speed and Frictions". The "under 1 hour" draft target is not supported (section B.1). |
| Time to payout, fast-track claim today | 92% within three days (MSIG) | MSIG Singapore claims report, 17 Aug 2026. |
| Time to payout, Singapore standard | Pay within 10 business days after settlement is agreed | GIA Code of Practice. Notion page "Insurance Payout Speed and Frictions". |
| Time to payout, property damage today | Typically 30 to 60 days | Notion page, citing MoneySmart. Not checked. |
| Haze, weather income cover today | Pays nothing: SmartBiz 360 business interruption needs physical damage | Distribution note, source S1. |
| 2026 payout per stall | S$375.33 at Tier 1, S$2,091.12 at Tier 2 (island average, 1 Jan to 8 Nov, final tariff) | `data/processed/burn_yearly_island.csv` on branch `production-ready-pricing`, and the Tier 2 rerun (appendix). |
| Normal-year payout per stall | S$128.41 at Tier 1, S$715.44 at Tier 2 (2017 to 2025 mean) | Same files. |
| Share of estimated lost sales replaced | 7.0% at Tier 1, 39.0% at Tier 2, in every year | Assumption: S$500 a day takings (`scripts/burn_analysis.py`, `DAILY_TAKINGS_SGD`). Fixed by the tier amount. |
| Loss ratio, island (premium before GST) | 71.8% in 2026 at Tier 1 (78.3% at Tier 2); 29.3% a year over 2017 to 2026 at Tier 1 (32.0% at Tier 2) | Same files. Notion page "Payung pricing for review: loss, payout, premium and profit", sections 7.1 and 7.2. |
| Loss ratio, hero stall (Tiong Bahru) | 73.2% in 2026 at Tier 1, 24.5% mean over 2017 to 2025 | `data/processed/burn_yearly_hero.csv` on the branch. |
| 2015 haze, per stall | S$393.36 at Tier 1 (haze only) | `data/processed/burn_yearly_island.csv` on the branch. |
| 2015 haze, island loss ratio | 75.3% at Tier 1, 82.1% at Tier 2 (haze only). A 2015-type year with average rain and heat: 104.8% and 114.3%. | Same files. Pricing page, section 7.2. |
| Say-it-back pass rate | Not tested yet. Target 90% (draft plan, not tested). | SafeDay Hackathon Plan PDF, section 14. No test found in Notion or the repo. |

## F. Three sentences for the proposal

Payung would protect about 800 to 16,700 hawkers, shop owners and riders in year 1 (middle case 6,152, an Assumption), which reaches about 2,400 to 51,000 people in their households. In a 2026-type haze year the Tier 1 cover pays about S$375 a stall against about S$128 in a normal year, and the island loss ratio reaches 72% (78% at Tier 2), against 29% a year over the last ten years. The payout is automatic by PayNow with no claim form and is designed for the same day, against days for a fast-track claim and nothing at all from SmartBiz 360 on a haze day, but the speed is not yet measured and the say-it-back test has not been run.

## G. Open items for the team

1. Sky: put the final-tariff figures in the master list and the deck: 71.8% (Tier 1) or 78.3% (Tier 2) for 2026, and 29.3% or 32.0% for the ten-year average. Rerun `scripts/burn_analysis.py` first if the tariff changes again.
2. Dewa or Deval: pick one source for the SEWA payout time (2 to 3 weeks or 6 to 8 weeks) and open the CGAP case study.
3. Income: answer how many Stallholder Insurance and SmartBiz 360 policies are in force. The answer replaces the Assumptions in section A.2 for hawkers and shops.
4. Dewa: decide whether to fix the haze gaps in the day table (section C.2) before the numbers go on a slide. A fix changes `data/processed/` files, so it is outside this note.
5. Rafael: run the say-it-back test (section D) and report passes out of people tested.
6. Open the MSE reply on the hawker stall count (more than 14,000 against 11,446) before any slide quotes a total.

## Appendix: how to reproduce every computed number

The script reads the repo and writes nothing to it. Run it from the repo root:

```
cd /Users/dewa/Documents/Projects/SIH/sih-fin-4
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /path/to/impact_calc.py
```

Save the code below as `impact_calc.py` anywhere outside the repo. The repo does not hold the script.

The working copy of the script was kept at `/private/tmp/claude-501/-Users-dewa--claude-spares-spare-fqhk7Y/d3ed11b2-54b1-468a-92a5-82f010f17a46/scratchpad/impact_calc.py`. The full code follows, then its output on 15 Nov 2026. That output is on the old tariff. Its sections C1, C2 and A (money that reaches stallholders) are replaced by the rerun at the end of this appendix.

### Script `impact_calc.py`

```python
"""Expected-impact numbers for the Payung proposal. Read-only: writes nothing to the repo.

Run:  cd /Users/dewa/Documents/Projects/SIH/sih-fin-4
      PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this file>
Reads data/processed/burn_yearly_island.csv, burn_yearly_hero.csv, map_static.json,
      data/psi/psi_history_24hr.parquet, api/default_tariff.json.
"""
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path("/Users/dewa/Documents/Projects/SIH/sih-fin-4")
sys.path.insert(0, str(REPO))
from api import calculator  # noqa: E402
from api.models import Tariff  # noqa: E402

TIER, PRODUCT, TAKINGS = "tier_2", "cooked_food", 500.0
HOUSEHOLD_SIZE = 3.06  # SingStat, resident households 2025, table M810371
NORMAL_YEARS = range(2017, 2026)

tariff = Tariff.model_validate_json((REPO / "api/default_tariff.json").read_text())
tier = calculator.find(tariff.tiers, TIER, "tier")
cap = tier.daily_payout_sgd * tier.max_paid_days_per_year
print(f"Tier 2: S${tier.daily_payout_sgd}/day, {tier.max_paid_days_per_year} days, cap S${cap}")
for t in tariff.tiers:
    print(f"  share of S${TAKINGS:.0f} takings replaced by a full-loss day at {t.key}: "
          f"{t.daily_payout_sgd / TAKINGS:.0%}")

print("\n== C1. Burn analysis, island (103 centres) ==")
isl = pd.read_csv(REPO / "data/processed/burn_yearly_island.csv").set_index("year")
isl["paid_per_stall"] = isl.payout_sgd / isl.stalls
isl["premium_per_stall"] = isl.premium_pool_sgd / isl.stalls
isl["replaced"] = isl.payout_sgd / isl.est_lost_sgd
print(isl.round(3).to_string())
n = isl.loc[list(NORMAL_YEARS)]
print(f"Normal years 2017-2025: mean paid S${n.payout_sgd.mean():,.0f}, per stall "
      f"S${n.paid_per_stall.mean():.2f}, min/max per stall S${n.paid_per_stall.min():.2f}/"
      f"{n.paid_per_stall.max():.2f}, mean loss ratio {n.payout_sgd.sum() / n.premium_pool_before_gst_sgd.sum():.3f}, "
      f"range {n.loss_ratio.min()}-{n.loss_ratio.max()}, mean replaced {n.payout_sgd.sum() / n.est_lost_sgd.sum():.3%}")
y = isl.loc[2026]
print(f"2026: paid S${y.payout_sgd:,.0f}, per stall S${y.paid_per_stall:.2f}, "
      f"pool S${y.premium_pool_sgd:,.0f}, loss ratio {y.loss_ratio}, replaced {y.replaced:.3%}, "
      f"x normal paid {y.payout_sgd / n.payout_sgd.mean():.2f}")

print("\n== C1. Hero stall (Tiong Bahru, south region) ==")
hero = pd.read_csv(REPO / "data/processed/burn_yearly_hero.csv").set_index("year")
print(hero.to_string())
hn = hero.loc[list(NORMAL_YEARS)]
print(f"Normal 2017-2025 mean paid S${hn.payout_sgd.mean():.2f}, mean trigger days "
      f"{hn.trigger_days.mean():.1f}, loss ratio {hn.payout_sgd.sum() / hn.premium_before_gst_sgd.sum():.3f}")

print("\n== C2. Haze only from PSI history, all regions, Tier 2 cooked food ==")
psi = pd.read_parquet(REPO / "data/psi/psi_history_24hr.parquet")
psi["day"] = psi.timestamp.dt.date
daily = psi.groupby(["region", "day"]).psi_twenty_four_hourly.max().reset_index()
daily["year"] = pd.to_datetime(daily.day).dt.year


def haze_year_payout(frame: pd.DataFrame) -> tuple[float, int]:
    paid, days = 0.0, 0
    for value in frame.sort_values("day").psi_twenty_four_hourly:
        if value < 101:
            continue
        a = calculator.assess(tariff, PRODUCT, TIER, {"haze": float(value)})
        room = max(0.0, cap - paid)
        paid += min(a.payout_sgd, room)
        days += 1
    return paid, days


static = json.loads((REPO / "data/processed/map_static.json").read_text())
stalls_by_region: dict[str, int] = {}
for c in static["hawker_centres"]:
    stalls_by_region[c["region"]] = stalls_by_region.get(c["region"], 0) + c["food_stalls"]
print("stalls by region:", stalls_by_region, sum(stalls_by_region.values()))
rows = []
for year in sorted(daily.year.unique()):
    per_region, total = {}, 0.0
    for region, frame in daily[daily.year == year].groupby("region"):
        paid, days = haze_year_payout(frame)
        per_region[region] = (round(paid, 2), days, int(frame.day.nunique()), int(frame.psi_twenty_four_hourly.max()))
        total += paid * stalls_by_region[region]
    rows.append({"year": year, "island_haze_paid_sgd": round(total),
                 "per_stall_sgd": round(total / sum(stalls_by_region.values()), 2),
                 "south_paid": per_region["south"][0], "south_haze_days": per_region["south"][1],
                 "south_days_with_data": per_region["south"][2], "peak_psi_any_region":
                 max(v[3] for v in per_region.values()),
                 "max_region_paid": max(v[0] for v in per_region.values())})
out = pd.DataFrame(rows).set_index("year")
print(out.to_string())
print("\nCheck against burn_yearly_hero.csv payout_haze_sgd (south): "
      + ", ".join(f"{yr}: burn {hero.loc[yr, 'payout_haze_sgd']} vs here {out.loc[yr, 'south_paid']}" for yr in (2016, 2019)))
print("2015 daily PSI days per region:", daily[daily.year == 2015].groupby("region").day.nunique().to_dict())
d15 = daily[(daily.year == 2015) & (daily.psi_twenty_four_hourly >= 101)]
print(d15.groupby("region").psi_twenty_four_hourly.agg(["count", "max"]).to_string())

print("\n== A. Year-1 cases ==")
STALLS_EXISTING, COOKED_OPERATING, ALL_HAWKER, HDB_SHOPS, WORKERS = 5837, 6665, 11446, 15200, 71600
cases = {
    "low": dict(stalls=300, shops=0, workers=500),
    "middle": dict(stalls=1000, shops=round(0.01 * HDB_SHOPS), workers=5000),
    "high": dict(stalls=round(STALLS_EXISTING * 2 / 3 * 0.5), shops=round(0.03 * HDB_SHOPS),
                 workers=round(0.20 * WORKERS)),
}
for name, c in cases.items():
    people = c["stalls"] + c["shops"] + c["workers"]
    print(f"{name}: {c}  policyholders={people}  persons in households={people * HOUSEHOLD_SIZE:,.0f}  "
          f"stalls share of 5,837={c['stalls'] / STALLS_EXISTING:.1%} of 6,665={c['stalls'] / COOKED_OPERATING:.1%} "
          f"of 11,446={c['stalls'] / ALL_HAWKER:.1%}; shops share of 15,200={c['shops'] / HDB_SHOPS:.1%}; "
          f"workers share of 71,600={c['workers'] / WORKERS:.1%}")
    stall_normal = c["stalls"] * n.paid_per_stall.mean()
    stall_haze = c["stalls"] * y.paid_per_stall
    print(f"   stalls only, island-average Tier 2: normal-year payouts S${stall_normal:,.0f}, "
          f"2026-type year S${stall_haze:,.0f}")
print("two-thirds insured x half of them =", round(STALLS_EXISTING * 2 / 3 * 0.5))
print("stalls with insurance (2/3 of 5,837):", round(STALLS_EXISTING * 2 / 3))

print("\n== C2 extra. 2015 haze only against the same premium pool ==")
pool = isl.loc[2026, "premium_pool_before_gst_sgd"]
print(f"2015 haze-only island paid S${out.loc[2015, 'island_haze_paid_sgd']:,} / pool S${pool:,} = "
      f"{out.loc[2015, 'island_haze_paid_sgd'] / pool:.3f}")
print(f"2015 haze-only per stall S${out.loc[2015, 'per_stall_sgd']}, cap S${cap}, "
      f"share of cap {out.loc[2015, 'per_stall_sgd'] / cap:.0%}")
```

### Output

```
Tier 2: S$40.0/day, 15 days, cap S$600.0
  share of S$500 takings replaced by a full-loss day at tier_1: 4%
  share of S$500 takings replaced by a full-loss day at tier_2: 8%
  share of S$500 takings replaced by a full-loss day at tier_3: 14%
  share of S$500 takings replaced by a full-loss day at tier_4: 20%

== C1. Burn analysis, island (103 centres) ==
      stalls  premium_pool_sgd  premium_pool_before_gst_sgd  payout_sgd  est_lost_sgd  loss_ratio  paid_per_stall  premium_per_stall  replaced
year                                                                                                                                          
2016    5837           2606576                      2391355      180997       2262460       0.076          31.009            446.561     0.080
2017    5837           2606576                      2391355      598073       7475910       0.250         102.462            446.561     0.080
2018    5837           2606576                      2391355      683152       8539400       0.286         117.038            446.561     0.080
2019    5837           2606576                      2391355      710600       8882495       0.297         121.741            446.561     0.080
2020    5837           2606576                      2391355      824488      10306100       0.345         141.252            446.561     0.080
2021    5837           2606576                      2391355      972242      12153020       0.407         166.565            446.561     0.080
2022    5837           2606576                      2391355      941232      11765400       0.394         161.253            446.561     0.080
2023    5837           2606576                      2391355     1098350      13729375       0.459         188.170            446.561     0.080
2024    5837           2606576                      2391355      713556       8919450       0.298         122.247            446.561     0.080
2025    5837           2606576                      2391355     1107559      13844488       0.463         189.748            446.561     0.080
2026    5837           2606576                      2391355     2550484      33556566       1.067         436.951            446.561     0.076
Normal years 2017-2025: mean paid S$849,917, per stall S$145.61, min/max per stall S$102.46/189.75, mean loss ratio 0.355, range 0.25-0.463, mean replaced 8.000%
2026: paid S$2,550,484, per stall S$436.95, pool S$2,606,576, loss ratio 1.067, replaced 7.601%, x normal paid 3.00

== C1. Hero stall (Tiong Bahru, south region) ==
      trigger_days  payout_sgd  payout_haze_sgd  payout_rain_sgd  payout_heat_sgd  est_lost_sgd  premium_sgd  premium_before_gst_sgd  loss_ratio  recovered_share
year                                                                                                                                                             
2016             3       31.20             19.2             12.0              0.0         390.0       515.21                  472.67       0.066             0.08
2017            12      110.00              0.0            110.0              0.0        1375.0       515.21                  472.67       0.233             0.08
2018            14      114.00              0.0            114.0              0.0        1425.0       515.21                  472.67       0.241             0.08
2019            16      143.60             57.6             86.0              0.0        1795.0       515.21                  472.67       0.304             0.08
2020            17      146.00              0.0            146.0              0.0        1825.0       515.21                  472.67       0.309             0.08
2021            20      162.00              0.0            162.0              0.0        2025.0       515.21                  472.67       0.343             0.08
2022            18      132.00              0.0            132.0              0.0        1650.0       515.21                  472.67       0.279             0.08
2023            23      228.00              0.0            228.0              0.0        2850.0       515.21                  472.67       0.482             0.08
2024            15      134.00              0.0            134.0              0.0        1675.0       515.21                  472.67       0.283             0.08
2025            43      332.00              0.0            116.0            216.0        4150.0       515.21                  472.67       0.702             0.08
2026            49      445.36            220.8            154.0             72.0        5567.0       515.21                  472.67       0.942             0.08
Normal 2017-2025 mean paid S$166.84, mean trigger days 19.8, loss ratio 0.353

== C2. Haze only from PSI history, all regions, Tier 2 cooked food ==
stalls by region: {'south': 3265, 'east': 1325, 'central': 741, 'west': 398, 'north': 108} 5837
      island_haze_paid_sgd  per_stall_sgd  south_paid  south_haze_days  south_days_with_data  peak_psi_any_region  max_region_paid
year                                                                                                                              
2014                314371          53.86        67.2                7                   275                  125             67.2
2015               2624054         449.56       473.6               42                   365                  322            492.8
2016                 88704          15.20        19.2                2                   366                  143             38.4
2017                  1037           0.18         0.0                0                   365                  143              9.6
2018                     0           0.00         0.0                0                   365                   91              0.0
2019                517862          88.72       105.6               11                   365                  154            105.6
2020                     0           0.00         0.0                0                   366                   84              0.0
2021                  2074           0.36         0.0                0                   365                  124             19.2
2022                     0           0.00         0.0                0                   365                   75              0.0
2023                 71011          12.17         9.6                1                   365                  123             19.2
2024                     0           0.00         0.0                0                   366                   77              0.0
2025                  1037           0.18         0.0                0                   365                  114              9.6
2026                405974          69.55        48.0                5                   274                  167            153.6

Check against burn_yearly_hero.csv payout_haze_sgd (south): 2016: burn 19.2 vs here 19.2, 2019: burn 57.6 vs here 105.6
2015 daily PSI days per region: {'central': 365, 'east': 365, 'north': 365, 'south': 365, 'west': 365}
         count  max
region             
central     38  268
east        39  285
north       43  302
south       42  322
west        45  321

== A. Year-1 cases ==
low: {'stalls': 300, 'shops': 0, 'workers': 500}  policyholders=800  persons in households=2,448  stalls share of 5,837=5.1% of 6,665=4.5% of 11,446=2.6%; shops share of 15,200=0.0%; workers share of 71,600=0.7%
   stalls only, island-average Tier 2: normal-year payouts S$43,683, 2026-type year S$131,085
middle: {'stalls': 1000, 'shops': 152, 'workers': 5000}  policyholders=6152  persons in households=18,825  stalls share of 5,837=17.1% of 6,665=15.0% of 11,446=8.7%; shops share of 15,200=1.0%; workers share of 71,600=7.0%
   stalls only, island-average Tier 2: normal-year payouts S$145,609, 2026-type year S$436,951
high: {'stalls': 1946, 'shops': 456, 'workers': 14320}  policyholders=16722  persons in households=51,169  stalls share of 5,837=33.3% of 6,665=29.2% of 11,446=17.0%; shops share of 15,200=3.0%; workers share of 71,600=20.0%
   stalls only, island-average Tier 2: normal-year payouts S$283,354, 2026-type year S$850,307
two-thirds insured x half of them = 1946
stalls with insurance (2/3 of 5,837): 3891

== C2 extra. 2015 haze only against the same premium pool ==
2015 haze-only island paid S$2,624,054 / pool S$2,391,355 = 1.097
2015 haze-only per stall S$449.56, cap S$600.0, share of cap 75%
```

### Rerun on the final tariff, 16 Nov 2026

The haze-year numbers in sections 0, A.2, C, E and F come from this rerun.

1. Tier 1: the burn files as committed on branch `production-ready-pricing` (commit `ebe955a`, "Rerun the burn analysis on the final tariff, for a Tier 1 stall").
2. Tier 2: in a scratch checkout of the same branch (commit `b9aaced`), set `TIER = "tier_2"` in `scripts/burn_analysis.py`, run it, copy `data/processed/burn_yearly_island.csv` and `burn_yearly_hero.csv` out, then discard the changes. The Tier 2 files are not committed.

   ```
   uv run python scripts/burn_analysis.py
   ```

   The run printed: "Island 2026: 5,837 stalls would have been paid S$12,205,895 against S$31,297,022 est. losses (pool S$16,982,321, loss ratio 78%)".
3. Put the Tier 1 files in `<dir>/t1/` and the Tier 2 files in `<dir>/t2/`, then run the script below with `<dir>` as its argument.

The results match the pricing page, sections 7.1 and 7.2: 71.8% and 78.3% for 2026, 75.3% and 82.1% for 2015, 29.3% and 32.0% a year over 2017 to 2026, and 17.2% to 33.2% and 18.7% to 36.2% in normal years.

```python
"""Haze-year numbers for the expected-impact note, on the final tariff (branch production-ready-pricing, b9aaced).
Tier 1: data/processed/burn_yearly_*.csv as committed on the branch (ebe955a).
Tier 2: the same scripts/burn_analysis.py with TIER = "tier_2", run in a scratch checkout, files not committed.
"""
import sys
from pathlib import Path
import pandas as pd

base = Path(sys.argv[1])
CAP = {"t1": (35, 45), "t2": (195, 45)}
for t in ("t1", "t2"):
    isl = pd.read_csv(base / t / "burn_yearly_island.csv").set_index("year")
    hero = pd.read_csv(base / t / "burn_yearly_hero.csv").set_index("year")
    n = isl.stalls.iloc[0]
    d, days = CAP[t]
    norm = isl.loc[2017:2025]
    ten = isl.loc[2017:2026]
    print(f"== {t}: S${d}/day x {days} days, cap S${d*days:,}")
    print(f"pool before GST S${isl.premium_pool_before_gst_sgd.iloc[0]:,} (with GST S${isl.premium_pool_sgd.iloc[0]:,}), stalls {n}")
    print(f"normal 2017-2025: mean paid S${norm.payout_sgd.mean():,.0f}, per stall mean S${norm.payout_sgd.mean()/n:.2f} "
          f"(range S${norm.payout_sgd.min()/n:.2f} to S${norm.payout_sgd.max()/n:.2f}), "
          f"loss ratio mean {norm.loss_ratio.mean():.1%} (range {norm.loss_ratio.min():.1%} to {norm.loss_ratio.max():.1%}), "
          f"replaced {norm.payout_sgd.sum()/norm.est_lost_sgd.sum():.1%}")
    print(f"average a year 2017-2026: loss ratio {ten.payout_sgd.sum()/ten.premium_pool_before_gst_sgd.sum():.1%}")
    for y in (2015, 2026):
        r = isl.loc[y]
        print(f"{y}: paid S${r.payout_sgd:,}, per stall S${r.payout_sgd/n:.2f}, est lost S${r.est_lost_sgd:,}, "
              f"replaced {r.payout_sgd/r.est_lost_sgd:.1%}, loss ratio {r.loss_ratio:.1%}")
    print(f"2026 vs normal: {isl.loc[2026].payout_sgd/norm.payout_sgd.mean():.2f} times")
    hn = hero.loc[2017:2025]; h = hero.loc[2026]
    print(f"hero normal: paid mean S${hn.payout_sgd.mean():.2f}, trigger days mean {hn.trigger_days.mean():.1f}, "
          f"loss ratio mean {hn.loss_ratio.mean():.1%}; premium before GST S${h.premium_before_gst_sgd}")
    print(f"hero 2026: paid S${h.payout_sgd} (haze {h.payout_haze_sgd}, rain {h.payout_rain_sgd}, heat {h.payout_heat_sgd}), "
          f"trigger days {h.trigger_days}, est lost S${h.est_lost_sgd}, replaced {h.payout_sgd/h.est_lost_sgd:.1%}, loss ratio {h.loss_ratio:.1%}")
```

Output:

```
== t1: S$35/day x 45 days, cap S$1,575
pool before GST S$3,050,651 (with GST S$3,325,210), stalls 5837
normal 2017-2025: mean paid S$749,543, per stall mean S$128.41 (range S$89.65 to S$173.39), loss ratio mean 24.6% (range 17.2% to 33.2%), replaced 7.0%
average a year 2017-2026: loss ratio 29.3%
2015: paid S$2,296,048.0, per stall S$393.36, est lost S$32,800,680.0, replaced 7.0%, loss ratio 75.3%
2026: paid S$2,190,799.0, per stall S$375.33, est lost S$31,297,022.0, replaced 7.0%, loss ratio 71.8%
2026 vs normal: 2.92 times
hero normal: paid mean S$130.59, trigger days mean 17.2, loss ratio mean 24.5%; premium before GST S$532.27
hero 2026: paid S$389.69 (haze 193.2, rain 134.75, heat 63.0), trigger days 49.0, est lost S$5567.0, replaced 7.0%, loss ratio 73.2%
== t2: S$195/day x 45 days, cap S$8,775
pool before GST S$15,580,111 (with GST S$16,982,321), stalls 5837
normal 2017-2025: mean paid S$4,176,023, per stall mean S$715.44 (range S$499.50 to S$966.01), loss ratio mean 26.8% (range 18.7% to 36.2%), replaced 39.0%
average a year 2017-2026: loss ratio 32.0%
2015: paid S$12,792,265.0, per stall S$2191.58, est lost S$32,800,680.0, replaced 39.0%, loss ratio 82.1%
2026: paid S$12,205,895.0, per stall S$2091.12, est lost S$31,297,022.0, replaced 39.0%, loss ratio 78.3%
2026 vs normal: 2.92 times
hero normal: paid mean S$727.57, trigger days mean 17.2, loss ratio mean 26.8%; premium before GST S$2718.34
hero 2026: paid S$2171.13 (haze 1076.4, rain 750.75, heat 351.0), trigger days 49.0, est lost S$5567.0, replaced 39.0%, loss ratio 79.9%
```
