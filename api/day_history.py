"""What NEA recorded on each past day, per region (haze) and per station (rain, heat).

Reads data/processed/day_readings.csv.gz (scripts/build_day_readings.py), once per process.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from api import burn

DayTable = dict[str, dict[str, dict[str, float]]]


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


def nearest_station_id(stations: list[dict], lat: float, lng: float) -> str:
    return min(stations, key=lambda s: (s["lat"] - lat) ** 2 + (s["lng"] - lng) ** 2)["id"]


def centre_readings(day: dict[str, dict[str, float]], centre: dict, map_static: dict) -> dict:
    """One centre's readings for one day: its region's PSI and its nearest gauge and WBGT station.

    The table leaves out zero rain and heat rows, so a station with no row read 0 that day.
    The nearest station is taken from every station, never only from those that reported.
    """
    rain_station = nearest_station_id(map_static["rain_stations"], centre["lat"], centre["lng"])
    heat_station = nearest_station_id(map_static["wbgt_stations"], centre["lat"], centre["lng"])
    return {
        "haze": day.get("haze", {}).get(centre["region"], 0.0),
        "rain": day.get("rain", {}).get(rain_station, 0.0),
        "heat": day.get("heat", {}).get(heat_station, 0.0),
    }
