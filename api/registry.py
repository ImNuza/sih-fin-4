"""Who a business is, from the number it gives: a UEN (ACRA) or a hawker licence (demo register).

UEN: ACRA publishes every registered entity on data.gov.sg under the Singapore Open Data Licence.
Two datasets answer one UEN:
- "Entities Registered with ACRA" (ENTITIES): name, entity type, UEN status, registered postcode.
- "ACRA Information on Corporate Entities", one dataset per first letter of the name
  (DETAILS_BY_LETTER): full address and primary SSIC code. It covers sole proprietorships too.
The first call gives the name, the name picks the second dataset. If the second call fails, the
lookup still returns what the first call gave.

Licence: SFA has no open lookup for food stall licences. Its "Licensed Food Establishment Search"
(sfa.gov.sg/tools-and-resources/licensed-food-establishment-search) is a web form, and the open
"List of NEA Licensed Eating Establishments" on data.gov.sg stops in Sep 2016. So the prototype
checks hawker licences against a made-up register (DEMO_LICENCES_PATH). A live pilot needs a
data-sharing agreement with SFA.

The demo also keeps 20 real, live companies from ACRA (DEMO_COMPANIES_PATH, built by
scripts/build_demo_registry.py), so the buy flow fills in a shop without calling data.gov.sg.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

import requests
from pydantic import BaseModel

from api import onboarding
from api.kyc import api_key

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_COMPANIES_PATH = REPO_ROOT / "data" / "registry" / "demo_companies.json"
DEMO_LICENCES_PATH = REPO_ROOT / "data" / "registry" / "demo_licences.json"

DATASTORE = "https://data.gov.sg/api/action/datastore_search"
TIMEOUT_SECONDS = 6
# data.gov.sg, "Entities Registered with ACRA" (about 2.1 million rows).
ENTITIES = "d_3f960c10fed6145404ca7b821f263b87"
# data.gov.sg collection 2, "ACRA Information on Corporate Entities": one dataset per first
# letter of the entity name, and "Others" for a name that starts with a digit or a sign.
DETAILS_BY_LETTER = {
    "A": "d_8575e84912df3c28995b8e6e0e05205a", "B": "d_3a3807c023c61ddfba947dc069eb53f2",
    "C": "d_c0650f23e94c42e7a20921f4c5b75c24", "D": "d_acbc938ec77af18f94cecc4a7c9ec720",
    "E": "d_124a9bd407c7a25f8335b93b86e50fdd", "F": "d_4526d47d6714d3b052eed4a30b8b1ed6",
    "G": "d_b58303c68e9cf0d2ae93b73ffdbfbfa1", "H": "d_fa2ed456cf2b8597bb7e064b08fc3c7c",
    "I": "d_85518d970b8178975850457f60f1e738", "J": "d_478f45a9c541cbe679ca55d1cd2b970b",
    "K": "d_5573b0db0575db32190a2ad27919a7aa", "L": "d_a2141adf93ec2a3c2ec2837b78d6d46e",
    "M": "d_9af9317c646a1c881bb5591c91817cc6", "N": "d_67e99e6eabc4aad9b5d48663b579746a",
    "O": "d_5c4ef48b025fdfbc80056401f06e3df9", "P": "d_181005ca270b45408b4cdfc954980ca2",
    "Q": "d_4130f1d9d365d9f1633536e959f62bb7", "R": "d_2b8c54b2a490d2fa36b925289e5d9572",
    "S": "d_df7d2d661c0c11a7c367c9ee4bf896c1", "T": "d_72f37e5c5d192951ddc5513c2b134482",
    "U": "d_0cc5f52a1f298b916f317800251057f3", "V": "d_e97e8e7fc55b85a38babf66b0fa46b73",
    "W": "d_af2042c77ffaf0db5d75561ce9ef5688", "X": "d_1cd970d8351b42be4a308d628a6dd9d3",
    "Y": "d_31af23fdb79119ed185c256f03cb5773", "Z": "d_4e3db8955fdcda6f9944097bef3d2724",
}
OTHERS = "d_300ddc8da4e8f7bdc1bfc62d0d99e2e7"
ACRA_SOURCE = "ACRA via data.gov.sg"

# UEN formats from ACRA: 8 digits + letter (businesses: sole proprietorships and partnerships),
# 9 digits + letter (local companies), or T/S/R + 2 digits + 2 letters + 4 digits + letter
# (other entities, such as LLPs and societies).
UEN = re.compile(r"^(\d{8}[A-Z]|\d{9}[A-Z]|[TSR]\d{2}[A-Z]{2}\d{4}[A-Z])$")
BUSINESS_UEN = re.compile(r"^\d{8}[A-Z]$")
# The status words ACRA uses for an entity that still trades.
LIVE_STATUS = re.compile(r"^(Registered|Live)", re.IGNORECASE)
NOT_GIVEN = {"", "na", "n/a", "-"}


class RegistryUnavailable(Exception):
    """data.gov.sg did not answer, or refused the call (for example over its rate limit)."""


class Business(BaseModel):
    """One entity as ACRA lists it. Fields ACRA leaves empty are None."""

    uen: str
    name: str
    entity_type: str | None = None
    status: str | None = None
    live: bool
    postcode: str | None = None
    address: str | None = None
    ssic_code: str | None = None
    ssic_title: str | None = None
    source: str


class Licence(BaseModel):
    """One hawker stall licence in the demo register. Every entry is made up."""

    licence_no: str
    licensee_name: str
    business_name: str
    centre: str
    stall_unit: str | None = None
    product: str
    source: str = "Demo licence register (made up; SFA has no open lookup)"


def applicant_type(uen: str | None) -> str:
    """"company" for a company or other entity, "individual" for a licensee or a sole
    proprietorship or partnership. The UEN format says which: ACRA gives businesses 8 digits."""
    return "company" if uen and not BUSINESS_UEN.match(uen) else "individual"


def given(value: object) -> str | None:
    text = str(value or "").strip()
    return None if text.lower() in NOT_GIVEN else text


def fetch_records(resource_id: str, filters: dict) -> list[dict]:
    """Rows of one data.gov.sg dataset that match the filters. Raises RegistryUnavailable."""
    key = api_key("DATA_GOV_SG_API_KEY")
    try:
        response = requests.get(
            DATASTORE,
            params={"resource_id": resource_id, "filters": json.dumps(filters), "limit": 5},
            headers={"x-api-key": key} if key else {},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        raise RegistryUnavailable(str(error)) from error
    if not body.get("success"):
        raise RegistryUnavailable(str(body.get("error") or body.get("errorMsg") or body))
    return body["result"]["records"]


def details_dataset(name: str) -> str:
    first = name.strip()[:1].upper()
    return DETAILS_BY_LETTER.get(first, OTHERS)


def address_of(row: dict) -> str | None:
    """"1 WOODLANDS HEIGHT #04-06 KOUFU GROUP HQ Singapore 737859" from a details row."""
    street = " ".join(p for p in (given(row.get("block")), given(row.get("street_name"))) if p)
    level, unit = given(row.get("level_no")), given(row.get("unit_no"))
    parts = [
        street,
        f"#{level}-{unit}" if level and unit else None,
        given(row.get("building_name")),
        f"Singapore {given(row.get('postal_code'))}" if given(row.get("postal_code")) else None,
    ]
    return " ".join(p for p in parts if p) or None


def business_from(entity: dict, details: dict | None) -> Business:
    """One Business from an ENTITIES row and, when it was found, its details row."""
    status = given(entity.get("uen_status_desc"))
    detail_status = given((details or {}).get("entity_status_description"))
    code = given((details or {}).get("primary_ssic_code"))
    return Business(
        uen=entity["uen"],
        name=given(entity.get("entity_name")) or entity["uen"],
        entity_type=given(entity.get("entity_type_desc")),
        status=detail_status or status,
        live=bool(status and LIVE_STATUS.match(status))
        and (detail_status is None or bool(LIVE_STATUS.match(detail_status))),
        postcode=given((details or {}).get("postal_code")) or given(entity.get("reg_postal_code")),
        address=address_of(details) if details else None,
        ssic_code=code,
        ssic_title=onboarding.SHOP_SSIC_CODES.get(code or "")
        or given((details or {}).get("primary_ssic_description")),
        source=ACRA_SOURCE,
    )


@cache
def demo_companies() -> dict[str, Business]:
    """The 20 real companies the demo keeps, by UEN. Empty when the file is missing."""
    if not DEMO_COMPANIES_PATH.exists():
        return {}
    saved = json.loads(DEMO_COMPANIES_PATH.read_text())
    source = f"{ACRA_SOURCE}, saved {saved['fetched_on']}"
    return {
        row["uen"]: Business(**{**row, "source": source}) for row in saved["companies"]
    }


@cache
def demo_licences() -> dict[str, Licence]:
    """The made-up hawker licences, by licence number."""
    saved = json.loads(DEMO_LICENCES_PATH.read_text())
    return {row["licence_no"]: Licence(**row) for row in saved["licences"]}


LOOKED_UP: dict[str, Business] = {}
LOOKED_UP_LIMIT = 1000


def lookup_uen(uen: str) -> Business | None:
    """ACRA's record for a UEN, or None when ACRA has no entity with it.

    Raises RegistryUnavailable when data.gov.sg cannot be reached. The demo companies and earlier
    answers are served without a call."""
    uen = uen.strip().upper()
    if uen in demo_companies():
        return demo_companies()[uen]
    if uen in LOOKED_UP:
        return LOOKED_UP[uen]
    entities = fetch_records(ENTITIES, {"uen": uen})
    if not entities:
        return None
    entity = entities[0]
    try:
        rows = fetch_records(details_dataset(entity.get("entity_name") or ""), {"uen": uen})
        complete = True
    except RegistryUnavailable:
        rows, complete = [], False
    business = business_from(entity, rows[0] if rows else None)
    # An answer without its details is not kept, so the next lookup tries the details again.
    if complete and len(LOOKED_UP) < LOOKED_UP_LIMIT:
        LOOKED_UP[uen] = business
    return business


def lookup_licence(licence_no: str) -> Licence | None:
    """The demo register's entry for a licence number, or None."""
    return demo_licences().get(licence_no.strip().upper())
