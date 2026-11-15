"""Payung platform: pricing API, SME and insurer dashboards, risk map and admin panel.

Usage:
    ADMIN_USERNAME=admin ADMIN_PASSWORD=... uv run uvicorn api.main:app --reload
    Site on http://localhost:8000/ (landing, /login/, /dashboard/), risk map on /map/,
    tariff desk on /admin/, API docs on /docs.

Reads  data/processed/site_hazard_readings.csv      (from scripts/region_hazard_readings.py)
       data/processed/place_day_readings.npz       (from scripts/build_place_years.py)
       data/processed/day_readings.csv.gz          (from scripts/build_day_readings.py)
       data/processed/map_static.json              (from scripts/build_map_static.py)
       data/processed/hawker_rent.csv              (from scripts/build_hawker_rent.py)
       api/default_tariff.json                     (the first tariff, when the database is empty)
Writes the tariff database at DATABASE_URL         (default sqlite:///api/tariff.db)
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import secrets
import statistics
from calendar import month_name, monthrange
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlalchemy import insert as sa_insert
from sqlalchemy import select as sa_select

from api import (
    accounts, assistant, burn, calculator, day_check, kyc, model_history, onboarding,
    payout_api, payout_flow, paynow_qr, place_days, postcodes, premium, readings, sms, store,
    underwriting, voice,
)
from api.accounts import InsurerDep, Registration, SmeDep, UserDep
from api.calculator import BidRecord
from api.day_history import day_readings, day_table
from api.payouts import haze_bonus_payouts
from api.live import LiveFeed
from api.readings import Site, Sites
from api.models import (
    Assessment,
    AssessRequest,
    Choice,
    HazardChoice,
    HazeBonusQuote,
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
    Tier,
    TierQuote,
)

logger = logging.getLogger(__name__)
API_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_DIR.parent
HISTORY_PATH = REPO_ROOT / "data" / "processed" / "site_hazard_readings.csv"
MAP_STATIC_PATH = REPO_ROOT / "data" / "processed" / "map_static.json"
MAP_BUILDINGS_PATH = REPO_ROOT / "data" / "processed" / "map_buildings.json"
RENT_PATH = REPO_ROOT / "data" / "processed" / "hawker_rent.csv"
DEFAULT_TARIFF_PATH = API_DIR / "default_tariff.json"
DEFAULT_DATABASE_URL = f"sqlite:///{API_DIR / 'tariff.db'}"


def load_sites(path: Path) -> Sites:
    """Every NEA station (PSI region for haze) of the network the price reads, with its place."""
    if not path.exists():
        raise SystemExit(f"{path} is missing. Run scripts/region_hazard_readings.py first.")
    sites: dict[str, dict[str, Site]] = defaultdict(dict)
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            sites[row["hazard"]][row["site"]] = Site(
                row["site"], row["region"], float(row["latitude"]), float(row["longitude"])
            )
    return {hazard: list(by_key.values()) for hazard, by_key in sites.items()}


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
    app.state.sites = load_sites(HISTORY_PATH)
    app.state.regions = sorted({s.region for hazard in app.state.sites.values() for s in hazard})
    if not MAP_STATIC_PATH.exists():
        raise SystemExit(f"{MAP_STATIC_PATH} is missing. Run scripts/build_map_static.py first.")
    app.state.map_static = json.loads(MAP_STATIC_PATH.read_text())
    app.state.place_days = place_days.PlaceDays(
        app.state.sites, lambda: day_table(app.state), place_days.PLACE_DAYS_PATH
    )
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
    except ValidationError as error:
        # Saved before the tariff gained required fields (product margins, stations per
        # trigger). Older versions stay in the database; pricing starts again from the default.
        logger.error(
            "The latest saved tariff no longer validates, so the default tariff is saved as a "
            "new version over it. The old version stays in the database. %s", error,
        )
        saved = None
    default = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
    if saved is None:
        store.save(app.state.db, default, saved_by="default")
    else:
        bring_up_to_date(app.state.db, saved, default)
    yield
    app.state.db.dispose()


def bring_up_to_date(engine, saved: SavedTariff, default: Tariff) -> Tariff:
    """Save the saved tariff again, once, with what later versions of the default tariff added.

    Each step decides from the tariff as it was saved: a tariff written out by an earlier step
    carries every field, so it would look as if the tariff desk had set them.
    """
    as_saved = saved.tariff
    tariff, added = as_saved, []
    steps = (
        ("new products", lambda current: add_missing_products(current, default)),
        ("yearly limits, stations on hold",
         lambda current: adopt_yearly_price_rules(current, default, as_saved)),
        ("severe haze payout", lambda current: adopt_haze_bonus(current, default, as_saved)),
    )
    for name, step in steps:
        if updated := step(tariff):
            tariff = updated
            added.append(name)
    if added:
        store.save(engine, tariff, saved_by="default: " + ", ".join(added))
    return tariff


def adopt_haze_bonus(tariff: Tariff, default: Tariff, as_saved: Tariff | None = None) -> Tariff | None:
    """A tariff saved before the severe haze payout existed, with the default's add-on. None
    when the tariff says what it offers: a tariff saved since holds haze_bonus, empty when the
    tariff desk took the add-on off sale."""
    if "haze_bonus" in (as_saved or tariff).model_fields_set or default.haze_bonus is None:
        return None
    return Tariff.model_validate(
        tariff.model_copy(update={"haze_bonus": default.haze_bonus}).model_dump()
    )


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


# The yearly limits and daily amounts every tariff had before the yearly price.
TIERS_BEFORE_YEARLY_PRICE = {
    "tier_1": (10, 20), "tier_2": (15, 40), "tier_3": (20, 70), "tier_4": (30, 100),
}


def adopt_yearly_price_rules(
    tariff: Tariff, default: Tariff, as_saved: Tariff | None = None
) -> Tariff | None:
    """A tariff saved before the yearly price, with the default's stations on hold, and each
    tier the tariff desk left as shipped given the default's limit and premium shares. None
    when it is newer.

    A tariff saved since carries refer_above_limit_share, so this changes it only once. A tier
    the desk changed keeps its limit and prices on the Pricing loads, as before; if the shipped
    tiers' new limits would then fall below it, every tier is kept. Sold policies keep the
    limit they were sold with.
    """
    if "refer_above_limit_share" in (as_saved or tariff).pricing.model_fields_set:
        return None
    default_hazards = {hazard.key: hazard for hazard in default.hazards}
    holds_set = {
        hazard.key for hazard in (as_saved or tariff).hazards
        if "stations_on_hold" in hazard.model_fields_set
    }
    hazards = [
        hazard.model_copy(update={"stations_on_hold": default_hazards[hazard.key].stations_on_hold})
        if hazard.key in default_hazards and hazard.key not in holds_set
        else hazard
        for hazard in tariff.hazards
    ]
    default_tiers = {tier.key: tier for tier in default.tiers}

    def as_shipped(tier: Tier) -> bool:
        shipped = (tier.max_paid_days_per_year, tier.daily_payout_sgd)
        return (
            tier.key in default_tiers and tier.premium_shares is None
            and TIERS_BEFORE_YEARLY_PRICE.get(tier.key) == shipped
        )

    tiers = [
        tier.model_copy(update={
            "max_paid_days_per_year": default_tiers[tier.key].max_paid_days_per_year,
            "premium_shares": default_tiers[tier.key].premium_shares,
        })
        if as_shipped(tier) else tier
        for tier in tariff.tiers
    ]
    # Validated from a full dump, every field counts as set, so a second start changes nothing.
    try:
        return Tariff.model_validate(
            tariff.model_copy(update={"hazards": hazards, "tiers": tiers}).model_dump()
        )
    except ValidationError:
        return Tariff.model_validate(tariff.model_copy(update={"hazards": hazards}).model_dump())


app = FastAPI(title="Payung pricing API", lifespan=lifespan)
basic_auth = HTTPBasic(auto_error=False)


@app.exception_handler(calculator.UnknownKey)
def unknown_key(_: Request, error: calculator.UnknownKey) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})


@app.exception_handler(calculator.MissingHistory)
def missing_history(_: Request, error: calculator.MissingHistory) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(error)}
    )


def saved_tariff(request: Request) -> SavedTariff:
    return store.latest(request.app.state.db)


def current_tariff(saved: Annotated[SavedTariff, Depends(saved_tariff)]) -> Tariff:
    return saved.tariff


class TariffEditor(BaseModel):
    """Who is using the tariff desk, and the name a save is recorded under."""

    name: str
    organisation: str
    signed_in_with: Literal["session", "password"]
    saved_by: str


def admin_by_password(request: Request, credentials: HTTPBasicCredentials) -> TariffEditor:
    username, password = request.app.state.admin_login
    valid_username = secrets.compare_digest(credentials.username.encode(), username.encode())
    valid_password = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not (valid_username and valid_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    return TariffEditor(
        name=credentials.username,
        organisation="Tariff desk login",
        signed_in_with="password",
        saved_by=credentials.username,
    )


def admin(
    request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)]
) -> TariffEditor:
    """An insurer signed in to Payung, or anyone with the tariff desk login."""
    # No WWW-Authenticate header on purpose: it would make browsers open their own login box
    # over the admin panel's login form.
    if credentials is not None:
        return admin_by_password(request, credentials)
    user = accounts.current_user(request)
    if user.role != "insurer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only insurer accounts can edit the tariff")
    return TariffEditor(
        name=user.name,
        organisation=user.insurer or "Insurer",
        signed_in_with="session",
        saved_by=f"{user.name} ({user.email})",
    )


SavedTariffDep = Annotated[SavedTariff, Depends(saved_tariff)]
TariffDep = Annotated[Tariff, Depends(current_tariff)]
AdminDep = Annotated[TariffEditor, Depends(admin)]


@app.get("/api/options")
def options(tariff: TariffDep, request: Request) -> Options:
    """What a customer can choose from, and the readings a payout check takes."""
    hazards_with_history = set(request.app.state.sites)
    return Options(
        regions=request.app.state.regions,
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


def place_quote(
    request: Request, tariff: Tariff, product: str, region: str, lat: float, lng: float
) -> Quote:
    """The quote at one point paid on a PSI region, from the replay of its recorded days, with
    how each hazard was priced there next to the region's point."""
    known_region(region, request)
    rule = readings.station_rule(tariff)
    days: place_days.PlaceDays = request.app.state.place_days
    region_lat, region_lng = request.app.state.map_static["region_points"][region]
    where = readings.history_place(region, lat, lng, request.app.state.sites)
    stations = {
        "haze": [region],
        "rain": readings.stations_used(where, "rain", rule),
        "heat": readings.stations_used(where, "heat", rule),
    }
    return calculator.quote(
        tariff, product, region, days.replay(rule, region, lat, lng),
        days.replay(rule, region, region_lat, region_lng), stations,
    )


def region_quote(request: Request, tariff: Tariff, product: str, region: str) -> Quote:
    """The quote for a whole PSI region, read at the region's point as its payouts are."""
    known_region(region, request)
    lat, lng = request.app.state.map_static["region_points"][region]
    replay = request.app.state.place_days.replay(readings.station_rule(tariff), region, lat, lng)
    return calculator.quote(tariff, product, region, replay)


def nearest_region(request: Request, lat: float, lng: float) -> str:
    """The PSI region of the NEA station nearest a point."""
    every_site = [site for hazard in request.app.state.sites.values() for site in hazard]
    nearest = min(
        every_site, key=lambda site: calculator.km_between(lat, lng, site.latitude, site.longitude)
    )
    return nearest.region


def business_quote(
    request: Request, tariff: Tariff, product: str, region: str | None,
    centre: str | None = None, postcode: str | None = None,
) -> Quote:
    """The price a business is shown and charged: replayed at its hawker centre, else at its
    postcode's area. A business with neither, such as a platform worker who works across the
    island, is priced for its region. Haze is read for the PSI region a payout reads: the
    centre's map region, the postcode's region (postcodes.region_of).
    """
    if centre is not None:
        place = centre_place(request, centre)
        return place_quote(request, tariff, product, place["region"], place["lat"], place["lng"])
    if postcode is not None:
        point = postcode_point(request, postcode)
        return place_quote(request, tariff, product, point["region"], point["lat"], point["lng"])
    return region_quote(request, tariff, product, region)


@app.post("/api/quote")
def quote(body: QuoteRequest, request: Request, tariff: TariffDep) -> Quote:
    """Yearly, weekly and daily premium, payout and proof of every tier, for one product, at a
    region, a map point, a hawker centre or a postcode's area. A centre or postcode gives the
    price a business there is charged when it buys."""
    if body.latitude is not None and body.longitude is not None:
        region = nearest_region(request, body.latitude, body.longitude)
        return place_quote(request, tariff, body.product, region, body.latitude, body.longitude)
    return business_quote(request, tariff, body.product, body.region, body.centre, body.postcode)


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
def map_quotes(saved: SavedTariffDep, request: Request, product: str = "cooked_food") -> dict:
    """Quotes for every region and every hawker centre at once, with the per-hazard loss-day
    split and pricing loads. A centre's quote is the price a stall there is charged."""
    tariff = saved.tariff
    calculator.find(tariff.products, product, "product")
    priced = priced_places(saved, request, product)
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
        "quotes": priced["regions"],
        "loss_day_parts": {
            region: quote.loss_day_parts for region, quote in priced["regions"].items()
        },
        # Each hawker centre priced as a stall there is charged (business_quote), with its parts.
        "centres": priced["centres"],
        "centre_loss_day_parts": {
            name: quote.loss_day_parts for name, quote in priced["centres"].items()
        },
    }


def priced_places(saved: SavedTariff, request: Request, product: str) -> dict[str, dict]:
    """Every region's and hawker centre's quote, priced once per saved tariff version and
    product. A new version starts a fresh cache."""
    # The haze add-on's on_sale_now follows the month, so a new month prices afresh.
    key = (saved.version, product, calculator.singapore_today().month)
    cache = request.app.state.centre_quotes
    if key not in cache:
        if any(version != saved.version for version, *_ in cache):
            cache = request.app.state.centre_quotes = {}
        cache[key] = {
            "regions": {
                region: region_quote(request, saved.tariff, product, region)
                for region in request.app.state.regions
            },
            "centres": {
                centre["name"]: business_quote(
                    request, saved.tariff, product, None, centre=centre["name"]
                )
                for centre in request.app.state.map_static["hawker_centres"]
            },
        }
    return cache[key]




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
def map_scenario(body: ScenarioRequest, saved: SavedTariffDep, request: Request) -> dict:
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

    priced_by_name = priced_places(saved, request, body.product)["centres"] if centres else {}

    def priced_centre(centre: dict) -> dict:
        priced = priced_by_name[centre["name"]]
        baseline = next(t for t in priced.tiers if t.tier == body.tier)
        stressed_days = min(
            priced.expected_loss_days + body.extra_days_per_year * day_loss,
            tier.max_paid_days_per_year,
        )
        stressed_yearly = calculator.yearly_premium(
            stressed_days * tier.daily_payout_sgd, tariff.pricing, tier.premium_shares
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


def known_region(region: str, request: Request) -> None:
    if region not in request.app.state.regions:
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
    centre: str, request: Request, tariff: Tariff, product: str
) -> tuple[readings.Place, Quote]:
    """A hawker centre's place for the replay and the price a stall there is charged."""
    place = centre_place(request, centre)
    where = readings.history_place(
        place["region"], place["lat"], place["lng"], request.app.state.sites
    )
    return where, business_quote(request, tariff, product, None, centre=centre)


def point_burn_site(
    lat: float, lng: float, region: str, request: Request, tariff: Tariff, product: str
) -> tuple[readings.Place, Quote]:
    """A point's place for the replay and its price there, with haze read for the region it is
    paid on."""
    known_region(region, request)
    where = readings.history_place(region, lat, lng, request.app.state.sites)
    return where, place_quote(request, tariff, product, region, lat, lng)


def region_burn_site(
    lat: float, lng: float, region: str, request: Request, tariff: Tariff, product: str
) -> tuple[readings.Place, Quote]:
    """A platform worker's place for the replay, at its region's point as a payout reads it,
    and the region price they are charged."""
    where = readings.history_place(region, lat, lng, request.app.state.sites)
    return where, region_quote(request, tariff, product, region)


def checked_takings(takings: float) -> None:
    if not 50 <= takings <= 20000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "takings must be 50 to 20000")


@app.get("/api/map/burn")
def map_burn(
    request: Request,
    tariff: TariffDep,
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
    checked_takings(takings)
    if centre is not None:
        site, priced = centre_burn_site(centre, request, tariff, product)
    elif lat is not None and lng is not None and region is not None:
        site, priced = point_burn_site(lat, lng, region, request, tariff, product)
    elif lat is None and lng is None and region is not None:
        known_region(region, request)
        lat, lng = request.app.state.map_static["region_points"][region]
        site, priced = region_burn_site(lat, lng, region, request, tariff, product)
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


def filled_history(request: Request) -> model_history.ModelHistory:
    """The model-filled daily readings since 1980, loaded once per process."""
    if not hasattr(request.app.state, "model_history"):
        try:
            request.app.state.model_history = model_history.load()
        except FileNotFoundError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return request.app.state.model_history


def model_insights_data(request: Request) -> dict:
    if not hasattr(request.app.state, "model_insights"):
        try:
            request.app.state.model_insights = model_history.load_insights()
        except FileNotFoundError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return request.app.state.model_insights


@app.get("/api/model/history")
def model_centre_history(
    request: Request,
    tariff: TariffDep,
    history: HistoryDep,
    centre: str | None = None,
    lat: Annotated[float | None, Query(**SG_LAT)] = None,
    lng: Annotated[float | None, Query(**SG_LNG)] = None,
    product: str = "cooked_food",
    tier: str = "tier_2",
    takings: float = 500.0,
) -> dict:
    """One business's payouts in every year since 1980, with model-filled years, and the
    typical, bad and worst year that history implies.

    A centre reads its own history. A point (lat, lng) reads its nearest hawker centre's and
    is priced at the point, as /api/map/burn prices it. takings is the business's normal daily
    sales in SGD, which the sales lost to weather scale with.
    """
    checked_takings(takings)
    centres = request.app.state.map_static["hawker_centres"]
    if centre is not None:
        place = next((c for c in centres if c["name"] == centre), None)
        if place is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown hawker centre: {centre}")
        lat, lng = place["lat"], place["lng"]
    elif lat is not None and lng is not None:
        place = min(centres, key=lambda c: (c["lat"] - lat) ** 2 + (c["lng"] - lng) ** 2)
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a centre, or lat and lng")
    priced = calculator.quote_at(tariff, history, request.app.state.sites, lat, lng, product)
    tier_quote = next((t for t in priced.tiers if t.tier == tier), None)
    if tier_quote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tier: {tier}")
    filled = filled_history(request)
    insights = model_insights_data(request)
    return {
        "centre": place["name"],
        "read_from_nearest_centre": centre is None,
        "region": place["region"],
        "product": product,
        "tier": tier,
        "tier_label": tier_quote.label,
        "daily_payout_sgd": tier_quote.daily_payout_sgd,
        "max_payout_per_year_sgd": tier_quote.max_payout_per_year_sgd,
        "weekly_premium_sgd": tier_quote.weekly_premium_sgd,
        **model_history.centre_years(
            filled, place["name"], tariff, product, tier, tier_quote.yearly_premium_sgd,
            set(insights["haze"]["el_nino_years"]), outlook_start(), takings,
        ),
        "haze_facts": insights["haze"],
        "data_to": insights["data_to"],
    }


def outlook_start() -> date:
    """The first day the outlooks look at: tomorrow, Singapore time."""
    return datetime.now(ZoneInfo("Asia/Singapore")).date() + timedelta(days=1)


@app.get("/api/model/book")
def model_book(
    _: InsurerDep,
    request: Request,
    tariff: TariffDep,
    history: HistoryDep,
    product: str = "cooked_food",
    tier: str = "tier_2",
) -> dict:
    """Every food stall in every hawker centre, one policy each, back-tested since 1980."""
    centres = request.app.state.map_static["hawker_centres"]
    region_quotes = {
        region: calculator.quote(tariff, history, region, product)
        for region in {c["region"] for c in centres}
    }
    premium_by_centre = {}
    for c in centres:
        tier_quote = next((t for t in region_quotes[c["region"]].tiers if t.tier == tier), None)
        if tier_quote is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tier: {tier}")
        premium_by_centre[c["name"]] = tier_quote.yearly_premium_sgd
    stalls = {c["name"]: c["food_stalls"] for c in centres}
    insights = model_insights_data(request)
    book = model_history.book_years(
        filled_history(request), tariff, product, tier, stalls, premium_by_centre,
        set(insights["haze"]["el_nino_years"]), outlook_start(),
    )
    return {
        "product": product,
        "tier": tier,
        "tier_label": tier_quote.label,
        "daily_payout_sgd": tier_quote.daily_payout_sgd,
        "haze_facts": insights["haze"],
        **book,
    }


@app.get("/api/model/insights")
def model_insights(request: Request) -> dict:
    """How each trained model scored against a simple guess, and what the product uses it for."""
    return model_insights_data(request)


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
    rule = readings.station_rule(tariff)
    for where in centre_places(request):
        centre_readings = readings.day_readings_at(day, where, rule)
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
    lat: Annotated[float, Query(**SG_LAT)],
    lng: Annotated[float, Query(**SG_LNG)],
    region: str,
    product: str = "cooked_food",
) -> dict:
    """Today's loss score at one point in a PSI region, scored as /api/map/live scores a centre.

    Returns the feed's status until `available` is true, then one hawker_losses entry with the
    feed's fetched_at.
    """
    known_region(region, request)
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
    now = readings.day_readings_at(today.day, where, readings.station_rule(tariff))
    assessment = calculator.assess(tariff, product, tariff.tiers[0].key, now)
    return {"loss_percent": assessment.loss_percent, "readings": now}


class SellerFields(BaseModel):
    """Who arranges the cover with the customer: their Income adviser (with the adviser's code) or
    an association (with its name). Payung is never sold to the customer directly, because Income
    sells SmartBiz 360 through intermediaries. See api/onboarding.py."""

    sold_by: onboarding.SoldBy
    adviser_code: str | None = None
    association: str | None = Field(default=None, max_length=120)

    @field_validator("adviser_code")
    @classmethod
    def adviser_code_format(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().upper()
        if not onboarding.ADVISER_CODE.match(value):
            raise ValueError("An adviser code has 4 to 12 letters or digits")
        return value

    def channel_complete(self) -> None:
        if self.sold_by == "adviser":
            if self.adviser_code is None:
                raise ValueError("Enter the code of the Income adviser who helps the customer")
            self.association = None
            return
        shortest, longest = onboarding.ASSOCIATION_NAME_LENGTH
        association = (self.association or "").strip()
        if not shortest <= len(association) <= longest:
            raise ValueError("Enter the name of the association that offers the cover")
        self.association = association
        self.adviser_code = None


class PolicyRequest(SellerFields):
    """A cover started or changed after the application, always with the customer's adviser or
    association, who is recorded in policy_channel."""

    tier: str
    product: str | None = None
    add_haze_bonus: bool = False


def haze_bonus_offer(tier: TierQuote, tariff: Tariff) -> HazeBonusQuote:
    """The severe haze payout for a tier. Raises 422 when the tariff offers none, or in a month
    it cannot be added."""
    offer = tier.haze_bonus
    if offer is None or tariff.haze_bonus is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The severe haze payout is not offered"
        )
    if not offer.on_sale_now:
        off_sale = ", ".join(month_name[month] for month in tariff.haze_bonus.no_sale_months)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"The severe haze payout cannot be added in {off_sale}, so that nobody buys it as "
            "the haze season nears. The daily cover can be bought now",
        )
    return offer


def haze_bonus_starts(tariff: Tariff, cover_from: date) -> date:
    """The first day the severe haze payout can pay: after its own waiting period."""
    return cover_from + timedelta(days=tariff.haze_bonus.waiting_days)


def add_haze_bonus(db, policy_id: int, offer: HazeBonusQuote, starts_on: date) -> dict:
    """Put the severe haze payout on a policy, in place of any it had."""
    row = {"policy_id": policy_id, "lump_sum_cents": round(offer.lump_sum_sgd * 100),
           "yearly_cents": round(offer.yearly_sgd * 100), "starts_on": starts_on,
           "created_at": datetime.now(UTC)}
    table = accounts.policy_haze_bonus
    db.execute(sa_delete(table).where(table.c.policy_id == policy_id))
    db.execute(sa_insert(table).values(**row))
    return haze_bonus_view(row)


def haze_bonus_view(row) -> dict:
    yearly = row["yearly_cents"] / 100
    return {"lump_sum_sgd": row["lump_sum_cents"] / 100, "yearly_sgd": yearly,
            "weekly_sgd": round(yearly / calculator.WEEKS_PER_YEAR, 2),
            "starts_on": row["starts_on"]}


def chosen_tier(priced: Quote, tier_key: str) -> TierQuote:
    """One tier of a quote. Raises 404 on an unknown tier."""
    tier = next((t for t in priced.tiers if t.tier == tier_key), None)
    if tier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tier: {tier_key}")
    return tier


def referral_reason(tier: TierQuote, tariff: Tariff) -> str | None:
    """Why a tier must go to an underwriter before it starts, or None when it is sold directly."""
    if tier.sold_directly:
        return None
    share = tariff.pricing.refer_above_limit_share
    return (
        f"{tier.label} costs S${tier.yearly_premium_sgd:,.2f} a year here, more than {share:.0%} "
        f"of the S${tier.max_payout_per_year_sgd:,.2f} it can pay in a year, so an underwriter "
        "must approve it"
    )

    @model_validator(mode="after")
    def seller_complete(self) -> PolicyRequest:
        self.channel_complete()
        return self


def policy_values(
    priced: Quote, user_id: int, region: str, centre: str | None, product: str, tier_key: str
) -> dict:
    """A policies row for one tier of a business_quote. Raises on an unknown tier."""
    tier = chosen_tier(priced, tier_key)
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
    body: PolicyRequest, user: SmeDep, tariff: TariffDep, request: Request, response: Response
) -> dict:
    """Start a cover for the signed-in business, priced server-side at its hawker centre or its
    shop's postcode (business_quote), else its region.

    Refused while an underwriter is reviewing the business's application, and once the term of
    that application has ended: payouts stop then (payout_flow.cover_ends), so a renewal is a new
    application. A tier the quote does not sell directly starts nothing: a copy of the latest
    application for that tier goes to the underwriter queue (202), and approval starts it.

    A higher daily amount starts a new waiting period for the whole cover, so nobody moves up a
    tier when a bad day is forecast. The same or a lower amount keeps the cover's start. A cover
    bought after a cancelled one is new and waits again. Payouts already made are never taken back.

    The customer's Income adviser or association always arranges it (PolicyRequest), and is kept
    in policy_channel: there is no self-serve sale from the dashboard.
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
    # A declined change of tier leaves the business free to buy a tier sold directly.
    if application and application["status"] == "declined" and not application["referral_reason"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "An underwriter declined this application")
    product = body.product or user.product or "cooked_food"
    priced = business_quote(
        request, tariff, product, user.region, user.centre, shop_postcode(application)
    )
    tier = chosen_tier(priced, body.tier)
    offer = haze_bonus_offer(tier, tariff) if body.add_haze_bonus else None
    if reason := referral_reason(chosen_tier(priced, body.tier), tariff):
        if application is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{reason}. Apply through the buy flow, so the underwriter has your details",
            )
        response.status_code = status.HTTP_202_ACCEPTED
        referral = {"reason": reason, "product": product,
                    "weekly_premium_sgd": chosen_tier(priced, body.tier).weekly_premium_sgd}
        return refer_for_tier(
            request.app.state.db, application["id"], body.tier, referral, offer is not None
        )
    values = policy_values(priced, user.id, user.region, user.centre, product, body.tier)
    engine = request.app.state.db
    with engine.begin() as db:
        current = db.execute(
            sa_select(accounts.policies).where(accounts.policies.c.user_id == user.id)
        ).first()
        if current and values["daily_payout_sgd"] <= current.daily_payout_sgd:
            values["started_at"] = current.started_at
        drop_policies(db, accounts.policies.c.user_id == user.id)
        policy_id = db.execute(
            sa_insert(accounts.policies).values(**values).returning(accounts.policies.c.id)
        ).scalar_one()
        db.execute(
            sa_insert(accounts.policy_channel).values(
                policy_id=policy_id,
                user_id=user.id,
                tier=body.tier,
                sold_by=body.sold_by,
                adviser_code=body.adviser_code,
                association=body.association,
                created_at=datetime.now(UTC),
            )
        )
        payout_flow.send_welcome_if_due(db, user.id, tariff)
        bonus = None
        if offer is not None:
            starts_on = haze_bonus_starts(tariff, datetime.now(SINGAPORE).date())
            bonus = add_haze_bonus(db, policy_id, offer, starts_on)
    return {"id": policy_id, **{k: v for k, v in values.items() if k != "user_id"},
            "haze_bonus": bonus}


def refer_for_tier(
    engine, application_id: int, tier_key: str, referral: dict, haze_bonus: bool
) -> dict:
    """A copy of an application, its details and profile, for a tier that needs an underwriter.

    The copy waits in the underwriter queue with the referral (reason, product and the weekly
    premium quoted); the cover in force, if any, stays until the new tier starts.
    """
    tables = (accounts.application_details, accounts.application_profile)
    applications = accounts.applications
    with engine.begin() as db:
        old = db.execute(
            sa_select(applications).where(applications.c.id == application_id)
        ).mappings().one()
        copy = {key: value for key, value in old.items() if key != "id"}
        copy.update(
            add_safeday=True, tier=tier_key, status="referred", payment_method=None,
            payment_ref=None, created_at=datetime.now(UTC),
        )
        new_id = db.execute(
            sa_insert(applications).values(**copy).returning(applications.c.id)
        ).scalar_one()
        for table in tables:
            row = db.execute(
                sa_select(table).where(table.c.application_id == application_id)
            ).mappings().first()
            if row is not None:
                db.execute(sa_insert(table).values(**{**row, "application_id": new_id}))
        db.execute(
            sa_insert(accounts.application_referrals).values(application_id=new_id, **referral)
        )
        if haze_bonus:
            db.execute(sa_insert(accounts.application_haze_bonus).values(application_id=new_id))
    return {"application_id": new_id, "status": "referred", "tier": tier_key,
            "referral_reason": referral["reason"]}


def drop_policies(db, which) -> int:
    """Delete the policies that match, with any change of tier they were waiting for."""
    changes = accounts.policy_tier_changes
    ids = sa_select(accounts.policies.c.id).where(which)
    db.execute(sa_delete(changes).where(changes.c.policy_id.in_(ids)))
    bonus = accounts.policy_haze_bonus
    db.execute(sa_delete(bonus).where(bonus.c.policy_id.in_(ids)))
    return db.execute(sa_delete(accounts.policies).where(which)).rowcount


# UEN formats from ACRA: 8 digits + letter (businesses), 9 digits + letter (local companies),
# or T/S/R + 2 digits + 2 letters + 4 digits + letter (other entities).
UEN = re.compile(r"^(\d{8}[A-Z]|\d{9}[A-Z]|[TSR]\d{2}[A-Z]{2}\d{4}[A-Z])$")
# Singapore mobile and fixed-line numbers: 8 digits starting with 3, 6, 8 or 9.
SG_PHONE = re.compile(r"^[3689]\d{7}$")
PAYMENT_REF = re.compile(r"^DEMO-[0-9A-F]{6}$")
MAX_QR_AMOUNT_SGD = 1000


SINGAPORE = ZoneInfo("Asia/Singapore")
LATEST_COVER_START_DAYS = 90


class BuyRequest(SellerFields):
    """Everything the guided buy flow (/buy/) collects, sent once at the pay step.

    The form is filled in with the customer by their Income adviser or by an association
    (sold_by), never sold to them directly. See api/onboarding.py.

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
    sms_language: sms.SmsLanguage = Field(
        default="en", description="The language of every text Payung sends this customer."
    )
    add_safeday: bool
    add_haze_bonus: bool = False
    tier: str | None = None
    declined_before: bool
    declined_details: str | None = Field(default=None, max_length=500)
    accept_declaration: bool
    accept_pdpa: bool
    marketing_email: bool = False
    marketing_sms: bool = False
    payment_method: Literal["paynow", "giro"] | None = None
    payment_ref: str | None = Field(default=None, pattern=PAYMENT_REF.pattern)
    payment_token: str | None = Field(
        default=None, max_length=100,
        description="PayNow only: a paid payment from POST /api/premium-payments.",
    )

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
        if self.business_class not in onboarding.OPEN_CLASSES:
            raise ValueError(onboarding.NEXT_PHASE)
        {
            "hawker": self.hawker_complete,
            "shop": self.shop_complete,
            "platform_worker": self.platform_worker_complete,
        }[self.business_class]()
        self.channel_complete()
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
            raise ValueError("Pick a Payung tier")
        if self.add_haze_bonus and not self.add_safeday:
            raise ValueError("The severe haze payout is added to Payung: add Payung first")
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
        "open_classes": onboarding.OPEN_CLASSES,
        "sold_by": onboarding.SOLD_BY,
        "associations": onboarding.ASSOCIATIONS,
        "centre_associations": onboarding.CENTRE_ASSOCIATIONS,
        "platform_product": onboarding.PLATFORM_PRODUCT,
        "ssic_codes": [
            {"code": code, "title": title} for code, title in onboarding.SHOP_SSIC_CODES.items()
        ],
        "platforms": onboarding.PLATFORMS,
        "staff_bands": onboarding.STAFF_BANDS,
        "not_an_sme": onboarding.NOT_AN_SME,
        "terms_months": accounts.TERMS_MONTHS,
        "waiting_period_days": accounts.WAITING_PERIOD_DAYS,
        "cap_window_days": payout_flow.CAP_WINDOW_DAYS,
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
    body: BuyRequest, tariff: TariffDep, request: Request, response: Response
) -> dict:
    """Create the account, the application and, when Payung is added, its policy, then sign in.

    A past decline, or a tier the quote does not sell directly, sends the application to an
    underwriter: no policy starts and nothing is charged. Payment is simulated, and no money
    moves. PayNow needs a payment paid on the demo bank screen (api/premium.py), whose
    reference is kept; GIRO keeps the made-up DEMO- reference.
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
    priced = reason = None
    if body.add_safeday:
        postcode = body.postcode if body.business_class == "shop" else None
        priced = business_quote(
            request, tariff, body.product, user["region"], user["centre"], postcode
        )
        reason = referral_reason(chosen_tier(priced, body.tier), tariff)
    offer = None
    if body.add_haze_bonus:
        offer = haze_bonus_offer(chosen_tier(priced, body.tier), tariff)
    referred = body.declined_before or reason is not None
    pays = body.add_safeday and not referred
    if pays and body.payment_method is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick how to pay")
    paynow = pays and body.payment_method == "paynow"
    if paynow and not body.payment_token:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pay with PayNow first")
    now = datetime.now(UTC)
    cover_start = body.cover_start or now.astimezone(SINGAPORE).date()
    starts_at = max(now, datetime.combine(cover_start, datetime.min.time(), SINGAPORE))
    with engine.begin() as db:
        user_id = db.execute(
            sa_insert(accounts.users).values(**user).returning(accounts.users.c.id)
        ).scalar_one()
        policy = None
        payment_ref = None
        if pays:
            policy = policy_values(
                priced, user_id, user["region"], user["centre"], body.product, body.tier
            )
            policy["started_at"] = starts_at
            payment_ref = (
                premium.take_payment(
                    db, body.payment_token, body.tier, round(policy["weekly_premium_sgd"] * 100)
                )
                if paynow
                else body.payment_ref or demo_payment_ref()
            )
            policy["id"] = db.execute(
                sa_insert(accounts.policies).values(**policy).returning(accounts.policies.c.id)
            ).scalar_one()
            if offer is not None:
                policy["haze_bonus"] = add_haze_bonus(
                    db, policy["id"], offer, haze_bonus_starts(tariff, cover_start)
                )
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
            "payment_ref": payment_ref if pays else None,
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
        if reason is not None:
            db.execute(sa_insert(accounts.application_referrals).values(
                application_id=application["id"], reason=reason, product=body.product,
                weekly_premium_sgd=chosen_tier(priced, body.tier).weekly_premium_sgd,
            ))
        if offer is not None and referred:
            db.execute(sa_insert(accounts.application_haze_bonus).values(
                application_id=application["id"]
            ))
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
        channel = {
            "sold_by": body.sold_by,
            "adviser_code": body.adviser_code,
            "association": body.association,
        }
        db.execute(
            sa_insert(accounts.application_channel).values(application_id=application["id"], **channel)
        )
        sms.set_preferred_language(db, user_id, body.sms_language)
        payout_flow.send_welcome_if_due(db, user_id, tariff)
        application.update(details, **profile, **channel, referral_reason=reason)
    accounts.start_session(engine, user_id, response)
    return {
        "application": {k: v for k, v in application.items() if k != "user_id"},
        "policy": {k: v for k, v in policy.items() if k != "user_id"} if policy else None,
    }


def latest_application(engine, user_id: int) -> dict | None:
    """The user's latest application with its details, profile and channel, flat. Missing rows:
    nulls."""
    details, profile = accounts.application_details, accounts.application_profile
    channel = accounts.application_channel
    referrals = accounts.application_referrals
    query = (
        sa_select(
            accounts.applications,
            details.c.stall_unit,
            details.c.designation,
            details.c.cover_start,
            *(column for column in profile.c if column.name != "application_id"),
            *(column for column in channel.c if column.name != "application_id"),
            referrals.c.reason.label("referral_reason"),
        )
        .outerjoin(details, details.c.application_id == accounts.applications.c.id)
        .outerjoin(profile, profile.c.application_id == accounts.applications.c.id)
        .outerjoin(channel, channel.c.application_id == accounts.applications.c.id)
        .outerjoin(referrals, referrals.c.application_id == accounts.applications.c.id)
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
    """The stallholder's own policy, or every policy for an insurer, with any approved change
    of tier still waiting to start (tier_change) and the severe haze payout add-on (haze_bonus,
    with its lump sums paid). weekly_total_sgd is what the customer pays a week for both."""
    engine = request.app.state.db
    today = datetime.now(SINGAPORE).date()
    changes = accounts.policy_tier_changes
    query = (
        sa_select(accounts.policies, accounts.users.c.business_name, accounts.users.c.name)
        .join(accounts.users, accounts.users.c.id == accounts.policies.c.user_id)
        .order_by(accounts.policies.c.started_at.desc())
    )
    if user.role != "insurer":
        query = query.where(accounts.policies.c.user_id == user.id)
    with engine.connect() as db:
        rows = db.execute(query).mappings().all()
        coming = db.execute(
            sa_select(changes).where(changes.c.starts_on > today).order_by(changes.c.starts_on)
        ).mappings().all()
        shown = [
            {**{k: v for k, v in row.items() if k != "user_id"},
             **payout_flow.terms_on(db, row["id"], today)}
            for row in rows
        ]
        bonuses = haze_bonuses(db)
    waiting: dict[int, dict] = {}
    for change in coming:
        terms = {k: v for k, v in change.items() if k != "policy_id"}
        waiting.setdefault(change["policy_id"], terms)
    return [
        {**policy, "tier_change": waiting.get(policy["id"]),
         "haze_bonus": bonuses.get(policy["id"]),
         "weekly_total_sgd": round(policy["weekly_premium_sgd"] + (
             bonuses[policy["id"]]["weekly_sgd"] if policy["id"] in bonuses else 0), 2)}
        for policy in shown
    ]


def haze_bonuses(db) -> dict[int, dict]:
    """Every policy's severe haze payout add-on, with the lump sums it has paid."""
    paid: dict[int, list[dict]] = defaultdict(list)
    lumps = haze_bonus_payouts
    for row in db.execute(sa_select(lumps).order_by(lumps.c.loss_date)).mappings():
        paid[row["policy_id"]].append({
            "reference": payout_flow.bonus_reference(row["id"]), "loss_date": row["loss_date"],
            "policy_year_starts": row["policy_year_starts"],
            "unhealthy_days": row["unhealthy_days"], "amount_sgd": row["amount_cents"] / 100,
            "status": row["status"], "paid_at": row["paid_at"],
        })
    return {
        row["policy_id"]: {**haze_bonus_view(row), "payouts": paid[row["policy_id"]]}
        for row in db.execute(sa_select(accounts.policy_haze_bonus)).mappings()
    }


@app.delete("/api/policies/{policy_id}")
def cancel_policy(policy_id: int, user: SmeDep, request: Request) -> dict:
    engine = request.app.state.db
    with engine.begin() as db:
        gone = drop_policies(
            db, (accounts.policies.c.id == policy_id) & (accounts.policies.c.user_id == user.id)
        )
    if not gone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such policy on this account")
    return {"cancelled": policy_id}


@app.get("/api/insurer/portfolio")
def insurer_portfolio(user: InsurerDep, request: Request) -> dict:
    """What the signed-in insurer carries: sold policies aggregated by region and tier."""
    engine = request.app.state.db
    today = datetime.now(SINGAPORE).date()
    with engine.connect() as db:
        rows = [
            {**row, **payout_flow.terms_on(db, row["id"], today)}
            for row in db.execute(sa_select(accounts.policies)).mappings().all()
        ]
        bonuses = haze_bonuses(db)
        lump = haze_bonus_payouts
        lumps = db.execute(
            sa_select(lump.c.status, func.count(), func.sum(lump.c.amount_cents))
            .group_by(lump.c.status)
        ).all()
    on_policies = [bonuses[row["id"]] for row in rows if row["id"] in bonuses]
    bonus_yearly = sum(bonus["yearly_sgd"] for bonus in on_policies)
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
        # The severe haze payout add-on, priced and owed apart from the daily cover.
        "haze_bonus": {
            "policies": len(on_policies),
            "weekly_premium_sgd": round(bonus_yearly / calculator.WEEKS_PER_YEAR, 2),
            "annual_premium_sgd": round(bonus_yearly, 2),
            "lump_sum_exposure_sgd": round(sum(b["lump_sum_sgd"] for b in on_policies), 2),
            "lump_sums": {
                status_: {"count": count, "amount_sgd": cents / 100}
                for status_, count, cents in lumps
            },
        },
    }


@app.get("/api/admin/me")
def tariff_editor(editor: AdminDep) -> TariffEditor:
    return editor


# Accounts that scripts/seed_demo_policies.py makes for the pitch use this email domain.
DEMO_EMAIL_DOMAIN = "demo-seed.safeday.test"


def latest_application_ids():
    """Each user's latest buy-flow application id."""
    applications = accounts.applications
    return (
        sa_select(applications.c.user_id, func.max(applications.c.id).label("application_id"))
        .group_by(applications.c.user_id)
        .subquery()
    )


def payouts_by_policy():
    """Per policy: payouts paid, cents paid, and cents assessed but not paid yet (held, failed)."""
    rows = payout_api.payouts
    paid = rows.c.status == "paid"
    unpaid = rows.c.status.in_([s for s in payout_flow.COUNTED_TOWARDS_CAP if s != "paid"])
    return (
        sa_select(
            rows.c.policy_id,
            func.count().filter(paid).label("payouts_paid"),
            func.sum(rows.c.amount_cents).filter(paid).label("paid_cents"),
            func.sum(rows.c.amount_cents).filter(unpaid).label("owed_cents"),
        )
        .group_by(rows.c.policy_id)
        .subquery()
    )


def insurer_policy_view(row) -> dict:
    started_at = row["started_at"]
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    hidden = ("user_id", "email", "paid_cents", "owed_cents")
    return {
        **{k: v for k, v in row.items() if k not in hidden},
        "started_at": started_at,
        "waiting_ends": payout_flow.first_covered_day(started_at),
        "payouts_paid": row["payouts_paid"] or 0,
        "paid_sgd": (row["paid_cents"] or 0) / 100,
        "owed_sgd": (row["owed_cents"] or 0) / 100,
        "demo": row["email"].endswith("@" + DEMO_EMAIL_DOMAIN),
    }


@app.get("/api/insurer/policies")
def insurer_policies(_: InsurerDep, request: Request) -> list[dict]:
    """Every policy with its business, cover dates, underwriting note and payouts so far.

    demo is true for the made-up book that scripts/seed_demo_policies.py adds for the pitch.
    """
    policies, users, profile = accounts.policies, accounts.users, accounts.application_profile
    channel = accounts.application_channel
    decisions = underwriting.underwriting_decisions
    latest, paid = latest_application_ids(), payouts_by_policy()
    query = (
        sa_select(
            policies,
            users.c.business_name,
            users.c.name,
            users.c.email,
            profile.c.business_class,
            profile.c.postcode,
            profile.c.term_months,
            profile.c.cover_ends,
            channel.c.sold_by,
            channel.c.adviser_code,
            channel.c.association,
            decisions.c.decision.label("underwriting_decision"),
            decisions.c.note.label("underwriting_note"),
            paid.c.payouts_paid,
            paid.c.paid_cents,
            paid.c.owed_cents,
        )
        .join(users, users.c.id == policies.c.user_id)
        .outerjoin(latest, latest.c.user_id == policies.c.user_id)
        .outerjoin(profile, profile.c.application_id == latest.c.application_id)
        .outerjoin(channel, channel.c.application_id == latest.c.application_id)
        .outerjoin(decisions, decisions.c.application_id == latest.c.application_id)
        .outerjoin(paid, paid.c.policy_id == policies.c.id)
        .order_by(policies.c.started_at.desc(), policies.c.id.desc())
    )
    with request.app.state.db.connect() as db:
        rows = db.execute(query).mappings().all()
    return [insurer_policy_view(row) for row in rows]


@app.get("/api/admin/tariff")
def get_tariff(_: AdminDep, saved: SavedTariffDep) -> SavedTariff:
    return saved


@app.put("/api/admin/tariff")
def put_tariff(
    change: TariffChange,
    editor: AdminDep,
    saved: SavedTariffDep,
    request: Request,
) -> SavedTariff:
    """Save a new tariff version, made from the latest one. Every region and product must price."""
    if change.based_on_version != saved.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{saved.saved_by} saved version {saved.version} after you started. "
            "Reload to see it, then make your change again.",
        )
    calculator.check_prices(change.tariff, region_replays(change.tariff, request))
    return store.save(request.app.state.db, change.tariff, saved_by=editor.saved_by)


@app.post("/api/admin/preview")
def preview(body: PreviewRequest, _: AdminDep, request: Request) -> Preview:
    """Quote and payouts of an unsaved tariff, so an admin sees a change before saving it."""
    tariff = body.tariff
    return Preview(
        quote=region_quote(request, tariff, body.product, body.region),
        assessments=[
            calculator.assess(tariff, body.product, tier.key, body.readings)
            for tier in tariff.tiers
        ],
    )


def region_replays(tariff: Tariff, request: Request) -> list[calculator.Replay]:
    """Every PSI region's replay at its point, read with this tariff's station rule."""
    rule = readings.station_rule(tariff)
    points = request.app.state.map_static["region_points"]
    return [
        request.app.state.place_days.replay(rule, region, *points[region])
        for region in request.app.state.regions
    ]


app.include_router(accounts.router)
app.include_router(payout_api.router)
app.include_router(day_check.router)
app.include_router(underwriting.router)
app.include_router(premium.router)
app.include_router(assistant.router)
app.include_router(voice.router)
app.mount("/admin", StaticFiles(directory=API_DIR / "admin", html=True), name="admin")
app.mount("/map", StaticFiles(directory=API_DIR / "map", html=True), name="map")
app.mount("/", StaticFiles(directory=API_DIR / "site", html=True), name="site")
