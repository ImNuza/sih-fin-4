"""Users, sessions and policies: role-based access for the SME and insurer dashboards.

Roles: "sme" (business owners, open registration) and "insurer" (pick the insurer and
proceed; no access code in this demo). Passwords are scrypt-hashed; a login puts a random
session token in an HttpOnly cookie. Tables share the tariff database (api/store.py).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Engine,
    Float,
    Integer,
    String,
    Table,
    delete,
    insert,
    select,
)

from api.store import metadata

SESSION_COOKIE = "safeday_session"
SESSION_DAYS = 7
SCRYPT = {"n": 2**14, "r": 8, "p": 1}
INSURERS = ("Income Insurance",)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("role", String, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("business_name", String),
    Column("centre", String),
    Column("region", String),
    Column("product", String),
    Column("insurer", String),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token", String, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
policies = Table(
    "policies",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("tier", String, nullable=False),
    Column("tier_label", String, nullable=False),
    Column("product", String, nullable=False),
    Column("region", String, nullable=False),
    Column("centre", String),
    Column("weekly_premium_sgd", Float, nullable=False),
    Column("daily_payout_sgd", Float, nullable=False),
    Column("max_paid_days_per_year", Integer, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
)
# One row per buy-flow application: what the owner declared and agreed to, and when.
# A table of its own, so existing databases need no new columns on users.
applications = Table(
    "applications",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("applicant_type", String, nullable=False),
    Column("uen", String),
    Column("phone", String, nullable=False),
    Column("add_safeday", Boolean, nullable=False),
    Column("tier", String),
    Column("declined_before", Boolean, nullable=False),
    Column("declined_details", String),
    Column("status", String, nullable=False),
    Column("declaration_accepted_at", DateTime(timezone=True), nullable=False),
    Column("pdpa_accepted_at", DateTime(timezone=True), nullable=False),
    Column("marketing_email", Boolean, nullable=False),
    Column("marketing_sms", Boolean, nullable=False),
    Column("payment_method", String),
    Column("payment_ref", String),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **SCRYPT)
    return secrets.compare_digest(digest.hex(), digest_hex)


class Registration(BaseModel):
    role: str = Field(pattern="^(sme|insurer)$")
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)
    business_name: str | None = None
    centre: str | None = None
    product: str | None = None
    insurer: str | None = None


class Login(BaseModel):
    email: str
    password: str


class Account(BaseModel):
    id: int
    email: str
    name: str
    role: str
    business_name: str | None
    centre: str | None
    region: str | None
    product: str | None
    insurer: str | None


def account_from_row(row) -> Account:
    return Account(
        id=row.id,
        email=row.email,
        name=row.name,
        role=row.role,
        business_name=row.business_name,
        centre=row.centre,
        region=row.region,
        product=row.product,
        insurer=row.insurer,
    )


def find_by_email(engine: Engine, email: str):
    with engine.connect() as db:
        return db.execute(select(users).where(users.c.email == email.lower())).first()


def start_session(engine: Engine, user_id: int, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    with engine.begin() as db:
        db.execute(insert(sessions).values(token=token, user_id=user_id, created_at=datetime.now(UTC)))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_DAYS * 24 * 3600,
    )


def current_user(request: Request) -> Account:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in first")
    engine: Engine = request.app.state.db
    with engine.connect() as db:
        row = db.execute(
            select(users)
            .join(sessions, sessions.c.user_id == users.c.id)
            .where(sessions.c.token == token)
        ).first()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again")
    return account_from_row(row)


UserDep = Annotated[Account, Depends(current_user)]


def require_role(role: str):
    def check(user: UserDep) -> Account:
        if user.role != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only {role} accounts can do this")
        return user

    return check


SmeDep = Annotated[Account, Depends(require_role("sme"))]
InsurerDep = Annotated[Account, Depends(require_role("insurer"))]

router = APIRouter(prefix="/api/auth")


def user_values(body: Registration, request: Request) -> dict:
    """The users row for a new account, checked. Raises if the email or centre is wrong."""
    engine: Engine = request.app.state.db
    if find_by_email(engine, body.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email exists. Sign in")
    values = {
        "email": body.email.lower(),
        "name": body.name,
        "role": body.role,
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(UTC),
    }
    if body.role == "insurer":
        if body.insurer not in INSURERS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick an insurer")
        values["insurer"] = body.insurer
    else:
        centres = {c["name"]: c for c in request.app.state.map_static["hawker_centres"]}
        if body.centre not in centres:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick your hawker centre")
        values["business_name"] = body.business_name or body.name
        values["centre"] = body.centre
        values["region"] = centres[body.centre]["region"]
        values["product"] = body.product
    return values


@router.post("/register")
def register(body: Registration, request: Request, response: Response) -> Account:
    """Create an account and sign it in."""
    engine: Engine = request.app.state.db
    values = user_values(body, request)
    with engine.begin() as db:
        user_id = db.execute(insert(users).values(**values).returning(users.c.id)).scalar_one()
    start_session(engine, user_id, response)
    with engine.connect() as db:
        row = db.execute(select(users).where(users.c.id == user_id)).first()
    return account_from_row(row)


@router.post("/login")
def login(body: Login, request: Request, response: Response) -> Account:
    row = find_by_email(request.app.state.db, body.email)
    if row is None or not verify_password(body.password, row.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    start_session(request.app.state.db, row.id, response)
    return account_from_row(row)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        engine: Engine = request.app.state.db
        with engine.begin() as db:
            db.execute(delete(sessions).where(sessions.c.token == token))
    response.delete_cookie(SESSION_COOKIE)
    return {"signed_out": True}


@router.get("/me")
def me(user: UserDep) -> Account:
    return user
