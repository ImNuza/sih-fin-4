"""The early-warning text: sent the evening before NEA forecasts heavy rain, haze or heat.

Forecasts come from NEA's 24-hour forecast (data.gov.sg twenty-four-hr-forecast), which labels
each of the 5 PSI regions for three periods: tonight, tomorrow morning and tomorrow afternoon.
English, Malay and Mandarin fit one SMS. Tamil takes three parts, as the welcome text does,
until a native speaker shortens it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from api import forecast_warning, live, sms
from api.accounts import application_profile, policies
from api.main import app
from tests.test_api import buy_body
from tests.test_payout_api import (
    LONG_AGO,
    register,
    sign_in,
    stallholder_with_cover,
    start_cover_on,
)

REGIONS = ("north", "south", "east", "west", "central")
TOMORROW = date(2026, 11, 16)
NOT_A_PAYOUT = "A forecast is not a payout; payment depends on the real reading."
WARNING_PARTS = {"en": 1, "ms": 1, "zh": 1, "ta": 3}
ALL_HAZARDS = ["rain", "haze", "heat"]


def period(start: str, end: str, labels: dict[str, str]) -> dict:
    return {
        "regions": {
            region: {"code": "", "text": labels.get(region, "Cloudy")} for region in REGIONS
        },
        "timePeriod": {"start": start, "end": end, "text": ""},
    }


def forecast(tonight: dict[str, str] | None = None, morning: dict[str, str] | None = None,
             afternoon: dict[str, str] | None = None, high_c: float = 33) -> dict:
    """One record shaped like NEA's 5:30 pm issue for 6 pm 15 Nov to 6 pm 16 Nov 2026."""
    return {
        "date": "2026-11-15",
        "timestamp": "2026-11-15T17:31:00+08:00",
        "general": {
            "validPeriod": {
                "start": "2026-11-15T18:00:00+08:00", "end": "2026-11-16T18:00:00+08:00",
            },
            "temperature": {"high": high_c, "low": 24, "unit": "Degrees Celsius"},
            "forecast": {"code": "TL", "text": "Thundery Showers"},
        },
        "periods": [
            period("2026-11-15T18:00:00+08:00", "2026-11-16T06:00:00+08:00", tonight or {}),
            period("2026-11-16T06:00:00+08:00", "2026-11-16T12:00:00+08:00", morning or {}),
            period("2026-11-16T12:00:00+08:00", "2026-11-16T18:00:00+08:00", afternoon or {}),
        ],
    }


def test_the_forecast_day_is_the_day_its_daytime_periods_fall_on():
    assert forecast_warning.forecast_day(forecast()) == TOMORROW


def test_the_late_night_issue_warns_for_the_day_it_covers():
    """NEA's 11 pm issue says 0 am to 0 am but ends its validPeriod a day later (12 Jun 2025)."""
    record = forecast(afternoon={"east": "Heavy Showers"})
    record["general"]["validPeriod"] = {
        "start": "2026-11-16T00:00:00+08:00", "end": "2026-11-18T00:00:00+08:00",
    }
    record["periods"][0] = period(
        "2026-11-16T00:00:00+08:00", "2026-11-16T06:00:00+08:00", {}
    )
    record["periods"].append(
        period("2026-11-16T18:00:00+08:00", "2026-11-17T00:00:00+08:00", {})
    )
    assert forecast_warning.forecast_day(record) == TOMORROW
    assert forecast_warning.warned_regions(record) == {"east": ["rain"]}


def test_heavy_rain_tomorrow_afternoon_warns_that_region_only():
    record = forecast(afternoon={"south": "Heavy Thundery Showers"})
    assert forecast_warning.warned_regions(record) == {"south": ["rain"]}


def test_heavy_rain_tonight_does_not_warn_for_tomorrow():
    record = forecast(tonight={"south": "Heavy Thundery Showers"})
    assert forecast_warning.warned_regions(record) == {}


def test_thundery_showers_that_are_not_heavy_do_not_warn():
    record = forecast(morning=dict.fromkeys(REGIONS, "Thundery Showers"))
    assert forecast_warning.warned_regions(record) == {}


def test_hazy_warns_of_haze_but_slightly_hazy_does_not():
    record = forecast(morning={"west": "Hazy", "east": "Slightly Hazy"})
    assert forecast_warning.warned_regions(record) == {"west": ["haze"]}


def test_a_forecast_high_at_the_heat_level_warns_every_region_of_heat():
    record = forecast(high_c=forecast_warning.HEAT_FORECAST_HIGH_C)
    assert forecast_warning.warned_regions(record) == {region: ["heat"] for region in REGIONS}


def test_a_region_lists_each_hazard_once_in_a_fixed_order():
    record = forecast(
        morning={"north": "Hazy"}, afternoon={"north": "Heavy Showers"},
        high_c=forecast_warning.HEAT_FORECAST_HIGH_C,
    )
    assert forecast_warning.warned_regions(record)["north"] == ALL_HAZARDS


def test_the_warning_says_a_forecast_is_not_a_payout():
    assert NOT_A_PAYOUT in sms.warning_text("en", ["rain"], TOMORROW)


def test_the_warning_names_what_is_forecast_the_day_and_one_safety_tip():
    body = sms.warning_text("en", ["rain"], TOMORROW)
    assert "heavy rain" in body
    assert "16 Nov" in body
    assert sms.WARNING_TIPS["en"]["rain"] in body
    assert sms.WARNING_TIPS["en"]["haze"] not in body


@pytest.mark.parametrize("language", sms.LANGUAGES)
@pytest.mark.parametrize("hazards", [["rain"], ["haze"], ["heat"], ALL_HAZARDS])
def test_the_warning_fits_one_sms(language, hazards):
    body = sms.warning_text(language, hazards, TOMORROW)
    assert sms.segments(body) <= WARNING_PARTS[language], (len(body), body)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


def nea_forecasts(monkeypatch, record: dict) -> None:
    monkeypatch.setattr(live, "fetch_day_forecast", lambda: record)


def stallholder_region(client) -> str:
    with client.app.state.db.connect() as db:
        return db.execute(select(policies.c.region)).scalar_one()


def warnings_on_the_phone(client) -> list[dict]:
    sign_in(client, "tan@example.com")
    return [text for text in client.get("/api/sms").json() if text["kind"] == "forecast_warning"]


def run_warnings(client) -> dict:
    register(client, "insurer", "desk@example.com")
    response = client.post("/api/insurer/forecast-warnings")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_customer_in_the_warned_region_gets_the_warning(client, monkeypatch):
    stallholder_with_cover(client)
    nea_forecasts(monkeypatch, forecast(afternoon={stallholder_region(client): "Heavy Showers"}))
    run = run_warnings(client)
    assert run["counts"]["sent"] == 1
    [text] = warnings_on_the_phone(client)
    assert text["body"] == sms.warning_text("en", ["rain"], TOMORROW)


def test_a_customer_outside_the_warned_region_gets_nothing(client, monkeypatch):
    stallholder_with_cover(client)
    other = next(region for region in REGIONS if region != stallholder_region(client))
    nea_forecasts(monkeypatch, forecast(afternoon={other: "Heavy Showers"}))
    assert run_warnings(client)["counts"]["sent"] == 0
    assert warnings_on_the_phone(client) == []


def test_a_customer_gets_one_warning_a_day_however_often_it_runs(client, monkeypatch):
    stallholder_with_cover(client)
    nea_forecasts(monkeypatch, forecast(high_c=forecast_warning.HEAT_FORECAST_HIGH_C))
    run_warnings(client)
    again = client.post("/api/insurer/forecast-warnings").json()
    assert again["counts"]["already_warned"] == 1
    assert len(warnings_on_the_phone(client)) == 1


def test_a_customer_in_the_waiting_period_is_warned_too(client, monkeypatch):
    stallholder_with_cover(client, started_at=datetime.now(UTC))
    nea_forecasts(monkeypatch, forecast(high_c=forecast_warning.HEAT_FORECAST_HIGH_C))
    assert run_warnings(client)["counts"]["sent"] == 1


def test_a_customer_whose_cover_ended_before_the_forecast_day_gets_nothing(client, monkeypatch):
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    start_cover_on(client, LONG_AGO)
    with client.app.state.db.begin() as db:
        db.execute(update(application_profile).values(cover_ends=TOMORROW))
    nea_forecasts(monkeypatch, forecast(high_c=forecast_warning.HEAT_FORECAST_HIGH_C))
    run = run_warnings(client)
    assert run["counts"]["sent"] == 0
    assert run["counts"]["cover_ended"] == 1


def test_a_quiet_forecast_sends_nothing(client, monkeypatch):
    stallholder_with_cover(client)
    nea_forecasts(monkeypatch, forecast())
    run = run_warnings(client)
    assert run["regions"] == {}
    assert run["day"] == TOMORROW.isoformat()
    assert warnings_on_the_phone(client) == []


def test_stallholders_cannot_send_warnings(client, monkeypatch):
    stallholder_with_cover(client)
    nea_forecasts(monkeypatch, forecast(high_c=forecast_warning.HEAT_FORECAST_HIGH_C))
    assert client.post("/api/insurer/forecast-warnings").status_code == 403


def test_the_run_needs_the_data_gov_sg_key(client, monkeypatch):
    def no_key() -> dict:
        raise SystemExit("DATA_GOV_SG_API_KEY is not set.")

    monkeypatch.setattr(live, "fetch_day_forecast", no_key)
    register(client, "insurer", "desk@example.com")
    response = client.post("/api/insurer/forecast-warnings")
    assert response.status_code == 503
    assert "DATA_GOV_SG_API_KEY" in response.json()["detail"]


def demo_warning(client, user_id: int, hazards: list[str], **extra) -> dict:
    body = {"user_id": user_id, "hazards": hazards, **extra}
    response = client.post("/api/insurer/demo-forecast-warnings", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def policyholder_id(client) -> int:
    register(client, "insurer", "desk@example.com")
    [holder] = client.get("/api/insurer/policyholders").json()["policyholders"]
    return holder["user_id"]


def test_the_demo_warning_texts_the_chosen_customer_now(client):
    stallholder_with_cover(client)
    sent = demo_warning(client, policyholder_id(client), ["haze"])
    assert sent["text"]["kind"] == "forecast_warning"
    assert sent["text"]["to"] == "+65 ****4567"
    [text] = warnings_on_the_phone(client)
    assert sms.WARNING_TIPS["en"]["haze"] in text["body"]
    assert NOT_A_PAYOUT in text["body"]


def test_the_demo_warning_can_be_shown_again_the_same_day(client):
    stallholder_with_cover(client)
    user_id = policyholder_id(client)
    demo_warning(client, user_id, ["rain"])
    demo_warning(client, user_id, ["heat"], sms_language="ms")
    assert len(warnings_on_the_phone(client)) == 2


def test_the_demo_warning_refuses_a_hazard_with_no_forecast(client):
    stallholder_with_cover(client)
    user_id = policyholder_id(client)
    response = client.post(
        "/api/insurer/demo-forecast-warnings", json={"user_id": user_id, "hazards": ["flood"]}
    )
    assert response.status_code == 422


def test_the_demo_warning_needs_a_mobile(client):
    register(client, "sme", "tan@example.com")
    assert client.post("/api/policies", json={"tier": "tier_1"}).status_code == 200
    user_id = policyholder_id(client)
    response = client.post(
        "/api/insurer/demo-forecast-warnings", json={"user_id": user_id, "hazards": ["rain"]}
    )
    assert response.status_code == 422
    assert "mobile" in response.json()["detail"]


def test_the_insurer_desk_has_the_demo_warning_card(client):
    script = client.get("/payouts.js")
    assert script.status_code == 200
    assert "Demo: send a forecast warning now" in script.text
