"""The tariff that admins edit, and the request and response shapes of the API."""

from __future__ import annotations

from datetime import datetime
from itertools import pairwise
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

Share = Annotated[float, Field(ge=0, le=1)]
Money = Annotated[float, Field(gt=0)]


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
    shelf_life_days: float = Field(gt=0)
    restock_every_days: float = Field(gt=0)
    demand_sensitivity: Share = Field(
        description="How much of a bad day's demand this product loses."
    )


class Tier(BaseModel):
    key: str
    label: str
    daily_payout_sgd: Money = Field(description="Paid for a day at 100% loss.")
    max_paid_days_per_year: int = Field(gt=0)


class Pricing(BaseModel):
    recovered_share: Share = Field(description="Share of lost non-perishable sales made up later.")
    uncertainty_load: Share
    catastrophe_load: Share
    expense_ratio: float = Field(ge=0, lt=1)
    gst_rate: Share


class Tariff(BaseModel):
    hazards: list[Hazard] = Field(min_length=1)
    products: list[Product] = Field(min_length=1)
    tiers: list[Tier] = Field(min_length=1)
    pricing: Pricing

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


class Options(BaseModel):
    regions: list[str]
    products: list[Choice]
    tiers: list[Choice]
    hazards: list[HazardChoice]


class QuoteRequest(BaseModel):
    region: str
    product: str


class TierQuote(BaseModel):
    tier: str
    label: str
    daily_payout_sgd: float
    max_payout_per_year_sgd: float
    expected_paid_days: float
    yearly_premium_sgd: float
    weekly_premium_sgd: float


class Quote(BaseModel):
    region: str
    product: str
    expected_loss_days: float
    tiers: list[TierQuote]


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
