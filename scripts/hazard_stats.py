"""Haze and rain first look, plus a heat / rain / haze comparison.

Usage:
    uv run scripts/hazard_stats.py      (run heat_stats.py first: it makes the heat table)

Reads  data/psi/*.parquet, data/rainfall/*.parquet, data/processed/wbgt_station_days.parquet
Writes data/processed/psi_daily.parquet, psi_yearly.csv, psi_episodes.csv
       data/processed/rain_station_days.parquet, rain_monthly.csv
       data/processed/peril_comparison.csv
       docs/figures/psi_daily_max_2016_2026.png
       docs/figures/rain_heavy_days_by_month.png
"""

from __future__ import annotations

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dgs import REPO_ROOT
from heat_stats import (
    BAR,
    INK,
    INK_2,
    MUTED,
    SOURCE,
    SURFACE,
    core_station_ids,
    period_label,
    style_axes,
)

PROC_DIR = REPO_ROOT / "data" / "processed"
FIG_DIR = REPO_ROOT / "docs" / "figures"

# NEA 24-hour PSI bands: 0-50 good, 51-100 moderate, 101-200 unhealthy,
# 201-300 very unhealthy, above 300 hazardous.
PSI_UNHEALTHY = 100
PSI_VERY_UNHEALTHY = 200
WORK_START_HOUR, WORK_END_HOUR = 7, 19
WET_HOUR_MM = 1.0  # an hour with at least 1 mm counts as wet
HEAVY_HOUR_MM = (10, 20, 30)
MIN_EPISODE_DAYS = 1


# ---------- haze ----------


def load_psi() -> pd.DataFrame:
    frame = pd.concat(
        pd.read_parquet(p) for p in sorted((REPO_ROOT / "data" / "psi").glob("psi_*.parquet"))
    )
    frame["day"] = (
        frame["timestamp"].dt.tz_convert("Asia/Singapore").dt.tz_localize(None).dt.normalize()
    )
    return frame


def psi_daily(psi: pd.DataFrame) -> pd.DataFrame:
    """Daily max 24-hour PSI per region, the island max, and how many regions were unhealthy."""
    per_region = psi.pivot_table(
        index="day", columns="region", values="psi_twenty_four_hourly", aggfunc="max"
    )
    out = pd.DataFrame(index=per_region.index)
    out["psi_max"] = per_region.max(axis=1)
    out["regions_reporting"] = per_region.notna().sum(axis=1)
    out["regions_unhealthy"] = (per_region > PSI_UNHEALTHY).sum(axis=1)
    return out.join(per_region.add_prefix("psi_")).reset_index()


def psi_yearly(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.assign(year=daily["day"].dt.year)
    out = daily.groupby("year").agg(days_with_data=("day", "count"), psi_peak=("psi_max", "max"))
    out["days_unhealthy"] = (
        daily.assign(x=daily["psi_max"] > PSI_UNHEALTHY).groupby("year")["x"].sum()
    )
    out["days_very_unhealthy"] = (
        daily.assign(x=daily["psi_max"] > PSI_VERY_UNHEALTHY).groupby("year")["x"].sum()
    )
    return out.reset_index()


def psi_episodes(daily: pd.DataFrame) -> pd.DataFrame:
    """Runs of consecutive days with island max PSI above 100."""
    hazy = daily.set_index("day")["psi_max"] > PSI_UNHEALTHY
    episodes, start = [], None
    days = list(hazy.index)
    for i, day in enumerate(days):
        if hazy.iloc[i] and start is None:
            start = day
        last_of_run = hazy.iloc[i] and (
            i + 1 == len(days) or not hazy.iloc[i + 1] or days[i + 1] - day > pd.Timedelta(days=1)
        )
        if last_of_run:
            part = daily[(daily["day"] >= start) & (daily["day"] <= day)]
            episodes.append(
                {
                    "start": start.date(),
                    "end": day.date(),
                    "days": len(part),
                    "psi_peak": part["psi_max"].max(),
                    "days_all_regions_unhealthy": int(
                        (part["regions_unhealthy"] == part["regions_reporting"]).sum()
                    ),
                }
            )
            start = None
    out = pd.DataFrame(episodes)
    return out[out["days"] >= MIN_EPISODE_DAYS].sort_values("start") if len(out) else out


def plot_psi(daily: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.4), facecolor=SURFACE)
    style_axes(ax)
    ax.plot(daily["day"], daily["psi_max"], color=BAR, linewidth=1.2)
    for level, label in (
        (PSI_UNHEALTHY, "100 unhealthy"),
        (PSI_VERY_UNHEALTHY, "200 very unhealthy"),
    ):
        ax.axhline(level, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(daily["day"].iloc[0], level + 4, label, fontsize=8, color=INK_2)
    ax.set_ylabel("24-hour PSI", color=INK_2)
    ax.set_ylim(bottom=0)
    fig.suptitle(
        "Haze: highest 24-hour PSI in Singapore each day",
        x=0.01,
        ha="left",
        fontsize=13,
        color=INK,
        fontweight="bold",
    )
    ax.set_title(
        f"Daily maximum across the 5 NEA regions, {period_label(daily['day'])}. {SOURCE}",
        loc="left",
        fontsize=9,
        color=INK_2,
    )
    fig.tight_layout()
    fig.savefig(FIG_DIR / "psi_daily_max_2016_2026.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


# ---------- rain ----------


def load_rain() -> pd.DataFrame:
    frame = pd.concat(
        pd.read_parquet(p)
        for p in sorted((REPO_ROOT / "data" / "rainfall").glob("rain_hourly_*.parquet"))
    )
    local = frame["hour"].dt.tz_convert("Asia/Singapore")
    frame["day"] = local.dt.tz_localize(None).dt.normalize()
    frame["work_hour"] = (local.dt.hour >= WORK_START_HOUR) & (local.dt.hour < WORK_END_HOUR)
    return frame


def rain_station_days(rain: pd.DataFrame) -> pd.DataFrame:
    work = rain[rain["work_hour"]].copy()
    work["wet_hours"] = work["rain_mm"] >= WET_HOUR_MM
    for t in HEAVY_HOUR_MM:
        work[f"hours_ge_{t}mm"] = work["rain_mm"] >= t
    return (
        work.groupby(["station_id", "day"])
        .agg(
            work_rain_mm=("rain_mm", "sum"),
            wet_hours=("wet_hours", "sum"),
            **{f"hours_ge_{t}mm": (f"hours_ge_{t}mm", "sum") for t in HEAVY_HOUR_MM},
        )
        .reset_index()
    )


def rain_monthly(days: pd.DataFrame) -> pd.DataFrame:
    island = days.groupby("day").agg(max_heavy=("hours_ge_20mm", "max")).reset_index()
    island["month"] = island["day"].dt.to_period("M").astype(str)
    out = island.groupby("month").agg(days_with_data=("day", "count"))
    out["days_any_station_ge_20mm_hour"] = (
        island.assign(x=island["max_heavy"] > 0).groupby("month")["x"].sum()
    )
    days = days.assign(month=days["day"].dt.to_period("M").astype(str))
    out["share_station_days_ge_20mm_hour"] = (
        days.assign(x=days["hours_ge_20mm"] > 0).groupby("month")["x"].mean().round(3)
    )
    out["avg_wet_work_hours_per_station_day"] = days.groupby("month")["wet_hours"].mean().round(2)
    return out.reset_index()


def heavy_share(days: pd.DataFrame, key: pd.Series) -> pd.Series:
    return (days["hours_ge_20mm"] > 0).groupby(key).mean() * 100


def label_bars(ax: plt.Axes, bars, values: pd.Series) -> None:
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.15,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            color=INK_2,
        )


def plot_rain(days: pd.DataFrame, rain: pd.DataFrame) -> None:
    """Left: season (calendar month, all years pooled). Right: each year, part years muted."""
    gauges = rain.groupby("day")["station_id"].nunique()
    by_month = heavy_share(days, days["day"].dt.month)
    by_year = heavy_share(days, days["day"].dt.year)
    first_year, last_year = by_year.index.min(), by_year.index.max()

    fig, (ax_month, ax_year) = plt.subplots(
        1, 2, figsize=(12, 4.8), facecolor=SURFACE, sharey=True, width_ratios=(12, 11)
    )
    for ax in (ax_month, ax_year):
        style_axes(ax)
    bars = ax_month.bar(range(12), by_month, width=0.6, color=BAR, edgecolor=SURFACE, linewidth=2)
    label_bars(ax_month, bars, by_month)
    month_names = pd.date_range("2001-01-01", periods=12, freq="MS").strftime("%b")
    ax_month.set_xticks(range(12), month_names, fontsize=9)
    ax_month.set_title("By calendar month, all years", loc="left", fontsize=10, color=INK)
    ax_month.set_ylabel("% of station-days", color=INK_2)

    colors = [MUTED if year in (first_year, last_year) else BAR for year in by_year.index]
    bars = ax_year.bar(
        range(len(by_year)),
        by_year,
        width=0.6,
        color=colors,
        edgecolor=SURFACE,
        linewidth=2,
    )
    label_bars(ax_year, bars, by_year)
    ax_year.set_xticks(range(len(by_year)), by_year.index.astype(str), fontsize=9)
    ax_year.set_title(
        f"By year (grey: only part of {first_year} and {last_year})",
        loc="left",
        fontsize=10,
        color=INK,
    )

    fig.suptitle(
        "Heavy rain: share of days with an hour of 20 mm or more at a station (7am to 7pm)",
        x=0.01,
        ha="left",
        fontsize=13,
        color=INK,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.9,
        f"{gauges.min()} to {gauges.max()} rain gauges per day (median {gauges.median():.0f}), "
        f"{period_label(rain['day'])}. {SOURCE}",
        fontsize=9,
        color=INK_2,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(FIG_DIR / "rain_heavy_days_by_month.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


# ---------- comparison ----------


def spread(days: pd.DataFrame, hit_column: str) -> float:
    """Average share of locations hit, on days with at least one hit (1.0 = whole island)."""
    per_day = days.groupby("day")[hit_column].agg(["sum", "count"])
    per_day = per_day[per_day["sum"] > 0]
    return round((per_day["sum"] / per_day["count"]).mean(), 2)


def comparison(heat_days: pd.DataFrame, rain_days: pd.DataFrame, psi: pd.DataFrame) -> pd.DataFrame:
    """Each peril over the WBGT period (like for like), then rain and haze over all years."""
    heat_days = heat_days[heat_days["station_id"].isin(core_station_ids(heat_days))]
    heat = heat_days.assign(hit=heat_days["max_wbgt"] >= 32)
    rain = rain_days.assign(hit=rain_days["hours_ge_20mm"] > 0)
    region_days = psi.groupby(["region", "day"])["psi_twenty_four_hourly"].max().reset_index()
    haze = region_days.assign(hit=region_days["psi_twenty_four_hourly"] > PSI_UNHEALTHY)
    wbgt_start = heat["day"].min()
    rows = []
    for name, frame in (
        ("Heat: WBGT >= 32°C in work hours (7 core stations)", heat),
        ("Rain: an hour >= 20 mm in work hours", rain[rain["day"] >= wbgt_start]),
        ("Haze: 24-hour PSI > 100", haze[haze["day"] >= wbgt_start]),
        ("Rain: an hour >= 20 mm in work hours", rain),
        ("Haze: 24-hour PSI > 100", haze),
    ):
        rows.append(
            {
                "peril": name,
                "period": period_label(frame["day"]),
                "share_days_one_location": round(frame["hit"].mean(), 3),
                "share_days_anywhere": round(frame.groupby("day")["hit"].max().mean(), 3),
                "share_of_locations_hit_on_event_days": spread(frame, "hit"),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    psi = load_psi()
    daily = psi_daily(psi)
    daily.to_parquet(PROC_DIR / "psi_daily.parquet", index=False)
    yearly = psi_yearly(daily)
    yearly.to_csv(PROC_DIR / "psi_yearly.csv", index=False)
    episodes = psi_episodes(daily)
    episodes.to_csv(PROC_DIR / "psi_episodes.csv", index=False)
    plot_psi(daily)

    rain = load_rain()
    rain_days = rain_station_days(rain)
    rain_days.to_parquet(PROC_DIR / "rain_station_days.parquet", index=False)
    rain_month = rain_monthly(rain_days)
    rain_month.to_csv(PROC_DIR / "rain_monthly.csv", index=False)
    plot_rain(rain_days, rain)

    heat_days = pd.read_parquet(PROC_DIR / "wbgt_station_days.parquet")
    table = comparison(heat_days, rain_days, psi.assign(day=psi["day"]))
    table.to_csv(PROC_DIR / "peril_comparison.csv", index=False)

    print("PSI by year:\n" + yearly.to_string(index=False))
    print(
        "\nHaze episodes (island max 24-hour PSI > 100):\n"
        + (episodes.to_string(index=False) if len(episodes) else "none")
    )
    print("\nRain by month:\n" + rain_month.to_string(index=False))
    for t in HEAVY_HOUR_MM:
        print(
            f"Rain: station-days with a work hour >= {t} mm: "
            f"{(rain_days[f'hours_ge_{t}mm'] > 0).mean():.1%}"
        )
    print(
        f"Rain: average wet work hours (>= {WET_HOUR_MM} mm) per station-day: "
        f"{rain_days['wet_hours'].mean():.2f}"
    )
    print("\nComparison:\n" + table.to_string(index=False))


if __name__ == "__main__":
    main()
