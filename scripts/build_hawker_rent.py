"""Monthly stall rent at each hawker centre on the map, from NEA's successful tender bids.

Usage:
    uv run scripts/build_hawker_rent.py   (run fetch_nea_tender_bids.py and build_map_static.py first)

Reads  data/processed/nea_tender_bids.csv   (from scripts/fetch_nea_tender_bids.py)
       data/processed/map_static.json       (from scripts/build_map_static.py)
Writes data/processed/hawker_rent.csv       one row per map centre: the median winning monthly bid
       for a cooked-food stall, how many bids it comes from and their dates. Centres with no
       bid on record get an empty median. The rent classes themselves live in the tariff
       (api/default_tariff.json), so the tariff desk can move the class limits.

Why bids: no public source gives hawker revenue. A stall's rent is its biggest fixed cost
that a bad day does not reduce, and NEA publishes every winning bid, so rent is the one
cost we can show per centre from real data.
"""

from __future__ import annotations

import json
import re

import pandas as pd

from dgs import REPO_ROOT

PROC_DIR = REPO_ROOT / "data" / "processed"
BIDS_PATH = PROC_DIR / "nea_tender_bids.csv"
MAP_PATH = PROC_DIR / "map_static.json"
OUT_PATH = PROC_DIR / "hawker_rent.csv"

# Rents rise over time, so use the last three years of bids when a centre has any.
RECENT_FROM = "2023-08"

# NEA names that the general rules below cannot match to a map centre.
ALIASES = {
    "BK 49 SIMS PLACE": "BLK 49 SIMS PLACE",
    # Same centre: NEA lists Blk 117 bids under Aljunied Avenue 2, 3 and 4.
    "BLK 117 ALJUNIED AVENUE 3": "BLK 117 ALJUNIED AVENUE 2",
    "BLK 117 ALJUNIED AVENUE 4": "BLK 117 ALJUNIED AVENUE 2",
    "BLK 32 NEW MARKET ROAD FOOD CENTRE": "BLK 32 NEW MARKET ROAD",
    "BLK 503 WEST COAST ROAD": "BLK 503 WEST COAST DRIVE",
    "BLK 79/79A CIRCUIT ROAD": "BLK 79 CIRCUIT ROAD",
    "HOLLAND VILLAGE MARKET": "HOLLAND VILLAGE MARKET AND FOOD CENTRE",
    "KALLANG ESTATE MARKET": "KALLANG ESTATE FRESH MARKET AND FOOD CENTRE",
}
ABBREVIATIONS = {"AVE": "AVENUE", "ST": "STREET", "RD": "ROAD", "LOR": "LORONG", "BK": "BLK"}


def normalise(name: str) -> str:
    name = name.upper().replace("&", " AND ").replace("'", "").replace(".", "")
    return " ".join(ABBREVIATIONS.get(word, word) for word in name.split())


def blocks(text: str) -> list[str]:
    """Block numbers in '20/21', '22A/B', '79/79A' or '2 and 3' form, one by one."""
    parts = re.split(r"/| AND ", text)
    first = parts[0]
    out = [first]
    for part in parts[1:]:
        # "22A/B" means 22A and 22B.
        out.append(re.sub(r"[A-Z]$", part, first) if re.fullmatch(r"[A-Z]", part) else part)
    return out


def map_keys(centre: dict) -> set[str]:
    """Every name NEA might use for a map centre."""
    name = normalise(centre["name"])
    outer = re.sub(r"\s*\(.*\)", "", name)
    keys = {outer, *re.findall(r"\((.*?)\)", name)}
    numbered = re.fullmatch(r"(.+?) BLK (.+)", outer)
    if numbered:
        keys |= {f"BLK {block} {numbered[1]}" for block in blocks(numbered[2])}
    address = re.match(r"(?:BLK )?([\w/]+(?: AND \w+)?), ([^,]+),", normalise(centre["address"]))
    if address:
        keys |= {f"BLK {block} {address[2]}" for block in blocks(address[1])}
    return keys


def main() -> None:
    for path in (BIDS_PATH, MAP_PATH):
        if not path.exists():
            raise SystemExit(f"{path} is missing. Run the script named in its docstring first.")
    centres = json.loads(MAP_PATH.read_text())["hawker_centres"]
    by_key = {key: centre["name"] for centre in centres for key in map_keys(centre)}

    bids = pd.read_csv(BIDS_PATH)
    bids = bids[bids.section == "cooked_food"].copy()
    nea_key = bids.centre.map(lambda name: normalise(ALIASES.get(name, name)))
    bids["map_centre"] = nea_key.map(by_key)
    unmatched = sorted(bids.loc[bids.map_centre.isna(), "centre"].unique())

    rows = []
    for centre in centres:
        mine = bids[bids.map_centre == centre["name"]]
        recent = mine[mine.month >= RECENT_FROM]
        used = recent if len(recent) else mine
        rows.append(
            {
                "centre": centre["name"],
                "region": centre["region"],
                "median_bid_sgd": round(float(used.bid_sgd.median()), 2) if len(used) else None,
                "bids": len(used),
                "basis": ("since " + RECENT_FROM) if len(recent) else ("2019 on" if len(mine) else "none"),
                "first_month": used.month.min() if len(used) else None,
                "last_month": used.month.max() if len(used) else None,
            }
        )
    table = pd.DataFrame(rows)
    OUT_PATH.write_text(table.to_csv(index=False))

    priced = table.dropna(subset=["median_bid_sgd"])
    print(
        f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(table)} centres, "
        f"{len(priced)} with a cooked-food bid on record "
        f"({(priced.basis != '2019 on').sum()} since {RECENT_FROM})"
    )
    quartiles = priced.median_bid_sgd.quantile([0.25, 0.5, 0.75]).round(0).tolist()
    print(f"Centre medians: quartiles {quartiles}, max {priced.median_bid_sgd.max():,.0f}")
    print(f"{len(unmatched)} NEA centres not on the map: {', '.join(unmatched)}")


if __name__ == "__main__":
    main()
