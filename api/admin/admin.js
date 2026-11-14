"use strict";

const SECTIONS = [
  {
    key: "hazards",
    label: "Hazards",
    intro:
      "What makes a bad day and how much of a normal day's sales it takes. " +
      "Loss is the weight times the severity of the band the reading reaches.",
  },
  {
    key: "products",
    label: "Products",
    intro:
      "What the business sells. A lost day costs the margin on sales that never come back, " +
      "plus the cost of stock that spoils first: the shorter the shelf life and the slower " +
      "the restock, the more is thrown away.",
  },
  {
    key: "tiers",
    label: "Tiers",
    intro:
      "What each tier pays for a day with no sales, and how many such days it pays a year. " +
      "Each tier pays more than the one before it.",
  },
  {
    key: "pricing",
    label: "Pricing",
    intro: "Loads that turn the expected payout into the premium the customer pays.",
  },
];

const PRICING_FIELDS = [
  {
    key: "uncertainty_load",
    label: "Data uncertainty load",
    hint: "Extra on the expected loss for short records, data gaps and rising extremes.",
  },
  {
    key: "catastrophe_load",
    label: "Catastrophe load",
    hint: "Capital and reinsurance for a year like the 2026 haze.",
  },
  {
    key: "expense_ratio",
    label: "Expenses and commission",
    hint: "Share of the premium for running costs, partner commission and margin.",
  },
  { key: "gst_rate", label: "GST", hint: "Quoted premiums include GST." },
];

const FIELD_LABELS = {
  label: "Name",
  key: "Key",
  reading: "Reading",
  weight: "Weight",
  scaled_by_product: "Depends on the product",
  bands: "Bands",
  sites_used: "Nearest stations read",
  assumed_days_per_year: "Assumed days a year",
  source: "Source",
  shelf_life_days: "Shelf life, days",
  restock_every_days: "Restock every, days",
  demand_sensitivity: "Demand lost on a bad day",
  gross_margin: "Gross margin",
  recovered_share: "Sales recovered later",
  daily_payout_sgd: "Payout for a day with no sales, S$",
  max_paid_days_per_year: "Paid days a year, at most",
};
const PERCENT_FIELDS = new Set([
  "weight",
  "demand_sensitivity",
  "gross_margin",
  "recovered_share",
  ...PRICING_FIELDS.map((f) => f.key),
]);

const PREVIEW_DELAY_MS = 250;
const TOAST_MS = 4000;

const state = {
  auth: sessionStorage.getItem("auth"),
  regions: [],
  hazardsWithHistory: new Set(),
  saved: null,
  draft: null,
  section: "hazards",
  region: null,
  product: null,
  readings: {},
};

const $ = (id) => document.getElementById(id);

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
  const response = await fetch(path, { method, headers, body: body && JSON.stringify(body) });
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

async function signIn(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  state.auth = encodeLogin(form.get("username"), form.get("password"));
  try {
    await openDesk();
    sessionStorage.setItem("auth", state.auth);
  } catch (error) {
    state.auth = null;
    $("login-error").textContent = error.message;
  }
}

function signOut(message = "") {
  if ($("review-dialog").open) $("review-dialog").close();
  sessionStorage.removeItem("auth");
  state.auth = null;
  state.saved = state.draft = null;
  $("desk").hidden = true;
  $("login").hidden = false;
  $("login-error").textContent = message;
}

function handleAuthError(error) {
  if (error.status !== 401) return false;
  signOut("Your session has ended. Sign in again.");
  return true;
}

async function openDesk() {
  const [options, saved] = await Promise.all([api("/api/options"), api("/api/admin/tariff")]);
  state.regions = options.regions;
  state.hazardsWithHistory = new Set(
    options.hazards.filter((hazard) => hazard.has_history).map((hazard) => hazard.key),
  );
  state.region ??= options.regions[0];
  showSaved(saved);
  $("login").hidden = true;
  $("desk").hidden = false;
}

function showSaved(saved) {
  state.saved = saved;
  state.draft = structuredClone(saved.tariff);
  renderNav();
  renderEditor();
  renderPickers();
  renderReadings();
  renderVersion();
  draftChanged();
}

// ---------- Draft editing ----------

function getPath(path) {
  return path.split(".").reduce((node, part) => node?.[part], state.draft);
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
  if (input.value === "") return kind === "optional" ? null : NaN;
  const value = Number(input.value);
  return kind === "percent" ? value / 100 : value;
}

function isDirty() {
  return JSON.stringify(state.draft) !== JSON.stringify(state.saved.tariff);
}

function draftChanged() {
  const dirty = isDirty();
  $("review").disabled = !dirty;
  $("discard").disabled = !dirty;
  schedulePreview();
}

function newItem(path, list) {
  const top = list.at(-1);
  if (path.endsWith(".bands")) return { at_least: top.at_least + 1, severity: top.severity };
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
  };
}

function onEdit(event) {
  const input = event.target.closest("[data-path]");
  if (!input) return;
  const { path } = input.dataset;
  setPath(path, readInput(input));
  const hazard = path.match(/^hazards\.(\d+)\./);
  if (hazard) $(`chart-${hazard[1]}`).innerHTML = bandChart(state.draft.hazards[hazard[1]]);
  if (path.startsWith("products.")) renderPickers();
  draftChanged();
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
  renderNav();
  renderEditor();
  renderPickers();
  draftChanged();
}

// ---------- Review and apply ----------

function percent(share) {
  return `${+(share * 100).toFixed(2)}%`;
}

function shown(field, value) {
  if (value === null || value === undefined) return "empty";
  if (field === "bands") {
    return value
      .map((band) => `from ${number(band.at_least)}: ${percent(band.severity)}`)
      .join(", ");
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
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
  return [
    ...itemChanges("Hazards", before.hazards, after.hazards),
    ...itemChanges("Products", before.products, after.products),
    ...itemChanges("Tiers", before.tiers, after.tiers),
    ...pricing,
  ];
}

function changesTable(changes) {
  const rows = changes
    .map(
      ({ where, before, after }) => `<tr>
        <th scope="row">${esc(where)}</th>
        <td class="before">${esc(before)}</td>
        <td class="after">${esc(after)}</td>
      </tr>`,
    )
    .join("");
  return `<div class="table-wrap"><table class="changes">
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
      return `<tr><th scope="row">${esc(tier.label)}</th>
        <td class="before">${was}</td><td class="after">${money(tier.weekly_premium_sgd)}</td></tr>`;
    })
    .join("");
  return `<table class="changes">
    <thead><tr><th>Tier</th><th>Before</th><th>After</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function showReviewError(message) {
  $("review-error").hidden = !message;
  $("review-error").textContent = message;
  $("apply").disabled = Boolean(message);
}

async function openReview() {
  const changes = tariffChanges(state.saved.tariff, state.draft);
  const plural = changes.length === 1 ? "change" : "changes";
  $("review-summary").textContent =
    `${changes.length} ${plural} to version ${state.saved.version}. Nothing is saved until you apply.`;
  $("review-changes").innerHTML = changesTable(changes);
  const product = state.draft.products.find((item) => item.key === state.product);
  $("impact-title").textContent = `Weekly premium: ${product.label}, ${titleCase(state.region)}`;
  $("review-impact").innerHTML = "";
  showReviewError("");
  $("apply").disabled = true;
  $("review-dialog").showModal();
  try {
    const [before, after] = await Promise.all([
      premiumsOf(state.saved.tariff),
      premiumsOf(state.draft),
    ]);
    $("review-impact").innerHTML = impactTable(before, after);
    $("apply").disabled = false;
  } catch (error) {
    if (handleAuthError(error)) return;
    showReviewError(`Fix this before applying. ${error.message}`);
  }
}

async function apply() {
  $("apply").disabled = true;
  try {
    const body = { based_on_version: state.saved.version, tariff: state.draft };
    const saved = await api("/api/admin/tariff", { method: "PUT", body });
    $("review-dialog").close();
    showSaved(saved);
    toast(`Applied. The tariff is now version ${saved.version}.`);
  } catch (error) {
    if (handleAuthError(error)) return;
    showReviewError(`Not applied. ${error.message}`);
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

function field(path, kind, label) {
  const value = getPath(path);
  const named = `data-path="${path}" data-kind="${kind}" aria-label="${esc(label)}"`;
  if (kind === "bool") return `<input type="checkbox" ${named} ${value ? "checked" : ""}>`;
  if (kind === "text") return `<input ${named} value="${esc(value)}">`;
  if (kind === "long-text") {
    return `<textarea data-path="${path}" data-kind="text" aria-label="${esc(label)}">${esc(value)}</textarea>`;
  }
  const shown = kind === "percent" ? +(value * 100).toFixed(2) : value;
  const limits = kind === "percent" ? 'min="0" max="100"' : 'min="0"';
  const display = Number.isFinite(shown) ? shown : "";
  return `<input type="number" step="any" ${limits} ${named} value="${display}">`;
}

function withUnit(input, unit) {
  return `<span class="with-unit">${input}<span>${unit}</span></span>`;
}

function removeButton(listPath, index, allowed) {
  if (!allowed) return "";
  return `<button type="button" class="remove" data-remove="${listPath}" data-index="${index}">Remove</button>`;
}

function addButton(listPath, label) {
  return `<button type="button" class="add" data-add="${listPath}">${label}</button>`;
}

function option(value, label, selected) {
  const mark = value === selected ? "selected" : "";
  return `<option value="${esc(value)}" ${mark}>${esc(label)}</option>`;
}

function toast(message) {
  const box = $("toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (box.hidden = true), TOAST_MS);
}

// ---------- Layout ----------

function renderVersion() {
  const { version, saved_at, saved_by } = state.saved;
  const when = new Date(saved_at).toLocaleString("en-SG", {
    dateStyle: "medium",
    timeStyle: "short",
  });
  $("version").innerHTML = `Version <b>${version}</b>, saved by ${esc(saved_by)} on ${esc(when)}`;
}

function renderNav() {
  $("sections").innerHTML = SECTIONS.map((section) => {
    const items = state.draft[section.key];
    const count = Array.isArray(items) ? items.length : "";
    const current = section.key === state.section;
    return `<button type="button" data-section="${section.key}" aria-current="${current}">
      ${section.label}<span class="count">${count}</span></button>`;
  }).join("");
}

function renderEditor() {
  const section = SECTIONS.find((item) => item.key === state.section);
  const editors = {
    hazards: hazardsEditor,
    products: productsEditor,
    tiers: tiersEditor,
    pricing: pricingEditor,
  };
  $("editor").innerHTML = `
    <header><h1>${section.label}</h1><p class="hint">${section.intro}</p></header>
    ${editors[section.key]()}`;
}

function onSectionClick(event) {
  const button = event.target.closest("button[data-section]");
  if (!button) return;
  state.section = button.dataset.section;
  renderNav();
  renderEditor();
}

// ---------- Section editors ----------

function hazardsEditor() {
  return state.draft.hazards.map(hazardCard).join("");
}

function hazardCard(hazard, i) {
  const base = `hazards.${i}`;
  const bandRows = hazard.bands
    .map(
      (_, b) => `<tr>
        <td>${field(`${base}.bands.${b}.at_least`, "number", `Band ${b + 1} starts at`)}</td>
        <td>${withUnit(field(`${base}.bands.${b}.severity`, "percent", `Band ${b + 1} severity`), "%")}</td>
        <td>${removeButton(`${base}.bands`, b, hazard.bands.length > 1)}</td>
      </tr>`,
    )
    .join("");
  const daysNote = state.hazardsWithHistory.has(hazard.key)
    ? "Leave empty to price from NEA history."
    : "No NEA history. Set the days to price this hazard.";
  return `<article class="card hazard" style="--mark: var(--${esc(hazard.key)}, var(--closure))">
    <div>
      <div class="hazard-title"><span class="mark"></span><h2>${esc(hazard.label)}</h2></div>
      <p class="hint">${esc(hazard.reading)}</p>
      <div class="hazard-fields">
        <label>Weight: sales lost at full severity
          ${withUnit(field(`${base}.weight`, "percent", "Weight"), "%")}</label>
        <label>Nearest stations read
          ${field(`${base}.sites_used`, "number", "Nearest stations read")}</label>
        <label>Assumed days a year
          ${field(`${base}.assumed_days_per_year`, "optional", "Assumed days a year")}
          <span class="history-note">${daysNote}</span></label>
        <label class="check wide">
          ${field(`${base}.scaled_by_product`, "bool", "Loss depends on the product")}
          Loss depends on the product sold</label>
        <div class="wide table-wrap">
          <table>
            <thead><tr><th>From reading</th><th>Severity</th><th></th></tr></thead>
            <tbody>${bandRows}</tbody>
          </table>
          ${addButton(`${base}.bands`, "Add band")}
        </div>
        <label class="wide">Source ${field(`${base}.source`, "long-text", "Source")}</label>
      </div>
    </div>
    <figure class="chart" id="chart-${i}">${bandChart(hazard)}</figure>
  </article>`;
}

function bandChart(hazard) {
  const { bands, weight } = hazard;
  const complete = [weight, ...bands.flatMap((b) => [b.at_least, b.severity])].every(
    Number.isFinite,
  );
  if (!complete) return "<figcaption>Fill in every band to see the chart.</figcaption>";
  const width = 280,
    height = 150,
    left = 36,
    right = 10,
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
      (
        share,
      ) => `<line class="grid" x1="${left}" x2="${width - right}" y1="${y(share)}" y2="${y(share)}"/>
        <text x="${left - 6}" y="${y(share) + 3}" text-anchor="end">${share * 100}%</text>`,
    )
    .join("");
  const ticks = bands
    .map(
      (b) =>
        `<text x="${x(b.at_least)}" y="${height - 8}" text-anchor="middle">${number(b.at_least)}</text>`,
    )
    .join("");
  const peak = Math.max(...bands.map((b) => weight * b.severity));
  const summary = `${hazard.label}: loss rises in ${bands.length} steps to ${Math.round(peak * 100)}%`;
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(summary)}">
      ${grid}<path class="area" d="${line}V${y(0)}Z"/><path class="line" d="${line}"/>${ticks}
    </svg>
    <figcaption>Share of sales lost by reading, before the product adjustment.</figcaption>`;
}

function productsEditor() {
  const rows = state.draft.products
    .map((product, i) => {
      const base = `products.${i}`;
      return `<tr>
        <td>${field(`${base}.label`, "text", "Product")}</td>
        <td>${field(`${base}.key`, "text", "Key")}</td>
        <td>${field(`${base}.shelf_life_days`, "number", "Shelf life in days")}</td>
        <td>${field(`${base}.restock_every_days`, "number", "Days between restocks")}</td>
        <td>${withUnit(field(`${base}.demand_sensitivity`, "percent", "Demand lost on a bad day"), "%")}</td>
        <td>${withUnit(field(`${base}.gross_margin`, "percent", "Gross margin"), "%")}</td>
        <td>${withUnit(field(`${base}.recovered_share`, "percent", "Sales recovered later"), "%")}</td>
        <td>${removeButton("products", i, state.draft.products.length > 1)}</td>
      </tr>
      <tr class="source-row">
        <td colspan="8">${field(`${base}.source`, "long-text", "Source")}</td>
      </tr>`;
    })
    .join("");
  return `<div class="card table-wrap">
    <table>
      <thead><tr>
        <th>Product</th><th>Key</th><th>Shelf life, days</th><th>Restock every, days</th>
        <th>Demand lost on a bad day</th><th>Gross margin</th><th>Sales recovered later</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${addButton("products", "Add product")}
  </div>`;
}

function tiersEditor() {
  const rows = state.draft.tiers
    .map((tier, i) => {
      const base = `tiers.${i}`;
      return `<tr>
        <td>${field(`${base}.label`, "text", "Tier")}</td>
        <td>${field(`${base}.key`, "text", "Key")}</td>
        <td>${field(`${base}.daily_payout_sgd`, "number", "Payout for a day with no sales, S$")}</td>
        <td>${field(`${base}.max_paid_days_per_year`, "number", "Paid days a year")}</td>
        <td>${removeButton("tiers", i, state.draft.tiers.length > 1)}</td>
      </tr>`;
    })
    .join("");
  return `<div class="card table-wrap">
    <table>
      <thead><tr>
        <th>Tier</th><th>Key</th><th>Payout for a day with no sales, S$</th><th>Paid days a year, at most</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${addButton("tiers", "Add tier")}
  </div>`;
}

function pricingEditor() {
  const rows = PRICING_FIELDS.map(
    ({ key, label, hint }) => `<label>
      <span><b>${label}</b>${hint}</span>
      ${withUnit(field(`pricing.${key}`, "percent", label), "%")}
    </label>`,
  ).join("");
  return `<div class="card pricing-fields">${rows}</div>`;
}

// ---------- Preview ----------

function renderPickers() {
  const { products } = state.draft;
  if (!products.some((product) => product.key === state.product)) state.product = products[0].key;
  $("region").innerHTML = state.regions.map((r) => option(r, titleCase(r), state.region)).join("");
  $("product").innerHTML = products.map((p) => option(p.key, p.label, state.product)).join("");
}

function renderReadings() {
  $("readings").innerHTML = state.draft.hazards
    .map(
      (hazard) => `<label>${esc(hazard.label)}
        <input type="number" step="any" data-reading="${esc(hazard.key)}"
          value="${state.readings[hazard.key] ?? ""}" aria-describedby="reading-${esc(hazard.key)}">
        <span id="reading-${esc(hazard.key)}">${esc(hazard.reading)}</span></label>`,
    )
    .join("");
}

function onReading(event) {
  const { reading } = event.target.dataset;
  if (!reading) return;
  if (event.target.value === "") delete state.readings[reading];
  else state.readings[reading] = Number(event.target.value);
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

async function refreshPreview() {
  const request = (refreshPreview.latest = (refreshPreview.latest ?? 0) + 1);
  const hazardKeys = new Set(state.draft.hazards.map((hazard) => hazard.key));
  const readings = Object.fromEntries(
    Object.entries(state.readings).filter(([key]) => hazardKeys.has(key)),
  );
  const body = { tariff: state.draft, region: state.region, product: state.product, readings };
  try {
    const preview = await api("/api/admin/preview", { method: "POST", body });
    if (request !== refreshPreview.latest) return;
    showPreviewError("");
    renderQuote(preview.quote);
    renderAssessment(preview.assessments);
  } catch (error) {
    if (request !== refreshPreview.latest || handleAuthError(error)) return;
    showPreviewError(error.message);
  }
}

function showPreviewError(message) {
  $("preview-error").hidden = !message;
  $("preview-error").textContent = message;
  $("quote").classList.toggle("stale", Boolean(message));
  $("assessment").classList.toggle("stale", Boolean(message));
}

function renderQuote(quote) {
  const highest = Math.max(...quote.tiers.map((tier) => tier.weekly_premium_sgd), 0.01);
  const rungs = quote.tiers
    .map((tier) => {
      const share = Math.max((tier.weekly_premium_sgd / highest) * 100, 4);
      return `<li class="rung">
        <span class="rung-name">${esc(tier.label)}</span>
        <span class="rung-bar"><i style="width: ${share}%"></i></span>
        <span class="rung-price">${money(tier.weekly_premium_sgd)} a week</span>
        <span class="rung-detail">Pays up to ${money(tier.daily_payout_sgd)} a day,
          ${money(tier.max_payout_per_year_sgd)} a year</span>
      </li>`;
    })
    .join("");
  $("quote").innerHTML = `
    <p class="loss-days">An average year here brings <b>${number(quote.expected_loss_days)}</b>
      days of full loss.</p>
    <ol class="ladder">${rungs}</ol>`;
}

function renderAssessment(assessments) {
  const [day] = assessments;
  if (!day || day.hazards.length === 0) {
    $("assessment").innerHTML = "";
    return;
  }
  const labelOf = (items, key) => items.find((item) => item.key === key)?.label ?? key;
  const causes = day.hazards
    .map(
      (
        h,
      ) => `<li><span>${esc(labelOf(state.draft.hazards, h.hazard))} at ${number(h.reading)}</span>
        <span>${h.loss_percent}%</span></li>`,
    )
    .join("");
  const payouts = assessments
    .map(
      (a) => `<li><span>${esc(labelOf(state.draft.tiers, a.tier))}</span>
        <span>${money(a.payout_sgd)}</span></li>`,
    )
    .join("");
  $("assessment").innerHTML = `
    <div class="day-loss"><strong>${day.loss_percent}%</strong>
      <span>of a normal day's sales lost</span></div>
    <ul class="breakdown">${causes}</ul>
    <h3>Payout for this day</h3>
    <ul class="payouts">${payouts}</ul>`;
}

// ---------- Start ----------

function start() {
  $("login-form").addEventListener("submit", signIn);
  $("sign-out").addEventListener("click", () => {
    if (!isDirty() || confirm("Sign out and lose your unsaved changes?")) signOut();
  });
  $("review").addEventListener("click", openReview);
  $("apply").addEventListener("click", apply);
  $("discard").addEventListener("click", discard);
  $("sections").addEventListener("click", onSectionClick);
  $("editor").addEventListener("input", onEdit);
  $("editor").addEventListener("click", onEditorClick);
  $("region").addEventListener("change", onPick);
  $("product").addEventListener("change", onPick);
  $("readings").addEventListener("input", onReading);
  window.addEventListener("beforeunload", (event) => {
    if (state.draft && isDirty()) event.preventDefault();
  });
  if (state.auth) openDesk().catch(() => signOut("Sign in again."));
  else signOut();
}

start();
