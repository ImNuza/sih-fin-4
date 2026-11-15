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

A station that did not report is skipped, never read as a dry or cool day. A hazard with no
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

from api.calculator import Sites, km_between
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
Day = dict[str, dict[str, float]]


@dataclass(frozen=True)
class Place:
    region: str
    gauges: tuple[str, ...]  # rain gauges a reading may take, nearest first
    heat_stations: tuple[str, ...]  # WBGT stations a reading may take, nearest first


@dataclass
class SiteReadings:
    readings: dict[str, float] = field(default_factory=dict)
    basis: dict[str, str] = field(default_factory=dict)
    waiting_for: list[str] = field(default_factory=list)


def eligible(stations: Iterable[Station], lat: float, lng: float) -> tuple[str, ...]:
    """The nearest station and every other station within NEIGHBOUR_RADIUS_KM, nearest first."""
    by_distance = sorted(
        (km_between(lat, lng, station_lat, station_lng), station_id)
        for station_id, station_lat, station_lng in stations
    )
    return tuple(
        station_id
        for rank, (km, station_id) in enumerate(by_distance)
        if rank == 0 or km <= NEIGHBOUR_RADIUS_KM
    )


def place(
    region: str, lat: float, lng: float, gauges: Iterable[Station], heat_stations: Iterable[Station]
) -> Place:
    return Place(region, eligible(gauges, lat, lng), eligible(heat_stations, lat, lng))


def history_place(region: str, lat: float, lng: float, sites: Sites) -> Place:
    """A place ranked against the stations the price reads (site_hazard_readings.csv)."""

    def stations(hazard: str) -> list[Station]:
        return [(s.key, s.latitude, s.longitude) for s in sites.get(hazard, [])]

    return place(region, lat, lng, stations("rain"), stations("heat"))


def stations_read(tariff: Tariff) -> tuple[int, int]:
    """How many rain gauges and WBGT stations a reading takes: as many as the price reads."""
    used = {hazard.key: hazard.sites_used for hazard in tariff.hazards}
    return used.get("rain", RAIN_GAUGES_READ), used.get("heat", HEAT_STATIONS_READ)


def described(chosen: list[str], passed_over: list[str]) -> str:
    named = chosen[0] if len(chosen) == 1 else f"median of {', '.join(chosen)}"
    if passed_over:
        return f"{named} ({', '.join(passed_over)} did not report)"
    return f"{named} (nearest)" if len(chosen) == 1 else named


def station_reading(
    day: Day, kind: str, stations: tuple[str, ...], count: int
) -> tuple[float | None, str]:
    """One hazard's reading from the first count stations that reported. None: waits for data."""
    name = STATION_NAMES[kind]
    if not stations:
        return None, f"no {name} in the network"
    values, silent = day.get(kind, {}), day.get(f"{kind}_missing", {})
    chosen: list[str] = []
    passed_over: list[str] = []
    for station_id in stations:
        if len(chosen) == count:
            break
        (passed_over if station_id in silent else chosen).append(station_id)
    if chosen:
        value = statistics.median(values.get(station_id, 0.0) for station_id in chosen)
        return value, described(chosen, passed_over)
    nearest = stations[0]
    mss = day.get(f"{kind}_mss", {})
    if nearest in mss:
        radius = f"{NEIGHBOUR_RADIUS_KM:g} km"
        return mss[nearest], f"MSS daily record for {nearest} (no {name} within {radius} reported)"
    return None, f"{nearest} and every {name} within {NEIGHBOUR_RADIUS_KM:g} km did not report"


def haze_reading(day: Day, region: str) -> tuple[float | None, str]:
    regions = day.get("haze", {})
    if region in regions:
        return regions[region], f"{region} region"
    if regions:
        names = sorted(regions)
        value = statistics.median(regions[name] for name in names)
        return value, f"median of {', '.join(names)} ({region} did not report)"
    return None, "no PSI region reported"


def site_readings(day: Day, where: Place, gauges_read: int, heat_read: int) -> SiteReadings:
    """A place's readings for one day, the rule behind each, and the hazards still waiting."""
    found = {
        "haze": haze_reading(day, where.region),
        "rain": station_reading(day, "rain", where.gauges, gauges_read),
        "heat": station_reading(day, "heat", where.heat_stations, heat_read),
    }
    site = SiteReadings()
    for hazard, (value, basis) in found.items():
        site.basis[hazard] = basis
        if value is None:
            site.waiting_for.append(hazard)
        else:
            site.readings[hazard] = value
    return site


def day_readings_at(
    day: Day, where: Place, gauges_read: int, heat_read: int = HEAT_STATIONS_READ
) -> dict[str, float]:
    """A place's readings for a replay or a live score, where a hazard that would wait reads 0."""
    found = site_readings(day, where, gauges_read, heat_read).readings
    return {hazard: found.get(hazard, 0.0) for hazard in HAZARDS}
