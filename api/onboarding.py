"""What the buy flow (/buy/) asks each business class, and the rules it checks them against.

Three classes, one sign-up path each:
- "hawker": a stall at an NEA hawker centre. Licensed hawkers need no ACRA registration: the
  Business Names Registration Act 2014, s 4(1)(q), keeps the exemption for the businesses in the
  First Schedule to the Business Registration Act (Cap. 32), licensed hawkers among them (ACRA,
  acra.gov.sg/regulations/legislation/business-names-registration-act). So an individual hawker
  gives a licence number, not a UEN.
- "shop": a neighbourhood shop, identified by its postcode and SSIC 2025 code.
- "platform_worker": a ride-hail or delivery worker under a platform work agreement with a
  platform operator, as the Platform Workers Act 2024 defines one (MOM,
  mom.gov.sg/employment-practices/platform-workers-act/platform-worker). Always an individual.
"""

from __future__ import annotations

import re
from typing import Literal, get_args

BusinessClass = Literal["hawker", "shop", "platform_worker"]
BUSINESS_CLASSES = get_args(BusinessClass)
# The pilot sells to hawker stalls and neighbourhood shops only. Platform workers join in the next
# phase (team decision, 15 Nov 2026); their path stays built and the buy flow shows it as coming.
OPEN_CLASSES = ("hawker", "shop")
NEXT_PHASE = "Platform workers join in the next phase. The pilot covers hawker stalls and shops"
PLATFORM_PRODUCT = "platform_work"

# SFA food stall licence or NEA stall tenancy number. Formats differ by issuer, so only the
# characters and length are checked.
LICENCE_NO = re.compile(r"^[A-Z0-9/-]{5,20}$")
SSIC_CODE = re.compile(r"^\d{5}$")

# Codes and titles exactly as SingStat publishes them: Singapore Standard Industrial
# Classification 2025, https://singstat.gov.sg/files/603e56e4-d7b3-416e-91fa-24ec2e6ab54f.pdf
SHOP_SSIC_CODES = {
    "47102": "Mini-marts, convenience stores and provision shops",
    "47211": "Retail sale of fruits and vegetables",
    "47212": "Retail sale of meat, poultry, eggs and seafood",
    "47213": "Retail sale of confectionery and bakery products (not manufactured on site)",
    "47219": "Retail sale of food n.e.c.",
    "47220": "Retail sale of beverages",
    "47411": "Retail sale of handphones and related telecommunications and peripheral equipment",
    "47522": "Retail sale of hardware",
    "47610": "Retail sale of books, newspapers and stationery",
    "47711": "Retail sale of clothing for adults",
    "47721": "Retail sale of personal care products",
    "47722": "Pharmacies and drug stores (Western)",
    "47723": "Chinese medicine shops",
    "47743": "Retail sale of cut flowers",
    "47761": "Retail sale of joss paper and other ceremonial products",
    "56111": "Restaurants",
    "56112": "Cafes",
    "56122": "Operators of food courts, hawker centres, coffee shops and canteens "
    "(with mainly food and beverage income)",
    "96011": "Laundry and dry cleaning services (except self-operated laundries)",
    "96021": "Hairdressing salons/shops",
    "96022": "Beauty salons and spas",
}

PLATFORMS = (
    "Grab", "Gojek", "foodpanda", "Deliveroo", "Lalamove", "Ryde", "TADA", "CDG Zig", "Other",
)

StaffBand = Literal["1-4", "5-9", "10-49", "50-200", "over-200"]
STAFF_BANDS = get_args(StaffBand)
PLATFORM_WORKER_STAFF_BAND = "1-4"
# An SME has operating revenue up to S$100 million or employment up to 200 workers (Enterprise
# Singapore and SingStat, as MOM quotes them in its written answer to a parliamentary question
# on the distribution of SMEs, 3 Mar 2026, mom.gov.sg/newsroom/parliament-questions-and-replies).
OVER_SME_STAFF_BAND = "over-200"
NOT_AN_SME = (
    "Payung is for small and medium enterprises: annual sales up to S$100 million or up to "
    "200 workers (Enterprise Singapore and SingStat definition)"
)

# Income sells SmartBiz 360 through intermediaries, and a sale around the customer's agent is not
# allowed (Income product lead, private mentoring session, 15 Nov 2026). So every application
# names who arranged it with the customer: their Income adviser, or an association that offers
# Payung to its members as a group scheme.
SoldBy = Literal["adviser", "association"]
SOLD_BY = {
    "adviser": "Income adviser",
    "association": "Hawker or merchants' association",
}
# Income's adviser code format is not public, so only the characters and length are checked.
ADVISER_CODE = re.compile(r"^[A-Z0-9]{4,12}$")
ASSOCIATION_NAME_LENGTH = (3, 120)
# Suggestions for the association field, not a closed list: the Federation of Merchants'
# Associations, Singapore (75 member associations, FMAS Instagram post of 27 Aug 2026) and centre
# associations named in the press (Mothership Feb 2025, NLB Infopedia, TNP Oct 2024, Must Share
# News May 2024, CNA 20 May 2026). Sources in docs/notes/distribution-proposal-2026-11-15.md.
FMAS = "Federation of Merchants' Associations, Singapore (FMAS)"
# Each centre association by the name of its centre in data/processed/map_static.json.
CENTRE_ASSOCIATIONS = {
    "Tiong Bahru Market": "Tiong Bahru Market Hawkers' Association",
    "Smith Street Blk 335 (Chinatown Complex Market)": "Chinatown Complex Hawkers' Association",
    "Old Airport Road Blk 51 (51 Old Airport Road Food Centre and Shopping Mall)":
        "Old Airport Road Food Centre Merchants' Association",
    "Ghim Moh Road Blk 20": "Ghim Moh Market & Shops Merchants' Association",
    "Bedok North Street 1 Blk 216":
        "Bedok North Blk 216 Food Centre and Market Hawkers' Association",
}
ASSOCIATIONS = (FMAS, *CENTRE_ASSOCIATIONS.values())


def association_for(centre: str | None) -> str:
    """The association a stall at this centre would join through: its centre's own, else FMAS."""
    return CENTRE_ASSOCIATIONS.get(centre or "", FMAS)
