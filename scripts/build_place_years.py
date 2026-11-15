"""Read every priced place's readings on every recorded day once, for the year-based price.

The price replays each day of data/processed/day_readings.csv.gz at the customer's place, read
through api/readings.py as a payout reads it (api/place_days.py). This reads them for every
place a business is priced at: each hawker centre, each PSI region's point (platform workers)
and each postcode area point (postcodes.area_point for every postal sector), under the default
tariff's station rule. The API then prices any tariff with that rule from this file in
milliseconds, and reads any other place or rule on demand.

Usage:
    uv run scripts/build_place_years.py       (run build_day_readings.py first)

Reads  data/processed/day_readings.csv.gz, data/processed/site_hazard_readings.csv,
       data/processed/map_static.json, api/default_tariff.json
Writes data/processed/place_day_readings.npz  (format in api/place_days.py)
"""

from __future__ import annotations

import json
import sys

import numpy as np

from dgs import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from api import place_days, postcodes, readings  # noqa: E402
from api.burn import load_day_table  # noqa: E402
from api.main import DEFAULT_TARIFF_PATH, HISTORY_PATH, MAP_STATIC_PATH, load_sites  # noqa: E402
from api.models import Tariff  # noqa: E402

PricedPlace = tuple[str, str, float, float]  # name, region, latitude, longitude


def priced_places(static: dict) -> list[PricedPlace]:
    """Every hawker centre, region point and postcode area point, each place once."""
    centres = [(c["name"], c["region"], c["lat"], c["lng"]) for c in static["hawker_centres"]]
    regions = [
        (f"{region} region", region, lat, lng)
        for region, (lat, lng) in sorted(static["region_points"].items())
    ]
    by_sector = postcodes.centres_by_sector(static["hawker_centres"])
    areas = []
    for sector in sorted(postcodes.SECTOR_REGION):
        point = postcodes.area_point(f"{sector}0000", by_sector, static["region_points"])
        areas.append((point["basis"], point["region"], point["lat"], point["lng"]))
    unique: dict[place_days.PlaceKey, PricedPlace] = {}
    for name, region, lat, lng in centres + regions + areas:
        unique.setdefault(place_days.place_key(region, lat, lng), (name, region, lat, lng))
    return list(unique.values())


def main() -> None:
    tariff = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
    rule = readings.station_rule(tariff)
    sites = load_sites(HISTORY_PATH)
    static = json.loads(MAP_STATIC_PATH.read_text())
    table = load_day_table()
    days, fed = place_days.feed_days(table)
    places = priced_places(static)
    values = np.stack([
        place_days.read_place(table, days, readings.history_place(region, lat, lng, sites), rule)
        for _, region, lat, lng in places
    ], axis=1)
    np.savez_compressed(
        place_days.PLACE_DAYS_PATH,
        days=days,
        fed=fed,
        readings=values,
        name=np.array([name for name, *_ in places]),
        region=np.array([region for _, region, _, _ in places]),
        latitude=np.array([lat for *_, lat, _ in places]),
        longitude=np.array([lng for *_, lng in places]),
        gauges_read=rule.gauges_read,
        heat_read=rule.heat_read,
        regions_on_hold=np.array(sorted(rule.regions_on_hold), dtype=str),
        gauges_on_hold=np.array(sorted(rule.gauges_on_hold), dtype=str),
        heat_on_hold=np.array(sorted(rule.heat_on_hold), dtype=str),
        inputs_sha256=place_days.inputs_sha256(),
    )
    path = place_days.PLACE_DAYS_PATH
    print(
        f"Wrote {path.relative_to(REPO_ROOT)}: {len(places)} places over {len(days):,} days "
        f"({days[0]} to {days[-1]}), {path.stat().st_size:,} bytes"
    )


if __name__ == "__main__":
    main()
