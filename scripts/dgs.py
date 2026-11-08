"""Small client for the data.gov.sg real-time APIs.

Reads DATA_GOV_SG_API_KEY from the environment or from .env at the repo root.
See docs/reference/data-gov-sg-api.md.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import requests

BASE_URL = "https://api-open.data.gov.sg/v2/real-time/api"
REPO_ROOT = Path(__file__).resolve().parent.parent
# The API rejects Python's default User-Agent with HTTP 403, so send our own.
USER_AGENT = "sih-fin-4-data/0.1"
CODE_NOT_FOUND = 17
MAX_RETRIES = 12
MAX_BACKOFF_SECONDS = 60
# Limits reset every 10 seconds. A short gap between calls keeps one worker under the limit.
MIN_SECONDS_BETWEEN_CALLS = 0.25


KEY_NAMES = ("DATA_GOV_SG_API_KEY", "DATA_GOV_SG_API_KEY_DEV")


def load_api_keys() -> list[str]:
    """Production key first, then the development key. Each key has its own rate-limit quota."""
    values = {name: os.environ.get(name, "") for name in KEY_NAMES}
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() in values and not values[name.strip()]:
                values[name.strip()] = value.strip()
    keys = [values[name] for name in KEY_NAMES if values[name]]
    if not keys:
        sys.exit("DATA_GOV_SG_API_KEY is not set. Copy .env.example to .env and add the key.")
    return keys


class DgsClient:
    def __init__(self, max_retries: int = MAX_RETRIES) -> None:
        self.max_retries = max_retries
        self.keys = load_api_keys()
        self.key_index = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self._last_call = 0.0

    def _switch_key(self) -> bool:
        """Move to the next key. Return False when every key has been tried in this round."""
        self.key_index = (self.key_index + 1) % len(self.keys)
        return self.key_index != 0

    def get(self, path: str, params: dict) -> dict | None:
        """Return the JSON body, or None when the API has no data for the query."""
        url = f"{BASE_URL}/{path}"
        for attempt in range(self.max_retries):
            wait = self._last_call + MIN_SECONDS_BETWEEN_CALLS - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            headers = {"x-api-key": self.keys[self.key_index]}
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 429 and self._switch_key():
                continue  # the other key has its own quota: try it at once
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After", "")
                time.sleep(float(retry_after) if retry_after.isdigit() else min(MAX_BACKOFF_SECONDS, 2**attempt))
                continue
            body = response.json()
            if body.get("code") == CODE_NOT_FOUND:
                return None
            if response.status_code != 200 or body.get("code") != 0:
                raise RuntimeError(f"{path} {params}: HTTP {response.status_code}, {body.get('errorMsg')}")
            return body
        raise RuntimeError(f"{path} {params}: still rate limited after {self.max_retries} retries")

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


def day_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


_thread_local = threading.local()


def _thread_client() -> DgsClient:
    if not hasattr(_thread_local, "client"):
        _thread_local.client = DgsClient()
    return _thread_local.client


def fetch_days(path: str, params: dict, days: list[date], raw_dir: Path, workers: int = 2) -> dict[date, list[dict]]:
    """Fetch every page for each day, in parallel, caching finished days as raw_dir/YYYY-MM-DD.json.gz.

    Days with no data are left out of the result. Today is never cached because it is incomplete.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()

    def one(day: date) -> tuple[date, list[dict] | None]:
        cache = raw_dir / f"{day.isoformat()}.json.gz"
        if cache.exists():
            return day, json.loads(gzip.decompress(cache.read_bytes()))
        try:
            pages = _thread_client().get_all_pages(path, dict(params, date=day.isoformat()))
        except RuntimeError as error:
            print(f"  skipped {day}: {error}. Rerun the script to fill it.", flush=True)
            return day, None
        if pages is not None and day < today:
            cache.write_bytes(gzip.compress(json.dumps(pages).encode()))
        return day, pages

    results: dict[date, list[dict]] = {}
    done = 0
    newest_first = sorted(days, reverse=True)  # recent data matters most if a run stops early
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for day, pages in pool.map(one, newest_first):
            done += 1
            if pages is not None:
                results[day] = pages
            if done % 100 == 0 or done == len(days):
                print(f"  {path}: {done}/{len(days)} days ({len(results)} with data)", flush=True)
    return results
