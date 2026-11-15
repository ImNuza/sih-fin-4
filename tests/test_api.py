from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, update

from api import burn, calculator, onboarding, postcodes, readings, store
from api.accounts import application_profile
from api.main import DEFAULT_TARIFF_PATH, MAP_STATIC_PATH, SINGAPORE, add_months, app
from api.paynow_qr import crc16_ccitt, paynow_payload

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
        "business_class": "hawker",
        "sold_by": "adviser",
        "adviser_code": "demo1234",
        "licence_no": "DEMO/12345",
        "staff_band": "1-4",
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
        "payment_method": "giro",
        "stall_unit": "01-23",
        "designation": "Owner",
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
        {"cover_start": "2020-01-01"},
        {"email": ""},
        {"licence_no": None},
        {"licence_no": "AB"},
        {"staff_band": None},
        {"term_months": 6},
        {"product": "platform_work"},
        {"sold_by": None},
        {"sold_by": "direct"},
        {"adviser_code": None},
        {"adviser_code": "A1"},
        {"sold_by": "association", "association": ""},
    ],
)
def test_buy_rejects_incomplete_applications(client, changes):
    assert client.post("/api/buy", json=buy_body(**changes)).status_code == 422


def test_an_adviser_sale_keeps_the_adviser_code(client):
    application = client.post("/api/buy", json=buy_body(association="Ignored")).json()["application"]
    assert (application["sold_by"], application["adviser_code"]) == ("adviser", "DEMO1234")
    assert application["association"] is None
    assert client.get("/api/applications/mine").json()["adviser_code"] == "DEMO1234"


def test_an_association_sale_keeps_the_association_and_shows_on_the_insurer_desk(client):
    body = buy_body(sold_by="association", association="  Test Hawkers' Association ")
    application = client.post("/api/buy", json=body).json()["application"]
    assert (application["sold_by"], application["adviser_code"]) == ("association", None)
    assert application["association"] == "Test Hawkers' Association"
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={
        "role": "insurer", "name": "Desk", "email": "desk@example.test",
        "password": "insurer-pass-1", "insurer": "Income Insurance",
    })
    [policy] = client.get("/api/insurer/policies").json()
    assert (policy["sold_by"], policy["association"]) == ("association", "Test Hawkers' Association")


def test_buy_options_name_the_two_channels(client):
    options = client.get("/api/buy/options").json()
    assert set(options["sold_by"]) == {"adviser", "association"}
    assert options["associations"]


def test_company_uen_is_stored_in_capitals(client):
    result = client.post("/api/buy", json=buy_body(applicant_type="company", uen="201912345k")).json()
    assert result["application"]["uen"] == "201912345K"


def test_a_place_is_priced_from_its_nearest_stations(client):
    maxwell_food_centre = {"latitude": 1.28033, "longitude": 103.84475}
    body = {"product": "cooked_food", **maxwell_food_centre}
    quote = client.post("/api/quote", json=body).json()
    assert quote["region"] in {"central", "south"}
    by_hazard = {risk["hazard"]: risk for risk in quote["local_risks"]}
    assert set(by_hazard) == {"haze", "rain", "heat"}
    assert len(by_hazard["rain"]["stations"]) == 3
    assert all(0 <= risk["credibility"] <= 1 for risk in by_hazard.values())
    assert quote["tiers"][0]["weekly_premium_sgd"] > 0


@pytest.mark.parametrize(
    "where",
    [
        {},
        {"region": "east", "latitude": 1.3, "longitude": 103.9},
        {"latitude": 1.3},
        {"region": "south", "centre": "Maxwell Food Centre (Kim Hua Market)"},
        {"centre": "Maxwell Food Centre (Kim Hua Market)", "postcode": "560123"},
    ],
)
def test_a_quote_needs_exactly_one_place(client, where):
    response = client.post("/api/quote", json={"product": "cooked_food", **where})
    assert response.status_code == 422


MAXWELL = "Maxwell Food Centre (Kim Hua Market)"


def weekly(quote: dict, tier: str = "tier_2") -> float:
    return next(t for t in quote["tiers"] if t["tier"] == tier)["weekly_premium_sgd"]


def centre_point(client, name: str) -> dict:
    centres = client.get("/api/map/static").json()["hawker_centres"]
    centre = next(c for c in centres if c["name"] == name)
    return {"latitude": centre["lat"], "longitude": centre["lng"]}


def test_a_centre_is_priced_at_its_nearest_stations_not_its_region(client):
    by_centre = client.post("/api/quote", json={"product": "cooked_food", "centre": MAXWELL}).json()
    point = centre_point(client, MAXWELL)
    at_point = client.post("/api/quote", json={"product": "cooked_food", **point}).json()
    by_region = client.post("/api/quote", json={"product": "cooked_food", "region": "south"}).json()
    assert by_centre == at_point
    assert weekly(by_centre) != weekly(by_region)


def test_an_unknown_centre_is_404_and_an_unknown_sector_is_422(client):
    unknown = client.post("/api/quote", json={"product": "cooked_food", "centre": "Nowhere Market"})
    assert unknown.status_code == 404
    bad_sector = client.post("/api/quote", json={"product": "cooked_food", "postcode": "990123"})
    assert bad_sector.status_code == 422


def test_a_hawker_is_charged_the_price_shown_for_its_centre(client):
    shown = client.post("/api/quote", json={"product": "cooked_food", "centre": MAXWELL}).json()
    policy = client.post("/api/buy", json=buy_body()).json()["policy"]
    assert policy["weekly_premium_sgd"] == weekly(shown)


SHOP_QUOTE = {"product": "packaged_food", "postcode": "560123"}


def test_a_shop_is_charged_the_price_shown_for_its_postcode(client):
    shown = client.post("/api/quote", json=SHOP_QUOTE).json()
    by_region = client.post("/api/quote", json={"product": "packaged_food", "region": "north"})
    policy = client.post("/api/buy", json=shop_body()).json()["policy"]
    assert policy["weekly_premium_sgd"] == weekly(shown) != weekly(by_region.json())
    again = client.post("/api/policies", json={"tier": "tier_2"}).json()
    assert again["weekly_premium_sgd"] == weekly(shown)


def test_a_platform_worker_is_charged_the_region_price(client, riders_open):
    region = client.post("/api/buy", json=platform_worker_body()).json()["application"]
    shown = client.post("/api/quote", json={"product": "platform_work", "region": "north"}).json()
    policy = client.get("/api/policies").json()[0]
    assert policy["region"] == "north" and region["postcode"] == "730123"
    assert policy["weekly_premium_sgd"] == weekly(shown)


def test_buying_again_from_the_dashboard_keeps_the_centre_price(client):
    first = client.post("/api/buy", json=buy_body()).json()["policy"]
    again = client.post("/api/policies", json={"tier": "tier_2"}).json()
    assert again["weekly_premium_sgd"] == first["weekly_premium_sgd"]


def test_the_map_prices_every_centre_as_its_stalls_are_charged(client):
    quotes = client.get("/api/map/quotes").json()
    centres = client.get("/api/map/static").json()["hawker_centres"]
    assert set(quotes["centres"]) == {c["name"] for c in centres}
    shown = client.post("/api/quote", json={"product": "cooked_food", "centre": MAXWELL}).json()
    assert quotes["centres"][MAXWELL] == shown
    parts = quotes["centre_loss_day_parts"][MAXWELL]
    assert abs(sum(parts.values()) - shown["expected_loss_days"]) < 0.02


def test_the_what_if_circle_prices_each_centre_from_its_own_stations(client):
    point = centre_point(client, MAXWELL)
    body = {"lat": point["latitude"], "lng": point["longitude"], "radius_km": 0.3,
            "readings": {"haze": 230}, "product": "cooked_food", "tier": "tier_2"}
    scenario = client.post("/api/map/scenario", json=body).json()
    shown = client.post("/api/quote", json={"product": "cooked_food", "centre": MAXWELL}).json()
    assert scenario["centres"][MAXWELL]["weekly_baseline_sgd"] == weekly(shown)
    assert scenario["centres"][MAXWELL]["weekly_stressed_sgd"] > weekly(shown)


def test_a_tariff_saved_in_the_old_shape_is_replaced_by_the_default(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'tariff.db'}"
    old = default_tariff()
    old["pricing"]["recovered_share"] = 0.5
    for product in old["products"]:
        for field in ("gross_margin", "recovered_share", "source"):
            del product[field]
    old_row = insert(store.tariff_versions).values(
        saved_at=datetime.now(UTC), saved_by="admin", body=old
    )
    with store.connect(database_url).begin() as db:
        db.execute(old_row)
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    assert (saved["version"], saved["saved_by"]) == (2, "default")


def test_a_saved_tariff_gains_products_added_to_the_default(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'tariff.db'}"
    old = default_tariff()
    old["products"] = [p for p in old["products"] if p["key"] != "platform_work"]
    old["products"][0]["gross_margin"] = 0.5
    with store.connect(database_url).begin() as db:
        db.execute(insert(store.tariff_versions).values(
            saved_at=datetime.now(UTC), saved_by="admin", body=old
        ))
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        saved = client.get("/api/admin/tariff", auth=ADMIN).json()
        quote = client.post("/api/quote", json={"region": "central", "product": "platform_work"})
    assert (saved["version"], saved["saved_by"]) == (2, "default: new products")
    assert saved["tariff"]["products"][0]["gross_margin"] == 0.5
    assert quote.status_code == 200


def test_buy_keeps_the_new_details_and_defaults_cover_to_today(client):
    result = client.post("/api/buy", json=buy_body()).json()
    application = result["application"]
    assert (application["stall_unit"], application["designation"]) == ("01-23", "Owner")
    assert application["cover_start"] == datetime.now(SINGAPORE).date().isoformat()
    assert client.get("/api/applications/mine").json()["stall_unit"] == "01-23"


def test_cover_can_start_later_and_the_policy_starts_then(client):
    later = (datetime.now(SINGAPORE).date() + timedelta(days=7)).isoformat()
    result = client.post("/api/buy", json=buy_body(cover_start=later)).json()
    assert result["policy"]["started_at"].startswith(later)


def test_demo_email_and_password_need_only_be_present(client):
    body = buy_body(email="not-an-email", password="x")
    assert client.post("/api/buy", json=body).status_code == 200
    assert client.post("/api/buy", json=body).status_code == 409


def shop_body(**changes) -> dict:
    shop = {
        "business_class": "shop",
        "centre": None,
        "stall_unit": None,
        "licence_no": None,
        "postcode": "560123",
        "ssic_code": "47102",
        "business_name": "Ah Kow Minimart",
        "product": "packaged_food",
        "staff_band": "5-9",
    }
    return buy_body(**{**shop, **changes})


def platform_worker_body(**changes) -> dict:
    worker = {
        "business_class": "platform_worker",
        "centre": None,
        "stall_unit": None,
        "licence_no": None,
        "business_name": None,
        "designation": None,
        "staff_band": None,
        "platform": "Grab",
        "platform_worker_id": "DEMO-RIDER-0042",
        "postcode": "730123",
        "product": "platform_work",
    }
    return buy_body(**{**worker, **changes})


PROFILE_FIELDS = {
    "business_class", "licence_no", "ssic_code", "platform", "platform_worker_id", "postcode",
    "staff_band", "term_months", "waiting_ends", "cover_ends",
}


def test_a_hawker_needs_no_uen_and_takes_the_centre_postcode(client):
    result = client.post("/api/buy", json=buy_body()).json()
    application = result["application"]
    assert (application["business_class"], application["uen"]) == ("hawker", None)
    assert (application["licence_no"], application["postcode"]) == ("DEMO/12345", "069184")
    mine = client.get("/api/applications/mine").json()
    assert PROFILE_FIELDS <= set(mine)
    assert mine["licence_no"] == "DEMO/12345"


def test_a_shop_is_placed_by_its_postcode_and_has_no_centre(client):
    result = client.post("/api/buy", json=shop_body()).json()
    assert result["application"]["ssic_code"] == "47102"
    assert result["policy"]["region"] == "central"
    me = client.get("/api/auth/me").json()
    assert (me["centre"], me["region"]) == (None, "central")
    assert client.get("/api/applications/mine").json()["postcode"] == "560123"


def test_a_platform_worker_is_an_individual_covered_for_platform_work(client, riders_open):
    result = client.post("/api/buy", json=platform_worker_body()).json()
    application = result["application"]
    assert (application["platform"], application["platform_worker_id"]) == (
        "Grab", "DEMO-RIDER-0042"
    )
    assert application["staff_band"] == "1-4"
    assert result["policy"]["product"] == "platform_work"
    me = client.get("/api/auth/me").json()
    assert (me["centre"], me["region"]) == (None, "north")


@pytest.mark.parametrize(
    "body",
    [
        platform_worker_body(applicant_type="company", uen="201912345K"),
        platform_worker_body(platform="Uber"),
        platform_worker_body(platform_worker_id="ab"),
        platform_worker_body(postcode=None),
        platform_worker_body(product="cooked_food"),
        shop_body(ssic_code="4710"),
        shop_body(postcode="12345"),
    ],
)
def test_each_class_must_give_its_own_details(client, riders_open, body):
    assert client.post("/api/buy", json=body).status_code == 422


def test_the_pilot_refuses_platform_workers_and_says_they_come_next(client):
    response = client.post("/api/buy", json=platform_worker_body())
    assert response.status_code == 422
    assert "next phase" in response.text
    options = client.get("/api/buy/options").json()
    assert options["open_classes"] == ["hawker", "shop"]


def test_an_unknown_postal_sector_is_refused(client):
    response = client.post("/api/buy", json=shop_body(postcode="990123"))
    assert response.status_code == 422
    assert "Postal sector 99 is not a Singapore postal sector" in response.text


def test_a_business_over_200_workers_must_have_sales_under_100_million(client):
    big = shop_body(staff_band="over-200", sales_under_100m=False)
    response = client.post("/api/buy", json=big)
    assert response.status_code == 422
    assert "SafeDay is for small and medium enterprises" in response.text
    assert client.post("/api/buy", json=shop_body(staff_band="over-200")).status_code == 422
    assert client.post("/api/buy", json={**big, "sales_under_100m": True}).status_code == 200


def test_job_title_and_stall_unit_are_optional(client):
    body = buy_body(designation=None, stall_unit=None)
    assert client.post("/api/buy", json=body).status_code == 200


def test_payouts_wait_30_days_and_the_term_sets_the_end(client):
    start = datetime.now(SINGAPORE).date() + timedelta(days=7)
    body = buy_body(cover_start=start.isoformat(), term_months=24)
    application = client.post("/api/buy", json=body).json()["application"]
    assert application["waiting_ends"] == (start + timedelta(days=30)).isoformat()
    assert application["cover_ends"] == add_months(start, 24).isoformat()
    assert client.get("/api/applications/mine").json()["term_months"] == 24


def test_a_term_defaults_to_12_months_at_the_same_weekly_price(client):
    one_year = client.post("/api/buy", json=buy_body()).json()
    two_years = client.post("/api/buy", json=buy_body(email="b@example.test", term_months=24)).json()
    assert one_year["application"]["term_months"] == 12
    assert one_year["policy"]["weekly_premium_sgd"] == two_years["policy"]["weekly_premium_sgd"]


@pytest.mark.parametrize(
    "start, months, end",
    [(date(2026, 11, 15), 12, date(2027, 11, 15)), (date(2028, 2, 29), 12, date(2029, 2, 28)),
     (date(2026, 12, 31), 24, date(2028, 12, 31))],
)
def test_add_months_keeps_the_day_or_takes_the_month_end(start, months, end):
    assert add_months(start, months) == end


def test_platform_work_quotes_and_assesses_without_stock(client):
    quote = client.post("/api/quote", json={"region": "east", "product": "platform_work"}).json()
    assert quote["tiers"][0]["weekly_premium_sgd"] > 0
    body = {"product": "platform_work", "tier": "tier_1", "readings": {"rain": 50}}
    day = client.post("/api/assess", json=body).json()
    # rain weight 0.5 x severity 1.0 x (demand 0.6 x margin 0.7, nothing recovered, nothing spoils)
    assert day["loss_percent"] == 21.0
    assert day["payout_sgd"] == 4.2


def test_crc_matches_the_ccitt_false_check_value():
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_paynow_payload_pays_the_demo_proxy_a_fixed_amount():
    payload = paynow_payload(12.3, "DEMO-ABC123")
    assert "0009SG.PAYNOW" in payload and "0212SAFEDAY-DEMO" in payload
    assert "540512.30" in payload and "03010" in payload and "0111DEMO-ABC123" in payload
    assert int(payload[-4:], 16) == crc16_ccitt(payload[:-4].encode())


def test_paynow_qr_is_an_svg_and_checks_its_inputs(client):
    query = {"amount_sgd": 3.15, "reference": "DEMO-ABC123"}
    response = client.get("/api/paynow/qr", params=query)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.text.startswith("<svg")
    assert client.get("/api/paynow/qr", params={**query, "reference": "x"}).status_code == 422
    assert client.get("/api/paynow/qr", params={**query, "amount_sgd": 0}).status_code == 422


def test_buy_options_list_each_class_and_every_postal_sector(client):
    options = client.get("/api/buy/options").json()
    assert options["business_classes"] == ["hawker", "shop", "platform_worker"]
    minimart = {"code": "47102", "title": "Mini-marts, convenience stores and provision shops"}
    assert minimart in options["ssic_codes"]
    assert options["postal_sector_regions"]["56"] == "central"
    assert len(options["postal_sector_regions"]) == 81


MAP_STATIC = json.loads(MAP_STATIC_PATH.read_text())
CENTRES_BY_SECTOR = postcodes.centres_by_sector(MAP_STATIC["hawker_centres"])


def centres_in(*sectors: str) -> list[dict]:
    def sector(centre: dict) -> str | None:
        match = postcodes.ADDRESS_POSTCODE.search(centre["address"])
        return match.group(1)[:2] if match else None

    return [centre for centre in MAP_STATIC["hawker_centres"] if sector(centre) in sectors]


def area(postcode: str) -> dict:
    return postcodes.area_point(postcode, CENTRES_BY_SECTOR, MAP_STATIC["region_points"])


def test_a_postcode_sits_at_the_mean_of_its_sectors_hawker_centres():
    centres = centres_in("56")
    point = area("561965")
    assert (point["basis"], point["region"], len(centres)) == ("postal sector 56", "central", 8)
    assert point["lat"] == pytest.approx(sum(c["lat"] for c in centres) / 8, abs=1e-5)
    assert point["lng"] == pytest.approx(sum(c["lng"] for c in centres) / 8, abs=1e-5)


def test_a_sector_without_a_centre_falls_back_to_its_district():
    centres = centres_in("53", "54", "55", "82")
    point = area("540123")
    assert point["basis"] == "postal district 19"
    assert point["lat"] == pytest.approx(sum(c["lat"] for c in centres) / len(centres), abs=1e-5)


def test_a_district_without_a_centre_falls_back_to_its_region_point():
    point = area("730123")
    assert (point["basis"], point["region"]) == ("middle of the north region", "north")
    assert [point["lat"], point["lng"]] == MAP_STATIC["region_points"]["north"]


def test_only_priced_stations_are_marked_missing_and_value_rows_skip_dry_and_cool_days(client):
    table = burn.load_day_table()
    for hazard in ("rain", "heat"):
        priced = {site.key for site in client.app.state.sites[hazard]}
        marked = {station for day in table.values() for station in day.get(f"{hazard}_missing", {})}
        assert marked and marked <= priced
    rain = [mm for day in table.values() for mm in day.get("rain", {}).values()]
    heat = [hours for day in table.values() for hours in day.get("heat", {}).values()]
    assert min(rain) >= 1.0 and min(heat) > 0


def test_burn_at_a_centre_reads_each_day_as_a_payout_would(client):
    replay = client.get("/api/map/burn", params={"centre": MAXWELL}).json()
    centre = next(c for c in MAP_STATIC["hawker_centres"] if c["name"] == MAXWELL)
    sites = client.app.state.sites
    where = readings.history_place(centre["region"], centre["lat"], centre["lng"], sites)
    tariff = store.latest(client.app.state.db).tariff
    shown = client.post("/api/quote", json={"product": "cooked_food", "centre": MAXWELL}).json()
    yearly = next(t["yearly_premium_sgd"] for t in shown["tiers"] if t["tier"] == "tier_2")
    expected = burn.site_burn(
        burn.load_day_table(), where, tariff, "cooked_food", "tier_2", 500.0, yearly
    )
    assert replay["years"] == expected["years"]


def test_burn_loss_ratio_is_over_the_premium_before_gst(client):
    replay = client.get("/api/map/burn", params={"centre": MAXWELL}).json()
    gst = 1 + store.latest(client.app.state.db).tariff.pricing.gst_rate
    for year in replay["years"]:
        before_gst = year["premium_sgd"] / gst
        assert year["loss_ratio"] == pytest.approx(year["paid_sgd"] / before_gst, abs=0.001)


def test_burn_replays_ten_years_at_a_point(client):
    point = area("561965")
    query = {
        "lat": point["lat"], "lng": point["lng"], "region": point["region"],
        "product": "packaged_food", "tier": "tier_2",
    }
    replay = client.get("/api/map/burn", params=query).json()
    assert (replay["centre"], replay["region"], replay["lat"]) == (None, "central", point["lat"])
    assert replay["years"][0]["year"] == 2017 and len(replay["years"]) >= 10
    priced = client.post("/api/quote", json={
        "latitude": point["lat"], "longitude": point["lng"], "product": "packaged_food",
    }).json()
    weekly = next(t["weekly_premium_sgd"] for t in priced["tiers"] if t["tier"] == "tier_2")
    assert replay["weekly_premium_sgd"] == weekly


def test_burn_needs_a_centre_or_a_whole_point(client):
    assert client.get("/api/map/burn", params={"lat": 1.35, "lng": 103.85}).status_code == 422
    query = {"lat": 1.35, "lng": 103.85, "region": "middle"}
    assert client.get("/api/map/burn", params=query).status_code == 404


class StubFeed:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot

    def ensure_started(self) -> None:
        pass

    def read(self) -> dict:
        return self.snapshot


LIVE_SNAPSHOT = {
    "available": True,
    "status": "ok",
    "fetched_at": "2026-11-15T12:00:00+08:00",
    "haze": {"central": {"max_today": 150.0}},
    "rain": [{"id": "S1", "lat": 1.37, "lng": 103.85, "wettest_work_hour_today": 25.0,
              "reporting": True}],
    "heat": [{"id": "H1", "lat": 1.37, "lng": 103.85, "hours_ge_32_today": 0.0}],
    "flood_alerts": [],
}


def test_live_at_a_point_scores_it_as_the_live_feed_scores_a_centre(client):
    client.app.state.live = StubFeed(LIVE_SNAPSHOT)
    index, centre = next(
        (i, c) for i, c in enumerate(MAP_STATIC["hawker_centres"]) if c["region"] == "central"
    )
    query = {"lat": centre["lat"], "lng": centre["lng"], "region": "central"}
    today = client.get("/api/map/live/at", params=query).json()
    assert today["loss_percent"] > 0
    assert today["readings"] == {"haze": 150.0, "rain": 25.0, "heat": 0.0}
    assert today["fetched_at"] == LIVE_SNAPSHOT["fetched_at"]
    every_centre = client.get("/api/map/live").json()["hawker_losses"]
    assert {k: today[k] for k in ("loss_percent", "readings")} == every_centre[index]


def test_live_rain_is_the_middle_of_the_3_nearest_gauges_that_reported(client):
    def gauge(gauge_id: str, lat: float, mm: float, reporting: bool = True) -> dict:
        return {
            "id": gauge_id, "lat": lat, "lng": 103.85, "wettest_work_hour_today": mm,
            "reporting": reporting,
        }

    gauges = [
        gauge("dead", 1.3500, 0.0, reporting=False),
        gauge("a", 1.3501, 40.0),
        gauge("b", 1.3502, 10.0),
        gauge("c", 1.3503, 30.0),
        gauge("d", 1.3600, 90.0),
    ]
    client.app.state.live = StubFeed({**LIVE_SNAPSHOT, "rain": gauges})
    query = {"lat": 1.35, "lng": 103.85, "region": "central"}
    assert client.get("/api/map/live/at", params=query).json()["readings"]["rain"] == 30.0


def test_live_scores_the_customers_own_product(client):
    client.app.state.live = StubFeed(LIVE_SNAPSHOT)
    cooked = client.get("/api/map/live", params={"product": "cooked_food"}).json()["hawker_losses"]
    goods = client.get("/api/map/live", params={"product": "general_goods"}).json()["hawker_losses"]
    assert goods[0]["loss_percent"] < cooked[0]["loss_percent"]


def test_a_replayed_day_scores_every_centre_on_its_own_readings(client):
    day = client.get("/api/map/day", params={"date": "2026-10-15"}).json()
    assert len(day["hawker_losses"]) == len(MAP_STATIC["hawker_centres"])
    table = burn.load_day_table()["2026-10-15"]
    tariff = store.latest(client.app.state.db).tariff
    sites = client.app.state.sites
    for place, loss in zip(MAP_STATIC["hawker_centres"], day["hawker_losses"]):
        where = readings.history_place(place["region"], place["lat"], place["lng"], sites)
        assert loss["readings"] == readings.day_readings_at(table, where, 3)
        assert loss["loss_percent"] == calculator.assess(
            tariff, "cooked_food", "tier_1", loss["readings"]
        ).loss_percent
    rains = {loss["readings"]["rain"] for loss in day["hawker_losses"]}
    assert len(rains) > 1 and max(rains) <= day["rain"]["value"]


def test_live_at_a_point_waits_for_the_feed(client):
    client.app.state.live = StubFeed({"available": False, "status": "starting"})
    query = {"lat": 1.35, "lng": 103.85, "region": "central"}
    assert client.get("/api/map/live/at", params=query).json() == {
        "available": False, "status": "starting"
    }


def test_a_shops_application_carries_its_area_point(client):
    client.post("/api/buy", json=shop_body(postcode="561965"))
    mine = client.get("/api/applications/mine").json()
    point = area("561965")
    assert (mine["area_lat"], mine["area_lng"]) == (point["lat"], point["lng"])
    assert mine["area_basis"] == "postal sector 56"


def test_a_place_quote_explains_its_loss_days_and_premium(client):
    body = {"product": "cooked_food", "latitude": 1.28033, "longitude": 103.84475}
    quote = client.post("/api/quote", json=body).json()
    assert sum(quote["loss_day_parts"].values()) == pytest.approx(
        quote["expected_loss_days"], abs=0.05)
    tier = quote["tiers"][0]
    total = sum(step["amount_sgd"] for step in tier["build_up"])
    assert round(total, 2) == tier["yearly_premium_sgd"]


def test_options_give_each_hazards_first_trigger_level(client):
    hazards = {h["key"]: h for h in client.get("/api/options").json()["hazards"]}
    assert (hazards["haze"]["first_band"], hazards["rain"]["first_band"]) == (101, 20)
    assert hazards["heat"]["first_band"] == 2


def test_a_shop_is_priced_on_the_haze_of_the_region_it_is_paid_on(client):
    postcode = "380123"
    shown = client.post("/api/quote", json={"product": "packaged_food", "postcode": postcode})
    shown = shown.json()
    region = postcodes.region_of(postcode)
    haze = next(risk for risk in shown["local_risks"] if risk["hazard"] == "haze")
    tariff = store.latest(client.app.state.db).tariff
    product = calculator.find(tariff.products, "packaged_food", "product")
    region_haze = calculator.loss_day_parts(tariff, product, client.app.state.history[region])
    assert (shown["region"], haze["stations"]) == (region, [region]) == ("east", ["east"])
    assert haze["loss_days"] == round(region_haze["haze"], 2)
    policy = client.post("/api/buy", json=shop_body(postcode=postcode)).json()["policy"]
    assert (policy["region"], policy["weekly_premium_sgd"]) == (region, weekly(shown))


def test_a_hawker_centre_keeps_its_price(client):
    shown = client.post("/api/quote", json={"product": "cooked_food", "centre": MAXWELL}).json()
    assert weekly(shown) == 9.27
    for risk in shown["local_risks"]:
        assert shown["loss_day_parts"][risk["hazard"]] == risk["loss_days"]


def end_term_on(client, cover_ends: date) -> None:
    with client.app.state.db.begin() as db:
        db.execute(update(application_profile).values(cover_ends=cover_ends))


def test_buying_again_after_the_term_ended_is_refused(client):
    client.post("/api/buy", json=buy_body())
    today = datetime.now(SINGAPORE).date()
    end_term_on(client, today)
    response = client.post("/api/policies", json={"tier": "tier_2"})
    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Your 12-month term ended on {today:%d %b %Y}; apply again to renew"
    )
    end_term_on(client, today + timedelta(days=1))
    assert client.post("/api/policies", json={"tier": "tier_2"}).status_code == 200


def test_a_new_tariff_version_reprices_the_map(client):
    before = client.get("/api/map/quotes").json()["centres"][MAXWELL]
    saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    haze = next(hazard for hazard in saved["tariff"]["hazards"] if hazard["key"] == "haze")
    haze["weight"] = haze["weight"] / 2
    change = {"based_on_version": saved["version"], "tariff": saved["tariff"]}
    assert client.put("/api/admin/tariff", json=change, auth=ADMIN).status_code == 200
    after = client.get("/api/map/quotes").json()["centres"][MAXWELL]
    shown = client.post("/api/quote", json={"product": "cooked_food", "centre": MAXWELL}).json()
    assert weekly(after) < weekly(before)
    assert after == shown


def test_burn_replays_ten_years_for_a_platform_worker_by_region(client):
    query = {"region": "north", "product": "platform_work", "tier": "tier_2"}
    replay = client.get("/api/map/burn", params=query).json()
    lat, lng = MAP_STATIC["region_points"]["north"]
    assert (replay["centre"], replay["region"], replay["lat"], replay["lng"]) == (
        None, "north", lat, lng
    )
    charged = client.post("/api/quote", json={"region": "north", "product": "platform_work"})
    tier_2 = next(t for t in charged.json()["tiers"] if t["tier"] == "tier_2")
    assert replay["weekly_premium_sgd"] == tier_2["weekly_premium_sgd"]
    where = readings.history_place("north", lat, lng, client.app.state.sites)
    tariff = store.latest(client.app.state.db).tariff
    expected = burn.site_burn(
        burn.load_day_table(), where, tariff, "platform_work", "tier_2", 500.0,
        tier_2["yearly_premium_sgd"],
    )
    assert replay["years"] == expected["years"]


def test_burn_by_region_needs_a_known_region_and_no_half_point(client):
    assert client.get("/api/map/burn", params={"region": "middle"}).status_code == 404
    query = {"region": "north", "lat": 1.35}
    assert client.get("/api/map/burn", params=query).status_code == 422


def test_a_stall_joins_through_its_centre_association_else_fmas():
    assert onboarding.association_for("Tiong Bahru Market") == (
        "Tiong Bahru Market Hawkers' Association"
    )
    assert onboarding.association_for("Maxwell Food Centre (Kim Hua Market)") == onboarding.FMAS
    assert onboarding.association_for(None) == onboarding.FMAS
