/* Payung risk atlas: 3D map of SME climate-risk exposure and pricing over Singapore.
   Data: /api/map/static (geography, exposure, hazard stats), /api/map/quotes (pricing),
   /api/map/live (today's NEA readings), POST /api/assess (one day's loss score).
   All pricing comes from the server's calculator; this file only draws it. */
"use strict";

// The hazard and status colours are defined once, in /theme.css, and read here for deck.gl.
const THEME = getComputedStyle(document.documentElement);
function themeRgb(name) {
  const hex = THEME.getPropertyValue(`--${name}`).trim();
  return [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16));
}
const COLORS = {
  ...Object.fromEntries(["heat", "rain", "haze", "flood", "good", "warning", "serious", "critical", "ink", "muted"]
    .map((name) => [name, themeRgb(name)])),
  rentLow: [96, 110, 128], rentHigh: [244, 196, 78], rentNone: [70, 74, 80],
};
// Pins on a live or simulated day take the colour of the day's label from /day-colour.js.
const PIN_BY_DAY = { none: "muted", yellow: "warning", red: "critical" };
const CSS_BY_HAZARD = { haze: "var(--haze)", rain: "var(--rain)", heat: "var(--heat)", flood: "var(--flood)", closure: "var(--closure)" };
const AFFORDABLE_WEEKLY_SGD = 3;   // the brief's "a few dollars a week"
const COPAY_WEEKLY_SGD = 6;        // above this even a co-payer is a stretch
const LIVE_POLL_MS = 60_000;       // the server refreshes its NEA snapshot every 5 minutes
const DEFAULT_PRODUCT = "cooked_food";  // what a hand-drawn circle sells until a shop says otherwise
const WAITING_PERIOD_DAYS = 30;     // api/payout_flow.py: no payout in the first 30 days of cover
const SHOP_RADIUS_KM = 0.5;
const SHOP_ZOOM = 14;
const PANELS_UNDER_MAP = window.matchMedia("(max-width: 720px)");   // map.css stacks the panels over the map's lower half
const PANELS_CROWD_MAP = window.matchMedia("(max-width: 1024px)");  // the right-hand panels cover the middle of the map
const PHOTO_MAX_BYTES = 5 * 1024 * 1024;
const BAD_DAYS = [
  { key: "haze230", hazard: "haze", label: "Haze day · PSI 230", sim: { psi: 230, rain: 0, heat: 0, flood: false } },
  { key: "storm", hazard: "rain", label: "50 mm storm hour", sim: { psi: 0, rain: 50, heat: 0, flood: true } },
  { key: "hot", hazard: "heat", label: "4 h at 32 °C", sim: { psi: 0, rain: 0, heat: 4, flood: false } },
];
const PSI_BANDS = [[301, "Hazardous"], [201, "Very unhealthy"], [101, "Unhealthy"], [51, "Moderate"], [0, "Good"]];
const HAZARD_ICON = { haze: "cloud-fog", rain: "cloud-rain", heat: "thermometer-sun", flood: "waves" };
// Hawker centre dot colours: the pricing verdict in History, the day's loss label otherwise.
const SME_LEGEND = {
  history: [["good", "Offer"], ["warning", "Co-pay"], ["serious", "Not offered"]],
  day: [["good", "Under 30%"], ["warning", "Under 70%"], ["critical", "70% and up"], ["muted", "No payout"]],
};
// Inside a dashboard iframe, or on a small screen, the panels start folded so the map stays visible.
const EMBEDDED = window.self !== window.top;
const COMPACT_SCREEN = "(max-width: 720px), (max-height: 600px)";
document.documentElement.classList.toggle("embedded", EMBEDDED);

const state = {
  mode: "history",                 // history | sim | live
  camera: "bird",                  // plan | bird | city
  orbit: false,
  layers: { sme: true, heat: true, rain: true, haze: true, flood: false, pa: true, bld: true, base: true },
  sim: { psi: 0, rain: 0, heat: 0, flood: false },
  simExtra: {},                    // readings for tariff hazards beyond the four built-in ones
  simAssessment: null,             // latest POST /api/assess result for the sim readings
  replay: null,                    // a replayed past day: /api/map/day with every centre's own loss
  circles: [],                     // scenario circles: {id, lat, lng, radiusKm, product, place, readings, extraDays, scn}
  shopId: null,                    // the circle placed from the "Tell us about your shop" box
  shopDraft: null,                 // the box's answer, waiting for the owner to confirm it
  activeId: null,                  // the circle the simulator's controls are editing
  nextId: 1,
  drawing: null,                   // "center" | "drag" while the user draws
  draft: null,                     // the circle being drawn
  extraDays: 5,                    // frequency stress buffer: days like this added per year
  live: null,                      // latest /api/map/live snapshot
  livePoll: null,
  zoom: 10.6,
  rev: 0,                          // bumped on anything that changes layer accessors
  selected: null,                  // {type, index|obj}
  tier: null,                      // portfolio tier key
  smeByRent: false,                // colour hawker centres by NEA rent class instead of pricing
};
let STATIC = null, QUOTES = null, OPTIONS = null, BUILDINGS = null, RENT = null, deckgl = null;
let PARTIAL_DAYS = {}; // each tier's payout on a day at the first haze band (partialExamples)
let lastView = null;               // the camera, kept across presets, orbit and user drags
const ONEMAP_TILES = "https://www.onemap.gov.sg/maps/tiles/Night/{z}/{x}/{y}.png";

const el = (id) => document.getElementById(id);
const icon = (name) => SafeUI.icon(name);
const SGD = (v) => "S$" + (v >= 1000 ? Math.round(v).toLocaleString("en-SG") : v.toFixed(2));
const SGD0 = (v) => "S$" + Math.round(v).toLocaleString("en-SG");
const psiBand = (v) => PSI_BANDS.find(([from]) => v >= from)[1];

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json();
}
const api = {
  static: () => getJson("/api/map/static"),
  quotes: () => getJson("/api/map/quotes?product=cooked_food"),
  options: () => getJson("/api/options"),
  rent: () => getJson("/api/rent").catch(() => null),
  live: () => getJson("/api/map/live?product=cooked_food"),
  coverText: (tier) => getJson(`/api/cover-text?${new URLSearchParams({ tier })}`),
  assess: (readings) => getJson("/api/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product: "cooked_food", tier: state.tier, readings }),
  }),
  day: (date) => getJson(`/api/map/day?date=${date}`),
  burn: (centre, product, tier, takings) => getJson(
    `/api/map/burn?centre=${encodeURIComponent(centre)}&product=${product}&tier=${tier}&takings=${takings}`),
  scenario: (body) => getJson("/api/map/scenario", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
  kyc: (body) => getJson("/api/map/kyc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
};
// The four hazards with a built-in control. Every other tariff hazard reads from `extra`, or 0.
const SIM_READING = {
  haze: (sim) => sim.psi, rain: (sim) => sim.rain, heat: (sim) => sim.heat, flood: (sim) => (sim.flood ? 1 : 0),
};
function readingsOf(sim, extra) {
  return Object.fromEntries(OPTIONS.hazards.map((h) => [h.key, SIM_READING[h.key]?.(sim) ?? extra[h.key] ?? 0]));
}
function simReadings() { return readingsOf(state.sim, state.simExtra); }
// Everything the engine prices a circle from. A new ScenarioRequest field is one line here.
function scenarioBody(circle, readings) {
  return {
    lat: circle.lat, lng: circle.lng, radius_km: circle.radiusKm,
    readings: { ...readings }, extra_days_per_year: circle.extraDays,
    product: circle.product, tier: state.tier,
  };
}
function productLabel(key) { return OPTIONS.products.find((p) => p.key === key)?.label ?? key; }
function tierLabel(key) { return OPTIONS.tiers.find((t) => t.key === key)?.label ?? key; }

/* ---------- pricing views (all numbers come from the API) ---------- */
function regionQuote(region) { return QUOTES.quotes[region]; }
// A hawker centre is priced from its nearest NEA stations, as a stall there is charged.
function centreQuote(centre) { return QUOTES.centres?.[centre.name] ?? regionQuote(centre.region); }
function centreParts(centre) { return QUOTES.centre_loss_day_parts?.[centre.name] ?? QUOTES.loss_day_parts[centre.region]; }
// The tier the atlas headlines for a centre, from the tiers offered there (offeredTiers,
// tier-proof.js). Not a suggestion: that needs the business's own daily sales.
function headlineTier(quote) {
  const offered = offeredTiers(quote);
  const affordable = offered.filter((t) => t.weekly_premium_sgd <= AFFORDABLE_WEEKLY_SGD);
  return affordable.length ? affordable[affordable.length - 1] : offered[0] ?? quote.tiers[0];
}
function verdict(quote) {
  const tier = headlineTier(quote);
  if (!offeredTiers(quote).length)
    return { cls: "serious", word: "Not offered here", tier, detail: notOfferedLine(quote) };
  if (tier.weekly_premium_sgd <= AFFORDABLE_WEEKLY_SGD)
    return { cls: "good", word: "Offer", tier,
      detail: `${tier.label} fits the brief's "few dollars a week": ${SGD(tier.weekly_premium_sgd)}/wk for ${SGD0(tier.daily_payout_sgd)}/day.` };
  if (tier.weekly_premium_sgd <= COPAY_WEEKLY_SGD)
    return { cls: "warning", word: "Offer with co-pay", tier,
      detail: `Cheapest tier is ${SGD(tier.weekly_premium_sgd)}/wk here - needs an operator, platform or NTUC co-payment to stay affordable.` };
  // Above the co-pay level the tier is still offered: only the price rule hides a tier.
  return { cls: "warning", word: "Offer with co-pay", tier,
    detail: `${quote.expected_loss_days.toFixed(1)} expected loss-days/yr price every tier above ${SGD0(COPAY_WEEKLY_SGD)}/wk here.` };
}
function activeCircle() { return state.circles.find((c) => c.id === state.activeId) || null; }
function circlesAt(point) {
  return state.circles.filter((c) => haversineKm(c, point) <= c.radiusKm);
}
function currentLossFraction(index) {
  if (state.mode === "sim") {
    if (state.circles.length) {
      let worst = 0;
      for (const circle of circlesAt(STATIC.hawker_centres[index]))
        if (circle.scn) worst = Math.max(worst, circle.scn.assessment.loss_percent / 100);
      return worst;
    }
    if (state.replay) return state.replay.hawker_losses[index].loss_percent / 100;
    return state.simAssessment ? state.simAssessment.loss_percent / 100 : 0;
  }
  if (state.mode === "live" && state.live?.hawker_losses) return state.live.hawker_losses[index].loss_percent / 100;
  return 0;
}
function haversineKm(a, b) {
  const R = 6371, dLat = (b.lat - a.lat) * Math.PI / 180, dLng = (b.lng - a.lng) * Math.PI / 180;
  const h = Math.sin(dLat / 2) ** 2 +
    Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
function nearest(stations, point) {
  let best = null, bestKm = Infinity;
  for (const station of stations) {
    const km = haversineKm(station, point);
    if (km < bestKm) { bestKm = km; best = station; }
  }
  return { station: best, km: bestKm };
}

/* ---------- map layers ---------- */
const REGION_TINT = {
  north: [46, 56, 52], south: [56, 48, 52], east: [46, 52, 60], west: [56, 52, 44], central: [52, 50, 58],
};
function hazeLift(region) {
  if (state.mode === "sim" && state.replay) return Math.max(0, (state.replay.haze_by_region?.[region] ?? 0) - 50) * 28;
  if (state.mode === "sim") return Math.max(0, state.sim.psi - 50) * 28;
  if (state.mode === "live") return Math.max(0, (state.live?.haze?.[region]?.max_today ?? 0) - 50) * 28;
  return (QUOTES.loss_day_parts[region]?.haze ?? 0) * 900;
}
function heatLift(station) {
  if (state.mode === "sim") return state.sim.heat * 400;
  if (state.mode === "live") {
    const live = state.live?.heat?.find((s) => s.id === station.id);
    return (live?.hours_ge_32_today ?? 0) * 400;
  }
  return station.share_days_ge_32 * 4200;
}
function rainLift(gauge) {
  if (state.mode === "sim") return state.sim.rain * 45;
  if (state.mode === "live") {
    const live = state.live?.rain?.find((s) => s.id === gauge.id);
    return (live?.wettest_work_hour_today ?? 0) * 45;
  }
  return gauge.share_days_ge_20 * 26000;
}
function rentOf(centre) { return RENT?.centres[centre.name] || null; }
function rentColor(centre) {
  const rent = rentOf(centre);
  if (!rent || rent.estimated) return COLORS.rentNone.concat(200);
  const classes = RENT.classes, at = classes.findIndex((c) => c.key === rent.rent_class);
  const t = classes.length > 1 ? at / (classes.length - 1) : 1;
  return [0, 1, 2].map((i) => COLORS.rentLow[i] + (COLORS.rentHigh[i] - COLORS.rentLow[i]) * t).concat(235);
}
function rentChip(rent) {
  if (!rent) return "";
  return rent.estimated
    ? `${rent.rent_class_label} (estimated: no NEA bid on record)`
    : `${rent.rent_class_label} · ${SGD0(rent.median_bid_sgd)}/mo median NEA bid · ${SGD(rent.rent_per_day_sgd)}/trading day`;
}
function smeColor(centre, index) {
  if (state.mode === "sim" && state.circles.length && !circlesAt(centre).length) return [70, 74, 80, 150];
  if (state.smeByRent && state.mode === "history") return rentColor(centre);
  if (state.mode !== "history") {
    const day = dayColour(currentLossFraction(index) * 100);
    return COLORS[PIN_BY_DAY[day.key]].concat(235);
  }
  return COLORS[verdict(centreQuote(centre)).cls].concat(235);
}

function buildLayers() {
  const { GeoJsonLayer, ColumnLayer, ScatterplotLayer, TextLayer, PolygonLayer, TileLayer, BitmapLayer } = deck;
  const zoom = state.zoom, layers = [];
  const paFeatures = STATIC.planning_areas.map((p) => ({ type: "Feature", geometry: p.geometry, properties: p }));

  if (state.layers.base) layers.push(new TileLayer({
    id: "base", data: ONEMAP_TILES, minZoom: 9, maxZoom: 18, tileSize: 256, opacity: 0.5,
    getTileData: async ({ url, signal }) => {
      // OneMap answers tiles outside Singapore with an empty body, which is not an image.
      try {
        const blob = await (await fetch(url, { signal })).blob();
        return blob.size ? await createImageBitmap(blob) : null;
      } catch { return null; }
    },
    renderSubLayers: (props) => {
      const { west, south, east, north } = props.tile.bbox;
      return new BitmapLayer(props, { data: null, image: props.data, bounds: [west, south, east, north] });
    },
  }));
  if (state.layers.bld && BUILDINGS && zoom >= 11.8) layers.push(new PolygonLayer({
    id: "bld", data: BUILDINGS.rings, extruded: true, pickable: false,
    getPolygon: (d) => d,
    getElevation: BUILDINGS.nominal_height_m,
    getFillColor: [64, 70, 79, 220], getLineColor: [28, 31, 35, 255],
    material: { ambient: 0.45, diffuse: 0.6, shininess: 28 },
  }));
  if (state.layers.pa) layers.push(new GeoJsonLayer({
    id: "pa", data: paFeatures, stroked: true, filled: true, pickable: true,
    getFillColor: (f) => REGION_TINT[f.properties.psi_region].concat(state.layers.base ? 110 : 205),
    updateTriggers: { getFillColor: [state.layers.base] },
    getLineColor: [70, 74, 80, 160], getLineWidth: 1, lineWidthUnits: "pixels",
    onClick: (info) => select("region", info.object.properties),
  }));
  if (state.layers.haze) layers.push(new GeoJsonLayer({
    id: "haze", data: paFeatures, extruded: true, filled: true, stroked: false, pickable: false,
    getElevation: (f) => hazeLift(f.properties.psi_region),
    getFillColor: (f) => COLORS.haze.concat(hazeLift(f.properties.psi_region) > 0 ? 70 : 0),
    material: { ambient: 0.55, diffuse: 0.5, shininess: 24 },
    parameters: { depthWriteEnabled: false },
    transitions: { getElevation: 380 },
    updateTriggers: { getElevation: [state.rev], getFillColor: [state.rev] },
  }));
  if (state.layers.heat) layers.push(new ColumnLayer({
    id: "heat", data: STATIC.wbgt_stations, diskResolution: 14, radius: zoom > 12 ? 240 : 420,
    extruded: true, pickable: true,
    getPosition: (d) => [d.lng, d.lat],
    getElevation: (d) => heatLift(d),
    getFillColor: COLORS.heat.concat(215),
    material: { ambient: 0.5, diffuse: 0.55, shininess: 30 },
    transitions: { getElevation: 380 },
    onClick: (info) => select("heat", info.object),
    updateTriggers: { getElevation: [state.rev] },
  }));
  if (state.layers.rain) layers.push(new ColumnLayer({
    id: "rain", data: STATIC.rain_stations, diskResolution: 10, radius: zoom > 12 ? 170 : 280,
    extruded: true, pickable: true,
    getPosition: (d) => [d.lng, d.lat],
    getElevation: (d) => rainLift(d),
    getFillColor: COLORS.rain.concat(205),
    material: { ambient: 0.5, diffuse: 0.55, shininess: 30 },
    transitions: { getElevation: 380 },
    onClick: (info) => select("rain", info.object),
    updateTriggers: { getElevation: [state.rev] },
  }));
  if (state.layers.flood) layers.push(new ScatterplotLayer({
    id: "flood", data: STATIC.flood_hotspots, pickable: true, stroked: true, filled: true,
    getPosition: (d) => [d.lng, d.lat],
    getRadius: 380, radiusUnits: "meters",
    getFillColor: COLORS.flood.concat(55),
    getLineColor: COLORS.flood.concat(255), getLineWidth: 2, lineWidthUnits: "pixels",
    onClick: (info) => select("flood", info.object),
  }));
  if (state.layers.sme && zoom >= 11) layers.push(new ScatterplotLayer({
    id: "sme", data: STATIC.hawker_centres, pickable: true, stroked: true, filled: true,
    getPosition: (d) => [d.lng, d.lat],
    getRadius: (d) => 60 + Math.sqrt(Math.max(d.food_stalls, 6)) * 22, radiusUnits: "meters",
    radiusMinPixels: 3.5, radiusMaxPixels: 26,
    getFillColor: (d, { index }) => smeColor(d, index),
    getLineColor: [16, 18, 20, 255], getLineWidth: 1.5, lineWidthUnits: "pixels",
    onClick: (info) => select("sme", info.index),
    updateTriggers: { getFillColor: [state.rev, state.mode, state.smeByRent] },
  }));
  if (state.layers.sme && zoom >= 13) layers.push(new TextLayer({
    id: "sme-labels", data: STATIC.hawker_centres,
    getPosition: (d) => [d.lng, d.lat],
    getText: (d) => d.name.split(" (")[0],
    getSize: 11, getColor: [242, 241, 237, 225],
    getTextAnchor: "start", getAlignmentBaseline: "center", getPixelOffset: [12, 0],
    fontFamily: "Schibsted Grotesk, sans-serif", fontWeight: 600,
    outlineWidth: 2, outlineColor: [16, 18, 20, 255], fontSettings: { sdf: true },
    parameters: { depthWriteEnabled: false, depthCompare: "always" },
  }));
  if (state.mode === "sim" && (state.circles.length || state.draft)) {
    const circles = state.draft ? state.circles.concat([state.draft]) : state.circles;
    layers.push(new ScatterplotLayer({
      id: "circles", data: circles, pickable: false, stroked: true, filled: true,
      getPosition: (d) => [d.lng, d.lat],
      getRadius: (d) => d.radiusKm * 1000, radiusUnits: "meters",
      getFillColor: (d) => [...COLORS.ink, d === state.draft || d.id === state.activeId ? 30 : 13],
      getLineColor: (d) => d === state.draft ? [...COLORS.ink, 255]
        : d.id === state.activeId ? [...COLORS.ink, 210] : [...COLORS.muted, 160],
      getLineWidth: (d) => (d === state.draft || d.id === state.activeId ? 2 : 1.5),
      lineWidthUnits: "pixels",
      updateTriggers: { getRadius: [state.rev], getFillColor: [state.rev], getLineColor: [state.rev], getLineWidth: [state.rev] },
    }));
  }
  if (zoom < 11.6) layers.push(new TextLayer({
    id: "region-labels",
    data: Object.entries(STATIC.region_points).map(([name, [lat, lng]]) => ({ name: name.toUpperCase(), lat, lng })),
    getPosition: (d) => [d.lng, d.lat], getText: (d) => d.name,
    getSize: 13, getColor: [195, 194, 183, 200],
    fontFamily: "Schibsted Grotesk, sans-serif", fontWeight: 700,
    outlineWidth: 2, outlineColor: [16, 18, 20, 220], fontSettings: { sdf: true },
    parameters: { depthWriteEnabled: false, depthCompare: "always" },
  }));
  return layers;
}
function redraw() { state.rev += 1; deckgl.setProps({ layers: buildLayers() }); }

function tooltip({ object, layer, index }) {
  if (!object) return null;
  if (layer.id === "sme") {
    const quote = centreQuote(object), tier = headlineTier(quote);
    const live = state.mode !== "history"
      ? ` · today's loss ${(currentLossFraction(index) * 100).toFixed(0)}% ${dayChip(currentLossFraction(index) * 100)}` : "";
    const rent = rentOf(object);
    const rentLine = rent ? `<div class="m">${rentChip(rent)}</div>` : "";
    return { html: `<b>${object.name}</b><div class="m">${object.food_stalls} food stalls · ${object.region} region · ${SGD(tier.weekly_premium_sgd)}/wk at ${tier.label}${live}</div>${rentLine}` };
  }
  if (layer.id === "heat") return { html: `<b>${object.name}</b><div class="m">reached 32 °C on ${(object.share_days_ge_32 * 100).toFixed(0)}% of its ${object.days} recorded days · hottest ${object.max_wbgt.toFixed(1)} °C</div>` };
  if (layer.id === "rain") return { html: `<b>${object.name}</b><div class="m">rain gauge · a 20 mm downpour hour on ${(object.share_days_ge_20 * 100).toFixed(1)}% of its ${object.days} recorded days</div>` };
  if (layer.id === "flood") return { html: `<b>${object.name}</b><div class="m">PUB flash-flood hotspot</div>` };
  if (layer.id === "pa") return { html: `<b>${object.properties.name}</b><div class="m">${object.properties.ura_region} planning region · haze zone: ${object.properties.psi_region}</div>` };
  return null;
}

/* ---------- scenario circles ---------- */
let dragPending = false;
function circleHint(text) { el("circle-hint").textContent = text; }
const HINT_IDLE = "Scope a day to one area. Draw several circles with their own readings to compare.";
function requestScenario(circle) {
  if (state.mode !== "sim" || !circle || state.drawing === "drag") return;
  clearTimeout(circle.timer);
  circle.timer = setTimeout(async () => {
    const seq = (circle.seq = (circle.seq || 0) + 1);
    try {
      const result = await api.scenario(scenarioBody(circle, circle.readings));
      if (seq !== circle.seq) return;
      circle.scn = result;
      renderScenario(); renderFloats(); redraw(); renderPortfolio(); renderDetail();
    } catch (error) { console.error(error); }
  }, 180);
}
function requestAllScenarios() { for (const circle of state.circles) requestScenario(circle); }
function applyControlChange() {
  const circle = activeCircle();
  if (circle) {
    circle.readings = simReadings();
    circle.extraDays = state.extraDays;
    requestScenario(circle);
    markBadDay();
  } else {
    refreshSimAssessment();
  }
}
function renderScenario() {
  const box = el("scn-results"), circle = activeCircle(), scn = circle?.scn;
  if (!scn) { box.hidden = true; return; }
  box.hidden = false;
  const t = scn.totals;
  const factors = scn.assessment.hazards.filter((h) => h.loss_percent > 0);
  const empty = t.centres === 0
    ? `<p class="note" style="color:var(--warning)">No hawker centres sit inside this circle, so its payouts and premiums are S$0. Drag it over the dots, or widen it.</p>` : "";
  box.innerHTML = `
    <p class="cap">Circle ${circle.id} · ${t.centres} centres · ${t.stalls.toLocaleString("en-SG")} stalls</p>
    <div class="kv"><span class="k">Priced as</span><span class="v">${productLabel(circle.product)}</span></div>
    ${empty}
    <div class="kv"><span class="k">Loss score on this day</span><span class="v">${scn.assessment.loss_percent.toFixed(0)}% ${dayChip(scn.assessment.loss_percent)}</span></div>
    <div class="kv"><span class="k">Payout per stall (${state.tier.replace("_", " ")})</span><span class="v">${SGD(scn.assessment.payout_sgd)}</span></div>
    <div class="kv"><span class="k">Payout, whole circle</span><span class="v">${SGD(t.payout_today_sgd)}</span></div>
    <div class="kv"><span class="k">Weekly premium pool</span>
      <span class="v">${SGD(t.weekly_premium_baseline_sgd)} → <span class="delta-up">${SGD(t.weekly_premium_stressed_sgd)}</span></span></div>
    ${factors.length ? `<p class="cap">What is driving it</p>` : ""}
    ${factors.map((h) => `<div class="factor"><span>${QUOTES.hazard_labels[h.hazard] || h.hazard}</span>
      <div class="bar"><div style="width:${h.loss_percent}%;background:${CSS_BY_HAZARD[h.hazard] || "var(--accent)"}"></div></div>
      <output>${h.loss_percent.toFixed(0)}%</output></div>`).join("")}
    <p class="fine">The "if more common" slider moves only the premium line, never the day's payout. Click a circle's card on the map to edit it.</p>`;
}
function syncControls(circle) {
  state.sim = {
    psi: circle.readings.haze || 0, rain: circle.readings.rain || 0,
    heat: circle.readings.heat || 0, flood: !!circle.readings.flood,
  };
  state.simExtra = Object.fromEntries(Object.entries(circle.readings)
    .filter(([key]) => !(key in SIM_READING)));
  state.extraDays = circle.extraDays;
  el("s-psi").value = state.sim.psi; el("v-psi").textContent = state.sim.psi;
  el("psi-band").textContent = state.sim.psi > 0 ? psiBand(state.sim.psi) : "";
  el("s-rain").value = state.sim.rain; el("v-rain").textContent = `${state.sim.rain} mm`;
  el("s-heat").value = state.sim.heat; el("v-heat").textContent = `${state.sim.heat} h`;
  el("s-flood").checked = state.sim.flood;
  document.querySelectorAll("#extra-hazards [data-extra]").forEach((input) => {
    const value = state.simExtra[input.dataset.extra] || 0;
    if (input.type === "checkbox") input.checked = value >= 1;
    else { input.value = value; const out = el(`xv-${input.dataset.extra}`); if (out) out.textContent = value; }
  });
  el("s-extradays").value = state.extraDays; el("v-extradays").textContent = `${state.extraDays} d`;
  el("s-radius").value = circle.radiusKm; el("v-radius").textContent = `${circle.radiusKm.toFixed(1)} km`;
}
function selectCircle(id) {
  state.activeId = id;
  const circle = activeCircle();
  if (!circle) return;
  circle.expanded = !isCompact();
  openPanel(el("sim"));
  el("radius-row").hidden = false; el("extradays-row").hidden = false;
  el("remove-circle").hidden = false; el("clear-all").hidden = state.circles.length < 2;
  syncControls(circle);
  circleHint(`Editing circle ${id} (${circle.radiusKm.toFixed(1)} km). The sliders shape this circle's day.`);
  renderScenario(); renderFloats(); redraw(); renderPortfolio(); renderDetail();
}
const CONTROLLER_ON = { touchRotate: true, inertia: 260 };
// While aiming, panning is off so a touchpad tap with a little jitter still lands as a click.
const CONTROLLER_AIMING = { dragPan: false, dragRotate: false, touchRotate: false, scrollZoom: true, inertia: 0 };
function startDrawing() {
  if (state.drawing) { stopDrawing(); return; }
  state.drawing = "center"; state.draft = null;
  deckgl.setProps({ controller: CONTROLLER_AIMING });
  el("draw-circle").setAttribute("aria-pressed", "true");
  el("draw-circle").innerHTML = `${icon("check")}Done drawing`;
  circleHint("Press and drag outward for each circle, one after another. Done or Esc finishes, and panning comes back.");
  redraw();
}
function stopDrawing() {
  state.drawing = null; state.draft = null;
  deckgl.setProps({ controller: CONTROLLER_ON });
  el("draw-circle").setAttribute("aria-pressed", "false");
  el("draw-circle").innerHTML = `${icon("plus")}Draw circles`;
}
function newCircle(lat, lng, radiusKm) {
  return { id: state.nextId++, lat, lng, radiusKm, product: DEFAULT_PRODUCT, place: null,
           readings: simReadings(), extraDays: state.extraDays, scn: null };
}
function commitCircle(circle) {
  circle.radiusKm = Math.min(15, Math.max(0.2, circle.radiusKm));
  circle.expanded = !isCompact();
  state.circles.push(circle);
  state.activeId = circle.id;
  if (state.drawing) state.drawing = "center";  // stay armed: drag the next circle straight away
  el("remove-circle").hidden = false;
  el("clear-all").hidden = state.circles.length < 2;
  el("radius-row").hidden = false; el("extradays-row").hidden = false;
  el("s-radius").value = circle.radiusKm; el("v-radius").textContent = `${circle.radiusKm.toFixed(1)} km`;
  circleHint(`Circle ${circle.id} set (${circle.radiusKm.toFixed(1)} km). Drag the next one, or press Done or Esc to finish.`);
  requestScenario(circle);
  renderFloats();
  redraw();
}
function removeCircleById(id) {
  state.circles = state.circles.filter((c) => c.id !== id);
  if (id === state.shopId) { if (state.shopDraft) state.shopId = null; else forgetShop(); }
  if (!state.circles.length) { clearAllCircles(); return; }
  if (state.activeId === id) { selectCircle(state.circles[state.circles.length - 1].id); return; }
  el("clear-all").hidden = state.circles.length < 2;
  renderFloats(); redraw(); renderPortfolio(); renderDetail();
}
function removeActiveCircle() { removeCircleById(state.activeId); }
function clearAllCircles() {
  state.circles = []; state.activeId = null;
  forgetShop();
  stopDrawing();
  renderFloats();
  el("remove-circle").hidden = true; el("clear-all").hidden = true;
  el("radius-row").hidden = true; el("extradays-row").hidden = true;
  circleHint(HINT_IDLE);
  renderScenario(); redraw(); renderPortfolio(); renderDetail();
}
function onMapClick(info) {
  if (!info.coordinate) return;
  const [lng, lat] = info.coordinate;
  if (state.shopDraft && !state.shopDraft.place) {
    state.shopDraft.place = { name: "Point picked on the map", lat, lng };
    // The click is the owner's own answer for the place, so a known product needs no second confirm.
    if (state.shopDraft.product) placeShop(); else showShopDraft();
    return;
  }
  if (state.drawing !== "center") return;
  commitCircle(newCircle(lat, lng, +el("s-radius").value));
}
function onMapDragStart(info) {
  if (state.drawing !== "center" || !info.coordinate) return;
  const [lng, lat] = info.coordinate;
  state.draft = newCircle(lat, lng, 0.2);
  state.drawing = "drag";
  redraw();
}
function onMapDrag(info) {
  if (state.drawing !== "drag" || !info.coordinate || dragPending) return;
  const [lng, lat] = info.coordinate;
  state.draft.radiusKm = Math.min(15, Math.max(0.1, haversineKm(state.draft, { lat, lng })));
  circleHint(`${state.draft.radiusKm.toFixed(1)} km. Release to set.`);
  dragPending = true;
  requestAnimationFrame(() => { dragPending = false; redraw(); });
}
function onMapDragEnd() {
  if (state.drawing !== "drag") return;
  const draft = state.draft;
  state.draft = null;
  commitCircle(draft);
}
function buildExtraHazardControls() {
  const host = el("extra-hazards");
  const extras = (QUOTES.hazards || []).filter((h) => !(h.key in SIM_READING));
  const plain = { closure: "A government order shuts businesses here for the day" };
  host.innerHTML = extras.map((h) => h.binary
    ? `<label class="floodrow"><input type="checkbox" data-extra="${h.key}" /> ${plain[h.key] || h.label}</label>`
    : `<div class="slider">${icon("sliders-horizontal")}
        <label for="x-${h.key}">${h.label}</label>
        <input type="range" id="x-${h.key}" data-extra="${h.key}" min="0" max="${h.max}" step="1" value="0" />
        <output class="num" id="xv-${h.key}">0</output></div>`).join("");
  host.querySelectorAll("[data-extra]").forEach((input) =>
    input.addEventListener("input", () => {
      const value = input.type === "checkbox" ? (input.checked ? 1 : 0) : +input.value;
      state.simExtra[input.dataset.extra] = value;
      const out = el(`xv-${input.dataset.extra}`);
      if (out) out.textContent = input.value;
      setSim({});
    }));
}

/* ---------- floating circle records ---------- */
/* The portfolio tier's monthly price per stall at the centres in a circle, as each is charged:
   one price, or the lowest to the highest. */
function circlePrice(scn) {
  const offered = scn.affected.filter((a) => a.offered);
  if (!scn.affected.length) return "–";
  if (!offered.length) return "Not offered here";
  const monthly = offered.map((a) => a.yearly_baseline_sgd / 12);
  const [low, high] = [Math.min(...monthly), Math.max(...monthly)];
  return high - low < 0.005 ? `${SGD(low)} a month` : `${SGD(low)} to ${SGD(high)} a month`;
}
function floatCardHtml(circle) {
  const scn = circle.scn, active = circle.id === state.activeId;
  const head = `<div class="chead">
    <button class="ctoggle" type="button" data-act="toggle" aria-expanded="${!!circle.expanded}">
      <span class="tag">C${circle.id}</span>
      <span class="pay">${scn.assessment.loss_percent.toFixed(0)}% · ${SGD0(scn.totals.payout_today_sgd)}/day</span>
      ${dayChip(scn.assessment.loss_percent)}
      <span class="tgl">${icon(circle.expanded ? "chevron-down" : "chevron-right")}</span></button>
    <button class="x" type="button" data-act="remove" aria-label="Remove circle ${circle.id}">${icon("x")}</button></div>`;
  const body = circle.expanded ? `<div class="cbody" data-act="edit">
    ${circle.place ? `<p class="where">${circle.place}</p>` : ""}
    <div class="kv"><span class="k" style="white-space:nowrap">Priced as</span><span class="v">${productLabel(circle.product)}</span></div>
    <div class="kv"><span class="k">Loss score today</span><span class="v">${scn.assessment.loss_percent.toFixed(0)}% ${dayChip(scn.assessment.loss_percent)}</span></div>
    <div class="kv"><span class="k">Payout per stall today</span><span class="v">${SGD(scn.assessment.payout_sgd)}</span></div>
    <div class="kv"><span class="k">${tierLabel(state.tier)} price per stall</span><span class="v">${circlePrice(scn)}</span></div>
    <div class="kv"><span class="k">Centres hit · stalls covered</span><span class="v">${scn.totals.centres} · ${scn.totals.stalls.toLocaleString("en-SG")}</span></div>
    <div class="kv"><span class="k">Weekly premium, now → if more common</span><span class="v">${SGD(scn.totals.weekly_premium_baseline_sgd)} → <span class="delta-up">${SGD(scn.totals.weekly_premium_stressed_sgd)}</span></span></div>
    <p class="hintline">${active ? "editing: the sliders shape this circle" : "click to edit this circle's readings"}</p>
  </div>` : "";
  return head + body;
}
function renderFloats() {
  const layer = el("float-layer");
  const priced = state.mode === "sim" ? state.circles.filter((c) => c.scn) : [];
  layer.hidden = priced.length === 0;
  const seen = new Set();
  for (const circle of priced) {
    seen.add(String(circle.id));
    let card = layer.querySelector(`[data-id="${circle.id}"]`);
    if (!card) {
      card = document.createElement("div");
      card.className = "ccard";
      card.dataset.id = circle.id;
      card.addEventListener("click", (event) => {
        const act = event.target.closest("[data-act]")?.dataset.act;
        if (act === "toggle") { circle.expanded = !circle.expanded; renderFloats(); }
        if (act === "edit") selectCircle(circle.id);
        if (act === "remove") removeCircleById(circle.id);
      });
      layer.appendChild(card);
    }
    card.classList.toggle("active", circle.id === state.activeId);
    card.innerHTML = floatCardHtml(circle);
  }
  for (const card of [...layer.children]) if (!seen.has(card.dataset.id)) card.remove();
}
function currentViewport() {
  const viewports = deckgl && deckgl.getViewports ? deckgl.getViewports() : null;
  if (viewports && viewports.length) return viewports[0];
  return new deck.WebMercatorViewport({ ...lastView, width: window.innerWidth, height: window.innerHeight });
}
function positionFloats() {
  const layer = el("float-layer");
  if (!layer.hidden && deckgl) {
    const viewport = currentViewport();
    // A card above a circle near the top edge stays below the top bar.
    const topbarHeight = el("topbar").offsetHeight;
    for (const card of layer.children) {
      const circle = state.circles.find((c) => String(c.id) === card.dataset.id);
      if (!circle) continue;
      const [x, yEdge] = viewport.project([circle.lng, circle.lat + circle.radiusKm / 111]);
      const visible = x > -200 && x < window.innerWidth + 200 && yEdge > -100 && yEdge < window.innerHeight + 200;
      card.style.display = visible ? "" : "none";
      card.style.left = `${x}px`;
      card.style.top = `${Math.max(yEdge - 8, topbarHeight + card.offsetHeight + 8)}px`;
    }
  }
  requestAnimationFrame(positionFloats);
}

/* ---------- detail panel ---------- */
function select(type, value) {
  if (state.drawing || (state.shopDraft && !state.shopDraft.place)) return;
  state.selected = { type, value };
  setFolded(el("portfolio"), true);
  renderDetail();
  openPanel(el("detail"));
}
function stackBar(parts) {
  const total = Object.values(parts).reduce((a, b) => a + b, 0) || 1;
  let bars = "", legend = "";
  for (const [key, days] of Object.entries(parts)) {
    if (!days) continue;
    bars += `<div style="width:${(days / total * 100)}%;background:${CSS_BY_HAZARD[key]}"></div>`;
    legend += `<span><i style="background:${CSS_BY_HAZARD[key]}"></i>${QUOTES.hazard_labels[key] || key} ${days.toFixed(2)} d/yr</span>`;
  }
  return `<div class="stackbar">${bars}</div><div class="stacklegend">${legend}</div>`;
}
function hazeYearChart() {
  const years = STATIC.psi_yearly;
  const max = Math.max(...years.map((y) => y.days_unhealthy), 1);
  const W = 320, H = 96, bw = W / years.length;
  let bars = "";
  years.forEach((y, i) => {
    const h = Math.max(y.days_unhealthy / max * (H - 30), 1.5);
    const hot = y.year === years[years.length - 1].year;
    bars += `<rect x="${(i * bw + 3).toFixed(1)}" y="${(H - 16 - h).toFixed(1)}" width="${(bw - 6).toFixed(1)}" height="${h.toFixed(1)}" rx="2.5" style="fill:var(--haze)" opacity="${hot ? 1 : 0.4}"/>`;
    if (y.days_unhealthy > 0) bars += `<text x="${(i * bw + bw / 2).toFixed(1)}" y="${(H - 20 - h).toFixed(1)}" font-size="9.5" style="fill:var(--ink-2)" text-anchor="middle">${y.days_unhealthy}</text>`;
    if (i % 2 === 0 || hot) bars += `<text x="${(i * bw + bw / 2).toFixed(1)}" y="${H - 4}" font-size="9" style="fill:var(--muted)" text-anchor="middle">${String(y.year).slice(2)}</text>`;
  });
  return `<div class="minichart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Unhealthy haze days per year">
    <line x1="0" y1="${H - 16}" x2="${W}" y2="${H - 16}" style="stroke:var(--line)" stroke-width="1"/>${bars}</svg>
    <p class="note">Days per year with 24-hour PSI above 100. PSI is NEA's 0 to 500 air quality index; above 100 the air is officially unhealthy. NEA, Mar 2016 to Nov 2026.</p></div>`;
}
// The quote's own build-up (expected payouts, reinsurance, management, distribution, profit,
// GST), in the server's order: no step is worked out here.
function premiumBuildup(tier) {
  const rows = tier.build_up.map((step, at) => {
    const label = step.key === "expected_payouts"
      ? `${step.label} · ${tier.expected_paid_days.toFixed(2)} paid days × ${SGD0(tier.daily_payout_sgd)}` : step.label;
    return `<div class="row"><span>${at ? "+ " : ""}${label}</span><span>${SGD(step.amount_sgd)}</span></div>`;
  }).join("");
  return `<div class="buildup">${rows}
    <div class="row total"><span>Yearly premium → ${SGD(tier.weekly_premium_sgd)}/week, ${dayPrice(tier)}</span><span>${SGD(tier.yearly_premium_sgd)}</span></div>
  </div>`;
}
function dayDetail(index, tier) {
  const loss = currentLossFraction(index);
  const centre = STATIC.hawker_centres[index];
  const containing = state.mode === "sim" && state.circles.length
    ? circlesAt(centre).filter((c) => c.scn) : [];
  if (state.mode === "sim" && state.circles.length && !containing.length)
    return `<div class="sec"><p class="cap">On the simulated day</p>
      <p class="note">Outside every drawn circle: the scenario readings do not apply here.</p></div>`;
  const best = containing.length
    ? containing.reduce((a, b) => (b.scn.assessment.loss_percent > a.scn.assessment.loss_percent ? b : a))
    : null;
  const readings = state.mode === "live"
    ? state.live?.hawker_losses?.[index]?.readings
    : best ? best.readings
    : state.replay ? state.replay.hawker_losses[index].readings
    : { haze: state.sim.psi, rain: state.sim.rain, heat: state.sim.heat };
  if (state.mode === "history" || !readings) return "";
  const label = state.mode === "live" ? `Live today (${state.live?.date ?? ""})`
    : !best && state.replay ? `NEA readings here on ${state.replay.date}` : "On the simulated day";
  const stressed = best ? best.scn.centres?.[centre.name] ?? null : null;
  // Inside a circle the payout is the one the API priced for that circle's product and tier.
  const paid = best
    ? { tier: tierLabel(state.tier), perStall: best.scn.assessment.payout_sgd }
    : { tier: tier.label, perStall: loss * tier.daily_payout_sgd };
  return `<div class="sec"><p class="cap">${label}${best ? ` · circle ${best.id}` : ""}</p>
    <div class="kv"><span class="k">Readings here (PSI / mm / h ≥32)</span><span class="v">${Math.round(readings.haze)} / ${Math.round(readings.rain)} / ${readings.heat}</span></div>
    ${best ? `<div class="kv"><span class="k">Priced as</span><span class="v">${productLabel(best.product)}</span></div>` : ""}
    <div class="kv"><span class="k">Loss score (share of a normal day's sales)</span><span class="v">${(loss * 100).toFixed(0)}% ${dayChip(loss * 100)}</span></div>
    <div class="kv"><span class="k">Payout per stall at ${paid.tier}</span><span class="v" id="day-payout">${SGD(paid.perStall)}</span></div>
    <div class="kv"><span class="k">Whole centre (${centre.food_stalls} stalls)</span><span class="v">${SGD0(paid.perStall * centre.food_stalls)}</span></div>
    ${stressed ? `<div class="kv"><span class="k">Weekly premium if this grows ${state.extraDays} d/yr more frequent</span>
      <span class="v">${stressed.offered === false ? `${paid.tier} not offered here` : `${SGD(stressed.weekly_baseline_sgd)} → <span class="delta-up">${SGD(stressed.weekly_stressed_sgd)}</span>`}</span></div>` : ""}
    <p class="note">Paid automatically on NEA readings - no claim form, no loss adjuster.</p></div>`;
}
function rentSection(centre, quote) {
  const rent = rentOf(centre);
  if (!rent) return "";
  const shares = offeredTiers(quote).map((t) => `${t.label} ${rentShare(t.daily_payout_sgd, rent.rent_per_day_sgd)}`).join(" · ");
  const source = rent.estimated
    ? `No NEA bid on record for this centre, so it borrows the median of all centres (${SGD0(RENT.all_centre_median_sgd)} a month).`
    : `Median of ${rent.bids} winning NEA bid${rent.bids === 1 ? "" : "s"} for a cooked-food stall, ${rent.first_month} to ${rent.last_month}.`;
  return `<div class="sec"><p class="cap">Stall rent · ${rent.rent_class_label}</p>
    <div class="kv"><span class="k">Monthly rent</span><span class="v">${SGD0(rent.median_bid_sgd)}</span></div>
    <div class="kv"><span class="k">Per trading day (${RENT.trading_days_per_month} a month)</span><span class="v">${SGD(rent.rent_per_day_sgd)}</span></div>
    <div class="kv"><span class="k">A full bad day pays</span><span class="v">${shares}</span></div>
    <p class="note">${source} Rent is shown for information. It sets neither the premium nor the tier a stall is offered: that comes from the stall's own daily sales.</p></div>`;
}

/** Fill the card's SMS with the real welcome text, so the atlas sells what is texted. */
async function showCoverText(tier) {
  try {
    const cover = await api.coverText(tier);
    const bubble = el("atlas-cover-sms");
    if (bubble) bubble.textContent = `"${cover.body}"`;
  } catch (error) {
    const bubble = el("atlas-cover-sms");
    if (bubble) bubble.textContent = `Could not load the SMS: ${error.message}`;
  }
}

function renderDetail() {
  const panel = el("detail"), body = el("detail-body"), kind = el("detail-kind");
  if (!state.selected) { panel.hidden = true; return; }
  panel.hidden = false;
  const { type, value } = state.selected;

  if (type === "sme") {
    const centre = STATIC.hawker_centres[value];
    const quote = centreQuote(centre), v = verdict(quote), rec = v.tier;
    const parts = centreParts(centre);
    const nearHeat = nearest(STATIC.wbgt_stations, centre), nearRain = nearest(STATIC.rain_stations, centre);
    const basisFar = Math.min(nearHeat.km, nearRain.km) > 3;
    kind.textContent = "SME · hawker centre";
    body.innerHTML = `
      <p class="title">${centre.name}</p>
      <p class="subtitle">${centre.address} · haze zone: ${centre.region}${centre.built ? ` · est. ${centre.built}` : ""}</p>
      <div class="chips">
        <span class="chip">${centre.food_stalls} cooked-food stalls (NEA)</span>
        <span class="chip ${basisFar ? "warning" : "good"}">trigger stations ${nearHeat.km.toFixed(1)} km (heat) · ${nearRain.km.toFixed(1)} km (rain)</span>
        ${rentOf(centre) ? `<span class="chip">${rentChip(rentOf(centre))}</span>` : ""}
      </div>
      <div class="verdict"><span class="chip ${v.cls}">${v.word}</span>
        <div class="t1">${rec.label} at ${SGD(monthlyPrice(rec))} a month (${SGD(rec.weekly_premium_sgd)} a week)${rec.best_value ? ` <span class="chip good">Best value</span>` : ""}</div>
        <div class="t2">Pays up to ${SGD0(rec.daily_payout_sgd)} a day when haze, heavy rain, extreme heat or a flood alert hits this area. ${coverLine(rec)} ${centsBack(rec)} Paid on NEA readings, usually the same day, up to ${SGD0(rec.max_payout_per_year_sgd)} a year. <b>If readings stay below the trigger levels, nothing is paid, even if sales were down.</b> No payout in the first ${WAITING_PERIOD_DAYS} days of cover. Injury, medical costs and damaged goods are not covered. ${quote.suggestion}${v.cls === "serious" ? ` ${v.detail}` : ""}${bestValueLine(quote, rec.tier) ? ` ${bestValueLine(quote, rec.tier)}` : ""}</div></div>
      ${rec.proof ? `<div class="sec"><p class="cap">What ${rec.label} would have paid here</p>
        ${proofLines(rec, "hawker").map((line) => `<p class="note">${line}</p>`).join("")}
        ${rec.haze_bonus ? `<p class="note">Severe haze payout add-on: ${hazeBonusPitch(rec)}${rec.haze_bonus.on_sale_now ? "" : " It can be added from November to April."}</p>` : ""}</div>` : ""}
      <div class="sec"><p class="cap">The policy in one SMS</p>
        <p class="sms" id="atlas-cover-sms">Loading the SMS…</p>
        <p class="note">The welcome text a ${rec.label} customer gets, word for word. ${SGD(rec.weekly_premium_sgd)}/wk.</p></div>
      <div class="sec"><p class="cap">Expected loss · ${quote.expected_loss_days.toFixed(2)} full-loss days a year</p>
        ${stackBar(parts)}
        <p class="note">Day-weighted severity of the NEA readings at the stations nearest this centre (haze: the ${centre.region} zone), read as a payout reads them, × 365.25 × peril weight × product factor (cooked food keeps nothing overnight).</p></div>
      <div class="sec"><p class="cap">All tiers · weekly premium per stall</p>
        <table class="tiers"><tr><th>Tier</th><th>Payout/day</th><th>Cap</th><th>Max/yr</th><th>Weekly</th></tr>
        ${quote.tiers.map((t) => `<tr class="${t.tier === rec.tier ? "rec" : ""}"><td>${t.label}</td><td>${SGD0(t.daily_payout_sgd)}</td><td>${tierDays(t)} d</td><td>${SGD0(t.max_payout_per_year_sgd)}</td><td>${t.offered === false ? "Not offered here" : SGD(t.weekly_premium_sgd)}</td></tr>`).join("")}
        </table>
        ${notOfferedLine(quote) ? `<p class="note">${notOfferedLine(quote)}</p>` : ""}
        ${offeredTiers(quote).map((t) => `<p class="note">${t.label}${t.best_value ? " (best value)" : ""}: ${SGD(monthlyPrice(t))} a month, ${SGD(t.weekly_premium_sgd)} a week, ${dayPrice(t)}. ${fullLossLine(t, PARTIAL_DAYS[t.tier])} ${lockdownLine(t)}${t.tier === rec.tier ? ` ${lockdownExample(t)}` : ""} ${coverLine(t)} ${centsBack(t)}</p>`).join("")}</div>
      ${rentSection(centre, quote)}
      <div class="sec"><p class="cap">Premium build-up · ${rec.label}</p>${premiumBuildup(rec)}
        <p class="note">Insurable interest (Insurance Act 1966 s151): the payout is a pre-estimate of a stall's lost daily takings, so this is insurance, not a wager.</p></div>
      ${dayDetail(value, rec)}`;
    showCoverText(rec.tier);
  } else if (type === "heat") {
    const s = value;
    const live = state.live?.heat?.find((x) => x.id === s.id);
    kind.textContent = "Hazard · WBGT station";
    body.innerHTML = `<p class="title">${s.name}</p>
      <p class="subtitle">NEA station ${s.id} · ${s.days} days of record since 16 Jan 2025</p>
      ${live ? `<div class="kv"><span class="k">Latest WBGT (live)</span><span class="v">${live.latest.toFixed(1)} °C</span></div>
      <div class="kv"><span class="k">Work hours ≥32 °C today</span><span class="v">${live.hours_ge_32_today.toFixed(2)} h</span></div>` : ""}
      <div class="kv"><span class="k">Days reaching 32 °C (MOM rest-break level)</span><span class="v">${(s.share_days_ge_32 * 100).toFixed(0)}% of ${s.days} days</span></div>
      <div class="kv"><span class="k">Hours at ≥32 °C over the record</span><span class="v">${s.hours_ge_32.toFixed(0)} h</span></div>
      <div class="kv"><span class="k">Hottest reading</span><span class="v">${s.max_wbgt.toFixed(1)} °C</span></div>
      <p class="note">Heat is frequent but short: when WBGT reaches 32 °C it usually stays under an hour, so the trigger uses a duration rule (2 h+), not a single touch.</p>`;
  } else if (type === "rain") {
    const s = value;
    const live = state.live?.rain?.find((x) => x.id === s.id);
    kind.textContent = "Hazard · rain gauge";
    body.innerHTML = `<p class="title">${s.name}</p>
      <p class="subtitle">Rain gauge ${s.id}, an NEA roadside rain meter · ${s.days} days of record over 10 years</p>
      ${live ? `<div class="kv"><span class="k">Wettest work hour today (live)</span><span class="v">${live.wettest_work_hour_today.toFixed(1)} mm</span></div>` : ""}
      <div class="kv"><span class="k">Days with 20 mm in one hour</span><span class="v">${(s.share_days_ge_20 * 100).toFixed(1)}% of ${s.days} days</span></div>
      <div class="kv"><span class="k">Days with 30 mm in one hour</span><span class="v">${(s.share_days_ge_30 * 100).toFixed(1)}% of ${s.days} days</span></div>
      <div class="kv"><span class="k">Average wet work-hours per day</span><span class="v">${s.wet_hours_per_day.toFixed(2)} h</span></div>
      <p class="note">The trigger is 20 mm of rain falling within one working hour (7am to 7pm): a downpour hard enough to empty a hawker centre. The percentages count how many of this gauge's recorded days had such an hour. Rain is local, so the policy reads the 3 rain gauges nearest each business and takes the middle reading of those that reported, not an island average.</p>`;
  } else if (type === "flood") {
    kind.textContent = "Hazard · flood hotspot";
    body.innerHTML = `<p class="title">${value.name}</p>
      <p class="subtitle">PUB flash-flood hotspot (list of 2 Feb 2026)</p>
      <p class="note">Flash floods in Singapore are localised and usually subside within an hour; flood-prone area is down to 23.3 ha (PUB, 2025) from ~3,200 ha in the 1970s. PUB records 2017-2023 show ~7 flash-flood days a year island-wide (Li et al. 2024). The live trigger is PUB's Flood Alerts feed, shown in Live mode.</p>`;
  } else if (type === "region") {
    const area = value, region = area.psi_region;
    const quote = regionQuote(region), parts = QUOTES.loss_day_parts[region];
    const tier2 = quote.tiers[1] ?? quote.tiers[0];
    kind.textContent = "Region profile";
    body.innerHTML = `<p class="title">${area.name}</p>
      <p class="subtitle">In URA's ${area.ura_region} planning region. NEA reports haze in five zones (north, south, east, west, central); this area's prices come from the <b>${region}</b> zone's history.</p>
      <div class="sec"><p class="cap">Expected full-loss days (cooked food)</p>
        ${stackBar(parts)}
        <p class="note">${quote.expected_loss_days.toFixed(2)} days/yr → ${tier2.label} (${SGD0(tier2.daily_payout_sgd)}/day) prices at ${SGD(tier2.weekly_premium_sgd)}/week here.</p></div>
      <div class="sec"><p class="cap">Unhealthy haze days per year</p>${hazeYearChart()}<p class="note">Haze is the catastrophe peril: most years have a handful of bad days, then one year (like 2026, with 39) hits the whole island for weeks, so every policy pays at once. That is what the yearly caps and the reinsurance for haze years are for.</p></div>`;
  }
}

/* ---------- portfolio ---------- */
function setPortfolioPayout(label, amount) {
  el("p-pay-label").textContent = label;
  el("p-pay").textContent = amount;
  el("p-pay-head").textContent = amount;
}
function renderPortfolio() {
  const box = el("portfolio");
  box.hidden = false;
  const tierKey = state.tier;
  let stalls = 0, premiumPool = 0, expectedPayouts = 0, dayPayout = 0;
  STATIC.hawker_centres.forEach((centre, index) => {
    const tier = centreQuote(centre).tiers.find((t) => t.tier === tierKey);
    stalls += centre.food_stalls;
    premiumPool += tier.yearly_premium_sgd * centre.food_stalls;
    expectedPayouts += tier.expected_paid_days * tier.daily_payout_sgd * centre.food_stalls;
    dayPayout += currentLossFraction(index) * tier.daily_payout_sgd * centre.food_stalls;
  });
  if (state.mode === "sim" && state.circles.length) {
    const per = {};
    for (const circle of state.circles) {
      if (!circle.scn) continue;
      const pay = circle.scn.assessment.payout_sgd;
      for (const a of circle.scn.affected) {
        if (!per[a.name] || pay > per[a.name].pay)
          per[a.name] = { stalls: a.stalls, pay, base: a.weekly_baseline_sgd, stressed: a.weekly_stressed_sgd };
      }
    }
    const rows = Object.values(per);
    const circleStalls = rows.reduce((sum, r) => sum + r.stalls, 0);
    el("p-n").textContent = `${circleStalls.toLocaleString("en-SG")} in ${state.circles.length} circle${state.circles.length > 1 ? "s" : ""}`;
    el("p-prem").textContent = `${SGD0(rows.reduce((sum, r) => sum + r.stalls * r.base, 0) * 52)}/yr`;
    setPortfolioPayout("Payout in the circles today", SGD0(rows.reduce((sum, r) => sum + r.stalls * r.pay, 0)));
    el("p-note").textContent = `Overlapping centres counted once, at their worst circle. Stressed pool `
      + `${SGD0(rows.reduce((sum, r) => sum + r.stalls * r.stressed, 0) * 52)}/yr.`;
    return;
  }
  el("p-n").textContent = stalls.toLocaleString("en-SG");
  el("p-prem").textContent = SGD0(premiumPool);
  if (state.mode === "history") {
    setPortfolioPayout("Expected payouts / year", SGD0(expectedPayouts));
    el("p-note").textContent = "Illustrative accumulation: every cooked-food stall in all "
      + `${STATIC.hawker_centres.length} centres buys one policy. Not a sales forecast.`;
  } else {
    setPortfolioPayout(state.mode === "live" ? "Payout for today so far" : "Payout on this day", SGD0(dayPayout));
    el("p-note").textContent = dayPayout > 0
      ? `This day consumes ${(dayPayout / premiumPool * 100).toFixed(1)}% of the annual premium pool. `
        + "The Oct 2026 haze ran 23 unhealthy days - why payable days are capped and part of each premium buys reinsurance for haze years."
      : "No trigger level is reached on these readings, so nothing is paid.";
  }
}

/* ---------- simulator ---------- */
let assessTimer = null, assessSeq = 0;
function refreshSimAssessment() {
  clearTimeout(assessTimer);
  assessTimer = setTimeout(async () => {
    const seq = ++assessSeq;
    try {
      const assessment = await api.assess(simReadings());
      if (seq !== assessSeq) return;
      state.simAssessment = assessment;
      redraw(); renderPortfolio(); renderDetail();
    } catch (error) {
      console.error(error);
    }
  }, 150);
}
function setSim(partial) {
  // Moving a slider turns a replayed day back into one what-if day for every centre.
  if (state.replay) {
    el("day-note").textContent = `The sliders now set one what-if day for every centre. `
      + `Pick a date to replay a real day again.`;
    el("s-date").value = "";
  }
  state.replay = null;
  Object.assign(state.sim, partial);
  el("s-psi").value = state.sim.psi; el("s-rain").value = state.sim.rain; el("s-heat").value = state.sim.heat;
  el("s-flood").checked = state.sim.flood;
  el("v-psi").textContent = state.sim.psi;
  el("psi-band").textContent = state.sim.psi > 0 ? psiBand(state.sim.psi) : "";
  el("v-rain").textContent = `${state.sim.rain} mm`;
  el("v-heat").textContent = `${state.sim.heat} h`;
  applyControlChange();
  redraw();
}

/* ---------- tell us about your shop ---------- */
const EXAMPLE_HAWKER_GOODS = ["chicken rice", "duck rice", "wanton noodles", "prawn noodles", "fresh fish", "vegetables"];
const EXAMPLE_SHOPS = ["provision shop selling drinks and snacks", "phone accessories shop", "clothing shop"];
const EXAMPLE_SHOP_STREETS = ["Ang Mo Kio Ave 3", "Bedok North Street 3", "Yishun Ring Road", "Hougang Ave 8", "Jurong West Street 42"];
const EXAMPLE_DELIVERY = ["foodpanda", "GrabFood"];
const EXAMPLE_DELIVERY_AREAS = ["Tampines", "Woodlands", "Punggol", "Sengkang", "Bukit Batok"];
const examplePick = (list) => list[Math.floor(Math.random() * list.length)];

/* The everyday name of a centre: "Smith Street Blk 335 (Chinatown Complex Market)" is Chinatown Complex Market. */
function everydayCentreName(name) {
  const [address, bracket = ""] = name.split(" (");
  return [address, ...bracket.replace(/\)$/, "").split("/")].find((part) => /(Market|Food Centre)$/.test(part)) || null;
}
function exampleShopText() {
  const centres = STATIC.hawker_centres.map((c) => everydayCentreName(c.name)).filter(Boolean);
  const block = 100 + Math.floor(Math.random() * 800);
  return examplePick([
    () => `I sell ${examplePick(EXAMPLE_HAWKER_GOODS)} at ${examplePick(centres)}`,
    () => `I run a ${examplePick(EXAMPLE_SHOPS)} at Blk ${block} ${examplePick(EXAMPLE_SHOP_STREETS)}`,
    () => `I deliver cooked food for ${examplePick(EXAMPLE_DELIVERY)} around ${examplePick(EXAMPLE_DELIVERY_AREAS)}`,
  ])();
}
function clearShopText() {
  el("kyc-text").value = "";
  el("kyc-photo").value = "";
  shopStatus("");
}

let stripSeq = 0;
function shopCircle() { return state.circles.find((c) => c.id === state.shopId) || null; }
function shopStatus(text) {
  el("kyc-status").hidden = !text;
  el("kyc-status-text").textContent = text;
}
function hideShopStrip() {
  stripSeq++;  // drops a strip still being priced, so it cannot reappear beside a newer reading
  el("kyc-strip").hidden = true;
  el("kyc-strip").replaceChildren();
}
function forgetShop() {
  state.shopId = null; state.shopDraft = null;
  el("kyc-confirm").hidden = true;
  hideShopStrip();
  shopStatus("");
}
function placeName(place) {
  return place.area && place.area !== place.name ? `${place.name}, ${place.area}` : place.name;
}
function readPhoto(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ media_type: file.type, data: reader.result.split(",")[1] });
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
async function readShop() {
  const text = el("kyc-text").value.trim(), file = el("kyc-photo").files[0];
  if (!text && !file) { shopStatus("Describe your shop, or attach a photo of it."); return; }
  if (file && file.size > PHOTO_MAX_BYTES) { shopStatus("That photo is over 5 MB. Pick a smaller one."); return; }
  el("kyc-submit").disabled = true;
  shopStatus("Reading your description…");
  try {
    const answer = await api.kyc({ text, photo: file ? await readPhoto(file) : null });
    hideShopStrip();
    // The answer's fields go onto the circle as they are, so a new one needs no change here.
    state.shopDraft = { product: answer.product, place: answer.place, summary: answer.summary };
    showShopDraft();
    if (file && answer.source === "keywords")
      shopStatus(`${el("kyc-status-text").textContent} The photo was not read: no assistant key is set, so only your words were matched.`.trim());
  } catch (error) {
    console.error(error);
    shopStatus("Could not read that just now. Try again, or draw a circle by hand below.");
  } finally {
    el("kyc-submit").disabled = false;
  }
}
function showShopDraft() {
  const draft = state.shopDraft;
  el("kyc-confirm").hidden = false;
  el("kyc-confirm-btn").hidden = false;
  el("kyc-product").value = draft.product ?? "";
  el("kyc-place").textContent = draft.place ? placeName(draft.place) : "Not found";
  el("kyc-confirm-btn").disabled = !draft.place || !draft.product;
  shopStatus([
    draft.product ? "" : "We could not tell what you sell. Choose it from the list.",
    draft.place ? "" : "We could not find that place. Click the map where your shop is instead.",
  ].filter(Boolean).join(" "));
}
/* The middle of the map still showing on a phone or tablet: above the panels when they sit under
   the map, else left of the right-hand panels. */
function middleOfVisibleMap() {
  if (PANELS_UNDER_MAP.matches) {
    const top = el("topbar").getBoundingClientRect().bottom;
    const bottom = document.querySelector(".dock").getBoundingClientRect().top;
    return [innerWidth / 2, (top + bottom) / 2];
  }
  return [document.querySelector(".dock-right").getBoundingClientRect().left / 2, innerHeight / 2];
}
/* The map centre that puts `point` at the screen position `pixel`. */
function centreWithPointAt(view, point, pixel) {
  return new deck.WebMercatorViewport({ ...view, width: innerWidth, height: innerHeight })
    .panByPosition([point.lng, point.lat], pixel);
}
function focusOn(point) {
  if (state.orbit) toggleOrbit(false);
  const view = { ...lastView, longitude: point.lng, latitude: point.lat, zoom: Math.max(lastView.zoom, SHOP_ZOOM) };
  lastView = PANELS_CROWD_MAP.matches ? { ...view, ...centreWithPointAt(view, point, middleOfVisibleMap()) } : view;
  state.zoom = lastView.zoom;
  deckgl.setProps({
    initialViewState: {
      ...lastView,
      transitionDuration: REDUCED_MOTION ? 0 : 1400,
      transitionInterpolator: new deck.FlyToInterpolator(),
    },
  });
}
function placeShop() {
  const { product, place } = state.shopDraft;
  if (state.drawing) stopDrawing();
  state.circles = state.circles.filter((c) => c.id !== state.shopId);
  const circle = Object.assign(newCircle(place.lat, place.lng, SHOP_RADIUS_KM), { product, place: placeName(place) });
  el("kyc-place").textContent = circle.place;
  state.shopDraft = null; state.shopId = circle.id;
  commitCircle(circle);
  selectCircle(circle.id);
  el("kyc-confirm-btn").hidden = true;
  shopStatus("");
  focusOn(circle);
  renderShopStrip();
}
function setShopProduct(product) {
  const circle = shopCircle();
  if (state.shopDraft) { state.shopDraft.product = product; showShopDraft(); return; }
  if (!circle) return;
  circle.product = product;
  requestScenario(circle);
  renderShopStrip();
}
async function renderShopStrip() {
  const circle = shopCircle(), strip = el("kyc-strip");
  if (!circle || state.shopDraft) { hideShopStrip(); return; }
  const seq = ++stripSeq;
  try {
    const days = await Promise.all(BAD_DAYS.map((day) => api.scenario(scenarioBody(circle, readingsOf(day.sim, {})))));
    if (seq !== stripSeq || circle !== shopCircle()) return;
    strip.hidden = false;
    const centres = days[0].totals.centres;
    strip.innerHTML = `<p class="cap">What a bad day costs this shop</p>
      <p class="note">${productLabel(circle.product)} · ${circle.place} · ${centres} hawker centre${centres === 1 ? "" : "s"} in the circle · payout per stall at ${tierLabel(state.tier)}, as priced by the API. Click a day to apply it.</p>
      <div class="days">${BAD_DAYS.map((day, i) => `<button class="day" type="button" data-day="${day.key}" data-hazard="${day.hazard}">
        ${icon(HAZARD_ICON[day.hazard])}<span>${day.label}</span><b>${SGD(days[i].assessment.payout_sgd)}</b></button>`).join("")}</div>`;
    markBadDay();
  } catch (error) { console.error(error); }
}
function markBadDay() {
  const readings = JSON.stringify(shopCircle()?.readings);
  for (const button of el("kyc-strip").querySelectorAll(".day")) {
    const day = BAD_DAYS.find((d) => d.key === button.dataset.day);
    button.setAttribute("aria-pressed", JSON.stringify(readingsOf(day.sim, {})) === readings);
  }
}
function applyBadDay(key) {
  const circle = shopCircle(), day = BAD_DAYS.find((d) => d.key === key);
  if (!circle || !day) return;
  circle.readings = readingsOf(day.sim, {});
  selectCircle(circle.id);
  setSim({ ...day.sim });
  markBadDay();
}

/* ---------- live mode ---------- */
async function pollLive() {
  const label = el("live-state");
  try {
    const snapshot = await api.live();
    state.live = snapshot;
    if (!snapshot.available) {
      label.textContent = SafeUI.LIVE_UNAVAILABLE;
      label.classList.add("err");
    } else {
      const at = snapshot.fetched_at ? snapshot.fetched_at.slice(11, 16) : "";
      const down = Object.entries(snapshot.feeds).filter(([, err]) => err).map(([name]) => name);
      label.textContent = `LIVE · NEA readings as of ${at} SGT` + (down.length ? ` · ${down.join(", ")} unavailable` : "");
      label.classList.toggle("err", down.length > 0);
    }
    const alerts = snapshot.flood_alerts || [];
    el("flood-banner").hidden = alerts.length === 0;
    if (alerts.length) {
      state.layers.flood = true; el("ly-flood").checked = true;
      el("flood-text").textContent = `PUB flood alert${alerts.length > 1 ? "s" : ""} active: `
        + alerts.slice(0, 3).map((a) => Object.values(a).filter((v) => typeof v === "string").join(" ")).join(" · ");
    }
    redraw(); renderPortfolio(); renderDetail();
  } catch (error) {
    label.textContent = "LIVE · feed error, retrying";
    label.classList.add("err");
    console.error(error);
  }
}
function setMode(mode) {
  state.mode = mode;
  for (const name of ["history", "sim", "live"]) el(`mode-${name}`).setAttribute("aria-pressed", name === mode);
  el("sim").hidden = mode !== "sim";
  el("live-state").hidden = mode !== "live";
  if (mode !== "live") el("flood-banner").hidden = true;
  clearInterval(state.livePoll); state.livePoll = null;
  if (mode === "live") {
    el("live-state").textContent = "LIVE · fetching today's NEA readings…";
    el("live-state").classList.remove("err");
    pollLive();
    state.livePoll = setInterval(pollLive, LIVE_POLL_MS);
  }
  if (mode === "sim" && !state.simAssessment) refreshSimAssessment();
  renderLegend(); renderFloats(); redraw(); renderPortfolio(); renderDetail();
}
/* ---------- cameras ---------- */
const CAMERAS = {
  plan: { pitch: 0, bearing: 0, zoom: 10.9 },
  bird: { pitch: 52, bearing: -12, zoom: 10.6 },
  city: { pitch: 68, bearing: 35, zoom: 14.4 },
};
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function flyTo(name) {
  const resumeOrbit = state.orbit;
  if (resumeOrbit) toggleOrbit(false);
  state.camera = name;
  for (const cam of Object.keys(CAMERAS)) el(`cam-${cam}`).setAttribute("aria-pressed", cam === name);
  const target = { ...lastView, ...CAMERAS[name] };
  if (name === "city") {
    // Land on the selected hawker centre, or the densest one, so the city view opens on a story.
    const centre = state.selected?.type === "sme"
      ? STATIC.hawker_centres[state.selected.value]
      : STATIC.hawker_centres.reduce((a, b) => (b.food_stalls > a.food_stalls ? b : a));
    target.longitude = centre.lng; target.latitude = centre.lat;
  }
  lastView = target;
  state.zoom = target.zoom;
  deckgl.setProps({
    initialViewState: {
      ...target,
      transitionDuration: REDUCED_MOTION ? 0 : 1400,
      transitionInterpolator: new deck.FlyToInterpolator(),
    },
  });
  if (resumeOrbit) setTimeout(() => toggleOrbit(true), REDUCED_MOTION ? 50 : 1500);
  redraw();
}
function orbitStep() {
  if (!state.orbit) return;
  lastView = { ...lastView, bearing: (lastView.bearing + 0.16) % 360 };
  deckgl.setProps({ initialViewState: { ...lastView, transitionDuration: 0 } });
  requestAnimationFrame(orbitStep);
}
function toggleOrbit(force) {
  state.orbit = force ?? !state.orbit;
  if (REDUCED_MOTION) state.orbit = false;
  el("cam-orbit").setAttribute("aria-pressed", state.orbit);
  if (state.orbit) orbitStep();
}

/* ---------- the time machine ---------- */
let timeTimer = null;
function wireTimeMachine() {
  const centreSelect = el("t-centre"), tierSelect = el("t-tier");
  centreSelect.innerHTML = [...STATIC.hawker_centres]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((c) => `<option value="${c.name}">${c.name}</option>`).join("");
  tierSelect.innerHTML = OPTIONS.tiers
    .map((t) => `<option value="${t.key}">${t.label}</option>`).join("");
  const refresh = () => {
    clearTimeout(timeTimer);
    timeTimer = setTimeout(runTimeMachine, 150);
  };
  centreSelect.addEventListener("change", refresh);
  tierSelect.addEventListener("change", refresh);
  el("t-takings").addEventListener("change", refresh);
  el("time-open").addEventListener("click", () => {
    if (state.selected?.type === "sme")
      centreSelect.value = STATIC.hawker_centres[state.selected.value].name;
    tierSelect.value = state.tier;
    el("time-dialog").showModal();
    runTimeMachine();
  });
}
async function runTimeMachine() {
  const body = el("t-body");
  body.innerHTML = `<p class="loading">Replaying ten years of NEA readings…</p>`;
  try {
    const burn = await api.burn(
      el("t-centre").value, "cooked_food", el("t-tier").value, +el("t-takings").value || 500);
    const t = burn.totals, hz = t.by_hazard_sgd;
    const hzMax = Math.max(hz.haze, hz.rain, hz.heat, 1);
    const labels = { haze: "Haze", rain: "Heavy rain", heat: "Heat" };
    const lostMax = Math.max(...burn.years.map((y) => y.est_lost_sgd), 1);
    body.innerHTML = `
      <p class="t-big"><span class="num">${SGD0(t.paid_sgd)}</span> <small>back in your till, ${t.from_year} to ${t.to_year}</small></p>
      <p class="t-line">Weather took about <b>${SGD0(t.est_lost_sgd)}</b> from a business like this.
        ${burn.tier_label} would have paid on <b>${t.trigger_days} bad days</b>, usually the same
        day, for <b>${SGD0(t.premium_sgd)}</b> of premium (${SGD(burn.weekly_premium_sgd)} a week).</p>
      <h3>Where the payouts came from</h3>
      ${Object.keys(labels).map((k) => `<div class="t-hz"><span>${labels[k]}</span>
        <div class="bar"><div style="width:${hz[k] / hzMax * 100}%;background:${CSS_BY_HAZARD[k]}"></div></div>
        <output>${SGD0(hz[k])}</output></div>`).join("")}
      <div class="t-hz"><span>Flash flood</span><div class="bar"></div><output>S$0</output></div>
      <h3>Year by year</h3>
      <p class="t-key"><span><i class="lost"></i>Lost to weather</span><span><i class="paid"></i>Paid by Payung</span></p>
      <div class="t-years">${burn.years.map((y) => `
        <div class="t-year"><div class="bars">
          <div class="lost" style="height:${Math.max(y.est_lost_sgd / lostMax * 60, 2)}px" title="Lost ~${SGD0(y.est_lost_sgd)}"></div>
          <div class="paid" style="height:${Math.max(y.paid_sgd / lostMax * 60, y.paid_sgd ? 2 : 0)}px" title="Paid ${SGD0(y.paid_sgd)}"></div>
        </div><span>${String(y.year).slice(2)}</span></div>`).join("")}</div>
      <p class="fine t-note">Losses are the tariff's loss score times the daily sales entered above; heat
        readings exist from 2025; flood pays on PUB alerts but is priced at zero history days so far.</p>
      <a class="btn primary t-cta" href="/login/#sme" target="_top">Get covered from ${SGD(burn.weekly_premium_sgd)}/week</a>`;
  } catch (error) {
    console.error(error);
    body.innerHTML = `<p class="notice critical">${icon("circle-alert")}<span>Could not replay this centre just now. Pick another centre or try again.</span></p>`;
  }
}

/* ---------- static UI ---------- */
function renderLegend() {
  el("sme-label").textContent = `Hawker centres (${STATIC.hawker_centres.length})`;
  const byRent = state.smeByRent && state.mode === "history";
  el("rent-legend").hidden = !byRent;
  el("sme-legend").hidden = byRent;
  el("sme-legend").innerHTML = SME_LEGEND[state.mode === "history" ? "history" : "day"]
    .map(([colour, label]) => `<span><i class="dot" style="--dot:var(--${colour})"></i>${label}</span>`).join("");
}
function aboutHtml() {
  return `
  <h3>How this map underwrites</h3>
  <p>Insurers price catastrophe-exposed risk with layered models. A catastrophe model has four modules - this atlas is the same structure drawn as a live map of Singapore, so an SME owner and an underwriter look at the same calculation.</p>
  <div class="modules">
    <div class="module"><div class="m1" style="--dot:var(--haze)">1 · Hazard</div><div class="m2">Where and how often each peril strikes.</div><div class="m3">NEA WBGT, rain-gauge and 24-h PSI history 2016-2026, plus today's live readings.</div></div>
    <div class="module"><div class="m1" style="--dot:var(--ink)">2 · Exposure</div><div class="m2">Who is standing in the way, geocoded.</div><div class="m3">${STATIC.hawker_centres.length} hawker centres, ${STATIC.hawker_centres.reduce((a, c) => a + c.food_stalls, 0).toLocaleString("en-SG")} cooked-food stalls (NEA).</div></div>
    <div class="module"><div class="m1" style="--dot:var(--heat)">3 · Vulnerability</div><div class="m2">How much a reading hurts a given business.</div><div class="m3">Severity bands × product factor (shelf life, restock, demand).</div></div>
    <div class="module"><div class="m1" style="--dot:var(--accent)">4 · Financial</div><div class="m2">Turning damage into premium and payout.</div><div class="m3">Day caps, the five-part premium, GST - the live tariff from the tariff desk.</div></div>
  </div>
  <p>This mirrors regulator-recognised practice (NAIC's description of property cat models) and the geospatial tools underwriters already use - Swiss Re CatNet and Munich Re Location Risk Intelligence score locations by stacking hazard layers over geocoded exposure. The difference here: the layers are open NEA data, so the customer sees the same map as the underwriter.</p>
  <h4>The premium, step by step (the Swiss Re and Munich Re recipe)</h4>
  <p>Swiss Re's CatNet and Munich Re's Location Risk Intelligence price a location by layering
  hazard frequency over geocoded exposure, applying a damage function, then adding the money
  terms. Payung runs the same four steps, with every input public:</p>
  <p>Every number on this page comes from the pricing API (<code>/api/quote</code>, <code>/api/assess</code>) - the same engine the tariff desk edits. For a stall, the engine replays every recorded day (haze from April 2014, rain from December 2016, heat from 2025) at the stations nearest the stall, read as a payout reads them (day-weighted severity × peril weight × product factor - classical burning-cost rating), counts each year's loss-days up to the tier's yearly cap and averages the years: the expected paid days. Expected payouts are those days times the daily amount. The tier's premium shares turn them into the premium before GST, in Income's five parts: expected payouts, reinsurance for haze years, management expenses, selling and distribution, and expected profit and risk margin. Then +9% GST (IRAS).</p>
  <h4>Why a payout is insurance, not a bet</h4>
  <p>Insurance Act 1966 s151 voids cover without insurable interest. Tier payouts run from S$35 to S$1,355 a day. Each payout is a pre-estimate of lost income, sold only to operating businesses. Tier 1 and Tier 2 sit below a stall's normal daily takings (triangulated S$400-800/day gross); Tier 3 and Tier 4 can pass them, so they fit businesses with higher takings. A tier is sold to a business only when it pays no more than that business loses on a day with no sales: its normal weekday sales times its product factor. Every price can be explained, as MAS's FEAT rules require: it comes from a public formula over public weather data, we can show a customer exactly why they pay what they pay, and no personal data goes into any price.</p>
  <h4>The protection gap</h4>
  <ul>
    <li>Singapore has ~369,500 SMEs - 99% of enterprises (SingStat, 2025); NEA manages 123 markets and hawker centres.</li>
    <li>About two-thirds of cooked-food stallholders hold insurance, but it is fire and liability cover; nothing covers weather-driven income loss without physical damage (MSE written parliamentary reply, 4 Aug 2026).</li>
    <li>~74% of SMEs worry about business-interruption income loss; only ~23% hold BI cover (QBE Singapore SME surveys 2024-2025).</li>
    <li>The payout shape already exists: Income's Stallholder Insurance paid S$100-200 per closure day after fire-type loss. Payung extends that familiar shape to haze, rain, heat and flood days.</li>
  </ul>
  <h4>What is real and what is assumed</h4>
  <ul>
    <li><b>Real:</b> every hazard reading (NEA via data.gov.sg, Singapore Open Data Licence), live readings in Live mode, hawker centre locations and stall counts (NEA), planning areas (URA MP2019), the 19 PUB flood hotspots (2 Feb 2026 list; plotted points approximate), the Oct 2026 haze episode (PSI peak 230; estimated cost S$2.32 bn, NTU).</li>
    <li><b>Assumed (team tariff, editable in the tariff desk):</b> severity bands, weights, product factors, tier payouts, caps and premium shares. Flood is priced at the tariff's assumed days/year; PUB records 2017-2023 suggest ~7 flash-flood days/yr island-wide (Li et al. 2024, Environ. Res. Lett.), and PUB's Flood Alerts feed (Oct 2025-) is the live trigger.</li>
    <li><b>Illustrative:</b> the portfolio ("every food stall buys one policy") sizes accumulation risk, not sales.</li>
  </ul>
  <p>No personal data is used anywhere: only aggregate NEA readings and public geography (PDPA-clean by construction).</p>`;
}

/* ---------- panels, drawers and the top bar ---------- */
function setFolded(panel, folded) {
  panel.classList.toggle("folded", folded);
  panel.querySelector(".fold")?.setAttribute("aria-expanded", !folded);
}
const FOLDING_PANELS = ["layers", "portfolio", "sim", "detail"];
const isCompact = () => EMBEDDED || window.matchMedia(COMPACT_SCREEN).matches;
function foldPanels() {
  for (const id of FOLDING_PANELS) setFolded(el(id), true);
}
/* Unfold one panel. On a small screen or in a dashboard the others fold, like an accordion. */
function openPanel(panel) {
  if (isCompact()) for (const id of FOLDING_PANELS) setFolded(el(id), el(id) !== panel);
  else setFolded(panel, false);
  if (isCompact()) panel.scrollIntoView({ block: "start" });
}
function wireDrawers() {
  for (const dialog of document.querySelectorAll("dialog.drawer")) {
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
  }
}
/* The dock sits under the top bar, which wraps to more rows on narrow screens. */
function trackTopbarHeight() {
  const topbar = el("topbar");
  new ResizeObserver(() => document.documentElement.style.setProperty("--topbar-h", `${topbar.offsetHeight}px`))
    .observe(topbar);
}
async function showDashboardLink() {
  if (EMBEDDED) return;
  try {
    await getJson("/api/auth/me");
    el("dashboard-link").hidden = false;
  } catch { /* signed out: the brand link is the way back */ }
}

function wireUi() {
  el("mode-history").addEventListener("click", () => setMode("history"));
  el("mode-sim").addEventListener("click", () => {
    setMode("sim");
    setFolded(el("portfolio"), true);
    openPanel(el("sim"));
  });
  el("mode-live").addEventListener("click", () => setMode("live"));
  el("cam-plan").addEventListener("click", () => flyTo("plan"));
  el("cam-bird").addEventListener("click", () => flyTo("bird"));
  el("cam-city").addEventListener("click", () => flyTo("city"));
  el("cam-orbit").addEventListener("click", () => toggleOrbit());
  el("map").addEventListener("pointerdown", () => { if (state.orbit) toggleOrbit(false); });
  window.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (state.orbit) toggleOrbit(false);
    if (state.drawing) { stopDrawing(); circleHint("Drawing cancelled."); redraw(); }
  });
  el("about-open").addEventListener("click", () => el("about-dialog").showModal());
  wireDrawers();
  wireTimeMachine();
  el("detail-close").addEventListener("click", () => { state.selected = null; renderDetail(); });
  for (const key of Object.keys(state.layers)) {
    el(`ly-${key}`).addEventListener("change", (event) => { state.layers[key] = event.target.checked; redraw(); });
  }
  el("sme-by-rent").addEventListener("change", (event) => {
    state.smeByRent = event.target.checked;
    renderLegend();
    redraw();
  });
  el("s-psi").addEventListener("input", (e) => setSim({ psi: +e.target.value }));
  el("s-rain").addEventListener("input", (e) => setSim({ rain: +e.target.value }));
  el("s-heat").addEventListener("input", (e) => setSim({ heat: +e.target.value }));
  el("s-flood").addEventListener("change", (e) => setSim({ flood: e.target.checked }));
  document.querySelectorAll(".panel .fold").forEach((button) => button.addEventListener("click", () => {
    const panel = button.closest(".panel");
    if (panel.classList.contains("folded")) openPanel(panel);
    else setFolded(panel, true);
  }));
  const dateInput = el("s-date");
  const today = new Date().toISOString().slice(0, 10);
  api.day(today).then((bounds) => {
    dateInput.min = bounds.available.min;
    dateInput.max = bounds.available.max;
    dateInput.value = bounds.found ? today : bounds.available.max;
  }).catch(() => {});
  dateInput.addEventListener("change", async () => {
    if (!dateInput.value) return;
    try {
      const day = await api.day(dateInput.value);
      const note = el("day-note");
      note.hidden = false;
      if (!day.found) {
        note.textContent = `No NEA readings for ${dateInput.value}. Data runs ${day.available.min} to ${day.available.max}.`;
        return;
      }
      state.replay = null;
      state.simExtra = {};
      document.querySelectorAll("#extra-hazards [data-extra]").forEach((input) => {
        if (input.type === "checkbox") input.checked = false;
        else { input.value = 0; const out = el(`xv-${input.dataset.extra}`); if (out) out.textContent = 0; }
      });
      setSim({
        psi: Math.round(day.haze.value), rain: Math.round(day.rain.value),
        heat: day.heat.value, flood: false,
      });
      state.replay = day;
      redraw(); renderPortfolio(); renderDetail();
      note.textContent = `On ${dateInput.value} each centre is scored on its own NEA readings: its zone's PSI, `
        + "the middle of its 3 nearest rain gauges that reported, and its nearest heat station. "
        + `Worst on the island: PSI ${Math.round(day.haze.value)}`
        + (day.haze.site ? ` (${day.haze.site} zone)` : "")
        + `, ${day.rain.value} mm rain` + (day.rain.site ? ` (gauge ${day.rain.site})` : "")
        + `, ${day.heat.value} h of dangerous heat` + (day.heat.site ? ` (${day.heat.site})` : "")
        + ". The sliders show these; moving one applies it to every centre.";
    } catch (error) { console.error(error); }
  });
  const productSelect = el("kyc-product");
  productSelect.innerHTML = `<option value="" disabled>Choose what you sell</option>`
    + OPTIONS.products.map((p) => `<option value="${p.key}">${p.label}</option>`).join("");
  productSelect.addEventListener("change", () => setShopProduct(productSelect.value));
  el("kyc-submit").addEventListener("click", readShop);
  el("kyc-clear").addEventListener("click", clearShopText);
  el("kyc-text").value = exampleShopText();
  el("kyc-confirm-btn").addEventListener("click", placeShop);
  el("kyc-strip").addEventListener("click", (event) => {
    const day = event.target.closest("[data-day]");
    if (day) applyBadDay(day.dataset.day);
  });
  el("draw-circle").addEventListener("click", startDrawing);
  el("remove-circle").addEventListener("click", removeActiveCircle);
  el("clear-all").addEventListener("click", clearAllCircles);
  el("s-radius").addEventListener("input", (e) => {
    const circle = activeCircle();
    if (!circle) return;
    circle.radiusKm = +e.target.value;
    el("v-radius").textContent = `${circle.radiusKm.toFixed(1)} km`;
    requestScenario(circle); redraw();
  });
  el("s-extradays").addEventListener("input", (e) => {
    state.extraDays = +e.target.value;
    el("v-extradays").textContent = `${state.extraDays} d`;
    applyControlChange();
  });
  buildExtraHazardControls();
  const tierSelect = el("p-tier");
  for (const tier of OPTIONS.tiers) {
    const option = document.createElement("option");
    option.value = tier.key; option.textContent = tier.label;
    tierSelect.appendChild(option);
  }
  state.tier = OPTIONS.tiers[1] ? OPTIONS.tiers[1].key : OPTIONS.tiers[0].key;
  tierSelect.value = state.tier;
  tierSelect.addEventListener("change", (e) => {
    state.tier = e.target.value;
    refreshSimAssessment(); requestAllScenarios(); renderShopStrip(); renderPortfolio(); renderDetail();
  });
}

/* ---------- boot ---------- */
async function boot() {
  trackTopbarHeight();
  showDashboardLink();
  try {
    if (!window.deck) throw new Error("deck.gl failed to load (vendor/deck.min.js)");
    [STATIC, QUOTES, OPTIONS, RENT] = await Promise.all([api.static(), api.quotes(), api.options(), api.rent()]);
    const anyQuote = Object.values(QUOTES.quotes)[0];
    PARTIAL_DAYS = await partialExamples(QUOTES.product, anyQuote.product_factor, anyQuote.tiers.map((t) => t.tier));
    const { DeckGL, AmbientLight, DirectionalLight, LightingEffect, MapView } = deck;
    lastView = {
      longitude: 103.832, latitude: 1.322, zoom: 10.6, pitch: 52, bearing: -12,
      maxZoom: 17.4, minZoom: 9.4, maxPitch: 78,
    };
    deckgl = new DeckGL({
      container: "map",
      views: new MapView({ repeat: false }),
      initialViewState: lastView,
      controller: { touchRotate: true, inertia: 260 },
      onClick: onMapClick,
      onDragStart: onMapDragStart,
      onDrag: onMapDrag,
      onDragEnd: onMapDragEnd,
      getCursor: ({ isDragging }) => (state.drawing ? "crosshair" : isDragging ? "grabbing" : "grab"),
      effects: [new LightingEffect({
        ambient: new AmbientLight({ color: [255, 255, 255], intensity: 1.6 }),
        sun: new DirectionalLight({ color: [255, 248, 240], intensity: 1.1, direction: [-2, -3, -1] }),
      })],
      getTooltip: tooltip,
      onViewStateChange: ({ viewState }) => {
        const crossed = [11, 11.6, 11.8, 12, 13].some((edge) => (state.zoom < edge) !== (viewState.zoom < edge));
        state.zoom = viewState.zoom;
        lastView = { ...lastView, ...viewState };
        if (crossed) redraw();
      },
      layers: [],
    });
    el("about-body").innerHTML = aboutHtml();
    wireUi();
    const params = new URLSearchParams(location.search);
    setMode(["history", "sim", "live"].includes(params.get("mode")) ? params.get("mode") : "history");
    const focusName = params.get("focus");
    const focusIndex = focusName ? STATIC.hawker_centres.findIndex((c) => c.name === focusName) : -1;
    if (focusIndex >= 0) select("sme", focusIndex);
    if (["plan", "bird", "city"].includes(params.get("camera"))) flyTo(params.get("camera"));
    if (state.mode === "sim") setFolded(el("portfolio"), true);
    if (isCompact()) foldPanels();
    el("boot").remove();
    positionFloats();
    if (document.fonts?.ready) document.fonts.ready.then(() => redraw());
    getJson("/api/map/buildings")
      .then((data) => { BUILDINGS = data; redraw(); })
      .catch((error) => console.error("buildings layer unavailable:", error));
  } catch (error) {
    const message = el("boot-msg");
    message.className = "notice critical";
    message.innerHTML = `${icon("circle-alert")}<span></span>`;
    message.querySelector("span").textContent = `Could not start the atlas: ${error.message}. `
      + "Check that the API is running and data/processed/map_static.json exists, then reload.";
  }
}
boot();
