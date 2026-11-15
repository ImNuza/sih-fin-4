"""SafeDay platform: pricing API, SME and insurer dashboards, risk map and admin panel.

Usage:
    ADMIN_USERNAME=admin ADMIN_PASSWORD=... uv run uvicorn api.main:app --reload
    Site on http://localhost:8000/ (landing, /login/, /dashboard/), risk map on /map/,
    tariff desk on /admin/, API docs on /docs.

Reads  data/processed/site_hazard_readings.csv      (from scripts/region_hazard_readings.py)
       data/processed/map_static.json              (from scripts/build_map_static.py)
       data/processed/hawker_rent.csv              (from scripts/build_hawker_rent.py)
       api/default_tariff.json                     (the first tariff, when the database is empty)
Writes the tariff database at DATABASE_URL         (default sqlite:///api/tariff.db)
"""

from __future__ import annotations

import csv
import json
import os
import re
import secrets
import statistics
from calendar import monthrange
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete as sa_delete
from sqlalchemy import insert as sa_insert
from sqlalchemy import select as sa_select

from api import (
    accounts, burn, calculator, kyc, onboarding, payout_api, paynow_qr, postcodes, readings, store,
    underwriting,
)
from api.accounts import InsurerDep, Registration, SmeDep, UserDep
from api.day_history import day_readings
from api.live import LiveFeed
from api.calculator import BidRecord, History, Readings, Site, Sites
from api.models import (
    Assessment,
    AssessRequest,
    Choice,
    HazardChoice,
    KycRequest,
    KycResult,
    Options,
    Preview,
    PreviewRequest,
    Quote,
    QuoteRequest,
    RentTable,
    SavedTariff,
    Tariff,
    TariffChange,
)

API_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_DIR.parent
HISTORY_PATH = REPO_ROOT / "data" / "processed" / "site_hazard_readings.csv"
MAP_STATIC_PATH = REPO_ROOT / "data" / "processed" / "map_static.json"
MAP_BUILDINGS_PATH = REPO_ROOT / "data" / "processed" / "map_buildings.json"
RENT_PATH = REPO_ROOT / "data" / "processed" / "hawker_rent.csv"
DEFAULT_TARIFF_PATH = API_DIR / "default_tariff.json"
DEFAULT_DATABASE_URL = f"sqlite:///{API_DIR / 'tariff.db'}"


def as_readings(rows: list[tuple[float, int]]) -> Readings:
    return Readings(np.array([value for value, _ in rows]), np.array([days for _, days in rows]))


def load_history(path: Path) -> tuple[History, Sites]:
    """Each hazard's readings pooled per region, and kept per station with its location."""
    if not path.exists():
        raise SystemExit(f"{path} is missing. Run scripts/region_hazard_readings.py first.")
    by_region: dict[str, dict[str, list[tuple[float, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    by_site: dict[tuple[str, str, str, float, float], list[tuple[float, int]]] = defaultdict(list)
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            reading = (float(row["reading"]), int(row["days"]))
            by_region[row["region"]][row["hazard"]].append(reading)
            place = (float(row["latitude"]), float(row["longitude"]))
            by_site[(row["hazard"], row["site"], row["region"], *place)].append(reading)
    history = {
        region: {hazard: as_readings(rows) for hazard, rows in by_hazard.items()}
        for region, by_hazard in by_region.items()
    }
    sites: Sites = defaultdict(list)
    for (hazard, key, region, latitude, longitude), rows in by_site.items():
        sites[hazard].append(Site(key, region, latitude, longitude, as_readings(rows)))
    return history, dict(sites)


def load_rent(path: Path) -> dict[str, BidRecord]:
    if not path.exists():
        raise SystemExit(f"{path} is missing. Run scripts/build_hawker_rent.py first.")
    with path.open(newline="") as file:
        return {
            row["centre"]: BidRecord(
                centre=row["centre"],
                median_bid_sgd=float(row["median_bid_sgd"]) if row["median_bid_sgd"] else None,
                bids=int(row["bids"]),
                basis=row["basis"],
                first_month=row["first_month"] or None,
                last_month=row["last_month"] or None,
            )
            for row in csv.DictReader(file)
        }


def admin_login_from_env() -> tuple[str, str]:
    username, password = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        raise SystemExit("Set ADMIN_USERNAME and ADMIN_PASSWORD to start the API.")
    return username, password


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.admin_login = admin_login_from_env()
    app.state.history, app.state.sites = load_history(HISTORY_PATH)
    if not MAP_STATIC_PATH.exists():
        raise SystemExit(f"{MAP_STATIC_PATH} is missing. Run scripts/build_map_static.py first.")
    app.state.map_static = json.loads(MAP_STATIC_PATH.read_text())
    app.state.places = kyc.load_places(app.state.map_static)
    app.state.centres_by_name = {c["name"]: c for c in app.state.map_static["hawker_centres"]}
    app.state.centre_quotes = {}
    app.state.centres_by_sector = postcodes.centres_by_sector(
        app.state.map_static["hawker_centres"]
    )
    app.state.rent = load_rent(RENT_PATH)
    app.state.live = LiveFeed()
    app.state.db = store.connect(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    try:
        saved = store.latest(app.state.db)
    except ValidationError:
        # Saved before the tariff gained fields (product margins, stations per trigger). Older
        # versions stay in the database; pricing starts again from the default tariff.
        saved = None
    default = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
    if saved is None:
        store.save(app.state.db, default, saved_by="default")
    elif with_new_products := add_missing_products(saved.tariff, default):
        store.save(app.state.db, with_new_products, saved_by="default: new products")
    yield
    app.state.db.dispose()


def add_missing_products(tariff: Tariff, default: Tariff) -> Tariff | None:
    """The saved tariff plus any product the default tariff has and it lacks, or None.

    A saved tariff outlives deploys, so a product added to default_tariff.json (such as
    platform_work) would otherwise never reach a database that already holds a tariff.
    """
    known = {product.key for product in tariff.products}
    missing = [product for product in default.products if product.key not in known]
    if not missing:
        return None
    return tariff.model_copy(update={"products": [*tariff.products, *missing]})


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


def sites(request: Request) -> Sites:
    return request.app.state.sites


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
SavedTariffDep = Annotated[SavedTariff, Depends(saved_tariff)]
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
                first_band=h.bands[0].at_least,
            )
            for h in tariff.hazards
        ],
    )


def centre_place(request: Request, centre: str) -> dict:
    """The NEA hawker centre with this name. Raises 404 for a name the map does not know."""
    place = request.app.state.centres_by_name.get(centre)
    if place is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown hawker centre: {centre}")
    return place


def postcode_point(request: Request, postcode: str) -> dict:
    """The approximate map point of a postcode's area (postcodes.area_point). Raises 422."""
    try:
        return postcodes.area_point(
            postcode,
            request.app.state.centres_by_sector,
            request.app.state.map_static["region_points"],
        )
    except postcodes.UnknownSector as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error


def business_quote(
    request: Request, tariff: Tariff, history: History, product: str, region: str | None,
    centre: str | None = None, postcode: str | None = None,
) -> Quote:
    """The price a business is shown and charged: from the NEA stations nearest its hawker
    centre, else nearest its postcode's area. A business with neither, such as a platform
    worker who works across the island, is priced for its region. Haze is priced for the PSI
    region a payout reads: the centre's map region, the postcode's region (postcodes.region_of).
    """
    sites = request.app.state.sites
    if centre is not None:
        place = centre_place(request, centre)
        return calculator.quote_at(
            tariff, history, sites, place["lat"], place["lng"], product, place["region"]
        )
    if postcode is not None:
        point = postcode_point(request, postcode)
        return calculator.quote_at(
            tariff, history, sites, point["lat"], point["lng"], product, point["region"]
        )
    return calculator.quote(tariff, history, region, product)


@app.post("/api/quote")
def quote(
    body: QuoteRequest,
    request: Request,
    tariff: TariffDep,
    history: HistoryDep,
    sites: Annotated[Sites, Depends(sites)],
) -> Quote:
    """Weekly premium and payout of every tier, for one product, at a region, a map point, a
    hawker centre or a postcode's area. A centre or postcode gives the price a business there
    is charged when it buys."""
    if body.latitude is not None and body.longitude is not None:
        return calculator.quote_at(
            tariff, history, sites, body.latitude, body.longitude, body.product
        )
    return business_quote(
        request, tariff, history, body.product, body.region, body.centre, body.postcode
    )


def rent_table(tariff: Tariff, records: dict[str, BidRecord]) -> RentTable:
    medians = [r.median_bid_sgd for r in records.values() if r.median_bid_sgd is not None]
    fallback = statistics.median(medians)
    return RentTable(
        trading_days_per_month=tariff.rent.trading_days_per_month,
        classes=tariff.rent.classes,
        source=tariff.rent.source,
        all_centre_median_sgd=round(fallback, 2),
        centres={
            name: calculator.centre_rent(tariff, record, fallback)
            for name, record in records.items()
        },
    )


@app.get("/api/rent")
def rent(tariff: TariffDep, request: Request) -> RentTable:
    """Rent class of every hawker centre, from NEA's winning bids, and the tier that covers a
    day's rent. The class sets the recommended tier; the premium still comes from the hazards."""
    return rent_table(tariff, request.app.state.rent)


@app.post("/api/assess")
def assess(request: AssessRequest, tariff: TariffDep) -> Assessment:
    """Loss score of one day and the payout it brings on the chosen tier."""
    return calculator.assess(tariff, request.product, request.tier, request.readings)


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
def map_quotes(
    saved: SavedTariffDep, history: HistoryDep, request: Request, product: str = "cooked_food"
) -> dict:
    """Quotes for every region and every hawker centre at once, with the per-hazard loss-day
    split and pricing loads. A centre's quote is the price a stall there is charged."""
    tariff = saved.tariff
    chosen = calculator.find(tariff.products, product, "product")
    region_parts = {
        region: {
            key: round(days, 4)
            for key, days in calculator.loss_day_parts(tariff, chosen, history[region]).items()
        }
        for region in sorted(history)
    }
    centres = centre_quotes(saved, history, request, product, region_parts)
    return {
        "product": product,
        "pricing": tariff.pricing,
        "hazard_labels": {h.key: h.label for h in tariff.hazards},
        # Enough for the map to build a control per hazard, however the tariff desk changes them.
        "hazards": [
            {
                "key": h.key,
                "label": h.label,
                "reading": h.reading,
                "binary": len(h.bands) == 1 and h.bands[0].at_least == 1,
                "max": h.bands[-1].at_least * 1.5,
            }
            for h in tariff.hazards
        ],
        "quotes": {
            region: calculator.quote(tariff, history, region, product) for region in sorted(history)
        },
        "loss_day_parts": region_parts,
        # Each hawker centre priced as a stall there is charged (business_quote), with its parts.
        "centres": {name: priced for name, (priced, _) in centres.items()},
        "centre_loss_day_parts": {name: parts for name, (_, parts) in centres.items()},
    }


def priced_centres(
    saved: SavedTariff, history: History, request: Request, product: str
) -> dict[str, Quote]:
    """Every hawker centre's business_quote, priced once per saved tariff version and product:
    pricing all of them takes about half a second. A new version starts a fresh cache."""
    key = (saved.version, product)
    cache = request.app.state.centre_quotes
    if key not in cache:
        if any(version != saved.version for version, _ in cache):
            cache = request.app.state.centre_quotes = {}
        cache[key] = {
            centre["name"]: business_quote(
                request, saved.tariff, history, product, None, centre=centre["name"]
            )
            for centre in request.app.state.map_static["hawker_centres"]
        }
    return cache[key]


def centre_quotes(
    saved: SavedTariff, history: History, request: Request, product: str,
    region_parts: dict[str, dict[str, float]],
) -> dict[str, tuple[Quote, dict[str, float]]]:
    """Every hawker centre's quote from its nearest stations, and its loss days per hazard: the
    stations' share where they price the hazard, the region's share for the rest."""
    out = {}
    priced_by_name = priced_centres(saved, history, request, product)
    for centre in request.app.state.map_static["hawker_centres"]:
        priced = priced_by_name[centre["name"]]
        parts = dict(region_parts[centre["region"]])
        parts.update({risk.hazard: risk.loss_days for risk in priced.local_risks})
        out[centre["name"]] = (priced, parts)
    return out




SG_LAT = {"ge": 1.1, "le": 1.6}
SG_LNG = {"ge": 103.5, "le": 104.2}


class ScenarioRequest(BaseModel):
    lat: float = Field(**SG_LAT)
    lng: float = Field(**SG_LNG)
    radius_km: float = Field(gt=0.05, le=15)
    readings: dict[str, float]
    extra_days_per_year: float = Field(default=5, ge=0, le=60)
    product: str = "cooked_food"
    tier: str = "tier_2"


SCENARIO_PRICES = (
    "expected_loss_days", "stressed_loss_days", "weekly_baseline_sgd", "weekly_stressed_sgd",
)


@app.post("/api/map/scenario")
def map_scenario(
    body: ScenarioRequest, saved: SavedTariffDep, history: HistoryDep, request: Request
) -> dict:
    """Price a what-if day inside a drawn circle.

    The readings score one day's loss and payout (as /api/assess). Each centre's premium is
    its own, from its nearest stations (business_quote), stressed by assuming days like this
    hit it extra_days_per_year more times a year on top of its NEA history, then priced by
    the same engine as every quote.
    """
    tariff = saved.tariff
    assessment = calculator.assess(tariff, body.product, body.tier, body.readings)
    day_loss = assessment.loss_percent / 100
    tier = calculator.find(tariff.tiers, body.tier, "tier")
    centres = [
        centre
        for centre in request.app.state.map_static["hawker_centres"]
        if calculator.km_between(body.lat, body.lng, centre["lat"], centre["lng"]) <= body.radius_km
    ]

    priced_by_name = priced_centres(saved, history, request, body.product) if centres else {}

    def priced_centre(centre: dict) -> dict:
        priced = priced_by_name[centre["name"]]
        baseline = next(t for t in priced.tiers if t.tier == body.tier)
        stressed_days = min(
            priced.expected_loss_days + body.extra_days_per_year * day_loss,
            tier.max_paid_days_per_year,
        )
        stressed_yearly = calculator.yearly_premium(
            stressed_days * tier.daily_payout_sgd, tariff.pricing
        )
        return {
            "expected_loss_days": priced.expected_loss_days,
            "stressed_loss_days": round(stressed_days, 2),
            "weekly_baseline_sgd": baseline.weekly_premium_sgd,
            "weekly_stressed_sgd": round(stressed_yearly / calculator.WEEKS_PER_YEAR, 2),
        }

    affected = [
        {
            "name": centre["name"],
            "stalls": centre["food_stalls"],
            "region": centre["region"],
            **priced_centre(centre),
        }
        for centre in centres
    ]
    stalls = sum(centre["food_stalls"] for centre in centres)
    return {
        "assessment": assessment,
        "centres": {a["name"]: {k: a[k] for k in SCENARIO_PRICES} for a in affected},
        "affected": affected,
        "totals": {
            "centres": len(centres),
            "stalls": stalls,
            "payout_today_sgd": round(assessment.payout_sgd * stalls, 2),
            "weekly_premium_baseline_sgd": round(
                sum(c["stalls"] * c["weekly_baseline_sgd"] for c in affected), 2
            ),
            "weekly_premium_stressed_sgd": round(
                sum(c["stalls"] * c["weekly_stressed_sgd"] for c in affected), 2
            ),
        },
    }


@app.post("/api/map/kyc")
def map_kyc(body: KycRequest, tariff: TariffDep, request: Request) -> KycResult:
    """Read a shop owner's description, and an optional photo, into a product and a place.

    Advisory only: the owner confirms both on the map before /api/map/scenario prices anything,
    so every payout still comes from the tariff and the day's readings. Nothing is stored.
    """
    return kyc.read_shop(body, tariff.products, request.app.state.places)


def known_region(region: str, history: History) -> None:
    if region not in history:
        raise calculator.UnknownKey(f"Unknown region: {region}")


def centre_places(request: Request) -> list[readings.Place]:
    """Every hawker centre's place for reading history, in map order, ranked once per process."""
    if not hasattr(request.app.state, "centre_places"):
        request.app.state.centre_places = [
            readings.history_place(c["region"], c["lat"], c["lng"], request.app.state.sites)
            for c in request.app.state.map_static["hawker_centres"]
        ]
    return request.app.state.centre_places


def centre_burn_site(
    centre: str, request: Request, tariff: Tariff, history: History, product: str
) -> tuple[readings.Place, Quote]:
    """A hawker centre's place for the replay and the price a stall there is charged."""
    place = centre_place(request, centre)
    where = readings.history_place(
        place["region"], place["lat"], place["lng"], request.app.state.sites
    )
    return where, business_quote(request, tariff, history, product, None, centre=centre)


def point_burn_site(
    lat: float, lng: float, region: str, request: Request, tariff: Tariff, history: History,
    product: str,
) -> tuple[readings.Place, Quote]:
    """A point's place for the replay and its price from its nearest stations, with haze
    priced for the region it is paid on."""
    known_region(region, history)
    sites = request.app.state.sites
    where = readings.history_place(region, lat, lng, sites)
    return where, calculator.quote_at(tariff, history, sites, lat, lng, product, region)


def region_burn_site(
    lat: float, lng: float, region: str, request: Request, tariff: Tariff, history: History,
    product: str,
) -> tuple[readings.Place, Quote]:
    """A platform worker's place for the replay, at its region's point as a payout reads it,
    and the region price they are charged."""
    where = readings.history_place(region, lat, lng, request.app.state.sites)
    return where, calculator.quote(tariff, history, region, product)


@app.get("/api/map/burn")
def map_burn(
    request: Request,
    tariff: TariffDep,
    history: HistoryDep,
    centre: str | None = None,
    lat: Annotated[float | None, Query(**SG_LAT)] = None,
    lng: Annotated[float | None, Query(**SG_LNG)] = None,
    region: str | None = None,
    product: str = "cooked_food",
    tier: str = "tier_2",
    takings: float = 500.0,
) -> dict:
    """One business's last ten years: what it lost and what this cover would have paid.

    The business is a hawker centre, a point (lat, lng) in a PSI region, such as the area point
    of a shop's postcode, or a region alone, for a platform worker: read at the region's point
    and priced for the region. Each day is read as a payout reads it (api/readings.py), and a
    hazard a payout would wait for reads 0. The price is the one the business is charged. takings
    is the business's own normal daily sales in SGD; every loss figure scales with it, the
    payouts not.
    """
    if not 50 <= takings <= 20000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "takings must be 50 to 20000")
    if centre is not None:
        site, priced = centre_burn_site(centre, request, tariff, history, product)
    elif lat is not None and lng is not None and region is not None:
        site, priced = point_burn_site(lat, lng, region, request, tariff, history, product)
    elif lat is None and lng is None and region is not None:
        known_region(region, history)
        lat, lng = request.app.state.map_static["region_points"][region]
        site, priced = region_burn_site(lat, lng, region, request, tariff, history, product)
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a centre, lat, lng and region, or a region"
        )
    tier_quote = next((t for t in priced.tiers if t.tier == tier), None)
    if tier_quote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tier: {tier}")
    result = burn.site_burn(
        day_readings(request), site, tariff, product, tier, takings, tier_quote.yearly_premium_sgd
    )
    return {
        "centre": centre,
        "lat": lat if centre is None else None,
        "lng": lng if centre is None else None,
        "region": site.region,
        "product": product,
        "tier": tier,
        "tier_label": tier_quote.label,
        "daily_payout_sgd": tier_quote.daily_payout_sgd,
        "weekly_premium_sgd": tier_quote.weekly_premium_sgd,
        **result,
    }


@app.get("/api/map/day")
def map_day(
    date: str, request: Request, tariff: TariffDep, product: str = "cooked_food"
) -> dict:
    """What NEA recorded on one past day, and the loss score it gives each hawker centre.

    Every centre is scored on its own readings, as a payout that day would read them
    (api/readings.py), a hazard it would wait for read as 0: hawker_losses is in map order, like
    /api/map/live. haze, rain and heat are the worst island readings, for the map's sliders and
    its note.
    """
    table = day_readings(request)
    available = sorted(table)
    if date not in table:
        return {
            "date": date,
            "available": {"min": available[0], "max": available[-1]},
            "found": False,
        }
    day = table[date]

    def worst(kind: str) -> dict:
        sites = day.get(kind, {})
        if not sites:
            return {"value": 0, "site": None}
        site = max(sites, key=sites.get)
        return {"value": sites[site], "site": site}

    losses = []
    stations_read = readings.stations_read(tariff)
    for where in centre_places(request):
        centre_readings = readings.day_readings_at(day, where, *stations_read)
        assessment = calculator.assess(tariff, product, tariff.tiers[0].key, centre_readings)
        losses.append({"loss_percent": assessment.loss_percent, "readings": centre_readings})
    return {
        "date": date,
        "available": {"min": available[0], "max": available[-1]},
        "found": True,
        "product": product,
        "haze": worst("haze"),
        "rain": worst("rain"),
        "heat": worst("heat"),
        "haze_by_region": day.get("haze", {}),
        "hawker_losses": losses,
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
    today = LiveToday(snapshot)
    losses = [
        live_loss(today, tariff, product, centre["region"], centre["lat"], centre["lng"])
        for centre in request.app.state.map_static["hawker_centres"]
    ]
    return {**snapshot, "product": product, "hawker_losses": losses}


@app.get("/api/map/live/at")
def map_live_at(
    request: Request,
    tariff: TariffDep,
    history: HistoryDep,
    lat: Annotated[float, Query(**SG_LAT)],
    lng: Annotated[float, Query(**SG_LNG)],
    region: str,
    product: str = "cooked_food",
) -> dict:
    """Today's loss score at one point in a PSI region, scored as /api/map/live scores a centre.

    Returns the feed's status until `available` is true, then one hawker_losses entry with the
    feed's fetched_at.
    """
    known_region(region, history)
    live: LiveFeed = request.app.state.live
    live.ensure_started()
    snapshot = live.read()
    if not snapshot.get("available"):
        return snapshot
    return {
        "available": True,
        "fetched_at": snapshot.get("fetched_at"),
        "product": product,
        **live_loss(LiveToday(snapshot), tariff, product, region, lat, lng),
    }


class LiveToday:
    """One live snapshot as a day of api/readings.py: a listed gauge that is not reporting is
    marked missing, and only WBGT stations that sent a reading today are listed."""

    def __init__(self, snapshot: dict) -> None:
        gauges = snapshot.get("rain") or []
        stations = snapshot.get("heat") or []
        self.gauges = [(g["id"], g["lat"], g["lng"]) for g in gauges]
        self.heat_stations = [(s["id"], s["lat"], s["lng"]) for s in stations]
        self.day = {
            "haze": {
                region: float(values.get("max_today", 0.0))
                for region, values in (snapshot.get("haze") or {}).items()
            },
            "rain": {g["id"]: float(g["wettest_work_hour_today"]) for g in gauges},
            "rain_missing": {g["id"]: 1.0 for g in gauges if not g.get("reporting", True)},
            "heat": {s["id"]: float(s["hours_ge_32_today"]) for s in stations},
        }


def live_loss(
    today: LiveToday, tariff: Tariff, product: str, region: str, lat: float, lng: float
) -> dict:
    """Loss score from today's readings at a place, read as a payout reads them
    (api/readings.py), with no MSS record live: a hazard with nothing reporting reads 0."""
    where = readings.place(region, lat, lng, today.gauges, today.heat_stations)
    now = readings.day_readings_at(today.day, where, *readings.stations_read(tariff))
    assessment = calculator.assess(tariff, product, tariff.tiers[0].key, now)
    return {"loss_percent": assessment.loss_percent, "readings": now}


class PolicyRequest(BaseModel):
    tier: str
    product: str | None = None


def policy_values(
    priced: Quote, user_id: int, region: str, centre: str | None, product: str, tier_key: str
) -> dict:
    """A policies row for one tier of a business_quote. Raises on an unknown tier."""
    tier = next((t for t in priced.tiers if t.tier == tier_key), None)
    if tier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tier: {tier_key}")
    return {
        "user_id": user_id,
        "tier": tier.tier,
        "tier_label": tier.label,
        "product": product,
        "region": region,
        "centre": centre,
        "weekly_premium_sgd": tier.weekly_premium_sgd,
        "daily_payout_sgd": tier.daily_payout_sgd,
        "max_paid_days_per_year": round(tier.max_payout_per_year_sgd / tier.daily_payout_sgd),
        "started_at": datetime.now(UTC),
    }


@app.post("/api/policies")
def buy_policy(
    body: PolicyRequest, user: SmeDep, tariff: TariffDep, history: HistoryDep, request: Request
) -> dict:
    """Start a cover for the signed-in business, priced server-side at its hawker centre or its
    shop's postcode (business_quote), else its region.

    Refused while an underwriter is reviewing the business's application, and once the term of
    that application has ended: payouts stop then (payout_flow.cover_ends), so a renewal is a new
    application.
    """
    application = latest_application(request.app.state.db, user.id)
    cover_ends = application["cover_ends"] if application else None
    if cover_ends and cover_ends <= datetime.now(SINGAPORE).date():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Your {application['term_months']}-month term ended on {cover_ends:%d %b %Y}; "
            "apply again to renew",
        )
    if application and application["status"] == "referred":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An underwriter is reviewing your application. Cover starts after they reply"
        )
    if application and application["status"] == "declined":
        raise HTTPException(status.HTTP_409_CONFLICT, "An underwriter declined this application")
    product = body.product or user.product or "cooked_food"
    priced = business_quote(
        request, tariff, history, product, user.region, user.centre, shop_postcode(application)
    )
    values = policy_values(priced, user.id, user.region, user.centre, product, body.tier)
    engine = request.app.state.db
    with engine.begin() as db:
        db.execute(sa_delete(accounts.policies).where(accounts.policies.c.user_id == user.id))
        policy_id = db.execute(
            sa_insert(accounts.policies).values(**values).returning(accounts.policies.c.id)
        ).scalar_one()
    return {"id": policy_id, **{k: v for k, v in values.items() if k != "user_id"}}


# UEN formats from ACRA: 8 digits + letter (businesses), 9 digits + letter (local companies),
# or T/S/R + 2 digits + 2 letters + 4 digits + letter (other entities).
UEN = re.compile(r"^(\d{8}[A-Z]|\d{9}[A-Z]|[TSR]\d{2}[A-Z]{2}\d{4}[A-Z])$")
# Singapore mobile and fixed-line numbers: 8 digits starting with 3, 6, 8 or 9.
SG_PHONE = re.compile(r"^[3689]\d{7}$")
PAYMENT_REF = re.compile(r"^DEMO-[0-9A-F]{6}$")
MAX_QR_AMOUNT_SGD = 1000


SINGAPORE = ZoneInfo("Asia/Singapore")
LATEST_COVER_START_DAYS = 90


class BuyRequest(BaseModel):
    """Everything the guided buy flow (/buy/) collects, sent once at the pay step.

    Email and password are only checked for being present: the demo fills them with made-up
    values. An email that already has an account is still refused. Each business class sends
    only its own identifying fields; the others are dropped. See api/onboarding.py.
    """

    business_class: onboarding.BusinessClass
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)
    business_name: str | None = Field(default=None, max_length=120)
    centre: str | None = None
    stall_unit: str | None = Field(default=None, max_length=20)
    licence_no: str | None = None
    ssic_code: str | None = None
    platform: str | None = None
    platform_worker_id: str | None = None
    postcode: str | None = None
    product: str
    staff_band: onboarding.StaffBand | None = None
    sales_under_100m: bool | None = None
    designation: str | None = Field(default=None, max_length=60)
    cover_start: date | None = Field(default=None, description="Singapore date. Empty: today.")
    term_months: Literal[12, 24] = 12
    applicant_type: Literal["individual", "company"]
    uen: str | None = None
    phone: str
    add_safeday: bool
    tier: str | None = None
    declined_before: bool
    declined_details: str | None = Field(default=None, max_length=500)
    accept_declaration: bool
    accept_pdpa: bool
    marketing_email: bool = False
    marketing_sms: bool = False
    payment_method: Literal["paynow", "giro"] | None = None
    payment_ref: str | None = Field(default=None, pattern=PAYMENT_REF.pattern)

    @field_validator("phone")
    @classmethod
    def singapore_phone(cls, value: str) -> str:
        digits = re.sub(r"[\s-]", "", value).removeprefix("+65")
        if not SG_PHONE.match(digits):
            raise ValueError("Enter an 8-digit Singapore number")
        return digits

    @field_validator("uen")
    @classmethod
    def uen_format(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().upper()
        if not UEN.match(value):
            raise ValueError("That UEN does not look right, e.g. 53123456A or 201912345K")
        return value

    @field_validator("licence_no")
    @classmethod
    def licence_format(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().upper()
        if not onboarding.LICENCE_NO.match(value):
            raise ValueError("A licence number has 5 to 20 letters, digits, '/' or '-'")
        return value

    @field_validator("postcode")
    @classmethod
    def known_postcode(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        postcodes.region_of(value)
        return value

    @field_validator("cover_start")
    @classmethod
    def cover_start_soon(cls, value: date | None) -> date | None:
        if value is None:
            return None
        today = datetime.now(SINGAPORE).date()
        if not today <= value <= today + timedelta(days=LATEST_COVER_START_DAYS):
            raise ValueError(f"Cover can start today or within {LATEST_COVER_START_DAYS} days")
        return value

    @model_validator(mode="after")
    def complete(self) -> BuyRequest:
        {
            "hawker": self.hawker_complete,
            "shop": self.shop_complete,
            "platform_worker": self.platform_worker_complete,
        }[self.business_class]()
        platform_product = self.product == onboarding.PLATFORM_PRODUCT
        if platform_product != (self.business_class == "platform_worker"):
            raise ValueError("Ride-hail and delivery work is the cover for platform workers only")
        if self.staff_band is None:
            raise ValueError("Say how many people work in the business")
        if self.staff_band == onboarding.OVER_SME_STAFF_BAND:
            if self.sales_under_100m is None:
                raise ValueError("Say whether annual sales were under S$100 million")
            if not self.sales_under_100m:
                raise ValueError(onboarding.NOT_AN_SME)
        if self.applicant_type == "company" and self.uen is None:
            raise ValueError("A company needs its UEN")
        if not (self.accept_declaration and self.accept_pdpa):
            raise ValueError("Tick the declaration and the personal data consent to continue")
        if self.add_safeday and self.tier is None:
            raise ValueError("Pick a SafeDay tier")
        if self.declined_before and not (self.declined_details or "").strip():
            raise ValueError("Say which insurer declined you and why")
        return self

    def hawker_complete(self) -> None:
        if self.licence_no is None:
            raise ValueError("Enter your SFA food stall licence or NEA stall tenancy number")
        self.ssic_code = self.platform = self.platform_worker_id = self.postcode = None

    def shop_complete(self) -> None:
        if self.postcode is None:
            raise ValueError("Enter the shop's 6-digit postcode")
        if not onboarding.SSIC_CODE.match(self.ssic_code or ""):
            raise ValueError("Enter the shop's 5-digit SSIC code")
        self.centre = self.stall_unit = self.licence_no = None
        self.platform = self.platform_worker_id = None

    def platform_worker_complete(self) -> None:
        if self.platform not in onboarding.PLATFORMS:
            raise ValueError("Pick the platform you work on")
        worker_id = (self.platform_worker_id or "").strip()
        if not 3 <= len(worker_id) <= 40:
            raise ValueError("Enter your driver or rider ID, 3 to 40 characters")
        if self.postcode is None:
            raise ValueError("Enter your 6-digit home postcode")
        if self.applicant_type != "individual":
            raise ValueError("A platform worker applies as an individual")
        self.platform_worker_id = worker_id
        self.staff_band = self.staff_band or onboarding.PLATFORM_WORKER_STAFF_BAND
        self.business_name = self.centre = self.stall_unit = None
        self.licence_no = self.ssic_code = None


def add_months(day: date, months: int) -> date:
    """The same day of the month, months later; the month's last day if it is shorter."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, monthrange(year, month)[1]))


def cover_dates(cover_start: date, term_months: int) -> dict:
    """When payouts can start (after the waiting period) and when the term ends."""
    return {
        "term_months": term_months,
        "waiting_ends": cover_start + timedelta(days=accounts.WAITING_PERIOD_DAYS),
        "cover_ends": add_months(cover_start, term_months),
    }


def demo_payment_ref() -> str:
    return f"DEMO-{secrets.token_hex(3).upper()}"


def hawker_postcode(request: Request, centre: str) -> str | None:
    """The postcode at the end of a hawker centre's address, if its address has one."""
    match = postcodes.ADDRESS_POSTCODE.search(centre_place(request, centre)["address"])
    return match.group(1) if match else None


@app.get("/api/buy/options")
def buy_options() -> dict:
    """The choices the buy flow offers each business class, and the postal sector regions."""
    return {
        "business_classes": onboarding.BUSINESS_CLASSES,
        "platform_product": onboarding.PLATFORM_PRODUCT,
        "ssic_codes": [
            {"code": code, "title": title} for code, title in onboarding.SHOP_SSIC_CODES.items()
        ],
        "platforms": onboarding.PLATFORMS,
        "staff_bands": onboarding.STAFF_BANDS,
        "not_an_sme": onboarding.NOT_AN_SME,
        "terms_months": accounts.TERMS_MONTHS,
        "waiting_period_days": accounts.WAITING_PERIOD_DAYS,
        "postal_sector_regions": postcodes.SECTOR_REGION,
    }


@app.get("/api/paynow/qr")
def paynow_qr_code(
    amount_sgd: Annotated[float, Query(gt=0, le=MAX_QR_AMOUNT_SGD)],
    reference: Annotated[str, Query(pattern=PAYMENT_REF.pattern)],
) -> Response:
    """A PayNow QR (SVG) for the first week's premium. Prototype: its proxy pays nobody."""
    return Response(paynow_qr.paynow_svg(amount_sgd, reference), media_type="image/svg+xml")


@app.post("/api/buy")
def buy(
    body: BuyRequest, tariff: TariffDep, history: HistoryDep, request: Request, response: Response
) -> dict:
    """Create the account, the application and, when SafeDay is added, its policy, then sign in.

    A past decline sends the application to an underwriter: no policy starts and nothing is
    charged. Payment is a prototype step: no money moves, the reference is made up.
    """
    engine = request.app.state.db
    calculator.find(tariff.products, body.product, "product")
    hawker = body.business_class == "hawker"
    # model_construct skips Registration's email and password rules, which the demo does not need.
    account = Registration.model_construct(
        role="sme", name=body.name, email=body.email, password=body.password,
        business_name=body.business_name, centre=body.centre, product=body.product, insurer=None,
    )
    region = None if hawker else postcodes.region_of(body.postcode)
    user = accounts.user_values(account, request, region)
    referred = body.declined_before
    pays = body.add_safeday and not referred
    if pays and body.payment_method is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick how to pay")
    now = datetime.now(UTC)
    cover_start = body.cover_start or now.astimezone(SINGAPORE).date()
    starts_at = max(now, datetime.combine(cover_start, datetime.min.time(), SINGAPORE))
    with engine.begin() as db:
        user_id = db.execute(
            sa_insert(accounts.users).values(**user).returning(accounts.users.c.id)
        ).scalar_one()
        policy = None
        if pays:
            postcode = body.postcode if body.business_class == "shop" else None
            priced = business_quote(
                request, tariff, history, body.product, user["region"], user["centre"], postcode
            )
            policy = policy_values(
                priced, user_id, user["region"], user["centre"], body.product, body.tier
            )
            policy["started_at"] = starts_at
            policy["id"] = db.execute(
                sa_insert(accounts.policies).values(**policy).returning(accounts.policies.c.id)
            ).scalar_one()
        application = {
            "user_id": user_id,
            "applicant_type": body.applicant_type,
            "uen": body.uen,
            "phone": body.phone,
            "add_safeday": body.add_safeday,
            "tier": body.tier if body.add_safeday else None,
            "declined_before": body.declined_before,
            "declined_details": body.declined_details if body.declined_before else None,
            "status": "referred" if referred else "accepted",
            "declaration_accepted_at": now,
            "pdpa_accepted_at": now,
            "marketing_email": body.marketing_email,
            "marketing_sms": body.marketing_sms,
            "payment_method": body.payment_method if pays else None,
            "payment_ref": (body.payment_ref or demo_payment_ref()) if pays else None,
            "created_at": now,
        }
        application["id"] = db.execute(
            sa_insert(accounts.applications).values(**application).returning(accounts.applications.c.id)
        ).scalar_one()
        details = {
            "stall_unit": body.stall_unit,
            "designation": body.designation,
            "cover_start": cover_start,
        }
        db.execute(
            sa_insert(accounts.application_details).values(application_id=application["id"], **details)
        )
        profile = {
            "business_class": body.business_class,
            "licence_no": body.licence_no,
            "ssic_code": body.ssic_code,
            "platform": body.platform,
            "platform_worker_id": body.platform_worker_id,
            "postcode": hawker_postcode(request, user["centre"]) if hawker else body.postcode,
            "staff_band": body.staff_band,
            **cover_dates(cover_start, body.term_months),
        }
        profile_row = {"application_id": application["id"], **profile}
        db.execute(sa_insert(accounts.application_profile).values(**profile_row))
        application.update(details, **profile)
    accounts.start_session(engine, user_id, response)
    return {
        "application": {k: v for k, v in application.items() if k != "user_id"},
        "policy": {k: v for k, v in policy.items() if k != "user_id"} if policy else None,
    }


def latest_application(engine, user_id: int) -> dict | None:
    """The user's latest application with its details and profile, flat. Missing rows: nulls."""
    details, profile = accounts.application_details, accounts.application_profile
    query = (
        sa_select(
            accounts.applications,
            details.c.stall_unit,
            details.c.designation,
            details.c.cover_start,
            *(column for column in profile.c if column.name != "application_id"),
        )
        .outerjoin(details, details.c.application_id == accounts.applications.c.id)
        .outerjoin(profile, profile.c.application_id == accounts.applications.c.id)
        .where(accounts.applications.c.user_id == user_id)
        .order_by(accounts.applications.c.id.desc())
    )
    with engine.connect() as db:
        row = db.execute(query).mappings().first()
    return {k: v for k, v in row.items() if k != "user_id"} if row else None


def shop_postcode(application: dict | None) -> str | None:
    """A shop's postcode, which places its price. Hawkers are placed by their centre, and
    platform workers are priced for their region, so neither has one here."""
    if application and application.get("business_class") == "shop":
        return application.get("postcode")
    return None


@app.get("/api/applications/mine")
def my_application(user: SmeDep, request: Request) -> dict | None:
    """The signed-in business's latest buy-flow application, or null.

    area_lat, area_lng and area_basis place its postcode approximately: the mean of the hawker
    centres in its postal sector, else district, else its region's point (postcodes.area_point).
    """
    application = latest_application(request.app.state.db, user.id)
    if application is None:
        return None
    area = (
        postcodes.area_point(
            application["postcode"],
            request.app.state.centres_by_sector,
            request.app.state.map_static["region_points"],
        )
        if application["postcode"]
        else {}
    )
    return {
        **application,
        "area_lat": area.get("lat"),
        "area_lng": area.get("lng"),
        "area_basis": area.get("basis"),
    }


@app.get("/api/policies")
def list_policies(user: UserDep, request: Request) -> list[dict]:
    """The stallholder's own policy, or every policy for an insurer."""
    engine = request.app.state.db
    query = (
        sa_select(accounts.policies, accounts.users.c.business_name, accounts.users.c.name)
        .join(accounts.users, accounts.users.c.id == accounts.policies.c.user_id)
        .order_by(accounts.policies.c.started_at.desc())
    )
    if user.role != "insurer":
        query = query.where(accounts.policies.c.user_id == user.id)
    with engine.connect() as db:
        rows = db.execute(query).mappings().all()
    return [{k: v for k, v in row.items() if k not in ("user_id",)} for row in rows]


@app.delete("/api/policies/{policy_id}")
def cancel_policy(policy_id: int, user: SmeDep, request: Request) -> dict:
    engine = request.app.state.db
    with engine.begin() as db:
        gone = db.execute(
            sa_delete(accounts.policies).where(
                accounts.policies.c.id == policy_id, accounts.policies.c.user_id == user.id
            )
        ).rowcount
    if not gone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such policy on this account")
    return {"cancelled": policy_id}


@app.get("/api/insurer/portfolio")
def insurer_portfolio(user: InsurerDep, request: Request) -> dict:
    """What the signed-in insurer carries: sold policies aggregated by region and tier."""
    engine = request.app.state.db
    with engine.connect() as db:
        rows = db.execute(sa_select(accounts.policies)).mappings().all()
    by_region: dict[str, dict] = {}
    for row in rows:
        entry = by_region.setdefault(row["region"], {"policies": 0, "weekly_premium_sgd": 0.0, "daily_payout_sgd": 0.0})
        entry["policies"] += 1
        entry["weekly_premium_sgd"] += row["weekly_premium_sgd"]
        entry["daily_payout_sgd"] += row["daily_payout_sgd"]
    return {
        "insurer": user.insurer,
        "policies": len(rows),
        "weekly_premium_sgd": round(sum(r["weekly_premium_sgd"] for r in rows), 2),
        "annual_premium_sgd": round(sum(r["weekly_premium_sgd"] for r in rows) * 52, 2),
        "daily_payout_exposure_sgd": round(sum(r["daily_payout_sgd"] for r in rows), 2),
        "by_region": {k: {**v, "weekly_premium_sgd": round(v["weekly_premium_sgd"], 2)} for k, v in by_region.items()},
    }


@app.get("/api/admin/tariff")
def get_tariff(_: AdminDep, saved: SavedTariffDep) -> SavedTariff:
    return saved


@app.put("/api/admin/tariff")
def put_tariff(
    change: TariffChange,
    username: AdminDep,
    saved: SavedTariffDep,
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


app.include_router(accounts.router)
app.include_router(payout_api.router)
app.include_router(underwriting.router)
app.mount("/admin", StaticFiles(directory=API_DIR / "admin", html=True), name="admin")
app.mount("/map", StaticFiles(directory=API_DIR / "map", html=True), name="map")
app.mount("/", StaticFiles(directory=API_DIR / "site", html=True), name="site")
