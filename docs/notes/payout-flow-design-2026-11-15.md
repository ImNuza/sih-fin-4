# Payout flow: PayNow transfer and SMS alert (database design)

Draft for the team, 15 Nov 2026. Covers the tables. The API and the UI flow come after we agree on these.

## The flow in one line

NEA readings for a day cross a band → each active policy in that region is assessed with `calculator.assess` → a payout row is created → it is sent to the stallholder's PayNow proxy → when the transfer settles, an SMS tells them how much, why and the reference.

## What is in place today

The schema is not in a migration folder. `api/store.py` and `api/accounts.py` declare SQLAlchemy tables and `metadata.create_all` creates any that are missing when the API starts. The same code runs on SQLite (`api/tariff.db`, laptop) and Postgres 18 (`db` service in `compose.yaml`, hosted, no internet).

| Table | Holds | Notes that matter for payouts |
|---|---|---|
| `tariff_versions` | Every saved tariff, append-only. | A payout records the version it was assessed under. |
| `users` | SME and insurer accounts. | No phone number or bank details. No foreign keys anywhere. |
| `sessions` | Login tokens. | |
| `policies` | One cover per stallholder: tier, `daily_payout_sgd`, `max_paid_days_per_year`, `started_at`. | Buying a new tier **hard-deletes** the old row, and so does cancel. Money is `Float`. |

Two constraints follow:

1. **`create_all` adds tables but never alters them.** A new column on `users` or `policies` would not reach the hosted Postgres without a manual `ALTER`. The design below therefore adds new tables only and leaves the existing four alone.
2. **Policies disappear.** A payout must still explain itself after its policy is replaced or cancelled, so it keeps a snapshot of the policy terms it was paid under instead of relying on a join.

## New tables

Money in the new tables is integer cents (`amount_cents`), not `Float`, so sums and caps are exact. Times are UTC like the rest of the schema. `loss_date` is the Singapore calendar date of the bad day (AGENTS.md: group by `Asia/Singapore`).

### `payout_accounts`: where to pay and whom to text

One row per stallholder. A separate table, not new `users` columns, for the `create_all` reason above.

| Column | Type | Notes |
|---|---|---|
| `user_id` | int, PK | One account per user. |
| `paynow_proxy_type` | str | `mobile` or `uen`. No NRIC/FIN: PDPC's advisory guidelines restrict collecting NRIC numbers, and a mobile or UEN proxy is enough to pay. |
| `paynow_proxy` | str | `+6591234567` or the UEN. Full value is needed to pay; the API only ever returns it masked. |
| `paynow_name` | str, null | Name the PayNow lookup returns, shown to the user to confirm before saving ("Pay to TAN AH KOW?"). |
| `sms_mobile` | str | E.164, Singapore only (`+65` and 8 digits starting 8 or 9). Often the same as the proxy. |
| `sms_language` | str | `en`, `zh`, `ms` or `ta`. The brief asks that the trigger, payout and exclusions fit in one SMS in the customer's language. |
| `mobile_verified_at` | datetime, null | Set after an SMS one-time code. Payouts wait until it is set. |
| `created_at`, `updated_at` | datetime | |

### `payouts`: one row per insured per bad day

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | Shown to customers as `SD-000123`. |
| `user_id` | int | |
| `policy_id` | int | Snapshot only, no foreign key, since policies are hard-deleted. |
| `loss_date` | date | Singapore date of the bad day. |
| `region`, `centre`, `product`, `tier` | str | Copied from the policy at assessment time. |
| `daily_payout_cents` | int | Policy term at assessment time. |
| `tariff_version` | int | Tariff the assessment used. |
| `readings` | JSON | Hazard key to reading, exactly what went into `calculator.assess`. |
| `source` | str | `nea_history`, `nea_live` or `manual` (an insurer entering a PUB flood or closure order). |
| `loss_percent` | float | From the assessment. |
| `main_hazard` | str | Hazard with the largest loss that day; the SMS names it. |
| `assessed_cents` | int | `loss_percent × daily_payout`, before the yearly cap. |
| `amount_cents` | int | What is paid after the yearly cap. 0 when the cap is used up. |
| `status` | str | See the lifecycle below. |
| `paynow_proxy_type`, `paynow_proxy_masked` | str | Where it went, snapshot for the statement (`+65 ****4567`). |
| `provider_reference` | str, unique, null | The bank or PayNow provider's transfer id. Webhooks match on it. |
| `failure_reason` | str, null | |
| `created_at`, `updated_at`, `paid_at` | datetime | |

**Unique `(user_id, loss_date)`.** Re-running the trigger job for a day cannot pay twice. This is the main idempotency guard.

**Yearly cap.** Today's quote caps a year at `daily_payout × max_paid_days_per_year`. A new payout gets `min(assessed, cap − paid so far in the policy year)`, where the policy year runs from `started_at`. Because buying a new tier resets `started_at`, the cap sum should run over the user's payouts in the last 365 days, not per `policy_id`, so switching tiers cannot reset the cap.

**Lifecycle.**

```
assessed ──► approved ──► sending ──► paid
   │             │            │
   │             │            └──► failed ──► approved (retry)
   │             └──► held ──► sending   (once the mobile is verified)
   ├──► capped   (yearly cap used up, amount 0, kept so the day stays explainable)
   └──► rejected (insurer, with a reason; also from held or failed)
```

`assessed` to `approved` is automatic (decision 2 below). The PayNow simulator settles at once, so `sending` to `paid` or `failed` happens in the same request; a real provider would report it later through a callback.

### `payout_events`: the audit trail

Append-only, one row per status change. A payout's history can always be read back and nothing is overwritten.

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `payout_id` | int, FK → `payouts.id` | |
| `from_status`, `to_status` | str | `from_status` is null for the first row. |
| `actor` | str | `system`, `paynow-webhook` or the insurer's email. |
| `detail` | JSON, null | Provider response, reason for a rejection, and so on. Never the full proxy. |
| `at` | datetime | |

### `sms_messages`: every text sent

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `user_id` | int | |
| `payout_id` | int, FK → `payouts.id`, null | Null for one-time codes. |
| `kind` | str | `otp`, `payout_paid`, `payout_failed`, `payout_held`. |
| `to_mobile` | str | Needed to resend. |
| `language` | str | |
| `body` | str | Exactly what was sent. Null for `otp`, so codes are never stored in clear. |
| `provider_message_id` | str, unique, null | |
| `status` | str | `queued`, `sent`, `delivered`, `failed`. |
| `error` | str, null | |
| `created_at`, `sent_at`, `delivered_at` | datetime | |

**Unique `(payout_id, kind)`** where `payout_id` is set: one "paid" text per payout, even if the PayNow webhook arrives twice.

### `sms_codes`: one-time codes for verifying the mobile

| Column | Type | Notes |
|---|---|---|
| `user_id` | int, PK | One live code per user; a new request replaces it. |
| `code_hash` | str | scrypt like passwords in `accounts.py`. |
| `expires_at` | datetime | 10 minutes. |
| `attempts` | int | Locked after 5. |

## When a station's feed is missing (added 15 Nov 2026)

The brief asks for "a fallback if the feed fails". Payouts, the live score on the map, the
ten-year replay and the day replay now all read a place by one rule (`api/readings.py`).

The place is where the policy is priced: the hawker centre, else the shop's postcode area,
else the middle of the region (platform workers, who work across an area). A centre that has
left the map or a postcode with no postal sector also falls back to the region's middle.

Stations are the ones the price reads (`data/processed/site_hazard_readings.csv`: 116 rain
gauges, 31 WBGT stations), ranked by distance from the place. A place may read its nearest
station and any other station within 5 km (90% of these gauges and WBGT stations have another
station within 2.9 km and 4.1 km). Per hazard:

1. rain: the median of the first 3 of those gauges that reported (3 is the rain hazard's
   `sites_used` in the tariff, so the payout reads as many gauges as the price);
2. rain, if none of them reported: MSS's published highest 60-minute rain for the nearest gauge
   that day;
3. heat: the first of those WBGT stations that reported (heat `sites_used` is 1; with more, the
   median of that many). Heat has no MSS record to fall back on;
4. haze: the region's PSI, else the median of the regions that reported;
5. nothing: the policy counts as `awaiting_data`. No payout row is made, so running the same day
   again once the data arrives can still pay it. Late, never refused.

A station that sent under half its work-hour data counts as not reported.
`scripts/build_day_readings.py` writes a `rain_missing` or `heat_missing` row for each priced
station that did not report on a day the feed covers (a day the whole feed was down included),
and a `rain_mss` row where MSS has a record for a missing gauge. Rain rows are kept from 1 mm
and heat rows above 0, so a station that reported with no row read 0.

Each payout keeps its readings and, in the `assessed` event, the rule that gave each one, for
example `median of S72, S118, S79`, `median of S118, S79 (S72 did not report)`,
`S145 (S144 did not report)`, `MSS daily record for S72 (no gauge within 5 km reported)` or
`median of east, north (south did not report)`. `GET /api/payouts` returns it as `basis`.

The live score uses the same rule on today's snapshot, with no MSS record live: a hazard with
no eligible station reporting reads 0. A replay reads a hazard that would wait as 0 too. Before
this, a missing station read as 0, so a broken feed meant no payout, and the nearest WBGT station
of many centres had reported on few days.

## Example SMS (English, 1 segment)

> SafeDay: S$62.40 sent to PayNow +65 ****4567 for heavy rain at Maxwell on 14 Nov. Ref SD-000123. No claim needed. Reply HELP for help.

## Decisions

1. **Both providers are simulated.** No bank offers PayNow payouts without a corporate account (for example DBS RAPID or OCBC's APIs), and the hosted API container has no internet. A built-in PayNow simulator does proxy lookup, transfer and an asynchronous settlement callback; a built-in SMS outbox records texts and shows them in the UI. Both sit behind a small provider interface so a real bank API or SMS gateway can replace them later.
2. **Payouts go out automatically.** The readings decide (parametric). A payout moves from `assessed` to `approved` without a click; the insurer can still reject one with a reason before it is sent.
3. **The insurer desk starts a run.** "Run payouts for 14 Nov" assesses every active policy for that Singapore date from the committed NEA history (or today's live readings). No scheduled job for now.
4. **30-day waiting period** (team decision, 15 Nov 09:28). A policy pays only for Singapore dates from the purchase date plus 30 days. Earlier days count as `waiting_period` in the run summary and create no payout row. This stops people buying cover only when bad weather is forecast, which the brief warns about (Igloo x DANA).
