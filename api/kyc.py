"""Read a shop owner's own words (and an optional photo) into a tariff product and a map place.

The reading is advisory: it proposes a product and a place for the owner to confirm, and never
a price. With ANTHROPIC_API_KEY (environment or .env at the repo root) one Claude call classifies
the product; without it, or with no route to the Anthropic API, a keyword table does. Places
resolve against the hawker centres and planning areas in data/processed/map_static.json, and a
planning area stands for its most central hawker centre. Nothing sent here is stored.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

import anthropic
from pydantic import BaseModel

from api.models import KycPhoto, KycPlace, KycRequest, KycResult, Product

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
KEY_NAME = "ANTHROPIC_API_KEY"
MODEL = "claude-haiku-5-5"
MAX_ANSWER_TOKENS = 1024
FUZZY_CUTOFF = 0.85
MIN_ALIAS_CHARS = 4
MAX_ALIAS_WORDS = 8
# Words that end many centre names without telling one centre from another.
GENERIC_NAME_WORDS = {"market", "food", "centre", "hawker", "cooked", "and", "mart"}
# Checked in order, so a "seafood stall" is fresh produce, not cooked food.
PRODUCT_KEYWORDS = {
    "fresh_produce": ("fruit", "vegetable", "fish", "seafood", "meat"),
    "flowers": ("flower", "plant"),
    "packaged_food": ("drink", "snack", "packaged"),
    "general_goods": ("clothes", "clothing", "phone", "shoes", "general"),
    "cooked_food": ("cook", "noodle", "rice", "chicken", "stall"),
}

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Places:
    """Every name a place can be called by, and the exact names the model may choose from."""

    by_alias: dict[str, KycPlace]
    by_name: dict[str, KycPlace]


class ModelAnswer(BaseModel):
    product: str | None
    place_name: str | None
    confidence: float
    summary: str


def words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def without_generic_ending(name: str) -> str:
    parts = name.split()
    while parts and parts[-1] in GENERIC_NAME_WORDS:
        parts.pop()
    return " ".join(parts)


def centre_names(name: str) -> list[str]:
    """A centre's full name, its address part and each name in its brackets."""
    address, _, bracket = name.partition(" (")
    return [name, address, *bracket.rstrip(")").split("/")]


def ring_centre(ring: list[list[float]]) -> tuple[float, float, float]:
    """Area and centroid (lat, lng) of one polygon ring, by the shoelace formula."""
    lng0, lat0 = ring[0]
    area = lng_sum = lat_sum = 0.0
    for (lng1, lat1), (lng2, lat2) in zip(ring, ring[1:]):
        cross = (lng1 - lng0) * (lat2 - lat0) - (lng2 - lng0) * (lat1 - lat0)
        area += cross
        lng_sum += (lng1 + lng2 - 2 * lng0) * cross
        lat_sum += (lat1 + lat2 - 2 * lat0) * cross
    if area == 0:
        return 0.0, lat0, lng0
    return abs(area) / 2, lat0 + lat_sum / (3 * area), lng0 + lng_sum / (3 * area)


def outlines(geometry: dict) -> list[list[list[float]]]:
    """The outer ring of each piece of a planning area. Holes are ignored."""
    polygons = (
        [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    )
    return [polygon[0] for polygon in polygons]


def area_centre(geometry: dict) -> tuple[float, float]:
    """Centroid of a planning area's largest piece, so an island does not pull it out to sea."""
    _, lat, lng = max(ring_centre(ring) for ring in outlines(geometry))
    return lat, lng


def ring_holds(ring: list[list[float]], lat: float, lng: float) -> bool:
    """Ray casting: inside when a line east of the point crosses the ring an odd number of times."""
    inside = False
    for (lng1, lat1), (lng2, lat2) in zip(ring, ring[1:]):
        if (lat1 > lat) == (lat2 > lat):
            continue
        if lng < lng1 + (lat - lat1) * (lng2 - lng1) / (lat2 - lat1):
            inside = not inside
    return inside


def area_place(area: dict, centres: list[KycPlace]) -> KycPlace:
    """Where a shop "in Bedok" goes: the hawker centre in the area nearest its middle.

    An area with no hawker centre keeps its own middle, and the summary says so.
    """
    lat, lng = area_centre(area["geometry"])
    inside = [
        centre
        for centre in centres
        if any(ring_holds(ring, centre.lat, centre.lng) for ring in outlines(area["geometry"]))
    ]
    if not inside:
        return KycPlace(
            name=area["name"],
            lat=round(lat, 5),
            lng=round(lng, 5),
            region=area["psi_region"],
            match="planning_area",
            area=area["name"],
        )
    # Singapore is small enough that plain degree distance ranks neighbours correctly.
    nearest = min(inside, key=lambda centre: (centre.lat - lat) ** 2 + (centre.lng - lng) ** 2)
    return nearest.model_copy(update={"match": "planning_area", "area": area["name"]})


def load_places(map_static: dict) -> Places:
    centres = [
        KycPlace(
            name=centre["name"],
            lat=centre["lat"],
            lng=centre["lng"],
            region=centre["region"],
            match="hawker_centre",
        )
        for centre in map_static["hawker_centres"]
    ]
    areas = [area_place(area, centres) for area in map_static["planning_areas"]]
    by_alias: dict[str, KycPlace] = {}

    def add(alias: str, place: KycPlace) -> None:
        if len(alias) >= MIN_ALIAS_CHARS and without_generic_ending(alias):
            by_alias.setdefault(alias, place)

    # Earlier names win a shared alias: "Bedok" alone is the planning area, not Bedok Food Centre.
    for centre in centres:
        for name in centre_names(centre.name):
            add(words(name), centre)
    for area in areas:
        add(words(area.area), area)
    for centre in centres:
        for name in centre_names(centre.name):
            add(without_generic_ending(words(name)), centre)
    by_name = {centre.name: centre for centre in centres} | {area.area: area for area in areas}
    return Places(by_alias=by_alias, by_name=by_name)


def match_place(text: str, places: Places) -> KycPlace | None:
    """The longest place name written in the text, allowing small spelling slips."""
    tokens = words(text).split()
    phrases = {
        " ".join(tokens[start : start + size])
        for size in range(1, MAX_ALIAS_WORDS + 1)
        for start in range(len(tokens) - size + 1)
    }
    exact = [phrase for phrase in phrases if phrase in places.by_alias]
    if exact:
        return places.by_alias[max(exact, key=len)]
    close = [
        alias
        for phrase in phrases
        if len(phrase) >= MIN_ALIAS_CHARS
        for alias in get_close_matches(phrase, places.by_alias, n=1, cutoff=FUZZY_CUTOFF)
    ]
    return places.by_alias[max(close, key=len)] if close else None


def keyword_product(text: str, products: list[Product]) -> str | None:
    offered = {product.key for product in products}
    tokens = words(text).split()
    for key, keywords in PRODUCT_KEYWORDS.items():
        if key in offered and any(token.startswith(keywords) for token in tokens):
            return key
    return None


def api_key() -> str | None:
    if os.environ.get(KEY_NAME):
        return os.environ[KEY_NAME]
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == KEY_NAME and value.strip():
                return value.strip()
    return None


def prompt(products: list[Product], places: Places) -> str:
    product_lines = "\n".join(f"- {product.key}: {product.label}" for product in products)
    place_lines = "\n".join(f"- {name}" for name in places.by_name)
    return (
        "A small business owner in Singapore describes their shop so an insurance demo can put "
        "it on a map. Read their words, and the photo if there is one, and answer with:\n"
        "- product: the key of the one product below that best fits what they sell, or null "
        "if you cannot tell.\n"
        "- place_name: the place below where the shop is, copied exactly, or null if none "
        "fits. Use the photo only to judge the product, never the place.\n"
        "- confidence: 0 to 1, how sure you are of the product.\n"
        "- summary: one short line naming what the shop sells and where.\n"
        "Do not estimate any price, loss or payout.\n\n"
        f"Products:\n{product_lines}\n\nPlaces:\n{place_lines}"
    )


def ask_model(
    key: str, text: str, photo: KycPhoto | None, products: list[Product], places: Places
) -> ModelAnswer | None:
    """One Claude call. None when the API rejects it, the model refuses or the answer won't parse.

    A connection error is left to the caller: with no route to the API, keywords still work.
    """
    content: list[dict] = []
    if photo is not None:
        source = {"type": "base64", "media_type": photo.media_type, "data": photo.data}
        content.append({"type": "image", "source": source})
    content.append({"type": "text", "text": text or "(The owner sent only a photo.)"})
    try:
        response = anthropic.Anthropic(api_key=key).messages.parse(
            model=MODEL,
            max_tokens=MAX_ANSWER_TOKENS,
            output_config={"effort": "low"},
            system=prompt(products, places),
            messages=[{"role": "user", "content": content}],
            output_format=ModelAnswer,
        )
    except (anthropic.APIStatusError, ValueError) as error:
        # The owner can still pick the product by hand, so a failed reading is not fatal.
        log.warning("Shop reading failed: %s", type(error).__name__)
        return None
    if response.stop_reason == "refusal":
        return None
    return response.parsed_output


def with_place_note(summary: str, place: KycPlace | None) -> str:
    if place is None or place.area is None:
        return summary
    if place.name == place.area:
        return f"{summary} (no hawker centre found in {place.area}; priced at the area centre)"
    return f"{summary} (the hawker centre nearest the middle of {place.area})"


def keyword_reading(text: str, place: KycPlace | None, products: list[Product]) -> KycResult:
    product = keyword_product(text, products)
    label = next((p.label for p in products if p.key == product), "Shop")
    return KycResult(
        product=product,
        place=place,
        confidence=None,
        summary=with_place_note(f"{label} at {place.name}" if place else label, place),
        source="keywords",
    )


def read_shop(body: KycRequest, products: list[Product], places: Places) -> KycResult:
    place = match_place(body.text, places)
    key = api_key()
    if key is None:
        return keyword_reading(body.text, place, products)
    try:
        answer = ask_model(key, body.text, body.photo, products, places)
    except anthropic.APIConnectionError:
        log.warning("No route to the Anthropic API; matched keywords instead")
        return keyword_reading(body.text, place, products)
    if answer is None:
        return KycResult(product=None, place=place, confidence=None, summary="Shop", source="llm")
    place = place or places.by_name.get(answer.place_name)
    return KycResult(
        product=answer.product if answer.product in {p.key for p in products} else None,
        place=place,
        confidence=answer.confidence,
        summary=with_place_note(answer.summary, place),
        source="llm",
    )
