/* SafeDay guided buy flow (/buy/): a SmartBiz 360-style application with SafeDay as an add-on.
   Steps: business, cover, details, confirm, pay. Pay is skipped when SafeDay is not added or a
   past decline sends the application to an underwriter. Prices and rent come from the API;
   nothing is saved until POST /api/buy at the last step. Needs site.js (el, api, post, SGD).
   For the demo every field starts filled with made-up details (fillRandom), so the whole flow is
   Next, Next, Next. "New random details" draws a new set. */
"use strict";

const STEPS = ["business", "cover", "details", "confirm", "pay", "done"];
const buyState = { step: "business", centres: [], rent: null, quotes: {}, tier: null };

const buyForm = () => el("buy");
const field = (name) => buyForm().elements[name];
const chosen = (name) => buyForm().querySelector(`[name="${name}"]:checked`)?.value ?? null;

function centreOf(name) { return buyState.centres.find((c) => c.name === name) || null; }
function rentOf(name) { return buyState.rent?.centres[name] || null; }
function addsSafeDay() { return el("add-safeday").checked; }
function referred() { return chosen("declined_before") === "yes"; }
function pays() { return addsSafeDay() && !referred(); }
function shownSteps() { return STEPS.filter((s) => s !== "done" && (s !== "pay" || pays())); }

async function quoteFor(centreName, product) {
  const centre = centreOf(centreName);
  if (!centre || !product) return null;
  const key = `${centre.region}/${product}`;
  buyState.quotes[key] ??= post("/api/quote", { region: centre.region, product });
  return buyState.quotes[key];
}

/* ---------- made-up details for the demo ---------- */
const pick = (list) => list[Math.floor(Math.random() * list.length)];
const digits = (n) => Array.from({ length: n }, () => Math.floor(Math.random() * 10)).join("");
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
const ROLES = ["Owner", "Owner", "Director", "Partner", "Manager"];

function todayIso() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function setRadio(name, value) {
  const input = buyForm().querySelector(`[name="${name}"][value="${value}"]`);
  if (input) input.checked = true;
}

function fillRandom() {
  const [name, short] = pick(OWNERS);
  const products = [...el("buy-product").options].map((o) => o.value);
  // Most stalls at a hawker centre sell cooked food; keep it the usual answer.
  const product = Math.random() < 0.7 && products.includes("cooked_food") ? "cooked_food" : pick(products);
  const company = Math.random() < 0.4;
  setRadio("applicant_type", company ? "company" : "individual");
  // UEN formats: 9 digits + letter for a company (year first), 8 digits + letter for a business.
  field("uen").value = company ? `20${pick(["15", "18", "19", "21", "23"])}${digits(5)}${pick(LETTERS)}` : "";
  field("business_name").value = `${short} ${pick(DISHES[product] || ["Stall"])}`;
  field("centre").value = pick(buyState.centres).name;
  field("stall_unit").value = `01-${String(Math.floor(Math.random() * 180) + 1).padStart(2, "0")}`;
  field("product").value = product;
  el("add-safeday").checked = true;
  field("cover_start").value = todayIso();
  field("cover_start").min = todayIso();
  field("name").value = name;
  field("designation").value = pick(ROLES);
  field("phone").value = `${pick(["8", "9"])}${digits(3)} ${digits(4)}`;
  const slug = short.toLowerCase().replace(/[^a-z]+/g, "");
  field("email").value = `${slug}.${digits(5)}@example.test`;
  field("password").value = `demo-${digits(6)}`;
  setRadio("declined_before", "no");
  el("declined-box").hidden = true;
  field("declined_details").value = "";
  field("accept_declaration").checked = true;
  field("accept_pdpa").checked = true;
  buyState.tier = null;
  toggleUen();
  showRentHint();
  renderTiers();
}

/* ---------- step 1: business ---------- */
function showRentHint() {
  const hint = el("buy-rent");
  const rent = rentOf(field("centre").value);
  hint.hidden = !rent;
  if (rent) hint.innerHTML = `<b>${rent.rent_class_label} centre.</b> ${rentSource(rent, buyState.rent)} About ${SGD(rent.rent_per_day_sgd)} per trading day.`;
}
function toggleUen() {
  const company = chosen("applicant_type") === "company";
  el("uen-field").hidden = !company;
  field("uen").required = company;
}

/* ---------- step 2: cover ---------- */
async function renderTiers() {
  const body = el("addon-body");
  el("addon").classList.toggle("on", addsSafeDay());
  body.hidden = !addsSafeDay();
  if (!addsSafeDay()) return;
  const quote = await quoteFor(field("centre").value, field("product").value);
  const rent = rentOf(field("centre").value);
  if (!quote) return;
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
async function renderSummary() {
  const centre = field("centre").value, rent = rentOf(centre);
  const quote = addsSafeDay() ? await quoteFor(centre, field("product").value) : null;
  const tier = quote?.tiers.find((t) => t.tier === buyState.tier);
  const productLabel = field("product").selectedOptions[0]?.textContent || "";
  const row = (k, v) => `<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`;
  el("summary").innerHTML = [
    row("Applying as", chosen("applicant_type") === "company" ? `Company · UEN ${field("uen").value.toUpperCase()}` : "Individual"),
    row("Business", `${field("business_name").value} · ${productLabel}`),
    row("Hawker centre", `${centre}${field("stall_unit").value ? ` · #${field("stall_unit").value}` : ""}`),
    rent ? row("Rent class", `${rent.rent_class_label} · about ${SGD(rent.rent_per_day_sgd)} a trading day`) : "",
    row("SmartBiz 360", "Priced by Income"),
    row("SafeDay", tier ? `${tier.label} · ${SGD(tier.weekly_premium_sgd)} a week · ${SGD(tier.daily_payout_sgd)} a bad day` : "Not added"),
    row("Cover starts", field("cover_start").value ? new Date(field("cover_start").value).toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric" }) : "Today"),
    row("Contact", `${field("name").value}${field("designation").value ? ` (${field("designation").value})` : ""} · ${field("phone").value} · ${field("email").value}`),
  ].join("");
  if (tier) el("due-amount").textContent = SGD(tier.weekly_premium_sgd);
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
  const section = buyForm().querySelector(`[data-step="${step}"]`);
  for (const input of section.querySelectorAll("input, select, textarea")) {
    if (input.closest("[hidden]")) continue;
    if (!input.reportValidity()) return false;
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
  return {
    name: data.name, email: data.email, password: data.password,
    business_name: data.business_name, centre: data.centre, product: data.product,
    stall_unit: data.stall_unit || null, designation: data.designation || null,
    cover_start: data.cover_start || null,
    applicant_type: data.applicant_type, uen: data.applicant_type === "company" ? data.uen : null,
    phone: data.phone, add_safeday: addsSafeDay(), tier: addsSafeDay() ? buyState.tier : null,
    declined_before: referred(), declined_details: referred() ? data.declined_details : null,
    accept_declaration: Boolean(data.accept_declaration), accept_pdpa: Boolean(data.accept_pdpa),
    marketing_email: Boolean(data.marketing_email), marketing_sms: Boolean(data.marketing_sms),
    payment_method: pays() ? data.payment_method : null,
  };
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
  const starts = application.cover_start && application.cover_start > todayIso()
    ? `from ${new Date(application.cover_start).toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric" })}`
    : "from today";
  return `<h2>You are covered ${starts}</h2>
    <p>SafeDay ${policy.tier_label} pays up to ${SGD(policy.daily_payout_sgd)} on a bad day at ${policy.centre}, for ${SGD(policy.weekly_premium_sgd)} a week. There is nothing to claim: we pay when NEA readings cross the trigger levels.</p>
    <div class="kv"><span class="k">Payment reference (prototype)</span><span class="v">${application.payment_ref}</span></div>
    <div class="kv"><span class="k">Paid by</span><span class="v">${application.payment_method === "giro" ? "GIRO, every week" : "PayNow"}</span></div>
    <a class="btn primary" href="/dashboard/">Go to your dashboard</a>`;
}

async function onNext(event) {
  event.preventDefault();
  const step = buyState.step;
  if (!stepIsValid(step)) return;
  if (step === "cover") await renderSummary();
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
    const result = await post("/api/buy", requestBody());
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

async function wireBuy() {
  if (!el("buy")) return;
  const [map, options, rent] = await Promise.all([
    api("/api/map/static"), api("/api/options"), api("/api/rent").catch(() => null),
  ]);
  buyState.centres = [...map.hawker_centres].sort((a, b) => a.name.localeCompare(b.name));
  buyState.rent = rent;
  el("buy-centre").innerHTML = '<option value="">Pick your centre…</option>' +
    buyState.centres.map((c) => `<option value="${c.name}">${c.name} (${c.region})</option>`).join("");
  el("buy-product").innerHTML = options.products.map((p) => `<option value="${p.key}">${p.label}</option>`).join("");

  buyForm().addEventListener("submit", onNext);
  el("buy-back").addEventListener("click", onBack);
  buyForm().addEventListener("change", (event) => {
    const name = event.target.name;
    if (name === "applicant_type") toggleUen();
    if (name === "centre") showRentHint();
    if (name === "centre" || name === "product") { buyState.tier = null; renderTiers(); }
    if (name === "add_safeday") renderTiers();
    if (name === "declined_before") {
      el("declined-box").hidden = !referred();
      showStep("confirm", false);
    }
  });
  el("buy-tiers").addEventListener("click", (event) => {
    const card = event.target.closest("[data-tier]");
    if (!card) return;
    buyState.tier = card.dataset.tier;
    renderTiers();
  });
  el("refill").addEventListener("click", fillRandom);
  fillRandom();
  showStep("business");
}

wireBuy();
