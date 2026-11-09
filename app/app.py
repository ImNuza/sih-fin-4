"""SIH 2026 Fin 4: climate data explorer for Income's parametric insurance brief.

Run:  uv run streamlit run app/app.py
Set SIH_LIVE_DATA=off to turn off the Live tab (the hosted copy has no internet and no API key).
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st

import data

BLUE = "#2a78d6"
SEQ_BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
MAP_CENTER = {"lat": 1.355, "lon": 103.82}
LIVE_DATA = os.environ.get("SIH_LIVE_DATA", "on") != "off"

st.set_page_config(
    page_title="Fin 4 climate data", page_icon=":material/thermostat:", layout="wide"
)


def bar(frame: pd.DataFrame, x: str, y: str, y_title: str, hover: dict | None = None):
    fig = px.bar(frame, x=x, y=y, hover_data=hover)
    fig.update_traces(marker_color=BLUE, marker_line_width=0)
    fig.update_layout(
        bargap=0.35,
        xaxis_title=None,
        yaxis_title=y_title,
        margin=dict(t=10, b=10, l=10, r=10),
        height=340,
    )
    return fig


def station_map(frame: pd.DataFrame, color: str, color_title: str, hover_name: str, hover: dict):
    fig = px.scatter_map(
        frame,
        lat="latitude",
        lon="longitude",
        color=color,
        size_max=14,
        hover_name=hover_name,
        hover_data=hover,
        color_continuous_scale=SEQ_BLUES,
        center=MAP_CENTER,
        zoom=9.6,
        height=420,
    )
    fig.update_traces(marker=dict(size=13))
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), coloraxis_colorbar=dict(title=color_title))
    return fig


def per_month(hits: pd.DataFrame, value: str) -> pd.DataFrame:
    out = hits.assign(month=hits["day"].dt.to_period("M").dt.to_timestamp())
    return out.groupby("month")[value].mean().mul(100).round(1).reset_index()


st.title("Fin 4 climate data explorer")
st.caption(
    "Real NEA data from data.gov.sg. Heat (WBGT) from Jan 2025, rain from Dec 2016, "
    "haze (PSI) from Mar 2016. "
    "Work hours are 7am to 7pm."
)

tabs = st.tabs(["Overview", "Heat", "Rain", "Haze", "Trigger & price", "Live now"])

# ---------------- Overview ----------------
with tabs[0]:
    path = data.DATA / "processed" / "peril_comparison.csv"
    if path.exists():
        comp = pd.read_csv(path)
        st.subheader("How often does each peril happen?")
        shown = comp.rename(
            columns={
                "peril": "Peril",
                "period": "Period",
                "share_days_one_location": "Days at one location",
                "share_days_anywhere": "Days anywhere in Singapore",
                "share_of_locations_hit_on_event_days": "Share of locations hit on an event day",
            }
        )
        st.dataframe(
            shown,
            hide_index=True,
            use_container_width=True,
            column_config={
                c: st.column_config.ProgressColumn(c, format="percent", min_value=0, max_value=1)
                for c in [
                    "Days at one location",
                    "Days anywhere in Singapore",
                    "Share of locations hit on an event day",
                ]
            },
        )
        st.markdown(
            "- **Days at one location** is what one insured person or shop would see.\n"
            "- **Share of locations hit** near 100% means the peril hits the whole island at once. "
            "That is the capital risk the brief warns about."
        )
    else:
        st.info("Run `uv run scripts/hazard_stats.py` to build the comparison table.")
    st.markdown(
        "**Data notes:** the WBGT network grew from 8 to 30 stations in 2025 to 2026. "
        "Heat comparisons over time use the 7 stations that reported all period."
    )

# ---------------- Heat ----------------
with tabs[1]:
    left, right = st.columns([1, 3])
    threshold = left.slider(
        "WBGT level (°C)",
        30.0,
        34.0,
        32.0,
        0.5,
        key="heat_t",
        help="MOM: paid 10-minute rest break every hour for heavy outdoor work at 32°C and above.",
    )
    min_hours = left.select_slider(
        "Hours at or above, per day", [0.25, 0.5, 1.0, 2.0, 3.0, 4.0], value=0.25, key="heat_h"
    )
    days = data.heat_station_days(threshold)
    days["hit"] = days["hours_at_or_above"] >= min_hours
    stations = data.wbgt_stations()
    by_station = days.groupby("station_id")["hit"].agg(["mean", "sum", "count"]).reset_index()
    by_station = by_station.merge(stations, on="station_id")
    by_station["share_pct"] = (by_station["mean"] * 100).round(1)
    by_station["days_per_year"] = (by_station["mean"] * 365).round(0)
    core = stations[stations["days"] >= 0.95 * days["day"].nunique()]["station_id"]
    left.metric(
        "Typical station, days a year",
        f"{by_station[by_station.station_id.isin(core)]['days_per_year'].median():.0f}",
    )
    left.caption("Median of the 7 stations that reported all period.")
    with right:
        st.markdown(
            f"**Share of work days with {min_hours:g} h or more at WBGT ≥ {threshold:g}°C**"
        )
        st.plotly_chart(
            station_map(
                by_station,
                "share_pct",
                "% of days",
                "station_name",
                {
                    "share_pct": True,
                    "days_per_year": True,
                    "count": True,
                    "latitude": False,
                    "longitude": False,
                },
            ),
            use_container_width=True,
        )
    st.markdown("**By month, 7 core stations (% of station-days)**")
    monthly = per_month(days[days["station_id"].isin(core)], "hit")
    st.plotly_chart(bar(monthly, "month", "hit", "% of station-days"), use_container_width=True)
    pick = st.selectbox(
        "One station over time", sorted(stations["station_name"]), index=0, key="heat_station"
    )
    sid = stations.loc[stations["station_name"] == pick, "station_id"].iloc[0]
    one = days[days["station_id"] == sid]
    fig = px.line(
        one, x="day", y="max_wbgt", labels={"max_wbgt": "max WBGT in work hours (°C)", "day": ""}
    )
    fig.update_traces(line_color=BLUE, line_width=1.5)
    fig.add_hline(y=threshold, line_dash="dash", line_color="#898781")
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- Rain ----------------
with tabs[2]:
    if data.rain_hourly().empty:
        st.info("Rain data is not downloaded yet. Run `uv run scripts/fetch_rainfall.py`.")
    else:
        left, right = st.columns([1, 3])
        mm = left.select_slider(
            "Rain in one hour (mm)",
            [5, 10, 20, 30, 50],
            value=20,
            key="rain_mm",
            help="20 mm in an hour is a heavy downpour that stops outdoor work and deliveries.",
        )
        min_hours = left.select_slider(
            "Hours at or above, per day", [1, 2, 3], value=1, key="rain_h"
        )
        days = data.rain_station_days(mm)
        days["hit"] = days["hours_at_or_above"] >= min_hours
        stations = data.rain_stations()
        by_station = (
            days.groupby("station_id")["hit"]
            .agg(["mean", "count"])
            .reset_index()
            .merge(stations, on="station_id")
        )
        by_station["share_pct"] = (by_station["mean"] * 100).round(1)
        by_station["days_per_year"] = (by_station["mean"] * 365).round(0)
        left.metric("Typical station, days a year", f"{by_station['days_per_year'].median():.0f}")
        with right:
            st.markdown(f"**Share of work days with {min_hours} h or more of rain ≥ {mm} mm/h**")
            st.plotly_chart(
                station_map(
                    by_station,
                    "share_pct",
                    "% of days",
                    "station_name",
                    {
                        "share_pct": True,
                        "days_per_year": True,
                        "latitude": False,
                        "longitude": False,
                    },
                ),
                use_container_width=True,
            )
        st.markdown("**By month, all stations (% of station-days)**")
        st.plotly_chart(
            bar(per_month(days, "hit"), "month", "hit", "% of station-days"),
            use_container_width=True,
        )
        spread = days.groupby("day")["hit"].agg(["sum", "count"])
        spread = spread[spread["sum"] > 0]
        if len(spread):
            st.caption(
                "On a day with heavy rain somewhere, on average "
                f"{(spread['sum'] / spread['count']).mean():.0%} "
                "of stations are hit. Rain is local, unlike haze."
            )

# ---------------- Haze ----------------
with tabs[3]:
    region_days = data.psi_region_days()
    island = region_days.groupby("day")["psi_max"].max().reset_index()
    level = st.select_slider(
        "24-hour PSI level",
        [100, 150, 200, 300],
        value=100,
        key="psi_level",
        help="NEA bands: 101 to 200 unhealthy, 201 to 300 very unhealthy, above 300 hazardous.",
    )
    fig = px.line(
        island, x="day", y="psi_max", labels={"psi_max": "highest 24-hour PSI", "day": ""}
    )
    fig.update_traces(line_color=BLUE, line_width=1.2)
    fig.add_hline(y=level, line_dash="dash", line_color="#898781")
    fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)
    yearly = (
        island.assign(year=island["day"].dt.year, hit=island["psi_max"] > level)
        .groupby("year")["hit"]
        .sum()
        .reset_index()
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Days with PSI above {level}, by year**")
        st.plotly_chart(bar(yearly, "year", "hit", "days"), use_container_width=True)
    with c2:
        st.markdown("**Haze episodes (PSI above 100 on consecutive days)**")
        ep_path = data.DATA / "processed" / "psi_episodes.csv"
        if ep_path.exists():
            st.dataframe(
                pd.read_csv(ep_path).sort_values("start", ascending=False),
                hide_index=True,
                use_container_width=True,
            )
        hit_days = region_days[region_days["psi_max"] > level].groupby("day")["region"].nunique()
        if len(hit_days):
            st.caption(
                f"On days above {level}, on average {hit_days.mean():.1f} of 5 regions "
                "are above it. "
                "Haze hits the whole island at once."
            )

# ---------------- Trigger & price ----------------
with tabs[4]:
    st.markdown(
        "Pick a trigger and a payout. The app counts how often the trigger fired in the real data, "
        "then prices it. **Indicative only, not an actuarial price.**"
    )
    a, b, c = st.columns(3)
    peril = a.radio("Peril", ["Heat", "Rain", "Haze"], horizontal=True)
    if peril == "Heat":
        stations = data.wbgt_stations()
        place = a.selectbox("Station", sorted(stations["station_name"]), key="p_heat_station")
        t = a.slider("WBGT level (°C)", 30.0, 34.0, 32.0, 0.5, key="p_heat_t")
        h = a.select_slider(
            "Hours at or above", [0.25, 0.5, 1.0, 2.0, 3.0], value=2.0, key="p_heat_h"
        )
        sid = stations.loc[stations["station_name"] == place, "station_id"].iloc[0]
        d = data.heat_station_days(t)
        d = d[d["station_id"] == sid].assign(hit=lambda f: f["hours_at_or_above"] >= h)
        rule = f"WBGT ≥ {t:g}°C for {h:g} h or more, 7am to 7pm, at {place}"
    elif peril == "Rain":
        stations = data.rain_stations()
        if stations.empty:
            st.stop()
        place = a.selectbox("Station", sorted(stations["station_name"]), key="p_rain_station")
        mm = a.select_slider(
            "Rain in one hour (mm)", [5, 10, 20, 30, 50], value=20, key="p_rain_mm"
        )
        h = a.select_slider("Hours at or above", [1, 2, 3], value=1, key="p_rain_h")
        sid = stations.loc[stations["station_name"] == place, "station_id"].iloc[0]
        d = data.rain_station_days(mm)
        d = d[d["station_id"] == sid].assign(hit=lambda f: f["hours_at_or_above"] >= h)
        rule = f"{h} h or more with ≥ {mm} mm/h, 7am to 7pm, at {place}"
    else:
        regions = data.psi_region_days()
        place = a.selectbox("Region", sorted(regions["region"].unique()), key="p_psi_region")
        lvl = a.select_slider(
            "24-hour PSI above", [100, 150, 200, 300], value=100, key="p_psi_level"
        )
        d = regions[regions["region"] == place].assign(hit=lambda f: f["psi_max"] > lvl)
        rule = f"24-hour PSI above {lvl} in the {place} region"

    payout = b.number_input("Payout per trigger day (S$)", 10, 500, 50, 10)
    cap = b.number_input("Max payable days per year", 1, 60, 10)
    expense = b.slider(
        "Expenses, % of premium",
        5,
        40,
        20,
        help="The brief says expenses should be about 20% of premium.",
    )
    margin = b.slider("Safety margin for bad years, %", 0, 100, 25)

    d = d.assign(year=d["day"].dt.year)
    per_year = (
        d.groupby("year").agg(days=("day", "nunique"), trigger_days=("hit", "sum")).reset_index()
    )
    full_years = per_year[per_year["days"] >= 300]
    rate = d["hit"].mean()  # share of days that triggered
    expected_days = rate * 365
    paid_days = min(expected_days, cap)
    expected_payout = paid_days * payout
    premium_year = expected_payout * (1 + margin / 100) / (1 - expense / 100)

    c.metric("Trigger days a year (history)", f"{expected_days:.1f}")
    c.metric("Expected payout a year", f"S${expected_payout:,.0f}")
    c.metric(
        "Premium a year",
        f"S${premium_year:,.0f}",
        help="Expected payout plus safety margin, then grossed up for expenses.",
    )
    c.metric("Premium a week", f"S${premium_year / 52:,.2f}")
    st.markdown(f"**Trigger:** {rule}. Pays S${payout} per day, up to {cap} days a year.")
    st.caption(
        f"Based on {d['day'].nunique():,} days of data. The cap applies to the average year, "
        "not to each year, so this price is approximate. "
        "A real price needs a longer back-test and Income's actuaries."
    )
    if len(full_years):
        st.markdown("**Trigger days in each year with 300+ days of data**")
        st.plotly_chart(bar(full_years, "year", "trigger_days", "days"), use_container_width=True)
    st.markdown("**Trigger days by month**")
    st.plotly_chart(
        bar(
            d.assign(month=d["day"].dt.to_period("M").dt.to_timestamp())
            .groupby("month")["hit"]
            .sum()
            .reset_index(),
            "month",
            "hit",
            "days",
        ),
        use_container_width=True,
    )

# ---------------- Live ----------------
with tabs[5]:
    if not LIVE_DATA:
        st.info("Live readings are off on this copy. Run the app locally to see them.")
        st.stop()
    st.markdown("Latest NEA readings. Refreshes at most every 10 minutes.")
    try:
        live = data.live_readings()
    except (Exception, SystemExit) as error:  # dgs exits when no API key is set
        st.error(f"Could not fetch live data: {error}")
        live = {}
    if "wbgt" in live:
        w = live["wbgt"]
        st.markdown(
            f"**Heat (WBGT) at {pd.to_datetime(w['time'].iloc[0]):%d %b %Y %H:%M}**. "
            f"Stations at 32°C or above: {(w['wbgt'] >= 32).sum()} of {len(w)}."
        )
        st.plotly_chart(
            station_map(
                w,
                "wbgt",
                "WBGT °C",
                "station",
                {
                    "wbgt": True,
                    "heat_stress": True,
                    "latitude": False,
                    "longitude": False,
                    "time": False,
                },
            ),
            use_container_width=True,
        )
    col1, col2 = st.columns(2)
    if "psi" in live:
        col1.markdown("**Haze: 24-hour PSI by region**")
        col1.dataframe(
            live["psi"][["region", "psi_24h"]], hide_index=True, use_container_width=True
        )
    if "rain" in live:
        r = live["rain"]
        col2.markdown(
            f"**Rain in the last 5 minutes**: {(r['rain_mm_5min'] > 0).sum()} of {len(r)} "
            "stations wet. "
            f"Max {r['rain_mm_5min'].max()} mm."
        )
