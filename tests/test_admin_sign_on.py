from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.main import DEFAULT_TARIFF_PATH, app

ADMIN = ("admin", "secret")
CENTRE = "Commonwealth Crescent Market"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def register(client, role: str) -> None:
    body = {
        "role": role,
        "name": "Arjun Menon",
        "email": f"{role}@example.com",
        "password": "password1",
    }
    if role == "sme":
        body |= {"centre": CENTRE, "product": "cooked_food"}
    else:
        body |= {"insurer": "Income Insurance"}
    assert client.post("/api/auth/register", json=body).status_code == 200


def tariff_change(version: int = 1) -> dict:
    tariff = json.loads(DEFAULT_TARIFF_PATH.read_text())
    tariff["tiers"][0]["daily_payout_sgd"] = 10
    return {"based_on_version": version, "tariff": tariff}


def preview_body() -> dict:
    tariff = json.loads(DEFAULT_TARIFF_PATH.read_text())
    return {"tariff": tariff, "region": "central", "product": "cooked_food", "readings": {}}


def test_an_insurer_session_opens_the_desk_without_the_admin_login(client):
    register(client, "insurer")
    me = client.get("/api/admin/me").json()
    assert (me["name"], me["organisation"], me["signed_in_with"]) == (
        "Arjun Menon",
        "Income Insurance",
        "session",
    )
    assert client.get("/api/admin/tariff").status_code == 200
    assert client.post("/api/admin/preview", json=preview_body()).status_code == 200


def test_an_insurer_session_saves_a_version_under_its_own_name(client):
    register(client, "insurer")
    response = client.put("/api/admin/tariff", json=tariff_change())
    assert response.status_code == 200
    assert response.json()["saved_by"] == "Arjun Menon (insurer@example.com)"
    assert client.get("/api/admin/tariff").json()["version"] == 2


def test_a_business_owner_session_cannot_use_the_desk(client):
    register(client, "sme")
    assert client.get("/api/admin/me").status_code == 403
    assert client.get("/api/admin/tariff").status_code == 403
    assert client.post("/api/admin/preview", json=preview_body()).status_code == 403
    assert client.put("/api/admin/tariff", json=tariff_change()).status_code == 403


def test_no_session_and_no_login_cannot_use_the_desk(client):
    assert client.get("/api/admin/me").status_code == 401
    assert client.get("/api/admin/tariff").status_code == 401
    assert client.put("/api/admin/tariff", json=tariff_change()).status_code == 401


def test_a_signed_out_insurer_cannot_use_the_desk(client):
    register(client, "insurer")
    client.post("/api/auth/logout")
    assert client.get("/api/admin/tariff").status_code == 401


def test_the_admin_login_still_works_and_saves_as_admin(client):
    me = client.get("/api/admin/me", auth=ADMIN).json()
    assert (me["name"], me["signed_in_with"]) == ("admin", "password")
    saved = client.put("/api/admin/tariff", json=tariff_change(), auth=ADMIN).json()
    assert (saved["version"], saved["saved_by"]) == (2, "admin")


def test_a_wrong_admin_login_is_refused_even_with_an_insurer_session(client):
    register(client, "insurer")
    assert client.get("/api/admin/tariff", auth=("admin", "wrong")).status_code == 401


def test_the_admin_login_works_while_a_business_owner_is_signed_in(client):
    register(client, "sme")
    assert client.get("/api/admin/tariff", auth=ADMIN).status_code == 200
