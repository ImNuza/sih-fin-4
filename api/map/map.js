/* SafeDay risk atlas: 3D map of SME climate-risk exposure and pricing over Singapore.
   Data: /api/map/static (geography, exposure, hazard stats), /api/map/quotes (pricing),
   /api/map/live (today's NEA readings), POST /api/assess (one day's loss score).
   All pricing comes from the server's calculator; this file only draws it. */
"use strict";

const COLORS = {
  heat: [217, 89, 38], rain: [57, 135, 229], haze: [144, 133, 233], flood: [25, 158, 112],
  good: [12, 163, 12], warning: [250, 178, 25], serious: [236, 131, 90],
  ink: [242, 241, 237], lossLow: [82, 81, 78], lossHigh: [230, 103, 103],
};
const CSS_BY_HAZARD = { haze: "var(--haze)", rain: "var(--rain)", heat: "var(--heat)", flood: "var(--flood)", closure: "#898781" };
const AFFORDABLE_WEEKLY_SGD = 3;   // the brief's "a few dollars a week"
const COPAY_WEEKLY_SGD = 6;        // above this even a co-payer is a stretch
const LIVE_POLL_MS = 60_000;       // the server refreshes its NEA snapshot every 5 minutes
const PSI_BANDS = [[301, "Hazardous"], [201, "Very unhealthy"], [101, "Unhealthy"], [51, "Moderate"], [0, "Good"]];

const state = {
  mode: "history",                 // history | sim | live
  view: "insurer",                 // insurer | owner
  camera: "bird",                  // plan | bird | city
  orbit: false,
  layers: { sme: true, heat: true, rain: true, haze: true, flood: false, pa: true, bld: true, base: true },
  sim: { psi: 0, rain: 0, heat: 0, flood: false },
  simExtra: {},                    // readings for tariff hazards beyond the four built-in ones
  simAssessment: null,             // latest POST /api/assess result for the sim readings
  circle: null,                    // {lat, lng, radiusKm} the scenario is scoped to
  drawing: null,                   // "center" | "radius" while the user draws
  extraDays: 5,                    // frequency stress: days like this added per year
  scn: null,                       // latest POST /api/map/scenario result
  live: null,                      // latest /api/map/live snapshot
  livePoll: null,
  zoom: 10.6,
  rev: 0,                          // bumped on anything that changes layer accessors
  selected: null,                  // {type, index|obj}
  tier: null,                      // portfolio tier key
};
let STATIC = null, QUOTES = null, OPTIONS = null, BUILDINGS = null, deckgl = null;
let lastView = null;               // the camera, kept across presets, orbit and user drags
const ONEMAP_TILES = "https://www.onemap.gov.sg/maps/tiles/Night/{z}/{x}/{y}.png";

const el = (id) => document.getElementById(id);
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
  live: () => getJson("/api/map/live?product=cooked_food"),
  assess: (readings) => getJson("/api/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product: "cooked_food", tier: state.tier, readings }),
  }),
  scenario: (body) => getJson("/api/map/scenario", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
};
function simReadings() {
  return {
    haze: state.sim.psi, rain: state.sim.rain, heat: state.sim.heat,
    flood: state.sim.flood ? 1 : 0, ...state.simExtra,
  };
}

/* ---------- pricing views (all numbers come from the API) ---------- */
function regionQuote(region) { return QUOTES.quotes[region]; }
function recommendedTier(quote) {
  const affordable = quote.tiers.filter((t) => t.weekly_premium_sgd <= AFFORDABLE_WEEKLY_SGD);
  return affordable.length ? affordable[affordable.length - 1] : quote.tiers[0];
}
function verdict(quote) {
  const tier = recommendedTier(quote);
  if (tier.weekly_premium_sgd <= AFFORDABLE_WEEKLY_SGD)
    return { cls: "good", word: "Offer", tier,
      detail: `${tier.label} fits the brief's "few dollars a week": ${SGD(tier.weekly_premium_sgd)}/wk for ${SGD0(tier.daily_payout_sgd)}/day.` };
  if (tier.weekly_premium_sgd <= COPAY_WEEKLY_SGD)
    return { cls: "warning", word: "Offer with co-pay", tier,
      detail: `Cheapest tier is ${SGD(tier.weekly_premium_sgd)}/wk here - needs an operator, platform or NTUC co-payment to stay affordable.` };
  return { cls: "serious", word: "Refer to underwriter", tier,
    detail: `${quote.expected_loss_days.toFixed(1)} expected loss-days/yr price every tier above ${SGD0(COPAY_WEEKLY_SGD)}/wk in this region.` };
}
function insideCircle(point) {
  return state.circle && haversineKm(state.circle, point) <= state.circle.radiusKm;
}
function currentLossFraction(index) {
  if (state.mode === "sim") {
    if (state.circle) {
      if (!insideCircle(STATIC.hawker_centres[index])) return 0;
      return state.scn ? state.scn.assessment.loss_percent / 100 : 0;
    }
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
function smeColor(centre, index) {
  if (state.mode === "sim" && state.circle && !insideCircle(centre)) return [70, 74, 80, 150];
  if (state.mode !== "history") {
    const t = Math.min(1, currentLossFraction(index));
    return [0, 1, 2].map((i) => COLORS.lossLow[i] + (COLORS.lossHigh[i] - COLORS.lossLow[i]) * t).concat(235);
  }
  if (state.view === "insurer") return COLORS[verdict(regionQuote(centre.region)).cls].concat(235);
  return COLORS.ink.concat(235);
}

function buildLayers() {
  const { GeoJsonLayer, ColumnLayer, ScatterplotLayer, TextLayer, PolygonLayer, TileLayer, BitmapLayer } = deck;
  const zoom = state.zoom, layers = [];
  const paFeatures = STATIC.planning_areas.map((p) => ({ type: "Feature", geometry: p.geometry, properties: p }));

  if (state.layers.base) layers.push(new TileLayer({
    id: "base", data: ONEMAP_TILES, minZoom: 9, maxZoom: 18, tileSize: 256, opacity: 0.5,
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
    updateTriggers: { getFillColor: [state.rev, state.view, state.mode] },
  }));
  if (state.layers.sme && zoom >= 13) layers.push(new TextLayer({
    id: "sme-labels", data: STATIC.hawker_centres,
    getPosition: (d) => [d.lng, d.lat], getText: (d) => d.name,
    getSize: 11.5, getColor: [242, 241, 237, 235],
    getTextAnchor: "start", getAlignmentBaseline: "center", getPixelOffset: [12, 0],
    fontFamily: "Schibsted Grotesk, sans-serif", fontWeight: 600,
    outlineWidth: 2, outlineColor: [16, 18, 20, 255], fontSettings: { sdf: true },
  }));
  if (state.mode === "sim" && state.circle) layers.push(new ScatterplotLayer({
    id: "circle", data: [state.circle], pickable: false, stroked: true, filled: true,
    getPosition: (d) => [d.lng, d.lat],
    getRadius: (d) => d.radiusKm * 1000, radiusUnits: "meters",
    getFillColor: [134, 182, 239, 26],
    getLineColor: [134, 182, 239, state.drawing ? 255 : 190], getLineWidth: 2, lineWidthUnits: "pixels",
    updateTriggers: { getRadius: [state.rev], getLineColor: [state.rev] },
  }));
  if (zoom < 11.6) layers.push(new TextLayer({
    id: "region-labels",
    data: Object.entries(STATIC.region_points).map(([name, [lat, lng]]) => ({ name: name.toUpperCase(), lat, lng })),
    getPosition: (d) => [d.lng, d.lat], getText: (d) => d.name,
    getSize: 13, getColor: [195, 194, 183, 200],
    fontFamily: "Schibsted Grotesk, sans-serif", fontWeight: 700,
    outlineWidth: 2, outlineColor: [16, 18, 20, 220], fontSettings: { sdf: true },
  }));
  return layers;
}
function redraw() { state.rev += 1; deckgl.setProps({ layers: buildLayers() }); }

function tooltip({ object, layer, index }) {
  if (!object) return null;
  if (layer.id === "sme") {
    const quote = regionQuote(object.region), tier = recommendedTier(quote);
    const live = state.mode !== "history"
      ? ` · today's loss ${(currentLossFraction(index) * 100).toFixed(0)}%` : "";
    return { html: `<b>${object.name}</b><div class="m">${object.food_stalls} food stalls · ${object.region} region · ${SGD(tier.weekly_premium_sgd)}/wk at ${tier.label}${live}</div>` };
  }
  if (layer.id === "heat") return { html: `<b>${object.name}</b><div class="m">WBGT ≥32 °C on ${(object.share_days_ge_32 * 100).toFixed(0)}% of days · max ${object.max_wbgt.toFixed(1)} °C</div>` };
  if (layer.id === "rain") return { html: `<b>${object.name}</b><div class="m">20 mm hour on ${(object.share_days_ge_20 * 100).toFixed(1)}% of days (${object.days} days of record)</div>` };
  if (layer.id === "flood") return { html: `<b>${object.name}</b><div class="m">PUB flash-flood hotspot · location approximate</div>` };
  if (layer.id === "pa") return { html: `<b>${object.properties.name}</b><div class="m">${object.properties.psi_region} PSI region · URA ${object.properties.ura_region}</div>` };
  return null;
}

/* ---------- scenario circle ---------- */
let scenarioTimer = null, scenarioSeq = 0, hoverPending = false;
function circleHint(text) { el("circle-hint").textContent = text; }
function requestScenario() {
  if (state.mode !== "sim" || !state.circle || state.drawing) return;
  clearTimeout(scenarioTimer);
  scenarioTimer = setTimeout(async () => {
    const seq = ++scenarioSeq;
    try {
      const result = await api.scenario({
        lat: state.circle.lat, lng: state.circle.lng, radius_km: state.circle.radiusKm,
        readings: simReadings(), extra_days_per_year: state.extraDays,
        product: "cooked_food", tier: state.tier,
      });
      if (seq !== scenarioSeq) return;
      state.scn = result;
      renderScenario(); redraw(); renderPortfolio(); renderDetail();
    } catch (error) { console.error(error); }
  }, 180);
}
function renderScenario() {
  const box = el("scn-results"), scn = state.scn;
  if (!scn || !state.circle) { box.hidden = true; return; }
  box.hidden = false;
  const t = scn.totals;
  const factors = scn.assessment.hazards.filter((h) => h.loss_percent > 0);
  box.innerHTML = `
    <p class="cap">Inside the circle · ${t.centres} centres · ${t.stalls.toLocaleString("en-SG")} stalls</p>
    <div class="kv"><span class="k">Loss score on this day</span><span class="v">${scn.assessment.loss_percent.toFixed(0)}%</span></div>
    <div class="kv"><span class="k">Payout per stall (${state.tier.replace("_", " ")})</span><span class="v">${SGD(scn.assessment.payout_sgd)}</span></div>
    <div class="kv"><span class="k">Payout, whole circle</span><span class="v">${SGD(t.payout_today_sgd)}</span></div>
    <div class="kv"><span class="k">Weekly premium pool</span>
      <span class="v">${SGD(t.weekly_premium_baseline_sgd)} → <span class="delta-up">${SGD(t.weekly_premium_stressed_sgd)}</span></span></div>
    ${factors.length ? `<p class="cap">What is driving it</p>` : ""}
    ${factors.map((h) => `<div class="factor"><span>${QUOTES.hazard_labels[h.hazard] || h.hazard}</span>
      <div class="bar"><div style="width:${h.loss_percent}%;background:${CSS_BY_HAZARD[h.hazard] || "var(--accent)"}"></div></div>
      <output>${h.loss_percent.toFixed(0)}%</output></div>`).join("")}
    <p class="note">Premium stress: days like this hitting ${state.extraDays} more times a year on top of the region's NEA history, repriced by the same engine. All numbers from the API.</p>`;
}
function startDrawing() {
  state.drawing = "center"; state.scn = null;
  el("draw-circle").classList.add("on");
  el("clear-circle").hidden = false;
  circleHint("Click the map to set the centre.");
  renderScenario(); redraw();
}
function clearCircle() {
  state.circle = null; state.drawing = null; state.scn = null;
  el("draw-circle").classList.remove("on");
  el("clear-circle").hidden = true;
  el("extradays-row").hidden = true;
  circleHint("Scope the day to one area: the readings then apply only inside it.");
  renderScenario(); redraw(); renderPortfolio(); renderDetail();
}
function onMapClick(info) {
  if (!state.drawing || !info.coordinate) return;
  const [lng, lat] = info.coordinate;
  if (state.drawing === "center") {
    state.circle = { lat, lng, radiusKm: 0.8 };
    state.drawing = "radius";
    circleHint("Move the pointer, then click to set the size.");
  } else {
    state.circle.radiusKm = Math.min(15, Math.max(0.1, haversineKm(state.circle, { lat, lng }) || 0.8));
    state.drawing = null;
    el("draw-circle").classList.remove("on");
    el("extradays-row").hidden = false;
    circleHint(`${state.circle.radiusKm.toFixed(1)} km around ${state.circle.lat.toFixed(3)}, ${state.circle.lng.toFixed(3)} — sent to the backend with every slider move.`);
    requestScenario();
  }
  redraw();
}
function onMapHover(info) {
  if (state.drawing !== "radius" || !info.coordinate || hoverPending) return;
  const [lng, lat] = info.coordinate;
  state.circle.radiusKm = Math.min(15, Math.max(0.1, haversineKm(state.circle, { lat, lng })));
  hoverPending = true;
  requestAnimationFrame(() => { hoverPending = false; redraw(); });
}
function buildExtraHazardControls() {
  const host = el("extra-hazards");
  const known = new Set(["haze", "rain", "heat", "flood"]);
  const extras = (QUOTES.hazards || []).filter((h) => !known.has(h.key));
  host.innerHTML = extras.map((h) => h.binary
    ? `<label class="floodrow"><input type="checkbox" data-extra="${h.key}" /> ${h.label} — ${h.reading}</label>`
    : `<div class="slider"><i style="background:var(--accent)"></i>
        <label for="x-${h.key}">${h.label}</label>
        <input type="range" id="x-${h.key}" data-extra="${h.key}" min="0" max="${h.max}" step="1" value="0" />
        <output id="xv-${h.key}">0</output></div>`).join("");
  host.querySelectorAll("[data-extra]").forEach((input) =>
    input.addEventListener("input", () => {
      const value = input.type === "checkbox" ? (input.checked ? 1 : 0) : +input.value;
      state.simExtra[input.dataset.extra] = value;
      const out = el(`xv-${input.dataset.extra}`);
      if (out) out.textContent = input.value;
      refreshSimAssessment(); requestScenario();
    }));
}

/* ---------- detail panel ---------- */
function select(type, value) {
  if (state.drawing) return;
  state.selected = { type, value };
  renderDetail();
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
    bars += `<rect x="${(i * bw + 3).toFixed(1)}" y="${(H - 16 - h).toFixed(1)}" width="${(bw - 6).toFixed(1)}" height="${h.toFixed(1)}" rx="2.5" fill="${hot ? "#9085e9" : "#4b4766"}"/>`;
    if (y.days_unhealthy > 0) bars += `<text x="${(i * bw + bw / 2).toFixed(1)}" y="${(H - 20 - h).toFixed(1)}" font-size="9.5" fill="#c3c2b7" text-anchor="middle" font-family="IBM Plex Mono">${y.days_unhealthy}</text>`;
    if (i % 2 === 0 || hot) bars += `<text x="${(i * bw + bw / 2).toFixed(1)}" y="${H - 4}" font-size="9" fill="#898781" text-anchor="middle" font-family="IBM Plex Mono">${String(y.year).slice(2)}</text>`;
  });
  return `<div class="minichart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Unhealthy haze days per year">
    <line x1="0" y1="${H - 16}" x2="${W}" y2="${H - 16}" stroke="#383835" stroke-width="1"/>${bars}</svg>
    <p class="note">Days with 24-h PSI &gt; 100 per year. NEA, Mar 2016 - Nov 2026.</p></div>`;
}
function premiumBuildup(tier) {
  const p = QUOTES.pricing;
  const risk = tier.expected_paid_days * tier.daily_payout_sgd;
  const loads = risk * (p.uncertainty_load + p.catastrophe_load);
  const expenses = (risk + loads) / (1 - p.expense_ratio) - (risk + loads);
  const gst = (risk + loads + expenses) * p.gst_rate;
  return `<div class="buildup">
    <div class="row"><span>Risk cost - ${tier.expected_paid_days.toFixed(2)} paid days × ${SGD0(tier.daily_payout_sgd)}</span><span>${SGD(risk)}</span></div>
    <div class="row"><span>+ uncertainty load ${Math.round(p.uncertainty_load * 100)}% + catastrophe load ${Math.round(p.catastrophe_load * 100)}%</span><span>${SGD(loads)}</span></div>
    <div class="row"><span>+ expenses (${Math.round(p.expense_ratio * 100)}% of gross)</span><span>${SGD(expenses)}</span></div>
    <div class="row"><span>+ GST ${Math.round(p.gst_rate * 100)}%</span><span>${SGD(gst)}</span></div>
    <div class="row total"><span>Yearly premium → ${SGD(tier.weekly_premium_sgd)}/week</span><span>${SGD(tier.yearly_premium_sgd)}</span></div>
  </div>`;
}
function dayDetail(index, tier) {
  const loss = currentLossFraction(index);
  const centre = STATIC.hawker_centres[index];
  const inCircle = state.mode === "sim" && state.circle && insideCircle(centre);
  if (state.mode === "sim" && state.circle && !inCircle)
    return `<div class="sec"><p class="cap">On the simulated day</p>
      <p class="note">Outside the drawn circle: the scenario's readings do not apply here.</p></div>`;
  const readings = state.mode === "live"
    ? state.live?.hawker_losses?.[index]?.readings
    : { haze: state.sim.psi, rain: state.sim.rain, heat: state.sim.heat };
  if (state.mode === "history" || !readings) return "";
  const label = state.mode === "live" ? `Live today (${state.live?.date ?? ""})` : "On the simulated day";
  const stressed = inCircle && state.scn ? state.scn.regions[centre.region] : null;
  return `<div class="sec"><p class="cap">${label}${inCircle ? " · inside the circle" : ""}</p>
    <div class="kv"><span class="k">Readings here (PSI / mm / h ≥32)</span><span class="v">${Math.round(readings.haze)} / ${Math.round(readings.rain)} / ${readings.heat}</span></div>
    <div class="kv"><span class="k">Loss score (share of a normal day's sales)</span><span class="v">${(loss * 100).toFixed(0)}%</span></div>
    <div class="kv"><span class="k">Payout per stall at ${tier.label}</span><span class="v">${SGD(loss * tier.daily_payout_sgd)}</span></div>
    <div class="kv"><span class="k">Whole centre (${centre.food_stalls} stalls)</span><span class="v">${SGD0(loss * tier.daily_payout_sgd * centre.food_stalls)}</span></div>
    ${stressed ? `<div class="kv"><span class="k">Weekly premium if this grows ${state.extraDays} d/yr more frequent</span>
      <span class="v">${SGD(stressed.weekly_baseline_sgd)} → <span class="delta-up">${SGD(stressed.weekly_stressed_sgd)}</span></span></div>` : ""}
    <p class="note">Paid automatically on NEA readings - no claim form, no loss adjuster.</p></div>`;
}
function renderDetail() {
  const panel = el("detail"), body = el("detail-body"), kind = el("detail-kind");
  if (!state.selected) { panel.hidden = true; return; }
  panel.hidden = false;
  const insurer = state.view === "insurer";
  const { type, value } = state.selected;

  if (type === "sme") {
    const centre = STATIC.hawker_centres[value];
    const quote = regionQuote(centre.region), v = verdict(quote), rec = v.tier;
    const parts = QUOTES.loss_day_parts[centre.region];
    const nearHeat = nearest(STATIC.wbgt_stations, centre), nearRain = nearest(STATIC.rain_stations, centre);
    const basisFar = Math.min(nearHeat.km, nearRain.km) > 3;
    kind.textContent = "SME · hawker centre";
    body.innerHTML = `
      <p class="title">${centre.name}</p>
      <p class="subtitle">${centre.address} · ${centre.region} PSI region${centre.built ? ` · est. ${centre.built}` : ""}</p>
      <div class="chips">
        <span class="chip">${centre.food_stalls} cooked-food stalls (NEA)</span>
        <span class="chip ${basisFar ? "warning" : "good"}">trigger stations ${nearHeat.km.toFixed(1)} km (heat) · ${nearRain.km.toFixed(1)} km (rain)</span>
      </div>
      ${insurer ? `
      <div class="verdict"><div class="mark" style="background:var(--${v.cls})"></div>
        <div><div class="t1">${v.word} - ${rec.label}</div><div class="t2">${v.detail}</div></div></div>
      <div class="sec"><p class="cap">Expected loss - ${quote.expected_loss_days.toFixed(2)} full-loss days / year</p>
        ${stackBar(parts)}
        <p class="note">Day-weighted severity of every NEA reading in the ${centre.region} region's history × 365.25 × peril weight × product factor (cooked food keeps nothing overnight).</p></div>
      <div class="sec"><p class="cap">Tariff - weekly premium per stall</p>
        <table class="tiers"><tr><th>Tier</th><th>Payout/day</th><th>Cap</th><th>Max/yr</th><th>Weekly</th></tr>
        ${quote.tiers.map((t) => `<tr class="${t.tier === rec.tier ? "rec" : ""}"><td>${t.label}</td><td>${SGD0(t.daily_payout_sgd)}</td><td>${t.max_paid_days_per_year ?? Math.round(t.max_payout_per_year_sgd / t.daily_payout_sgd)} d</td><td>${SGD0(t.max_payout_per_year_sgd)}</td><td>${SGD(t.weekly_premium_sgd)}</td></tr>`).join("")}
        </table></div>
      <div class="sec"><p class="cap">Premium build-up - ${rec.label}</p>${premiumBuildup(rec)}
        <p class="note">Insurable interest (Insurance Act 1966 s151): the payout is a pre-estimate of a stall's lost daily takings, so this is insurance, not a wager.</p></div>`
      : `
      <div class="verdict"><div class="mark" style="background:var(--${v.cls})"></div>
        <div><div class="t1">${SGD(rec.weekly_premium_sgd)} a week</div>
        <div class="t2">Pays up to ${SGD0(rec.daily_payout_sgd)} a day when haze, heavy rain, extreme heat or a flood alert hits your stall's area. Paid on NEA readings, usually same-day. You can lose sales and receive nothing if readings stay below the trigger.</div></div></div>
      <div class="sec"><p class="cap">In one SMS</p>
        <p class="note" style="font-size:12px;color:var(--ink-2)">"SafeDay: we pay ${SGD0(rec.daily_payout_sgd)}/day (max ${SGD0(rec.max_payout_per_year_sgd)}/yr) when NEA shows PSI>100, rain ≥20 mm/h, WBGT ≥32 °C for 2 h+, or a PUB flood alert near ${centre.name}. ${SGD(rec.weekly_premium_sgd)}/wk. No payout below these levels."</p></div>`}
      ${dayDetail(value, rec)}`;
  } else if (type === "heat") {
    const s = value;
    const live = state.live?.heat?.find((x) => x.id === s.id);
    kind.textContent = "Hazard · WBGT station";
    body.innerHTML = `<p class="title">${s.name}</p>
      <p class="subtitle">NEA station ${s.id} · ${s.days} days of record since 16 Jan 2025</p>
      ${live ? `<div class="kv"><span class="k">Latest WBGT (live)</span><span class="v">${live.latest.toFixed(1)} °C</span></div>
      <div class="kv"><span class="k">Work hours ≥32 °C today</span><span class="v">${live.hours_ge_32_today.toFixed(2)} h</span></div>` : ""}
      <div class="kv"><span class="k">Days reaching 32 °C (MOM rest-break level)</span><span class="v">${(s.share_days_ge_32 * 100).toFixed(0)}%</span></div>
      <div class="kv"><span class="k">Hours at ≥32 °C over the record</span><span class="v">${s.hours_ge_32.toFixed(0)} h</span></div>
      <div class="kv"><span class="k">Hottest reading</span><span class="v">${s.max_wbgt.toFixed(1)} °C</span></div>
      <p class="note">Heat is frequent but short: when WBGT reaches 32 °C it usually stays under an hour, so the trigger uses a duration rule (2 h+), not a single touch. MOM accepts NEA myENV readings as the workplace reference.</p>`;
  } else if (type === "rain") {
    const s = value;
    const live = state.live?.rain?.find((x) => x.id === s.id);
    kind.textContent = "Hazard · rain gauge";
    body.innerHTML = `<p class="title">${s.name}</p>
      <p class="subtitle">Gauge ${s.id} · ${s.days} days of record (10-year NEA history)</p>
      ${live ? `<div class="kv"><span class="k">Wettest work hour today (live)</span><span class="v">${live.wettest_work_hour_today.toFixed(1)} mm</span></div>` : ""}
      <div class="kv"><span class="k">Days with a 20 mm work-hour</span><span class="v">${(s.share_days_ge_20 * 100).toFixed(1)}%</span></div>
      <div class="kv"><span class="k">Days with a 30 mm work-hour</span><span class="v">${(s.share_days_ge_30 * 100).toFixed(1)}%</span></div>
      <div class="kv"><span class="k">Average wet work-hours per day</span><span class="v">${s.wet_hours_per_day.toFixed(2)} h</span></div>
      <p class="note">Rain is local: on an island-wide "rain day" only ~13% of gauges see a heavy hour, so the policy triggers on the gauge nearest the stall.</p>`;
  } else if (type === "flood") {
    kind.textContent = "Hazard · flood hotspot";
    body.innerHTML = `<p class="title">${value.name}</p>
      <p class="subtitle">PUB flash-flood hotspot (list of 2 Feb 2026) · plotted location approximate</p>
      <p class="note">Flash floods in Singapore are localised and usually subside within an hour; flood-prone area is down to 23.3 ha (PUB, 2025) from ~3,200 ha in the 1970s. PUB records 2017-2023 show ~7 flash-flood days a year island-wide (Li et al. 2024). The live trigger is PUB's Flood Alerts feed, shown in Live mode.</p>`;
  } else if (type === "region") {
    const area = value, region = area.psi_region;
    const quote = regionQuote(region), parts = QUOTES.loss_day_parts[region];
    const tier2 = quote.tiers[1] ?? quote.tiers[0];
    kind.textContent = "Region profile";
    body.innerHTML = `<p class="title">${area.name}</p>
      <p class="subtitle">URA ${area.ura_region} region · priced from the <b>${region}</b> PSI region's NEA history</p>
      <div class="sec"><p class="cap">Expected full-loss days (cooked food)</p>
        ${stackBar(parts)}
        <p class="note">${quote.expected_loss_days.toFixed(2)} days/yr → ${tier2.label} (${SGD0(tier2.daily_payout_sgd)}/day) prices at ${SGD(tier2.weekly_premium_sgd)}/week here.</p></div>
      <div class="sec"><p class="cap">Haze history - the catastrophe peril</p>${hazeYearChart()}</div>`;
  }
}

/* ---------- portfolio ---------- */
function renderPortfolio() {
  const box = el("portfolio");
  if (state.view !== "insurer") { box.hidden = true; return; }
  box.hidden = false;
  box.classList.toggle("raised", state.mode === "sim");
  const tierKey = state.tier;
  let stalls = 0, premiumPool = 0, expectedPayouts = 0, dayPayout = 0;
  STATIC.hawker_centres.forEach((centre, index) => {
    const tier = regionQuote(centre.region).tiers.find((t) => t.tier === tierKey);
    stalls += centre.food_stalls;
    premiumPool += tier.yearly_premium_sgd * centre.food_stalls;
    expectedPayouts += tier.expected_paid_days * tier.daily_payout_sgd * centre.food_stalls;
    dayPayout += currentLossFraction(index) * tier.daily_payout_sgd * centre.food_stalls;
  });
  if (state.mode === "sim" && state.circle && state.scn) {
    const t = state.scn.totals;
    el("p-n").textContent = `${t.stalls.toLocaleString("en-SG")} in circle`;
    el("p-prem").textContent = `${SGD0(t.weekly_premium_baseline_sgd * 52)}/yr`;
    el("p-pay-label").textContent = "Payout in the circle today";
    el("p-pay").textContent = SGD0(t.payout_today_sgd);
    el("p-note").textContent =
      `${t.centres} centres affected. Stressed premium pool ${SGD0(t.weekly_premium_stressed_sgd * 52)}/yr `
      + `if days like this hit ${state.extraDays} more times a year.`;
    return;
  }
  el("p-n").textContent = stalls.toLocaleString("en-SG");
  el("p-prem").textContent = SGD0(premiumPool);
  if (state.mode === "history") {
    el("p-pay-label").textContent = "Expected payouts / year";
    el("p-pay").textContent = SGD0(expectedPayouts);
    el("p-note").textContent = "Illustrative accumulation: every cooked-food stall in all "
      + `${STATIC.hawker_centres.length} centres buys one policy. Not a sales forecast.`;
  } else {
    el("p-pay-label").textContent = state.mode === "live" ? "Payout for today so far" : "Payout on this day";
    el("p-pay").textContent = SGD0(dayPayout);
    el("p-note").textContent = dayPayout > 0
      ? `This day consumes ${(dayPayout / premiumPool * 100).toFixed(1)}% of the annual premium pool. `
        + "The Oct 2026 haze ran 23 unhealthy days - why payable days are capped and the catastrophe load buys reinsurance."
      : "No trigger level is reached on these readings, so nothing is paid.";
  }
}

/* ---------- simulator ---------- */
const PRESETS = {
  calm: { psi: 0, rain: 0, heat: 0, flood: false },
  haze230: { psi: 230, rain: 0, heat: 0, flood: false },
  storm: { psi: 0, rain: 50, heat: 0, flood: true },
  hot: { psi: 0, rain: 0, heat: 4, flood: false },
};
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
function setSim(partial, preset) {
  Object.assign(state.sim, partial);
  document.querySelectorAll(".preset").forEach((b) => b.classList.toggle("on", b.dataset.p === preset));
  el("s-psi").value = state.sim.psi; el("s-rain").value = state.sim.rain; el("s-heat").value = state.sim.heat;
  el("s-flood").checked = state.sim.flood;
  el("v-psi").textContent = state.sim.psi;
  el("psi-band").textContent = state.sim.psi > 0 ? psiBand(state.sim.psi) : "";
  el("v-rain").textContent = `${state.sim.rain} mm`;
  el("v-heat").textContent = `${state.sim.heat} h`;
  refreshSimAssessment();
  requestScenario();
  redraw();
}

/* ---------- live mode ---------- */
async function pollLive() {
  const label = el("live-state");
  try {
    const snapshot = await api.live();
    state.live = snapshot;
    if (!snapshot.available) {
      label.textContent = `LIVE · ${snapshot.status}`;
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
      el("flood-banner").textContent = `PUB flood alert${alerts.length > 1 ? "s" : ""} active: `
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
  for (const name of ["history", "sim", "live"]) el(`mode-${name === "sim" ? "sim" : name}`).classList.toggle("on", name === mode);
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
  if (mode === "sim" && !state.simAssessment) setSim({ ...PRESETS.haze230 }, "haze230");
  redraw(); renderPortfolio(); renderDetail();
}
function setView(view) {
  state.view = view;
  el("view-owner").classList.toggle("on", view === "owner");
  el("view-insurer").classList.toggle("on", view === "insurer");
  redraw(); renderPortfolio(); renderDetail();
}

/* ---------- cameras ---------- */
const CAMERAS = {
  plan: { pitch: 0, bearing: 0, zoom: 10.9 },
  bird: { pitch: 52, bearing: -12, zoom: 10.6 },
  city: { pitch: 68, bearing: 35, zoom: 14.4 },
};
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function flyTo(name) {
  state.camera = name;
  for (const cam of Object.keys(CAMERAS)) el(`cam-${cam}`).classList.toggle("on", cam === name);
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
  updateZoomChip(target.zoom);
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
  el("cam-orbit").classList.toggle("on", state.orbit);
  if (state.orbit) orbitStep();
}

/* ---------- static UI ---------- */
function legendNotes() {
  el("sme-label").textContent = `SMEs — hawker centres (${STATIC.hawker_centres.length})`;
  el("heat-note").textContent = "History: column height = share of days reaching WBGT 32 °C. Live: work hours ≥32 °C today.";
  el("rain-note").textContent = "History: share of days with a 20 mm work-hour. Live: wettest work hour today.";
  el("haze-note").textContent = "History: expected haze loss-days by region. Simulate and Live: region lift = 24-h PSI.";
  el("sources-foot").textContent = STATIC.sources.hazard;
}
function updateZoomChip(zoom) {
  const level = zoom < 11 ? "island" : zoom < 13 ? "region" : "site";
  document.querySelectorAll(".zoomchip .step").forEach((s) => s.classList.toggle("on", s.dataset.z === level));
}
function aboutHtml() {
  return `
  <h3>How this map underwrites</h3>
  <p>Insurers price catastrophe-exposed risk with layered models. A catastrophe model has four modules - this atlas is the same structure drawn as a live map of Singapore, so an SME owner and an underwriter look at the same calculation.</p>
  <div class="modules">
    <div class="module"><div class="m1" style="color:var(--haze)">1 · Hazard</div><div class="m2">Where and how often each peril strikes.</div><div class="m3">NEA WBGT, rain-gauge and 24-h PSI history 2016-2026, plus today's live readings.</div></div>
    <div class="module"><div class="m1" style="color:#f2f1ed">2 · Exposure</div><div class="m2">Who is standing in the way, geocoded.</div><div class="m3">${STATIC.hawker_centres.length} hawker centres, ${STATIC.hawker_centres.reduce((a, c) => a + c.food_stalls, 0).toLocaleString("en-SG")} cooked-food stalls (NEA).</div></div>
    <div class="module"><div class="m1" style="color:var(--heat)">3 · Vulnerability</div><div class="m2">How much a reading hurts a given business.</div><div class="m3">Severity bands × product factor (shelf life, restock, demand).</div></div>
    <div class="module"><div class="m1" style="color:var(--accent)">4 · Financial</div><div class="m2">Turning damage into premium and payout.</div><div class="m3">Day caps, loads, expenses, GST - the live tariff from the tariff desk.</div></div>
  </div>
  <p>This mirrors regulator-recognised practice (NAIC's description of property cat models) and the geospatial tools underwriters already use - Swiss Re CatNet and Munich Re Location Risk Intelligence score locations by stacking hazard layers over geocoded exposure. The difference here: the layers are open NEA data, so the customer sees the same map as the underwriter.</p>
  <h4>The premium, step by step</h4>
  <p>Every number on this page comes from the pricing API (<code>/api/quote</code>, <code>/api/assess</code>) - the same engine the tariff desk edits. For a stall, the engine computes expected loss-days (day-weighted severity of every NEA reading in the region's history × 365.25 × peril weight × product factor - classical burning-cost rating), caps paid days per tier, then loads: +15% uncertainty, +10% catastrophe (modest next to the 2-4× expected-loss multiples of the cat-bond market), ÷ (1-25%) expenses (the documented microinsurance average), +9% GST (IRAS).</p>
  <h4>Why a payout is insurance, not a bet</h4>
  <p>Insurance Act 1966 s151 voids cover without insurable interest. Tier payouts (S$20-100/day) sit below a stall's normal daily takings (triangulated S$400-800/day gross), so each payout is a pre-estimate of lost income, sold only to operating stallholders. Pricing is a transparent formula over public data, in line with MAS FEAT explainability and Fair Dealing.</p>
  <h4>The protection gap</h4>
  <ul>
    <li>Singapore has ~369,500 SMEs - 99% of enterprises (SingStat, 2025); NEA manages 123 markets and hawker centres.</li>
    <li>About two-thirds of cooked-food stallholders hold insurance, but it is fire and liability cover; nothing covers weather-driven income loss without physical damage (MSE written parliamentary reply, 4 Aug 2026).</li>
    <li>~74% of SMEs worry about business-interruption income loss; only ~23% hold BI cover (QBE Singapore SME surveys 2024-2025).</li>
    <li>The payout shape already exists: Income's Stallholder Insurance paid S$100-200 per closure day after fire-type loss. SafeDay extends that familiar shape to haze, rain, heat and flood days.</li>
  </ul>
  <h4>What is real and what is assumed</h4>
  <ul>
    <li><b>Real:</b> every hazard reading (NEA via data.gov.sg, Singapore Open Data Licence), live readings in Live mode, hawker centre locations and stall counts (NEA), planning areas (URA MP2019), the 19 PUB flood hotspots (2 Feb 2026 list; plotted points approximate), the Oct 2026 haze episode (PSI peak 230; estimated cost S$2.32 bn, NTU).</li>
    <li><b>Assumed (team tariff, editable in the tariff desk):</b> severity bands, weights, product factors, tier payouts, caps and loads. Flood is priced at the tariff's assumed days/year; PUB records 2017-2023 suggest ~7 flash-flood days/yr island-wide (Li et al. 2024, Environ. Res. Lett.), and PUB's Flood Alerts feed (Oct 2025-) is the live trigger.</li>
    <li><b>Illustrative:</b> the portfolio ("every food stall buys one policy") sizes accumulation risk, not sales.</li>
  </ul>
  <p>No personal data is used anywhere: only aggregate NEA readings and public geography (PDPA-clean by construction).</p>`;
}

function wireUi() {
  el("mode-history").addEventListener("click", () => setMode("history"));
  el("mode-sim").addEventListener("click", () => setMode("sim"));
  el("mode-live").addEventListener("click", () => setMode("live"));
  el("cam-plan").addEventListener("click", () => flyTo("plan"));
  el("cam-bird").addEventListener("click", () => flyTo("bird"));
  el("cam-city").addEventListener("click", () => flyTo("city"));
  el("cam-orbit").addEventListener("click", () => toggleOrbit());
  el("map").addEventListener("pointerdown", () => { if (state.orbit) toggleOrbit(false); });
  window.addEventListener("keydown", (e) => { if (e.key === "Escape" && state.orbit) toggleOrbit(false); });
  el("view-owner").addEventListener("click", () => setView("owner"));
  el("view-insurer").addEventListener("click", () => setView("insurer"));
  el("about-open").addEventListener("click", () => el("about-dialog").showModal());
  el("detail-close").addEventListener("click", () => { state.selected = null; renderDetail(); });
  for (const key of Object.keys(state.layers)) {
    el(`ly-${key}`).addEventListener("change", (event) => { state.layers[key] = event.target.checked; redraw(); });
  }
  document.querySelectorAll(".preset").forEach((b) =>
    b.addEventListener("click", () => setSim({ ...PRESETS[b.dataset.p] }, b.dataset.p)));
  el("s-psi").addEventListener("input", (e) => setSim({ psi: +e.target.value }));
  el("s-rain").addEventListener("input", (e) => setSim({ rain: +e.target.value }));
  el("s-heat").addEventListener("input", (e) => setSim({ heat: +e.target.value }));
  el("s-flood").addEventListener("change", (e) => setSim({ flood: e.target.checked }));
  el("draw-circle").addEventListener("click", startDrawing);
  el("clear-circle").addEventListener("click", clearCircle);
  el("s-extradays").addEventListener("input", (e) => {
    state.extraDays = +e.target.value;
    el("v-extradays").textContent = `${state.extraDays} d`;
    requestScenario();
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
    refreshSimAssessment(); requestScenario(); renderPortfolio(); renderDetail();
  });
}

/* ---------- boot ---------- */
async function boot() {
  try {
    if (!window.deck) throw new Error("deck.gl failed to load (vendor/deck.min.js)");
    [STATIC, QUOTES, OPTIONS] = await Promise.all([api.static(), api.quotes(), api.options()]);
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
      onHover: onMapHover,
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
        updateZoomChip(viewState.zoom);
        if (crossed) redraw();
      },
      layers: [],
    });
    el("about-body").innerHTML = aboutHtml();
    legendNotes();
    wireUi();
    const params = new URLSearchParams(location.search);
    setView(["owner", "insurer"].includes(params.get("view")) ? params.get("view") : "insurer");
    setMode(["history", "sim", "live"].includes(params.get("mode")) ? params.get("mode") : "history");
    const focusName = params.get("focus");
    const focusIndex = focusName ? STATIC.hawker_centres.findIndex((c) => c.name === focusName) : -1;
    if (focusIndex >= 0) select("sme", focusIndex);
    if (["plan", "bird", "city"].includes(params.get("camera"))) flyTo(params.get("camera"));
    updateZoomChip(state.zoom);
    el("boot").remove();
    if (document.fonts?.ready) document.fonts.ready.then(() => redraw());
    getJson("/api/map/buildings")
      .then((data) => { BUILDINGS = data; redraw(); })
      .catch((error) => console.error("buildings layer unavailable:", error));
  } catch (error) {
    el("boot-msg").textContent = `Could not start the atlas: ${error.message}. `
      + "Check that the API is running and data/processed/map_static.json exists, then reload.";
    document.querySelector("#boot .pulse")?.remove();
  }
}
boot();
