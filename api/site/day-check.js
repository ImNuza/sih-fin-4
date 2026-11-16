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

const reading = (value) => value.toLocaleString("en-SG");
const NOT_REPORTED = `<span class="fine">not reported yet</span>`;

/* Each hazard's unit, so a number never reads as the wrong thing. Heat counts work hours at WBGT
   32°C or more (scripts/heat_stats.py), not degrees. Flood and closure are yes or no. */
const UNITS = {
  haze: () => "PSI",
  rain: () => "mm",
  heat: (value) => (value === 1 ? "hr" : "hrs"),
};
const UNIT_AFTER = { heat: " at 32°C+" };
const YES_NO = { flood: ["No flood alert", "PUB flood alert"], closure: ["No closure order", "Closure order"] };

const withUnit = (hazard, value) => `${reading(value)} ${UNITS[hazard]?.(value) ?? ""}`.trim();
const levelColour = (level) => `${dayColour(level.loss_percent).label.toLowerCase()} (${level.loss_percent.toFixed(0)}% of the day)`;

/* "0 of 2 hrs at 32°C+", "45 of 101 PSI", "No flood alert": the reading against the next level. */
function readingLine(h, next) {
  const yesNo = YES_NO[h.hazard];
  if (yesNo) return h.value === null ? NOT_REPORTED : `<b>${yesNo[h.value >= 1 ? 1 : 0]}</b>`;
  const after = UNIT_AFTER[h.hazard] || "";
  const target = next ? `${withUnit(h.hazard, next.at_least)}${after}` : null;
  if (h.value === null) return target ? `${NOT_REPORTED} <span class="trigger">/ ${target}</span>` : NOT_REPORTED;
  if (!target) return `<b class="num">${withUnit(h.hazard, h.value)}${after}</b>`;
  return `<b class="num">${reading(h.value)}</b> <span class="trigger">of ${target}</span>`;
}

/* What the next level brings: "2 hrs or more at 32°C+: yellow (30% of the day)". */
function aheadLine(h, next) {
  if (!next) return "the highest level";
  const yesNo = YES_NO[h.hazard];
  if (yesNo) return `${yesNo[1]}: ${levelColour(next)}`;
  return `${withUnit(h.hazard, next.at_least)} or more${UNIT_AFTER[h.hazard] || ""}: ${levelColour(next)}`;
}

/* The reading next to the next level up, so the gap reads at a glance: the first trigger until
   it is reached, then each higher level (yellow, then red) in turn. The chip is the day colour of
   the level reached; the line under it is what the next level brings. Levels score one hazard
   alone, so several hazards on one day can make it redder. Heat also shows the day's peak WBGT,
   which says how close a day came; only the hours pay. */
function readingCell(h) {
  const reached = h.value === null ? null : h.levels.filter((l) => h.value >= l.at_least).at(-1);
  const next = h.levels.find((l) => h.value === null || h.value < l.at_least);
  const now = reached ? dayChip(reached.loss_percent) : pill("muted", "below");
  const peak = h.peak == null ? "" : `<span class="fine block">Peak WBGT ${h.peak.toFixed(1)}°C</span>`;
  return `${readingLine(h, next)} ${now}<span class="fine block">${aheadLine(h, next)}</span>${peak}`;
}

function readingRows(hazards) {
  if (!hazards.length) return "";
  return `<div class="table-wrap"><table class="data day-readings">
    <thead><tr><th>Hazard</th><th class="num">Reading / next level</th><th>Station and rule</th></tr></thead>
    <tbody>${hazards.map((h) => `<tr>
      <td>${SafeUI.icon(ICON_FOR_HAZARD[h.hazard] || "info")} <b>${escapeHtml(h.label)}</b><span class="fine block">${escapeHtml(h.measures)}</span></td>
      <td class="num nowrap">${readingCell(h)}</td>
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

/* The card: a date box and the readings below it, open from the start on the owner's latest
   payout day, or else the latest day NEA has published. Picking another day shows it at once. */
async function renderDayCheck(slot, latestPayoutDay) {
  const history = await api("/api/map/day?date=0000-00-00");
  const latest = history.available.max;
  slot.innerHTML = `<form id="day-check-form" class="day-check-form">
      <label>Day <input type="date" id="day-check-date" value="${latest}" max="${latest}" required /></label>
    </form>
    <p class="fine">Pick any day to see the NEA reading at your place, the station it came from and the level it is measured against. NEA readings run to ${dayLabel(latest)}.</p>
    <div id="day-check-result" aria-live="polite"></div>`;
  el("day-check-form").addEventListener("submit", (event) => event.preventDefault());
  el("day-check-date").addEventListener("change", (event) => {
    if (event.target.value) showDay(event.target.value);
  });
  await showDay(latestPayoutDay || latest);
}
