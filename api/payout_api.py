"""Payout endpoints: the stallholder's PayNow account and texts, and the insurer's payout runs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Engine, delete, insert, select, update

from api import paynow, payout_flow, postcodes, sms, store
from api.accounts import (
    InsurerDep, SmeDep, UserDep, application_profile, applications, policies, users,
)
from api.day_history import SiteReadings, day_readings, site_readings
from api.payouts import payout_accounts, payout_events, payouts, sms_messages

router = APIRouter(prefix="/api")


class PayoutAccountIn(BaseModel):
    paynow_proxy_type: Literal["mobile", "uen"]
    paynow_proxy: str = Field(max_length=20)
    sms_mobile: str | None = Field(
        default=None, description="Mobile for texts. Defaults to the PayNow mobile."
    )
    sms_language: Literal["en", "zh", "ms", "ta"] = "en"

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


def payout_view(row, events: list) -> dict:
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
        "basis": next((e.detail.get("basis") for e in events if e.to_status == "assessed"), None),
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
    by_payout: dict[int, list] = {}
    for event in events:
        by_payout.setdefault(event.payout_id, []).append(event)
    return [payout_view(row, by_payout.get(row.id, [])) for row in rows]


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
    """Text a one-time code. The SMS gateway is simulated, so the code is also returned."""
    engine: Engine = request.app.state.db
    account = find_account(engine, user.id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Save a PayNow account first")
    with engine.begin() as db:
        code = sms.start_verification(db, user.id, account.sms_mobile, account.sms_language)
    return {"sent_to": paynow.mask("mobile", account.sms_mobile), "demo_code": code}


@router.post("/payout-account/verify")
def finish_mobile_check(body: CodeIn, user: SmeDep, request: Request) -> dict:
    """Check the code, mark the mobile verified and pay anything that was waiting for it."""
    engine: Engine = request.app.state.db
    with engine.begin() as db:
        result = sms.check_code(db, user.id, body.code)
        if result == "ok":
            db.execute(
                update(payout_accounts)
                .where(payout_accounts.c.user_id == user.id)
                .values(mobile_verified_at=datetime.now(UTC))
            )
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
        {
            "id": row.id,
            "kind": row.kind,
            "body": row.body or "SafeDay code: ****** (codes are not stored)",
            "to": paynow.mask("mobile", row.to_mobile),
            "language": row.language,
            "status": row.status,
            "sent_at": row.sent_at,
        }
        for row in rows
    ]


def policy_places(
    engine: Engine, map_static: dict, centres_by_sector: dict
) -> dict[int, tuple[float, float]]:
    """Where each policy's readings are taken: its hawker centre, else the area of the postcode
    on its latest application (postcodes.area_point), else the middle of its PSI region."""
    centres = {c["name"]: c for c in map_static["hawker_centres"]}
    with engine.connect() as db:
        postcode_of = dict(db.execute(
            select(applications.c.user_id, application_profile.c.postcode)
            .join(application_profile, application_profile.c.application_id == applications.c.id)
            .where(application_profile.c.postcode.is_not(None))
            .order_by(applications.c.id)
        ).all())
        in_force = db.execute(select(policies)).all()
    places = {}
    for policy in in_force:
        if policy.centre in centres:
            centre = centres[policy.centre]
            places[policy.id] = (centre["lat"], centre["lng"])
        elif policy.user_id in postcode_of:
            area = postcodes.area_point(
                postcode_of[policy.user_id], centres_by_sector, map_static["region_points"]
            )
            places[policy.id] = (area["lat"], area["lng"])
        else:
            places[policy.id] = tuple(map_static["region_points"][policy.region])
    return places


@router.post("/insurer/payout-runs")
def run_payouts(body: RunIn, user: InsurerDep, request: Request) -> dict:
    """Assess every policy for one Singapore date and pay what the readings give."""
    engine: Engine = request.app.state.db
    saved = store.latest(engine)
    if body.source == "nea_history":
        day = day_readings(request).get(body.loss_date.isoformat())
        if day is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"No NEA readings for {body.loss_date} yet. Run the day again once NEA publishes "
                "them. No policy is refused in the meantime.",
            )
        map_static = request.app.state.map_static
        places = policy_places(engine, map_static, request.app.state.centres_by_sector)

        def readings_for(policy) -> SiteReadings:
            lat, lng = places[policy.id]
            return site_readings(day, lat, lng, policy.region, map_static)
    else:
        manual = SiteReadings(
            readings=body.readings, basis=dict.fromkeys(body.readings, "entered by the insurer")
        )

        def readings_for(policy) -> SiteReadings:
            return manual

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
