"""Small client for the data.gov.sg real-time APIs.

Reads DATA_GOV_SG_API_KEY from the environment or from .env at the repo root.
See docs/reference/data-gov-sg-api.md.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://api-open.data.gov.sg/v2/real-time/api"
REPO_ROOT = Path(__file__).resolve().parent.parent
# The API rejects Python's default User-Agent with HTTP 403, so send our own.
USER_AGENT = "sih-fin-4-data/0.1"
CODE_NOT_FOUND = 17
MAX_RETRIES = 6


def load_api_key() -> str:
    key = os.environ.get("DATA_GOV_SG_API_KEY")
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DATA_GOV_SG_API_KEY" and value.strip():
                return value.strip()
    sys.exit("DATA_GOV_SG_API_KEY is not set. Copy .env.example to .env and add the key.")


class DgsClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {"x-api-key": load_api_key(), "User-Agent": USER_AGENT, "Accept": "application/json"}
        )

    def get(self, path: str, params: dict) -> dict | None:
        """Return the JSON body, or None when the API has no data for the query."""
        url = f"{BASE_URL}/{path}"
        for attempt in range(MAX_RETRIES):
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(2**attempt)
                continue
            body = response.json()
            if body.get("code") == CODE_NOT_FOUND:
                return None
            if response.status_code != 200 or body.get("code") != 0:
                raise RuntimeError(f"{path} {params}: HTTP {response.status_code}, {body.get('errorMsg')}")
            return body
        raise RuntimeError(f"{path} {params}: still rate limited after {MAX_RETRIES} retries")

    def get_all_pages(self, path: str, params: dict) -> list[dict] | None:
        """Follow paginationToken and return every data object, or None when there is no data."""
        pages = []
        token = None
        while True:
            query = dict(params, paginationToken=token) if token else params
            body = self.get(path, query)
            if body is None:
                return None if not pages else pages
            pages.append(body["data"])
            token = body["data"].get("paginationToken")
            if not token:
                return pages
