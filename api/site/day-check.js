/* The 'see the reading' card on the owner's dashboard. For any day it shows each reading at the
   business, the station rule that chose it, the trigger it is measured against, and whether the
   day paid and why not. There is no appeal that changes a payout; a wrong reading or a wrong shop
   category is reported as an ordinary Income service request, which corrects data only.
   Uses el, api, post, SGD, formData, escapeHtml, notice, pill and loadError from site.js, and
   dayLabel and busy from payouts.js. The API decides every outcome; this file puts it in words. */
"use strict";

const ICON_FOR_HAZARD = { haze: "cloud-fog", rain: "cloud-rain", heat: "thermometer-sun", flood: "waves", closure: "store" };
const SERVICE_KINDS = { wrong_reading: "A reading is wrong", wrong_category: "My shop category is wrong" };

/* Tone, icon and sentence for each outcome: a payout status, or why a day was not paid. */
function outcomeNotice(check) {
  const p = check.payout;
  const reason = p?.failure_reason ? `: ${escapeHtml(p.failure_reason)}` : "";
  const says = {
    paid: ["", "check", `Paid ${p && SGD(p.amount_sgd)} by PayNow (${p && escapeHtml(p.reference)}). These are the readings the payout used.`],
    capped: ["warning", "info", "A reading reached its trigger, but this year's paid days were already used up, so nothing more was paid."],
    held: ["warning", "clock", `Owed ${p && SGD(p.amount_sgd)}, waiting for your mobile to be verified.`],
    sending: ["warning", "clock", "Being paid by PayNow now."],
    approved: ["warning", "clock", "Approved and about to be paid."],
    assessed: ["warning", "clock", "Assessed and about to be paid."],
    failed: ["critical", "circle-alert", `The PayNow transfer failed${reason}. Income will retry it.`],
    rejected: ["critical", "circle-alert", `Not paid${reason}.`],
    below_trigger: ["warning", "info", "<b>No payout.</b> No reading reached its trigger, so this day pays nothing, even if your sales were down."],
    not_run_yet: ["", "clock", "A reading reached its trigger. Income has not run payouts for this day yet; when it does, the money comes without a claim."],
    waiting_period: ["warning", "info", `<b>No payout.</b> Your cover pays from ${dayLabel(check.cover_pays_from)}, after the 30-day waiting period, so this day pays nothing.`],
    cover_ended: ["warning", "info", "<b>No payout.</b> Your cover had ended by this day."],
    awaiting_data: ["", "clock", "Not every station has reported yet. If a reading reaches its trigger once the data arrives, the day is paid then."],
    no_record: ["", "info", "NEA has not published this day's readings yet. Check again in a day or two."],
  };
  const [tone, icon, html] = says[check.outcome] || ["", "info", escapeHtml(check.outcome)];
  return notice(tone, icon, html);
}

function readingCell(h) {
  if (h.value === null) return `<span class="fine">not reported yet</span>`;
  const reached = h.crossed ? pill("warning", "reached") : pill("muted", "below");
  return `<span class="num">${h.value.toLocaleString("en-SG")}</span> ${reached}`;
}

function readingRows(hazards) {
  if (!hazards.length) return "";
  return `<div class="table-wrap"><table class="data day-readings">
    <thead><tr><th>Hazard</th><th class="num">Reading</th><th class="num">Pays from</th><th>Station and rule</th></tr></thead>
    <tbody>${hazards.map((h) => `<tr>
      <td>${SafeUI.icon(ICON_FOR_HAZARD[h.hazard] || "info")} <b>${escapeHtml(h.label)}</b><span class="fine block">${escapeHtml(h.measures)}</span></td>
      <td class="num">${readingCell(h)}</td>
      <td class="num">${h.pays_from.toLocaleString("en-SG")}</td>
      <td>${escapeHtml(h.basis || "")}</td>
    </tr>`).join("")}</tbody></table></div>`;
}

function serviceRequestForm(day) {
  const kinds = Object.entries(SERVICE_KINDS).map(([key, label]) => `<option value="${key}">${label}</option>`).join("");
  return `<details class="day-report"><summary>Report a wrong reading or wrong shop category</summary>
    <form id="service-request-form" class="payout-form" novalidate>
      <input type="hidden" name="loss_date" value="${day}" />
      <label>What is wrong <select name="kind">${kinds}</select></label>
      <label>What you saw <textarea name="note" rows="2" maxlength="500" placeholder="For example: heavy rain at my stall from 12 to 2pm"></textarea></label>
      <p class="fine">This opens an ordinary Income service request. It corrects a wrong reading or shop category; it never adds money for the size of a loss.</p>
      <p class="error" id="service-request-error" role="alert"></p>
      <button class="btn small" type="submit">Send to Income</button>
    </form></details>`;
}

function dayResult(check) {
  return `<h3 class="day-title">${dayLabel(check.date)}</h3>
    ${outcomeNotice(check)}
    ${readingRows(check.hazards)}
    ${serviceRequestForm(check.date)}`;
}

async function showDay(day) {
  const slot = el("day-check-result");
  if (!slot) return;
  el("day-check-date").value = day;
  slot.setAttribute("aria-busy", "true");
  try {
    slot.innerHTML = dayResult(await api(`/api/my-day?day=${encodeURIComponent(day)}`));
    wireServiceRequest();
  } catch (error) {
    slot.innerHTML = loadError("that day's readings", error);
  } finally {
    slot.removeAttribute("aria-busy");
  }
}

function wireServiceRequest() {
  el("service-request-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(event.target);
    if (!data.note) delete data.note;
    busy(event.submitter, "service-request-error", async () => {
      const sent = await post("/api/service-requests", data);
      event.target.outerHTML = notice("", "check", `Sent to Income as ${escapeHtml(sent.reference)}. Their service team will check the reading and the station it came from.`);
    });
  });
}

/* The card: a date box set to the latest day NEA has published, and the result below it. */
async function renderDayCheck(slot) {
  const history = await api("/api/map/day?date=0000-00-00");
  const latest = history.available.max;
  slot.innerHTML = `<form id="day-check-form" class="day-check-form">
      <label>Day <input type="date" id="day-check-date" value="${latest}" max="${latest}" required /></label>
      <button class="btn small" type="submit">See the reading</button>
    </form>
    <p class="fine">Any day shows the NEA reading at your place, the station it came from and the trigger it is measured against. NEA readings run to ${dayLabel(latest)}.</p>
    <div id="day-check-result" aria-live="polite"></div>`;
  el("day-check-form").addEventListener("submit", (event) => {
    event.preventDefault();
    showDay(el("day-check-date").value);
  });
}
