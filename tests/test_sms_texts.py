"""The welcome SMS: one-SMS length in every language, and the cover text shown at the point of sale.

The brief: the trigger, the payout and the exclusions must fit in one SMS in the customer's
language. English and Malay fit one 160-character SMS. Chinese and Tamil need Unicode SMS
(70 characters a part): Mandarin fits one, and the Tamil welcome is held to three until a
native speaker shortens it. The payout texts are tested in tests/test_day_colour.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from api import sms
from api.main import app
from api.models import Tariff

ROOT = Path(__file__).resolve().parent.parent
TARIFF = Tariff.model_validate_json((ROOT / "api/default_tariff.json").read_text())
WELCOME_PARTS = {"en": 1, "ms": 1, "zh": 1, "ta": 3}
LAST_DAY_OF_YEAR = date(2026, 12, 31)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def welcome(language: str, tier) -> str:
    return sms.welcome_text(
        language, payout_sgd=tier.daily_payout_sgd, heat_hours=2, rain_mm=20, psi=101,
        max_days=tier.max_paid_days_per_year, first_day=LAST_DAY_OF_YEAR,
    )


def test_plain_text_fits_160_characters_a_part():
    assert sms.segments("a" * 160) == 1
    assert sms.segments("a" * 161) == 2


def test_unicode_text_fits_70_characters_a_part():
    assert sms.segments("雨" * 70) == 1
    assert sms.segments("雨" * 71) == 2
    assert sms.segments("雨" * 134) == 2


@pytest.mark.parametrize("language", sms.LANGUAGES)
def test_welcome_text_fits_for_every_tier(language):
    for tier in TARIFF.tiers:
        body = welcome(language, tier)
        assert sms.segments(body) <= WELCOME_PARTS[language], (tier.key, len(body), body)


def test_welcome_text_names_every_trigger_and_the_no_pay_rule():
    body = welcome("en", TARIFF.tiers[-1])
    for phrase in ("WBGT 32C+ 2h+", "rain 20mm/h+", "PSI 101+", "flood alert", "7am-7pm",
                   "S$100/day", "Max 30 days/yr", "even if you lose income"):
        assert phrase in body


def test_malay_texts_use_malay_month_names():
    assert sms.day_text("ms", date(2026, 12, 15)) == "15 Dis"
    assert sms.day_text("ms", date(2026, 8, 1)) == "1 Ogo"


def sgt_today() -> date:
    return datetime.now(ZoneInfo("Asia/Singapore")).date()


def test_cover_text_is_public_and_matches_the_welcome_sms(client):
    response = client.get("/api/cover-text", params={"tier": "tier_4", "language": "en"})
    assert response.status_code == 200
    cover = response.json()
    first_day = sgt_today() + timedelta(days=30)
    assert cover["first_day"] == first_day.isoformat()
    assert cover["body"] == sms.welcome_text(
        "en", payout_sgd=100, heat_hours=2, rain_mm=20, psi=101, max_days=30,
        first_day=first_day,
    )
    assert cover["segments"] == 1
    assert cover["characters"] == len(cover["body"])


def test_cover_text_comes_in_every_language(client):
    for language in sms.LANGUAGES:
        cover = client.get("/api/cover-text", params={"tier": "tier_1", "language": language})
        assert cover.status_code == 200
        assert "S$20" in cover.json()["body"]


def test_cover_text_rejects_an_unknown_tier_or_language(client):
    assert client.get("/api/cover-text", params={"tier": "tier_9"}).status_code == 404
    assert client.get("/api/cover-text", params={"language": "fr"}).status_code == 422


def test_mandarin_welcome_keeps_every_part_of_the_cover():
    body = welcome("zh", TARIFF.tiers[-1])
    for phrase in ("7-19时", "WBGT≥32°C达2小时", "雨≥20mm/时", "PSI≥101", "水灾", "日赔≤S$100",
                   "年限30天", "12月31日起", "否则亏损也不赔"):
        assert phrase in body
