"""Build the static data bundles the risk map (/map/) loads: geography, exposure and hazard stats.

Usage:
    uv run scripts/build_map_static.py      (run fetch_geo.py, heat_stats.py and hazard_stats.py first)

Reads  data/raw/geo/planning_areas.geojson, data/raw/geo/hawker_centres.geojson
       data/raw/geo/hdb_buildings.geojson, data/raw/geo/hdb_property_information.csv
       data/processed/wbgt_stations.csv, data/processed/rain_station_days.parquet
       data/processed/psi_yearly.csv, data/processed/psi_episodes.csv
       data/rainfall/stations.csv, data/wbgt/*.parquet
Writes data/processed/map_static.json     one bundle: planning areas (simplified polygons),
       hawker centres with stall counts, station stats, PUB flood hotspots, yearly haze series
       data/processed/map_buildings.json  HDB block footprints near hawker centres, for the
       city view; heights are nominal at the HDB median storey count (see NOMINAL_STOREYS)
"""

from __future__ import annotations

import json

import pandas as pd
from shapely.geometry import mapping, shape

from dgs import REPO_ROOT

RAW_GEO = REPO_ROOT / "data" / "raw" / "geo"
PROC_DIR = REPO_ROOT / "data" / "processed"
OUT_PATH = PROC_DIR / "map_static.json"
BUILDINGS_PATH = PROC_DIR / "map_buildings.json"

# About 130 m at the equator: planning areas stay recognisable, the file stays small.
SIMPLIFY_TOLERANCE_DEG = 0.0012
MIN_RAIN_DAYS = 365
# City view: HDB blocks within this distance of a hawker centre, outer ring only.
BUILDING_RADIUS_DEG = 0.007  # about 780 m
BUILDING_TOLERANCE_DEG = 0.00005  # about 5.5 m: block outlines stay recognisable
# Block heights are nominal: the HDB Property Information max_floor_lvl median is 12 storeys,
# and the footprints dataset has no per-block join key for it (10% of block numbers are unique).
NOMINAL_STOREYS = 12
METRES_PER_STOREY = 3.0

# Label points of the five PSI regions, from regionMetadata in the NEA /psi API response.
# Same assignment rule as scripts/region_hazard_readings.py: nearest label point.
REGION_POINTS = {
    "north": (1.41803, 103.82),
    "south": (1.29587, 103.82),
    "east": (1.35735, 103.94),
    "west": (1.35735, 103.70),
    "central": (1.35735, 103.82),
}

# PUB "List of Hotspots in Singapore (as of 2 Feb 2026)": 19 road junctions and stretches with
# recent flash-flood occurrences (pub.gov.sg, Flood Management). PUB names roads only; the
# coordinates are approximate geocodes for display, not survey data.
FLOOD_HOTSPOTS = [
    ("Ang Mo Kio Ave 3 / Ave 8 junction", 1.3680, 103.8521),
    ("Bukit Timah Rd (Wilby Rd - Blackmore Dr)", 1.3340, 103.7823),
    ("Cavenagh Rd / Kramat Ln junction", 1.3008, 103.8418),
    ("Craig Rd / Tanjong Pagar Rd junction", 1.2786, 103.8437),
    ("Dunearn Rd (Rifle Range - Binjai Park)", 1.3350, 103.7855),
    ("Dunearn Rd (Hillcrest Rd - Watten Estate Rd)", 1.3280, 103.8065),
    ("Eng Neo Ave (Vanda Link - Dunearn Rd)", 1.3338, 103.7900),
    ("Enterprise Rd (Wan Lee Rd - Jalan Boon Lay)", 1.3255, 103.7085),
    ("Jalan Boon Lay (International Rd - Enterprise Rd)", 1.3320, 103.7130),
    ("Jalan Nipah", 1.3165, 103.9365),
    ("Lor 1 / Lor 2 Toa Payoh junction", 1.3397, 103.8458),
    ("Lorong Gambir (Lor Penchalak - Gambir Walk)", 1.3400, 103.8795),
    ("Lorong Kismis / Kismis Pl junction", 1.3335, 103.7725),
    ("Punggol Way (slip road to TPE)", 1.3960, 103.9075),
    ("Seletar North Link (Punggol Barat)", 1.4150, 103.8950),
    ("Service rd off Upper Paya Lebar Rd", 1.3480, 103.8875),
    ("Yishun Ave 5 (slip road to Ave 2)", 1.4330, 103.8365),
    ("Yishun Ave 7 / St 22 junction", 1.4400, 103.8420),
    ("King's Rd (Prince Rd - Lutheran Rd)", 1.3230, 103.8090),
]


def psi_region(lat: float, lng: float) -> str:
    return min(
        REGION_POINTS,
        key=lambda r: (lat - REGION_POINTS[r][0]) ** 2 + (lng - REGION_POINTS[r][1]) ** 2,
    )


def rounded_geometry(geometry: dict) -> dict:
    simplified = shape(geometry).simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
    result = mapping(simplified)

    def round_coords(coords: object) -> object:
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], 5), round(coords[1], 5)]
        return [round_coords(part) for part in coords]

    result["coordinates"] = round_coords(result["coordinates"])
    return result


def planning_areas() -> list[dict]:
    collection = json.loads((RAW_GEO / "planning_areas.geojson").read_text())
    areas = []
    for feature in collection["features"]:
        props = feature["properties"]
        geometry = shape(feature["geometry"])
        centroid = geometry.centroid
        areas.append(
            {
                "name": props["PLN_AREA_N"].title(),
                "ura_region": props["REGION_N"].replace(" REGION", "").title(),
                "psi_region": psi_region(centroid.y, centroid.x),
                "geometry": rounded_geometry(feature["geometry"]),
            }
        )
    return areas


def hawker_centres() -> list[dict]:
    collection = json.loads((RAW_GEO / "hawker_centres.geojson").read_text())
    centres = []
    for feature in collection["features"]:
        props = feature["properties"]
        if props.get("STATUS") != "Existing":
            continue
        point = shape(feature["geometry"]).centroid
        centres.append(
            {
                "name": props["NAME"],
                "address": props.get("ADDRESS_MYENV") or props.get("ADDRESSSTREETNAME") or "",
                "lat": round(point.y, 5),
                "lng": round(point.x, 5),
                "region": psi_region(point.y, point.x),
                "food_stalls": props.get("NUMBER_OF_COOKED_FOOD_STALLS") or 0,
                "built": props.get("EST_ORIGINAL_COMPLETION_DATE") or "",
            }
        )
    return centres


def wbgt_stations() -> list[dict]:
    stats = pd.read_csv(PROC_DIR / "wbgt_stations.csv")
    frames = [
        pd.read_parquet(path, columns=["station_id", "latitude", "longitude"])
        for path in sorted((REPO_ROOT / "data" / "wbgt").glob("wbgt_*.parquet"))
    ]
    locations = pd.concat(frames).groupby("station_id")[["latitude", "longitude"]].last()
    stations = []
    for row in stats.itertuples():
        if row.station_id not in locations.index:
            continue
        lat, lng = (float(v) for v in locations.loc[row.station_id])
        stations.append(
            {
                "id": row.station_id,
                "name": row.station_name,
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "days": int(row.days_with_data),
                "share_days_ge_32": float(row.share_days_ge_32),
                "hours_ge_32": float(row.total_hours_ge_32),
                "max_wbgt": float(row.max_wbgt),
            }
        )
    return stations


def rain_stations() -> list[dict]:
    days = pd.read_parquet(PROC_DIR / "rain_station_days.parquet")
    locations = pd.read_csv(REPO_ROOT / "data" / "rainfall" / "stations.csv").set_index(
        "station_id"
    )
    totals = days.groupby("station_id").agg(
        days=("day", "count"),
        days_ge_20=("hours_ge_20mm", lambda hours: int((hours > 0).sum())),
        days_ge_30=("hours_ge_30mm", lambda hours: int((hours > 0).sum())),
        wet_hours=("wet_hours", "mean"),
    )
    stations = []
    for station_id, row in totals.iterrows():
        if station_id not in locations.index or row.days < MIN_RAIN_DAYS:
            continue
        lat = float(locations.loc[station_id, "latitude"])
        lng = float(locations.loc[station_id, "longitude"])
        stations.append(
            {
                "id": station_id,
                "name": str(locations.loc[station_id, "station_name"]),
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "days": int(row.days),
                "share_days_ge_20": round(row.days_ge_20 / row.days, 4),
                "share_days_ge_30": round(row.days_ge_30 / row.days, 4),
                "wet_hours_per_day": round(float(row.wet_hours), 2),
            }
        )
    return stations


def hdb_buildings(centres: list[dict]) -> dict:
    """Outer rings of HDB blocks near hawker centres, for the city view."""
    collection = json.loads((RAW_GEO / "hdb_buildings.geojson").read_text())
    floors = pd.read_csv(RAW_GEO / "hdb_property_information.csv")
    points = [(c["lng"], c["lat"]) for c in centres]
    rings = []
    for feature in collection["features"]:
        geometry = shape(feature["geometry"])
        centroid = geometry.centroid
        if not any(
            abs(centroid.x - lng) < BUILDING_RADIUS_DEG and abs(centroid.y - lat) < BUILDING_RADIUS_DEG
            for lng, lat in points
        ):
            continue
        simplified = geometry.simplify(BUILDING_TOLERANCE_DEG, preserve_topology=True)
        parts = simplified.geoms if simplified.geom_type == "MultiPolygon" else [simplified]
        for part in parts:
            rings.append(
                [[round(lng, 5), round(lat, 5)] for lng, lat, *_ in part.exterior.coords]
            )
    return {
        "source": "HDB Existing Building footprints via data.gov.sg, filtered to blocks within "
        "about 780 m of a hawker centre.",
        "height_note": f"Heights are nominal at {NOMINAL_STOREYS} storeys x {METRES_PER_STOREY} m, "
        f"the HDB Property Information median of {floors.max_floor_lvl.median():.0f} storeys; "
        "the footprints dataset has no reliable per-block storey join.",
        "nominal_height_m": NOMINAL_STOREYS * METRES_PER_STOREY,
        "rings": rings,
    }


def main() -> None:
    for name in (
        "planning_areas.geojson",
        "hawker_centres.geojson",
        "hdb_buildings.geojson",
        "hdb_property_information.csv",
    ):
        if not (RAW_GEO / name).exists():
            raise SystemExit(f"{RAW_GEO / name} is missing. Run scripts/fetch_geo.py first.")
    bundle = {
        "sources": {
            "hazard": "NEA via data.gov.sg, Singapore Open Data Licence. Heat 16 Jan 2025 - "
            "7 Nov 2026, rain 2 Dec 2016 - 8 Nov 2026, haze 9 Mar 2016 - 7 Nov 2026.",
            "exposure": "NEA Hawker Centres dataset (existing centres, cooked-food stalls).",
            "geography": "URA Master Plan 2019 Planning Area Boundary (No Sea).",
            "flood": "PUB List of Hotspots in Singapore, 2 Feb 2026. Coordinates approximate.",
        },
        "region_points": {name: list(point) for name, point in REGION_POINTS.items()},
        "planning_areas": planning_areas(),
        "hawker_centres": hawker_centres(),
        "wbgt_stations": wbgt_stations(),
        "rain_stations": rain_stations(),
        "flood_hotspots": [
            {"name": name, "lat": lat, "lng": lng} for name, lat, lng in FLOOD_HOTSPOTS
        ],
        "psi_yearly": pd.read_csv(PROC_DIR / "psi_yearly.csv").to_dict("records"),
        "psi_episodes": pd.read_csv(PROC_DIR / "psi_episodes.csv").to_dict("records"),
    }
    OUT_PATH.write_text(json.dumps(bundle, separators=(",", ":")))
    print(
        f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}: "
        f"{len(bundle['planning_areas'])} planning areas, "
        f"{len(bundle['hawker_centres'])} hawker centres "
        f"({sum(c['food_stalls'] for c in bundle['hawker_centres']):,} food stalls), "
        f"{len(bundle['wbgt_stations'])} WBGT stations, "
        f"{len(bundle['rain_stations'])} rain gauges, "
        f"{OUT_PATH.stat().st_size:,} bytes"
    )
    buildings = hdb_buildings(bundle["hawker_centres"])
    BUILDINGS_PATH.write_text(json.dumps(buildings, separators=(",", ":")))
    print(
        f"Wrote {BUILDINGS_PATH.relative_to(REPO_ROOT)}: "
        f"{len(buildings['rings']):,} HDB blocks, {BUILDINGS_PATH.stat().st_size:,} bytes"
    )


if __name__ == "__main__":
    main()
