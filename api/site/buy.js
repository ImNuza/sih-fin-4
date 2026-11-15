/* SafeDay guided buy flow (/buy/): a SmartBiz 360-style application with SafeDay as an add-on,
   filled in with the customer by their Income adviser or by an association (sold_by). Income
   sells SmartBiz 360 through intermediaries, so the flow never reads as a direct sale.
   /buy/?via=adviser or ?via=association picks who fills it in.
   Steps: business, cover, details, confirm, pay. Pay is skipped when SafeDay is not added or a
   past decline sends the application to an underwriter. Three business classes, one path each:
   hawker stall, neighbourhood shop, platform worker (the choices come from /api/buy/options).
   The pilot sells only the open_classes; the platform worker card shows as coming next.
   Prices and rent come from the API; nothing is saved until POST /api/buy at the last step.
   Needs site.js (el, api, post, SGD).
   For the demo every field starts filled with made-up details (fillRandom), so the whole flow is
   Next, Next, Next. "New random details" draws a new set; "Clear" empties every field. */
"use strict";

const STEPS = ["business", "cover", "details", "confirm", "pay", "done"];
const buyState = {
  step: "business", centres: [], rent: null, options: null, quotes: {}, tier: null, paymentRef: null,
  demoPhone: null,
};
const STAFF_LABELS = {
  "1-4": "1 to 4", "5-9": "5 to 9", "10-49": "10 to 49", "50-200": "50 to 200", "over-200": "More than 200",
};

const buyForm = () => el("buy");
const field = (name) => buyForm().elements[name];
const chosen = (name) => buyForm().querySelector(`[name="${name}"]:checked`)?.value ?? null;

function centreOf(name) { return buyState.centres.find((c) => c.name === name) || null; }
function businessClass() { return chosen("business_class"); }
function isHawker() { return businessClass() === "hawker"; }
function isPlatformWorker() { return businessClass() === "platform_worker"; }
function addsSafeDay() { return el("add-safeday").checked; }
function soldBy() { return chosen("sold_by"); }
function referred() { return chosen("declined_before") === "yes"; }
function pays() { return addsSafeDay() && !referred(); }
function shownSteps() { return STEPS.filter((s) => s !== "done" && (s !== "pay" || pays())); }
function overSmeStaff() { return !isPlatformWorker() && field("staff_band").value === "over-200"; }

function sectorRegion(postcode) {
  return /^\d{6}$/.test(postcode) ? buyState.options.postal_sector_regions[postcode.slice(0, 2)] ?? null : null;
}
function businessRegion() {
  return isHawker() ? centreOf(field("centre").value)?.region ?? null : sectorRegion(field("postcode").value.trim());
}
function businessProduct() {
  return isPlatformWorker() ? buyState.options.platform_product : field("product").value;
}
function currentRent() { return isHawker() ? buyState.rent?.centres[field("centre").value] || null : null; }
function ssicCode() {
  const choice = field("ssic_choice").value;
  return choice === "other" ? field("ssic_other").value.trim() : choice;
}

// Where the business is priced, as the server charges it: a hawker at its centre's nearest NEA
// stations, a shop at its postcode's area, a platform worker (who moves around) by region.
function businessPlace() {
  if (isHawker()) {
    const centre = field("centre").value;
    return centreOf(centre) ? { centre } : null;
  }
  if (isPlatformWorker()) {
    const region = businessRegion();
    return region ? { region } : null;
  }
  const postcode = field("postcode").value.trim();
  return sectorRegion(postcode) ? { postcode } : null;
}

async function quoteFor(place, product) {
  if (!place || !product) return null;
  const key = `${JSON.stringify(place)}/${product}`;
  buyState.quotes[key] ??= post("/api/quote", { ...place, product }).catch((error) => {
    delete buyState.quotes[key];
    throw error;
  });
  return buyState.quotes[key];
}

function priceBasis() {
  if (isHawker()) return "The price comes from the NEA weather stations nearest your hawker centre.";
  if (isPlatformWorker()) return "The price comes from your region's NEA weather history.";
  return "The price comes from the NEA weather stations nearest your shop's area.";
}

/* ---------- errors ---------- */
/* What to do when a field is empty or wrong, by input name. A custom validity message wins. */
const FIELD_PROBLEMS = {
  sold_by: "Say who is filling in this form with you: your Income adviser or your association.",
  adviser_code: "Enter the Income adviser code: 4 to 12 letters or digits, for example DEMO1234.",
  association: "Enter the name of the association, at least 3 characters.",
  business_class: "Pick the kind of business.",
  applicant_type: "Say whether you apply as an individual or a company.",
  uen: "Enter the UEN as ACRA shows it, for example 53123456A or 201912345K.",
  business_name: "Enter the business name.",
  centre: "Pick your hawker centre.",
  licence_no: "Enter your licence number: 5 to 20 letters, digits, / or -, for example FS12345X.",
  ssic_choice: "Pick your SSIC code, or pick Other and type it.",
  ssic_other: "Enter your 5-digit SSIC code, for example 47219.",
  platform: "Pick your platform.",
  platform_worker_id: "Enter the driver or rider ID from your platform app, 3 to 40 characters.",
  postcode: "Enter the 6-digit postcode, for example 560123.",
  product: "Pick what you sell.",
  staff_band: "Pick how many people work in the business.",
  sales_under_100m: "Say whether annual sales were under S$100 million.",
  term_months: "Pick 12 or 24 months.",
  cover_start: "Pick the day cover starts: today or a later day.",
  name: "Enter your name.",
  phone: "Enter a Singapore mobile number: 8 digits that start with 3, 6, 8 or 9.",
  email: "Enter an email address like name@example.com.",
  password: "Enter a password for your dashboard.",
  declined_before: "Say whether an insurer has declined this business before.",
  declined_details: "Say which insurer declined you and why.",
  accept_declaration: "Tick the declaration to go on.",
  accept_pdpa: "Tick the data protection consent to go on.",
  payment_method: "Pick how you want to pay.",
};
const OFFLINE_PROBLEM = "Could not reach SafeDay. Check your connection and try again.";

function showBuyError(message) {
  el("buy-error").innerHTML = message ? `${SafeUI.icon("circle-alert")}<span></span>` : "";
  if (message) el("buy-error").lastElementChild.textContent = message;
}
function problemText(error) {
  return error instanceof TypeError ? OFFLINE_PROBLEM : error.message;
}

/* The box that shows a field's error: its fieldset for a radio, else its label. */
function errorHolder(input) {
  return input.type === "radio" ? input.closest("fieldset") : input.closest("label");
}
function clearInvalid(input) {
  if (!input.name) return;
  el(`error-${input.name}`)?.remove();
  for (const same of buyForm().querySelectorAll(`[name="${input.name}"]`)) {
    same.removeAttribute("aria-invalid");
    same.removeAttribute("aria-describedby");
  }
}
function markInvalid(input, message) {
  clearInvalid(input);
  const note = document.createElement("span");
  note.className = "field-error";
  note.id = `error-${input.name}`;
  note.innerHTML = SafeUI.icon("circle-alert");
  note.append(message);
  const holder = errorHolder(input);
  if (holder.classList.contains("check")) holder.after(note);
  else holder.append(note);
  input.setAttribute("aria-invalid", "true");
  input.setAttribute("aria-describedby", note.id);
  input.focus();
}
function fieldProblem(input) {
  if (input.validity.customError) return input.validationMessage;
  if (input.validity.rangeUnderflow && input.type === "date") return "Cover cannot start before today. Pick today or a later day.";
  return FIELD_PROBLEMS[input.name] || input.validationMessage;
}

/* ---------- dates ---------- */
const DATE = (date) => date.toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric" });
const localDate = (iso) => new Date(`${iso}T00:00:00`);

function todayIso() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
function addDays(date, days) {
  const later = new Date(date);
  later.setDate(later.getDate() + days);
  return later;
}
/* Same day of the month, months later; the month's last day if it is shorter (as the API does). */
function addMonths(date, months) {
  const later = new Date(date.getFullYear(), date.getMonth() + months, 1);
  const lastDay = new Date(later.getFullYear(), later.getMonth() + 1, 0).getDate();
  later.setDate(Math.min(date.getDate(), lastDay));
  return later;
}
function coverDates() {
  const start = field("cover_start").value;
  if (!start) return null;
  const startDate = localDate(start);
  return {
    start: startDate,
    payoutsFrom: addDays(startDate, buyState.options.waiting_period_days),
    ends: addMonths(startDate, Number(chosen("term_months") || 12)),
  };
}

/* ---------- made-up details for the demo ---------- */
const pick = (list) => list[Math.floor(Math.random() * list.length)];
const digits = (n) => Array.from({ length: n }, () => Math.floor(Math.random() * 10)).join("");
const hex = (bytes) => Array.from(crypto.getRandomValues(new Uint8Array(bytes)), (b) => b.toString(16).padStart(2, "0")).join("").toUpperCase();
const LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ";
const OWNERS = [
  ["Tan Wei Ming", "Ah Ming"], ["Lim Mei Ling", "Mei Ling"], ["Siti Aminah binte Rahman", "Siti"],
  ["Rajesh s/o Kumar", "Raj"], ["Wong Kai Xin", "Kai Xin"], ["Muhammad Faiz bin Ismail", "Faiz"],
  ["Goh Ah Hock", "Ah Hock"], ["Priya d/o Ramasamy", "Priya"], ["Ng Boon Keat", "Boon Keat"],
];
const DISHES = {
  cooked_food: ["Chicken Rice", "Fishball Noodles", "Nasi Lemak", "Prata House", "Wanton Mee", "Char Kway Teow", "Mee Rebus", "Kopi & Teh"],
  fresh_produce: ["Fresh Fish", "Vegetables", "Poultry", "Fruits"],
  flowers: ["Florist", "Flowers & Plants"],
  packaged_food: ["Provision Shop", "Drinks Stall"],
  general_goods: ["Trading", "Sundries"],
};
/* What a shop with each SSIC code most likely sells, and names it might trade under. */
const SHOP_KINDS = {
  "47102": ["packaged_food", ["Minimart", "Provision Shop"]],
  "47211": ["fresh_produce", ["Greengrocer", "Fruit Shop"]],
  "47212": ["fresh_produce", ["Seafood", "Meat Supply"]],
  "47213": ["packaged_food", ["Bakery", "Confectionery"]],
  "47522": ["general_goods", ["Hardware", "Hardware & Tools"]],
  "47610": ["general_goods", ["Bookshop", "Stationery"]],
  "47711": ["general_goods", ["Fashion", "Boutique"]],
  "47723": ["packaged_food", ["Medical Hall"]],
  "47743": ["flowers", ["Florist"]],
  "56111": ["cooked_food", ["Eating House", "Restaurant"]],
  "56112": ["cooked_food", ["Cafe", "Kopitiam"]],
};
/* Postal sectors of busy HDB towns (Toa Payoh, Geylang, Bedok, Tampines, Sengkang, Ang Mo Kio,
   Jurong, Bukit Panjang, Woodlands, Yishun, Punggol). */
const TOWN_SECTORS = ["31", "38", "46", "52", "54", "56", "60", "64", "67", "73", "76", "82"];
const ROLES = ["Owner", "Owner", "Director", "Partner", "Manager"];
const COMPANY_SHARE = { hawker: 0.25, shop: 0.5, platform_worker: 0 };
const ADVISER_SHARE = 0.7;

function setRadio(name, value) {
  const input = buyForm().querySelector(`[name="${name}"][value="${value}"]`);
  if (input) input.checked = true;
}
function businessClassAtRandom() {
  const kind = Math.random() < 0.7 ? "hawker" : "shop";
  return buyState.options.open_classes.includes(kind) ? kind : buyState.options.open_classes[0];
}
function townPostcode() {
  const sectors = TOWN_SECTORS.filter((s) => s in buyState.options.postal_sector_regions);
  return `${pick(sectors)}${digits(4)}`;
}
// UEN formats: 9 digits + letter for a company (year first), 8 digits + letter for a business.
function demoUen() { return `20${pick(["15", "18", "19", "21", "23"])}${digits(5)}${pick(LETTERS)}`; }

function fillHawker(short) {
  const products = [...el("buy-product").options].map((o) => o.value).filter(Boolean);
  // Most stalls at a hawker centre sell cooked food; keep it the usual answer.
  const product = Math.random() < 0.7 && products.includes("cooked_food") ? "cooked_food" : pick(products);
  field("product").value = product;
  field("business_name").value = `${short} ${pick(DISHES[product] || ["Stall"])}`;
  field("staff_band").value = pick(["1-4", "1-4", "1-4", "5-9"]);
}
function fillShop(short) {
  const codes = Object.keys(SHOP_KINDS).filter((c) => [...field("ssic_choice").options].some((o) => o.value === c));
  const code = pick(codes);
  const [product, names] = SHOP_KINDS[code];
  field("ssic_choice").value = code;
  field("product").value = product;
  field("business_name").value = `${short} ${pick(names)}`;
  field("staff_band").value = pick(["1-4", "1-4", "5-9", "10-49"]);
}

/* Who fills in the form: the ?via= link from the landing page, else mostly an adviser. */
function fillChannel() {
  const via = new URLSearchParams(location.search).get("via");
  const sold = via in buyState.options.sold_by ? via : Math.random() < ADVISER_SHARE ? "adviser" : "association";
  setRadio("sold_by", sold);
  field("adviser_code").value = `DEMO${digits(4)}`;
}
/* The association a stall joins through: its centre's own, else the federation (FMAS). */
function fillAssociation() {
  const centre = isHawker() ? field("centre").value : "";
  field("association").value = buyState.options.centre_associations[centre] || buyState.options.associations[0];
}

function fillRandom() {
  const [name, short] = pick(OWNERS);
  fillChannel();
  const kind = businessClassAtRandom();
  setRadio("business_class", kind);
  field("centre").value = pick(buyState.centres).name;
  field("stall_unit").value = `01-${String(Math.floor(Math.random() * 180) + 1).padStart(2, "0")}`;
  field("licence_no").value = `DEMO${digits(5)}${pick(LETTERS)}`;
  field("ssic_other").value = "";
  field("platform").value = pick(buyState.options.platforms.filter((p) => p !== "Other"));
  field("platform_worker_id").value = `DEMO-${pick(["DRV", "RDR"])}-${digits(6)}`;
  field("postcode").value = townPostcode();
  // Fill both business paths, the chosen one last, so switching class still shows made-up details.
  const [other, own] = kind === "shop" ? [fillHawker, fillShop] : [fillShop, fillHawker];
  other(short);
  own(short);
  const company = Math.random() < COMPANY_SHARE[kind];
  setRadio("applicant_type", company ? "company" : "individual");
  field("uen").value = company ? demoUen() : "";
  for (const input of buyForm().querySelectorAll('[name="sales_under_100m"]')) input.checked = false;
  el("add-safeday").checked = true;
  setRadio("term_months", Math.random() < 0.7 ? "12" : "24");
  field("cover_start").value = todayIso();
  field("cover_start").min = todayIso();
  field("name").value = name;
  field("designation").value = kind === "platform_worker" ? pick(["Driver", "Rider"]) : pick(ROLES);
  field("phone").value = buyState.demoPhone || `${pick(["8", "9"])}${digits(3)} ${digits(4)}`;
  const slug = short.toLowerCase().replace(/[^a-z]+/g, "");
  field("email").value = `${slug}.${digits(5)}@example.test`;
  field("password").value = `demo-${digits(6)}`;
  setRadio("declined_before", "no");
  el("declined-box").hidden = true;
  field("declined_details").value = "";
  field("accept_declaration").checked = true;
  field("accept_pdpa").checked = true;
  setRadio("payment_method", "paynow");
  fillAssociation();
  afterRefill();
}

function clearAll() {
  for (const input of buyForm().querySelectorAll("input, select, textarea")) {
    if (input === el("add-safeday")) continue;
    if (input.type === "radio" || input.type === "checkbox") input.checked = false;
    else input.value = "";
  }
  el("declined-box").hidden = true;
  afterRefill();
}

function afterRefill() {
  buyState.tier = null;
  buyState.paymentRef = null;
  showBuyError("");
  for (const input of buyForm().querySelectorAll("[aria-invalid]")) clearInvalid(input);
  showChannelFields();
  showClassFields();
  showWaitingNote();
  renderTiers();
}

/* ---------- step 1: business ---------- */
function showChannelFields() {
  const sold = soldBy();
  el("adviser-field").hidden = sold !== "adviser";
  el("association-field").hidden = sold !== "association";
  el("addon-who").textContent = sold === "association" ? "Your association" : "Your adviser";
}
function channelText() {
  return soldBy() === "association"
    ? `${field("association").value.trim()} (group scheme)`
    : `Income adviser · code ${field("adviser_code").value.trim().toUpperCase()}`;
}
function showClassFields() {
  const kind = businessClass();
  const placed = kind === "shop" || kind === "platform_worker";
  el("hawker-box").hidden = kind !== "hawker";
  el("shop-box").hidden = kind !== "shop";
  el("platform-box").hidden = kind !== "platform_worker";
  el("postcode-field").hidden = !placed;
  el("postcode-label").textContent = kind === "shop" ? "Shop postcode" : "Home postcode";
  el("applicant-box").hidden = kind === "platform_worker";
  el("product-field").hidden = kind === "platform_worker";
  el("staff-box").hidden = kind === "platform_worker";
  el("ssic-other-field").hidden = field("ssic_choice").value !== "other";
  el("sales-box").hidden = field("staff_band").value !== "over-200";
  toggleUen();
  showRentHint();
  checkPostcode();
}
function showRentHint() {
  const hint = el("buy-rent");
  const rent = currentRent();
  hint.hidden = !rent;
  if (rent) hint.innerHTML = `<b>${rent.rent_class_label} centre.</b> ${rentSource(rent, buyState.rent)} About ${SGD(rent.rent_per_day_sgd)} per trading day.`;
}
function toggleUen() {
  const company = !isPlatformWorker() && chosen("applicant_type") === "company";
  el("uen-field").hidden = !company;
  field("uen").required = company;
}
function checkPostcode() {
  const input = field("postcode"), postcode = input.value.trim();
  const region = sectorRegion(postcode);
  const unknown = /^\d{6}$/.test(postcode) && !region;
  input.setCustomValidity(unknown ? `Postal sector ${postcode.slice(0, 2)} is not a Singapore postal sector. Check the postcode.` : "");
  el("postcode-region").textContent = region
    ? `NEA region: ${region}. ${isPlatformWorker() ? "Your price comes from this region's weather history." : "Your price comes from the NEA stations nearest your shop's area."}`
    : "";
}

/* ---------- step 2: cover ---------- */
function showWaitingNote() {
  const dates = coverDates();
  el("waiting-note").textContent = dates
    ? `Payouts can start from ${DATE(dates.payoutsFrom)}, after the ${buyState.options.waiting_period_days}-day waiting period.`
    : "";
}

async function renderTiers() {
  const body = el("addon-body");
  el("addon").classList.toggle("on", addsSafeDay());
  body.hidden = !addsSafeDay();
  if (!addsSafeDay()) return;
  let quote;
  try {
    quote = await quoteFor(businessPlace(), businessProduct());
  } catch (error) {
    el("buy-tiers").innerHTML = "";
    el("what-pays").innerHTML = "";
    el("why-price").innerHTML = "";
    el("tier-note").innerHTML = `<span class="tier-problem">${SafeUI.icon("circle-alert")}<span>Could not load the prices. ${escapeHtml(problemText(error))}</span>
      <button class="btn small" id="tier-retry" type="button">Try again</button></span>`;
    el("tier-retry").addEventListener("click", renderTiers);
    return;
  }
  const rent = currentRent();
  if (!quote) {
    el("buy-tiers").innerHTML = "";
    el("what-pays").innerHTML = "";
    el("why-price").innerHTML = "";
    el("tier-note").textContent = "Tell us where the business is and what it does to see the prices.";
    return;
  }
  buyState.tier ??= rent?.recommended_tier || quote.tiers[0].tier;
  const share = (t) => rent ? `${Math.round((100 * t.daily_payout_sgd) / rent.rent_per_day_sgd)}% of a day's rent` : "";
  el("buy-tiers").innerHTML = quote.tiers.map((t) => `
    <button class="tier-card ${t.tier === rent?.recommended_tier ? "rec" : ""}" type="button" role="radio"
      aria-checked="${t.tier === buyState.tier}" data-tier="${t.tier}">
      <span class="tier-check">${SafeUI.icon("check")}</span>
      <span class="t">${t.label}${t.tier === rent?.recommended_tier ? ' <span class="chip accent">Suggested</span>' : ""}</span>
      <span class="p">${SGD(t.weekly_premium_sgd)}<small>/wk</small></span>
      <span class="d">${SGD(t.daily_payout_sgd)} a bad day · up to ${SGD(t.max_payout_per_year_sgd)} a year</span>
      ${rent ? `<span class="d">${share(t)}</span>` : ""}
    </button>`).join("");
  el("tier-note").textContent = rent
    ? (rent.covers_rent
      ? `Suggested: the smallest tier that pays your whole day's rent (about ${SGD(rent.rent_per_day_sgd)}) on a full bad day.`
      : `No tier pays a whole day's rent here (about ${SGD(rent.rent_per_day_sgd)}). Suggested: the biggest tier.`)
      + ` ${priceBasis()}`
    : priceBasis();
  el("what-pays").innerHTML = whatPays(quote, buyState.tier);
  el("why-price").innerHTML = whyPrice(quote, buyState.tier);
}

const HAZARD_WORDS = { haze: "haze", rain: "heavy rain", heat: "extreme heat", flood: "flash floods", closure: "closure orders" };
const DAYS = (days) => days.toFixed(1);

// The first level that pays, per hazard, from /api/options. Closure orders are left out: they are
// not a climate trigger and are paid only by an insurer's manual run.
const TRIGGER_WORDS = {
  haze: (level) => `24-hour PSI of ${level} or more in your region`,
  rain: (level) => `${level} mm of rain or more in one work hour at your nearest rain gauges (the middle reading)`,
  heat: (level) => `${level} work hours or more at WBGT 32 °C at the nearest station`,
  flood: () => "a PUB flood alert at your place",
};

function whatPays(quote, tierKey) {
  const tier = quote.tiers.find((t) => t.tier === tierKey) || quote.tiers[0];
  const triggers = buyState.options.hazards.filter((h) => TRIGGER_WORDS[h.key])
    .map((h) => TRIGGER_WORDS[h.key](h.first_band));
  const wait = buyState.options.waiting_period_days;
  return `<h3>What it pays, and what it does not</h3>
    <ul>
      <li>${tier.label} pays up to ${SGD(tier.daily_payout_sgd)} for a bad day, and up to ${SGD(tier.max_payout_per_year_sgd)} a year.</li>
      <li>A bad day starts at ${triggers.slice(0, -1).join(", ")} or ${triggers.at(-1)}. Higher readings pay a bigger share of the day.</li>
      <li>No payout for a bad day in the first ${wait} days of cover.</li>
      <li>A move to a higher tier starts a new ${wait}-day wait for the whole cover. A move to a lower tier keeps your start date.</li>
      <li>Cover stops if the weekly premium is not paid. If you buy again later, the new cover waits ${wait} days, and the yearly limit still counts what was paid in the last ${buyState.options.cap_window_days} days.</li>
      <li>Payouts already made are yours to keep.</li>
      <li><b>You can lose sales and receive nothing if the readings stay below these levels.</b></li>
      <li>There is no claim form. Injury, medical costs and damaged goods are not covered by SafeDay.</li>
    </ul>`;
}

// The quote's own build-up, in words: no number here is worked out in the browser.
function whyPrice(quote, tierKey) {
  const tier = quote.tiers.find((t) => t.tier === tierKey) || quote.tiers[0];
  const product = buyState.options.productLabels[quote.product] || quote.product;
  const parts = Object.entries(quote.loss_day_parts).filter(([, days]) => days > 0)
    .map(([hazard, days]) => `${HAZARD_WORDS[hazard] || hazard} ${DAYS(days)}`).join(", ");
  const records = quote.local_risks.length
    ? `NEA's records from the stations nearest ${isHawker() ? "your hawker centre" : "your shop's area"} in the ${quote.region} region`
    : `NEA's records for the ${quote.region} region`;
  const steps = tier.build_up.map((step, at) => `<tr><td>${at ? "+ " : ""}${step.label}</td><td class="num">${SGD(step.amount_sgd)}</td></tr>`).join("");
  return `
    <p>1. In an average year, ${records} show ${DAYS(quote.expected_loss_days)} days of full loss for ${product.toLowerCase()} (${parts}). The count already allows for what you sell: on a full bad day it loses about ${Math.round(quote.product_factor * 100)}% of its normal sales for good.</p>
    <p>2. ${tier.label} pays ${SGD(tier.daily_payout_sgd)} a day, for up to ${SGD(tier.max_payout_per_year_sgd)} a year. In an average year that is ${DAYS(tier.expected_paid_days)} paid days.</p>
    <table class="list why-steps">${steps}
      <tr class="total"><td>Yearly premium</td><td class="num">${SGD(tier.yearly_premium_sgd)}</td></tr>
      <tr><td>Weekly premium</td><td class="num">${SGD(tier.weekly_premium_sgd)}</td></tr></table>
    <p class="fine">No personal data goes into this price: only where the business is, what you sell and the tier you pick. The same inputs give the same price for everyone.</p>`;
}

/* ---------- step 4: confirm ---------- */
function placeRows(row) {
  const region = businessRegion();
  if (isHawker()) {
    const rent = currentRent();
    return [
      row("Hawker centre", `${field("centre").value}${field("stall_unit").value ? ` · #${field("stall_unit").value}` : ""}`),
      row("Licence number", field("licence_no").value.toUpperCase()),
      rent ? row("Rent class", `${rent.rent_class_label} · about ${SGD(rent.rent_per_day_sgd)} a trading day`) : "",
    ];
  }
  if (isPlatformWorker())
    return [
      row("Platform", `${field("platform").value} · ID ${field("platform_worker_id").value}`),
      row("Home postcode", `${field("postcode").value} · ${region} region`),
    ];
  const ssicTitle = buyState.options.ssic_codes.find((s) => s.code === ssicCode())?.title || "";
  return [
    row("Shop postcode", `${field("postcode").value} · ${region} region`),
    row("SSIC code", `${ssicCode()}${ssicTitle ? ` · ${ssicTitle}` : ""}`),
  ];
}

async function renderSummary() {
  const quote = addsSafeDay() ? await quoteFor(businessPlace(), businessProduct()) : null;
  const tier = quote?.tiers.find((t) => t.tier === buyState.tier);
  const productLabel = buyState.options.productLabels[businessProduct()] || "";
  const dates = coverDates();
  const row = (k, v) => `<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`;
  el("summary").innerHTML = [
    row("Filled in with", escapeHtml(channelText())),
    row("Applying as", isPlatformWorker() ? "Individual platform worker"
      : chosen("applicant_type") === "company" ? `Company · UEN ${field("uen").value.toUpperCase()}` : "Individual"),
    row("Business", isPlatformWorker() ? productLabel : `${field("business_name").value} · ${productLabel}`),
    ...placeRows(row),
    isPlatformWorker() ? "" : row("People in the business", STAFF_LABELS[field("staff_band").value]),
    row("SmartBiz 360", "Priced by Income"),
    row("SafeDay", tier ? `${tier.label} · ${SGD(tier.weekly_premium_sgd)} a week · ${SGD(tier.daily_payout_sgd)} a bad day` : "Not added"),
    row("Cover starts", dates ? DATE(dates.start) : "Today"),
    row("Term", `${chosen("term_months")} months`),
    dates ? row("Payouts from", `${DATE(dates.payoutsFrom)} (after the ${buyState.options.waiting_period_days}-day waiting period)`) : "",
    dates ? row("Cover ends", DATE(dates.ends)) : "",
    row("Texts in", SMS_LANGUAGES[chosen("sms_language")] || "English"),
    row("Contact", `${field("name").value}${field("designation").value ? ` (${field("designation").value})` : ""} · ${field("phone").value} · ${field("email").value}`),
  ].join("") + (tier ? `<p class="fine">What you are buying, in the SMS we will send you:</p>
    <div class="cover-sms" id="buy-cover-sms"></div>` : "");
  if (tier) {
    showDue(tier.weekly_premium_sgd);
    coverSms(el("buy-cover-sms"), tier.tier, chosen("sms_language") || "en", tier.weekly_premium_sgd);
  }
}

/* ---------- step 5: pay ---------- */
/** The first week's premium due today. GIRO keeps a made-up DEMO- reference; PayNow takes its
    reference from the simulated payment (startPayNow). */
function showDue(amountSgd) {
  buyState.paymentRef ??= `DEMO-${hex(3)}`;
  buyState.dueSgd = amountSgd;
  el("due-amount").textContent = SGD(amountSgd);
}

/* ---------- navigation ---------- */
function showStep(step, scroll = true) {
  buyState.step = step;
  for (const section of buyForm().querySelectorAll("[data-step]")) section.hidden = section.dataset.step !== step;
  const steps = shownSteps(), at = steps.indexOf(step);
  el("progress-bar").style.width = step === "done" ? "100%" : `${Math.round((100 * at) / steps.length)}%`;
  for (const li of el("stepper").children) {
    const index = steps.indexOf(li.dataset.for);
    li.classList.toggle("skip", index < 0);
    li.classList.toggle("on", li.dataset.for === step);
    if (li.dataset.for === step) li.setAttribute("aria-current", "step");
    else li.removeAttribute("aria-current");
    li.classList.toggle("done", step === "done" || (index >= 0 && index < at));
  }
  el("buy-back").hidden = at <= 0;
  el("buy-actions").hidden = step === "done";
  const last = step === "pay" || (step === "confirm" && !pays());
  el("buy-next").textContent = step === "pay"
    ? `Pay ${el("due-amount").textContent}`
    : last ? "Submit application" : step === "confirm" ? "Continue to payment" : "Next";
  showBuyError("");
  el("buy-next").removeAttribute("aria-busy");
  if (step !== "pay") resetPayNow();
  if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
}

function stepIsValid(step) {
  if (step === "business") checkPostcode();
  const section = buyForm().querySelector(`[data-step="${step}"]`);
  for (const input of section.querySelectorAll("input, select, textarea")) {
    if (input.closest("[hidden]")) continue;
    if (!input.checkValidity()) {
      markInvalid(input, fieldProblem(input));
      return false;
    }
  }
  if (step === "business" && overSmeStaff() && chosen("sales_under_100m") === "no") {
    showBuyError(buyState.options.not_an_sme);
    return false;
  }
  if (step === "cover" && addsSafeDay() && !buyState.tier) {
    showBuyError("Pick a SafeDay tier, or untick SafeDay to apply for SmartBiz 360 alone.");
    return false;
  }
  if (step === "confirm" && referred() && !field("declined_details").value.trim()) {
    markInvalid(field("declined_details"), FIELD_PROBLEMS.declined_details);
    return false;
  }
  return true;
}

function requestBody() {
  const data = Object.fromEntries(new FormData(buyForm()).entries());
  const kind = businessClass(), hawker = kind === "hawker", shop = kind === "shop";
  const platformWorker = kind === "platform_worker";
  const applicantType = platformWorker ? "individual" : data.applicant_type;
  return {
    business_class: kind,
    sold_by: soldBy(),
    adviser_code: soldBy() === "adviser" ? data.adviser_code.trim() : null,
    association: soldBy() === "association" ? data.association.trim() : null,
    name: data.name, email: data.email, password: data.password,
    sms_language: data.sms_language || "en",
    business_name: platformWorker ? null : data.business_name,
    centre: hawker ? data.centre : null,
    stall_unit: hawker ? data.stall_unit || null : null,
    licence_no: hawker ? data.licence_no : null,
    ssic_code: shop ? ssicCode() : null,
    platform: platformWorker ? data.platform : null,
    platform_worker_id: platformWorker ? data.platform_worker_id : null,
    postcode: hawker ? null : data.postcode.trim(),
    product: businessProduct(),
    staff_band: platformWorker ? null : data.staff_band,
    sales_under_100m: overSmeStaff() ? data.sales_under_100m === "yes" : null,
    designation: data.designation || null,
    cover_start: data.cover_start || null,
    term_months: Number(data.term_months),
    applicant_type: applicantType, uen: applicantType === "company" ? data.uen : null,
    phone: data.phone, add_safeday: addsSafeDay(), tier: addsSafeDay() ? buyState.tier : null,
    declined_before: referred(), declined_details: referred() ? data.declined_details : null,
    accept_declaration: Boolean(data.accept_declaration), accept_pdpa: Boolean(data.accept_pdpa),
    marketing_email: Boolean(data.marketing_email), marketing_sms: Boolean(data.marketing_sms),
    payment_method: pays() ? data.payment_method : null,
    payment_ref: pays() ? buyState.paymentRef : null,
    payment_token: pays() && data.payment_method === "paynow" ? paynowState.payment?.token ?? null : null,
  };
}

/* FastAPI sends a list of field errors on a 422; show their messages as one sentence. */
function errorText(detail) {
  if (!Array.isArray(detail)) return detail;
  return detail.map((item) => item.msg.replace(/^Value error, /, "")).join(". ");
}
async function submitApplication(body) {
  const response = await fetch("/api/buy", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(errorText(result.detail)
      || `The application could not be saved (error ${response.status}). Nothing was charged. Try again in a minute.`);
  rememberDemoAccount("sme", body.email, body.password);
  return result;
}

function coverPlace(application, policy) {
  if (policy.centre) return `at ${policy.centre}`;
  return application.business_class === "shop" ? "at your shop" : "in your area";
}

function doneHtml({ application, policy }) {
  if (application.status === "referred")
    return `<span class="done-mark wait">${SafeUI.icon("clock", "i-lg")}</span>
      <h2>Sent to an underwriter</h2>
      <p>Thank you. Because an insurer has declined cover for this business before, an underwriter will review your application first. No cover has started and nothing was charged.</p>
      <p class="fine">Application ${application.id} · we will contact you on ${application.phone}.</p>
      <a class="btn primary" href="/dashboard/">Go to your dashboard</a>`;
  if (!policy)
    return `<span class="done-mark">${SafeUI.icon("check", "i-lg")}</span>
      <h2>Application received</h2>
      <p>Income will send your SmartBiz 360 quote. You did not add SafeDay. You can add it any time from your dashboard.</p>
      <a class="btn primary" href="/dashboard/">Go to your dashboard</a>`;
  const starts = application.cover_start > todayIso() ? `on ${DATE(localDate(application.cover_start))}` : "today";
  return `<span class="done-mark">${SafeUI.icon("check", "i-lg")}</span>
    <h2>Your SafeDay cover starts ${starts}</h2>
    <p>The first ${buyState.options.waiting_period_days} days are a waiting period: SafeDay pays for bad days from ${DATE(localDate(application.waiting_ends))}. Your ${application.term_months}-month cover ends on ${DATE(localDate(application.cover_ends))}.</p>
    <p>SafeDay ${policy.tier_label} pays up to ${SGD(policy.daily_payout_sgd)} on a bad day ${coverPlace(application, policy)}, for ${SGD(policy.weekly_premium_sgd)} a week. There is nothing to claim: we pay when NEA readings cross the trigger levels.</p>
    <div class="done-facts">
      <div class="kv"><span class="k">Payment reference (prototype)</span><span class="v num">${application.payment_ref}</span></div>
      <div class="kv"><span class="k">Paid by</span><span class="v">${application.payment_method === "giro" ? "GIRO, every week" : "PayNow"}</span></div>
    </div>
    <a class="btn primary" href="/dashboard/">Go to your dashboard</a>`;
}

async function onNext(event) {
  event.preventDefault();
  const step = buyState.step;
  if (el("buy-next").hasAttribute("aria-busy") || !stepIsValid(step)) return;
  const steps = shownSteps();
  const last = step === "pay" || (step === "confirm" && !pays());
  if (!last) {
    el("buy-next").setAttribute("aria-busy", "true");
    try {
      const next = steps[steps.indexOf(step) + 1];
      if (next === "confirm" || next === "pay") await renderSummary();
      showStep(next);
    } catch (error) {
      showBuyError(problemText(error));
    } finally {
      el("buy-next").removeAttribute("aria-busy");
    }
    return;
  }
  if (step === "pay" && chosen("payment_method") === "paynow") {
    await startPayNow();
    return;
  }
  await submitBuy();
}

async function submitBuy() {
  el("buy-next").setAttribute("aria-busy", "true");
  try {
    const result = await submitApplication(requestBody());
    el("done").innerHTML = doneHtml(result);
    showStep("done");
  } catch (error) {
    showBuyError(problemText(error));
  } finally {
    el("buy-next").removeAttribute("aria-busy");
  }
}

/* ---------- step 5: pay by PayNow (simulated) ----------
   POST /api/premium-payments starts a payment of the amount due and returns a QR. The QR opens
   a "payment successful" page (/paynow-demo/), and opening it pays. For the demo the payment
   also pays itself after AUTO_PAY_MS, so the flow goes on even when the phone cannot reach this
   server. This page checks every POLL_MS and finishes the purchase once it is paid. No real
   PayNow code is made and no money moves. */
const POLL_MS = 1000;
const AUTO_PAY_MS = 20000;
const paynowState = { payment: null, timer: null, autoPay: null, autoPayAt: 0, finishing: false };

function paynowHtml(p) {
  return `<img class="paynow-qr" src="${p.qr_url}" width="180" height="180"
      alt="QR code that opens the simulated bank screen" />
    <div class="paynow-info">
      <p class="paynow-brand">PayNow · simulated</p>
      <div class="kv"><span class="k">Pay to</span><span class="v">${p.payee}</span></div>
      <div class="kv"><span class="k">Amount</span><span class="v">${SGD(p.amount_sgd)}</span></div>
      <div class="kv"><span class="k">Reference</span><span class="v">${p.reference}</span></div>
      <p class="fine"><b>Scan with your phone's camera app</b> to see the payment go through (a
        banking app will not recognise this demo QR), or
        <a href="${p.bank_path}" target="_blank" rel="noopener">open it here</a>. Demo: the
        payment also goes through by itself after ${AUTO_PAY_MS / 1000} seconds.</p>
      <p class="paynow-status" id="paynow-status" role="status">Waiting for payment…</p>
    </div>`;
}

function stopPolling() {
  clearInterval(paynowState.timer);
  clearTimeout(paynowState.autoPay);
  paynowState.timer = null;
  paynowState.autoPay = null;
}

/** The demo's stand-in for the customer paying in their bank app. */
async function autoPay() {
  const payment = paynowState.payment;
  if (!payment) return;
  // 409 means the phone already paid, or the payment ended; checkPayment reads which.
  await post(`/api/premium-payments/${encodeURIComponent(payment.token)}/pay`, {}).catch(() => {});
  await checkPayment();
}

function secondsToAutoPay() {
  return Math.max(0, Math.ceil((paynowState.autoPayAt - Date.now()) / 1000));
}

/** Leave the PayNow panel: stop checking and cancel a payment that was never made. */
function resetPayNow() {
  stopPolling();
  const pending = paynowState.finishing ? null : paynowState.payment;
  paynowState.payment = null;
  paynowState.finishing = false;
  if (el("paynow-box")) el("paynow-box").hidden = true;
  if (pending) post(`/api/premium-payments/${encodeURIComponent(pending.token)}/cancel`, {}).catch(() => {});
}

async function startPayNow() {
  el("buy-next").setAttribute("aria-busy", "true");
  paynowState.finishing = false;
  try {
    const payment = await post("/api/premium-payments", {
      tier: buyState.tier, amount_sgd: buyState.dueSgd,
    });
    paynowState.payment = payment;
    el("paynow-box").innerHTML = paynowHtml(payment);
    el("paynow-box").hidden = false;
    el("buy-next").textContent = "Waiting for PayNow…";
    paynowState.autoPayAt = Date.now() + AUTO_PAY_MS;
    paynowState.autoPay = setTimeout(autoPay, AUTO_PAY_MS);
    paynowState.timer = setInterval(checkPayment, POLL_MS);
  } catch (error) {
    showBuyError(problemText(error));
    el("buy-next").removeAttribute("aria-busy");
  }
}

async function checkPayment() {
  const payment = paynowState.payment;
  if (!payment) return;
  try {
    const now = await api(`/api/premium-payments/${encodeURIComponent(payment.token)}`);
    if (now.status === "paid") {
      if (paynowState.finishing) return;  // the other check already started the purchase
      paynowState.finishing = true;
      stopPolling();
      el("paynow-status").textContent = `Paid ${SGD(now.amount_sgd)}. Setting up your cover…`;
      await submitBuy();
    } else if (now.status === "pending") {
      el("paynow-status").textContent = `Waiting for payment… paying by itself in ${secondsToAutoPay()} s`;
    } else {
      stopPolling();
      paynowState.payment = null;
      el("paynow-status").textContent = `Payment ${now.status}. Press Pay to get a new QR.`;
      el("buy-next").textContent = `Pay ${el("due-amount").textContent}`;
      el("buy-next").removeAttribute("aria-busy");
    }
  } catch (error) {
    stopPolling();
    showBuyError(problemText(error));
    el("buy-next").removeAttribute("aria-busy");
  }
}

function onBack() {
  const steps = shownSteps();
  showStep(steps[Math.max(0, steps.indexOf(buyState.step) - 1)]);
}

/* Classes the pilot does not sell yet stay on the page, greyed out and marked as coming. */
function closeUnsoldClasses() {
  for (const input of buyForm().querySelectorAll('[name="business_class"]')) {
    const open = buyState.options.open_classes.includes(input.value);
    input.disabled = !open;
    const label = input.closest("label");
    label.querySelector(".kind-soon")?.toggleAttribute("hidden", open);
    label.querySelector(".kind-today")?.toggleAttribute("hidden", !open);
  }
}

function fillChoices(options) {
  const choice = (value, label) => `<option value="${value}">${label}</option>`;
  el("buy-centre").innerHTML = choice("", "Pick your centre…") +
    buyState.centres.map((c) => choice(c.name, `${c.name} (${c.region})`)).join("");
  el("buy-product").innerHTML = choice("", "Pick what you sell…") + options.products
    .filter((p) => p.key !== buyState.options.platform_product).map((p) => choice(p.key, p.label)).join("");
  el("buy-ssic").innerHTML = choice("", "Pick your SSIC code…") +
    buyState.options.ssic_codes.map((s) => choice(s.code, `${s.code} · ${s.title}`)).join("") +
    choice("other", "Other: I will type my code");
  el("buy-platform").innerHTML = choice("", "Pick your platform…") +
    buyState.options.platforms.map((p) => choice(p, p)).join("");
  el("association-list").innerHTML = buyState.options.associations.map((a) => `<option value="${escapeHtml(a)}"></option>`).join("");
  el("buy-staff").innerHTML = choice("", "Pick a number…") +
    buyState.options.staff_bands.map((b) => choice(b, STAFF_LABELS[b] || b)).join("");
}

function onChange(event) {
  clearInvalid(event.target);
  const name = event.target.name;
  if (name === "sold_by") showChannelFields();
  // A new centre suggests its own association, unless someone typed a name not on the list.
  const typed = field("association").value.trim();
  if (["business_class", "centre"].includes(name) && (!typed || buyState.options.associations.includes(typed))) fillAssociation();
  if (["business_class", "applicant_type", "ssic_choice", "staff_band", "centre", "postcode"].includes(name)) showClassFields();
  if (["business_class", "centre", "postcode", "product"].includes(name)) { buyState.tier = null; renderTiers(); }
  if (name === "add_safeday") renderTiers();
  if (name === "cover_start" || name === "term_months") showWaitingNote();
  if (name === "declined_before") {
    el("declined-box").hidden = !referred();
    showStep("confirm", false);
  }
}

function showLoadProblem(error) {
  const notice = document.createElement("div");
  notice.className = "notice critical load-problem";
  notice.innerHTML = `${SafeUI.icon("circle-alert")}<span><b>Could not load the form.</b> <span></span></span>
    <button class="btn small" type="button">Reload</button>`;
  notice.querySelector("span span").textContent = problemText(error);
  notice.querySelector("button").addEventListener("click", () => location.reload());
  buyForm().before(notice);
  buyForm().hidden = true;
}

/* A signed-in insurer is told this flow is for business owners. Signed out: nothing to show. */
async function noteInsurer() {
  const user = await api("/api/auth/me").catch(() => null);
  el("insurer-note").hidden = user?.role !== "insurer";
}

/** "+6592471234" as the form shows it, "9247 1234". */
function localMobile(mobile) {
  if (!mobile) return null;
  const local = mobile.replace(/^\+65/, "");
  return `${local.slice(0, 4)} ${local.slice(4)}`;
}

async function wireBuy() {
  if (!el("buy")) return;
  noteInsurer();
  el("buy-next").setAttribute("aria-busy", "true");
  let loaded;
  try {
    loaded = await Promise.all([
      api("/api/map/static"), api("/api/options"), api("/api/rent").catch(() => null), api("/api/buy/options"),
      api("/api/demo-phone"),
    ]);
  } catch (error) {
    el("buy-next").removeAttribute("aria-busy");
    showLoadProblem(error);
    return;
  }
  el("buy-next").removeAttribute("aria-busy");
  const [map, options, rent, buyOptions, demo] = loaded;
  buyState.demoPhone = localMobile(demo.mobile);
  buyState.centres = [...map.hawker_centres].sort((a, b) => a.name.localeCompare(b.name));
  buyState.rent = rent;
  buyState.options = {
    ...buyOptions, hazards: options.hazards,
    productLabels: Object.fromEntries(options.products.map((p) => [p.key, p.label])),
  };
  fillChoices(options);
  closeUnsoldClasses();

  buyForm().addEventListener("submit", onNext);
  buyForm().addEventListener("change", onChange);
  field("postcode").addEventListener("input", checkPostcode);
  buyForm().addEventListener("input", (event) => clearInvalid(event.target));
  buyForm().querySelectorAll('[name="payment_method"]').forEach((radio) =>
    radio.addEventListener("change", () => { resetPayNow(); showStep("pay", false); }));
  el("buy-back").addEventListener("click", onBack);
  el("buy-tiers").addEventListener("click", (event) => {
    const card = event.target.closest("[data-tier]");
    if (!card) return;
    buyState.tier = card.dataset.tier;
    renderTiers();
  });
  el("refill").addEventListener("click", fillRandom);
  el("clear").addEventListener("click", clearAll);
  fillRandom();
  showStep("business");
}

wireBuy();
