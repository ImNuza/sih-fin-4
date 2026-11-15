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
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete as sa_delete
from sqlalchemy import insert as sa_insert
from sqlalchemy import select as sa_select

from api import accounts, calculator, kyc, store
from api.accounts import InsurerDep, Registration, SmeDep, UserDep
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
    app.state.rent = load_rent(RENT_PATH)
    app.state.live = LiveFeed()
    app.state.db = store.connect(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    try:
        saved = store.latest(app.state.db)
    except ValidationError:
        # Saved before the tariff gained fields (product margins, stations per trigger). Older
        # versions stay in the database; pricing starts again from the default tariff.
        saved = None
    if saved is None:
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
def quote(
    request: QuoteRequest,
    tariff: TariffDep,
    history: HistoryDep,
    sites: Annotated[Sites, Depends(sites)],
) -> Quote:
    """Weekly premium and payout of every tier, for a region or for one place and product."""
    if request.region is not None:
        return calculator.quote(tariff, history, request.region, request.product)
    return calculator.quote_at(
        tariff, history, sites, request.latitude, request.longitude, request.product
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
        "loss_day_parts": {
            region: {
                key: round(days, 4)
                for key, days in calculator.loss_day_parts(tariff, chosen, history[region]).items()
            }
            for region in sorted(history)
        },
    }




class ScenarioRequest(BaseModel):
    lat: float = Field(ge=1.1, le=1.6)
    lng: float = Field(ge=103.5, le=104.2)
    radius_km: float = Field(gt=0.05, le=15)
    readings: dict[str, float]
    extra_days_per_year: float = Field(default=5, ge=0, le=60)
    product: str = "cooked_food"
    tier: str = "tier_2"


@app.post("/api/map/scenario")
def map_scenario(
    body: ScenarioRequest, tariff: TariffDep, history: HistoryDep, request: Request
) -> dict:
    """Price a what-if day inside a drawn circle.

    The readings score one day's loss and payout (as /api/assess). The premium is stressed
    by assuming days like this hit the circle extra_days_per_year more times a year on top
    of the region's NEA history, then priced by the same engine as every quote.
    """
    assessment = calculator.assess(tariff, body.product, body.tier, body.readings)
    day_loss = assessment.loss_percent / 100
    tier = calculator.find(tariff.tiers, body.tier, "tier")
    centres = [
        centre
        for centre in request.app.state.map_static["hawker_centres"]
        if calculator.km_between(body.lat, body.lng, centre["lat"], centre["lng"]) <= body.radius_km
    ]
    regions = {}
    for region in sorted({centre["region"] for centre in centres}):
        priced = calculator.quote(tariff, history, region, body.product)
        baseline = next(t for t in priced.tiers if t.tier == body.tier)
        stressed_days = min(
            priced.expected_loss_days + body.extra_days_per_year * day_loss,
            tier.max_paid_days_per_year,
        )
        stressed_yearly = calculator.yearly_premium(
            stressed_days * tier.daily_payout_sgd, tariff.pricing
        )
        regions[region] = {
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
            **regions[centre["region"]],
        }
        for centre in centres
    ]
    stalls = sum(centre["food_stalls"] for centre in centres)
    return {
        "assessment": assessment,
        "regions": regions,
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


DAY_READINGS_PATH = REPO_ROOT / "data" / "processed" / "day_readings.csv.gz"


def day_readings(request: Request) -> dict[str, dict[str, dict[str, float]]]:
    """All historical daily readings, loaded once: {day: {kind: {site: value}}}."""
    if not hasattr(request.app.state, "day_readings"):
        if not DAY_READINGS_PATH.exists():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "day_readings.csv.gz is missing. Run scripts/build_day_readings.py.",
            )
        import csv as csv_module
        import gzip

        table: dict[str, dict[str, dict[str, float]]] = {}
        with gzip.open(DAY_READINGS_PATH, "rt", newline="") as file:
            for row in csv_module.DictReader(file):
                table.setdefault(row["day"], {}).setdefault(row["kind"], {})[row["site"]] = float(
                    row["value"]
                )
        request.app.state.day_readings = table
    return request.app.state.day_readings


@app.get("/api/map/day")
def map_day(date: str, request: Request) -> dict:
    """What NEA actually recorded on one past day: the worst reading of each peril.

    The map sets its simulator sliders from these maxima, so a replayed day prices
    through the same engine as any simulated one.
    """
    table = day_readings(request)
    available = sorted(table)
    if date not in table:
        return {
            "date": date,
            "available": {"min": available[0], "max": available[-1]},
            "found": False,
        }
    readings = table[date]

    def worst(kind: str) -> dict:
        sites = readings.get(kind, {})
        if not sites:
            return {"value": 0, "site": None}
        site = max(sites, key=sites.get)
        return {"value": sites[site], "site": site}

    return {
        "date": date,
        "available": {"min": available[0], "max": available[-1]},
        "found": True,
        "haze": worst("haze"),
        "rain": worst("rain"),
        "heat": worst("heat"),
        "haze_by_region": readings.get("haze", {}),
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


class PolicyRequest(BaseModel):
    tier: str
    product: str | None = None


def policy_values(
    tariff: Tariff, history: History, user_id: int, region: str, centre: str | None,
    product: str, tier_key: str,
) -> dict:
    """A policies row priced server-side from the region, for one tier. Raises on an unknown tier."""
    priced = calculator.quote(tariff, history, region, product)
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
    """Start a cover for the signed-in stallholder, priced server-side from their region.

    Refused while an underwriter is reviewing the stallholder's application.
    """
    application = latest_application(request.app.state.db, user.id)
    if application and application["status"] == "referred":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An underwriter is reviewing your application. Cover starts after they reply"
        )
    product = body.product or user.product or "cooked_food"
    values = policy_values(tariff, history, user.id, user.region, user.centre, product, body.tier)
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


SINGAPORE = ZoneInfo("Asia/Singapore")
LATEST_COVER_START_DAYS = 90


class BuyRequest(BaseModel):
    """Everything the guided buy flow (/buy/) collects, sent once at the pay step.

    Email and password are only checked for being present: the demo fills them with made-up
    values. An email that already has an account is still refused.
    """

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)
    business_name: str | None = Field(default=None, max_length=120)
    centre: str
    stall_unit: str | None = Field(default=None, max_length=20)
    product: str
    designation: str | None = Field(default=None, max_length=60)
    cover_start: date | None = Field(default=None, description="Singapore date. Empty: today.")
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
        if self.applicant_type == "company" and self.uen is None:
            raise ValueError("A company needs its UEN")
        if not (self.accept_declaration and self.accept_pdpa):
            raise ValueError("Tick the declaration and the personal data consent to continue")
        if self.add_safeday and self.tier is None:
            raise ValueError("Pick a SafeDay tier")
        if self.declined_before and not (self.declined_details or "").strip():
            raise ValueError("Say which insurer declined you and why")
        return self


@app.post("/api/buy")
def buy(
    body: BuyRequest, tariff: TariffDep, history: HistoryDep, request: Request, response: Response
) -> dict:
    """Create the account, the application and, when SafeDay is added, its policy, then sign in.

    A past decline sends the application to an underwriter: no policy starts and nothing is
    charged. Payment is a prototype step: no money moves, the reference is made up here.
    """
    engine = request.app.state.db
    calculator.find(tariff.products, body.product, "product")
    # model_construct skips Registration's email and password rules, which the demo does not need.
    account = Registration.model_construct(
        role="sme", name=body.name, email=body.email, password=body.password,
        business_name=body.business_name, centre=body.centre, product=body.product, insurer=None,
    )
    user = accounts.user_values(account, request)
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
            policy = policy_values(
                tariff, history, user_id, user["region"], user["centre"], body.product, body.tier
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
            "payment_ref": f"DEMO-{secrets.token_hex(3).upper()}" if pays else None,
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
        application.update(details)
    accounts.start_session(engine, user_id, response)
    return {
        "application": {k: v for k, v in application.items() if k != "user_id"},
        "policy": {k: v for k, v in policy.items() if k != "user_id"} if policy else None,
    }


def latest_application(engine, user_id: int) -> dict | None:
    details = accounts.application_details
    query = (
        sa_select(accounts.applications, details.c.stall_unit, details.c.designation, details.c.cover_start)
        .outerjoin(details, details.c.application_id == accounts.applications.c.id)
        .where(accounts.applications.c.user_id == user_id)
        .order_by(accounts.applications.c.id.desc())
    )
    with engine.connect() as db:
        row = db.execute(query).mappings().first()
    return {k: v for k, v in row.items() if k != "user_id"} if row else None


@app.get("/api/applications/mine")
def my_application(user: SmeDep, request: Request) -> dict | None:
    """The signed-in stallholder's latest buy-flow application, or null."""
    return latest_application(request.app.state.db, user.id)


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


app.include_router(accounts.router)
app.mount("/admin", StaticFiles(directory=API_DIR / "admin", html=True), name="admin")
app.mount("/map", StaticFiles(directory=API_DIR / "map", html=True), name="map")
app.mount("/", StaticFiles(directory=API_DIR / "site", html=True), name="site")
