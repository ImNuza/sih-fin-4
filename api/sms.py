"""Simulated SMS gateway, the texts SafeDay sends, and one-time codes for verifying a mobile.

Every text is a row in sms_messages; the dashboard shows them as the stallholder's phone.
The brief asks for the trigger, payout and exclusions in one SMS in the customer's language,
so each text has an English, Chinese, Malay and Tamil version; the demo offers English
and Mandarin. English and Malay fit one
160-character SMS at every tier, and Mandarin one 70-character Unicode SMS. The Tamil welcome
takes three parts. The translations, and shorter
Tamil version, need a native speaker before launch.
"""

from __future__ import annotations

import math
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import Connection, delete, insert, select, update

from api.accounts import hash_password, verify_password
from api.payouts import sms_codes, sms_messages

CODE_DIGITS = 6
CODE_LIFETIME = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
# Languages a customer can pick. For the demo: English and Mandarin. The Malay and Tamil texts
# stay below, tested, to switch back on once a native speaker has checked them.
LANGUAGES = ("en", "zh")
SmsLanguage = Literal["en", "zh"]
TRANSLATED = ("en", "zh", "ms", "ta")

# The heat readings count work hours at WBGT 32°C or more (scripts/heat_stats.py): MOM's
# threshold for mandatory rest breaks in heavy outdoor work. Readings cover 07:00 to 19:00 SGT.
HEAT_WBGT_C = 32
WORK_HOURS = {"en": "7am-7pm", "ms": "7pg-7mlm", "zh": "7-19时", "ta": "காலை 7-மாலை 7"}
MONTHS_ZH = "{month}月{day}日"
MONTHS_MS = ("Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogo", "Sep", "Okt", "Nov", "Dis")

# SMS parts: GSM-7 text fits 160 characters in one SMS (153 a part when split); anything
# outside GSM-7, such as Chinese or Tamil, goes as UCS-2 at 70 (67 a part).
GSM_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXTENDED = frozenset("^{}\\[~]|€")
GSM_SINGLE, GSM_PART = 160, 153
UCS2_SINGLE, UCS2_PART = 70, 67
# Parts a payout text may take; past this the centre name is left out.
PAID_PARTS = {"en": 1, "ms": 1, "zh": 1, "ta": 2}

# What NEA or the government recorded, written out so customers can check it themselves.
# "WBGT 32C" keeps heat stress from being read as the air temperature on a weather app.
TRIGGERS = {
    "en": {"heat": "NEA WBGT {wbgt}C+ for {value}h", "rain": "NEA rain {value}mm/h",
           "haze": "NEA PSI {value}", "flood": "PUB flood alert", "closure": "Closure order"},
    "zh": {"heat": "WBGT≥{wbgt}°C达{value}小时", "rain": "雨量{value}mm/时", "haze": "PSI {value}",
           "flood": "PUB水灾警报", "closure": "关闭令"},
    "ms": {"heat": "WBGT NEA {wbgt}C+ selama {value}j", "rain": "Hujan NEA {value}mm/j",
           "haze": "PSI NEA {value}", "flood": "Amaran banjir PUB", "closure": "Perintah tutup"},
    "ta": {"heat": "NEA WBGT {wbgt}C+ {value} மணி", "rain": "NEA மழை {value}mm/மணி",
           "haze": "NEA PSI {value}", "flood": "PUB வெள்ள எச்சரிக்கை", "closure": "மூடல் உத்தரவு"},
}
# Where the reading counted, when the text has room for it.
PLACES = {"en": " at {centre}", "ms": " di {centre}", "zh": "{centre}", "ta": " {centre} இல்"}

TEMPLATES = {
    "welcome": {
        "en": "SafeDay: up to S${payout}/day if NEA WBGT {wbgt}C+ {heat_hours}h+, "
        "rain {rain}mm/h+, PSI {psi}+ or flood alert, {hours}. Max {days} days/yr from {start}. "
        "Else no pay, even if you lose income.",
        # Mandarin leaves out the "SafeDay：" prefix to fit one 70-character SMS: the phone
        # shows SafeDay as the registered sender ID (Singapore SMS Sender ID Registry).
        "zh": "{hours}WBGT≥{wbgt}°C达{heat_hours}小时、雨≥{rain}mm/时、PSI≥{psi}或水灾，"
        "日赔≤S${payout}，年限{days}天，{start}起。否则亏损也不赔",
        "ms": "SafeDay: hingga S${payout}/hari jika WBGT {wbgt}C+ {heat_hours}j+, "
        "hujan {rain}mm/j+, PSI {psi}+ atau banjir, {hours}. Had {days} hari/thn dari {start}. "
        "Jika tidak, tiada bayaran walau rugi.",
        "ta": "SafeDay: {hours} NEA WBGT {wbgt}C+ {heat_hours} மணி+, மழை {rain}mm/மணி+, "
        "PSI {psi}+ அல்லது வெள்ளம்: நாளுக்கு S${payout} வரை. ஆண்டுக்கு {days} நாள், "
        "{start} முதல். இல்லையெனில் இழப்பிலும் பணம் இல்லை.",
    },
    "payout_paid": {
        "en": "SafeDay: S${amount} sent by PayNow to {proxy}. {trigger}{place} on {day}. "
        "No claim needed. Ref {ref}",
        "zh": "{day}{place}{trigger}，S${amount}已转入PayNow {proxy}。无需索赔。编号{ref}",
        "ms": "SafeDay: S${amount} dihantar melalui PayNow ke {proxy}. {trigger}{place} "
        "pada {day}. Tiada tuntutan diperlukan. Ruj {ref}",
        "ta": "SafeDay: {day}{place} {trigger}. S${amount} PayNow {proxy} க்கு "
        "அனுப்பினோம். கோரிக்கை தேவையில்லை. குறிப்பு {ref}",
    },
    "payout_failed": {
        "en": "SafeDay: we could not send S${amount} for {day} to PayNow {proxy}. Update your "
        "PayNow number in the app and we will retry. Ref {ref}.",
        "zh": "{day}的S${amount}未能转入PayNow {proxy}。请在应用中更新号码，我们会重试。编号{ref}",
        "ms": "SafeDay: S${amount} untuk {day} gagal dihantar ke PayNow {proxy}. Kemas kini "
        "nombor PayNow dalam aplikasi. Ruj {ref}.",
        "ta": "SafeDay: {day} க்கான S${amount} PayNow {proxy} க்கு அனுப்ப முடியவில்லை. "
        "செயலியில் எண்ணைப் புதுப்பிக்கவும். குறிப்பு {ref}.",
    },
    "payout_held": {
        "en": "SafeDay: S${amount} for {day} is waiting for you. Verify your mobile in the app to "
        "receive it. Ref {ref}.",
        "zh": "{day}的S${amount}正在等您领取。请在应用中验证手机号码。编号{ref}",
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


def segments(body: str) -> int:
    """How many SMS parts the text goes out as."""
    if all(c in GSM_BASIC or c in GSM_EXTENDED for c in body):
        units = len(body) + sum(c in GSM_EXTENDED for c in body)
        single, part = GSM_SINGLE, GSM_PART
    else:
        units = len(body.encode("utf-16-le")) // 2
        single, part = UCS2_SINGLE, UCS2_PART
    return 1 if units <= single else math.ceil(units / part)


def number(value: float) -> str:
    return f"{value:g}"


def money(sgd: float) -> str:
    """S$ amount for a text: whole dollars without cents, otherwise two decimals."""
    cents = round(sgd * 100)
    return str(cents // 100) if cents % 100 == 0 else f"{cents / 100:.2f}"


def familiar_name(centre: str) -> str:
    """The name people use: NEA lists many centres as 'Street Blk 32 (People's Park Food Centre)'."""
    bracketed = re.search(r"\(([^)]+)\)", centre)
    return bracketed.group(1) if bracketed else centre


def day_text(language: str, day: date) -> str:
    if language == "zh":
        return MONTHS_ZH.format(month=day.month, day=day.day)
    if language == "ms":
        return f"{day.day} {MONTHS_MS[day.month - 1]}"
    return f"{day.day} {day:%b}"


def trigger_text(language: str, hazard: str, reading: float) -> str:
    return TRIGGERS[language][hazard].format(wbgt=HEAT_WBGT_C, value=number(reading))


def payout_text(kind: str, language: str, hazard: str, reading: float, day: date,
                centre: str = "", **fields: str) -> str:
    """A payout text, naming the centre only when the text still fits its parts."""
    def build(place: str) -> str:
        return TEMPLATES[kind][language].format(
            trigger=trigger_text(language, hazard, reading), day=day_text(language, day),
            place=place, **fields,
        )

    if centre:
        with_centre = build(PLACES[language].format(centre=familiar_name(centre)))
        if segments(with_centre) <= PAID_PARTS[language]:
            return with_centre
    return build("")


def welcome_text(language: str, payout_sgd: float, heat_hours: float, rain_mm: float,
                 psi: float, max_days: int, first_day: date) -> str:
    """The cover in one SMS: what pays, how much, the cap, and that nothing else pays."""
    return TEMPLATES["welcome"][language].format(
        payout=number(payout_sgd), wbgt=HEAT_WBGT_C, heat_hours=number(heat_hours),
        rain=number(rain_mm), psi=number(psi), hours=WORK_HOURS[language], days=max_days,
        start=day_text(language, first_day),
    )


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
