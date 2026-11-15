"""Build the burn-analysis review PDF from the burn_analysis.py outputs.

Usage:
    uv run docs/reports/build_burn_report.py     (run scripts/burn_analysis.py first)

Reads  data/processed/burn_yearly_hero.csv, burn_yearly_island.csv, burn_daily_hero.csv
       data/processed/site_hazard_readings.csv, place_day_readings.npz, map_static.json
       api/default_tariff.json
       docs/figures/burn_hero_yearly.png, burn_2026_episode.png, burn_loss_ratio.png
Writes docs/reports/safeday-burn-analysis-2026-11-14.pdf
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from api import calculator, place_days  # noqa: E402
from api.burn import load_day_table  # noqa: E402
from api.main import load_sites  # noqa: E402
from api.models import Tariff, TierQuote  # noqa: E402
from api.readings import station_rule  # noqa: E402
from burn_analysis import DAILY_TAKINGS_SGD, HERO, PRODUCT, TIER  # noqa: E402

PROC = REPO_ROOT / "data" / "processed"
FIGS = REPO_ROOT / "docs" / "figures"
OUT = REPO_ROOT / "docs" / "reports" / "safeday-burn-analysis-2026-11-14.pdf"

INK = colors.HexColor("#191a1c")
INK2 = colors.HexColor("#45474b")
MUTED = colors.HexColor("#73716b")
ACCENT = colors.HexColor("#1c5cab")
LINE = colors.HexColor("#dcd9d0")
WASH = colors.HexColor("#f4f3ee")

S = {
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=INK),
    "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=11.5, leading=16, textColor=INK2),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=INK, spaceBefore=14, spaceAfter=5),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.8, leading=14.5, textColor=INK2, spaceAfter=6),
    "kpi_v": ParagraphStyle("kpi_v", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=ACCENT),
    "kpi_k": ParagraphStyle("kpi_k", fontName="Helvetica", fontSize=7.6, leading=10, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.6, leading=11, textColor=INK2),
    "foot": ParagraphStyle("foot", fontName="Helvetica", fontSize=7.6, leading=10.5, textColor=MUTED),
}


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def kpi_row(items: list[tuple[str, str]]) -> Table:
    cells = [[Paragraph(value, S["kpi_v"]), ] for value, _ in items]
    table = Table(
        [[Paragraph(v, S["kpi_v"]) for v, _ in items], [Paragraph(k, S["kpi_k"]) for _, k in items]],
        colWidths=[(170 * mm) / len(items)] * len(items),
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WASH),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


def data_table(header: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    body = [[Paragraph(f"<b>{h}</b>", S["cell"]) for h in header]]
    body += [[Paragraph(str(c), S["cell"]) for c in row] for row in rows]
    table = Table(body, colWidths=[w * mm for w in widths])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def money(value: float) -> str:
    return f"S${value:,.0f}"


def hero_quote(tariff: Tariff, replay: calculator.Replay, region: str) -> list[TierQuote]:
    """Every tier as a stall at the hero centre is quoted and charged (api/main.py
    business_quote): the centre's own replay, read on the stations a payout reads."""
    return calculator.quote(tariff, PRODUCT, region, replay).tiers


def haze_what_if(tariff: Tariff, replay: calculator.Replay, region: str) -> tuple[float, float]:
    """The hero's 2026 payout and weekly premium at TIER with haze severities 0.5/0.8/1.0,
    the tariff desk's one knob that most changes what haze pays."""
    raised = tariff.model_copy(deep=True)
    haze = calculator.find(raised.hazards, "haze", "hazard")
    for band, severity in zip(haze.bands, (0.5, 0.8, 1.0), strict=True):
        band.severity = severity
    tier = calculator.find(raised.tiers, TIER, "tier")
    losses = calculator.replay_losses(raised, calculator.find(raised.products, PRODUCT, "product"), replay)
    paid_2026 = calculator.paid_years(losses, tier)[2026][0]
    weekly = next(t for t in hero_quote(raised, replay, region) if t.tier == TIER).weekly_premium_sgd
    return paid_2026, weekly


def build() -> None:
    hero = pd.read_csv(PROC / "burn_yearly_hero.csv")
    island = pd.read_csv(PROC / "burn_yearly_island.csv")
    daily = pd.read_csv(PROC / "burn_daily_hero.csv")
    full = hero[(hero.year >= 2017) & (hero.year <= 2026)]
    paid, lost = full.payout_sgd.sum(), full.est_lost_sgd.sum()
    premium = full.premium_sgd.sum()
    island_2026 = island[island.year == 2026].iloc[0]
    hero_2026 = hero[hero.year == 2026].iloc[0]
    # Loss ratios are payouts over the premium before GST, as scripts/burn_analysis.py writes them.
    lr10 = paid / full.premium_before_gst_sgd.sum()
    lr_all = hero.payout_sgd.sum() / hero.premium_before_gst_sgd.sum()
    island_lr = island_2026.payout_sgd / island_2026.premium_pool_before_gst_sgd
    streak = daily[(daily.day >= "2026-10-03") & (daily.day <= "2026-10-25") & (daily.payout_sgd > 0)]

    tariff = Tariff.model_validate_json((REPO_ROOT / "api" / "default_tariff.json").read_text())
    sites = load_sites(PROC / "site_hazard_readings.csv")
    replays = place_days.PlaceDays(sites, load_day_table, place_days.PLACE_DAYS_PATH)
    static = json.loads((PROC / "map_static.json").read_text())
    centre = next(c for c in static["hawker_centres"] if c["name"] == HERO)
    replay = replays.replay(station_rule(tariff), centre["region"], centre["lat"], centre["lng"])
    tiers = hero_quote(tariff, replay, centre["region"])
    tier = next(t for t in tiers if t.tier == TIER)
    shares = calculator.find(tariff.tiers, TIER, "tier").premium_shares
    limit_days = round(tier.max_payout_per_year_sgd / tier.daily_payout_sgd)
    what_if_2026, what_if_weekly = haze_what_if(tariff, replay, centre["region"])
    first_day = pd.Timestamp(replays.days[0]).strftime("%b %Y")
    last_day = pd.Timestamp(replays.days[-1]).strftime("%b %Y")

    years_paid = int((full.payout_sgd > 0).sum())
    worst_island = island.loc[(island.payout_sgd / island.premium_pool_before_gst_sgd).idxmax()]
    worst_island_lr = worst_island.payout_sgd / worst_island.premium_pool_before_gst_sgd
    story = [
        Spacer(1, 8 * mm),
        para("SafeDay burn analysis", "title"),
        para("Every recorded day of Singapore's real weather, priced day by day through the live "
             "tariff. What one hawker stall lost, what SafeDay would have paid, and what the whole "
             "book would have carried. For team and Income review before it goes onto the risk "
             "atlas.", "subtitle"),
        Spacer(1, 5 * mm),
        kpi_row([
            (f"{len(replays.days):,}", f"days of NEA readings replayed, {first_day} to {last_day}"),
            (f"{int(hero_2026.trigger_days)}", "payable days for the hero stall in 2026 alone"),
            (f"{lr10:.0%}", "ten-year loss ratio, 2017-26 (APAC microinsurance median: 29.8%)"),
            (f"{island_lr:.0%}", "island loss ratio in 2026, the worst haze year since 2015"),
        ]),
        Spacer(1, 4 * mm),
        para("The one-line verdict: on every day that NEA's own readings crossed a trigger since "
             f"2017, this product would have paid, automatically, including {len(streak)} payable "
             "days inside the record 23-day haze streak of October 2026. Over the decade, premiums "
             f"cover payouts with room to spare ({lr10:.0%}); the 2026 season alone slightly "
             f"outruns its own year's pool ({island_lr:.0%}), which is the scenario the "
             "reinsurance share of each premium is there for. The schemes in the brief that died "
             "(SEWA 2023, ZhongAn) died because their first season paid nothing. Ours would have "
             f"paid in {years_paid} of the last {len(full)} years."),

        para("Why a burn analysis", "h2"),
        para("The problem statement is explicit: <i>back-test the trigger: show, from past NEA and "
             "PUB data, how often target customers would have lost income or property with no "
             "payout.</i> A burn analysis is the standard actuarial way to do that: run the exact "
             "product over the exact recorded history and count the dollars. Nothing here is "
             "modelled weather; every reading is what NEA actually published."),
        para(f"Method, in five steps: (1) take every day's readings since {first_day}: each haze "
             "zone's 24-hour PSI, each gauge's wettest work hour, each station's hours at WBGT "
             "32&nbsp;°C or more; (2) for each of the 103 hawker centres, read the stations a "
             "payout there reads, the same stations its price reads; (3) score each day with the "
             "live tariff's own calculator, exactly as a real claim would be scored; (4) pay the "
             "day's loss score times the tier payout, until the tier's yearly limit; (5) charge "
             "the premium the pricing API quotes a stall at that centre today. Hero case: one "
             f"cooked-food stall at {HERO}, {tier.label} "
             f"(S${tier.daily_payout_sgd:.0f} per bad day, {limit_days}-day yearly limit, "
             f"S${tier.weekly_premium_sgd:.2f} a week)."),

        para("One stall, ten years, dollar for dollar", "h2"),
        Image(str(FIGS / "burn_hero_yearly.png"), width=170 * mm, height=85 * mm),
        Spacer(1, 2 * mm),
    ]

    rows = [[int(r.year), int(r.trigger_days), money(r.payout_sgd), money(r.est_lost_sgd),
             money(r.premium_sgd), f"{r.loss_ratio:.0%}"] for r in full.itertuples()]
    rows.append(["2017-26", int(full.trigger_days.sum()), money(paid), money(lost),
                 money(premium), f"{lr10:.0%}"])
    story += [
        data_table(["Year", "Payable days", "Paid", "Est. revenue lost", "Premium",
                    "Loss ratio (before GST)"], rows, [18, 24, 28, 36, 30, 34]),
        Spacer(1, 2 * mm),
        para("Estimated losses use the tariff's own loss score times "
             f"S${DAILY_TAKINGS_SGD:.0f}-a-day takings, the midpoint of the only available range "
             "(S$400-800, triangulated from MSE cost replies; no official takings figure exists). "
             "The premium column includes GST; the loss ratio is paid over the premium before "
             f"GST. The stall would have been paid in {years_paid} of the {len(full)} years. That "
             "is the single most important line in this document: a parametric product whose "
             "back-test shows zero-payout years loses its customers in year one.", "foot"),

        para("2026: the catastrophe year, day by day", "h2"),
        Image(str(FIGS / "burn_2026_episode.png"), width=170 * mm, height=68 * mm),
        Spacer(1, 2 * mm),
        para(f"The 2026 haze season put {money(island_2026.est_lost_sgd)} of estimated revenue "
             f"losses across all {int(island_2026.stalls):,} stalls. SafeDay would have paid "
             f"{money(island_2026.payout_sgd)} against a premium pool of "
             f"{money(island_2026.premium_pool_before_gst_sgd)} before GST: a {island_lr:.0%} "
             "loss ratio in the worst haze year since 2015. One season slightly exceeding its "
             f"own year's premium is what the {shares.reinsurance:.0%} reinsurance share of each "
             "premium exists to absorb, and the yearly limits kept the overrun small; across the "
             "ten years the book stays profitable. That is what the brief means by keeping mass "
             "events insurable."),
        para("Speed is the other half. SEWA's 2024 payouts took six to eight weeks; BlockBima "
             "settled in a day and kept 86% preference. SafeDay's trigger is the same NEA feed the "
             f"public already watches, so every one of those {int(hero_2026.trigger_days)} payable "
             "days would have paid the same day, while the stall's rent (median S$1,250 a month) "
             "kept falling due."),

        para("Is the price right?", "h2"),
        Image(str(FIGS / "burn_loss_ratio.png"), width=170 * mm, height=68 * mm),
        Spacer(1, 2 * mm),
        para(f"A ten-year loss ratio of {lr10:.0%} ({lr_all:.0%} over every year since 2014, with "
             "the 2015 haze) sits above the Asia-Pacific microinsurance median of 29.8% (global "
             "median 21.7%; Landscape of Microinsurance 2023), with 2026 reaching "
             f"{island_lr:.0%} island-wide. {tier.label} is priced so expected payouts are "
             f"{shares.expected_payouts:.0%} of the premium before GST; the rest is reinsurance "
             f"{shares.reinsurance:.0%}, management {shares.management:.0%}, distribution "
             f"{shares.distribution:.0%} and profit {shares.profit:.0%}. The burn pays less than "
             f"{shares.expected_payouts:.0%} mainly because the price charges heat in every year at its "
             "2025-26 rate, while the burn can only pay heat where WBGT was recorded. In plain "
             "words: the premium is neither a rip-off nor fat. The tariff desk can move every "
             "number in this paragraph, and this same burn re-runs after every change. Each "
             "centre is priced on the stations its payouts read, so two centres in one zone do "
             "not pay identical rates."),

        para("What a stall actually gets, honestly", "h2"),
        para(f"{tier.label} insures S${tier.daily_payout_sgd:.0f} of a roughly "
             f"S${DAILY_TAKINGS_SGD:.0f} day: a liquidity floor of "
             f"{tier.daily_payout_sgd / DAILY_TAKINGS_SGD:.0%}, not full indemnity. That is the design, priced at a few dollars a "
             "week as the brief demands; the ladder below is the customer's lever. In 2026 the "
             f"stall would have been paid {money(hero_2026.payout_sgd)}, well inside its "
             f"{money(tier.max_payout_per_year_sgd)} yearly limit. A what-if that raises haze "
             f"severities to 0.5/0.8/1.0 lifts 2026 to {money(what_if_2026)} for "
             f"S${what_if_weekly - tier.weekly_premium_sgd:.2f} a week more premium."),
    ]

    tier_rows = [[t.label, money(t.daily_payout_sgd),
                  f"{round(t.max_payout_per_year_sgd / t.daily_payout_sgd)} days",
                  money(t.max_payout_per_year_sgd), f"S${t.weekly_premium_sgd:.2f}",
                  f"{t.cover_multiple}x" + (" (best value)" if t.best_value else ""),
                  f"{t.daily_payout_sgd / DAILY_TAKINGS_SGD:.0%}"] for t in tiers]
    story += [
        data_table(["Tier", "Per bad day", "Yearly limit", "Max a year",
                    f"Weekly premium ({HERO})", "Cover for each S$1", "Share of a S$500 day"],
                   tier_rows, [16, 20, 20, 22, 34, 32, 26]),
        PageBreak(),

        para("The stakes, in other people's numbers", "h2"),
        para("Every figure below is from this project's cited research; none is ours."),
        para("<b>Haze.</b> The 2026 episode: 39 unhealthy days, 23 consecutive, PSI peak 230 (NEA "
             "data in this repo); estimated national cost S$2.32 billion, surpassing 2015's "
             "S$1.83 billion (NTU economists, 8 Nov 2026). The 2015 regional haze was associated "
             "with roughly 2,200 modelled excess deaths in Singapore (Koplitz et al. 2016, "
             "Environmental Research Letters; a model estimate, not a death registry count)."),
        para("<b>Heat.</b> Heat already removes about 11.3% of outdoor productive working time, "
             "roughly S$1.18 billion for 2018 and projected S$2.22 billion a year by 2035 (Project "
             "HeatSafe, NUS, 2024). MOM's mandatory rest breaks from 1 Dec 2026 formalise the "
             "income loss for the self-employed."),
        para("<b>The people.</b> About 6,500 cooked-food stalls; hawkers' median age is 60 and "
             "their typical income sits in the second-lowest decile (MSE, 2024). Two-thirds hold "
             "insurance, but it is fire and liability cover; no product pays for weather-driven "
             "income loss (MSE parliamentary reply, 4 Aug 2026). Across SMEs, 74% fear business "
             "interruption and 23% are covered for it (QBE Singapore, 2024-25). 71,600 residents "
             "are regular platform workers (MOM, 2025). Flash floods: about 7 days a year "
             "island-wide (PUB records 2017-2023, Li et al. 2024)."),

        para("What this proves against the brief", "h2"),
        para("<b>Back-tested trigger:</b> shown above, dollar for dollar, ten years. "
             f"<b>Pays when it matters:</b> payouts in {years_paid} of {len(full)} years and "
             f"{len(streak)} payable days inside the record streak. <b>Affordable:</b> the hero "
             f"stall's {tier.label} is S${tier.weekly_premium_sgd:.2f} a week at its own centre. "
             f"<b>Mass events stay insurable:</b> the worst island year, {int(worst_island.year)}, "
             f"ran at a {worst_island_lr:.0%} loss ratio under yearly limits and the reinsurance "
             "share. <b>Independent, verifiable data:</b> every input is a published NEA reading. "
             "<b>Explainable:</b> the same engine that priced this document prices the website, "
             "the map and the tariff desk."),

        para("Honest limitations", "h2"),
        para("(1) No claims data exists anywhere, so estimated losses are the tariff's own loss "
             "score times assumed takings; the comparison shows scale, not independently measured "
             "damage. (2) Real WBGT begins Jan 2025, so heat pays only in 2025-26 here; the ML "
             "back-test's reconstructed heat (1980 on) is the follow-up. (3) Flood is priced at "
             "zero assumed days pending a payout-grade PUB history; the live PUB alert feed is "
             f"already wired. (4) Takings of S${DAILY_TAKINGS_SGD:.0f} a day is an assumption; "
             "every loss figure scales linearly with it. (5) Losses below trigger levels are "
             "uncovered by design and are disclosed at the point of sale."),

        para("Next step", "h2"),
        para("After this review: wire the burn into the risk atlas, so clicking any centre shows "
             "its own ten-year lost-vs-paid record, and the replay-a-day picker shows the payout "
             "that date would have produced, live beside today's readings."),
        Spacer(1, 4 * mm),
        para("SafeDay burn analysis, rebuilt 15 Nov 2026. Data: NEA via data.gov.sg (Singapore "
             "Open Data Licence), MSS daily records, PUB. Engine: api/calculator.py at the current "
             "default tariff. Reproduce: uv run scripts/build_place_years.py, uv run "
             "scripts/burn_analysis.py, then this script.", "foot"),
    ]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="SafeDay burn analysis")
    doc.build(story)
    print(f"Wrote {OUT.relative_to(REPO_ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
