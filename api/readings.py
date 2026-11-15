"""The one rule for which readings a place is paid on, used by every payout, live score and replay.

Stations are ranked by distance from the place. A place may read its nearest station and any
other station within NEIGHBOUR_RADIUS_KM, nearest first:

    haze  the highest 24-hour PSI of the day in the place's PSI region, else the median of the
          regions that reported
    rain  the median of the wettest work hour at the first gauges that reported, as many as the
          tariff's rain hazard prices from (sites_used, 3 in the default tariff); if none
          reported, the MSS daily record of the nearest gauge
    heat  work hours at WBGT 32°C or more at the first stations that reported, as many as the
          heat hazard prices from (sites_used, 1 in the default tariff), median when more than 1

A station that did not report is skipped, never read as a dry or cool day. A station the tariff
puts on hold (a hazard's stations_on_hold) is skipped too, on every day: it leaves the ranking,
so the next nearest station becomes the place's nearest, however far it is. A hazard with no
reading waits for data: a payout run pays the day once the data arrives, and a replay or live
score reads it as 0. Every reading keeps its basis, the rule that gave it in plain words.

A day is {kind: {site: value}} as in data/processed/day_readings.csv.gz: haze, rain and heat
values, rain_missing and heat_missing for the stations that did not report, and rain_mss. A
station that reported but has no value row read 0. The stations are the ones the price reads
(site_hazard_readings.csv), so a place is priced and paid from the same network.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field

from api.calculator import km_between
from api.models import Tariff

# 90% of the priced rain gauges and WBGT stations have another station within 2.9 km and 4.1 km
# (data/processed/site_hazard_readings.csv, checked 15 Nov 2026), so 5 km keeps a neighbour local.
NEIGHBOUR_RADIUS_KM = 5.0
# For a tariff without the hazard, whose reading no payout uses.
RAIN_GAUGES_READ = 3
HEAT_STATIONS_READ = 1
HAZARDS = ("haze", "rain", "heat")
STATION_NAMES = {"rain": "gauge", "heat": "WBGT station"}

Station = tuple[str, float, float]  # id, latitude, longitude
Ranked = tuple[tuple[str, float], ...]  # (id, km from the place), nearest first
Day = dict[str, dict[str, float]]


@dataclass(frozen=True)
class Site:
    """One NEA station (or, for haze, PSI region) of the network the price reads, and where."""

    key: str
    region: str
    latitude: float
    longitude: float


Sites = dict[str, list[Site]]


@dataclass(frozen=True)
class Place:
    region: str
    gauges: Ranked  # every rain gauge, nearest first
    heat_stations: Ranked  # every WBGT station, nearest first

    def ranked(self, kind: str) -> Ranked:
        return self.gauges if kind == "rain" else self.heat_stations


@dataclass(frozen=True)
class StationRule:
    """How a tariff reads stations: how many of each it takes, and which are on hold."""

    gauges_read: int = RAIN_GAUGES_READ
    heat_read: int = HEAT_STATIONS_READ
    regions_on_hold: frozenset[str] = frozenset()
    gauges_on_hold: frozenset[str] = frozenset()
    heat_on_hold: frozenset[str] = frozenset()

    def count(self, kind: str) -> int:
        return self.gauges_read if kind == "rain" else self.heat_read

    def on_hold(self, kind: str) -> frozenset[str]:
        return {
            "haze": self.regions_on_hold, "rain": self.gauges_on_hold, "heat": self.heat_on_hold,
        }[kind]


@dataclass
class SiteReadings:
    readings: dict[str, float] = field(default_factory=dict)
    basis: dict[str, str] = field(default_factory=dict)
    waiting_for: list[str] = field(default_factory=list)


def ranked(stations: Iterable[Station], lat: float, lng: float) -> Ranked:
    """Every station with its distance from the place, nearest first."""
    by_distance = sorted(
        (km_between(lat, lng, station_lat, station_lng), station_id)
        for station_id, station_lat, station_lng in stations
    )
    return tuple((station_id, km) for km, station_id in by_distance)


def eligible(stations: Ranked, on_hold: frozenset[str]) -> tuple[str, ...]:
    """The nearest station not on hold and every other within NEIGHBOUR_RADIUS_KM, nearest first."""
    chosen: list[str] = []
    for station_id, km in stations:
        if station_id in on_hold:
            continue
        if chosen and km > NEIGHBOUR_RADIUS_KM:
            break
        chosen.append(station_id)
    return tuple(chosen)


def place(
    region: str, lat: float, lng: float, gauges: Iterable[Station], heat_stations: Iterable[Station]
) -> Place:
    return Place(region, ranked(gauges, lat, lng), ranked(heat_stations, lat, lng))


def history_place(region: str, lat: float, lng: float, sites: Sites) -> Place:
    """A place ranked against the stations the price reads (site_hazard_readings.csv)."""

    def stations(hazard: str) -> list[Station]:
        return [(s.key, s.latitude, s.longitude) for s in sites.get(hazard, [])]

    return place(region, lat, lng, stations("rain"), stations("heat"))


def station_rule(tariff: Tariff) -> StationRule:
    """How many rain gauges and WBGT stations a reading takes, as many as the price reads, and
    the stations each hazard has on hold."""
    hazards = {hazard.key: hazard for hazard in tariff.hazards}

    def on_hold(key: str) -> frozenset[str]:
        return frozenset(hazards[key].stations_on_hold) if key in hazards else frozenset()

    return StationRule(
        gauges_read=hazards["rain"].sites_used if "rain" in hazards else RAIN_GAUGES_READ,
        heat_read=hazards["heat"].sites_used if "heat" in hazards else HEAT_STATIONS_READ,
        regions_on_hold=on_hold("haze"),
        gauges_on_hold=on_hold("rain"),
        heat_on_hold=on_hold("heat"),
    )


def stations_used(where: Place, kind: str, rule: StationRule) -> list[str]:
    """The stations a reading takes on a day when every station reports."""
    return list(eligible(where.ranked(kind), rule.on_hold(kind))[: rule.count(kind)])


def described(chosen: list[str], passed_over: list[str], held: list[str]) -> str:
    named = chosen[0] if len(chosen) == 1 else f"median of {', '.join(chosen)}"
    notes = []
    if passed_over:
        notes.append(f"{', '.join(passed_over)} did not report")
    if held:
        notes.append(f"{', '.join(held)} on hold")
    if notes:
        return f"{named} ({'; '.join(notes)})"
    return f"{named} (nearest)" if len(chosen) == 1 else named


def held_nearer(stations: Ranked, on_hold: frozenset[str], first: str) -> list[str]:
    """The stations on hold that are nearer than the first station read."""
    nearer = []
    for station_id, _ in stations:
        if station_id == first:
            break
        if station_id in on_hold:
            nearer.append(station_id)
    return nearer


def station_reading(
    day: Day, kind: str, where: Place, rule: StationRule
) -> tuple[float | None, str]:
    """One hazard's reading from the first stations that reported. None: waits for data."""
    name = STATION_NAMES[kind]
    on_hold = rule.on_hold(kind)
    stations = eligible(where.ranked(kind), on_hold)
    if not stations:
        return None, f"no {name} in the network"
    held = held_nearer(where.ranked(kind), on_hold, stations[0])
    values, silent = day.get(kind, {}), day.get(f"{kind}_missing", {})
    count = rule.count(kind)
    chosen: list[str] = []
    passed_over: list[str] = []
    for station_id in stations:
        if len(chosen) == count:
            break
        (passed_over if station_id in silent else chosen).append(station_id)
    if chosen:
        value = statistics.median(values.get(station_id, 0.0) for station_id in chosen)
        return value, described(chosen, passed_over, held)
    nearest = stations[0]
    mss = day.get(f"{kind}_mss", {})
    if nearest in mss:
        radius = f"{NEIGHBOUR_RADIUS_KM:g} km"
        return mss[nearest], f"MSS daily record for {nearest} (no {name} within {radius} reported)"
    return None, f"{nearest} and every {name} within {NEIGHBOUR_RADIUS_KM:g} km did not report"


def haze_reading(day: Day, region: str, on_hold: frozenset[str]) -> tuple[float | None, str]:
    regions = {name: value for name, value in day.get("haze", {}).items() if name not in on_hold}
    if region in regions:
        return regions[region], f"{region} region"
    if regions:
        names = sorted(regions)
        value = statistics.median(regions[name] for name in names)
        why = "on hold" if region in on_hold else "did not report"
        return value, f"median of {', '.join(names)} ({region} {why})"
    return None, "no PSI region reported"


def site_readings(day: Day, where: Place, rule: StationRule) -> SiteReadings:
    """A place's readings for one day, the rule behind each, and the hazards still waiting."""
    found = {
        "haze": haze_reading(day, where.region, rule.regions_on_hold),
        "rain": station_reading(day, "rain", where, rule),
        "heat": station_reading(day, "heat", where, rule),
    }
    site = SiteReadings()
    for hazard, (value, basis) in found.items():
        site.basis[hazard] = basis
        if value is None:
            site.waiting_for.append(hazard)
        else:
            site.readings[hazard] = value
    return site


def day_readings_at(day: Day, where: Place, rule: StationRule) -> dict[str, float]:
    """A place's readings for a replay or a live score, where a hazard that would wait reads 0."""
    found = site_readings(day, where, rule).readings
    return {hazard: found.get(hazard, 0.0) for hazard in HAZARDS}
