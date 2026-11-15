# Notion decisions sweep, 15 Nov 2026

Read-only sweep of the SafeDay Notion workspace. Nothing was edited in Notion.
Swept at about 15:30 SGT on 15 Nov 2026. Notion edits all day, so re-check before you quote a number.

## How to read this file

- Confidence: **final** (locked or built and tested), **likely final** (stated as the design, not formally locked), **conflicting** (two sources disagree), **not found**.
- "Pricing page" = "SafeDay pricing for review: loss, payout, premium and profit", https://app.notion.com/p/419ecd5c15be8153a239c8c2a05f3af0 (last edited 15 Nov 07:27 UTC). Its values are for branch `align-pricing-and-payouts`, not yet merged to `main`.
- "Master List" = "Pitch, Features & Proposal - Master List", https://app.notion.com/p/419ecd5c15be813597e4d97c132a1574 (last edited 15 Nov 04:21 UTC). It is older than the Pricing page. Where they differ, the Pricing page wins.
- "Global Doc" = https://app.notion.com/p/418ecd5c15be8067be83f96e72b640f0 (Singapore Hackathon Global Doc (REAL)).
- TODO rows are cited by title and URL. Date and author come from the row comment text.
- Time stamps in comments such as "LOCKED 15 Nov 09:28 (Sky)" are as written by the team. Time zone not stated.

## Source limits

- Notion comments (discussion threads) are sparse. Only one thread exists on the Pricing-related pages: Dewa, 15 Nov 2026 07:21 UTC, on the source-of-truth row (https://app.notion.com/p/419ecd5c15be81aeaacfe38b0347d69e). Most "comments" are in the TODO `Comment` column.
- The public 1 PM Industry track Q&A notes (15 Nov, Connexion) are NOT in Notion. The only record of what Income said is the six `[FROM INCOME Q&A]` TODO rows. The transcript of the earlier 29 Oct industry session is in the repo (`docs/notes/transcript-2026-10-29-industry-track-sharing.md`), not Notion.
- The private Income mentoring session answers are NOT recorded. The tally row is still To do.
- The meeting-notes query tool needs a Business plan, so it did not run. Meeting notes were found by search and fetch.
- A page named "review the payout calculation and unit economics with the following doc" (https://app.notion.com/p/419ecd5c15be8044b838de8a487f57df) holds only an alias block that this tool cannot read. Its likely target is the page "review calculation with this if have missed anything" (https://app.notion.com/p/419ecd5c15be80aea731ef0a87347aa4). That page is an unsigned analysis, not a decision. Its author is not shown. It reads like a Claude-style review.

---

## 1. Tiers

| Item | Final decision | Source | Confidence |
| --- | --- | --- | --- |
| Number of tiers | 4. Standard tiers. Custom needs go through a contact form. | TODO "Number of allowed days per tier..." (https://app.notion.com/p/fceecd5c15be8395b842813442bf146c): "Tiers decided 14 Nov (Ashutosh meet): standard tiers, custom needs via contact form." Also Master List section 4, decision 14 Nov. | final |
| Names | Tier 1, Tier 2, Tier 3, Tier 4. No marketing names found. The meeting talked of "A B C D" tiers, but nobody chose names. | Global Doc "Decisions made in meet" list; Pricing page Part 1 step 4 | final (names); "A B C D" not adopted |
| Daily amount (full lost day) | Tier 1 S$20, Tier 2 S$40, Tier 3 S$70, Tier 4 S$100 | Pricing page Part 1 step 4; Master List section 1 | final |
| Most paid days a year | 10 / 15 / 20 / 30 | Pricing page Part 1 step 4 | final |
| Most paid money a year | S$200 / S$600 / S$1,400 / S$3,000 | Pricing page Part 1 step 4 | final |
| Days-per-tier check | Median centre expects 5.7 full-loss days a year. No centre reached 10 days in 2017 to 2025. In 2026, 9% to 19% of stalls reached 15 days. Verdict: "10 / 15 / 20 / 30 days work." | TODO row above (comment, 15 Nov); "Pricing tested against Devnavin's hawker cost data (15 Nov)" section 5 (https://app.notion.com/p/419ecd5c15be81e98f1cde88b4d26070) | final |
| How a tier is recommended | The platform suggests the smallest tier whose daily amount covers one day of the centre's rent. If none does, Tier 4. Rent per day = monthly rent / 26 trading days. Rent is a tier hint only. Rent never changes the price. | Pricing page Part 6 "Rent and the suggested tier (`/api/rent`)"; checklist item 22 = Done | final for the code. The 26-day vs 30.4-day split is open (item 21). |
| Rent as a story for the tiers | "Tier 3 (S$70) pays about one day of a typical stall's rent and charges (S$71)." Suggested SMS line. Whether to use it is "for the team to decide". | Pricing page Part 2; "Pricing tested..." section 4 | likely final (explanation), not locked |
| Rent classes | Lower under S$1,500, mid S$1,500 to S$3,000, high S$3,000 or more | Pricing page Part 6 | final (display only) |
| Tier change | Changing tier restarts the 30-day wait (listed as a code gap D17) | TODO "[FROM PS DOC] Claim parameters + exclusions list" (https://app.notion.com/p/d8eecd5c15be832390e201bb337b1eb4), Dewa, 15 Nov | final as built. Not discussed with Income. |
| Rent as a pricing factor | NOT allowed. Rent and prosperity may not load the premium (FEAT). Rent and weather risk are unrelated (correlation -0.17). | Master List section 4 (15 Nov); TODO "Check PS: are extra layers (crime rate etc.) in scope" (Sky) | final |

### Tier conflict to know about

- A tier can cost more a year than it can ever pay. Source: Pricing page checklist item 39 and Dewa's comment (15 Nov 07:21 UTC). Examples: South region cooked food, Tier 1 = S$341.61 a year against a S$200 maximum. Tier 2 = S$683.22 against S$600. At location prices, Tier 1 costs at least its S$200 maximum at 59 of 103 centres, Tier 2 at 9, Tiers 3 and 4 at 1 (Telok Blangah Rise). Status: **Needs input**. See open decisions.

---

## 2. Premium formula

| Item | Final decision | Source | Confidence |
| --- | --- | --- | --- |
| Formula | Premium a year = expected payout x 1.25 / 0.75 x 1.09. Weekly price = yearly / 52. | Pricing page Part 3; checklist item 8 = Done (factor 1.81667 on all four tiers) | final (as built) |
| Expected payout | Expected bad days (up to the yearly limit) x daily amount. Bad days come from a replay of NEA history through the loss rules. | Pricing page Part 3 step 1 | final |
| Uncertainty load | 15% of expected payout. Assumed. | Pricing page Part 3 table | likely final. Item 32 says "For the mentors and the reviewer." |
| Rare event (catastrophe) load | 10% of expected payout. Assumed. | same | likely final. Still open (see below). |
| Running costs | 25% of premium before GST. Assumed. Divide by 0.75. | same | likely final. Master List section 4 "pending: Expense ratio 25% (ours) vs ~20% (PS) - ask Income". |
| Target loss ratio | Payouts = 60% of premium before GST (1 / 1.25 x 0.75 = 0.60). Combined ratio 85%. Margin 15%. | Pricing page Part 3 and Part 4; Pricing API doc (https://app.notion.com/p/f1cecd5c15be826b8b29810ef1f1f566) | likely final (design target) |
| GST | 9%, added on top. Passed to IRAS. Running costs are a share of the premium before GST. | Pricing page Part 3; Reviewer question 8 | final |
| S$100 split | Of S$100 paid: GST S$8.26, payouts S$55.04, running costs S$22.94, profit S$13.76. | Pricing page Part 4; proposal v4 (https://app.notion.com/p/418ecd5c15be81cc95f1edaeb99e3a46) | final. See conflict below. |
| Billing | Flat weekly rate on a 12 or 24 month term. No surge pricing. No deposits. | Global Doc green LOCKED callout (15 Nov 09:28, Sky); TODO "DECIDE: incentive-based pricing ideas from the mentor call" (https://app.notion.com/p/418ecd5c15be81dab2acc21cd37b6981) | final |
| Weekly vs monthly | Weekly price shown (yearly / 52). The PayNow request is the weekly amount. A monthly option was not found. Mentor/Q&A "per month" appears only in the PS benchmark wording ("a few dollars a week or month"). | Pricing page Part 6 "Buying and the policy" | final (weekly). Monthly: not found |
| Affordability target | PS benchmark: "a few dollars a week or month"; Asia-Pacific microinsurance average about US$13 a year; Philippines 7.5% of the daily minimum wage; expenses about 20% of premium. The check row is still **To do**. No team-set numeric target was found. | TODO "[FROM PS DOC] Affordability check against PS benchmarks" (https://app.notion.com/p/da0ecd5c15be834a8f340106bee9e708), Dewa, P2, To do | not found (no locked target) |
| Affordability evidence in hand | Tier 1 cooked food S$2.85 to S$6.99 a week by place (median S$3.98). Tier 2 S$5.70 to S$20.96 (median S$7.95). Tier 2 is a median 1.7% of monthly rent (Tier 1: 0.8%). About 0.2% of operating costs. Verdict "owner pays holds, no subsidy". Master List warns it is above the APAC average of about US$13 a year. | Pricing page Part 3; "Pricing tested..." section 6; Master List section 7 | likely final |
| Price floor / ceiling | No official floor or ceiling found. The map shows an "underwriting hint": offer if weekly premium is S$3 or less, offer with co-pay up to S$6, otherwise refer to an underwriter. These limits are hard-coded with no source. | Pricing page Part 6 "Map labels"; checklist item 30 = Needs input | conflicting / open |
| Minimum payout transfer | A S$2 minimum transfer was PROPOSED (hold smaller sums to the next payable day or month end). Not decided. Source is the unsigned "review calculation..." page. | https://app.notion.com/p/419ecd5c15be80aea731ef0a87347aa4 | not decided |
| Price basis | Hawker pays its centre's price. Shop pays its postcode area's price. Platform worker pays its region's price. Example: Maxwell Tier 2 = S$9.27 a week (region price would be S$13.14). | Pricing page Part 6 and checklist item 11 = **Fixed in PR** | likely final. Live only after the PR merges. |
| Region prices (Tier 1 cooked food, weekly) | East 3.63, West 5.28, North 5.46, Central 6.00, South 6.57 | Pricing API doc; Master List section 5 | final |
| Pricing story order | Income's product lead asked: start with the target customer and what they can afford, then coverage, benefits, risk retention, price. | TODO "[FROM INCOME Q&A] Reorder the pricing story..." (https://app.notion.com/p/419ecd5c15be81f18b1dc27f46700ce4), P0, Deval, To do | final request; not yet applied |

### Conflicts in section 2

- **S$100 split.** Master List section 5 says "Two S$100 splits exist. Pick one" (60/25/15 vs 55.04/22.94/13.76). The "review calculation..." page says they are the same. 60/25/15 is the share of premium before GST. 55.04/22.94/13.76 is the same split on S$100 including GST (plus S$8.26 GST). Treat as **one split, two bases**. The Master List flag is stale.
- **Payout share.** Design target is 60%. The Pricing page says the Maxwell replay pays 42% of premium before GST over ten years (item 26, Needs input). The "review calculation..." page says about 52% in a normal year and 105% in 2026. The Master List and proposal say 30% (ten-year) and 76% (island, 2026). Dewa's comment says now 36.7% over ten years, 90.8% hero stall and 101.6% island for 2026. The Pricing API doc says 147% (1,000 customers, 2026). These use different methods and dates. **Do not quote any of them without naming the method.** Use the Pricing page Part 4 table for the story: "As designed 60%", "Normal years 41% to 62%", "2026 haze year 147%".
- **Profit per policy.** Proposal v4: about S$82 a policy, S$24,575 for 300 stalls. The "review calculation..." page says about S$94 at region-to-location prices and 52% payouts, with a loss of about S$125 per policy in 2026. Not decided.
- **Rain price vs rain paid.** The Pricing page says the price counts about 13% more rain days than the trigger pays. The "review calculation..." page says 22% (4.19 priced vs 3.26 paid). Both agree the price is on the safe side. Whether to re-price rain is open (item 26).

---

## 3. Payout rule

### Triggers and thresholds (Pricing page Part 1; checklist items 1 to 5 = Done, 75 of 75 live checks)

| Hazard | Reading | Step 1 (30%) | Step 2 (60%) | Step 3 (100%) | Weight | Confidence |
| --- | --- | --- | --- | --- | --- | --- |
| Haze | Highest 24-hour PSI of the day in the stall's region | PSI 101 | PSI 201 | PSI 301 | 0.8 | final (haze from day 1, locked 15 Nov 10:52, Sky) |
| Rain | Wettest hour 7am to 7pm, middle value of the 3 nearest reporting NEA gauges (nearest plus any within 5 km) | 20 mm | 30 mm | 50 mm | 0.5 | final (our bands, assumed) |
| Heat | Hours 7am to 7pm at WBGT 32C or more, nearest reporting WBGT station | 2 hours | 4 hours | 6 hours | 0.4 | final. NEA 31/33 alignment row (https://app.notion.com/p/e81ecd5c15be8204952981c499d24b94) still To do, P2. |
| Flood | PUB flood alert near the stall in trading hours | | | alert on (80% loss at weight 0.8) | 0.8 | final |
| Closure | Government order | | | order in force = 100% for every product | 1.0 | final (rider-only story; not climate) |

- Severity steps (30/60/100%) and rain/heat levels are **assumed**. PSI bands and 32C WBGT are **measured** (NEA bands, MOM rest-break rule).
- Heat 32C: documented 14 Nov (Master List section 4). Reason: MOM rest-break level, not NEA 31/33.
- Haze day 1 vs day 2: **DECIDED 15 Nov 10:52 (Sky)**, row "Align the haze trigger between docs and code" (https://app.notion.com/p/418ecd5c15be81ac8ae7d07b96f798f6). Day 1 pays. The older "day 2" rule is dropped. Deck sentence given in the row.
- Flood: **DECIDED 15 Nov 10:52 (Sky)**, row "Flood is a trigger without a price" (https://app.notion.com/p/418ecd5c15be81cf9985f5a68aa8f993). Flood pays on a live PUB flash-flood alert. It is NOT priced (0 days a year). Disclose on the limitations slide. No placeholder price. If PUB sends data, price it.
- Flood code gap: per Dewa (row "Claim parameters + exclusions", 15 Nov) flood paid only on an insurer manual run, not on a live alert (gap D6). Check whether this is fixed.

### Partial payouts and the loss score

- Day's loss = 1 - (1 - haze loss) x (1 - rain loss) x (1 - heat loss). Loss from one hazard = weight x severity x product share. Closure = 100%. Source: Pricing page Part 1. Confidence: final.
- Payout = day's loss x tier daily amount. One payout a day. Never above the yearly limit. Source: same. final.
- Product shares: cooked food 1.00, flowers 0.45, fresh produce 0.35, packaged food 0.11, general goods 0.11, platform work 0.42 (assumed). Source: Pricing page Part 1 step 2. final.
- Worked example: PSI 230 + 35 mm rain gives 63.6% loss and S$25.44 for cooked food on Tier 2 (yellow day).

### Green / yellow / red

- Green under 30%. Yellow 30% to under 70%. Red 70% to 100%. Grey for no payout.
- **DECIDED 15 Nov (Deval)**, row "Red day / yellow day payout amounts" (https://app.notion.com/p/8c7ecd5c15be82348aa101a27b8c791c). Built by Dewa, commit a2564cb, row https://app.notion.com/p/419ecd5c15be81319027eea33f25e55d.
- The colour is a label for the SMS and map. The payout is still % loss x daily amount, so a green day still pays a small amount. Confidence: **final**.
- Old naming conflict: the page "Pricing tested..." section 4 names bands by hazard ("Yellow haze PSI 101 to 200", "Red haze PSI 201 to 300"). That is the old naming. The final rule colours by total day loss. Use the Pricing page version.
- Hazard weights "stay as in the current tariff until the mentors review them" (Deval, same row). Open.

### Station reading rule

- Rain: middle of the 3 nearest reporting gauges within 5 km, else MSS daily record for the nearest gauge, else wait for data (no payout row; a later run pays). Heat: nearest reporting WBGT station, same fallback. Haze: region PSI, else median of regions that reported. Skipped station = under half its work-hour data that day.
- Source: TODO "[FROM PS DOC] Feed-failure fallback rule" (https://app.notion.com/p/e6aecd5c15be82e3a75381bf3d481459), Dewa, commit 3682dba, 15 Nov; Pricing page Part 6 and items 12, 13 (Fixed in PR). Confidence: **final**, merged to `main` for the fallback (3682dba). The 3-gauge median is in the PR branch.
- Basis-risk finding (Dewa, 15 Nov, row https://app.notion.com/p/733ecd5c15be839b97068196e21eb738): nearest-gauge rule misses 37.7% of 20 mm storm days. Worst-of-2 would miss 23.3% but raise false alarms. Recommendation only. No product change. Heat nearest-station rule misses 85.6%. Open for Deval.

### Waiting period

- **30 days. LOCKED 15 Nov 09:28 (Sky)**, row "Decide when cover takes effect" (https://app.notion.com/p/80eecd5c15be825ab94681a402fab1ad). It replaced the 10-day idea in the row title and the 7 days in proposal v4. Wired by Dewa on 15 Nov (payout run pays nobody inside 30 days). Confidence: **final**.
- Left open in that row: "ask Income today whether 30 is their norm; if they say otherwise, that overrides." No answer recorded.
- Stale: the proposal PDF and LaTeX still say 7 days (proposal page "Before the final version"; checklist item 19). Fix before submission.
- A forecast may still be shown during the wait.

### Term

- **12 or 24 months**, flat weekly rate. LOCKED 15 Nov 09:28 / 09:28 (Sky) in the Global Doc callout and row "DECIDE: incentive-based pricing ideas...". Cover stops on the day the term ends; no re-buy from the dashboard after the term (items 18, 38 = Fixed in PR). Confidence: **final**.

### Yearly limit window

- Design intent: policy year. The proposal, the pricing and the SMS ("max S$600 a year") assume it. Code: rolling 365 days per person across all their policies. Replay: calendar year. Source: Pricing page checklist item 16 = **Needs input**; "review calculation..." page point 2 suggests a per-policy-year fix.
- Applying the limit to the average year (not each year) is fine, per the "review calculation..." page point 2 of Task 3 (capping each year would lower Tier 1 by only 5.7%). Pricing page reviewer question 5 still lists it as open. Confidence: **conflicting / open**.
- Yearly limit as a count of days, not money: the row "Claim parameters + exclusions" (D10) says code caps money over 365 days, not days. The Pricing page Part 6 step 5 now says: "daily amount x limit days, minus everything paid in the last 365 days". Treat as money-based.
- Proposed rule: limit = 5 x expected bad days (item 33). **On hold for the mentors.**

### Other locked rules

- One payout per person per day. Automatic on a public NEA reading. No claim form. Payouts by PayNow with SMS. Source: Pricing page Part 6 "Real payouts".
- Challenges: about the reading, station or classification, never the size of the loss. Proof submitted online. Manual or AI-assisted check. LOCKED 15 Nov, Sky. Row "Dispute / challenge flow" (https://app.notion.com/p/abdecd5c15be834e99008135932f9684) is still To do for Rafael (design of the screen). final (decision), not built.
- If the vendor stays open and the trigger fires, the full amount is still paid. Devnavin, row https://app.notion.com/p/79cecd5c15be83288b8201c0604d49b4. likely final.
- Anti-selection: 30-day wait + sales freeze during an NEA advisory + 12/24 month term. Not by price. LOCKED 15 Nov 09:28 (Sky). The sales-freeze rule is NOT built (D13) and is listed as "still open" in the proposal page.
- No surge pricing. No security deposits. LOCKED 15 Nov 09:28 (Sky). This differs from Ashutosh's 14 Nov advice (surge on forecast, deposits). Row "Realign with Ashutosh tonight" (https://app.notion.com/p/419ecd5c15be81738290d69ca2adf789) is To do.
- Health, injury and medical cover: out. Income loss only. Source: row "Recheck whether the PS covers only income-loss..." (Sky, 14 Nov).
- Pricing inputs allowed: flood-proneness, regional PSI, local rain/heat frequency, trend, exposure. Not allowed: crime, rent/prosperity, race/religion/gender/age. Master List section 4 (15 Nov). final.
- Who pays: SME 100% as an add-on to SmartBiz 360 / Stallholder; platform worker 50/50 with the platform (our design; do not say "as per law"); no permanent subsidy. LOCKED 15 Nov 12:21 (Sky), row https://app.notion.com/p/e48ecd5c15be83eea03e01100b5c1616. final. Still open: what a platform worker buys (row https://app.notion.com/p/419ecd5c15be8101b511ebfa15fd9361).
- Target groups: hawkers and neighbourhood shops yes; platform workers "??" at 14 Nov, now built in the buy flow; home-based "No prolly". Households on paper only.

---

## 4. What Income and the mentors asked for

All six rows were created 15 Nov 05:44 UTC, assigned to Deval, P0, To do. The speaker is "Income's product lead" or "Income's head of AI". Names are not recorded.

| Ask | What was said (as recorded) | Source | Status |
| --- | --- | --- | --- |
| Assumptions list | Listing assumptions is "very important". "As long as it's logical, with some substantiation, the product will work." Put it on one slide and one proposal page, with value and substantiation. List to include: severities 30/60/100%, rain and heat bands, hazard weights, demand lost and recovered share, loads 15% and 10%, expenses 25%, S$500/day takings, reinsurance and distribution costs once set. | https://app.notion.com/p/419ecd5c15be813c8a6de58c5207ef45 | open to do |
| Distribution cost | "Your acquisition cost is going to be very high." Count awareness, marketing and channel costs as a % of premium. It must fit in the 25% expense line, or the 25% changes. PS says about 20%. | https://app.notion.com/p/419ecd5c15be816db6c5ca615e992787 | open to do |
| Five premium components | Show the premium by Income's five names: loss ratio, reinsurance cost, management expenses, selling and distribution cost, expected profit. We have no reinsurance cost line. Profit is stated before reinsurance. | https://app.notion.com/p/419ecd5c15be8189bef5c5bfd52ab8cf | open to do |
| AI in three places | Distributing the product (shop reader built), handling claims (no claim form; AI assists on challenge only), weeding out abuse (challenge checks and sign-up checks designed, not built). Keep AI out of the payout decision. | https://app.notion.com/p/419ecd5c15be81aaad85fcbaf5631df4 | open to do |
| Haze reinsurance | She asked which: keep in-house, an excess layer, or a percentage ceded. "A logical, substantiated assumption is enough." Inputs: 2026 haze year = 147% payouts on 1,000 customers; 76% island loss ratio in the burn analysis; 10% catastrophe load. | https://app.notion.com/p/419ecd5c15be81c6b255da3d03e1bb72 | open to do |
| Pricing story order | Target customer and what they can afford, then coverage, benefits, risk retention, price. | https://app.notion.com/p/419ecd5c15be81f18b1dc27f46700ce4 | open to do |
| Automation ladder | Head of AI: copilot first, then automatic action on confident cases, then full automation once proved. Income's own LLM uses: document verification, content generation checked by a second agent. | https://app.notion.com/p/419ecd5c15be8109a6e9f780a6889832 | open to do |

- Q&A process: 22 questions went to the 1 PM group Q&A; "none was answered directly". They were cut to 16 assumption-first questions for the private session. Source: row https://app.notion.com/p/114ecd5c15be835aa83d81234b12d9ec (Devnavin, 15 Nov).
- That page also holds a draft mentor-style question: premium "about S$728" and maximum payout "about S$2,000", plus a per-event cap with a reset (15 days per event, annual cap). **S$728 / S$2,000 matches none of the four tiers** (Tier 2 = S$600 a year maximum). Its source is not stated. Treat as an unverified figure. Do not quote it.
- Per-event limit with reset vs the annual cap: raised by the team as a question. No answer recorded. The cross-check row (https://app.notion.com/p/419ecd5c15be81ce96a4d7c217aa82fa, Sky, Done) lists it as "yearly cap of paid days (vs the per-event limit + reset we asked about)". Result of the cross-check is not written in the row.
- Earlier mentor input (Ashutosh, 14 Nov, "Meeting with Ashutosh", https://app.notion.com/p/418ecd5c15be8199b45ddd5d64c2d9fd): use the government MSME classification; standard tiers; clone an existing insurance app; confusion matrix for the model; project to 2030/2035/2040; offline LLM to explain only; surge pricing on forecast and deposits (later dropped).
- Mentor sessions pending: row "Final tally after all three mentoring sessions today" (https://app.notion.com/p/419ecd5c15be8133a52ce2d237350777) is To do. Row "Tally after the private Income mentoring session" (https://app.notion.com/p/419ecd5c15be81fca7a0e2c527f33626) is To do. **No private-session answer exists in Notion yet.**

### The "5x" value expectation

- **Not found.** No page, row or comment says a customer should get at least 5x back.
- Other "5" numbers that may be confused with it:
  - Tier 2, 3, 4 cost 2x, 3.5x and 5x Tier 1 (the same ratio as the daily amounts). Pricing API doc; Pricing page Part 3.
  - Item 33: yearly limit proposed at 5 x expected bad days. On hold for mentors.
  - What-if circle adds 5 extra bad days a year as a stress test (item 24, Needs input).
  - "One haze year wipes out about 5 normal years of margin." Pricing API doc; Master List section 8.
- What the data say about "money back" (computed from the Pricing page Part 6 table, my arithmetic, not a team decision):
  - Hawker, Maxwell, Tier 2: pays S$482 a year; expected payout S$265 (0.55x); 2026 received S$432 (0.90x); most possible S$600 (1.24x premium).
  - Shop, 380123, Tier 2: pays S$44; most possible S$600 (13.6x premium); expected S$24.
  - Rider, north, Tier 2: pays S$238; most possible S$600 (2.5x); expected S$131.
  - So "5x back" is not true on expected payouts for any customer. It is true only as "maximum payout vs premium" for the shop. A claim of 5x needs an explicit decision and a clear basis.

---

## 5. Open decisions

Owner = row assignee or the person named in the source. "Needs input" is the Pricing page status.

| # | Open decision | Owner | Source |
| --- | --- | --- | --- |
| 1 | A tier can cost more than it can pay (item 39). Options: more paid days on low tiers; limit of 5 x expected days (item 33); do not offer a tier where premium passes a set share of its maximum; lower load once the limit binds. | Deval (pricing); flagged by Dewa, 15 Nov 07:21 UTC | Pricing page item 39; comment on https://app.notion.com/p/419ecd5c15be81aeaacfe38b0347d69e |
| 2 | Loads and running costs: 15% / 10% / 25%. Expense ratio 25% vs PS 20% vs Income 35.5%. Should the 10% load be sized from a 1-in-100 year loss? | Mentors and reviewer; Deval | Pricing page item 32 and reviewer questions 1 to 3; Master List section 4 |
| 3 | Replay pays 42% of premium (Maxwell) against the 60% target. Lower the price? Re-price rain from the median-of-3 daily series? | Deval | Pricing page item 26 |
| 4 | Yearly limit window: policy year, rolling 365 days or calendar year. Which one does the SMS promise? | Deval and Rafael (payout code) | Pricing page item 16 |
| 5 | Yearly limit rule 5 x expected days. | Mentors | Pricing page item 33 |
| 6 | Haze: reinsurance (excess layer, percent ceded, or in-house) and its cost; or a whole-book limit. | Deval | row https://app.notion.com/p/419ecd5c15be81c6b255da3d03e1bb72; Pricing page reviewer question 6 |
| 7 | Rent per day: 26 trading days (code) or 30.4 calendar days (page). | Deval | Pricing page item 21 |
| 8 | Takings S$500 a day: add a source, or let each stall enter its own (S$50 to S$20,000 allowed now). Master List cites S$400 to S$800. | Deval / Dewa | Pricing page item 23 |
| 9 | Map underwriting hint (S$3 and S$6). Agree the limits or remove. | Deval | item 30 |
| 10 | Stress test (+5 days) in the what-if circle: keep or remove. | Deval | item 24 |
| 11 | Flood and closure prices (both 0). Flood waits for PUB data (requested 14 Nov). | Deval (data chase) | item 31; row https://app.notion.com/p/418ecd5c15be811390e3c701f4c5463f |
| 12 | `ml/backtest.py` divides by premium including GST. Needs a model re-run. | Bhoomi (ML owner) | item 37; row https://app.notion.com/p/419ecd5c15be81138a45cb4940c33d85 |
| 13 | Insurer view shows no payouts, costs or profit. | Deval / Dewa | item 27 (Not done) |
| 14 | Growth projection 2030 / 2035 / 2040. | Deval; India team (TAM) | item 34; rows https://app.notion.com/p/418ecd5c15be81498754fc8acf72d55a and https://app.notion.com/p/418ecd5c15be81d19089df1135705fd9 |
| 15 | Proposal PDF says 7-day wait. Change to 30. | Devnavin (proposal owner) | item 19; proposal page |
| 16 | What does a platform worker buy? "SmartBiz 360 base package" row does not fit riders. | Sky | row https://app.notion.com/p/419ecd5c15be8101b511ebfa15fd9361 |
| 17 | SmartBiz 360 attachment: endorsement or standalone. Ask Income. | Dewa | row https://app.notion.com/p/a94ecd5c15be8324a81301f275c825f8 |
| 18 | Worksite vs station heat gap. Ask Income how to handle. | Devnavin | row https://app.notion.com/p/e81ecd5c15be823ea5ef810fec0f4a4f |
| 19 | Heat trigger: keep 32C or align to NEA 31/33. Document why 32C. | Dewa (P2) | row https://app.notion.com/p/e81ecd5c15be8204952981c499d24b94 |
| 20 | V3 climate trend load: is it in the price? | Bhoomi | row https://app.notion.com/p/0c7ecd5c15be83e4994a015c01009f29 |
| 21 | Rider reading: a region-wide share of gauges may suit riders better than the mid-region point. "For the team to decide later." | Deval | Pricing page, end of Part 6 |
| 22 | Minimum transfer of S$2 and a hold for small payouts. | Deval (code owner Rafael) | "review calculation..." page |
| 23 | Distribution cost as a % of premium and its place inside the 25%. | Deval | row https://app.notion.com/p/419ecd5c15be816db6c5ca615e992787 |
| 24 | Income's five-name premium build-up, with a reinsurance line. | Deval | row https://app.notion.com/p/419ecd5c15be8189bef5c5bfd52ab8cf |
| 25 | Dispute screen and verification steps. Sales-freeze, 14-day activity rule and unpaid-plan exclusion not built (D12 to D14). Payout runs are started by the insurer, not scheduled (D15). | Rafael; Dewa | rows https://app.notion.com/p/abdecd5c15be834e99008135932f9684 and https://app.notion.com/p/d8eecd5c15be832390e201bb337b1eb4 |
| 26 | Payout timing: same day or end of day. | Unassigned | row https://app.notion.com/p/e63ecd5c15be82199aab01109fcf1fe7 |
| 27 | Record the private Income session answers. Check each locked decision. | Sky | rows https://app.notion.com/p/419ecd5c15be81fca7a0e2c527f33626 and https://app.notion.com/p/419ecd5c15be8133a52ce2d237350777 |
| 28 | Merge the PR `align-pricing-and-payouts` ("PR to be opened"). Live site still shows the old region price at purchase. | Deval | row https://app.notion.com/p/419ecd5c15be81aeaacfe38b0347d69e (Needs testing) |
| 29 | Event cover, El Nino opt-in, risk-reduction element. | Unassigned / Sky | P2 rows |

Counts as of the Pricing page: 13 Done, 12 Fixed in PR, 1 In progress, 12 Needs input, 1 Not done, 0 Misaligned. The row comment on the source-of-truth todo says 11 Needs input, so the counts are not in sync.
Order given on the Pricing page for the open decisions: 39, 32, 26, 16, 21, 19.

---

## 6. Wow factor and sales framing

| Item | What is recorded | Source | Confidence |
| --- | --- | --- | --- |
| "Up to N times what you pay" | **Not found.** | n/a | not found |
| One-liner | "Parametric climate-income cover for Singapore hawkers and small shops, offered with Income... a fixed daily amount is paid to the stallholder, same day, no claim form." | Master List section 1 | final |
| Speed | Same day, automatic. Compared with 6 to 8 weeks (SEWA). Warning: do not say "within the hour". Code still needs an insurer to start the run; speed not measured. | Master List section 2; row "[FROM PS DOC] Expected impact" (https://app.notion.com/p/1f4ecd5c15be83d9bc3781aa57342782), Dewa, 15 Nov | likely final |
| Value message already used | "Up to S$200-600 per stall in a haze year"; "S$2.85-6.99 a week vs Stallholder S$109-262 a year". Master List also records: Tier 1 from S$2.85 a week. | Master List sections 2 and 5 | conflicting. Dewa's comment says the "Master List haze numbers are stale". |
| Customer pitch examples | Hawkers near offices and schools on hot or wet days; tourism-area vendors; Grab drivers in heat; sports-ground rentals. | Global Doc "Decisions made in meet"; row https://app.notion.com/p/418ecd5c15be818fa5f0dff3bc055519 | final |
| 10-year history story | Show vendors their own 10-year history: what they would have been paid. | rows "Burn analysis..." and "Show vendors their history" (Done) | final |
| Hero stall numbers | Tiong Bahru, Tier 2: 223 payable days in 10 years; paid S$2,029 vs premium S$6,832; 30% loss ratio; 2026: 52 days, 68%. Dewa's comment (15 Nov) says these are stale: now 90.8% (hero) and 101.6% (island) for 2026, and 36.7% over ten years. | Master List section 5; Dewa comment | conflicting |
| Maxwell example | Tier 2 chicken rice stall pays S$9.27 a week (S$482 a year). Replay: S$1,878 paid on 223 days (2017 to 2026) against S$4,818 premium, 42% of premium. | Pricing page Part 6 | final (branch) |
| Competitors | Do NOT say "first mover" or "within the hour". Swiss Re HazeShield (2018) already pays businesses for haze income loss with no damage. Say: "no product we found pays hawkers, small shops or platform workers for income lost to heat, rain or haze." Better on reach, four hazards in one, open triggers, low entry price. Worse on basis risk, no claims history, needs Income and a platform partner. 9 products compared (SmartBiz 360 BI, Stallholder, Grab Partner Cover, Etiqa, HazeShield, Singlife Rainfall, Droplet, SEWA, Igloo x DANA). "SmartBiz from $180/yr" has no source. | Row "[FROM PS DOC] Market competitiveness" (https://app.notion.com/p/ccdecd5c15be822380a1819a24e22c05), Dewa, 15 Nov | final |
| Value vs market loss ratio | "Customers get more back than from most general insurance: 60% against the market's 50% and personal accident's 32-39%." | Pricing API doc | likely final. The replay shows 42% to 52%, not 60%. |
| Honest limits slide | Nine limits, including no sales data, 22 months of real heat data, flood at zero, expense ratio 25% vs 20%, one haze year wipes out five normal years. | Master List section 8 | final |
| Do not say | Questioning the PS; "extra money for the company"; surge pricing; deposits; crime/wealth pricing; "live Income product"; health/injury cover; tornadoes; admin URL or password. | Master List section 12 | final |
| Income's priorities for the story | Assumptions listed with substantiation; five premium components; automation ladder; AI in three places. | `[FROM INCOME Q&A]` rows | final request |
| Affordability framing | Pitch the stall owner's cost as a share of rent: Tier 2 about 1.7% of monthly rent. Tier 3 equals one day of a median stall's fixed bills. | "Pricing tested..." sections 4 and 6 | likely final |

---

## Appendix: keyword coverage

Searched: "SafeDay pricing for review", "5x / five times", "wow factor / value message", "Income Q&A / mentor / meeting notes", "Industry track Q&A Connexion". Fetched: Global Doc, Pricing page, Master List, proposal v4, Pricing API doc, "Pricing tested against Devnavin's hawker cost data", "Meeting with Ashutosh", "review calculation...", the question-list row, and every row of the TODOs database (about 110 rows; Comment column read for all rows). Pages not read in full: Bhoomi Product design doc, Customer Personas, Success in Insurance, Premium and Payout Parameters (weighted checklist), Loss ratio target, Location pricing and perishable stock, SafeDay burn analysis, Industry-standard formulas, "Act of God" and "Anti-Fraud and PDPA" pages. They may hold older tier or price wording. The Bhoomi doc holds older "Amber Day" and day-2 haze wording that the final decisions replaced.
