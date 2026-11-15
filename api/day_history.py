"""What NEA recorded on each past day, per region (haze) and per station (rain, heat).

Read a place's readings from it with api/readings.py, the rule every payout uses, including
its fallbacks when a station's feed is missing.

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
