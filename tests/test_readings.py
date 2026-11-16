from __future__ import annotations

import json

from api import readings
from api.main import DEFAULT_TARIFF_PATH
from api.models import Tariff

# Four gauges east of a place at 1.30, 103.80, nearest first, one more about 11 km away, and
# two heat stations.
GAUGES = [("near", 1.30, 103.801), ("middle", 1.30, 103.802), ("far", 1.30, 103.803),
          ("farthest", 1.30, 103.804), ("away", 1.30, 103.90)]
HEAT = [("hot_near", 1.30, 103.801), ("hot_far", 1.30, 103.805)]
PLACE = readings.place("central", 1.30, 103.80, GAUGES, HEAT)
THREE_GAUGES = 3


def read(day: dict) -> dict[str, float]:
    return readings.day_readings_at(day, PLACE, THREE_GAUGES)


def test_stations_within_5_km_are_ranked_nearest_first_and_farther_ones_left_out():
    assert PLACE.gauges == ("near", "middle", "far", "farthest")
    assert PLACE.heat_stations == ("hot_near", "hot_far")


def test_the_nearest_station_is_read_however_far_it_is():
    alone = readings.place("central", 1.30, 103.80, [("away", 1.30, 103.90)], HEAT)
    assert alone.gauges == ("away",)


def test_rain_is_the_middle_of_the_three_nearest_gauges():
    rain = {"near": 40.0, "middle": 5.0, "far": 22.0, "farthest": 90.0}
    assert read({"rain": rain})["rain"] == 22.0


def test_a_gauge_that_did_not_report_is_skipped_not_read_as_dry():
    day = {"rain": {"middle": 30.0, "far": 25.0, "farthest": 50.0}, "rain_missing": {"near": 1}}
    assert read(day)["rain"] == 30.0


def test_a_reporting_gauge_without_a_row_read_zero():
    assert read({"rain": {"far": 20.0, "farthest": 90.0}})["rain"] == 0.0


def test_with_fewer_than_three_reporting_the_middle_of_those_is_used():
    two_silent = {"rain": {"far": 20.0, "farthest": 30.0}, "rain_missing": {"near": 1, "middle": 1}}
    assert read(two_silent)["rain"] == 25.0
    three_silent = {"rain": {"farthest": 31.0}, "rain_missing": {"near": 1, "middle": 1, "far": 1}}
    assert read(three_silent)["rain"] == 31.0


def test_heat_is_the_nearest_station_that_reported():
    day = {"heat": {"hot_far": 3.25}, "heat_missing": {"hot_near": 1}}
    assert read(day)["heat"] == 3.25
    assert read({"heat": {"hot_far": 6.0}})["heat"] == 0.0


def test_heat_takes_the_middle_when_the_tariff_reads_more_than_one_station():
    day = {"heat": {"hot_near": 2.0, "hot_far": 4.0}}
    assert readings.day_readings_at(day, PLACE, THREE_GAUGES, 2)["heat"] == 3.0


def test_the_heat_peak_is_the_highest_wbgt_at_the_stations_the_reading_used():
    day = {"heat_peak": {"hot_near": 31.4, "hot_far": 33.0}}
    assert readings.heat_peak(day, PLACE, 1) == 31.4
    assert readings.heat_peak(day, PLACE, 2) == 33.0


def test_the_heat_peak_skips_a_station_that_did_not_report():
    day = {"heat_peak": {"hot_near": 35.0, "hot_far": 30.2}, "heat_missing": {"hot_near": 1}}
    assert readings.heat_peak(day, PLACE, 1) == 30.2


def test_a_day_with_no_peak_recorded_has_no_heat_peak():
    assert readings.heat_peak({"heat": {"hot_near": 2.0}}, PLACE, 1) is None


def test_haze_is_the_places_region():
    assert read({"haze": {"central": 230.0, "west": 300.0}}) == {
        "haze": 230.0, "rain": 0.0, "heat": 0.0,
    }


def test_a_replay_reads_a_hazard_that_would_wait_as_zero():
    silent = {
        "rain_missing": dict.fromkeys(PLACE.gauges, 1),
        "heat_missing": dict.fromkeys(PLACE.heat_stations, 1),
    }
    assert read(silent) == {"haze": 0.0, "rain": 0.0, "heat": 0.0}
    site = readings.site_readings(silent, PLACE, THREE_GAUGES, 1)
    assert site.waiting_for == ["haze", "rain", "heat"]


def default_tariff() -> Tariff:
    return Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())


def test_rain_and_heat_read_as_many_stations_as_the_tariff_prices_from():
    tariff = default_tariff()
    assert readings.stations_read(tariff) == (3, 1)
    rain_hazard = next(hazard for hazard in tariff.hazards if hazard.key == "rain")
    rain_hazard.sites_used = 1
    gauges_read, heat_read = readings.stations_read(tariff)
    day = {"rain": {"middle": 30.0, "far": 25.0, "farthest": 50.0}, "rain_missing": {"near": 1}}
    assert readings.day_readings_at(day, PLACE, gauges_read, heat_read)["rain"] == 30.0


def test_a_tariff_without_rain_still_reads_the_default_gauges():
    body = json.loads(DEFAULT_TARIFF_PATH.read_text())
    body["hazards"] = [hazard for hazard in body["hazards"] if hazard["key"] != "rain"]
    gauges_read, _ = readings.stations_read(Tariff.model_validate(body))
    assert gauges_read == readings.RAIN_GAUGES_READ
