"""Loss score, payout and premium: pure functions of a tariff and the hazard history.

A day's loss is the share of a normal day's sales the seller loses, from 0 (no loss) to 1
(no sales at all). Each tier pays its daily payout times that share, up to its yearly limit.

The premium is priced on the payout rule. Every recorded day at the customer's place (a Replay,
read through api/readings.py as a payout reads it) is scored with the tariff, the hazards
combined as a payout combines them. A year's loss-days are the sum of its days' losses,
annualised for a part year; on days a hazard's NEA feed had not started (rain before Dec 2016,
heat before 2025) the hazard adds its average daily loss over the days its feed ran. A tier's
expected paid days are the average over the years of min(year loss-days, its yearly limit).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import TypeVar
from zoneinfo import ZoneInfo

import numpy as np

from api.models import (
    Assessment,
    CentreRent,
    Hazard,
    HazardLoss,
    HazeBonus,
    HazeBonusQuote,
    LocalRisk,
    PremiumShares,
    PremiumStep,
    Pricing,
    Product,
    Quote,
    Rent,
    RentClass,
    Tariff,
    Tier,
    TierProof,
    TierQuote,
)

DAYS_PER_YEAR = 365.25
# The price per day is a calendar year's premium over a calendar year's days.
PRICE_DAYS_PER_YEAR = 365
WEEKS_PER_YEAR = 52
EARTH_RADIUS_KM = 6371.0
# The proof replays the years with rain recorded all year: the rain feed starts on 2 Dec 2016.
FIRST_FULL_YEAR = 2017
PROOF_YEAR = 2026
HAZE_YEAR = 2015
HAZE = "haze"
SINGAPORE = ZoneInfo("Asia/Singapore")


@dataclass(frozen=True)
class Replay:
    """A place's readings on every recorded day, read as a payout reads them (api/readings.py).

    A hazard a payout would wait for reads 0. fed is True on the days the hazard's NEA feed ran.
    """

    days: np.ndarray  # datetime64[D], ascending
    readings: dict[str, np.ndarray]
    fed: dict[str, np.ndarray]


@dataclass(frozen=True)
class ReplayLosses:
    """A place's loss-days for one product, per year and per hazard, and its daily losses."""

    years: np.ndarray
    loss_days: np.ndarray  # per year, annualised, unfed days at the hazard's average
    parts: dict[str, float]  # each hazard's average loss-days a year
    hazard_years: dict[str, dict[int, float]]  # each replayed hazard's loss-days per year
    fed_days: dict[str, int]
    day_years: np.ndarray
    day_loss: np.ndarray  # each recorded day's loss, as a payout scores it


Keyed = TypeVar("Keyed", Hazard, Product, Tier)
Severity = TypeVar("Severity", float, np.ndarray)


class UnknownKey(LookupError):
    pass


class MissingHistory(ValueError):
    pass


def find(items: list[Keyed], key: str, kind: str) -> Keyed:
    for item in items:
        if item.key == key:
            return item
    raise UnknownKey(f"Unknown {kind}: {key}")


def severities(hazard: Hazard, readings: np.ndarray) -> np.ndarray:
    """Severity of the highest band each reading reaches, and 0 below the first band."""
    levels = np.array([band.at_least for band in hazard.bands])
    values = np.array([0.0] + [band.severity for band in hazard.bands])
    return values[np.searchsorted(levels, readings, side="right")]


def product_factor(product: Product) -> float:
    """Share of a bad day's normal sales the seller loses for good, per S$1 of those sales.

    Two parts, as insurers split them: the gross profit on sales that never come back (business
    interruption cover), and the cost of stock that spoils before it can be sold (deterioration
    of stock cover). Stock spoils when it waits longer for a sale than its shelf life. A product
    with a shelf life of 0 holds no stock, so nothing spoils.
    """
    if product.shelf_life_days == 0:
        wasted = 0.0
    else:
        wasted = min(1.0, product.restock_every_days / product.shelf_life_days)
    lost_profit = product.gross_margin * (1 - product.recovered_share)
    spoiled_stock = wasted * (1 - product.gross_margin)
    return product.demand_sensitivity * (lost_profit + spoiled_stock)


def hazard_loss(hazard: Hazard, severity: Severity, factor: float) -> Severity:
    return hazard.weight * severity * (factor if hazard.scaled_by_product else 1.0)


def as_percent(share: float) -> float:
    return round(share * 100, 1)


def assess(
    tariff: Tariff,
    product_key: str,
    tier_key: str,
    readings: dict[str, float],
    daily_payout_sgd: float | None = None,
) -> Assessment:
    """One day's loss and payout. daily_payout_sgd is the amount a policy was sold with; it
    defaults to the tier's amount in this tariff, so a tariff change never alters a policy."""
    product = find(tariff.products, product_key, "product")
    tier = find(tariff.tiers, tier_key, "tier")
    daily = tier.daily_payout_sgd if daily_payout_sgd is None else daily_payout_sgd
    factor = product_factor(product)
    hazards = []
    for key, reading in readings.items():
        hazard = find(tariff.hazards, key, "hazard")
        severity = float(severities(hazard, np.array([reading]))[0])
        hazards.append((key, reading, severity, hazard_loss(hazard, severity, factor)))
    # Hazards count as independent causes of lost sales, so together they never pass 100%.
    day_loss = 1 - math.prod(1 - loss for *_, loss in hazards)
    return Assessment(
        tier=tier.key,
        loss_percent=as_percent(day_loss),
        payout_sgd=round(day_loss * daily, 2),
        hazards=[
            HazardLoss(
                hazard=key, reading=reading, severity=severity, loss_percent=as_percent(loss)
            )
            for key, reading, severity, loss in hazards
        ],
    )


def year_of(days: np.ndarray) -> np.ndarray:
    return days.astype("datetime64[Y]").astype(int) + 1970


def replay_losses(tariff: Tariff, product: Product, replay: Replay) -> ReplayLosses:
    """Score every recorded day at a place with the tariff, and sum the days into years.

    A hazard with assumed days a year adds them at its top band to every year. Raises
    MissingHistory for a hazard with neither assumed days nor a single recorded day.
    """
    factor = product_factor(product)
    day_years = year_of(replay.days)
    years, year_index, days_in_year = np.unique(
        day_years, return_inverse=True, return_counts=True
    )

    def per_year(values: np.ndarray) -> np.ndarray:
        return np.bincount(year_index, weights=values, minlength=len(years))

    no_loss = np.ones(len(replay.days))
    unfed_loss_days = np.zeros(len(years))
    assumed_loss_days = 0.0
    parts: dict[str, float] = {}
    hazard_years: dict[str, dict[int, float]] = {}
    fed_days: dict[str, int] = {}
    for hazard in tariff.hazards:
        if hazard.assumed_days_per_year is not None:
            top = hazard.bands[-1].severity
            parts[hazard.key] = hazard.assumed_days_per_year * hazard_loss(hazard, top, factor)
            assumed_loss_days += parts[hazard.key]
            continue
        fed = replay.fed.get(hazard.key)
        if fed is None or not fed.any():
            raise MissingHistory(f"{hazard.label} has no NEA history. Set its assumed days a year.")
        loss = hazard_loss(hazard, severities(hazard, replay.readings[hazard.key]), factor) * fed
        no_loss *= 1 - loss
        parts[hazard.key] = DAYS_PER_YEAR * float(loss[fed].mean())
        unfed_loss_days += per_year(~fed) * parts[hazard.key] / DAYS_PER_YEAR
        fed_in_year = per_year(fed)
        recorded = per_year(loss) * DAYS_PER_YEAR / np.maximum(fed_in_year, 1)
        hazard_years[hazard.key] = {
            int(year): float(days) if fed_count else parts[hazard.key]
            for year, days, fed_count in zip(years, recorded, fed_in_year, strict=True)
        }
        fed_days[hazard.key] = int(fed.sum())
    day_loss = 1 - no_loss
    recorded_loss_days = per_year(day_loss) + unfed_loss_days
    loss_days = recorded_loss_days * DAYS_PER_YEAR / days_in_year + assumed_loss_days
    return ReplayLosses(
        years=years, loss_days=loss_days, parts=parts, hazard_years=hazard_years,
        fed_days=fed_days, day_years=day_years, day_loss=day_loss,
    )


def shares_from_loads(pricing: Pricing) -> PremiumShares:
    """The five shares of the premium before GST that the Pricing loads give: the rare-event
    load buys the reinsurance for haze years, the uncertainty load is the profit and risk
    margin, and the running costs split into management and distribution."""
    payouts = (1 - pricing.expense_ratio) / (
        1 + pricing.uncertainty_load + pricing.catastrophe_load
    )
    return PremiumShares(
        expected_payouts=payouts,
        reinsurance=payouts * pricing.catastrophe_load,
        management=pricing.expense_ratio - pricing.distribution_expense_ratio,
        distribution=pricing.distribution_expense_ratio,
        profit=payouts * pricing.uncertainty_load,
    )


def yearly_premium(
    risk_cost: float, pricing: Pricing, shares: PremiumShares | None = None
) -> float:
    """Expected payouts over their share of the premium before GST, plus GST. Without a tier's
    own shares, the Pricing loads set the share."""
    if shares is None:
        loaded = risk_cost * (1 + pricing.uncertainty_load + pricing.catastrophe_load)
        return loaded / (1 - pricing.expense_ratio) * (1 + pricing.gst_rate)
    return risk_cost / shares.expected_payouts * (1 + pricing.gst_rate)


def premium_build_up(
    risk_cost: float, pricing: Pricing, shares: PremiumShares | None = None
) -> list[PremiumStep]:
    """The yearly premium in the insurer's five parts, then GST, each as money.

    Each part is its share of the premium before GST, the tier's own shares or else those of
    the Pricing loads. Each part is rounded to the cent, and GST takes the rounding left over,
    so the parts add up to the rounded yearly premium exactly.
    """
    split = shares or shares_from_loads(pricing)
    premium = yearly_premium(risk_cost, pricing, shares)
    before_gst = premium / (1 + pricing.gst_rate)
    steps = [
        ("expected_payouts", "Expected payouts to customers", risk_cost),
        ("reinsurance", "Reinsurance for haze years", before_gst * split.reinsurance),
        ("management", "Management expenses", before_gst * split.management),
        ("distribution", "Selling and distribution", before_gst * split.distribution),
        ("profit", "Expected profit and risk margin", before_gst * split.profit),
        ("gst", f"GST, {pricing.gst_rate:.0%}", before_gst * pricing.gst_rate),
    ]
    rounded = [round(amount, 2) for _, _, amount in steps[:-1]]
    rounded.append(round(round(premium, 2) - sum(rounded), 2))
    return [PremiumStep(key=key, label=label, amount_sgd=amount)
            for (key, label, _), amount in zip(steps, rounded, strict=True)]


def paid_years(losses: ReplayLosses, tier: Tier) -> dict[int, tuple[float, int]]:
    """What the tier would have paid each year, and on how many days, paying each day as a
    payout does (to the cent) until the yearly limit is reached."""
    limit_sgd = tier.daily_payout_sgd * tier.max_paid_days_per_year
    payouts = np.round(losses.day_loss * tier.daily_payout_sgd, 2)
    paid = {}
    for year in losses.years:
        first, last = np.searchsorted(losses.day_years, [year, year + 1])
        in_year = payouts[first:last]
        before = np.cumsum(in_year) - in_year
        paid_days = int(((in_year > 0) & (before < limit_sgd)).sum())
        paid[int(year)] = (min(float(in_year.sum()), limit_sgd), paid_days)
    return paid


def tier_proof(
    tier: Tier, losses: ReplayLosses, risk_cost: float, premium: float
) -> TierProof | None:
    """The four proof numbers at the customer's place. None when no replay year is complete."""
    paid = paid_years(losses, tier)
    latest = int(losses.years[-1])
    replayed = [year for year in paid if year >= FIRST_FULL_YEAR]
    full = [year for year in replayed if year < latest]
    if not full:
        return None
    other_hazards = sum(days for key, days in losses.parts.items() if key != HAZE)
    haze_years = losses.hazard_years.get(HAZE, {})
    haze_2015 = haze_years.get(HAZE_YEAR, losses.parts.get(HAZE, 0.0))
    limit_days = tier.max_paid_days_per_year
    return TierProof(
        years_replayed=len(replayed),
        years_paid=sum(paid[year][0] > 0 for year in replayed),
        payout_days_per_year=round(float(np.mean([paid[year][1] for year in full])), 1),
        typical_year_paid_sgd=round(float(np.median([paid[year][0] for year in full])), 2),
        paid_2026_sgd=round(paid.get(PROOF_YEAR, (0.0, 0))[0], 2),
        haze_2015_like_sgd=round(
            min(haze_2015 + other_hazards, limit_days) * tier.daily_payout_sgd, 2
        ),
        payback_share=round(risk_cost / premium, 3) if premium > 0 else 0.0,
    )


def not_offered_reason(tariff: Tariff, tier: Tier, yearly_premium_sgd: float) -> str | None:
    """Why a tier is not offered at a place, or None when it is.

    A tier is never offered where its yearly premium is at or above the most it can pay in a
    year. A tier with premium shares is also not offered where its premium is more than
    refer_above_limit_share of that limit; a tier without them, as every tier of a tariff saved
    before the shares, keeps only the first rule. The premium comes from the place's weather
    history alone, so the reason names it and nothing about the customer.
    """
    limit_sgd = tier.daily_payout_sgd * tier.max_paid_days_per_year
    share = tariff.pricing.refer_above_limit_share
    if yearly_premium_sgd >= limit_sgd:
        cap = "as much as or more than"
    elif tier.premium_shares is not None and yearly_premium_sgd > share * limit_sgd:
        cap = f"more than {share:.0%} of"
    else:
        return None
    return (
        f"{tier.label} is not offered here. The weather recorded here (NEA haze, rain and heat "
        f"readings) prices it at S${yearly_premium_sgd:,.2f} a year, {cap} the "
        f"S${limit_sgd:,.2f} it can pay in a year. At that price it gives too little back for what "
        "it costs. The price comes from the place's weather history, never from the business or "
        "its owner"
    )


def on_sale(bonus: HazeBonus, today: date) -> bool:
    return today.month not in bonus.no_sale_months


def haze_years(bonus: HazeBonus, replay: Replay) -> list[int]:
    """Calendar years of the replay with at least trigger_days at trigger_psi or more."""
    unhealthy = (replay.readings[HAZE] >= bonus.trigger_psi) & replay.fed[HAZE]
    years, counts = np.unique(year_of(replay.days[unhealthy]), return_counts=True)
    return [int(year) for year, days in zip(years, counts, strict=True)
            if days >= bonus.trigger_days]


def haze_bonus_build_up(
    yearly_sgd: float, bonus: HazeBonus, pricing: Pricing, shares: PremiumShares | None
) -> list[PremiumStep]:
    """The add-on's price: payout_share as payouts, the rest in the tier's own proportions of
    reinsurance, management, distribution and profit, then GST, which takes the leftover cent."""
    split = shares or shares_from_loads(pricing)
    before_gst = yearly_sgd / (1 + pricing.gst_rate)
    costs = {"reinsurance": split.reinsurance, "management": split.management,
             "distribution": split.distribution, "profit": split.profit}
    rest = (1 - bonus.payout_share) * before_gst / sum(costs.values())
    labels = {step.key: step.label for step in premium_build_up(1.0, pricing, shares)}
    amounts = {"expected_payouts": bonus.payout_share * before_gst,
               **{key: share * rest for key, share in costs.items()}}
    steps = [PremiumStep(key=key, label=labels[key], amount_sgd=round(amount, 2))
             for key, amount in amounts.items()]
    gst = round(yearly_sgd - sum(step.amount_sgd for step in steps), 2)
    return [*steps, PremiumStep(key="gst", label=labels["gst"], amount_sgd=gst)]


def haze_bonus_quote(
    tariff: Tariff, tier: Tier, replay: Replay, today: date
) -> HazeBonusQuote | None:
    """The severe haze payout for a tier: a lump sum of lump_sum_daily_multiple daily amounts,
    sold at lump sum / payout_multiple a year, GST included."""
    bonus = tariff.haze_bonus
    if bonus is None:
        return None
    lump_sgd = bonus.lump_sum_daily_multiple * tier.daily_payout_sgd
    yearly_sgd = round(lump_sgd / bonus.payout_multiple, 2)
    gst = 1 + tariff.pricing.gst_rate
    return HazeBonusQuote(
        lump_sum_sgd=round(lump_sgd, 2),
        yearly_sgd=yearly_sgd,
        weekly_sgd=round(yearly_sgd / WEEKS_PER_YEAR, 2),
        multiple=bonus.payout_multiple,
        trigger_days=bonus.trigger_days,
        trigger_psi=bonus.trigger_psi,
        implied_yearly_chance=round(bonus.payout_share / (gst * bonus.payout_multiple), 3),
        on_sale_now=on_sale(bonus, today),
        would_have_paid_years=haze_years(bonus, replay) if HAZE in replay.readings else [],
        build_up=haze_bonus_build_up(yearly_sgd, bonus, tariff.pricing, tier.premium_shares),
    )


def singapore_today() -> date:
    return datetime.now(SINGAPORE).date()


def tier_quote(
    tariff: Tariff, tier: Tier, losses: ReplayLosses, replay: Replay, today: date
) -> TierQuote:
    paid_days = float(np.minimum(losses.loss_days, tier.max_paid_days_per_year).mean())
    risk_cost = paid_days * tier.daily_payout_sgd
    premium = yearly_premium(risk_cost, tariff.pricing, tier.premium_shares)
    yearly = round(premium, 2)
    limit_sgd = tier.daily_payout_sgd * tier.max_paid_days_per_year
    reason = not_offered_reason(tariff, tier, yearly)
    return TierQuote(
        tier=tier.key,
        label=tier.label,
        daily_payout_sgd=tier.daily_payout_sgd,
        max_payout_per_year_sgd=limit_sgd,
        expected_paid_days=round(paid_days, 2),
        yearly_premium_sgd=yearly,
        weekly_premium_sgd=round(premium / WEEKS_PER_YEAR, 2),
        build_up=premium_build_up(risk_cost, tariff.pricing, tier.premium_shares),
        price_per_day_sgd=round(premium / PRICE_DAYS_PER_YEAR, 2),
        cover_multiple=round(limit_sgd / premium, 1) if premium > 0 else None,
        offered=reason is None,
        not_offered_reason=reason,
        proof=tier_proof(tier, losses, risk_cost, premium),
        cost_per_sgd_of_daily_cover=round(yearly / tier.daily_payout_sgd, 2),
        haze_bonus=haze_bonus_quote(tariff, tier, replay, today),
    )


def mark_best_value(tiers: list[TierQuote]) -> list[TierQuote]:
    """Mark the tier offered here that pays the most a year per S$1 of premium. The first of
    equals is marked; with none offered, none is."""
    offered = [t for t in tiers if t.offered and t.yearly_premium_sgd > 0]
    if offered:
        best = max(offered, key=lambda t: t.max_payout_per_year_sgd / t.yearly_premium_sgd)
        best.best_value = True
    return tiers


def local_risks(
    losses: ReplayLosses, region_losses: ReplayLosses, stations: dict[str, list[str]]
) -> list[LocalRisk]:
    """How each replayed hazard was priced at a place, next to the region's point."""
    return [
        LocalRisk(
            hazard=hazard,
            stations=stations[hazard],
            station_days=fed_days,
            credibility=1.0,
            station_loss_days=round(losses.parts[hazard], 2),
            region_loss_days=round(region_losses.parts[hazard], 2),
            loss_days=round(losses.parts[hazard], 2),
        )
        for hazard, fed_days in losses.fed_days.items()
        if hazard in stations
    ]


def quote(
    tariff: Tariff,
    product_key: str,
    region: str,
    replay: Replay,
    region_replay: Replay | None = None,
    stations: dict[str, list[str]] | None = None,
    today: date | None = None,
) -> Quote:
    """Every tier's price for one product at one place, from the replay of its recorded days.

    With the region's replay and the stations the place reads, the quote also says how each
    hazard was priced at the place (local_risks); a region's own quote has none. today, by
    default today in Singapore, says whether the haze add-on is on sale.
    """
    today = today or singapore_today()
    product = find(tariff.products, product_key, "product")
    losses = replay_losses(tariff, product, replay)
    risks = []
    if region_replay is not None and stations is not None:
        risks = local_risks(losses, replay_losses(tariff, product, region_replay), stations)
    return Quote(
        region=region,
        product=product.key,
        expected_loss_days=round(float(losses.loss_days.mean()), 2),
        loss_day_parts={key: round(days, 2) for key, days in losses.parts.items()},
        product_factor=round(product_factor(product), 3),
        tiers=mark_best_value(
            [tier_quote(tariff, tier, losses, replay, today) for tier in tariff.tiers]
        ),
        local_risks=risks,
    )


def km_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rad = np.radians([lat1, lng1, lat2, lng2])
    h = (
        np.sin((rad[2] - rad[0]) / 2) ** 2
        + np.cos(rad[0]) * np.cos(rad[2]) * np.sin((rad[3] - rad[1]) / 2) ** 2
    )
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h)))


def check_prices(tariff: Tariff, replays: list[Replay]) -> None:
    """Raise if any of these places and products cannot be priced, so a saved tariff works."""
    for replay in replays:
        for product in tariff.products:
            replay_losses(tariff, product, replay)


@dataclass(frozen=True)
class BidRecord:
    """A centre's NEA cooked-food bids, as data/processed/hawker_rent.csv holds them."""

    centre: str
    median_bid_sgd: float | None
    bids: int
    basis: str
    first_month: str | None
    last_month: str | None


def rent_class(rent: Rent, monthly_sgd: float) -> RentClass:
    """The highest class whose lower limit the monthly rent reaches."""
    return [c for c in rent.classes if monthly_sgd >= c.at_least_monthly_sgd][-1]


def rent_tier(tiers: list[Tier], rent_per_day_sgd: float) -> tuple[Tier, bool]:
    """The smallest tier whose full-day payout covers a day's rent, else the biggest tier."""
    for tier in tiers:
        if tier.daily_payout_sgd >= rent_per_day_sgd:
            return tier, True
    return tiers[-1], False


def centre_rent(tariff: Tariff, record: BidRecord, fallback_sgd: float) -> CentreRent:
    """Rent class, rent per trading day and the tier that covers it, for one centre.

    A centre with no bid on record borrows the median of all centres and says so.
    """
    estimated = record.median_bid_sgd is None
    monthly = fallback_sgd if estimated else record.median_bid_sgd
    per_day = monthly / tariff.rent.trading_days_per_month
    chosen = rent_class(tariff.rent, monthly)
    tier, covers = rent_tier(tariff.tiers, per_day)
    return CentreRent(
        centre=record.centre,
        median_bid_sgd=round(monthly, 2),
        bids=record.bids,
        basis=record.basis,
        first_month=record.first_month,
        last_month=record.last_month,
        estimated=estimated,
        rent_class=chosen.key,
        rent_class_label=chosen.label,
        rent_per_day_sgd=round(per_day, 2),
        recommended_tier=tier.key,
        covers_rent=covers,
    )
