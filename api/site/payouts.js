/* Payout panels on the dashboards: the stallholder's PayNow setup, payouts and texts, and the
   insurer's payout run and payout list. The API decides every amount; this file draws it.
   Uses el, api, post, SGD and formData from site.js. */
"use strict";

const STATUS_TONE = {
  paid: "good", held: "warning", sending: "warning", approved: "warning", assessed: "warning",
  failed: "critical", rejected: "critical", capped: "muted",
};
const LANGUAGES = { en: "English", zh: "中文", ms: "Bahasa Melayu", ta: "தமிழ்" };

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
    <div class="kv"><span class="k">Texts to</span><span class="v">${esc(account.sms_mobile_masked)} · ${LANGUAGES[account.sms_language]}</span></div>
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
    </tr>`).join("")}
  </table>`;
}

function phoneInbox(texts) {
  if (!texts.length) return `<p class="fine">Texts from SafeDay will show here.</p>`;
  return `<div class="sms-inbox">${texts.map((t) => `<div class="sms ${esc(t.kind)}">
    <p>${esc(t.body)}</p><span>${esc(t.to)} · ${String(t.sent_at).slice(0, 16).replace("T", " ")} UTC</span></div>`).join("")}</div>`;
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
    <div class="card"><h2>Texts on your phone</h2>${phoneInbox(texts)}</div>
  </div>
  <div class="card"><h2>Your payouts</h2>${payoutRows(payouts, false)}</div>`;
  if (!account) prefillPaynowMobile(application?.phone);
  wireSmePayouts(slot, hasPolicy);
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
      el("code-note").textContent = `Code sent to ${sent.sent_to}. Demo only, the SMS is simulated: your code is ${sent.demo_code}.`;
      el("code-input").value = sent.demo_code;
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
  const [payouts, options, history] = await Promise.all([
    api("/api/payouts"),
    api("/api/options"),
    api("/api/map/day?date=0000-00-00"),
  ]);
  const latest = history.available.max;
  const paid = payouts.filter((p) => p.status === "paid");
  const hazards = options.hazards.map((h) => `<option value="${h.key}">${esc(h.label)} (${esc(h.reading)})</option>`).join("");
  slot.innerHTML = `<div class="card"><h2>Payouts</h2>
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

function runSummary(run) {
  const parts = Object.entries(run.counts).filter(([, n]) => n).map(([outcome, n]) => `${n} ${outcome.replace("_", " ")}`);
  return `${dayLabel(run.loss_date)} (tariff v${run.tariff_version}): ${parts.join(" · ") || "no policies in force"}`;
}

function wireInsurerPayouts(slot) {
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
