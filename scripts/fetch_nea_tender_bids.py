"""Download NEA's list of successful hawker stall tender bids and turn it into a table.

Usage:
    uv run scripts/fetch_nea_tender_bids.py

Reads  the NEA PDF "Tender bids for hawker stalls from January 2019 to July 2026" (nea.gov.sg),
       saved once to data/raw/nea_tender_bids/. A rerun reuses the saved copy.
Writes data/processed/nea_tender_bids.csv   one row per successful bid: section, centre,
       stall, trade, monthly bid in SGD and the tender month
"""

from __future__ import annotations

import re

import pandas as pd
import requests
from pypdf import PdfReader

from dgs import REPO_ROOT, USER_AGENT

PDF_URL = (
    "https://www.nea.gov.sg/docs/default-source/hawker-centres-documents/tender-notice-docs/"
    "successful-tenderers/tender-bids-from-jan-2019-to-jul-2026.pdf"
)
RAW_PATH = REPO_ROOT / "data" / "raw" / "nea_tender_bids" / PDF_URL.rsplit("/", 1)[1]
OUT_PATH = REPO_ROOT / "data" / "processed" / "nea_tender_bids.csv"

# One bid per line: centre, stall number (01-010, B1-01, 01-123A, 01-K1), trade, bid, month.
# One tender round is written "Feb/Mar 2025"; it is dated to its later month.
BID_LINE = re.compile(
    r"^(?P<centre>.+?) (?P<stall>[A-Z0-9]{2}-[A-Z]?\d{1,4}[A-Z]?)\"? (?P<trade>.+?) "
    r"\$(?P<bid>[\d,]+(?:\.\d+)?) (?:[A-Za-z]{3,4}/)?(?P<month>[A-Za-z]{3,4})[- ](?P<year>\d{4})$"
)
SECTIONS = ("COOKED FOOD STALL", "MARKET STALL", "LOCK-UP STALL")
# The PDF writes September as "Sept".
MONTHS = {"Sept": "Sep"}


def download() -> None:
    if RAW_PATH.exists():
        return
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(PDF_URL, headers={"User-Agent": USER_AGENT}, timeout=120)
    response.raise_for_status()
    RAW_PATH.write_bytes(response.content)


def parse() -> tuple[pd.DataFrame, list[str]]:
    rows, skipped, section = [], [], None
    for page in PdfReader(RAW_PATH).pages:
        for line in (page.extract_text() or "").splitlines():
            line = " ".join(line.split())
            if line in SECTIONS:
                section = line.removesuffix(" STALL").lower().replace(" ", "_")
                continue
            match = BID_LINE.match(line)
            if match is None:
                if "$" in line:
                    skipped.append(line)
                continue
            month = MONTHS.get(match["month"], match["month"])
            rows.append(
                {
                    "section": section,
                    "centre": match["centre"],
                    "stall": match["stall"],
                    "trade": match["trade"],
                    "bid_sgd": float(match["bid"].replace(",", "")),
                    "month": pd.to_datetime(f"{month}-{match['year']}", format="%b-%Y").strftime("%Y-%m"),
                }
            )
    return pd.DataFrame(rows), skipped


def main() -> None:
    download()
    bids, skipped = parse()
    OUT_PATH.write_text(bids.to_csv(index=False))
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(bids):,} bids")
    print(bids.groupby("section").bid_sgd.describe().round(0).to_string())
    if skipped:
        print(f"{len(skipped)} lines with a $ did not parse, for example:")
        for line in skipped[:5]:
            print("  " + line)


if __name__ == "__main__":
    main()
