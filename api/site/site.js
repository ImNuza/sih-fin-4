/* Payung platform shell: auth, the login page and the two role dashboards.
   All pricing and access control happen in the API; this file only draws the answers. */
"use strict";

const el = (id) => document.getElementById(id);
const SGD = (v) => "S$" + (v >= 1000 ? Math.round(v).toLocaleString("en-SG") : Number(v).toFixed(2));
const SG_DATE = (value) => new Date(value).toLocaleDateString("en-CA", { timeZone: "Asia/Singapore" });
const MONTH = (ym) => ym ? new Date(ym + "-01").toLocaleDateString("en-SG", { month: "short", year: "numeric" }) : "";

/* One sentence on where a centre's rent figure comes from. */
function rentSource(rent, table) {
  if (rent.estimated)
    return `No NEA bid on record for this centre, so we use the median of all centres, ${SGD(table.all_centre_median_sgd)} a month.`;
  const span = rent.first_month === rent.last_month ? MONTH(rent.first_month) : `${MONTH(rent.first_month)} to ${MONTH(rent.last_month)}`;
  return `Median winning NEA bid for a cooked-food stall: ${SGD(rent.median_bid_sgd)} a month (${rent.bids} bid${rent.bids === 1 ? "" : "s"}, ${span}).`;
}

/* FastAPI sends a string, or a list of field errors for a bad request body. */
function errorText(detail) {
  if (!Array.isArray(detail)) return detail;
  // A rule checked in code arrives as "Value error, <message>": keep only the message.
  return detail.map((error) => `${error.loc?.at(-1) ?? "field"}: ${String(error.msg).replace(/^Value error, /, "")}`).join("; ");
}

async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorText(body.detail) || `${url}: HTTP ${response.status}`);
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
  const paint = () => {
    const dark = document.documentElement.dataset.theme === "dark";
    button.innerHTML = SafeUI.icon(dark ? "sun" : "moon");
    button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  };
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
    (link.querySelector(".label-wide") || link).textContent = "Dashboard";
    link.href = "/dashboard/";
  } catch { /* signed out: keep Sign in */ }
}

/* ---------- login page ---------- */
const DEMO_ACCOUNTS_KEY = "safeday-demo-accounts";
const DEMO_INSURER_STAFF = ["Chua Li Hui", "Daniel Teo", "Nur Aisyah binte Hassan", "Arjun Menon", "Rachel Koh", "Benjamin Lee"];
const demoPick = (list) => list[Math.floor(Math.random() * list.length)];
const demoDigits = (n) => Array.from({ length: n }, () => Math.floor(Math.random() * 10)).join("");

/* The last account this browser created per role, so the demo signs in with no typing. */
function demoAccounts() {
  try {
    const stored = JSON.parse(localStorage.getItem(DEMO_ACCOUNTS_KEY));
    return stored && typeof stored === "object" ? stored : {};
  } catch {
    return {};
  }
}
function rememberDemoAccount(role, email, password) {
  const accounts = { ...demoAccounts(), [role]: { email, password, role } };
  try { localStorage.setItem(DEMO_ACCOUNTS_KEY, JSON.stringify(accounts)); } catch { /* private window */ }
}
/* Fill the sign-in form with this browser's demo account for `role`. Returns whether one exists. */
function fillDemoSignIn(formId, hintId, role) {
  const account = demoAccounts()[role];
  el(hintId).hidden = Boolean(account);
  if (!account) return false;
  el(formId).elements.email.value = account.email;
  el(formId).elements.password.value = account.password;
  return true;
}
function fillDemoInsurerRegister() {
  const form = el("ins-register");
  const name = demoPick(DEMO_INSURER_STAFF);
  form.elements.name.value = name;
  form.elements.email.value = `${name.toLowerCase().replace(/[^a-z]+/g, ".")}.${demoDigits(4)}@example.test`;
  form.elements.password.value = `demo-${demoDigits(6)}`;
}

function wireLogin() {
  if (!el("tab-sme")) return;
  const MIN_PASSWORD_LENGTH = 8;
  const EMAIL_SHAPE = /^[^@\s]+@[^@\s]+$/;
  const tabs = { sme: el("tab-sme"), insurer: el("tab-insurer") };

  const showPane = (role) => {
    for (const [key, tab] of Object.entries(tabs)) {
      const on = key === role;
      tab.classList.toggle("on", on);
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      el(`pane-${key}`).hidden = !on;
    }
  };
  const showStep = (card, step) => {
    for (const section of card.querySelectorAll("[data-step]")) section.hidden = section.dataset.step !== step;
  };
  tabs.sme.addEventListener("click", () => showPane("sme"));
  tabs.insurer.addEventListener("click", () => showPane("insurer"));
  el("tab-sme").parentElement.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const next = tabs.sme.classList.contains("on") ? "insurer" : "sme";
    showPane(next);
    tabs[next].focus();
  });
  if (location.hash === "#insurer") showPane("insurer");
  document.querySelectorAll(".authcard [data-goto]").forEach((link) =>
    link.addEventListener("click", () => {
      const card = link.closest(".authcard");
      showStep(card, link.dataset.goto);
      card.querySelector(`[data-step="${link.dataset.goto}"] input`)?.focus();
    }));

  /* The first problem in a form, as [field, message], or null when it can be sent. */
  const problemIn = (form) => {
    const { name, email, password } = form.elements;
    if (name && !name.value.trim()) return [name, "Enter your name."];
    if (!email.value.trim()) return [email, "Enter your email address."];
    if (!EMAIL_SHAPE.test(email.value.trim())) return [email, "Enter an email address like name@example.com."];
    if (!password.value) return [password, "Enter your password."];
    if (form.id === "ins-register" && password.value.length < MIN_PASSWORD_LENGTH)
      return [password, `Use at least ${MIN_PASSWORD_LENGTH} characters for the password.`];
    return null;
  };
  const showError = (errorId, message) => {
    el(errorId).innerHTML = message ? `${SafeUI.icon("circle-alert")}<span>${message}</span>` : "";
  };
  const serverProblem = (formId, error) => {
    if (error instanceof TypeError) return "Could not reach Payung. Check your connection and try again.";
    if (formId === "ins-register" && /exists/i.test(error.message))
      return "An account with this email already exists. Sign in with it instead, or use another email.";
    if (/wrong email or password/i.test(error.message))
      return formId === "sme-login"
        ? "The email or password is wrong. Check both and try again. No account yet? Apply with your Income adviser first."
        : "The email or password is wrong. Check both and try again, or set up insurer access.";
    return `Could not sign in: ${escapeHtml(error.message)}. Try again.`;
  };

  const submit = (formId, errorId, build) => {
    const form = el(formId);
    form.addEventListener("input", (event) => {
      event.target.removeAttribute("aria-invalid");
      showError(errorId, "");
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      for (const input of form.elements) input.removeAttribute("aria-invalid");
      const problem = problemIn(form);
      if (problem) {
        const [input, message] = problem;
        input.setAttribute("aria-invalid", "true");
        showError(errorId, message);
        input.focus();
        return;
      }
      showError(errorId, "");
      const button = form.querySelector('[type="submit"]');
      button.setAttribute("aria-busy", "true");
      try {
        const data = formData(form);
        const body = build ? build(data) : data;
        await post(build ? "/api/auth/register" : "/api/auth/login", body);
        if (build) rememberDemoAccount(body.role, body.email, body.password);
        location.href = "/dashboard/";
      } catch (error) {
        showError(errorId, serverProblem(formId, error));
        button.removeAttribute("aria-busy");
      }
    });
  };
  submit("sme-login", "sme-login-error", null);
  submit("ins-login", "ins-login-error", null);
  submit("ins-register", "ins-register-error", (d) => ({ ...d, role: "insurer" }));

  fillDemoSignIn("sme-login", "sme-login-hint", "sme");
  if (!fillDemoSignIn("ins-login", "ins-login-hint", "insurer")) showStep(el("pane-insurer").querySelector(".authcard"), "register");
  fillDemoInsurerRegister();
  document.querySelectorAll(".authcard [data-clear]").forEach((button) =>
    button.addEventListener("click", () => {
      const form = button.closest("form");
      form.reset();
      for (const input of form.elements) input.removeAttribute("aria-invalid");
      form.querySelector(".error").textContent = "";
    }));
}

/* ---------- dashboards: shared parts ---------- */
const WAITING_PERIOD_DAYS = 30;
const WEEKS_PER_YEAR = 52;
const BUSINESS_CLASSES = { hawker: "Hawker stall", shop: "Neighbourhood shop", platform_worker: "Platform worker" };
const escapeHtml = (text) => String(text ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const titleCase = (text) => String(text ?? "").replace(/^\w/, (c) => c.toUpperCase());
const TODAY = () => SG_DATE(Date.now());
/* A Singapore date for a key-value row, kept on one line. */
const dateValue = (value) => `<span class="nowrap">${SG_DATE(value)}</span>`;
const COMPACT = new Intl.NumberFormat("en-SG", { notation: "compact", maximumFractionDigits: 1 });
/* Money for a KPI cell: exact up to a million, then "S$123.5M" so it fits on one line. */
const SGD_KPI = (v) => (v >= 1e6 ? `S$${COMPACT.format(v)}` : SGD(v));

function initials(name) {
  const words = String(name || "").trim().split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] || "") + (words.length > 1 ? words.at(-1)[0] : "")).toUpperCase() || "?";
}
function kpi(label, value, note, help) {
  return `<div class="kpi"><div class="k">${label}${help ? ` ${SafeUI.help(help)}` : ""}</div>
    <div class="v">${value}</div>${note ? `<div class="n">${note}</div>` : ""}</div>`;
}
function kpiSkeletons(labels) {
  return labels.map((label) =>
    kpi(label, `<span class="skeleton value"></span>`, `<span class="skeleton line note"></span>`)).join("");
}
function kv(key, value) {
  return `<div class="kv"><span class="k">${key}</span><span class="v">${value}</span></div>`;
}
function pill(tone, text) {
  return `<span class="chip ${tone}">${escapeHtml(text)}</span>`;
}
function notice(tone, iconName, html) {
  return `<p class="notice ${tone}">${SafeUI.icon(iconName)}<span>${html}</span></p>`;
}
function tableSkeleton(rows) {
  return `<div class="table-skeleton" aria-hidden="true">${`<span class="skeleton line"></span>`.repeat(rows)}</div>`;
}
/* A section that failed to load: what went wrong and a way to try again. */
function loadError(what, error) {
  return `<div class="card flush"><div class="empty" role="alert">${SafeUI.icon("circle-alert")}
    <h3>Could not load ${what}</h3><p>${escapeHtml(error.message)}. Try again in a moment.</p>
    <button class="btn small" type="button" data-reload>Try again</button></div></div>`;
}
function sortHeader(label, { num = false, help = "" } = {}) {
  return `<th${num ? ` class="num"` : ""}><button class="sort" type="button">${label}${SafeUI.icon("arrow-up-down")}</button>${help ? ` ${SafeUI.help(help)}` : ""}</th>`;
}
function mapPreview(params, caption) {
  const src = "/map/?" + new URLSearchParams(params).toString();
  return `<a class="mappreview" href="${src}" target="_blank" rel="noopener" aria-label="${caption}. Opens the full risk atlas in a new tab">
    <iframe src="${src}" title="${caption}" loading="lazy" tabindex="-1" aria-hidden="true"></iframe>
    <span class="map-chip cap">${caption}</span>
    <span class="map-chip open">${SafeUI.icon("external-link")}Open the full atlas</span>
  </a>`;
}

/* "Hawker stall · licence SFA-123": the business class and the proof the owner gave, or "". */
function businessProof(application) {
  if (!application) return "";
  const platform = application.platform
    ? `${application.platform}${application.platform_worker_id ? ` ID ${application.platform_worker_id}` : ""}` : null;
  return [
    BUSINESS_CLASSES[application.business_class],
    application.licence_no && `licence ${application.licence_no}`,
    application.ssic_code && `SSIC ${application.ssic_code}`,
    platform,
  ].filter(Boolean).join(" · ");
}
function liveStatus(live) {
  if (!live || !live.available) return { ok: false, text: SafeUI.LIVE_UNAVAILABLE };
  return { ok: true, text: `NEA readings as of ${String(live.fetched_at).slice(11, 16)} SGT` };
}

/* A shop, placed at its postcode's area point, or null. */
function areaOf(user, application, product) {
  if (user.centre || application?.business_class !== "shop" || application.area_lat == null) return null;
  return {
    query: new URLSearchParams({
      lat: application.area_lat, lng: application.area_lng, region: user.region, product,
    }).toString(),
    label: `around postcode ${escapeHtml(application.postcode)} (${escapeHtml(application.area_basis)})`,
  };
}

/* Where today's score and the ten-year replay are read, as a payout reads them: a hawker at its
   centre, a shop at its postcode's area point, anyone else (a platform worker) at its region's point. */
function scoringSite(user, application, staticData, product) {
  if (user.centre) {
    const query = new URLSearchParams({ centre: user.centre, product }).toString();
    return { kind: "centre", live: `/api/map/live?product=${encodeURIComponent(product)}`, burn: query,
             heading: "Today at your stall", label: `at ${escapeHtml(user.centre)}` };
  }
  const area = areaOf(user, application, product);
  if (area) {
    return { kind: "area", live: `/api/map/live/at?${area.query}`, burn: area.query,
             heading: "Today around your postcode", label: area.label };
  }
  const point = staticData.region_points?.[user.region];
  if (!point) return null;
  const [lat, lng] = point;
  return {
    kind: "region",
    live: `/api/map/live/at?${new URLSearchParams({ lat, lng, region: user.region, product })}`,
    burn: new URLSearchParams({ region: user.region, product }).toString(),
    heading: "Today in your region", label: `in the ${escapeHtml(user.region)} region`,
  };
}

/* Where the business is priced, as the server charges it: a hawker at its centre, a shop at its
   postcode's area, anyone else (a platform worker) by region. */
function pricedPlace(user, application) {
  if (user.centre) return { centre: user.centre };
  if (application?.business_class === "shop" && application.postcode) return { postcode: application.postcode };
  return { region: user.region };
}
function priceBasis(place) {
  if (place.centre) return "priced from the NEA stations nearest your centre";
  if (place.postcode) return "priced from the NEA stations nearest your postcode's area";
  return "priced from your region's NEA history";
}

/* ---------- business owner dashboard ---------- */
function smeSkeleton() {
  return `<div class="dash-head"><span class="skeleton title"></span><span class="skeleton line note"></span></div>
    <div class="kpis">${kpiSkeletons(["Today's loss score", "Payout due today", "Your weekly premium", "Expected trigger days"])}</div>
    ${tableSkeleton(4)}`;
}

async function renderSme(user) {
  if (!el("sme-dash")) el("dash").innerHTML = smeSkeleton();
  const [policies, staticData, rentTable, application] = await Promise.all([
    api("/api/policies"),
    api("/api/map/static"),
    api("/api/rent"),
    api("/api/applications/mine").catch(() => null),
  ]);
  const policy = policies[0] || null;
  const product = policy?.product || user.product || "cooked_food";
  const place = pricedPlace(user, application);
  const site = scoringSite(user, application, staticData, product);
  const [quote, live] = await Promise.all([
    post("/api/quote", { ...place, product }),
    site ? api(site.live).catch(() => null) : null,
  ]);
  const decision = application?.declined_before
    ? await api("/api/applications/mine/decision").catch(() => null) : null;
  const rent = rentTable.centres[user.centre];
  const index = staticData.hawker_centres.findIndex((c) => c.name === user.centre);
  const todays = !live?.available ? null : site?.kind !== "centre" ? live : index >= 0 ? live.hawker_losses[index] : null;
  // Recommend the smallest tier that pays a full day's rent at this centre.
  const rec = rent ? rent.recommended_tier : quote.tiers[0].tier;
  const view = { user, quote, policy, rent, rentTable, application, decision, site, place, todays, rec, live };

  el("dash").innerHTML = `<div id="sme-dash">
    ${smeHead(view)}
    <div class="kpis sme-kpis">${smeKpis(view)}</div>
    <div class="sme-grid">
      <section class="card" id="cover-card">${coverCard(view)}</section>
      <section class="card">${todayCard(view)}</section>
    </div>
    <section class="dash-section">
      ${user.centre
        ? mapPreview({ view: "owner", focus: user.centre, camera: "city" }, "Your stall on the risk atlas")
        : mapPreview({ view: "owner", camera: "city" }, `The ${titleCase(user.region)} region on the risk atlas`)}
    </section>
    ${site ? burnCard(view) : ""}
    <div id="model-history"></div>
    <div id="payouts-panel" class="dash-section"></div>
  </div>`;
  wireCoverSms();
  renderSmePayouts(el("payouts-panel"), Boolean(policy)).catch((error) => {
    el("payouts-panel").innerHTML = loadError("your payouts", error);
  });
  wireSme(view);
}

function smeHead({ user, application, site, place }) {
  const proof = businessProof(application);
  const where = [user.centre || (site?.kind === "area" ? site.label : null), `${titleCase(user.region)} region`, priceBasis(place)];
  return `<div class="dash-head">
    <h1 class="page-title">${escapeHtml(user.business_name || user.name)}</h1>
    ${proof ? `<p class="proof">${escapeHtml(proof)}</p>` : ""}
    <p class="page-sub">${where.filter(Boolean).join(" · ")}</p>
  </div>`;
}

function smeKpis({ quote, policy, rent, application, todays, rec, live }) {
  const status = liveStatus(live);
  const waitingEnds = application?.waiting_ends;
  const inWaitingPeriod = Boolean(policy && waitingEnds && TODAY() < waitingEnds);
  const payoutToday = todays && policy ? (todays.loss_percent / 100) * policy.daily_payout_sgd : null;
  const underReview = application?.status === "referred";
  const declined = application?.status === "declined";
  const payoutNote = policy ? `at ${policy.tier_label}` : underReview ? "after the underwriter replies"
    : declined ? "the underwriter declined cover" : "pick a tier below";
  return [
    kpi("Today's loss score",
      todays ? `<span class="num">${todays.loss_percent.toFixed(0)}%</span> ${dayChip(todays.loss_percent)}` : "–",
      status.text, "How much of a normal day's sales today's NEA readings take, scored by the live tariff. A payout follows this score, with no claim."),
    inWaitingPeriod
      ? kpi("Payout due today", "None yet", `In the ${WAITING_PERIOD_DAYS}-day waiting period until ${dateValue(waitingEnds)}`)
      : kpi("Payout due today", policy ? (payoutToday != null ? `<span class="num">${SGD(payoutToday)}</span>` : "–") : "No cover yet", payoutNote),
    kpi("Your weekly premium",
      `<span class="num">${SGD(policy ? policy.weekly_premium_sgd : quote.tiers.find((t) => t.tier === rec).weekly_premium_sgd)}</span>`,
      policy ? policy.tier_label : "recommended tier"),
    kpi("Expected trigger days", `<span class="num">${quote.expected_loss_days.toFixed(1)}</span>&nbsp;/&nbsp;yr`, "full-loss-day equivalents",
      "Days of full loss in an average year, from the NEA history where you are priced. Two half days count as one."),
    rent ? kpi("Your rent per trading day", `<span class="num">${SGD(rent.rent_per_day_sgd)}</span>`,
      `${rent.rent_class_label} centre${rent.estimated ? " · estimated" : ""}`) : "",
  ].join("");
}

function todayCard({ site, todays, live }) {
  const title = `<h2>${site ? site.heading : "Today at your stall"}</h2>`;
  if (!todays) return `${title}<p class="fine">${escapeHtml(liveStatus(live).text)}</p>
    <button class="btn small" id="retry-live" type="button">Refresh</button>`;
  return `${title}
    ${kv("24-h PSI (your region)", `<span class="num">${Math.round(todays.readings.haze)}</span>`)}
    ${kv("Wettest work hour (middle of the 3 nearest rain gauges that reported)", `<span class="num">${todays.readings.rain.toFixed(1)}</span>&nbsp;mm`)}
    ${kv("Hours at WBGT ≥32 °C (nearest heat station that reported)", `<span class="num">${todays.readings.heat}</span>&nbsp;h`)}
    <p class="fine card-foot">Readings refresh every 5 minutes from NEA. A payout needs no claim. It follows these numbers.</p>`;
}

function coverCard(view) {
  const { policy, application } = view;
  if (!policy && application?.status === "referred") return referredCover(application);
  if (!policy && application?.status === "declined") return declinedCover(view);
  return policy ? policyCover(view) : chooseCover(view);
}

function referredCover(application) {
  return `<div class="card-head"><h2>Your application</h2>${pill("warning", "With an underwriter")}</div>
    <p class="fine">Application ${application.id}, sent ${String(application.created_at).slice(0, 10)}. Because an insurer declined cover for this business before, an underwriter reviews it first. Cover starts, and you pay, only after they reply. We will contact you on ${escapeHtml(application.phone)}.</p>`;
}

function declinedCover({ application, decision }) {
  return `<div class="card-head"><h2>Your application</h2>${pill("critical", "Declined")}</div>
    <p class="fine">Application ${application.id}: the underwriter declined cover for this business. No cover started and you were not charged.</p>
    ${decision?.note ? `<p class="fine">Their note: ${escapeHtml(decision.note)}</p>` : ""}`;
}

function policyCover({ user, policy, rent, application, decision }) {
  const waitingEnds = application?.waiting_ends;
  const rentShare = rent ? Math.round((100 * policy.daily_payout_sgd) / rent.rent_per_day_sgd) : null;
  return `<div class="card-head"><h2>Your cover</h2>${pill("good", "Covered")}</div>
    ${waitingEnds && TODAY() < waitingEnds ? notice("warning", "clock",
      `<b>Waiting period.</b> Cover starts paying ${WAITING_PERIOD_DAYS} days after the start date, from ${SG_DATE(waitingEnds)}.`) : ""}
    ${kv("Tier", policy.tier_label)}
    ${kv("Pays per bad day", `<span class="num">${SGD(policy.daily_payout_sgd)}</span>`)}
    ${rent ? kv("Share of a day's rent", `<span class="num">${rentShare}%</span>`) : ""}
    ${kv("Cap", `${policy.max_paid_days_per_year} days / yr`)}
    ${kv("Weekly premium", `<span class="num">${SGD(policy.weekly_premium_sgd)}</span>`)}
    ${kv("Started", dateValue(policy.started_at))}
    ${application?.term_months ? kv("Term", `${application.term_months} months`) : ""}
    ${waitingEnds ? kv("Payouts from", dateValue(waitingEnds)) : ""}
    ${application?.cover_ends ? kv("Cover ends", dateValue(application.cover_ends)) : ""}
    ${decision?.decision === "approve" && decision.note ? `<p class="fine">Underwriter's note: ${escapeHtml(decision.note)}</p>` : ""}
    <p class="fine card-foot">Pays when NEA shows PSI>100, rain ≥20 mm/h, WBGT ≥32 °C for 2 h+, or a PUB flood alert near ${escapeHtml(user.centre) || `you, in the ${titleCase(user.region)} region`}. Below those levels nothing is paid.</p>
    <div class="cancel-row" id="cancel-row">
      <button class="btn small quiet" id="cancel-policy" type="button">Cancel cover</button>
    </div>`;
}

function chooseCover({ quote, rent, rentTable, rec }) {
  const rentShare = (payout) => Math.round((100 * payout) / rent.rent_per_day_sgd);
  const cards = quote.tiers.map((t) => `
    <div class="tier-card ${t.tier === rec ? "rec" : ""}" data-tier="${t.tier}">
      <span class="t">${t.label}${t.tier === rec ? ` <span class="chip accent">Recommended</span>` : ""}</span>
      <span class="p">${SGD(t.weekly_premium_sgd)}<small>/wk</small></span>
      <span class="d">${SGD(t.daily_payout_sgd)} a bad day · up to ${SGD(t.max_payout_per_year_sgd)} a year</span>
      ${rent ? `<span class="d">${rentShare(t.daily_payout_sgd)}% of a day's rent</span>` : ""}
    </div>`).join("");
  const why = !rent ? "We mark the recommended tier."
    : (rent.covers_rent
      ? `Recommended is the smallest tier that pays your whole day's rent (about ${SGD(rent.rent_per_day_sgd)}) on a full bad day.`
      : `No tier pays a whole day's rent here (about ${SGD(rent.rent_per_day_sgd)}). Recommended is the biggest tier.`)
      + ` ${rentSource(rent, rentTable)}`;
  return `<h2>Payung prices for your stall</h2>
    <div class="tiers-row">${cards}</div>
    <p class="fine">${why}</p>
    ${notice("info", "users", "<b>To start cover, ask your Income adviser or your hawker association.</b> They add Payung to your policy with you. Payung is not sold directly.")}
    <p class="fine">The recommended tier in one SMS, as we would text it to you:</p>
    <div class="cover-sms" data-cover-tier="${rec}" data-cover-weekly="${quote.tiers.find((t) => t.tier === rec)?.weekly_premium_sgd ?? ""}"></div>`;
}

function burnCard({ site }) {
  return `<section class="card dash-section" id="burn-card">
    <div class="card-head"><div><h2>Your last ten years, replayed</h2>
      <p class="fine">Every NEA reading since 2017 ${site.label}, scored by the live tariff.
        Set your normal daily sales; the losses scale with it, the payouts do not.</p></div></div>
    <label class="burn-takings">My daily sales (S$)
      <input type="number" id="burn-takings" min="50" max="20000" step="50" value="500" inputmode="numeric" /></label>
    <div id="burn-body" aria-live="polite">${burnSkeleton()}</div>
  </section>`;
}

function burnSkeleton() {
  return `<span class="skeleton line note"></span><div class="burn-chart" aria-hidden="true">${
    `<div class="burn-year"><div class="burn-bars"><span class="skeleton burn-ghost"></span></div></div>`.repeat(10)}</div>`;
}

function wireSme(view) {
  const { user, policy, site, rec } = view;
  el("cancel-policy")?.addEventListener("click", () => confirmCancel(user, policy));
  el("retry-live")?.addEventListener("click", () => renderSme(user));
  const burnTier = policy ? policy.tier : rec;
  const loadBurn = async () => {
    const takings = +el("burn-takings").value || 500;
    try {
      const burn = await api(`/api/map/burn?${site.burn}&tier=${burnTier}&takings=${takings}`);
      el("burn-body").innerHTML = renderBurn(burn, policy);
    } catch (error) {
      el("burn-body").innerHTML = `<p class="error" role="alert">Could not replay the last ten years: ${escapeHtml(error.message)}</p>`;
    }
  };
  if (!site) return;
  renderModelHistory(el("model-history"), site.burn, burnTier, view.todays).catch((error) => {
    el("model-history").innerHTML = loadError("your history since 1980", error);
  });
  el("burn-takings").addEventListener("change", loadBurn);
  loadBurn();
}

/* Cancelling stops cover at once, so it asks once, in place, before it acts. */
function confirmCancel(user, policy) {
  const row = el("cancel-row");
  row.innerHTML = `<p class="fine">Cancel your cover? It stops now, and Payung pays nothing for bad days after this.</p>
    <div class="row-actions">
      <button class="btn small danger" id="cancel-confirm" type="button">Yes, cancel cover</button>
      <button class="btn small ghost" id="cancel-keep" type="button">Keep my cover</button>
    </div><p class="error" role="alert"></p>`;
  el("cancel-confirm").focus();
  el("cancel-keep").addEventListener("click", () => renderSme(user));
  el("cancel-confirm").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.setAttribute("aria-busy", "true");
    try {
      await api(`/api/policies/${policy.id}`, { method: "DELETE" });
      await renderSme(user);
    } catch (error) {
      button.removeAttribute("aria-busy");
      row.querySelector(".error").textContent = `Could not cancel: ${error.message}`;
    }
  });
}

const BURN_CHART_PX = 120;
function renderBurn(burn, policy) {
  const t = burn.totals;
  const maxLost = Math.max(...burn.years.map((y) => Math.max(y.est_lost_sgd, y.paid_sgd)), 1);
  const height = (value, floor) => Math.max((value / maxLost) * BURN_CHART_PX, floor);
  const bars = burn.years.map((y) => {
    const tip = `${y.year}: lost about ${SGD(y.est_lost_sgd)}, Payung would have paid ${SGD(y.paid_sgd)}`;
    return `<div class="burn-year" data-tip="${tip}" aria-label="${tip}">
      <div class="burn-bars">
        <span class="burn-lost" style="height:${height(y.est_lost_sgd, 2)}px"></span>
        <span class="burn-paid" style="height:${height(y.paid_sgd, y.paid_sgd ? 2 : 0)}px"></span>
      </div>
      <span class="burn-label">${String(y.year).slice(2)}</span>
    </div>`;
  }).join("");
  const hz = t.by_hazard_sgd;
  return `
    <p class="burn-headline">Weather took about <b>${SGD(t.est_lost_sgd)}</b> from a business like
      yours since ${t.from_year}. With ${burn.tier_label}, Payung would have paid you
      <b>${SGD(t.paid_sgd)}</b> across <b>${t.trigger_days} bad days</b>, for
      ${SGD(t.premium_sgd)} of premium${policy ? "" : " (you are not covered yet)"}.</p>
    <div class="burn-chart" role="img" aria-label="Revenue lost and payouts per year since ${t.from_year}">${bars}</div>
    <div class="burn-legend"><span><i class="burn-lost"></i>Estimated revenue lost</span><span><i class="burn-paid"></i>What this tier would have paid</span></div>
    <p class="fine">Grey: estimated revenue lost each year. Blue: what this tier would have paid.
      Of the payouts, ${SGD(hz.rain)} came from heavy rain, ${SGD(hz.haze)} from haze and
      ${SGD(hz.heat)} from heat (heat readings exist from 2025).</p>`;
}

/* ---------- every year since 1980, filled in by the trained models (api/model_history.py) ---------- */
const PCT = (share) => `${Math.round(share * 100)}%`;
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_RANGE = (from, to) => `${new Date(from).toLocaleDateString("en-SG", { day: "numeric", month: "short" })} to ${new Date(to).toLocaleDateString("en-SG", { day: "numeric", month: "short" })}`;
const ONE_DP = (v) => Number(v).toFixed(1).replace(/\.0$/, "");
const colourDays = (r, y, g) => `<span class="day-chip day-red">${ONE_DP(r)} red</span> <span class="day-chip day-yellow">${ONE_DP(y)} yellow</span> <span class="day-chip day-green">${ONE_DP(g)} green</span>`;
const TIER_KEYS = ["tier_1", "tier_2", "tier_3", "tier_4"];

/* One thin bar per year since 1980, labelled every fifth year; hover or tap shows the year. */
function yearBars(years, value, describe, selected) {
  const max = Math.max(...years.map(value), 0.01);
  return `<div class="burn-chart dense" role="img" aria-label="One bar per year since ${years[0].year}">${years.map((y) => {
    const tip = `${y.year}: ${describe(y)}`;
    return `<div class="burn-year${y.year === selected ? " selected" : ""}" data-year="${y.year}" data-tip="${tip}" aria-label="${tip}">
      <div class="burn-bars"><span class="burn-paid${y.complete ? "" : " partial"}${y.el_nino ? " elnino" : ""}" style="height:${value(y) ? Math.max(value(y) / max * 88, 2) : 0}px"></span></div>
      <span class="burn-label">${y.year % 5 === 0 ? String(y.year).slice(2) : ""}</span>
    </div>`;
  }).join("")}</div>`;
}

function hazeOutlook(haze) {
  return `In El Niño years with haze data (${haze.haze_el_nino_years.join(", ")}) each region had about
    ${haze.haze_days_el_nino} days above PSI 100, against ${haze.haze_days_other} in other years.
    NOAA's latest El Niño index is ${haze.latest_oni} (${MONTH(haze.latest_oni_month)})${haze.el_nino_now
      ? ", an El Niño, so expect more haze days than usual" : ", not an El Niño"}.
    Once PSI passes 100, the next day is above 100 too in ${PCT(haze.next_day_bad_share)} of cases.`;
}

/* The filled-in history is measured where NEA measured it and model-filled before that. */
function sourceNote(year) {
  const m = year.measured_share;
  const part = (share) => share >= 0.95 ? "measured" : share <= 0.05 ? "model-filled" : `${PCT(share)} measured`;
  return `haze ${m.haze > 0 ? part(m.haze) : "no data"}, rain ${part(m.rain)}, heat ${part(m.heat)}`;
}

function yearDetail(h, year) {
  const y = h.years.find((r) => r.year === year);
  const hz = y.by_hazard_sgd;
  return `
    ${kv(`Paid in ${y.year}${y.complete ? "" : " so far"}`, `<b class="num">${SGD(y.paid_sgd)}</b>${y.capped ? " (yearly cap reached)" : ""}`)}
    ${kv("Payout days", `<span class="num">${y.trigger_days}</span>: ${colourDays(y.red_days, y.yellow_days, y.green_days)}`)}
    ${kv("From haze / rain / heat", `<span class="num">${SGD(hz.haze)} / ${SGD(hz.rain)} / ${SGD(hz.heat)}</span>`)}
    ${kv("Premium at this tier", `<span class="num">${SGD(h.since_1980.premium_sgd)}</span> a year`)}
    ${kv("Readings", `${sourceNote(y)}${y.el_nino ? " · El Niño year" : ""}`)}`;
}

function tenDaysText(h, todays) {
  const w = h.next_10_days;
  const a = w.all_years;
  const r = w.recent;
  const haze = h.haze_facts;
  const psiNow = todays ? Math.round(todays.readings.haze) : null;
  return `
    <p class="burn-headline">${DAY_RANGE(w.from, w.to)}: in <b>${Math.round(a.share_years_with_payout * a.years_checked)} of the last
      ${a.years_checked} years</b> these ten days brought at least one payout day here. On average they paid
      <b>${SGD(a.average_paid_sgd)}</b> at ${h.tier_label} over ${ONE_DP(a.average_trigger_days)} payout days
      (${colourDays(a.average_red_days, a.average_yellow_days, a.average_green_days)}). The most was ${SGD(a.highest_paid_sgd)} in ${a.highest_year}.</p>
    <p class="fine">Over the last ${r.years_checked} years alone: ${SGD(r.average_paid_sgd)} on average, a payout day in
      ${PCT(r.share_years_with_payout)} of them.</p>
    ${psiNow != null && psiNow >= haze.trigger_psi
      ? notice("warning", "clock", `<b>Today the 24-hour PSI in your region is ${psiNow}.</b> After a day above 100, the next day is above 100 too ${PCT(haze.next_day_bad_share)} of the time, so a haze payout tomorrow is likely.`)
      : psiNow != null ? `<p class="fine">Today the 24-hour PSI in your region is ${psiNow}, below the payout level.</p>` : ""}
    ${haze.el_nino_now ? notice("accent", "info", "An El Niño is under way. El Niño years bring far more haze days than other years.") : ""}
    <p class="fine card-foot">This is what these dates did in past years, not a weather forecast.</p>`;
}

function outlookYearsText(h) {
  const e = h.el_nino;
  const first = h.outlooks[0];
  const rows = h.outlooks.map((o) => `<tr>
    <td>Next ${o.years} years</td>
    <td class="num">${SGD(o.premium_sgd / (o.years * 12))}<span class="fine">/month</span></td>
    <td class="num">${SGD(o.typical_sgd)}</td>
    <td class="num">${SGD(o.bad_sgd)}</td>
    <td class="num">${SGD(o.highest_sgd)}<br><span class="fine">${o.highest_from_year} to ${o.highest_to_year}</span></td>
    <td>${colourDays(o.typical_red_days, o.typical_yellow_days, o.typical_green_days)}</td>
    <td class="num">${o.windows_paid_more_than_premium} of ${o.windows}</td>
  </tr>`).join("");
  return `
    <p class="burn-headline">Every stretch of the last ${first.basis_years} years (${first.basis_from_year} to ${first.basis_to_year})
      at this stall, at ${h.tier_label}: what you pay each month, what a typical, a bad and the worst stretch paid back, and the
      payout days to expect. These years run hotter and wetter than the decades before, so they are the best guide to what is coming.</p>
    <div class="table-wrap"><table class="data">
      <thead><tr><th>Period</th><th class="num">If you pay monthly</th><th class="num">Typical payout</th><th class="num">Bad stretch (1 in 10)</th>
        <th class="num">Worst stretch</th><th>Payout days, typical (every colour pays)</th><th class="num">Stretches that paid back more than the premium</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${kv(`El Niño years (${e.years.join(", ")})`, `<span class="num">${SGD(e.average_paid_sgd)}</span> a year on average`)}
    ${kv("Other years", `<span class="num">${SGD(e.average_paid_other_sgd)}</span> a year on average`)}
    <p class="fine">Every coloured day pays: a green day pays up to a third of ${SGD(h.daily_payout_sgd)}, a yellow day a third to
      two thirds, a red day more. ${hazeOutlook(h.haze_facts)}</p>
    <p class="fine card-foot">Only this stall's location is used. This is history, not a promise: Payung pays only when the
      readings reach a payout level, so a year can bring losses and no payout. The cover earns its keep in the bad stretches.</p>`;
}

async function renderModelHistory(target, place, tier, todays) {
  const h = await api(`/api/model/history?${place}&tier=${tier}`);
  const all = h.since_1980;
  const recent = h.recent;
  const big = h.haze_year;
  const from = h.read_from_nearest_centre
    ? `the readings at ${escapeHtml(h.centre)}, the hawker centre nearest you` : escapeHtml(h.centre);
  const complete = h.years.filter((y) => y.complete);
  let picked = complete[complete.length - 1].year;
  const describe = (y) => `${SGD(y.paid_sgd)} paid over ${y.trigger_days} payout days`
    + `${y.capped ? ", yearly cap reached" : ""}${y.complete ? "" : " (year so far)"}`;
  target.innerHTML = `
    <section class="card dash-section" id="model-years">
      <div class="card-head"><div><h2>Every year since 1980 at your stall</h2>
        <p class="fine">What ${h.tier_label} would have paid each year, from ${from}, scored by the live tariff. Only this location is used, never the whole market.</p></div></div>
      <p class="burn-headline">With ${h.tier_label} (${SGD(h.daily_payout_sgd)} for a full bad day, up to
        ${SGD(h.max_payout_per_year_sgd)} a year), Payung would have paid you about <b>${SGD(all.typical_sgd)}</b>
        in a typical year since ${all.from_year}, and the full <b>${SGD(all.worst_sgd)}</b> in ${all.worst_year}.
        ${all.years_without_payout ? `It paid nothing in ${all.years_without_payout} of ${all.years} years.`
          : `It paid something in every one of the ${all.years} years.`}</p>
      <div id="model-bars">${yearBars(h.years, (y) => y.paid_sgd, describe, picked)}</div>
      <div class="burn-legend"><span><i class="burn-paid"></i>Paid that year</span><span><i class="burn-paid elnino"></i>El Niño year</span></div>
      <div class="table-tools model-controls">
        <label class="tool-select">Year <select id="model-year">${[...h.years].reverse().map((y) =>
          `<option value="${y.year}"${y.year === picked ? " selected" : ""}>${y.year}${y.complete ? "" : " (so far)"}</option>`).join("")}</select></label>
        <span class="count">or tap a bar</span>
      </div>
      <div id="model-year-detail">${yearDetail(h, picked)}</div>
      ${notice("accent", "info", `<b>Measured</b> readings are used wherever they exist: haze from 2014, the wettest work hour of
        rain from 2017, heat from 2025. <b>Older years are filled in by our models</b>: heat is rebuilt from ERA5
        weather, and the wettest rain hour from each gauge's daily total, both matched to the measured years.
        Heat before 2025 is the least certain part. The money follows today's tariff and the yearly cap.`)}
    </section>
    <section class="card dash-section">
      <h2>What a year could look like for you</h2>
      <div class="kpis">
        ${kpi("Typical year", `<span class="num">${SGD(recent.typical_sgd)}</span>`, `paid, over the last ${recent.years} years`)}
        ${kpi("Bad year (1 in 10)", `<span class="num">${SGD(recent.bad_year_sgd)}</span>`, "paid")}
        ${kpi("Worst year", `<span class="num">${SGD(all.worst_sgd)}</span>`, `${all.worst_year}${big && big.year === all.worst_year ? ", the big haze" : ""}`)}
        ${kpi("Your premium", `<span class="num">${SGD(recent.premium_sgd)}</span>`, `a year, ${SGD(h.weekly_premium_sgd)} a week`)}
      </div>
      ${kv("Payout days in a typical year", colourDays(recent.typical_red_days, recent.typical_yellow_days, recent.typical_green_days))}
      ${kv("In a bad year (1 in 10)", colourDays(recent.bad_year_red_days, recent.bad_year_yellow_days, recent.bad_year_green_days))}
      <p class="fine card-foot">In ${recent.years_paid_more_than_premium} of the last ${recent.years} years the cover paid
        back more than its premium.${big ? ` A year like ${big.year} would pay you ${SGD(big.paid_sgd)}:
        ${SGD(big.by_hazard_sgd.haze)} for haze, ${SGD(big.by_hazard_sgd.rain)} for rain and
        ${SGD(big.by_hazard_sgd.heat)} for heat, over ${big.trigger_days} payout days.` : ""}</p>
    </section>
    <section class="card dash-section">
      <h2>The next 10 days</h2>
      ${tenDaysText(h, todays)}
    </section>
    <section class="card dash-section">
      <h2>The next 2, 5 and 10 years at your stall</h2>
      ${outlookYearsText(h)}
    </section>`;
  const pick = (year) => {
    picked = year;
    el("model-year").value = String(year);
    el("model-year-detail").innerHTML = yearDetail(h, year);
    el("model-bars").innerHTML = yearBars(h.years, (y) => y.paid_sgd, describe, picked);
    wireBars();
  };
  const wireBars = () => el("model-bars").querySelectorAll(".burn-year").forEach((bar) =>
    bar.addEventListener("click", () => pick(+bar.dataset.year)));
  el("model-year").addEventListener("change", (event) => pick(+event.target.value));
  wireBars();
}

/* The market figures at a premium of `m` times the tariff's. Payouts do not move; the premium does. */
function bookFigures(book, m) {
  const premium = book.premium_sgd * m;
  const years = book.years.map((y) => ({ ...y, loss_ratio: y.loss_ratio / m }));
  const complete = years.filter((y) => y.complete);
  const losing = complete.filter((y) => y.loss_ratio > 1).length;
  const average = complete.reduce((a, y) => a + y.loss_ratio, 0) / complete.length;
  const worst = complete.reduce((a, y) => (y.paid_sgd > a.paid_sgd ? y : a), complete[0]);
  const shortfall = Math.max(0, worst.paid_sgd - premium);
  const decade = book.next_10_years;
  const typical = complete[Math.floor(complete.length / 2)];
  const busiest = book.month_share.map((share, i) => [share, MONTH_NAMES[i]])
    .sort((a, b) => b[0] - a[0]).slice(0, 3);
  const e = book.el_nino;
  return `
    <div class="kpis">
      ${kpi("Premium pool", `<span class="num">${SGD_KPI(premium)}</span><wbr>/yr`, `${SGD(book.weekly_premium_per_policy_sgd * m)} a week per stall`)}
      ${kpi("Average loss ratio", `<span class="num">${PCT(average)}</span>`, "payouts ÷ premium, per year",
        "Every food stall in every hawker centre with one policy, run through every day since 1980 with today's tariff. Below 100% the premium covered the year's payouts.")}
      ${kpi("Years losing money", `<span class="num">${losing}</span> of ${complete.length}`, "loss ratio above 100%")}
      ${kpi("Worst year", `<span class="num">${worst.year}</span>`, `loss ratio ${PCT(worst.loss_ratio)}`)}
      ${kpi("Worst single day", `<span class="num">${SGD_KPI(book.worst_day.paid_sgd)}</span>`, `${SG_DATE(book.worst_day.day)}, ${PCT(book.worst_day.share_of_centres_paying)} of centres paid`)}
    </div>
    ${yearBars(years, (y) => y.loss_ratio, (y) => `loss ratio ${PCT(y.loss_ratio)}, ${SGD(y.paid_sgd)} paid, `
      + `${ONE_DP(y.yellow_days)} yellow and ${ONE_DP(y.green_days)} green days per stall${y.complete ? "" : " (year so far)"}`)}
    <div class="burn-legend"><span><i class="burn-paid"></i>Loss ratio that year</span><span><i class="burn-paid elnino"></i>El Niño year</span></div>
    <p class="fine">${shortfall > 0
      ? `In ${worst.year} payouts beat the premium by ${SGD(shortfall)}: that is the capital or reinsurance to hold.`
      : `Even ${worst.year} stayed within the premium${worst.loss_ratio > 0.85 ? ", but only just" : ""}: a worse year needs reinsurance.`}
      Haze hits every centre on the same day, so the worst day sets the cash you need at once.</p>
    ${kv("El Niño years against other years", `loss ratio <span class="num">${PCT(e.average_loss_ratio / m)}</span> against <span class="num">${PCT(e.average_loss_ratio_other / m)}</span>`)}
    ${kv("Payout days per stall in a typical year", colourDays(book.typical_red_days, book.typical_yellow_days, typical.green_days))}
    ${kv("Any ten years since 1980, loss ratio", `<span class="num">${PCT(decade.lowest_loss_ratio / m)}</span> to <span class="num">${PCT(decade.highest_loss_ratio / m)}</span>, typically ${PCT(decade.typical_loss_ratio / m)}`)}
    ${kv("When payouts come", `${busiest.map(([share, month]) => `${month} ${PCT(share)}`).join(", ")} of a year's`)}`;
}

function bookTenDays(book) {
  const w = book.next_10_days;
  const a = w.all_years;
  const r = w.recent;
  return `
    <p class="burn-headline">${DAY_RANGE(w.from, w.to)}: in <b>${Math.round(a.share_years_with_payout * a.years_checked)} of the last
      ${a.years_checked} years</b> these ten days paid at least one stall. Across the whole book they paid
      <b>${SGD(a.average_paid_sgd * book.policies)}</b> on average (${SGD(a.average_paid_sgd)} per policy), and the most was
      ${SGD(a.highest_paid_sgd * book.policies)} in ${a.highest_year}. Over the last ${r.years_checked} years: ${SGD(r.average_paid_sgd * book.policies)} on average.</p>`;
}

async function renderModelBook(target, live, staticData, tier = "tier_2") {
  const [book, insights] = await Promise.all([api(`/api/model/book?tier=${tier}`), api("/api/model/insights")]);
  const haze = insights.haze;
  const hazyNow = live?.available
    ? [...new Set(live.hawker_losses
        .map((loss, i) => (loss.readings.haze > haze.trigger_psi - 1 ? staticData.hawker_centres[i].region : null))
        .filter(Boolean))] : null;
  target.innerHTML = `
    <section class="card">
      <div class="card-head"><div><h2>The whole market, back-tested since 1980</h2>
        <p class="fine">Every food stall in every hawker centre (${book.policies.toLocaleString("en-SG")}) with one
          cooked-food policy each, run through every day since 1980 with today's tariff. Measured readings where
          they exist; older heat and rain filled in by our models.</p></div></div>
      <div class="table-tools model-controls">
        <label class="tool-select">Tier <select id="book-tier">${TIER_KEYS.map((t) =>
          `<option value="${t}"${t === tier ? " selected" : ""}>${t.replace("tier_", "Tier ")}</option>`).join("")}</select></label>
        <label class="tool-select">Premium <input type="range" id="book-premium" min="50" max="150" step="5" value="100" aria-describedby="book-premium-label" />
          <span id="book-premium-label" class="range-value">100% of the tariff's</span></label>
        <span class="count">Payouts do not move with the slider; the premium does.</span>
      </div>
      <div id="book-figures">${bookFigures(book, 1)}</div>
    </section>
    <section class="card dash-section">
      <h2>Outlook: the next 10 days, and when to pause sales</h2>
      ${bookTenDays(book)}
      ${kv(`El Niño index (NOAA, ${MONTH(haze.latest_oni_month)})`, `<span class="num">${haze.latest_oni}</span>${haze.el_nino_now ? " · El Niño" : ""}`)}
      ${kv("Days above PSI 100 per region", `<span class="num">${haze.haze_days_el_nino}</span> in El Niño years, <span class="num">${haze.haze_days_other}</span> in others`)}
      ${kv("A day above PSI 100 is followed by another", `<span class="num">${PCT(haze.next_day_bad_share)}</span> of the time`)}
      ${kv("Regions above PSI 100 now", hazyNow == null ? "live feed not ready" : hazyNow.length ? hazyNow.map(titleCase).join(", ") : "none")}
      ${notice("warning", "clock", `<b>Pause rule:</b> stop new sales in a region while its 24-hour PSI is above 100. The next day
        pays again ${PCT(haze.next_day_bad_share)} of the time, so a buyer then is buying a known loss.
        ${haze.el_nino_now ? "With an El Niño under way, hold extra reserve for the haze season (August to October)." : ""}`)}
      <p class="fine card-foot">The outlook above is the record of these dates since 1980, which is what a premium is
        priced on, not a weather forecast.</p>
    </section>`;
  el("book-tier").addEventListener("change", (event) => renderModelBook(target, live, staticData, event.target.value));
  el("book-premium").addEventListener("input", (event) => {
    const m = +event.target.value / 100;
    el("book-premium-label").textContent = `${event.target.value}% of the tariff's`;
    el("book-figures").innerHTML = bookFigures(book, m);
  });
}

/* ---------- insurer: underwriter queue ---------- */
/* One referred application, with what an underwriter needs to approve or decline it. */
function referralCard(application, quotes) {
  const tier = quotes[application.region]?.tiers.find((t) => t.tier === application.tier);
  const cover = application.add_safeday
    ? [tier ? tier.label : application.tier,
       application.term_months && `${application.term_months} months`,
       application.cover_start && `from ${SG_DATE(application.cover_start)}`].filter(Boolean).join(" · ")
    : "Business account only, no Payung";
  const place = [application.centre, application.stall_unit && `unit ${application.stall_unit}`,
    `${titleCase(application.region)} region`, application.postcode && `postcode ${application.postcode}`].filter(Boolean).join(" · ");
  const applicant = application.applicant_type === "company" ? `Company, UEN ${application.uen}` : "Individual";
  const row = (key, value) => value ? kv(key, escapeHtml(value)) : "";
  return `<article class="referral" data-application="${application.id}">
    <div class="referral-head"><h3>${escapeHtml(application.business_name || application.name)}</h3>
      <span class="fine">Application ${application.id} · sent ${String(application.created_at).slice(0, 10)}</span></div>
    <div class="referral-body">
      <div class="referral-facts">
        ${row("Owner", `${application.name}${application.designation ? `, ${application.designation}` : ""} · ${application.phone}`)}
        ${row("Business", businessProof(application))}
        ${row("Where", place)}
        ${row("Applicant", applicant)}
        ${row("Staff", application.staff_band)}
        ${row("Cover asked for", cover)}
      </div>
      <div class="referral-decide">
        ${notice("warning", "triangle-alert", `<b>Why an insurer declined before</b><br>${escapeHtml(application.declined_details)}`)}
        <label class="field">Note for the owner (optional)
          <textarea maxlength="500" rows="2"></textarea></label>
        <div class="row-actions">
          <button class="btn small secondary" type="button" data-decision="approve">${SafeUI.icon("check")}Approve</button>
          <button class="btn small danger" type="button" data-decision="decline">Decline</button>
        </div>
        <p class="error" role="alert"></p>
      </div>
    </div>
  </article>`;
}

function underwriterQueue(queue, quotes) {
  const decided = queue.recent_decisions;
  const waiting = queue.waiting.length
    ? `<div class="card referrals">${queue.waiting.map((a) => referralCard(a, quotes)).join("")}</div>`
    : `<div class="card flush"><div class="empty">${SafeUI.icon("shield-check")}<h3>No applications are waiting</h3>
        <p>When a business that an insurer declined before applies, it waits here until an underwriter approves or declines it.</p></div></div>`;
  return `${waiting}
    ${decided.length ? `<h3 class="subhead">Recent decisions</h3><div class="table-wrap"><table class="data">
      <thead><tr><th>Business</th><th>Decision</th><th>Note</th><th>By</th><th class="num">Date</th></tr></thead>
      <tbody>${decided.map((d) => `<tr><td>${escapeHtml(d.business_name || d.name)}</td>
        <td>${d.decision === "approve" ? pill("good", "Approved") : pill("critical", "Declined")}</td>
        <td class="note-cell">${escapeHtml(d.note || "–")}</td>
        <td>${escapeHtml(d.decided_by_name)}</td><td class="num">${SG_DATE(d.decided_at)}</td></tr>`).join("")}</tbody>
    </table></div>` : ""}`;
}

function wireReferrals(user) {
  document.querySelectorAll(".referral [data-decision]").forEach((button) =>
    button.addEventListener("click", async () => {
      const card = button.closest(".referral");
      const buttons = card.querySelectorAll("button");
      buttons.forEach((b) => { b.disabled = true; });
      button.setAttribute("aria-busy", "true");
      try {
        const note = card.querySelector("textarea").value.trim();
        await post(`/api/insurer/applications/${card.dataset.application}/decision`,
          { decision: button.dataset.decision, note: note || null });
        await renderInsurer(user);
      } catch (error) {
        card.querySelector(".error").textContent = `Could not save the decision: ${error.message}`;
        buttons.forEach((b) => { b.disabled = false; });
        button.removeAttribute("aria-busy");
      }
    }));
}

/* ---------- insurer: the book ---------- */
const POLICY_STATUS = {
  waiting: { label: "Waiting period", tone: "warning", order: 1 },
  active: { label: "Active", tone: "good", order: 0 },
  ended: { label: "Ended", tone: "muted", order: 2 },
};
const placeOf = (p) => p.centre || (p.postcode ? `Postcode ${p.postcode}` : "Not recorded");
const businessClassOf = (p) => p.business_class || (p.centre ? "hawker" : "");
const yearlyPremium = (p) => p.weekly_premium_sgd * WEEKS_PER_YEAR;
const mostInAYear = (p) => p.daily_payout_sgd * p.max_paid_days_per_year;
const ratioText = (ratio) => `${ratio.toFixed(1)} x`;

function policyStatus(policy) {
  const today = TODAY();
  if (policy.cover_ends && policy.cover_ends <= today) return "ended";
  return today < policy.waiting_ends ? "waiting" : "active";
}

function insurerShell(user) {
  return `<div id="insurer-dash">
    <div class="dash-head">
      <h1 class="page-title">Portfolio desk</h1>
      <p class="page-sub">${escapeHtml(user.insurer)} · signed in as ${escapeHtml(user.name)} · every number from the live tariff and NEA data</p>
    </div>
    <div class="kpis" id="ins-kpis" aria-busy="true">${kpiSkeletons(["Policies in force", "Premium booked", "Payout exposure", "Worst live loss now", "Market potential"])}</div>
    <nav class="quicklinks" aria-label="Insurer tools">
      <a href="/admin/" target="_blank" rel="noopener">${SafeUI.icon("sliders-horizontal", "i-lg")}
        <span><b>Tariff desk (admin portal)</b><span>Change the weights, payouts and premium calculations. Every save is a new version.</span></span>${SafeUI.icon("external-link")}</a>
      <a href="/map/?view=insurer&amp;mode=live" target="_blank" rel="noopener">${SafeUI.icon("map", "i-lg")}
        <span><b>Risk atlas</b><span>Hazard, exposure and live NEA readings over Singapore.</span></span>${SafeUI.icon("external-link")}</a>
    </nav>
    <section class="dash-section" aria-labelledby="tiers-title">
      <div class="section-head"><div><h2 id="tiers-title">Tiers in the live tariff</h2>
        <p class="page-sub">What each tier costs, what it pays and how many bad days its yearly cap covers.</p></div></div>
      <div id="ins-tiers">${tableSkeleton(5)}</div>
    </section>
    <section class="dash-section" aria-labelledby="book-title">
      <div class="section-head"><div><h2 id="book-title">Policies</h2>
        <p class="page-sub">Every policy on the book. Pick a row to see its cover, premium and payouts.</p></div></div>
      <div id="ins-book">${tableSkeleton(8)}</div>
    </section>
    <section class="dash-section" aria-labelledby="queue-title">
      <div class="section-head"><div><h2 id="queue-title">Waiting for an underwriter</h2>
        <p class="page-sub">Applications from businesses that an insurer declined before.</p></div></div>
      <div id="underwriting">${tableSkeleton(3)}</div>
    </section>
    <section class="dash-section" id="payouts-panel">${tableSkeleton(4)}</section>
    <section class="dash-section" aria-labelledby="model-title">
      <div class="section-head"><div><h2 id="model-title">Every year since 1980, and what comes next</h2>
        <p class="page-sub">The whole market back-tested with today's tariff, the premium you could charge, and the season ahead.</p></div></div>
      <div id="model-book">${tableSkeleton(6)}</div>
    </section>
    <section class="dash-section" aria-labelledby="map-title">
      <div class="section-head"><div><h2 id="map-title">The book on the map, live</h2>
        <p class="page-sub">Where the policies sit and what NEA reads there now.</p></div>
        <a class="btn small" href="/map/?view=insurer&amp;mode=live" target="_blank" rel="noopener"
          aria-label="Open full screen, in a new tab">${SafeUI.icon("maximize-2")}Open full screen</a></div>
      <div class="mapframe">
        <iframe src="/map/?view=insurer&amp;mode=live" title="The book on the map, live" loading="lazy"></iframe>
      </div>
    </section>
  </div>`;
}

async function renderInsurer(user) {
  if (!el("insurer-dash")) el("dash").innerHTML = insurerShell(user);
  const data = {
    portfolio: api("/api/insurer/portfolio"),
    book: api("/api/insurer/policies"),
    quotes: api("/api/map/quotes"),
    options: api("/api/options"),
    staticData: api("/api/map/static"),
    live: api("/api/map/live").catch(() => null),
    queue: api("/api/insurer/applications"),
  };
  // Counts from the book are extras on the KPIs and tiers; they still draw when it fails.
  const bookCounts = data.book.catch(() => null);
  await Promise.all([
    fill("ins-kpis", "the portfolio figures", async () => insurerKpis(
      await data.portfolio, await bookCounts, await data.live, await data.staticData, await data.quotes)),
    fill("ins-tiers", "the tiers", async () => {
      tierView.cache = { [API_DEFAULT_PRODUCT]: data.quotes };
      return tierSection(await tierQuotes(), await data.options, await bookCounts);
    }, wireTiers),
    fill("ins-book", "the policies", async () => bookSection(await data.book, await data.options), wireBook),
    fill("underwriting", "the underwriter queue", async () => underwriterQueue(await data.queue, (await data.quotes).quotes),
      () => wireReferrals(user)),
    renderInsurerPayouts(el("payouts-panel")).catch((error) => {
      el("payouts-panel").innerHTML = loadError("the payouts", error);
    }),
    (async () => renderModelBook(el("model-book"), await data.live, await data.staticData))().catch((error) => {
      el("model-book").innerHTML = loadError("the back-test", error);
    }),
  ]);
}

/* Put a section's HTML in its slot, or say it failed. A failed section never blanks the rest. */
async function fill(slotId, what, build, wire) {
  const slot = el(slotId);
  try {
    const html = await build();
    slot.innerHTML = html;
    slot.removeAttribute("aria-busy");
    wire?.(slot);
  } catch (error) {
    slot.innerHTML = loadError(what, error);
    slot.removeAttribute("aria-busy");
  }
}

function insurerKpis(portfolio, book, live, staticData, quotesData) {
  const demo = book ? book.filter((p) => p.demo).length : 0;
  const empty = portfolio.policies === 0;
  const maxLoss = live?.available && live.hawker_losses.length
    ? Math.max(...live.hawker_losses.map((l) => l.loss_percent)) : null;
  const stalls = staticData.hawker_centres.reduce((sum, c) => sum + c.food_stalls, 0);
  const centreQuote = (centre) => quotesData.centres?.[centre.name] ?? quotesData.quotes[centre.region];
  const poolTier = centreQuote(staticData.hawker_centres[0]).tiers[1];
  const marketPool = staticData.hawker_centres.reduce((sum, centre) =>
    sum + centreQuote(centre).tiers[1].yearly_premium_sgd * centre.food_stalls, 0);
  const sold = portfolio.policies - demo;
  const policiesNote = empty ? "No policies on the book yet" : !book ? ""
    : demo ? `${demo.toLocaleString("en-SG")} demo · ${sold.toLocaleString("en-SG")} sold here` : "sold on this platform";
  return [
    kpi("Policies in force", `<span class="num">${portfolio.policies.toLocaleString("en-SG")}</span>`, policiesNote,
      "Every policy on the book, including those still in their 30-day waiting period. Demo policies are made up for the pitch."),
    kpi("Premium booked", `<span class="num">${SGD_KPI(portfolio.annual_premium_sgd)}</span><wbr>/yr`,
      empty ? "Starts with the first policy sold" : `${SGD_KPI(portfolio.weekly_premium_sgd)}/wk`,
      "Weekly premiums of every policy on the book, times 52."),
    kpi("Payout exposure", `<span class="num">${SGD_KPI(portfolio.daily_payout_exposure_sgd)}</span><wbr>/day`,
      empty ? "Nothing to pay out yet" : "if every policy pays in full",
      "What one full bad day everywhere would cost: the payout per full bad day of every policy, added up."),
    kpi("Worst live loss now", maxLoss != null ? `<span class="num">${maxLoss.toFixed(0)}%</span> ${dayChip(maxLoss)}` : "–",
      escapeHtml(liveStatus(live).text),
      "The highest loss score at any hawker centre today, from live NEA readings, scored on the first tier."),
    kpi("Market potential", `<span class="num">${stalls.toLocaleString("en-SG")}</span> stalls`,
      `${SGD_KPI(marketPool)}/yr pool at ${escapeHtml(poolTier.label)}`,
      `Cooked-food stalls at every NEA hawker centre, each priced at ${poolTier.label} for its region.`),
  ].join("");
}

/* ---------- insurer: tier overview ---------- */
const API_DEFAULT_PRODUCT = "cooked_food";
const tierView = { product: API_DEFAULT_PRODUCT, region: "all", cache: {}, options: null, book: [] };
const tierQuotes = () =>
  tierView.cache[tierView.product] ??= api(`/api/map/quotes?product=${encodeURIComponent(tierView.product)}`);
const bandChip = (band) => `<span class="day-chip day-${band.key}">${band.label}</span>`;

/* Loss-score bands from /day-colour.js, highest first, each with its upper limit. */
function dayBands() {
  return DAY_COLOURS.map((band, i) => ({ ...band, to: i === 0 ? 100 : DAY_COLOURS[i - 1].from }));
}
/* How many days of one colour the yearly cap pays in full: fewest at the band's top, most at its floor. */
function capDays(dayCap, band) {
  const fewest = Math.floor((dayCap * 100) / band.to);
  if (!band.from) return `${fewest}+`;
  const most = Math.floor((dayCap * 100) / band.from);
  return fewest === most ? `${fewest}` : `${fewest}–${most}`;
}
const span = (values, format) => {
  const [low, high] = [Math.min(...values), Math.max(...values)];
  return format(low) === format(high) ? format(low) : `${format(low)}–${format(high)}`;
};

function tierRow(tierKey, quotes, regions, book) {
  const priced = regions.map((region) => quotes.quotes[region].tiers.find((t) => t.tier === tierKey));
  const tier = priced[0];
  const dayCap = Math.round(tier.max_payout_per_year_sgd / tier.daily_payout_sgd);
  const ratios = priced.map((t) => t.max_payout_per_year_sgd / t.yearly_premium_sgd);
  const policies = book ? book.filter((p) => p.tier === tierKey).length.toLocaleString("en-SG") : "–";
  return `<tr>
    <td>${escapeHtml(tier.label)}</td>
    <td class="num">${span(priced.map((t) => t.weekly_premium_sgd), SGD)}</td>
    <td class="num">${SGD(tier.daily_payout_sgd)}</td>
    <td class="num">${dayCap} days</td>
    <td class="num">${SGD(tier.max_payout_per_year_sgd)}</td>
    <td class="num">${span(ratios, (r) => r.toFixed(1))} x</td>
    ${dayBands().map((band) => `<td class="num">${capDays(dayCap, band)}</td>`).join("")}
    <td class="num">${policies}</td>
  </tr>`;
}

function bandLegend(quotes) {
  const firstTier = quotes.quotes[Object.keys(quotes.quotes)[0]].tiers[0];
  const pay = (share) => SGD((firstTier.daily_payout_sgd * share) / 100);
  const top = (band) => band.to === 100 ? "100%" : `under ${band.to}%`;
  const line = (band) => {
    const scores = `${band.from ? `${band.from}%` : "Above 0%"} to ${top(band)}`;
    const pays = band.from ? `${pay(band.from)} to ${band.to === 100 ? "" : "under "}${pay(band.to)}` : `under ${pay(band.to)}`;
    return `<li>${bandChip(band)}<span>Loss score ${scores.charAt(0).toLowerCase() + scores.slice(1)}. Pays that share of the tier's payout for the day, for example ${pays} at ${escapeHtml(firstTier.label)}.</span></li>`;
  };
  return `<ul class="band-legend">${dayBands().map(line).join("")}</ul>`;
}

function tierSection(quotes, options, book) {
  Object.assign(tierView, { options, book });
  const regions = tierView.region === "all" ? options.regions : [tierView.region];
  const product = options.products.find((p) => p.key === tierView.product);
  const regionTabs = [["all", "All regions"], ...options.regions.map((r) => [r, titleCase(r)])]
    .map(([key, label]) => `<button type="button" data-region="${key}" aria-pressed="${key === tierView.region}">${label}</button>`).join("");
  const helpRatio = "Most it can pay in a year divided by the yearly premium. Above 1 x, a business that hits the cap gets back more than it paid.";
  const helpDays = (band) => `${band.label}s the yearly cap pays in full: fewest when each scores ${band.to}%, ${band.from ? `most when each scores ${band.from}%` : "more when scores are lower"}.`;
  return `<div class="table-tools">
      <div class="segmented" role="group" aria-label="Region">${regionTabs}</div>
      <label class="tool-select">Product <select id="tier-product">${options.products.map((p) =>
        `<option value="${p.key}" ${p.key === tierView.product ? "selected" : ""}>${escapeHtml(p.label)}</option>`).join("")}</select></label>
    </div>
    <div class="table-wrap"><table class="data tiers-table">
      <thead><tr>
        <th>Tier</th>
        <th class="num">Weekly premium ${SafeUI.help("The live tariff's price for each region. A hawker or shop pays the price for its own centre or postcode area, so its premium can differ. A range covers the regions shown.")}</th>
        <th class="num">Payout per full bad day ${SafeUI.help("Paid for a day with a loss score of 100%. A partial day pays its share.")}</th>
        <th class="num">Day cap a year ${SafeUI.help("Full bad days the tier pays in a year. The cap is in money, so partial days use less of it.")}</th>
        <th class="num">Most it pays a year</th>
        <th class="num">Ratio ${SafeUI.help(helpRatio)}</th>
        ${dayBands().map((band) => `<th class="num"><span class="band-dot day-${band.key}" aria-hidden="true"></span>${band.label}s ${SafeUI.help(helpDays(band))}</th>`).join("")}
        <th class="num">Policies ${SafeUI.help("Policies on the book at this tier, every product and region.")}</th>
      </tr></thead>
      <tbody>${options.tiers.map((t) => tierRow(t.key, quotes, regions, book)).join("")}</tbody>
    </table></div>
    <p class="fine table-foot">Premiums for ${escapeHtml(product?.label || tierView.product).toLowerCase()} in ${tierView.region === "all" ? "all five regions" : `the ${titleCase(tierView.region)} region`}, from tariff pricing loads: uncertainty ${Math.round(quotes.pricing.uncertainty_load * 100)}%, bad years ${Math.round(quotes.pricing.catastrophe_load * 100)}%, expenses ${Math.round(quotes.pricing.expense_ratio * 100)}%, GST ${Math.round(quotes.pricing.gst_rate * 100)}%.</p>
    ${bandLegend(quotes)}`;
}

function wireTiers(slot) {
  const rerender = async (focusSelector) => {
    slot.innerHTML = tierSection(await tierQuotes(), tierView.options, tierView.book);
    wireTiers(slot);
    slot.querySelector(focusSelector)?.focus();
  };
  slot.querySelectorAll("[data-region]").forEach((button) => button.addEventListener("click", () => {
    tierView.region = button.dataset.region;
    rerender(`[data-region="${tierView.region}"]`).catch((error) => { slot.innerHTML = loadError("the tiers", error); });
  }));
  el("tier-product").addEventListener("change", (event) => {
    tierView.product = event.target.value;
    rerender("#tier-product").catch((error) => {
      delete tierView.cache[tierView.product];
      slot.innerHTML = loadError("the tiers", error);
    });
  });
}

/* ---------- insurer: policies table and drawer ---------- */
let bookPolicies = [];
const SOLD_BY = { adviser: "Income adviser", association: "Association" };
/* Who filled in the application with the customer: an adviser's code or an association's name. */
function channelOf(p) {
  if (p.sold_by === "adviser") return `Income adviser · ${p.adviser_code}`;
  if (p.sold_by === "association") return p.association;
  return "Not recorded";
}

function bookRow(p, tierOrder) {
  const status = policyStatus(p);
  const businessClass = businessClassOf(p);
  const search = [p.business_name, p.name, p.centre, p.postcode, p.region, p.tier_label, channelOf(p)].join(" ").toLowerCase();
  return `<tr class="clickable" tabindex="0" data-policy="${p.id}" data-tier="${p.tier}" data-region="${p.region}"
      data-class="${businessClass}" data-channel="${p.sold_by || ""}" data-status="${status}" data-search="${escapeHtml(search)}">
    <td data-value="${escapeHtml((p.business_name || p.name).toLowerCase())}"><span class="biz">${escapeHtml(p.business_name || p.name)}</span>${p.demo ? ` <span class="demo-tag">demo</span>` : ""}</td>
    <td>${escapeHtml(placeOf(p))}</td>
    <td>${titleCase(p.region)}</td>
    <td>${BUSINESS_CLASSES[businessClass] || "Not recorded"}</td>
    <td data-value="${tierOrder[p.tier] ?? 99}">${escapeHtml(p.tier_label)}</td>
    <td class="num" data-value="${p.weekly_premium_sgd}">${SGD(p.weekly_premium_sgd)}</td>
    <td class="num" data-value="${p.daily_payout_sgd}">${SGD(p.daily_payout_sgd)}</td>
    <td class="num" data-value="${p.started_at}">${SG_DATE(p.started_at)}</td>
    <td data-value="${POLICY_STATUS[status].order}">${pill(POLICY_STATUS[status].tone, POLICY_STATUS[status].label)}</td>
  </tr>`;
}

function filterSelect(id, label, all, choices) {
  return `<select id="${id}" aria-label="${label}"><option value="">${all}</option>${choices.map(([key, text]) =>
    `<option value="${key}">${escapeHtml(text)}</option>`).join("")}</select>`;
}

function bookSection(book, options) {
  bookPolicies = book;
  if (!book.length) return `<div class="card flush"><div class="empty">${SafeUI.icon("users")}
    <h3>No policies sold yet</h3>
    <p>When a business owner signs up and picks a tier, the policy lands here with its region, tier and payout exposure.</p>
    <a class="btn small" href="/buy/">Open the buy flow</a></div></div>`;
  const tierOrder = Object.fromEntries(options.tiers.map((t, i) => [t.key, i]));
  return `<div class="table-tools">
      <label class="input-icon">${SafeUI.icon("search")}<input type="search" id="book-search" placeholder="Search businesses" aria-label="Search policies" autocomplete="off" /></label>
      ${filterSelect("book-tier", "Tier", "All tiers", options.tiers.map((t) => [t.key, t.label]))}
      ${filterSelect("book-region", "Region", "All regions", options.regions.map((r) => [r, titleCase(r)]))}
      ${filterSelect("book-class", "Business type", "All business types",
        Object.entries(BUSINESS_CLASSES).filter(([key]) => book.some((p) => businessClassOf(p) === key)))}
      ${filterSelect("book-channel", "Filled in with", "All channels", Object.entries(SOLD_BY))}
      ${filterSelect("book-status", "Status", "All statuses", Object.entries(POLICY_STATUS).map(([k, s]) => [k, s.label]))}
      <span class="count" id="book-count" aria-live="polite"></span>
    </div>
    <div class="table-wrap book-wrap"><table class="data" id="book-table">
      <thead><tr>
        ${sortHeader("Business")}
        ${sortHeader("Centre or postcode", { help: "The hawker centre, or the postcode of a shop or platform worker." })}
        ${sortHeader("Region", { help: "The NEA PSI region the policy is priced in." })}
        ${sortHeader("Business type")}
        ${sortHeader("Tier")}
        ${sortHeader("Weekly", { num: true, help: "Premium the business pays each week." })}
        ${sortHeader("Payout/day", { num: true, help: "What Payung pays on a full bad day. A partial day pays its share." })}
        ${sortHeader("Started", { num: true })}
        ${sortHeader("Status", { help: `Waiting period: the first ${WAITING_PERIOD_DAYS} days, when nothing is paid. Active: payouts follow NEA readings. Ended: the term is over.` })}
      </tr></thead>
      <tbody>${book.map((p) => bookRow(p, tierOrder)).join("")}</tbody>
    </table></div>
    <div class="card flush" id="book-none" hidden><div class="empty">${SafeUI.icon("funnel")}
      <h3>No policies match</h3><p>Change the search or the filters to see more policies.</p>
      <button class="btn small" type="button" id="book-clear">Clear filters</button></div></div>`;
}

function wireBook(slot) {
  const table = el("book-table");
  if (!table) return;
  const controls = ["book-search", "book-tier", "book-region", "book-class", "book-channel", "book-status"].map(el);
  const [search, tier, region, businessClass, channel, status] = controls;
  const apply = () => {
    const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const row of table.tBodies[0].rows) {
      const match = words.every((w) => row.dataset.search.includes(w))
        && (!tier.value || row.dataset.tier === tier.value)
        && (!region.value || row.dataset.region === region.value)
        && (!businessClass.value || row.dataset.class === businessClass.value)
        && (!channel.value || row.dataset.channel === channel.value)
        && (!status.value || row.dataset.status === status.value);
      row.hidden = !match;
      shown += match;
    }
    const total = bookPolicies.length;
    const noun = total === 1 ? "policy" : "policies";
    el("book-count").textContent = shown === total ? `${total.toLocaleString("en-SG")} ${noun}`
      : `${shown.toLocaleString("en-SG")} of ${total.toLocaleString("en-SG")} ${noun}`;
    el("book-none").hidden = shown > 0;
    slot.querySelector(".book-wrap").hidden = shown === 0;
  };
  controls.forEach((control) => control.addEventListener("input", apply));
  el("book-clear").addEventListener("click", () => {
    controls.forEach((control) => { control.value = ""; });
    apply();
    search.focus();
  });
  SafeUI.sortable(table);
  const open = (row) => openPolicy(row, bookPolicies.find((p) => String(p.id) === row.dataset.policy));
  table.tBodies[0].addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-policy]");
    if (row) open(row);
  });
  table.tBodies[0].addEventListener("keydown", (event) => {
    const row = event.target.closest("tr[data-policy]");
    if (row && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      open(row);
    }
  });
  apply();
}

function openPolicy(row, policy) {
  row.setAttribute("aria-selected", "true");
  const status = POLICY_STATUS[policyStatus(policy)];
  const dialog = SafeUI.openDrawer({
    title: policy.business_name || policy.name,
    subtitle: escapeHtml([placeOf(policy), `${titleCase(policy.region)} region`, policy.tier_label].join(" · ")),
    body: policyDrawer(policy, status),
  });
  dialog.scrollTop = 0;
  dialog.addEventListener("close", () => row.removeAttribute("aria-selected"), { once: true });
}

function policyDrawer(p, status) {
  const most = mostInAYear(p);
  const yearly = yearlyPremium(p);
  const used = p.paid_sgd + p.owed_sgd;
  const usedShare = most ? Math.min(used / most, 1) : 0;
  const bands = dayBands().map((band) => `<span>${bandChip(band)} ${capDays(p.max_paid_days_per_year, band)}</span>`).join("");
  return `
    <div class="drawer-tags">${pill(status.tone, status.label)}${p.demo ? `<span class="demo-tag">demo</span>` : ""}</div>
    ${p.demo ? notice("", "info", "Demo policy, made up for the pitch. No real business holds it.") : ""}
    <section><h3>Business</h3>
      ${kv("Business type", BUSINESS_CLASSES[businessClassOf(p)] || "Not recorded")}
      ${kv(p.centre ? "Hawker centre" : "Postcode", escapeHtml(p.centre || p.postcode || "Not recorded"))}
      ${kv("Region", titleCase(p.region))}
      ${kv("Owner", escapeHtml(p.name))}
      ${kv("Filled in with", escapeHtml(channelOf(p)))}
    </section>
    <section><h3>Cover</h3>
      ${kv("Tier", escapeHtml(p.tier_label))}
      ${kv("Term", p.term_months ? `${p.term_months} months` : "Not recorded")}
      ${kv("Start date", dateValue(p.started_at))}
      ${kv(`End of the ${WAITING_PERIOD_DAYS}-day waiting period`, dateValue(p.waiting_ends))}
      ${p.cover_ends ? kv("Cover ends", dateValue(p.cover_ends)) : ""}
    </section>
    <section><h3>Premium and payouts</h3>
      ${kv("Weekly premium", `<span class="num">${SGD(p.weekly_premium_sgd)}</span>`)}
      ${kv("Yearly premium", `<span class="num">${SGD(yearly)}</span>`)}
      ${kv("Payout per full bad day", `<span class="num">${SGD(p.daily_payout_sgd)}</span>`)}
      ${kv("Day cap", `${p.max_paid_days_per_year} full days a year`)}
      ${kv("Most it can pay in a year", `<span class="num">${SGD(most)}</span>`)}
      ${kv(`Ratio ${SafeUI.help("Most it can pay in a year divided by the yearly premium.")}`, `<span class="num">${ratioText(most / yearly)}</span>`)}
      <div class="band-line"><span class="fine">Days the cap pays in full</span>${bands}</div>
    </section>
    <section><h3>Payouts so far</h3>
      ${kv("Paid", `<span class="num">${SGD(p.paid_sgd)}</span> · ${p.payouts_paid} payout${p.payouts_paid === 1 ? "" : "s"}`)}
      ${p.owed_sgd ? kv("Assessed, not paid yet", `<span class="num">${SGD(p.owed_sgd)}</span>`) : ""}
      <div class="cap-meter" role="meter" aria-valuemin="0" aria-valuemax="${most}" aria-valuenow="${used}"
        aria-label="Share of the yearly cap used"><span style="transform: scaleX(${usedShare})"></span></div>
      <p class="fine">${SGD(used)} of the ${SGD(most)} yearly cap used.</p>
    </section>
    ${p.underwriting_note ? `<section><h3>Underwriting note</h3>
      ${notice("", "shield-check", `<b>${p.underwriting_decision === "decline" ? "Declined" : "Approved"} by an underwriter.</b> ${escapeHtml(p.underwriting_note)}`)}</section>` : ""}`;
}

/* ---------- start ---------- */
async function wireDashboard() {
  if (!el("dash")) return;
  let user;
  try {
    user = await api("/api/auth/me");
  } catch {
    location.href = "/login/";
    return;
  }
  const place = user.role === "insurer" ? user.insurer : user.centre || user.business_name;
  const label = [user.name, place].filter(Boolean).join(" · ");
  const who = el("whoami");
  who.title = label;
  who.innerHTML = `<span class="avatar" aria-hidden="true">${escapeHtml(initials(user.name))}</span>
    <span class="who-text">${escapeHtml(label)}</span>`;
  el("signout").addEventListener("click", async () => {
    await post("/api/auth/logout", {});
    location.href = "/";
  });
  const render = () => (user.role === "insurer" ? renderInsurer(user) : renderSme(user));
  el("dash").addEventListener("click", (event) => {
    if (event.target.closest("[data-reload]")) render().catch(showDashboardError);
  });
  await render().catch(showDashboardError);
  el("dash").removeAttribute("aria-busy");
}

function showDashboardError(error) {
  el("dash").innerHTML = `<div class="dash-head"><h1 class="page-title">Dashboard</h1></div>${loadError("your dashboard", error)}`;
}

/* ---------- the policy in one SMS ---------- */
const SMS_LANGUAGES = { en: "English", zh: "中文", ms: "Melayu", ta: "தமிழ்" };

/** Draw the welcome SMS for a tier, exactly as /api/cover-text gives it, with a language switch.
    The landing page, the buy flow and the dashboard all show this one text, so what is sold is
    what is texted, with the no-pay sentence the brief asks for at the point of sale. */
async function coverSms(slot, tier, language = "en", weekly = null) {
  if (!slot) return;
  try {
    const params = new URLSearchParams({ tier, language });
    if (weekly) params.set("weekly", weekly);
    const cover = await api(`/api/cover-text?${params}`);
    const switcher = document.createElement("div");
    switcher.className = "sms-langs";
    switcher.setAttribute("role", "group");
    switcher.setAttribute("aria-label", "SMS language");
    for (const [key, label] of Object.entries(SMS_LANGUAGES)) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-pressed", String(key === language));
      button.addEventListener("click", () => coverSms(slot, tier, key, weekly));
      switcher.append(button);
    }
    const bubble = document.createElement("p");
    bubble.className = "sms";
    bubble.lang = language;
    bubble.textContent = cover.body;
    const size = document.createElement("p");
    size.className = "fine";
    size.textContent = `${cover.characters} characters · ${cover.segments === 1 ? "one SMS" : `${cover.segments} SMS parts`}`;
    slot.replaceChildren(switcher, bubble, size);
  } catch (error) {
    slot.textContent = `Could not load the cover text: ${error.message}`;
  }
}

function wireCoverSms() {
  document.querySelectorAll("[data-cover-tier]").forEach((slot) =>
    coverSms(slot, slot.dataset.coverTier, "en", slot.dataset.coverWeekly || null));
}

wireTheme();
updateNav();
wireLogin();
wireDashboard();
wireCoverSms();
