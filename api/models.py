"""The tariff that admins edit, and the request and response shapes of the API."""

from __future__ import annotations

from datetime import datetime
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Share = Annotated[float, Field(ge=0, le=1)]
Money = Annotated[float, Field(gt=0)]
# Shares typed with two decimals add up to 1 within float rounding.
SHARES_TOLERANCE = 1e-6
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
    stations_on_hold: list[str] = Field(
        default=[],
        description="Stations (PSI regions for haze) left out of every reading, for price and "
        "payout, until NEA confirms them. The next nearest station is read instead.",
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


class PremiumShares(BaseModel):
    """A tier's premium before GST in the insurer's five parts. A policy's fixed costs do not
    grow with its daily amount, so a bigger tier spends a smaller share on costs."""

    expected_payouts: Annotated[float, Field(gt=0, le=1)]
    reinsurance: Share
    management: Share
    distribution: Share
    profit: Share

    @model_validator(mode="after")
    def add_up_to_one(self) -> PremiumShares:
        total = sum(self.model_dump().values())
        if abs(total - 1) > SHARES_TOLERANCE:
            raise ValueError(f"The five premium shares must add up to 1, not {total:g}")
        return self


class Tier(BaseModel):
    key: str
    label: str
    daily_payout_sgd: Money = Field(description="Paid for a day at 100% loss.")
    max_paid_days_per_year: int = Field(gt=0)
    premium_shares: PremiumShares | None = Field(
        default=None,
        description="This tier's split of the premium before GST. Empty: the Pricing loads, "
        "and the tier is held back only where its premium reaches its yearly limit.",
    )


class Pricing(BaseModel):
    uncertainty_load: Share = Field(description="Shown as the expected profit and risk margin.")
    catastrophe_load: Share = Field(description="Shown as the reinsurance for haze years.")
    expense_ratio: float = Field(ge=0, lt=1, description="Running costs, share of the premium "
                                 "before GST: management plus distribution.")
    gst_rate: Share
    # Tariffs saved before these fields existed load with the defaults.
    distribution_expense_ratio: Share = Field(
        default=0.15, description="The selling and distribution part of expense_ratio."
    )
    # The name is kept so saved tariffs load; the rule now hides the tier instead of referring.
    refer_above_limit_share: Share = Field(
        default=0.5,
        description="A tier with premium shares whose yearly premium is more than this share of "
        "its yearly limit is not offered at that place.",
    )

    @model_validator(mode="before")
    @classmethod
    def distribution_from_old_expenses(cls, data: object) -> object:
        """A tariff saved before the split keeps its running costs: selling and distribution
        is the default share, or all of them when they are smaller."""
        if isinstance(data, dict) and "distribution_expense_ratio" not in data:
            expenses = data.get("expense_ratio")
            if isinstance(expenses, int | float):
                default = cls.model_fields["distribution_expense_ratio"].default
                return {**data, "distribution_expense_ratio": min(default, expenses)}
        return data

    @model_validator(mode="after")
    def distribution_within_expenses(self) -> Pricing:
        if self.distribution_expense_ratio > self.expense_ratio:
            raise ValueError("Selling and distribution cannot be more than the running costs")
        return self


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


class HazeBonus(BaseModel):
    """The optional severe haze payout: one lump sum in a policy year with many haze days."""

    trigger_psi: float = Field(gt=0, description="Daily highest 24-hour PSI in the region.")
    trigger_days: int = Field(gt=0, description="Days at or above trigger_psi in a policy year.")
    lump_sum_daily_multiple: float = Field(gt=0, description="Lump sum over the daily amount.")
    payout_multiple: float = Field(gt=1, description="Lump sum over the yearly price incl. GST.")
    payout_share: Annotated[float, Field(gt=0, le=1)] = Field(
        description="Share of the price before GST expected back as payouts."
    )
    no_sale_months: list[Annotated[int, Field(ge=1, le=12)]] = Field(
        description="Months the add-on cannot be added, so nobody buys it as haze nears."
    )
    waiting_days: int = Field(ge=0, description="Days from purchase before it can pay.")
    source: str


class Tariff(BaseModel):
    hazards: list[Hazard] = Field(min_length=1)
    products: list[Product] = Field(min_length=1)
    tiers: list[Tier] = Field(min_length=1)
    pricing: Pricing
    # Tariffs saved before rent classes existed load with the defaults.
    rent: Rent = Field(default_factory=lambda: DEFAULT_RENT.model_copy(deep=True))
    haze_bonus: HazeBonus | None = Field(
        default=None, description="The severe haze payout add-on. Empty: not offered."
    )

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
    centre: str | None = Field(
        default=None, description="Price at this NEA hawker centre, as a stall there is charged."
    )
    postcode: str | None = Field(
        default=None, description="Price at this postcode's area, as a shop there is charged."
    )

    @model_validator(mode="after")
    def one_place(self) -> QuoteRequest:
        has_point = self.latitude is not None and self.longitude is not None
        places = (self.region, self.centre, self.postcode)
        if sum(place is not None for place in places) + has_point != 1:
            raise ValueError(
                "Give one of: a region, a latitude and longitude, a hawker centre or a postcode"
            )
        return self


class PremiumStep(BaseModel):
    key: str
    label: str
    amount_sgd: float


class TierProof(BaseModel):
    """What the tier would have paid at the customer's own place, replayed on NEA's readings."""

    years_replayed: int = Field(description="Full replay years, 2017 to the latest year.")
    years_paid: int = Field(description="Of those, years with at least one payout.")
    payout_days_per_year: float = Field(
        description="Average days with any payout a year, over the full years before the latest."
    )
    typical_year_paid_sgd: float = Field(
        description="Median yearly payout over the full years before the latest."
    )
    paid_2026_sgd: float = Field(description="Paid in 2026, to the last day of data.")
    haze_2015_like_sgd: float = Field(
        description="A 2015 haze year plus the average year of the other hazards, within the "
        "yearly limit."
    )
    payback_share: float = Field(
        description="Expected yearly payout over the yearly premium, GST included."
    )


class HazeBonusQuote(BaseModel):
    """The severe haze payout add-on for one tier at one place."""

    lump_sum_sgd: float
    yearly_sgd: float = Field(description="lump_sum_sgd over multiple, GST included.")
    weekly_sgd: float
    multiple: float
    trigger_days: int
    trigger_psi: float
    implied_yearly_chance: float = Field(
        description="The yearly chance of a payout the price assumes: payout share over "
        "(1 + GST) x multiple."
    )
    on_sale_now: bool = Field(description="False in the months it cannot be added (Singapore).")
    would_have_paid_years: list[int] = Field(
        description="Calendar years of the replay in which this place's region reached "
        "trigger_days."
    )
    build_up: list[PremiumStep] = Field(
        description="The add-on's yearly price in the five parts, then GST."
    )


class TierQuote(BaseModel):
    tier: str
    label: str
    daily_payout_sgd: float
    max_payout_per_year_sgd: float
    expected_paid_days: float = Field(
        description="Average over the replay years of each year's loss-days within the limit."
    )
    yearly_premium_sgd: float
    weekly_premium_sgd: float
    build_up: list[PremiumStep] = Field(
        description="Why this premium: expected payouts, reinsurance, management, distribution, "
        "profit and GST. They add up to yearly_premium_sgd."
    )
    price_per_day_sgd: float = Field(description="yearly_premium_sgd over 365 days.")
    cover_multiple: float | None = Field(
        description="max_payout_per_year_sgd over yearly_premium_sgd. Empty for a free tier."
    )
    offered: bool = Field(
        description="False when the yearly premium here is at or above the yearly limit, or, for "
        "a tier with premium shares, more than refer_above_limit_share of it. A tier that is not "
        "offered cannot be bought at this place."
    )
    not_offered_reason: str | None = Field(
        default=None,
        description="Why the tier is not offered here, in plain words: the place's weather "
        "history. Empty when it is offered.",
    )
    proof: TierProof | None = Field(description="Empty only when no replay year is complete.")
    best_value: bool = Field(
        default=False,
        description="True for the tier offered here with the highest cover_multiple.",
    )
    cost_per_sgd_of_daily_cover: float = Field(
        description="yearly_premium_sgd over daily_payout_sgd."
    )
    haze_bonus: HazeBonusQuote | None = Field(
        default=None, description="The severe haze payout add-on. Empty: not offered."
    )


class LocalRisk(BaseModel):
    hazard: str
    stations: list[str] = Field(
        description="What the place reads on a day every station reports: its PSI region, or "
        "its nearest stations not on hold."
    )
    station_days: int = Field(description="Days in the replay with this hazard's feed running.")
    credibility: float = Field(
        description="Weight on the place's own readings; the rest is the region. The replay "
        "reads the place's stations directly, so this is 1."
    )
    station_loss_days: float = Field(description="Loss-days a year at the place.")
    region_loss_days: float = Field(description="Loss-days a year at the region's point.")
    loss_days: float = Field(description="Loss-days a year priced: the place's.")


class Quote(BaseModel):
    region: str
    product: str
    expected_loss_days: float
    loss_day_parts: dict[str, float] = Field(
        description="Days of full loss in an average year, per hazard, over the days its feed "
        "ran. They add up to expected_loss_days, give or take rounding and the few days two "
        "hazards struck at once."
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
