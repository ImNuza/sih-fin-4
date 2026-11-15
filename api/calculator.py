"""Loss score, payout and premium: pure functions of a tariff and the hazard history.

A day's loss is the share of a normal day's sales the seller loses, from 0 (no loss) to 1
(no sales at all). Each tier pays its daily payout times that share. The premium prices the
loss days an average year brings in the customer's region.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeVar

import numpy as np

from api.models import (
    Assessment,
    CentreRent,
    Hazard,
    HazardLoss,
    Pricing,
    Product,
    Quote,
    Rent,
    RentClass,
    Tariff,
    Tier,
    TierQuote,
)

DAYS_PER_YEAR = 365.25
WEEKS_PER_YEAR = 52


@dataclass(frozen=True)
class Readings:
    """Each distinct reading of one hazard in one region, and on how many site-days it happened."""

    values: np.ndarray
    days: np.ndarray


History = dict[str, dict[str, Readings]]
Keyed = TypeVar("Keyed", Hazard, Product, Tier)


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


def product_factor(product: Product, recovered_share: float) -> float:
    """Share of a bad day's lost sales the seller never gets back.

    Stock that spends most of its shelf life waiting for the next restock is thrown away when
    a day is lost. The rest can still be sold, and part of the lost demand comes back later.
    """
    wasted = min(1.0, product.restock_every_days / product.shelf_life_days)
    return product.demand_sensitivity * (wasted + (1 - wasted) * (1 - recovered_share))


def hazard_loss(hazard: Hazard, severity: float, factor: float) -> float:
    return hazard.weight * severity * (factor if hazard.scaled_by_product else 1.0)


def as_percent(share: float) -> float:
    return round(share * 100, 1)


def assess(
    tariff: Tariff, product_key: str, tier_key: str, readings: dict[str, float]
) -> Assessment:
    product = find(tariff.products, product_key, "product")
    tier = find(tariff.tiers, tier_key, "tier")
    factor = product_factor(product, tariff.pricing.recovered_share)
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
        payout_sgd=round(day_loss * tier.daily_payout_sgd, 2),
        hazards=[
            HazardLoss(
                hazard=key, reading=reading, severity=severity, loss_percent=as_percent(loss)
            )
            for key, reading, severity, loss in hazards
        ],
    )


def loss_day_parts(
    tariff: Tariff, product: Product, region_history: dict[str, Readings]
) -> dict[str, float]:
    """Days of full loss in an average year, per hazard.

    A day with two hazards counts twice, a small overstatement.
    """
    factor = product_factor(product, tariff.pricing.recovered_share)
    parts: dict[str, float] = {}
    for hazard in tariff.hazards:
        if hazard.assumed_days_per_year is not None:
            days, severity = hazard.assumed_days_per_year, hazard.bands[-1].severity
        elif hazard.key in region_history:
            readings = region_history[hazard.key]
            severity = np.average(severities(hazard, readings.values), weights=readings.days)
            days = DAYS_PER_YEAR
        else:
            raise MissingHistory(f"{hazard.label} has no NEA history. Set its assumed days a year.")
        parts[hazard.key] = days * hazard_loss(hazard, severity, factor)
    return parts


def expected_loss_days(
    tariff: Tariff, product: Product, region_history: dict[str, Readings]
) -> float:
    return sum(loss_day_parts(tariff, product, region_history).values())


def yearly_premium(risk_cost: float, pricing: Pricing) -> float:
    loaded = risk_cost * (1 + pricing.uncertainty_load + pricing.catastrophe_load)
    return loaded / (1 - pricing.expense_ratio) * (1 + pricing.gst_rate)


def quote(tariff: Tariff, history: History, region: str, product_key: str) -> Quote:
    if region not in history:
        raise UnknownKey(f"Unknown region: {region}")
    product = find(tariff.products, product_key, "product")
    loss_days = expected_loss_days(tariff, product, history[region])
    tiers = []
    for tier in tariff.tiers:
        # The cap applies to the average year. Bad years reach it sooner; the catastrophe load
        # pays for that.
        paid_days = min(loss_days, tier.max_paid_days_per_year)
        premium = yearly_premium(paid_days * tier.daily_payout_sgd, tariff.pricing)
        tiers.append(
            TierQuote(
                tier=tier.key,
                label=tier.label,
                daily_payout_sgd=tier.daily_payout_sgd,
                max_payout_per_year_sgd=tier.daily_payout_sgd * tier.max_paid_days_per_year,
                expected_paid_days=round(paid_days, 2),
                yearly_premium_sgd=round(premium, 2),
                weekly_premium_sgd=round(premium / WEEKS_PER_YEAR, 2),
            )
        )
    return Quote(
        region=region, product=product.key, expected_loss_days=round(loss_days, 2), tiers=tiers
    )


def check_prices(tariff: Tariff, history: History) -> None:
    """Raise if any region and product cannot be priced, so a saved tariff always works."""
    for region in history:
        for product in tariff.products:
            quote(tariff, history, region, product.key)


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
