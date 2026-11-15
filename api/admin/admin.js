"use strict";

const SECTIONS = [
  {
    key: "hazards",
    label: "Hazards",
    icon: "cloud-rain",
    intro:
      "What makes a bad day and how much of a normal day's sales it takes. " +
      "Loss is the weight times the severity of the band the reading reaches.",
  },
  {
    key: "products",
    label: "Products",
    icon: "store",
    intro:
      "What the business sells. A lost day costs the margin on sales that never come back, " +
      "plus the cost of stock that spoils first: the shorter the shelf life and the slower " +
      "the restock, the more is thrown away.",
  },
  {
    key: "tiers",
    label: "Tiers",
    icon: "banknote",
    intro:
      "What each tier pays for a day with no sales, and how many such days it pays a year. " +
      "Each tier pays more than the one before it. Premium shares split a tier's premium before " +
      "GST into Income's five parts and must add up to 100%.",
  },
  {
    key: "pricing",
    label: "Pricing",
    icon: "sliders-horizontal",
    intro:
      "Where a tier is not offered, GST, and the loads that price a tier without " +
      "premium shares. Below them, the optional severe haze payout add-on.",
  },
  {
    key: "rent",
    label: "Rent classes",
    icon: "building-2",
    intro:
      "Hawker centres grouped by the median winning NEA bid for a cooked-food stall. " +
      "A stall's rent per trading day sets the tier we recommend: the smallest tier " +
      "that pays a whole day's rent. Rent never changes the premium.",
  },
];

const HAZARD_ICONS = {
  haze: "cloud-fog",
  rain: "cloud-rain",
  heat: "thermometer-sun",
  flood: "waves",
  closure: "store",
};

const PRICING_FIELDS = [
  {
    key: "uncertainty_load",
    label: "Data uncertainty load",
    hint:
      "Extra on the expected loss for short records, data gaps and rising extremes. " +
      "Prices only a tier without premium shares.",
  },
  {
    key: "catastrophe_load",
    label: "Catastrophe load",
    hint: "Capital and reinsurance for a year like the 2026 haze. Prices only a tier without premium shares.",
  },
  {
    key: "expense_ratio",
    label: "Expenses and commission",
    hint:
      "Share of the premium for running costs, partner commission and margin. " +
      "Prices only a tier without premium shares.",
  },
  {
    key: "distribution_expense_ratio",
    label: "Selling and distribution",
    hint: "The part of the expenses above spent on selling and partner commission. The rest is management.",
  },
  {
    key: "refer_above_limit_share",
    label: "Not offered above",
    hint:
      "A tier whose yearly premium is more than this share of its yearly limit is not offered " +
      "at that place. A tier whose premium reaches the whole limit is never offered.",
  },
  { key: "gst_rate", label: "GST", hint: "Quoted premiums include GST." },
];

// A tier's premium before GST in Income's five parts: shares that add up to 100%.
const PREMIUM_SHARES = [
  ["expected_payouts", "Expected payouts"],
  ["reinsurance", "Reinsurance"],
  ["management", "Management"],
  ["distribution", "Distribution"],
  ["profit", "Profit"],
];

// The optional severe haze payout add-on (tariff.haze_bonus): [key, label, hint, kind].
const HAZE_BONUS_FIELDS = [
  ["trigger_psi", "Haze reading that counts", "Daily highest 24-hour PSI in the policy's region, as payouts read it.", "number"],
  ["trigger_days", "Days in a policy year", "The lump sum is paid on the day the count reaches this.", "int"],
  ["lump_sum_daily_multiple", "Lump sum, times the daily amount", "25 gives S$4,875 on a S$195-a-day tier.", "number"],
  ["payout_multiple", "Lump sum over the add-on price", "The add-on's yearly price with GST is the lump sum divided by this.", "number"],
  ["payout_share", "Share of the add-on price paid out", "Priced yearly chance = this / ((1 + GST) x the multiple above).", "percent"],
  ["no_sale_months", "Months it cannot be added", "Month numbers, 1 to 12, separated by commas.", "number-list"],
  ["waiting_days", "Waiting days", "Days from purchase before a policy year's count starts.", "int"],
];

const FIELD_LABELS = {
  label: "Name",
  key: "Key",
  reading: "Reading",
  weight: "Weight",
  scaled_by_product: "Depends on the product",
  bands: "Bands",
  at_least: "From reading",
  severity: "Severity",
  sites_used: "Nearest stations read",
  assumed_days_per_year: "Assumed days a year",
  source: "Source",
  shelf_life_days: "Shelf life, days",
  restock_every_days: "Restock every, days",
  demand_sensitivity: "Demand lost on a bad day",
  gross_margin: "Gross margin",
  recovered_share: "Sales recovered later",
  daily_payout_sgd: "Payout for a day with no sales",
  max_paid_days_per_year: "Paid days a year, at most",
  at_least_monthly_sgd: "From median monthly bid",
  trading_days_per_month: "Trading days a month",
  stations_on_hold: "Stations on hold",
  premium_shares: "Premium shares",
  ...Object.fromEntries(PREMIUM_SHARES.map(([key, label]) => [key, `${label} share`])),
  ...Object.fromEntries(PRICING_FIELDS.map((f) => [f.key, f.label])),
  ...Object.fromEntries(HAZE_BONUS_FIELDS.map(([key, label]) => [key, label])),
};

const FIELD_HELP = {
  weight: "Share of a normal day's sales lost when the reading reaches the top band.",
  sites_used: "How many of the nearest NEA stations or gauges the price reads.",
  assumed_days_per_year:
    "Days a year this hazard reaches its top band, when there is no NEA history to count.",
  shelf_life_days: "How long stock keeps. 0 for work with no stock: nothing spoils.",
  restock_every_days: "Days between deliveries. Slow restocks mean more stock is thrown away.",
  demand_sensitivity: "Share of customers who stay away on a bad day.",
  gross_margin: "Share of each sale left after the cost of goods.",
  recovered_share: "Share of lost sales made up on later days.",
  daily_payout_sgd: "What the tier pays for a day at 100% loss.",
  max_paid_days_per_year: "The most full days the tier pays in a year.",
  stations_on_hold:
    "Station ids read as if they did not report, for price and payout, separated by commas.",
  premium_shares: "Share of the premium before GST that goes to this part.",
};

const PERCENT_FIELDS = new Set([
  "weight",
  "severity",
  "demand_sensitivity",
  "gross_margin",
  "recovered_share",
  "payout_share",
  ...PREMIUM_SHARES.map(([key]) => key),
  ...PRICING_FIELDS.map((f) => f.key),
]);

const NUMBER_LIMITS = {
  number: 'min="0" step="any"',
  optional: 'min="0" step="any"',
  percent: 'min="0" max="100" step="any"',
  int: 'min="0" step="1"',
};

const PREVIEW_DELAY_MS = 250;
const TOAST_MS = 4000;
const CHART_TICK_GAP = 22;
const AUTH_KEY = "auth";

const state = {
  auth: sessionStorage.getItem(AUTH_KEY),
  editor: null,
  regions: [],
  hazardsWithHistory: new Set(),
  centreRents: [],
  saved: null,
  savedQuote: null,
  draft: null,
  section: "hazards",
  region: null,
  product: null,
  readings: {},
};

const $ = (id) => document.getElementById(id);
const icon = (name, className) => SafeUI.icon(name, className);

// ---------- API ----------

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.auth) headers.Authorization = `Basic ${state.auth}`;
  let response;
  try {
    response = await fetch(path, { method, headers, body: body && JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, describeError(data.detail));
  return data;
}

function describeError(detail) {
  if (!Array.isArray(detail)) return detail ?? "The server did not answer. Try again.";
  return detail
    .map(({ loc, msg }) => {
      const message = msg.replace(/^Value error, /, "");
      const field = loc
        .filter((part) => part !== "body" && part !== "tariff")
        .map((part) => (typeof part === "number" ? part + 1 : part.replaceAll("_", " ")))
        .join(" › ");
      return field ? `${field}: ${message}` : message;
    })
    .join("\n");
}

// ---------- Sign in ----------

function encodeLogin(username, password) {
  const bytes = new TextEncoder().encode(`${username}:${password}`);
  return btoa(String.fromCharCode(...bytes));
}

function loginMessage(error) {
  if (error.status === 401) return "";
  if (error.status === 403) {
    return (
      "You are signed in to Payung as a business owner. The tariff desk is for insurer " +
      "staff: sign in as an insurer, or use the tariff desk login."
    );
  }
  return error.message;
}

async function begin() {
  try {
    await openDesk();
  } catch (error) {
    if (state.auth && error.status === 401) {
      forgetLogin();
      return begin();
    }
    showLogin(loginMessage(error));
  }
}

async function signIn(event) {
  event.preventDefault();
  const form = event.target;
  const { username, password } = form.elements;
  const missing = [username, password].filter((input) => !input.value);
  [username, password].forEach((input) => markInvalid(input, missing.includes(input)));
  if (missing.length) {
    showLoginError("Enter the tariff desk username and password.");
    missing[0].focus();
    return;
  }
  state.auth = encodeLogin(username.value, password.value);
  $("login-submit").setAttribute("aria-busy", "true");
  try {
    await openDesk();
    sessionStorage.setItem(AUTH_KEY, state.auth);
    password.value = "";
  } catch (error) {
    state.auth = null;
    const wrong = error.status === 401;
    markInvalid(password, wrong);
    showLoginError(wrong ? "Wrong username or password. Check both and try again." : error.message);
    if (wrong) password.select();
  } finally {
    $("login-submit").removeAttribute("aria-busy");
  }
}

function showLoginError(message) {
  $("login-error").innerHTML = message ? `${icon("circle-alert")}<span>${esc(message)}</span>` : "";
}

function forgetLogin() {
  sessionStorage.removeItem(AUTH_KEY);
  state.auth = null;
}

function showLogin(message = "") {
  if ($("drawer")?.open) $("drawer").close();
  state.saved = state.draft = state.editor = null;
  $("loading").hidden = true;
  $("desk").hidden = true;
  $("login").hidden = false;
  showLoginError(message);
}

async function signOut() {
  if (isDirty() && !confirm("Sign out and lose your unsaved changes?")) return;
  if (state.editor.signed_in_with === "session") {
    state.draft = null;
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    location.href = "/login/";
    return;
  }
  forgetLogin();
  showLogin();
}

function handleAuthError(error) {
  if (error.status !== 401 && error.status !== 403) return false;
  forgetLogin();
  showLogin("Your sign-in has ended. Sign in again to keep editing.");
  return true;
}

async function openDesk() {
  const editor = await api("/api/admin/me");
  const [options, saved, rents] = await Promise.all([
    api("/api/options"),
    api("/api/admin/tariff"),
    api("/api/rent").catch(() => ({ centres: {} })),
  ]);
  state.editor = editor;
  state.regions = options.regions;
  state.centreRents = Object.values(rents.centres);
  state.hazardsWithHistory = new Set(
    options.hazards.filter((hazard) => hazard.has_history).map((hazard) => hazard.key),
  );
  state.region ??= options.regions[0];
  renderWho();
  showSaved(saved);
  $("loading").hidden = true;
  $("login").hidden = true;
  $("desk").hidden = false;
}

function showSaved(saved) {
  state.saved = saved;
  state.draft = structuredClone(saved.tariff);
  renderEditor();
  renderPickers();
  renderReadings();
  renderVersion();
  draftChanged();
}

// ---------- Draft editing ----------

function pathIn(root, path) {
  return path.split(".").reduce((node, part) => node?.[part], root);
}

function getPath(path) {
  return pathIn(state.draft, path);
}

function setPath(path, value) {
  const parts = path.split(".");
  const last = parts.pop();
  parts.reduce((node, part) => node[part], state.draft)[last] = value;
}

function readInput(input) {
  const { kind } = input.dataset;
  if (kind === "bool") return input.checked;
  if (kind === "text") return input.value;
  const items = input.value.split(",").map((item) => item.trim()).filter(Boolean);
  if (kind === "list") return items;
  if (kind === "number-list") {
    const months = items.map(Number);
    return months.every((month) => Number.isInteger(month) && month >= 1 && month <= 12) ? months : NaN;
  }
  if (input.value === "") return kind === "optional" && input.validity.valid ? null : NaN;
  if (!input.validity.valid) return NaN;
  const value = Number(input.value);
  return kind === "percent" ? value / 100 : value;
}

function isDirty() {
  return Boolean(state.draft) && JSON.stringify(state.draft) !== JSON.stringify(state.saved.tariff);
}

function invalidPaths(node = state.draft, path = "") {
  if (typeof node === "number") return Number.isNaN(node) ? [path] : [];
  if (node === null || typeof node !== "object") return [];
  return Object.entries(node).flatMap(([key, child]) =>
    invalidPaths(child, path ? `${path}.${key}` : key),
  );
}

function sectionOf(path) {
  if (path.startsWith("haze_bonus.")) return "pricing";
  return path.startsWith("rent.") ? "rent" : path.split(".")[0];
}

function fieldName(path) {
  const parts = path.split(".");
  const name = FIELD_LABELS[parts.at(-1)];
  const item = parts.length > 2 ? getPath(parts.slice(0, 2).join("."))?.label : null;
  if (parts.includes("bands")) return `${item}, band ${Number(parts[3]) + 1}: ${name}`;
  return item && parts[0] !== "rent" ? `${item}: ${name}` : name;
}

function fixMessage(path) {
  const percent = PERCENT_FIELDS.has(path.split(".").at(-1));
  return `${fieldName(path)} needs ${percent ? "a number from 0 to 100" : "a number, 0 or more"}.`;
}

function draftChanged() {
  const changes = tariffChanges(state.saved.tariff, state.draft);
  const invalid = invalidPaths();
  const ready = changes.length > 0 && invalid.length === 0;
  const review = $("review");
  review.disabled = !ready;
  review.innerHTML = ready
    ? `Review changes <span class="count-badge num">${changes.length}</span>`
    : "Review changes";
  review.setAttribute("aria-label", ready ? `Review ${plural(changes.length, "change")}` : "Review changes");
  $("discard").disabled = changes.length === 0 && invalid.length === 0;
  renderDraftStatus(changes.length, invalid);
  renderNav(changes, invalid);
  schedulePreview();
}

function renderDraftStatus(changeCount, invalid) {
  const status = $("draft-status");
  status.className = "draft-status";
  if (invalid.length) {
    status.classList.add("critical");
    status.innerHTML = `${icon("circle-alert")}<button type="button" class="linklike" id="fix-first">
      ${esc(fixMessage(invalid[0]))}</button>`;
    $("fix-first").addEventListener("click", () => focusPath(invalid[0]));
  } else if (changeCount) {
    status.classList.add("accent");
    status.innerHTML = `<span class="dot" aria-hidden="true"></span>${plural(changeCount, "unsaved change")}`;
  } else {
    status.innerHTML = `${icon("check")}No unsaved changes`;
  }
}

function focusPath(path) {
  const section = sectionOf(path);
  if (section !== state.section) showSection(section);
  const input = document.querySelector(`[data-path="${path}"]`);
  input?.scrollIntoView({ block: "center" });
  input?.focus({ preventScroll: true });
}

function newItem(path, list) {
  const top = list.at(-1);
  if (path.endsWith(".bands")) return { at_least: top.at_least + 1, severity: top.severity };
  if (path === "rent.classes") {
    return {
      key: `class_${list.length + 1}`,
      label: "New class",
      at_least_monthly_sgd: top.at_least_monthly_sgd + 1000,
    };
  }
  const number = list.length + 1;
  if (path === "products") {
    return {
      key: `product_${number}`,
      label: "New product",
      shelf_life_days: 1,
      restock_every_days: 1,
      demand_sensitivity: 1,
      gross_margin: 0.32,
      recovered_share: 0.5,
      source: "",
    };
  }
  return {
    key: `tier_${number}`,
    label: `Tier ${number}`,
    daily_payout_sgd: Math.round(top.daily_payout_sgd * 1.5),
    max_paid_days_per_year: top.max_paid_days_per_year,
    ...(top.premium_shares ? { premium_shares: { ...top.premium_shares } } : {}),
  };
}

function onEdit(event) {
  const input = event.target.closest("[data-path]");
  if (!input) return;
  const { path } = input.dataset;
  const value = readInput(input);
  setPath(path, value);
  markInvalid(input, Number.isNaN(value));
  input.classList.toggle("changed", isChanged(path));
  const hazard = path.match(/^hazards\.(\d+)\./);
  if (hazard) $(`chart-${hazard[1]}`).innerHTML = bandChart(state.draft.hazards[hazard[1]]);
  if (path.startsWith("products.")) renderPickers();
  if (path.endsWith(".label")) retitle(path, value);
  if (path.startsWith("rent.")) $("rent-spread").innerHTML = rentSpread();
  draftChanged();
}

function retitle(path, label) {
  const title = document.querySelector(`[data-title-for="${path}"]`);
  if (title) title.textContent = label || "Unnamed";
}

function onEditorClick(event) {
  const button = event.target.closest("button[data-add], button[data-remove]");
  if (!button) return;
  if (button.dataset.add) {
    const list = getPath(button.dataset.add);
    list.push(newItem(button.dataset.add, list));
  } else {
    getPath(button.dataset.remove).splice(Number(button.dataset.index), 1);
  }
  renderEditor();
  renderPickers();
  renderReadings();
  draftChanged();
}

// ---------- Review and apply ----------

function percent(share) {
  return `${+(share * 100).toFixed(2)}%`;
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function shown(field, value) {
  if (value === null || value === undefined) return "empty";
  if (field === "bands") {
    return value
      .map((band) => `from ${number(band.at_least)}: ${percent(band.severity)}`)
      .join(", ");
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (field === "premium_shares") {
    return PREMIUM_SHARES.map(([key, label]) => `${label} ${percent(value[key] ?? 0)}`).join(", ");
  }
  if (PERCENT_FIELDS.has(field)) return percent(value);
  return typeof value === "number" ? number(value) : String(value);
}

function itemChanges(section, before, after) {
  const changes = [];
  for (const item of after) {
    const old = before.find((candidate) => candidate.key === item.key);
    if (!old) {
      changes.push({ where: `${section} › ${item.label}`, before: "", after: "Added" });
      continue;
    }
    for (const field of Object.keys(item)) {
      const [was, now] = [shown(field, old[field]), shown(field, item[field])];
      if (was !== now) {
        changes.push({
          where: `${section} › ${old.label} › ${FIELD_LABELS[field]}`,
          before: was,
          after: now,
        });
      }
    }
  }
  for (const item of before) {
    if (!after.some((candidate) => candidate.key === item.key)) {
      changes.push({ where: `${section} › ${item.label}`, before: "", after: "Removed" });
    }
  }
  return changes;
}

function tariffChanges(before, after) {
  const pricing = PRICING_FIELDS.filter(
    ({ key }) => before.pricing[key] !== after.pricing[key],
  ).map(({ key, label }) => ({
    where: `Pricing › ${label}`,
    before: shown(key, before.pricing[key]),
    after: shown(key, after.pricing[key]),
  }));
  const bonusBefore = before.haze_bonus ?? {};
  const bonusAfter = after.haze_bonus ?? {};
  const hazeBonus = [...HAZE_BONUS_FIELDS, ["source", "Source"]]
    .filter(([key]) => shown(key, bonusBefore[key]) !== shown(key, bonusAfter[key]))
    .map(([key, label]) => ({
      where: `Pricing › Severe haze payout › ${label}`,
      before: shown(key, bonusBefore[key]),
      after: shown(key, bonusAfter[key]),
    }));
  const rent = ["trading_days_per_month", "source"]
    .filter((key) => before.rent[key] !== after.rent[key])
    .map((key) => ({
      where: `Rent classes › ${FIELD_LABELS[key]}`,
      before: shown(key, before.rent[key]),
      after: shown(key, after.rent[key]),
    }));
  return [
    ...itemChanges("Hazards", before.hazards, after.hazards),
    ...itemChanges("Products", before.products, after.products),
    ...itemChanges("Tiers", before.tiers, after.tiers),
    ...pricing,
    ...hazeBonus,
    ...itemChanges("Rent classes", before.rent.classes, after.rent.classes),
    ...rent,
  ];
}

function changesTable(changes) {
  const rows = changes
    .map(
      ({ where, before, after }) => `<tr>
        <td>${esc(where)}</td>
        <td class="before"><div class="cell-text">${esc(before) || "–"}</div></td>
        <td class="after"><div class="cell-text">${esc(after)}</div></td>
      </tr>`,
    )
    .join("");
  return `<div class="table-wrap"><table class="data changes">
    <thead><tr><th>What</th><th>Before</th><th>After</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

async function premiumsOf(tariff) {
  const body = { tariff, region: state.region, product: state.product, readings: {} };
  const preview = await api("/api/admin/preview", { method: "POST", body });
  return preview.quote.tiers;
}

function impactTable(before, after) {
  const rows = after
    .map((tier) => {
      const old = before.find((candidate) => candidate.tier === tier.tier);
      const was = old ? money(old.weekly_premium_sgd) : "–";
      return `<tr><td>${esc(tier.label)}</td>
        <td class="num before">${was}</td><td class="num after">${money(tier.weekly_premium_sgd)}</td></tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table class="data changes">
    <thead><tr><th>Tier</th><th class="num">Before</th><th class="num">After</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

function showReviewError(message) {
  $("review-error").hidden = !message;
  $("review-error").innerHTML = message ? `${icon("circle-alert")}<span>${esc(message)}</span>` : "";
}

function reviewBody(changes) {
  const product = state.draft.products.find((item) => item.key === state.product);
  return `<section>
      <h3>What changes</h3>
      ${changesTable(changes)}
    </section>
    <section>
      <h3>Weekly premium: ${esc(product.label)}, ${esc(titleCase(state.region))}</h3>
      <div id="review-impact"><span class="skeleton line"></span><span class="skeleton line"></span></div>
    </section>
    <div class="review-actions">
      <p class="notice critical" id="review-error" role="alert" hidden></p>
      <button type="button" class="btn" data-close-review>Keep editing</button>
      <button type="button" class="btn primary" id="apply" disabled>Apply changes</button>
    </div>`;
}

async function openReview() {
  const changes = tariffChanges(state.saved.tariff, state.draft);
  const dialog = SafeUI.openDrawer({
    title: "Review changes",
    subtitle: `${plural(changes.length, "change")} to version ${state.saved.version}. Nothing is saved until you apply.`,
    body: reviewBody(changes),
  });
  dialog.querySelector("[data-close-review]").addEventListener("click", () => dialog.close());
  $("apply").addEventListener("click", apply);
  try {
    const [before, after] = await Promise.all([
      premiumsOf(state.saved.tariff).catch(() => []),
      premiumsOf(state.draft),
    ]);
    $("review-impact").innerHTML = impactTable(before, after);
    $("apply").disabled = false;
  } catch (error) {
    if (handleAuthError(error)) return;
    $("review-impact").innerHTML = "";
    showReviewError(`Fix this before applying. ${error.message}`);
  }
}

async function apply() {
  const button = $("apply");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  showReviewError("");
  try {
    const body = { based_on_version: state.saved.version, tariff: state.draft };
    const saved = await api("/api/admin/tariff", { method: "PUT", body });
    $("drawer").close();
    showSaved(saved);
    toast(`Saved. The tariff is now version ${saved.version}.`);
  } catch (error) {
    if (handleAuthError(error)) return;
    showReviewError(`Not saved. ${error.message}`);
    button.disabled = error.status !== 0;
  } finally {
    button.removeAttribute("aria-busy");
  }
}

function discard() {
  if (confirm("Discard all unsaved changes?")) showSaved(state.saved);
}

// ---------- Rendering helpers ----------

function esc(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value ?? "").replace(/[&<>"']/g, (char) => entities[char]);
}

function number(value) {
  return Number(value).toLocaleString("en-SG");
}

function money(value) {
  const amount = value.toLocaleString("en-SG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `S$${amount}`;
}

function titleCase(word) {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

function initials(name) {
  const words = name.trim().split(/\s+/);
  return words.map((word) => word[0]).join("").slice(0, 2).toUpperCase() || "?";
}

function isChanged(path) {
  return JSON.stringify(pathIn(state.saved.tariff, path)) !== JSON.stringify(getPath(path));
}

function markInvalid(input, invalid) {
  if (invalid) input.setAttribute("aria-invalid", "true");
  else input.removeAttribute("aria-invalid");
}

function field(path, kind, label) {
  const value = getPath(path);
  const changed = isChanged(path) ? "changed" : "";
  const named = `data-path="${path}" data-kind="${kind}" aria-label="${esc(label)}" class="${changed}"`;
  if (kind === "bool") return `<input type="checkbox" ${named} ${value ? "checked" : ""}>`;
  if (kind === "text") return `<input ${named} value="${esc(value)}">`;
  if (kind === "list" || kind === "number-list") {
    return `<input ${named} value="${esc(Array.isArray(value) ? value.join(", ") : "")}">`;
  }
  if (kind === "long-text") {
    return `<textarea data-path="${path}" data-kind="text" aria-label="${esc(label)}" class="${changed}">${esc(value)}</textarea>`;
  }
  const display = kind === "percent" ? +(value * 100).toFixed(2) : value;
  const limits = NUMBER_LIMITS[kind] ?? NUMBER_LIMITS.number;
  const invalid = Number.isNaN(value) ? 'aria-invalid="true"' : "";
  const shownValue = Number.isFinite(display) ? display : "";
  return `<input type="number" inputmode="decimal" ${limits} ${named} ${invalid} value="${shownValue}">`;
}

function withUnit(input, unit, side = "after") {
  return `<span class="unit-input ${side}">${input}<span class="unit" aria-hidden="true">${unit}</span></span>`;
}

function labelled(label, control, help = "") {
  return `<label class="field"><span class="field-label">${esc(label)}${help ? SafeUI.help(help) : ""}</span>${control}</label>`;
}

function removeButton(listPath, index, allowed, what) {
  if (!allowed) return "";
  return `<button type="button" class="icon-btn remove" data-remove="${listPath}" data-index="${index}"
    aria-label="Remove ${esc(what)}" data-tip="Remove ${esc(what)}">${icon("x")}</button>`;
}

function addButton(listPath, label) {
  return `<button type="button" class="btn small add" data-add="${listPath}">${icon("plus")}${label}</button>`;
}

function option(value, label, selected) {
  const mark = value === selected ? "selected" : "";
  return `<option value="${esc(value)}" ${mark}>${esc(label)}</option>`;
}

function toast(message) {
  const box = $("toast");
  box.innerHTML = `${icon("check")}<span>${esc(message)}</span>`;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (box.hidden = true), TOAST_MS);
}

// ---------- Layout ----------

function renderWho() {
  const { name, organisation } = state.editor;
  const text = `${name} · ${organisation}`;
  $("who").title = text;
  $("who").innerHTML = `<span class="avatar" aria-hidden="true">${esc(initials(name))}</span>
    <span class="who-text">${esc(text)}</span><span class="visually-hidden">Signed in as ${esc(text)}</span>`;
}

function renderVersion() {
  const { version, saved_at, saved_by } = state.saved;
  const when = new Date(saved_at).toLocaleString("en-SG", {
    dateStyle: "medium",
    timeStyle: "short",
  });
  $("version").title = `Version ${version}, saved ${when} by ${saved_by}`;
  $("version").innerHTML = `<b>Version ${version}</b>
    <span class="saved-when">saved ${esc(when)} by ${esc(saved_by)}</span>`;
}

function renderNav(changes, invalid) {
  $("sections").innerHTML = SECTIONS.map((section) => {
    const current = section.key === state.section;
    const changed = changes.some((change) => change.where.startsWith(`${section.label} ›`));
    const broken = invalid.some((path) => sectionOf(path) === section.key);
    const mark = broken
      ? `<span class="nav-mark critical">${icon("circle-alert")}<span class="visually-hidden">needs a fix</span></span>`
      : changed
        ? `<span class="nav-mark accent"><span class="dot"></span><span class="visually-hidden">changed</span></span>`
        : "";
    return `<button type="button" data-section="${section.key}" aria-current="${current}">
      ${icon(section.icon)}<span class="nav-label">${section.label}</span>${mark}</button>`;
  }).join("");
}

function renderEditor() {
  const section = SECTIONS.find((item) => item.key === state.section);
  const editors = {
    hazards: hazardsEditor,
    products: productsEditor,
    tiers: tiersEditor,
    pricing: pricingEditor,
    rent: rentEditor,
  };
  $("editor").innerHTML = `
    <header class="editor-head"><h2 class="page-title">${section.label}</h2>
      <p class="page-sub">${section.intro}</p></header>
    ${editors[section.key]()}`;
}

function showSection(key) {
  state.section = key;
  renderEditor();
  draftChanged();
  scrollTo({ top: 0 });
  $("sections")
    .querySelector('[aria-current="true"]')
    .scrollIntoView({ block: "nearest", inline: "nearest" });
}

function onSectionClick(event) {
  const button = event.target.closest("button[data-section]");
  if (button) showSection(button.dataset.section);
}

// ---------- Section editors ----------

function hazardsEditor() {
  return state.draft.hazards.map(hazardCard).join("");
}

function hazardMark(key) {
  return `<span class="hazard-mark" style="--mark: var(--${esc(key)}, var(--closure))">${icon(HAZARD_ICONS[key] ?? "triangle-alert")}</span>`;
}

function bandRows(hazard, base) {
  return hazard.bands
    .map(
      (_, b) => `<tr>
        <td>${field(`${base}.bands.${b}.at_least`, "number", `${hazard.label} band ${b + 1} starts at`)}</td>
        <td>${withUnit(field(`${base}.bands.${b}.severity`, "percent", `${hazard.label} band ${b + 1} severity`), "%")}</td>
        <td class="row-action">${removeButton(`${base}.bands`, b, hazard.bands.length > 1, `band ${b + 1}`)}</td>
      </tr>`,
    )
    .join("");
}

function hazardCard(hazard, i) {
  const base = `hazards.${i}`;
  const daysNote = state.hazardsWithHistory.has(hazard.key)
    ? "Leave empty to price from NEA history."
    : "No NEA history. Set the days to price this hazard.";
  return `<article class="card hazard" style="--mark: var(--${esc(hazard.key)}, var(--closure))">
    <header class="hazard-head">
      ${hazardMark(hazard.key)}
      <div><h3 class="card-title">${esc(hazard.label)}</h3><p class="fine">${esc(hazard.reading)}</p></div>
    </header>
    <div class="field-grid">
      ${labelled("Weight", withUnit(field(`${base}.weight`, "percent", `${hazard.label} weight`), "%"), FIELD_HELP.weight)}
      ${labelled("Nearest stations read", field(`${base}.sites_used`, "int", `${hazard.label} nearest stations read`), FIELD_HELP.sites_used)}
      <label class="field"><span class="field-label">Assumed days a year${SafeUI.help(FIELD_HELP.assumed_days_per_year)}</span>
        ${field(`${base}.assumed_days_per_year`, "optional", `${hazard.label} assumed days a year`)}
        <span class="hint">${daysNote}</span></label>
      ${"stations_on_hold" in hazard ? labelled("Stations on hold", field(`${base}.stations_on_hold`, "list", `${hazard.label} stations on hold`), FIELD_HELP.stations_on_hold) : ""}
    </div>
    <label class="check">
      ${field(`${base}.scaled_by_product`, "bool", `${hazard.label} loss depends on the product`)}
      Loss depends on the product sold</label>
    <div class="bands">
      <div class="bands-table">
        <h4>Severity bands</h4>
        <div class="table-wrap"><table class="data edit">
          <thead><tr><th>From reading</th><th>Severity</th><th><span class="visually-hidden">Remove</span></th></tr></thead>
          <tbody>${bandRows(hazard, base)}</tbody>
        </table></div>
        ${addButton(`${base}.bands`, "Add band")}
      </div>
      <figure class="chart" id="chart-${i}">${bandChart(hazard)}</figure>
    </div>
    ${labelled("Source", field(`${base}.source`, "long-text", `${hazard.label} source`))}
  </article>`;
}

function chartTicks(bands, x, height) {
  let lastX = -Infinity;
  return bands
    .map((band) => {
      const at = x(band.at_least);
      if (at - lastX < CHART_TICK_GAP) return "";
      lastX = at;
      return `<text x="${at}" y="${height - 6}" text-anchor="middle">${number(band.at_least)}</text>`;
    })
    .join("");
}

function bandChart(hazard) {
  const { bands, weight } = hazard;
  const values = [weight, ...bands.flatMap((b) => [b.at_least, b.severity])];
  if (!values.every(Number.isFinite)) {
    return `<p class="chart-note">Fill in the weight and every band to see the chart.</p>`;
  }
  if (bands.some((band, b) => b > 0 && band.at_least <= bands[b - 1].at_least)) {
    return `<p class="chart-note">Put the bands in rising order to see the chart.</p>`;
  }
  const width = 300,
    height = 160,
    left = 38,
    right = 12,
    top = 10,
    bottom = 24;
  const first = Math.min(0, bands[0].at_least);
  const last = bands.at(-1).at_least;
  const end = last + Math.max((last - first) * 0.25, 1);
  const x = (reading) => left + ((reading - first) / (end - first)) * (width - left - right);
  const y = (share) => height - bottom - share * (height - top - bottom);
  const steps = bands.map((b) => `H${x(b.at_least)}V${y(weight * b.severity)}`).join("");
  const line = `M${x(first)},${y(0)}${steps}H${x(end)}`;
  const grid = [0, 0.5, 1]
    .map(
      (share) => `<line class="grid" x1="${left}" x2="${width - right}" y1="${y(share)}" y2="${y(share)}"/>
        <text x="${left - 6}" y="${y(share) + 4}" text-anchor="end">${share * 100}%</text>`,
    )
    .join("");
  const peak = Math.max(...bands.map((b) => weight * b.severity));
  const summary = `${hazard.label}: loss rises in ${bands.length} steps to ${Math.round(peak * 100)}%`;
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(summary)}">
      ${grid}<path class="area" d="${line}V${y(0)}Z"/><path class="line" d="${line}"/>
      ${chartTicks(bands, x, height)}
    </svg>
    <figcaption>Share of a day's sales lost by reading, before the product adjustment.</figcaption>`;
}

function productCard(product, i) {
  const base = `products.${i}`;
  const amount = (key, kind = "number") =>
    labelled(FIELD_LABELS[key], field(`${base}.${key}`, kind, `${product.label} ${FIELD_LABELS[key]}`), FIELD_HELP[key]);
  const share = (key) =>
    labelled(
      FIELD_LABELS[key],
      withUnit(field(`${base}.${key}`, "percent", `${product.label} ${FIELD_LABELS[key]}`), "%"),
      FIELD_HELP[key],
    );
  return `<article class="card item">
    <header class="card-head">
      <h3 class="card-title" data-title-for="${base}.label">${esc(product.label) || "Unnamed"}</h3>
      ${removeButton("products", i, state.draft.products.length > 1, product.label || "this product")}
    </header>
    <div class="field-grid">
      ${labelled("Name", field(`${base}.label`, "text", "Product name"))}
      ${labelled("Key", field(`${base}.key`, "text", "Product key"), "The code quotes and policies use. Change it only for a new product.")}
      ${amount("shelf_life_days")}
      ${amount("restock_every_days")}
      ${share("demand_sensitivity")}
      ${share("gross_margin")}
      ${share("recovered_share")}
    </div>
    ${labelled("Source", field(`${base}.source`, "long-text", `${product.label} source`))}
  </article>`;
}

function productsEditor() {
  return `${state.draft.products.map(productCard).join("")}
    <div>${addButton("products", "Add product")}</div>`;
}

function tiersEditor() {
  // Share columns show when the tariff has premium shares; a tier without them uses the loads.
  const shares = state.draft.tiers.some((tier) => tier.premium_shares);
  const shareCells = (tier, base) =>
    shares
      ? PREMIUM_SHARES.map(([key, label]) =>
          tier.premium_shares
            ? `<td>${withUnit(field(`${base}.premium_shares.${key}`, "percent", `${tier.label} ${label} share`), "%")}</td>`
            : `<td><span class="fixed">Pricing loads</span></td>`,
        ).join("")
      : "";
  const shareHeads = shares
    ? PREMIUM_SHARES.map(([, label]) => `<th>${label} ${SafeUI.help(FIELD_HELP.premium_shares)}</th>`).join("")
    : "";
  const rows = state.draft.tiers
    .map((tier, i) => {
      const base = `tiers.${i}`;
      return `<tr>
        <td>${field(`${base}.label`, "text", "Tier name")}</td>
        <td>${field(`${base}.key`, "text", "Tier key")}</td>
        <td>${withUnit(field(`${base}.daily_payout_sgd`, "number", `${tier.label} payout for a day with no sales`), "S$", "before")}</td>
        <td>${field(`${base}.max_paid_days_per_year`, "int", `${tier.label} paid days a year`)}</td>
        ${shareCells(tier, base)}
        <td class="row-action">${removeButton("tiers", i, state.draft.tiers.length > 1, tier.label || "this tier")}</td>
      </tr>`;
    })
    .join("");
  return `<section class="card">
    <div class="table-wrap"><table class="data edit">
      <thead><tr>
        <th>Name</th><th>Key</th>
        <th>Payout a day ${SafeUI.help(FIELD_HELP.daily_payout_sgd)}</th>
        <th>Paid days a year ${SafeUI.help(FIELD_HELP.max_paid_days_per_year)}</th>
        ${shareHeads}
        <th><span class="visually-hidden">Remove</span></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${addButton("tiers", "Add tier")}
  </section>`;
}

function pricingEditor() {
  const rows = PRICING_FIELDS.map(
    ({ key, label, hint }) => `<label class="setting">
      <span><b>${label}</b><span class="hint">${hint}</span></span>
      ${withUnit(field(`pricing.${key}`, "percent", label), "%")}
    </label>`,
  ).join("");
  return `<section class="card settings">${rows}</section>${hazeBonusEditor()}`;
}

// Shown only when the tariff offers the add-on; a tariff without haze_bonus does not.
function hazeBonusEditor() {
  if (!state.draft.haze_bonus) return "";
  const rows = HAZE_BONUS_FIELDS.map(([key, label, hint, kind]) => {
    const input = field(`haze_bonus.${key}`, kind, label);
    return `<label class="setting">
      <span><b>${label}</b><span class="hint">${hint}</span></span>
      ${kind === "percent" ? withUnit(input, "%") : input}
    </label>`;
  }).join("");
  return `<section class="card settings">
    <div class="card-head"><h3 class="card-title">Severe haze payout add-on</h3></div>
    ${rows}
    ${labelled("Source", field("haze_bonus.source", "long-text", "Severe haze payout source"))}
  </section>`;
}

function rentSpread() {
  const { classes, trading_days_per_month: days } = state.draft.rent;
  const known = state.centreRents.filter((rent) => !rent.estimated);
  if (!known.length) {
    return `<div class="empty">${icon("building-2")}<h3>No rent data</h3>
      <p>The NEA bid table did not load, so the desk cannot show how centres fall into classes.</p></div>`;
  }
  const levels = classes.map((c) => c.at_least_monthly_sgd);
  if (![days, ...levels].every(Number.isFinite)) {
    return `<p class="chart-note">Fill in every limit to see how the centres spread.</p>`;
  }
  const rows = classes
    .map((rentClass, i) => {
      const upper = levels[i + 1] ?? Infinity;
      const inside = known.filter(
        (rent) => rent.median_bid_sgd >= levels[i] && rent.median_bid_sgd < upper,
      );
      const open = upper === Infinity;
      const range = open ? `${money(levels[i])} and up` : `${money(levels[i])} to ${money(upper)}`;
      const perDay = open
        ? `from ${money(levels[i] / days)}`
        : `${money(levels[i] / days)} to ${money(upper / days)}`;
      return `<tr><td>${esc(rentClass.label)}</td><td class="num">${range}</td>
        <td class="num">${perDay}</td><td class="num">${inside.length}</td></tr>`;
    })
    .join("");
  const missing = state.centreRents.length - known.length;
  return `<div class="card-head"><h3 class="card-title">How centres spread</h3></div>
    <div class="table-wrap"><table class="data">
      <thead><tr><th>Class</th><th class="num">Monthly rent</th><th class="num">Rent per trading day</th><th class="num">Centres</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <p class="fine spread-note">${known.length} centres have a bid on record. ${missing} have none and
      borrow the median of all centres.</p>`;
}

function rentEditor() {
  const rows = state.draft.rent.classes
    .map((rentClass, i) => {
      const base = `rent.classes.${i}`;
      const from =
        i === 0
          ? `<span class="fixed">S$0 (fixed)</span>`
          : withUnit(field(`${base}.at_least_monthly_sgd`, "number", `${rentClass.label} from median monthly bid`), "S$", "before");
      return `<tr>
        <td>${field(`${base}.label`, "text", "Class name")}</td>
        <td>${field(`${base}.key`, "text", "Class key")}</td>
        <td>${from}</td>
        <td class="row-action">${removeButton("rent.classes", i, i > 0, rentClass.label || "this class")}</td>
      </tr>`;
    })
    .join("");
  return `<section class="card">
    <div class="table-wrap"><table class="data edit">
      <thead><tr><th>Name</th><th>Key</th><th>From median monthly bid</th><th><span class="visually-hidden">Remove</span></th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${addButton("rent.classes", "Add class")}
  </section>
  <section class="card settings">
    <label class="setting"><span><b>Trading days a month</b>
      <span class="hint">Turns monthly rent into rent per trading day.</span></span>
      ${field("rent.trading_days_per_month", "number", "Trading days a month")}</label>
    ${labelled("Source", field("rent.source", "long-text", "Rent source"))}
  </section>
  <section class="card" id="rent-spread">${rentSpread()}</section>`;
}

// ---------- Preview ----------

function renderPickers() {
  const { products } = state.draft;
  if (!products.some((product) => product.key === state.product)) state.product = products[0].key;
  $("region").innerHTML = state.regions.map((r) => option(r, titleCase(r), state.region)).join("");
  $("product").innerHTML = products.map((p) => option(p.key, p.label || p.key, state.product)).join("");
}

function renderReadings() {
  $("readings").innerHTML = state.draft.hazards
    .map(
      (hazard) => `<label class="reading">
        <span class="reading-name">${hazardMark(hazard.key)}<span>${esc(hazard.label)}</span>${SafeUI.help(hazard.reading)}</span>
        <input type="number" inputmode="decimal" step="any" min="0" data-reading="${esc(hazard.key)}"
          value="${state.readings[hazard.key] ?? ""}" placeholder="None" aria-label="${esc(hazard.label)}: ${esc(hazard.reading)}">
      </label>`,
    )
    .join("");
}

function onReading(event) {
  const input = event.target;
  const { reading } = input.dataset;
  if (!reading) return;
  const valid = input.validity.valid;
  markInvalid(input, !valid);
  if (input.value === "" || !valid) delete state.readings[reading];
  else state.readings[reading] = Number(input.value);
  schedulePreview();
}

function onPick() {
  state.region = $("region").value;
  state.product = $("product").value;
  schedulePreview();
}

function schedulePreview() {
  clearTimeout(schedulePreview.timer);
  schedulePreview.timer = setTimeout(refreshPreview, PREVIEW_DELAY_MS);
}

async function savedPremiums() {
  const key = `${state.saved.version}|${state.region}|${state.product}`;
  if (state.savedQuote?.key !== key) {
    const tiers = await premiumsOf(state.saved.tariff).catch(() => []);
    state.savedQuote = { key, tiers };
  }
  return state.savedQuote.tiers;
}

async function refreshPreview() {
  if (!state.draft) return;
  const request = (refreshPreview.latest = (refreshPreview.latest ?? 0) + 1);
  if (invalidPaths().length) {
    showPreviewError("The preview waits until every field holds a number.");
    return;
  }
  const hazardKeys = new Set(state.draft.hazards.map((hazard) => hazard.key));
  const readings = Object.fromEntries(
    Object.entries(state.readings).filter(([key]) => hazardKeys.has(key)),
  );
  const body = { tariff: state.draft, region: state.region, product: state.product, readings };
  try {
    const [preview, before] = await Promise.all([
      api("/api/admin/preview", { method: "POST", body }),
      isDirty() ? savedPremiums() : [],
    ]);
    if (request !== refreshPreview.latest) return;
    showPreviewError("");
    renderQuote(preview.quote, before);
    renderAssessment(preview.assessments);
  } catch (error) {
    if (request !== refreshPreview.latest || handleAuthError(error)) return;
    showPreviewError(error.message);
  }
}

function showPreviewError(message) {
  $("preview-error").hidden = !message;
  $("preview-error").innerHTML = message
    ? `${icon("circle-alert")}<span><b>Preview out of date.</b> ${esc(message)}</span>`
    : "";
  $("quote").classList.toggle("stale", Boolean(message));
  $("assessment").classList.toggle("stale", Boolean(message));
  const chip = $("preview-state");
  const [label, tone] = message
    ? ["Out of date", "critical"]
    : isDirty()
      ? ["Unsaved tariff", "accent"]
      : ["Saved tariff", "muted"];
  chip.textContent = label;
  chip.className = `chip ${tone}`;
}

function rung(tier, highest, before) {
  const share = Math.max((tier.weekly_premium_sgd / highest) * 100, 4);
  const old = before.find((candidate) => candidate.tier === tier.tier);
  const moved = old && money(old.weekly_premium_sgd) !== money(tier.weekly_premium_sgd);
  const was = moved ? `<s class="was num">${money(old.weekly_premium_sgd)}</s>` : "";
  return `<li class="rung">
    <span class="rung-name">${esc(tier.label)}</span>
    <span class="rung-bar"><i style="width: ${share}%"></i></span>
    <span class="rung-price">${was}<span class="num">${money(tier.weekly_premium_sgd)}</span><small>/wk</small></span>
    <span class="rung-detail">${money(tier.price_per_day_sgd)} a day. Pays up to ${money(tier.daily_payout_sgd)} a day, ${money(tier.max_payout_per_year_sgd)} a year${tier.cover_multiple != null ? `: ${tier.cover_multiple} times the premium` : ""}${tier.best_value ? ". Best value" : ""}${tier.offered === false ? ". Not offered at this place" : ""}</span>
  </li>`;
}

function renderQuote(quote, before) {
  const highest = Math.max(...quote.tiers.map((tier) => tier.weekly_premium_sgd), 0.01);
  $("quote").innerHTML = `
    <p class="loss-days">An average year here brings <b class="num">${number(quote.expected_loss_days)}</b>
      days of full loss.</p>
    <ol class="ladder">${quote.tiers.map((tier) => rung(tier, highest, before)).join("")}</ol>`;
}

function renderAssessment(assessments) {
  const [day] = assessments;
  if (!day || day.hazards.length === 0) {
    $("assessment").innerHTML = `<p class="fine try-empty">Enter a reading above to see the day's loss and what each tier pays.</p>`;
    return;
  }
  const labelOf = (items, key) => items.find((item) => item.key === key)?.label ?? key;
  const causes = day.hazards
    .map(
      (h) => `<div class="kv"><span class="k">${esc(labelOf(state.draft.hazards, h.hazard))} at
        <span class="num">${number(h.reading)}</span></span><span class="v num">${h.loss_percent}%</span></div>`,
    )
    .join("");
  const payouts = assessments
    .map(
      (a) => `<div class="kv"><span class="k">${esc(labelOf(state.draft.tiers, a.tier))}</span>
        <span class="v num">${money(a.payout_sgd)}</span></div>`,
    )
    .join("");
  $("assessment").innerHTML = `
    <div class="day-loss"><strong class="num">${day.loss_percent}%</strong>
      <span>of a normal day's sales lost</span>${dayChip(day.loss_percent)}</div>
    <div class="breakdown">${causes}</div>
    <h4>Payout for this day</h4>
    <div class="payouts">${payouts}</div>`;
}

// ---------- Theme ----------

function paintThemeToggle() {
  const dark = document.documentElement.dataset.theme === "dark";
  $("theme-toggle").innerHTML = icon(dark ? "sun" : "moon");
  $("theme-toggle").setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("safeday-theme", next);
  } catch {
    // Private windows can refuse storage; the theme still changes for this visit.
  }
  paintThemeToggle();
}

// ---------- Start ----------

function start() {
  $("login-form").addEventListener("submit", signIn);
  $("sign-out").addEventListener("click", signOut);
  $("theme-toggle").addEventListener("click", toggleTheme);
  $("review").addEventListener("click", openReview);
  $("discard").addEventListener("click", discard);
  $("sections").addEventListener("click", onSectionClick);
  $("editor").addEventListener("input", onEdit);
  $("editor").addEventListener("click", onEditorClick);
  $("region").addEventListener("change", onPick);
  $("product").addEventListener("change", onPick);
  $("readings").addEventListener("input", onReading);
  window.addEventListener("beforeunload", (event) => {
    if (isDirty()) event.preventDefault();
  });
  paintThemeToggle();
  begin();
}

start();
