from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from basis_risk import count_outcomes  # noqa: E402

# Five stations on one line, unevenly spaced so no two are the same distance from a third.
POSITIONS = {"A": 0, "B": 1, "C": 3, "D": 7, "E": 12}
STATIONS = [{"id": name, "lat": 1.30 + 0.01 * at, "lng": 103.80} for name, at in POSITIONS.items()]
NEAREST = "nearest station (today's rule)"
WORST_2 = "worst of 2 nearest"
MEDIAN_3 = "median of 3 nearest"


def test_a_storm_only_at_the_stall_is_a_missed_loss_for_every_option():
    counts = count_outcomes([({"C": 60.0}, set())], STATIONS, 20)
    for option in (NEAREST, WORST_2, MEDIAN_3):
        assert counts[option]["missed_loss"] == 1
    assert counts[NEAREST]["false_alarm"] == 1
    assert counts[WORST_2]["false_alarm"] == 4


def test_worst_of_two_catches_a_storm_the_nearest_station_misses():
    counts = count_outcomes([({"B": 60.0, "C": 60.0}, set())], STATIONS, 20)
    assert counts[NEAREST]["missed_loss"] == 1
    assert counts[WORST_2]["hit"] == 2


def test_a_silent_station_is_neither_a_stall_nor_read_for_a_payout():
    counts = count_outcomes([({"B": 60.0}, {"B"})], STATIONS, 20)
    assert counts[NEAREST] == {"hit": 0, "missed_loss": 0, "false_alarm": 0, "quiet": 4}
