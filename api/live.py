"""Live NEA readings for the risk map: today's heat, rain, haze and flood alerts.

A background thread refreshes one snapshot every REFRESH_SECONDS from the data.gov.sg
real-time APIs (docs/reference/data-gov-sg-api.md), so map requests never wait on NEA.
The thread starts on the first /api/map/live request. Without an API key the live layer
reports itself unavailable and the map keeps working from committed history.

Reads  DATA_GOV_SG_API_KEY (environment or .env at the repo root)
"""

from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from dgs import DgsClient  # noqa: E402

SGT = ZoneInfo("Asia/Singapore")
REFRESH_SECONDS = 300
WORK_START_HOUR, WORK_END_HOUR = 7, 19
WBGT_REST_BREAK_C = 32.0  # MOM: paid 10-minute rest breaks for heavy outdoor work from here up
READING_HOURS = 0.25  # WBGT reports every 15 minutes
PSI_MEASURE = "psi_twenty_four_hourly"


def to_float(value: object) -> float | None:
    """Readings can be missing or the string "NA" when a station has a gap."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def in_work_hours(timestamp: str) -> bool:
    moment = datetime.fromisoformat(timestamp).astimezone(SGT)
    return WORK_START_HOUR <= moment.hour < WORK_END_HOUR


def fetch_haze(client: DgsClient, day: str) -> dict:
    """Per PSI region: the day's highest 24-hour PSI so far, and the latest hourly reading."""
    pages = client.get_all_pages("psi", {"date": day}) or []
    regions: dict[str, dict] = {}
    for page in pages:
        for item in page.get("items", []):
            for region, value in item.get("readings", {}).get(PSI_MEASURE, {}).items():
                psi = to_float(value)
                if psi is None:
                    continue
                entry = regions.setdefault(region, {"max_today": psi, "latest": psi})
                entry["max_today"] = max(entry["max_today"], psi)
                entry["latest"] = psi
                entry["latest_at"] = item["timestamp"]
    return regions


def fetch_heat(client: DgsClient, day: str) -> list[dict]:
    """Per WBGT station: work hours at or above 32°C so far today, and the latest reading."""
    pages = client.get_all_pages("weather", {"api": "wbgt", "date": day}) or []
    stations: dict[str, dict] = {}
    for page in pages:
        for record in page.get("records", []):
            for reading in record["item"]["readings"]:
                wbgt = to_float(reading.get("wbgt"))
                if wbgt is None:
                    continue
                station = stations.setdefault(
                    reading["station"]["id"],
                    {
                        "id": reading["station"]["id"],
                        "name": reading["station"]["name"],
                        "lat": float(reading["location"]["latitude"]),
                        "lng": float(reading["location"]["longitude"]),
                        "hours_ge_32_today": 0.0,
                        "latest": wbgt,
                    },
                )
                if wbgt >= WBGT_REST_BREAK_C and in_work_hours(record["datetime"]):
                    station["hours_ge_32_today"] += READING_HOURS
                station["latest"] = wbgt
                station["latest_at"] = record["datetime"]
    return sorted(stations.values(), key=lambda s: s["id"])


def fetch_rain(client: DgsClient, day: str) -> list[dict]:
    """Per rain gauge: the wettest work hour so far today (mm), and the latest 5-minute reading."""
    pages = client.get_all_pages("rainfall", {"date": day}) or []
    locations: dict[str, dict] = {}
    by_hour: dict[tuple[str, str], float] = {}
    latest: dict[str, dict] = {}
    for page in pages:
        for station in page.get("stations", []):
            locations[station["id"]] = {
                "name": station["name"],
                "lat": float(station["location"]["latitude"]),
                "lng": float(station["location"]["longitude"]),
            }
        for reading in page.get("readings", []):
            timestamp = reading["timestamp"]
            hour = datetime.fromisoformat(timestamp).astimezone(SGT).strftime("%H")
            work = in_work_hours(timestamp)
            for value in reading["data"]:
                rain = to_float(value["value"])
                if rain is None:
                    continue
                if work:
                    key = (value["stationId"], hour)
                    by_hour[key] = by_hour.get(key, 0.0) + rain
                latest[value["stationId"]] = {"mm": rain, "at": timestamp}
    gauges = []
    for station_id, location in sorted(locations.items()):
        hours = [mm for (sid, _), mm in by_hour.items() if sid == station_id]
        gauges.append(
            {
                "id": station_id,
                **location,
                "wettest_work_hour_today": round(max(hours), 1) if hours else 0.0,
                "latest_5min": latest.get(station_id, {}).get("mm", 0.0),
                "latest_at": latest.get(station_id, {}).get("at"),
            }
        )
    return gauges


def fetch_flood_alerts(client: DgsClient) -> list[dict]:
    """Active PUB flood alerts, newest first. The feed starts Oct 2025 and refreshes every 2 min."""
    body = client.get("weather/flood-alerts", {})
    if body is None:
        return []
    records = body.get("data", {}).get("records", []) or body.get("data", {}).get("items", [])
    alerts = []
    for record in records:
        if not isinstance(record, dict):
            continue
        text = {
            key: record[key]
            for key in ("alertType", "type", "location", "description", "message", "datetime", "timestamp")
            if key in record
        }
        alerts.append(text or record)
    return alerts


class LiveFeed:
    """One shared snapshot of today's readings, refreshed by a daemon thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.snapshot: dict = {"available": False, "status": "not started"}

    def ensure_started(self) -> None:
        with self._lock:
            if self._thread is None:
                self.snapshot = {"available": False, "status": "starting"}
                self._thread = threading.Thread(target=self._run, daemon=True, name="live-feed")
                self._thread.start()

    def _run(self) -> None:
        try:
            client = DgsClient()
        except SystemExit as error:
            with self._lock:
                self.snapshot = {"available": False, "status": str(error)}
            return
        while True:
            self._refresh(client)
            threading.Event().wait(REFRESH_SECONDS)

    def _refresh(self, client: DgsClient) -> None:
        day = datetime.now(SGT).date().isoformat()
        feeds: dict[str, str | None] = {}
        result: dict = {"available": True, "status": "ok", "date": day}
        for name, fetch in (
            ("haze", lambda: fetch_haze(client, day)),
            ("heat", lambda: fetch_heat(client, day)),
            ("rain", lambda: fetch_rain(client, day)),
            ("flood_alerts", lambda: fetch_flood_alerts(client)),
        ):
            try:
                result[name] = fetch()
                feeds[name] = None
            except Exception as error:  # one broken feed must not take down the others
                traceback.print_exception(error)
                result[name] = [] if name != "haze" else {}
                feeds[name] = str(error)
        result["feeds"] = feeds
        result["available"] = any(status is None for status in feeds.values())
        result["fetched_at"] = datetime.now(SGT).isoformat(timespec="seconds")
        with self._lock:
            self.snapshot = result

    def read(self) -> dict:
        with self._lock:
            return self.snapshot
