# Testing plan: PayNow payouts and SMS (15 Nov 2026)

Owner: Rafael. Notion TODO: **"Whole payout flow using PayNow + the SMS flow"** (P1). This plan also
covers the part of **"Write the one-SMS product explanation"** (P0) that this branch delivers: the
welcome SMS and the same text at every point of sale. Design: `payout-flow-design-2026-11-15.md`.

## 1. What is being tested

| Piece | Where |
| --- | --- |
| PayNow account, OTP check, masked proxy | `api/payout_api.py`, `api/paynow.py`, `api/sms.py` |
| Payout run: assess, cap, waiting period, pay, hold, fail, retry, reject | `api/payout_flow.py` |
| Texts: welcome, paid, held, failed, code; English and Mandarin; SMS parts | `api/sms.py` |
| Cover text at the point of sale (`GET /api/cover-text`) | `api/payout_api.py`, `site.js`, `buy.js`, `map.js`, landing page |
| Screens: stallholder payouts and inbox, insurer run and payout list | `api/site/payouts.js` |
| First week's premium by PayNow at sign-up (simulated QR and bank screen) | `api/premium.py`, `api/site/buy.js`, `/paynow-demo/` |

PayNow and the SMS gateway are simulated (design decision 1). A PayNow proxy ending `0000` fails.

**Languages for the demo: English and Mandarin.** Customers can pick only these two; the API refuses
`ms` and `ta`. The Malay and Tamil texts stay in `api/sms.py`, still tested for length, to switch
back on (one line: `sms.LANGUAGES`) once a native speaker has checked them. Every English and
Mandarin text fits one SMS. Mandarin texts leave out the "SafeDay：" prefix to fit 70 characters:
the phone shows SafeDay as the registered sender ID. The one-time code text keeps the brand.

## 2. Brief requirements and how each is checked

| Requirement (problem statement / team decision) | How SafeDay meets it | Checked by |
| --- | --- | --- |
| Pay when claimants need it; no slow loss assessment | Automatic payout on the day's reading; no claim form | `test_closure_day_pays_by_paynow_and_texts_the_stallholder`, manual step C |
| Triggers on independent, verifiable data | Paid text quotes the NEA/PUB reading, e.g. "NEA rain 52.4mm/h" | `test_paid_text_quotes_the_nea_reading_that_triggered_it`, `test_history_run_records_the_readings_it_used` |
| Trigger, payout and exclusions in one SMS in the customer's language | Welcome SMS: all triggers, 7am-7pm, daily amount, yearly cap, start day, no-pay sentence | `test_sms_texts.py` (length per tier and language), `test_welcome_text_explains_the_cover_with_the_tariff_numbers` |
| Say plainly when it does not pay, at the point of sale | "Else no pay, even if you lose income." on landing, buy confirm step, dashboard, risk atlas | `test_cover_text_is_public_and_matches_the_welcome_sms`, manual step F |
| Cap the number of payable days | Daily payout × max days per year, over the 365 days to the loss date | `test_yearly_cap_limits_what_is_paid` |
| 30-day waiting period (locked 15 Nov) | Days before purchase + 30 (Singapore date) count as `waiting_period` | the three waiting-period tests |
| Collect only the data needed (PDPA) | PayNow proxy and one mobile. No NRIC. OTP codes hashed, never stored in clear | `test_payout_account_is_returned_masked_with_the_paynow_name`, manual step A |
| Nothing to game | Same day never paid twice; one payout per user per day; one text per payout and kind | `test_running_the_same_day_twice_pays_once`, `test_payout_schema.py` |
| Explainable decisions | Every status change logged in `payout_events` with actor and reason | `test_payout_history_is_kept_in_order` |

## 3. Automated tests

Run `uv run pytest -q` (187 tests, all passing on 15 Nov) and `uvx ruff check api tests`.

| File | Tests | Covers |
| --- | --- | --- |
| `tests/test_payout_schema.py` | 8 | Tables, unique day per user, unique text per payout |
| `tests/test_payout_api.py` | 36 | Account, OTP, runs, hold/fail/retry/reject, cap, waiting period, roles, texts |
| `tests/test_premium_payments.py` | 15 | Premium payment: start, QR, pay, cancel, expiry, one use, buy checks |
| `tests/test_sms_texts.py` | 26 | SMS parts, every tier × language, all 103 hawker centres, cover-text endpoint, demo languages |

## 4. Manual test script (local, http://127.0.0.1:8000)

Use `example.test` accounts only. To test a payout before the 30-day wait ends, backdate the test
policy in the local `api/tariff.db` (gitignored), for example
`update policies set started_at='2026-09-01 00:00:00' where user_id=<test user id>`.

**A. PayNow setup (stallholder)**
1. Register a stallholder and open the dashboard. Expect the tier cards with the ● tier's SMS below them.
2. Save PayNow `+6591234567`, language English. The language list offers only English and 中文 (Mandarin). Expect `+65 ****4567`, the PayNow name and "not verified".
3. Try `91234567` and `+6571234567`. Expect a clear error and nothing saved.
4. Pick UEN. Expect the "Mobile for texts" field to appear.

**B. Mobile check and welcome SMS**
1. Click "Text me a code" and enter a wrong code: expect "Wrong code". After five wrong tries: expect "Too many tries".
2. Ask for a new code and enter it: expect "verified". The inbox shows the welcome SMS with the tier's S$/day, max days and a start day 30 days after purchase.
3. Verify again: expect no second welcome.

**C. Payout run (insurer)**
1. Register an insurer, open the dashboard and run "Enter a reading" with rain 52.4 for a day after the wait. Expect "1 paid", a `paid` row and the SMS bubble under it.
2. Run the same day again: expect "already assessed" and no second payout.
3. Run "NEA history" for a past day: expect the readings used to be stored on the payout.
4. Run a day before the wait ends: expect "waiting period" and no payout.

**D. Hold, fail, retry, reject**
1. With a stallholder whose mobile isn't verified, run a day: expect `held` and a "verify your mobile" text. Verify: expect it to become `paid`.
2. Use a PayNow proxy ending `0000` and run a day: expect `failed` with a reason and a failed text. Change the proxy and click Retry: expect `paid`.
3. Reject a held payout with a reason: expect `rejected` with the reason in the history. Try to reject a paid payout: expect an error.

**E. Cap**
1. Run more bad days than the tier's max days: expect the extra days `capped`, or a part payout shown as "of S$…".

**F. Point-of-sale text (same text everywhere)**
1. Landing page: the bubble shows the Tier 1 text. Switch English / 中文 and check the part count under it (both "one SMS").
2. Buy flow (`/buy/`): add SafeDay, pick a tier and reach "Check and confirm". Expect "What you are buying, in the SMS we will send you" with that tier's text.
3. Risk atlas: click a hawker centre. Expect "The policy in one SMS" with the same words as the cover-text endpoint.
4. Compare all three with `GET /api/cover-text?tier=<tier>&language=<lang>`: the words must match.

**G. Languages**
1. Set the language to 中文 and repeat B and C. Expect the welcome and paid texts in Mandarin, with dates like "12月15日".
2. Send `sms_language: "ms"` to `PUT /api/payout-account`: expect 422.

**H. Paying the first premium by PayNow (simulated)**
1. Open `/buy/`, click Next to the Pay step and keep PayNow. Click "Pay S$…". Expect a QR, the payee "SafeDay by Income (demo)", the amount, a reference `SDP-…` and "paying by itself in 20 s".
2. Without scanning: after about 20 seconds the page shows "You are covered" with that reference and "Paid by PayNow".
3. Start again and scan the QR with the phone's camera app (or click "open it here") within 20 seconds. Expect a "Payment successful" screen with the same amount and reference, and the laptop finishes straight away.
4. Pick GIRO instead: the QR disappears and the purchase finishes with a `DEMO-` reference.

## 5. Known gaps (say so in the demo; don't claim them)

- **Mandarin wording is compressed:** to fit 70 characters it uses 7-19时, 日赔≤ and 否则亏损也不赔, and has no "SafeDay：" prefix. A native speaker should check it reads naturally.
- **Sender ID:** the Mandarin texts rely on the phone showing "SafeDay" as the sender. That needs the name registered with the Singapore SMS Sender ID Registry; the demo's simulated gateway doesn't show a sender.
- **Malay and Tamil are off for the demo:** the brief asks for the customer's language; say these come after the demo.
- **"Say it back" test:** the brief asks that customers can say back what the product does. This hasn't been done with a hawker or rider yet; it needs one English and one Mandarin speaker.
- **The premium QR is not a PayNow code:** it links to the simulated bank screen, so it can't move real money, and a real banking app won't recognise it. On a laptop, the QR uses the laptop's Wi-Fi address instead of `127.0.0.1`, so start the server with `--host 0.0.0.0` and put the phone on the same Wi-Fi. Networks that keep devices apart (some venue or guest Wi-Fi) block this; then use a phone hotspot.
- **Real providers:** PayNow and the SMS gateway are simulated. A real rollout needs a bank's PayNow API and an SMS provider with a registered Singapore sender ID.
- **Feed failure:** a station with no row for a day reads 0, because the readings file leaves out zero rows. A station outage therefore looks like a dry, cool day. The fallback is a manual run from the insurer desk.
- **Station vs stall:** readings come from the nearest NEA station, not the stall. The paid text names the centre, not the station.
- **Challenge flow:** challenging a payout or a non-payout (P0 TODO, locked 15 Nov) isn't built yet.

## 6. Checklist

Automated
- [ ] `uv run pytest -q` passes (187)
- [ ] `uvx ruff check` passes for the payout files

PayNow and mobile
- [ ] Valid mobile saved and masked; PayNow name shown
- [ ] Non-Singapore mobiles rejected with a clear message
- [ ] UEN shows the extra mobile field
- [ ] Wrong code rejected; 5 wrong tries lock; a new code works
- [ ] The code text in the inbox shows `******`, never the code

Payouts
- [ ] Manual run pays a covered stallholder the same day
- [ ] The same day run twice pays once
- [ ] NEA history run stores the readings used
- [ ] Day inside the 30-day wait → `waiting_period`, no payout
- [ ] Unverified mobile → `held`, paid after verifying
- [ ] Proxy ending `0000` → `failed`; retry pays after the proxy is fixed
- [ ] Reject needs a reason; paid payouts can't be rejected
- [ ] Yearly cap stops or trims payouts
- [ ] Stallholder sees only their own payouts; stallholders can't run payouts

Texts
- [ ] Welcome SMS after cover plus a verified mobile, once per cover
- [ ] Welcome names WBGT, rain, PSI, flood, 7am-7pm, S$/day, max days, start day and "even if you lose income"
- [ ] Paid SMS quotes the NEA reading, amount, masked PayNow and ref, and the centre when it fits
- [ ] English and Mandarin texts are one SMS at every tier and centre
- [ ] Insurer desk shows each payout's SMS under its row
- [ ] Texts arrive in the chosen language (English or Mandarin); Malay and Tamil are refused

Paying at sign-up (PayNow, simulated)
- [ ] Pay step shows the QR, payee, amount, `SDP-` reference and countdown
- [ ] Without scanning, the purchase finishes by itself after about 20 seconds
- [ ] Scanning (camera app) shows "Payment successful" with the same amount and reference
- [ ] A payment can't be reused or paid twice; an expired one asks for a new QR
- [ ] GIRO still finishes without PayNow

Point of sale
- [ ] Landing, buy confirm step, dashboard and risk atlas show the same text as `/api/cover-text`
- [ ] Language switch shows English and 中文 only, on landing, buy and dashboard
- [ ] No SMS bubble still shows the old hard-coded triggers ("PSI>100", "No payout below these levels")

Before the demo
- [ ] Native-speaker check of the 中文 texts
- [ ] "Say it back" test with at least one hawker
- [ ] Demo accounts are `example.test`; no real mobiles or PayNow numbers used
