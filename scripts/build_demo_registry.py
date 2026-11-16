"""Save 20 real, live Singapore companies from ACRA for the buy flow demo.

Writes data/registry/demo_companies.json. For each shop SSIC code the demo fills in, it takes the
first two live local companies (in ACRA's row order) with that primary SSIC code and a Singapore
postcode, from the first letters of the alphabet that have one. Each one is then looked up by UEN
the same way the API does (api/registry.py), so the file holds exactly what a live lookup returns.

Source: ACRA via data.gov.sg (Singapore Open Data Licence). Reads DATA_GOV_SG_API_KEY when set.
Run: uv run scripts/build_demo_registry.py
"""

from __future__ import annotations

import json
import time
from datetime import date

from api import postcodes, registry

# The shop SSIC codes the demo fills in (buy.js SHOP_KINDS), two companies each.
SSIC_CODES = ("47102", "47211", "47212", "47213", "47522", "47610", "47711", "47723", "47743", "56111", "56112")
PER_CODE = 2
WANTED = 20
PAUSE_SECONDS = 1.2


def candidates(code: str) -> list[dict]:
    """Up to PER_CODE live local companies with this primary SSIC code, one per letter."""
    found: list[dict] = []
    for letter, dataset in registry.DETAILS_BY_LETTER.items():
        filters = {
            "primary_ssic_code": code,
            "entity_status_description": "Live Company",
            "entity_type_description": "Local Company",
            "address_type": "LOCAL",
        }
        time.sleep(PAUSE_SECONDS)
        rows = registry.fetch_records(dataset, filters)
        row = next((r for r in rows if postcodes.is_known(str(r.get("postal_code", "")))), None)
        if row:
            print(f"{code} {letter}: {row['uen']} {row['entity_name']}")
            found.append(row)
        if len(found) == PER_CODE:
            break
    return found


def main() -> None:
    companies: list[dict] = []
    for code in SSIC_CODES:
        for row in candidates(code):
            time.sleep(PAUSE_SECONDS)
            business = registry.lookup_uen(row["uen"])
            if business and business.live:
                companies.append(business.model_dump(exclude={"source"}))
        if len(companies) >= WANTED:
            break
    registry.DEMO_COMPANIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    saved = {
        "source": "ACRA via data.gov.sg: 'Entities Registered with ACRA' and 'ACRA Information "
        "on Corporate Entities', Singapore Open Data Licence. Built by "
        "scripts/build_demo_registry.py.",
        "fetched_on": date.today().isoformat(),
        "companies": companies[:WANTED],
    }
    registry.DEMO_COMPANIES_PATH.write_text(json.dumps(saved, indent=2) + "\n")
    print(f"Saved {len(saved['companies'])} companies to {registry.DEMO_COMPANIES_PATH}")


if __name__ == "__main__":
    main()
