"""Payout endpoints: the stallholder's PayNow account and texts, and the insurer's payout runs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Engine, delete, insert, select, update

from api import paynow, payout_flow, sms, sms_gateway, store
from api.accounts import InsurerDep, SmeDep, UserDep, policies, users
from api.day_history import centre_readings, day_readings
from api.payouts import payout_accounts, payout_events, payouts, sms_messages

router = APIRouter(prefix="/api")


class PayoutAccountIn(BaseModel):
    paynow_proxy_type: Literal["mobile", "uen"]
    paynow_proxy: str = Field(max_length=20)
    sms_mobile: str | None = Field(
        default=None, description="Mobile for texts. Defaults to the PayNow mobile."
    )
    sms_language: sms.SmsLanguage = "en"

    @model_validator(mode="after")
    def proxy_and_mobile_are_valid(self) -> PayoutAccountIn:
        if not paynow.is_valid_proxy(self.paynow_proxy_type, self.paynow_proxy):
            raise ValueError("PayNow mobile must be +65 and 8 digits starting 8 or 9, or a UEN")
        self.sms_mobile = self.sms_mobile or (
            self.paynow_proxy if self.paynow_proxy_type == "mobile" else None
        )
        if self.sms_mobile is None or not paynow.is_valid_mobile(self.sms_mobile):
            raise ValueError("A Singapore mobile (+65 8 or 9 then 7 digits) is needed for texts")
        return self


class CodeIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class RunIn(BaseModel):
    loss_date: date
    source: Literal["nea_history", "manual"]
    readings: dict[str, float] | None = Field(
        default=None, description="Manual runs only: hazard key to reading for every policy."
    )
    regions: list[str] | None = None

    @model_validator(mode="after")
    def manual_runs_need_readings(self) -> RunIn:
        if self.source == "manual" and not self.readings:
            raise ValueError("A manual run needs readings, for example {'flood': 1}")
        return self


class DemoPayoutIn(BaseModel):
    user_id: int
    readings: dict[str, float] = Field(
        min_length=1, description="Hazard key to reading, for example {'rain': 50}."
    )


class RejectIn(BaseModel):
    reason: str = Field(min_length=2, max_length=300)


def account_view(row) -> dict:
    return {
        "paynow_proxy_type": row.paynow_proxy_type,
        "paynow_proxy_masked": paynow.mask(row.paynow_proxy_type, row.paynow_proxy),
        "paynow_name": row.paynow_name,
        "sms_mobile_masked": paynow.mask("mobile", row.sms_mobile),
        "sms_language": row.sms_language,
        "mobile_verified": row.mobile_verified_at is not None,
    }


def find_account(engine: Engine, user_id: int):
    with engine.connect() as db:
        return db.execute(
            select(payout_accounts).where(payout_accounts.c.user_id == user_id)
        ).first()


def text_view(row) -> dict:
    return {
        "kind": row.kind,
        "body": row.body,
        "to": paynow.mask("mobile", row.to_mobile),
        "language": row.language,
        "status": row.status,
        "error": row.error,
        "sent_at": row.sent_at,
    }


def payout_view(row, events: list, texts: list) -> dict:
    return {
        "id": row.id,
        "reference": payout_flow.reference(row.id),
        "business_name": row.business_name,
        "loss_date": row.loss_date.isoformat(),
        "region": row.region,
        "centre": row.centre,
        "tier": row.tier,
        "source": row.source,
        "readings": row.readings,
        "main_hazard": row.main_hazard,
        "loss_percent": row.loss_percent,
        "daily_payout_sgd": row.daily_payout_cents / 100,
        "assessed_sgd": row.assessed_cents / 100,
        "amount_sgd": row.amount_cents / 100,
        "status": row.status,
        "paid_to": row.paynow_proxy_masked,
        "provider_reference": row.provider_reference,
        "failure_reason": row.failure_reason,
        "paid_at": row.paid_at,
        "events": [
            {"from_status": e.from_status, "to_status": e.to_status, "actor": e.actor, "at": e.at}
            for e in events
        ],
        "texts": [text_view(text) for text in texts],
    }


def load_payouts(engine: Engine, user_id: int | None, payout_id: int | None = None) -> list[dict]:
    query = (
        select(payouts, users.c.business_name)
        .join(users, users.c.id == payouts.c.user_id)
        .order_by(payouts.c.loss_date.desc(), payouts.c.id.desc())
    )
    if user_id is not None:
        query = query.where(payouts.c.user_id == user_id)
    if payout_id is not None:
        query = query.where(payouts.c.id == payout_id)
    with engine.connect() as db:
        rows = db.execute(query).all()
        ids = [row.id for row in rows]
        events = db.execute(
            select(payout_events)
            .where(payout_events.c.payout_id.in_(ids))
            .order_by(payout_events.c.id)
        ).all()
        texts = db.execute(
            select(sms_messages)
            .where(sms_messages.c.payout_id.in_(ids))
            .order_by(sms_messages.c.id)
        ).all()
    events_by_payout: dict[int, list] = {}
    for event in events:
        events_by_payout.setdefault(event.payout_id, []).append(event)
    texts_by_payout: dict[int, list] = {}
    for text in texts:
        texts_by_payout.setdefault(text.payout_id, []).append(text)
    return [
        payout_view(row, events_by_payout.get(row.id, []), texts_by_payout.get(row.id, []))
        for row in rows
    ]


@router.get("/payout-account")
def get_payout_account(user: SmeDep, request: Request) -> dict:
    row = find_account(request.app.state.db, user.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No PayNow account yet")
    return account_view(row)


@router.put("/payout-account")
def put_payout_account(body: PayoutAccountIn, user: SmeDep, request: Request) -> dict:
    """Save where payouts go. A new texting mobile has to be verified again."""
    engine: Engine = request.app.state.db
    before = find_account(engine, user.id)
    now = datetime.now(UTC)
    same_mobile = before is not None and before.sms_mobile == body.sms_mobile
    values = {
        "paynow_proxy_type": body.paynow_proxy_type,
        "paynow_proxy": body.paynow_proxy,
        "paynow_name": paynow.lookup_name(user.name),
        "sms_mobile": body.sms_mobile,
        "sms_language": body.sms_language,
        "mobile_verified_at": before.mobile_verified_at if same_mobile else None,
        "updated_at": now,
    }
    with engine.begin() as db:
        db.execute(delete(payout_accounts).where(payout_accounts.c.user_id == user.id))
        created_at = before.created_at if before else now
        db.execute(
            insert(payout_accounts).values(user_id=user.id, created_at=created_at, **values)
        )
    return account_view(find_account(engine, user.id))


@router.post("/payout-account/verify/start")
def start_mobile_check(user: SmeDep, request: Request) -> dict:
    """Text a one-time code. While texts are simulated the code is also returned, for the demo."""
    engine: Engine = request.app.state.db
    account = find_account(engine, user.id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Save a PayNow account first")
    with engine.begin() as db:
        code = sms.start_verification(db, user.id, account.sms_mobile, account.sms_language)
    sent = {"sent_to": paynow.mask("mobile", account.sms_mobile), "texts_are_real": False}
    if sms_gateway.is_live():
        return {**sent, "texts_are_real": True}
    return {**sent, "demo_code": code}


@router.post("/payout-account/verify")
def finish_mobile_check(body: CodeIn, user: SmeDep, request: Request) -> dict:
    """Check the code, mark the mobile verified and pay anything that was waiting for it."""
    engine: Engine = request.app.state.db
    tariff = store.latest(engine).tariff
    with engine.begin() as db:
        result = sms.check_code(db, user.id, body.code)
        if result == "ok":
            db.execute(
                update(payout_accounts)
                .where(payout_accounts.c.user_id == user.id)
                .values(mobile_verified_at=datetime.now(UTC))
            )
            payout_flow.send_welcome_if_due(db, user.id, tariff)
            payout_flow.release_held(db, user.id)
    if result == "locked":
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries. Ask for a new code")
    if result != "ok":
        messages = {"wrong": "Wrong code", "expired": "Code expired", "none": "Ask for a code"}
        raise HTTPException(status.HTTP_400_BAD_REQUEST, messages[result])
    return account_view(find_account(engine, user.id))


@router.get("/payouts")
def list_payouts(user: UserDep, request: Request) -> list[dict]:
    """The stallholder's own payouts, or every payout for an insurer, newest day first."""
    return load_payouts(request.app.state.db, None if user.role == "insurer" else user.id)


@router.get("/sms")
def list_texts(user: SmeDep, request: Request) -> list[dict]:
    """Texts sent to the stallholder, newest first: the simulated phone's inbox."""
    with request.app.state.db.connect() as db:
        rows = db.execute(
            select(sms_messages)
            .where(sms_messages.c.user_id == user.id)
            .order_by(sms_messages.c.id.desc())
        ).all()
    return [
        {**text_view(row), "id": row.id,
         "body": row.body or "SafeDay code: ****** (codes are not stored)"}
        for row in rows
    ]


@router.get("/cover-text")
def cover_text(
    request: Request,
    tier: str = "tier_1",
    language: sms.SmsLanguage = "en",
) -> dict:
    """The welcome SMS for a tier bought today: the same text the landing page, the risk atlas
    and the dashboard show, so what is sold is what is texted. Public: it is the point of sale."""
    tariff = store.latest(request.app.state.db).tariff
    chosen = next((t for t in tariff.tiers if t.key == tier), None)
    if chosen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No tier {tier}")
    first_day = payout_flow.first_day_if_bought_now()
    body = payout_flow.cover_text(
        tariff, language, chosen.daily_payout_sgd, chosen.max_paid_days_per_year, first_day
    )
    return {
        "tier": chosen.key,
        "language": language,
        "body": body,
        "characters": len(body),
        "segments": sms.segments(body),
        "first_day": first_day.isoformat(),
    }


@router.post("/insurer/payout-runs")
def run_payouts(body: RunIn, user: InsurerDep, request: Request) -> dict:
    """Assess every policy for one Singapore date and pay what the readings give."""
    engine: Engine = request.app.state.db
    saved = store.latest(engine)
    if body.source == "nea_history":
        day = day_readings(request).get(body.loss_date.isoformat())
        if day is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No NEA readings for {body.loss_date}")
        centres = {c["name"]: c for c in request.app.state.map_static["hawker_centres"]}
        map_static = request.app.state.map_static

        def readings_for(policy) -> dict[str, float]:
            return centre_readings(day, centres[policy.centre], map_static)
    else:
        def readings_for(policy) -> dict[str, float]:
            return body.readings

    with engine.begin() as db:
        counts = payout_flow.run_day(
            db, saved.tariff, saved.version, body.loss_date, readings_for, body.source,
            set(body.regions) if body.regions else None,
        )
    return {
        "loss_date": body.loss_date.isoformat(),
        "source": body.source,
        "readings_found": True,
        "tariff_version": saved.version,
        "counts": counts,
    }


@router.get("/insurer/policyholders")
def list_policyholders(user: InsurerDep, request: Request) -> dict:
    """Every stallholder with cover, where their texts go, and whether texts reach real phones."""
    query = (
        select(policies, users.c.business_name, payout_accounts.c.sms_mobile,
               payout_accounts.c.sms_language, payout_accounts.c.mobile_verified_at)
        .join(users, users.c.id == policies.c.user_id)
        .outerjoin(payout_accounts, payout_accounts.c.user_id == policies.c.user_id)
        .order_by(users.c.business_name)
    )
    with request.app.state.db.connect() as db:
        rows = db.execute(query).all()
    return {
        "texts_are_real": sms_gateway.is_live(),
        "policyholders": [
            {
                "user_id": row.user_id,
                "business_name": row.business_name,
                "centre": row.centre or row.region,
                "tier_label": row.tier_label,
                "daily_payout_sgd": row.daily_payout_sgd,
                "texts_to": paynow.mask("mobile", row.sms_mobile) if row.sms_mobile else None,
                "sms_language": row.sms_language,
                "mobile_verified": row.mobile_verified_at is not None,
            }
            for row in rows
        ],
    }


@router.post("/insurer/demo-payouts")
def send_demo_payout(body: DemoPayoutIn, user: InsurerDep, request: Request) -> dict:
    """Pay one stallholder now on the readings given, by PayNow with an SMS: the demo button."""
    engine: Engine = request.app.state.db
    saved = store.latest(engine)
    known = {hazard.key for hazard in saved.tariff.hazards}
    if not set(body.readings) <= known:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Readings must be for {', '.join(sorted(known))}")
    with engine.begin() as db:
        policy = db.execute(select(policies).where(policies.c.user_id == body.user_id)).first()
        if policy is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That customer has no cover")
        outcome, loss_date = payout_flow.pay_demo(
            db, policy, saved.tariff, saved.version, body.readings
        )
    if outcome == "no_loss":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Those readings are below every trigger, so nothing is paid")
    paid = next(
        p for p in load_payouts(engine, body.user_id) if p["loss_date"] == loss_date.isoformat()
    )
    return {"outcome": outcome, "payout": paid}


def change_payout(request: Request, payout_id: int, action) -> dict:
    engine: Engine = request.app.state.db
    try:
        with engine.begin() as db:
            exists = db.execute(select(payouts.c.id).where(payouts.c.id == payout_id)).first()
            if exists is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payout")
            action(db)
    except payout_flow.WrongStatus as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    [payout] = load_payouts(engine, None, payout_id)
    return payout


@router.post("/insurer/payouts/{payout_id}/retry")
def retry_payout(payout_id: int, user: InsurerDep, request: Request) -> dict:
    return change_payout(
        request, payout_id, lambda db: payout_flow.retry(db, payout_id, user.email)
    )


@router.post("/insurer/payouts/{payout_id}/reject")
def reject_payout(payout_id: int, body: RejectIn, user: InsurerDep, request: Request) -> dict:
    return change_payout(
        request, payout_id, lambda db: payout_flow.reject(db, payout_id, body.reason, user.email)
    )
