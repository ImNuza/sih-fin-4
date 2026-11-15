/* Payung proof lines: what a tier would have paid at the customer's own place, in plain words,
   shared by the buy page, the dashboard and the risk atlas. Served at /tier-proof.js. Every number
   comes from the quote's TierQuote (price_per_day_sgd, cover_multiple, proof, best_value,
   haze_bonus); nothing is worked out here, only worded. */
"use strict";

/* S$1.30 for small amounts, S$1,400 or S$432 for whole or large ones. */
/* A year's payout in whole dollars, as the buy page and the atlas both show it. */
function yearMoney(value) {
  return "S$" + Math.round(Number(value)).toLocaleString("en-SG");
}

function proofMoney(value) {
  const amount = Number(value);
  if (amount >= 100 || Number.isInteger(amount)) return "S$" + Math.round(amount).toLocaleString("en-SG");
  return "S$" + amount.toFixed(2);
}

/* Who the proof is about, by business class: a shop, else a stall at a hawker centre. */
function proofWho(businessClass) {
  return businessClass === "shop" ? "a shop here" : "a stall here";
}

/* The most full bad days a tier pays in a year. */
function tierDays(tier) {
  return tier.max_paid_days_per_year ?? Math.round(tier.max_payout_per_year_sgd / tier.daily_payout_sgd);
}

/* "S$1.30 a day", or "" when the quote has no daily price. */
function dayPrice(tier) {
  return tier?.price_per_day_sgd == null ? "" : `${proofMoney(tier.price_per_day_sgd)} a day`;
}

/* "Up to S$1,400 a year: 3 times what you pay." */
function coverLine(tier) {
  const multiple = tier.cover_multiple == null ? "" : `: ${Number(tier.cover_multiple)} times what you pay`;
  return `Up to ${proofMoney(tier.max_payout_per_year_sgd)} a year${multiple}.`;
}

/* "Priced to return about 55 cents of every S$1 on average.", from proof.payback_share, or "". */
function centsBack(tier) {
  const share = tier?.proof?.payback_share;
  return share == null ? "" : `Priced to return about ${Math.round(share * 100)} cents of every S$1 on average.`;
}

/* The four proof numbers as sentences, in order. [] when there is no replay. */
function proofLines(tier, businessClass) {
  const proof = tier?.proof;
  if (!proof) return [];
  const who = proofWho(businessClass);
  const Who = who.charAt(0).toUpperCase() + who.slice(1);
  const years = proof.years_replayed;
  const days = Math.round(proof.payout_days_per_year);
  const spread = days >= 1 ? `about ${days} day${days === 1 ? "" : "s"}` : "less than one day";
  const lines = [];
  if (proof.typical_year_paid_sgd > 0)
    lines.push(`A typical year paid ${yearMoney(proof.typical_year_paid_sgd)}, spread over ${spread} with a part payout.`);
  lines.push(proof.years_paid === 0
    ? `${Who} would not have been paid in any of the last ${years} years.`
    : proof.years_paid === years
      ? `${Who} would have been paid in each of the last ${years} years.`
      : `${Who} would have been paid in ${proof.years_paid} of the last ${years} years.`);
  lines.push(proof.paid_2026_sgd > 0
    ? `In 2026, ${who} would have been paid ${yearMoney(proof.paid_2026_sgd)} in total.`
    : `In 2026, ${who} would not have been paid.`);
  lines.push(`We estimate a year like 2015 would pay about ${yearMoney(proof.haze_2015_like_sgd)}. It does not run out before ${tierDays(tier)} bad days.`);
  return lines;
}

/* The tier to suggest: the wanted one (by default the first) when the quote sells it directly,
   else the nearest smaller tier sold directly, else the smallest one that is. When no tier is
   sold directly here, the wanted one: it then goes to an underwriter. */
function directTier(quote, wantedKey) {
  const keys = quote.tiers.map((t) => t.tier);
  const wanted = Math.max(0, keys.indexOf(wantedKey ?? keys[0]));
  const direct = quote.tiers.map((t, at) => ({ t, at })).filter(({ t }) => t.sold_directly !== false);
  if (!direct.length) return quote.tiers[wanted];
  const below = direct.filter(({ at }) => at <= wanted);
  return (below.length ? below.at(-1) : direct[0]).t;
}

/* "Tier 4 gives the most cover for each dollar: up to 4.4 times what you pay.", when the quote's
   best_value tier is not the suggested one, else "". */
function bestValueLine(quote, suggestedKey) {
  const best = quote.tiers.find((t) => t.best_value);
  if (!best || best.tier === suggestedKey) return "";
  return `${best.label} gives the most cover for each dollar: up to ${Number(best.cover_multiple)} times what you pay.`;
}

const HAZE_RECORD_FROM = 2014; // the PSI history the add-on is priced on starts in April 2014
const timesWord = (n) => (n === 1 ? "once" : n === 2 ? "twice" : `${n} times`);

/* The severe haze payout add-on for a tier, in plain words, from tier.haze_bonus. "" without it. */
function hazeBonusPitch(tier) {
  const bonus = tier?.haze_bonus;
  if (!bonus) return "";
  const years = bonus.would_have_paid_years || [];
  const span = new Date().getFullYear() - HAZE_RECORD_FROM + 1;
  const history = years.length
    ? `That happened ${timesWord(years.length)} in the last ${span} years (${years.join(", ")}).`
    : `It has not happened here since ${HAZE_RECORD_FROM}, the start of the records.`;
  return `Add ${proofMoney(bonus.weekly_sgd)} a week. If your area has ${bonus.trigger_days} or more unhealthy-haze days in a year, we pay ${proofMoney(bonus.lump_sum_sgd)} at once: ${Number(bonus.multiple)} times what the add-on costs. ${history}`;
}
