from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, inspect
from sqlalchemy.exc import IntegrityError

from api import payouts
from api.main import app

NOW = datetime(2026, 11, 14, 4, 0, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client.app.state.db


def payout_row(**changes) -> dict:
    return {
        "user_id": 1,
        "policy_id": 7,
        "loss_date": date(2026, 11, 14),
        "region": "central",
        "centre": "Maxwell Food Centre",
        "product": "cooked_food",
        "tier": "tier_2",
        "daily_payout_cents": 5000,
        "tariff_version": 1,
        "readings": {"rain": 52.4},
        "source": "nea_history",
        "loss_percent": 62.4,
        "main_hazard": "rain",
        "assessed_cents": 3120,
        "amount_cents": 3120,
        "status": "assessed",
        "paynow_proxy_type": "mobile",
        "paynow_proxy_masked": "+65 ****4567",
        "created_at": NOW,
        "updated_at": NOW,
        **changes,
    }


def sms_row(**changes) -> dict:
    return {
        "user_id": 1,
        "kind": "payout_paid",
        "to_mobile": "+6591234567",
        "language": "en",
        "status": "queued",
        "created_at": NOW,
        **changes,
    }


def test_api_start_creates_the_payout_tables(engine):
    tables = set(inspect(engine).get_table_names())
    assert {"payout_accounts", "payouts", "payout_events", "sms_messages", "sms_codes"} <= tables


def test_existing_tables_are_left_unchanged(engine):
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert "paynow_proxy" not in user_columns
    assert "sms_mobile" not in user_columns


def test_one_payout_per_user_per_loss_date(engine):
    with engine.begin() as db:
        db.execute(insert(payouts.payouts).values(**payout_row()))
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(insert(payouts.payouts).values(**payout_row(policy_id=8)))


def test_same_user_can_be_paid_on_another_day(engine):
    with engine.begin() as db:
        db.execute(insert(payouts.payouts).values(**payout_row()))
        db.execute(insert(payouts.payouts).values(**payout_row(loss_date=date(2026, 11, 15))))


def test_provider_reference_is_unique(engine):
    with engine.begin() as db:
        db.execute(insert(payouts.payouts).values(**payout_row(provider_reference="PN-1")))
    duplicate = payout_row(loss_date=date(2026, 11, 15), provider_reference="PN-1")
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(insert(payouts.payouts).values(**duplicate))


def test_one_paid_text_per_payout(engine):
    with engine.begin() as db:
        payout_id = db.execute(
            insert(payouts.payouts).values(**payout_row()).returning(payouts.payouts.c.id)
        ).scalar_one()
        db.execute(insert(payouts.sms_messages).values(**sms_row(payout_id=payout_id)))
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(insert(payouts.sms_messages).values(**sms_row(payout_id=payout_id)))


def test_one_time_codes_have_no_payout_and_do_not_collide(engine):
    with engine.begin() as db:
        db.execute(insert(payouts.sms_messages).values(**sms_row(kind="otp")))
        db.execute(insert(payouts.sms_messages).values(**sms_row(kind="otp")))


def test_payout_events_point_at_their_payout(engine):
    foreign_keys = inspect(engine).get_foreign_keys("payout_events")
    assert [(fk["referred_table"], fk["constrained_columns"]) for fk in foreign_keys] == [
        ("payouts", ["payout_id"])
    ]
