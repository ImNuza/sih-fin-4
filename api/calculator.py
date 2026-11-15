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
    LocalRisk,
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
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Readings:
    """Each distinct reading of one hazard in one region, and on how many site-days it happened."""

    values: np.ndarray
    days: np.ndarray


@dataclass(frozen=True)
class Site:
    """One NEA station's history of one hazard, and where it is."""

    key: str
    region: str
    latitude: float
    longitude: float
    readings: Readings


History = dict[str, dict[str, Readings]]
Sites = dict[str, list[Site]]
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


def product_factor(product: Product) -> float:
    """Share of a bad day's normal sales the seller loses for good, per S$1 of those sales.

    Two parts, as insurers split them: the gross profit on sales that never come back (business
    interruption cover), and the cost of stock that spoils before it can be sold (deterioration
    of stock cover). Stock spoils when it waits longer for a sale than its shelf life.
    """
    wasted = min(1.0, product.restock_every_days / product.shelf_life_days)
    lost_profit = product.gross_margin * (1 - product.recovered_share)
    spoiled_stock = wasted * (1 - product.gross_margin)
    return product.demand_sensitivity * (lost_profit + spoiled_stock)


def hazard_loss(hazard: Hazard, severity: float, factor: float) -> float:
    return hazard.weight * severity * (factor if hazard.scaled_by_product else 1.0)


def as_percent(share: float) -> float:
    return round(share * 100, 1)


def assess(
    tariff: Tariff, product_key: str, tier_key: str, readings: dict[str, float]
) -> Assessment:
    product = find(tariff.products, product_key, "product")
    tier = find(tariff.tiers, tier_key, "tier")
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
    factor = product_factor(product)
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


def tier_quotes(tariff: Tariff, loss_days: float) -> list[TierQuote]:
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
    return tiers


def quote(tariff: Tariff, history: History, region: str, product_key: str) -> Quote:
    if region not in history:
        raise UnknownKey(f"Unknown region: {region}")
    product = find(tariff.products, product_key, "product")
    loss_days = expected_loss_days(tariff, product, history[region])
    return Quote(
        region=region,
        product=product.key,
        expected_loss_days=round(loss_days, 2),
        tiers=tier_quotes(tariff, loss_days),
    )


def km_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rad = np.radians([lat1, lng1, lat2, lng2])
    h = (
        np.sin((rad[2] - rad[0]) / 2) ** 2
        + np.cos(rad[0]) * np.cos(rad[2]) * np.sin((rad[3] - rad[1]) / 2) ** 2
    )
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h)))


def nearest_sites(sites: list[Site], latitude: float, longitude: float, count: int) -> list[Site]:
    return sorted(
        sites, key=lambda site: km_between(latitude, longitude, site.latitude, site.longitude)
    )[:count]


def mean_severity(hazard: Hazard, readings: list[Readings]) -> tuple[float, int]:
    """Average severity over the pooled days of these readings, and how many days that is."""
    values = np.concatenate([r.values for r in readings])
    days = np.concatenate([r.days for r in readings])
    return float(np.average(severities(hazard, values), weights=days)), int(days.sum())


def credibility_constant(hazard: Hazard, sites: list[Site]) -> float:
    """Bühlmann-Straub K = within-station variance / variance between stations of one region.

    Werner and Modlin, Basic Ratemaking (CAS, 2016), ch. 12: Z = N / (N + K). Daily severity is
    the observation and each station is a risk; the region's mean is the complement, so the
    between-station spread is measured inside each region. K is infinite (no weight on the
    station) when the stations of a region differ no more than chance would make them.
    """
    by_region: dict[str, list[tuple[float, int]]] = {}
    within_squares, within_freedom = 0.0, 0
    for site in sites:
        severity = severities(hazard, site.readings.values)
        mean, days = mean_severity(hazard, [site.readings])
        within_squares += float(np.sum(site.readings.days * (severity - mean) ** 2))
        within_freedom += days - 1
        by_region.setdefault(site.region, []).append((mean, days))
    within_variance = within_squares / within_freedom
    between_squares, between_weight = 0.0, 0.0
    for stations in by_region.values():
        region_days = sum(days for _, days in stations)
        region_mean = sum(mean * days for mean, days in stations) / region_days
        between_squares += sum(days * (mean - region_mean) ** 2 for mean, days in stations)
        between_weight += region_days - sum(days**2 for _, days in stations) / region_days
    station_count = sum(len(stations) for stations in by_region.values())
    if between_weight == 0:
        return math.inf
    excess = between_squares - (station_count - len(by_region)) * within_variance
    between_variance = excess / between_weight
    return within_variance / between_variance if between_variance > 0 else math.inf


def local_risk(
    tariff: Tariff,
    product: Product,
    history: History,
    hazard: Hazard,
    sites: list[Site],
    latitude: float,
    longitude: float,
) -> LocalRisk:
    """Loss days a year at one place: its nearest stations, blended with their region.

    The price reads the same stations as the trigger. With little station history the region
    average carries most of the weight; with years of it, the station does.
    """
    factor = product_factor(product)
    nearest = nearest_sites(sites, latitude, longitude, hazard.sites_used)
    region = nearest[0].region
    station_severity, station_days = mean_severity(hazard, [site.readings for site in nearest])
    region_severity, _ = mean_severity(hazard, [history[region][hazard.key]])
    k = credibility_constant(hazard, sites)
    credibility = station_days / (station_days + k)
    severity = credibility * station_severity + (1 - credibility) * region_severity

    def loss_days(mean: float) -> float:
        return DAYS_PER_YEAR * hazard_loss(hazard, mean, factor)

    return LocalRisk(
        hazard=hazard.key,
        stations=[site.key for site in nearest],
        station_days=station_days,
        credibility=round(credibility, 3),
        station_loss_days=round(loss_days(station_severity), 2),
        region_loss_days=round(loss_days(region_severity), 2),
        loss_days=round(loss_days(severity), 2),
    )


def quote_at(
    tariff: Tariff,
    history: History,
    sites: Sites,
    latitude: float,
    longitude: float,
    product_key: str,
) -> Quote:
    """Quote for one place, from the NEA stations nearest to it."""
    product = find(tariff.products, product_key, "product")
    every_site = [site for hazard_sites in sites.values() for site in hazard_sites]
    region = nearest_sites(every_site, latitude, longitude, 1)[0].region
    risks = [
        local_risk(tariff, product, history, hazard, sites[hazard.key], latitude, longitude)
        for hazard in tariff.hazards
        if hazard.assumed_days_per_year is None and hazard.key in sites
    ]
    priced = {risk.hazard for risk in risks}
    region_parts = loss_day_parts(tariff, product, history[region])
    loss_days = sum(risk.loss_days for risk in risks) + sum(
        days for key, days in region_parts.items() if key not in priced
    )
    return Quote(
        region=region,
        product=product.key,
        expected_loss_days=round(loss_days, 2),
        tiers=tier_quotes(tariff, loss_days),
        local_risks=risks,
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
