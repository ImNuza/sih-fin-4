"""SafeDay pricing API, admin panel and the public risk map.

Usage:
    ADMIN_USERNAME=admin ADMIN_PASSWORD=... uv run uvicorn api.main:app --reload
    API docs on http://localhost:8000/docs, admin panel on http://localhost:8000/admin/,
    risk map on http://localhost:8000/map/

Reads  data/processed/region_hazard_readings.csv    (from scripts/region_hazard_readings.py)
       data/processed/map_static.json              (from scripts/build_map_static.py)
       api/default_tariff.json                     (the first tariff, when the database is empty)
Writes the tariff database at DATABASE_URL         (default sqlite:///api/tariff.db)
"""

from __future__ import annotations

import csv
import json
import os
import secrets
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from api import calculator, store
from api.live import LiveFeed
from api.calculator import History, Readings
from api.models import (
    Assessment,
    AssessRequest,
    Choice,
    HazardChoice,
    Options,
    Preview,
    PreviewRequest,
    Quote,
    QuoteRequest,
    SavedTariff,
    Tariff,
    TariffChange,
)

API_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_DIR.parent
HISTORY_PATH = REPO_ROOT / "data" / "processed" / "region_hazard_readings.csv"
MAP_STATIC_PATH = REPO_ROOT / "data" / "processed" / "map_static.json"
MAP_BUILDINGS_PATH = REPO_ROOT / "data" / "processed" / "map_buildings.json"
DEFAULT_TARIFF_PATH = API_DIR / "default_tariff.json"
DEFAULT_DATABASE_URL = f"sqlite:///{API_DIR / 'tariff.db'}"


def load_history(path: Path) -> History:
    if not path.exists():
        raise SystemExit(f"{path} is missing. Run scripts/region_hazard_readings.py first.")
    counts: dict[str, dict[str, list[tuple[float, int]]]] = defaultdict(lambda: defaultdict(list))
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            counts[row["region"]][row["hazard"]].append((float(row["reading"]), int(row["days"])))
    return {
        region: {
            hazard: Readings(np.array([v for v, _ in rows]), np.array([d for _, d in rows]))
            for hazard, rows in by_hazard.items()
        }
        for region, by_hazard in counts.items()
    }


def admin_login_from_env() -> tuple[str, str]:
    username, password = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        raise SystemExit("Set ADMIN_USERNAME and ADMIN_PASSWORD to start the API.")
    return username, password


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.admin_login = admin_login_from_env()
    app.state.history = load_history(HISTORY_PATH)
    if not MAP_STATIC_PATH.exists():
        raise SystemExit(f"{MAP_STATIC_PATH} is missing. Run scripts/build_map_static.py first.")
    app.state.map_static = json.loads(MAP_STATIC_PATH.read_text())
    app.state.live = LiveFeed()
    app.state.db = store.connect(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    if store.latest(app.state.db) is None:
        tariff = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
        store.save(app.state.db, tariff, saved_by="default")
    yield
    app.state.db.dispose()


app = FastAPI(title="SafeDay pricing API", lifespan=lifespan)
basic_auth = HTTPBasic(auto_error=False)


@app.exception_handler(calculator.UnknownKey)
def unknown_key(_: Request, error: calculator.UnknownKey) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})


@app.exception_handler(calculator.MissingHistory)
def missing_history(_: Request, error: calculator.MissingHistory) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(error)}
    )


def history(request: Request) -> History:
    return request.app.state.history


def saved_tariff(request: Request) -> SavedTariff:
    return store.latest(request.app.state.db)


def current_tariff(saved: Annotated[SavedTariff, Depends(saved_tariff)]) -> Tariff:
    return saved.tariff


def admin(
    request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)]
) -> str:
    # No WWW-Authenticate header on purpose: it would make browsers open their own login box
    # over the admin panel's login form.
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin login required")
    username, password = request.app.state.admin_login
    valid_username = secrets.compare_digest(credentials.username.encode(), username.encode())
    valid_password = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not (valid_username and valid_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    return credentials.username


HistoryDep = Annotated[History, Depends(history)]
TariffDep = Annotated[Tariff, Depends(current_tariff)]
AdminDep = Annotated[str, Depends(admin)]


@app.get("/api/options")
def options(tariff: TariffDep, history: HistoryDep) -> Options:
    """What a customer can choose from, and the readings a payout check takes."""
    hazards_with_history = {hazard for region in history.values() for hazard in region}
    return Options(
        regions=sorted(history),
        products=[Choice(key=p.key, label=p.label) for p in tariff.products],
        tiers=[Choice(key=t.key, label=t.label) for t in tariff.tiers],
        hazards=[
            HazardChoice(
                key=h.key,
                label=h.label,
                reading=h.reading,
                has_history=h.key in hazards_with_history,
            )
            for h in tariff.hazards
        ],
    )


@app.post("/api/quote")
def quote(request: QuoteRequest, tariff: TariffDep, history: HistoryDep) -> Quote:
    """Weekly premium and payout of every tier, for one region and product."""
    return calculator.quote(tariff, history, request.region, request.product)


@app.post("/api/assess")
def assess(request: AssessRequest, tariff: TariffDep) -> Assessment:
    """Loss score of one day and the payout it brings on the chosen tier."""
    return calculator.assess(tariff, request.product, request.tier, request.readings)


def nearest_reading(stations: list[dict], lat: float, lng: float, field: str) -> float:
    """The reading at the station closest to a site, 0 when no station reports."""
    if not stations:
        return 0.0
    closest = min(stations, key=lambda s: (s["lat"] - lat) ** 2 + (s["lng"] - lng) ** 2)
    return float(closest[field])


@app.get("/api/map/static")
def map_static() -> FileResponse:
    """Geography, exposure and hazard history the risk map draws: one static bundle."""
    return FileResponse(MAP_STATIC_PATH, media_type="application/json")


@app.get("/api/map/buildings")
def map_buildings() -> FileResponse:
    """HDB block footprints near hawker centres, for the city view. Heights are nominal."""
    if not MAP_BUILDINGS_PATH.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "map_buildings.json is missing. Run scripts/build_map_static.py."
        )
    return FileResponse(MAP_BUILDINGS_PATH, media_type="application/json")


@app.get("/api/map/quotes")
def map_quotes(tariff: TariffDep, history: HistoryDep, product: str = "cooked_food") -> dict:
    """Quotes for every region at once, with the per-hazard loss-day split and pricing loads."""
    chosen = calculator.find(tariff.products, product, "product")
    return {
        "product": product,
        "pricing": tariff.pricing,
        "hazard_labels": {h.key: h.label for h in tariff.hazards},
        "quotes": {
            region: calculator.quote(tariff, history, region, product) for region in sorted(history)
        },
        "loss_day_parts": {
            region: {
                key: round(days, 4)
                for key, days in calculator.loss_day_parts(tariff, chosen, history[region]).items()
            }
            for region in sorted(history)
        },
    }


@app.get("/api/map/live")
def map_live(request: Request, tariff: TariffDep, product: str = "cooked_food") -> dict:
    """Today's NEA readings and the loss score they give each hawker centre right now.

    The first call starts the background refresh; poll until `available` is true.
    Flood alerts are listed but not scored: the PUB feed names roads, not coordinates.
    """
    live: LiveFeed = request.app.state.live
    live.ensure_started()
    snapshot = live.read()
    if not snapshot.get("available"):
        return snapshot
    haze = snapshot.get("haze") or {}
    heat = snapshot.get("heat") or []
    rain = snapshot.get("rain") or []
    first_tier = tariff.tiers[0].key
    losses = []
    for centre in request.app.state.map_static["hawker_centres"]:
        readings = {
            "haze": float(haze.get(centre["region"], {}).get("max_today", 0.0)),
            "rain": nearest_reading(rain, centre["lat"], centre["lng"], "wettest_work_hour_today"),
            "heat": nearest_reading(heat, centre["lat"], centre["lng"], "hours_ge_32_today"),
        }
        assessment = calculator.assess(tariff, product, first_tier, readings)
        losses.append({"loss_percent": assessment.loss_percent, "readings": readings})
    return {**snapshot, "product": product, "hawker_losses": losses}


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/map/")


@app.get("/api/admin/tariff")
def get_tariff(_: AdminDep, saved: Annotated[SavedTariff, Depends(saved_tariff)]) -> SavedTariff:
    return saved


@app.put("/api/admin/tariff")
def put_tariff(
    change: TariffChange,
    username: AdminDep,
    saved: Annotated[SavedTariff, Depends(saved_tariff)],
    history: HistoryDep,
    request: Request,
) -> SavedTariff:
    """Save a new tariff version, made from the latest one. Every region and product must price."""
    if change.based_on_version != saved.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{saved.saved_by} saved version {saved.version} after you started. "
            "Reload to see it, then make your change again.",
        )
    calculator.check_prices(change.tariff, history)
    return store.save(request.app.state.db, change.tariff, saved_by=username)


@app.post("/api/admin/preview")
def preview(request: PreviewRequest, _: AdminDep, history: HistoryDep) -> Preview:
    """Quote and payouts of an unsaved tariff, so an admin sees a change before saving it."""
    tariff = request.tariff
    return Preview(
        quote=calculator.quote(tariff, history, request.region, request.product),
        assessments=[
            calculator.assess(tariff, request.product, tier.key, request.readings)
            for tier in tariff.tiers
        ],
    )


app.mount("/admin", StaticFiles(directory=API_DIR / "admin", html=True), name="admin")
app.mount("/map", StaticFiles(directory=API_DIR / "map", html=True), name="map")
