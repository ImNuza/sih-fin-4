#!/usr/bin/env python3
"""Build the Fin 4 climate findings digest from the slate template.

Reads the html-digest slate template and the four chart PNGs.
Writes one self-contained HTML file. Does not edit the template.
"""

import base64
from pathlib import Path

ROOT = Path("/Users/dewa/Documents/Projects/SIH/sih-fin-4")
TEMPLATE = Path("/Users/dewa/.claude/skills/html-digest/templates/slate.html")
OUT = ROOT / "docs/reports/fin4-climate-data-findings-2026-11-09.html"
FIG = ROOT / "docs/figures"

FIGURES = {
    "HEAT_MONTH": FIG / "wbgt_trigger_days_by_month.png",
    "HEAT_STATION": FIG / "wbgt_trigger_share_by_station.png",
    "RAIN_MONTH": FIG / "rain_heavy_days_by_month.png",
    "HAZE": FIG / "psi_daily_max_2016_2026.png",
}


def data_uri(path: Path) -> str:
    raw = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:image/png;base64," + raw


def figure(uri: str, caption: str, alt: str) -> str:
    return (
        "<figure class=\"shot\">"
        f"<a class=\"thumb\" data-lightbox href=\"{uri}\" data-caption=\"{caption}\">"
        f"<img src=\"{uri}\" alt=\"{alt}\">"
        "</a>"
        f"<figcaption>{caption}</figcaption>"
        "</figure>"
    )


def main() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    uris = {key: data_uri(path) for key, path in FIGURES.items()}
    figs = build_body_uris(uris)

    paint = """
.shots { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 16px; margin: 18px 0 8px; }
.shot { margin: 0; min-width: 0; }
.shots .thumb { float: none; width: 100%; max-width: none; margin: 0; }
.shots .thumb img { width: 100%; height: auto; }
.shot figcaption { margin-top: 8px; font-size: 13px; line-height: 1.45; color: var(--text-2); }
html.kit-phone .shots { grid-template-columns: minmax(0, 1fr); }
"""
    marker = "/* html-digest layout END */"
    if marker not in html:
        raise SystemExit("layout end marker missing")
    html = html.replace(marker, marker + paint, 1)

    html = html.replace(
        "<title>{{TITLE}}</title>",
        "<title>Fin 4 climate findings, 9 Nov 2026</title>",
        1,
    )
    html = html.replace(
        '<span class="kicker-date">{{DATE}}</span>',
        '<span class="kicker-date">9 Nov 2026</span>',
        1,
    )
    html = html.replace("<h1>{{HEADLINE}}</h1>", "<h1>" + H1 + "</h1>", 1)
    html = html.replace(
        '<p class="standfirst">{{STANDFIRST}}</p>',
        '<p class="standfirst">' + STANDFIRST + "</p>",
        1,
    )

    tiles_old = html.split("<!-- tiles BEGIN -->", 1)[1].split("<!-- tiles END -->", 1)[0]
    html = html.replace(
        "<!-- tiles BEGIN -->" + tiles_old + "<!-- tiles END -->",
        "<!-- tiles BEGIN -->\n" + TILES + "        <!-- tiles END -->",
        1,
    )

    toc_old_start = html.index('<nav class="toc"')
    toc_old_end = html.index("</nav>", toc_old_start) + len("</nav>")
    html = html[:toc_old_start] + TOC + html[toc_old_end:]

    content_old = html.split("<!-- content BEGIN -->", 1)[1].split("<!-- content END -->", 1)[0]
    body = BODY.format(**figs)
    html = html.replace(
        "<!-- content BEGIN -->" + content_old + "<!-- content END -->",
        "<!-- content BEGIN -->\n" + body + "<!-- content END -->",
        1,
    )
    html = html.replace(
        '<ol class="footnotes"><li id="fn1">{{SOURCE}}</li></ol>',
        FOOTNOTES,
        1,
    )

    if "{{" in html:
        raise SystemExit("unfilled placeholder remains")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(OUT)
    print(OUT.stat().st_size)

H1 = (
    "Heat is common but short. Rain is short and local. "
    "<em>Haze is rare</em>, but when it comes it covers the whole island "
    "and it can last weeks, as in October 2026."
)

STANDFIRST = (
    "We counted heat, rain and haze in NEA readings on data.gov.sg. "
    "Income wants a cover that pays when a public measurement passes a level. "
    "These counts show how often that happens."
)

TILES = """        <div class="tiles">
          <div class="tile" data-value="22" data-max="100" data-tone="accent"><div class="tile-num">22%</div><div class="tile-label">of days with heat at one station</div></div>
          <div class="tile" data-value="4.8" data-max="100" data-tone="accent"><div class="tile-num">4.8%</div><div class="tile-label">of days with heavy rain at one gauge</div></div>
          <div class="tile"><div class="tile-num">39</div><div class="tile-label">unhealthy haze days in 2026</div></div>
          <div class="tile"><div class="tile-num">23</div><div class="tile-label">days in the longest haze run, 3 to 25 Oct 2026</div></div>
        </div>
"""

TOC = """<nav class="toc" aria-label="Sections">
        <a href="#data">Data we used</a>
        <a href="#heat">Heat</a>
        <a href="#rain">Rain</a>
        <a href="#haze">Haze</a>
        <a href="#compare">Compare the three</a>
        <a href="#product">What this may mean</a>
        <a href="#decide">Decide at the meeting</a>
        <a href="#limits">Limits</a>
      </nav>"""

BODY = """      <section id="data">
        <h2>Data we used</h2>
        <p>Work hours are 7am to 7pm, Singapore time. WBGT is a heat stress index that combines temperature, humidity, sun and wind. PSI is a haze index. A parametric cover pays a fixed amount when a public measurement passes a level. It does not check each person's loss.</p>
        <p>NEA WBGT history starts in January 2025. Other NEA feeds start in 2016. All numbers are from scripts/heat_stats.py and scripts/hazard_stats.py.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th data-sort>Peril</th>
                <th data-sort>Measure</th>
                <th data-sort>Period</th>
                <th data-sort>Locations</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td data-val="Heat">Heat</td>
                <td data-val="WBGT every 15 minutes">WBGT (heat stress), every 15 minutes</td>
                <td data-val="2025-01-16">16 Jan 2025 to 7 Nov 2026 (661 days)</td>
                <td data-val="8">8 stations at the start, 30 at the end. Trends use the 7 stations that reported all period.</td>
              </tr>
              <tr>
                <td data-val="Rain">Rain</td>
                <td data-val="Rainfall every 5 minutes">Rainfall, every 5 minutes, summed per hour</td>
                <td data-val="2025-01-16">16 Jan 2025 to 8 Nov 2026</td>
                <td data-val="54">54 to 90 rain gauges per day (median 61)</td>
              </tr>
              <tr>
                <td data-val="Haze">Haze</td>
                <td data-val="24-hour PSI hourly">24-hour PSI, hourly</td>
                <td data-val="2016-03-09">9 Mar 2016 to 7 Nov 2026</td>
                <td data-val="5">5 regions</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section id="heat">
        <h2>Heat</h2>
        <ul>
          <li>WBGT reached 32°C, the MOM rest-break level, on 22% of days at a typical station. In the 7-station network, WBGT reached 32°C at one or more stations on 55% of days.</li>
          <li>The heat is short. On 78% of station-days, WBGT was under 32°C for the whole day. A station-day is one station on one day. When WBGT reached 32°C, it usually lasted under 1 hour. Only 3.2% of station-days had 2 hours or more at 32°C.</li>
          <li>The strong season is April to October, with 22 to 26 hot days a month. December to March had 1 to 15 hot days a month.</li>
          <li>Location matters. Among stations with a full year of data, Sentosa reached 32°C on 58% of days. Tuas reached 32°C on 0% of days.</li>
          <li>One app example pays S$50 a day, up to 10 days a year. It pays when WBGT is at 32°C or more for 2 hours at Bedok. The trigger was true on about 7 days a year. The premium is about S$11 a week. That is above the brief's "a few dollars a week".</li>
        </ul>
        <h3>Hours at 32°C</h3>
        <p>Share of station-days by hours at WBGT 32°C.</p>
        <div data-bars data-max="100">
          <div data-value="77.8"><span class="bar-label">0 h</span><span class="bar-value">77.8%</span></div>
          <div data-value="13.7"><span class="bar-label">under 1 h</span><span class="bar-value">13.7%</span></div>
          <div data-value="5.3"><span class="bar-label">1 to 2 h</span><span class="bar-value">5.3%</span></div>
          <div data-value="2.9"><span class="bar-label">2 to 4 h</span><span class="bar-value">2.9%</span></div>
          <div data-value="0.3"><span class="bar-label">4 h or more</span><span class="bar-value">0.3%</span></div>
        </div>
        <div class="shots">
          {HEAT_MONTH_FIG}
          {HEAT_STATION_FIG}
        </div>
      </section>

      <section id="rain">
        <h2>Rain</h2>
        <ul>
          <li>A heavy hour is 20 mm or more in one hour, in work hours. It happened on 4.8% of days at a gauge, about 17 days a year.</li>
          <li>At 10 mm the share is 10.4%. At 30 mm the share is 2.2%.</li>
          <li>Somewhere in Singapore, a heavy hour happened on 36% of days.</li>
          <li>Rain is local. On a day with a heavy hour, on average only 14% of gauges had one.</li>
          <li>Rain is short. A gauge had on average 0.6 wet work hours a day. A wet hour is 1 mm or more.</li>
        </ul>
        <div class="shots">
          {RAIN_FIG}
        </div>
      </section>

      <section id="haze">
        <h2>Haze</h2>
        <ul>
          <li>From 2016 to 2025, the 24-hour PSI was above 100 ("unhealthy") on 0 to 6 days a year.</li>
          <li>2026 is different. There were 39 unhealthy days. 5 of those days were above 200 ("very unhealthy"). The peak was 230.</li>
          <li>The main episode was 3 to 25 October 2026. That was 23 days in a row above 100. On 17 of those days, all 5 regions were above 100. Shorter episodes occurred in September 2026.</li>
          <li>Haze is island-wide. On an unhealthy day, on average 3.5 of 5 regions were above 100.</li>
        </ul>
        <div class="shots">
          {HAZE_FIG}
        </div>
      </section>

      <section id="compare">
        <h2>Compare the three</h2>
        <p>Each cell is a share of days. Read each haze row on its own period.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th data-sort>Peril (trigger)</th>
                <th data-sort>Days at one location</th>
                <th data-sort>Days anywhere</th>
                <th data-sort>Locations hit on an event day</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td data-val="Heat">Heat: WBGT 32°C or more in work hours</td>
                <td data-val="22">22%</td>
                <td data-val="55">55%</td>
                <td data-val="40">40%</td>
              </tr>
              <tr>
                <td data-val="Rain">Rain: an hour of 20 mm or more in work hours</td>
                <td data-val="4.8">4.8%</td>
                <td data-val="36">36%</td>
                <td data-val="14">14%</td>
              </tr>
              <tr>
                <td data-val="Haze 2025">Haze: 24-hour PSI above 100 (2025 to 2026)</td>
                <td data-val="4.2">4.2%</td>
                <td data-val="6.1">6.1%</td>
                <td data-val="70">70%</td>
              </tr>
              <tr>
                <td data-val="Haze 2016">Haze: 24-hour PSI above 100 (2016 to 2026)</td>
                <td data-val="0.9">0.9%</td>
                <td data-val="1.5">1.5%</td>
                <td data-val="66">66%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section id="product">
        <h2>What this may mean for our product</h2>
        <p>These four points are for discussion.</p>
        <div class="cards">
          <article class="card" id="haze-peril" data-card="open">
            <header class="card-head">
              <div class="card-meta"><span class="badge">for discussion</span></div>
              <h3 class="card-title">Haze looks like the catastrophe peril</h3>
              <p class="card-summary">Rare, island-wide, and it can last weeks.</p>
            </header>
            <div class="card-body">
              <p>Haze looks like the catastrophe peril. It is rare. It hits almost everyone at once. It can last weeks. That fits a parametric trigger well. PSI is public. People already respond to it. It also brings the capital risk the brief warns about. It needs a cap on payable days and reinsurance.</p>
              <div class="evidence" data-evidence>
                <p>From 2016 to 2025, unhealthy days were 0 to 6 a year. 2026 has 39 unhealthy days. The longest run is 23 days. On an unhealthy day, 3.5 of 5 regions were above 100.</p>
              </div>
            </div>
          </article>
          <article class="card" id="heat-trigger" data-card="open">
            <header class="card-head">
              <div class="card-meta"><span class="badge">for discussion</span></div>
              <h3 class="card-title">Heat at 32°C happens too often for a simple trigger</h3>
              <p class="card-summary">A duration rule, or 33°C, makes it rarer.</p>
            </header>
            <div class="card-body">
              <p>Heat at 32°C happens too often to be a simple trigger. A duration rule makes it rarer. One example is 2 hours or more. A higher level also makes it rarer. One example is 33°C. The employer rest-break cost per hot day looks small, because the heat is usually short.</p>
              <div class="evidence" data-evidence>
                <p>WBGT reached 32°C on 22% of days at a typical station. Only 3.2% of station-days had 2 hours or more at 32°C.</p>
              </div>
            </div>
          </article>
          <article class="card" id="rain-basis" data-card="open">
            <header class="card-head">
              <div class="card-meta"><span class="badge">for discussion</span></div>
              <h3 class="card-title">Rain is local, so basis risk is high</h3>
              <p class="card-summary">Use the gauge nearest to the worker or shop.</p>
            </header>
            <div class="card-body">
              <p>Rain is local, so basis risk is high. A trigger must use the gauge nearest to the worker or shop. If it does not, people will see payouts that do not match their day.</p>
              <div class="evidence" data-evidence>
                <p>On a day with a heavy hour, on average only 14% of gauges had one. Somewhere in Singapore, a heavy hour happened on 36% of days.</p>
              </div>
            </div>
          </article>
          <article class="card" id="bundle" data-card="open">
            <header class="card-head">
              <div class="card-meta"><span class="badge">for discussion</span></div>
              <h3 class="card-title">A bundle may work best</h3>
              <p class="card-summary">One cover, with a cap on payable days per season.</p>
            </header>
            <div class="card-body">
              <p>A bundle may work best. One cover can include heat, rain and haze. It can include a cap on payable days per season, as the brief suggests.</p>
              <div class="evidence" data-evidence>
                <p>Heat at one location is 22% of days. Rain at one gauge is 4.8% of days. Haze at one location is 4.2% of days in 2025 to 2026, and 0.9% of days in 2016 to 2026.</p>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section id="decide">
        <h2>Decide at the meeting</h2>
        <ol class="checklist">
          <li>Who do we insure: outdoor and platform workers, SMEs such as hawkers, or households?</li>
          <li>Which trigger, or which bundle?</li>
          <li>Who pays the premium: the worker, a platform, an employer, NTUC, or a lender?</li>
        </ol>
      </section>

      <section id="limits">
        <h2>Limits</h2>
        <ul>
          <li>Heat and rain cover under 2 years. That is two hot seasons, not "decades of history".</li>
          <li>Haze covers 10 years, but 130 days have no data at the source.</li>
          <li>The prices in the app are indicative only. A real price needs a longer back-test and Income's actuaries.</li>
        </ul>
      </section>
"""

FOOTNOTES = """<ol class="footnotes">
        <li id="fn1">Data source: NEA real-time APIs on data.gov.sg, https://data.gov.sg</li>
        <li id="fn2">Scripts in the team repo ImNuza/sih-fin-4: scripts/heat_stats.py and scripts/hazard_stats.py.</li>
      </ol>"""


def build_body_uris(uris: dict) -> dict:
    return {
        "HEAT_MONTH_FIG": figure(
            uris["HEAT_MONTH"],
            "Days when WBGT reached 32°C at one or more stations, 7am to 7pm.",
            "Bar chart of days when WBGT reached 32°C at one or more stations",
        ),
        "HEAT_STATION_FIG": figure(
            uris["HEAT_STATION"],
            "Share of days at WBGT 32°C by station. Sentosa is 58%. Tuas is 0%.",
            "Bar chart of the share of days at WBGT 32°C by station",
        ),
        "RAIN_FIG": figure(
            uris["RAIN_MONTH"],
            "Share of days with an hour of 20 mm or more at a gauge, 7am to 7pm.",
            "Bar chart of heavy rain days by month",
        ),
        "HAZE_FIG": figure(
            uris["HAZE"],
            "Highest 24-hour PSI each day, 9 Mar 2016 to 7 Nov 2026.",
            "Line chart of the highest 24-hour PSI each day from 2016 to 2026",
        ),
    }



if __name__ == "__main__":
    main()
