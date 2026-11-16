"""Payout endpoints: the stallholder's PayNow account and texts, and the insurer's payout runs."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Connection, Engine, delete, insert, select, update

from api import (
    forecast_warning, live, paynow, payout_flow, postcodes, readings, sms, sms_gateway, store,
)
from api.accounts import (
    InsurerDep, SmeDep, UserDep, application_profile, applications, policies, users,
)
from api.day_history import day_readings
from api.kyc import api_key
from api.payouts import (
    haze_bonus_events, haze_bonus_payouts, payout_accounts, payout_events, payouts, sms_messages,
    sms_preferences,
)

router = APIRouter(prefix="/api")
# The demo phone: the demo card fills it in, and a demo payout goes to it when the insurer types
# no mobile and the customer has no verified one. A real person's number: .env only, never code.
FALLBACK_MOBILE_SETTING = "DEMO_PAYOUT_MOBILE"


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
    mobile: str | None = Field(
        default=None,
        description="Singapore mobile to pay by PayNow and text, taken as verified. Leave out "
        "to use the customer's verified mobile, or else the DEMO_PAYOUT_MOBILE fallback.",
    )
    sms_language: sms.SmsLanguage | None = Field(
        default=None, description="Leave out to text in the customer's preferred language."
    )

    @field_validator("mobile")
    @classmethod
    def mobile_is_singapore(cls, mobile: str | None) -> str | None:
        if mobile is None:
            return None
        cleaned = re.sub(r"[\s-]", "", mobile)
        if not paynow.is_valid_mobile(cleaned):
            raise ValueError("Mobile must be +65 then 8 digits starting 8 or 9")
        return cleaned


class DemoWarningIn(BaseModel):
    user_id: int
    hazards: list[Literal["rain", "haze", "heat"]] = Field(
        min_length=1, description="What the demo forecast says, for example ['rain']."
    )
    mobile: str | None = Field(
        default=None,
        description="Singapore mobile to text. Leave out to use the customer's mobile, or else "
        "the DEMO_PAYOUT_MOBILE fallback.",
    )
    sms_language: sms.SmsLanguage | None = None

    @field_validator("mobile")
    @classmethod
    def mobile_is_singapore(cls, mobile: str | None) -> str | None:
        return DemoPayoutIn.mobile_is_singapore(mobile)


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
        "kind": "daily",
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
        "created_at": row.created_at,
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
    daily = [
        payout_view(row, events_by_payout.get(row.id, []), texts_by_payout.get(row.id, []))
        for row in rows
    ]
    if payout_id is not None:
        return daily
    lumps = haze_bonus_views(engine, user_id, None)
    return sorted(daily + lumps, key=lambda p: (p["loss_date"], p["created_at"]), reverse=True)


@router.get("/sms-preference")
def get_sms_preference(user: SmeDep, request: Request) -> dict:
    """The language the customer's texts go out in, as they chose it."""
    with request.app.state.db.connect() as db:
        return {"language": customer_language(db, user.id)}


HAZE_BONUS_ID = "haze_bonus-"


def haze_bonus_views(engine: Engine, user_id: int | None, bonus_id: int | None) -> list[dict]:
    """The severe haze payout's lump sums, in the shape of a daily payout, kind haze_bonus. Their
    id is text (HAZE_BONUS_ID and the number), so it never names a daily payout."""
    lumps = haze_bonus_payouts
    query = select(lumps, users.c.business_name).join(users, users.c.id == lumps.c.user_id)
    if user_id is not None:
        query = query.where(lumps.c.user_id == user_id)
    if bonus_id is not None:
        query = query.where(lumps.c.id == bonus_id)
    with engine.connect() as db:
        rows = db.execute(query).all()
        events: dict[int, list] = {}
        for event in db.execute(
            select(haze_bonus_events)
            .where(haze_bonus_events.c.bonus_id.in_([row.id for row in rows]))
            .order_by(haze_bonus_events.c.id)
        ):
            events.setdefault(event.bonus_id, []).append(event)
    return [
        {
            "id": f"{HAZE_BONUS_ID}{row.id}",
            "kind": "haze_bonus",
            "reference": payout_flow.bonus_reference(row.id),
            "business_name": row.business_name,
            "loss_date": row.loss_date.isoformat(),
            "region": row.region,
            "centre": row.centre,
            "tier": row.tier,
            "source": row.source,
            "readings": {"haze_days": row.unhealthy_days, "trigger_psi": row.trigger_psi},
            "basis": {"haze": f"{row.unhealthy_days} days at PSI {row.trigger_psi:g}+ in the "
                              f"{row.region} region this policy year"},
            "main_hazard": row.main_hazard,
            "loss_percent": 0.0,
            "daily_payout_sgd": None,
            "assessed_sgd": row.amount_cents / 100,
            "amount_sgd": row.amount_cents / 100,
            "status": row.status,
            "paid_to": row.paynow_proxy_masked,
            "provider_reference": row.provider_reference,
            "failure_reason": row.failure_reason,
            "paid_at": row.paid_at,
            "created_at": row.created_at,
            "events": [
                {"from_status": e.from_status, "to_status": e.to_status, "actor": e.actor,
                 "at": e.at}
                for e in events.get(row.id, [])
            ],
            "texts": [],
        }
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
        sms.set_preferred_language(db, user.id, body.sms_language)
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
    user_id = None if user.role == "insurer" else user.id
    with request.app.state.db.begin() as db:
        sms.refresh_statuses(db, user_id)
    return load_payouts(request.app.state.db, user_id)


@router.get("/sms")
def list_texts(user: SmeDep, request: Request) -> list[dict]:
    """Texts sent to the stallholder, newest first, with what the phone reported for each."""
    with request.app.state.db.begin() as db:
        sms.refresh_statuses(db, user.id)
        rows = db.execute(
            select(sms_messages)
            .where(sms_messages.c.user_id == user.id)
            .order_by(sms_messages.c.id.desc())
        ).all()
    return [
        {**text_view(row), "id": row.id,
         "body": row.body or "Payung code: ****** (codes are not stored)"}
        for row in rows
    ]


def shop_postcodes(engine: Engine) -> dict[int, str]:
    """Each shop owner's postcode from their latest shop application, by user id."""
    query = (
        select(applications.c.user_id, application_profile.c.postcode)
        .join(applications, applications.c.id == application_profile.c.application_id)
        .where(application_profile.c.business_class == "shop")
        .order_by(applications.c.id)
    )
    with engine.connect() as db:
        return {row.user_id: row.postcode for row in db.execute(query) if row.postcode}


def policy_point(policy, shops: dict[int, str], request: Request) -> tuple[float, float]:
    """Where a policy is paid from, as it is priced (main.business_quote): its hawker centre,
    else its shop's postcode area, else its region's point (a platform worker, who works across
    an area). A centre the map no longer has, or a postcode with no postal sector, falls back
    to the region's point, so one bad policy never stops a run for every other policy."""
    state = request.app.state
    centre = state.centres_by_name.get(policy.centre)
    if centre is not None:
        return centre["lat"], centre["lng"]
    postcode = shops.get(policy.user_id)
    if postcode is not None and postcodes.is_known(postcode):
        point = postcodes.area_point(
            postcode, state.centres_by_sector, state.map_static["region_points"]
        )
        return point["lat"], point["lng"]
    lat, lng = state.map_static["region_points"][policy.region]
    return lat, lng


def policy_place(policy, shops: dict[int, str], request: Request) -> readings.Place:
    """A policy's place, its stations ranked against the network the price reads."""
    lat, lng = policy_point(policy, shops, request)
    return readings.history_place(policy.region, lat, lng, request.app.state.sites)


@router.get("/cover-text")
def cover_text(
    request: Request,
    tier: str = "tier_1",
    language: sms.SmsLanguage = "en",
    weekly: Annotated[float | None, Query(gt=0, le=1000)] = None,
) -> dict:
    """The welcome SMS for a tier bought today: the same text the landing page, the risk atlas
    and the dashboard show, so what is sold is what is texted. Public: it is the point of sale.
    weekly is the customer's own price where the page knows their place; without it, no price."""
    tariff = store.latest(request.app.state.db).tariff
    chosen = next((t for t in tariff.tiers if t.key == tier), None)
    if chosen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No tier {tier}")
    first_day = payout_flow.first_day_if_bought_now()
    body = payout_flow.cover_text(language, weekly, chosen.daily_payout_sgd)
    return {
        "tier": chosen.key,
        "language": language,
        "body": body,
        "characters": len(body),
        "segments": sms.segments(body),
        "first_day": first_day.isoformat(),
    }


def history_haze(request: Request, tariff) -> payout_flow.HazeOn:
    """A region's haze reading on a past day from NEA's history, as a payout reads it."""
    table = day_readings(request)
    on_hold = readings.station_rule(tariff).regions_on_hold

    def haze_on(region: str, day) -> float | None:
        return readings.haze_reading(table.get(day.isoformat(), {}), region, on_hold)[0]

    return haze_on


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
        shops = shop_postcodes(engine)
        rule = readings.station_rule(saved.tariff)

        def readings_for(policy) -> readings.SiteReadings:
            where = policy_place(policy, shops, request)
            return readings.site_readings(day, where, rule)
    else:
        manual = readings.SiteReadings(
            readings=body.readings, basis=dict.fromkeys(body.readings, "entered by the insurer")
        )

        def readings_for(policy) -> readings.SiteReadings:
            return manual

    with engine.begin() as db:
        counts = payout_flow.run_day(
            db, saved.tariff, saved.version, body.loss_date, readings_for, body.source,
            set(body.regions) if body.regions else None, history_haze(request, saved.tariff),
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
    """Every stallholder with cover, where their texts go, whether texts reach real phones, and
    the demo payouts' fallback phone."""
    query = (
        select(policies, users.c.business_name, payout_accounts.c.sms_mobile,
               payout_accounts.c.sms_language, payout_accounts.c.mobile_verified_at,
               sms_preferences.c.language.label("preferred_language"))
        .join(users, users.c.id == policies.c.user_id)
        .outerjoin(payout_accounts, payout_accounts.c.user_id == policies.c.user_id)
        .outerjoin(sms_preferences, sms_preferences.c.user_id == policies.c.user_id)
        .order_by(users.c.business_name)
    )
    with request.app.state.db.connect() as db:
        rows = db.execute(query).all()
    return {
        "texts_are_real": sms_gateway.is_live(),
        "fallback_mobile": fallback_mobile(),
        "policyholders": [
            {
                "user_id": row.user_id,
                "business_name": row.business_name,
                "centre": row.centre or row.region,
                "tier_label": row.tier_label,
                "daily_payout_sgd": row.daily_payout_sgd,
                "texts_to": paynow.mask("mobile", row.sms_mobile) if row.sms_mobile else None,
                "sms_language": row.preferred_language or row.sms_language or "en",
                "mobile_verified": row.mobile_verified_at is not None,
            }
            for row in rows
        ],
    }


@router.get("/demo-phone")
def demo_phone() -> dict:
    """The demo phone the sign-up and PayNow forms start with. Unset on the hosted copy."""
    return {"mobile": fallback_mobile()}


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
        language = body.sms_language or customer_language(db, body.user_id)
        mobile = body.mobile
        if mobile is None and not has_verified_mobile(db, body.user_id):
            mobile = fallback_mobile()
        if mobile:
            point_account_at(db, body.user_id, mobile, language)
        else:
            db.execute(
                update(payout_accounts)
                .where(payout_accounts.c.user_id == body.user_id)
                .values(sms_language=language)
            )
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


@router.post("/insurer/forecast-warnings")
def send_forecast_warnings(user: InsurerDep, request: Request) -> dict:
    """Read NEA's latest 24-hour forecast and text every customer in a region it warns of.
    Meant for the evening, after NEA's late-afternoon issue; a customer gets one a day."""
    try:
        record = live.fetch_day_forecast()
    except (SystemExit, RuntimeError) as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    with request.app.state.db.begin() as db:
        return forecast_warning.send_warnings(db, record)


@router.post("/insurer/demo-forecast-warnings")
def send_demo_forecast_warning(body: DemoWarningIn, user: InsurerDep, request: Request) -> dict:
    """Text one customer a warning for tomorrow now, on the hazards given: the demo button.
    The one-a-day rule is skipped, so the demo can be shown again."""
    tomorrow = datetime.now(payout_flow.SINGAPORE).date() + timedelta(days=1)
    with request.app.state.db.begin() as db:
        policy = db.execute(select(policies).where(policies.c.user_id == body.user_id)).first()
        if policy is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That customer has no cover")
        contact = payout_flow.welcome_contact(db, body.user_id)
        mobile = body.mobile or (contact[0] if contact else None) or fallback_mobile()
        if mobile is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "That customer has no mobile yet: type one on the card")
        language = body.sms_language or customer_language(db, body.user_id)
        forecast_warning.warn(db, body.user_id, mobile, language, body.hazards, tomorrow)
        sent = db.execute(
            select(sms_messages)
            .where(sms_messages.c.user_id == body.user_id)
            .order_by(sms_messages.c.id.desc())
        ).first()
    return {"day": tomorrow.isoformat(), "text": text_view(sent)}


def fallback_mobile() -> str | None:
    mobile = api_key(FALLBACK_MOBILE_SETTING)
    if mobile is not None and not paynow.is_valid_mobile(mobile):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"{FALLBACK_MOBILE_SETTING} in .env must be +65 then 8 digits starting 8 or 9",
        )
    return mobile


def customer_language(db: Connection, user_id: int) -> str:
    """The language the customer chose, at sign-up or with their PayNow details; else English."""
    account_language = db.execute(
        select(payout_accounts.c.sms_language).where(payout_accounts.c.user_id == user_id)
    ).scalar_one_or_none()
    return sms.preferred_language(db, user_id) or account_language or "en"


def has_verified_mobile(db: Connection, user_id: int) -> bool:
    verified_at = db.execute(
        select(payout_accounts.c.mobile_verified_at).where(payout_accounts.c.user_id == user_id)
    ).scalar_one_or_none()
    return verified_at is not None


def point_account_at(db: Connection, user_id: int, mobile: str, language: str) -> None:
    """Pay and text this mobile, taken as verified: the insurer typed it in for the demo."""
    before = db.execute(
        select(payout_accounts).where(payout_accounts.c.user_id == user_id)
    ).first()
    holder = db.execute(select(users.c.name).where(users.c.id == user_id)).scalar_one()
    now = datetime.now(UTC)
    db.execute(delete(payout_accounts).where(payout_accounts.c.user_id == user_id))
    db.execute(
        insert(payout_accounts).values(
            user_id=user_id,
            paynow_proxy_type="mobile",
            paynow_proxy=mobile,
            paynow_name=paynow.lookup_name(holder),
            sms_mobile=mobile,
            sms_language=language,
            mobile_verified_at=now,
            created_at=before.created_at if before else now,
            updated_at=now,
        )
    )


def change_payout(request: Request, payout_id: str, daily, lump_sum) -> dict:
    """Apply an insurer's action to a daily payout (a number) or a lump sum (haze_bonus-N)."""
    engine: Engine = request.app.state.db
    table, number = payout_table(payout_id)
    try:
        with engine.begin() as db:
            exists = db.execute(select(table.c.id).where(table.c.id == number)).first()
            if exists is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payout")
            (lump_sum if table is haze_bonus_payouts else daily)(db, number)
    except payout_flow.WrongStatus as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    if table is haze_bonus_payouts:
        [payout] = haze_bonus_views(engine, None, number)
    else:
        [payout] = load_payouts(engine, None, number)
    return payout


def payout_table(payout_id: str):
    """The table and row number a payout id names. Raises 404 for an id that names neither."""
    text = payout_id.removeprefix(HAZE_BONUS_ID)
    if not text.isdigit():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payout")
    return (haze_bonus_payouts if text != payout_id else payouts), int(text)


@router.post("/insurer/payouts/{payout_id}/retry")
def retry_payout(payout_id: str, user: InsurerDep, request: Request) -> dict:
    return change_payout(
        request, payout_id,
        lambda db, number: payout_flow.retry(db, number, user.email),
        lambda db, number: payout_flow.retry_haze_bonus(db, number, user.email),
    )


@router.post("/insurer/payouts/{payout_id}/reject")
def reject_payout(payout_id: str, body: RejectIn, user: InsurerDep, request: Request) -> dict:
    return change_payout(
        request, payout_id,
        lambda db, number: payout_flow.reject(db, number, body.reason, user.email),
        lambda db, number: payout_flow.reject_haze_bonus(db, number, body.reason, user.email),
    )
