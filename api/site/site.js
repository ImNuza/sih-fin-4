/* SafeDay platform shell: auth, the login page and the two role dashboards.
   All pricing and access control happen in the API; this file only draws the answers. */
"use strict";

const el = (id) => document.getElementById(id);
const SGD = (v) => "S$" + (v >= 1000 ? Math.round(v).toLocaleString("en-SG") : Number(v).toFixed(2));
const PRODUCT_LABELS = {};

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

  api("/api/map/static").then((data) => {
    const centres = [...data.hawker_centres].sort((a, b) => a.name.localeCompare(b.name));
    el("centre-select").innerHTML =
      '<option value="">Pick your centre…</option>' +
      centres.map((c) => `<option value="${c.name}">${c.name} (${c.region})</option>`).join("");
  });
  api("/api/options").then((options) => {
    el("product-select").innerHTML = options.products
      .map((p) => `<option value="${p.key}">${p.label}</option>`)
      .join("");
  });

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
  submit("sme-register", "sme-register-error", (d) => ({ ...d, role: "sme" }));
  submit("ins-register", "ins-register-error", (d) => ({ ...d, role: "insurer" }));
}

/* ---------- dashboards ---------- */
function kpi(label, value, note) {
  return `<div class="kpi"><div class="k">${label}</div><div class="v">${value}</div>${note ? `<div class="n">${note}</div>` : ""}</div>`;
}
function mapFrame(params, caption) {
  const src = "/map/?" + new URLSearchParams(params).toString();
  return `<section class="mapframe">
    <div class="bar"><h2 style="margin:0;font:700 17px var(--sans)">${caption}</h2>
    <a class="btn small" href="${src}" target="_blank" rel="noopener">Open full screen</a></div>
    <iframe src="${src}" title="${caption}" loading="lazy"></iframe></section>`;
}
function liveStatus(live) {
  if (!live || !live.available) return { ok: false, text: live?.status || "live feed warming up — refresh in a minute" };
  return { ok: true, text: `NEA readings as of ${String(live.fetched_at).slice(11, 16)} SGT` };
}

async function renderSme(user) {
  const [quote, policies, staticData, live] = await Promise.all([
    post("/api/quote", { region: user.region, product: user.product || "cooked_food" }),
    api("/api/policies"),
    api("/api/map/static"),
    api("/api/map/live").catch(() => null),
  ]);
  const policy = policies[0] || null;
  const index = staticData.hawker_centres.findIndex((c) => c.name === user.centre);
  const todays = live?.available && index >= 0 ? live.hawker_losses[index] : null;
  const status = liveStatus(live);
  const affordable = quote.tiers.filter((t) => t.weekly_premium_sgd <= 3);
  const rec = (affordable[affordable.length - 1] || quote.tiers[0]).tier;
  const payoutToday = todays && policy ? (todays.loss_percent / 100) * policy.daily_payout_sgd : null;

  el("dash").innerHTML = `
    <h1>${user.business_name || user.name}</h1>
    <p class="sub">${user.centre} · ${user.region} region · priced from your region's own NEA history</p>
    <div class="kpis">
      ${kpi("Today's loss score", todays ? `${todays.loss_percent.toFixed(0)}%` : "—", status.text)}
      ${kpi("Payout due today", policy ? (payoutToday != null ? SGD(payoutToday) : "—") : "no cover yet", policy ? `at ${policy.tier_label}` : "pick a tier below")}
      ${kpi("Your weekly premium", policy ? SGD(policy.weekly_premium_sgd) : SGD(quote.tiers.find((t) => t.tier === rec).weekly_premium_sgd), policy ? policy.tier_label : "recommended tier")}
      ${kpi("Expected trigger days", quote.expected_loss_days.toFixed(1) + " / yr", "full-loss-day equivalents")}
    </div>
    <div class="grid">
      <div class="card"><h2>Today at your stall</h2>
        ${todays ? `
        <div class="kv"><span class="k">24-h PSI (your region)</span><span class="v">${Math.round(todays.readings.haze)}</span></div>
        <div class="kv"><span class="k">Wettest work hour (nearest gauge)</span><span class="v">${todays.readings.rain.toFixed(1)} mm</span></div>
        <div class="kv"><span class="k">Hours at WBGT ≥32 °C (nearest station)</span><span class="v">${todays.readings.heat} h</span></div>
        <p class="fine">Readings refresh every 5 minutes from NEA. A payout needs no claim — it follows these numbers.</p>`
        : `<p class="fine">${status.text}</p><button class="btn small" id="retry-live" type="button">Refresh</button>`}
      </div>
      <div class="card"><h2>${policy ? "Your cover" : "Choose your cover"}</h2>
        ${policy ? `
        <div class="kv"><span class="k">Tier</span><span class="v">${policy.tier_label}</span></div>
        <div class="kv"><span class="k">Pays per bad day</span><span class="v">${SGD(policy.daily_payout_sgd)}</span></div>
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
          </button>`).join("")}</div>
        <p class="fine">One price, four sizes. ● marks the dearest tier still within "a few dollars a week". Click a tier to start cover.</p>
        <p class="error" id="buy-error"></p>`}
      </div>
    </div>
    ${mapFrame({ view: "owner", focus: user.centre, camera: "city" }, "Your stall on the risk atlas")}`;

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
}

async function renderInsurer(user) {
  const [portfolio, policies, quotesData, staticData, live] = await Promise.all([
    api("/api/insurer/portfolio"),
    api("/api/policies"),
    api("/api/map/quotes"),
    api("/api/map/static"),
    api("/api/map/live").catch(() => null),
  ]);
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
      ${kpi("Worst live loss now", maxLoss != null ? maxLoss.toFixed(0) + "%" : "—", status.text)}
      ${kpi("Market potential", stalls.toLocaleString("en-SG") + " stalls", SGD(marketPool) + "/yr pool at Tier 2")}
    </div>
    <div class="tools">
      <a class="tool" href="/map/?view=insurer&mode=live" target="_blank" rel="noopener"><b>3D risk atlas</b><span>Hazard, exposure and accumulation over Singapore — live NEA readings, worst-day simulator, city view.</span></a>
      <a class="tool" href="/admin/" target="_blank" rel="noopener"><b>Tariff desk</b><span>Change any weight, severity band, product factor, tier or load. Every save is a new version; every dashboard reprices instantly.</span></a>
      <a class="tool" href="http://localhost:8501" target="_blank" rel="noopener"><b>Data dashboard</b><span>The team's Streamlit explorer: heat, rain and haze history, trigger &amp; price experiments, live readings. Run: uv run streamlit run app/app.py</span></a>
      <a class="tool" href="/docs" target="_blank" rel="noopener"><b>API docs</b><span>Quote, assess, map and portfolio endpoints — the same engine behind every screen.</span></a>
    </div>
    <div class="card">
      <h2>Policies in force</h2>
      ${policies.length ? `<table class="list">
        <tr><th>Business</th><th>Centre</th><th>Region</th><th>Tier</th><th>Weekly</th><th>Payout/day</th><th>Started</th></tr>
        ${policies.map((p) => `<tr>
          <td>${p.business_name || p.name}</td><td>${p.centre || "—"}</td><td>${p.region}</td>
          <td>${p.tier_label}</td><td class="num">${SGD(p.weekly_premium_sgd)}</td>
          <td class="num">${SGD(p.daily_payout_sgd)}</td><td class="num">${String(p.started_at).slice(0, 10)}</td></tr>`).join("")}
      </table>` : `<p class="fine">No policies sold yet. When a stallholder signs up and picks a tier, it lands here with its region and accumulation.</p>`}
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

updateNav();
wireLogin();
wireDashboard();
