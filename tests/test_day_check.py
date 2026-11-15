from __future__ import annotations

import pytest

from api import burn, readings
from tests.test_payout_api import (
    CENTRE,
    FLOOD_DAY,
    STARTED_1_OCT_SGT,
    client,
    register,
    run_as_insurer,
    sign_in,
    stallholder_with_cover,
)

__all__ = ["client"]

HAZE_DAY = "2026-10-15"
QUIET_DAY = "2026-11-01"
NO_PSI_DAY = "2026-11-08"


def my_day(client, day: str) -> dict:
    response = client.get("/api/my-day", params={"day": day})
    assert response.status_code == 200, response.text
    return response.json()


def hazard(check: dict, key: str) -> dict:
    return next(h for h in check["hazards"] if h["hazard"] == key)


def centre_readings(client, day: str) -> dict:
    centre = client.app.state.centres_by_name[CENTRE]
    where = readings.history_place(
        centre["region"], centre["lat"], centre["lng"], client.app.state.sites
    )
    return readings.day_readings_at(burn.load_day_table()[day], where, 3)


def test_a_quiet_day_says_it_pays_nothing_and_shows_each_reading(client):
    stallholder_with_cover(client)
    check = my_day(client, QUIET_DAY)
    assert check["outcome"] == "below_trigger"
    assert check["payout"] is None
    rain = hazard(check, "rain")
    assert rain["value"] == centre_readings(client, QUIET_DAY)["rain"]
    assert rain["pays_from"] == 20
    assert rain["crossed"] is False
    assert rain["basis"].startswith("median of ")


def test_a_day_the_readings_would_pay_but_no_run_has_assessed_yet(client):
    stallholder_with_cover(client)
    check = my_day(client, HAZE_DAY)
    assert check["outcome"] == "not_run_yet"
    assert hazard(check, "haze")["crossed"] is True
    assert hazard(check, "haze")["basis"].endswith("region")


def test_a_paid_day_shows_the_readings_and_rule_the_payout_used(client):
    stallholder_with_cover(client)
    run_as_insurer(client, {"loss_date": HAZE_DAY, "source": "nea_history"})
    sign_in(client, "tan@example.com")
    check = my_day(client, HAZE_DAY)
    assert check["outcome"] == "paid"
    assert check["payout"]["amount_sgd"] > 0
    shown = {h["hazard"]: h["value"] for h in check["hazards"]}
    assert shown == centre_readings(client, HAZE_DAY)
    assert hazard(check, "heat")["basis"].endswith("(nearest)")


def test_a_manual_payout_shows_the_reading_was_entered_by_the_insurer(client):
    stallholder_with_cover(client)
    run_as_insurer(client, FLOOD_DAY)
    sign_in(client, "tan@example.com")
    check = my_day(client, FLOOD_DAY["loss_date"])
    assert hazard(check, "closure")["basis"] == "entered by the insurer"


def test_a_hazard_with_no_report_yet_is_shown_as_waiting(client):
    stallholder_with_cover(client)
    check = my_day(client, NO_PSI_DAY)
    assert check["outcome"] == "awaiting_data"
    assert hazard(check, "haze")["value"] is None
    assert hazard(check, "haze")["basis"] == "no PSI region reported"


def test_a_day_in_the_waiting_period_shows_the_readings_and_why_it_does_not_pay(client):
    stallholder_with_cover(client, started_at=STARTED_1_OCT_SGT)
    check = my_day(client, HAZE_DAY)
    assert check["outcome"] == "waiting_period"
    assert check["cover_pays_from"] == "2026-10-31"
    assert hazard(check, "haze")["crossed"] is True


def test_a_day_nea_has_not_published_says_so(client):
    stallholder_with_cover(client)
    check = my_day(client, "2001-01-01")
    assert check["outcome"] == "no_record"
    assert check["hazards"] == []


def test_an_owner_without_cover_has_no_day_to_check(client):
    register(client, "sme", "tan@example.com")
    assert client.get("/api/my-day", params={"day": QUIET_DAY}).status_code == 404


def test_only_a_business_owner_checks_their_day(client):
    register(client, "insurer", "desk@example.com")
    assert client.get("/api/my-day", params={"day": QUIET_DAY}).status_code == 403


def file_request(client, **changes):
    body = {"loss_date": QUIET_DAY, "kind": "wrong_reading", "note": "It rained hard at noon."}
    return client.post("/api/service-requests", json=body | changes)


def test_a_wrong_reading_report_reaches_the_insurer_as_a_service_request(client):
    stallholder_with_cover(client)
    response = file_request(client)
    assert response.status_code == 200, response.text
    assert response.json()["reference"].startswith("SR-")

    register(client, "insurer", "desk@example.com")
    [request] = client.get("/api/insurer/service-requests").json()
    assert request["kind"] == "wrong_reading"
    assert request["loss_date"] == QUIET_DAY
    assert request["note"] == "It rained hard at noon."
    assert request["business_name"]
    assert request["reference"] == response.json()["reference"]


@pytest.mark.parametrize("kind", ["bigger_loss", "top_up", ""])
def test_a_service_request_is_only_for_a_data_error(client, kind):
    stallholder_with_cover(client)
    assert file_request(client, kind=kind).status_code == 422


def test_business_owners_cannot_list_service_requests(client):
    stallholder_with_cover(client)
    assert client.get("/api/insurer/service-requests").status_code == 403
