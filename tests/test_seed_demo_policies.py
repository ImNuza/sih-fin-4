from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api import accounts, store
from api.main import DEMO_EMAIL_DOMAIN, app

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_demo_policies  # noqa: E402

ADMIN = ("admin", "secret")
INSURER = {"role": "insurer", "name": "Test Insurer", "email": "insurer@example.test",
           "password": "insurer-pass-1", "insurer": "Income Insurance"}


@pytest.fixture
def database(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'tariff.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    return url


def count(url: str, table) -> int:
    engine = store.connect(url)
    with engine.connect() as db:
        total = db.execute(select(func.count()).select_from(table)).scalar_one()
    engine.dispose()
    return total


def test_seed_adds_200_priced_demo_policies_once(database):
    seed_demo_policies.main([])
    seed_demo_policies.main([])
    assert count(database, accounts.policies) == seed_demo_policies.DEMO_POLICIES

    with TestClient(app) as client:
        client.post("/api/auth/register", json=INSURER)
        book = client.get("/api/insurer/policies").json()
        quotes = {kind: client.post("/api/quote", json=quote_request(policy)).json()
                  for kind, policy in first_of_each_class(book).items()}
    assert len(book) == seed_demo_policies.DEMO_POLICIES
    assert all(policy["demo"] for policy in book)
    assert {policy["business_class"] for policy in book} == {"hawker", "shop", "platform_worker"}
    assert len({policy["region"] for policy in book}) == 5
    assert all(policy["term_months"] in (12, 24) for policy in book)

    for kind, policy in first_of_each_class(book).items():
        tier = next(t for t in quotes[kind]["tiers"] if t["tier"] == policy["tier"])
        assert policy["weekly_premium_sgd"] == tier["weekly_premium_sgd"], kind
        assert policy["daily_payout_sgd"] == tier["daily_payout_sgd"], kind


def first_of_each_class(book: list[dict]) -> dict[str, dict]:
    firsts: dict[str, dict] = {}
    for policy in book:
        firsts.setdefault(policy["business_class"], policy)
    return firsts


def quote_request(policy: dict) -> dict:
    """The /api/quote body for where the buy flow prices this business."""
    if policy["business_class"] == "hawker":
        return {"centre": policy["centre"], "product": policy["product"]}
    if policy["business_class"] == "shop":
        return {"postcode": policy["postcode"], "product": policy["product"]}
    return {"region": policy["region"], "product": policy["product"]}


def test_remove_deletes_only_demo_records(database):
    seed_demo_policies.main([])
    with TestClient(app) as client:
        client.post("/api/auth/register", json=INSURER)
    seed_demo_policies.main(["--remove"])

    assert count(database, accounts.policies) == 0
    engine = store.connect(database)
    with engine.connect() as db:
        emails = list(db.execute(select(accounts.users.c.email)).scalars())
    engine.dispose()
    assert emails == [INSURER["email"]]
    assert not any(email.endswith(DEMO_EMAIL_DOMAIN) for email in emails)


def test_seed_refuses_a_database_on_another_host(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.example.com/safeday")
    with pytest.raises(SystemExit, match="db.example.com"):
        seed_demo_policies.main([])
