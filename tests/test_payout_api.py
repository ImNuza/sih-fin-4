from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from api import burn, payout_api, payout_flow, postcodes, readings, sms, sms_gateway
from api.accounts import application_profile, policies
from api.main import app
from tests.test_api import buy_body, platform_worker_body, shop_body

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


@pytest.mark.parametrize("language", ["fr", "xx"])
def test_payout_account_refuses_a_language_with_no_texts(client, language):
    register(client, "sme", "tan@example.com")
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": GOOD_MOBILE, "sms_language": language}
    assert client.put("/api/payout-account", json=account).status_code == 422


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
    assert f"S${payout['amount_sgd']:.2f} " in text["body"]
    assert payout["reference"] in text["body"]
    assert "+65 ****4567" in text["body"]
    assert "Red day, 100% loss" in text["body"]


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


def change_tier_amount(client, tier_index: int, amount: float) -> None:
    saved = client.get("/api/admin/tariff", auth=("admin", "secret")).json()
    tariff = saved["tariff"]
    tariff["tiers"][tier_index]["daily_payout_sgd"] = amount
    body = {"based_on_version": saved["version"], "tariff": tariff}
    assert client.put("/api/admin/tariff", json=body, auth=("admin", "secret")).status_code == 200


def test_a_payout_uses_the_daily_amount_the_policy_was_sold_with(client):
    stallholder_with_cover(client)
    [policy] = client.get("/api/policies").json()
    change_tier_amount(client, 0, policy["daily_payout_sgd"] + 5)
    run_as_insurer(client, FLOOD_DAY)
    [payout] = client.get("/api/payouts").json()
    assert payout["amount_sgd"] == policy["daily_payout_sgd"]


def buy_and_start(client, body: dict) -> None:
    assert client.post("/api/buy", json=body).status_code == 200
    start_cover_on(client, LONG_AGO)


def test_cover_stops_on_the_day_the_term_ends(client):
    buy_and_start(client, buy_body())
    with client.app.state.db.begin() as db:
        db.execute(update(application_profile).values(cover_ends=date(2026, 11, 14)))
    register(client, "insurer", "desk@example.com")
    last_day_body = {**FLOOD_DAY, "loss_date": "2026-11-13"}
    last_day = client.post("/api/insurer/payout-runs", json=last_day_body).json()
    ended = client.post("/api/insurer/payout-runs", json=FLOOD_DAY).json()
    assert last_day["counts"]["cover_ended"] == 0
    assert ended["counts"]["cover_ended"] == 1


HAZE_DAY = {"loss_date": "2026-10-15", "source": "nea_history"}


def paid_readings(client) -> dict:
    [payout] = client.get("/api/payouts").json()
    return payout["readings"]


def expected_readings(client, region: str, lat: float, lng: float) -> dict:
    where = readings.history_place(region, lat, lng, client.app.state.sites)
    return readings.day_readings_at(burn.load_day_table()["2026-10-15"], where, 3)


def test_a_shop_is_paid_on_the_readings_at_its_postcode_area(client):
    buy_and_start(client, shop_body(postcode="561965"))
    run_as_insurer(client, HAZE_DAY)
    point = postcodes.area_point(
        "561965", client.app.state.centres_by_sector, client.app.state.map_static["region_points"]
    )
    expected = expected_readings(client, point["region"], point["lat"], point["lng"])
    assert paid_readings(client) == expected


def test_a_platform_worker_is_paid_on_the_readings_at_their_region(client, riders_open):
    buy_and_start(client, platform_worker_body())
    run_as_insurer(client, HAZE_DAY)
    lat, lng = client.app.state.map_static["region_points"]["north"]
    assert paid_readings(client) == expected_readings(client, "north", lat, lng)


def test_a_hawker_is_paid_on_the_readings_at_its_centre(client):
    stallholder_with_cover(client)
    run_as_insurer(client, HAZE_DAY)
    centre = next(c for c in client.app.state.map_static["hawker_centres"] if c["name"] == CENTRE)
    expected = expected_readings(client, centre["region"], centre["lat"], centre["lng"])
    assert paid_readings(client) == expected


def centre_readings(client, loss_date: str, gauges_read: int) -> tuple[dict, dict, tuple]:
    centre = client.app.state.centres_by_name[CENTRE]
    where = readings.history_place(
        centre["region"], centre["lat"], centre["lng"], client.app.state.sites
    )
    day = burn.load_day_table()[loss_date]
    return readings.day_readings_at(day, where, gauges_read), day, where.gauges


def test_a_payout_reads_as_many_rain_gauges_as_the_tariff_prices_from(client):
    stallholder_with_cover(client)
    saved = client.get("/api/admin/tariff", auth=("admin", "secret")).json()
    rain = next(hazard for hazard in saved["tariff"]["hazards"] if hazard["key"] == "rain")
    rain["sites_used"] = 1
    body = {"based_on_version": saved["version"], "tariff": saved["tariff"]}
    assert client.put("/api/admin/tariff", json=body, auth=("admin", "secret")).status_code == 200
    run_as_insurer(client, {"loss_date": "2026-02-19", "source": "nea_history"})
    one_gauge, day, gauges = centre_readings(client, "2026-02-19", 1)
    three_gauges, _, _ = centre_readings(client, "2026-02-19", 3)
    nearest_reporting = next(gauge for gauge in gauges if gauge not in day["rain_missing"])
    paid = paid_readings(client)
    assert paid == one_gauge
    assert paid["rain"] == day["rain"].get(nearest_reporting, 0.0) != three_gauges["rain"]


def region_point_readings(client, region: str) -> dict:
    lat, lng = client.app.state.map_static["region_points"][region]
    return expected_readings(client, region, lat, lng)


def test_a_policy_at_a_centre_the_map_no_longer_has_is_paid_at_its_region_point(client):
    stallholder_with_cover(client)
    [policy] = client.get("/api/policies").json()
    with client.app.state.db.begin() as db:
        db.execute(update(policies).values(centre="Closed Market"))
    run = run_as_insurer(client, HAZE_DAY)
    assert sum(run["counts"].values()) == 1
    assert paid_readings(client) == region_point_readings(client, policy["region"])


def test_a_shop_whose_postcode_has_no_sector_is_paid_at_its_region_point(client):
    buy_and_start(client, shop_body(postcode="561965"))
    with client.app.state.db.begin() as db:
        db.execute(update(application_profile).values(postcode="990123"))
    run_as_insurer(client, HAZE_DAY)
    assert paid_readings(client) == region_point_readings(client, "central")


SMS_LIMIT = 160


def texts_of_kind(client, kind: str) -> list[dict]:
    return [text for text in client.get("/api/sms").json() if text["kind"] == kind]


def test_insurer_sees_the_text_sent_with_each_payout(client):
    stallholder_with_cover(client)
    run_as_insurer(client, FLOOD_DAY)
    [payout] = client.get("/api/payouts").json()
    [text] = payout["texts"]
    assert text["kind"] == "payout_paid"
    assert payout["reference"] in text["body"]


def test_welcome_text_explains_the_cover_with_the_tariff_numbers(client):
    stallholder_with_cover(client)
    [welcome] = texts_of_kind(client, "welcome")
    body = welcome["body"]
    phrases = ("Up to S$20", "Heat 2h WBGT 32C+", "rain 20mm/h+", "Haze PSI 101+",
               "10 days/yr")
    for phrase in phrases:
        assert phrase in body
    assert "no pay, even if you lose income" in body
    assert len(body) <= SMS_LIMIT


def test_welcome_text_names_the_day_cover_starts_paying(client):
    stallholder_with_cover(client, started_at=STARTED_1_OCT_SGT)
    [welcome] = texts_of_kind(client, "welcome")
    assert "from 31 Oct" in welcome["body"]


def test_welcome_text_waits_for_a_verified_mobile(client):
    stallholder_with_cover(client, verify=False)
    assert texts_of_kind(client, "welcome") == []


def test_buying_cover_with_a_verified_mobile_sends_the_welcome_text(client):
    register(client, "sme", "tan@example.com")
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": GOOD_MOBILE, "sms_language": "en"}
    client.put("/api/payout-account", json=account)
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    client.post("/api/payout-account/verify", json={"code": code})
    assert texts_of_kind(client, "welcome") == []

    client.post("/api/policies", json={"tier": "tier_2"})
    [welcome] = texts_of_kind(client, "welcome")
    assert "Up to S$40" in welcome["body"]
    assert "15 days/yr" in welcome["body"]


def test_welcome_text_is_sent_once_per_cover(client):
    stallholder_with_cover(client)
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    client.post("/api/payout-account/verify", json={"code": code})
    assert len(texts_of_kind(client, "welcome")) == 1


@pytest.mark.parametrize("language", ["zh", "ms", "ta"])
def test_welcome_and_paid_texts_go_out_in_the_chosen_language(client, language):
    register(client, "sme", "tan@example.com")
    client.post("/api/policies", json={"tier": "tier_1"})
    start_cover_on(client, LONG_AGO)
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": GOOD_MOBILE, "sms_language": language}
    client.put("/api/payout-account", json=account)
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    client.post("/api/payout-account/verify", json={"code": code})
    run_as_insurer(client, {**FLOOD_DAY, "readings": {"rain": 52.4}})
    sign_in(client, "tan@example.com")
    texts = client.get("/api/sms").json()
    assert {t["language"] for t in texts} == {language}
    [paid] = [t for t in texts if t["kind"] == "payout_paid"]
    assert any(name in paid["body"] for name in sms.DAY_NAMES[language].values())


RAIN_STORM = {"rain": 50}


def demo_payout(client, user_id: int, readings: dict | None = None):
    return client.post(
        "/api/insurer/demo-payouts",
        json={"user_id": user_id, "readings": readings or RAIN_STORM},
    )


def insurer_sees_one_policyholder(client) -> int:
    register(client, "insurer", "desk@example.com")
    [holder] = client.get("/api/insurer/policyholders").json()["policyholders"]
    return holder["user_id"]


def test_insurer_lists_policyholders_with_where_their_texts_go(client):
    stallholder_with_cover(client)
    register(client, "insurer", "desk@example.com")
    listing = client.get("/api/insurer/policyholders").json()
    assert listing["texts_are_real"] is False
    [holder] = listing["policyholders"]
    assert holder["texts_to"] == "+65 ****4567"
    assert holder["mobile_verified"] is True


def test_demo_payout_pays_today_inside_the_waiting_period_and_texts(client):
    stallholder_with_cover(client, started_at=datetime.now(UTC))
    user_id = insurer_sees_one_policyholder(client)
    response = demo_payout(client, user_id)
    assert response.status_code == 200, response.text
    sent = response.json()
    payout = sent["payout"]
    assert sent["outcome"] == "paid"
    assert payout["source"] == "demo"
    assert payout["loss_date"] == datetime.now(payout_flow.SINGAPORE).date().isoformat()
    assert payout["texts"][-1]["kind"] == "payout_paid"
    assert payout["texts"][-1]["status"] == "delivered"


def test_demo_payout_can_be_run_again_on_the_day_before(client):
    stallholder_with_cover(client)
    user_id = insurer_sees_one_policyholder(client)
    first = demo_payout(client, user_id).json()["payout"]["loss_date"]
    second = demo_payout(client, user_id).json()["payout"]["loss_date"]
    assert date.fromisoformat(second) == date.fromisoformat(first) - timedelta(days=1)


def test_demo_payout_below_every_trigger_pays_nothing(client):
    stallholder_with_cover(client)
    user_id = insurer_sees_one_policyholder(client)
    assert demo_payout(client, user_id, {"rain": 1}).status_code == 422
    assert client.get("/api/payouts").json() == []


def test_demo_payout_rejects_an_unknown_hazard(client):
    stallholder_with_cover(client)
    user_id = insurer_sees_one_policyholder(client)
    assert demo_payout(client, user_id, {"earthquake": 9}).status_code == 422


def test_stallholders_cannot_send_demo_payouts(client):
    stallholder_with_cover(client)
    assert demo_payout(client, 1).status_code == 403


def test_code_is_not_shown_once_texts_reach_real_phones(client, monkeypatch):
    stallholder_with_cover(client, verify=False)
    monkeypatch.setattr(sms_gateway, "textbee_key", lambda: "key1")
    monkeypatch.setattr(
        sms_gateway, "send_by_textbee",
        lambda key, to, body: sms_gateway.Delivery("sent", "TB9", None),
    )
    sent = client.post("/api/payout-account/verify/start").json()
    assert sent["texts_are_real"] is True
    assert "demo_code" not in sent


def test_a_text_textbee_refuses_still_leaves_the_payout_paid(client, monkeypatch):
    stallholder_with_cover(client)
    user_id = insurer_sees_one_policyholder(client)
    monkeypatch.setattr(sms_gateway, "textbee_key", lambda: "key1")
    monkeypatch.setattr(
        sms_gateway, "send_by_textbee",
        lambda key, to, body: sms_gateway.Delivery("failed", None, "textbee 400: No enabled device"),
    )
    payout = demo_payout(client, user_id).json()["payout"]
    assert payout["status"] == "paid"
    assert payout["texts"][-1]["status"] == "failed"
    assert payout["texts"][-1]["error"] == "textbee 400: No enabled device"


def test_demo_payout_pays_and_texts_the_mobile_the_insurer_enters(client):
    register(client, "sme", "tan@example.com")
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 200
    user_id = insurer_sees_one_policyholder(client)
    response = client.post("/api/insurer/demo-payouts", json={
        "user_id": user_id, "readings": RAIN_STORM,
        "mobile": "+65 8123-4567", "sms_language": "zh",
    })
    assert response.status_code == 200, response.text
    payout = response.json()["payout"]
    assert payout["status"] == "paid"
    assert payout["paid_to"] == "+65 ****4567"
    text = payout["texts"][-1]
    assert text["kind"] == "payout_paid"
    assert text["to"] == "+65 ****4567"
    assert text["language"] == "zh"

    [holder] = client.get("/api/insurer/policyholders").json()["policyholders"]
    assert holder["mobile_verified"] is True


def test_demo_payout_refuses_a_mobile_outside_singapore(client):
    stallholder_with_cover(client)
    user_id = insurer_sees_one_policyholder(client)
    response = client.post("/api/insurer/demo-payouts", json={
        "user_id": user_id, "readings": RAIN_STORM, "mobile": "+6512345678",
    })
    assert response.status_code == 422
    assert client.get("/api/payouts").json() == []


FALLBACK = {"DEMO_PAYOUT_MOBILE": "+6581112222"}


def test_demo_payout_without_a_mobile_goes_to_the_fallback_phone(client, monkeypatch):
    monkeypatch.setattr(payout_api, "api_key", FALLBACK.get)
    register(client, "sme", "tan@example.com")
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 200
    user_id = insurer_sees_one_policyholder(client)
    listing = client.get("/api/insurer/policyholders").json()
    assert listing["fallback_mobile"] == "+6581112222"
    payout = demo_payout(client, user_id).json()["payout"]
    assert payout["status"] == "paid"
    assert payout["paid_to"] == "+65 ****2222"
    assert payout["texts"][-1]["to"] == "+65 ****2222"


def test_demo_payout_prefers_the_customers_verified_mobile_to_the_fallback(client, monkeypatch):
    monkeypatch.setattr(payout_api, "api_key", FALLBACK.get)
    stallholder_with_cover(client)
    user_id = insurer_sees_one_policyholder(client)
    payout = demo_payout(client, user_id).json()["payout"]
    assert payout["texts"][-1]["to"] == "+65 ****4567"


def test_demo_payout_without_any_mobile_is_held(client, monkeypatch):
    monkeypatch.setattr(payout_api, "api_key", lambda name: None)
    register(client, "sme", "tan@example.com")
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 200
    user_id = insurer_sees_one_policyholder(client)
    assert demo_payout(client, user_id).json()["payout"]["status"] == "held"


@pytest.mark.parametrize(("setting", "mobile"), [(FALLBACK, "+6581112222"), ({}, None)])
def test_sign_up_forms_start_with_the_demo_phone_when_one_is_set(
    client, monkeypatch, setting, mobile
):
    monkeypatch.setattr(payout_api, "api_key", setting.get)
    assert client.get("/api/demo-phone").json() == {"mobile": mobile}


def test_a_text_the_phone_fails_to_send_shows_as_failed_with_the_reason(client, monkeypatch):
    stallholder_with_cover(client)
    user_id = insurer_sees_one_policyholder(client)
    monkeypatch.setattr(sms_gateway, "textbee_key", lambda: "key1")
    monkeypatch.setattr(
        sms_gateway, "send_by_textbee",
        lambda key, to, body: sms_gateway.Delivery("queued", "TBb1", None),
    )
    payout = demo_payout(client, user_id).json()["payout"]
    assert payout["texts"][-1]["status"] == "queued"

    no_service = sms_gateway.Delivery("failed", "TBb1", "The phone has no mobile service.")
    monkeypatch.setattr(sms_gateway, "check", lambda provider_id: no_service)
    [listed] = client.get("/api/payouts").json()
    assert listed["status"] == "paid"
    assert listed["texts"][-1]["status"] == "failed"
    assert listed["texts"][-1]["error"] == "The phone has no mobile service."


def signs_up_in(client, language: str) -> None:
    body = buy_body(payment_method="giro", sms_language=language)
    response = client.post("/api/buy", json=body)
    assert response.status_code == 200, response.text


def test_sign_up_keeps_the_language_the_customer_picked(client):
    signs_up_in(client, "zh")
    assert client.get("/api/sms-preference").json() == {"language": "zh"}


def test_sign_up_refuses_a_language_with_no_texts(client):
    response = client.post("/api/buy", json=buy_body(payment_method="giro", sms_language="fr"))
    assert response.status_code == 422


def test_demo_payout_texts_in_the_language_picked_at_sign_up(client, monkeypatch):
    monkeypatch.setattr(payout_api, "api_key", lambda name: None)
    signs_up_in(client, "ta")
    user_id = insurer_sees_one_policyholder(client)
    [holder] = client.get("/api/insurer/policyholders").json()["policyholders"]
    assert holder["sms_language"] == "ta"
    response = client.post(
        "/api/insurer/demo-payouts",
        json={"user_id": user_id, "readings": RAIN_STORM, "mobile": "+6581112222"},
    )
    text = response.json()["payout"]["texts"][-1]
    assert text["language"] == "ta"
    assert any(name in text["body"] for name in sms.DAY_NAMES["ta"].values())


def test_insurer_can_send_the_demo_text_in_another_language(client, monkeypatch):
    monkeypatch.setattr(payout_api, "api_key", lambda name: None)
    signs_up_in(client, "ta")
    user_id = insurer_sees_one_policyholder(client)
    response = client.post("/api/insurer/demo-payouts", json={
        "user_id": user_id, "readings": RAIN_STORM, "mobile": "+6581112222", "sms_language": "ms",
    })
    assert response.json()["payout"]["texts"][-1]["language"] == "ms"


def test_changing_the_texting_language_with_paynow_details_updates_the_choice(client):
    signs_up_in(client, "zh")
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": GOOD_MOBILE, "sms_language": "ms"}
    assert client.put("/api/payout-account", json=account).status_code == 200
    assert client.get("/api/sms-preference").json() == {"language": "ms"}



def welcomes(client) -> list[dict]:
    return [text for text in client.get("/api/sms").json() if text["kind"] == "welcome"]


def test_paying_in_the_buy_flow_texts_the_welcome_in_the_chosen_language(client):
    signs_up_in(client, "zh")
    [welcome] = welcomes(client)
    assert welcome["to"] == "+65 ****4567"
    assert welcome["language"] == "zh"
    assert "红色日最多赔" in welcome["body"]


def test_a_landline_given_at_sign_up_gets_no_welcome_text(client):
    body = buy_body(payment_method="giro", phone="6123 4567")
    assert client.post("/api/buy", json=body).status_code == 200
    assert welcomes(client) == []


def test_an_application_sent_to_an_underwriter_gets_no_welcome_text(client):
    body = buy_body(payment_method=None, declined_before=True, declined_details="Flooded in 2025")
    assert client.post("/api/buy", json=body).status_code == 200
    assert welcomes(client) == []


def test_verifying_paynow_later_does_not_resend_the_welcome(client):
    cover_start = (datetime.now(payout_flow.SINGAPORE).date() + timedelta(days=10)).isoformat()
    body = buy_body(payment_method="giro", sms_language="ms", cover_start=cover_start)
    assert client.post("/api/buy", json=body).status_code == 200
    account = {"paynow_proxy_type": "mobile", "paynow_proxy": GOOD_MOBILE, "sms_language": "ms"}
    client.put("/api/payout-account", json=account)
    code = client.post("/api/payout-account/verify/start").json()["demo_code"]
    assert client.post("/api/payout-account/verify", json={"code": code}).status_code == 200
    assert len(welcomes(client)) == 1
