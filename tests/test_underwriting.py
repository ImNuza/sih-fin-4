from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api.main import SINGAPORE, app
from tests.test_api import ADMIN, buy_body, shop_body

QUEUE = "/api/insurer/applications"
REFERRED = {"declined_before": True, "declined_details": "AIG declined in 2024", "payment_method": None}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def refer(client: TestClient, **changes) -> int:
    """Buy as an owner who was declined before, then sign out. Returns the application id."""
    response = client.post("/api/buy", json=buy_body(**REFERRED, **changes))
    assert response.status_code == 200, response.text
    client.post("/api/auth/logout")
    return response.json()["application"]["id"]


def sign_in_as_insurer(client: TestClient) -> None:
    insurer = {
        "role": "insurer",
        "name": "Lim Underwriter",
        "email": "lim@example.test",
        "password": "test-pass-123",
        "insurer": "Income Insurance",
    }
    assert client.post("/api/auth/register", json=insurer).status_code == 200


def decide(client: TestClient, application_id: int, decision: str, note: str | None = None):
    body = {"decision": decision, "note": note}
    return client.post(f"{QUEUE}/{application_id}/decision", json=body)


def test_insurer_sees_a_referred_application_with_why_it_was_declined(client):
    application_id = refer(client)
    sign_in_as_insurer(client)
    waiting = client.get(QUEUE).json()["waiting"]
    assert [a["id"] for a in waiting] == [application_id]
    assert waiting[0]["business_name"] == "Ah Kow Noodles"
    assert waiting[0]["declined_details"] == "AIG declined in 2024"
    assert waiting[0]["region"] and waiting[0]["phone"] == "91234567"


def test_approval_accepts_the_application_and_starts_the_priced_policy(client):
    later = (datetime.now(SINGAPORE).date() + timedelta(days=7)).isoformat()
    application_id = refer(client, cover_start=later)
    sign_in_as_insurer(client)
    result = decide(client, application_id, "approve", "Shelter fitted since 2024").json()
    assert result["status"] == "accepted"
    assert result["policy"]["tier"] == "tier_2"
    assert result["policy"]["started_at"].startswith(later)
    centre_quote = {"product": "cooked_food", "centre": buy_body()["centre"]}
    shown = client.post("/api/quote", json=centre_quote).json()
    assert result["policy"]["weekly_premium_sgd"] == shown["tiers"][1]["weekly_premium_sgd"]
    assert len(client.get("/api/policies").json()) == 1
    queue = client.get(QUEUE).json()
    assert queue["waiting"] == []
    assert queue["recent_decisions"][0]["note"] == "Shelter fitted since 2024"


def test_an_approved_shop_is_charged_the_price_shown_for_its_postcode(client):
    response = client.post("/api/buy", json=shop_body(**REFERRED))
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    result = decide(client, response.json()["application"]["id"], "approve").json()
    shown = client.post("/api/quote", json={"product": "packaged_food", "postcode": "560123"})
    assert result["policy"]["weekly_premium_sgd"] == shown.json()["tiers"][1]["weekly_premium_sgd"]


def test_decline_starts_no_policy_and_the_owner_sees_the_note(client):
    application_id = refer(client)
    sign_in_as_insurer(client)
    assert decide(client, application_id, "decline", "Floods every year").json()["policy"] is None
    assert client.get("/api/policies").json() == []
    client.post("/api/auth/logout")
    owner = {"email": buy_body()["email"], "password": buy_body()["password"]}
    assert client.post("/api/auth/login", json=owner).status_code == 200
    assert client.get("/api/applications/mine").json()["status"] == "declined"
    assert client.get("/api/applications/mine/decision").json()["note"] == "Floods every year"


def test_a_declined_owner_cannot_start_cover_later(client):
    application_id = refer(client)
    sign_in_as_insurer(client)
    decide(client, application_id, "decline")
    client.post("/api/auth/logout")
    owner = {"email": buy_body()["email"], "password": buy_body()["password"]}
    client.post("/api/auth/login", json=owner)
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 409


def test_an_application_is_decided_only_once(client):
    application_id = refer(client)
    sign_in_as_insurer(client)
    assert decide(client, application_id, "approve").status_code == 200
    assert decide(client, application_id, "decline").status_code == 409


def test_an_accepted_application_cannot_be_decided(client):
    client.post("/api/buy", json=buy_body())
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    assert decide(client, 1, "approve").status_code == 409


def test_an_owner_cannot_use_the_underwriter_queue(client):
    application_id = refer(client)
    owner = {"email": buy_body()["email"], "password": buy_body()["password"]}
    client.post("/api/auth/login", json=owner)
    assert client.get(QUEUE).status_code == 403
    assert decide(client, application_id, "approve").status_code == 403
