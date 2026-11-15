"""Sends one text to a real phone through textbee, or simulates delivery when textbee is not set up.

textbee (textbee.dev) sends each text from an Android phone running its app, on that phone's own
SIM, so the customer sees an ordinary Singapore number. It is used when TEXTBEE_API_KEY is set in
the environment or .env. textbee accepting a text is not delivery: the phone sends it a moment
later and reports back, which check() reads. The free plan sends up to 50 texts a day.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass

import requests

from api.kyc import api_key

TEXTBEE_SEND_URL = "https://api.textbee.dev/api/v1/gateway/send-sms"
TEXTBEE_MESSAGES_URL = "https://api.textbee.dev/api/v1/gateway/messages"
TEXTBEE_TIMEOUT_SECONDS = 10
TEXTBEE_ID_PREFIX = "TB"
# What the phone reports, as this app's text statuses. 'pending' and 'dispatched' are still on
# their way to the phone; 'unknown' means it did not report in time, which textbee says is not
# a failure.
PHONE_STATUSES = {
    "pending": "queued", "dispatched": "queued", "sent": "sent", "delivered": "delivered",
    "failed": "failed", "unknown": "unknown",
}

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Delivery:
    """status: 'queued' (textbee took it), 'sent' (the phone sent it), 'delivered' (the network
    confirmed it, or simulated), 'failed' or 'unknown' (the phone did not report in time)."""

    status: str
    provider_message_id: str | None
    error: str | None


def textbee_key() -> str | None:
    return api_key("TEXTBEE_API_KEY")


def is_live() -> bool:
    return textbee_key() is not None


def deliver(to_mobile: str, body: str) -> Delivery:
    key = textbee_key()
    if key is None:
        return Delivery("delivered", f"SIM{secrets.token_hex(8).upper()}", None)
    return send_by_textbee(key, to_mobile, body)


def send_by_textbee(key: str, to_mobile: str, body: str) -> Delivery:
    """A failed text is kept as failed rather than raised: the payout has already gone out."""
    try:
        response = requests.post(
            TEXTBEE_SEND_URL,
            json={"recipients": [to_mobile], "message": body},
            headers={"x-api-key": key},
            timeout=TEXTBEE_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        log.warning("textbee could not be reached: %s", type(error).__name__)
        return Delivery("failed", None, "Could not reach textbee")
    reply = response.json() if response.content else {}
    if not response.ok:
        error = f"textbee {response.status_code}: {reply.get('message', response.reason)}"
        log.warning("textbee refused a text: %s", error)
        return Delivery("failed", None, error)
    batch_id = reply.get("data", {}).get("smsBatchId")
    return Delivery("queued", f"{TEXTBEE_ID_PREFIX}{batch_id}" if batch_id else None, None)


def check(provider_message_id: str) -> Delivery | None:
    """What the phone did with a text textbee accepted, or None when there is no news yet."""
    key = textbee_key()
    if key is None or not provider_message_id.startswith(TEXTBEE_ID_PREFIX):
        return None
    try:
        response = requests.get(
            TEXTBEE_MESSAGES_URL,
            params={"smsBatchId": provider_message_id.removeprefix(TEXTBEE_ID_PREFIX)},
            headers={"x-api-key": key},
            timeout=TEXTBEE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        log.warning("textbee status check failed: %s", type(error).__name__)
        return None
    messages = response.json().get("data") or []
    if not messages:
        return None
    status = PHONE_STATUSES.get(messages[0].get("status"), "unknown")
    error = messages[0].get("errorMessage") if status == "failed" else None
    return Delivery(status, provider_message_id, error)
