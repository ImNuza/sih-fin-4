/* Payung day colours: one label for a day's loss score, shared by the dashboards, the risk map
   and the tariff desk. Served at /day-colour.js. The bands were set by the team on 15 Nov 2026:
   green under 30%, yellow 30% to under 70%, red 70% to 100%. A day with no loss gets its own grey
   label, because a green day still pays. The label sits next to the % and the payout, never
   instead of them. api/sms.py holds the same bands for the payout text. */
"use strict";

const DAY_COLOURS = [
  { key: "red", from: 70, label: "Red day" },
  { key: "yellow", from: 30, label: "Yellow day" },
  { key: "green", from: 0, label: "Green day" },
];
const NO_LOSS_DAY = { key: "none", label: "No payout today" };

function dayColour(lossPercent) {
  if (!(lossPercent > 0)) return NO_LOSS_DAY;
  return DAY_COLOURS.find((band) => lossPercent >= band.from);
}

function dayChip(lossPercent) {
  const colour = dayColour(lossPercent);
  return `<span class="day-chip day-${colour.key}" title="${colour.label}">${colour.label}</span>`;
}
