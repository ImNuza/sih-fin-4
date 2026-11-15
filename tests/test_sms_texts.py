"""The welcome SMS: one SMS in every language, and the cover text shown at the point of sale.

The brief: the trigger, the payout and the exclusions must fit in one SMS in the customer's
language. English and Malay fit one 160-character SMS; Chinese and Tamil one 70-character
Unicode SMS. The payout texts are tested in tests/test_day_colour.py.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import sms
from api.main import app
from api.models import Tariff

ROOT = Path(__file__).resolve().parent.parent
TARIFF = Tariff.model_validate_json((ROOT / "api/default_tariff.json").read_text())
WAIT_DAYS = 30
# The cheapest and dearest weekly prices a tier can carry, and a preview with no place.
PRICES = (None, 3.44, 99.99)
APPROVED = {
    "en": "SafeDay Tier 2: S$9.11/wk, cover from day 30. Haze, heavy rain, heat or flood alert "
    "near your stall: up to S$40/day, S$1,400/yr. Else no pay even if sales drop.",
    "zh": "SafeDay第2级每周S$9.11，买后30天生效。摊位附近烟霾、大雨、酷热或水灾：日赔≤S$40，"
    "年≤S$1,400。否则生意差也不赔",
    "ms": "SafeDay Tahap 2: S$9.11/mgu, mula hari ke-30. Jerebu, hujan lebat, panas atau banjir "
    "dekat gerai: hingga S$40/hari, S$1,400/thn. Lain tiada bayaran walau rugi.",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def welcome(language: str, tier, weekly: float | None = 9.11) -> str:
    return sms.welcome_text(
        language, int(tier.key[-1]), weekly, tier.daily_payout_sgd,
        tier.max_paid_days_per_year, WAIT_DAYS,
    )


def test_plain_text_fits_160_characters_a_part():
    assert sms.segments("a" * 160) == 1
    assert sms.segments("a" * 161) == 2


def test_unicode_text_fits_70_characters_a_part():
    assert sms.segments("雨" * 70) == 1
    assert sms.segments("雨" * 71) == 2
    assert sms.segments("雨" * 134) == 2


@pytest.mark.parametrize("language", sms.LANGUAGES)
@pytest.mark.parametrize("weekly", PRICES)
def test_welcome_text_fits_one_sms_for_every_tier_and_price(language, weekly):
    for tier in TARIFF.tiers:
        body = welcome(language, tier, weekly)
        assert sms.segments(body) == 1, (tier.key, weekly, len(body), body)


@pytest.mark.parametrize("language", sorted(APPROVED))
def test_welcome_text_is_the_approved_wording(language):
    """Tier 2 at Maxwell in the proposal: S$9.11 a week, S$40 a day, 35 days a year."""
    assert sms.welcome_text(language, 2, 9.11, 40, 35, WAIT_DAYS) == APPROVED[language]


def test_tamil_welcome_names_the_wait_the_triggers_and_the_payout():
    body = sms.welcome_text("ta", 2, 9.11, 40, 35, WAIT_DAYS)
    for phrase in ("30நாள் பின்", "புகை/மழை/வெயில்/வெள்ளம்", "S$40/நாள்", "S$1,400", "இல்லையேல் 0"):
        assert phrase in body


def test_a_long_price_shortens_the_wording_rather_than_send_two_sms():
    body = sms.welcome_text("en", 4, 99.99, 100, 45, WAIT_DAYS)
    assert sms.segments(body) == 1
    assert "up to S$100/day" in body


def test_a_preview_without_a_place_leaves_the_price_out():
    body = sms.welcome_text("en", 1, None, 20, 10, WAIT_DAYS)
    assert body.startswith("SafeDay Tier 1: cover from day 30.")


def test_malay_texts_use_malay_month_names():
    assert sms.day_text("ms", date(2026, 12, 15)) == "15 Dis"
    assert sms.day_text("ms", date(2026, 8, 1)) == "1 Ogo"


def test_cover_text_is_public_and_matches_the_welcome_sms(client):
    params = {"tier": "tier_2", "language": "en", "weekly": 9.11}
    cover = client.get("/api/cover-text", params=params).json()
    tier = next(t for t in TARIFF.tiers if t.key == "tier_2")
    assert cover["body"] == welcome("en", tier, 9.11)
    assert cover["segments"] == 1
    assert cover["characters"] == len(cover["body"])


def test_cover_text_refuses_a_price_out_of_range(client):
    assert client.get("/api/cover-text", params={"weekly": -1}).status_code == 422


def test_cover_text_comes_in_every_language(client):
    for language in sms.LANGUAGES:
        cover = client.get("/api/cover-text", params={"tier": "tier_1", "language": language})
        assert cover.status_code == 200
        assert "S$20" in cover.json()["body"]


def test_cover_text_rejects_an_unknown_tier_or_language(client):
    assert client.get("/api/cover-text", params={"tier": "tier_9"}).status_code == 404
    assert client.get("/api/cover-text", params={"language": "fr"}).status_code == 422


@pytest.mark.parametrize("language", sms.LANGUAGES)
def test_welcome_text_never_says_only_a_red_day_pays(language):
    """Payouts are graded: a milder day pays a share, so the text promises "up to"."""
    body = welcome(language, TARIFF.tiers[0])
    assert "S$20" in body
    for wrong in ("No Red Day", "no Red day", "无红色日", "Tiada Hari", "Red Day = no pay"):
        assert wrong not in body
