"""Every place's readings on every recorded day, read once so that any tariff prices fast.

The price replays each recorded day at the customer's place through api/readings.py
(calculator.Replay). A place's readings depend on the tariff only through its station rule: how
many stations it reads and which are on hold. scripts/build_place_years.py reads them once,
under the default tariff's rule, for every hawker centre, PSI region point and postcode area
point, into PLACE_DAYS_PATH. Any other place, or a tariff with another station rule, is read
here from the day table on demand and kept for the life of the process.

The file holds, with no pickled objects:
    days          datetime64[D], every day of day_readings.csv.gz, ascending
    fed           bool (hazard, day): the hazard's NEA feed ran that day
    readings      float64 (hazard, place, day): the reading a payout takes, 0 where it waits
    region, latitude, longitude, name   per place
    gauges_read, heat_read, regions_on_hold, gauges_on_hold, heat_on_hold   the station rule
    inputs_sha256 the day_readings.csv.gz, site_hazard_readings.csv and api/readings.py it
                  was read with, so a changed reading rule cannot price from an old file
Hazards are in readings.HAZARDS order.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

import numpy as np

from api import readings
from api.burn import DAY_READINGS_PATH, DayTable
from api.calculator import Replay
from api.readings import Place, Sites, StationRule

PROC_DIR = DAY_READINGS_PATH.parent
PLACE_DAYS_PATH = PROC_DIR / "place_day_readings.npz"
SITES_PATH = PROC_DIR / "site_hazard_readings.csv"
# A feed is running from its first to its last recorded day: a day of it may have no row at all
# when every station reported a dry or cool day.
FEED_KINDS = {"haze": ("haze",), "rain": ("rain", "rain_missing"), "heat": ("heat", "heat_missing")}
COORDINATE_DECIMALS = 6
# Places read on demand that are kept, the least recently used dropped first: each is about
# 110 kB, so a stream of arbitrary map points cannot grow the process without bound.
ON_DEMAND_PLACES_KEPT = 256

PlaceKey = tuple[str, float, float]


def inputs_sha256() -> str:
    digest = hashlib.sha256()
    for path in (DAY_READINGS_PATH, SITES_PATH, Path(readings.__file__)):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def place_key(region: str, lat: float, lng: float) -> PlaceKey:
    return region, round(lat, COORDINATE_DECIMALS), round(lng, COORDINATE_DECIMALS)


def feed_days(table: DayTable) -> tuple[np.ndarray, np.ndarray]:
    """Every recorded day, and on which of them each hazard's feed ran: (days, fed[hazard])."""
    names = sorted(table)
    days = np.array(names, dtype="datetime64[D]")
    fed = np.zeros((len(readings.HAZARDS), len(names)), dtype=bool)
    for row, hazard in enumerate(readings.HAZARDS):
        recorded = [
            index for index, name in enumerate(names)
            if any(table[name].get(kind) for kind in FEED_KINDS[hazard])
        ]
        if not recorded:
            continue
        if hazard == "haze":
            fed[row, recorded] = True
        else:
            fed[row, recorded[0]:recorded[-1] + 1] = True
    return days, fed


def read_place(table: DayTable, days: np.ndarray, where: Place, rule: StationRule) -> np.ndarray:
    """A place's reading of each hazard on each day, as a payout takes it: (hazard, day)."""
    values = np.zeros((len(readings.HAZARDS), len(days)))
    for column, day in enumerate(days.astype(str)):
        found = readings.day_readings_at(table[day], where, rule)
        for row, hazard in enumerate(readings.HAZARDS):
            values[row, column] = found[hazard]
    return values


def as_replay(days: np.ndarray, fed: np.ndarray, values: np.ndarray) -> Replay:
    return Replay(
        days=days,
        readings=dict(zip(readings.HAZARDS, values, strict=True)),
        fed=dict(zip(readings.HAZARDS, fed, strict=True)),
    )


def file_rule(saved: np.lib.npyio.NpzFile) -> StationRule:
    return StationRule(
        gauges_read=int(saved["gauges_read"]),
        heat_read=int(saved["heat_read"]),
        regions_on_hold=frozenset(saved["regions_on_hold"].tolist()),
        gauges_on_hold=frozenset(saved["gauges_on_hold"].tolist()),
        heat_on_hold=frozenset(saved["heat_on_hold"].tolist()),
    )


class PlaceDays:
    """Replays of places, from the file where it holds them, else read on demand and kept."""

    def __init__(self, sites: Sites, load_table: Callable[[], DayTable], path: Path) -> None:
        if not path.exists():
            raise SystemExit(f"{path} is missing. Run scripts/build_place_years.py first.")
        with np.load(path, allow_pickle=False) as saved:
            if str(saved["inputs_sha256"]) != inputs_sha256():
                raise SystemExit(
                    f"{path} was read from older day readings or stations. "
                    "Run scripts/build_place_years.py again."
                )
            self.rule = file_rule(saved)
            self.days = saved["days"]
            self.fed = saved["fed"]
            self.values = saved["readings"]
            keys = zip(saved["region"], saved["latitude"], saved["longitude"], strict=True)
            self.index = {
                place_key(str(region), float(lat), float(lng)): at
                for at, (region, lat, lng) in enumerate(keys)
            }
        self.sites = sites
        self.load_table = load_table
        self.read_on_demand: OrderedDict[tuple[StationRule, PlaceKey], Replay] = OrderedDict()

    def replay(self, rule: StationRule, region: str, lat: float, lng: float) -> Replay:
        key = place_key(region, lat, lng)
        if rule == self.rule and key in self.index:
            return as_replay(self.days, self.fed, self.values[:, self.index[key]])
        kept = self.read_on_demand
        if (rule, key) in kept:
            kept.move_to_end((rule, key))
            return kept[(rule, key)]
        where = readings.history_place(region, lat, lng, self.sites)
        values = read_place(self.load_table(), self.days, where, rule)
        kept[(rule, key)] = as_replay(self.days, self.fed, values)
        if len(kept) > ON_DEMAND_PLACES_KEPT:
            kept.popitem(last=False)
        return kept[(rule, key)]
