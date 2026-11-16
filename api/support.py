"""Support tickets: an owner raises one from their dashboard, the insurer's desk answers it.

POST /api/support/tickets                 an owner raises a ticket (premium, application, payout,
                                          other)
GET  /api/support/tickets                 an owner sees their own; an insurer sees every ticket,
                                          open ones first
POST /api/support/tickets/{id}/reply      an insurer answers, and may close it

A ticket asks a person for help; it never changes a price or a payout by itself. The table
shares the tariff database (api/store.py) and is created at API start.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, case, insert, select, update

from api import accounts
from api.accounts import InsurerDep, SmeDep, UserDep
from api.store import metadata

CATEGORIES = {
    "premium": "My premium or price",
    "application": "My application",
    "payout": "A payout, or a day that did not pay",
    "other": "Something else",
}

support_tickets = Table(
    "support_tickets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("category", String, nullable=False),
    Column("subject", String, nullable=False),
    Column("message", String, nullable=False),
    Column("status", String, nullable=False),
    Column("reply", String),
    Column("replied_by", Integer),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

router = APIRouter(prefix="/api/support")


class NewTicket(BaseModel):
    category: Literal["premium", "application", "payout", "other"]
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=5, max_length=2000)


class Reply(BaseModel):
    reply: str = Field(min_length=2, max_length=2000)
    close: bool = False


def ticket_row(row) -> dict:
    return {key: value for key, value in dict(row).items() if key != "replied_by"}


@router.get("/categories")
def categories() -> dict[str, str]:
    return CATEGORIES


@router.post("/tickets")
def raise_ticket(body: NewTicket, user: SmeDep, request: Request) -> dict:
    now = datetime.now(UTC)
    values = {
        "user_id": user.id, "category": body.category, "subject": body.subject.strip(),
        "message": body.message.strip(), "status": "open", "created_at": now, "updated_at": now,
    }
    with request.app.state.db.begin() as db:
        ticket_id = db.execute(
            insert(support_tickets).values(**values).returning(support_tickets.c.id)
        ).scalar_one()
    return {"id": ticket_id, **{k: v for k, v in values.items() if k != "user_id"}}


@router.get("/tickets")
def list_tickets(user: UserDep, request: Request) -> list[dict]:
    """An owner's own tickets, newest first; for an insurer, every ticket, open ones first."""
    users = accounts.users
    query = select(support_tickets, users.c.name, users.c.business_name, users.c.centre).join(
        users, users.c.id == support_tickets.c.user_id
    )
    if user.role == "insurer":
        open_first = case((support_tickets.c.status == "open", 0), else_=1)
        query = query.order_by(open_first, support_tickets.c.id.desc())
    else:
        query = query.where(support_tickets.c.user_id == user.id).order_by(support_tickets.c.id.desc())
    with request.app.state.db.connect() as db:
        return [ticket_row(row) for row in db.execute(query).mappings()]


@router.post("/tickets/{ticket_id}/reply")
def reply(ticket_id: int, body: Reply, user: InsurerDep, request: Request) -> dict:
    new_status = "closed" if body.close else "answered"
    with request.app.state.db.begin() as db:
        changed = db.execute(
            update(support_tickets)
            .where(support_tickets.c.id == ticket_id)
            .values(reply=body.reply.strip(), replied_by=user.id, status=new_status,
                    updated_at=datetime.now(UTC))
        ).rowcount
    if not changed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No ticket {ticket_id}")
    return {"id": ticket_id, "status": new_status, "reply": body.reply.strip()}
