"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const fmt = (x, d = 4) => (x == null || Number.isNaN(x)) ? "—" : Number(x).toFixed(d);
const pct = (x, d = 2) => (x == null || Number.isNaN(x)) ? "—" : (100 * x).toFixed(d) + "%";
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let META = null, polling = null, currentRunId = null, ACCESS_TOKEN = null;
// Red-team adversaries are now set ONLY via presets (folded in); held as state
// and shown in the preset "what changes" summary, not a standalone tab.
let currentRedTeam = [];

/* ---------- seeded generative imagery (deterministic, offline) ---------- */
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function seedFrom(str) { let h = 2166136261; for (let i = 0; i < String(str).length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
const PALETTE = [210, 250, 284, 330, 168, 22, 196];
function avatarSVG(seed) {
  const r = mulberry32(seedFrom("av" + seed));
  const h = PALETTE[Math.floor(r() * PALETTE.length)], h2 = (h + 30 + r() * 60) % 360;
  const cx = 20 + r() * 24, cy = 14 + r() * 20;
  return `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${h},72%,62%)"/><stop offset="1" stop-color="hsl(${h2},70%,52%)"/></linearGradient></defs><rect width="64" height="64" fill="url(#g)"/><circle cx="${cx}" cy="${cy}" r="${10 + r() * 12}" fill="hsla(${h2},90%,85%,.5)"/><circle cx="${48 - r() * 18}" cy="${46 + r() * 12}" r="${6 + r() * 8}" fill="hsla(${h},90%,30%,.35)"/></svg>`;
}
function meshSVG(seed, w, h, hueBias) {
  const r = mulberry32(seedFrom("m" + seed));
  const base = hueBias != null ? hueBias : PALETTE[Math.floor(r() * PALETTE.length)];
  const h2 = (base + 40 + r() * 80) % 360, h3 = (base + 300 + r() * 60) % 360;
  let blobs = "";
  for (let i = 0; i < 4; i++) blobs += `<circle cx="${r() * w}" cy="${r() * h}" r="${30 + r() * 70}" fill="hsla(${[base, h2, h3][i % 3]},85%,${64 + r() * 16}%,.55)"/>`;
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="bg${seedFrom(seed)}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${base},68%,72%)"/><stop offset="1" stop-color="hsl(${h2},62%,58%)"/></linearGradient><filter id="b${seedFrom(seed)}"><feGaussianBlur stdDeviation="22"/></filter></defs><rect width="${w}" height="${h}" fill="url(#bg${seedFrom(seed)})"/><g filter="url(#b${seedFrom(seed)})">${blobs}</g></svg>`;
}

/* ---------- count-up ---------- */
function countUp(el) {
  const target = parseFloat(el.dataset.count); if (Number.isNaN(target)) return;
  const dec = +el.dataset.dec || 0, suf = el.dataset.suf || "", pre = el.dataset.pre || "", t0 = performance.now(), dur = 680, ease = t => 1 - Math.pow(1 - t, 3);
  (function s(now) { const p = Math.min((now - t0) / dur, 1); el.textContent = pre + (target * ease(p)).toFixed(dec) + suf; if (p < 1) requestAnimationFrame(s); else el.textContent = pre + target.toFixed(dec) + suf; })(t0);
}


/* ---------- tabs with sliding pill ---------- */
function moveInk(nav) {
  const btn = $("button.on", nav); if (!btn) return;
  let ink = $(".seg-ink", nav); if (!ink) { ink = document.createElement("span"); ink.className = "seg-ink"; nav.appendChild(ink); }
  ink.style.width = btn.offsetWidth + "px"; ink.style.transform = `translateX(${btn.offsetLeft - 6}px)`;
}
function wireTabs(navSel, attr, panelAttr) {
  const nav = $(navSel);
  const buttons = $$("button", nav);
  const panels = $$(`[data-${panelAttr}]`);
  buttons.forEach((btn, i) => {
    const panel = panels.find(p => p.dataset[panelAttr] === btn.dataset[attr]);
    if (!btn.id) btn.id = `${panelAttr}-tab-${i}`;
    if (panel && !panel.id) panel.id = `${panelAttr}-panel-${i}`;
    if (panel) {
      btn.setAttribute("aria-controls", panel.id);
      panel.setAttribute("aria-labelledby", btn.id);
    }
  });
  const activate = (btn, focus = false) => {
    buttons.forEach(b => {
      const on = b === btn;
      b.classList.toggle("on", on);
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    panels.forEach(p => p.classList.toggle("on", p.dataset[panelAttr] === btn.dataset[attr]));
    moveInk(nav);
    if (panelAttr === "opanel" && btn.dataset[attr] === "charts") redrawCharts();
    if (focus) btn.focus();
  };
  buttons.forEach(btn => {
    btn.addEventListener("click", () => activate(btn));
    btn.addEventListener("keydown", e => {
      const i = buttons.indexOf(btn);
      let next = null;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") next = buttons[(i + 1) % buttons.length];
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = buttons[(i - 1 + buttons.length) % buttons.length];
      if (e.key === "Home") next = buttons[0];
      if (e.key === "End") next = buttons[buttons.length - 1];
      if (next) { e.preventDefault(); activate(next, true); }
    });
  });
  activate($("button.on", nav) || buttons[0]);
  requestAnimationFrame(() => moveInk(nav));
}
function activateTab(navSel, attr, value, focus = false) {
  const nav = $(navSel);
  const btn = nav && $(`button[data-${attr}="${value}"]`, nav);
  if (!btn) return;
  btn.click();
  if (focus) btn.focus();
}

/* ---------- bootstrap ---------- */
// POST headers incl. the per-session access token (CSRF/DNS-rebinding guard).
function postHeaders() {
  const h = { "Content-Type": "application/json" };
  const tok = ACCESS_TOKEN || (META && META.token);
  if (tok) h["X-SocioSim-Token"] = tok;
  return h;
}
function authHeaders() {
  const tok = ACCESS_TOKEN || (META && META.token);
  return tok ? { "X-SocioSim-Token": tok } : {};
}
function authQuery() {
  return "";
}
async function fetchProtected(url, opts = {}) {
  const headers = { ...(opts.headers || {}), ...authHeaders() };
  return fetch(url, { ...opts, headers });
}
async function downloadProtected(url, filename) {
  const res = await fetchProtected(url);
  if (!res.ok) return fail(`Export failed (${res.status})`);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl; a.download = filename; document.body.appendChild(a);
  a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
// Run-lens banner: which decision lens (Government / Marketing) is active + what
// the ending output means (mirrors the report's "Run lens" section).
function renderLens(lens) {
  const el = $("#runLens"); if (!el) return;
  if (!lens) { el.hidden = true; return; }
  const badge = (on, cls, label) =>
    `<span class="lens-badge ${cls} ${on ? "on" : "off"}">${label}: ${on ? "active" : "off"}</span>`;
  const fmt2 = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  const readiness = (lens.decision_readiness || [])[0] || "Lens & decision readiness";
  el.innerHTML = badge(lens.government_active, "government", "Government / Regulatory")
    + badge(lens.marketing_active, "marketing", "Marketing")
    + `<details class="lens-details"><summary>${fmt2(readiness)}</summary><ul class="lens-lines">`
    + (lens.lines || []).map(l => `<li>${fmt2(l)}</li>`).join("")
    + "</ul></details>";
  el.hidden = false;
}
async function loadMeta() {
  try { META = await (await fetch("/api/meta")).json(); }
  catch (e) { const el = $("#engLabel"); el.textContent = "Engine offline"; el.classList.add("bad"); return; }
  $("#version").textContent = "v" + META.version;
  ACCESS_TOKEN = META.token || null;
  if (!ACCESS_TOKEN && META.token_required) {
    try { ACCESS_TOKEN = sessionStorage.getItem("sociosim-token"); } catch (e) { ACCESS_TOKEN = null; }
    if (!ACCESS_TOKEN) {
      ACCESS_TOKEN = window.prompt("SocioSim access token") || null;
      try { if (ACCESS_TOKEN) sessionStorage.setItem("sociosim-token", ACCESS_TOKEN); } catch (e) { /* ignore */ }
    }
  }
  $("#ticker").textContent = META.notice;
  $("#engLabel").textContent = "Engine ready";
  $("#llmLabel").textContent = META.llm_available ? "LLM ready" : "LLM idle";
  const ps = $("#preset");
  // group presets by category into <optgroup>s (Regulatory / Research / Business)
  const cats = {};
  for (const [k, p] of Object.entries(META.presets)) (cats[p.category || "General"] ||= []).push([k, p]);
  const order = ["General", "Regulatory", "Research", "Business"];
  ps.innerHTML = order.filter(c => cats[c]).map(c =>
    `<optgroup label="${esc(c)}">` +
    cats[c].map(([k, p]) => `<option value="${k}">${esc(p.label)}</option>`).join("") +
    `</optgroup>`).join("");
  ps.value = "eu_dsa"; ps.addEventListener("change", () => applyPreset(ps.value));
  $("#rates").innerHTML = META.harmful_categories.concat(["ai_generated"]).map(c => rateControl(c)).join("");
  $("#rates").addEventListener("input", e => { if (e.target.id.startsWith("rate_")) setRateLabel(e.target.id.slice(5), e.target.value); updateAriaValueText(e.target); });
  renderGarm(); wireMarketing(); recalcMarketing();
  applyPreset("eu_dsa"); refreshHistory();
}

/* ---------- presets / form ---------- */
function setVal(id, v) {
  const el = $("#" + id); if (!el) return;
  if (el.type === "checkbox") el.checked = !!v; else el.value = v;
  const lab = $("#" + ({
    homophily_rewire_fraction: "homoVal", classifier_precision: "precVal",
    classifier_recall: "recVal", human_review_accuracy: "hraVal",
    follow_rate: "folVal", unfollow_rate: "unfVal", churn_rate: "chuVal",
  }[id]));
  if (lab && v !== "") lab.textContent = (+v).toFixed(2);
  updateAriaValueText(el);
}
const RATE_LIMITS = {
  hate: { max: 0.10, step: 0.001, note: "Rare severe content; default 1.0%, realistic platform prevalence is far lower, upper range is for stress tests." },
  harassment: { max: 0.10, step: 0.001, note: "Stress-test share of all posts." },
  fraud: { max: 0.10, step: 0.001, note: "Fraud/scam prevalence as share of all posts." },
  misinfo: { max: 0.20, step: 0.002, note: "Scenario prevalence; high values are stress tests." },
  adult: { max: 0.10, step: 0.001, note: "Adult-content share of all posts." },
  illegal_goods: { max: 0.05, step: 0.0005, note: "Rare severe category; upper range is for stress tests." },
  self_harm: { max: 0.05, step: 0.0005, note: "Rare severe category; upper range is for stress tests." },
  ai_generated: { max: 0.50, step: 0.005, note: "Synthetic/AI-labelled share can be high in lab scenarios." },
};
function rateMeta(cat) { return RATE_LIMITS[cat] || { max: 0.30, step: 0.005, note: "Share of all posts." }; }
function ratePct(v) {
  const pct = Number(v) * 100;
  return (pct < 1 ? pct.toFixed(2) : pct.toFixed(1)) + "%";
}
function setRateLabel(cat, value) {
  const b = $("#rl_" + cat);
  if (b) b.textContent = ratePct(value);
}
function rateControl(cat) {
  const v = META.defaults[cat] ?? 0.02;
  const lbl = cat.replace(/_/g, " ");
  const meta = rateMeta(cat);
  return `<div class="rate"><label for="rate_${cat}">${lbl}<b id="rl_${cat}">${ratePct(v)}</b><small>${esc(meta.note)}</small></label><input type="range" id="rate_${cat}" aria-label="${lbl} content prevalence, share of all posts" min="0" max="${meta.max}" step="${meta.step}" value="${v}"></div>`;
}
// Documented defaults for every control a preset may touch, so selecting a
// preset yields a CLEAN known state instead of inheriting stale values from a
// previously selected preset (audit S1).
const FIELD_DEFAULTS = {
  label: "", root_seed: 42, tick_hours: 1, verify_replay: true,
  n_replicates: 1, n_agents: "", n_ticks: "", n_topics: 8,
  graph_kind: "ba", graph_m: 5, graph_plc_p: 0.7, graph_k: 10, graph_p: 0.05,
  ftc_enabled: true, feed_strategy: "personalized", eu_optout_rate: 0.20,
  exploration_epsilon: 0.10, human_review_accuracy: 0.92,
  human_review_delay_ticks: 6, appeal_grant_fp_rate: 0.70, ftc_compliance: true,
  ads_enabled: true, holdout_fraction: 0.10, ad_frequency_cap_per_day: 4,
  ad_slot_interval: 5, classifier_mode: "noise", content_mode: "template",
  llm_model: "qwen2.5:0.5b", llm_base_url: "", benchmark: "default",
  classifier_precision: 0.90, classifier_recall: 0.85,
  homophily_rewire_fraction: 0.15, follow_rate: 0, unfollow_rate: 0,
  churn_rate: 0, feed_size: 20,
};
function resetDefaults() {
  const quick = $("input[name=profile][value=quick]"); if (quick) quick.checked = true;
  $$("#jurisdictions input").forEach(i => i.checked = i.value === "EU");
  currentRedTeam = [];
  Object.entries(FIELD_DEFAULTS).forEach(([k, v]) => setVal(k, v));
  $("#campaigns").innerHTML = "";
  $("#content_mode").dispatchEvent(new Event("change"));
  $("#graph_kind").dispatchEvent(new Event("change"));
  syncClassifierMode();
  (META.harmful_categories.concat(["ai_generated"])).forEach(c => {
    const v = META.defaults[c] ?? 0.02; setVal("rate_" + c, v);
    setRateLabel(c, v);
  });
}
// Human-readable labels for fields a preset may set (so the change-summary is
// plain-language, not raw keys). Falls back to the key when unmapped.
const FIELD_LABELS = {
  jurisdictions: "Jurisdiction packs", red_team: "Adversaries",
  ftc_enabled: "FTC pack", ftc_compliance: "FTC ad disclosures",
  feed_strategy: "Feed ranking", eu_optout_rate: "EU opt-out",
  exploration_epsilon: "Exploration ε", human_review_accuracy: "Reviewer accuracy",
  human_review_delay_ticks: "Review delay (ticks)", appeal_grant_fp_rate: "Appeal grant (FP)",
  ads_enabled: "Advertising", holdout_fraction: "RCT holdout",
  ad_frequency_cap_per_day: "Freq cap/day", ad_slot_interval: "Ad slot interval",
  classifier_precision: "Classifier precision", classifier_recall: "Classifier recall",
  classifier_mode: "Classifier mode", benchmark: "Benchmark set",
  homophily_rewire_fraction: "Homophily", feed_size: "Feed size",
};
function prettyField(k, v) {
  if (k === "jurisdictions" || k === "red_team") return `${FIELD_LABELS[k]}: ${(v || []).join(", ") || "none"}`;
  if (k.startsWith("rate_")) return `${k.slice(5).replace(/_/g, " ")} prevalence: ${ratePct(v)}`;
  const lab = FIELD_LABELS[k] || k;
  return `${lab}: ${typeof v === "boolean" ? (v ? "on" : "off") : v}`;
}
function renderPresetSummary(f, sources) {
  const box = $("#presetSummary"), ul = $("#presetSummaryList");
  const keys = Object.keys(f);
  const src = $("#presetSources");
  if (src) src.innerHTML = (sources && sources.length)
    ? "Sources: " + sources.map(esc).join("; ") : "";
  if (!keys.length) { box.hidden = true; return; }  // "custom" preset
  ul.innerHTML = keys.map(k => `<li>${esc(prettyField(k, f[k]))}</li>`).join("");
  box.hidden = false;
}
function applyPreset(name) {
  const p = META.presets[name]; if (!p) return; $("#presetDesc").textContent = p.desc; const f = p.fields;
  resetDefaults();  // clean slate, then apply this preset's overrides (S1)
  if (f.jurisdictions) $$("#jurisdictions input").forEach(i => i.checked = f.jurisdictions.includes(i.value));
  currentRedTeam = f.red_team || [];
  Object.entries(f).forEach(([k, v]) => { if (k === "jurisdictions" || k === "red_team") return; if (k.startsWith("rate_")) { setVal(k, v); setRateLabel(k.slice(5), v); } else setVal(k, v); });
  renderPresetSummary(f, p.sources);  // visible "what this changes" + sources
}
function updateAriaValueText(el) {
  if (!el || el.type !== "range") return;
  const label = el.closest("label")?.querySelector(".lbl")?.textContent?.replace(/\s+/g, " ").trim() || el.id;
  el.setAttribute("aria-valuetext", `${label}: ${Number(el.value).toFixed(2)}`);
}
function syncClassifierMode() {
  const trained = $("#classifier_mode")?.value === "trained";
  ["classifier_precision", "classifier_recall"].forEach(id => {
    const el = $("#" + id); if (!el) return;
    el.disabled = trained;
    el.closest("label")?.classList.toggle("muted", trained);
    el.setAttribute("aria-disabled", String(trained));
    el.title = trained
      ? "Precision/recall targets apply to the calibrated noise model; trained mode uses the measured classifier benchmark."
      : "";
  });
}
$("#content_mode").addEventListener("change", e => $$("[data-llm]").forEach(el => el.hidden = e.target.value === "template"));
$("#graph_kind").addEventListener("change", e => $$("[data-graph]").forEach(el => el.hidden = el.dataset.graph !== e.target.value));
$("#classifier_mode").addEventListener("change", syncClassifierMode);
// Selecting the Calibrated profile configures the graph to its history-matched
// values (Holme–Kim plc, p=0.7) so the form matches RunConfig.calibrated().
$$("input[name=profile]").forEach(r => r.addEventListener("change", e => {
  if (e.target.value === "calibrated" && e.target.checked) {
    setVal("graph_kind", "plc"); setVal("graph_plc_p", 0.7);
    $("#graph_kind").dispatchEvent(new Event("change"));
  }
}));
["homophily_rewire_fraction", "classifier_precision", "classifier_recall", "human_review_accuracy", "follow_rate", "unfollow_rate", "churn_rate"].forEach(id => {
  const lab = { homophily_rewire_fraction: "homoVal", classifier_precision: "precVal", classifier_recall: "recVal", human_review_accuracy: "hraVal", follow_rate: "folVal", unfollow_rate: "unfVal", churn_rate: "chuVal" }[id];
  const el = $("#" + id);
  if (el) {
    updateAriaValueText(el);
    el.addEventListener("input", e => { $("#" + lab).textContent = (+e.target.value).toFixed(2); updateAriaValueText(e.target); });
  }
});

/* ---------- marketing business suite ---------- */
// WFA/GARM Brand Safety Floor + Suitability — 11 categories (+ Misinformation).
const GARM_CATEGORIES = [
  "Adult & explicit sexual content", "Arms & ammunition",
  "Crime & harmful acts / human-rights violations",
  "Death, injury or military conflict", "Online piracy",
  "Hate speech & acts of aggression", "Obscenity & profanity",
  "Illegal drugs / tobacco / alcohol", "Spam or harmful content",
  "Terrorism", "Debated sensitive social issues", "Misinformation",
];
function renderGarm() {
  const el = $("#garmList"); if (el) el.innerHTML = GARM_CATEGORIES.map(c => `<li>${esc(c)}</li>`).join("");
}
// A/B incremental-lift power calc: required N/arm for two proportions at
// 80% power, α=0.05 two-sided (z=1.959964 / 0.841621).
function abCalc() {
  const out = $("#ab_out"); if (!out) return;
  const p1 = (+$("#ab_base").value) / 100, r = (+$("#ab_mde").value) / 100;
  const aud = +$("#ab_aud").value, hold = (+$("#ab_hold").value) / 100;
  if (!(p1 > 0 && p1 < 1 && r > 0 && aud > 0 && hold > 0 && hold < 1)) {
    out.innerHTML = '<div class="mkt-verdict bad">Enter valid inputs.</div>'; return;
  }
  const p2 = Math.min(p1 * (1 + r), 0.999999), pbar = (p1 + p2) / 2;
  const num = 1.959964 * Math.sqrt(2 * pbar * (1 - pbar)) + 0.841621 * Math.sqrt(p1 * (1 - p1) + p2 * (1 - p2));
  const nPer = Math.ceil((num * num) / Math.pow(p2 - p1, 2));
  const control = Math.floor(aud * hold), treat = Math.floor(aud * (1 - hold));
  const powered = control >= nPer;
  out.innerHTML =
    `<div class="mkt-row"><span>Required sample / arm</span><b>${nPer.toLocaleString()}</b></div>` +
    `<div class="mkt-row"><span>Control arm (holdout)</span><b>${control.toLocaleString()}</b></div>` +
    `<div class="mkt-row"><span>Treatment arm</span><b>${treat.toLocaleString()}</b></div>` +
    `<div class="mkt-verdict ${powered ? "ok" : "bad"}">${powered
      ? "✓ Adequately powered to detect this lift"
      : "✗ Under-powered — need " + nPer.toLocaleString() + "/arm; raise audience, MDE, or holdout"}</div>`;
}
function econCalc() {
  const out = $("#ec_out"); if (!out) return;
  const spend = +$("#ec_spend").value, rev = +$("#ec_rev").value;
  const conv = +$("#ec_conv").value, ltv = +$("#ec_ltv").value;
  const roas = spend > 0 ? rev / spend : NaN, cac = conv > 0 ? spend / conv : NaN;
  const ratio = (cac > 0 && ltv > 0) ? ltv / cac : NaN;
  const rc = roas >= 4 ? "ok" : roas >= 2 ? "warn" : "bad";
  const qc = ratio >= 3 ? "ok" : ratio >= 1 ? "warn" : "bad";
  out.innerHTML =
    `<div class="mkt-row"><span>ROAS</span><b class="${rc}">${isFinite(roas) ? roas.toFixed(2) + ":1" : "—"}</b></div>` +
    `<div class="mkt-row"><span>CAC</span><b>${isFinite(cac) ? "$" + cac.toFixed(2) : "—"}</b></div>` +
    `<div class="mkt-row"><span>LTV:CAC</span><b class="${qc}">${isFinite(ratio) ? ratio.toFixed(2) + ":1" : "—"}</b></div>` +
    `<div class="mkt-verdict ${qc}">${isFinite(ratio)
      ? (ratio >= 3 ? "✓ Healthy unit economics (≥3:1)" : ratio >= 1 ? "△ Marginal — below the 3:1 guideline" : "✗ Unsustainable — CAC exceeds LTV")
      : "Enter LTV + conversions for LTV:CAC"}</div>`;
}
function reachCalc() {
  const out = $("#rf_out"); if (!out) return;
  const impr = +$("#rf_impr").value, reach = +$("#rf_reach").value, eff = +$("#rf_eff").value;
  const freq = reach > 0 ? impr / reach : NaN;
  const effReach = isFinite(freq) ? Math.round(reach * Math.min(1, freq / eff)) : NaN;
  const cls = !isFinite(freq) ? "bad" : freq < eff ? "warn" : freq > 7 ? "warn" : "ok";
  out.innerHTML =
    `<div class="mkt-row"><span>Average frequency</span><b class="${cls}">${isFinite(freq) ? freq.toFixed(2) : "—"}</b></div>` +
    `<div class="mkt-row"><span>Approx. effective reach (≥${eff})</span><b>${isFinite(effReach) ? effReach.toLocaleString() : "—"}</b></div>` +
    `<div class="mkt-verdict ${cls}">${isFinite(freq)
      ? (freq < eff ? "△ Below target effective frequency (" + eff + ")" : freq > 7 ? "△ High frequency (>7) — fatigue/waste risk; cap 3–7" : "✓ Within the 3–7 effective-frequency band")
      : "Enter impressions + reach"}</div>`;
}
function recalcMarketing() { abCalc(); econCalc(); reachCalc(); }
function wireMarketing() {
  const nav = $("#mktTabs"); if (!nav) return;
  const buttons = $$("button", nav), panels = $$("[data-mktpanel]");
  buttons.forEach((btn, i) => {
    const panel = panels.find(p => p.dataset.mktpanel === btn.dataset.mkt);
    if (!btn.id) btn.id = `mkt-tab-${i}`;
    if (panel && !panel.id) panel.id = `mkt-panel-${i}`;
    if (panel) {
      btn.setAttribute("aria-controls", panel.id);
      panel.setAttribute("aria-labelledby", btn.id);
    }
  });
  const activate = (btn, focus = false) => {
    buttons.forEach(b => {
      const on = b === btn;
      b.classList.toggle("on", on);
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    panels.forEach(p => p.classList.toggle("on", p.dataset.mktpanel === btn.dataset.mkt));
    if (focus) btn.focus();
  };
  buttons.forEach(btn => {
    btn.addEventListener("click", () => activate(btn));
    btn.addEventListener("keydown", e => {
      const i = buttons.indexOf(btn);
      let next = null;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") next = buttons[(i + 1) % buttons.length];
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = buttons[(i - 1 + buttons.length) % buttons.length];
      if (e.key === "Home") next = buttons[0];
      if (e.key === "End") next = buttons[buttons.length - 1];
      if (next) { e.preventDefault(); activate(next, true); }
    });
  });
  activate($("button.on", nav) || buttons[0]);
  ["ab_base", "ab_mde", "ab_aud", "ab_hold", "ec_spend", "ec_rev", "ec_conv",
   "ec_ltv", "rf_impr", "rf_reach", "rf_eff"].forEach(id => {
    const el = $("#" + id); if (el) el.addEventListener("input", recalcMarketing);
  });
}

/* ---------- campaign editor (S3) ---------- */
const AGE_SEGMENTS = ["all", "13-17", "18-24", "25-34", "35-49", "50-64", "65+"];
function campaignRow(c = {}) {
  const d = document.createElement("div"); d.className = "camp-row";
  const segOpts = AGE_SEGMENTS.map(s => `<option value="${s}"${(c.segment || "all") === s ? " selected" : ""}>${s === "all" ? "All ages" : s}</option>`).join("");
  const mktOpts = ['<option value="any">Any market</option>']
    .concat([...Array(8).keys()].map(t => `<option value="${t}"${String(c.market) === String(t) ? " selected" : ""}>Topic ${t}</option>`)).join("");
  d.innerHTML = `<input class="cf-adv" placeholder="Advertiser" aria-label="advertiser" value="${esc(c.advertiser || "")}">`
    + `<input class="cf-bid" type="number" step="0.1" min="0" title="bid per impression" aria-label="bid" value="${c.bid ?? 2}">`
    + `<input class="cf-bud" type="number" step="1" min="0" title="budget" aria-label="budget" value="${c.budget ?? 100}">`
    + `<input class="cf-ctr" type="number" step="0.001" min="0" max="1" title="base CTR" aria-label="base CTR" value="${c.base_ctr ?? 0.012}">`
    + `<input class="cf-cvr" type="number" step="0.01" min="0" max="1" title="base CVR" aria-label="base CVR" value="${c.base_cvr ?? 0.05}">`
    + `<input class="cf-val" type="number" step="0.1" min="0" title="conversion value" aria-label="conversion value" value="${c.conversion_value ?? 1}">`
    + `<input class="cf-ltv" type="number" step="0.1" min="0" title="LTV multiplier" aria-label="LTV multiplier" value="${c.ltv_multiplier ?? 3}">`
    + `<input class="cf-attr" type="number" step="1" min="1" title="attribution window in ticks" aria-label="attribution window ticks" value="${c.attribution_window_ticks ?? 168}">`
    + `<select class="cf-seg" title="audience segment" aria-label="audience segment">${segOpts}</select>`
    + `<select class="cf-mkt" title="market / topic" aria-label="market topic">${mktOpts}</select>`
    + `<button type="button" class="cf-del" title="remove" aria-label="remove campaign">×</button>`;
  d.querySelector(".cf-del").addEventListener("click", () => d.remove());
  return d;
}
$("#addCampaign")?.addEventListener("click", () => $("#campaigns").appendChild(campaignRow()));

function collectCampaigns() {
  return $$("#campaigns .camp-row").map((r, i) => ({
    id: "c" + (i + 1),
    advertiser: r.querySelector(".cf-adv").value || "Advertiser",
    bid: +r.querySelector(".cf-bid").value, budget: +r.querySelector(".cf-bud").value,
    base_ctr: +r.querySelector(".cf-ctr").value, base_cvr: +r.querySelector(".cf-cvr").value,
    conversion_value: +r.querySelector(".cf-val").value,
    ltv_multiplier: +r.querySelector(".cf-ltv").value,
    attribution_window_ticks: +r.querySelector(".cf-attr").value,
    segment: r.querySelector(".cf-seg").value, market: r.querySelector(".cf-mkt").value,
  }));
}

function collect() {
  const v = id => { const e = $("#" + id); return e && e.value !== "" ? e.value : null; };
  const num = id => { const x = v(id); return x == null ? null : +x; }, chk = id => $("#" + id).checked, checked = sel => $$(sel + " input:checked").map(i => i.value);
  const body = {
    label: v("label") || "", profile: $("input[name=profile]:checked").value, root_seed: num("root_seed"), tick_hours: num("tick_hours"), verify_replay: chk("verify_replay"), n_replicates: num("n_replicates"),
    n_agents: num("n_agents"), n_ticks: num("n_ticks"), n_topics: num("n_topics"), graph_kind: v("graph_kind"), graph_m: num("graph_m"), graph_plc_p: num("graph_plc_p"), graph_k: num("graph_k"), graph_p: num("graph_p"), homophily_rewire_fraction: num("homophily_rewire_fraction"),
    benchmark: v("benchmark"), follow_rate: num("follow_rate"), unfollow_rate: num("unfollow_rate"), churn_rate: num("churn_rate"),
    content_mode: v("content_mode"), classifier_mode: v("classifier_mode"), llm_model: v("llm_model"), llm_base_url: v("llm_base_url"), jurisdictions: checked("#jurisdictions"), ftc_enabled: chk("ftc_enabled"),
    classifier_precision: num("classifier_precision"), classifier_recall: num("classifier_recall"), human_review_accuracy: num("human_review_accuracy"), human_review_delay_ticks: num("human_review_delay_ticks"), appeal_grant_fp_rate: num("appeal_grant_fp_rate"),
    feed_strategy: v("feed_strategy"), eu_optout_rate: num("eu_optout_rate"), exploration_epsilon: num("exploration_epsilon"), feed_size: num("feed_size"),
    ads_enabled: chk("ads_enabled"), ftc_compliance: chk("ftc_compliance"), holdout_fraction: num("holdout_fraction"), ad_frequency_cap_per_day: num("ad_frequency_cap_per_day"), ad_slot_interval: num("ad_slot_interval"), red_team: currentRedTeam,
  };
  (META.harmful_categories.concat(["ai_generated"])).forEach(c => body["rate_" + c] = num("rate_" + c));
  const campaigns = collectCampaigns();
  if (campaigns.length) body.campaigns = campaigns;
  return body;
}
function stage(id) { ["idle", "running", "errstage", "results"].forEach(s => $("#" + s).hidden = s !== id); }
function fail(msg) { if (polling) clearInterval(polling); polling = null; if (cmpPolling) clearInterval(cmpPolling); cmpPolling = null; $("#runBtn").disabled = false; $("#errText").textContent = msg; stage("errstage"); }

/* ---------- A/B compare (baseline vs intervention) ---------- */
let cmpPolling = null;
$("#cmpBtn")?.addEventListener("click", async () => {
  const body = collect();
  if (!body.jurisdictions.length) return fail("Select at least one jurisdiction pack (Moderation tab).");
  try { body.intervention = JSON.parse($("#cmpIntervention").value); }
  catch (e) { return fail("Invalid intervention."); }
  body.compare_replicates = +($("#cmpReplicates").value || 5);
  stage("running"); $("#runPhase").textContent = "comparing";
  $("#meterFill").style.width = "45%"; $("#runDetail").textContent = "baseline vs intervention (common random numbers)…";
  let res;
  try { res = await (await fetch("/api/compare", { method: "POST", headers: postHeaders(), body: JSON.stringify(body) })).json(); }
  catch (err) { return fail(String(err)); }
  if (res.error) return fail(res.error);
  cmpPolling = setInterval(() => pollCompare(res.job_id), 400);
});
async function pollCompare(id) {
  let j; try { j = await (await fetch("/api/job/" + id, { headers: authHeaders() })).json(); } catch (e) { return; }
  if (j.status === "running") { $("#runPhase").textContent = j.phase || "comparing"; }
  else if (j.status === "done") { clearInterval(cmpPolling); cmpPolling = null; renderCompare(j.result); }
  else if (j.status === "error") fail(j.error || "compare failed");
}
function renderCompare(r) {
  stage("results");
  renderLens(null);
  currentRunId = null;
  $("#runMeta").innerHTML = `A/B compare · baseline ${esc((r.baseline_jurisdictions || []).join("+"))} vs intervention ${esc((r.intervention_jurisdictions || []).join("+"))} · ${r.n_replicates} replicates · ${esc(r.provenance || "")}`;
  $("#footHash").textContent = "";
  const seal = $("#seal"); seal.className = "seal ok"; $("#sealTxt").textContent = "compare complete";
  const msg = `<p class="dim small">This is a compare-only result. Open Compare for paired Monte Carlo deltas; run a simulation for this tab's single-run output.</p>`;
  $("#cards").innerHTML = msg;
  $("#feedWrap").innerHTML = msg;
  $("#charts").innerHTML = msg;
  $("#network").innerHTML = msg;
  $("#cascade").innerHTML = msg;
  $("#confusion").innerHTML = msg;
  $("#fairness").innerHTML = msg;
  $("#ads").innerHTML = msg;
  $("#implaus").textContent = "Compare mode does not produce a single-run calibration score.";
  $("#calib").innerHTML = msg;
  $("#audit").innerHTML = msg;
  $("#rawReport").textContent = "COMPARE RUN\n" + JSON.stringify(r.compare || {}, null, 2);
  ["expReport", "expJson", "expTransparency", "expEvents"].forEach(id => { const el = $("#" + id); if (el) { el.removeAttribute("href"); el.hidden = true; } });
  const c = r.compare || {};
  const rows = Object.entries(c).map(([k, m]) => {
    const lo = m.delta_ci[0], hi = m.delta_ci[1], excludesZero = (lo > 0 || hi < 0);
    return `<tr><td>${esc(k.replace(/_/g, " "))}</td><td class="num">${fmt(m.baseline_median, 4)}</td><td class="num">${fmt(m.intervention_median, 4)}</td><td class="num">${fmt(m.delta_median, 4)}</td><td class="num">[${fmt(lo, 4)}, ${fmt(hi, 4)}]</td><td>${excludesZero ? '<b style="color:var(--blue)">CI excludes 0</b>' : '<span class="dim">includes 0</span>'}</td></tr>`;
  }).join("");
  $("#compare").innerHTML = `<table class="read"><thead><tr><th>metric</th><th>baseline</th><th>intervention</th><th>Δ</th><th>Δ 95% CI</th><th>single-metric screen</th></tr></thead><tbody>${rows}</tbody></table><p class="hint">Δ = intervention − baseline (common random numbers; mc-replicated). "CI excludes 0" is a per-metric interval screen, not a multiple-comparison-adjusted discovery claim.</p>`;
  activateTab("#outTabs", "otab", "compare");
}
$("#cfgForm").addEventListener("submit", async e => {
  e.preventDefault(); const body = collect();
  if (!body.jurisdictions.length) return fail("Select at least one jurisdiction pack (Moderation tab).");
  $("#runBtn").disabled = true; stage("running"); $("#meterFill").style.width = "0%"; $("#runPhase").textContent = "initializing"; $("#runDetail").textContent = "building world…";
  let res; try { res = await (await fetch("/api/run", { method: "POST", headers: postHeaders(), body: JSON.stringify(body) })).json(); } catch (err) { return fail(String(err)); }
  if (res.error) return fail(res.error); polling = setInterval(() => poll(res.job_id), 350);
});
async function poll(id) {
  let j; try { j = await (await fetch("/api/job/" + id, { headers: authHeaders() })).json(); } catch (e) { return; }
  if (j.status === "running") { const p = Math.round((j.progress || 0) * 100); $("#meterFill").style.width = p + "%"; $("#runPhase").textContent = j.phase || "simulating"; $("#runDetail").textContent = j.tick ? `tick ${j.tick} / ${j.n_ticks || "?"} · ${p}%` : (j.phase || "preparing…"); }
  else if (j.status === "done") { clearInterval(polling); polling = null; $("#runBtn").disabled = false; currentRunId = id; render(j.result); refreshHistory(); }
  else if (j.status === "error") fail(j.error || "unknown error");
}

/* ---------- charts (light theme, draw-in) ---------- */
const NS = "http://www.w3.org/2000/svg", AXIS = "#e4e4e9";
const svg = (w, h) => { const s = document.createElementNS(NS, "svg"); s.setAttribute("viewBox", `0 0 ${w} ${h}`); return s; };
const elm = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
function barChart(data, { w = 460, h = 170, color = "#0a84ff", labelEvery = 0 } = {}) {
  const s = svg(w, h), p = { l: 30, r: 8, t: 8, b: 18 }, iw = w - p.l - p.r, ih = h - p.t - p.b, max = Math.max(...data.map(d => d[1]), 1), bw = iw / data.length;
  s.appendChild(elm("line", { x1: p.l, y1: p.t + ih, x2: p.l + iw, y2: p.t + ih, stroke: AXIS }));
  [0, max].forEach(g => { const t = elm("text", { x: p.l - 5, y: p.t + ih - (g / max) * ih + 3, "text-anchor": "end" }); t.textContent = g; s.appendChild(t); });
  data.forEach((d, i) => { const bh = (d[1] / max) * ih, r = elm("rect", { x: p.l + i * bw + bw * .14, y: p.t + ih - bh, width: bw * .72, height: bh, fill: color, rx: 2, class: "bar-g" }); r.style.animationDelay = (i * 14) + "ms"; s.appendChild(r); if (labelEvery && i % labelEvery === 0) { const t = elm("text", { x: p.l + i * bw + bw / 2, y: h - 5, "text-anchor": "middle" }); t.textContent = d[0]; s.appendChild(t); } });
  return s;
}
const path = (vals, X, Y, c) => elm("path", { d: "M " + vals.map((v, i) => `${X(i)} ${Y(v)}`).join(" L "), fill: "none", stroke: c, "stroke-width": 2, "stroke-linejoin": "round", class: "draw" });
function areaChart(vals, { w = 460, h = 170, color = "#30c0b4", xlabels = [] } = {}) {
  const s = svg(w, h), p = { l: 30, r: 8, t: 8, b: 18 }, iw = w - p.l - p.r, ih = h - p.t - p.b, max = Math.max(...vals, 1), X = i => p.l + (i / (vals.length - 1 || 1)) * iw, Y = v => p.t + ih - (v / max) * ih;
  s.appendChild(elm("line", { x1: p.l, y1: p.t + ih, x2: p.l + iw, y2: p.t + ih, stroke: AXIS }));
  [0, max].forEach(g => { const t = elm("text", { x: p.l - 5, y: Y(g) + 3, "text-anchor": "end" }); t.textContent = g; s.appendChild(t); });
  s.appendChild(elm("path", { d: "M " + vals.map((v, i) => `${X(i)} ${Y(v)}`).join(" L ") + ` L ${X(vals.length - 1)} ${p.t + ih} L ${X(0)} ${p.t + ih} Z`, fill: color, opacity: .12 }));
  s.appendChild(path(vals, X, Y, color));
  vals.forEach((v, i) => { if (xlabels[i]) { const t = elm("text", { x: X(i), y: h - 5, "text-anchor": "middle" }); t.textContent = xlabels[i]; s.appendChild(t); } });
  return s;
}
function dualLine(a, b, { w = 460, h = 170 } = {}) {
  const s = svg(w, h), p = { l: 30, r: 8, t: 8, b: 14 }, iw = w - p.l - p.r, ih = h - p.t - p.b, max = Math.max(...a, ...b, 1), X = i => p.l + (i / (a.length - 1 || 1)) * iw, Y = v => p.t + ih - (v / max) * ih;
  s.appendChild(elm("line", { x1: p.l, y1: p.t + ih, x2: p.l + iw, y2: p.t + ih, stroke: AXIS }));
  [["#30c0b4", a], ["#0a84ff", b]].forEach(([c, vals]) => s.appendChild(path(vals, X, Y, c)));
  return s;
}
function activateDraw(root) { $$("path.draw", root).forEach(p => p.style.setProperty("--len", p.getTotalLength())); }
let _charts = null;
function tableAlt(headers, rows) {
  const det = document.createElement("details"); det.className = "chart-data-table";
  const sum = document.createElement("summary"); sum.textContent = "Data table"; det.appendChild(sum);
  const tab = document.createElement("table");
  const hrow = document.createElement("tr");
  headers.forEach(h => { const th = document.createElement("th"); th.textContent = h; hrow.appendChild(th); });
  const thead = document.createElement("thead"); thead.appendChild(hrow); tab.appendChild(thead);
  const tbody = document.createElement("tbody");
  rows.forEach(row => { const tr = document.createElement("tr"); row.forEach(v => { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }); tbody.appendChild(tr); });
  tab.appendChild(tbody); det.appendChild(tab); return det;
}
function renderCharts(ch) {
  _charts = ch; const host = $("#charts"); host.innerHTML = "";
  const hours = [...Array(24)].map((_, i) => (i % 6 === 0 ? i : ""));
  const cc = (title, sub, node, alt) => { const d = document.createElement("div"); d.className = "chart"; d.innerHTML = `<div class="ct">${title}</div><div class="cs">${sub}</div>`; node.setAttribute("role", "img"); node.setAttribute("aria-label", `${title} — ${sub}`); d.appendChild(node); if (alt) d.appendChild(alt); return d; };
  const diurnalRows = ch.diurnal.map((v, i) => [i, v]);
  host.appendChild(cc("Diurnal Posting", "posts by hour of day", areaChart(ch.diurnal, { color: "#30c0b4", xlabels: hours }), tableAlt(["Hour", "Posts"], diurnalRows)));
  const degRows = ch.degree_hist.map(d => [Math.round(d[0]), d[1]]);
  host.appendChild(cc("Degree Distribution", "agents by follower count", barChart(degRows, { color: "#0a84ff", labelEvery: 4 }), tableAlt(["Degree", "Count"], degRows)));
  const tlRows = ch.timeline_posts.map((v, i) => [i, v, ch.timeline_removed[i] ?? 0]);
  host.appendChild(cc("Activity Timeline", "posts (teal) vs moderation actions (blue)", dualLine(ch.timeline_posts, ch.timeline_removed), tableAlt(["Tick", "Posts", "Moderation Actions"], tlRows)));
  const cascRows = (ch.cascade || []).map(d => [d[0], d[1]]);
  host.appendChild(cc("Cascade Sizes", "share-tree size distribution", barChart(ch.cascade, { color: "#ff9500", labelEvery: Math.max(1, Math.ceil(ch.cascade.length / 8)) }), tableAlt(["Size", "Count"], cascRows)));
  requestAnimationFrame(() => activateDraw(host));
}
function redrawCharts() { if (_charts) renderCharts(_charts); }

/* ---------- network topology (deterministic force layout) ---------- */
let _net3dRaf = null;
function renderNetwork(gs) {
  if (_net3dRaf) { cancelAnimationFrame(_net3dRaf); _net3dRaf = null; }
  const host = $("#network"); if (!host) return;
  if (!gs || !gs.nodes || !gs.nodes.length) { host.innerHTML = `<p class="dim small">No graph sample for this run.</p>`; return; }
  const W = 640, H = 440;
  host.innerHTML = `<div class="chart" style="position:relative"><div class="ct">Social Graph — 3D perspective (top ${gs.nodes.length} hubs)</div><div class="cs">depth = front/back · size = degree · colour = ideology · drag to rotate · hover a node to inspect</div><canvas id="net3d" width="${W}" height="${H}" style="width:100%" role="img" aria-label="3D perspective view of the sampled social network: ${gs.nodes.length} highest-degree agents coloured by ideology with edges among them"></canvas><div id="net3dTip" class="net-tip" hidden></div></div>`;
  const cv = $("#net3d"); if (!cv) return;
  const ctx = cv.getContext("2d");
  const nodes = gs.nodes.map(n => ({ ...n })), idx = {};
  nodes.forEach((n, i) => idx[n.id] = i);
  const links = gs.edges.filter(([u, v]) => idx[u] != null && idx[v] != null).map(([u, v]) => [idx[u], idx[v]]);
  const rnd = mulberry32(seedFrom("net3d" + nodes.length));
  nodes.forEach(n => { n.x = (rnd() - 0.5) * 240; n.y = (rnd() - 0.5) * 240; n.z = (rnd() - 0.5) * 240; n.vx = n.vy = n.vz = 0; });
  for (let it = 0; it < 120; it++) {            // deterministic 3D force layout
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z, d2 = dx * dx + dy * dy + dz * dz + 0.01, f = 900 / d2;
      a.vx += dx * f; a.vy += dy * f; a.vz += dz * f; b.vx -= dx * f; b.vy -= dy * f; b.vz -= dz * f;
    }
    for (const [a, b] of links) {
      const na = nodes[a], nb = nodes[b];
      const dx = nb.x - na.x, dy = nb.y - na.y, dz = nb.z - na.z, d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1, f = (d - 50) * 0.02;
      na.vx += dx / d * f; na.vy += dy / d * f; na.vz += dz / d * f; nb.vx -= dx / d * f; nb.vy -= dy / d * f; nb.vz -= dz / d * f;
    }
    for (const n of nodes) {
      n.vx -= n.x * 0.001; n.vy -= n.y * 0.001; n.vz -= n.z * 0.001;
      n.x += Math.max(-8, Math.min(8, n.vx)); n.y += Math.max(-8, Math.min(8, n.vy)); n.z += Math.max(-8, Math.min(8, n.vz));
      n.vx *= 0.85; n.vy *= 0.85; n.vz *= 0.85;
    }
  }
  const maxDeg = Math.max(...nodes.map(n => n.deg), 1);
  const col = g => g === "L" ? "#0a84ff" : g === "R" ? "#ff9500" : "#86868b";
  const cx = W / 2, cy = H / 2, focal = 520;
  let lastProj = null;
  function draw(angle) {
    ctx.clearRect(0, 0, W, H);
    const ca = Math.cos(angle), sa = Math.sin(angle);
    const proj = nodes.map(n => {
      const rx = n.x * ca - n.z * sa, rz = n.x * sa + n.z * ca;   // rotate about Y
      const s = focal / (focal + rz + 280);
      return { px: cx + rx * s, py: cy + n.y * s, s, rz, n };
    });
    lastProj = proj;
    ctx.lineWidth = 0.6;
    for (const [a, b] of links) {
      ctx.strokeStyle = "rgba(150,150,160,0.32)";
      ctx.beginPath(); ctx.moveTo(proj[a].px, proj[a].py); ctx.lineTo(proj[b].px, proj[b].py); ctx.stroke();
    }
    for (const p of proj.slice().sort((u, v) => u.rz - v.rz)) {   // back-to-front
      ctx.globalAlpha = Math.max(0.35, Math.min(1, p.s));
      ctx.fillStyle = col(p.n.group);
      ctx.beginPath(); ctx.arc(p.px, p.py, Math.max(1, (2 + 6 * Math.sqrt(p.n.deg / maxDeg)) * p.s), 0, 6.2832); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  // Interactive: drag to rotate (works even with reduced motion); otherwise
  // auto-rotates. Drag pauses the auto-spin.
  let angle = 0, dragging = false, lastX = 0;
  cv.style.cursor = "grab";
  cv.addEventListener("pointerdown", e => { dragging = true; lastX = e.offsetX; cv.style.cursor = "grabbing"; try { cv.setPointerCapture(e.pointerId); } catch (_) {} });
  const tip = $("#net3dTip");
  cv.addEventListener("pointermove", e => {
    if (dragging) { angle += (e.offsetX - lastX) * 0.01; lastX = e.offsetX; draw(angle); return; }
    if (!lastProj || !tip) return;                       // hover-pick nearest node
    const sx = cv.width / (cv.clientWidth || cv.width), sy = cv.height / (cv.clientHeight || cv.height);
    const mx = e.offsetX * sx, my = e.offsetY * sy;
    let best = null, bd = 1e9;
    for (const p of lastProj) { const dx = p.px - mx, dy = p.py - my, d = dx * dx + dy * dy; if (d < bd) { bd = d; best = p; } }
    if (best && bd < 220) {
      const g = best.n.group === "L" ? "left" : best.n.group === "R" ? "right" : best.n.group;
      tip.hidden = false; tip.style.left = (e.offsetX + 12) + "px"; tip.style.top = (e.offsetY + 8) + "px";
      tip.textContent = `agent ${best.n.id} · degree ${best.n.deg} · ${g}`;
    } else { tip.hidden = true; }
  });
  cv.addEventListener("pointerleave", () => { if (tip) tip.hidden = true; });
  cv.addEventListener("pointerup", () => { dragging = false; cv.style.cursor = "grab"; });
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) { draw(0.5); return; }   // static auto-view; drag still rotates
  (function frame() { if (!dragging) angle += 0.006; draw(angle); _net3dRaf = requestAnimationFrame(frame); })();
}

/* ---------- cascade propagation replay ---------- */
function renderCascade(t) {
  const host = $("#cascade"); if (!host) return;
  if (!t || !t.nodes || t.nodes.length < 2) { host.innerHTML = `<p class="dim small">No multi-post cascade (share tree) in this run.</p>`; return; }
  const W = 640, H = 380, nodes = t.nodes.map(n => ({ ...n })), idx = {};
  nodes.forEach((n, i) => idx[n.id] = i);
  const maxDepth = Math.max(...nodes.map(n => n.depth), 1);
  const byDepth = {};
  nodes.forEach(n => { (byDepth[n.depth] = byDepth[n.depth] || []).push(n); });
  Object.values(byDepth).forEach(arr => arr.forEach((n, i) => {
    n.x = 50 + (n.depth / maxDepth) * (W - 100);
    n.y = 30 + (i + 1) / (arr.length + 1) * (H - 60);
  }));
  // reveal in posting-time order -> propagation replay (motion communicates spread)
  [...nodes].sort((a, b) => a.tick - b.tick).forEach((n, i) => n.delay = i * 45);
  const e = t.edges.map(([u, v]) => { const a = nodes[idx[u]], b = nodes[idx[v]]; return `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="#e4e4e9" stroke-width="1"/>`; }).join("");
  const c = nodes.map(n => `<circle class="casc-node" style="animation-delay:${n.delay}ms" cx="${n.x.toFixed(1)}" cy="${n.y.toFixed(1)}" r="${(5 - n.depth * 0.5 < 3 ? 3 : 5 - n.depth * 0.5).toFixed(1)}" fill="#ff9500"><title>${esc(n.id)} · tick ${n.tick} · depth ${n.depth}</title></circle>`).join("");
  host.innerHTML = `<div class="chart"><div class="ct">Largest cascade — ${t.size} posts</div><div class="cs">share tree, left→right by depth; nodes appear in posting-time order (propagation replay)</div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Largest share cascade: ${nodes.length} posts revealed in posting-time order showing propagation">${e}${c}</svg></div>`;
}

/* ---------- interval bar ---------- */
function ibar(lo, hi, pt, lo0, hi0, cls = "") {
  if (lo == null) return `<div class="bar"><span class="axis"></span></div>`;
  const sp = Math.max(hi0 - lo0, 1e-9), L = v => Math.max(0, Math.min(100, 100 * (v - lo0) / sp));
  return `<div class="bar"><span class="axis"></span><span class="tk" style="left:0"></span><span class="tk" style="left:100%"></span><span class="span ${cls}" style="left:${L(lo)}%;width:${Math.max(L(hi) - L(lo), .6)}%"></span><span class="pt ${cls}" style="left:${L(pt)}%"></span></div>`;
}

/* ---------- render ---------- */
function metric(k, count, { dec = 0, suf = "", pre = "", ci = "" } = {}) {
  const cnt = count == null || Number.isNaN(count) ? `<div class="v">—</div>` : `<div class="v"><span data-count="${count}" data-dec="${dec}" data-suf="${suf}" data-pre="${pre}">${pre}0${suf}</span></div>`;
  return `<div class="card"><div class="k">${k}</div>${cnt}${ci}</div>`;
}
function render(r) {
  stage("results");
  const s = r.summary, m = r.manifest, mod = s.moderation, ap = s.appeals, he = s.harmful_exposure, w = s.welfare;
  const modeTag = r.mode === "research" ? ` · research ×${r.n_replicates} (mc-replicated CIs)` : " · preview (within-run CIs)";
  $("#runMeta").innerHTML = `cfg ${m.config_hash.slice(0, 10)} · seed ${m.root_seed} · ${r.n_events} events · ${r.elapsed_s}s · packs ${Object.keys(m.pack_versions).join(",")}` + modeTag + (r.content_mode !== "template" ? ` · ${r.content_mode}: ${r.n_llm_calls} calls / ${r.n_degradations} degraded` : "");
  renderLens(r.lens);
  $("#footHash").textContent = "stream " + m.stream_hash.slice(0, 16);
  const seal = $("#seal"); seal.className = "seal";
  if (!r.replay.checked) $("#sealTxt").textContent = "replay skipped";
  else if (r.replay.ok) { seal.classList.add("ok"); $("#sealTxt").textContent = "replay verified"; }
  else { seal.classList.add("bad"); $("#sealTxt").textContent = "replay mismatch"; }
  if (currentRunId) {
    $("#expReport").hidden = false; $("#expJson").hidden = false; $("#expTransparency").hidden = false; $("#expEvents").hidden = false;
    $("#expReport").href = `/api/runs/${currentRunId}/export?fmt=report`;
    $("#expJson").href = `/api/runs/${currentRunId}/export?fmt=json`;
    $("#expTransparency").href = `/api/runs/${currentRunId}/export?fmt=transparency`;
    $("#expEvents").href = `/api/runs/${currentRunId}/events`;
  }

  const heB = ibar(he.ci[0], he.ci[1], he.rate, 0, Math.max(he.ci[1] * 1.3, .05));
  const wB = ibar(w.ci[0], w.ci[1], w.mean, Math.min(w.ci[0], -.1), Math.max(w.ci[1], .1), "teal");
  $("#cards").innerHTML = [
    metric("Harmful Exposure", he.rate * 100, { dec: 2, suf: "%", ci: `<div class="ci">95% within-run ${pct(he.ci[0])}–${pct(he.ci[1])}</div>${heB}` }),
    metric("Mod Precision", mod.precision, { dec: 3 }), metric("Mod Recall", mod.recall, { dec: 3 }),
    metric("Notices Sent", s.notices.notices_sent, { ci: `<div class="ci">coverage ${pct(s.notices.removal_notice_coverage)}</div>` }),
    metric("Appeals Filed", ap.filed, { ci: `<div class="ci">granted ${pct(ap.granted_rate)}</div>` }),
    metric("Welfare Proxy", w.mean, { dec: 3, ci: `<div class="ci">95% within-run ${fmt(w.ci[0], 2)}–${fmt(w.ci[1], 2)}</div>${wB}` }),
    metric("Posts", s.n_posts, { ci: `<div class="ci">${s.n_impressions} impressions</div>` }),
    metric("Max Cascade", s.cascades.max, { ci: `<div class="ci">${s.cascades.n} trees</div>` }),
  ].join("");
  $$(".card").forEach((c, i) => { c.style.animationDelay = (i * 45) + "ms"; });
  setTimeout(() => $$("#cards .v [data-count]").forEach(countUp), 120);

  renderFeed(r.feed || []);
  renderCharts(r.charts);
  renderNetwork(r.summary.graph && r.summary.graph.graph_sample);
  renderCascade(r.charts && r.charts.cascade_tree);
  renderAudit(r.event_sample, r.event_kinds);

  $("#confusion").innerHTML = `<div class="cell tp"><div class="cl">true positive</div><div class="cv">${mod.tp}</div></div><div class="cell fp"><div class="cl">false positive</div><div class="cv">${mod.fp}</div></div><div class="cell fn"><div class="cl">false negative</div><div class="cv">${mod.fn}</div></div><div class="cell tn"><div class="cl">true negative</div><div class="cv">${mod.tn}</div></div>`;
  $("#fairness").innerHTML = Object.entries(s.fairness).map(([dim, gs]) => `<div class="fgrp">${esc(dim.replace(/_/g, " "))}</div><table class="read"><thead><tr><th>group</th><th>FPR</th><th>FNR</th><th>posts</th><th>harm</th><th>benign</th><th>status</th></tr></thead><tbody>${Object.entries(gs).map(([g, d]) => `<tr><td>${esc(g)}</td><td class="num">${fmt(d.fpr, 4)}</td><td class="num">${fmt(d.fnr, 3)}</td><td class="num">${d.n_posts}</td><td class="num">${d.n_harmful ?? "—"}</td><td class="num">${d.n_benign ?? "—"}</td><td>${d.insufficient_sample ? "directional only" : "screened"}</td></tr>`).join("")}</tbody></table>`).join("");

  renderAds(Object.values(s.ads));
  $("#compare").innerHTML = `<p class="dim small">No comparison run for this result.</p>`;

  $("#implaus").textContent = `implausibility I = ${fmt(r.implausibility, 2)} (dominant: ${esc(r.implausibility_dominant_metric || "n/a")}; history-matching cutoff 3.0; lower = closer to published aggregate benchmarks)`;
  $("#calib").innerHTML = Object.entries(r.targets).map(([name, spec]) => {
    const obs = r.observed[name]; if (obs == null) return "";
    const lo0 = spec.value - 3 * spec.tolerance, hi0 = spec.value + 3 * spec.tolerance, sp = Math.max(hi0 - lo0, 1e-9), L = v => Math.max(0, Math.min(100, 100 * (v - lo0) / sp)), inb = Math.abs(obs - spec.value) <= spec.tolerance;
    return `<div class="calib-row"><span class="nm">${esc(name.replace(/_/g, " "))}</span><div class="ctrack"><span class="tol" style="left:${L(spec.value - spec.tolerance)}%;width:${L(spec.value + spec.tolerance) - L(spec.value - spec.tolerance)}%"></span><span class="ctr" style="left:${L(spec.value)}%"></span><span class="obs ${inb ? "in" : "out"}" style="left:${L(obs)}%"></span></div><span class="vl">${fmt(obs, 3)} <span class="dim">/ ${spec.value}</span></span></div>`;
  }).join("");
  let prefix = "";
  if (r.mc) {
    prefix += `MONTE CARLO (provenance: mc-replicated, ${r.n_replicates} replicates)\n`;
    for (const [k, d] of Object.entries(r.mc))
      prefix += `  ${k}: median ${(+d.median).toFixed(4)}  95% [${(+d.ci[0]).toFixed(4)}, ${(+d.ci[1]).toFixed(4)}]\n`;
    prefix += "\n";
  }
  if (r.transparency) {
    const t = r.transparency;
    prefix += `TRANSPARENCY REPORT: notices ${t.notices_sent} · appeals ${t.appeals.filed} filed / ${t.appeals.granted} granted · human reviews ${t.human_reviews} · deadline misses ${t.deadline_misses} · max retention ${t.max_retention_months}mo\n\n`;
  }
  $("#rawReport").textContent = prefix + (r.report_md || JSON.stringify(r.manifest, null, 2));
  activateTab("#outTabs", "otab", "overview");
}

function renderAudit(events, kinds) {
  const host = $("#audit"); if (!host) return;
  if (!events || !events.length) { host.innerHTML = `<p class="dim small">No event sample for this run.</p>`; return; }
  const opts = ['<option value="">all kinds</option>']
    .concat((kinds || []).map(k => `<option value="${esc(k)}">${esc(k)}</option>`)).join("");
  host.innerHTML = `<div class="ahead"><select id="auditKind">${opts}</select> <span class="dim small">sampled audit events (up to 60 per kind; full append-only log on disk at the run's out_dir/events.jsonl)</span></div><div id="auditRows"></div>`;
  const draw = (filter) => {
    const rows = events.filter(e => !filter || e.kind === filter).map(e =>
      `<tr><td class="num">${e.tick}</td><td>${esc(e.kind)}</td><td class="num">${e.actor_id}</td><td>${esc(e.content_id || "")}</td><td class="mono small">${esc(JSON.stringify(e.data || {}).slice(0, 90))}</td></tr>`).join("");
    $("#auditRows").innerHTML = `<table class="read"><thead><tr><th>tick</th><th>kind</th><th>actor</th><th>content</th><th>data</th></tr></thead><tbody>${rows}</tbody></table>`;
  };
  $("#auditKind").addEventListener("change", e => draw(e.target.value));
  draw("");
}

function renderFeed(feed) {
  if (!feed.length) { $("#feedWrap").innerHTML = `<p class="dim small">No content sampled.</p>`; return; }
  $("#feedWrap").innerHTML = feed.map((f, i) => {
    const harm = f.categories.filter(c => c !== "political" && c !== "ai_generated");
    const badge = f.action !== "none" ? `<span class="badge">${esc(f.action.replace(/_/g, " "))}</span>` : (f.ai_generated ? `<span class="badge">AI-generated</span>` : "");
    const tags = [...harm.map(c => `<span class="tag harm">${esc(c.replace(/_/g, " "))}</span>`), f.ai_generated ? `<span class="tag ai">ai-generated</span>` : "", f.categories.includes("political") ? `<span class="tag">political</span>` : "", f.media_type ? `<span class="tag media">${esc(f.media_type)}</span>` : "", f.action !== "none" ? `<span class="tag act">${esc(f.action.replace(/_/g, " "))}</span>` : ""].join("");
    const tile = seedFrom(`${f.id}|${f.topic}|${f.media_type}|${f.author}`) % 12;
    const img = `/static/assets/feed-cover-v3-${String(tile).padStart(2, "0")}.png`;
    return `<article class="post" style="animation-delay:${i * 50}ms"><div class="cover"><img class="feed-img" src="${img}" alt="Representative feed image for ${esc(f.topic)} post by Agent ${f.author}">${badge}</div><div class="body"><div class="who"><span class="av">${avatarSVG(f.author)}</span><span class="meta"><b>Agent ${f.author}</b><span>${esc(f.age)} · ${esc(f.ideology)} · ${esc(f.topic)}</span></span></div><p class="txt">${esc(f.text)}</p><div class="tags">${tags}</div></div></article>`;
  }).join("");
}

function renderAds(ads) {
  if (!ads.length) { $("#ads").innerHTML = `<p class="dim small">Advertising disabled or no impressions recorded.</p>`; return; }
  const remoteProtected = META && META.token_required && !META.token;
  const grid = ads.map((a, i) => {
    const key = encodeURIComponent(a.creative_key || a.campaign_id || "ad");
    const disc = a.disclosure_present ? `<span class="disc">#ad</span>` : `<span class="disc warn">undisclosed</span>`;
    const targeting = a.targeting && Object.keys(a.targeting).length ? esc(JSON.stringify(a.targeting)) : "untargeted";
    const name = esc(a.advertiser || a.campaign_id);
    const img = `/api/creative?key=${key}&w=1024&h=512`;
    const src = remoteProtected ? "" : ` src="${img}"`;
    return `<div class="adcard" style="animation-delay:${i * 50}ms"><div class="creative"><img class="creative-img protected-creative"${src} data-src="${img}" alt="Generated ad creative for ${name} targeting ${targeting}">${disc}<button type="button" class="dl-creative" data-download="${img}" data-filename="creative-${key}.png" title="Download deterministic creative">download</button></div><div class="ad-body"><div class="adname">${name}</div><div class="adtarget">${targeting}</div><div class="adstat"><span>CTR <b>${fmt(a.ctr, 4)}</b></span><span>lift <b>${fmt(a.lift, 4)}</b></span><span>iROAS <b>${fmt(a.iroas, 2)}</b></span></div></div></div>`;
  }).join("");
  const table = `<div class="table-wrap"><table class="read"><thead><tr><th>campaign</th><th>impr</th><th>eligible</th><th>CTR</th><th>CVR</th><th>lift 95% CI</th><th>CUPED lift</th><th>p</th><th>MDE</th><th>ROAS</th><th>iROAS</th><th>CAC</th><th>LTV</th><th>holdout</th><th>attr W</th></tr></thead><tbody>${ads.map(a => `<tr><td>${esc(a.campaign_id)}</td><td class="num">${a.impressions}</td><td class="num">${a.eligible_opportunities ?? "—"}</td><td class="num">${fmt(a.ctr, 4)}</td><td class="num">${fmt(a.cvr, 4)}</td><td class="num">${fmt(a.lift_ci[0], 4)}–${fmt(a.lift_ci[1], 4)}</td><td class="num">${fmt(a.lift_cuped, 4)}</td><td class="num">${fmt(a.lift_pvalue, 3)}</td><td class="num">${fmt(a.mde, 4)}</td><td class="num">${fmt(a.roas, 2)}</td><td class="num">${fmt(a.iroas, 2)}</td><td class="num">${fmt(a.cac, 2)}</td><td class="num">${fmt(a.ltv, 2)}</td><td class="num">${a.n_holdout}</td><td class="num">${a.attribution_window_ticks}</td></tr>`).join("")}</tbody></table></div>`;
  const tableV2 = `<div class="table-wrap"><table class="read"><thead><tr><th>campaign</th><th>impr</th><th>eligible</th><th>budget</th><th>CTR</th><th>CVR</th><th>lift raw CI</th><th>CUPED lift</th><th>p(raw)</th><th>q(BH)</th><th>MDE</th><th>ROAS*</th><th>iROAS*</th><th>CAC*</th><th>LTV*</th><th>holdout</th><th>attr W</th></tr></thead><tbody>${ads.map(a => `<tr><td>${esc(a.campaign_id)}</td><td class="num">${a.impressions}</td><td class="num">${a.eligible_opportunities ?? "—"}</td><td class="num">${fmt(a.spend, 2)} / ${fmt(a.budget_configured, 2)}</td><td class="num">${fmt(a.ctr, 4)}</td><td class="num">${fmt(a.cvr, 4)}</td><td class="num">${a.lift_ci ? `${fmt(a.lift_ci[0], 4)}-${fmt(a.lift_ci[1], 4)}` : "—"}</td><td class="num">${fmt(a.lift_cuped, 4)}</td><td class="num">${fmt(a.lift_pvalue_raw ?? a.lift_pvalue, 3)}</td><td class="num">${fmt(a.lift_qvalue_bh, 3)}</td><td class="num">${fmt(a.mde, 4)}</td><td class="num">${fmt(a.roas, 2)}</td><td class="num">${fmt(a.iroas, 2)}</td><td class="num">${fmt(a.cac, 2)}</td><td class="num">${fmt(a.ltv, 2)}</td><td class="num">${a.n_holdout}</td><td class="num">${a.attribution_window_ticks}</td></tr>`).join("")}</tbody></table><p class="hint">* Scenario economics are assumption-derived from conversion value, LTV multiplier, and attribution window inputs.</p></div>`;
  // Campaign screen — each campaign is measured against its own holdout. This is
  // not a direct creative-vs-creative randomized contrast.
  let ab = "";
  if (ads.length >= 2) {
    const ranked = [...ads].filter(a => a.lift != null).sort((a, b) => (b.lift || 0) - (a.lift || 0));
    if (ranked.length >= 2) {
      const top = ranked[0], second = ranked[1];
      const sep = top.lift_ci && second.lift_ci && top.lift_ci[0] > second.lift_ci[1];
      const win = top.lift_significant_bh_fdr && sep;
      ab = `<div class="ab-verdict ${win ? "ok" : "warn"}"><b>Campaign lift screen:</b> ${win
        ? `<b>${esc(top.campaign_id)}</b> clears its holdout screen — incremental lift ${fmt(top.lift, 4)} [${fmt(top.lift_ci[0], 4)}, ${fmt(top.lift_ci[1], 4)}], p(raw)=${fmt(top.lift_pvalue_raw ?? top.lift_pvalue, 3)}, q(BH)=${fmt(top.lift_qvalue_bh, 3)}. Treat this as campaign-vs-holdout evidence, not a direct creative-vs-creative winner.`
        : `no decision-grade campaign winner yet — best lift ${fmt(top.lift, 4)} but confidence intervals overlap or sit below the minimum detectable effect (MDE ${fmt(top.mde, 4)}). Increase audience, holdout, or run more replicates.`}</div>`;
    }
  }
  $("#ads").innerHTML = `${ab}<div class="ads-grid">${grid}</div>${tableV2}`;
  $$("#ads [data-download]").forEach(b => b.addEventListener("click", () => downloadProtected(b.dataset.download, b.dataset.filename)));
  if (remoteProtected) {
    $$("#ads img.protected-creative").forEach(async img => {
      const res = await fetchProtected(img.dataset.src);
      if (!res.ok) return;
      img.src = URL.createObjectURL(await res.blob());
    });
  }
}

/* ---------- export + history ---------- */
$("#exportBtn").addEventListener("click", () => $("#exportMenu").hidden = !$("#exportMenu").hidden);
["expReport", "expJson", "expTransparency", "expEvents"].forEach(id => {
  $("#" + id)?.addEventListener("click", e => {
    e.preventDefault();
    const href = e.currentTarget.getAttribute("href");
    if (!href) return;
    const ext = id === "expReport" ? "md" : (id === "expEvents" ? "jsonl" : "json");
    downloadProtected(href, `sociosim-${currentRunId || "run"}-${id}.${ext}`);
  });
});
document.addEventListener("click", e => { if (!e.target.closest(".export")) $("#exportMenu").hidden = true; });
const ago = ts => { const d = Date.now() / 1000 - ts; if (d < 60) return "just now"; if (d < 3600) return Math.floor(d / 60) + "m ago"; if (d < 86400) return Math.floor(d / 3600) + "h ago"; return Math.floor(d / 86400) + "d ago"; };
async function refreshHistory() {
  let data; try { data = await (await fetch("/api/runs", { headers: authHeaders() })).json(); } catch (e) { return; }
  $("#histCount").textContent = data.count; const list = $("#histList");
  if (!data.runs.length) { list.innerHTML = `<div class="hist-empty">No saved runs yet.<br>Run a simulation to populate history.</div>`; return; }
  list.innerHTML = data.runs.map((r, i) => `<div class="hist-card" style="animation-delay:${i * 35}ms"><div class="hc-top"><span class="hc-label">${esc(r.label || r.id)}</span><span class="hc-when">${ago(r.created_at)}</span></div><div class="hc-meta">${esc(r.jurisdictions || "—")} · ${r.n_agents}a×${r.n_ticks}t · ${esc(r.content_mode)} · ${r.replay_ok ? "✓ replay" : "replay n/a"}</div><div class="hc-stats"><span>harm <b>${r.harmful_rate == null ? "—" : pct(r.harmful_rate)}</b></span><span>prec <b>${fmt(r.mod_precision, 2)}</b></span><span>I <b>${fmt(r.implausibility, 2)}</b></span></div><div class="hc-actions"><button class="open" data-open="${r.id}">Open</button><a href="/api/runs/${r.id}/export?fmt=report" data-export="/api/runs/${r.id}/export?fmt=report" data-filename="sociosim-${r.id}-report.md">Export</a><button class="del" data-del="${r.id}">Delete</button></div></div>`).join("");
  $$("[data-open]", list).forEach(b => b.addEventListener("click", () => openRun(b.dataset.open)));
  $$("[data-export]", list).forEach(a => a.addEventListener("click", e => { e.preventDefault(); downloadProtected(a.dataset.export, a.dataset.filename); }));
  $$("[data-del]", list).forEach(b => b.addEventListener("click", async () => {
    if (!window.confirm("Delete this saved run?")) return;
    await fetch("/api/runs/" + b.dataset.del, { method: "DELETE", headers: postHeaders() });
    refreshHistory();
  }));
}
async function openRun(id) { let data; try { data = await (await fetchProtected("/api/runs/" + id)).json(); } catch (e) { return; } if (data.error) return; currentRunId = id; closeDrawer(); render(data.result); }
let drawerReturnFocus = null;
function drawerFocusables() { return $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', $("#histDrawer")).filter(el => !el.disabled && !el.hidden); }
function openDrawer() {
  drawerReturnFocus = document.activeElement;
  refreshHistory(); $("#histScrim").hidden = false; $("#histDrawer").hidden = false;
  setTimeout(() => (drawerFocusables()[0] || $("#histClose")).focus(), 0);
}
function closeDrawer() {
  $("#histScrim").hidden = true; $("#histDrawer").hidden = true;
  if (drawerReturnFocus && drawerReturnFocus.focus) drawerReturnFocus.focus();
}
$("#histBtn").addEventListener("click", openDrawer);
$("#histClose").addEventListener("click", closeDrawer);
$("#histScrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", e => {
  if ($("#histDrawer").hidden) return;
  if (e.key === "Escape") { e.preventDefault(); closeDrawer(); return; }
  if (e.key !== "Tab") return;
  const f = drawerFocusables(); if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

window.addEventListener("resize", () => { moveInk($("#cfgTabs")); if (!$("#results").hidden) moveInk($("#outTabs")); });
/* ---------- theme (dark control-room / light editorial) ---------- */
function applyTheme(t) {
  document.body.dataset.theme = (t === "dark") ? "dark" : "";
  try { localStorage.setItem("sociosim-theme", t); } catch (e) { /* private mode */ }
}
$("#themeBtn")?.addEventListener("click", () =>
  applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark"));
try { if (localStorage.getItem("sociosim-theme") === "dark") applyTheme("dark"); } catch (e) { /* ignore */ }

wireTabs("#cfgTabs", "tab", "panel");
wireTabs("#outTabs", "otab", "opanel");
loadMeta();
