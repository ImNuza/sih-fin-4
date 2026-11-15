"""Simulated PayNow payment of the first week's premium, for the buy flow demo.

The buy flow starts a payment for the tier being bought and shows a QR. The QR holds a link to
a simulated bank screen (/paynow-demo/), never a real PayNow code, so scanning it cannot send
real money. Confirming on that screen marks the payment paid; the buy flow sees it and
finishes, and POST /api/buy accepts a PayNow purchase only with a paid, unused payment for the
same tier and for exactly the weekly premium it prices for the policy. The buy flow sends the
amount it shows; a payment for any other amount cannot buy cover.

Statuses: pending → paid → used, or pending → cancelled. A pending payment past expires_at
reads as expired.
"""

from __future__ import annotations

import io
import secrets
from datetime import UTC, datetime, timedelta

import segno
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    Integer,
    String,
    Table,
    insert,
    select,
    update,
)

from api.store import metadata

PAYMENT_LIFETIME = timedelta(minutes=10)
MAX_WEEKLY_PREMIUM_SGD = 500
PAYEE = "SafeDay by Income (demo)"
BANK_PAGE = "/paynow-demo/"

premium_payments = Table(
    "premium_payments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("token", String, nullable=False, unique=True),
    Column("reference", String, nullable=False, unique=True),
    Column("tier", String, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("paid_at", DateTime(timezone=True)),
    Column("used_at", DateTime(timezone=True)),
)

router = APIRouter(prefix="/api/premium-payments")


class PaymentIn(BaseModel):
    tier: str = Field(min_length=1, max_length=30)
    amount_sgd: float = Field(gt=0, le=MAX_WEEKLY_PREMIUM_SGD)


def as_utc(moment: datetime) -> datetime:
    """SQLite drops the time zone; every time here is stored in UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def current_status(row) -> str:
    if row.status == "pending" and as_utc(row.expires_at) < datetime.now(UTC):
        return "expired"
    return row.status


def site_origin(request: Request) -> str:
    """The address the customer used, so a phone scanning the QR reaches the same site."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{scheme}://{host}"


def bank_url(request: Request, token: str) -> str:
    return f"{site_origin(request)}{BANK_PAGE}?t={token}"


def view(row, request: Request) -> dict:
    return {
        "token": row.token,
        "reference": row.reference,
        "payee": PAYEE,
        "amount_sgd": row.amount_cents / 100,
        "tier": row.tier,
        "status": current_status(row),
        "expires_at": as_utc(row.expires_at),
        "bank_url": bank_url(request, row.token),
        "qr_url": f"/api/premium-payments/{row.token}/qr.svg",
    }


def find(db: Connection, token: str):
    row = db.execute(select(premium_payments).where(premium_payments.c.token == token)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payment")
    return row


def new_reference(db: Connection) -> str:
    while True:
        reference = f"SDP-{secrets.token_hex(3).upper()}"
        taken = db.execute(
            select(premium_payments.c.id).where(premium_payments.c.reference == reference)
        ).first()
        if taken is None:
            return reference


@router.post("")
def start_payment(body: PaymentIn, request: Request) -> dict:
    """Start a PayNow payment of the first week's premium. Public: the buyer has no account yet."""
    now = datetime.now(UTC)
    with request.app.state.db.begin() as db:
        values = {
            "token": secrets.token_urlsafe(24),
            "reference": new_reference(db),
            "tier": body.tier,
            "amount_cents": round(body.amount_sgd * 100),
            "status": "pending",
            "created_at": now,
            "expires_at": now + PAYMENT_LIFETIME,
        }
        db.execute(insert(premium_payments).values(**values))
        row = find(db, values["token"])
    return view(row, request)


@router.get("/{token}")
def get_payment(token: str, request: Request) -> dict:
    with request.app.state.db.connect() as db:
        return view(find(db, token), request)


@router.get("/{token}/qr.svg")
def payment_qr(token: str, request: Request) -> Response:
    """A QR of the simulated bank screen's link. Not a PayNow code: it cannot move real money."""
    with request.app.state.db.connect() as db:
        find(db, token)
    svg = io.BytesIO()
    segno.make(bank_url(request, token), error="m").save(svg, kind="svg", scale=6, border=2)
    return Response(svg.getvalue(), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


def finish(request: Request, token: str, to_status: str) -> dict:
    """Move a pending payment to paid or cancelled, once."""
    now = datetime.now(UTC)
    with request.app.state.db.begin() as db:
        row = find(db, token)
        if current_status(row) != "pending":
            raise HTTPException(status.HTTP_409_CONFLICT, f"This payment is {current_status(row)}")
        stamp = {"paid_at": now} if to_status == "paid" else {}
        db.execute(
            update(premium_payments)
            .where(premium_payments.c.id == row.id, premium_payments.c.status == "pending")
            .values(status=to_status, **stamp)
        )
        row = find(db, token)
    return view(row, request)


@router.post("/{token}/pay")
def pay(token: str, request: Request) -> dict:
    """The simulated bank's 'Pay' button. No money moves."""
    return finish(request, token, "paid")


@router.post("/{token}/cancel")
def cancel(token: str, request: Request) -> dict:
    return finish(request, token, "cancelled")


def take_payment(db: Connection, token: str, tier: str, amount_cents: int) -> str:
    """Use a paid payment for one purchase. Returns its reference; raises 409 if it can't pay."""
    row = find(db, token)
    if current_status(row) != "paid":
        raise HTTPException(status.HTTP_409_CONFLICT, "The PayNow payment is not complete")
    if (row.tier, row.amount_cents) != (tier, amount_cents):
        raise HTTPException(status.HTTP_409_CONFLICT, "That payment was for a different cover")
    used = db.execute(
        update(premium_payments)
        .where(premium_payments.c.id == row.id, premium_payments.c.status == "paid")
        .values(status="used", used_at=datetime.now(UTC))
    )
    if used.rowcount != 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "That payment has already been used")
    return row.reference
