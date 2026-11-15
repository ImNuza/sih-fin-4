from __future__ import annotations

import pytest

from tests.test_api import MAXWELL, buy_body, client, shop_body  # noqa: F401
from tests.test_underwriting import sign_in_as_insurer

COOKED_FOOD_AT_MAXWELL = {"product": "cooked_food", "centre": MAXWELL}
PROVISION_SHOP = {"product": "packaged_food", "postcode": "380123"}
TIERS = ["tier_1", "tier_2", "tier_3", "tier_4"]


def quote(client, daily_sales_sgd: float | None = None, **place) -> dict:
    body = {**place, "daily_sales_sgd": daily_sales_sgd}
    response = client.post("/api/quote", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def offered(priced: dict) -> list[str]:
    return [t["tier"] for t in priced["tiers"] if t["offered"]]


@pytest.mark.parametrize("place, sales, suggested", [
    (COOKED_FOOD_AT_MAXWELL, 150, "tier_1"),
    (COOKED_FOOD_AT_MAXWELL, 500, "tier_2"),
    (COOKED_FOOD_AT_MAXWELL, 1500, "tier_4"),
    (PROVISION_SHOP, 2000, "tier_2"),
])
def test_the_suggestion_is_the_biggest_tier_at_or_below_a_day_with_no_sales(
    client, place, sales, suggested
):
    priced = quote(client, sales, **place)
    assert priced["suggested_tier"] == suggested
    assert offered(priced) == TIERS[: TIERS.index(suggested) + 1]
    for tier in priced["tiers"]:
        assert tier["fits_business"] == (tier["tier"] in offered(priced))


def test_a_drinks_stall_selling_150_a_day_is_offered_tier_1_only(client):
    priced = quote(client, 150, **COOKED_FOOD_AT_MAXWELL)
    assert priced["full_loss_day_sgd"] == 150
    tier_3 = next(t for t in priced["tiers"] if t["tier"] == "tier_3")
    assert tier_3["not_offered_reason"] == (
        "Tier 3 pays S$630 for a day with no sales, more than this business loses on such a day "
        "(about S$150)"
    )


def test_a_provision_shop_loses_about_a_ninth_of_its_sales(client):
    priced = quote(client, 2000, **PROVISION_SHOP)
    assert 215 <= priced["full_loss_day_sgd"] <= 230
    assert priced["suggestion"].startswith("Suggested for your sales: Tier 2")


def test_without_daily_sales_every_tier_the_place_allows_is_shown_and_none_suggested(client):
    priced = quote(client, **COOKED_FOOD_AT_MAXWELL)
    assert offered(priced) == TIERS
    assert priced["suggested_tier"] is None and priced["full_loss_day_sgd"] is None
    assert [t["fits_business"] for t in priced["tiers"]] == [None] * 4
    assert priced["suggestion"] == "Tell us your normal daily sales to see which tier fits."


def test_a_business_that_loses_less_than_tier_1_pays_is_offered_nothing(client):
    priced = quote(client, 300, **PROVISION_SHOP)
    assert offered(priced) == [] and priced["suggested_tier"] is None
    assert priced["suggestion"] == (
        "Payung's smallest tier pays more than this business loses on a bad day."
    )


def test_daily_sales_must_be_sensible(client):
    for sales in (19, 50_001):
        body = {**COOKED_FOOD_AT_MAXWELL, "daily_sales_sgd": sales}
        assert client.post("/api/quote", json=body).status_code == 422


def test_buying_a_tier_above_the_loss_is_refused_before_anything_is_saved(client):
    response = client.post("/api/buy", json=buy_body(daily_sales_sgd=500, tier="tier_3"))
    assert response.status_code == 409
    assert response.json()["detail"].startswith("Tier 3 pays S$630 for a day with no sales")
    login = {"email": buy_body()["email"], "password": buy_body()["password"]}
    assert client.post("/api/auth/login", json=login).status_code == 401


def test_a_shop_cannot_buy_more_than_its_sales_lose(client):
    response = client.post("/api/buy", json=shop_body(postcode="380123", tier="tier_3"))
    assert response.status_code == 409
    assert client.post("/api/buy", json=shop_body(postcode="380123")).status_code == 200


def test_hawkers_and_shops_must_declare_their_daily_sales(client):
    for body in (buy_body(daily_sales_sgd=None), shop_body(daily_sales_sgd=None)):
        response = client.post("/api/buy", json=body)
        assert response.status_code == 422
        assert "normal sales on a weekday" in response.text


def test_the_dashboard_refuses_a_tier_above_the_declared_sales(client):
    assert client.post("/api/buy", json=buy_body(daily_sales_sgd=500)).status_code == 200
    response = client.post("/api/policies", json={"tier": "tier_4"})
    assert response.status_code == 409
    assert "more than this business loses" in response.json()["detail"]
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 200


def test_the_declared_sales_show_to_the_owner_and_the_insurer(client):
    assert client.post("/api/buy", json=buy_body(daily_sales_sgd=500)).json()[
        "application"]["daily_sales_sgd"] == 500
    assert client.get("/api/applications/mine").json()["daily_sales_sgd"] == 500
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    [policy] = client.get("/api/insurer/policies").json()
    assert policy["daily_sales_sgd"] == 500
