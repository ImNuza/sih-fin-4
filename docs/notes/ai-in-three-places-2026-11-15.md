# AI in Income's three places: distribution, claims and abuse

Date: 15 Nov 2026. Also in Notion, under the todo "[FROM INCOME Q&A] Show AI in the three places Income named".

This page answers that todo. In the private session on 15 Nov, Income's product lead told us "you do need to bring in AI to some degree", and named three places to show it: distributing the product, handling claims and weeding out abuse. This page goes through each one, says what we have built, what is only designed, and where AI should stay out.

It builds on `docs/notes/automation-and-ai-recheck-2026-11-15.md` ("Payout automation and the AI check"), which explains why the payout itself is a formula and not AI. That point is not repeated here in full.

## The short version

- **Distribution.** AI reads a stall owner's own description, or a photo, and fills in the product and the place. Data does the rest of the selling work: a price for the stall's own location, proof numbers from that location's past weather, a suggested tier from the stall's rent, and the cover texted in the customer's language.
- **Claims.** There is no claim to handle. NEA's reading goes through a published formula and the money goes out by PayNow. Income already uses AI to read paper claims; SafeDay has no paper to read. AI's job here is to check each day's payouts afterwards and to explain them.
- **Abuse.** Nobody can fake the weather, so abuse moves to sign-up and timing. Fixed rules carry most of the weight today, and they are built. AI adds pattern checks on top, which flag cases to an underwriter. Those are designed, not built.

## What Income asked for

The product lead's reason for wanting AI was speed: a payout triggered by an event has to reach people fast. She also ruled out any appeal inside the product that can change a payout, so the earlier idea of "AI checks challenges" is gone.

The brief adds two limits. Payout triggers must use "data that is independent and verifiable", and "any AI decisions must be explainable". Its list of directions asks for "responsible use of AI and alternative data to lower the cost of underwriting, pricing or claims".

One correction to what we said in the room: the premium does not come from a trained model. It comes from the published tariff formula applied to NEA's recorded history. Our models rebuild missing history and forecast hazards. They do not set prices or payouts.

## 1. Distributing the product

SafeDay is sold through the customer's Income adviser or through a hawker association, never directly. Income suggested a lower commission for a product like this, about 5% instead of the usual 15%. A cheap product sold on a small commission needs a sale that takes very little of the adviser's time. That is where AI and data help.

| Part | What it does | Kind | Status |
| --- | --- | --- | --- |
| Shop reader | The owner types a sentence ("I sell fruit at Tiong Bahru") or sends a photo of the stall. A language model suggests the product category and the place, with a confidence score. The owner and adviser confirm it. It never sets a price. With no model available, a keyword table does the same job. | AI | Built on the map (`api/kyc.py`). Not yet part of the buy flow. |
| Price for the stall's own place | Each hawker is quoted the price for its own centre, read from the stations nearest to it, not a regional average. | Data | Built |
| Proof numbers on the quote | Each tier shows what it would have paid at that exact place: in a typical year, in 2026 and in a 2015-type haze, next to the most it can pay. This answers the "why not just save the money" question both mentors asked. | Data | Built |
| Suggested tier | Suggests the smallest tier whose daily amount covers a day of the stall's rent, using NEA's tender bids for that centre. | Data | Built (`/api/rent`) |
| Cover in the customer's language | Once the customer pays, the cover is texted in English, Chinese, Malay or Tamil from fixed, checked wording. | Plain language, not AI | Built (`api/sms.py`) |
| Hazard forecasts for customers | Show a customer how often bad days hit their area and warn them before a hazy day. Never used to raise the price or to push a sale before bad weather: the price is flat and cover only starts after 30 days. | AI | Models built (`ml/`). Showing forecasts to customers is designed. |

The gap to close: the shop reader works on the map but not inside the buy flow the adviser uses. Wiring it into the product step of `/buy/` is the change that would let us say AI fills in the sign-up.

## 2. Handling claims

Income already uses AI in claims. In 2017 it became the first insurer in Singapore to use IBM Watson Explorer, to read about 14,000 paper hospitalisation claims a month (medical certificates and bills) that staff had reviewed by hand. That kind of AI reads a document so that someone can decide on it.

SafeDay has no document and no decision to make. The payout is worked out from NEA's reading by a published formula. So the honest answer for claims is that the speed Income wants comes from removing the claim, not from adding AI to it. AI comes in afterwards, to check and to explain.

| Step | How it works | Kind | Status |
| --- | --- | --- | --- |
| Read the weather | The station rule in `api/readings.py`: nearest reporting stations, a station with too little data is skipped, then a fallback record, then wait for data. | Rule | Built |
| Work out the payout | Day's loss x daily amount, up to what is left of the yearly limit. | Formula | Built |
| Pay and text | PayNow transfer and an SMS naming the amount and the main hazard. | Rule | Built. The run is started from the insurer desk; a nightly run is designed. |
| Explain the payout | Every payout saves the readings and the rule behind them, for example "median of S79, S119, S222 (S72, S118 did not report)". A language model would turn that into a plain sentence, checked by a second model before it is sent. | Data, then AI | Saved explanation built. Model-written text designed. |
| Check the day's payouts | Compares each payout's readings with NEA's later records, looks for stations out of line with their neighbours, and checks the sums. It flags to a person and never holds back a payout. | AI | Designed |
| Check the trigger itself | A back-test of how often a stall's own station had a bad day that the payout missed, and how often it paid a day that was fine there. | Data | Built (`docs/notes/basis-risk-2026-11-15.md`) |

The full reasoning for keeping AI out of the payout decision, and the five places where "fully automatic" needs care, are in `docs/notes/automation-and-ai-recheck-2026-11-15.md`.

## 3. Weeding out abuse

(Gap: today nothing checks a shop's SSIC code against the product it picks, so a mini-mart could sign up as cooked food and be paid about nine times as much on the same day. A simple table of which products each SSIC code may choose would fix most of this without AI. Details at the end of this section.)

In ordinary insurance, most abuse is in the claim: an exaggerated loss or a staged one. Parametric cover removes that, because the payout follows a public index and not the customer's own account of the loss. Industry and academic write-ups make the same point (PwC 2024 on basis risk; Picard, EGRIE 2022). What is left to game is everything around the index:

- what the customer says they sell, because a cooked food stall is paid about nine times as much as a packaged food stall on the same day;
- where they say they are;
- when they buy, for example just before a haze;
- how many policies pay into one account;
- and, without anyone meaning harm, a faulty station that triggers payouts it should not.

| Risk | Rule that already stops it | AI check on top |
| --- | --- | --- |
| Buying just before bad weather | Cover starts 30 days after purchase. Terms are 12 or 24 months at a flat weekly rate. The severe haze add-on cannot be bought from May to October. A move to a higher tier only pays after its own waiting period. (Built) | Flag a burst of sign-ups in one area just before a forecast haze. (Designed) |
| Claiming the wrong product | A hawker gives an SFA licence or NEA tenancy number; a shop gives its SSIC industry code. (Built) | Compare the product chosen with the SSIC code and with the shop reader's reading, and flag a mismatch to the underwriter. (Designed) |
| Claiming the wrong place | A hawker names its centre; a shop's postcode must be a real Singapore postcode. (Built) | Flag a centre or postcode that does not fit the licence. (Designed) |
| One person, many policies | One payout per person per day. The yearly limit counts every policy that person holds. The payout mobile is verified by a one-time code before any money moves. (Built) | Flag several policies paying into the same PayNow account. (Designed) |
| Cover that runs on after it should stop | Payouts stop when the term ends, and a lapsed policy cannot be restarted from the dashboard. (Built) | None needed |
| A customer declined before | Goes to the underwriter queue with the reason. (Built) | None needed |
| A faulty station | A station sending under half its data is skipped. Stations can be put on hold, as S142 and S128 are now. (Built) | Flag stations far out of line with their neighbours. (Designed) |

Every AI flag goes to a person. An AI check may clear plainly normal cases on its own once it has proved itself, but a decline always stays with an underwriter. This matches the ladder Income's head of AI described, and the FEAT work MAS has already done on this exact use: in the Veritas consortium, UOB, AXA and Accenture applied MAS's ethics and accountability method to insurance fraud detection.

The gap to close: today nothing compares a shop's SSIC code with the product it picks. A shop with code 47102 (mini-mart) could pick cooked food. A simple table of which products each SSIC code may choose would close most of this without any AI, and it should come first.

## What our models can and cannot do yet

The models are tested on years they never saw, against two simple baselines: "same as this month in past years" and "same as yesterday". The score below is average precision, from 0 to 1, for how well a model picks out the days that reach the first payout level. Higher is better.

| Forecast | Best model | Best simple baseline |
| --- | --- | --- |
| Haze, 1 day ahead | 0.86 | 0.64 |
| Haze, 7 days ahead | 0.47 | 0.35 |
| Heat, 1 day ahead | 0.41 | 0.17 |
| Rain, 1 day ahead | 0.13 | 0.10 |
| Haze days next month | No model beat the baseline | |

So the models are useful for warnings, especially haze a day ahead, and weak for rain. That is another reason they must not decide prices or payouts. Figures from `ml/results/report.md`.

## For the slide

| Distributing the product | Handling claims | Weeding out abuse |
| --- | --- | --- |
| AI reads the shop from a sentence or photo and fills in the sign-up (built on the map) | No claim form: NEA reading, published formula, PayNow (built) | Rules first: 30-day wait, 12 or 24 month terms, one payout a day, verified payout mobile (built) |
| A price and proof numbers for the stall's own place (built) | Every payout saves the reading and the rule, so anyone can check it (built) | AI flags odd patterns to an underwriter: category mismatch, one account for many policies, sign-up bursts before haze (designed) |
| Cover texted in 4 languages (built) | AI checks each day's payouts afterwards and never holds one back (designed) | AI flags faulty stations, like the one we found by hand (designed) |

What to say: "Income asked us to show AI in three places. In distribution, AI reads the shop so the adviser's sale takes minutes. In claims, we removed the claim: the payout is a published rule on NEA's data, and AI only checks and explains it afterwards. In abuse, fixed rules do most of the work, and AI watches for patterns and hands them to a person. AI never decides who gets paid."

## Questions for Income

1. Would Income's advisers use the shop reader inside their own sales tools, or only through our buy page?
2. Which abuse patterns has Income seen on small, cheap covers like Stallholder Insurance? We would rather start from Income's real cases than from our guesses.
3. Does Income's fraud team already have checks we should plug into, rather than building our own?

## Sources

- The brief: `docs/problem-statements.md`, section 1, must-haves and directions.
- Income's product lead: Notion, "Mentor session 1, 15 Nov: Income private session (Safe Day feedback)", and the Comment on the todo this page answers.
- Income and IBM Watson Explorer, 5 June 2017: [Income press release](https://www.income.com.sg/about-us/corporate-information/press-releases/income-becomes-the-first-insurer-in-singapore-to-u).
- Parametric cover and moral hazard: [PwC, Basis risk in parametric insurance (2024)](https://www.pwc.ch/en/publications/2024/Basis_risk_in_parametric_insurance_challenges_and_mitigation_strategies.pdf); [Picard, EGRIE 2022](https://www.wu.ac.at/fileadmin/wu/d/i/finance/EGRIE_2022/Papers/B1.1._Picard.pdf).
- MAS Veritas and insurance fraud detection: [MAS media release, 2022](https://www.mas.gov.sg/news/media-releases/2022/mas-led-industry-consortium-publishes-assessment-methodologies-for-responsible-use-of-ai-by-financial-institutions).
- Code: `api/kyc.py`, `api/main.py` (buy checks, referrals), `api/onboarding.py`, `api/readings.py`, `api/payout_flow.py`, `api/payout_api.py`, `api/sms.py`.
- Models: `ml/README.md`, `ml/results/report.md`.
- Basis risk: `docs/notes/basis-risk-2026-11-15.md`.
- Distribution and commission: `docs/notes/distribution-proposal-2026-11-15.md`.
