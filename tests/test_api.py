from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.main import DEFAULT_TARIFF_PATH, app

ADMIN = ("admin", "secret")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def default_tariff() -> dict:
    return json.loads(DEFAULT_TARIFF_PATH.read_text())


def test_options_list_the_five_psi_regions(client):
    options = client.get("/api/options").json()
    assert options["regions"] == ["central", "east", "north", "south", "west"]
    with_history = {hazard["key"] for hazard in options["hazards"] if hazard["has_history"]}
    assert with_history == {"haze", "rain", "heat"}


@pytest.mark.parametrize("region", ["central", "east", "north", "south", "west"])
def test_every_region_quotes_rising_premiums(client, region):
    response = client.post("/api/quote", json={"region": region, "product": "cooked_food"})
    assert response.status_code == 200
    premiums = [tier["weekly_premium_sgd"] for tier in response.json()["tiers"]]
    assert premiums == sorted(premiums)
    assert premiums[0] > 0


def test_perishable_food_costs_more_than_general_goods(client):
    def tier_1_price(product: str) -> float:
        quote = client.post("/api/quote", json={"region": "east", "product": product}).json()
        return quote["tiers"][0]["weekly_premium_sgd"]

    assert tier_1_price("cooked_food") > tier_1_price("general_goods")


def test_unknown_product_is_404(client):
    response = client.post("/api/quote", json={"region": "east", "product": "fish"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown product: fish"


def test_closure_pays_the_full_tier_payout(client):
    body = {"product": "general_goods", "tier": "tier_3", "readings": {"closure": 1}}
    day = client.post("/api/assess", json=body).json()
    assert day["loss_percent"] == 100
    assert day["payout_sgd"] == 70


def test_admin_needs_the_right_login(client):
    assert client.get("/api/admin/tariff").status_code == 401
    assert client.get("/api/admin/tariff", auth=("admin", "wrong")).status_code == 401
    saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    assert saved["version"] == 1
    assert saved["saved_by"] == "default"


def test_saving_adds_a_version_that_quotes_use(client):
    tariff = default_tariff()
    tariff["tiers"][0]["daily_payout_sgd"] = 10
    change = {"based_on_version": 1, "tariff": tariff}
    saved = client.put("/api/admin/tariff", json=change, auth=ADMIN).json()
    assert (saved["version"], saved["saved_by"]) == (2, "admin")
    quote = client.post("/api/quote", json={"region": "east", "product": "cooked_food"}).json()
    assert quote["tiers"][0]["daily_payout_sgd"] == 10


def test_a_tariff_that_cannot_price_is_not_saved(client):
    tariff = default_tariff()
    flood = next(hazard for hazard in tariff["hazards"] if hazard["key"] == "flood")
    flood["assumed_days_per_year"] = None
    change = {"based_on_version": 1, "tariff": tariff}
    response = client.put("/api/admin/tariff", json=change, auth=ADMIN)
    assert response.status_code == 422
    assert "Flash flood has no NEA history" in response.json()["detail"]
    assert client.get("/api/admin/tariff", auth=ADMIN).json()["version"] == 1


def test_a_change_from_an_old_version_is_refused(client):
    change = {"based_on_version": 1, "tariff": default_tariff()}
    assert client.put("/api/admin/tariff", json=change, auth=ADMIN).status_code == 200
    response = client.put("/api/admin/tariff", json=change, auth=ADMIN)
    assert response.status_code == 409
    assert "admin saved version 2 after you started" in response.json()["detail"]


def test_preview_prices_an_unsaved_tariff_for_every_tier(client):
    body = {
        "tariff": default_tariff(),
        "region": "west",
        "product": "flowers",
        "readings": {"haze": 230, "rain": 35},
    }
    preview = client.post("/api/admin/preview", json=body, auth=ADMIN).json()
    assert [a["tier"] for a in preview["assessments"]] == ["tier_1", "tier_2", "tier_3", "tier_4"]
    assert len({a["loss_percent"] for a in preview["assessments"]}) == 1


def test_rent_table_covers_every_map_centre(client):
    table = client.get("/api/rent").json()
    centres = client.get("/api/map/static").json()["hawker_centres"]
    assert set(table["centres"]) == {c["name"] for c in centres}
    maxwell = table["centres"]["Maxwell Food Centre (Kim Hua Market)"]
    assert maxwell["bids"] > 0 and not maxwell["estimated"]
    for rent in table["centres"].values():
        assert rent["estimated"] == (rent["bids"] == 0)


def buy_body(**changes) -> dict:
    body = {
        "name": "Tan Ah Kow",
        "email": "tan@example.test",
        "password": "test-pass-123",
        "business_name": "Ah Kow Noodles",
        "centre": "Maxwell Food Centre (Kim Hua Market)",
        "product": "cooked_food",
        "applicant_type": "individual",
        "phone": "+65 9123 4567",
        "add_safeday": True,
        "tier": "tier_2",
        "declined_before": False,
        "accept_declaration": True,
        "accept_pdpa": True,
        "payment_method": "paynow",
    }
    body.update(changes)
    return body


def test_buy_creates_account_application_and_policy_and_signs_in(client):
    response = client.post("/api/buy", json=buy_body())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["application"]["status"] == "accepted"
    assert result["application"]["phone"] == "91234567"
    assert result["application"]["payment_ref"].startswith("DEMO-")
    assert result["policy"]["tier"] == "tier_2"
    assert client.get("/api/auth/me").json()["centre"] == buy_body()["centre"]
    assert len(client.get("/api/policies").json()) == 1


def test_buy_without_safeday_starts_no_policy_and_charges_nothing(client):
    result = client.post("/api/buy", json=buy_body(add_safeday=False, tier=None, payment_method=None)).json()
    assert result["policy"] is None
    assert result["application"]["payment_ref"] is None


def test_past_decline_is_referred_and_cannot_buy_from_the_dashboard(client):
    body = buy_body(declined_before=True, declined_details="Declined in 2024", payment_method=None)
    result = client.post("/api/buy", json=body).json()
    assert result["application"]["status"] == "referred"
    assert result["policy"] is None
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"applicant_type": "company", "uen": None},
        {"applicant_type": "company", "uen": "NOT-A-UEN"},
        {"phone": "1234"},
        {"accept_pdpa": False},
        {"declined_before": True, "declined_details": ""},
        {"payment_method": None},
        {"centre": "Nowhere Food Centre"},
    ],
)
def test_buy_rejects_incomplete_applications(client, changes):
    assert client.post("/api/buy", json=buy_body(**changes)).status_code == 422


def test_company_uen_is_stored_in_capitals(client):
    result = client.post("/api/buy", json=buy_body(applicant_type="company", uen="201912345k")).json()
    assert result["application"]["uen"] == "201912345K"
