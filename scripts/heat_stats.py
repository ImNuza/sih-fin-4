"""First look at NEA WBGT data: how often does heat reach the MOM 32°C rest-break level?

Usage:
    uv run scripts/heat_stats.py

Reads  data/wbgt/*.parquet  (from fetch_wbgt.py)
Writes data/processed/wbgt_station_days.parquet   one row per station per day
       data/processed/wbgt_monthly.csv
       data/processed/wbgt_stations.csv
       docs/figures/wbgt_trigger_days_by_month.png
       docs/figures/wbgt_trigger_share_by_station.png
"""

from __future__ import annotations

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dgs import REPO_ROOT

WORK_START_HOUR = 7   # 07:00 SGT
WORK_END_HOUR = 19    # until 19:00 SGT
READING_HOURS = 0.25  # one reading = 15 minutes
THRESHOLDS = (31, 32, 33)
MOM_THRESHOLD = 32    # MOM: paid 10-minute rest break every hour for heavy work at WBGT >= 32°C

IN_DIR = REPO_ROOT / "data" / "wbgt"
PROC_DIR = REPO_ROOT / "data" / "processed"
FIG_DIR = REPO_ROOT / "docs" / "figures"

# Chart style (dataviz reference palette, light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e6e5e1"
BAR = "#2a78d6"


CORE_COVERAGE = 0.95  # a "core" station has data on at least 95% of days


def load_readings() -> pd.DataFrame:
    frame = pd.concat(pd.read_parquet(p) for p in sorted(IN_DIR.glob("wbgt_*.parquet")))
    frame["timestamp"] = frame["timestamp"].dt.tz_convert("Asia/Singapore")
    # Stations get renamed (S135: Mandai Wildlife Reserve -> Bird Paradise). Use the latest name per ID.
    latest = frame.sort_values("timestamp").groupby("station_id")["station_name"].last()
    frame["station_name"] = frame["station_id"].map(latest)
    frame["day"] = frame["timestamp"].dt.date
    hour = frame["timestamp"].dt.hour
    frame["work_hours"] = (hour >= WORK_START_HOUR) & (hour < WORK_END_HOUR)
    return frame


def station_days(readings: pd.DataFrame) -> pd.DataFrame:
    work = readings[readings["work_hours"]].copy()
    for t in THRESHOLDS:
        work[f"hours_ge_{t}"] = (work["wbgt"] >= t) * READING_HOURS
    grouped = work.groupby(["station_id", "station_name", "day"])
    days = grouped.agg(
        max_wbgt=("wbgt", "max"),
        readings=("wbgt", "count"),
        **{f"hours_ge_{t}": (f"hours_ge_{t}", "sum") for t in THRESHOLDS},
    ).reset_index()
    days["day"] = pd.to_datetime(days["day"])
    return days


def core_station_ids(days: pd.DataFrame) -> list[str]:
    """Stations that report on nearly every day, so counts stay comparable as the network grows."""
    coverage = days.groupby("station_id")["day"].nunique() / days["day"].nunique()
    return sorted(coverage[coverage >= CORE_COVERAGE].index)


def monthly(days: pd.DataFrame, core_ids: list[str]) -> pd.DataFrame:
    core = days[days["station_id"].isin(core_ids)]
    island = core.groupby("day").agg(max_wbgt=("max_wbgt", "max")).reset_index()
    island["month"] = island["day"].dt.to_period("M").astype(str)
    out = island.groupby("month").agg(days_with_data=("day", "count"))
    for t in THRESHOLDS:
        out[f"days_core_ge_{t}"] = island.assign(hit=island["max_wbgt"] >= t).groupby("month")["hit"].sum()
    core = core.assign(month=core["day"].dt.to_period("M").astype(str))
    out["avg_hours_ge_32_per_station_day"] = core.groupby("month")["hours_ge_32"].mean().round(2)
    out["stations_reporting"] = days.assign(month=days["day"].dt.to_period("M").astype(str)).groupby("month")["station_id"].nunique()
    return out.reset_index()


def hours_distribution(days: pd.DataFrame, core_ids: list[str]) -> pd.Series:
    """How long the heat lasts: share of core station-days by hours at WBGT >= 32."""
    hours = days[days["station_id"].isin(core_ids)]["hours_ge_32"]
    bins = {"0 h": hours == 0, "under 1 h": (hours > 0) & (hours < 1), "1 to 2 h": (hours >= 1) & (hours < 2),
            "2 to 4 h": (hours >= 2) & (hours < 4), "4 h or more": hours >= 4}
    return pd.Series({k: round(v.mean() * 100, 1) for k, v in bins.items()}, name="% of station-days")


def stations(days: pd.DataFrame) -> pd.DataFrame:
    out = days.groupby(["station_id", "station_name"], as_index=False).agg(
        days_with_data=("day", "count"),
        days_ge_32=("max_wbgt", lambda s: int((s >= MOM_THRESHOLD).sum())),
        total_hours_ge_32=("hours_ge_32", "sum"),
        max_wbgt=("max_wbgt", "max"),
    )
    out["share_days_ge_32"] = (out["days_ge_32"] / out["days_with_data"]).round(3)
    return out.sort_values("share_days_ge_32", ascending=False)


def style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK_2, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_monthly(month_table: pd.DataFrame, core_count: int) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor=SURFACE)
    style_axes(ax)
    labels = pd.PeriodIndex(month_table["month"], freq="M").strftime("%b\n%y")
    values = month_table["days_core_ge_32"]
    bars = ax.bar(range(len(values)), values, width=0.6, color=BAR, edgecolor=SURFACE, linewidth=2)
    ax.set_xticks(range(len(values)), labels, fontsize=9)
    for bar, value in zip(bars, values):
        if value > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.4, f"{int(value)}",
                    ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_ylabel("days", color=INK_2)
    fig.suptitle("Days when WBGT reached 32°C at one or more NEA stations (7am to 7pm)",
                 x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
    ax.set_title(f"MOM rest-break level. The {core_count} stations that reported all period. "
                 "Jan 2025 and Nov 2026 are partial months.",
                 loc="left", fontsize=9, color=INK_2)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "wbgt_trigger_days_by_month.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


MIN_DAYS_FOR_STATION_CHART = 365  # newer stations only cover recent months, which skews their share


def plot_stations(station_table: pd.DataFrame) -> None:
    table = station_table[station_table["days_with_data"] >= MIN_DAYS_FOR_STATION_CHART]
    table = table.sort_values("share_days_ge_32")
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(table) + 1.6), facecolor=SURFACE)
    style_axes(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines["bottom"].set_visible(False)
    names = table["station_name"]
    values = table["share_days_ge_32"] * 100
    bars = ax.barh(range(len(values)), values, height=0.55, color=BAR, edgecolor=SURFACE, linewidth=2)
    ax.set_yticks(range(len(values)), names, fontsize=9)
    for bar, value in zip(bars, values):
        ax.text(value + 0.5, bar.get_y() + bar.get_height() / 2, f"{value:.0f}%",
                va="center", fontsize=8, color=INK_2)
    ax.set_xlabel("% of days with data", color=INK_2)
    fig.suptitle("Share of days reaching WBGT 32°C, by station (7am to 7pm)",
                 x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
    ax.set_title(f"Stations with at least {MIN_DAYS_FOR_STATION_CHART} days of data. "
                 "Full list in data/processed/wbgt_stations.csv.", loc="left", fontsize=9, color=INK_2)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "wbgt_trigger_share_by_station.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    readings = load_readings()
    days = station_days(readings)
    days.to_parquet(PROC_DIR / "wbgt_station_days.parquet", index=False)
    core_ids = core_station_ids(days)
    month_table = monthly(days, core_ids)
    month_table.to_csv(PROC_DIR / "wbgt_monthly.csv", index=False)
    station_table = stations(days)
    station_table.to_csv(PROC_DIR / "wbgt_stations.csv", index=False)
    hours = hours_distribution(days, core_ids)
    plot_monthly(month_table, len(core_ids))
    plot_stations(station_table)

    first, last = readings["timestamp"].min(), readings["timestamp"].max()
    missing = readings["wbgt"].isna().mean()
    core = days[days["station_id"].isin(core_ids)]
    island_days = core.groupby("day")["max_wbgt"].max()
    print(f"Readings: {len(readings):,} from {first:%Y-%m-%d} to {last:%Y-%m-%d}, "
          f"{readings['station_id'].nunique()} stations ever, {missing:.2%} missing")
    print(f"Core stations ({len(core_ids)}): {', '.join(core_ids)}")
    print(f"Days with data: {len(island_days)}")
    for t in THRESHOLDS:
        any_core = (island_days >= t).mean()
        per_station = (core["max_wbgt"] >= t).mean()
        print(f"  >= {t}°C in work hours: {any_core:.0%} of days at any core station, "
              f"{per_station:.0%} of days at a typical single station")
    print(f"Highest WBGT seen: {readings['wbgt'].max()}°C")
    print("\nHours at WBGT >= 32 per core station-day:\n" + hours.to_string())
    print("\nMonthly (core stations):\n" + month_table.to_string(index=False))
    print("\nStations:\n" + station_table.to_string(index=False))


if __name__ == "__main__":
    main()
