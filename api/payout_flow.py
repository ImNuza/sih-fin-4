"""Assess a day's loss for each policy, cap it, pay it by PayNow and text the stallholder.

Payouts are automatic: once readings give a loss, the payout is approved and sent. Every
status change adds a payout_events row, so the full history of a payout can be read back.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, func, insert, select, update

from api import calculator, paynow, sms
from api.accounts import application_profile, applications, policies
from api.models import Tariff
from api.payouts import payout_accounts, payout_events, payouts, sms_messages
from api.readings import SiteReadings

SINGAPORE = ZoneInfo("Asia/Singapore")
CAP_WINDOW_DAYS = 365
# Team decision, 15 Nov 2026: cover pays from 30 days after purchase, so people cannot buy
# only when bad weather is forecast (the brief's Igloo x DANA warning).
WAITING_PERIOD_DAYS = 30
COUNTED_TOWARDS_CAP = ("assessed", "approved", "held", "sending", "paid", "failed")
REJECTABLE = ("assessed", "approved", "held", "failed")
RUN_OUTCOMES = (
    "paid", "held", "failed", "capped", "no_loss", "already_assessed", "waiting_period",
    "cover_ended", "awaiting_data",
)


class WrongStatus(ValueError):
    pass


def to_cents(sgd: float) -> int:
    return round(sgd * 100)


def reference(payout_id: int) -> str:
    return f"PY-{payout_id:06d}"


def record(db: Connection, payout_id: int, from_status: str | None, to_status: str, actor: str,
           detail: dict | None = None) -> None:
    db.execute(
        insert(payout_events).values(
            payout_id=payout_id, from_status=from_status, to_status=to_status, actor=actor,
            detail=detail, at=datetime.now(UTC),
        )
    )


def move(db: Connection, payout_id: int, from_status: str, to_status: str, actor: str,
         detail: dict | None = None, **changes) -> None:
    db.execute(
        update(payouts)
        .where(payouts.c.id == payout_id)
        .values(status=to_status, updated_at=datetime.now(UTC), **changes)
    )
    record(db, payout_id, from_status, to_status, actor, detail)


def owed_in_cap_window(db: Connection, user_id: int, loss_date: date) -> int:
    """Cents already owed for the 365 days up to loss_date, across every policy the user held."""
    window_start = loss_date - timedelta(days=CAP_WINDOW_DAYS - 1)
    total = db.execute(
        select(func.coalesce(func.sum(payouts.c.amount_cents), 0)).where(
            payouts.c.user_id == user_id,
            payouts.c.status.in_(COUNTED_TOWARDS_CAP),
            payouts.c.loss_date.between(window_start, loss_date),
        )
    ).scalar_one()
    return int(total)


def cover_ends(db: Connection, user_id: int) -> date | None:
    """The day the term of the owner's latest application ends; cover stops from that day.
    None for an account with no buy-flow application, which has no term on record."""
    return db.execute(
        select(application_profile.c.cover_ends)
        .join(applications, applications.c.id == application_profile.c.application_id)
        .where(applications.c.user_id == user_id)
        .order_by(applications.c.id.desc())
    ).scalar()


def as_utc(moment: datetime) -> datetime:
    """SQLite drops the time zone. Every time is saved in UTC, so put it back."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def first_covered_day(started_at: datetime) -> date:
    """Singapore date the cover first pays for."""
    return as_utc(started_at).astimezone(SINGAPORE).date() + timedelta(days=WAITING_PERIOD_DAYS)


def text(db: Connection, payout, account, kind: str) -> None:
    body = sms.payout_text(
        kind,
        account.sms_language,
        payout.main_hazard,
        day_colour=sms.day_name(account.sms_language, payout.loss_percent),
        loss=f"{payout.loss_percent:.0f}",
        amount=f"{payout.amount_cents / 100:.2f}",
        proxy=paynow.mask(account.paynow_proxy_type, account.paynow_proxy),
        centre=payout.centre or payout.region,
        day=sms.day_text(account.sms_language, payout.loss_date),
        ref=reference(payout.id),
    )
    sms.send(db, payout.user_id, kind, account.sms_mobile, account.sms_language, body, payout.id)


def welcome_contact(db: Connection, user_id: int) -> tuple[str, str] | None:
    """Where the welcome text goes, and in which language: the verified PayNow mobile, else the
    mobile given at sign-up (a landline is never texted). None when there is no mobile."""
    account = db.execute(
        select(payout_accounts).where(payout_accounts.c.user_id == user_id)
    ).first()
    language = sms.preferred_language(db, user_id) or (account.sms_language if account else "en")
    if account is not None and account.mobile_verified_at is not None:
        return account.sms_mobile, language
    phone = db.execute(
        select(applications.c.phone)
        .where(applications.c.user_id == user_id)
        .order_by(applications.c.id.desc())
    ).scalar()
    mobile = f"+65{phone}" if phone else None
    return (mobile, language) if mobile and paynow.is_valid_mobile(mobile) else None


def bought_at(db: Connection, policy) -> datetime:
    """When the policy was bought: its start, or for cover starting on a later date, the time of
    the buy-flow application that bought it."""
    started = as_utc(policy.started_at)
    if started <= datetime.now(UTC):
        return started
    applied = db.execute(
        select(applications.c.created_at)
        .where(applications.c.user_id == policy.user_id)
        .order_by(applications.c.id.desc())
    ).scalar()
    return as_utc(applied) if applied else started


def send_welcome_if_due(db: Connection, user_id: int, tariff: Tariff) -> None:
    """Text the cover in one SMS once the customer has paid for a policy and has a mobile.

    Sent once per policy: a new tier starts a new policy and gets its own welcome.
    """
    policy = db.execute(select(policies).where(policies.c.user_id == user_id)).first()
    contact = welcome_contact(db, user_id)
    if policy is None or contact is None:
        return
    welcomed = db.execute(
        select(sms_messages.c.id).where(
            sms_messages.c.user_id == user_id,
            sms_messages.c.kind == "welcome",
            sms_messages.c.created_at >= bought_at(db, policy),
        )
    ).first()
    if welcomed:
        return
    mobile, language = contact
    body = cover_text(language, policy.weekly_premium_sgd, policy.daily_payout_sgd)
    sms.send(db, user_id, "welcome", mobile, language, body)


def cover_text(language: str, weekly_sgd: float | None, payout_sgd: float) -> str:
    """The cover in one SMS. Sent after payment and shown wherever cover is sold. The tier and
    yearly cap are on the site the SMS links to, not in the SMS."""
    return sms.welcome_text(language, weekly_sgd, payout_sgd, WAITING_PERIOD_DAYS)


def first_day_if_bought_now() -> date:
    return first_covered_day(datetime.now(UTC))


def send(db: Connection, payout_id: int, actor: str = "system") -> str:
    """Pay an approved, held or retried payout. Returns its new status."""
    payout = db.execute(select(payouts).where(payouts.c.id == payout_id)).one()
    account = db.execute(
        select(payout_accounts).where(payout_accounts.c.user_id == payout.user_id)
    ).first()
    if account is None or account.mobile_verified_at is None:
        move(db, payout_id, payout.status, "held", actor, {"reason": "no verified payout account"})
        if account is not None:
            text(db, payout, account, "payout_held")
        return "held"
    masked = paynow.mask(account.paynow_proxy_type, account.paynow_proxy)
    move(db, payout_id, payout.status, "sending", actor, {"to": masked},
         paynow_proxy_type=account.paynow_proxy_type, paynow_proxy_masked=masked)
    result = paynow.transfer(account.paynow_proxy)
    if result.settled:
        move(db, payout_id, "sending", "paid", "paynow",
             {"provider_reference": result.provider_reference},
             provider_reference=result.provider_reference, paid_at=datetime.now(UTC),
             failure_reason=None)
        text(db, payout, account, "payout_paid")
        return "paid"
    move(db, payout_id, "sending", "failed", "paynow", {"reason": result.failure_reason},
         failure_reason=result.failure_reason)
    text(db, payout, account, "payout_failed")
    return "failed"


def not_payable_reason(db: Connection, policy, loss_date: date, site: SiteReadings,
                       apply_waiting_period: bool = True) -> str | None:
    """Why a day is not assessed for this policy, before its readings are scored. None: the
    readings decide. A hazard with no reading yet is 'awaiting_data', so a later run can pay."""
    already = db.execute(
        select(payouts.c.id).where(
            payouts.c.user_id == policy.user_id, payouts.c.loss_date == loss_date
        )
    ).first()
    if already:
        return "already_assessed"
    if apply_waiting_period and loss_date < first_covered_day(policy.started_at):
        return "waiting_period"
    ends = cover_ends(db, policy.user_id)
    if ends is not None and loss_date >= ends:
        return "cover_ended"
    if site.waiting_for:
        return "awaiting_data"
    return None


def assess_policy(db: Connection, policy, tariff: Tariff, tariff_version: int, loss_date: date,
                  site: SiteReadings, source: str, apply_waiting_period: bool = True) -> str:
    """Assess one policy for one day."""
    reason = not_payable_reason(db, policy, loss_date, site, apply_waiting_period)
    if reason is not None:
        return reason
    readings = site.readings
    # The loss comes from today's tariff; the money from the daily amount the policy was sold with.
    assessment = calculator.assess(
        tariff, policy.product, policy.tier, readings, policy.daily_payout_sgd
    )
    if assessment.payout_sgd <= 0:
        return "no_loss"
    daily_cents = to_cents(policy.daily_payout_sgd)
    cap_left = daily_cents * policy.max_paid_days_per_year - owed_in_cap_window(
        db, policy.user_id, loss_date
    )
    assessed_cents = to_cents(assessment.payout_sgd)
    amount_cents = max(0, min(assessed_cents, cap_left))
    main_hazard = max(assessment.hazards, key=lambda hazard: hazard.loss_percent).hazard
    now = datetime.now(UTC)
    payout_id = db.execute(
        insert(payouts)
        .values(
            user_id=policy.user_id, policy_id=policy.id, loss_date=loss_date,
            region=policy.region, centre=policy.centre, product=policy.product, tier=policy.tier,
            daily_payout_cents=daily_cents, tariff_version=tariff_version, readings=readings,
            source=source, loss_percent=assessment.loss_percent, main_hazard=main_hazard,
            assessed_cents=assessed_cents, amount_cents=amount_cents, status="assessed",
            created_at=now, updated_at=now,
        )
        .returning(payouts.c.id)
    ).scalar_one()
    record(db, payout_id, None, "assessed", "system",
           {"readings": readings, "basis": site.basis, "loss_percent": assessment.loss_percent})
    if amount_cents == 0:
        move(db, payout_id, "assessed", "capped", "system", {"cap_left_cents": cap_left})
        return "capped"
    move(db, payout_id, "assessed", "approved", "system", {"rule": "automatic"})
    return send(db, payout_id)


def run_day(db: Connection, tariff: Tariff, tariff_version: int, loss_date: date,
            readings_for: Callable[[object], SiteReadings], source: str,
            regions: set[str] | None) -> dict[str, int]:
    """Assess every policy in force for one day. readings_for gives each policy's readings."""
    counts = dict.fromkeys(RUN_OUTCOMES, 0)
    for policy in db.execute(select(policies)).all():
        if regions and policy.region not in regions:
            continue
        outcome = assess_policy(db, policy, tariff, tariff_version, loss_date,
                                readings_for(policy), source)
        counts[outcome] += 1
    return counts


def demo_day(db: Connection, user_id: int) -> date:
    """Today in Singapore, or the latest earlier day not yet assessed, so a demo can be rerun."""
    assessed = set(
        db.execute(select(payouts.c.loss_date).where(payouts.c.user_id == user_id)).scalars()
    )
    day = datetime.now(SINGAPORE).date()
    while day in assessed:
        day -= timedelta(days=1)
    return day


def pay_demo(db: Connection, policy, tariff: Tariff, tariff_version: int,
             readings: dict[str, float]) -> tuple[str, date]:
    """Pay one stallholder now on readings the insurer enters, to show a payout and its SMS.

    The waiting period is skipped, since a demo customer bought cover minutes ago. The cap,
    the tariff and the one-payout-a-day rule still apply, and the payout is saved as a demo.
    """
    loss_date = demo_day(db, policy.user_id)
    site = SiteReadings(
        readings=readings, basis=dict.fromkeys(readings, "entered by the insurer for a demo")
    )
    outcome = assess_policy(db, policy, tariff, tariff_version, loss_date, site, "demo",
                            apply_waiting_period=False)
    return outcome, loss_date


def release_held(db: Connection, user_id: int) -> None:
    held = db.execute(
        select(payouts.c.id).where(payouts.c.user_id == user_id, payouts.c.status == "held")
    ).scalars()
    for payout_id in list(held):
        send(db, payout_id)


def retry(db: Connection, payout_id: int, actor: str) -> str:
    status = db.execute(select(payouts.c.status).where(payouts.c.id == payout_id)).scalar_one()
    if status != "failed":
        raise WrongStatus(f"Only a failed payout can be retried; this one is {status}")
    move(db, payout_id, "failed", "approved", actor, {"rule": "retry"})
    return send(db, payout_id, actor)


def reject(db: Connection, payout_id: int, reason: str, actor: str) -> None:
    status = db.execute(select(payouts.c.status).where(payouts.c.id == payout_id)).scalar_one()
    if status not in REJECTABLE:
        raise WrongStatus(f"A {status} payout cannot be rejected")
    move(db, payout_id, status, "rejected", actor, {"reason": reason}, failure_reason=reason)
