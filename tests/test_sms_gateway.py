from __future__ import annotations

import pytest
import requests

from api import sms_gateway

LOGIN = sms_gateway.Twilio("AC123", "token", "+15005550006")
SETTINGS = {"TWILIO_ACCOUNT_SID": "AC123", "TWILIO_AUTH_TOKEN": "token", "TWILIO_FROM": "+1500"}
read_twilio_settings = sms_gateway.twilio


class FakeResponse:
    def __init__(self, status_code: int, reply: dict):
        self.status_code = status_code
        self.reply = reply
        self.content = b"{}"

    def json(self) -> dict:
        return self.reply


def answer_with(monkeypatch, response: FakeResponse) -> list[dict]:
    calls: list[dict] = []

    def post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return response

    monkeypatch.setattr(sms_gateway.requests, "post", post)
    return calls


def test_without_twilio_the_text_is_simulated_as_delivered():
    delivery = sms_gateway.deliver("+6591234567", "hello")
    assert delivery.status == "delivered"
    assert delivery.provider_message_id.startswith("SIM")


def test_twilio_gets_the_mobile_sender_and_body(monkeypatch):
    calls = answer_with(monkeypatch, FakeResponse(201, {"sid": "SM1", "status": "queued"}))
    delivery = sms_gateway.send_by_twilio(LOGIN, "+6591234567", "SafeDay paid S$40")
    assert delivery == sms_gateway.Delivery("sent", "SM1", None)
    [call] = calls
    assert call["url"].endswith("/Accounts/AC123/Messages.json")
    assert call["data"] == {
        "To": "+6591234567", "From": "+15005550006", "Body": "SafeDay paid S$40",
    }
    assert call["auth"] == ("AC123", "token")


def test_a_refused_text_is_kept_as_failed_with_twilios_reason(monkeypatch):
    answer_with(monkeypatch, FakeResponse(400, {"code": 21608, "message": "Unverified number."}))
    delivery = sms_gateway.send_by_twilio(LOGIN, "+6591234567", "hello")
    assert delivery == sms_gateway.Delivery("failed", None, "Twilio 21608: Unverified number.")


def test_an_unreachable_twilio_is_kept_as_failed(monkeypatch):
    def post(url, **kwargs):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(sms_gateway.requests, "post", post)
    delivery = sms_gateway.send_by_twilio(LOGIN, "+6591234567", "hello")
    assert delivery == sms_gateway.Delivery("failed", None, "Could not reach Twilio")


def test_twilio_is_used_when_all_three_settings_are_set(monkeypatch):
    monkeypatch.setattr(sms_gateway, "api_key", SETTINGS.get)
    assert read_twilio_settings() == sms_gateway.Twilio("AC123", "token", "+1500")


@pytest.mark.parametrize("missing", sorted(SETTINGS))
def test_texts_stay_simulated_unless_all_three_settings_are_set(monkeypatch, missing):
    monkeypatch.setattr(
        sms_gateway, "api_key", lambda name: None if name == missing else SETTINGS[name]
    )
    assert read_twilio_settings() is None
