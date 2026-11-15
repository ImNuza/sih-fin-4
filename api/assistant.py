"""Payung's one assistant: a chat that answers owners, insurers and visitors from the platform's
own numbers.

POST /api/assistant/chat. A language model picks which tool to run; the tools call the same
engine as every page (quotes, the station rule in api/readings.py, payouts, the burn, the
underwriting queue), so every number in a reply comes from the API. A place is priced exactly
as POST /api/quote prices it: a hawker at its centre, a shop at its postcode's area point, a
map point at its nearest region, a region as a whole. The model never sets a price or decides
a payout, and replies in the language the person writes in: English, Chinese, Malay or Tamil
(Singlish is fine).

The model is DeepSeek, Grok or OpenAI, by the first of DEEPSEEK_API_KEY, XAI_API_KEY or
OPENAI_API_KEY set (environment or the repo's env file), else a local model served by Ollama
(OLLAMA_MODEL, qwen3:8b by default), which keeps the conversation on this machine. The reply
is always in the language picked in the chat: a remote model writes it directly; the local
model writes English and Chinese directly, and for Malay and Tamil answers in English that
api/translate.py turns into the picked language. With no model at all, keywords pick the tool
and an English template answers, translated the same way. Nothing sent here is stored: the conversation lives in
the browser tab.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from calendar import month_name
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import get_close_matches
from zoneinfo import ZoneInfo

import openai
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from api import (
    accounts, calculator, kyc, payout_flow, readings, store, translate, underwriting,
)
from api.day_history import day_readings
from api.models import HazeBonusQuote, KycRequest, Quote, Tariff, TierQuote
from api.payouts import payouts

log = logging.getLogger(__name__)
SINGAPORE = ZoneInfo("Asia/Singapore")

DEEPSEEK_KEY_NAME, DEEPSEEK_MODEL = "DEEPSEEK_API_KEY", "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
LANGUAGE_NAMES = {"en": "English", "zh": "Simplified Chinese", "ms": "Malay", "ta": "Tamil"}
MAX_TOOL_ROUNDS = 5
MAX_REPLY_TOKENS = 1600
MAX_TURNS_KEPT = 12
MAX_MESSAGE_CHARS = 2000
HAZARDS = ("haze", "rain", "heat")
DEFAULT_PRODUCT, DEFAULT_TIER = "cooked_food", "tier_2"
CLOSURE = "closure"
# The headline price is the yearly premium over 12 months (api/site/tier-proof.js); billing is
# weekly.
MONTHS_PER_YEAR = 12
# The lockdown example every page uses (api/site/tier-proof.js).
LOCKDOWN_EXAMPLE_DAYS = 40
POSTCODE_IN_TEXT = re.compile(r"\b(\d{6})\b")
# Fields of the buy form (api/site/buy/index.html) the assistant may fill from what a person
# says. Identity and payment fields stay with the person, so a password is never among them.
FORM_FIELDS = (
    "business_class", "business_name", "centre", "stall_unit", "licence_no", "postcode",
    "product", "name", "designation", "phone", "email", "sms_language", "term_months",
)

router = APIRouter(prefix="/api/assistant")


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    messages: list[Turn] = Field(min_length=1, max_length=40)
    page: str = Field(default="site", max_length=20)
    language: str = Field(default="en", pattern="^(en|zh|ms|ta)$")


class Action(BaseModel):
    type: str
    label: str | None = None
    url: str | None = None
    fields: dict[str, str] | None = None


class ChatReply(BaseModel):
    reply: str
    actions: list[Action] = []
    source: str


# Languages the local model writes poorly: it answers in English and api/translate.py translates.
TRANSLATED_LOCALLY = ("ms", "ta")


@dataclass
class Context:
    """What one chat request can see: the live tariff, the app's replays, and who is asking."""

    request: Request
    tariff: Tariff
    page: str
    user: accounts.Account | None
    language: str = "en"
    reply_language: str = "en"
    actions: list[Action] = field(default_factory=list)

    @property
    def state(self):
        return self.request.app.state

    @property
    def role(self) -> str:
        return self.user.role if self.user else "visitor"


def current_user_or_none(request: Request) -> accounts.Account | None:
    try:
        return accounts.current_user(request)
    except HTTPException:
        return None


def today() -> date:
    return datetime.now(SINGAPORE).date()


# ---------- places and policies ----------


@dataclass(frozen=True)
class Where:
    """A place as POST /api/quote prices it: a hawker centre, a shop's postcode area, a map point
    (priced for its nearest region) or a whole PSI region."""

    name: str
    region: str
    lat: float
    lng: float
    centre: str | None = None
    postcode: str | None = None
    whole_region: bool = False

    @property
    def who(self) -> str:
        """Who the proof lines are about, as api/site/tier-proof.js words them."""
        if self.centre:
            return "a stall here"
        return "a shop here" if self.postcode else "a business here"


def centre_place(centre: dict) -> Where:
    return Where(centre["name"], centre["region"], centre["lat"], centre["lng"], centre["name"])


def postcode_place(ctx: Context, postcode: str) -> Where:
    """A shop's postcode at its area's point (postcodes.area_point), as its price reads it."""
    from api import main as app_main  # the app, loaded by now; main imports this module

    point = app_main.postcode_point(ctx.request, postcode)
    return Where(f"postcode {postcode} ({point['basis']})", point["region"], point["lat"],
                 point["lng"], postcode=postcode)


def point_place(ctx: Context, name: str, lat: float, lng: float) -> Where:
    """A map point, paid on the PSI region of its nearest NEA station, as POST /api/quote."""
    from api import main as app_main

    return Where(name, app_main.nearest_region(ctx.request, lat, lng), lat, lng)


def region_place(ctx: Context, region: str) -> Where:
    lat, lng = ctx.state.map_static["region_points"][region]
    return Where(f"the {region} region", region, lat, lng, whole_region=True)


def find_place(ctx: Context, centre: str | None = None, region: str | None = None,
               postcode: str | None = None) -> Where | None:
    """A shop's postcode, else a hawker centre by (fuzzy) name, else a named area's point, else
    a PSI region."""
    if postcode:
        return postcode_place(ctx, postcode.strip())
    centres = ctx.state.map_static["hawker_centres"]
    if centre:
        by_name = {c["name"].lower(): c for c in centres}
        match = by_name.get(centre.lower()) or next(
            (c for c in centres if centre.lower() in c["name"].lower()), None
        )
        if match is None:
            close = get_close_matches(centre.lower(), list(by_name), n=1, cutoff=0.6)
            match = by_name[close[0]] if close else None
        if match:
            return centre_place(match)
    named = kyc.match_place(centre or region or "", ctx.state.places)
    if named is not None:
        if named.match == "hawker_centre":
            return centre_place(ctx.state.centres_by_name[named.name])
        label = f"{named.name} (for {named.area})" if named.area and named.area != named.name else named.name
        return point_place(ctx, label, named.lat, named.lng)
    if region and region.lower() in ctx.state.map_static["region_points"]:
        return region_place(ctx, region.lower())
    return None


def my_policy(ctx: Context):
    """The signed-in owner's policy with the terms in force today, or None."""
    if ctx.user is None or ctx.user.role != "sme":
        return None
    with ctx.state.db.connect() as db:
        policy = db.execute(
            select(accounts.policies).where(accounts.policies.c.user_id == ctx.user.id)
        ).first()
        return payout_flow.policy_on(db, policy, today()) if policy else None


def policy_place(ctx: Context, policy) -> Where | None:
    """Where a policy is priced and paid from (payout_api.policy_point): its hawker centre, else
    its shop's postcode area, else its region's point."""
    from api import main as app_main

    if policy is None:
        return None
    if policy.centre in ctx.state.centres_by_name:
        return centre_place(ctx.state.centres_by_name[policy.centre])
    postcode = app_main.shop_postcode(app_main.latest_application(ctx.state.db, policy.user_id))
    if postcode:
        return postcode_place(ctx, postcode)
    return region_place(ctx, policy.region)


def place_quote(ctx: Context, where: Where, product: str) -> Quote:
    """The quote POST /api/quote gives this place: what a business there is shown and charged."""
    from api import main as app_main

    if where.centre or where.postcode or where.whole_region:
        return app_main.business_quote(
            ctx.request, ctx.tariff, product, where.region, where.centre, where.postcode
        )
    return app_main.place_quote(
        ctx.request, ctx.tariff, product, where.region, where.lat, where.lng
    )


def chosen_tier(quote: Quote, tier: str) -> TierQuote:
    found = next((t for t in quote.tiers if t.tier == tier), None)
    if found is None:
        raise calculator.UnknownKey(f"Unknown tier: {tier}")
    return found


def monthly(yearly_sgd: float) -> float:
    return round(yearly_sgd / MONTHS_PER_YEAR, 2)


def paid_days_limit(tier: TierQuote) -> int:
    return round(tier.max_payout_per_year_sgd / tier.daily_payout_sgd)


def year_money(value: float) -> str:
    """A year's payout in whole dollars, as api/site/tier-proof.js shows it."""
    return f"S${int(value + 0.5):,}"


def proof_lines(tier: TierQuote, who: str) -> list[str]:
    """The replay at the customer's own place in the words of api/site/tier-proof.js."""
    proof = tier.proof
    if proof is None:
        return []
    years = proof.years_replayed
    days = int(proof.payout_days_per_year + 0.5)
    spread = f"about {days} day{'' if days == 1 else 's'}" if days >= 1 else "less than one day"
    lines = []
    if proof.typical_year_paid_sgd > 0:
        lines.append(f"A typical year paid {year_money(proof.typical_year_paid_sgd)}, spread over "
                     f"{spread} with a part payout.")
    if proof.years_paid == 0:
        lines.append(f"{who.capitalize()} would not have been paid in any of the last {years} "
                     "years.")
    elif proof.years_paid == years:
        lines.append(f"{who.capitalize()} would have been paid in each of the last {years} years.")
    else:
        lines.append(f"{who.capitalize()} would have been paid in {proof.years_paid} of the last "
                     f"{years} years.")
    year = calculator.PROOF_YEAR
    paid = proof.paid_2026_sgd
    lines.append(f"In {year}, {who} would have been paid {year_money(paid)} in total." if paid > 0
                 else f"In {year}, {who} would not have been paid.")
    lines.append(f"We estimate a year like {calculator.HAZE_YEAR} would pay about "
                 f"{year_money(proof.haze_2015_like_sgd)}. It does not run out before "
                 f"{paid_days_limit(tier)} bad days.")
    return lines


def haze_bonus_row(bonus: HazeBonusQuote | None) -> dict | None:
    if bonus is None:
        return None
    return {
        "pays_once_sgd": bonus.lump_sum_sgd,
        "pays_when": f"{bonus.trigger_days} or more days at PSI {bonus.trigger_psi:g} or above in "
                     "the region in a policy year",
        "monthly_sgd": monthly(bonus.yearly_sgd), "yearly_sgd": bonus.yearly_sgd,
        "weekly_billed_sgd": bonus.weekly_sgd,
        "pays_times_its_price": bonus.multiple,
        "can_be_added_now": bonus.on_sale_now,
        "would_have_paid_here_in_years": bonus.would_have_paid_years,
    }


def tier_row(tier: TierQuote, who: str) -> dict:
    return {
        "tier": tier.tier, "label": tier.label,
        "monthly_premium_sgd": monthly(tier.yearly_premium_sgd),
        "yearly_premium_sgd": tier.yearly_premium_sgd,
        "weekly_billed_sgd": tier.weekly_premium_sgd,
        "pays_for_a_day_with_no_sales_sgd": tier.daily_payout_sgd,
        "paid_days_a_year_up_to": paid_days_limit(tier),
        "most_paid_in_a_year_sgd": tier.max_payout_per_year_sgd,
        "price_per_day_sgd": tier.price_per_day_sgd,
        "pays_up_to_times_its_price": tier.cover_multiple,
        "best_value": tier.best_value,
        "sold_directly": tier.sold_directly,
        "proof": proof_lines(tier, who),
        "severe_haze_payout_add_on": haze_bonus_row(tier.haze_bonus),
    }


def tier_rows(quote: Quote, who: str) -> list[dict]:
    return [tier_row(t, who) for t in quote.tiers]


def amount(value: float) -> str:
    return f"S${value:,.0f}" if float(value).is_integer() else f"S${value:,.2f}"


def listed(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def months_text(months: list[int]) -> str:
    """'May to October' for a run of months, else the months listed."""
    if months == list(range(months[0], months[0] + len(months))) and len(months) > 2:
        return f"{month_name[months[0]]} to {month_name[months[-1]]}"
    return listed([month_name[m] for m in months])


def product_facts(tariff: Tariff) -> dict[str, str]:
    """What the product is, worded from the live tariff, never from numbers written here."""
    tiers = tariff.tiers
    limits = sorted({t.max_paid_days_per_year for t in tiers})
    wait = payout_flow.WAITING_PERIOD_DAYS
    closure = next((h for h in tariff.hazards if h.key == CLOSURE), None)
    lockdown_in_full = (
        f", so a {LOCKDOWN_EXAMPLE_DAYS}-day lockdown or closure order is paid in full"
        if closure is not None and LOCKDOWN_EXAMPLE_DAYS <= limits[0] else ""
    )
    facts = {
        "daily_amounts": (
            "Each tier pays a fixed amount for a day with no sales: "
            + listed([f"{t.label} {amount(t.daily_payout_sgd)}" for t in tiers]) + "."
        ),
        "partial_days": "A partly bad day pays the share of the day lost.",
        "yearly_limit": (
            f"Every tier pays up to {limits[0]} full days a year{lockdown_in_full}."
            if len(limits) == 1 else
            "Each tier pays up to " + listed([f"{t.max_paid_days_per_year} full days a year on "
                                              f"{t.label}" for t in tiers]) + "."
        ),
        "monthly_price": "The price is shown a month: the yearly premium over 12. It is billed "
                         "weekly.",
        "higher_tiers": f"{listed([t.label for t in tiers[-2:]])} can pay more than a hawker stall "
                        "takes in a day, so they suit businesses with higher takings. Not every "
                        "tier matches a stall's loss.",
        "waiting_period": f"Cover pays from {wait} days after it starts. A move to a higher "
                          f"tier starts the {wait}-day wait again; the same or a lower tier "
                          "keeps it.",
        "proof": "Each quote carries proof numbers from a replay at the customer's own place: "
                 "'A typical year paid ...' with its payout days, 'In "
                 f"{calculator.PROOF_YEAR} ... in total' (rain and heat as well as haze), and 'We "
                 f"estimate a year like {calculator.HAZE_YEAR} ...' (an estimate).",
        "forecast": "The evening warning text uses NEA's own forecast, and a forecast is not a "
                    "payout. Payung's trained models only rebuild past years' readings; no "
                    "model predicts bad days.",
    }
    if closure is not None and closure.assumed_days_per_year:
        every = LOCKDOWN_EXAMPLE_DAYS / closure.assumed_days_per_year
        facts["lockdown"] = (
            "A lockdown or closure order pays the daily amount for every day it lasts, within "
            "the yearly limit. It has no history, so it is priced as one "
            f"{LOCKDOWN_EXAMPLE_DAYS}-day lockdown every {every:g} years, a team assumption "
            "until Income gives its view."
        )
    if all(t.premium_shares for t in tiers):
        facts["premium_shares"] = (
            "Of the premium before GST, expected payouts are "
            + listed([f"{t.premium_shares.expected_payouts:.0%} on {t.label}" for t in tiers])
            + f"; the rest pays reinsurance, running costs and profit. GST of "
            f"{tariff.pricing.gst_rate:.0%} goes on top."
        )
    bonus = tariff.haze_bonus
    if bonus is not None:
        facts["severe_haze_payout"] = (
            f"Optional severe haze payout: when the customer's PSI region has {bonus.trigger_days} "
            f"or more days at PSI {bonus.trigger_psi:g} or above in a policy year, it pays "
            f"{bonus.lump_sum_daily_multiple:g} times the daily amount once that year, on top of "
            f"the daily cover's limit. It costs the lump sum divided by {bonus.payout_multiple:g} "
            f"a year, cannot be added from {months_text(bonus.no_sale_months)}, and has its own "
            f"{bonus.waiting_days}-day wait. The daily cover still pays from the first hazy day."
        )
    held = [(h, h.stations_on_hold) for h in tariff.hazards if h.stations_on_hold]
    if held:
        facts["stations_on_hold"] = " ".join(
            f"{hazard.label} stations {listed(stations)} are on hold until NEA confirms them, so "
            "places near them read the next nearest station."
            for hazard, stations in held
        )
    return facts


def trigger_levels(tariff: Tariff) -> dict[str, str]:
    units = {"haze": "24-hour PSI", "rain": "mm of rain in one work hour",
             "heat": "work hours at WBGT 32°C or more"}
    levels = {}
    for hazard in tariff.hazards:
        if hazard.key in units:
            levels[hazard.key] = f"pays from {hazard.bands[0].at_least:g} {units[hazard.key]}"
    levels["flood"] = "pays when a PUB flash-flood alert covers the place"
    return levels


def parse_day(text: str | None) -> date | None:
    """A date from 'today', 'yesterday', '2026-10-18' or '18 Oct 2026'."""
    if not text:
        return None
    text = text.strip().lower()
    if text in ("today", "now"):
        return today()
    if text == "yesterday":
        return today() - timedelta(days=1)
    for pattern in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d %b", "%d %B"):
        try:
            parsed = datetime.strptime(text, pattern).date()
        except ValueError:
            continue
        if "%Y" not in pattern:
            parsed = parsed.replace(year=today().year)
            if parsed > today():
                parsed = parsed.replace(year=today().year - 1)
        return parsed
    return None


def readings_on(ctx: Context, where: Where, day: date) -> tuple[dict[str, float], dict, str]:
    """A place's readings on one day by the payout rule, the rule behind each, and the source."""
    from api import main as app_main

    if day == today():
        live = ctx.state.live
        live.ensure_started()
        snapshot = live.read()
        if not snapshot.get("available"):
            return {}, {}, "the live NEA feed is still loading"
        scored = app_main.live_loss(
            app_main.LiveToday(snapshot), ctx.tariff, DEFAULT_PRODUCT, where.region,
            where.lat, where.lng,
        )
        return scored["readings"], {}, f"live NEA readings at {snapshot.get('fetched_at')}"
    table = day_readings(ctx.request)
    recorded = table.get(day.isoformat())
    if recorded is None:
        return {}, {}, "no NEA record for that day"
    place = readings.history_place(where.region, where.lat, where.lng, ctx.state.sites)
    site = readings.site_readings(recorded, place, readings.station_rule(ctx.tariff))
    values = {hazard: site.readings.get(hazard, 0.0) for hazard in HAZARDS}
    return values, site.basis, "NEA's recorded readings"


# ---------- tools ----------


def tool_describe_business(ctx: Context, description: str, postcode: str | None = None) -> dict:
    """Read a business from the owner's words into a product, a place and cover options."""
    shop = kyc.read_shop(KycRequest(text=description), ctx.tariff.products, ctx.state.places)
    postcode = postcode or next(iter(POSTCODE_IN_TEXT.findall(description)), None)
    if shop.product is None or (shop.place is None and postcode is None):
        return {
            "understood": shop.summary,
            "missing": [n for n, v in (("what you sell", shop.product),
                                       ("where (the hawker centre or the shop's postcode)",
                                        shop.place or postcode)) if v is None],
        }
    from api import main as app_main

    if postcode:
        where = postcode_place(ctx, postcode)
    elif shop.place.match == "hawker_centre":
        where = centre_place(ctx.state.centres_by_name[shop.place.name])
    else:
        where = point_place(ctx, shop.place.name, shop.place.lat, shop.place.lng)
    quote = place_quote(ctx, where, shop.product)
    rents = app_main.rent_table(ctx.tariff, ctx.state.rent).centres
    rent = rents.get(where.centre) if where.centre else None
    product = calculator.find(ctx.tariff.products, shop.product, "product")
    fields = {"business_class": "hawker" if where.centre else "shop", "product": shop.product}
    if where.centre:
        fields["centre"] = where.centre
    if where.postcode:
        fields["postcode"] = where.postcode
    ctx.actions.append(Action(type="start_signup", label="Start sign-up with these details",
                              url="/buy/?via=adviser", fields=fields))
    facts = product_facts(ctx.tariff)
    return {
        "product": product.label, "place": where.name, "region": where.region,
        "expected_full_loss_days_a_year": quote.expected_loss_days,
        "tiers": tier_rows(quote, where.who),
        "recommended_tier": rent.recommended_tier if rent else quote.tiers[0].tier,
        "why_recommended": (
            f"the hawker plan: a full bad day pays about "
            f"{round(100 * quote.tiers[0].daily_payout_sgd / rent.rent_per_day_sgd)}% of a day's rent "
            f"here (about S${rent.rent_per_day_sgd:.0f} a day)" if rent else "the lowest-cost tier"
        ),
        "triggers": trigger_levels(ctx.tariff),
        "cover_rules": [facts[k] for k in ("daily_amounts", "partial_days", "yearly_limit",
                                           "lockdown", "higher_tiers", "waiting_period")
                        if k in facts],
    }


def tool_explain_price(ctx: Context, centre: str | None = None, product: str | None = None,
                       tier: str | None = None, postcode: str | None = None) -> dict:
    """Why a cover costs what it does: the stations, the bad days and the price build-up."""
    policy = my_policy(ctx)
    where = (find_place(ctx, centre, postcode=postcode) if (centre or postcode)
             else policy_place(ctx, policy))
    if where is None:
        return {"error": "Tell me which hawker centre or the shop's postcode, or sign in so I "
                         "can use your cover."}
    product = product or (policy.product if policy else DEFAULT_PRODUCT)
    quote = place_quote(ctx, where, product)
    chosen = chosen_tier(quote, tier or (policy.tier if policy else DEFAULT_TIER))
    shares = calculator.find(ctx.tariff.tiers, chosen.tier, "tier").premium_shares
    assumed = {h.key: h.assumed_days_per_year for h in ctx.tariff.hazards
               if h.assumed_days_per_year is not None}
    local = {r.hazard: r for r in quote.local_risks}
    return {
        "place": where.name, "product": product, "tier": chosen.label,
        "expected_full_loss_days_a_year": quote.expected_loss_days,
        "by_hazard": [
            {"hazard": hazard, "full_loss_days_a_year": days,
             **({"priced_from": f"an assumed {assumed[hazard]:g} days a year"} if hazard in assumed
                else {"priced_from": "NEA's recorded readings at this place"}),
             **({"stations_read": local[hazard].stations,
                 "days_of_station_data": local[hazard].station_days} if hazard in local else {})}
            for hazard, days in quote.loss_day_parts.items()
        ],
        "expected_paid_days_a_year": chosen.expected_paid_days,
        "paid_days_a_year_up_to": paid_days_limit(chosen),
        "expected_payouts_share_of_premium_before_gst": (
            f"{shares.expected_payouts:.0%}" if shares else None
        ),
        "build_up_sgd_a_year": {
            **{step.key: step.amount_sgd for step in chosen.build_up},
            "yearly_premium": chosen.yearly_premium_sgd,
        },
        "monthly_premium_sgd": monthly(chosen.yearly_premium_sgd),
        "weekly_billed_sgd": chosen.weekly_premium_sgd,
        "how_it_is_priced": (
            "Yearly premium = expected paid days x the daily amount / the tier's payout share, "
            "plus GST. Expected paid days are the average, over the years replayed, of each "
            "year's full-loss days within the yearly limit, every day read as a payout reads it."
        ),
        "proof": proof_lines(chosen, where.who),
        "note": "No personal data goes into the price: only the place's NEA history and the product.",
    }


def tool_my_cover(ctx: Context) -> dict:
    """The signed-in owner's cover and their latest payouts."""
    from api import main as app_main

    policy = my_policy(ctx)
    if policy is None:
        return {"covered": False}
    with ctx.state.db.connect() as db:
        rows = db.execute(
            select(payouts).where(payouts.c.user_id == ctx.user.id)
            .order_by(payouts.c.loss_date.desc()).limit(8)
        ).mappings().all()
        bonus = app_main.haze_bonuses(db).get(policy.id)
    return {
        "covered": True, "tier": policy.tier_label, "product": policy.product,
        "place": policy_place(ctx, policy).name,
        "weekly_premium_sgd": policy.weekly_premium_sgd,
        "pays_for_a_day_with_no_sales_sgd": policy.daily_payout_sgd,
        "most_paid_days_a_year": policy.max_paid_days_per_year,
        "cover_pays_from": payout_flow.first_covered_day(policy.started_at).isoformat(),
        "severe_haze_payout_add_on": (
            {"pays_once_sgd": bonus["lump_sum_sgd"], "weekly_sgd": bonus["weekly_sgd"],
             "pays_from": bonus["starts_on"].isoformat()} if bonus else None
        ),
        "latest_payouts": [
            {"date": r["loss_date"].isoformat(), "status": r["status"],
             "amount_sgd": r["amount_cents"] / 100, "share_of_day_lost_pc": r["loss_percent"],
             "main_hazard": r["main_hazard"]}
            for r in rows
        ],
    }


def tool_why_paid(ctx: Context, day: str) -> dict:
    """Why the signed-in owner was or was not paid on one day."""
    policy = my_policy(ctx)
    if policy is None:
        return {"error": "Only a signed-in owner with cover has payouts to explain."}
    when = parse_day(day)
    if when is None:
        return {"error": f"I could not read the date '{day}'. Try 2026-10-18 or 'yesterday'."}
    with ctx.state.db.connect() as db:
        payout = db.execute(
            select(payouts).where(payouts.c.user_id == ctx.user.id, payouts.c.loss_date == when)
        ).mappings().first()
    covered_from = payout_flow.first_covered_day(policy.started_at)
    where = policy_place(ctx, policy)
    values, basis, source = readings_on(ctx, where, when)
    assessment = calculator.assess(
        ctx.tariff, policy.product, policy.tier, values, policy.daily_payout_sgd
    ) if values else None
    return {
        "date": when.isoformat(), "place": where.name, "readings": values,
        "how_each_reading_was_chosen": basis, "readings_source": source,
        "triggers": trigger_levels(ctx.tariff),
        "share_of_day_lost_pc": assessment.loss_percent if assessment else None,
        "payout_by_the_rule_sgd": assessment.payout_sgd if assessment else None,
        "in_waiting_period": when < covered_from, "cover_pays_from": covered_from.isoformat(),
        "payout_record": (
            {"status": payout["status"], "amount_sgd": payout["amount_cents"] / 100,
             "reason": payout["failure_reason"]} if payout else None
        ),
    }


def tool_weather_now(ctx: Context, centre: str | None = None, region: str | None = None,
                     postcode: str | None = None) -> dict:
    """Today's live readings at a place and the loss they would score."""
    policy = my_policy(ctx)
    where = (find_place(ctx, centre, region, postcode) if (centre or region or postcode)
             else policy_place(ctx, policy))
    if where is None:
        return {"error": "Name a hawker centre, a postcode or a region (north, south, east, "
                         "west, central)."}
    values, basis, source = readings_on(ctx, where, today())
    if not values:
        return {"error": source}
    product = policy.product if policy else DEFAULT_PRODUCT
    loss = calculator.assess(ctx.tariff, product, ctx.tariff.tiers[0].key, values).loss_percent
    return {"place": where.name, "readings": values, "readings_source": source,
            "triggers": trigger_levels(ctx.tariff), "share_of_day_lost_pc_so_far": loss}


def tool_ten_year_record(ctx: Context, centre: str | None = None, product: str | None = None,
                         tier: str | None = None, daily_sales_sgd: float = 500.0,
                         postcode: str | None = None) -> dict:
    """What this cover would have paid a business here, year by year, since 2017."""
    from api import main as app_main

    policy = my_policy(ctx)
    where = (find_place(ctx, centre, postcode=postcode) if (centre or postcode)
             else policy_place(ctx, policy))
    if where is None:
        return {"error": "Name the hawker centre or the shop's postcode."}
    if where.centre:
        place = {"centre": where.centre}
    elif where.whole_region:
        place = {"region": where.region}
    else:
        place = {"lat": where.lat, "lng": where.lng, "region": where.region}
    record = app_main.map_burn(
        ctx.request, ctx.tariff, **place,
        product=product or (policy.product if policy else DEFAULT_PRODUCT),
        tier=tier or (policy.tier if policy else DEFAULT_TIER), takings=daily_sales_sgd,
    )
    return {"place": where.name, "tier": record["tier_label"], "totals": record["totals"],
            "years": [{k: y[k] for k in ("year", "trigger_days", "paid_sgd", "est_lost_sgd")}
                      for y in record["years"]],
            "note": record["assumptions"]["note"]}


def tool_check_dispute(ctx: Context, day: str, what_happened: str, centre: str | None = None,
                       region: str | None = None) -> dict:
    """Check a challenge against the published readings and draft it for a human verifier."""
    when = parse_day(day)
    where = find_place(ctx, centre, region) or policy_place(ctx, my_policy(ctx))
    if when is None or where is None:
        return {"error": "I need the date and the hawker centre or region."}
    values, basis, source = readings_on(ctx, where, when)
    levels = {h.key: h.bands[0].at_least for h in ctx.tariff.hazards if h.key in HAZARDS}
    crossed = [h for h, level in levels.items() if values.get(h, 0) >= level]
    return {
        "date": when.isoformat(), "place": where.name, "readings": values,
        "how_each_reading_was_chosen": basis, "readings_source": source,
        "trigger_crossed": crossed,
        "draft_for_verifier": (
            f"Challenge for {when:%d %b %Y} at {where.name}. Owner says: {what_happened.strip()} "
            f"Published readings ({source}): {values}. Triggers crossed: {crossed or 'none'}. "
            "A challenge is about the reading or the classification, never the size of the loss; "
            "a human verifier decides."
        ),
    }


def tool_portfolio(ctx: Context) -> dict:
    """The insurer's book: policies in force, premium and daily payout exposure by region."""
    from api import main as app_main

    return app_main.insurer_portfolio(ctx.user, ctx.request)


def tool_what_if_day(ctx: Context, psi: float = 0, rain_mm: float = 0, heat_hours: float = 0,
                     flood: bool = False, region: str | None = None) -> dict:
    """What one day with these readings would pay across the book, by region."""
    day = {"haze": psi, "rain": rain_mm, "heat": heat_hours, "flood": 1.0 if flood else 0.0}
    with ctx.state.db.connect() as db:
        rows = db.execute(select(accounts.policies)).mappings().all()
    by_region: dict[str, dict] = {}
    for row in rows:
        if region and row["region"] != region.lower():
            continue
        paid = calculator.assess(
            ctx.tariff, row["product"], row["tier"], day, row["daily_payout_sgd"]
        ).payout_sgd
        entry = by_region.setdefault(row["region"], {"policies": 0, "payout_sgd": 0.0})
        entry["policies"] += 1
        entry["payout_sgd"] = round(entry["payout_sgd"] + paid, 2)
    cooked = calculator.assess(ctx.tariff, DEFAULT_PRODUCT, DEFAULT_TIER, day)
    stalls = sum(c["food_stalls"] for c in ctx.state.map_static["hawker_centres"]
                 if not region or c["region"] == region.lower())
    return {
        "readings": day, "book_by_region": by_region,
        "book_total_payout_sgd": round(sum(e["payout_sgd"] for e in by_region.values()), 2),
        "if_every_cooked_food_stall_held_tier_2": {
            "stalls": stalls, "share_of_day_lost_pc": cooked.loss_percent,
            "payout_sgd": round(cooked.payout_sgd * stalls, 2),
        },
    }


def tool_underwriting_queue(ctx: Context) -> dict:
    """Applications waiting for an underwriter, for a human to decide."""
    queue = underwriting.underwriter_queue(ctx.user, ctx.request)
    keep = ("id", "business_name", "name", "business_class", "centre", "tier", "status",
            "declined_details", "created_at")
    return {
        "waiting": [{k: str(a.get(k)) for k in keep if a.get(k) is not None}
                    for a in queue["waiting"][:10]],
        "waiting_count": len(queue["waiting"]),
        "note": "The assistant summarises; an underwriter decides each application.",
    }


HAZARD_SETTINGS = ("weight", "assumed_days_per_year")
TIER_LIMIT_SETTING = "yearly_limit_days"


def tool_tariff_change(ctx: Context, setting: str, value: float, hazard: str | None = None) -> dict:
    """What a tariff change would do to Tier 2 cooked-food prices in each region, priced on the
    replayed years as every quote is (main.region_quote). Saves nothing."""
    from api import main as app_main

    changed = ctx.tariff.model_copy(deep=True)
    if setting in HAZARD_SETTINGS:
        if hazard is None:
            return {"error": "Which hazard: " + ", ".join(h.key for h in ctx.tariff.hazards) + "?"}
        setattr(calculator.find(changed.hazards, hazard, "hazard"), setting, value)
    elif setting == TIER_LIMIT_SETTING:
        for tier in changed.tiers:
            tier.max_paid_days_per_year = int(value)
    else:
        return {"error": "I can test a hazard's weight or assumed_days_per_year, or every "
                         f"tier's {TIER_LIMIT_SETTING}."}
    changed = Tariff.model_validate(changed.model_dump())
    rows = []
    for region in ctx.state.regions:
        before = chosen_tier(
            app_main.region_quote(ctx.request, ctx.tariff, DEFAULT_PRODUCT, region), DEFAULT_TIER
        )
        after = chosen_tier(
            app_main.region_quote(ctx.request, changed, DEFAULT_PRODUCT, region), DEFAULT_TIER
        )
        rows.append({"region": region,
                     "monthly_now_sgd": monthly(before.yearly_premium_sgd),
                     "monthly_after_sgd": monthly(after.yearly_premium_sgd),
                     "yearly_now_sgd": before.yearly_premium_sgd,
                     "yearly_after_sgd": after.yearly_premium_sgd})
    return {"change": f"{hazard + ' ' if hazard else ''}{setting} -> {value:g}",
            "tier_2_cooked_food": rows,
            "note": "Nothing is saved. An admin applies changes in the tariff desk (/admin/)."}


def tool_fill_buy_form(ctx: Context, fields: dict) -> dict:
    """Put what the person said into the sign-up form for them to check."""
    clean = {k: str(v) for k, v in fields.items() if k in FORM_FIELDS and str(v).strip()}
    if not clean:
        return {"error": f"No usable fields. I can fill: {', '.join(FORM_FIELDS)}."}
    ctx.actions.append(Action(type="fill_form", fields=clean))
    return {"filled": sorted(clean), "note": "Ask the person to check every filled field."}


@dataclass(frozen=True)
class Tool:
    run: Callable[..., dict]
    description: str
    parameters: dict
    roles: tuple[str, ...] = ("visitor", "sme", "insurer")
    pages: tuple[str, ...] | None = None


def params(required: list[str] | None = None, **props: dict) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


STRING, NUMBER = {"type": "string"}, {"type": "number"}
TOOLS: dict[str, Tool] = {
    "describe_business": Tool(
        tool_describe_business,
        "Read an owner's description of their business (what they sell, and the hawker centre "
        "or the shop's 6-digit postcode) and return the matching product, the place and every "
        "tier as POST /api/quote prices it there: monthly price, what it pays for a day with no "
        "sales, the yearly day limit, proof lines and the optional severe haze payout.",
        params(["description"], description=STRING, postcode=STRING)),
    "explain_price": Tool(
        tool_explain_price,
        "Explain why cover at a hawker centre or a shop's postcode costs what it does: stations "
        "read, full-loss days a year, expected paid days within the yearly limit and the "
        "premium in its five parts plus GST. Defaults to the signed-in owner's own cover.",
        params(centre=STRING, product=STRING, tier=STRING, postcode=STRING)),
    "my_cover": Tool(tool_my_cover, "The signed-in owner's cover, its severe haze payout add-on "
                     "if any, and latest payouts.", params(), roles=("sme",)),
    "why_paid": Tool(
        tool_why_paid,
        "Why the signed-in owner was or was not paid on a day: readings, triggers, payout record.",
        params(["day"], day={"type": "string", "description": "YYYY-MM-DD, today or yesterday"}),
        roles=("sme",)),
    "weather_now": Tool(
        tool_weather_now,
        "Today's live NEA readings at a hawker centre, postcode or region, the trigger levels "
        "and the share of the day lost so far. These are readings, not a forecast.",
        params(centre=STRING, region=STRING, postcode=STRING)),
    "ten_year_record": Tool(
        tool_ten_year_record,
        "What this cover would have paid a business at a hawker centre or a shop's postcode "
        "each year since 2017, replayed on NEA's readings, against its estimated losses at its "
        "daily sales.",
        params(centre=STRING, product=STRING, tier=STRING, daily_sales_sgd=NUMBER,
               postcode=STRING)),
    "check_dispute": Tool(
        tool_check_dispute,
        "Check someone's challenge to a payout or non-payout against the published readings for "
        "that day and place, and draft it for a human verifier.",
        params(["day", "what_happened"], day=STRING, what_happened=STRING, centre=STRING,
               region=STRING)),
    "portfolio": Tool(tool_portfolio, "The insurer's book: policies, premium, exposure.", params(),
                      roles=("insurer",)),
    "what_if_day": Tool(
        tool_what_if_day,
        "What one day with given readings would pay across the insurer's book and the market.",
        params(psi=NUMBER, rain_mm=NUMBER, heat_hours=NUMBER, flood={"type": "boolean"},
               region=STRING),
        roles=("insurer",)),
    "underwriting_queue": Tool(tool_underwriting_queue,
                               "Applications waiting for an underwriter, to summarise.", params(),
                               roles=("insurer",)),
    "tariff_change": Tool(
        tool_tariff_change,
        "Preview a tariff change on Tier 2 cooked-food monthly and yearly prices by region, "
        "priced on the replayed years: a hazard's weight (a share like 0.6) or "
        "assumed_days_per_year (closure), or every tier's yearly_limit_days. Saves nothing.",
        params(["setting", "value"], setting=STRING, value=NUMBER, hazard=STRING),
        roles=("insurer",)),
    "fill_buy_form": Tool(
        tool_fill_buy_form,
        "Fill the sign-up form with details the person has said. Field names: "
        + ", ".join(FORM_FIELDS) + ". business_class is hawker or shop; product is a product "
        "key; sms_language is en, zh, ms or ta; term_months is 12 or 24.",
        params(["fields"], fields={"type": "object"}),
        pages=("buy",)),
}


def tools_for(ctx: Context) -> dict[str, Tool]:
    return {name: tool for name, tool in TOOLS.items()
            if ctx.role in tool.roles and (tool.pages is None or ctx.page in tool.pages)}


def run_tool(ctx: Context, name: str, arguments: dict) -> dict:
    tool = tools_for(ctx).get(name)
    if tool is None:
        return {"error": f"{name} is not available here."}
    try:
        return tool.run(ctx, **arguments)
    except (TypeError, ValueError, LookupError, calculator.UnknownKey, HTTPException) as error:
        return {"error": str(getattr(error, "detail", error))}


# ---------- the model ----------


def system_prompt(ctx: Context) -> str:
    products = ", ".join(f"{p.key} ({p.label})" for p in ctx.tariff.products)
    facts = "\n".join(f"- {fact}" for fact in product_facts(ctx.tariff).values())
    who = {"sme": f"a signed-in business owner ({ctx.user.name if ctx.user else ''})",
           "insurer": "an Income underwriter", "visitor": "a visitor who has not signed in"}[ctx.role]
    return (
        "You are Payung's assistant. Payung is parametric climate-income cover for Singapore "
        "hawker stalls and small shops, offered by Income Insurance. When NEA's published "
        "readings near a business cross a trigger (haze, heavy rain, heat stress, a PUB flood "
        "alert), or a lockdown or closure order stops trading, it pays the share of a fixed "
        "daily amount the day lost, by PayNow, with no claim form. You are talking to "
        f"{who}, on the {ctx.page} page. Today is {today():%d %b %Y}.\n"
        f"The product (from the live tariff):\n{facts}\n"
        "Rules:\n"
        "- Every number you state must come from a tool result in this conversation. Never "
        "estimate a price, payout, reading or date yourself.\n"
        "- You never set a price or decide a payout: the tariff and NEA's readings do. Say so "
        "if asked to change one.\n"
        "- Be honest about basis risk: a business can lose sales and receive nothing when the "
        "readings near it stay below the triggers.\n"
        f"- Always reply in {LANGUAGE_NAMES[ctx.reply_language]}, whatever language the person "
        "writes or speaks in, and translate tool results into it. Keep numbers, S$ amounts, "
        "dates and hawker centre names as they are. Use short sentences and plain words; many "
        "owners are over 60. Keep a reply under 120 words: lists of tiers as short lines. No emoji.\n"
        "- Read places generously: 'the Indian market' or 'Little India market' is Tekka "
        "Centre; pass the real centre name to tools.\n"
        "- When someone asks for the most cover, show the highest tier and what it pays, and "
        "say the top tiers suit businesses with higher takings.\n"
        "- When someone describes their business, call describe_business and lay out the tiers "
        "as choices with the monthly price and what each pays for a day with no sales. Use a "
        "tier's proof lines as worded; never call a past year's payout a promise.\n"
        "- Never say a model predicts or forecasts bad days.\n"
        "- On the buy page, when the person tells you their details, call fill_buy_form with "
        "only what they said, then ask them to check the form.\n"
        "- No medical, legal or investment advice. Health and injury are not covered.\n"
        f"Products: {products}.\n/no_think"
    )


def openai_tools(ctx: Context) -> list[dict]:
    return [{"type": "function",
             "function": {"name": name, "description": tool.description,
                          "parameters": tool.parameters}}
            for name, tool in tools_for(ctx).items()]


MODELS = (
    (DEEPSEEK_KEY_NAME, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL, "api.deepseek.com"),
    (kyc.XAI_KEY_NAME, kyc.XAI_MODEL, kyc.XAI_BASE_URL, "api.x.ai"),
    (kyc.OPENAI_KEY_NAME, kyc.OPENAI_MODEL, None, "api.openai.com"),
)


def local_model_ready() -> bool:
    """True when Ollama answers on this machine and has OLLAMA_MODEL."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=1) as response:
            names = {m["name"] for m in json.load(response).get("models", [])}
    except (OSError, ValueError):
        return False
    return OLLAMA_MODEL in names or f"{OLLAMA_MODEL}:latest" in names


def model_client() -> tuple[openai.OpenAI, str, bool] | None:
    """The model to ask, its name, and whether it runs on this machine."""
    for key_name, model, base_url, _host in MODELS:
        key = kyc.api_key(key_name)
        if key:
            return openai.OpenAI(api_key=key, base_url=base_url, timeout=40), model, False
    if local_model_ready():
        local = openai.OpenAI(api_key="ollama", base_url=f"{OLLAMA_URL}/v1", timeout=180)
        return local, OLLAMA_MODEL, True
    return None


def without_thinking(text: str) -> str:
    """Drop a reasoning block some local models put before the answer."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def ask_model(ctx: Context, turns: list[Turn]) -> str | None:
    """The model's reply after it has run its tools, or None to fall back to keywords."""
    chosen = model_client()
    if chosen is None:
        return None
    client, model, local = chosen
    translating = local and ctx.language in TRANSLATED_LOCALLY and translate.installed()
    ctx.reply_language = "en" if translating else ctx.language
    messages: list[dict] = [{"role": "system", "content": system_prompt(ctx)}]
    messages += [{"role": t.role, "content": t.content} for t in turns[-MAX_TURNS_KEPT:]]
    tools = openai_tools(ctx)
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model=model, messages=messages, tools=tools, temperature=0.2,
                max_tokens=MAX_REPLY_TOKENS,
            )
            message = response.choices[0].message
            if not message.tool_calls:
                return without_thinking(message.content or "")
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                result = run_tool(ctx, call.function.name, arguments)
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, default=str)})
    except openai.OpenAIError as error:
        log.warning("Assistant model call failed: %s", type(error).__name__)
        return None
    return None


# ---------- keywords, when there is no model ----------


def money(value: float) -> str:
    return f"S${value:,.2f}"


def plain(values: dict[str, float]) -> str:
    return (f"PSI {values.get('haze', 0):g}, {values.get('rain', 0):g} mm in the wettest work "
            f"hour, {values.get('heat', 0):g} hours of heat stress")


# Questions about the product itself, answered from product_facts.
FACT_KEYWORDS = (
    (("lockdown", "closure", "circuit breaker"), ("yearly_limit", "lockdown")),
    (("severe haze", "haze payout", "add-on", "addon", "lump sum"), ("severe_haze_payout",)),
    (("wait",), ("waiting_period",)),
    (("forecast", "predict"), ("forecast",)),
    (("on hold",), ("stations_on_hold",)),
)


def facts_reply(ctx: Context, low: str) -> str | None:
    facts = product_facts(ctx.tariff)
    for words, keys in FACT_KEYWORDS:
        if any(w in low for w in words):
            found = [facts[k] for k in keys if k in facts]
            if found:
                return " ".join(found)
    return None


def cover_reply(ctx: Context, r: dict, low: str) -> str:
    """The tiers of describe_business as short choices, with the yearly limit and the add-on."""
    lines = "; ".join(f"{t['label']} {money(t['monthly_premium_sgd'])}/month, pays "
                      f"{amount(t['pays_for_a_day_with_no_sales_sgd'])} for a day with no sales"
                      for t in r["tiers"])
    suggested = next(t for t in r["tiers"] if t["tier"] == r["recommended_tier"])
    facts = product_facts(ctx.tariff)
    reply = (f"{r['product']} at {r['place']}: {lines}. {facts['partial_days']} "
             f"{facts['yearly_limit']} I'd suggest {suggested['label']}, {r['why_recommended']}.")
    if bonus := suggested["severe_haze_payout_add_on"]:
        reply += (f" Optional severe haze payout: {money(bonus['monthly_sgd'])}/month more, pays "
                  f"{amount(bonus['pays_once_sgd'])} once if there are {bonus['pays_when']}.")
        if not bonus["can_be_added_now"]:
            reply += " It cannot be added this month."
    if re.search(r"most|max|highest|best", low):
        top = r["tiers"][-1]
        reply += (f" The most cover is {top['label']}: "
                  f"{amount(top['pays_for_a_day_with_no_sales_sgd'])} for a day with no sales and up to {amount(top['most_paid_in_a_year_sgd'])} a "
                  f"year, for {money(top['monthly_premium_sgd'])} a month. {facts['higher_tiers']}")
    return reply


def rules_reply(ctx: Context, text: str) -> str:
    """Pick a tool by keywords and answer from a template. English only."""
    low = text.lower()
    day_match = re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2} [a-z]{3,9}(?: \d{4})?|today|yesterday", low)
    day = day_match.group(0) if day_match else None
    named = kyc.match_place(text, ctx.state.places)
    centre = named.name if named else None
    postcode = next(iter(POSTCODE_IN_TEXT.findall(text)), None)

    if ctx.page == "buy" and re.search(r"\bmy name is\b|\bphone\b|\bemail\b|\bfill\b", low):
        fields = {}
        if m := re.search(r"my name is ([a-z][a-z .'-]{1,60}?)(?:,|\.| and |$)", low):
            fields["name"] = m.group(1).title()
        if m := re.search(r"(?:\+65\s*)?([689]\d{3})\s*-?(\d{4})", text):
            fields["phone"] = m.group(1) + m.group(2)
        if m := re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
            fields["email"] = m.group(0)
        result = tool_fill_buy_form(ctx, fields) if fields else {"error": "none"}
        if "filled" in result:
            return f"I filled in {', '.join(result['filled'])}. Please check them in the form."
    if any(w in low for w in ("insurer", "exposure", "what if", "book")) and ctx.role == "insurer":
        psi = re.search(r"psi\s*(\d+)", low)
        rain = re.search(r"(\d+)\s*mm", low)
        heat = re.search(r"(\d+)\s*h(?:ou)?rs?", low)
        r = tool_what_if_day(ctx, psi=float(psi.group(1)) if psi else 0,
                             rain_mm=float(rain.group(1)) if rain else 0,
                             heat_hours=float(heat.group(1)) if heat else 0)
        market = r["if_every_cooked_food_stall_held_tier_2"]
        return (f"A day with {r['readings']} would pay {money(r['book_total_payout_sgd'])} across "
                f"your book. If all {market['stalls']:,} cooked-food stalls held Tier 2, it would "
                f"pay {money(market['payout_sgd'])} ({market['share_of_day_lost_pc']}% of a day).")
    if ctx.role == "insurer" and any(w in low for w in ("queue", "application", "underwrit")):
        r = tool_underwriting_queue(ctx)
        names = ", ".join(a.get("business_name", a.get("name", "?")) for a in r["waiting"]) or "none"
        return f"{r['waiting_count']} applications wait for an underwriter: {names}."
    if any(w in low for w in ("why", "paid", "payout", "pay me", "didn't get", "没有", "bayar")) and \
            ctx.role == "sme" and day:
        r = tool_why_paid(ctx, day)
        if "error" in r:
            return r["error"]
        if r["in_waiting_period"]:
            return f"Your cover pays from {r['cover_pays_from']}, so {r['date']} was in the waiting period."
        verdict = (f"the readings gave {r['share_of_day_lost_pc']}% of a day lost, so the rule pays "
                   f"{money(r['payout_by_the_rule_sgd'])}"
                   if r["payout_by_the_rule_sgd"] else "no reading reached a trigger, so nothing is paid")
        return (f"On {r['date']} at {r['place']}, {r['readings_source']} were {plain(r['readings'])}: "
                f"{verdict}. Triggers: haze {r['triggers']['haze']}; rain {r['triggers']['rain']}; "
                f"heat {r['triggers']['heat']}.")
    if fact := facts_reply(ctx, low):
        return fact
    if any(w in low for w in ("why", "cost", "price", "expensive", "premium", "贵", "mahal")):
        r = tool_explain_price(ctx, centre, postcode=postcode)
        if "error" in r:
            return r["error"]
        parts = "; ".join(f"{h['hazard']} {h['full_loss_days_a_year']} days" for h in r["by_hazard"])
        b = r["build_up_sgd_a_year"]
        return (f"{r['tier']} at {r['place']} costs {money(r['monthly_premium_sgd'])} a month "
                f"({money(b['yearly_premium'])} a year, billed {money(r['weekly_billed_sgd'])} a "
                f"week). Its NEA readings give {r['expected_full_loss_days_a_year']} full bad days "
                f"a year ({parts}), and it expects to pay {r['expected_paid_days_a_year']} days a "
                f"year within its {r['paid_days_a_year_up_to']}-day limit. Expected payouts "
                f"{money(b['expected_payouts'])} a year are "
                f"{r['expected_payouts_share_of_premium_before_gst']} of the premium before GST; "
                "reinsurance, running costs, profit and GST make the rest. No personal data goes "
                "into the price.")
    if any(w in low for w in ("10 year", "ten year", "would have", "history", "past years")):
        r = tool_ten_year_record(ctx, centre, postcode=postcode)
        if "error" in r:
            return r["error"]
        t = r["totals"]
        return (f"At {r['place']} on {r['tier']}, from {t['from_year']} to {t['to_year']} this "
                f"cover would have paid {money(t['paid_sgd'])} over {t['trigger_days']} bad days.")
    describes_business = re.search(
        r"\b(i sell|i have a|i run|my (?:stall|shop|business))\b|卖|jual|கடை", low)
    wants_cover = any(w in low for w in ("plan", "cover", "tier", "coverage")) and \
        any(w in low for w in ("shop", "stall", "sell"))
    if describes_business or wants_cover:
        r = tool_describe_business(ctx, text)
        if "missing" in r:
            return (f"I understood: {r['understood']}. Please also tell me "
                    f"{' and '.join(r['missing'])}.")
        return cover_reply(ctx, r, low)
    if any(w in low for w in ("weather", "today", "haze", "rain", "psi", "hot", "heat")):
        r = tool_weather_now(ctx, centre, postcode=postcode)
        if "error" in r:
            return r["error"]
        return (f"Right now at {r['place']}: {plain(r['readings'])} ({r['readings_source']}). That is "
                f"{r['share_of_day_lost_pc_so_far']}% of a day lost so far.")
    if ctx.role == "sme" and any(w in low for w in ("my cover", "my policy", "my plan")):
        r = tool_my_cover(ctx)
        if not r["covered"]:
            return "You have no cover yet. Tell me what you sell and where, and I'll show the options."
        reply = (f"You hold {r['tier']} at {r['place']}: {money(r['weekly_premium_sgd'])} a week, "
                 f"{amount(r['pays_for_a_day_with_no_sales_sgd'])} for a day with no sales, up to "
                 f"{r['most_paid_days_a_year']} days a year, paying from {r['cover_pays_from']}.")
        if bonus := r["severe_haze_payout_add_on"]:
            reply += (f" Your severe haze payout pays {amount(bonus['pays_once_sgd'])} once, from "
                      f"{bonus['pays_from']}.")
        return reply
    if any(w in low for w in ("sell", "stall", "shop", "hawker", "卖", "jual", "கடை")):
        r = tool_describe_business(ctx, text)
        if "missing" in r:
            return f"I understood: {r['understood']}. Please also tell me {' and '.join(r['missing'])}."
        return cover_reply(ctx, r, low)
    return ("I can explain your price, tell you why a day did or didn't pay, show today's "
            "weather readings, or find cover for your business. Try: \"I sell chicken rice at "
            "Maxwell Food Centre\".")


@router.post("/chat")
def chat(body: ChatRequest, request: Request) -> ChatReply:
    """One reply to a conversation, grounded in the platform's own numbers."""
    ctx = Context(request, store.latest(request.app.state.db).tariff, body.page,
                  current_user_or_none(request), body.language)
    reply = ask_model(ctx, body.messages)
    source = "llm"
    if reply is None:
        ctx.actions.clear()
        ctx.reply_language = "en"
        last = next(t.content for t in reversed(body.messages) if t.role == "user")
        reply, source = rules_reply(ctx, last), "rules"
    if ctx.reply_language != ctx.language and translate.installed():
        reply = translate.translate(reply, ctx.language)
    return ChatReply(reply=reply, actions=ctx.actions, source=source)
