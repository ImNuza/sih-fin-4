"""Payouts to stallholders by PayNow, and the SMS that tells them they were paid.

Tables only for now; the design is in docs/notes/payout-flow-design-2026-11-15.md. They share
the tariff database (api/store.py) and are created at API start. They are new tables rather
than new columns on users or policies, because create_all never alters an existing table.
Money is integer cents. loss_date is the Singapore calendar date of the bad day.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)

from api.store import metadata

payout_accounts = Table(
    "payout_accounts",
    metadata,
    Column("user_id", Integer, primary_key=True, autoincrement=False),
    Column("paynow_proxy_type", String, nullable=False),
    Column("paynow_proxy", String, nullable=False),
    Column("paynow_name", String),
    Column("sms_mobile", String, nullable=False),
    Column("sms_language", String, nullable=False),
    Column("mobile_verified_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# policy_id and the policy terms are a snapshot: policies are deleted when replaced or cancelled.
payouts = Table(
    "payouts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("policy_id", Integer, nullable=False),
    Column("loss_date", Date, nullable=False),
    Column("region", String, nullable=False),
    Column("centre", String),
    Column("product", String, nullable=False),
    Column("tier", String, nullable=False),
    Column("daily_payout_cents", Integer, nullable=False),
    Column("tariff_version", Integer, nullable=False),
    Column("readings", JSON, nullable=False),
    Column("source", String, nullable=False),
    Column("loss_percent", Float, nullable=False),
    Column("main_hazard", String, nullable=False),
    Column("assessed_cents", Integer, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("paynow_proxy_type", String),
    Column("paynow_proxy_masked", String),
    Column("provider_reference", String, unique=True),
    Column("failure_reason", String),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("paid_at", DateTime(timezone=True)),
    UniqueConstraint("user_id", "loss_date", name="one_payout_per_user_per_day"),
)

payout_events = Table(
    "payout_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("payout_id", Integer, ForeignKey("payouts.id"), nullable=False),
    Column("from_status", String),
    Column("to_status", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("detail", JSON),
    Column("at", DateTime(timezone=True), nullable=False),
)

# One-time codes have no payout_id; NULLs never collide in the unique constraint.
sms_messages = Table(
    "sms_messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("payout_id", Integer, ForeignKey("payouts.id")),
    Column("kind", String, nullable=False),
    Column("to_mobile", String, nullable=False),
    Column("language", String, nullable=False),
    Column("body", String),
    Column("provider_message_id", String, unique=True),
    Column("status", String, nullable=False),
    Column("error", String),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("sent_at", DateTime(timezone=True)),
    Column("delivered_at", DateTime(timezone=True)),
    UniqueConstraint("payout_id", "kind", name="one_text_per_payout_and_kind"),
)

sms_codes = Table(
    "sms_codes",
    metadata,
    Column("user_id", Integer, primary_key=True, autoincrement=False),
    Column("code_hash", String, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
)
