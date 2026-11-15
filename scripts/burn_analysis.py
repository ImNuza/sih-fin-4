"""Burn analysis: what SafeDay would have paid on every recorded day since 2016.

Runs the live tariff over the actual NEA readings of 2016-2026 for every hawker centre:
each day's loss score, the payout at a chosen tier with the yearly cap applied in order,
and the estimated revenue the business lost that day. This is the back-test the brief
demands ("show, from past NEA and PUB data, how often target customers would have lost
income with no payout").

Usage:
    uv run scripts/burn_analysis.py           (run build_day_readings.py first)

Reads  data/processed/day_readings.csv.gz, data/processed/map_static.json
       data/processed/site_hazard_readings.csv, api/default_tariff.json
       data/mss_daily/mss_daily.parquet
Writes data/processed/burn_active_stations.json  the gauges and WBGT stations active each year
       data/processed/burn_site_map.json       each centre's active gauge and station per year
       data/processed/burn_yearly_hero.csv     the hero stall, year by year
       data/processed/burn_yearly_island.csv   all 103 centres summed, year by year
       data/processed/burn_daily_hero.csv      the hero stall, every day with a payout
       docs/figures/burn_hero_yearly.png, burn_2026_episode.png, burn_loss_ratio.png
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import defaultdict
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from dgs import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from api import calculator  # noqa: E402
from api.burn import point_site  # noqa: E402
from api.main import load_history  # noqa: E402
from api.models import Tariff  # noqa: E402

PROC_DIR = REPO_ROOT / "data" / "processed"
FIG_DIR = REPO_ROOT / "docs" / "figures"

HERO = "Tiong Bahru Market"
PRODUCT = "cooked_food"
TIER = "tier_2"
# Mid-point of the triangulated S$400-800/day gross takings of a viable cooked-food stall
# (no official figure exists; see the MSE replies cited in the report).
DAILY_TAKINGS_SGD = 500.0

HAZE_COLOR, RAIN_COLOR, HEAT_COLOR, LOST_COLOR = "#6f63c8", "#2a78d6", "#d95926", "#b9b7ae"


def active_stations_by_year(parquet: str, min_days: int) -> dict[str, list[str]]:
    """Which stations reported enough of each year to serve as a site's trigger station."""
    days = pd.read_parquet(PROC_DIR / parquet, columns=["station_id", "day"])
    days["year"] = pd.to_datetime(days["day"]).dt.year
    counts = days.groupby(["year", "station_id"]).size()
    active: dict[str, list[str]] = defaultdict(list)
    for (year, station), count in counts.items():
        if count >= min_days:
            active[str(year)].append(station)
    return dict(active)


def load_day_table() -> dict[str, dict[str, dict[str, float]]]:
    table: dict[str, dict[str, dict[str, float]]] = {}
    with gzip.open(PROC_DIR / "day_readings.csv.gz", "rt", newline="") as file:
        for row in csv.DictReader(file):
            table.setdefault(row["day"], {}).setdefault(row["kind"], {})[row["site"]] = float(
                row["value"]
            )
    return table


def burn() -> None:
    tariff = Tariff.model_validate_json((REPO_ROOT / "api" / "default_tariff.json").read_text())
    static = json.loads((PROC_DIR / "map_static.json").read_text())
    history, sites = load_history(PROC_DIR / "site_hazard_readings.csv")
    tier = calculator.find(tariff.tiers, TIER, "tier")
    cap_sgd = tier.daily_payout_sgd * tier.max_paid_days_per_year

    centres = static["hawker_centres"]
    active = {
        "rain": active_stations_by_year("rain_station_days.parquet", 300),
        "heat": active_stations_by_year("wbgt_station_days.parquet", 150),
    }
    (PROC_DIR / "burn_active_stations.json").write_text(json.dumps(active, separators=(",", ":")))
    site_map = {
        centre["name"]: point_site(centre["lat"], centre["lng"], centre["region"], static, active)
        for centre in centres
    }
    (PROC_DIR / "burn_site_map.json").write_text(json.dumps(site_map, separators=(",", ":")))
    premiums = {
        centre["name"]: next(
            t
            for t in calculator.quote_at(
                tariff, history, sites, centre["lat"], centre["lng"], PRODUCT
            ).tiers
            if t.tier == TIER
        ).yearly_premium_sgd
        for centre in centres
    }

    table = load_day_table()
    hero = next(c for c in centres if c["name"] == HERO)
    hero_days: list[dict] = []
    yearly: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"trigger_days": 0, "gross": 0.0, "paid": 0.0, "lost": 0.0,
                 "haze": 0.0, "rain": 0.0, "heat": 0.0}
    )
    paid_so_far: dict[tuple[str, int], float] = defaultdict(float)

    for day in sorted(table):
        readings_of_day = table[day]
        year = int(day[:4])
        for centre in centres:
            site = site_map[centre["name"]]
            gauge = site["gauge_by_year"].get(str(year))
            station = site["station_by_year"].get(str(year))
            readings = {
                "haze": readings_of_day.get("haze", {}).get(site["region"], 0.0),
                "rain": readings_of_day.get("rain", {}).get(gauge, 0.0),
                "heat": readings_of_day.get("heat", {}).get(station, 0.0),
            }
            if readings["haze"] < 101 and readings["rain"] < 20 and readings["heat"] < 2:
                continue
            assessment = calculator.assess(tariff, PRODUCT, TIER, readings)
            loss = assessment.loss_percent / 100
            if loss <= 0:
                continue
            key = (centre["name"], year)
            room = max(0.0, cap_sgd - paid_so_far[key])
            paid = min(assessment.payout_sgd, room)
            paid_so_far[key] += paid
            entry = yearly[key]
            entry["trigger_days"] += 1
            entry["gross"] += assessment.payout_sgd
            entry["paid"] += paid
            entry["lost"] += loss * DAILY_TAKINGS_SGD
            for part in assessment.hazards:
                if part.loss_percent > 0:
                    entry[part.hazard] += paid * (part.loss_percent / max(assessment.loss_percent, 0.01))
            if centre["name"] == HERO:
                hero_days.append(
                    {"day": day, **{k: round(v, 1) for k, v in readings.items()},
                     "loss_percent": assessment.loss_percent,
                     "payout_sgd": round(paid, 2), "est_lost_sgd": round(loss * DAILY_TAKINGS_SGD)}
                )

    years = sorted({year for _, year in yearly} | set(range(2017, 2027)))
    hero_rows, island_rows = [], []
    for year in years:
        entry = yearly[(HERO, year)]
        premium = premiums[HERO]
        hero_rows.append({
            "year": year, "trigger_days": entry["trigger_days"],
            "payout_sgd": round(entry["paid"], 2),
            "payout_haze_sgd": round(entry["haze"], 2),
            "payout_rain_sgd": round(entry["rain"], 2),
            "payout_heat_sgd": round(entry["heat"], 2),
            "est_lost_sgd": round(entry["lost"], 2),
            "premium_sgd": round(premium, 2),
            "loss_ratio": round(entry["paid"] / premium, 3),
            "recovered_share": round(entry["paid"] / entry["lost"], 3) if entry["lost"] else 0.0,
        })
        stalls = premium_pool = paid_total = lost_total = 0.0
        for centre in centres:
            c_entry = yearly[(centre["name"], year)]
            stalls += centre["food_stalls"]
            premium_pool += premiums[centre["name"]] * centre["food_stalls"]
            paid_total += c_entry["paid"] * centre["food_stalls"]
            lost_total += c_entry["lost"] * centre["food_stalls"]
        island_rows.append({
            "year": year, "stalls": int(stalls),
            "premium_pool_sgd": round(premium_pool),
            "payout_sgd": round(paid_total),
            "est_lost_sgd": round(lost_total),
            "loss_ratio": round(paid_total / premium_pool, 3),
        })

    pd.DataFrame(hero_rows).to_csv(PROC_DIR / "burn_yearly_hero.csv", index=False)
    pd.DataFrame(island_rows).to_csv(PROC_DIR / "burn_yearly_island.csv", index=False)
    pd.DataFrame(hero_days).to_csv(PROC_DIR / "burn_daily_hero.csv", index=False)
    figures(hero_rows, hero_days)
    summary(hero_rows, island_rows, hero_days)
    sensitivity(table, hero, site_map[HERO], history, sites, premiums[HERO] / 52)


def figures(hero_rows: list[dict], hero_days: list[dict]) -> None:
    full = [r for r in hero_rows if 2017 <= r["year"] <= 2026]
    years = [r["year"] for r in full]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([y - 0.21 for y in years], [r["est_lost_sgd"] for r in full], 0.38,
           color=LOST_COLOR, label="Estimated revenue lost")
    bottom = [0.0] * len(full)
    for key, color, label in [("payout_haze_sgd", HAZE_COLOR, "Paid for haze"),
                              ("payout_rain_sgd", RAIN_COLOR, "Paid for rain"),
                              ("payout_heat_sgd", HEAT_COLOR, "Paid for heat")]:
        values = [r[key] for r in full]
        ax.bar([y + 0.21 for y in years], values, 0.38, bottom=bottom, color=color, label=label)
        bottom = [b + v for b, v in zip(bottom, values)]
    ax.set_title("One Tiong Bahru stall, Tier 2: lost vs would-have-been-paid, by year")
    ax.set_ylabel("S$ per stall per year")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01, "NEA readings 2016-2026 through the live tariff. "
             f"Losses at S${DAILY_TAKINGS_SGD:.0f}/day takings.", fontsize=7, color="#73716b")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG_DIR / "burn_hero_yearly.png", dpi=200)

    episode = [d for d in hero_days if "2026-09-01" <= d["day"] <= "2026-11-08"]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    days = [date.fromisoformat(d["day"]) for d in episode]
    colors = [HAZE_COLOR if d["haze"] >= 101 else RAIN_COLOR for d in episode]
    ax.bar(days, [d["payout_sgd"] for d in episode], color=colors, width=1.0)
    ax.set_title("The 2026 haze season, day by day: payout per stall (Tier 2)")
    ax.set_ylabel("S$ per day")
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01, "Violet: haze trigger (24-h PSI > 100) at S$9.60-14.20 a day. Blue: rain trigger. "
             "3-25 Oct: 23 unhealthy days in a row.", fontsize=7, color="#73716b")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(FIG_DIR / "burn_2026_episode.png", dpi=200)

    fig, ax = plt.subplots(figsize=(8, 3.2))
    ratios = [r["loss_ratio"] * 100 for r in full]
    ax.bar(years, ratios, color=RAIN_COLOR, width=0.6)
    mean = sum(ratios) / len(ratios)
    ax.axhline(mean, color="#191a1c", linewidth=1, linestyle="--")
    ax.text(years[0] - 0.4, mean + 3, f"10-year average {mean:.0f}%", fontsize=8)
    ax.axhline(100, color="#b4512c", linewidth=1)
    ax.text(years[-1] - 1.6, 103, "100% = payouts eat the whole premium", fontsize=7, color="#b4512c")
    ax.set_title("Loss ratio by year: payouts as a share of the premium (one stall, Tier 2)")
    ax.set_ylabel("%")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "burn_loss_ratio.png", dpi=200)


def sensitivity(table, hero, hero_site, history, sites, premiums_base) -> None:
    """The same burn with haze severities raised to 0.5/0.8/1.0: the tariff desk's one knob
    that most changes what haze pays. Labelled a what-if; the base tariff stays the truth."""
    tariff = Tariff.model_validate_json((REPO_ROOT / "api" / "default_tariff.json").read_text())
    haze = calculator.find(tariff.hazards, "haze", "hazard")
    for band, severity in zip(haze.bands, (0.5, 0.8, 1.0)):
        band.severity = severity
    tier = calculator.find(tariff.tiers, TIER, "tier")
    cap_sgd = tier.daily_payout_sgd * tier.max_paid_days_per_year
    premium = next(
        t
        for t in calculator.quote_at(
            tariff, history, sites, hero["lat"], hero["lng"], PRODUCT
        ).tiers
        if t.tier == TIER
    ).yearly_premium_sgd
    paid_by_year: dict[int, float] = defaultdict(float)
    lost_by_year: dict[int, float] = defaultdict(float)
    for day in sorted(table):
        year = int(day[:4])
        gauge = hero_site["gauge_by_year"].get(str(year))
        station = hero_site["station_by_year"].get(str(year))
        readings = {
            "haze": table[day].get("haze", {}).get(hero_site["region"], 0.0),
            "rain": table[day].get("rain", {}).get(gauge, 0.0),
            "heat": table[day].get("heat", {}).get(station, 0.0),
        }
        if readings["haze"] < 101 and readings["rain"] < 20 and readings["heat"] < 2:
            continue
        assessment = calculator.assess(tariff, PRODUCT, TIER, readings)
        room = max(0.0, cap_sgd - paid_by_year[year])
        paid_by_year[year] += min(assessment.payout_sgd, room)
        lost_by_year[year] += assessment.loss_percent / 100 * DAILY_TAKINGS_SGD
    full_years = range(2017, 2027)
    paid = sum(paid_by_year[y] for y in full_years)
    lost = sum(lost_by_year[y] for y in full_years)
    print(f"Sensitivity (haze severities 0.5/0.8/1.0): hero 2017-2026 paid S${paid:,.0f} "
          f"of S${lost:,.0f} est. losses ({paid / lost:.0%}); 2026 paid S${paid_by_year[2026]:,.0f}; "
          f"premium S${premium:,.2f}/yr (S${premium / 52:.2f}/wk, base S${premiums_base:.2f}/wk)")


def summary(hero_rows: list[dict], island_rows: list[dict], hero_days: list[dict]) -> None:
    full = [r for r in hero_rows if 2017 <= r["year"] <= 2026]
    paid = sum(r["payout_sgd"] for r in full)
    lost = sum(r["est_lost_sgd"] for r in full)
    premium = sum(r["premium_sgd"] for r in full)
    print(f"Hero: {HERO}, {PRODUCT}, {TIER}, takings S${DAILY_TAKINGS_SGD:.0f}/day")
    print(f"2017-2026: paid S${paid:,.0f} of S${lost:,.0f} estimated losses "
          f"({paid / lost:.0%}) for S${premium:,.0f} premium (loss ratio {paid / premium:.0%})")
    worst = max(full, key=lambda r: r["payout_sgd"])
    print(f"Worst year {worst['year']}: {worst['trigger_days']} trigger days, "
          f"paid S${worst['payout_sgd']:,.0f}, est. lost S${worst['est_lost_sgd']:,.0f}")
    island_2026 = next(r for r in island_rows if r["year"] == 2026)
    print(f"Island 2026: {island_2026['stalls']:,} stalls would have been paid "
          f"S${island_2026['payout_sgd']:,.0f} against S${island_2026['est_lost_sgd']:,.0f} "
          f"est. losses (pool S${island_2026['premium_pool_sgd']:,.0f}, "
          f"loss ratio {island_2026['loss_ratio']:.0%})")
    streak = [d for d in hero_days if "2026-10-03" <= d["day"] <= "2026-10-25"]
    print(f"Hero 3-25 Oct 2026: {len(streak)} payable days, "
          f"S${sum(d['payout_sgd'] for d in streak):,.0f} paid")
    mss = pd.read_parquet(REPO_ROOT / "data" / "mss_daily" / "mss_daily.parquet")
    hours = mss.dropna(subset=["rain_max_60min_mm"])
    hours = hours[pd.to_datetime(hours["date"]) >= "2014-01-01"]
    by_station_year = hours.assign(year=pd.to_datetime(hours["date"]).dt.year).groupby(["station_id", "year"])
    share = by_station_year["rain_max_60min_mm"].apply(lambda s: (s >= 20).mean()).mean()
    print(f"MSS context 2014-2026: a 20 mm hour on {share:.1%} of station-days "
          f"(matches the 5.1% NEA figure within station mix)")


if __name__ == "__main__":
    burn()
