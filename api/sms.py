"""The texts SafeDay sends, and one-time codes for verifying a mobile.

Every text is a row in sms_messages; the dashboard shows them as the stallholder's phone.
api/sms_gateway.py delivers each one, to the real phone when textbee is set up.
The brief asks for one SMS in the customer's language, so each text has an English, Chinese,
Malay and Tamil version. The welcome text puts the trigger, payout and exclusions in one SMS:
English and Malay fit one 160-character SMS at every tier, Mandarin one 70-character Unicode
SMS, and Tamil takes three parts. The translations need a native speaker's check before launch.
"""

from __future__ import annotations

import math
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import Connection, delete, insert, select, update

from api import sms_gateway
from api.accounts import hash_password, verify_password
from api.payouts import sms_codes, sms_messages

CODE_DIGITS = 6
# Texts the phone may still report on. After an hour a text keeps its last status.
STILL_MOVING = ("queued", "sent", "unknown")
STATUS_CHECK_WINDOW = timedelta(hours=1)
CODE_LIFETIME = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
LANGUAGES = ("en", "zh", "ms", "ta")
SmsLanguage = Literal["en", "zh", "ms", "ta"]
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


def day_text(language: str, day: date) -> str:
    if language == "zh":
        return MONTHS_ZH.format(month=day.month, day=day.day)
    if language == "ms":
        return f"{day.day} {MONTHS_MS[day.month - 1]}"
    return f"{day.day} {day:%b}"


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
    """Send one text and keep a row of it, with the gateway's status.

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
    delivery = sms_gateway.deliver(to_mobile, body)
    now = datetime.now(UTC)
    db.execute(
        insert(sms_messages).values(
            user_id=user_id,
            payout_id=payout_id,
            kind=kind,
            to_mobile=to_mobile,
            language=language,
            body=body if keep_body else None,
            provider_message_id=delivery.provider_message_id,
            status=delivery.status,
            error=delivery.error,
            created_at=now,
            sent_at=None if delivery.status == "failed" else now,
            delivered_at=now if delivery.status == "delivered" else None,
        )
    )


def refresh_statuses(db: Connection, user_id: int | None) -> None:
    """Ask the gateway what happened to recent texts that have not reached a final status."""
    query = select(sms_messages.c.id, sms_messages.c.provider_message_id).where(
        sms_messages.c.status.in_(STILL_MOVING),
        sms_messages.c.provider_message_id.is_not(None),
        sms_messages.c.created_at >= datetime.now(UTC) - STATUS_CHECK_WINDOW,
    )
    if user_id is not None:
        query = query.where(sms_messages.c.user_id == user_id)
    for text_id, provider_message_id in db.execute(query).all():
        delivery = sms_gateway.check(provider_message_id)
        if delivery is None:
            continue
        db.execute(
            update(sms_messages)
            .where(sms_messages.c.id == text_id)
            .values(
                status=delivery.status,
                error=delivery.error,
                delivered_at=datetime.now(UTC) if delivery.status == "delivered" else None,
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
