"""Simulated SMS gateway, the texts SafeDay sends, and one-time codes for verifying a mobile.

Every text is a row in sms_messages; the dashboard shows them as the stallholder's phone.
The brief asks for one SMS in the customer's language, so each text has an English, Chinese,
Malay and Tamil version. The translations need a native speaker's check before launch.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, delete, insert, select, update

from api.accounts import hash_password, verify_password
from api.payouts import sms_codes, sms_messages

CODE_DIGITS = 6
CODE_LIFETIME = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
LANGUAGES = ("en", "zh", "ms", "ta")
# The day colour bands set by the team on 15 Nov 2026, the same as api/site/day-colour.js.
DAY_COLOUR_FROM_PERCENT = (("red", 70), ("yellow", 30), ("green", 0))

DAY_NAMES = {
    "en": {"green": "Green day", "yellow": "Yellow day", "red": "Red day"},
    "zh": {"green": "绿色日", "yellow": "黄色日", "red": "红色日"},
    "ms": {"green": "Hari hijau", "yellow": "Hari kuning", "red": "Hari merah"},
    "ta": {"green": "பச்சை நாள்", "yellow": "மஞ்சள் நாள்", "red": "சிவப்பு நாள்"},
}

HAZARD_NAMES = {
    "en": {"rain": "heavy rain", "haze": "haze", "heat": "extreme heat", "flood": "flooding",
           "closure": "a closure order"},
    "zh": {"rain": "大雨", "haze": "烟霾", "heat": "酷热", "flood": "水灾", "closure": "关闭令"},
    "ms": {"rain": "hujan lebat", "haze": "jerebu", "heat": "panas melampau", "flood": "banjir",
           "closure": "perintah tutup"},
    "ta": {"rain": "கனமழை", "haze": "புகைமூட்டம்", "heat": "கடும் வெப்பம்", "flood": "வெள்ளம்",
           "closure": "மூடல் உத்தரவு"},
}

TEMPLATES = {
    "payout_paid": {
        "en": "SafeDay: {day_colour}, {loss}% loss. S${amount} sent to PayNow {proxy} for "
        "{hazard} at {centre} on {day}. Ref {ref}. No claim needed.",
        "zh": "SafeDay：{day_colour}，损失{loss}%。因{day}{centre}{hazard}，S${amount}已转入您的"
        "PayNow {proxy}。编号{ref}。无需索赔。",
        "ms": "SafeDay: {day_colour}, kerugian {loss}%. S${amount} dihantar ke PayNow {proxy} "
        "kerana {hazard} di {centre} pada {day}. Ruj {ref}. Tiada tuntutan diperlukan.",
        "ta": "SafeDay: {day_colour}, இழப்பு {loss}%. {day} {centre} {hazard} காரணமாக "
        "S${amount} உங்கள் PayNow {proxy} க்கு அனுப்பப்பட்டது. குறிப்பு {ref}.",
    },
    "payout_failed": {
        "en": "SafeDay: we could not send S${amount} for {day} to PayNow {proxy}. Update your "
        "PayNow number in the app and we will retry. Ref {ref}.",
        "zh": "SafeDay：{day}的S${amount}未能转入PayNow {proxy}。"
        "请在应用中更新PayNow号码，我们会重试。编号{ref}。",
        "ms": "SafeDay: S${amount} untuk {day} gagal dihantar ke PayNow {proxy}. Kemas kini "
        "nombor PayNow dalam aplikasi. Ruj {ref}.",
        "ta": "SafeDay: {day} க்கான S${amount} PayNow {proxy} க்கு அனுப்ப முடியவில்லை. "
        "செயலியில் எண்ணைப் புதுப்பிக்கவும். குறிப்பு {ref}.",
    },
    "payout_held": {
        "en": "SafeDay: S${amount} for {day} is waiting for you. Verify your mobile in the app to "
        "receive it. Ref {ref}.",
        "zh": "SafeDay：{day}的S${amount}正在等您领取。请在应用中验证手机号码。编号{ref}。",
        "ms": "SafeDay: S${amount} untuk {day} sedang menunggu. Sahkan nombor telefon dalam "
        "aplikasi. Ruj {ref}.",
        "ta": "SafeDay: {day} க்கான S${amount} காத்திருக்கிறது. செயலியில் கைபேசி எண்ணை "
        "உறுதிப்படுத்தவும். குறிப்பு {ref}.",
    },
    "otp": {
        "en": "SafeDay code: {code}. It expires in 10 minutes. Do not share it.",
        "zh": "SafeDay验证码：{code}。10分钟内有效。请勿分享。",
        "ms": "Kod SafeDay: {code}. Tamat dalam 10 minit. Jangan kongsi.",
        "ta": "SafeDay குறியீடு: {code}. 10 நிமிடங்களில் காலாவதியாகும். பகிர வேண்டாம்.",
    },
}


def day_colour(loss_percent: float) -> str:
    """'none' for a day with no loss, else 'green', 'yellow' or 'red'. A green day still pays."""
    if loss_percent <= 0:
        return "none"
    return next(colour for colour, start in DAY_COLOUR_FROM_PERCENT if loss_percent >= start)


def day_name(language: str, loss_percent: float) -> str:
    return DAY_NAMES[language][day_colour(loss_percent)]


def payout_text(kind: str, language: str, hazard: str, **fields: str) -> str:
    hazard_name = HAZARD_NAMES[language].get(hazard, hazard)
    return TEMPLATES[kind][language].format(hazard=hazard_name, **fields)


def send(
    db: Connection,
    user_id: int,
    kind: str,
    to_mobile: str,
    language: str,
    body: str,
    payout_id: int | None = None,
    keep_body: bool = True,
) -> None:
    """Send one text through the simulated gateway, which delivers at once.

    A payout gets at most one text of each kind, so a repeated event sends nothing.
    """
    if payout_id is not None:
        sent_before = db.execute(
            select(sms_messages.c.id).where(
                sms_messages.c.payout_id == payout_id, sms_messages.c.kind == kind
            )
        ).first()
        if sent_before:
            return
    now = datetime.now(UTC)
    db.execute(
        insert(sms_messages).values(
            user_id=user_id,
            payout_id=payout_id,
            kind=kind,
            to_mobile=to_mobile,
            language=language,
            body=body if keep_body else None,
            provider_message_id=f"SM{secrets.token_hex(8).upper()}",
            status="delivered",
            created_at=now,
            sent_at=now,
            delivered_at=now,
        )
    )


def start_verification(db: Connection, user_id: int, mobile: str, language: str) -> str:
    """Text a new code to the mobile and keep only its hash. Returns the code for the demo."""
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    db.execute(delete(sms_codes).where(sms_codes.c.user_id == user_id))
    db.execute(
        insert(sms_codes).values(
            user_id=user_id,
            code_hash=hash_password(code),
            expires_at=datetime.now(UTC) + CODE_LIFETIME,
            attempts=0,
        )
    )
    body = TEMPLATES["otp"][language].format(code=code)
    send(db, user_id, "otp", mobile, language, body, keep_body=False)
    return code


def check_code(db: Connection, user_id: int, code: str) -> str:
    """'ok', 'wrong', 'expired', 'locked' or 'none'. A correct code is used up."""
    row = db.execute(select(sms_codes).where(sms_codes.c.user_id == user_id)).first()
    if row is None:
        return "none"
    if row.attempts >= MAX_CODE_ATTEMPTS:
        return "locked"
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        return "expired"
    if not verify_password(code, row.code_hash):
        db.execute(
            update(sms_codes)
            .where(sms_codes.c.user_id == user_id)
            .values(attempts=row.attempts + 1)
        )
        return "wrong"
    db.execute(delete(sms_codes).where(sms_codes.c.user_id == user_id))
    return "ok"
