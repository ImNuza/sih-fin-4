"""The underwriter queue: applications referred by a past decline or by a tier the quote does
not sell directly (its premium is more than the tariff's share of its yearly limit), and the
decision on each.

An insurer approves or declines a referred application. Approval accepts it and, when the owner
added SafeDay, starts the policy for the tier and product applied for at the weekly premium
quoted. An owner with cover in force keeps it on its old terms until the new tier's waiting
period ends (accounts.policy_tier_changes). Decline starts nothing and keeps the cover in force.
The owner reads the decision and its note from their dashboard.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Connection, DateTime, Integer, String, Table, delete, insert, select, update,
)

from api import accounts, calculator, store
from api.accounts import InsurerDep, SmeDep
from api.models import Tariff
from api.store import metadata

QUEUE_PATH = "/api/insurer/applications"
RECENT_DECISIONS = 10
SINGAPORE = ZoneInfo("Asia/Singapore")
STATUS_AFTER = {"approve": "accepted", "decline": "declined"}
# An approval in a month the add-on is off sale must not let anyone buy it as haze nears.
NOT_ON_SALE_NOTE = (
    "The severe haze payout cannot be added from May to October; add it from November."
)

underwriting_decisions = Table(
    "underwriting_decisions",
    metadata,
    Column("application_id", Integer, primary_key=True),
    Column("decision", String, nullable=False),
    Column("note", String),
    Column("decided_by", Integer, nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
)


class Decision(BaseModel):
    decision: Literal["approve", "decline"]
    note: str | None = Field(default=None, max_length=500)


router = APIRouter()


def profile_table() -> Table | None:
    """The buy flow's application_profile table, when this build defines it."""
    return metadata.tables.get("application_profile")


def referral_query():
    """Each application with its owner, its details and, when the table exists, its profile."""
    applications, details, users, referrals = (
        accounts.applications,
        accounts.application_details,
        accounts.users,
        accounts.application_referrals,
    )
    query = (
        select(
            applications.c.id,
            applications.c.applicant_type,
            applications.c.uen,
            applications.c.phone,
            applications.c.add_safeday,
            applications.c.tier,
            applications.c.declined_details,
            applications.c.status,
            applications.c.created_at,
            users.c.business_name,
            users.c.name,
            users.c.centre,
            users.c.region,
            users.c.product,
            details.c.stall_unit,
            details.c.designation,
            details.c.cover_start,
            referrals.c.reason.label("referral_reason"),
        )
        .join(users, users.c.id == applications.c.user_id)
        .outerjoin(details, details.c.application_id == applications.c.id)
        .outerjoin(referrals, referrals.c.application_id == applications.c.id)
    )
    profile = profile_table()
    if profile is None:
        return query
    profile_columns = [column for column in profile.c if column.name != "application_id"]
    return query.add_columns(*profile_columns).outerjoin(
        profile, profile.c.application_id == applications.c.id
    )


def recent_decisions(db: Connection) -> list[dict]:
    decisions, applications = underwriting_decisions, accounts.applications
    owner = accounts.users.alias("owner")
    decider = accounts.users.alias("decider")
    query = (
        select(
            decisions.c.application_id,
            decisions.c.decision,
            decisions.c.note,
            decisions.c.decided_at,
            owner.c.business_name,
            owner.c.name,
            decider.c.name.label("decided_by_name"),
        )
        .join(applications, applications.c.id == decisions.c.application_id)
        .join(owner, owner.c.id == applications.c.user_id)
        .join(decider, decider.c.id == decisions.c.decided_by)
        .order_by(decisions.c.decided_at.desc())
        .limit(RECENT_DECISIONS)
    )
    return [dict(row) for row in db.execute(query).mappings()]


@router.get(QUEUE_PATH)
def underwriter_queue(_: InsurerDep, request: Request) -> dict:
    """Applications waiting for an underwriter, newest first, and the latest decisions."""
    applications = accounts.applications
    waiting = (
        referral_query()
        .where(applications.c.status == "referred")
        .order_by(applications.c.id.desc())
    )
    with request.app.state.db.connect() as db:
        return {
            "waiting": [dict(row) for row in db.execute(waiting).mappings()],
            "recent_decisions": recent_decisions(db),
        }


def claim_referral(db: Connection, application_id: int, new_status: str) -> dict:
    """Move a referred application to its new status. Raises unless it is still referred."""
    applications, details = accounts.applications, accounts.application_details
    application = db.execute(
        select(applications, details.c.cover_start)
        .outerjoin(details, details.c.application_id == applications.c.id)
        .where(applications.c.id == application_id)
    ).mappings().first()
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No application {application_id}")
    claimed = db.execute(
        update(applications)
        .where(applications.c.id == application_id, applications.c.status == "referred")
        .values(status=new_status)
    ).rowcount
    if not claimed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Application {application_id} is {application['status']}. "
            "Only an application waiting for an underwriter can be decided",
        )
    return dict(application)


def cover_starts_at(cover_start: date | None) -> datetime:
    now = datetime.now(UTC)
    if cover_start is None:
        return now
    return max(now, datetime.combine(cover_start, datetime.min.time(), SINGAPORE))


def start_policy(
    db: Connection, application: dict, tariff: Tariff, request: Request
) -> dict | None:
    """The approved owner's SafeDay policy, priced as the buy flow does, or the change of tier of
    the policy in force, from the end of its waiting period. None when not wanted. A severe
    haze payout asked for in the application is added, from the end of its own waiting period.
    """
    from api.main import (
        add_haze_bonus, business_quote, chosen_tier, haze_bonus_starts, policy_values,
    )

    policies, users = accounts.policies, accounts.users
    user_id = application["user_id"]
    if not application["add_safeday"]:
        return None
    owner = db.execute(select(users).where(users.c.id == user_id)).first()
    referrals = accounts.application_referrals
    referral = db.execute(
        select(referrals).where(referrals.c.application_id == application["id"])
    ).first()
    product = referral.product if referral else owner.product or "cooked_food"
    profile = accounts.application_profile
    place = db.execute(
        select(profile.c.business_class, profile.c.postcode).where(
            profile.c.application_id == application["id"]
        )
    ).first()
    postcode = place.postcode if place and place.business_class == "shop" else None
    priced = business_quote(request, tariff, product, owner.region, owner.centre, postcode)
    policy = policy_values(
        priced, user_id, owner.region, owner.centre, product, application["tier"]
    )
    if referral:
        policy["weekly_premium_sgd"] = referral.weekly_premium_sgd
    wanted = db.execute(select(accounts.application_haze_bonus).where(
        accounts.application_haze_bonus.c.application_id == application["id"]
    )).first()
    offer = chosen_tier(priced, application["tier"]).haze_bonus if wanted else None
    in_force = db.execute(select(policies).where(policies.c.user_id == user_id)).first()
    if in_force is not None:
        started = change_tier(db, in_force, policy)
        policy_id, cover_from = in_force.id, datetime.now(SINGAPORE).date()
    else:
        policy["started_at"] = cover_starts_at(application["cover_start"])
        policy["id"] = db.execute(
            insert(policies).values(**policy).returning(policies.c.id)
        ).scalar_one()
        started = {k: v for k, v in policy.items() if k != "user_id"}
        policy_id, cover_from = policy["id"], policy["started_at"].astimezone(SINGAPORE).date()
    started["haze_bonus"] = None
    if offer is None or tariff.haze_bonus is None:
        return started
    if not calculator.on_sale(tariff.haze_bonus, calculator.singapore_today()):
        started["haze_bonus_note"] = NOT_ON_SALE_NOTE
        return started
    starts_on = haze_bonus_starts(tariff, cover_from)
    started["haze_bonus"] = add_haze_bonus(db, policy_id, offer, starts_on)
    return started


def change_tier(db: Connection, in_force, policy: dict) -> dict:
    """Schedule the policy in force onto the new terms from the end of their waiting period."""
    changes = accounts.policy_tier_changes
    starts_on = datetime.now(SINGAPORE).date() + timedelta(days=accounts.WAITING_PERIOD_DAYS)
    terms = {key: policy[key] for key in (
        "tier", "tier_label", "product", "weekly_premium_sgd", "daily_payout_sgd",
        "max_paid_days_per_year",
    )}
    # A change approved later replaces any that has not started by its own start.
    db.execute(delete(changes).where(
        changes.c.policy_id == in_force.id, changes.c.starts_on >= starts_on
    ))
    db.execute(insert(changes).values(policy_id=in_force.id, starts_on=starts_on, **terms))
    return {
        "id": in_force.id, "region": in_force.region, "centre": in_force.centre,
        "started_at": in_force.started_at, **terms, "tier_starts_on": starts_on,
    }


@router.post(QUEUE_PATH + "/{application_id}/decision")
def decide(application_id: int, body: Decision, user: InsurerDep, request: Request) -> dict:
    """Approve or decline a referred application. Only a referred application can be decided."""
    engine = request.app.state.db
    tariff = store.latest(engine).tariff
    new_status = STATUS_AFTER[body.decision]
    note = (body.note or "").strip() or None
    with engine.begin() as db:
        application = claim_referral(db, application_id, new_status)
        policy = None
        if body.decision == "approve":
            policy = start_policy(db, application, tariff, request)
        if policy and (system_note := policy.pop("haze_bonus_note", None)):
            note = f"{note} {system_note}" if note else system_note
        db.execute(
            insert(underwriting_decisions).values(
                application_id=application_id,
                decision=body.decision,
                note=note,
                decided_by=user.id,
                decided_at=datetime.now(UTC),
            )
        )
    return {"application_id": application_id, "status": new_status, "note": note, "policy": policy}


@router.get("/api/applications/mine/decision")
def my_decision(user: SmeDep, request: Request) -> dict | None:
    """The underwriter's decision and note on the owner's latest application, or null."""
    applications, decisions = accounts.applications, underwriting_decisions
    query = (
        select(decisions.c.decision, decisions.c.note, decisions.c.decided_at)
        .join(applications, applications.c.id == decisions.c.application_id)
        .where(applications.c.user_id == user.id)
        .order_by(applications.c.id.desc())
    )
    with request.app.state.db.connect() as db:
        row = db.execute(query).mappings().first()
    return dict(row) if row else None
