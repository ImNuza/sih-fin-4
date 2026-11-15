"""PSI region of a Singapore postcode, from its postal sector (the first two digits).

Sectors and their postal districts: URA, "List of Postal Districts" (source: SingPost),
https://ura.gov.sg/Corporate/-/media/Corporate/Property/PMI-Online/List_Of_Postal_Districts.pdf
Each district takes the PSI region of the URA planning area that holds most of the general
locations URA names for it, as data/processed/map_static.json assigns planning areas to regions
(nearest NEA PSI label point). Sectors URA does not list (00, 74, 83 to 99) are refused.

area_point places a postcode on the map without an address lookup, so it works offline and for
made-up demo postcodes: see its docstring.
"""

from __future__ import annotations

import re
from statistics import fmean

POSTCODE = re.compile(r"^\d{6}$")
ADDRESS_POSTCODE = re.compile(r"Singapore (\d{6})\s*$")

DISTRICT_SECTORS = {
    "01": ("01", "02", "03", "04", "05", "06"),
    "02": ("07", "08"),
    "03": ("14", "15", "16"),
    "04": ("09", "10"),
    "05": ("11", "12", "13"),
    "06": ("17",),
    "07": ("18", "19"),
    "08": ("20", "21"),
    "09": ("22", "23"),
    "10": ("24", "25", "26", "27"),
    "11": ("28", "29", "30"),
    "12": ("31", "32", "33"),
    "13": ("34", "35", "36", "37"),
    "14": ("38", "39", "40", "41"),
    "15": ("42", "43", "44", "45"),
    "16": ("46", "47", "48"),
    "17": ("49", "50", "81"),
    "18": ("51", "52"),
    "19": ("53", "54", "55", "82"),
    "20": ("56", "57"),
    "21": ("58", "59"),
    "22": ("60", "61", "62", "63", "64"),
    "23": ("65", "66", "67", "68"),
    "24": ("69", "70", "71"),
    "25": ("72", "73"),
    "26": ("77", "78"),
    "27": ("75", "76"),
    "28": ("79", "80"),
}

# District 01-10 (Downtown Core, Bukit Merah, Queenstown, Rochor, Orchard, Tanglin): south.
# 11-12 (Novena, Toa Payoh) and 20-21 (Bishan, Ang Mo Kio, Bukit Timah): central.
# 13-19 (Geylang, Marine Parade, Bedok, Changi, Tampines, Hougang, Punggol): east.
# 22-24 (Jurong, Bukit Batok, Choa Chu Kang, Lim Chu Kang, Tengah): west.
# 25-28 (Woodlands, Sungei Kadut, Mandai, Yishun, Sembawang, Seletar): north.
DISTRICT_REGION = {
    **dict.fromkeys(("01", "02", "03", "04", "05", "06", "07", "08", "09", "10"), "south"),
    **dict.fromkeys(("11", "12", "20", "21"), "central"),
    **dict.fromkeys(("13", "14", "15", "16", "17", "18", "19"), "east"),
    **dict.fromkeys(("22", "23", "24"), "west"),
    **dict.fromkeys(("25", "26", "27", "28"), "north"),
}

SECTOR_REGION = {
    sector: DISTRICT_REGION[district]
    for district, sectors in DISTRICT_SECTORS.items()
    for sector in sectors
}

SECTOR_DISTRICT = {
    sector: district for district, sectors in DISTRICT_SECTORS.items() for sector in sectors
}

Places = dict[str, list[tuple[float, float]]]


class UnknownSector(ValueError):
    pass


def region_of(postcode: str) -> str:
    """The PSI region of a 6-digit postcode. Raises UnknownSector for a sector URA does not list."""
    if not POSTCODE.match(postcode):
        raise UnknownSector("Enter a 6-digit Singapore postcode")
    sector = postcode[:2]
    if sector not in SECTOR_REGION:
        raise UnknownSector(
            f"Postal sector {sector} is not a Singapore postal sector. Check the postcode"
        )
    return SECTOR_REGION[sector]


def centres_by_sector(hawker_centres: list[dict]) -> Places:
    """Location of every hawker centre whose address ends in a postcode, by postal sector."""
    places: Places = {}
    for centre in hawker_centres:
        match = ADDRESS_POSTCODE.search(centre["address"])
        if match:
            places.setdefault(match.group(1)[:2], []).append((centre["lat"], centre["lng"]))
    return places


def mean_place(places: list[tuple[float, float]]) -> tuple[float, float]:
    return round(fmean(lat for lat, _ in places), 5), round(fmean(lng for _, lng in places), 5)


def area_point(
    postcode: str, centres: Places, region_points: dict[str, list[float]]
) -> dict:
    """An approximate map point for a postcode: the area it is in, not its exact address.

    The point is the mean location of the hawker centres in the postcode's postal sector. With
    no centre in the sector, it is the mean of the centres in its postal district; with none
    there either, the NEA PSI label point of its region. basis names which area was used.
    Raises UnknownSector for a postcode region_of refuses.
    """
    region = region_of(postcode)
    sector = postcode[:2]
    district = SECTOR_DISTRICT[sector]
    in_district = [place for s in DISTRICT_SECTORS[district] for place in centres.get(s, [])]
    if sector in centres:
        (lat, lng), basis = mean_place(centres[sector]), f"postal sector {sector}"
    elif in_district:
        (lat, lng), basis = mean_place(in_district), f"postal district {district}"
    else:
        (lat, lng), basis = region_points[region], f"middle of the {region} region"
    return {"lat": lat, "lng": lng, "region": region, "basis": basis}
