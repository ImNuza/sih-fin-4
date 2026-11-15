"""The SMS texts: one-SMS length in every language, and the cover text shown at the point of sale.

The brief: the trigger, the payout and the exclusions must fit in one SMS in the customer's
language. English and Malay fit one 160-character SMS. Chinese and Tamil need Unicode SMS
(70 characters a part): Mandarin fits one, and the Tamil welcome is held to three until a
native speaker shortens it. The demo offers English and Mandarin.
"""

from __future__ import annotations

import json
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
CENTRES = [
    c["name"]
    for c in json.loads((ROOT / "data/processed/map_static.json").read_text())["hawker_centres"]
]
WELCOME_PARTS = {"en": 1, "ms": 1, "zh": 1, "ta": 3}
PAID_PARTS = {"en": 1, "ms": 1, "zh": 1, "ta": 2}
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


def paid(language: str, centre: str, amount_sgd: float = 100) -> str:
    return sms.payout_text(
        "payout_paid", language, "heat", 4.5, LAST_DAY_OF_YEAR,
        amount=sms.money(amount_sgd), proxy="+65 ****4567", centre=centre, ref="SD-000123",
    )


def test_plain_text_fits_160_characters_a_part():
    assert sms.segments("a" * 160) == 1
    assert sms.segments("a" * 161) == 2


def test_unicode_text_fits_70_characters_a_part():
    assert sms.segments("雨" * 70) == 1
    assert sms.segments("雨" * 71) == 2
    assert sms.segments("雨" * 134) == 2


@pytest.mark.parametrize("language", sms.TRANSLATED)
def test_welcome_text_fits_for_every_tier(language):
    for tier in TARIFF.tiers:
        body = welcome(language, tier)
        assert sms.segments(body) <= WELCOME_PARTS[language], (tier.key, len(body), body)


def test_welcome_text_names_every_trigger_and_the_no_pay_rule():
    body = welcome("en", TARIFF.tiers[-1])
    for phrase in ("WBGT 32C+ 2h+", "rain 20mm/h+", "PSI 101+", "flood alert", "7am-7pm",
                   "S$100/day", "Max 30 days/yr", "even if you lose income"):
        assert phrase in body


@pytest.mark.parametrize("language", sms.TRANSLATED)
def test_paid_text_fits_at_every_hawker_centre(language):
    for centre in CENTRES:
        body = paid(language, centre)
        assert sms.segments(body) <= PAID_PARTS[language], (centre, len(body), body)


def test_paid_text_names_the_centre_by_its_familiar_name_when_it_fits():
    body = paid("en", "New Market Road Blk 32 (People's Park Food Centre)", amount_sgd=20)
    assert "at People's Park Food Centre" in body
    assert "Blk 32" not in body


def test_paid_text_drops_the_centre_rather_than_run_to_two_texts():
    long_name = "Marine Parade Central Blk 84 (84 Marine Parade Central Market and Food Centre)"
    body = paid("en", long_name)
    assert sms.segments(body) == 1
    assert "NEA WBGT 32C+ for 4.5h on 31 Dec" in body


def test_whole_dollar_amounts_drop_the_cents():
    assert sms.money(20) == "20"
    assert sms.money(13.47) == "13.47"
    assert sms.money(13.5) == "13.50"


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


def test_demo_offers_english_and_mandarin_only(client):
    assert sms.LANGUAGES == ("en", "zh")
    for language in ("ms", "ta"):
        assert client.get("/api/cover-text", params={"language": language}).status_code == 422


@pytest.mark.parametrize("language", sms.LANGUAGES)
@pytest.mark.parametrize("kind", ["payout_paid", "payout_failed", "payout_held"])
def test_demo_payout_texts_fit_one_sms(language, kind):
    body = sms.payout_text(
        kind, language, "heat", 10.5, LAST_DAY_OF_YEAR, centre=max(CENTRES, key=len),
        amount="99.99", proxy="+65 ****4567", ref="SD-000123",
    )
    assert sms.segments(body) == 1, (len(body), body)


def test_mandarin_welcome_keeps_every_part_of_the_cover():
    body = welcome("zh", TARIFF.tiers[-1])
    for phrase in ("7-19时", "WBGT≥32°C达2小时", "雨≥20mm/时", "PSI≥101", "水灾", "日赔≤S$100",
                   "年限30天", "12月31日起", "否则亏损也不赔"):
        assert phrase in body
