"""The welcome SMS: one SMS in every language, and the cover text shown at the point of sale.

The brief: the trigger, the payout and "no alert, no pay" must fit in one SMS in the customer's
language, with a link to the site for the rest. English and Malay fit one 160-character SMS; Chinese and Tamil one 70-character
Unicode SMS. The payout texts are tested in tests/test_day_colour.py.
"""

from __future__ import annotations

import json
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
LINK = "https://payung.nuza.dev"
# The cheapest and dearest weekly prices a tier can carry, and a preview with no place.
PRICES = (None, 3.44, 99.99)
APPROVED = {
    "en": "Payung: S$9.11/wk, covered from day 30. Pays up to S$40 a day for abnormal weather "
    "near your stall. No alert, no pay. Details: https://payung.nuza.dev",
    "zh": "Payung：每周S$9.11，买后30天起，摊位附近天气异常日赔最高S$40。无警报不赔。"
    "\nhttps://payung.nuza.dev",
    "ms": "Payung: S$9.11/mgu, lindungan dari hari ke-30. Bayar hingga S$40 sehari untuk "
    "cuaca luar biasa. Tiada amaran, tiada bayaran. Info: https://payung.nuza.dev",
    "ta": "அசாதாரண வானிலை: ≤S$40/நாள். அலர்ட் இல்லையேல் 0 https://payung.nuza.dev",
}
NO_ALERT_NO_PAY = {"en": "No alert, no pay", "zh": "无警报不赔",
                   "ms": "Tiada amaran, tiada bayaran", "ta": "அலர்ட் இல்லையேல் 0"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def welcome(language: str, tier, weekly: float | None = 9.11) -> str:
    return sms.welcome_text(language, weekly, tier.daily_payout_sgd, WAIT_DAYS)


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


@pytest.mark.parametrize("language", sms.LANGUAGES)
def test_welcome_text_is_the_approved_wording(language):
    """Tier 2 at Maxwell in the proposal: S$9.11 a week, up to S$40 a day."""
    assert sms.welcome_text(language, 9.11, 40, WAIT_DAYS) == APPROVED[language]


def test_a_preview_without_a_place_leaves_the_price_out():
    body = sms.welcome_text("en", None, 20, WAIT_DAYS)
    assert body.startswith("Payung: covered from day 30.")


@pytest.mark.parametrize("language", sms.LANGUAGES)
@pytest.mark.parametrize("weekly", PRICES)
def test_welcome_text_says_no_alert_no_pay_and_links_the_details(language, weekly):
    for tier in TARIFF.tiers:
        body = welcome(language, tier, weekly)
        assert NO_ALERT_NO_PAY[language] in body
        assert body.endswith(LINK)
        assert body[-len(LINK) - 1].isspace(), "a phone only makes the link tappable after a space"


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


@pytest.mark.parametrize("language", sms.LANGUAGES)
def test_welcome_text_does_not_mention_flood(language):
    """The team left the flood alert out of the welcome SMS; a flood alert still pays."""
    for tier in TARIFF.tiers:
        body = welcome(language, tier, None).lower()
        for flood in ("flood", "水灾", "banjir", "வெள்ளம்"):
            assert flood not in body


CENTRES = [
    c["name"] for c in json.loads((ROOT / "data/processed/map_static.json").read_text())["hawker_centres"]
]


@pytest.mark.parametrize("hazard", ["haze", "rain", "heat", "flood", "closure"])
def test_chinese_payment_text_fits_one_sms_at_every_hawker_centre(hazard):
    for centre in CENTRES:
        body = sms.payout_text(
            "payout_paid", "zh", hazard, day_colour="红色日", loss="100", amount="100.00",
            proxy="+65 ****2428", centre=centre, day=sms.day_text("zh", date(2026, 12, 31)),
            ref="PY-999999",
        )
        assert sms.segments(body) == 1, (centre, len(body), body)
        assert body.startswith("Payung：") and "无需索赔" in body
        assert body.endswith("\n" + LINK)


@pytest.mark.parametrize("hazard", ["haze", "rain", "heat", "flood", "closure"])
def test_english_payment_text_fits_one_sms_with_the_link_at_every_hawker_centre(hazard):
    for centre in CENTRES:
        body = sms.payout_text(
            "payout_paid", "en", hazard, day_colour="Yellow day", loss="100", amount="100.00",
            proxy="+65 ****2428", centre=centre, day="31 Dec", ref="PY-999999",
        )
        assert sms.segments(body) == 1, (centre, len(body), body)
        assert "Ref PY-999999. No claim needed." in body
        assert body.endswith(" " + LINK)


def test_chinese_payment_text_keeps_the_loss_share_when_it_fits():
    body = sms.payout_text(
        "payout_paid", "zh", "haze", day_colour="红色日", loss="48", amount="19.20",
        proxy="+65 ****2428", centre="Maxwell Food Centre", day="10月18日", ref="PY-001042",
    )
    assert body == "Payung：10月18日烟霾红色日，损失48%，S$19.20已转PayNow，无需索赔\nhttps://payung.nuza.dev"


def test_english_payment_text_names_a_short_hawker_centre():
    body = sms.payout_text(
        "payout_paid", "en", "haze", day_colour="Red day", loss="48", amount="19.20",
        proxy="+65 ****2428", centre="Tekka Centre", day="18 Oct", ref="PY-001042",
    )
    assert body == ("Payung: Red day, 48% loss. S$19.20 sent to PayNow +65 ****2428 for haze at "
                    "Tekka Centre on 18 Oct. Ref PY-001042. No claim needed. "
                    "https://payung.nuza.dev")
