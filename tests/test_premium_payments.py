"""Simulated PayNow payment of the first week's premium in the buy flow.

The customer scans a QR that opens a simulated bank screen, confirms, and the buy flow finishes
with that payment's reference. No real PayNow code is made: the QR holds a link to the demo
bank screen, so scanning it cannot send real money.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from api import calculator, premium
from api.main import app
from tests import test_api

CENTRE = test_api.buy_body()["centre"]
ORDER = {"tier": "tier_2", "amount_sgd": 0.0}  # amount_sgd: filled in by weekly_premium()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def buy_body(**changes) -> dict:
    """The buy flow's request (tests/test_api.py), paying by PayNow."""
    return test_api.buy_body(**({"payment_method": "paynow"} | changes))


def weekly_premium(client, tier: str = "tier_2") -> float:
    """What the buy flow shows as due, and charges: the tier's weekly premium priced at CENTRE."""
    quote = client.post("/api/quote", json={"centre": CENTRE, "product": "cooked_food"})
    return next(t for t in quote.json()["tiers"] if t["tier"] == tier)["weekly_premium_sgd"]


def start(client, **changes) -> dict:
    order = ORDER | {"amount_sgd": weekly_premium(client, changes.get("tier", "tier_2"))} | changes
    response = client.post("/api/premium-payments", json=order)
    assert response.status_code == 200, response.text
    return response.json()


def paid(client, **changes) -> dict:
    payment = start(client, **changes)
    assert client.post(f"/api/premium-payments/{payment['token']}/pay").status_code == 200
    return payment


def test_payment_starts_pending_for_the_first_weeks_premium(client):
    payment = start(client)
    assert payment["status"] == "pending"
    assert payment["amount_sgd"] > 0
    assert payment["reference"].startswith("SDP-")
    assert len(payment["token"]) >= 20
    assert "/paynow-demo/" in payment["bank_url"] and payment["token"] in payment["bank_url"]


def test_amount_is_the_weekly_premium_of_the_policy_it_buys(client):
    payment = paid(client)
    result = client.post("/api/buy", json=buy_body(payment_token=payment["token"])).json()
    assert result["policy"]["weekly_premium_sgd"] == payment["amount_sgd"]


def test_buying_with_a_paid_payment_keeps_its_reference(client):
    payment = paid(client)
    response = client.post("/api/buy", json=buy_body(payment_token=payment["token"]))
    assert response.status_code == 200, response.text
    application = response.json()["application"]
    assert application["payment_method"] == "paynow"
    assert application["payment_ref"] == payment["reference"]
    assert client.get(f"/api/premium-payments/{payment['token']}").json()["status"] == "used"


def test_qr_is_an_svg_image(client):
    payment = start(client)
    response = client.get(f"/api/premium-payments/{payment['token']}/qr.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in response.text


def test_paying_twice_or_after_cancelling_is_refused(client):
    payment = paid(client)
    assert client.post(f"/api/premium-payments/{payment['token']}/pay").status_code == 409
    cancelled = start(client)
    assert client.post(f"/api/premium-payments/{cancelled['token']}/cancel").status_code == 200
    assert client.get(f"/api/premium-payments/{cancelled['token']}").json()["status"] == "cancelled"
    assert client.post(f"/api/premium-payments/{cancelled['token']}/pay").status_code == 409


def test_an_expired_payment_cannot_be_paid(client):
    payment = start(client)
    with client.app.state.db.begin() as db:
        db.execute(
            update(premium.premium_payments).values(expires_at=datetime.now(UTC) - timedelta(1))
        )
    assert client.get(f"/api/premium-payments/{payment['token']}").json()["status"] == "expired"
    assert client.post(f"/api/premium-payments/{payment['token']}/pay").status_code == 409


def test_unknown_payment_is_404(client):
    assert client.get("/api/premium-payments/not-a-token").status_code == 404
    assert client.post("/api/premium-payments/not-a-token/pay").status_code == 404


@pytest.mark.parametrize("changes", [{"amount_sgd": 0}, {"amount_sgd": 501}, {"tier": ""}])
def test_payment_needs_a_tier_and_a_sensible_amount(client, changes):
    assert client.post("/api/premium-payments", json=ORDER | changes).status_code == 422


def test_paynow_buy_refuses_a_payment_for_another_amount(client):
    payment = start(client, amount_sgd=1.0)
    client.post(f"/api/premium-payments/{payment['token']}/pay")
    response = client.post("/api/buy", json=buy_body(payment_token=payment["token"]))
    assert response.status_code == 409


def test_paynow_buy_needs_a_payment(client):
    assert client.post("/api/buy", json=buy_body()).status_code == 422


def test_paynow_buy_refuses_an_unpaid_payment(client):
    payment = start(client)
    response = client.post("/api/buy", json=buy_body(payment_token=payment["token"]))
    assert response.status_code == 409


def test_paynow_buy_refuses_a_payment_for_another_tier(client):
    payment = paid(client, tier="tier_1")
    response = client.post("/api/buy", json=buy_body(payment_token=payment["token"]))
    assert response.status_code == 409


def test_a_payment_buys_once(client):
    payment = paid(client)
    first = client.post("/api/buy", json=buy_body(payment_token=payment["token"]))
    assert first.status_code == 200
    again = buy_body(email="other@example.test", payment_token=payment["token"])
    assert client.post("/api/buy", json=again).status_code == 409


def test_giro_buy_needs_no_paynow_payment(client):
    response = client.post("/api/buy", json=buy_body(payment_method="giro"))
    assert response.status_code == 200
    assert response.json()["application"]["payment_ref"].startswith("DEMO-")


def test_the_qr_opens_the_success_page_on_the_public_site(client, monkeypatch):
    monkeypatch.delenv("PUBLIC_SITE_URL", raising=False)
    payment = start(client)
    assert payment["bank_url"].startswith("https://payung.nuza.dev/paynow-demo/?")
    assert payment["bank_url"].endswith(payment["bank_path"])


def test_the_success_page_link_carries_the_amount_and_reference(client):
    payment = start(client)
    query = parse_qs(urlsplit(payment["bank_path"]).query)
    assert query == {
        "t": [payment["token"]],
        "a": [f"{payment['amount_sgd']:.2f}"],
        "r": [payment["reference"]],
    }


def test_public_site_url_moves_the_qr_to_another_site(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://safeday.example.test/")
    payment = start(client)
    assert payment["bank_url"].startswith("https://safeday.example.test/paynow-demo/?")


def test_a_public_site_url_without_http_is_ignored(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "safeday.example.test")
    payment = start(client)
    assert payment["bank_url"].startswith("https://payung.nuza.dev/paynow-demo/?")


def add_on_weekly(client, tier: str = "tier_2") -> float:
    quote = client.post("/api/quote", json={"centre": CENTRE, "product": "cooked_food"})
    return next(t for t in quote.json()["tiers"] if t["tier"] == tier)["haze_bonus"]["weekly_sgd"]


def test_the_first_payment_covers_the_severe_haze_payout_when_it_is_added(client, monkeypatch):
    monkeypatch.setattr(calculator, "singapore_today", lambda: date(2026, 11, 15))
    total = round(weekly_premium(client) + add_on_weekly(client), 2)
    cover_only = paid(client)
    refused = client.post("/api/buy", json=buy_body(
        payment_token=cover_only["token"], add_haze_bonus=True,
    ))
    assert refused.status_code == 409
    both = paid(client, amount_sgd=total)
    bought = client.post("/api/buy", json=buy_body(
        payment_token=both["token"], add_haze_bonus=True, email="both@example.test",
    ))
    assert bought.status_code == 200, bought.text
    assert bought.json()["policy"]["haze_bonus"]["weekly_sgd"] == add_on_weekly(client)
