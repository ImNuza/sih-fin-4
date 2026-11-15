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
THREE_GAUGES = readings.StationRule(gauges_read=3)
NOTHING_ON_HOLD = frozenset()


def read(day: dict, rule: readings.StationRule = THREE_GAUGES) -> dict[str, float]:
    return readings.day_readings_at(day, PLACE, rule)


def test_stations_within_5_km_are_ranked_nearest_first_and_farther_ones_left_out():
    assert readings.eligible(PLACE.gauges, NOTHING_ON_HOLD) == ("near", "middle", "far", "farthest")
    assert readings.eligible(PLACE.heat_stations, NOTHING_ON_HOLD) == ("hot_near", "hot_far")


def test_the_nearest_station_is_read_however_far_it_is():
    alone = readings.place("central", 1.30, 103.80, [("away", 1.30, 103.90)], HEAT)
    assert readings.eligible(alone.gauges, NOTHING_ON_HOLD) == ("away",)


def test_a_station_on_hold_is_skipped_like_one_that_did_not_report():
    held = readings.StationRule(gauges_read=3, gauges_on_hold=frozenset({"near"}))
    day = {"rain": {"near": 90.0, "middle": 30.0, "far": 25.0, "farthest": 50.0}}
    assert read(day, held)["rain"] == 30.0
    site = readings.site_readings(day, PLACE, held)
    assert site.basis["rain"] == "median of middle, far, farthest (near on hold)"


def test_with_the_nearest_on_hold_the_next_nearest_is_read_however_far_it_is():
    far_apart = [("held", 1.30, 103.801), ("next", 1.30, 103.86)]
    where = readings.place("central", 1.30, 103.80, GAUGES, far_apart)
    held = readings.StationRule(heat_on_hold=frozenset({"held"}))
    day = {"heat": {"held": 8.0, "next": 3.0}}
    assert readings.day_readings_at(day, where, held)["heat"] == 3.0
    assert readings.site_readings(day, where, held).basis["heat"] == "next (held on hold)"
    assert readings.stations_used(where, "heat", held) == ["next"]


def test_a_region_on_hold_reads_the_median_of_the_others():
    held = readings.StationRule(regions_on_hold=frozenset({"central"}))
    day = {"haze": {"central": 300.0, "east": 100.0, "west": 200.0}}
    assert read(day, held)["haze"] == 150.0


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
    two_heat_stations = readings.StationRule(gauges_read=3, heat_read=2)
    assert readings.day_readings_at(day, PLACE, two_heat_stations)["heat"] == 3.0


def test_haze_is_the_places_region():
    assert read({"haze": {"central": 230.0, "west": 300.0}}) == {
        "haze": 230.0, "rain": 0.0, "heat": 0.0,
    }


def test_a_replay_reads_a_hazard_that_would_wait_as_zero():
    silent = {
        "rain_missing": dict(PLACE.gauges),
        "heat_missing": dict(PLACE.heat_stations),
    }
    assert read(silent) == {"haze": 0.0, "rain": 0.0, "heat": 0.0}
    site = readings.site_readings(silent, PLACE, THREE_GAUGES)
    assert site.waiting_for == ["haze", "rain", "heat"]


def default_tariff() -> Tariff:
    return Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())


def test_rain_and_heat_read_as_many_stations_as_the_tariff_prices_from():
    tariff = default_tariff()
    rule = readings.station_rule(tariff)
    assert (rule.gauges_read, rule.heat_read) == (3, 1)
    rain_hazard = next(hazard for hazard in tariff.hazards if hazard.key == "rain")
    rain_hazard.sites_used = 1
    day = {"rain": {"middle": 30.0, "far": 25.0, "farthest": 50.0}, "rain_missing": {"near": 1}}
    assert readings.day_readings_at(day, PLACE, readings.station_rule(tariff))["rain"] == 30.0


def test_the_default_tariff_holds_the_two_heat_stations_nea_has_not_confirmed():
    rule = readings.station_rule(default_tariff())
    assert rule.heat_on_hold == {"S142", "S128"}
    assert rule.gauges_on_hold == rule.regions_on_hold == frozenset()


def test_a_tariff_without_rain_still_reads_the_default_gauges():
    body = json.loads(DEFAULT_TARIFF_PATH.read_text())
    body["hazards"] = [hazard for hazard in body["hazards"] if hazard["key"] != "rain"]
    rule = readings.station_rule(Tariff.model_validate(body))
    assert rule.gauges_read == readings.RAIN_GAUGES_READ
