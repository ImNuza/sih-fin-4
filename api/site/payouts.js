/* Payout panels on the dashboards: the stallholder's PayNow setup, payouts and texts, and the
   insurer's payout run and payout list. The API decides every amount; this file draws it.
   Uses el, api, post, SGD, formData, escapeHtml, kv, pill, notice and sortHeader from site.js. */
"use strict";

const STATUS_TONE = {
  paid: "good", held: "warning", sending: "warning", approved: "warning", assessed: "warning",
  failed: "critical", rejected: "critical", capped: "muted",
};
const LANGUAGES = { en: "English", zh: "中文", ms: "Bahasa Melayu", ta: "தமிழ்" };
const REJECTABLE = ["assessed", "approved", "held", "failed"];

function statusPill(status) {
  return `<span class="status-pill ${STATUS_TONE[status] || ""}">${escapeHtml(status)}</span>`;
}
function dayLabel(isoDate) {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric" });
}
function paidCell(p) {
  const capped = p.amount_sgd < p.assessed_sgd ? ` <span class="fine" data-tip="Cut to what is left of the yearly cap" aria-label="Cut to what is left of the yearly cap">of ${SGD(p.assessed_sgd)}</span>` : "";
  return `${SGD(p.amount_sgd)}${capped}`;
}

/* ---------- stallholder ---------- */
function accountForm(account) {
  const options = Object.entries(LANGUAGES)
    .map(([key, label]) => `<option value="${key}" ${account?.sms_language === key ? "selected" : ""}>${label}</option>`)
    .join("");
  return `<form id="paynow-form" class="payout-form" novalidate>
    <label>PayNow to
      <select name="paynow_proxy_type" id="proxy-type">
        <option value="mobile">Mobile number</option><option value="uen">Business UEN</option>
      </select></label>
    <label>PayNow mobile or UEN <input name="paynow_proxy" required placeholder="+6591234567" autocomplete="tel" /></label>
    <label id="sms-mobile-row" hidden>Mobile for texts <input name="sms_mobile" placeholder="+6591234567" autocomplete="tel" /></label>
    <label>Text me in <select name="sms_language">${options}</select></label>
    <p class="fine">Mobile numbers start +65 then 8 or 9. We never ask for your NRIC.</p>
    <p class="error" id="paynow-error" role="alert"></p>
    <button class="btn" type="submit">Save PayNow details</button>
  </form>`;
}

function accountSummary(account) {
  const verified = account.mobile_verified ? pill("good", "Verified") : pill("warning", "Not verified");
  return `${kv("Pays to", `PayNow ${escapeHtml(account.paynow_proxy_masked)}`)}
    ${kv("PayNow name", escapeHtml(account.paynow_name))}
    ${kv("Texts to", `${escapeHtml(account.sms_mobile_masked)} · ${LANGUAGES[account.sms_language]}`)}
    ${kv("Mobile", verified)}
    ${account.mobile_verified ? "" : `<div class="verify-row">
      <button class="btn small" id="send-code" type="button">Text me a code</button>
      <input id="code-input" inputmode="numeric" maxlength="6" placeholder="6-digit code" aria-label="Code" autocomplete="one-time-code" />
      <button class="btn small" id="check-code" type="button">Verify</button></div>
      <p class="fine" id="code-note">Payouts wait until your mobile is verified.</p>`}
    <p class="error" id="verify-error" role="alert"></p>
    <button class="btn small quiet" id="change-account" type="button">Change</button>`;
}

function smePayoutList(payouts) {
  if (!payouts.length) return `<div class="card flush"><div class="empty">${SafeUI.icon("banknote")}
    <h3>No payouts yet</h3><p>When NEA readings cross your trigger, the money comes here without a claim.</p></div></div>`;
  return `<ul class="payout-list card flush">${payouts.map((p) => `<li>
    <div><b>${dayLabel(p.loss_date)}</b><span class="fine">${escapeHtml(p.main_hazard)} · ${p.loss_percent.toFixed(0)}% ${dayChip(p.loss_percent)}</span>
      ${p.failure_reason ? `<span class="fine">${escapeHtml(p.failure_reason)}</span>` : ""}</div>
    <div class="payout-amount"><span class="num">${paidCell(p)}</span>${statusPill(p.status)}<span class="fine num">${escapeHtml(p.reference)}</span></div>
  </li>`).join("")}</ul>`;
}

function phoneInbox(texts) {
  if (!texts.length) return `<p class="fine">Texts from SafeDay will show here.</p>`;
  return `<div class="sms-inbox">${texts.map((t) => `<div class="sms ${escapeHtml(t.kind)}">
    <p>${escapeHtml(t.body)}</p><span>${escapeHtml(t.to)} · ${String(t.sent_at).slice(0, 16).replace("T", " ")} UTC</span></div>`).join("")}</div>`;
}

async function renderSmePayouts(slot, hasPolicy) {
  const [account, payouts, texts, application] = await Promise.all([
    api("/api/payout-account").catch(() => null),
    api("/api/payouts"),
    api("/api/sms"),
    api("/api/applications/mine").catch(() => null),
  ]);
  const editing = !account || slot.dataset.editing === "1";
  slot.innerHTML = `<div class="section-head"><div><h2>Payouts</h2>
      <p class="page-sub">When NEA readings cross your trigger, SafeDay pays by PayNow and sends you a text. There is no claim to make.</p></div></div>
    <div class="sme-grid">
      <div class="card"><h2>Get paid by PayNow</h2>
        ${editing ? accountForm(account) : accountSummary(account)}
        ${hasPolicy ? "" : notice("", "info", "Pick a cover above too, or there is nothing to pay.")}
      </div>
      <div class="card"><h2>Texts on your phone</h2>${phoneInbox(texts)}</div>
    </div>
    <h3 class="subhead">Your payouts</h3>
    ${smePayoutList(payouts)}`;
  if (!account) prefillPaynowMobile(application?.phone);
  wireSmePayouts(slot, hasPolicy);
}

/* For the demo: start the PayNow form with the mobile the owner gave in the buy flow. */
function prefillPaynowMobile(phone) {
  const proxy = el("paynow-form")?.elements.paynow_proxy;
  if (proxy && /^[89]\d{7}$/.test(phone || "")) proxy.value = `+65${phone}`;
}

/* Run an action from a button: busy while it runs, its error shown in errorId. */
async function busy(button, errorId, action) {
  button?.setAttribute("aria-busy", "true");
  el(errorId).textContent = "";
  try {
    await action();
  } catch (error) {
    el(errorId).textContent = error.message;
  } finally {
    button?.removeAttribute("aria-busy");
  }
}

function wireSmePayouts(slot, hasPolicy) {
  const rerender = () => renderSmePayouts(slot, hasPolicy);
  el("proxy-type")?.addEventListener("change", (event) => {
    el("sms-mobile-row").hidden = event.target.value !== "uen";
  });
  el("paynow-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(event.target);
    if (!data.sms_mobile) delete data.sms_mobile;
    busy(event.submitter, "paynow-error", async () => {
      await api("/api/payout-account", {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
      });
      slot.dataset.editing = "0";
      await rerender();
    });
  });
  el("change-account")?.addEventListener("click", () => { slot.dataset.editing = "1"; rerender(); });
  el("send-code")?.addEventListener("click", (event) => busy(event.currentTarget, "verify-error", async () => {
    const sent = await post("/api/payout-account/verify/start", {});
    el("code-note").textContent = `Code sent to ${sent.sent_to}. Demo only, the SMS is simulated: your code is ${sent.demo_code}.`;
    el("code-input").value = sent.demo_code;
  }));
  el("check-code")?.addEventListener("click", (event) => busy(event.currentTarget, "verify-error", async () => {
    await post("/api/payout-account/verify", { code: el("code-input").value.trim() });
    await rerender();
  }));
}

/* ---------- insurer ---------- */
function insurerPayoutTable(payouts, hazardLabels) {
  if (!payouts.length) return `<div class="card flush"><div class="empty">${SafeUI.icon("banknote")}
    <h3>No payouts yet</h3><p>Run a day above. Every policy past its waiting period is assessed against that day's NEA readings.</p></div></div>`;
  return `<div class="table-wrap payouts-wrap"><table class="data" id="payouts-table">
    <thead><tr>
      ${sortHeader("Business")}${sortHeader("Centre or region")}${sortHeader("Day", { num: true })}${sortHeader("Cause")}
      ${sortHeader("Loss", { num: true, help: "The day's loss score. The payout is this share of the tier's payout per full bad day." })}
      ${sortHeader("Paid", { num: true })}${sortHeader("Status")}<th>Ref</th><th><span class="visually-hidden">Actions</span></th>
    </tr></thead>
    <tbody>${payouts.map((p) => `<tr>
      <td>${escapeHtml(p.business_name)}</td><td>${escapeHtml(p.centre || titleCase(p.region))}</td>
      <td class="num" data-value="${p.loss_date}">${dayLabel(p.loss_date)}</td>
      <td>${escapeHtml(hazardLabels[p.main_hazard] || p.main_hazard)}</td>
      <td class="num" data-value="${p.loss_percent}">${p.loss_percent.toFixed(0)}% ${dayChip(p.loss_percent)}</td>
      <td class="num" data-value="${p.amount_sgd}">${paidCell(p)}</td>
      <td data-value="${escapeHtml(p.status)}">${statusPill(p.status)}${p.failure_reason ? `<div class="fine">${escapeHtml(p.failure_reason)}</div>` : ""}</td>
      <td class="num ref">${escapeHtml(p.reference)}</td>
      <td class="actions">${p.status === "failed" ? `<button class="btn small" data-retry="${p.id}" type="button">Retry</button>` : ""}
        ${REJECTABLE.includes(p.status) ? `<button class="btn small ghost" data-reject="${p.id}" data-business="${escapeHtml(p.business_name)}" type="button">Reject</button>` : ""}</td>
    </tr>`).join("")}</tbody>
  </table></div>`;
}

async function renderInsurerPayouts(slot) {
  const [payouts, options, history] = await Promise.all([
    api("/api/payouts"),
    api("/api/options"),
    api("/api/map/day?date=0000-00-00"),
  ]);
  const latest = history.available.max;
  const paid = payouts.filter((p) => p.status === "paid");
  const hazardLabels = Object.fromEntries(options.hazards.map((h) => [h.key, h.label]));
  const hazards = options.hazards.map((h) => `<option value="${h.key}">${escapeHtml(h.label)} (${escapeHtml(h.reading)})</option>`).join("");
  slot.innerHTML = `<div class="section-head"><div><h2>Payouts</h2>
      <p class="page-sub">Assesses every policy for that Singapore day and pays what the tariff gives, by PayNow, with an SMS. A day already run is never paid twice.</p></div>
      <p class="fine"><span class="num">${paid.length.toLocaleString("en-SG")}</span> paid · <span class="num">${SGD(paid.reduce((sum, p) => sum + p.amount_sgd, 0))}</span> sent in total</p></div>
    <form id="run-form" class="card run-form">
      <label>Day <input type="date" name="loss_date" value="${latest}" required /></label>
      <label>Readings
        <select name="source" id="run-source">
          <option value="nea_history">NEA history for that day</option>
          <option value="manual">Enter a reading (PUB flood, closure order…)</option>
        </select></label>
      <label class="manual" hidden>Hazard <select name="hazard">${hazards}</select></label>
      <label class="manual" hidden>Reading <input name="reading" type="number" step="any" value="1" /></label>
      <button class="btn primary" type="submit">Run payouts</button>
      <p class="fine run-note">History runs to ${dayLabel(latest)}.</p>
      <p class="run-result" id="run-result" aria-live="polite"></p><p class="error" id="run-error" role="alert"></p>
    </form>
    ${insurerPayoutTable(payouts, hazardLabels)}`;
  if (el("payouts-table")) SafeUI.sortable(el("payouts-table"));
  wireInsurerPayouts(slot);
}

function runSummary(run) {
  const parts = Object.entries(run.counts).filter(([, n]) => n).map(([outcome, n]) => `${n} ${outcome.replaceAll("_", " ")}`);
  return `${dayLabel(run.loss_date)} (tariff v${run.tariff_version}): ${parts.join(" · ") || "no policies in force"}`;
}

/* Rejecting keeps the payout with its reason, so the reason is asked for in the drawer first. */
function askRejectReason(slot, button) {
  const dialog = SafeUI.openDrawer({
    title: "Reject this payout",
    subtitle: escapeHtml(button.dataset.business),
    body: `<form id="reject-form">
      <label>Why is this payout rejected?
        <textarea name="reason" minlength="2" maxlength="300" required rows="4"></textarea>
        <span class="hint">The reason is kept with the payout. Nothing is paid.</span></label>
      <p class="error" id="reject-error" role="alert"></p>
      <div class="row-actions"><button class="btn danger" type="submit">Reject payout</button>
        <button class="btn ghost" type="button" data-close-form>Keep it</button></div>
    </form>`,
  });
  const form = dialog.querySelector("#reject-form");
  form.elements.reason.focus();
  form.querySelector("[data-close-form]").addEventListener("click", () => dialog.close());
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const reason = form.elements.reason.value.trim();
    if (reason.length < 2) {
      el("reject-error").textContent = "Write the reason in a few words.";
      form.elements.reason.setAttribute("aria-invalid", "true");
      return;
    }
    busy(event.submitter, "reject-error", async () => {
      await post(`/api/insurer/payouts/${button.dataset.reject}/reject`, { reason });
      dialog.close();
      await renderInsurerPayouts(slot);
    });
  });
}

function wireInsurerPayouts(slot) {
  el("run-source").addEventListener("change", (event) => {
    slot.querySelectorAll(".manual").forEach((label) => { label.hidden = event.target.value !== "manual"; });
  });
  el("run-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(event.target);
    const body = { loss_date: data.loss_date, source: data.source };
    if (data.source === "manual") body.readings = { [data.hazard]: Number(data.reading) };
    busy(event.submitter, "run-error", async () => {
      const run = await post("/api/insurer/payout-runs", body);
      await renderInsurerPayouts(slot);
      el("run-result").innerHTML = notice("", "check", escapeHtml(runSummary(run)));
    });
  });
  slot.querySelectorAll("[data-retry]").forEach((button) => button.addEventListener("click", () =>
    busy(button, "run-error", async () => {
      await post(`/api/insurer/payouts/${button.dataset.retry}/retry`, {});
      await renderInsurerPayouts(slot);
    })));
  slot.querySelectorAll("[data-reject]").forEach((button) =>
    button.addEventListener("click", () => askRejectReason(slot, button)));
}
