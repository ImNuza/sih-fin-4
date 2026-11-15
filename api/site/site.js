/* SafeDay platform shell: auth, the login page and the two role dashboards.
   All pricing and access control happen in the API; this file only draws the answers. */
"use strict";

const el = (id) => document.getElementById(id);
const SGD = (v) => "S$" + (v >= 1000 ? Math.round(v).toLocaleString("en-SG") : Number(v).toFixed(2));
const PRODUCT_LABELS = {};
const MONTH = (ym) => ym ? new Date(ym + "-01").toLocaleDateString("en-SG", { month: "short", year: "numeric" }) : "";

/* One sentence on where a centre's rent figure comes from. */
function rentSource(rent, table) {
  if (rent.estimated)
    return `No NEA bid on record for this centre, so we use the median of all centres, ${SGD(table.all_centre_median_sgd)} a month.`;
  const span = rent.first_month === rent.last_month ? MONTH(rent.first_month) : `${MONTH(rent.first_month)} to ${MONTH(rent.last_month)}`;
  return `Median winning NEA bid for a cooked-food stall: ${SGD(rent.median_bid_sgd)} a month (${rent.bids} bid${rent.bids === 1 ? "" : "s"}, ${span}).`;
}

async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `${url}: HTTP ${response.status}`);
  return body;
}
const post = (url, data) =>
  api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

/* ---------- theme ---------- */
function wireTheme() {
  const button = el("theme-toggle");
  if (!button) return;
  const paint = () => { button.textContent = document.documentElement.dataset.theme === "dark" ? "\u2600" : "\u263e"; };
  paint();
  button.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("safeday-theme", next); } catch { /* private window */ }
    paint();
  });
}

/* ---------- top nav: show Dashboard instead of Sign in when a session exists ---------- */
async function updateNav() {
  const link = el("nav-auth");
  if (!link) return;
  try {
    await api("/api/auth/me");
    link.textContent = "Dashboard";
    link.href = "/dashboard/";
  } catch { /* signed out: keep Sign in */ }
}

/* ---------- login page ---------- */
function wireLogin() {
  if (!el("tab-sme")) return;
  const showPane = (role) => {
    el("tab-sme").classList.toggle("on", role === "sme");
    el("tab-insurer").classList.toggle("on", role === "insurer");
    el("pane-sme").hidden = role !== "sme";
    el("pane-insurer").hidden = role !== "insurer";
  };
  el("tab-sme").addEventListener("click", () => showPane("sme"));
  el("tab-insurer").addEventListener("click", () => showPane("insurer"));
  if (location.hash === "#insurer") showPane("insurer");
  document.querySelectorAll(".authcard [data-goto]").forEach((link) =>
    link.addEventListener("click", () => {
      const card = link.closest(".authcard");
      for (const step of card.querySelectorAll("[data-step]"))
        step.hidden = step.dataset.step !== link.dataset.goto;
    }));

  const submit = (formId, errorId, build) => {
    el(formId).addEventListener("submit", async (event) => {
      event.preventDefault();
      el(errorId).textContent = "";
      try {
        const data = formData(event.target);
        await (build ? post("/api/auth/register", build(data)) : post("/api/auth/login", data));
        location.href = "/dashboard/";
      } catch (error) {
        el(errorId).textContent = error.message;
      }
    });
  };
  submit("sme-login", "sme-login-error", null);
  submit("ins-login", "ins-login-error", null);
  submit("ins-register", "ins-register-error", (d) => ({ ...d, role: "insurer" }));
}

/* ---------- dashboards ---------- */
function kpi(label, value, note) {
  return `<div class="kpi"><div class="k">${label}</div><div class="v">${value}</div>${note ? `<div class="n">${note}</div>` : ""}</div>`;
}
function mapPreview(params, caption) {
  const src = "/map/?" + new URLSearchParams(params).toString();
  return `<a class="mappreview" href="${src}" target="_blank" rel="noopener"
    title="Open the full risk atlas in a new tab">
    <iframe src="${src}" title="${caption}" loading="eager" tabindex="-1" aria-hidden="true"></iframe>
    <span class="chip cap">${caption}</span>
    <span class="chip open">Open the full atlas ↗</span>
  </a>`;
}
function mapFrame(params, caption) {
  const src = "/map/?" + new URLSearchParams(params).toString();
  return `<section class="mapframe">
    <div class="bar"><h2 style="margin:0;font:700 17px var(--sans)">${caption}</h2>
    <a class="btn small" href="${src}" target="_blank" rel="noopener">Open full screen</a></div>
    <iframe src="${src}" title="${caption}" loading="lazy"></iframe></section>`;
}
function liveStatus(live) {
  if (!live || !live.available) return { ok: false, text: live?.status || "live feed warming up, refresh in a minute" };
  return { ok: true, text: `NEA readings as of ${String(live.fetched_at).slice(11, 16)} SGT` };
}

async function renderSme(user) {
  const [quote, policies, staticData, live, rentTable] = await Promise.all([
    post("/api/quote", { region: user.region, product: user.product || "cooked_food" }),
    api("/api/policies"),
    api("/api/map/static"),
    api("/api/map/live").catch(() => null),
    api("/api/rent"),
  ]);
  const application = await api("/api/applications/mine").catch(() => null);
  const underReview = application?.status === "referred";
  const rent = rentTable.centres[user.centre];
  const policy = policies[0] || null;
  const index = staticData.hawker_centres.findIndex((c) => c.name === user.centre);
  const todays = live?.available && index >= 0 ? live.hawker_losses[index] : null;
  const status = liveStatus(live);
  // Recommend the smallest tier that pays a full day's rent at this centre.
  const rec = rent ? rent.recommended_tier : quote.tiers[0].tier;
  const rentShare = (payout) => rent ? Math.round((100 * payout) / rent.rent_per_day_sgd) : null;
  const payoutToday = todays && policy ? (todays.loss_percent / 100) * policy.daily_payout_sgd : null;

  el("dash").innerHTML = `
    <h1>${user.business_name || user.name}</h1>
    <p class="sub">${user.centre} · ${user.region} region · priced from your region's own NEA history</p>
    ${mapPreview({ view: "owner", focus: user.centre, camera: "city" }, "Your stall on the risk atlas")}
    <div class="kpis">
      ${kpi("Today's loss score", todays ? `${todays.loss_percent.toFixed(0)}%` : "–", status.text)}
      ${kpi("Payout due today", policy ? (payoutToday != null ? SGD(payoutToday) : "–") : "no cover yet", policy ? `at ${policy.tier_label}` : underReview ? "after the underwriter replies" : "pick a tier below")}
      ${kpi("Your weekly premium", policy ? SGD(policy.weekly_premium_sgd) : SGD(quote.tiers.find((t) => t.tier === rec).weekly_premium_sgd), policy ? policy.tier_label : "recommended tier")}
      ${kpi("Expected trigger days", quote.expected_loss_days.toFixed(1) + " / yr", "full-loss-day equivalents")}
      ${rent ? kpi("Your rent per trading day", SGD(rent.rent_per_day_sgd), `${rent.rent_class_label} centre${rent.estimated ? " · estimated" : ""}`) : ""}
    </div>
    <div class="grid">
      <div class="card"><h2>Today at your stall</h2>
        ${todays ? `
        <div class="kv"><span class="k">24-h PSI (your region)</span><span class="v">${Math.round(todays.readings.haze)}</span></div>
        <div class="kv"><span class="k">Wettest work hour (nearest gauge)</span><span class="v">${todays.readings.rain.toFixed(1)} mm</span></div>
        <div class="kv"><span class="k">Hours at WBGT ≥32 °C (nearest station)</span><span class="v">${todays.readings.heat} h</span></div>
        <p class="fine">Readings refresh every 5 minutes from NEA. A payout needs no claim. It follows these numbers.</p>`
        : `<p class="fine">${status.text}</p><button class="btn small" id="retry-live" type="button">Refresh</button>`}
      </div>
      <div class="card"><h2>${policy ? "Your cover" : underReview ? "Your application" : "Choose your cover"}</h2>
        ${underReview && !policy ? `
        <p><span class="pill warning">With an underwriter</span></p>
        <p class="fine" style="margin-top:10px">Application ${application.id}, sent ${String(application.created_at).slice(0, 10)}. Because an insurer declined cover for this business before, an underwriter reviews it first. Cover starts, and you pay, only after they reply. We will contact you on ${application.phone}.</p>`
        : policy ? `
        <div class="kv"><span class="k">Tier</span><span class="v">${policy.tier_label}</span></div>
        <div class="kv"><span class="k">Pays per bad day</span><span class="v">${SGD(policy.daily_payout_sgd)}</span></div>
        ${rent ? `<div class="kv"><span class="k">Share of a day's rent</span><span class="v">${rentShare(policy.daily_payout_sgd)}%</span></div>` : ""}
        <div class="kv"><span class="k">Cap</span><span class="v">${policy.max_paid_days_per_year} days / yr</span></div>
        <div class="kv"><span class="k">Weekly premium</span><span class="v">${SGD(policy.weekly_premium_sgd)}</span></div>
        <div class="kv"><span class="k">Started</span><span class="v">${String(policy.started_at).slice(0, 10)}</span></div>
        <p class="fine">Pays when NEA shows PSI>100, rain ≥20 mm/h, WBGT ≥32 °C for 2 h+, or a PUB flood alert near ${user.centre}. Below those levels nothing is paid.</p>
        <button class="btn small" id="cancel-policy" type="button">Cancel cover</button>`
        : `<div class="tiers-row">${quote.tiers.map((t) => `
          <button class="tier-card ${t.tier === rec ? "rec" : ""}" data-tier="${t.tier}" type="button">
            <span class="t">${t.label}${t.tier === rec ? " ●" : ""}</span>
            <span class="p">${SGD(t.weekly_premium_sgd)}<small>/wk</small></span>
            <span class="d">${SGD(t.daily_payout_sgd)}/bad day · max ${SGD(t.max_payout_per_year_sgd)}/yr</span>
            ${rent ? `<span class="d">${rentShare(t.daily_payout_sgd)}% of a day's rent</span>` : ""}
          </button>`).join("")}</div>
        <p class="fine">${rent ? (rent.covers_rent
          ? `● marks the smallest tier that pays your whole day's rent (about ${SGD(rent.rent_per_day_sgd)}) on a full bad day.`
          : `No tier pays a whole day's rent here (about ${SGD(rent.rent_per_day_sgd)}). ● marks the biggest tier.`)
          + ` ${rentSource(rent, rentTable)}` : "● marks the recommended tier."} Click a tier to start cover.</p>
        <p class="error" id="buy-error"></p>`}
      </div>
    </div>
    <div class="card" id="burn-card">
      <h2>Your last ten years, replayed</h2>
      <p class="fine">Every NEA reading since 2017 at ${user.centre}, scored by the live tariff.
        Set your normal daily sales; the losses scale with it, the payouts do not.</p>
      <div class="burn-controls">
        <label>My daily sales (S$)
          <input type="number" id="burn-takings" min="50" max="20000" step="50" value="500" /></label>
      </div>
      <div id="burn-body"><p class="fine">Computing…</p></div>
    </div>
`;

  document.querySelectorAll(".tier-card").forEach((button) =>
    button.addEventListener("click", async () => {
      try {
        await post("/api/policies", { tier: button.dataset.tier });
        renderSme(user);
      } catch (error) { el("buy-error").textContent = error.message; }
    }));
  el("cancel-policy")?.addEventListener("click", async () => {
    await api(`/api/policies/${policy.id}`, { method: "DELETE" });
    renderSme(user);
  });
  el("retry-live")?.addEventListener("click", () => renderSme(user));
  const burnTier = policy ? policy.tier : rec;
  const loadBurn = async () => {
    const takings = +el("burn-takings").value || 500;
    try {
      const burn = await api(`/api/map/burn?centre=${encodeURIComponent(user.centre)}`
        + `&product=${user.product || "cooked_food"}&tier=${burnTier}&takings=${takings}`);
      el("burn-body").innerHTML = renderBurn(burn, policy);
    } catch (error) {
      el("burn-body").innerHTML = `<p class="error">${error.message}</p>`;
    }
  };
  el("burn-takings").addEventListener("change", loadBurn);
  loadBurn();
}

function renderBurn(burn, policy) {
  const t = burn.totals;
  const maxLost = Math.max(...burn.years.map((y) => y.est_lost_sgd), 1);
  const bars = burn.years.map((y) => `
    <div class="burn-year">
      <div class="burn-bars">
        <div class="burn-lost" style="height:${Math.max(y.est_lost_sgd / maxLost * 72, 2)}px" title="Lost ~${SGD(y.est_lost_sgd)}"></div>
        <div class="burn-paid" style="height:${Math.max(y.paid_sgd / maxLost * 72, y.paid_sgd ? 2 : 0)}px" title="Paid ${SGD(y.paid_sgd)}"></div>
      </div>
      <span>${String(y.year).slice(2)}</span>
    </div>`).join("");
  const hz = t.by_hazard_sgd;
  return `
    <p class="burn-headline">Weather took about <b>${SGD(t.est_lost_sgd)}</b> from a business like
      yours since ${t.from_year}. With ${burn.tier_label}, SafeDay would have paid you
      <b>${SGD(t.paid_sgd)}</b> across <b>${t.trigger_days} bad days</b>, for
      ${SGD(t.premium_sgd)} of premium${policy ? "" : " (you are not covered yet)"}.</p>
    <div class="burn-chart">${bars}</div>
    <p class="fine">Grey: estimated revenue lost each year. Blue: what this tier would have paid.
      Of the payouts, ${SGD(hz.rain)} came from heavy rain, ${SGD(hz.haze)} from haze and
      ${SGD(hz.heat)} from heat (heat readings exist from 2025).</p>`;
}

async function renderInsurer(user) {
  const [portfolio, policies, quotesData, staticData, live, rentTable] = await Promise.all([
    api("/api/insurer/portfolio"),
    api("/api/policies"),
    api("/api/map/quotes"),
    api("/api/map/static"),
    api("/api/map/live").catch(() => null),
    api("/api/rent"),
  ]);
  const rentOf = (centre) => rentTable.centres[centre];
  const status = liveStatus(live);
  const stalls = staticData.hawker_centres.reduce((a, c) => a + c.food_stalls, 0);
  let marketPool = 0;
  for (const centre of staticData.hawker_centres) {
    const tier = quotesData.quotes[centre.region].tiers[1];
    marketPool += tier.yearly_premium_sgd * centre.food_stalls;
  }
  const maxLoss = live?.available ? Math.max(...live.hawker_losses.map((l) => l.loss_percent)) : null;

  el("dash").innerHTML = `
    <h1>${user.insurer} · portfolio desk</h1>
    <p class="sub">Signed in as ${user.name} · every number from the live tariff and NEA data</p>
    <div class="kpis">
      ${kpi("Policies in force", portfolio.policies, "sold on this platform")}
      ${kpi("Premium booked", SGD(portfolio.annual_premium_sgd) + "/yr", SGD(portfolio.weekly_premium_sgd) + "/wk")}
      ${kpi("Payout exposure", SGD(portfolio.daily_payout_exposure_sgd) + "/day", "if every policy pays in full")}
      ${kpi("Worst live loss now", maxLoss != null ? maxLoss.toFixed(0) + "%" : "–", status.text)}
      ${kpi("Market potential", stalls.toLocaleString("en-SG") + " stalls", SGD(marketPool) + "/yr pool at Tier 2")}
    </div>
    <div class="tools">
      <a class="tool" href="/map/?view=insurer&mode=live" target="_blank" rel="noopener"><b>3D risk atlas</b><span>Hazard, exposure and accumulation over Singapore, with live NEA readings, a worst-day simulator and the city view.</span></a>
      <a class="tool" href="/admin/" target="_blank" rel="noopener"><b>Tariff desk</b><span>Change any weight, severity band, product factor, tier or load. Every save is a new version and every dashboard reprices at once.</span></a>
      <a class="tool" href="http://localhost:8501" target="_blank" rel="noopener"><b>Data dashboard</b><span>The team's Streamlit explorer: heat, rain and haze history, trigger &amp; price experiments, live readings.</span></a>
      <a class="tool" href="/docs" target="_blank" rel="noopener"><b>API docs</b><span>Quote, assess, map and portfolio endpoints. One engine behind every screen.</span></a>
    </div>
    <div class="card">
      <h2>Policies in force</h2>
      ${policies.length ? `<table class="list">
        <tr><th>Business</th><th>Centre</th><th>Region</th><th>Rent class</th><th>Tier</th><th>Weekly</th><th>Payout/day</th><th>Rent/day</th><th>Started</th></tr>
        ${policies.map((p) => `<tr>
          <td>${p.business_name || p.name}</td><td>${p.centre || "–"}</td><td>${p.region}</td>
          <td>${rentOf(p.centre)?.rent_class_label || "–"}</td>
          <td>${p.tier_label}</td><td class="num">${SGD(p.weekly_premium_sgd)}</td>
          <td class="num">${SGD(p.daily_payout_sgd)}</td><td class="num">${rentOf(p.centre) ? SGD(rentOf(p.centre).rent_per_day_sgd) : "–"}</td><td class="num">${String(p.started_at).slice(0, 10)}</td></tr>`).join("")}
      </table>` : `<p class="fine">No policies sold yet. When a business owner signs up and picks a tier, it lands here with its region and accumulation.</p>`}
      ${Object.keys(portfolio.by_region).length ? `<p class="fine" style="margin-top:10px">By region: ${Object.entries(portfolio.by_region)
        .map(([region, r]) => `${region} ${r.policies} (${SGD(r.weekly_premium_sgd)}/wk)`).join(" · ")}</p>` : ""}
    </div>
    ${mapFrame({ view: "insurer", mode: "live" }, "The book on the map, live")}`;
}

async function wireDashboard() {
  if (!el("dash")) return;
  let user;
  try {
    user = await api("/api/auth/me");
  } catch {
    location.href = "/login/";
    return;
  }
  el("whoami").textContent = `${user.name} · ${user.role === "insurer" ? user.insurer : user.centre}`;
  el("signout").addEventListener("click", async () => {
    await post("/api/auth/logout", {});
    location.href = "/";
  });
  try {
    if (user.role === "insurer") await renderInsurer(user);
    else await renderSme(user);
  } catch (error) {
    el("dash").innerHTML = `<p class="error">Could not load the dashboard: ${error.message}</p>`;
  }
}

wireTheme();
updateNav();
wireLogin();
wireDashboard();
