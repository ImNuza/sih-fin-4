# Claim parameters and exclusions list (deliverable 4)

Research note for the SIH FIN-4 team, 15 Nov 2026. SafeDay by Income Insurance. Brief: `docs/problem-statements.md`, section 1.

How to read the sources in this note:
- All file paths are inside `/Users/dewa/Documents/Projects/SIH/sih-fin-4`. A path with a line number looks like `api/payout_flow.py:24`.
- "Draft doc" means "SafeDay doc section 6 and 7" in `/Users/dewa/Documents/Projects/SIH/whatsapp/2026-11-15 SIH FIN-4/00003068-SafeDay-Hackathon-Plan.pdf`. The PDF is dated 7 November 2026. Section 6 is on PDF pages 11 to 13. Section 7 is on page 14.
- "Notion locked" means the green LOCKED callout (15 Nov 09:28, Sky) on the Notion page "Singapore Hackathon Global Doc (REAL)".
- "Master list" means the Notion page "Pitch, Features & Proposal — Master List", last edited 15 Nov 04:21 UTC.
- "Act of God page" means the Notion page "Act of God and weather exclusions in Singapore", checked 13 Nov 2026.
- The code is the truth for what the product does today. This note changes no number in the product. Where a value looks wrong, the note gives a recommendation with evidence.

## Update, 15 Nov 2026 (after this note was written)

- **D18 is fixed** (commit 3682dba). A payout run no longer reads a silent station as 0. It takes
  the nearest station, else the median of up to 3 reporting stations within 5 km, else (rain) the
  MSS published record, else it waits for data and a later run can still pay. The rule is in
  `api/day_history.py` and `docs/notes/payout-flow-design-2026-11-15.md`. So the "one nearest
  gauge / station" rule in section 2 is now "nearest, with a fallback". Line numbers in
  `api/day_history.py` below refer to the old file.
- **Section 6 is on the buy page** (Cover step, "What it pays, and what it does not"). It is built
  from the tariff (`first_band` in `/api/options`) and the chosen tier, so it follows the tariff
  desk. It includes the sentence the brief asks for: "You can lose sales and receive nothing if
  the readings stay below these levels." It leaves out the challenge line (no route exists, D16)
  and closure orders (not a climate trigger, D7).
- Still open from section 5: D6, D10 to D16, D20. D17 is closed by the renewal rules below.

## Renewal and lapse rules (closes D17), 15 Nov 2026 evening

Why: Sky asked for a guard against "buy a high tier, collect, then not renew" (WhatsApp, 15 Nov
18:24; Notion row 419ecd5c15be811ab7d2cf640abc350a). The team ruled out a price change, surge
pricing and deposits. The guard uses the 30-day waiting period and the yearly limit only.

| Rule | What the product does | Where | Code or text |
|---|---|---|---|
| (a) Tier upgrade | A higher daily amount starts a new 30-day wait for the whole cover. The same or a lower amount keeps the cover's start date. | `api/main.py:854` (`buy_policy`) | Code |
| (b) Re-buy after a lapse | A cancelled cover is deleted. A cover bought after it is new and waits 30 days again. The yearly limit counts every payout to the customer in the last 365 days, from any earlier cover. | `api/main.py:1308` (`cancel_policy`), `api/payout_flow.py:66` (`owed_in_cap_window`) | Code (already true before this change; now tested) |
| (c) Premium not paid | Cover stops if the weekly premium is not paid. | Buy page text only | Text only. No premium-paid-until field exists. `api/premium.py` records the first week's PayNow payment and nothing after it. The code stops cover only when the 12 or 24-month term ends (`payout_flow.cover_ends`). |
| (d) No clawback | Payouts already made stay paid after a tier change or a lapse. No code path reverses a paid payout. | `api/payouts.py` rows are kept when a policy is deleted | Code (already true; now tested) |

Choice for (a): the whole cover waits, not only the added amount. Reason: the code keeps one policy
row per customer and pays its `daily_payout_sgd`. A wait for the added amount only needs the old
amount stored next to the new one, and `create_all` never adds a column to an existing table
(`api/payouts.py:5`), so the hosted database needs a new table. The cost to the customer: no cover
for 30 days after an upgrade. Before this change, a move to a lower tier also restarted the wait.
That is fixed: a lower tier cannot be gamed, so it keeps the start date.

Known side effect: a move to a lower tier keeps the old start, so the welcome text is not sent
again (`payout_flow.send_welcome_if_due` sends once per start). The customer sees the new amount
on the dashboard only.

Values: the 30 days are `accounts.WAITING_PERIOD_DAYS` and `payout_flow.WAITING_PERIOD_DAYS`
(both 30, D20), the 365 days are `payout_flow.CAP_WINDOW_DAYS`. The waiting period is a code
constant, not a tariff field. The buy page reads both values from `/api/buy/options`.

Buy page (Cover step, "What it pays, and what it does not"), three new lines:
- A move to a higher tier starts a new 30-day wait for the whole cover. A move to a lower tier keeps your start date.
- Cover stops if the weekly premium is not paid. If you buy again later, the new cover waits 30 days, and the yearly limit still counts what was paid in the last 365 days.
- Payouts already made are yours to keep.

Tests: `tests/test_renewal_rules.py`, one or more per rule.

## 1. Summary

SafeDay pays a share of a fixed daily amount when a public NEA or PUB reading crosses a trigger level. The tariff has four paid tiers (S$20, S$40, S$70 and S$100 a day). The tariff sets the trigger levels for haze, heavy rain, heat and flash flood, plus a closure order. The code enforces a 30-day waiting period, one payout per customer per day, and a yearly money cap per tier over a rolling 365 days. The code does not enforce the activity rule, the end of the 12 or 24-month term, a sales freeze, an unpaid-plan exclusion or a customer challenge route. The draft doc and the code disagree with each other or with the Notion decisions on 20 points (section 5). The most serious are the waiting period (7 days in the draft, 30 days now), the haze day-2 rule (dropped), the payout amounts (draft Red and Amber days, code tiers) and the flood trigger (the code does not pay on a live PUB alert without an insurer action). The buy flow does not yet say that a customer can lose sales and receive nothing.

## 2. What pays

Source for every value in this table: `api/default_tariff.json`. The reading rules come from `api/day_history.py:31-43`, `api/live.py:27-28,41-43,84,107-123` and `api/main.py:285-290,622-630`.

| Hazard | Reading (tariff) | Source station rule (payout) | Trigger levels and severity (tariff) | Hazard weight (tariff) |
|---|---|---|---|---|
| Haze | Highest 24-hour PSI of the day in the region (line 6) | The customer's PSI region. No station choice (`day_history.py:40`). | 101 gives 0.3, 201 gives 0.6, 301 gives 1.0 (lines 9-13). The levels are the NEA PSI bands (line 16). | 0.8 (line 7) |
| Heavy rain | Rain in the wettest work hour at the nearest gauge, in mm (line 21) | One nearest rain gauge (`day_history.py:37`, `main.py:285-290`). Work hours are 07:00 to 19:00 (`live.py:27`). The tariff says `sites_used` 3 (line 29). The price uses 3 gauges. The payout uses 1. | 20 mm gives 0.3, 30 mm gives 0.6, 50 mm gives 1.0 (lines 24-28). Severities are "a starting assumption" (line 31). | 0.5 (line 23) |
| Heat | Work hours with WBGT at 32°C or more at the nearest station (line 36) | One nearest WBGT station (`day_history.py:38`). Work hours are 07:00 to 19:00 (`live.py:27`). 32°C is the MOM rest-break level (`live.py:28`, tariff line 46). | 2 hours gives 0.3, 4 hours gives 0.6, 6 hours gives 1.0 (lines 39-43). | 0.4 (line 38) |
| Flash flood | 1 if a PUB flood alert covers the site, else 0 (line 51) | The PUB alert feed names roads, not coordinates. The live map lists alerts but does not score them (`main.py:576`). Only an insurer manual run can pay it (`payout_api.py:46-55`). | One level: 1 gives 1.0 (line 54). Priced at 0 days a year (line 56). | 0.8 (line 52) |
| Closure order | 1 if a government order closes the business for the day, else 0 (line 62) | No data feed. Only an insurer manual run can pay it (`payout_api.py:46-55`). | One level: 1 gives 1.0 (line 65). Priced at 0 days a year (line 67). | 1.0 and not scaled by product (lines 63-64) |

Share of a tier's daily amount paid:
- One hazard pays `weight x severity x product factor` (`api/calculator.py:100-101`). Closure and any hazard with `scaled_by_product` false skip the product factor.
- Several hazards on one day combine as `1 - product of (1 - hazard loss)`. The total never passes 100% (`api/calculator.py:119-120`).
- The payout is the combined share times the tier's daily amount (`api/calculator.py:124`).
- Product factor comes from `api/calculator.py:83-97`, applied to the product lines in the tariff (lines 72-77). I computed these values: cooked food 1.000, fresh produce 0.348, flowers 0.454, packaged food 0.112, general goods 0.108, platform work 0.420.
- Worked values for cooked food (factor 1.000), as a share of the daily amount: haze 24% / 48% / 80%, rain 15% / 30% / 50%, heat 12% / 24% / 40%, flood 80%, closure 100%.
- Worked values for platform work (factor 0.420): haze 10.1% / 20.2% / 33.6%, rain 6.3% / 12.6% / 21.0%, heat 5.0% / 10.1% / 16.8%, flood 33.6%, closure 100%.
- No reading below the first band pays anything (`api/calculator.py:76-80`, `api/payout_flow.py:139-140`).

Payout path (all in `api/payout_flow.py`): assess (127), cap (141-146), approve with rule "automatic" (166), send by PayNow (99-124), SMS to the customer (83-96). The insurer desk starts each run for one date (`api/payout_api.py:228-257`). No scheduled job exists (`docs/notes/payout-flow-design-2026-11-15.md`, Decisions, item 3).

## 3. What never pays (exclusions)

Part A: enforced in code today.

| # | Exclusion | Reason | Code location |
|---|---|---|---|
| A1 | A day where every reading is below the first band | The product pays on the trigger, not on the loss. The brief asks us to say this at the point of sale (`docs/problem-statements.md`, "Say plainly when it does not pay"). | `api/calculator.py:76-80`, `api/payout_flow.py:139-140` |
| A2 | A day inside the 30-day waiting period | Stops people from buying only when bad weather is forecast (Notion locked, 15 Nov). | `api/payout_flow.py:136-137` |
| A3 | A second payout for the same customer on the same day | One payout per day. This also stops a re-run from paying twice. | `api/payout_flow.py:129-135` |
| A4 | Any amount above the yearly cap | Cap on frequency, as the brief requires. A day with no cap left is stored as "capped" with amount 0. | `api/payout_flow.py:141-146,163-165` |
| A5 | A payout the insurer rejects, with a written reason | The insurer can reject before or after a failed send. A paid payout cannot be rejected. | `api/payout_flow.py:26,200-204`, `api/payout_api.py:281-285` |
| A6 | A customer with no policy, or whose application is referred or declined | No policy starts until an underwriter approves. | `api/main.py:672-677`, `api/underwriting.py:186-207` |
| A7 | A cancelled policy | Cancel deletes the policy row. | `api/main.py:1049-1060` |
| A8 | Injury, medical cost, damage to property or stock | The code has no payout path for them. Income loss only. Master list, decisions log, 15 Nov: "Health, injury, medical: OUT". Draft doc, section 6, Exclusions. | No code needed. Nothing in the tariff pays them. |

A payout is held, not refused, when the customer has no verified mobile or PayNow account. It is sent when the account is verified (`api/payout_flow.py:105-109,184-189`).

Part B: written in the draft doc or the Act of God page, but not in the code. Treat these as open items for the exclusions text.

| # | Exclusion | Where it is written | In code? |
|---|---|---|---|
| B1 | No payout if the plan is unpaid | Draft doc, section 6, Exclusions | No. The prototype takes no money (`api/main.py:692,951`, `api/site/buy/index.html:178`). |
| B2 | Work plan: no payout if not active on the platform or with the employer in the last 14 days (the "activity rule") | Draft doc, section 6, Exclusions and "Who can buy" | No. No source found for a 14-day check in `api/`. The buy flow only collects a platform name and worker ID (`api/onboarding.py:56-58`, `api/main.py:718`). |
| B3 | No new sign-ups while an NEA haze advisory is active, PSI is forecast above 100 or a heavy rain warning is in force (sales freeze) | Draft doc, section 6, "Rules that stop people gaming it". Master list, judge answers. Act of God page, item 3. | No. No source found in `api/`. |
| B4 | War, nuclear and terrorism | Act of God page, "Exclusions we still need to write" | No. |
| B5 | Days the customer was not covered or not trading | Act of God page, same list | Not covered is partly enforced (A2, A6, A7). Not trading is not enforced. |
| B6 | No overlap with work injury compensation | Act of God page, same list | No payout path exists for injury, so no overlap is possible today. |
| B7 | A payout after the 12 or 24-month term ends | Notion locked (term). Draft doc says "monthly, auto-renewing". | No. The end date is saved (`api/main.py:850-856`, `api/accounts.py:126`) but `api/payout_flow.py` never reads it. |

Not an exclusion: the Act of God page says "No act of God exclusion. The weather is the thing we insure." Extreme weather pays, inside the yearly cap.

## 4. Waiting period, term, activity rule, yearly cap, per-tier daily amount

| Parameter | Value | Source of the value | Code that enforces it |
|---|---|---|---|
| Waiting period | 30 days. Pays for Singapore dates from the start date plus 30 days. | Notion locked, 15 Nov. `api/payout_flow.py:22-24`. `api/accounts.py:38`. | `api/payout_flow.py:77-80` (first covered day) and `api/payout_flow.py:136-137` (skip with "waiting_period"). The buy flow shows the date (`api/main.py:850-856`, `api/site/buy.js:454`). |
| Term | 12 or 24 months at a flat weekly rate | Notion locked, 15 Nov. `api/accounts.py:39`. | The term is chosen and saved (`api/main.py:725`, `api/accounts.py:124-126`). Not enforced at payout. See B7. |
| Activity rule | None in code. The draft doc has "active in the past 14 days" for the Work plan only. | Draft doc, section 6 (PDF pages 12-13). Not in Notion locked. | Not enforced. See B2. |
| Yearly cap | `daily amount x max paid days`, counted in money, over the 365 days up to the loss date, across every policy the customer held. Partial days use partial money. | `api/payout_flow.py:21` (365), `api/default_tariff.json:80-83` (days). | `api/payout_flow.py:64-74` (money already owed), `api/payout_flow.py:141-146` (cap left), `api/payout_flow.py:25` (statuses that count). The quote uses the same formula (`api/calculator.py:179`). |
| Daily amount per tier | Tier 1 S$20, Tier 2 S$40, Tier 3 S$70, Tier 4 S$100 | `api/default_tariff.json:80-83` | `api/calculator.py:124` and `api/payout_flow.py:139-146`. The policy copies the amount at purchase (`api/main.py:654-656`). |
| Max paid days per year | Tier 1 10, Tier 2 15, Tier 3 20, Tier 4 30 | `api/default_tariff.json:80-83` | `api/payout_flow.py:142` |
| Yearly money cap (derived) | Tier 1 S$200, Tier 2 S$600, Tier 3 S$1,400, Tier 4 S$3,000 | Derived: daily amount times max days, as in `api/calculator.py:179`. | `api/payout_flow.py:142` |

## 5. Doc vs code

"Current" names the source that is right today. A number such as D6 below is the item number used in the reply.

| # | Item | Draft doc (7 Nov) | Notion (locked and master list) | Code | Current |
|---|---|---|---|---|---|
| D1 | Waiting period | 7 days after first purchase (PDF page 13) | 30 days, LOCKED 15 Nov | 30 days (`api/payout_flow.py:24`, `api/accounts.py:38`) | Notion and code: 30 days. The draft is old. |
| D2 | Haze: day-2 rule | Amber if PSI over 100 from the 2nd day in a row. Red if PSI over 200 at noon (PDF page 14). | "Haze pays from day 1", graded 30 / 60 / 100% at 101 / 201 / 301. Day-2 rule dropped. LOCKED 15 Nov (master list, decisions log). | Day 1. No streak state exists (`api/calculator.py:76-80`). | Notion and code. |
| D3 | Haze reading | PSI at noon | Highest 24-hour PSI in the region | Highest 24-hour PSI of the day (tariff line 6; `api/live.py` field `max_today`, `api/main.py:625`) | Notion and code. |
| D4 | Heat trigger | Red at WBGT 33°C or more for 2+ hours, 11:00 to 17:00. Amber (Biz add-on) at 32°C. Use the worse of the 2 nearest stations. | WBGT 32°C, 2 / 4 / 6 hours. Decision 14 Nov: 32°C is the MOM rest-break level. | WBGT 32°C, 07:00 to 19:00, one nearest station (`api/live.py:27-28`, `api/day_history.py:38`) | Notion and code. The "worst of 2 stations" fix is not built (master list, limitation 4). |
| D5 | Rain trigger | 50 mm in 60 minutes, median of the 3 nearest stations, in trading hours | 20 / 30 / 50 mm in the wettest work hour (07:00 to 19:00) at the nearest gauge | Same as Notion. Payout reads one gauge (`api/day_history.py:37`). Price reads 3 (`api/calculator.py:269`). | Notion and code. Recommendation: say "nearest gauge" in the buy text. Evidence: `api/main.py:285-290`. |
| D6 | Flash flood | Alert within 500 m of the stall or in the work zone, automatic | "Pays on a live PUB alert" (master list, locked 15 Nov) | The feed has no coordinates and the live map does not score it (`api/main.py:576`). History runs give no flood reading (`api/day_history.py:39-43`). Only an insurer manual run with `{"flood": 1}` pays (`api/payout_api.py:46-55`). | Code. Recommendation: do not say "automatic" for flood in the pitch until a feed run is built. |
| D7 | Closure order | Not in the draft | "Rider only, not climate" (master list, perils table) | In the tariff for every product (lines 59-69). Pays only on a manual run. | Code. It is not a climate trigger. Do not list it in the buy text. |
| D8 | What is paid | Biz: S$50 Red Day, S$25 Amber Day. Work: S$20 Red Day. Home: S$250 flood cleanup. | Tiers S$20 / 40 / 70 / 100 for a bad day (master list, key facts) | Tiers, times a loss share from 0 to 100% (`api/calculator.py:124`) | Code and Notion. The Red and Amber Day model is not in the code. The landing page still says "Pays S$20 to S$100 for each bad day" (`api/site/index.html:91`), which hides the loss share. |
| D9 | One payout per day | The higher tier is paid once | One payout per day (master list, section 6) | One row per customer per day (`api/payout_flow.py:129-135`). Hazards combine as independent causes (`api/calculator.py:119-120`). | Code. The draft wording "higher tier" is wrong. |
| D10 | Yearly cap | Biz S$300 a year. Work 10 Red Days (S$200). | Capped 10 / 15 / 20 / 30 days (master list, key facts) | A money cap, rolling 365 days, across policies (`api/payout_flow.py:21,64-74,142`). A 30% day uses 30% of one day of cap. | Code. The words "days" in the Notion text are loose. Customers can receive more payout events than the cap days. |
| D11 | Term and renewal | Monthly, auto-renewing. Biz yearly with monthly billing. | 12 or 24 months at a flat weekly rate, LOCKED 15 Nov | 12 or 24 saved. No renewal. The end date is not checked at payout. | Notion for the sale. Code does not enforce the end. |
| D12 | Activity rule | Work plan: active in the last 14 days | Not mentioned in the locked decisions or the master list. | None | Open. Neither the code nor the locked decisions have it. |
| D13 | Sales freeze | Yes (section 6) | Master list judge answer says yes. Act of God page says it is still to be written. | None | Open. Not built. |
| D14 | Unpaid-plan exclusion | Yes | Not mentioned | None. The prototype takes no money. | Open. |
| D15 | Speed and automation | "Usually within the hour" (PDF page 12) | "Same day, automatic" (master list, key facts) | An insurer starts a run for one date. No schedule. PayNow and SMS are simulated. | Code. Say "designed to be automatic" until a scheduled run exists. Evidence: `api/payout_api.py:228-257`. |
| D16 | Customer challenge | None. The draft says there is no claim. | Locked: submit proof, manual or AI-assisted check, about the reading or the classification and never about the loss size. Master list: "Dispute / appeal flow ... designed, not built". | No customer route. Only the insurer can reject (`api/payout_api.py:281-285`). | Notion is the intent. Code does not have it. See section 6 note. |
| D17 | Tier change resets the wait | Not covered | Not covered. The lock says the wait is 30 days "before cover starts". | A new tier deletes the old policy and starts a new one at "now" (`api/main.py:679-682`). The 30-day wait starts again. The underwriter route keeps the cover start date (`api/underwriting.py:155-159`). | Code. Recommendation: carry the old start date to the new row. Evidence: `api/main.py:679-682`. |
| D18 | Feed failure | Use the next nearest station, then MSS records. Pay late, not never. | Fallback rule "designed, not built". Act of God page: a sensor failure cannot be a reason not to pay. | A missing station reads 0 (`api/main.py:285-289`). In history, no row means 0 (`api/day_history.py:34`). So a dead feed pays nothing. | Code. This conflicts with the Act of God page. Recommendation: add the fallback before the pitch. |
| D19 | "Lose sales and receive nothing" sentence | Draft SMS says "No Red Day = no pay, even if you lose income." | Master list marks the landing bubble as missing this line. | Landing page: "If readings stay below them, nothing is paid" (`api/site/index.html:92`). Customer page: "Below those levels nothing is paid" (`api/site/site.js:266`). Buy confirmation has no such line (`api/site/buy.js:454-455`). | Code lacks the exact sentence. See section 6. |
| D20 | Waiting constant | Not covered | Not covered | Defined twice: `api/payout_flow.py:24` and `api/accounts.py:38`. Both are 30. | Both agree today. Recommendation: keep one. Evidence: the two lines. |

Total listed: 20 items. D2, D3, D4 and D5 say the draft doc is wrong and Notion and code agree. D6, D10, D11, D12, D13, D14, D15, D16, D17, D18 and D19 are real gaps between the written promise and the code.

## 6. Short version for the buy flow (5 lines)

1. SafeDay pays you up to S$20, S$40, S$70 or S$100 for a bad day, by your plan.
2. A bad day is when official NEA or PUB readings pass a public line: PSI 101 or more, rain 20 mm or more in one work hour, 2 hours at WBGT 32°C or more, or a PUB flood alert.
3. Cover starts after 30 days. It pays up to a yearly limit.
4. You can lose sales and receive nothing if readings stay below the trigger.
5. There is no claim form. Injury, medical cost and damaged goods are not covered. If you think a reading is wrong, send proof and we will check it.

Notes on the five lines:
- Line 1 uses the tier amounts in `api/default_tariff.json:80-83`. The code pays a share of the amount, from 0 to 100%. "Up to" is correct.
- Line 2 matches `api/site/site.js:266`. Flood is paid by an insurer action today (D6). Keep the flood words only if the team builds a feed run before the pitch. Otherwise remove "or a PUB flood alert" from line 2.
- Line 5, last sentence, is the locked challenge route. No route exists in the code (D16).
- The brief asks for the trigger, the payout and the exclusions to fit in one SMS (`docs/problem-statements.md`, "Understanding"). These five lines are for the screen. A shorter SMS version is Rafael's task (master list, section 11).

## Sources checked

- Code: `api/default_tariff.json`, `api/calculator.py`, `api/payout_flow.py`, `api/onboarding.py`, `api/underwriting.py`, `api/main.py`, `api/accounts.py`, `api/payout_api.py`, `api/day_history.py`, `api/live.py`, `api/site/index.html`, `api/site/site.js`, `api/site/buy.js`, `docs/notes/payout-flow-design-2026-11-15.md`.
- Draft: SafeDay Hackathon Plan PDF, 7 Nov 2026, sections 6 and 7.
- Notion (read only): "Singapore Hackathon Global Doc (REAL)", "Pitch, Features & Proposal — Master List", "Act of God and weather exclusions in Singapore".
- Web: none used.
