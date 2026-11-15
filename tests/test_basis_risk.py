from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from basis_risk import TODAYS_RULE, count_outcomes  # noqa: E402

# Five stations on one line, unevenly spaced so no two are the same distance from a third.
# 0.01 degree of latitude is about 1.1 km, so only A, B and C sit within 5 km of each other.
POSITIONS = {"A": 0, "B": 1, "C": 3, "D": 7, "E": 12}
STATIONS = [(name, 1.30 + 0.01 * at, 103.80) for name, at in POSITIONS.items()]
NEAREST = "nearest station"
WORST_2 = "worst of 2 nearest"
MEDIAN_3 = "median of 3 nearest"


def rain_day(values: dict, silent: set[str] = frozenset()) -> dict:
    return {"rain": values, "rain_missing": dict.fromkeys(silent, 1.0)}


def test_a_storm_only_at_the_stall_is_a_missed_loss_for_every_option():
    counts = count_outcomes([rain_day({"C": 60.0})], "rain", STATIONS, 20, 3)
    for option in (TODAYS_RULE, NEAREST, WORST_2, MEDIAN_3):
        assert counts[option]["missed_loss"] == 1
    assert counts[NEAREST]["false_alarm"] == 1
    assert counts[WORST_2]["false_alarm"] == 4


def test_worst_of_two_catches_a_storm_the_nearest_station_misses():
    counts = count_outcomes([rain_day({"B": 60.0, "C": 60.0})], "rain", STATIONS, 20, 3)
    assert counts[NEAREST]["missed_loss"] == 1
    assert counts[WORST_2]["hit"] == 2


def test_todays_rule_skips_a_silent_station_and_reads_the_next():
    day = rain_day({"B": 60.0, "C": 60.0}, {"A"})
    one_station = count_outcomes([day], "rain", STATIONS, 20, 1)
    assert one_station[TODAYS_RULE]["hit"] == 2


def test_a_silent_station_is_neither_a_stall_nor_read_for_a_payout():
    counts = count_outcomes([rain_day({"B": 60.0}, {"B"})], "rain", STATIONS, 20, 3)
    assert counts[NEAREST] == {"hit": 0, "missed_loss": 0, "false_alarm": 0, "quiet": 4}
