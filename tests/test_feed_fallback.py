from __future__ import annotations

import pytest

from api.day_history import site_readings
from tests.test_api import shop_body
from tests.test_payout_api import (  # noqa: F401  (client is a fixture)
    FLOOD_DAY,
    client,
    register,
    run_as_insurer,
    sign_in,
    stallholder_with_cover,
    start_cover_on,
    LONG_AGO,
)

# A, B and C sit about 1.1 km apart on one line; D is about 11 km away.
STATIONS = [
    {"id": "A", "lat": 1.30, "lng": 103.80},
    {"id": "B", "lat": 1.31, "lng": 103.80},
    {"id": "C", "lat": 1.32, "lng": 103.80},
    {"id": "D", "lat": 1.40, "lng": 103.80},
]
MAP = {"rain_stations": STATIONS, "wbgt_stations": STATIONS}
REGIONS = {"central": 60, "east": 60, "north": 60, "south": 60, "west": 60}


def read(day: dict):
    return site_readings({"haze": REGIONS, **day}, 1.30, 103.80, "central", MAP)


def test_nearest_station_reading_is_used():
    site = read({"rain": {"A": 30.0, "B": 90.0}})
    assert site.readings["rain"] == 30.0
    assert site.basis["rain"] == "A (nearest)"


def test_a_station_that_reported_no_rain_reads_zero():
    assert read({"rain": {"B": 90.0}}).readings["rain"] == 0.0


def test_a_silent_station_takes_the_median_of_its_reporting_neighbours():
    site = read({"rain": {"B": 20.0, "C": 40.0}, "rain_missing": {"A": 1}})
    assert site.readings["rain"] == 30.0
    assert site.basis["rain"] == "median of B, C (A did not report)"


def test_far_stations_are_not_neighbours_so_the_mss_record_is_used():
    missing = {"A": 1, "B": 1, "C": 1}
    site = read({"rain": {"D": 80.0}, "rain_missing": missing, "rain_mss": {"A": 25.0}})
    assert site.readings["rain"] == 25.0
    assert site.basis["rain"] == "MSS daily record for A (A did not report)"
    assert site.waiting_for == []


def test_with_no_reading_at_all_the_hazard_waits_for_data():
    site = read({"rain_missing": {"A": 1, "B": 1, "C": 1}})
    assert "rain" not in site.readings
    assert site.waiting_for == ["rain"]


def test_heat_has_no_mss_record_to_fall_back_on():
    site = read({"heat_missing": {"A": 1, "B": 1, "C": 1}, "rain_mss": {"A": 25.0}})
    assert site.waiting_for == ["heat"]


def test_a_silent_haze_region_takes_the_median_of_the_others():
    day = {"haze": {"north": 100, "south": 200, "east": 300}}
    site = site_readings(day, 1.30, 103.80, "central", MAP)
    assert site.readings["haze"] == 200
    assert site.basis["haze"] == "median of east, north, south (central did not report)"


def all_gauges_silent(app) -> dict:
    gauges = {station["id"]: 1 for station in app.state.map_static["rain_stations"]}
    return {"haze": REGIONS, "rain_missing": gauges}


@pytest.fixture
def use_day(client):
    """Replace the NEA day table with one test day, and put the real table back afterwards."""
    state = client.app.state
    real = getattr(state, "day_readings", None)
    yield lambda day: setattr(state, "day_readings", {"2026-11-09": day})
    if real is not None:
        state.day_readings = real
    elif hasattr(state, "day_readings"):
        del state.day_readings


def test_a_day_with_no_readings_is_paid_late_not_never(client, use_day):
    stallholder_with_cover(client)
    use_day(all_gauges_silent(client.app))
    run = run_as_insurer(client, {"loss_date": "2026-11-09", "source": "nea_history"})
    assert run["counts"]["awaiting_data"] == 1
    assert client.get("/api/payouts").json() == []

    use_day({"haze": REGIONS, "rain": {}})
    rerun = client.post("/api/insurer/payout-runs",
                        json={"loss_date": "2026-11-09", "source": "nea_history"}).json()
    assert rerun["counts"]["awaiting_data"] == 0
    assert rerun["counts"]["already_assessed"] == 0


def test_each_payout_keeps_the_basis_of_its_readings(client, use_day):
    stallholder_with_cover(client)
    gauges = {station["id"]: 80.0 for station in client.app.state.map_static["rain_stations"]}
    use_day({"haze": REGIONS, "rain": gauges})
    run_as_insurer(client, {"loss_date": "2026-11-09", "source": "nea_history"})
    sign_in(client, "tan@example.com")
    [payout] = client.get("/api/payouts").json()
    assert payout["readings"]["rain"] == 80.0
    assert payout["basis"]["rain"].endswith("(nearest)")
    assert set(payout["basis"]) == {"haze", "rain", "heat"}


def test_a_manual_run_says_the_insurer_entered_the_readings(client):
    stallholder_with_cover(client)
    run_as_insurer(client, FLOOD_DAY)
    sign_in(client, "tan@example.com")
    [payout] = client.get("/api/payouts").json()
    assert payout["basis"] == {"closure": "entered by the insurer"}


@pytest.mark.parametrize("body", [shop_body(), shop_body(postcode="730123", ssic_code="47102")])
def test_a_history_run_reads_a_shop_at_its_postcode_area(client, body):
    assert client.post("/api/buy", json=body).status_code == 200
    start_cover_on(client, LONG_AGO)
    run = run_as_insurer(client, {"loss_date": "2026-11-08", "source": "nea_history"})
    assert sum(run["counts"].values()) == 1
