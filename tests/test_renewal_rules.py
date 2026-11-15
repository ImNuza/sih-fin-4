"""Renewal and lapse rules: a customer cannot buy a high tier, collect, lapse and come back."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from api import payout_flow
from tests.test_api import SELLER
from tests.test_payout_api import (  # noqa: F401  (client is a fixture)
    FLOOD_DAY,
    LONG_AGO,
    client,
    register,
    sign_in,
    stallholder_with_cover,
    start_cover_on,
)

STALLHOLDER = "tan@example.com"
FIRST_CAPPED_DAY = date(2026, 9, 1)


def yesterday() -> str:
    return (datetime.now(payout_flow.SINGAPORE).date() - timedelta(days=1)).isoformat()


def run_day(client, loss_date: str) -> dict:
    register_desk_once(client)
    response = client.post("/api/insurer/payout-runs", json={**FLOOD_DAY, "loss_date": loss_date})
    assert response.status_code == 200, response.text
    sign_in(client, STALLHOLDER)
    return response.json()["counts"]


def register_desk_once(client) -> None:
    login = {"email": "desk@example.com", "password": "password1"}
    if client.post("/api/auth/login", json=login).status_code != 200:
        register(client, "insurer", "desk@example.com")


def own_policy(client) -> dict:
    [policy] = client.get("/api/policies").json()
    return policy


def cancel_cover(client) -> None:
    assert client.delete(f"/api/policies/{own_policy(client)['id']}").status_code == 200


def change_tier(client, tier: str) -> None:
    assert client.post("/api/policies", json={"tier": tier, **SELLER}).status_code == 200


def test_a_higher_tier_starts_a_new_waiting_period_for_the_whole_cover(client):
    stallholder_with_cover(client)
    change_tier(client, "tier_2")
    assert run_day(client, yesterday())["waiting_period"] == 1


def test_a_lower_tier_keeps_the_cover_start_and_pays_the_lower_amount(client):
    stallholder_with_cover(client)
    change_tier(client, "tier_2")
    start_cover_on(client, LONG_AGO)
    change_tier(client, "tier_1")
    assert run_day(client, yesterday())["paid"] == 1
    [payout] = client.get("/api/payouts").json()
    assert payout["amount_sgd"] == own_policy(client)["daily_payout_sgd"]


def test_buying_again_after_a_lapse_starts_a_new_waiting_period(client):
    stallholder_with_cover(client)
    cancel_cover(client)
    change_tier(client, "tier_1")
    assert run_day(client, yesterday())["waiting_period"] == 1


def test_the_yearly_cap_counts_payouts_made_before_a_lapse(client):
    stallholder_with_cover(client)
    max_days = own_policy(client)["max_paid_days_per_year"]
    for day in range(max_days):
        run_day(client, (FIRST_CAPPED_DAY + timedelta(days=day)).isoformat())
    cancel_cover(client)
    change_tier(client, "tier_1")
    start_cover_on(client, LONG_AGO)
    assert run_day(client, "2026-10-31")["capped"] == 1


def test_a_lapsed_cover_is_not_paid(client):
    stallholder_with_cover(client)
    cancel_cover(client)
    counts = run_day(client, yesterday())
    assert sum(counts.values()) == 0
    assert client.get("/api/payouts").json() == []


def test_payouts_already_made_are_kept_after_a_tier_change_and_a_lapse(client):
    stallholder_with_cover(client)
    run_day(client, "2026-10-01")
    [before] = client.get("/api/payouts").json()
    change_tier(client, "tier_3")
    cancel_cover(client)
    assert client.get("/api/payouts").json() == [before]
    assert before["status"] == "paid" and before["amount_sgd"] > 0


def test_the_buy_page_gets_the_rule_numbers_from_the_server(client):
    options = client.get("/api/buy/options").json()
    assert options["waiting_period_days"] == payout_flow.WAITING_PERIOD_DAYS
    assert options["cap_window_days"] == payout_flow.CAP_WINDOW_DAYS
