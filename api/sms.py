"""The texts Payung sends, and one-time codes for verifying a mobile.

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
from api.payouts import sms_codes, sms_messages, sms_preferences

CODE_DIGITS = 6
# Texts the phone may still report on. After an hour a text keeps its last status.
STILL_MOVING = ("queued", "sent", "unknown")
STATUS_CHECK_WINDOW = timedelta(hours=1)
CODE_LIFETIME = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
LANGUAGES = ("en", "zh", "ms", "ta")
SmsLanguage = Literal["en", "zh", "ms", "ta"]
# The day colour bands set by the team on 15 Nov 2026, the same as api/site/day-colour.js.
DAY_COLOUR_FROM_PERCENT = (("red", 30), ("yellow", 0))

DAY_NAMES = {
    "en": {"yellow": "Yellow day", "red": "Red day"},
    "zh": {"yellow": "黄色日", "red": "红色日"},
    "ms": {"yellow": "Hari kuning", "red": "Hari merah"},
    "ta": {"yellow": "மஞ்சள் நாள்", "red": "சிவப்பு நாள்"},
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
    "payout_paid": {
        "en": "Payung: {day_colour}, {loss}% loss. S${amount} sent to PayNow {proxy} for "
        "{hazard} at {centre} on {day}. Ref {ref}. No claim needed.",
        "zh": "Payung：{day_colour}，损失{loss}%。因{day}{centre}{hazard}，S${amount}已转入您的"
        "PayNow {proxy}。编号{ref}。无需索赔。",
        "ms": "Payung: {day_colour}, kerugian {loss}%. S${amount} dihantar ke PayNow {proxy} "
        "kerana {hazard} di {centre} pada {day}. Ruj {ref}. Tiada tuntutan diperlukan.",
        "ta": "Payung: {day_colour}, இழப்பு {loss}%. {day} {centre} {hazard} காரணமாக "
        "S${amount} உங்கள் PayNow {proxy} க்கு அனுப்பப்பட்டது. குறிப்பு {ref}.",
    },
    "payout_failed": {
        "en": "Payung: we could not send S${amount} for {day} to PayNow {proxy}. Update your "
        "PayNow number in the app and we will retry. Ref {ref}.",
        "zh": "Payung：{day}的S${amount}未能转入PayNow {proxy}。"
        "请在应用中更新PayNow号码，我们会重试。编号{ref}。",
        "ms": "Payung: S${amount} untuk {day} gagal dihantar ke PayNow {proxy}. Kemas kini "
        "nombor PayNow dalam aplikasi. Ruj {ref}.",
        "ta": "Payung: {day} க்கான S${amount} PayNow {proxy} க்கு அனுப்ப முடியவில்லை. "
        "செயலியில் எண்ணைப் புதுப்பிக்கவும். குறிப்பு {ref}.",
    },
    "payout_held": {
        "en": "Payung: S${amount} for {day} is waiting for you. Verify your mobile in the app to "
        "receive it. Ref {ref}.",
        "zh": "Payung：{day}的S${amount}正在等您领取。请在应用中验证手机号码。编号{ref}。",
        "ms": "Payung: S${amount} untuk {day} sedang menunggu. Sahkan nombor telefon dalam "
        "aplikasi. Ruj {ref}.",
        "ta": "Payung: {day} க்கான S${amount} காத்திருக்கிறது. செயலியில் கைபேசி எண்ணை "
        "உறுதிப்படுத்தவும். குறிப்பு {ref}.",
    },
    "forecast_warning": {
        "en": "Payung: {hazards} forecast {day}. {tip} A forecast is not a payout; payment "
        "depends on the real reading.",
        "zh": "Payung：{day}预报{hazards}。{tip}预报不等于赔付，赔付以实际读数为准。",
        "ms": "Payung: ramalan {hazards} {day}. {tip} Ramalan bukan bayaran; bayaran ikut "
        "bacaan sebenar.",
        "ta": "Payung: {day} {hazards} முன்னறிவிப்பு. {tip} முன்னறிவிப்பு பணம் அல்ல; "
        "உண்மையான அளவீட்டைப் பொறுத்தே பணம்.",
    },
    "otp": {
        "en": "Payung code: {code}. It expires in 10 minutes. Do not share it.",
        "zh": "Payung验证码：{code}。10分钟内有效。请勿分享。",
        "ms": "Kod Payung: {code}. Tamat dalam 10 minit. Jangan kongsi.",
        "ta": "Payung குறியீடு: {code}. 10 நிமிடங்களில் காலாவதியாகும். பகிர வேண்டாம்.",
    },
}


# One tip per early warning: the one for the first hazard forecast, in WARNED_HAZARDS order.
WARNING_TIPS = {
    "en": {"rain": "Tie down awnings, raise stock.", "haze": "Keep N95 masks ready, cover food.",
           "heat": "Drink water often, rest in shade."},
    "zh": {"rain": "请固定雨篷、垫高货物。", "haze": "备好N95口罩，盖好食物。",
           "heat": "多喝水，在阴凉处休息。"},
    "ms": {"rain": "Ikat kanopi, angkat stok.", "haze": "Sedia topeng N95, tutup makanan.",
           "heat": "Minum air, rehat di tempat teduh."},
    "ta": {"rain": "கூரையைக் கட்டி, பொருட்களை உயர்த்தவும்.",
           "haze": "N95 முகக்கவசம் தயாராக வைக்கவும்.",
           "heat": "நீர் அருந்தி, நிழலில் ஓய்வெடுக்கவும்."},
}
HAZARD_LIST_SEPARATOR = {"en": ", ", "zh": "、", "ms": ", ", "ta": ", "}


# The welcome SMS, as the team approved it (16 Nov 2026), from the fullest wording to the
# shortest: welcome_text takes the first that fits one SMS with the customer's own numbers.
# Payouts are graded, so it says "up to". The PUB flood alert still pays, but the team left it
# out of this text (16 Nov 2026). Tamil leaves out the price and tier to fit 70 characters, so
# they are said at the sale.
WELCOME_PRICE = {"en": "S${price}/wk, ", "zh": "每周S${price}，", "ms": "S${price}/mgu, ", "ta": ""}
WELCOME = {
    "en": (
        "Payung Tier {tier}: {price}cover from day {wait}. Haze, heavy rain or heat "
        "near your stall: up to S${daily}/day, S${year}/yr. Else no pay even if sales drop.",
        "Payung Tier {tier}: {price}cover from day {wait}. Haze, rain or heat "
        "near your stall: up to S${daily}/day, S${year}/yr. Else no pay even if sales drop.",
    ),
    "zh": (
        "Payung第{tier}级{price}买后{wait}天生效。摊位附近烟霾、大雨或酷热："
        "日赔≤S${daily}，年≤S${year}。否则生意差也不赔",
        "第{tier}级{price}买后{wait}天生效。摊位附近烟霾、大雨或酷热："
        "日赔≤S${daily}，年≤S${year}。否则生意差也不赔",
    ),
    "ms": (
        "Payung Tahap {tier}: {price}mula hari ke-{wait}. Jerebu, hujan lebat atau panas "
        "dekat gerai: hingga S${daily}/hari, S${year}/thn. Lain tiada bayaran walau rugi.",
        "Payung Tahap {tier}: {price}mula hari ke-{wait}. Jerebu, hujan atau panas "
        "dekat gerai: hingga S${daily}/hari, S${year}/thn. Lain tiada bayaran walau rugi.",
    ),
    "ta": (
        "{wait}நாள் பின் புகை/மழை/வெயில்: S${daily}/நாள், S${year}/ஆ. இல்லையேல் 0",
    ),
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
    """'none' for a day with no loss, else 'yellow' or 'red'. A yellow day still pays."""
    if loss_percent <= 0:
        return "none"
    return next(colour for colour, start in DAY_COLOUR_FROM_PERCENT if loss_percent >= start)


def day_name(language: str, loss_percent: float) -> str:
    return DAY_NAMES[language][day_colour(loss_percent)]


def payout_text(kind: str, language: str, hazard: str, **fields: str) -> str:
    hazard_name = HAZARD_NAMES[language].get(hazard, hazard)
    return TEMPLATES[kind][language].format(hazard=hazard_name, **fields)


def welcome_text(language: str, tier: int, weekly_sgd: float | None, payout_sgd: float,
                 max_days: int, wait_days: int) -> str:
    """The cover in one SMS: tier, price, when it starts, what pays, how much, and that nothing
    else pays. The first wording that fits one SMS wins (WELCOME). Without a price (a preview
    with no place yet) the price is left out."""
    price = "" if weekly_sgd is None else WELCOME_PRICE[language].format(price=f"{weekly_sgd:.2f}")
    yearly = payout_sgd * max_days
    body = ""
    for wording in WELCOME[language]:
        for year in (f"{yearly:,.0f}", f"{yearly:.0f}"):
            body = wording.format(tier=tier, price=price, wait=wait_days,
                                  daily=number(payout_sgd), year=year)
            if segments(body) == 1:
                return body
    return body


def warning_text(language: str, hazards: list[str], day: date) -> str:
    """The evening-before warning: what is forecast for which day, one tip, and that a forecast
    pays nothing on its own."""
    names = HAZARD_LIST_SEPARATOR[language].join(HAZARD_NAMES[language][h] for h in hazards)
    return TEMPLATES["forecast_warning"][language].format(
        hazards=names, day=day_text(language, day), tip=WARNING_TIPS[language][hazards[0]]
    )


def preferred_language(db: Connection, user_id: int) -> str | None:
    return db.execute(
        select(sms_preferences.c.language).where(sms_preferences.c.user_id == user_id)
    ).scalar_one_or_none()


def set_preferred_language(db: Connection, user_id: int, language: str) -> None:
    db.execute(delete(sms_preferences).where(sms_preferences.c.user_id == user_id))
    db.execute(
        insert(sms_preferences).values(
            user_id=user_id, language=language, updated_at=datetime.now(UTC)
        )
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
