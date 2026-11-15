"""Add a made-up book of 200 business policies for the insurer dashboard demo, or remove it.

Every demo account has an email at api.main.DEMO_EMAIL_DOMAIN, so the dashboard tags its
policies "demo" and --remove deletes only them. The businesses are made up. Their places are
real: hawker centres from data/processed/map_static.json and URA postal sectors. Each policy is
priced by the live tariff through api.main.business_quote and policy_values, as the buy flow
prices one. The same 200 records come out on every run, and a rerun adds only the missing ones.

Usage:
    uv run scripts/seed_demo_policies.py            add the demo book
    uv run scripts/seed_demo_policies.py --remove   delete every demo record

Reads  DATABASE_URL (default: the API's SQLite file api/tariff.db), the latest saved tariff,
       data/processed/site_hazard_readings.csv, data/processed/map_static.json
Writes users, applications, application_details, application_profile, application_channel,
       policies and underwriting_decisions rows for the demo accounts. Refuses a database that is not on
       this machine.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import Engine, delete, insert, select
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from api import accounts, onboarding, postcodes, store  # noqa: E402
from api.main import (  # noqa: E402
    DEFAULT_DATABASE_URL,
    DEFAULT_TARIFF_PATH,
    DEMO_EMAIL_DOMAIN,
    HISTORY_PATH,
    MAP_STATIC_PATH,
    SINGAPORE,
    business_quote,
    cover_dates,
    load_history,
    policy_values,
)
from api.models import Tariff  # noqa: E402
from api.payouts import (  # noqa: E402
    payout_accounts, payout_events, payouts, sms_codes, sms_messages,
)
from api.underwriting import underwriting_decisions  # noqa: E402

DEMO_POLICIES = 200
RANDOM_SEED = 2026
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
DAYS_BACK = 365
DAYS_APPLIED_BEFORE_START = (1, 6)
# The pilot sells to hawker stalls and shops only (api/onboarding.py OPEN_CLASSES).
CLASS_WEIGHTS = {"hawker": 0.65, "shop": 0.35}
TIER_WEIGHTS = {"tier_1": 0.25, "tier_2": 0.40, "tier_3": 0.25, "tier_4": 0.10}
TERM_WEIGHTS = {12: 0.7, 24: 0.3}
SOLD_BY_WEIGHTS = {"adviser": 0.7, "association": 0.3}
DECLINED_BEFORE_SHARE = 0.04
FRESH_PRODUCE_STALL_SHARE = 0.2
UNDERWRITER_EMAIL = f"underwriter@{DEMO_EMAIL_DOMAIN}"
UNDERWRITER_NAME = "Demo underwriter"
INSURER = accounts.INSURERS[0]

OWNERS = (
    "Ah Seng", "Mei Ling", "Kumar", "Siti", "Hock Lee", "Rahman", "Ah Huat", "Murugan", "Fatimah",
    "Jia Hui", "Ravi", "Zainal", "Bee Choo", "Lakshmi", "Kok Wah", "Aminah", "Teck Soon", "Devi",
)
PEOPLE = (
    "Tan Wei Ming", "Nurul Huda binte Ismail", "Priya Nair", "Lim Jun Jie", "Muhammad Hafiz",
    "Chen Xiaoling", "Daniel Ong", "Siva Rajan", "Goh Hui Min", "Farid bin Osman", "Wong Kai Lun",
    "Anita Pillai", "Lee Bao Zhu", "Hamid Yusof", "Koh Shu Fen", "Arun Kumar", "Yeo Chee Keong",
)
COOKED_DISHES = (
    "Chicken Rice", "Char Kway Teow", "Nasi Lemak", "Fishball Noodles", "Prawn Mee", "Laksa",
    "Roti Prata", "Mixed Rice", "Satay", "Wonton Mee", "Bak Chor Mee", "Carrot Cake",
    "Hokkien Mee", "Duck Rice", "Mee Rebus", "Briyani", "Rojak", "Kopi and Toast",
)
MARKET_STALLS = ("Fresh Fish", "Vegetables", "Poultry", "Seafood", "Pork", "Tofu and Beansprouts")
# SSIC 2025 code (api/onboarding.py) to the tariff product and a shop-name ending.
SHOP_KINDS = {
    "47102": ("packaged_food", "Provision Shop"),
    "47211": ("fresh_produce", "Fruits and Vegetables"),
    "47213": ("packaged_food", "Bakery"),
    "47220": ("packaged_food", "Drinks Supply"),
    "47522": ("general_goods", "Hardware"),
    "47610": ("general_goods", "Bookshop"),
    "47711": ("general_goods", "Fashion"),
    "47723": ("general_goods", "Medical Hall"),
    "47743": ("flowers", "Florist"),
    "56112": ("cooked_food", "Cafe"),
    "96011": ("general_goods", "Laundry"),
    "96021": ("general_goods", "Hair Studio"),
}
APPROVAL_NOTES = (
    "The past decline was for flood damage at an earlier stall. This place has no flood record, "
    "so cover is approved at the standard price.",
    "The last insurer declined over late premiums in 2024. Premiums have been paid on time "
    "since, so cover is approved.",
    "The earlier decline was for a different business at the same address. Approved.",
)


def database_url() -> str:
    """DATABASE_URL, or the API's own SQLite file. Raises for a database on another host."""
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" and parsed.host not in LOCAL_HOSTS:
        raise SystemExit(
            f"DATABASE_URL points to {parsed.host}. Demo policies go only into a database on "
            "this machine (SQLite, or a server on localhost)."
        )
    return url


def current_tariff(engine: Engine) -> Tariff:
    """The latest saved tariff. An empty database first gets the default, as the API does."""
    saved = store.latest(engine)
    if saved is None:
        default = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
        saved = store.save(engine, default, saved_by="default")
    return saved.tariff


def weighted(rng: random.Random, weights: dict):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def postcode_of(centre: dict) -> str | None:
    """The postcode at the end of a centre's address, as the buy flow reads it, or None."""
    match = postcodes.ADDRESS_POSTCODE.search(centre["address"])
    return match.group(1) if match else None


def sector_postcode(rng: random.Random) -> str:
    """A made-up postcode in a real URA postal sector, so it maps to a real PSI region."""
    sector = rng.choice(sorted(postcodes.SECTOR_REGION))
    return f"{sector}{rng.randint(0, 9999):04d}"


def hawker_business(rng: random.Random, number: int, centres: list[dict]) -> dict:
    centre = rng.choice(centres)
    fresh = rng.random() < FRESH_PRODUCE_STALL_SHARE
    trade = rng.choice(MARKET_STALLS if fresh else COOKED_DISHES)
    return {
        "business_class": "hawker",
        "business_name": f"{rng.choice(OWNERS)} {trade}",
        "centre": centre["name"],
        "region": centre["region"],
        "product": "fresh_produce" if fresh else "cooked_food",
        "licence_no": f"DEMO-SFA-{number:04d}",
        "postcode": postcode_of(centre),
        "stall_unit": f"#01-{rng.randint(1, 120):02d}",
        "staff_band": "1-4",
    }


def shop_business(rng: random.Random, number: int, centres: list[dict]) -> dict:
    ssic_code = rng.choice(list(SHOP_KINDS))
    product, ending = SHOP_KINDS[ssic_code]
    postcode = sector_postcode(rng)
    return {
        "business_class": "shop",
        "business_name": f"{rng.choice(OWNERS)} {ending}",
        "region": postcodes.region_of(postcode),
        "product": product,
        "ssic_code": ssic_code,
        "postcode": postcode,
        "staff_band": rng.choice(("1-4", "1-4", "5-9")),
    }


MAKE_BUSINESS = {"hawker": hawker_business, "shop": shop_business}


def demo_records(centres: list[dict], today: date) -> list[dict]:
    """The demo book: the same DEMO_POLICIES businesses, tiers and dates on every run."""
    rng = random.Random(RANDOM_SEED)
    # A second generator, so the channel draws leave the rest of the book as it was before.
    channel_rng = random.Random(f"{RANDOM_SEED}-channel")
    records = []
    for number in range(1, DEMO_POLICIES + 1):
        business = MAKE_BUSINESS[weighted(rng, CLASS_WEIGHTS)](rng, number, centres)
        cover_start = today - timedelta(days=rng.randrange(DAYS_BACK))
        started_at = datetime.combine(cover_start, time.min, SINGAPORE).astimezone(UTC)
        applied_at = started_at - timedelta(days=rng.randint(*DAYS_APPLIED_BEFORE_START))
        declined_before = rng.random() < DECLINED_BEFORE_SHARE
        records.append({
            **business,
            "email": f"business-{number:03d}@{DEMO_EMAIL_DOMAIN}",
            "name": business.get("name") or rng.choice(PEOPLE),
            "tier": weighted(rng, TIER_WEIGHTS),
            "term_months": weighted(rng, TERM_WEIGHTS),
            "cover_start": cover_start,
            "started_at": started_at,
            "applied_at": applied_at,
            "phone": f"{rng.choice('89')}{rng.randint(0, 9999999):07d}",
            "payment_method": rng.choice(("paynow", "giro")),
            "payment_ref": f"DEMO-{rng.randrange(16**6):06X}",
            "approval_note": rng.choice(APPROVAL_NOTES) if declined_before else None,
            **demo_channel(channel_rng, business),
        })
    return records


def demo_channel(rng: random.Random, business: dict) -> dict:
    """Who arranged a demo policy: a made-up Income adviser code, or the association a hawker or
    shop would join through."""
    sold_by = weighted(rng, SOLD_BY_WEIGHTS)
    if sold_by == "adviser":
        return {"sold_by": sold_by, "adviser_code": f"DEMO{rng.randrange(10**4):04d}",
                "association": None}
    return {"sold_by": sold_by, "adviser_code": None,
            "association": onboarding.association_for(business.get("centre"))}


def demo_user_ids(db) -> list[int]:
    users = accounts.users
    query = select(users.c.id).where(users.c.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))
    return list(db.execute(query).scalars())


def underwriter_id(db, password_hash: str) -> int:
    users = accounts.users
    found = db.execute(select(users.c.id).where(users.c.email == UNDERWRITER_EMAIL)).scalar()
    if found is not None:
        return found
    values = {
        "email": UNDERWRITER_EMAIL, "name": UNDERWRITER_NAME, "role": "insurer",
        "password_hash": password_hash, "insurer": INSURER, "created_at": datetime.now(UTC),
    }
    return db.execute(insert(users).values(**values).returning(users.c.id)).scalar_one()


def add_record(
    db, record: dict, tariff: Tariff, history, places, password_hash: str, underwriter: int
) -> None:
    """One demo business: its account, its accepted application and its priced policy."""
    user = {
        "email": record["email"], "name": record["name"], "role": "sme",
        "password_hash": password_hash, "business_name": record["business_name"],
        "centre": record.get("centre"), "region": record["region"], "product": record["product"],
        "created_at": record["applied_at"],
    }
    user_id = db.execute(
        insert(accounts.users).values(**user).returning(accounts.users.c.id)
    ).scalar_one()
    centre = record.get("centre")
    priced_by_postcode = not centre and record["business_class"] == "shop"
    priced = business_quote(
        places, tariff, history, record["product"], record["region"], centre=centre,
        postcode=record["postcode"] if priced_by_postcode else None,
    )
    policy = policy_values(
        priced, user_id, record["region"], centre, record["product"], record["tier"]
    )
    policy["started_at"] = record["started_at"]
    db.execute(insert(accounts.policies).values(**policy))
    declined_before = record["approval_note"] is not None
    application = {
        "user_id": user_id, "applicant_type": "individual", "phone": record["phone"],
        "add_safeday": True, "tier": record["tier"], "declined_before": declined_before,
        "declined_details": "Declined by another insurer before." if declined_before else None,
        "status": "accepted", "declaration_accepted_at": record["applied_at"],
        "pdpa_accepted_at": record["applied_at"], "marketing_email": False,
        "marketing_sms": False, "payment_method": record["payment_method"],
        "payment_ref": record["payment_ref"], "created_at": record["applied_at"],
    }
    application_id = db.execute(
        insert(accounts.applications).values(**application).returning(accounts.applications.c.id)
    ).scalar_one()
    db.execute(insert(accounts.application_details).values(
        application_id=application_id, stall_unit=record.get("stall_unit"),
        cover_start=record["cover_start"],
    ))
    profile_fields = ("business_class", "licence_no", "ssic_code", "postcode", "staff_band")
    db.execute(insert(accounts.application_profile).values(
        application_id=application_id,
        **{field: record.get(field) for field in profile_fields},
        **cover_dates(record["cover_start"], record["term_months"]),
    ))
    db.execute(insert(accounts.application_channel).values(
        application_id=application_id,
        **{field: record[field] for field in ("sold_by", "adviser_code", "association")},
    ))
    if declined_before:
        db.execute(insert(underwriting_decisions).values(
            application_id=application_id, decision="approve", note=record["approval_note"],
            decided_by=underwriter, decided_at=record["applied_at"] + timedelta(hours=20),
        ))


def priced_places(map_static: dict, sites) -> SimpleNamespace:
    """What api.main.business_quote reads from the running app, so each demo business is priced
    where the buy flow would price it: a hawker at its centre, a shop at its postcode's area."""
    state = SimpleNamespace(
        sites=sites,
        map_static=map_static,
        centres_by_name={c["name"]: c for c in map_static["hawker_centres"]},
        centres_by_sector=postcodes.centres_by_sector(map_static["hawker_centres"]),
    )
    return SimpleNamespace(app=SimpleNamespace(state=state))


def seed(engine: Engine) -> int:
    """Add the demo records that are missing. Returns how many it added."""
    tariff = current_tariff(engine)
    history, sites = load_history(HISTORY_PATH)
    map_static = json.loads(MAP_STATIC_PATH.read_text())
    centres = map_static["hawker_centres"]
    places = priced_places(map_static, sites)
    records = demo_records(centres, datetime.now(SINGAPORE).date())
    # Nobody signs in as a demo business, so one unguessable password serves them all.
    password_hash = accounts.hash_password(secrets.token_urlsafe(32))
    with engine.begin() as db:
        existing = set(db.execute(
            select(accounts.users.c.email)
            .where(accounts.users.c.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))
        ).scalars())
        missing = [record for record in records if record["email"] not in existing]
        underwriter = underwriter_id(db, password_hash)
        for record in missing:
            add_record(db, record, tariff, history, places, password_hash, underwriter)
    return len(missing)


def remove(engine: Engine) -> int:
    """Delete every demo account and everything that hangs off it. Returns accounts removed."""
    with engine.begin() as db:
        user_ids = demo_user_ids(db)
        application_ids = list(db.execute(
            select(accounts.applications.c.id).where(accounts.applications.c.user_id.in_(user_ids))
        ).scalars())
        payout_ids = list(db.execute(
            select(payouts.c.id).where(payouts.c.user_id.in_(user_ids))
        ).scalars())
        db.execute(delete(payout_events).where(payout_events.c.payout_id.in_(payout_ids)))
        for table in (sms_messages, payouts, payout_accounts, sms_codes, accounts.policies,
                      accounts.policy_channel, accounts.sessions, accounts.applications):
            db.execute(delete(table).where(table.c.user_id.in_(user_ids)))
        for table in (underwriting_decisions, accounts.application_details,
                      accounts.application_profile, accounts.application_channel):
            db.execute(delete(table).where(table.c.application_id.in_(application_ids)))
        db.execute(delete(accounts.users).where(accounts.users.c.id.in_(user_ids)))
    return len(user_ids)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--remove", action="store_true", help="delete every demo record")
    args = parser.parse_args(argv)
    engine = store.connect(database_url())
    try:
        if args.remove:
            print(f"Removed {remove(engine)} demo accounts and their policies.")
        else:
            added = seed(engine)
            print(f"Added {added} demo policies. {DEMO_POLICIES - added} were already there.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
