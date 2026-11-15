"""Growth projection for SafeDay, 2027 to 2040: customers, premium pool, payouts, Income's
profit and market share for each segment, with the weather of a real past year in every future
year. PROJECTION, NOT A FORECAST: the counts, uptake curves and tier mix are stated assumptions.

Prices and payouts come from the finished pricing engine, never a copy of it: each place's
replay (api/place_days.py) is priced by calculator.quote and scored by calculator.replay_losses
under api/default_tariff.json. A segment's price is the average over the places it buys at:
hawker centres weighted by their cooked-food stalls, postcode areas and PSI regions equally.
A policy's payout in a replay year is min(that year's loss-days, the tier's limit) x its daily
amount, the quantity the price averages. Prices are held at today's level in real terms.

Each simulated future year takes the weather of one real year, 2015 to 2026, drawn with equal
weight, the same year for every place and segment in that run, so a haze year hits everyone at
once. Income's profit is the premium before GST less payouts, management and distribution:
Income keeps the reinsurance part and carries every payout, so a bad year shows its full hit.

The V3 overlay (Singapore's Third National Climate Change Study, MSS 2024) is a projection and
is not used for pricing. Heat: V3's mid-century rise in mean daily maximum WBGT is added to
every NEA WBGT reading and the tariff's heat bands are scored again, which gives the rise in
heat loss-days. Rain: every place's wettest-hour reading is scaled by V3's end-century change
in very heavy daily rainfall. Both changes ramp in a straight line from 2020 (the middle of our
history) to the middle of V3's time slice. V3 does not project haze, so haze stays as observed.

Usage:
    uv run scripts/growth_projection.py        (after build_place_years.py)

Reads  data/processed/place_day_readings.npz, data/processed/site_hazard_readings.csv,
       data/processed/map_static.json, api/default_tariff.json, data/wbgt/wbgt_*.parquet
Writes data/processed/projection_unit_economics.csv   per policy, per segment and tier
       data/processed/projection_segments.csv        per segment x uptake case x year
       data/processed/projection_cumulative.csv      2027-2030, 2027-2035, 2027-2040 totals
       data/processed/projection_climate.csv         V3 overlay, base uptake
       data/processed/projection_climate_per_policy.csv  V3 at full mid-century, per policy
       docs/figures/projection_customers.png, projection_profit_fan.png,
       projection_v3_overlay.png
"""

from __future__ import annotations

import json
import math
import textwrap
import sys
from collections import defaultdict
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dgs import REPO_ROOT
from heat_stats import READING_HOURS, load_readings

sys.path.insert(0, str(REPO_ROOT))

from api import calculator, place_days, postcodes, readings  # noqa: E402
from api.burn import load_day_table  # noqa: E402
from api.main import DEFAULT_TARIFF_PATH, HISTORY_PATH, MAP_STATIC_PATH, load_sites  # noqa: E402
from api.models import Tariff  # noqa: E402

PROC_DIR = REPO_ROOT / "data" / "processed"
FIG_DIR = REPO_ROOT / "docs" / "figures"

YEARS = np.arange(2027, 2041)
REPLAY_YEARS = np.arange(2015, 2027)
WINDOWS = {"2027-2030": 2030, "2027-2035": 2035, "2027-2040": 2040}
RUNS = 10_000
SEED = 2026
BAD_1_IN_10, BAD_1_IN_20 = 10, 5  # percentiles of the simulated profit
UPTAKE_CASES = ("low", "base", "high")
# Assumption: most buy the middle tiers, few the top one.
TIER_MIX = {"tier_1": 0.30, "tier_2": 0.40, "tier_3": 0.20, "tier_4": 0.10}

# NEA Hawker Centres dataset (data.gov.sg d_4a086da0a5553be1d89383cd90d07ecd, read 15 Nov
# 2026): 5,837 cooked-food stalls in 103 existing centres, 589 in 16 new centres, 161 in 3
# replacement centres and 78 in 1 interim centre (260 more under construction).
COOKED_STALLS_2026 = 5837 + 589 + 161 + 78
# NEA "List of Government Markets Hawker Centres" (data.gov.sg
# d_68a42f09f350881996d83f9cd73ab02f, coverage 2016): 6,121 cooked-food stalls.
COOKED_STALLS_2016 = 6121
# SingStat table M890531 (SFA), "National Environment Agency Hawker Stalls", end of year.
NEA_STALLS_2015, NEA_STALLS_2025 = 13440, 11446
MARKET_STALLS_2025 = NEA_STALLS_2025 - COOKED_STALLS_2026
# HDB press release, 19 Nov 2022, "Supporting Heartland Shops": about 15,200 HDB shops.
HDB_SHOPS_2022 = 15200
# MOM, Labour Force in Singapore 2025, paragraph 2.36: resident regular platform workers.
PLATFORM_WORKERS_2025 = 71600

# MAS General Insurance Returns, Singapore Insurance Fund, Income (NTUC Income for 2021),
# S$ thousand: Table G5 Part I underwriting profit 2021 to 2025, Table G1 gross premiums 2025.
INCOME_UNDERWRITING_PROFIT_KSGD = (23739.573, 48808.611, 68789.335, 74315.385, 40900.354)
INCOME_GI_GROSS_PREMIUM_2025_KSGD = 529412.276
THOUSAND = 1000

# Assumption: the trade mix of HDB shops. No published split was found.
SHOP_PRODUCT_MIX = {
    "general_goods": 0.40,
    "packaged_food": 0.30,
    "cooked_food": 0.15,
    "fresh_produce": 0.10,
    "flowers": 0.05,
}

# V3 Stakeholder Report (MSS, Mar 2024). Table 5.4: mean daily maximum WBGT, 30.3 C observed at
# the current 9 stations; mid-century (2040-2059) medians 31.1, 31.3 and 31.7 C. Figure 5.4:
# change in very heavy daily rainfall (99.9th percentile), annual, end-century (2080-2099),
# medians read from the chart: about +33%, +21% and +26%.
OBSERVED_DAILY_MAX_WBGT_C = 30.3
V3_SCENARIOS = {
    "SSP1-2.6": {"label": "Low emissions (SSP1-2.6)", "wbgt": 31.1, "rain": 0.33},
    "SSP2-4.5": {"label": "Medium emissions (SSP2-4.5)", "wbgt": 31.3, "rain": 0.21},
    "SSP5-8.5": {"label": "High emissions (SSP5-8.5)", "wbgt": 31.7, "rain": 0.26},
}
HISTORY_MIDDLE_YEAR = 2020
MID_CENTURY_MIDDLE_YEAR = 2050
END_CENTURY_MIDDLE_YEAR = 2090
# The heat hazard counts work hours at WBGT 32 C or more (the MOM rest-break level).
HEAT_WBGT_C = 32.0
WBGT_SHIFT_STEP_C = 0.05
OBSERVED = "observed"
TODAYS_PRICE, YEARLY_REVIEW = "today's price", "yearly review"

GROUP_LABELS = {
    "hawker_cooked_food": "Hawkers: cooked food",
    "hawker_market_stalls": "Hawkers: market stalls",
    "shops": "Neighbourhood shops",
    "platform_workers": "Platform workers",
    "total": "All segments",
}
SERIES_COLORS = {
    "hawker_cooked_food": "#2a78d6",
    "hawker_market_stalls": "#eb6834",
    "shops": "#1baf7a",
    "platform_workers": "#eda100",
}
SCENARIO_COLORS = {OBSERVED: "#b9b7ae", "SSP1-2.6": "#9ec5f0", "SSP2-4.5": "#2a78d6",
                   "SSP5-8.5": "#0d3f7a"}
INK, MUTED = "#0b0b0b", "#52514e"
AXIS_LABEL_WIDTH = 14  # characters a line under a bar group


@dataclass(frozen=True)
class Uptake:
    """An S-curve of the share of a segment's market that holds a policy."""

    launch: int
    first_year: float  # customers in the launch year, as a share of the market
    ceiling: float
    steepness: float

    def share(self, year: int) -> float:
        if year < self.launch:
            return 0.0
        middle = self.launch + math.log(self.ceiling / self.first_year - 1) / self.steepness
        return self.ceiling / (1 + math.exp(-self.steepness * (year - middle)))


@dataclass(frozen=True)
class Segment:
    key: str
    group: str  # a GROUP_LABELS key: the shops' products add up to "shops"
    product: str
    places: str  # "centres", "areas" or "regions"
    base_count: float
    base_year: int
    growth: float  # a year
    uptake: dict[str, Uptake]

    def market(self, year: int) -> float:
        return self.base_count * (1 + self.growth) ** (year - self.base_year)

    def customers(self, case: str) -> np.ndarray:
        return np.array([self.market(y) * self.uptake[case].share(y) for y in YEARS])


@dataclass
class Economics:
    """One segment's policy at the tier mix: price, its parts, and payouts per replay year."""

    premium: float  # yearly, with GST
    parts: dict[str, float]  # the five parts and GST
    payouts: dict[tuple[str, int], np.ndarray]  # climate key -> payout per replay year
    risk_cost: dict[tuple[str, int], float]  # climate key -> expected payout as the price sets it
    tiers: dict[str, dict]  # per tier, for the unit economics table

    def net(self) -> float:
        """Premium before GST less management and distribution."""
        return self.premium - sum(self.parts[k] for k in ("gst", "management", "distribution"))


def cagr(start: float, end: float, years: int) -> float:
    return (end / start) ** (1 / years) - 1


COOKED_GROWTH = cagr(COOKED_STALLS_2016, COOKED_STALLS_2026, 2026 - 2016)
NEA_STALL_GROWTH = cagr(NEA_STALLS_2015, NEA_STALLS_2025, 2025 - 2015)


def segments() -> list[Segment]:
    cooked_2027 = COOKED_STALLS_2026 * (1 + COOKED_GROWTH)
    # Year-1 counts: docs/notes/expected-impact-2026-11-15.md, Assumptions A1 to A5.
    cooked = {
        "low": Uptake(2027, 300 / cooked_2027, 0.15, 0.5),
        "base": Uptake(2027, 1000 / cooked_2027, 0.33, 0.7),
        "high": Uptake(2027, 1946 / cooked_2027, 0.50, 0.9),
    }
    market_stalls = {
        "low": Uptake(2029, 0.01, 0.05, 0.5),
        "base": Uptake(2028, 0.02, 0.15, 0.7),
        "high": Uptake(2028, 0.04, 0.30, 0.9),
    }
    shops = {
        "low": Uptake(2029, 0.005, 0.03, 0.5),
        "base": Uptake(2027, 0.01, 0.10, 0.7),
        "high": Uptake(2027, 0.03, 0.20, 0.9),
    }
    platform = {
        "low": Uptake(2027, 500 / PLATFORM_WORKERS_2025, 0.05, 0.5),
        "base": Uptake(2027, 5000 / PLATFORM_WORKERS_2025, 0.20, 0.7),
        "high": Uptake(2027, 14320 / PLATFORM_WORKERS_2025, 0.40, 0.9),
    }
    shop_segments = [
        Segment(f"shop_{product}", "shops", product, "areas", HDB_SHOPS_2022 * share, 2022,
                0.0, shops)
        for product, share in SHOP_PRODUCT_MIX.items()
    ]
    return [
        Segment("hawker_cooked_food", "hawker_cooked_food", "cooked_food", "centres",
                COOKED_STALLS_2026, 2026, COOKED_GROWTH, cooked),
        Segment("hawker_market_stalls", "hawker_market_stalls", "fresh_produce", "centres",
                MARKET_STALLS_2025, 2025, NEA_STALL_GROWTH, market_stalls),
        *shop_segments,
        Segment("platform_workers", "platform_workers", "platform_work", "regions",
                PLATFORM_WORKERS_2025, 2025, 0.0, platform),
    ]


def ramp(year: int, slice_middle: int) -> float:
    return (year - HISTORY_MIDDLE_YEAR) / (slice_middle - HISTORY_MIDDLE_YEAR)


def climate_keys() -> list[tuple[str, int]]:
    """Every (scenario, year) payouts are scored for; 2050 is V3's full mid-century."""
    keys = [(OBSERVED, 0)]
    for scenario in V3_SCENARIOS:
        keys += [(scenario, int(y)) for y in YEARS] + [(scenario, MID_CENTURY_MIDDLE_YEAR)]
    return keys


def climate_shift(key: tuple[str, int]) -> tuple[float, float]:
    """(C added to every WBGT reading, factor on every rain reading) for a climate key."""
    scenario, year = key
    if scenario == OBSERVED:
        return 0.0, 1.0
    v3 = V3_SCENARIOS[scenario]
    wbgt = (v3["wbgt"] - OBSERVED_DAILY_MAX_WBGT_C) * ramp(year, MID_CENTURY_MIDDLE_YEAR)
    return wbgt, 1 + v3["rain"] * ramp(year, END_CENTURY_MIDDLE_YEAR)


def heat_multipliers(tariff: Tariff, shifts: set[float]) -> dict[float, float]:
    """Heat loss-days under each WBGT shift as a multiple of today's: every work-hour NEA
    reading of the stations the price reads is raised by the shift and scored with the
    tariff's heat bands."""
    heat = calculator.find(tariff.hazards, "heat", "hazard")
    work = load_readings().query("work_hours")
    work = work[~work["station_id"].isin(heat.stations_on_hold)]
    station_day = [work["station_id"], work["day"]]
    grid = np.arange(0, max(shifts) + 2 * WBGT_SHIFT_STEP_C, WBGT_SHIFT_STEP_C)
    severity = []
    for shift in grid:
        hours = ((work["wbgt"] + shift) >= HEAT_WBGT_C) * READING_HOURS
        severity.append(calculator.severities(heat, hours.groupby(station_day).sum()).mean())
    ratio = np.array(severity) / severity[0]
    return {shift: float(np.interp(shift, grid, ratio)) for shift in shifts}


def priced_places(static: dict) -> dict[str, list[tuple[str, float, float, float]]]:
    """(region, lat, lng, weight) of the places each kind of business is priced at."""
    centres = [(c["region"], c["lat"], c["lng"], c["food_stalls"])
               for c in static["hawker_centres"]]
    by_sector = postcodes.centres_by_sector(static["hawker_centres"])
    areas = []
    for sector in sorted(postcodes.SECTOR_REGION):
        point = postcodes.area_point(f"{sector}0000", by_sector, static["region_points"])
        areas.append((point["region"], point["lat"], point["lng"], 1.0))
    regions = [(region, lat, lng, 1.0)
               for region, (lat, lng) in sorted(static["region_points"].items())]
    return {"centres": centres, "areas": areas, "regions": regions}


def scaled_rain(replay: calculator.Replay, factor: float) -> calculator.Replay:
    return calculator.Replay(
        days=replay.days,
        readings={**replay.readings, "rain": replay.readings["rain"] * factor},
        fed=replay.fed,
    )


def place_economics(
    tariff: Tariff, product_key: str, replay: calculator.Replay,
    heat_multiplier: dict[float, float],
) -> dict[str, dict]:
    """Each tier's price, parts and payouts per replay year under every climate key."""
    quote = calculator.quote(tariff, product_key, "", replay)
    product = calculator.find(tariff.products, product_key, "product")
    loss_days = {}
    by_rain: dict[float, calculator.ReplayLosses] = {}
    for key in climate_keys():
        wbgt, rain = climate_shift(key)
        if rain not in by_rain:
            by_rain[rain] = calculator.replay_losses(tariff, product, scaled_rain(replay, rain))
        losses = by_rain[rain]
        heat_years = np.array([losses.hazard_years["heat"][int(y)] for y in losses.years])
        extra_heat = (heat_multiplier[round(wbgt, 6)] - 1) * heat_years
        loss_days[key] = (losses.years, np.maximum(losses.loss_days + extra_heat, 0))
    out = {}
    for tier_quote in quote.tiers:
        tier = calculator.find(tariff.tiers, tier_quote.tier, "tier")
        payouts, risk_cost = {}, {}
        for key, (years, days) in loss_days.items():
            paid = np.minimum(days, tier.max_paid_days_per_year) * tier.daily_payout_sgd
            payouts[key] = paid[np.isin(years, REPLAY_YEARS)]
            risk_cost[key] = float(paid.mean())
        out[tier.key] = {
            "premium": tier_quote.yearly_premium_sgd,
            "parts": {step.key: step.amount_sgd for step in tier_quote.build_up},
            "sold_directly": float(tier_quote.sold_directly),
            "payouts": payouts,
            "risk_cost": risk_cost,
        }
    return out


def segment_economics(
    tariff: Tariff, segment: Segment, places: list[tuple[str, float, float, float]],
    days: place_days.PlaceDays, heat_multiplier: dict[float, float],
) -> Economics:
    """The weighted average over a segment's places, per tier, then at the tier mix."""
    rule = readings.station_rule(tariff)
    weights = np.array([weight for *_, weight in places], dtype=float)
    weights /= weights.sum()
    per_place = [
        place_economics(tariff, segment.product, days.replay(rule, region, lat, lng),
                        heat_multiplier)
        for region, lat, lng, _ in places
    ]

    def average(get) -> float | np.ndarray:
        return sum(w * get(place) for w, place in zip(weights, per_place, strict=True))

    tiers = {}
    for tier in TIER_MIX:
        tiers[tier] = {
            "premium": average(lambda p, t=tier: p[t]["premium"]),
            "parts": {k: average(lambda p, t=tier, k=k: p[t]["parts"][k])
                      for k in per_place[0][tier]["parts"]},
            "sold_directly": average(lambda p, t=tier: p[t]["sold_directly"]),
            "payouts": {key: average(lambda p, t=tier, key=key: p[t]["payouts"][key])
                        for key in climate_keys()},
            "risk_cost": {key: average(lambda p, t=tier, key=key: p[t]["risk_cost"][key])
                          for key in climate_keys()},
        }

    def mix(get) -> float | np.ndarray:
        return sum(share * get(tiers[tier]) for tier, share in TIER_MIX.items())

    return Economics(
        premium=mix(lambda t: t["premium"]),
        parts={k: mix(lambda t, k=k: t["parts"][k]) for k in tiers["tier_1"]["parts"]},
        payouts={key: mix(lambda t, key=key: t["payouts"][key]) for key in climate_keys()},
        risk_cost={key: mix(lambda t, key=key: t["risk_cost"][key]) for key in climate_keys()},
        tiers=tiers,
    )


def unit_economics_table(segs: list[Segment], econ: dict[str, Economics]) -> pd.DataFrame:
    rows = []
    for segment in segs:
        e = econ[segment.key]
        levels = {**{t: e.tiers[t] for t in TIER_MIX},
                  "mix": {"premium": e.premium, "parts": e.parts, "sold_directly": np.nan,
                          "payouts": e.payouts, "risk_cost": e.risk_cost}}
        for tier, level in levels.items():
            paid = level["payouts"][(OBSERVED, 0)]
            net = level["premium"] - sum(
                level["parts"][k] for k in ("gst", "management", "distribution"))
            rows.append({
                "segment": segment.key,
                "product": segment.product,
                "tier": tier,
                "tier_share": TIER_MIX.get(tier, 1.0),
                "premium_yearly_sgd": level["premium"],
                **{f"part_{k}_sgd": v for k, v in level["parts"].items()},
                "share_of_places_sold_directly": level["sold_directly"],
                "expected_payouts_priced_sgd": level["risk_cost"][(OBSERVED, 0)],
                "payout_mean_2015_2026_sgd": paid.mean(),
                **{f"payout_{y}_sgd": v for y, v in zip(REPLAY_YEARS, paid, strict=True)},
                "income_profit_mean_sgd": net - paid.mean(),
                "income_profit_2015_sgd": net - paid[REPLAY_YEARS == 2015][0],
                "income_profit_2026_sgd": net - paid[REPLAY_YEARS == 2026][0],
                "income_profit_worst_year_sgd": net - paid.max(),
            })
    return pd.DataFrame(rows).round(2)


def run_stats(runs: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "mean": runs.mean(axis=0),
        "median": np.median(runs, axis=0),
        "bad_1_in_10": np.percentile(runs, BAD_1_IN_10, axis=0),
        "bad_1_in_20": np.percentile(runs, BAD_1_IN_20, axis=0),
    }


def simulate(
    customers: np.ndarray, net: np.ndarray, payouts: np.ndarray, draws: np.ndarray
) -> np.ndarray:
    """Income's profit in every run and year (runs, years). payouts is (years, replay years)."""
    return customers * (net - payouts[np.arange(len(YEARS)), draws])


def rolled_into(segment: Segment) -> list[str]:
    """The rows a segment's numbers add to: itself, its group and the total."""
    return list(dict.fromkeys((segment.key, segment.group, "total")))


def segment_rows(
    segs: list[Segment], econ: dict[str, Economics], draws: np.ndarray
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per segment and group, uptake case and year; and the cumulative windows."""
    yearly, cumulative = [], []
    for case in UPTAKE_CASES:
        runs = defaultdict(lambda: np.zeros((RUNS, len(YEARS))))
        sums = defaultdict(lambda: defaultdict(lambda: np.zeros(len(YEARS))))
        for segment in segs:
            e = econ[segment.key]
            customers = segment.customers(case)
            payouts = np.tile(e.payouts[(OBSERVED, 0)], (len(YEARS), 1))
            profit = simulate(customers, np.full(len(YEARS), e.net()), payouts, draws)
            values = {
                "market_size": np.array([segment.market(y) for y in YEARS]),
                "customers": customers,
                "premium_pool_sgd": customers * e.premium,
                "premium_before_gst_sgd": customers * (e.premium - e.parts["gst"]),
                "payouts_mean_sgd": customers * e.payouts[(OBSERVED, 0)].mean(),
            }
            for name in rolled_into(segment):
                runs[name] += profit
                for k, v in values.items():
                    sums[name][k] += v
        for name, profit in runs.items():
            stats = run_stats(profit)
            s = sums[name]
            for i, year in enumerate(YEARS):
                yearly.append({
                    "segment": name, "uptake": case, "year": int(year),
                    "market_size": s["market_size"][i], "customers": s["customers"][i],
                    "market_share": s["customers"][i] / s["market_size"][i],
                    "premium_pool_sgd": s["premium_pool_sgd"][i],
                    "premium_before_gst_sgd": s["premium_before_gst_sgd"][i],
                    "payouts_mean_sgd": s["payouts_mean_sgd"][i],
                    **{f"income_profit_{k}_sgd": v[i] for k, v in stats.items()},
                    "share_of_income_gi_premium": s["premium_before_gst_sgd"][i]
                    / (INCOME_GI_GROSS_PREMIUM_2025_KSGD * THOUSAND),
                    "share_of_income_underwriting_profit": stats["mean"][i]
                    / (np.mean(INCOME_UNDERWRITING_PROFIT_KSGD) * THOUSAND),
                })
            for window, last in WINDOWS.items():
                upto = YEARS <= last
                totals = run_stats(profit[:, upto].sum(axis=1, keepdims=True))
                cumulative.append({
                    "segment": name, "uptake": case, "window": window,
                    "customers_at_end": s["customers"][upto][-1],
                    "premium_pool_sgd": s["premium_pool_sgd"][upto].sum(),
                    "payouts_mean_sgd": s["payouts_mean_sgd"][upto].sum(),
                    **{f"income_profit_{k}_sgd": v[0] for k, v in totals.items()},
                    "share_of_runs_with_a_loss": float((profit[:, upto].sum(axis=1) < 0).mean()),
                })
    return pd.DataFrame(yearly).round(4), pd.DataFrame(cumulative).round(4)


def climate_rows(
    segs: list[Segment], econ: dict[str, Economics], draws: np.ndarray,
    heat_multiplier: dict[float, float],
) -> pd.DataFrame:
    """The V3 overlay at base uptake: today's price, or the price the yearly review sets."""
    rows = []
    for scenario in (OBSERVED, *V3_SCENARIOS):
        for pricing in (TODAYS_PRICE, YEARLY_REVIEW):
            runs = defaultdict(lambda: np.zeros((RUNS, len(YEARS))))
            sums = defaultdict(lambda: defaultdict(lambda: np.zeros(len(YEARS))))
            for segment in segs:
                e = econ[segment.key]
                keys = [(OBSERVED, 0) if scenario == OBSERVED else (scenario, int(y))
                        for y in YEARS]
                payouts = np.stack([e.payouts[k] for k in keys])
                repriced = np.array([e.risk_cost[k] / e.risk_cost[(OBSERVED, 0)] for k in keys])
                scale = repriced if pricing == YEARLY_REVIEW else np.ones(len(YEARS))
                customers = segment.customers("base")
                profit = simulate(customers, e.net() * scale, payouts, draws)
                for name in rolled_into(segment):
                    runs[name] += profit
                    sums[name]["customers"] += customers
                    sums[name]["premium_pool_sgd"] += customers * e.premium * scale
                    sums[name]["payouts_mean_sgd"] += customers * payouts.mean(axis=1)
                    sums[name]["payouts_worst_year_sgd"] += customers * payouts.max(axis=1)
            for name, profit in runs.items():
                stats = run_stats(profit)
                s = sums[name]
                for i, year in enumerate(YEARS):
                    wbgt, rain = climate_shift(
                        (OBSERVED, 0) if scenario == OBSERVED else (scenario, int(year)))
                    rows.append({
                        "segment": name, "climate": scenario, "pricing": pricing,
                        "year": int(year), "wbgt_added_c": wbgt,
                        "heat_loss_days_multiple": heat_multiplier[round(wbgt, 6)],
                        "rain_reading_factor": rain, "customers": s["customers"][i],
                        "premium_pool_sgd": s["premium_pool_sgd"][i],
                        "payouts_mean_sgd": s["payouts_mean_sgd"][i],
                        "payouts_worst_year_sgd": s["payouts_worst_year_sgd"][i],
                        **{f"income_profit_{k}_sgd": v[i] for k, v in stats.items()},
                        "label": "projection, not used for pricing",
                    })
    return pd.DataFrame(rows).round(4)


def mid_century_per_policy(segs: list[Segment], econ: dict[str, Economics]) -> pd.DataFrame:
    """Per policy at the tier mix, at V3's full mid-century shift (2050): the change in the
    expected payout and in the worst replay year's payout."""
    rows = []
    for segment in segs:
        e = econ[segment.key]
        base = e.payouts[(OBSERVED, 0)]
        for scenario in V3_SCENARIOS:
            shifted = e.payouts[(scenario, MID_CENTURY_MIDDLE_YEAR)]
            rows.append({"segment": segment.key, "climate": scenario,
                         "payout_mean_change": shifted.mean() / base.mean() - 1,
                         "payout_worst_year_change": shifted.max() / base.max() - 1})
    return pd.DataFrame(rows)


def style_axes(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)


def group_series(table: pd.DataFrame, name: str, case: str, column: str) -> np.ndarray:
    rows = table[(table["segment"] == name) & (table["uptake"] == case)]
    return rows.sort_values("year")[column].to_numpy()


def plot_customers(table: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.6))
    names = list(SERIES_COLORS)
    stack = [group_series(table, n, "base", "customers") / 1000 for n in names]
    ax.stackplot(YEARS, stack, colors=[SERIES_COLORS[n] for n in names],
                 labels=[GROUP_LABELS[n] for n in names], edgecolor="white", linewidth=1)
    for case, style in (("low", ":"), ("high", "--")):
        ax.plot(YEARS, group_series(table, "total", case, "customers") / 1000, style,
                color=INK, linewidth=1.5, label=f"All segments, {case} uptake")
    style_axes(ax)
    ax.set_ylabel("Policies in force (thousands)", fontsize=9, color=INK)
    ax.set_title("SafeDay customers by segment, base uptake, with the low and high totals\n"
                 "PROJECTION, not a forecast", fontsize=10, color=INK, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.text(0.01, 0.01, "Market: NEA hawker centres dataset, SingStat M890531, HDB (2022), "
             "MOM Labour Force 2025. Uptake curves are assumptions. "
             "scripts/growth_projection.py", fontsize=6.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG_DIR / "projection_customers.png", dpi=160)
    plt.close(fig)


def plot_profit_fan(table: pd.DataFrame) -> None:
    names = [*SERIES_COLORS, "total"]
    fig, axes = plt.subplots(1, len(names), figsize=(14, 3.8))
    for ax, name in zip(axes, names, strict=True):
        color = SERIES_COLORS.get(name, INK)
        mean = group_series(table, name, "base", "income_profit_mean_sgd") / 1e6
        bad10 = group_series(table, name, "base", "income_profit_bad_1_in_10_sgd") / 1e6
        bad20 = group_series(table, name, "base", "income_profit_bad_1_in_20_sgd") / 1e6
        low = group_series(table, name, "low", "income_profit_mean_sgd") / 1e6
        high = group_series(table, name, "high", "income_profit_mean_sgd") / 1e6
        ax.fill_between(YEARS, low, high, color=color, alpha=0.18, linewidth=0,
                        label="Mean, low to high uptake")
        ax.plot(YEARS, mean, color=color, linewidth=2, label="Mean year, base uptake")
        ax.plot(YEARS, bad10, color=color, linewidth=1.2, linestyle="--",
                label="1-in-10 bad year")
        ax.plot(YEARS, bad20, color=MUTED, linewidth=1.2, linestyle=":",
                label="1-in-20 bad year")
        ax.axhline(0, color=MUTED, linewidth=0.8)
        style_axes(ax)
        ax.set_title(GROUP_LABELS[name], fontsize=9, color=INK, loc="left")
        ax.set_xticks([2027, 2030, 2035, 2040])
    axes[0].set_ylabel("Income's profit a year (S$ million)", fontsize=9, color=INK)
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, frameon=False, ncol=4, loc="lower center",
               bbox_to_anchor=(0.5, 0.03))
    fig.suptitle("Income's yearly profit from SafeDay, 10,000 runs, each year the weather of one "
                 "real year 2015-2026. PROJECTION, not a forecast. Each panel has its own scale.",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.01, "Prices and payouts: SafeDay pricing engine on NEA readings 2015-2026, "
             "tier mix 30/40/20/10, prices held at today's level. Profit is before reinsurance "
             "recoveries. scripts/growth_projection.py", fontsize=6.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.1, 1, 0.93))
    fig.savefig(FIG_DIR / "projection_profit_fan.png", dpi=160)
    plt.close(fig)


def plot_v3(climate: pd.DataFrame) -> None:
    names = [*SERIES_COLORS, "total"]
    scenarios = [OBSERVED, *V3_SCENARIOS]
    in_2040 = climate[(climate["year"] == 2040) & (climate["pricing"] == TODAYS_PRICE)]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    panels = (("payouts_mean_sgd", "Expected payouts in 2040 (S$ million)"),
              ("income_profit_bad_1_in_20_sgd",
               "Income's profit in a 1-in-20 bad year, 2040 (S$ million)"))
    width = 0.8 / len(scenarios)
    for ax, (column, title) in zip(axes, panels, strict=True):
        for j, scenario in enumerate(scenarios):
            values = [in_2040[(in_2040["segment"] == n) & (in_2040["climate"] == scenario)]
                      [column].iloc[0] / 1e6 for n in names]
            label = "Observed 2015-2026" if scenario == OBSERVED else \
                V3_SCENARIOS[scenario]["label"]
            ax.bar(np.arange(len(names)) + (j - 1.5) * width, values, width * 0.92,
                   color=SCENARIO_COLORS[scenario], label=label)
        ax.axhline(0, color=MUTED, linewidth=0.8)
        style_axes(ax)
        ax.set_xticks(np.arange(len(names)),
                      [textwrap.fill(GROUP_LABELS[n], AXIS_LABEL_WIDTH) for n in names],
                      fontsize=8)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
    axes[0].legend(fontsize=7.5, frameon=False, loc="upper left")
    fig.suptitle("V3 climate overlay at base uptake, prices held at today's level. PROJECTION, "
                 "NOT USED FOR PRICING. Haze stays as observed (V3 does not project it).",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.01, "Heat: V3 Stakeholder Report (MSS 2024) Table 5.4, mid-century daily "
             "maximum WBGT, ramped from 2020 to 2050. Rain: Figure 5.4, end-century very heavy "
             "daily rainfall, ramped from 2020 to 2090. scripts/growth_projection.py",
             fontsize=6.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.savefig(FIG_DIR / "projection_v3_overlay.png", dpi=160)
    plt.close(fig)


def main() -> None:
    tariff = Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())
    static = json.loads(MAP_STATIC_PATH.read_text())
    days = place_days.PlaceDays(
        load_sites(HISTORY_PATH), load_day_table, place_days.PLACE_DAYS_PATH
    )
    shifts = {round(climate_shift(key)[0], 6) for key in climate_keys()}
    heat_multiplier = heat_multipliers(tariff, shifts)
    places = priced_places(static)
    segs = segments()
    econ = {
        s.key: segment_economics(tariff, s, places[s.places], days, heat_multiplier)
        for s in segs
    }
    draws = np.random.default_rng(SEED).integers(0, len(REPLAY_YEARS), (RUNS, len(YEARS)))

    unit = unit_economics_table(segs, econ)
    yearly, cumulative = segment_rows(segs, econ, draws)
    climate = climate_rows(segs, econ, draws, heat_multiplier)
    unit.to_csv(PROC_DIR / "projection_unit_economics.csv", index=False)
    yearly.to_csv(PROC_DIR / "projection_segments.csv", index=False)
    cumulative.to_csv(PROC_DIR / "projection_cumulative.csv", index=False)
    climate.to_csv(PROC_DIR / "projection_climate.csv", index=False)
    mid_century_per_policy(segs, econ).round(4).to_csv(
        PROC_DIR / "projection_climate_per_policy.csv", index=False)
    plot_customers(yearly)
    plot_profit_fan(yearly)
    plot_v3(climate)

    print(f"Cooked-stall growth {COOKED_GROWTH:.2%} a year, NEA stalls {NEA_STALL_GROWTH:.2%}, "
          f"market stalls 2025 {MARKET_STALLS_2025:,}")
    print("Heat loss-day multiples:", {k: round(v, 2) for k, v in sorted(heat_multiplier.items())
                                       if k in {round(climate_shift((s, y))[0], 6)
                                                for s in V3_SCENARIOS for y in (2040, 2050)}})
    print(unit[unit["tier"] == "mix"].T.to_string())

    milestones = yearly[yearly["year"].isin([2030, 2035, 2040])
                        & ~yearly["segment"].str.startswith("shop_")]
    print(milestones.pivot_table(index=["segment", "year"], columns="uptake",
                                 values=["customers", "income_profit_mean_sgd"]).round(0)
          .to_string())


if __name__ == "__main__":
    main()
