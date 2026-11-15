"""The early-warning text, sent the evening before NEA forecasts heavy rain, haze or heat.

Reads NEA's 24-hour forecast (data.gov.sg twenty-four-hr-forecast, issued a few times a day,
see docs/notes/weather-forecast-sources-2026-11-13.md). It labels each of the 5 PSI regions,
the regions policies are priced in, for tonight, tomorrow morning and tomorrow afternoon. The
labels are words, not amounts, so a warning never decides a payout: payouts read the real NEA
readings through api/readings.py. Design: docs/notes/early-warning-sms-2026-11-15.md.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import Connection, select

from api import payout_flow, sms
from api.accounts import policies
from api.payouts import sms_messages

SINGAPORE = payout_flow.SINGAPORE
WARNED_HAZARDS = ("rain", "haze", "heat")
WARNING_KIND = "forecast_warning"
# The forecast's morning and afternoon periods: the trading day a warning is about.
DAYTIME_START_HOUR, DAYTIME_END_HOUR = 6, 18
RAIN_LABEL_WORD = "Heavy"
HAZE_LABEL = "Hazy"
# NEA forecasts no WBGT, only the island's high temperature. From 16 Jan 2025 to 31 Oct 2026
# the island's highest MSS reading reached 35 C on 58 of 654 days; 34 C would text on 264.
HEAT_FORECAST_HIGH_C = 35
RUN_OUTCOMES = ("sent", "already_warned", "not_warned", "cover_ended", "no_mobile")


def in_singapore(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp).astimezone(SINGAPORE)


def daytime_periods(record: dict) -> list[tuple[date, dict]]:
    periods = []
    for period in record["periods"]:
        start = in_singapore(period["timePeriod"]["start"])
        if DAYTIME_START_HOUR <= start.hour < DAYTIME_END_HOUR:
            periods.append((start.date(), period))
    return periods


def forecast_day(record: dict) -> date:
    """The latest day the forecast's daytime periods fall on: tomorrow, for the evening issue.
    Not validPeriod, which the 11 pm issue ends a day late."""
    return max(day for day, _ in daytime_periods(record))


def daytime_labels(record: dict) -> dict[str, list[str]]:
    day = forecast_day(record)
    labels: dict[str, list[str]] = {}
    for period_day, period in daytime_periods(record):
        if period_day != day:
            continue
        for region, label in period["regions"].items():
            labels.setdefault(region, []).append(label["text"])
    return labels


def warned_regions(record: dict) -> dict[str, list[str]]:
    """Each region with a bad day forecast, and which hazards, in WARNED_HAZARDS order."""
    hot = record["general"]["temperature"]["high"] >= HEAT_FORECAST_HIGH_C
    regions = {}
    for region, labels in daytime_labels(record).items():
        forecast = {
            "rain": any(RAIN_LABEL_WORD in label for label in labels),
            "haze": HAZE_LABEL in labels,
            "heat": hot,
        }
        hazards = [hazard for hazard in WARNED_HAZARDS if forecast[hazard]]
        if hazards:
            regions[region] = hazards
    return regions


def warned_today(db: Connection, user_id: int) -> bool:
    today_start = datetime.combine(datetime.now(SINGAPORE).date(), time(), SINGAPORE)
    return db.execute(
        select(sms_messages.c.id).where(
            sms_messages.c.user_id == user_id,
            sms_messages.c.kind == WARNING_KIND,
            sms_messages.c.created_at >= today_start.astimezone(UTC),
        )
    ).first() is not None


def warn(db: Connection, user_id: int, mobile: str, language: str, hazards: list[str],
         day: date) -> None:
    sms.send(db, user_id, WARNING_KIND, mobile, language, sms.warning_text(language, hazards, day))


def send_warnings(db: Connection, record: dict) -> dict:
    """Text every policyholder in a warned region, at most once a Singapore day each.

    Policies in their waiting period are warned too: the warning helps them prepare, and it
    pays nothing.
    """
    day = forecast_day(record)
    regions = warned_regions(record)
    counts = dict.fromkeys(RUN_OUTCOMES, 0)
    for policy in db.execute(select(policies)).all():
        counts[warn_policy(db, policy, regions.get(policy.region), day)] += 1
    return {"day": day.isoformat(), "regions": regions, "counts": counts}


def warn_policy(db: Connection, policy, hazards: list[str] | None, day: date) -> str:
    if not hazards:
        return "not_warned"
    ends = payout_flow.cover_ends(db, policy.user_id)
    if ends is not None and day >= ends:
        return "cover_ended"
    if warned_today(db, policy.user_id):
        return "already_warned"
    contact = payout_flow.welcome_contact(db, policy.user_id)
    if contact is None:
        return "no_mobile"
    mobile, language = contact
    warn(db, policy.user_id, mobile, language, hazards, day)
    return "sent"
