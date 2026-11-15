"""What NEA recorded on each past day, per region (haze) and per station (rain, heat).

Reads data/processed/day_readings.csv.gz (scripts/build_day_readings.py), once per process.

A payout needs a reading for every hazard. When a station's feed is missing, site_readings
falls back in this order, and records which rule gave each reading:
1. the nearest station's own reading;
2. the median of up to NEIGHBOURS_FOR_MEDIAN stations that did report, within
   NEIGHBOUR_RADIUS_KM;
3. for rain only, the MSS published daily record of the nearest gauge (its highest 60-minute
   rain of the whole day, which can only be higher than the work-hour value);
4. no reading: the hazard waits for data, so the day can be paid late, never refused.
Haze falls back to the median of the regions that reported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median

from fastapi import HTTPException, Request, status

from api import burn

DayTable = dict[str, dict[str, dict[str, float]]]

# 90% of NEA rain gauges and WBGT stations have another station within 3.1 km and 4.1 km
# (data/processed/map_static.json, checked 15 Nov 2026), so 5 km keeps a neighbour local.
NEIGHBOUR_RADIUS_KM = 5.0
NEIGHBOURS_FOR_MEDIAN = 3
EARTH_RADIUS_KM = 6371.0
STATION_KINDS = {"rain": "rain_stations", "heat": "wbgt_stations"}


@dataclass
class SiteReadings:
    readings: dict[str, float] = field(default_factory=dict)
    basis: dict[str, str] = field(default_factory=dict)
    waiting_for: list[str] = field(default_factory=list)


def day_readings(request: Request) -> DayTable:
    """All historical daily readings, loaded once: {day: {kind: {site: value}}}."""
    if not hasattr(request.app.state, "day_readings"):
        if not burn.DAY_READINGS_PATH.exists():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "day_readings.csv.gz is missing. Run scripts/build_day_readings.py.",
            )
        request.app.state.day_readings = burn.load_day_table()
    return request.app.state.day_readings


def distance_km(lat: float, lng: float, station: dict) -> float:
    d_lat = math.radians(station["lat"] - lat)
    d_lng = math.radians(station["lng"] - lng)
    h = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat)) * math.cos(math.radians(station["lat"]))
         * math.sin(d_lng / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def station_reading(
    day: dict[str, dict[str, float]], kind: str, stations: list[dict], lat: float, lng: float
) -> tuple[float | None, str]:
    """One hazard's reading at a point, and the rule that gave it. None: no reading yet.

    The table leaves out zero rows, so a station that reported but has no row read 0.
    """
    values, silent = day.get(kind, {}), day.get(f"{kind}_missing", {})
    by_distance = sorted(stations, key=lambda station: distance_km(lat, lng, station))
    nearest = by_distance[0]["id"]
    if nearest not in silent:
        return values.get(nearest, 0.0), f"{nearest} (nearest)"
    neighbours = [
        station["id"] for station in by_distance[1:]
        if station["id"] not in silent and distance_km(lat, lng, station) <= NEIGHBOUR_RADIUS_KM
    ][:NEIGHBOURS_FOR_MEDIAN]
    if neighbours:
        value = median(values.get(station_id, 0.0) for station_id in neighbours)
        return value, f"median of {', '.join(neighbours)} ({nearest} did not report)"
    mss = day.get(f"{kind}_mss", {})
    if nearest in mss:
        return mss[nearest], f"MSS daily record for {nearest} ({nearest} did not report)"
    return None, f"{nearest} and every station within {NEIGHBOUR_RADIUS_KM:g} km did not report"


def haze_reading(day: dict[str, dict[str, float]], region: str) -> tuple[float | None, str]:
    regions = day.get("haze", {})
    if region in regions:
        return regions[region], f"{region} region"
    if regions:
        names = sorted(regions)
        value = median(regions[name] for name in names)
        return value, f"median of {', '.join(names)} ({region} did not report)"
    return None, "no PSI region reported"


def site_readings(
    day: dict[str, dict[str, float]], lat: float, lng: float, region: str, map_static: dict
) -> SiteReadings:
    """A place's readings for one day: its region's PSI and its nearest gauge and WBGT station,
    with the fallback rule above for any feed that is missing."""
    site = SiteReadings()
    found = {"haze": haze_reading(day, region)} | {
        kind: station_reading(day, kind, map_static[stations], lat, lng)
        for kind, stations in STATION_KINDS.items()
    }
    for hazard, (value, basis) in found.items():
        site.basis[hazard] = basis
        if value is None:
            site.waiting_for.append(hazard)
        else:
            site.readings[hazard] = value
    return site
