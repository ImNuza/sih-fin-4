/* SafeDay guided buy flow (/buy/): a SmartBiz 360-style application with SafeDay as an add-on.
   Steps: business, cover, details, confirm, pay. Pay is skipped when SafeDay is not added or a
   past decline sends the application to an underwriter. Three business classes, one path each:
   hawker stall, neighbourhood shop, platform worker (the choices come from /api/buy/options).
   Prices and rent come from the API; nothing is saved until POST /api/buy at the last step.
   Needs site.js (el, api, post, SGD).
   For the demo every field starts filled with made-up details (fillRandom), so the whole flow is
   Next, Next, Next. "New random details" draws a new set; "Clear" empties every field. */
"use strict";

const STEPS = ["business", "cover", "details", "confirm", "pay", "done"];
const buyState = {
  step: "business", centres: [], rent: null, options: null, quotes: {}, tier: null, paymentRef: null,
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

async function quoteFor(region, product) {
  if (!region || !product) return null;
  const key = `${region}/${product}`;
  buyState.quotes[key] ??= post("/api/quote", { region, product });
  return buyState.quotes[key];
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

function setRadio(name, value) {
  const input = buyForm().querySelector(`[name="${name}"][value="${value}"]`);
  if (input) input.checked = true;
}
function businessClassAtRandom() {
  const draw = Math.random();
  return draw < 0.6 ? "hawker" : draw < 0.85 ? "shop" : "platform_worker";
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

function fillRandom() {
  const [name, short] = pick(OWNERS);
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
  field("phone").value = `${pick(["8", "9"])}${digits(3)} ${digits(4)}`;
  const slug = short.toLowerCase().replace(/[^a-z]+/g, "");
  field("email").value = `${slug}.${digits(5)}@example.test`;
  field("password").value = `demo-${digits(6)}`;
  setRadio("declined_before", "no");
  el("declined-box").hidden = true;
  field("declined_details").value = "";
  field("accept_declaration").checked = true;
  field("accept_pdpa").checked = true;
  setRadio("payment_method", "paynow");
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
  el("buy-error").textContent = "";
  showClassFields();
  showWaitingNote();
  renderTiers();
}

/* ---------- step 1: business ---------- */
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
  input.setCustomValidity(unknown ? `Postal sector ${postcode.slice(0, 2)} is not a Singapore postal sector. Check the postcode` : "");
  el("postcode-region").textContent = region ? `NEA region: ${region}. Your price comes from this region's weather history.` : "";
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
  const quote = await quoteFor(businessRegion(), businessProduct());
  const rent = currentRent();
  if (!quote) {
    el("buy-tiers").innerHTML = "";
    el("tier-note").textContent = "Tell us where the business is and what it does to see the prices.";
    return;
  }
  buyState.tier ??= rent?.recommended_tier || quote.tiers[0].tier;
  const share = (t) => rent ? `${Math.round((100 * t.daily_payout_sgd) / rent.rent_per_day_sgd)}% of a day's rent` : "";
  el("buy-tiers").innerHTML = quote.tiers.map((t) => `
    <button class="tier-card ${t.tier === rent?.recommended_tier ? "rec" : ""}" type="button" role="radio"
      aria-checked="${t.tier === buyState.tier}" data-tier="${t.tier}">
      <span class="t">${t.label}${t.tier === rent?.recommended_tier ? " · suggested" : ""}</span>
      <span class="p">${SGD(t.weekly_premium_sgd)}<small>/wk</small></span>
      <span class="d">${SGD(t.daily_payout_sgd)} a bad day · up to ${SGD(t.max_payout_per_year_sgd)} a year</span>
      ${rent ? `<span class="d">${share(t)}</span>` : ""}
    </button>`).join("");
  el("tier-note").textContent = rent
    ? (rent.covers_rent
      ? `Suggested: the smallest tier that pays your whole day's rent (about ${SGD(rent.rent_per_day_sgd)}) on a full bad day.`
      : `No tier pays a whole day's rent here (about ${SGD(rent.rent_per_day_sgd)}). Suggested: the biggest tier.`)
      + " The price comes from your region's NEA weather history."
    : "The price comes from your region's NEA weather history.";
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
  const quote = addsSafeDay() ? await quoteFor(businessRegion(), businessProduct()) : null;
  const tier = quote?.tiers.find((t) => t.tier === buyState.tier);
  const productLabel = buyState.options.productLabels[businessProduct()] || "";
  const dates = coverDates();
  const row = (k, v) => `<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`;
  el("summary").innerHTML = [
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
    row("Contact", `${field("name").value}${field("designation").value ? ` (${field("designation").value})` : ""} · ${field("phone").value} · ${field("email").value}`),
  ].join("") + (tier ? `<p class="fine">What you are buying, in the SMS we will send you:</p>
    <div class="cover-sms" id="buy-cover-sms"></div>` : "");
  if (tier) {
    showPaynow(tier.weekly_premium_sgd);
    coverSms(el("buy-cover-sms"), tier.tier);
  }
}

/* ---------- step 5: pay ---------- */
function showPaynow(amountSgd) {
  buyState.paymentRef ??= `DEMO-${hex(3)}`;
  el("due-amount").textContent = SGD(amountSgd);
  const query = new URLSearchParams({ amount_sgd: amountSgd.toFixed(2), reference: buyState.paymentRef });
  el("paynow-qr").src = `/api/paynow/qr?${query}`;
  el("paynow-ref").textContent = `Reference ${buyState.paymentRef} · ${SGD(amountSgd)}`;
  el("paynow-box").hidden = chosen("payment_method") !== "paynow";
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
    li.classList.toggle("done", step === "done" || (index >= 0 && index < at));
  }
  el("buy-back").hidden = at <= 0;
  el("buy-actions").hidden = step === "done";
  const last = step === "pay" || (step === "confirm" && !pays());
  el("buy-next").textContent = step === "pay"
    ? `Pay ${el("due-amount").textContent}`
    : last ? "Submit application" : step === "confirm" ? "Continue to payment" : "Next";
  el("buy-error").textContent = "";
  if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
}

function stepIsValid(step) {
  if (step === "business") checkPostcode();
  const section = buyForm().querySelector(`[data-step="${step}"]`);
  for (const input of section.querySelectorAll("input, select, textarea")) {
    if (input.closest("[hidden]")) continue;
    if (!input.reportValidity()) return false;
  }
  if (step === "business" && overSmeStaff() && chosen("sales_under_100m") === "no") {
    el("buy-error").textContent = buyState.options.not_an_sme;
    return false;
  }
  if (step === "cover" && addsSafeDay() && !buyState.tier) {
    el("buy-error").textContent = "Pick a SafeDay tier";
    return false;
  }
  if (step === "confirm" && referred() && !field("declined_details").value.trim()) {
    field("declined_details").setCustomValidity("Say which insurer declined you and why");
    field("declined_details").reportValidity();
    field("declined_details").setCustomValidity("");
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
    name: data.name, email: data.email, password: data.password,
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
  if (!response.ok) throw new Error(errorText(result.detail) || `/api/buy: HTTP ${response.status}`);
  rememberDemoAccount("sme", body.email, body.password);
  return result;
}

function coverPlace(application, policy) {
  if (policy.centre) return `at ${policy.centre}`;
  return application.business_class === "shop" ? "at your shop" : "in your area";
}

function doneHtml({ application, policy }) {
  if (application.status === "referred")
    return `<h2>Sent to an underwriter</h2>
      <p>Thank you. Because an insurer has declined cover for this business before, an underwriter will review your application first. No cover has started and nothing was charged.</p>
      <p class="fine">Application ${application.id} · we will contact you on ${application.phone}.</p>
      <a class="btn primary" href="/dashboard/">Go to your dashboard</a>`;
  if (!policy)
    return `<h2>Application received</h2>
      <p>Income will send your SmartBiz 360 quote. You did not add SafeDay. You can add it any time from your dashboard.</p>
      <a class="btn primary" href="/dashboard/">Go to your dashboard</a>`;
  const starts = application.cover_start > todayIso() ? `on ${DATE(localDate(application.cover_start))}` : "today";
  return `<h2>Your SafeDay cover starts ${starts}</h2>
    <p>The first ${buyState.options.waiting_period_days} days are a waiting period: SafeDay pays for bad days from ${DATE(localDate(application.waiting_ends))}. Your ${application.term_months}-month cover ends on ${DATE(localDate(application.cover_ends))}.</p>
    <p>SafeDay ${policy.tier_label} pays up to ${SGD(policy.daily_payout_sgd)} on a bad day ${coverPlace(application, policy)}, for ${SGD(policy.weekly_premium_sgd)} a week. There is nothing to claim: we pay when NEA readings cross the trigger levels.</p>
    <div class="kv"><span class="k">Payment reference (prototype)</span><span class="v">${application.payment_ref}</span></div>
    <div class="kv"><span class="k">Paid by</span><span class="v">${application.payment_method === "giro" ? "GIRO, every week" : "PayNow"}</span></div>
    <a class="btn primary" href="/dashboard/">Go to your dashboard</a>`;
}

async function onNext(event) {
  event.preventDefault();
  const step = buyState.step;
  if (!stepIsValid(step)) return;
  const steps = shownSteps();
  const last = step === "pay" || (step === "confirm" && !pays());
  if (!last) {
    const next = steps[steps.indexOf(step) + 1];
    if (next === "confirm" || next === "pay") await renderSummary();
    showStep(next);
    return;
  }
  el("buy-next").disabled = true;
  try {
    const result = await submitApplication(requestBody());
    el("done").innerHTML = doneHtml(result);
    showStep("done");
  } catch (error) {
    el("buy-error").textContent = error.message;
  } finally {
    el("buy-next").disabled = false;
  }
}

function onBack() {
  const steps = shownSteps();
  showStep(steps[Math.max(0, steps.indexOf(buyState.step) - 1)]);
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
  el("buy-staff").innerHTML = choice("", "Pick a number…") +
    buyState.options.staff_bands.map((b) => choice(b, STAFF_LABELS[b] || b)).join("");
}

function onChange(event) {
  const name = event.target.name;
  if (["business_class", "applicant_type", "ssic_choice", "staff_band", "centre", "postcode"].includes(name)) showClassFields();
  if (["business_class", "centre", "postcode", "product"].includes(name)) { buyState.tier = null; renderTiers(); }
  if (name === "add_safeday") renderTiers();
  if (name === "cover_start" || name === "term_months") showWaitingNote();
  if (name === "payment_method") el("paynow-box").hidden = chosen("payment_method") !== "paynow";
  if (name === "declined_before") {
    el("declined-box").hidden = !referred();
    showStep("confirm", false);
  }
}

async function wireBuy() {
  if (!el("buy")) return;
  const [map, options, rent, buyOptions] = await Promise.all([
    api("/api/map/static"), api("/api/options"), api("/api/rent").catch(() => null), api("/api/buy/options"),
  ]);
  buyState.centres = [...map.hawker_centres].sort((a, b) => a.name.localeCompare(b.name));
  buyState.rent = rent;
  buyState.options = {
    ...buyOptions, productLabels: Object.fromEntries(options.products.map((p) => [p.key, p.label])),
  };
  fillChoices(options);

  buyForm().addEventListener("submit", onNext);
  buyForm().addEventListener("change", onChange);
  field("postcode").addEventListener("input", checkPostcode);
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
