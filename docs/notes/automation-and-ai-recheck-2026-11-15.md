# Payout automation and the AI check

Date: 15 Nov 2026. Also in Notion, under the todo "[FROM INCOME Q&A] Describe our automation as a ladder with a human in the loop".

This page answers that todo. Income's head of AI described how Income brings in AI in three steps: a copilot that only suggests, then automatic action when the model is confident, then full automation once it has proved itself. The todo asked us to describe SafeDay the same way. Our view is that the payout does not belong on that ladder at all, and this page explains why.

## The short version

The SafeDay payout is not AI. It is a published formula applied to readings that NEA publishes. Anyone can work out a payout by hand from the reading and the policy, so there is nothing for a person to approve. The payout can be fully automatic from the first day.

The ladder is meant for models. A model has to earn trust over time, because nobody can say in advance what it will answer. A formula can be checked before the day even starts. So we use Income's ladder only for the parts of SafeDay that really use AI: the shop reader at sign-up, the abuse checks at sign-up, and an AI check that looks over each day's payouts.

That AI check runs after the money has gone out. It never delays, stops or changes a payout. When something looks wrong, it tells a person at Income. It is designed but not built yet.

## What the brief and Income asked for

| Who | What they said | What it means for SafeDay |
| --- | --- | --- |
| The brief | Open data and AI "make it cheaper to price these risks, pay out automatically". | Automatic payout is what the brief is asking for. |
| The brief | Traditional insurance "requires loss assessments which are slow and expensive", and these can overwhelm an insurer when one event hits everyone. | SafeDay has no loss assessment, so a haze day does not swamp a claims team. |
| The brief | Triggers must use "data that is independent and verifiable", and "any AI decisions must be explainable". | A formula on NEA data is easy to explain. Keeping AI out of the payout keeps it that way. |
| The brief | The data source needs "a fallback if the feed fails". | The station rule already has one (point 2 below). |
| The brief | Deliverable 8: "How AI/data can be integrated". | We still need to show real AI, just not in the payout decision. |
| Income's product lead | Paying automatically with no claim form is fine as long as it is fast. No appeal inside the product that can change a payout. | Paid automatically at the end of the day, with nothing a customer or a model can argue up or down. |
| Income's head of AI | Income adopts AI as a ladder: copilot, then automatic action on confident cases, then full automation. | We use his ladder for our AI parts and explain why the payout skips it. |

## Why the payout needs no person

Everything that goes into a payout is either fixed before the day starts or published by a government agency.

| Input | Where it comes from | When it is set |
| --- | --- | --- |
| Daily amount and yearly limit | The policy | At purchase. A later change to the tariff does not affect it. |
| Product share (cooked food 1.00, packaged food 0.11 and so on) | The policy | At sign-up (see point 1 below) |
| Where the readings are taken | The policy | At sign-up |
| Hazard weights and severity steps | The published tariff | Before the day. Each change is saved as a new numbered version. |
| Haze, rain and heat readings | NEA, read through `api/readings.py` | On the day |

The calculation is the one on the Notion page "SafeDay pricing for review: loss, payout, premium and profit". Each hazard's loss is weight x severity x product share. The day's loss combines them as 1 - (1 - haze loss) x (1 - rain loss) x (1 - heat loss). The payout is the day's loss x the daily amount, up to whatever is left of the yearly limit.

Every payout also saves the readings and the rule behind them, for example "median of S79, S119, S222 (S72, S118 did not report)". The customer and Income can check any payout line by line.

No step needs judgement, and nothing learns or changes on the day. That is why it is a rule and not AI. A person in the loop would check the same sums the code already does, only slower, and on a haze day they would have to do it for every customer at once.

It is also fast. The payout is designed to go out by PayNow the same evening. SEWA's heat cover in India, one of the schemes the brief describes, took six to eight weeks to pay.

## Five things to be careful about

"Fully automatic" is true for the payout decision. These five points make the claim exact, and we should be ready for each one before a judge asks.

### 1. Sign-up is not automatic, and that is where gaming can happen

The product share is the biggest number a customer controls. A stall that sells packaged food but signs up as cooked food would be paid about nine times as much on the same day (1.00 against 0.11). The location matters as well. So the accurate claim is that no person and no AI is involved after sign-up.

This is where the ladder fits. The shop reader suggests a category and a location, and the owner and the adviser confirm it (`api/kyc.py`, built). The licence number or SSIC code backs up the category. Doubtful cases go to the underwriter queue (`api/underwriting.py`, already built for past declines and for tiers that are not sold directly).

### 2. The payout is only as good as the sensor

A formula pays a wrong reading just as quickly as a right one, and it pays everyone near that station. We have already seen this happen. Heat station S142 recorded 120 heat-trigger days in 2026, when the typical station recorded about 7, and S128 recorded 50. A person spotted it in the pricing data, and both stations are now on hold until NEA confirms them.

The current rules handle a station that goes quiet: if it sends less than half its working-hours data, it counts as not reporting and is never read as zero. They also handle a missing day, because the payout waits and a later run pays it. What they cannot catch is a station that keeps reporting but reports wrong values. That is the first job of the AI check.

### 3. Flood and closure orders are not automatic yet

Haze, rain and heat pay from NEA readings with nobody involved. Flood and closure orders pay only when someone at Income types in the reading. PUB's flood alerts name roads rather than map coordinates, and closure orders have no data feed at all. Until we build a flood run, we should say "automatic for haze, rain and heat, with flood and closure entered by Income for now".

### 4. The prototype starts each run from a button

At the moment the insurer desk starts a payout run for a chosen date (`POST /api/insurer/payout-runs`). There is no scheduled job. In a live product it would run every evening once NEA has published the day's readings. On stage we should say it is designed to run every evening, not that it already does.

### 5. A person touches a payout in two places, both on purpose

The first payout waits for the customer's PayNow details. Income asked us to collect bank details at the first payout rather than at sign-up, so that payout is held and goes out as soon as the customer verifies their mobile number.

Income can also reject a payout that has not been sent yet, and has to give a reason (`/api/insurer/payouts/{id}/reject`). This is there for the rare case where NEA withdraws a reading. Each rejection records who made it and why. It is not an appeal, and it can never raise a payout.

## AI and data that are already built

The payout itself uses no AI, but SafeDay already uses AI and data in four places that work today.

| What | Kind | What it does | Where it is |
| --- | --- | --- | --- |
| Shop reader | AI | Reads the owner's own words, or a photo of the stall, and suggests a product category and a location. The owner and the adviser confirm it. It never sets a price. | `api/kyc.py`, the "Tell us about your shop" box on the map |
| Hazard models | AI | Rebuild heat and the wettest rain hour back to 1980 from ERA5 weather data, for years and places with no sensor. Forecast haze 1 and 7 days ahead, rain and heat 1 day ahead, and the number of haze and heavy rain days next month. Nine kinds of model are compared with simple baselines on years they never saw. | `ml/`, results in `ml/results/` |
| Price breakdown and fairness check | Data | Every quote shows how many bad days each hazard adds and how the premium is built, so anyone can see why it costs what it costs. A check under MAS's FEAT principles measures how far the same cover's price moves between places, and compares it with stall rents as a rough sign of how well off each centre is. | `api/calculator.py`, `docs/notes/feat-fairness-check-2026-11-15.md` |
| Cover text in the customer's language | Plain language, not AI | Once the customer pays, the cover is texted in English, Chinese, Malay or Tamil from fixed, checked wording. | `api/sms.py` |

The models do not set the price. The price comes from the published formula applied to NEA's recorded history. The models fill gaps in that history and give the forecasts we would use for early-warning texts, which are designed but not built.

## The AI check on each day's payouts

**Designed, not built. Do not show it as live.**

The check runs after each evening's payouts have been sent. It does not change anything by itself. It raises a flag, and a person at Income decides what to do. The message check is the one exception to the timing: it runs before a text goes out.

| What it checks | What it compares | What it flags | Who acts on it |
| --- | --- | --- | --- |
| Readings | The readings saved with each payout, against NEA's later records (the MSS daily station record and NEA's historical PSI file) | A payout made on a value the later record does not support | Income's operations team. What happens to the payout depends on the policy wording (question 1 below). |
| Stations | Each station's trigger days against its neighbours over weeks and months, using an anomaly model | A station far out of line with the stations around it, as S142 was | Income puts the station on hold in the tariff desk. Prices and payouts then use the next nearest station from then on. |
| Sign-ups | New policies by location, category, timing and PayNow account | Several policies paying into one PayNow account, a category that does not match the licence or SSIC code, or a burst of sign-ups ahead of a haze forecast | The underwriter, through the existing queue. A wrong category is corrected through Income's normal service route. |
| Sums | Each payout against its saved readings, the tariff version and the policy's terms | A payout above the yearly limit, during the waiting period or after the term has ended | Our engineers. Any flag here means a bug. |
| Messages | The SMS and dashboard text for each payout, which a language model writes from the saved readings | Text that does not match the numbers it was written from | A second model checks the text before it is sent, the way Income checks its own generated content. |

The check only raises flags, for two reasons. If a model could stop a payout, the payout would become an AI decision again, and we would lose the explainability the brief asks for and the speed Income asked for. And a false alarm should cost Income a few minutes of someone's time, not cost a hawker their money on the day they need it. The brief asks for payouts "when claimants need them the most".

## AI in Income's three places

Income's product lead asked to see AI in three places: distributing the product, handling claims and weeding out abuse. This is how SafeDay's parts sort into them.

| Income's place | What SafeDay does | Status |
| --- | --- | --- |
| Distributing the product | The shop reader fills in the sign-up with the adviser. The cover is texted in the customer's own language. The hazard models show a customer how often bad days hit their area. | Shop reader and texts built. Models built; showing their forecasts to customers is designed. |
| Handling claims | There is no claim. The payout is a formula on NEA readings, paid by PayNow with no form. The AI check reviews each day's payouts afterwards, and a language model writes the payout text, checked by a second model. | Payout built. AI check and model-written text designed. |
| Weeding out abuse | The 30-day wait and the 12 or 24 month terms stop people buying only when haze is forecast. Risky applications go to the underwriter. AI checks look for several policies on one PayNow account, a category that does not match the licence, bursts of sign-ups before forecast haze, and faulty stations. | Rules and underwriter queue built. AI checks designed. |

## Where each part sits on Income's ladder

| Part | Step 1: suggests only | Step 2: acts when confident | Step 3: fully automatic |
| --- | --- | --- | --- |
| Payout | Not AI. A formula, fully automatic from the first day. | | |
| Shop reader at sign-up | Today it suggests a category and location, and the owner and adviser confirm (built). | Fills in the category by itself above a set confidence, for example 0.9, and asks below it. | Once its suggestions have matched what owners and underwriters chose throughout the pilot. |
| Abuse checks at sign-up | In the pilot it flags cases to the underwriter, who decides. | Clears plainly normal cases without review and refers the rest. | Only for clearing. A decline always stays with a person. |
| AI check on payouts | In the pilot it only flags, and a person acts. | Puts a station on hold for future days when the problem is clear, and tells a person the same day. | Not planned. It stays a check and never decides. |

The 0.9 confidence level and the step 3 tests are our own assumptions until Income gives its view.

## What to say on stage

> SafeDay's payout is not AI. It is a published rule applied to NEA's published readings, so it can be fully automatic from the first day: no claim form, no assessor, and the money arrives by PayNow the same evening. Every customer can check their payout against the reading and the rule. AI works alongside it. It reads the shop at sign-up, our models rebuild weather back to 1980 and forecast haze up to a week ahead, and every evening it checks the day's payouts against a second source and looks for faulty stations. When something looks off, it tells a person at Income. It never holds back a payout.

Things not to say:

- "AI decides the payout" or "ML calculates the payout".
- "Fully automatic" about flood or closure orders, until the flood run is built.
- That the AI check is already built.

## Questions for Income

1. If NEA corrects a reading after we have paid on it, what should the policy wording say? We suggest leaving that payout as it is and using the corrected reading from then on. Income's compliance team would need to confirm this fits the MAS Guidelines on Fair Dealing.
2. Who at Income would own the list of stations on hold, and how quickly could a station be put on hold after a flag?
3. What confidence level would Income accept before the shop reader fills in a category without the owner confirming it?

## Sources

- The brief: `docs/problem-statements.md`, section 1 ("Why does this matter now?", the constraints, the deliverables and the must-haves).
- Income's product lead: Notion, "Mentor session 1, 15 Nov: Income private session (Safe Day feedback)".
- Income's head of AI: the Comment on the todo this page answers.
- Payout formula and product shares: the Notion pricing page, Parts 1 and 6, and `api/calculator.py`, `api/readings.py`, `api/default_tariff.json`.
- Stations S142 and S128: the pricing page, Part 7.6, and `docs/notes/tier-design-proposal-2026-11-15.md`.
- Flood and closure paid only by hand: `docs/notes/claim-parameters-and-exclusions-2026-11-15.md`, rows D6 and D7.
- SEWA's six to eight weeks: the brief, "Overseas, heat and lost income".
- Hazard models: `ml/README.md` and `ml/results/`.
- Price breakdown and fairness check: `docs/notes/feat-fairness-check-2026-11-15.md`.
- Cover text languages: `api/sms.py`.
- Payout runs, held payouts and rejected payouts: `api/payout_api.py`, `api/payout_flow.py` and `docs/notes/payout-flow-design-2026-11-15.md`.
