"""The 'see the reading' check: for any day, the reading at each hazard, the rule that chose it,
the trigger it is measured against, and whether the day paid and why not.

There is no appeal that changes a payout (Income product lead, 15 Nov 2026). In its place a
customer sees the data behind every day and can report a wrong reading or a wrong shop category
as an ordinary service request, which corrects data and never tops up for the size of a loss.
Readings come from api/readings.py, the rule every payout run uses.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import insert, select

from api import calculator, payout_api, payout_flow, readings, store
from api.accounts import InsurerDep, SmeDep, policies, users
from api.day_history import day_readings
from api.models import Tariff
from api.payouts import service_requests

router = APIRouter(prefix="/api")

ServiceRequestKind = Literal["wrong_reading", "wrong_category"]


class ServiceRequestIn(BaseModel):
    loss_date: date
    kind: ServiceRequestKind
    note: str | None = Field(default=None, max_length=500)


def service_reference(request_id: int) -> str:
    return f"SR-{request_id:06d}"


def hazard_rows(tariff: Tariff, values: dict[str, float | None], basis: dict[str, str],
                product: str, tier: str) -> list[dict]:
    """One row per hazard that was read: its value, the rule behind it and its trigger."""
    found = {key: value for key, value in values.items() if value is not None}
    losses = {
        hazard.hazard: hazard.loss_percent
        for hazard in calculator.assess(tariff, product, tier, found).hazards
    }
    rows = []
    for hazard in tariff.hazards:
        if hazard.key not in values:
            continue
        value = values[hazard.key]
        pays_from = hazard.bands[0].at_least
        rows.append({
            "hazard": hazard.key,
            "label": hazard.label,
            "measures": hazard.reading,
            "value": value,
            "pays_from": pays_from,
            "crossed": value is not None and value >= pays_from,
            "basis": basis.get(hazard.key),
            "loss_percent": losses.get(hazard.key),
        })
    return rows


def unpaid_outcome(db, policy, tariff: Tariff, day: date, site: readings.SiteReadings) -> str:
    reason = payout_flow.not_payable_reason(db, policy, day, site)
    if reason is not None:
        return reason
    assessment = calculator.assess(tariff, policy.product, policy.tier, site.readings)
    return "below_trigger" if assessment.payout_sgd <= 0 else "not_run_yet"


@router.get("/my-day")
def my_day(user: SmeDep, request: Request, day: date) -> dict:
    """What the readings were at the owner's place on one day, and whether that day paid."""
    engine = request.app.state.db
    tariff = store.latest(engine).tariff
    with engine.connect() as db:
        policy = db.execute(select(policies).where(policies.c.user_id == user.id)).first()
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pick a cover first: no day to check.")
    check = {
        "date": day.isoformat(),
        "cover_pays_from": payout_flow.first_covered_day(policy.started_at).isoformat(),
        "payout": None,
    }
    paid = [p for p in payout_api.load_payouts(engine, user.id) if p["loss_date"] == check["date"]]
    if paid:
        payout = paid[0]
        rows = hazard_rows(tariff, payout["readings"], payout["basis"] or {}, policy.product,
                           policy.tier)
        return check | {"outcome": payout["status"], "hazards": rows, "payout": payout}
    recorded = day_readings(request).get(check["date"])
    if recorded is None:
        return check | {"outcome": "no_record", "hazards": []}
    where = payout_api.policy_place(policy, payout_api.shop_postcodes(engine), request)
    site = readings.site_readings(recorded, where, *readings.stations_read(tariff))
    values = {hazard: site.readings.get(hazard) for hazard in readings.HAZARDS}
    with engine.connect() as db:
        outcome = unpaid_outcome(db, policy, tariff, day, site)
    rows = hazard_rows(tariff, values, site.basis, policy.product, policy.tier)
    return check | {"outcome": outcome, "hazards": rows}


@router.post("/service-requests")
def file_service_request(body: ServiceRequestIn, user: SmeDep, request: Request) -> dict:
    """Report a wrong reading or a wrong shop category. Income's service team checks the data."""
    with request.app.state.db.begin() as db:
        request_id = db.execute(
            insert(service_requests)
            .values(user_id=user.id, loss_date=body.loss_date, kind=body.kind, note=body.note,
                    created_at=datetime.now(UTC))
            .returning(service_requests.c.id)
        ).scalar_one()
    return {"id": request_id, "reference": service_reference(request_id)}


@router.get("/insurer/service-requests")
def list_service_requests(user: InsurerDep, request: Request) -> list[dict]:
    query = (
        select(service_requests, users.c.business_name)
        .join(users, users.c.id == service_requests.c.user_id)
        .order_by(service_requests.c.id.desc())
    )
    with request.app.state.db.connect() as db:
        rows = db.execute(query).all()
    return [
        {
            "reference": service_reference(row.id),
            "business_name": row.business_name,
            "loss_date": row.loss_date.isoformat(),
            "kind": row.kind,
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in rows
    ]
