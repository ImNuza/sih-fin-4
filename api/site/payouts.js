/* Payout panels on the dashboards: the stallholder's PayNow setup, payouts and texts, and the
   insurer's payout run and payout list. The API decides every amount; this file draws it.
   Uses el, api, post, SGD and formData from site.js. */
"use strict";

const STATUS_TONE = {
  paid: "good", held: "warning", sending: "warning", approved: "warning", assessed: "warning",
  failed: "critical", rejected: "critical", capped: "muted",
};
const LANGUAGES = { en: "English", zh: "中文 (Mandarin)" };
const INBOX_REFRESH_MS = 5000;
const DEMO_READING = { hazard: "rain", reading: 50 };
let inboxTimer = null;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}
function statusPill(status) {
  return `<span class="status-pill ${STATUS_TONE[status] || ""}">${esc(status)}</span>`;
}
function dayLabel(isoDate) {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric" });
}

/* ---------- stallholder ---------- */
function accountForm(account) {
  const options = Object.entries(LANGUAGES)
    .map(([key, label]) => `<option value="${key}" ${account?.sms_language === key ? "selected" : ""}>${label}</option>`)
    .join("");
  return `<form id="paynow-form" class="payout-form">
    <label>PayNow to
      <select name="paynow_proxy_type" id="proxy-type">
        <option value="mobile">Mobile number</option><option value="uen">Business UEN</option>
      </select></label>
    <label>PayNow mobile or UEN <input name="paynow_proxy" required placeholder="+6591234567" autocomplete="tel" /></label>
    <label id="sms-mobile-row" hidden>Mobile for texts <input name="sms_mobile" placeholder="+6591234567" autocomplete="tel" /></label>
    <label>Text me in <select name="sms_language">${options}</select></label>
    <button class="btn small" type="submit">Save</button>
    <p class="fine">Mobile numbers start +65 then 8 or 9. We never ask for your NRIC.</p>
    <p class="error" id="paynow-error"></p>
  </form>`;
}

function accountSummary(account) {
  return `<div class="kv"><span class="k">Pays to</span><span class="v">PayNow ${esc(account.paynow_proxy_masked)}</span></div>
    <div class="kv"><span class="k">PayNow name</span><span class="v">${esc(account.paynow_name)}</span></div>
    <div class="kv"><span class="k">Texts to</span><span class="v">${esc(account.sms_mobile_masked)} · ${LANGUAGES[account.sms_language] || esc(account.sms_language)}</span></div>
    <div class="kv"><span class="k">Mobile</span><span class="v">${account.mobile_verified ? statusPill("paid").replace(">paid<", ">verified<") : statusPill("held").replace(">held<", ">not verified<")}</span></div>
    ${account.mobile_verified ? "" : `<div class="verify-row">
      <button class="btn small" id="send-code" type="button">Text me a code</button>
      <input id="code-input" inputmode="numeric" maxlength="6" placeholder="6-digit code" aria-label="Code" />
      <button class="btn small" id="check-code" type="button">Verify</button></div>
      <p class="fine" id="code-note">Payouts wait until your mobile is verified.</p>`}
    <p class="error" id="verify-error"></p>
    <button class="btn-link" id="change-account" type="button">Change</button>`;
}

function payoutRows(payouts, forInsurer) {
  if (!payouts.length) return `<p class="fine">${forInsurer ? "No payouts yet. Run a day above." : "No payouts yet. When NEA readings cross your trigger, the money comes here without a claim."}</p>`;
  return `<table class="list">
    <tr>${forInsurer ? "<th>Business</th><th>Centre</th>" : ""}<th>Day</th><th>Cause</th><th>Loss</th><th>Paid</th><th>Status</th><th>Ref</th>${forInsurer ? "<th></th>" : ""}</tr>
    ${payouts.map((p) => `<tr>
      ${forInsurer ? `<td>${esc(p.business_name)}</td><td>${esc(p.centre || p.region)}</td>` : ""}
      <td class="num">${dayLabel(p.loss_date)}</td><td>${esc(p.main_hazard)}</td>
      <td class="num">${p.loss_percent.toFixed(0)}%</td>
      <td class="num">${SGD(p.amount_sgd)}${p.amount_sgd < p.assessed_sgd ? ` <small title="Yearly cap">of ${SGD(p.assessed_sgd)}</small>` : ""}</td>
      <td>${statusPill(p.status)}${p.failure_reason ? `<div class="fine">${esc(p.failure_reason)}</div>` : ""}</td>
      <td class="num">${p.reference}</td>
      ${forInsurer ? `<td>${p.status === "failed" ? `<button class="btn small" data-retry="${p.id}" type="button">Retry</button>` : ""}
        ${["assessed", "approved", "held", "failed"].includes(p.status) ? `<button class="btn-link" data-reject="${p.id}" type="button">Reject</button>` : ""}</td>` : ""}
    </tr>${forInsurer ? sentTextRow(p) : ""}`).join("")}
  </table>`;
}

const INSURER_COLUMNS = 9;

function textBubble(t) {
  const when = t.sent_at ? `${String(t.sent_at).slice(0, 16).replace("T", " ")} UTC · ` : "";
  return `<div class="sms ${esc(t.kind)}"><p>${esc(t.body)}</p>
    <span>${esc(t.to)} · ${when}${esc(t.status)}${t.error ? ` · ${esc(t.error)}` : ""}</span></div>`;
}

/** The text the stallholder got for this payout, shown under its row on the insurer desk. */
function sentTextRow(p) {
  const latest = p.texts[p.texts.length - 1];
  if (!latest) return "";
  return `<tr class="text-row"><td colspan="${INSURER_COLUMNS}">
    <span class="fine">SMS to ${esc(p.business_name)}</span>${textBubble(latest)}</td></tr>`;
}

function phoneInbox(texts) {
  if (!texts.length) return `<p class="fine">Texts from SafeDay will show here.</p>`;
  return `<div class="sms-inbox">${texts.map(textBubble).join("")}</div>`;
}

async function renderSmePayouts(slot, hasPolicy) {
  const [account, payouts, texts, application] = await Promise.all([
    api("/api/payout-account").catch(() => null),
    api("/api/payouts"),
    api("/api/sms"),
    api("/api/applications/mine").catch(() => null),
  ]);
  const editing = !account || slot.dataset.editing === "1";
  slot.innerHTML = `<div class="grid">
    <div class="card"><h2>Get paid by PayNow</h2>
      ${editing ? accountForm(account) : accountSummary(account)}
      ${hasPolicy ? "" : `<p class="fine">Pick a cover above too, or there is nothing to pay.</p>`}
    </div>
    <div class="card"><h2>Texts on your phone</h2><div id="sme-inbox">${phoneInbox(texts)}</div></div>
  </div>
  <div class="card"><h2>Your payouts</h2><div id="sme-payout-list">${payoutRows(payouts, false)}</div></div>`;
  if (!account) prefillPaynowMobile(application?.phone);
  wireSmePayouts(slot, hasPolicy);
  keepInboxFresh();
}

/** Redraw the texts and payouts every few seconds, so one the insurer sends shows up live. */
function keepInboxFresh() {
  clearInterval(inboxTimer);
  inboxTimer = setInterval(async () => {
    if (document.hidden || !el("sme-inbox")) return;
    try {
      const [payouts, texts] = await Promise.all([api("/api/payouts"), api("/api/sms")]);
      el("sme-inbox").innerHTML = phoneInbox(texts);
      el("sme-payout-list").innerHTML = payoutRows(payouts, false);
    } catch (error) { el("verify-error").textContent = `Could not refresh your texts: ${error.message}`; }
  }, INBOX_REFRESH_MS);
}

/* For the demo: start the PayNow form with the mobile the owner gave in the buy flow. */
function prefillPaynowMobile(phone) {
  const proxy = el("paynow-form")?.elements.paynow_proxy;
  if (proxy && /^[89]\d{7}$/.test(phone || "")) proxy.value = `+65${phone}`;
}

function wireSmePayouts(slot, hasPolicy) {
  const rerender = () => renderSmePayouts(slot, hasPolicy);
  el("proxy-type")?.addEventListener("change", (event) => {
    el("sms-mobile-row").hidden = event.target.value !== "uen";
  });
  el("paynow-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    if (!data.sms_mobile) delete data.sms_mobile;
    try {
      await api("/api/payout-account", {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
      });
      slot.dataset.editing = "0";
      rerender();
    } catch (error) { el("paynow-error").textContent = error.message; }
  });
  el("change-account")?.addEventListener("click", () => { slot.dataset.editing = "1"; rerender(); });
  el("send-code")?.addEventListener("click", async () => {
    try {
      const sent = await post("/api/payout-account/verify/start", {});
      el("code-note").textContent = sent.texts_are_real
        ? `Code sent to ${sent.sent_to}. Check your phone.`
        : `Code sent to ${sent.sent_to}. Demo only, the SMS is simulated: your code is ${sent.demo_code}.`;
      if (sent.demo_code) el("code-input").value = sent.demo_code;
    } catch (error) { el("verify-error").textContent = error.message; }
  });
  el("check-code")?.addEventListener("click", async () => {
    try {
      await post("/api/payout-account/verify", { code: el("code-input").value.trim() });
      rerender();
    } catch (error) { el("verify-error").textContent = error.message; }
  });
}

/* ---------- insurer ---------- */
async function renderInsurerPayouts(slot) {
  const [payouts, options, history, holders] = await Promise.all([
    api("/api/payouts"),
    api("/api/options"),
    api("/api/map/day?date=0000-00-00"),
    api("/api/insurer/policyholders"),
  ]);
  const latest = history.available.max;
  const paid = payouts.filter((p) => p.status === "paid");
  const hazards = options.hazards.map((h) => `<option value="${h.key}">${esc(h.label)} (${esc(h.reading)})</option>`).join("");
  slot.innerHTML = `${demoPayoutCard(holders, options.hazards)}<div class="card"><h2>Payouts</h2>
    <form id="run-form" class="payout-form">
      <label>Day <input type="date" name="loss_date" value="${latest}" required /></label>
      <label>Readings
        <select name="source" id="run-source">
          <option value="nea_history">NEA history for that day</option>
          <option value="manual">Enter a reading (PUB flood, closure order…)</option>
        </select></label>
      <label class="manual" hidden>Hazard <select name="hazard">${hazards}</select></label>
      <label class="manual" hidden>Reading <input name="reading" type="number" step="any" value="1" /></label>
      <button class="btn small" type="submit">Run payouts</button>
      <p class="fine">Assesses every policy for that Singapore day and pays what the tariff gives, by PayNow, with an SMS. History runs to ${dayLabel(latest)}. A day already run is never paid twice.</p>
      <p class="fine" id="run-result"></p><p class="error" id="run-error"></p>
    </form>
    <p class="fine">${paid.length} paid · ${SGD(paid.reduce((sum, p) => sum + p.amount_sgd, 0))} sent in total</p>
    ${payoutRows(payouts, true)}
  </div>`;
  wireInsurerPayouts(slot);
}

function holderOption(h) {
  const phone = !h.texts_to ? "no mobile yet" : `${h.texts_to}${h.mobile_verified ? "" : ", not verified"}`;
  return `<option value="${h.user_id}">${esc(h.business_name)} · ${esc(h.centre)} · ${esc(h.tier_label)} (${phone})</option>`;
}

function demoPayoutCard(holders, hazards) {
  const customers = holders.policyholders;
  const hazardOptions = hazards.map((h) => `<option value="${h.key}" ${h.key === DEMO_READING.hazard ? "selected" : ""}>${esc(h.label)} (${esc(h.reading)})</option>`).join("");
  const how = holders.texts_are_real
    ? "The SMS goes to the customer's real phone through Twilio."
    : "Texts are simulated: set the Twilio keys to reach real phones. The customer still sees the text on their dashboard.";
  return `<div class="card"><h2>Demo: pay a customer now</h2>
    ${customers.length ? `<form id="demo-form" class="payout-form">
      <label>Customer <select name="user_id">${customers.map(holderOption).join("")}</select></label>
      <label>Hazard <select name="hazard">${hazardOptions}</select></label>
      <label>Reading <input name="reading" type="number" step="any" value="${DEMO_READING.reading}" required /></label>
      <button class="btn small" type="submit">Send payout and SMS</button>
      <p class="fine">Pays today, skipping the 30-day waiting period, by PayNow, and texts the customer. ${how} A payout only goes once the customer's mobile is verified.</p>
      <p class="fine" id="demo-result"></p><p class="error" id="demo-error"></p>
    </form>` : `<p class="fine">No customer has cover yet.</p>`}
  </div>`;
}

function demoSummary(sent) {
  const p = sent.payout;
  const text = p.texts[p.texts.length - 1];
  const sms = !text ? "no SMS" : text.status === "failed" ? `SMS failed: ${text.error}` : `SMS ${text.status} to ${text.to}`;
  return `${p.reference} · ${p.business_name} · ${SGD(p.amount_sgd)} ${sent.outcome} · ${sms}`;
}

function runSummary(run) {
  const parts = Object.entries(run.counts).filter(([, n]) => n).map(([outcome, n]) => `${n} ${outcome.replace("_", " ")}`);
  return `${dayLabel(run.loss_date)} (tariff v${run.tariff_version}): ${parts.join(" · ") || "no policies in force"}`;
}

function wireInsurerPayouts(slot) {
  el("demo-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {
      const sent = await post("/api/insurer/demo-payouts", {
        user_id: Number(data.user_id), readings: { [data.hazard]: Number(data.reading) },
      });
      await renderInsurerPayouts(slot);
      el("demo-result").textContent = demoSummary(sent);
    } catch (error) {
      el("demo-error").textContent = error.message;
      button.disabled = false;
    }
  });
  el("run-source").addEventListener("change", (event) => {
    slot.querySelectorAll(".manual").forEach((label) => { label.hidden = event.target.value !== "manual"; });
  });
  el("run-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    const body = { loss_date: data.loss_date, source: data.source };
    if (data.source === "manual") body.readings = { [data.hazard]: Number(data.reading) };
    try {
      const run = await post("/api/insurer/payout-runs", body);
      await renderInsurerPayouts(slot);
      el("run-result").textContent = runSummary(run);
    } catch (error) { el("run-error").textContent = error.message; }
  });
  slot.querySelectorAll("[data-retry]").forEach((button) => button.addEventListener("click", async () => {
    try {
      await post(`/api/insurer/payouts/${button.dataset.retry}/retry`, {});
      renderInsurerPayouts(slot);
    } catch (error) { el("run-error").textContent = error.message; }
  }));
  slot.querySelectorAll("[data-reject]").forEach((button) => button.addEventListener("click", async () => {
    const reason = prompt("Why is this payout rejected? The reason is kept with the payout.");
    if (!reason) return;
    try {
      await post(`/api/insurer/payouts/${button.dataset.reject}/reject`, { reason });
      renderInsurerPayouts(slot);
    } catch (error) { el("run-error").textContent = error.message; }
  }));
}
