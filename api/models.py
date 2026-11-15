"""The tariff that admins edit, and the request and response shapes of the API."""

from __future__ import annotations

from datetime import datetime
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Share = Annotated[float, Field(ge=0, le=1)]
Money = Annotated[float, Field(gt=0)]
KYC_TEXT_MAX_CHARS = 500
KYC_PHOTO_MAX_BYTES = 5 * 1024 * 1024
# Base64 writes every 3 bytes as 4 characters.
KYC_PHOTO_MAX_BASE64_CHARS = KYC_PHOTO_MAX_BYTES // 3 * 4 + 4


def unique_keys(items: list[BaseModel], kind: str) -> None:
    keys = [item.key for item in items]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {kind} keys: {', '.join(duplicates)}")


class Band(BaseModel):
    at_least: float
    severity: Share


class Hazard(BaseModel):
    key: str
    label: str
    reading: str = Field(description="What the reading measures, with its unit.")
    weight: Share = Field(description="Share of a day's sales lost at full severity.")
    scaled_by_product: bool = Field(
        description="False when the loss is the same for every product."
    )
    bands: list[Band] = Field(min_length=1)
    sites_used: int = Field(
        ge=1, description="How many of the nearest NEA stations the trigger reads."
    )
    assumed_days_per_year: float | None = Field(
        default=None,
        ge=0,
        description="Days a year at the top band. Empty: price from NEA history.",
    )
    source: str

    @model_validator(mode="after")
    def bands_ascend(self) -> Hazard:
        levels = [band.at_least for band in self.bands]
        if levels != sorted(set(levels)):
            raise ValueError(f"{self.label}: band levels must rise with no repeats")
        return self


class Product(BaseModel):
    key: str
    label: str
    shelf_life_days: float = Field(ge=0, description="0 for work with no stock: nothing spoils.")
    restock_every_days: float = Field(gt=0)
    demand_sensitivity: Share = Field(
        description="How much of a bad day's demand this product loses."
    )
    gross_margin: Share = Field(
        description="Share of sales left after buying the stock that was sold."
    )
    recovered_share: Share = Field(description="Share of lost sales made up on later days.")
    source: str


class Tier(BaseModel):
    key: str
    label: str
    daily_payout_sgd: Money = Field(description="Paid for a day at 100% loss.")
    max_paid_days_per_year: int = Field(gt=0)


class Pricing(BaseModel):
    uncertainty_load: Share
    catastrophe_load: Share
    expense_ratio: float = Field(ge=0, lt=1)
    gst_rate: Share


class RentClass(BaseModel):
    key: str
    label: str
    at_least_monthly_sgd: float = Field(ge=0, description="Lowest median monthly bid in the class.")


class Rent(BaseModel):
    """Rent classes of hawker centres. They set the recommended tier, never the premium."""

    trading_days_per_month: float = Field(gt=0, le=31)
    classes: list[RentClass] = Field(min_length=1)
    source: str

    @model_validator(mode="after")
    def classes_start_at_zero_and_rise(self) -> Rent:
        unique_keys(self.classes, "rent class")
        levels = [c.at_least_monthly_sgd for c in self.classes]
        if levels[0] != 0:
            raise ValueError("The first rent class must start at S$0")
        if levels != sorted(set(levels)):
            raise ValueError("Rent class limits must rise with no repeats")
        return self


DEFAULT_RENT = Rent(
    trading_days_per_month=26,
    classes=[
        RentClass(key="lower", label="Lower rent", at_least_monthly_sgd=0),
        RentClass(key="mid", label="Mid rent", at_least_monthly_sgd=1500),
        RentClass(key="high", label="High rent", at_least_monthly_sgd=3000),
    ],
    source="NEA successful tender bids for cooked-food stalls, Jan 2019 to Jul 2026, median per "
    "centre over the bids since Aug 2023. The limits split the 81 centres with a bid into "
    "thirds, rounded. 26 trading days a month (one rest day a week) is an assumption.",
)


class Tariff(BaseModel):
    hazards: list[Hazard] = Field(min_length=1)
    products: list[Product] = Field(min_length=1)
    tiers: list[Tier] = Field(min_length=1)
    pricing: Pricing
    # Tariffs saved before rent classes existed load with the defaults.
    rent: Rent = Field(default_factory=lambda: DEFAULT_RENT.model_copy(deep=True))

    @model_validator(mode="after")
    def keys_unique_and_tiers_rise(self) -> Tariff:
        unique_keys(self.hazards, "hazard")
        unique_keys(self.products, "product")
        unique_keys(self.tiers, "tier")
        for lower, higher in pairwise(self.tiers):
            if higher.daily_payout_sgd <= lower.daily_payout_sgd:
                raise ValueError(f"{higher.label} must pay more a day than {lower.label}")
            if higher.max_paid_days_per_year < lower.max_paid_days_per_year:
                raise ValueError(
                    f"{higher.label} must cover at least as many days as {lower.label}"
                )
        return self


class SavedTariff(BaseModel):
    version: int
    saved_at: datetime
    saved_by: str
    tariff: Tariff


class TariffChange(BaseModel):
    based_on_version: int = Field(description="The version the change was made from.")
    tariff: Tariff


class Choice(BaseModel):
    key: str
    label: str


class HazardChoice(Choice):
    reading: str
    has_history: bool
    first_band: float = Field(description="The lowest reading that pays anything.")


class Options(BaseModel):
    regions: list[str]
    products: list[Choice]
    tiers: list[Choice]
    hazards: list[HazardChoice]


class QuoteRequest(BaseModel):
    product: str
    region: str | None = Field(default=None, description="Price for the region as a whole.")
    latitude: float | None = Field(default=None, description="Price for this exact place.")
    longitude: float | None = None

    @model_validator(mode="after")
    def region_or_place(self) -> QuoteRequest:
        has_place = self.latitude is not None and self.longitude is not None
        if (self.region is None) == (not has_place):
            raise ValueError("Give either a region, or a latitude and longitude")
        return self


class PremiumStep(BaseModel):
    key: str
    label: str
    amount_sgd: float


class TierQuote(BaseModel):
    tier: str
    label: str
    daily_payout_sgd: float
    max_payout_per_year_sgd: float
    expected_paid_days: float
    yearly_premium_sgd: float
    weekly_premium_sgd: float
    build_up: list[PremiumStep] = Field(
        description="Why this premium: the steps from expected payouts to the yearly premium. "
        "They add up to yearly_premium_sgd."
    )


class LocalRisk(BaseModel):
    hazard: str
    stations: list[str]
    station_days: int
    credibility: float = Field(description="Weight on the stations; the rest is the region.")
    station_loss_days: float
    region_loss_days: float
    loss_days: float


class Quote(BaseModel):
    region: str
    product: str
    expected_loss_days: float
    loss_day_parts: dict[str, float] = Field(
        description="Days of full loss in an average year, per hazard. They add up to "
        "expected_loss_days, give or take rounding."
    )
    product_factor: float = Field(
        description="Share of a bad day's normal sales the product loses for good, per S$1."
    )
    tiers: list[TierQuote]
    local_risks: list[LocalRisk] = Field(
        default=[], description="How each hazard was priced for a place. Empty for a region."
    )


class AssessRequest(BaseModel):
    product: str
    tier: str
    readings: dict[str, float] = Field(
        description="Hazard key to the day's reading. Leave out hazards that did not occur."
    )


class HazardLoss(BaseModel):
    hazard: str
    reading: float
    severity: float
    loss_percent: float


class Assessment(BaseModel):
    tier: str
    loss_percent: float
    payout_sgd: float
    hazards: list[HazardLoss]


class PreviewRequest(BaseModel):
    tariff: Tariff
    region: str
    product: str
    readings: dict[str, float] = {}


class Preview(BaseModel):
    quote: Quote
    assessments: list[Assessment]


class CentreRent(BaseModel):
    centre: str
    median_bid_sgd: float = Field(description="Median winning monthly bid, or the all-centre median.")
    bids: int = Field(description="NEA bids behind the median. 0: no bid on record.")
    basis: str
    first_month: str | None
    last_month: str | None
    estimated: bool = Field(description="True when the centre has no bid and the median is borrowed.")
    rent_class: str
    rent_class_label: str
    rent_per_day_sgd: float
    recommended_tier: str = Field(description="Smallest tier whose payout covers a day's rent.")
    covers_rent: bool = Field(description="False when even the biggest tier pays less than a day's rent.")


class RentTable(BaseModel):
    trading_days_per_month: float
    classes: list[RentClass]
    source: str
    all_centre_median_sgd: float
    centres: dict[str, CentreRent]


class KycPhoto(BaseModel):
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(
        min_length=1,
        max_length=KYC_PHOTO_MAX_BASE64_CHARS,
        description="The photo as base64, 5 MB at most. Read once, never stored.",
    )


class KycRequest(BaseModel):
    text: str = Field(default="", max_length=KYC_TEXT_MAX_CHARS)
    photo: KycPhoto | None = None

    @model_validator(mode="after")
    def says_something(self) -> KycRequest:
        if not self.text.strip() and self.photo is None:
            raise ValueError("Describe the shop or attach a photo")
        return self


class KycPlace(BaseModel):
    name: str
    lat: float
    lng: float
    region: str
    match: Literal["hawker_centre", "planning_area"]
    area: str | None = Field(
        default=None,
        description="The planning area the owner named, when the place was found through it.",
    )


class KycResult(BaseModel):
    """A proposed product and place for the owner to confirm. Never a price."""

    product: str | None
    place: KycPlace | None
    confidence: float | None = Field(description="The model's own 0 to 1. Empty for keywords.")
    summary: str
    source: Literal["llm", "keywords"]
