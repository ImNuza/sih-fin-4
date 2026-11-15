from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from api.accounts import policies
from api.main import app

LONG_AGO = datetime(2026, 1, 1, 4, 0, tzinfo=UTC)
CENTRE = "Commonwealth Crescent Market"
GOOD_MOBILE = "+6591234567"
FAILING_MOBILE = "+6591230000"
FLOOD_DAY = {"loss_date": "2026-11-14", "source": "manual", "readings": {"closure": 1}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def register(client, role: str, email: str) -> None:
    body = {"role": role, "name": "Tan", "email": email, "password": "password1"}
    if role == "sme":
        body |= {"centre": CENTRE, "product": "cooked_food"}
    else:
        body |= {"insurer": "Income Insurance"}
    assert client.post("/api/auth/register", json=body).status_code == 200


def sign_in(client, email: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": "password1"})
    assert response.status_code == 200


def start_cover_on(client, started_at: datetime) -> None:
    with client.app.state.db.begin() as db:
        db.execute(update(policies).values(started_at=started_at))


def stallholder_with_cover(
    client, mobile: str = GOOD_MOBILE, verify: bool = True, started_at: datetime = LONG_AGO
) -> None:
    register(client, "sme", "tan@example.com")
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 200
    start_cover_on(client, started_at)
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": mobile, "sms_language": "en"}
    assert client.put("/api/payout-account", json=account).status_code == 200
    if verify:
        code = client.post("/api/payout-account/verify/start").json()["demo_code"]
        assert client.post("/api/payout-account/verify", json={"code": code}).status_code == 200


def run_as_insurer(client, body: dict) -> dict:
    register(client, "insurer", "desk@example.com")
    response = client.post("/api/insurer/payout-runs", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_payout_account_is_returned_masked_with_the_paynow_name(client):
    stallholder_with_cover(client, verify=False)
    account = client.get("/api/payout-account").json()
    assert account["paynow_proxy_masked"] == "+65 ****4567"
    assert "paynow_proxy" not in account
    assert account["paynow_name"]
    assert account["mobile_verified"] is False


@pytest.mark.parametrize("mobile", ["91234567", "+6571234567", "+659123456", "+6591234567x"])
def test_payout_account_rejects_non_singapore_mobiles(client, mobile):
    register(client, "sme", "tan@example.com")
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": mobile, "sms_language": "en"}
    assert client.put("/api/payout-account", json=account).status_code == 422


def test_wrong_code_does_not_verify_the_mobile(client):
    stallholder_with_cover(client, verify=False)
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    wrong = "000000" if code != "000000" else "111111"
    response = client.post("/api/payout-account/verify", json={"code": wrong})
    assert response.status_code == 400
    assert client.get("/api/payout-account").json()["mobile_verified"] is False


def test_code_locks_after_five_wrong_tries(client):
    stallholder_with_cover(client, verify=False)
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        client.post("/api/payout-account/verify", json={"code": wrong})
    response = client.post("/api/payout-account/verify", json={"code": code})
    assert response.status_code == 429


def test_closure_day_pays_by_paynow_and_texts_the_stallholder(client):
    stallholder_with_cover(client)
    run = run_as_insurer(client, FLOOD_DAY)
    assert run["counts"]["paid"] == 1

    sign_in(client, "tan@example.com")
    [payout] = client.get("/api/payouts").json()
    assert payout["status"] == "paid"
    assert payout["loss_percent"] == 100
    assert payout["amount_sgd"] == payout["daily_payout_sgd"]
    assert payout["reference"].startswith("SD-")

    [text] = [m for m in client.get("/api/sms").json() if m["kind"] == "payout_paid"]
    assert f"S${payout['amount_sgd']:.2f}" in text["body"]
    assert payout["reference"] in text["body"]
    assert "+65 ****4567" in text["body"]


def test_payout_history_is_kept_in_order(client):
    stallholder_with_cover(client)
    run_as_insurer(client, FLOOD_DAY)
    sign_in(client, "tan@example.com")
    [payout] = client.get("/api/payouts").json()
    statuses = [event["to_status"] for event in payout["events"]]
    assert statuses == ["assessed", "approved", "sending", "paid"]


def test_running_the_same_day_twice_pays_once(client):
    stallholder_with_cover(client)
    run_as_insurer(client, FLOOD_DAY)
    again = client.post("/api/insurer/payout-runs", json=FLOOD_DAY).json()
    assert again["counts"]["already_assessed"] == 1
    assert len(client.get("/api/payouts").json()) == 1


def test_day_without_loss_creates_no_payout(client):
    stallholder_with_cover(client)
    run = run_as_insurer(client, {**FLOOD_DAY, "readings": {"rain": 0}})
    assert run["counts"]["no_loss"] == 1
    assert client.get("/api/payouts").json() == []


def test_unverified_mobile_holds_the_payout_until_verified(client):
    stallholder_with_cover(client, verify=False)
    run = run_as_insurer(client, FLOOD_DAY)
    assert run["counts"]["held"] == 1

    sign_in(client, "tan@example.com")
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    client.post("/api/payout-account/verify", json={"code": code})
    [payout] = client.get("/api/payouts").json()
    assert payout["status"] == "paid"


def test_failed_transfer_texts_the_stallholder_and_can_be_retried(client):
    stallholder_with_cover(client, mobile=FAILING_MOBILE)
    run = run_as_insurer(client, FLOOD_DAY)
    assert run["counts"]["failed"] == 1

    sign_in(client, "tan@example.com")
    kinds = {m["kind"] for m in client.get("/api/sms").json()}
    assert "payout_failed" in kinds
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": GOOD_MOBILE, "sms_language": "en"}
    client.put("/api/payout-account", json=account)
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    client.post("/api/payout-account/verify", json={"code": code})

    sign_in(client, "desk@example.com")
    [payout] = client.get("/api/payouts").json()
    retried = client.post(f"/api/insurer/payouts/{payout['id']}/retry")
    assert retried.json()["status"] == "paid"


def test_insurer_can_reject_a_held_payout_with_a_reason(client):
    stallholder_with_cover(client, verify=False)
    run_as_insurer(client, FLOOD_DAY)
    [payout] = client.get("/api/payouts").json()
    response = client.post(
        f"/api/insurer/payouts/{payout['id']}/reject", json={"reason": "Stall closed that week"}
    )
    assert response.json()["status"] == "rejected"
    assert response.json()["failure_reason"] == "Stall closed that week"


def test_paid_payout_cannot_be_rejected(client):
    stallholder_with_cover(client)
    run_as_insurer(client, FLOOD_DAY)
    [payout] = client.get("/api/payouts").json()
    response = client.post(f"/api/insurer/payouts/{payout['id']}/reject", json={"reason": "No"})
    assert response.status_code == 409


def test_yearly_cap_limits_what_is_paid(client):
    stallholder_with_cover(client)
    [policy] = client.get("/api/policies").json()
    max_days = policy["max_paid_days_per_year"]
    register(client, "insurer", "desk@example.com")
    for day in range(1, max_days + 2):
        body = {**FLOOD_DAY, "loss_date": f"2026-10-{day:02d}"}
        client.post("/api/insurer/payout-runs", json=body)
    payouts = client.get("/api/payouts").json()
    paid = [p for p in payouts if p["status"] == "paid"]
    capped = [p for p in payouts if p["status"] == "capped"]
    assert len(paid) == max_days
    assert len(capped) == 1 and capped[0]["amount_sgd"] == 0


def test_history_run_records_the_readings_it_used(client):
    stallholder_with_cover(client)
    run = run_as_insurer(client, {"loss_date": "2026-11-08", "source": "nea_history"})
    assert run["readings_found"] is True
    assert sum(run["counts"].values()) == 1


def test_history_run_for_a_day_without_data_is_404(client):
    stallholder_with_cover(client)
    register(client, "insurer", "desk@example.com")
    body = {"loss_date": "2001-01-01", "source": "nea_history"}
    assert client.post("/api/insurer/payout-runs", json=body).status_code == 404


def test_stallholders_cannot_run_payouts(client):
    stallholder_with_cover(client)
    assert client.post("/api/insurer/payout-runs", json=FLOOD_DAY).status_code == 403


def test_stallholder_sees_only_their_own_payouts(client):
    stallholder_with_cover(client)
    run_as_insurer(client, FLOOD_DAY)
    register(client, "sme", "lim@example.com")
    assert client.get("/api/payouts").json() == []


# Cover bought at 12:00 Singapore time on 1 Oct 2026 pays from 31 Oct, 30 days later.
STARTED_1_OCT_SGT = datetime(2026, 10, 1, 4, 0, tzinfo=UTC)


@pytest.mark.parametrize("loss_date", ["2026-09-28", "2026-10-01", "2026-10-30"])
def test_day_before_or_inside_the_waiting_period_is_not_paid(client, loss_date):
    stallholder_with_cover(client, started_at=STARTED_1_OCT_SGT)
    run = run_as_insurer(client, {**FLOOD_DAY, "loss_date": loss_date})
    assert run["counts"]["waiting_period"] == 1
    assert client.get("/api/payouts").json() == []


def test_first_day_after_the_waiting_period_is_paid(client):
    stallholder_with_cover(client, started_at=STARTED_1_OCT_SGT)
    run = run_as_insurer(client, {**FLOOD_DAY, "loss_date": "2026-10-31"})
    assert run["counts"]["paid"] == 1


def test_waiting_period_uses_the_singapore_date_of_purchase(client):
    late_evening_30_sep_utc = datetime(2026, 9, 30, 17, 0, tzinfo=UTC)
    stallholder_with_cover(client, started_at=late_evening_30_sep_utc)
    run = run_as_insurer(client, {**FLOOD_DAY, "loss_date": "2026-10-30"})
    assert run["counts"]["waiting_period"] == 1
