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
const INBOX_REFRESH_MS = 5000;
const DEMO_READING = { hazard: "rain", reading: 50 };
const TEXT_STATUS = {
  queued: "waiting for the sending phone", sent: "sent by the phone", delivered: "delivered",
  failed: "failed", unknown: "the phone did not report back",
};
// After a demo payout, look again at its SMS this many ms apart until the phone reports.
const DEMO_TEXT_CHECKS_MS = [2000, 3000, 5000, 10000, 20000];
let inboxTimer = null;

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

/** One text as the phone shows it, with what the sending phone reported for it. */
function textBubble(t) {
  const when = t.sent_at ? `${String(t.sent_at).slice(0, 16).replace("T", " ")} UTC · ` : "";
  const status = TEXT_STATUS[t.status] || t.status;
  return `<div class="sms ${escapeHtml(t.kind)}"><p>${escapeHtml(t.body)}</p>
    <span>${escapeHtml(t.to)} · ${when}${escapeHtml(status)}${t.error ? ` · ${escapeHtml(t.error)}` : ""}</span></div>`;
}

function phoneInbox(texts) {
  if (!texts.length) return `<p class="fine">Texts from SafeDay will show here.</p>`;
  return `<div class="sms-inbox">${texts.map(textBubble).join("")}</div>`;
}

async function renderSmePayouts(slot, hasPolicy) {
  const [account, payouts, texts, application, demo] = await Promise.all([
    api("/api/payout-account").catch(() => null),
    api("/api/payouts"),
    api("/api/sms"),
    api("/api/applications/mine").catch(() => null),
    api("/api/demo-phone"),
  ]);
  const editing = !account || slot.dataset.editing === "1";
  slot.innerHTML = `<div class="section-head"><div><h2>Payouts</h2>
      <p class="page-sub">When NEA readings cross your trigger, SafeDay pays by PayNow and sends you a text. There is no claim to make.</p></div></div>
    <div class="sme-grid">
      <div class="card"><h2>Get paid by PayNow</h2>
        ${editing ? accountForm(account) : accountSummary(account)}
        ${hasPolicy ? "" : notice("", "info", "Pick a cover above too, or there is nothing to pay.")}
      </div>
      <div class="card"><h2>Texts on your phone</h2><div id="sme-inbox">${phoneInbox(texts)}</div></div>
    </div>
    <h3 class="subhead">Your payouts</h3>
    <div id="sme-payout-list">${smePayoutList(payouts)}</div>`;
  if (!account) prefillPaynowMobile(application?.phone, demo.mobile);
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
      el("sme-payout-list").innerHTML = smePayoutList(payouts);
    } catch (error) {
      el("verify-error").textContent = `Could not refresh your texts: ${error.message}`;
    }
  }, INBOX_REFRESH_MS);
}

/* For the demo: start the PayNow form with the mobile the owner gave in the buy flow, or else
   the demo phone. */
function prefillPaynowMobile(phone, demoMobile) {
  const proxy = el("paynow-form")?.elements.paynow_proxy;
  if (!proxy) return;
  if (/^[89]\d{7}$/.test(phone || "")) proxy.value = `+65${phone}`;
  else if (demoMobile) proxy.value = demoMobile;
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
    el("code-note").textContent = sent.texts_are_real
      ? `Code sent to ${sent.sent_to}. Check your phone.`
      : `Code sent to ${sent.sent_to}. Demo only, the SMS is simulated: your code is ${sent.demo_code}.`;
    if (sent.demo_code) el("code-input").value = sent.demo_code;
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
  const [payouts, options, history, holders] = await Promise.all([
    api("/api/payouts"),
    api("/api/options"),
    api("/api/map/day?date=0000-00-00"),
    api("/api/insurer/policyholders"),
  ]);
  const latest = history.available.max;
  const paid = payouts.filter((p) => p.status === "paid");
  const hazardLabels = Object.fromEntries(options.hazards.map((h) => [h.key, h.label]));
  const hazards = options.hazards.map((h) => `<option value="${h.key}">${escapeHtml(h.label)} (${escapeHtml(h.reading)})</option>`).join("");
  slot.innerHTML = `<div class="section-head"><div><h2>Payouts</h2>
      <p class="page-sub">Assesses every policy for that Singapore day and pays what the tariff gives, by PayNow, with an SMS. A day already run is never paid twice.</p></div>
      <p class="fine"><span class="num">${paid.length.toLocaleString("en-SG")}</span> paid · <span class="num">${SGD(paid.reduce((sum, p) => sum + p.amount_sgd, 0))}</span> sent in total</p></div>
    ${demoPayoutCard(holders, options.hazards)}
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

function holderOption(h) {
  const phone = !h.texts_to ? "no mobile yet" : `${h.texts_to}${h.mobile_verified ? "" : ", not verified"}`;
  return `<option value="${h.user_id}">${escapeHtml(h.business_name)} · ${escapeHtml(h.centre)} · ${escapeHtml(h.tier_label)} (${escapeHtml(phone)})</option>`;
}

/* For a demo: pay one customer now, by PayNow, with the payment SMS to a +65 mobile. */
function demoPayoutCard(holders, hazards) {
  const customers = holders.policyholders;
  if (!customers.length) return `<div class="card"><h3>Demo: pay a customer now</h3><p class="fine">No customer has cover yet.</p></div>`;
  const hazardOptions = hazards.map((h) => `<option value="${h.key}" ${h.key === DEMO_READING.hazard ? "selected" : ""}>${escapeHtml(h.label)} (${escapeHtml(h.reading)})</option>`).join("");
  const languageOptions = Object.entries(LANGUAGES).map(([key, label]) => `<option value="${key}">${label}</option>`).join("");
  const fallback = holders.fallback_mobile;
  const how = holders.texts_are_real
    ? "The SMS goes to the customer's real phone through textbee: keep the sending phone online with the textbee app open."
    : "Texts are simulated: set TEXTBEE_API_KEY to reach real phones. The customer still sees the text on their dashboard.";
  return `<form id="demo-form" class="card run-form">
    <h3>Demo: pay a customer now</h3>
    <label>Customer <select name="user_id">${customers.map(holderOption).join("")}</select></label>
    <label>Hazard <select name="hazard">${hazardOptions}</select></label>
    <label>Reading <input name="reading" type="number" step="any" value="${DEMO_READING.reading}" required /></label>
    <label>Pay and text mobile <input name="mobile" type="tel" placeholder="+6591234567" value="${escapeHtml(fallback || "")}" autocomplete="off" /></label>
    <label>SMS in <select name="sms_language">${languageOptions}</select></label>
    <button class="btn primary" type="submit">Send payout and SMS</button>
    <p class="fine run-note">Pays today, skipping the 30-day waiting period, by PayNow, and texts the payment notice. A mobile entered here becomes the customer's PayNow and texting mobile, with no code to verify. Left blank: the customer's own verified mobile${fallback ? `, or ${escapeHtml(fallback)} if they have none` : ""}. ${how}</p>
    <p class="run-result" id="demo-result" aria-live="polite"></p><p class="error" id="demo-error" role="alert"></p>
  </form>`;
}

function latestText(payout) {
  return payout.texts[payout.texts.length - 1];
}

function demoSummary(outcome, p) {
  const text = latestText(p);
  const sms = !text ? "no SMS"
    : text.status === "failed" ? `SMS to ${text.to} failed: ${text.error}`
    : `SMS to ${text.to}: ${TEXT_STATUS[text.status] || text.status}`;
  return `${p.reference} · ${p.business_name} · ${SGD(p.amount_sgd)} ${outcome.replaceAll("_", " ")} · ${sms}`;
}

function showDemoResult(outcome, payout) {
  el("demo-result").innerHTML = notice("", "check", escapeHtml(demoSummary(outcome, payout)));
}

/** Keep looking at a demo payout's SMS until the sending phone says what happened to it. */
async function followDemoText(slot, outcome, reference) {
  for (const wait of DEMO_TEXT_CHECKS_MS) {
    await new Promise((resolve) => setTimeout(resolve, wait));
    const payout = (await api("/api/payouts")).find((p) => p.reference === reference);
    if (!payout || !el("demo-result")) return;
    if (latestText(payout)?.status === "queued") continue;
    await renderInsurerPayouts(slot);
    showDemoResult(outcome, payout);
    return;
  }
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
  el("demo-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(event.target);
    const body = {
      user_id: Number(data.user_id),
      readings: { [data.hazard]: Number(data.reading) },
      sms_language: data.sms_language,
    };
    if (data.mobile.trim()) body.mobile = data.mobile.trim();
    busy(event.submitter, "demo-error", async () => {
      const sent = await post("/api/insurer/demo-payouts", body);
      await renderInsurerPayouts(slot);
      showDemoResult(sent.outcome, sent.payout);
      if (latestText(sent.payout)?.status === "queued") {
        followDemoText(slot, sent.outcome, sent.payout.reference)
          .catch((error) => { el("demo-error").textContent = `Could not check the SMS: ${error.message}`; });
      }
    });
  });
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
