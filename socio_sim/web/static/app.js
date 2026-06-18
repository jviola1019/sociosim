"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const fmt = (x, d = 4) => (x == null || Number.isNaN(x)) ? "—" : Number(x).toFixed(d);
const pct = (x, d = 2) => (x == null || Number.isNaN(x)) ? "—" : (100 * x).toFixed(d) + "%";
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let META = null, polling = null, currentRunId = null;

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
function creativeSVG(seed, initial, w, h) {
  const r = mulberry32(seedFrom("ad" + seed));
  const base = PALETTE[Math.floor(r() * PALETTE.length)], h2 = (base + 50 + r() * 90) % 360;
  let geo = "";
  for (let i = 0; i < 3; i++) { const t = r(); geo += t < .5 ? `<circle cx="${r() * w}" cy="${r() * h}" r="${20 + r() * 50}" fill="none" stroke="hsla(0,0%,100%,.4)" stroke-width="${1 + r() * 3}"/>` : `<rect x="${r() * w}" y="${r() * h}" width="${30 + r() * 80}" height="${30 + r() * 80}" rx="10" fill="hsla(${h2},90%,80%,.3)" transform="rotate(${r() * 90} ${r() * w} ${r() * h})"/>`; }
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="ad${seedFrom(seed)}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${base},74%,56%)"/><stop offset="1" stop-color="hsl(${h2},70%,44%)"/></linearGradient></defs><rect width="${w}" height="${h}" fill="url(#ad${seedFrom(seed)})"/>${geo}<text x="${w / 2}" y="${h / 2 + 18}" text-anchor="middle" font-family="-apple-system,Segoe UI,sans-serif" font-size="56" font-weight="700" fill="hsla(0,0%,100%,.92)">${esc(initial)}</text></svg>`;
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
  $$("button", nav).forEach(btn => btn.addEventListener("click", () => {
    $$("button", nav).forEach(b => b.classList.toggle("on", b === btn));
    $$(`[data-${panelAttr}]`).forEach(p => p.classList.toggle("on", p.dataset[panelAttr] === btn.dataset[attr]));
    moveInk(nav);
    if (panelAttr === "opanel" && btn.dataset[attr] === "charts") redrawCharts();
  }));
  requestAnimationFrame(() => moveInk(nav));
}

/* ---------- bootstrap ---------- */
async function loadMeta() {
  try { META = await (await fetch("/api/meta")).json(); }
  catch (e) { const el = $("#engLabel"); el.textContent = "Engine offline"; el.classList.add("bad"); return; }
  $("#version").textContent = "v" + META.version;
  $("#ticker").textContent = META.notice;
  $("#engLabel").textContent = "Engine ready";
  $("#llmLabel").textContent = META.llm_available ? "LLM ready" : "LLM idle";
  const ps = $("#preset");
  ps.innerHTML = Object.entries(META.presets).map(([k, p]) => `<option value="${k}">${esc(p.label)}</option>`).join("");
  ps.value = "eu_dsa"; ps.addEventListener("change", () => applyPreset(ps.value));
  $("#rates").innerHTML = META.harmful_categories.concat(["ai_generated"]).map(c => { const v = META.defaults[c] ?? 0.02; return `<div class="rate"><label>${c.replace(/_/g, " ")}<b id="rl_${c}">${v.toFixed(3)}</b></label><input type="range" id="rate_${c}" min="0" max="0.3" step="0.005" value="${v}"></div>`; }).join("");
  $("#rates").addEventListener("input", e => { if (e.target.id.startsWith("rate_")) $("#rl_" + e.target.id.slice(5)).textContent = (+e.target.value).toFixed(3); });
  $("#redteam").innerHTML = META.adversaries.map(a => `<label class="chip"><input type="checkbox" value="${a}"><b>${a.replace(/_/g, " ")}</b></label>`).join("");
  applyPreset("eu_dsa"); refreshHistory();
}

/* ---------- presets / form ---------- */
function setVal(id, v) { const el = $("#" + id); if (!el) return; if (el.type === "checkbox") el.checked = !!v; else el.value = v; const lab = $("#" + ({ homophily_rewire_fraction: "homoVal", classifier_precision: "precVal", classifier_recall: "recVal", human_review_accuracy: "hraVal" }[id])); if (lab) lab.textContent = (+v).toFixed(2); }
// Documented defaults for every control a preset may touch, so selecting a
// preset yields a CLEAN known state instead of inheriting stale values from a
// previously selected preset (audit S1).
const FIELD_DEFAULTS = {
  ftc_enabled: true, feed_strategy: "personalized", eu_optout_rate: 0.20,
  exploration_epsilon: 0.10, human_review_accuracy: 0.92,
  human_review_delay_ticks: 6, appeal_grant_fp_rate: 0.70, ftc_compliance: true,
  ads_enabled: true, holdout_fraction: 0.10, ad_frequency_cap_per_day: 4,
  ad_slot_interval: 5, classifier_precision: 0.90, classifier_recall: 0.85,
  homophily_rewire_fraction: 0.15, n_replicates: 1,
};
function resetDefaults() {
  $$("#jurisdictions input").forEach(i => i.checked = i.value === "EU");
  $$("#redteam input").forEach(i => i.checked = false);
  Object.entries(FIELD_DEFAULTS).forEach(([k, v]) => setVal(k, v));
  (META.harmful_categories.concat(["ai_generated"])).forEach(c => {
    const v = META.defaults[c] ?? 0.02; setVal("rate_" + c, v);
    const b = $("#rl_" + c); if (b) b.textContent = (+v).toFixed(3);
  });
}
function applyPreset(name) {
  const p = META.presets[name]; if (!p) return; $("#presetDesc").textContent = p.desc; const f = p.fields;
  resetDefaults();  // clean slate, then apply this preset's overrides (S1)
  if (f.jurisdictions) $$("#jurisdictions input").forEach(i => i.checked = f.jurisdictions.includes(i.value));
  if (f.red_team) $$("#redteam input").forEach(i => i.checked = f.red_team.includes(i.value));
  Object.entries(f).forEach(([k, v]) => { if (k === "jurisdictions" || k === "red_team") return; if (k.startsWith("rate_")) { setVal(k, v); const b = $("#rl_" + k.slice(5)); if (b) b.textContent = (+v).toFixed(3); } else setVal(k, v); });
}
$("#content_mode").addEventListener("change", e => $$("[data-llm]").forEach(el => el.hidden = e.target.value === "template"));
$("#graph_kind").addEventListener("change", e => $$("[data-graph]").forEach(el => el.hidden = el.dataset.graph !== e.target.value));
["homophily_rewire_fraction", "classifier_precision", "classifier_recall", "human_review_accuracy"].forEach(id => { const lab = { homophily_rewire_fraction: "homoVal", classifier_precision: "precVal", classifier_recall: "recVal", human_review_accuracy: "hraVal" }[id]; const el = $("#" + id); if (el) el.addEventListener("input", e => $("#" + lab).textContent = (+e.target.value).toFixed(2)); });

/* ---------- campaign editor (S3) ---------- */
function campaignRow(c = {}) {
  const d = document.createElement("div"); d.className = "camp-row";
  d.innerHTML = `<input class="cf-adv" placeholder="Advertiser" value="${esc(c.advertiser || "")}">`
    + `<input class="cf-bid" type="number" step="0.1" min="0" title="bid" value="${c.bid ?? 2}">`
    + `<input class="cf-bud" type="number" step="1" min="0" title="budget" value="${c.budget ?? 100}">`
    + `<input class="cf-ctr" type="number" step="0.001" min="0" max="1" title="base CTR" value="${c.base_ctr ?? 0.012}">`
    + `<input class="cf-cvr" type="number" step="0.01" min="0" max="1" title="base CVR" value="${c.base_cvr ?? 0.05}">`
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
  }));
}

function collect() {
  const v = id => { const e = $("#" + id); return e && e.value !== "" ? e.value : null; };
  const num = id => { const x = v(id); return x == null ? null : +x; }, chk = id => $("#" + id).checked, checked = sel => $$(sel + " input:checked").map(i => i.value);
  const body = {
    label: v("label") || "", profile: $("input[name=profile]:checked").value, root_seed: num("root_seed"), tick_hours: num("tick_hours"), verify_replay: chk("verify_replay"), n_replicates: num("n_replicates"),
    n_agents: num("n_agents"), n_ticks: num("n_ticks"), n_topics: num("n_topics"), graph_kind: v("graph_kind"), graph_m: num("graph_m"), graph_k: num("graph_k"), graph_p: num("graph_p"), homophily_rewire_fraction: num("homophily_rewire_fraction"),
    content_mode: v("content_mode"), llm_model: v("llm_model"), llm_base_url: v("llm_base_url"), jurisdictions: checked("#jurisdictions"), ftc_enabled: chk("ftc_enabled"),
    classifier_precision: num("classifier_precision"), classifier_recall: num("classifier_recall"), human_review_accuracy: num("human_review_accuracy"), human_review_delay_ticks: num("human_review_delay_ticks"), appeal_grant_fp_rate: num("appeal_grant_fp_rate"),
    feed_strategy: v("feed_strategy"), eu_optout_rate: num("eu_optout_rate"), exploration_epsilon: num("exploration_epsilon"), feed_size: num("feed_size"),
    ads_enabled: chk("ads_enabled"), ftc_compliance: chk("ftc_compliance"), holdout_fraction: num("holdout_fraction"), ad_frequency_cap_per_day: num("ad_frequency_cap_per_day"), ad_slot_interval: num("ad_slot_interval"), red_team: checked("#redteam"),
  };
  (META.harmful_categories.concat(["ai_generated"])).forEach(c => body["rate_" + c] = num("rate_" + c));
  const campaigns = collectCampaigns();
  if (campaigns.length) body.campaigns = campaigns;
  return body;
}
function stage(id) { ["idle", "running", "errstage", "results"].forEach(s => $("#" + s).hidden = s !== id); }
function fail(msg) { if (polling) clearInterval(polling); polling = null; $("#runBtn").disabled = false; $("#errText").textContent = msg; stage("errstage"); }
$("#cfgForm").addEventListener("submit", async e => {
  e.preventDefault(); const body = collect();
  if (!body.jurisdictions.length) return fail("Select at least one jurisdiction pack (Moderation tab).");
  $("#runBtn").disabled = true; stage("running"); $("#meterFill").style.width = "0%"; $("#runPhase").textContent = "initializing"; $("#runDetail").textContent = "building world…";
  let res; try { res = await (await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json(); } catch (err) { return fail(String(err)); }
  if (res.error) return fail(res.error); polling = setInterval(() => poll(res.job_id), 350);
});
async function poll(id) {
  let j; try { j = await (await fetch("/api/job/" + id)).json(); } catch (e) { return; }
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
function renderCharts(ch) {
  _charts = ch; const host = $("#charts"); host.innerHTML = "";
  const hours = [...Array(24)].map((_, i) => (i % 6 === 0 ? i : ""));
  const cc = (title, sub, node) => { const d = document.createElement("div"); d.className = "chart"; d.innerHTML = `<div class="ct">${title}</div><div class="cs">${sub}</div>`; node.setAttribute("role", "img"); node.setAttribute("aria-label", `${title} — ${sub}`); d.appendChild(node); return d; };
  host.appendChild(cc("Diurnal Posting", "posts by hour of day", areaChart(ch.diurnal, { color: "#30c0b4", xlabels: hours })));
  host.appendChild(cc("Degree Distribution", "agents by follower count", barChart(ch.degree_hist.map(d => [Math.round(d[0]), d[1]]), { color: "#0a84ff", labelEvery: 4 })));
  host.appendChild(cc("Activity Timeline", "posts (teal) vs moderation actions (blue)", dualLine(ch.timeline_posts, ch.timeline_removed)));
  host.appendChild(cc("Cascade Sizes", "share-tree size distribution", barChart(ch.cascade, { color: "#ff9500", labelEvery: Math.max(1, Math.ceil(ch.cascade.length / 8)) })));
  requestAnimationFrame(() => activateDraw(host));
}
function redrawCharts() { if (_charts) renderCharts(_charts); }

/* ---------- network topology (deterministic force layout) ---------- */
function renderNetwork(gs) {
  const host = $("#network"); if (!host) return;
  if (!gs || !gs.nodes || !gs.nodes.length) { host.innerHTML = `<p class="dim small">No graph sample for this run.</p>`; return; }
  const W = 640, H = 400, nodes = gs.nodes.map(n => ({ ...n })), idx = {};
  nodes.forEach((n, i) => idx[n.id] = i);
  const rnd = mulberry32(seedFrom("net" + nodes.length));
  nodes.forEach(n => { n.x = 80 + rnd() * (W - 160); n.y = 60 + rnd() * (H - 120); n.vx = 0; n.vy = 0; });
  const links = gs.edges.filter(([u, v]) => idx[u] != null && idx[v] != null).map(([u, v]) => [idx[u], idx[v]]);
  for (let it = 0; it < 120; it++) {
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y, d2 = dx * dx + dy * dy + 0.01, f = 200 / d2;
      const fx = dx * f, fy = dy * f; nodes[i].vx += fx; nodes[i].vy += fy; nodes[j].vx -= fx; nodes[j].vy -= fy;
    }
    for (const [a, b] of links) {
      const dx = nodes[b].x - nodes[a].x, dy = nodes[b].y - nodes[a].y, d = Math.hypot(dx, dy) || 1, f = (d - 42) * 0.02;
      const fx = dx / d * f, fy = dy / d * f; nodes[a].vx += fx; nodes[a].vy += fy; nodes[b].vx -= fx; nodes[b].vy -= fy;
    }
    for (const n of nodes) {
      n.vx += (W / 2 - n.x) * 0.002; n.vy += (H / 2 - n.y) * 0.002;
      n.x += Math.max(-6, Math.min(6, n.vx)); n.y += Math.max(-6, Math.min(6, n.vy));
      n.vx *= 0.85; n.vy *= 0.85;
      n.x = Math.max(10, Math.min(W - 10, n.x)); n.y = Math.max(10, Math.min(H - 10, n.y));
    }
  }
  const maxDeg = Math.max(...nodes.map(n => n.deg), 1);
  const col = g => g === "L" ? "#0a84ff" : g === "R" ? "#ff9500" : "#86868b";
  const e = links.map(([a, b]) => `<line x1="${nodes[a].x.toFixed(1)}" y1="${nodes[a].y.toFixed(1)}" x2="${nodes[b].x.toFixed(1)}" y2="${nodes[b].y.toFixed(1)}" stroke="#d2d2d7" stroke-width="0.6" opacity="0.55"/>`).join("");
  const c = nodes.map(n => `<circle cx="${n.x.toFixed(1)}" cy="${n.y.toFixed(1)}" r="${(2.5 + 5.5 * Math.sqrt(n.deg / maxDeg)).toFixed(1)}" fill="${col(n.group)}" opacity="0.9"><title>agent ${n.id} · degree ${n.deg} · ${esc(n.group)}</title></circle>`).join("");
  host.innerHTML = `<div class="chart"><div class="ct">Social Graph — top ${nodes.length} hubs</div><div class="cs">node size = degree · colour = ideology (blue = left, orange = right) · sampled subgraph, deterministic layout</div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Sampled social-network topology: the ${nodes.length} highest-degree agents and ${links.length} edges among them, coloured by ideology bucket">${e}${c}</svg></div>`;
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
  $("#footHash").textContent = "stream " + m.stream_hash.slice(0, 16);
  const seal = $("#seal"); seal.className = "seal";
  if (!r.replay.checked) $("#sealTxt").textContent = "replay skipped";
  else if (r.replay.ok) { seal.classList.add("ok"); $("#sealTxt").textContent = "replay verified"; }
  else { seal.classList.add("bad"); $("#sealTxt").textContent = "replay mismatch"; }
  if (currentRunId) { $("#expReport").href = `/api/runs/${currentRunId}/export?fmt=report`; $("#expJson").href = `/api/runs/${currentRunId}/export?fmt=json`; $("#expTransparency").href = `/api/runs/${currentRunId}/export?fmt=transparency`; }
  $("#expEvents").hidden = true;

  const heB = ibar(he.ci[0], he.ci[1], he.rate, 0, Math.max(he.ci[1] * 1.3, .05));
  const wB = ibar(w.ci[0], w.ci[1], w.mean, Math.min(w.ci[0], -.1), Math.max(w.ci[1], .1), "teal");
  $("#cards").innerHTML = [
    metric("Harmful Exposure", he.rate * 100, { dec: 2, suf: "%", ci: `<div class="ci">95% ${pct(he.ci[0])}–${pct(he.ci[1])}</div>${heB}` }),
    metric("Mod Precision", mod.precision, { dec: 3 }), metric("Mod Recall", mod.recall, { dec: 3 }),
    metric("Notices Sent", s.notices.notices_sent, { ci: `<div class="ci">coverage ${pct(s.notices.removal_notice_coverage)}</div>` }),
    metric("Appeals Filed", ap.filed, { ci: `<div class="ci">granted ${pct(ap.granted_rate)}</div>` }),
    metric("Welfare Proxy", w.mean, { dec: 3, ci: `<div class="ci">95% ${fmt(w.ci[0], 2)}–${fmt(w.ci[1], 2)}</div>${wB}` }),
    metric("Posts", s.n_posts, { ci: `<div class="ci">${s.n_impressions} impressions</div>` }),
    metric("Max Cascade", s.cascades.max, { ci: `<div class="ci">${s.cascades.n} trees</div>` }),
  ].join("");
  $$(".card").forEach((c, i) => { c.style.animationDelay = (i * 45) + "ms"; });
  setTimeout(() => $$("#cards .v [data-count]").forEach(countUp), 120);

  renderFeed(r.feed || []);
  renderCharts(r.charts);
  renderNetwork(r.summary.graph && r.summary.graph.graph_sample);
  renderCascade(r.charts && r.charts.cascade_tree);

  $("#confusion").innerHTML = `<div class="cell tp"><div class="cl">true positive</div><div class="cv">${mod.tp}</div></div><div class="cell fp"><div class="cl">false positive</div><div class="cv">${mod.fp}</div></div><div class="cell fn"><div class="cl">false negative</div><div class="cv">${mod.fn}</div></div><div class="cell tn"><div class="cl">true negative</div><div class="cv">${mod.tn}</div></div>`;
  $("#fairness").innerHTML = Object.entries(s.fairness).map(([dim, gs]) => `<div class="fgrp">${esc(dim.replace(/_/g, " "))}</div><table class="read"><thead><tr><th>group</th><th>FPR</th><th>FNR</th><th>n posts</th></tr></thead><tbody>${Object.entries(gs).map(([g, d]) => `<tr><td>${esc(g)}</td><td class="num">${fmt(d.fpr, 4)}</td><td class="num">${fmt(d.fnr, 3)}</td><td class="num">${d.n_posts}</td></tr>`).join("")}</tbody></table>`).join("");

  renderAds(Object.values(s.ads));

  $("#implaus").textContent = `implausibility I = ${fmt(r.implausibility, 2)} (history-matching cutoff 3.0; lower = closer to published benchmarks)`;
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
  $$("#outTabs button").forEach((b, i) => b.classList.toggle("on", i === 0));
  $$("[data-opanel]").forEach(p => p.classList.toggle("on", p.dataset.opanel === "overview"));
  moveInk($("#outTabs"));
}

function renderFeed(feed) {
  const HUE = { "local news": 210, sports: 130, technology: 250, health: 168, politics: 22, entertainment: 330, finance: 196, lifestyle: 290 };
  if (!feed.length) { $("#feedWrap").innerHTML = `<p class="dim small">No content sampled.</p>`; return; }
  $("#feedWrap").innerHTML = feed.map((f, i) => {
    const harm = f.categories.filter(c => c !== "political" && c !== "ai_generated");
    const badge = f.action !== "none" ? `<span class="badge" style="background:rgba(0,0,0,.55);color:#fff">${esc(f.action.replace(/_/g, " "))}</span>` : (f.ai_generated ? `<span class="badge" style="background:rgba(0,0,0,.55);color:#fff">AI-generated</span>` : "");
    const tags = [...harm.map(c => `<span class="tag harm">${esc(c.replace(/_/g, " "))}</span>`), f.ai_generated ? `<span class="tag ai">ai-generated</span>` : "", f.categories.includes("political") ? `<span class="tag">political</span>` : "", f.action !== "none" ? `<span class="tag act">${esc(f.action.replace(/_/g, " "))}</span>` : ""].join("");
    return `<article class="post" style="animation-delay:${i * 50}ms"><div class="cover">${meshSVG(f.id, 400, 160, HUE[f.topic])}${badge}</div><div class="body"><div class="who"><span class="av">${avatarSVG(f.author)}</span><span class="meta"><b>Agent ${f.author}</b><span>${esc(f.age)} · ${esc(f.ideology)} · ${esc(f.topic)}</span></span></div><p class="txt">${esc(f.text)}</p><div class="tags">${tags}</div></div></article>`;
  }).join("");
}

function renderAds(ads) {
  if (!ads.length) { $("#ads").innerHTML = `<p class="dim small">Advertising disabled or no impressions recorded.</p>`; return; }
  const grid = ads.map((a, i) => {
    const init = (a.campaign_id || "?").replace(/[^a-z]/gi, "").slice(0, 1).toUpperCase() || "A";
    return `<div class="adcard" style="animation-delay:${i * 50}ms"><div class="creative">${creativeSVG(a.campaign_id, init, 400, 200)}<span class="disc">#ad</span></div><div class="ad-body"><div class="adname">${esc(a.campaign_id)}</div><div class="adstat"><span>CTR <b>${fmt(a.ctr, 4)}</b></span><span>lift <b>${fmt(a.lift, 4)}</b></span><span>${a.impressions} impr</span></div></div></div>`;
  }).join("");
  const table = `<table class="read"><thead><tr><th>campaign</th><th>impr</th><th>CTR</th><th>CTR 95% CI</th><th>lift</th><th>spend</th><th>ROI</th></tr></thead><tbody>${ads.map(a => `<tr><td>${esc(a.campaign_id)}</td><td class="num">${a.impressions}</td><td class="num">${fmt(a.ctr, 4)}</td><td class="num">${fmt(a.ctr_ci[0], 4)}–${fmt(a.ctr_ci[1], 4)}</td><td class="num">${fmt(a.lift, 4)}</td><td class="num">${fmt(a.spend, 2)}</td><td class="num">${fmt(a.roi, 2)}</td></tr>`).join("")}</tbody></table>`;
  $("#ads").innerHTML = `<div class="ads-grid">${grid}</div>${table}`;
}

/* ---------- export + history ---------- */
$("#exportBtn").addEventListener("click", () => $("#exportMenu").hidden = !$("#exportMenu").hidden);
document.addEventListener("click", e => { if (!e.target.closest(".export")) $("#exportMenu").hidden = true; });
const ago = ts => { const d = Date.now() / 1000 - ts; if (d < 60) return "just now"; if (d < 3600) return Math.floor(d / 60) + "m ago"; if (d < 86400) return Math.floor(d / 3600) + "h ago"; return Math.floor(d / 86400) + "d ago"; };
async function refreshHistory() {
  let data; try { data = await (await fetch("/api/runs")).json(); } catch (e) { return; }
  $("#histCount").textContent = data.count; const list = $("#histList");
  if (!data.runs.length) { list.innerHTML = `<div class="hist-empty">No saved runs yet.<br>Run a simulation to populate history.</div>`; return; }
  list.innerHTML = data.runs.map((r, i) => `<div class="hist-card" style="animation-delay:${i * 35}ms"><div class="hc-top"><span class="hc-label">${esc(r.label || r.id)}</span><span class="hc-when">${ago(r.created_at)}</span></div><div class="hc-meta">${esc(r.jurisdictions || "—")} · ${r.n_agents}a×${r.n_ticks}t · ${esc(r.content_mode)} · ${r.replay_ok ? "✓ replay" : "replay n/a"}</div><div class="hc-stats"><span>harm <b>${r.harmful_rate == null ? "—" : pct(r.harmful_rate)}</b></span><span>prec <b>${fmt(r.mod_precision, 2)}</b></span><span>I <b>${fmt(r.implausibility, 2)}</b></span></div><div class="hc-actions"><button class="open" data-open="${r.id}">Open</button><a href="/api/runs/${r.id}/export?fmt=report" download>Export</a><button class="del" data-del="${r.id}">Delete</button></div></div>`).join("");
  $$("[data-open]", list).forEach(b => b.addEventListener("click", () => openRun(b.dataset.open)));
  $$("[data-del]", list).forEach(b => b.addEventListener("click", async () => { await fetch("/api/runs/" + b.dataset.del, { method: "DELETE" }); refreshHistory(); }));
}
async function openRun(id) { let data; try { data = await (await fetch("/api/runs/" + id)).json(); } catch (e) { return; } if (data.error) return; currentRunId = id; closeDrawer(); render(data.result); }
function openDrawer() { refreshHistory(); $("#histScrim").hidden = false; $("#histDrawer").hidden = false; }
function closeDrawer() { $("#histScrim").hidden = true; $("#histDrawer").hidden = true; }
$("#histBtn").addEventListener("click", openDrawer);
$("#histClose").addEventListener("click", closeDrawer);
$("#histScrim").addEventListener("click", closeDrawer);

window.addEventListener("resize", () => { moveInk($("#cfgTabs")); if (!$("#results").hidden) moveInk($("#outTabs")); });
wireTabs("#cfgTabs", "tab", "panel");
wireTabs("#outTabs", "otab", "opanel");
loadMeta();
