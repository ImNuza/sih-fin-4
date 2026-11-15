"""PayNow QR for the buy flow's pay step: an EMVCo merchant-presented payload, drawn as SVG.

Payload layout: EMVCo QR Code Specification for Payment Systems, Merchant-Presented Mode, with
the PayNow merchant account template (id "SG.PAYNOW") that SGQR uses. Each field is
id + 2-digit length + value; the last field is a CRC-16/CCITT-FALSE checksum.

The proxy is not a UEN that any bank can resolve, so the code pays nobody. It is a prototype.
"""

from __future__ import annotations

import io

import segno

DEMO_PROXY = "PAYUNG-DEMO"
DEMO_MERCHANT_NAME = "PAYUNG PROTOTYPE"
PROXY_TYPE_UEN = "2"
AMOUNT_NOT_EDITABLE = "0"
DYNAMIC_QR = "12"
SINGAPORE_DOLLAR = "702"
NO_MERCHANT_CATEGORY = "0000"
CRC_FIELD_HEAD = "6304"
QR_SCALE = 5


def field(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: polynomial 0x1021, initial value 0xFFFF, no reflection."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def paynow_payload(amount_sgd: float, reference: str) -> str:
    merchant_account = (
        field("00", "SG.PAYNOW")
        + field("01", PROXY_TYPE_UEN)
        + field("02", DEMO_PROXY)
        + field("03", AMOUNT_NOT_EDITABLE)
    )
    body = (
        field("00", "01")
        + field("01", DYNAMIC_QR)
        + field("26", merchant_account)
        + field("52", NO_MERCHANT_CATEGORY)
        + field("53", SINGAPORE_DOLLAR)
        + field("54", f"{amount_sgd:.2f}")
        + field("58", "SG")
        + field("59", DEMO_MERCHANT_NAME)
        + field("60", "Singapore")
        + field("62", field("01", reference))
        + CRC_FIELD_HEAD
    )
    return body + f"{crc16_ccitt(body.encode('ascii')):04X}"


def paynow_svg(amount_sgd: float, reference: str) -> str:
    buffer = io.BytesIO()
    qr = segno.make(paynow_payload(amount_sgd, reference), error="m")
    qr.save(buffer, kind="svg", scale=QR_SCALE, xmldecl=False)
    return buffer.getvalue().decode()
