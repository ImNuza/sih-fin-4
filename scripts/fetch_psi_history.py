"""Download the NEA Historical 24-hr PSI dataset (hourly, by region, from April 2014).

It starts two years before the real-time PSI feed, so it adds the 2015 haze to the history.

Usage:
    uv run scripts/fetch_psi_history.py

Writes:
    data/raw/psi_history/historical_24hr_psi.csv   raw file (gitignored)
    data/psi/psi_history_24hr.parquet              one row per hour per region
"""

from __future__ import annotations

import io

import pandas as pd

from dgs import REPO_ROOT, download_dataset

DATASET_ID = "d_b4cf557f8750260d229c49fd768e11ed"
RAW_FILE = REPO_ROOT / "data" / "raw" / "psi_history" / "historical_24hr_psi.csv"
OUT_FILE = REPO_ROOT / "data" / "psi" / "psi_history_24hr.parquet"


def main() -> None:
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.write_bytes(download_dataset(DATASET_ID))
    wide = pd.read_csv(io.BytesIO(RAW_FILE.read_bytes()))
    time_column = wide.columns[0]
    table = wide.melt(id_vars=time_column, var_name="region", value_name="psi_twenty_four_hourly")
    # One source row has a malformed time ("2016-04-04 010:00:00"). It is dropped and counted.
    table["timestamp"] = pd.to_datetime(
        table.pop(time_column), format="%d/%m/%Y %H:%M", errors="coerce"
    ).dt.tz_localize("Asia/Singapore")
    unparsed_rows = table["timestamp"].isna().sum() // (len(wide.columns) - 1)
    table = table.dropna(subset=["timestamp"])
    table["psi_twenty_four_hourly"] = pd.to_numeric(
        table["psi_twenty_four_hourly"], errors="coerce"
    )
    table = table[["timestamp", "region", "psi_twenty_four_hourly"]].sort_values(
        ["timestamp", "region"]
    )
    table.to_parquet(OUT_FILE, index=False)
    print(f"{len(table)} region-hours, {table['timestamp'].min()} to {table['timestamp'].max()}, "
          f"regions {sorted(table['region'].unique())}, {unparsed_rows} source rows dropped "
          f"-> {OUT_FILE}")


if __name__ == "__main__":
    main()
