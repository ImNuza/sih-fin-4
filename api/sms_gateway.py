"""Sends one text to a real phone through Twilio, or simulates delivery when Twilio is not set up.

Twilio is used when TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM (a Twilio number in
E.164 form, or a sender ID) are all set in the environment or .env. A Twilio trial account only
texts numbers verified in its console, and puts "Sent from your Twilio trial account" in front.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass

import requests

from api.kyc import api_key

TWILIO_MESSAGES_URL = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
TWILIO_TIMEOUT_SECONDS = 10

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Twilio:
    account_sid: str
    auth_token: str
    sender: str


@dataclass(frozen=True)
class Delivery:
    """status: 'delivered' (simulated), 'sent' (Twilio took it) or 'failed'."""

    status: str
    provider_message_id: str | None
    error: str | None


def twilio() -> Twilio | None:
    account_sid = api_key("TWILIO_ACCOUNT_SID")
    auth_token = api_key("TWILIO_AUTH_TOKEN")
    sender = api_key("TWILIO_FROM")
    if account_sid and auth_token and sender:
        return Twilio(account_sid, auth_token, sender)
    return None


def is_live() -> bool:
    return twilio() is not None


def deliver(to_mobile: str, body: str) -> Delivery:
    login = twilio()
    if login is None:
        return Delivery("delivered", f"SIM{secrets.token_hex(8).upper()}", None)
    return send_by_twilio(login, to_mobile, body)


def send_by_twilio(login: Twilio, to_mobile: str, body: str) -> Delivery:
    """A failed text is kept as failed rather than raised: the payout has already gone out."""
    try:
        response = requests.post(
            TWILIO_MESSAGES_URL.format(account_sid=login.account_sid),
            data={"To": to_mobile, "From": login.sender, "Body": body},
            auth=(login.account_sid, login.auth_token),
            timeout=TWILIO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        log.warning("Twilio could not be reached: %s", type(error).__name__)
        return Delivery("failed", None, "Could not reach Twilio")
    reply = response.json() if response.content else {}
    if response.status_code != requests.codes.created:
        error = f"Twilio {reply.get('code', response.status_code)}: {reply.get('message', '')}"
        log.warning("Twilio refused a text: %s", error)
        return Delivery("failed", None, error.strip())
    return Delivery("sent", reply["sid"], None)
