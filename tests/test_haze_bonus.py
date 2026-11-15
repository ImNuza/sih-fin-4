"""The optional severe haze payout: its price, when it is on sale, and its one lump sum a year."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from api import accounts, calculator, store
from api.main import app
from api.models import Tariff
from api.payouts import haze_bonus_payouts
from tests.test_api import (  # noqa: F401  (client is a fixture)
    ADMIN,
    MAP_STATIC,
    MAXWELL,
    buy_body,
    client,
    default_tariff,
)
from tests.test_payout_api import FAILING_MOBILE, GOOD_MOBILE, register
from tests.test_underwriting import decide, sign_in_as_insurer

OCTOBER, NOVEMBER = date(2026, 10, 15), date(2026, 11, 15)


def centre_quote(client, centre: str = MAXWELL) -> dict:
    return client.post("/api/quote", json={"product": "cooked_food", "centre": centre}).json()


@pytest.fixture
def today(monkeypatch):
    """Freeze the Singapore date the add-on's sale months are read from."""

    def freeze(day: date) -> None:
        monkeypatch.setattr(calculator, "singapore_today", lambda: day)

    freeze(NOVEMBER)
    return freeze


def test_the_price_is_the_lump_sum_over_10_to_the_cent(client, today):
    for t in centre_quote(client)["tiers"]:
        bonus = t["haze_bonus"]
        assert bonus["lump_sum_sgd"] == 25 * t["daily_payout_sgd"]
        assert bonus["yearly_sgd"] == round(bonus["lump_sum_sgd"] / 10, 2)
        assert bonus["weekly_sgd"] == round(bonus["yearly_sgd"] / 52, 2)
        steps = {step["key"]: step["amount_sgd"] for step in bonus["build_up"]}
        assert round(sum(steps.values()), 2) == bonus["yearly_sgd"]
        assert steps["expected_payouts"] == round(0.6 * bonus["yearly_sgd"] / 1.09, 2)
    yearly = [t["haze_bonus"]["yearly_sgd"] for t in centre_quote(client)["tiers"]]
    assert yearly == [87.5, 487.5, 1575, 3387.5]


def test_the_price_implies_a_payout_in_about_1_year_in_18(client, today):
    bonus = centre_quote(client)["tiers"][0]["haze_bonus"]
    assert bonus["implied_yearly_chance"] == 0.055
    assert (bonus["trigger_days"], bonus["trigger_psi"]) == (40, 101)


@pytest.mark.parametrize(
    "region, paid", [("north", [2015]), ("south", [2015]), ("west", [2015]),
                     ("central", []), ("east", [])],
)
def test_only_2015_in_three_regions_reached_40_haze_days(client, today, region, paid):
    quote = client.post("/api/quote", json={"product": "cooked_food", "region": region}).json()
    assert quote["tiers"][0]["haze_bonus"]["would_have_paid_years"] == paid


def test_it_cannot_be_added_from_may_to_october(client, today):
    today(OCTOBER)
    assert centre_quote(client)["tiers"][1]["haze_bonus"]["on_sale_now"] is False
    response = client.post("/api/buy", json=buy_body(add_haze_bonus=True))
    assert response.status_code == 422
    assert "cannot be added in May, June" in response.json()["detail"]
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    again = client.post("/api/policies", json={"tier": "tier_2", "add_haze_bonus": True})
    assert again.status_code == 422


def test_a_policy_with_the_add_on_shows_it_and_the_insurer_carries_it(client, today):
    result = client.post("/api/buy", json=buy_body(add_haze_bonus=True)).json()
    bonus = result["policy"]["haze_bonus"]
    cover_start = date.fromisoformat(result["application"]["cover_start"])
    assert (bonus["lump_sum_sgd"], bonus["yearly_sgd"]) == (4875, 487.5)
    assert bonus["starts_on"] == (cover_start + timedelta(days=30)).isoformat()
    [policy] = client.get("/api/policies").json()
    assert policy["haze_bonus"]["payouts"] == []
    assert policy["weekly_total_sgd"] == round(policy["weekly_premium_sgd"] + 9.38, 2)
    client.post("/api/auth/logout")
    register(client, "insurer", "desk@example.com")
    portfolio = client.get("/api/insurer/portfolio").json()["haze_bonus"]
    assert portfolio == {"policies": 1, "weekly_premium_sgd": 9.38, "annual_premium_sgd": 487.5,
                         "lump_sum_exposure_sgd": 4875, "lump_sums": {}}


def backdate_to_2015(client) -> None:
    """Put the signed-in owner's policy and add-on in force from 1 Jan 2015."""
    with client.app.state.db.begin() as db:
        db.execute(update(accounts.policies).values(started_at=datetime(2014, 12, 1, tzinfo=UTC)))
        db.execute(update(accounts.policy_haze_bonus).values(starts_on=date(2015, 1, 1)))


def replay_haze_season_2015(client) -> list:
    register(client, "insurer", "desk@example.com")
    day = date(2015, 10, 1)
    while day <= date(2015, 12, 31):
        run = {"loss_date": day.isoformat(), "source": "nea_history"}
        assert client.post("/api/insurer/payout-runs", json=run).status_code == 200
        day += timedelta(days=1)
    with client.app.state.db.connect() as db:
        return db.execute(select(haze_bonus_payouts)).all()


def test_the_lump_sum_is_paid_once_on_the_40th_unhealthy_day(client, today):
    assert client.post("/api/buy", json=buy_body(add_haze_bonus=True)).status_code == 200
    backdate_to_2015(client)
    client.post("/api/auth/logout")
    [lump] = replay_haze_season_2015(client)
    assert (lump.region, lump.loss_date, lump.unhealthy_days) == ("south", date(2015, 10, 26), 40)
    assert (lump.amount_cents, lump.source, lump.main_hazard) == (487_500, "haze_bonus", "haze")


def test_the_lump_sum_shows_with_the_payouts_and_in_the_run_and_portfolio(client, today):
    assert client.post("/api/buy", json=buy_body(add_haze_bonus=True)).status_code == 200
    backdate_to_2015(client)
    client.post("/api/auth/logout")
    register(client, "insurer", "desk@example.com")
    runs = {}
    for day in ("2015-10-25", "2015-10-26", "2015-10-27"):
        run = {"loss_date": day, "source": "nea_history"}
        runs[day] = client.post("/api/insurer/payout-runs", json=run).json()["counts"]
    assert [runs[day]["haze_bonus_held"] for day in runs] == [0, 1, 0]
    payouts = client.get("/api/payouts").json()
    assert [p["loss_date"] for p in payouts] == sorted((p["loss_date"] for p in payouts),
                                                        reverse=True)
    [lump] = [p for p in payouts if p["kind"] == "haze_bonus"]
    assert (lump["loss_date"], lump["amount_sgd"], lump["status"]) == ("2015-10-26", 4875, "held")
    assert lump["basis"]["haze"] == "40 days at PSI 101+ in the south region this policy year"
    assert lump["id"] == "haze_bonus-1" and lump["reference"].startswith("SDH-")
    assert {p["kind"] for p in payouts} == {"daily", "haze_bonus"}
    portfolio = client.get("/api/insurer/portfolio").json()["haze_bonus"]
    assert portfolio["lump_sums"] == {"held": {"count": 1, "amount_sgd": 4875}}
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "tan@example.test", "password": "test-pass-123"})
    mine = client.get("/api/payouts").json()
    assert [p["reference"] for p in mine if p["kind"] == "haze_bonus"] == [lump["reference"]]


def test_an_approval_from_may_to_october_starts_the_daily_cover_alone(client, today):
    body = buy_body(declined_before=True, declined_details="Declined in 2024", payment_method=None,
                    add_haze_bonus=True)
    application = client.post("/api/buy", json=body).json()["application"]
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    today(date(2026, 8, 10))
    decision = decide(client, application["id"], "approve", "Shelter fitted").json()
    assert decision["policy"]["tier"] == "tier_2" and decision["policy"]["haze_bonus"] is None
    assert decision["note"] == (
        "Shelter fitted The severe haze payout cannot be added from May to October; add it "
        "from November."
    )
    [policy] = client.get("/api/policies").json()
    assert policy["haze_bonus"] is None


def test_an_approval_in_a_sale_month_adds_the_add_on_asked_for(client, today):
    body = buy_body(declined_before=True, declined_details="Declined in 2024", payment_method=None,
                    add_haze_bonus=True)
    application = client.post("/api/buy", json=body).json()["application"]
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    decision = decide(client, application["id"], "approve").json()
    assert decision["policy"]["haze_bonus"]["lump_sum_sgd"] == 4875
    assert decision["note"] is None


def test_a_region_below_40_haze_days_is_never_paid(client, today):
    east = next(c for c in MAP_STATIC["hawker_centres"] if c["region"] == "east")
    response = client.post("/api/buy", json=buy_body(centre=east["name"], add_haze_bonus=True))
    assert response.status_code == 200, response.text
    backdate_to_2015(client)
    client.post("/api/auth/logout")
    assert replay_haze_season_2015(client) == []


def test_a_tariff_without_the_add_on_offers_none_and_prices_the_daily_cover_the_same(client):
    shown = centre_quote(client)
    body = default_tariff()
    body["haze_bonus"] = None
    saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    change = {"based_on_version": saved["version"], "tariff": body}
    assert client.put("/api/admin/tariff", json=change, auth=ADMIN).status_code == 200
    without = centre_quote(client)
    for with_add_on, daily_only in zip(shown["tiers"], without["tiers"], strict=True):
        assert daily_only["haze_bonus"] is None
        assert {**with_add_on, "haze_bonus": None} == daily_only
    response = client.post("/api/buy", json=buy_body(add_haze_bonus=True))
    assert response.status_code == 422
    assert response.json()["detail"] == "The severe haze payout is not offered"


def test_an_old_tariff_loads_without_the_block_and_startup_adds_it(tmp_path, monkeypatch):
    old = default_tariff()
    del old["haze_bonus"]
    assert Tariff.model_validate(old).haze_bonus is None
    database_url = f"sqlite:///{tmp_path / 'tariff.db'}"
    with store.connect(database_url).begin() as db:
        db.execute(insert(store.tariff_versions).values(
            saved_at=datetime.now(UTC), saved_by="admin", body=old
        ))
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    assert (saved["version"], saved["saved_by"]) == (2, "default: severe haze payout")
    assert saved["tariff"]["haze_bonus"] == default_tariff()["haze_bonus"]


def payout_account(client, mobile: str) -> None:
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": mobile, "sms_language": "en"}
    assert client.put("/api/payout-account", json=account).status_code == 200
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    assert client.post("/api/payout-account/verify", json={"code": code}).status_code == 200


def lump_sum_on_26_october_2015(client) -> dict:
    client.post("/api/auth/logout")
    register(client, "insurer", "desk@example.com")
    run = {"loss_date": "2015-10-26", "source": "nea_history"}
    assert client.post("/api/insurer/payout-runs", json=run).status_code == 200
    [lump] = [p for p in client.get("/api/payouts").json() if p["kind"] == "haze_bonus"]
    return lump


def owner_texts(client) -> list[dict]:
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "tan@example.test", "password": "test-pass-123"})
    return client.get("/api/sms").json()


def test_a_failed_lump_sum_can_be_retried_by_the_insurer(client, today):
    assert client.post("/api/buy", json=buy_body(add_haze_bonus=True)).status_code == 200
    backdate_to_2015(client)
    payout_account(client, FAILING_MOBILE)
    lump = lump_sum_on_26_october_2015(client)
    assert lump["status"] == "failed" and lump["failure_reason"]
    owner_texts(client)
    payout_account(client, GOOD_MOBILE)
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "desk@example.com", "password": "password1"})
    retried = client.post(f"/api/insurer/payouts/{lump['id']}/retry")
    assert retried.status_code == 200, retried.text
    paid = retried.json()
    assert (paid["status"], paid["amount_sgd"], paid["failure_reason"]) == ("paid", 4875, None)
    moves = [(e["from_status"], e["to_status"]) for e in paid["events"]]
    assert moves == [(None, "approved"), ("approved", "sending"), ("sending", "failed"),
                     ("failed", "approved"), ("approved", "sending"), ("sending", "paid")]
    assert client.post(f"/api/insurer/payouts/{lump['id']}/retry").status_code == 409
    kinds = [text["kind"] for text in owner_texts(client)]
    assert "haze_bonus_paid" in kinds and "payout_failed" in kinds


def test_a_held_lump_sum_can_be_rejected_by_the_insurer(client, today):
    assert client.post("/api/buy", json=buy_body(add_haze_bonus=True)).status_code == 200
    backdate_to_2015(client)
    lump = lump_sum_on_26_october_2015(client)
    assert lump["status"] == "held"
    rejected = client.post(
        f"/api/insurer/payouts/{lump['id']}/reject", json={"reason": "Policy under review"}
    ).json()
    assert (rejected["status"], rejected["failure_reason"]) == ("rejected", "Policy under review")
    assert rejected["events"][-1]["actor"] == "desk@example.com"
    again = client.post(f"/api/insurer/payouts/{lump['id']}/reject", json={"reason": "Again"})
    assert again.status_code == 409
    assert client.post("/api/insurer/payouts/haze_bonus-99/retry").status_code == 404
