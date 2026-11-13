"""Download monthly ENSO (ONI) and Indian Ocean Dipole (DMI) indices from NOAA PSL.

El Nino and a positive IOD bring dry seasons and haze to Singapore (2015, 2019, 2026), so these
are season-ahead features for the haze and rain models.

Sources:
    ONI: NOAA CPC via PSL, 3-month running mean of Nino 3.4 SST anomaly (ERSST), from 1950.
    DMI: NOAA PSL from HadISST, from 1870.

Usage:
    uv run scripts/fetch_climate_indices.py

Writes:
    data/climate_indices/climate_indices_monthly.csv   one row per month: oni, dmi
"""

from __future__ import annotations

import pandas as pd
import requests

from dgs import REPO_ROOT, USER_AGENT

INDEX_URLS = {
    "oni": "https://psl.noaa.gov/data/correlation/oni.data",
    "dmi": "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data",
}
MISSING_VALUE = -99.0
OUT_FILE = REPO_ROOT / "data" / "climate_indices" / "climate_indices_monthly.csv"


def parse_psl_table(text: str, name: str) -> pd.Series:
    """PSL files: a header line with the year range, then 'year v1 ... v12' rows, then notes."""
    first_year, last_year = (int(part) for part in text.splitlines()[0].split()[:2])
    values = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 13 or not parts[0].isdigit():
            continue
        year = int(parts[0])
        if not first_year <= year <= last_year:
            continue
        for month, value in enumerate(parts[1:], start=1):
            if float(value) > MISSING_VALUE:
                values[pd.Period(year=year, month=month, freq="M")] = float(value)
    return pd.Series(values, name=name)


def main() -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    series = []
    for name, url in INDEX_URLS.items():
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
        response.raise_for_status()
        series.append(parse_psl_table(response.text, name))
    table = pd.concat(series, axis=1).sort_index()
    table.index.name = "month"
    table.to_csv(OUT_FILE)
    print(f"{len(table)} months, {table.index.min()} to {table.index.max()} -> {OUT_FILE}")
    print(table.dropna().tail(3))


if __name__ == "__main__":
    main()
