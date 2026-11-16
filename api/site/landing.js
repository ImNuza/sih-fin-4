/* Landing page (/): the tier offer from the live tariff, and the three-step payout flow.
   The offer's figures in the HTML are the fallback; this replaces them with today's tariff. */
"use strict";

const OFFER_PRODUCT = "cooked_food";
const LOCKDOWN_DAYS = 40;

const money = (v) => "S$" + (v >= 100 || Number.isInteger(v)
  ? Math.round(v).toLocaleString("en-SG") : Number(v).toFixed(2));
const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};

/* Each tier: the cheapest hawker centre's weekly premium ("from"), its payout, a 40-day lockdown,
   a 2015-like haze year at the middle centre, and the yearly cap. A hawker pays its own centre's
   price, so the figures come from the 103 centre quotes, as the proposal's do. */
async function fillOffer() {
  const grid = document.getElementById("offer-grid");
  if (!grid) return;
  const response = await fetch(`/api/map/quotes?product=${OFFER_PRODUCT}`);
  if (!response.ok) throw new Error(`quotes ${response.status}`);
  const quotes = Object.values((await response.json()).centres);
  for (const card of grid.querySelectorAll("[data-tier]")) {
    const tiers = quotes.map((q) => q.tiers.find((t) => t.tier === card.dataset.tier)).filter(Boolean);
    if (!tiers.length) continue;
    const t = tiers[0];
    const days = t.max_paid_days_per_year ?? Math.round(t.max_payout_per_year_sgd / t.daily_payout_sgd);
    const set = (field, text) => { card.querySelector(`[data-f="${field}"]`).textContent = text; };
    set("daily", money(t.daily_payout_sgd));
    set("weekly", money(Math.min(...tiers.map((x) => x.weekly_premium_sgd))));
    set("lockdown", money(Math.min(LOCKDOWN_DAYS, days) * t.daily_payout_sgd));
    set("haze", `about ${money(median(tiers.map((x) => x.proof?.haze_2015_like_sgd ?? 0)))}`);
    set("year", money(t.max_payout_per_year_sgd));
  }
}

/* The flow plays once each time it scrolls into view: step 1 lights, the line to step 2 fills,
   step 2 lights, the line to step 3 fills, step 3 lights and shows the payout. It rests on the
   finished state, then plays again a few seconds later while it stays in view. */
const FLOW_TIMELINE = [
  [0, "s1"], [520, "l1"], [1120, "s2"], [1640, "l2"], [2240, "s3"],
];
const FLOW_REST_MS = 4200;
const FLOW_FADE_MS = 450;

function wireFlow() {
  const flow = document.getElementById("pay-flow");
  if (!flow) return;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (still.matches || !("IntersectionObserver" in window)) {
    flow.classList.add("s1", "l1", "s2", "l2", "s3", "still");
    return;
  }
  let timers = [];
  const stop = () => { timers.forEach(clearTimeout); timers = []; };
  // A replay first lets the finished state fade out, so step 1 visibly starts again.
  const play = (fadeMs = 0) => {
    stop();
    flow.classList.remove("s1", "l1", "s2", "l2", "s3");
    for (const [at, cls] of FLOW_TIMELINE) timers.push(setTimeout(() => flow.classList.add(cls), fadeMs + at));
    timers.push(setTimeout(() => play(FLOW_FADE_MS), fadeMs + FLOW_TIMELINE.at(-1)[0] + FLOW_REST_MS));
  };
  new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) play(FLOW_FADE_MS);
    else stop();
  }, { threshold: 0.4 }).observe(flow);
}

document.addEventListener("DOMContentLoaded", () => {
  wireFlow();
  fillOffer().catch(() => { /* the HTML's figures stay */ });
});
