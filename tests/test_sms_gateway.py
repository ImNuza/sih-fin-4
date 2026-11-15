from __future__ import annotations

import pytest
import requests

from api import sms_gateway

read_textbee_key = sms_gateway.textbee_key


class FakeResponse:
    def __init__(self, status_code: int, reply: dict, reason: str = ""):
        self.status_code = status_code
        self.ok = status_code < 400
        self.reason = reason
        self.reply = reply
        self.content = b"{}"

    def json(self) -> dict:
        return self.reply

    def raise_for_status(self) -> None:
        if not self.ok:
            raise requests.HTTPError(str(self.status_code))


def answer_with(monkeypatch, response: FakeResponse) -> list[dict]:
    calls: list[dict] = []

    def post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return response

    monkeypatch.setattr(sms_gateway.requests, "post", post)
    return calls


def test_without_textbee_the_text_is_simulated_as_delivered():
    delivery = sms_gateway.deliver("+6591234567", "hello")
    assert delivery.status == "delivered"
    assert delivery.provider_message_id.startswith("SIM")


def test_textbee_gets_the_mobile_and_body(monkeypatch):
    accepted = {"data": {"success": True, "smsBatchId": "b1", "recipientCount": 1}}
    calls = answer_with(monkeypatch, FakeResponse(201, accepted))
    delivery = sms_gateway.send_by_textbee("key1", "+6591234567", "Payung paid S$40")
    assert delivery == sms_gateway.Delivery("queued", "TBb1", None)
    [call] = calls
    assert call["url"] == sms_gateway.TEXTBEE_SEND_URL
    assert call["json"] == {"recipients": ["+6591234567"], "message": "Payung paid S$40"}
    assert call["headers"] == {"x-api-key": "key1"}


def test_a_refused_text_is_kept_as_failed_with_textbees_reason(monkeypatch):
    answer_with(monkeypatch, FakeResponse(400, {"message": "No enabled device"}))
    delivery = sms_gateway.send_by_textbee("key1", "+6591234567", "hello")
    assert delivery == sms_gateway.Delivery("failed", None, "textbee 400: No enabled device")


def test_a_refusal_without_a_body_keeps_the_http_reason(monkeypatch):
    answer_with(monkeypatch, FakeResponse(401, {}, "Unauthorized"))
    delivery = sms_gateway.send_by_textbee("key1", "+6591234567", "hello")
    assert delivery.error == "textbee 401: Unauthorized"


def test_an_unreachable_textbee_is_kept_as_failed(monkeypatch):
    def post(url, **kwargs):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(sms_gateway.requests, "post", post)
    delivery = sms_gateway.send_by_textbee("key1", "+6591234567", "hello")
    assert delivery == sms_gateway.Delivery("failed", None, "Could not reach textbee")


@pytest.mark.parametrize(("setting", "key"), [("abc", "abc"), (None, None)])
def test_texts_reach_real_phones_only_with_a_textbee_key(monkeypatch, setting, key):
    monkeypatch.setattr(sms_gateway, "api_key", lambda name: setting)
    assert read_textbee_key() == key


def phone_reports(monkeypatch, messages: list[dict]) -> list[dict]:
    monkeypatch.setattr(sms_gateway, "textbee_key", lambda: "key1")
    calls: list[dict] = []

    def get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse(200, {"data": messages})

    monkeypatch.setattr(sms_gateway.requests, "get", get)
    return calls


def test_check_reads_the_phones_failure_and_its_reason(monkeypatch):
    calls = phone_reports(monkeypatch, [{"status": "failed", "errorMessage": "No service"}])
    delivery = sms_gateway.check("TBb1")
    assert delivery == sms_gateway.Delivery("failed", "TBb1", "No service")
    [call] = calls
    assert call["params"] == {"smsBatchId": "b1"}
    assert call["headers"] == {"x-api-key": "key1"}


@pytest.mark.parametrize(("phone", "status"), [
    ("pending", "queued"), ("dispatched", "queued"), ("sent", "sent"),
    ("delivered", "delivered"), ("unknown", "unknown"),
])
def test_check_maps_what_the_phone_reports(monkeypatch, phone, status):
    phone_reports(monkeypatch, [{"status": phone}])
    assert sms_gateway.check("TBb1") == sms_gateway.Delivery(status, "TBb1", None)


def test_check_has_no_news_before_textbee_lists_the_text(monkeypatch):
    phone_reports(monkeypatch, [])
    assert sms_gateway.check("TBb1") is None


def test_check_leaves_simulated_texts_alone(monkeypatch):
    calls = phone_reports(monkeypatch, [{"status": "failed"}])
    assert sms_gateway.check("SIM123") is None
    assert calls == []


def test_check_has_no_news_when_textbee_cannot_be_reached(monkeypatch):
    monkeypatch.setattr(sms_gateway, "textbee_key", lambda: "key1")

    def get(url, **kwargs):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(sms_gateway.requests, "get", get)
    assert sms_gateway.check("TBb1") is None
