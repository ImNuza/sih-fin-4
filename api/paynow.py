"""Simulated PayNow: proxy checks, name lookup and transfer, shaped like a bank's payout API.

No bank offers PayNow payouts without a corporate account, and the hosted API container has
no internet, so this stands in for one. A transfer to a proxy ending in 0000 is rejected by the
"receiving bank", so the failure path can be shown. Replace transfer() to go live.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

MOBILE_PATTERN = re.compile(r"\+65[89]\d{7}")
UEN_PATTERN = re.compile(r"\d{8}[A-Z]|\d{9}[A-Z]|[TSR]\d{2}[A-Z]{2}\d{4}[A-Z]")
FAILING_SUFFIX = "0000"


@dataclass(frozen=True)
class Transfer:
    settled: bool
    provider_reference: str | None
    failure_reason: str | None


def is_valid_mobile(mobile: str) -> bool:
    return MOBILE_PATTERN.fullmatch(mobile) is not None


def is_valid_proxy(proxy_type: str, proxy: str) -> bool:
    if proxy_type == "mobile":
        return is_valid_mobile(proxy)
    return UEN_PATTERN.fullmatch(proxy) is not None


def mask(proxy_type: str, proxy: str) -> str:
    if proxy_type == "mobile":
        return f"+65 ****{proxy[-4:]}"
    return f"{proxy[:2]}*****{proxy[-2:]}"


def lookup_name(holder_name: str) -> str:
    """The registered name PayNow shows before a transfer. The simulator echoes the user's name."""
    return holder_name.upper()


def transfer(proxy: str) -> Transfer:
    if proxy.endswith(FAILING_SUFFIX):
        return Transfer(False, None, "Receiving bank rejected the transfer: account closed")
    return Transfer(True, f"PN{secrets.token_hex(6).upper()}", None)
