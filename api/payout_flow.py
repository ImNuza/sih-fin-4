"""Assess a day's loss for each policy, cap it, pay it by PayNow and text the stallholder.

Payouts are automatic: once readings give a loss, the payout is approved and sent. Every
status change adds a payout_events row, so the full history of a payout can be read back.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, func, insert, select, update

from api import calculator, paynow, sms
from api.accounts import (
    application_profile, applications, policies, policy_haze_bonus, policy_tier_changes,
)
from api.models import HazeBonus, Tariff
from api.payouts import (
    haze_bonus_events, haze_bonus_payouts, payout_accounts, payout_events, payouts, sms_messages,
)
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


def terms_on(db: Connection, policy_id: int, day: date) -> dict:
    """The policy's terms changed by the latest tier change starting by this day, if any."""
    changes = policy_tier_changes
    change = db.execute(
        select(changes)
        .where(changes.c.policy_id == policy_id, changes.c.starts_on <= day)
        .order_by(changes.c.starts_on.desc())
    ).mappings().first()
    if change is None:
        return {}
    return {key: value for key, value in change.items() if key not in ("policy_id", "starts_on")}


def policy_on(db: Connection, policy, day: date) -> SimpleNamespace:
    """A policy with the terms in force on this day, so a late run pays the day as it was."""
    return SimpleNamespace(**{**policy._mapping, **terms_on(db, policy.id, day)})


HazeOn = Callable[[str, date], float | None]
HAZE_BONUS_OUTCOMES = ("haze_bonus_paid", "haze_bonus_held", "haze_bonus_failed")


def run_day(db: Connection, tariff: Tariff, tariff_version: int, loss_date: date,
            readings_for: Callable[[object], SiteReadings], source: str,
            regions: set[str] | None, haze_on: HazeOn) -> dict[str, int]:
    """Assess every policy in force for one day. readings_for gives each policy's readings;
    haze_on(region, day) a past day's haze reading, for the severe haze payout's count.
    The haze_bonus_ counts are the lump sums the run paid, held or failed to send."""
    counts = dict.fromkeys(RUN_OUTCOMES, 0) | dict.fromkeys(HAZE_BONUS_OUTCOMES, 0)
    for policy in db.execute(select(policies)).all():
        if regions and policy.region not in regions:
            continue
        site = readings_for(policy)
        outcome = assess_policy(db, policy_on(db, policy, loss_date), tariff, tariff_version,
                                loss_date, site, source)
        counts[outcome] += 1
        if tariff.haze_bonus is not None:
            today_haze = site.readings.get("haze")
            lump = pay_haze_bonus(db, policy, tariff.haze_bonus, loss_date, today_haze, haze_on)
            if lump is not None:
                counts[f"haze_bonus_{lump}"] += 1
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


def policy_year_start(starts_on: date, day: date) -> date:
    """The latest anniversary of starts_on on or before day (28 Feb for a 29 Feb start)."""
    for years in (day.year - starts_on.year, day.year - starts_on.year - 1):
        try:
            anniversary = starts_on.replace(year=starts_on.year + years)
        except ValueError:
            anniversary = date(starts_on.year + years, 2, 28)
        if anniversary <= day:
            return anniversary
    return starts_on


def unhealthy_days(
    db: Connection, policy, bonus: HazeBonus, first: date, last: date,
    last_haze: float | None, haze_on: HazeOn,
) -> int:
    """Days from first to last with the region's haze at trigger_psi or more, from the readings
    the daily payout uses: the run's own reading on its day, NEA's history on past days, and the
    readings kept with the policy's payouts on days the history lacks."""
    kept = {
        row.loss_date: row.readings.get("haze")
        for row in db.execute(
            select(payouts.c.loss_date, payouts.c.readings).where(
                payouts.c.user_id == policy.user_id, payouts.c.loss_date.between(first, last)
            )
        )
    }
    count, day = 0, first
    while day <= last:
        haze = last_haze if day == last and last_haze is not None else haze_on(policy.region, day)
        if haze is None:
            haze = kept.get(day)
        count += haze is not None and haze >= bonus.trigger_psi
        day += timedelta(days=1)
    return count


def pay_haze_bonus(
    db: Connection, policy, bonus: HazeBonus, loss_date: date, today_haze: float | None,
    haze_on: HazeOn,
) -> str | None:
    """Pay the lump sum once in a policy year, on the day the region's unhealthy haze days reach
    trigger_days (or the first run after). Outside the daily cover's yearly limit. Returns the
    lump sum's status, or None when there is none to pay."""
    addon = db.execute(
        select(policy_haze_bonus).where(policy_haze_bonus.c.policy_id == policy.id)
    ).first()
    if addon is None or loss_date < addon.starts_on:
        return None
    ends = cover_ends(db, policy.user_id)
    if ends is not None and loss_date >= ends:
        return None
    year_starts = policy_year_start(addon.starts_on, loss_date)
    paid_before = db.execute(
        select(haze_bonus_payouts.c.id).where(
            haze_bonus_payouts.c.policy_id == policy.id,
            haze_bonus_payouts.c.policy_year_starts == year_starts,
        )
    ).first()
    if paid_before:
        return None
    days = unhealthy_days(db, policy, bonus, year_starts, loss_date, today_haze, haze_on)
    if days < bonus.trigger_days:
        return None
    now = datetime.now(UTC)
    bonus_id = db.execute(
        insert(haze_bonus_payouts).values(
            user_id=policy.user_id, policy_id=policy.id, policy_year_starts=year_starts,
            loss_date=loss_date, region=policy.region, centre=policy.centre, tier=policy.tier,
            trigger_psi=bonus.trigger_psi, unhealthy_days=days, source="haze_bonus",
            main_hazard="haze", amount_cents=addon.lump_sum_cents, status="approved",
            created_at=now,
        ).returning(haze_bonus_payouts.c.id)
    ).scalar_one()
    db.execute(insert(haze_bonus_events).values(
        bonus_id=bonus_id, from_status=None, to_status="approved", actor="system",
        detail={"rule": "automatic", "unhealthy_days": days}, at=now,
    ))
    return send_haze_bonus(db, bonus_id)


def bonus_reference(bonus_id: int) -> str:
    return f"SDH-{bonus_id:06d}"


def move_bonus(db: Connection, bonus_id: int, from_status: str | None, to_status: str,
               actor: str, detail: dict | None = None, **changes) -> None:
    """Change a lump sum's status and keep the change, as move() does for a daily payout."""
    db.execute(update(haze_bonus_payouts).where(haze_bonus_payouts.c.id == bonus_id)
               .values(status=to_status, **changes))
    db.execute(insert(haze_bonus_events).values(
        bonus_id=bonus_id, from_status=from_status, to_status=to_status, actor=actor,
        detail=detail, at=datetime.now(UTC),
    ))


def send_haze_bonus(db: Connection, bonus_id: int, actor: str = "system") -> str:
    """Pay an approved, held or retried lump sum by PayNow and text the owner, as send() pays
    a daily payout. Returns its new status."""
    bonus = db.execute(select(haze_bonus_payouts).where(haze_bonus_payouts.c.id == bonus_id)).one()
    account = db.execute(
        select(payout_accounts).where(payout_accounts.c.user_id == bonus.user_id)
    ).first()
    amount = f"{bonus.amount_cents / 100:.2f}"
    ref = bonus_reference(bonus_id)

    def text(kind: str, **fields: str) -> None:
        body = sms.TEMPLATES[kind][account.sms_language].format(amount=amount, ref=ref, **fields)
        sms.send(db, bonus.user_id, kind, account.sms_mobile, account.sms_language, body)

    if account is None or account.mobile_verified_at is None:
        move_bonus(db, bonus_id, bonus.status, "held", actor,
                   {"reason": "no verified payout account"})
        if account is not None:
            text("haze_bonus_waiting")
        return "held"
    proxy = paynow.mask(account.paynow_proxy_type, account.paynow_proxy)
    move_bonus(db, bonus_id, bonus.status, "sending", actor, {"to": proxy},
               paynow_proxy_masked=proxy)
    result = paynow.transfer(account.paynow_proxy)
    if result.settled:
        move_bonus(db, bonus_id, "sending", "paid", "paynow",
                   {"provider_reference": result.provider_reference},
                   provider_reference=result.provider_reference, paid_at=datetime.now(UTC),
                   failure_reason=None)
        text("haze_bonus_paid", days=str(bonus.unhealthy_days), region=bonus.region, proxy=proxy)
        return "paid"
    move_bonus(db, bonus_id, "sending", "failed", "paynow", {"reason": result.failure_reason},
               failure_reason=result.failure_reason)
    text("payout_failed", day=f"{bonus.loss_date.day} {bonus.loss_date:%b}", proxy=proxy)
    return "failed"


def bonus_status(db: Connection, bonus_id: int) -> str:
    return db.execute(
        select(haze_bonus_payouts.c.status).where(haze_bonus_payouts.c.id == bonus_id)
    ).scalar_one()


def retry_haze_bonus(db: Connection, bonus_id: int, actor: str) -> str:
    status = bonus_status(db, bonus_id)
    if status != "failed":
        raise WrongStatus(f"Only a failed payout can be retried; this one is {status}")
    move_bonus(db, bonus_id, "failed", "approved", actor, {"rule": "retry"})
    return send_haze_bonus(db, bonus_id, actor)


def reject_haze_bonus(db: Connection, bonus_id: int, reason: str, actor: str) -> None:
    status = bonus_status(db, bonus_id)
    if status not in REJECTABLE:
        raise WrongStatus(f"A {status} payout cannot be rejected")
    move_bonus(db, bonus_id, status, "rejected", actor, {"reason": reason},
               failure_reason=reason)


def release_held(db: Connection, user_id: int) -> None:
    held = db.execute(
        select(payouts.c.id).where(payouts.c.user_id == user_id, payouts.c.status == "held")
    ).scalars()
    for payout_id in list(held):
        send(db, payout_id)
    held_bonuses = db.execute(
        select(haze_bonus_payouts.c.id).where(
            haze_bonus_payouts.c.user_id == user_id, haze_bonus_payouts.c.status == "held"
        )
    ).scalars()
    for bonus_id in list(held_bonuses):
        send_haze_bonus(db, bonus_id)


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
