# AI in SafeDay: what is built and what is designed (15 Nov 2026)

> **To Deval's agent: read this order first.**
> 1. Do not read the rest of this file before you write your own text for the two rows below.
>    It is a second draft. It must not shape your first draft.
> 2. Write your own version first, from the code and the Notion rows.
> 3. Then read this file. Compare the two versions point by point: facts, status labels
>    (built / designed / not merged), cited numbers, proposal paragraph, PPT bullets.
> 4. Keep the better text for each point, or merge the two. Tell Deval which version you kept
>    for each point, and why. Check every number against its source before you keep it.
>
> Who wrote it: Dewa's agent, 15 Nov evening, before Dewa decided that the rows stay with Deval.

Draft text for two Notion rows from the Income mentor session on 15 Nov:

- "AI in three places" (https://app.notion.com/p/419ecd5c15be81aaad85fcbaf5631df4)
- "Automation ladder" (https://app.notion.com/p/419ecd5c15be8109a6e9f780a6889832)

Both rows belong to Deval. The asks, as recorded, are in `docs/notes/notion-decisions-sweep-2026-11-15.md`, section 4.

## The rule

**AI never sets the price or the payout.**

- The price comes from the tariff and the station history (`api/calculator.py`, `api/default_tariff.json`).
- The payout comes from the measured NEA reading at the station rule in `api/readings.py`. `api/payout_flow.py` applies the tariff to that reading. No model is in that path.
- So every payout can be explained from the tariff and the reading, as the problem statement asks. The backend notes in `AGENTS.md` (note 3) say the same for the shop reader: it returns a product and a place, never a price.

## Status of each place Income named

| Place Income named | What we have | Status |
|---|---|---|
| 1. Onboarding: read the shop | The "Tell us about your shop" box on the risk map (`api/kyc.py`, `POST /api/map/kyc`). The owner types a few words and can add a photo. One model call proposes a tariff product and a hawker centre or planning area. It asks Claude (`claude-haiku-5-5`), then OpenAI, then Grok, by the first key that is set. With no key, or when the model API cannot be reached, a keyword table answers. The result is a suggestion that the owner confirms. Nothing sent is stored. | **Built** on the map. `tests/test_kyc.py` covers all three model paths with stand-in clients. Only the Grok path was run against the real API. |
| 1b. The same reader inside the buy flow (`/buy/`) | The buy flow asks the class, the licence or postcode and the SSIC code as plain form fields (`api/onboarding.py`). It does not call the shop reader. | **Designed, not built.** |
| 2. Claims with no claim form | There is no claim. Each day, `api/payout_flow.py` reads the stations, finds the loss for each policy, caps it, pays by PayNow and sends a text. This is a fixed rule, not AI. | **Built** (no AI in it, on purpose). |
| 2b. Models of the hazard readings | `ml/` trains models of haze, rain and heat readings and runs a payout back-test (`ml/README.md`). Results are in `ml/results/`. On branch `origin/ml-integration` (9 commits), `ml/serving.py` and `api/model_history.py` fill every hawker centre's history back to 1980 with the trained models and serve 10-day and 10-year outlooks on the dashboards. | Training: **built** on `main`. Model history and outlooks: **on branch `ml-integration`, not merged.** |
| 2c. Customer challenge of a payout | The team dropped the in-product appeal. The customer sees the reading and the rule. A wrong reading or category goes to Income's normal service route (`docs/notes/notion-sweep-2026-11-15-evening.md`, lines 25 and 52). | **Dropped.** The Notion row still says "AI assists on challenge only". That text is out of date. |
| 3. Abuse checks on sign-ups | Rule checks exist now: a past decline sends the application to the underwriter queue (`api/main.py`, `declined_before`, and `api/underwriting.py`). The licence number has a format check (`api/onboarding.py`). Cover pays only from 30 days after purchase (`WAITING_PERIOD_DAYS` in `api/payout_flow.py`), so a customer cannot buy only when bad weather is forecast. | Rule checks: **built.** AI checks: **designed, not built.** |

### Why no model touches the payout

The models predict the weather. They are not good enough to decide money. In the test years, the best next-day heat model (`hist_gbm`) found 133 of 274 real trigger days (recall 0.49). Only 133 of its 411 warnings were right (precision 0.32). F1 was 0.39 (`ml/results/confusion_metrics.csv`, job `heat_h1_classification`, 4,883 station-days). The best next-day haze model (`lightgbm`) did better: F1 0.77, recall 0.83, precision 0.71 (same file, `haze_h1_classification`, 7,035 region-days). These scores are acceptable for a warning or a back-test. They are not acceptable for a payment. The payout reads the real sensor.

## The copilot ladder

Income's head of AI described three steps: copilot first, then automatic action on confident cases, then full automation once it is proved (Notion row "Automation ladder"). We apply it to two places only: the shop reader and the sign-up checks.

We do not apply it to:

- **Payouts.** They are already automatic, by a fixed rule on the measured reading. There is no AI step to climb.
- **Appeals.** The team dropped them (row 2c above).

| Step | Shop reader (onboarding) | Sign-up checks (abuse) |
|---|---|---|
| 1. Copilot (now) | The model proposes the product and the place. The owner and the Income agent or association confirm them. Built on the map today. | Designed: a model reads the sign-up (licence class, place, product, shop text or photo) and flags a mismatch, for example a "cooked food" stall with a photo of a phone shop. Each flag goes to the existing underwriter queue. A person decides. |
| 2. Act on confident cases | Designed: fill the form when the model answer and the keyword table agree. The agent still sees the filled form and can change it. | Designed: a clean application with no flag goes through with no human step. A flagged application still goes to a person. |
| 3. Full automation, once proved | Designed: drop the agent check after Income measures how often agents change the model answer, and accepts that rate. We set no number. Income sets it. | Designed: automatic approval only. A decline always stays with a person. This is our choice, so that each decline gets a human review under the MAS fair dealing outcomes (the proposal covers them in its section 10, `docs/notes/notion-sweep-2026-11-15-evening.md`, line 18). |

This matches the two LLM uses that Income's head of AI named: document checks, and content that a second agent checks (Notion row "Automation ladder"). The shop reader is a document check. Step 2 of the shop reader uses the keyword table as the second check.

## Proposal paragraph

SafeDay uses AI in two places and keeps it out of a third. At sign-up, a shop reader turns a stall owner's own words, and an optional photo, into a suggested product and hawker centre. The owner and their Income agent confirm the suggestion. The reader runs on Claude, OpenAI or Grok. When no model is available, a keyword table answers. Today the reader is on the risk map, and the next step puts it into the buy flow. For abuse, we designed a model that flags a sign-up when its licence, place and description do not match. Each flag goes to the underwriter queue that already handles past declines. Both uses follow Income's copilot ladder: the model suggests, a person confirms, and only proven, confident cases become automatic. A decline always stays with a person. AI never sets the price or the payout. The premium comes from the tariff and the NEA station history. The payout comes from the measured NEA reading at the nearest station. It is paid automatically by PayNow, with no claim form. Our hazard models are for back-tests and outlooks, never for a payment decision. For example, our next-day haze model had an F1 score of 0.77 in the test years.

## PPT bullets

- AI never sets the price or the payout. Price comes from the tariff. Payout comes from the real NEA reading.
- No claim form: the payout is automatic, by PayNow, with a text to the customer, once the reading is in.
- Sign-up: an AI shop reader suggests the product and the place. The owner and the agent confirm. Built today.
- Abuse checks: AI flags sign-ups that do not match. A person decides. Designed, rule checks built.
- Income's copilot ladder: suggest, then act on confident cases, then automate once proven. A decline always stays with a person.
- Hazard models fill 1980 to now and give outlooks for back-tests and warnings, never for payments.

## Open points

- **Branch `ml-integration` is not merged.** The last PPT bullet and the "1980 to now" claim depend on it. If it is not merged before the pitch, say "designed" for the model history and the outlooks.
- **The AI sign-up checks are a design only.** No code, no test, no measured flag rate. Do not show them in the demo as working.
- **The "AI assists on challenge" text in the Notion row is out of date.** The row needs an edit after the team agrees. This note does not edit Notion.
- **Model names in `api/kyc.py`** are the ones in code on 15 Nov. Check them again before the pitch if anyone changes the code.
