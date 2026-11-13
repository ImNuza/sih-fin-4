"""Download the static geospatial datasets the risk map is built from.

Usage:
    uv run scripts/fetch_geo.py

Reads  nothing (calls the data.gov.sg dataset download API; needs DATA_GOV_SG_API_KEY)
Writes data/raw/geo/hawker_centres.geojson        NEA hawker centre locations and stall counts
       data/raw/geo/planning_areas.geojson        URA Master Plan 2019 planning area boundaries
"""

from __future__ import annotations

from dgs import REPO_ROOT, download_dataset

RAW_DIR = REPO_ROOT / "data" / "raw" / "geo"
DATASETS = {
    # data.gov.sg dataset IDs, from each dataset's URL.
    "hawker_centres.geojson": "d_4a086da0a5553be1d89383cd90d07ecd",  # NEA Hawker Centres (GEOJSON)
    "planning_areas.geojson": "d_4765db0e87b9c86336792efe8a1f7a66",  # URA MP2019 Planning Area (No Sea)
}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, dataset_id in DATASETS.items():
        path = RAW_DIR / name
        path.write_bytes(download_dataset(dataset_id))
        print(f"Wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
