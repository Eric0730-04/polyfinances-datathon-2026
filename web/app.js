// SecondLook web app (no framework). Every string coming from agents is escaped before rendering.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x, d = 0) => (x == null || isNaN(x) ? "—" : `${(x * 100).toFixed(d)}%`);
const money = (x) => (x == null ? "—" : `${x < 0 ? "−" : ""}$${Math.abs(Math.round(x)).toLocaleString("en-CA")}`);
const bigMoney = (x, ccy) => (x == null ? "—" : x >= 1e12 ? `${(x / 1e12).toFixed(2)} T ${ccy}` : `${(x / 1e9).toFixed(0)} B ${ccy}`);
const fmtVal = (v) => (v == null ? "—" : typeof v === "string" ? v : Math.abs(v) > 1.5 ? money(v) : pct(v, 1));
const pts = (a, b) => { const d = (b - a) * 100; return `${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(1)} pts`; };
const title = (s) => String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const VERDICT = {
  CONSISTENT: { cls: "ok", label: "Consistent with profile", short: "Consistent" },
  CONSISTENT_WITH_CONDITIONS: { cls: "cond", label: "Consistent with conditions", short: "With conditions" },
  INCONSISTENT: { cls: "bad", label: "Inconsistent with profile", short: "Inconsistent" },
  INSUFFICIENT_DATA: { cls: "na", label: "Needs more information", short: "Needs info" },
};
const vinfo = (v) => VERDICT[v] || VERDICT.INSUFFICIENT_DATA;
const ICON = {
  ok: '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  cond: '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M12 6v7" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/><circle cx="12" cy="17.5" r="1.6" fill="currentColor"/></svg>',
  bad: '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M7 7l10 10M17 7L7 17" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>',
  na: '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M9.2 9.3a2.9 2.9 0 1 1 3.8 2.8c-.6.3-1 .8-1 1.5v.6" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/><circle cx="12" cy="17.6" r="1.5" fill="currentColor"/></svg>',
};
const CHECK_SVG = '<svg width="14" height="14" viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const AI_SVG = '<span class="mono">SL</span>';

const FLOW = [["Intake", "Intake"], ["Toolbox", "Toolbox"], ["Profile and market", "Profile + Market"], ["Advocate vs skeptic", "Debate"],
  ["Constraint guardian", "Guardian"], ["Judge", "Judge"], ["Guardrail", "Guardrail"]];
const FLOW_AGENTS = [["intake"], ["toolbox"], ["profile", "analyst"], ["advocate", "skeptic", "advocate_rebuttal", "skeptic_rebuttal"], ["guardian"], ["judge"], []];
const RISK = { low: "Low", low_moderate: "Low–moderate", moderate: "Moderate", high: "High" };
const PCOLOR = { robert: "#2563eb", amira: "#7c3aed", mateo: "#059669", maya: "#ea580c" };
const ACOLOR = { equity: "#2a78d6", fixed_income: "#1baf7a", cash_equivalent: "#6250d6", cash: "#eda100", crypto: "#e87ba4", commodity: "#eb6834" };
const RISKBAND = [[0.3, "#dcfce7", "Very low"], [0.9, "#e0f2fe", "Below S&P 500"], [1.5, "#e0e7ff", "About S&P 500"], [2.5, "#fef3c7", "Higher"], [99, "#fce7f3", "Much higher (2.5×+)"]];
const CONSTRAINT = {
  min_liquid_cad: ["Minimum cash & equivalents", money],
  max_single_position_pct: ["Max in one stock / crypto", (v) => `${v}%`],
  max_sector_pct: ["Max in one sector", (v) => `${v}%`],
  max_crypto_pct: ["Max in crypto", (v) => `${v}%`],
  excluded_sectors: ["Excluded sectors", (v) => v.join(", ")],
  excluded_asset_classes: ["Excluded asset classes", (v) => v.join(", ")],
  pref_max_security_risk_units: ["Avoid names more volatile than", (v) => `${v}× S&P`],
  pref_pass_esg_screen: ["US stocks must pass ESG screen", () => "yes"],
};

const state = { personas: [], meta: null, pid: null, threads: {}, history: [], charts: {}, seq: 0 };
const persona = (id = state.pid) => state.personas.find((p) => p.id === id);
const pcolor = (p) => PCOLOR[p.id] || (p.custom ? "#0f766e" : "#64748b");
const personaPayload = (p) => (p.custom ? { persona: p.def } : {});
const initials = (p) => p.name.slice(0, 1);

// ------------------------------------------------------------------ errors
class UserError extends Error { constructor(f) { super(f.title); this.f = f; } }
const SERVER_DOWN = { title: "Can't reach the SecondLook server", message: "The page couldn't connect to the analysis server.",
  action: "Make sure it is running (uvicorn server:app --port 8000), then try again.", retry: true };
function errorCard(f, retryId = "") {
  return `<div class="card err"><div class="err-title">${esc(f.title)}</div>${f.message ? `<p>${esc(f.message)}</p>` : ""}
    ${f.action ? `<p><b>What to do:</b> ${esc(f.action)}</p>` : ""}
    <div class="err-row">${f.retry && retryId ? `<button class="btn" data-retry="${retryId}">Try again</button>` : ""}
    ${f.technical ? `<details class="raw"><summary>Technical details</summary><pre class="json">${esc(f.technical)}</pre></details>` : ""}</div></div>`;
}
async function ok(r) {
  if (!r.ok) {
    let d = ""; try { d = (await r.json()).detail; } catch { /* ignore */ }
    throw new UserError({ title: d || `Request failed (${r.status})`, technical: `HTTP ${r.status}` });
  }
  return r.json();
}

// ------------------------------------------------------------------ boot
async function boot() {
  try {
    [state.personas, state.meta] = await Promise.all([fetch("/api/personas").then(ok), fetch("/api/meta").then(ok)]);
  } catch (e) {
    $("#thread").innerHTML = errorCard({ ...SERVER_DOWN, technical: String(e) });
    return;
  }
  await loadCustoms();
  $("#addInvestor").addEventListener("click", () => openBuilder());
  $$(".nav-item").forEach((a) => a.addEventListener("click", () => showView(a.dataset.view)));
  $("#newCheck").addEventListener("click", () => { showView("check"); $("#request").value = ""; $("#request").focus(); $("#askCard").scrollIntoView({ behavior: "smooth", block: "center" }); });
  $("#runBtn").addEventListener("click", () => ask());
  $("#request").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } });
  $("#compareBtn").addEventListener("click", compare);
  $("#compareRequest").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); compare(); } });
  renderComparePills();
  renderMethod();
  const qs = new URLSearchParams(location.search);
  selectPersona(state.personas.some((p) => p.id === qs.get("persona")) ? qs.get("persona") : state.personas[0].id);
  if (qs.get("view") === "builder") openBuilder();
  else if (qs.get("view")) showView(qs.get("view"));
  if (qs.get("q")) ask(qs.get("q"));
  if (qs.get("compare")) { showView("compare"); $("#compareRequest").value = qs.get("compare"); compare(); }
  if (qs.get("ask") && qs.get("run")) state.pendingChat = qs.get("ask");  // demo/test: open a run and ask a follow-up
  if (qs.get("run")) {
    try {
      const t = await fetch(`/api/trace/${encodeURIComponent(qs.get("run"))}`).then(ok);
      selectPersona(t.persona_id);
      addDone(t.persona_id, t.request, t, qs.get("tab"));
      if (state.pendingChat) { const it = thread(t.persona_id).at(-1); askChat(it, state.pendingChat); }
    } catch (e) { $("#thread").innerHTML = errorCard(e.f || { title: "Couldn't open that analysis", technical: String(e) }); }
  }
}

function showView(v) {
  $$(".nav-item").forEach((a) => a.classList.toggle("active", a.dataset.view === v));
  $$(".view").forEach((s) => s.classList.toggle("hidden", s.id !== `view-${v}`));
  $(".shell").classList.toggle("no-rail", v !== "check");
}

// ------------------------------------------------------------------ persona + dashboard
function selectPersona(pid) {
  state.pid = pid;
  const p = persona();
  $("#personaList").innerHTML = state.personas.map((x) => `
    <div class="persona-item ${x.id === pid ? "active" : ""}" data-pid="${x.id}">
      <div class="avatar" style="background:${pcolor(x)}">${initials(x)}</div>
      <div style="flex:1;min-width:0"><div class="nm">${esc(x.name)}, ${x.age}</div><div class="sb">${esc(RISK[x.risk_tolerance])} risk · ${x.custom ? "your investor" : x.official_persona ? "official" : "extra scenario"}</div></div>
      ${x.custom ? `<span class="p-edit" data-edit="${x.id}" title="Edit">Edit</span>` : ""}
    </div>`).join("");
  $$("[data-edit]").forEach((el) => el.addEventListener("click", (e) => { e.stopPropagation(); openBuilder(el.dataset.edit); }));
  $$(".persona-item").forEach((el) => el.addEventListener("click", () => { showView("check"); selectPersona(el.dataset.pid); }));
  $("#pTitle").innerHTML = `<div class="avatar lg" style="background:${pcolor(p)}">${initials(p)}</div>${esc(p.name)}, ${p.age}`;
  const hz = p.goals.filter((g) => g.horizon_years > 0).map((g) => (g.horizon_note || "").match(/(\d+[-–]\d+ years|\d+ years or more)/)?.[0] || `${g.horizon_years} years`);
  $("#pTags").innerHTML = [`${RISK[p.risk_tolerance]} risk`, ...hz.map((h) => `Horizon ${h}`), title(p.knowledge_level),
    p.custom ? "Your investor" : p.official_persona ? "Official persona" : "Extra scenario", "Fictional"].map((t, i) => `<span class="tag ${i === 0 ? "blue" : ""}">${esc(t)}</span>`).join("");
  $("#askTitle").textContent = `What is ${p.name} thinking of doing?`;
  $("#request").placeholder = p.sample_requests[0];
  $("#suggestions").innerHTML = p.sample_requests.map((s) => `<button class="pill">${esc(s)}</button>`).join("");
  $$("#suggestions .pill").forEach((b) => b.addEventListener("click", () => ask(b.textContent.trim())));
  renderTiles(p);
  renderDash(p);
  renderRail(p);
  renderThread();
}

function mainGoal(p) {
  const gs = p.baseline.goals.filter((g) => g.horizon_years > 0);
  return [...gs].sort((a, b) => b.value_cad - a.value_cad)[0] || p.baseline.goals[0];
}

function renderTiles(p) {
  const e = p.baseline.exposures, g = mainGoal(p);
  const used = g.risky_share / g.allowed_max_risky;
  const filled = Math.min(5, Math.round(used * 5));
  const liquid = p.holdings.filter((h) => ["cash", "cash_equivalent"].includes(state.meta.universe[h.ticker]?.asset_class)).reduce((s, h) => s + h.value_cad, 0);
  const minLiq = p.constraints.min_liquid_cad || 0;
  $("#tiles").innerHTML = `
    <div class="card tile"><div class="t-label">Risk budget · ${esc(g.label.split("(")[0].trim())}</div>
      <div class="t-value">${pct(g.risky_share)} <span class="delta ${used > 1 ? "bad" : used > 0.85 ? "warn" : "good"}">${used > 1 ? "Over limit" : `${((g.allowed_max_risky - g.risky_share) * 100).toFixed(0)} pts below limit`}</span></div>
      <div class="segbar">${[0, 1, 2, 3, 4].map((i) => `<span class="${i < filled ? (used > 1 ? "over" : "on") : ""}"></span>`).join("")}</div>
      <div class="segbar-scale"><span>0%</span><span>limit ${pct(g.allowed_max_risky)} (S&amp;P 500 = 100%)</span></div></div>
    <div class="card tile"><div class="t-label">Portfolio value</div><div class="t-value">${money(e.total_value_cad)}</div>
      <div class="t-sub">${p.holdings.length} holdings · fictional</div></div>
    <div class="card tile"><div class="t-label">Cash buffer</div><div class="t-value">${money(liquid)}</div>
      <div class="t-sub">minimum required ${money(minLiq)}</div></div>
    <div class="card tile"><div class="t-label">Past volatility</div><div class="t-value">${pct(p.baseline.risk.annual_volatility, 1)}</div>
      <div class="t-sub">worst drop ${pct(p.baseline.risk.max_drawdown, 1)} · 2021–2026</div></div>`;
}

function renderDash(p) {
  const e = p.baseline.exposures;
  $("#dash").innerHTML = `
    <div class="card"><div class="panel-head"><h3>Allocation</h3><span class="note">by asset class</span></div>
      <div class="donut-wrap"><div class="donut-box"><canvas id="dashDonut"></canvas></div>
      <div class="legend-list">${Object.entries(e.asset_class).map(([k, v]) => `<div><span><i style="background:${ACOLOR[k] || "#94a3b8"}"></i>${esc(title(k))}</span><b>${pct(v, 1)}</b></div>`).join("")}</div></div></div>
    <div class="card"><div class="panel-head"><h3>Holdings</h3><span class="note">size = weight · colour = risk vs S&amp;P 500</span></div>
      <div class="treemap" id="treemap"></div>
      <div class="tm-legend">${RISKBAND.map(([, c, l]) => `<span><i style="background:${c}"></i>${l}</span>`).join("")}</div></div>`;
  donut("dashDonut", e.asset_class);
  treemap($("#treemap"), p);
}

function donut(id, data, cutout = "68%") {
  const el = document.getElementById(id);
  if (!window.Chart || !el) return;
  state.charts[id]?.destroy();
  const keys = Object.keys(data);
  state.charts[id] = new Chart(el, {
    type: "doughnut",
    data: { labels: keys.map(title), datasets: [{ data: keys.map((k) => +(data[k] * 100).toFixed(1)), backgroundColor: keys.map((k) => ACOLOR[k] || "#94a3b8"), borderColor: "#fff", borderWidth: 2 }] },
    options: { cutout, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.raw}%` } } } },
  });
}

function treemap(el, p) {
  const total = p.holdings.reduce((s, h) => s + h.value_cad, 0);
  const items = Object.values(p.holdings.reduce((m, h) => { (m[h.ticker] ||= { t: h.ticker, v: 0 }).v += h.value_cad; return m; }, {})).sort((a, b) => b.v - a.v);
  const W = el.clientWidth || 600, H = el.clientHeight || 200;
  const rects = squarify(items.map((i) => ({ ...i, a: (i.v / total) * W * H })), 0, 0, W, H);
  el.innerHTML = rects.map((r) => {
    const ru = state.meta.risk_units[r.t];
    const col = RISKBAND.find(([lim]) => ru <= lim)[1];
    return `<div class="tm-cell" style="left:${r.x}px;top:${r.y}px;width:${r.w}px;height:${r.h}px;background:${col}" title="${esc(p.holding_names[r.t])}: ${money(r.v)} · risk ${ru.toFixed(2)}× S&P 500">
      ${r.w > 52 && r.h > 30 ? `<b>${esc(r.t)}</b>` : ""}${r.w > 70 && r.h > 46 ? `<span>${pct(r.v / total)} · ${ru.toFixed(1)}×</span>` : ""}</div>`;
  }).join("");
}
function squarify(items, x, y, w, h) {
  const out = [];
  const worst = (row, side) => { const s = row.reduce((a, r) => a + r.a, 0); const mx = Math.max(...row.map((r) => r.a)), mn = Math.min(...row.map((r) => r.a)); return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn)); };
  let rest = [...items];
  while (rest.length) {
    const side = Math.min(w, h);
    const row = [rest[0]];
    let i = 1;
    while (i < rest.length && worst([...row, rest[i]], side) <= worst(row, side)) row.push(rest[i++]);
    rest = rest.slice(row.length);
    const s = row.reduce((a, r) => a + r.a, 0);
    if (w >= h) { const rw = s / h; let yy = y; row.forEach((r) => { const rh = r.a / rw; out.push({ ...r, x, y: yy, w: rw, h: rh }); yy += rh; }); x += rw; w -= rw; }
    else { const rh = s / w; let xx = x; row.forEach((r) => { const rw = r.a / rh; out.push({ ...r, x: xx, y, w: rw, h: rh }); xx += rw; }); y += rh; h -= rh; }
  }
  return out;
}

function renderRail(p) {
  const b = p.baseline, total = b.exposures.total_value_cad;
  const c = p.constraints || {}, org = c._origin || {};
  $("#rail").innerHTML = `
    <div class="rail-sec"><h3>Profile</h3><p>${esc(p.summary)}</p>
      <dl class="kv"><dt>Objective</dt><dd>${esc(p.objective)}</dd><dt>Risk profile</dt><dd>${esc(RISK[p.risk_tolerance])}</dd>
      <dt>Experience</dt><dd>${esc(title(p.knowledge_level))}</dd></dl></div>
    <div class="rail-sec"><h3>Goals <span class="note">risk vs limit</span></h3>
      ${b.goals.map((g) => { const sc = Math.max(g.allowed_max_risky, g.risky_share, 0.05) * 1.15; return `<div class="row" style="display:block">
        <div style="display:flex;justify-content:space-between;gap:8px"><span>${esc(g.label)}</span><span class="r">${money(g.value_cad)}</span></div>
        <div class="sub">${g.horizon_years ? `${g.horizon_years}-year horizon` : "needed any time"} · ${pct(g.risky_share)} of ${pct(g.allowed_max_risky)}</div>
        <div class="mini"><div class="f" style="width:${(g.risky_share / sc) * 100}%"></div><div class="l" style="left:${(g.allowed_max_risky / sc) * 100}%"></div></div></div>`; }).join("")}</div>
    <div class="rail-sec"><h3>Limits &amp; preferences</h3>
      ${Object.entries(c).filter(([k]) => !k.startsWith("_")).map(([k, v]) => { const [lab, f] = CONSTRAINT[k] || [title(k), String]; const asm = /derived|assumption/i.test(org[k] || "");
        return `<div class="row" title="${esc(org[k] || "stated in the brief")}"><span>${esc(lab)}<span class="tg ${asm ? "tg-assumed" : "tg-stated"}">${asm ? "assumed" : "stated"}</span>${k.startsWith("pref_") ? '<span class="tg tg-pref">preference</span>' : ""}</span><span class="r">${esc(f(v))}</span></div>`; }).join("")}
      <p class="small muted" style="margin-top:8px">"Assumed" = our reading of the brief, to confirm with the investor.</p></div>
    <div class="rail-sec"><h3>Holdings <span class="note">risk vs S&amp;P 500</span></h3>
      ${[...p.holdings].sort((a, z) => z.value_cad - a.value_cad).map((h) => { const ru = state.meta.risk_units[h.ticker]; const col = RISKBAND.find(([l]) => ru <= l)[1];
        return `<div class="row"><span><b>${esc(h.ticker)}</b><span class="sub">${esc(p.holding_names[h.ticker])}</span></span><span class="r">${money(h.value_cad)}<span class="sub"><span class="rx" style="background:${col}">${ru.toFixed(2)}×</span> · ${pct(h.value_cad / total)}</span></span></div>`; }).join("")}</div>`;
}

// ------------------------------------------------------------------ SSE
async function sse(url, body, on) {
  let res;
  try { res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch (e) { throw new UserError({ ...SERVER_DOWN, technical: String(e) }); }
  if (!res.ok) await ok(res);
  const reader = res.body.getReader(), dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      const ev = (chunk.match(/^event: (.*)$/m) || [])[1], data = (chunk.match(/^data: (.*)$/m) || [])[1];
      if (ev && data) on(ev, JSON.parse(data));
    }
  }
}

// ------------------------------------------------------------------ ask / thread
const thread = (pid = state.pid) => (state.threads[pid] ||= []);

async function ask(text) {
  const p = persona();
  const req = (text ?? $("#request").value).trim();
  if (!req) { $("#request").focus(); $("#request").placeholder = `Type an idea for ${p.name}, or pick a suggestion below`; return; }
  $("#request").value = "";
  const item = { id: `m${++state.seq}`, pid: p.id, request: req, status: "pending", step: 0 };
  thread(p.id).push(item);
  renderThread(item.id);
  $("#runBtn").disabled = true;
  try {
    await sse("/api/analyze", { persona_id: p.id, request: req, ...personaPayload(p) }, (ev, data) => {
      if (ev === "step") { const i = FLOW.findIndex(([k]) => data.label.startsWith(k)); if (i >= 0) { item.step = i; updatePending(item); } }
      else if (ev === "result") { Object.assign(item, { status: "done", trace: data }); addHistory(item); }
      else if (ev === "error") { Object.assign(item, { status: "error", error: data }); }
    });
    if (item.status === "pending") Object.assign(item, { status: "error", error: { title: "The analysis stopped without an answer", action: "Try again.", retry: true } });
  } catch (e) {
    Object.assign(item, { status: "error", error: e.f || { title: "Something went wrong", action: "Try again.", retry: true, technical: String(e) } });
  } finally {
    $("#runBtn").disabled = false;
    if (state.pid === item.pid) renderThread(item.id);
  }
}

function addDone(pid, request, trace, tab = null) {
  const item = { id: `m${++state.seq}`, pid, request, status: "done", trace, tab };
  thread(pid).push(item);
  addHistory(item);
  if (state.pid === pid) renderThread(item.id);
}

function addHistory(item) {
  state.history.unshift(item);
  $("#history").innerHTML = state.history.slice(0, 12).map((h) => { const v = vinfo(h.trace.result.verdict);
    return `<div class="h-item" data-h="${h.id}"><span class="dot" style="background:var(--${v.cls})"></span><span class="txt"><b>${esc(persona(h.pid).name)}</b> · ${esc(h.request)}</span></div>`; }).join("");
  $$(".h-item").forEach((el) => el.addEventListener("click", () => {
    const h = state.history.find((x) => x.id === el.dataset.h);
    showView("check"); selectPersona(h.pid); document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }));
}

function renderThread(focusId) {
  const items = thread();
  $("#thread").innerHTML = items.map((it) => `<div class="msg-user">${esc(it.request)}</div>
    <div class="msg-ai" id="${it.id}"><div class="ai-avatar">${AI_SVG}</div><div style="min-width:0">${aiBody(it)}</div></div>`).join("");
  items.forEach(bindItem);
  if (focusId) document.getElementById(focusId)?.scrollIntoView({ behavior: "smooth", block: "start" });
}
function aiBody(it) {
  if (it.status === "pending") return `<div class="card answer">${flowHtml(null, it.step)}<div style="padding:14px 20px;color:var(--ink-2)">Agents are working on it…</div></div>`;
  if (it.status === "error") return errorCard(it.error, it.id);
  return answerHtml(it);
}
function updatePending(it) {
  const el = document.getElementById(it.id);
  if (el && it.status === "pending") el.querySelector(".flow").outerHTML = flowHtml(null, it.step);
}
function bindItem(it) {
  const root = document.getElementById(it.id);
  if (!root) return;
  root.querySelector("[data-retry]")?.addEventListener("click", () => { state.threads[it.pid] = thread(it.pid).filter((x) => x !== it); ask(it.request); });
  if (it.status !== "done") return;
  if (!it.trace.toolbox) { bindFollowup(it, root); return; }
  $$(".tabs button", root).forEach((b) => b.addEventListener("click", () => openTab(it, b.dataset.tab)));
  openTab(it, it.tab || "overview");
  drawGauge(it);
  renderChat(it);
}

// ------------------------------------------------------------------ agent flow
function flowHtml(trace, activeIdx = null) {
  const steps = trace?.steps || [];
  const stoppedEarly = trace && !trace.toolbox;
  return `<div class="flow">${FLOW.map(([, name], i) => {
    let cls = "", ms = "";
    if (trace) {
      if (stoppedEarly && i > 0) { cls = "skip"; ms = "not needed"; }
      else {
        cls = "done";
        const lat = steps.filter((s) => FLOW_AGENTS[i].includes(s.agent)).map((s) => s.latency_ms || 0);
        ms = i === 1 ? "code" : i === 6 ? `${trace.guardrail?.checked || 0} checks` : lat.length ? `${(Math.max(...lat) / 1000).toFixed(1)}s` : "";
      }
    } else { cls = i < activeIdx ? "done" : i === activeIdx ? "active" : ""; ms = i < activeIdx ? "done" : i === activeIdx ? "running" : ""; }
    return `${i ? `<div class="edge ${cls === "done" ? "done" : ""}"></div>` : ""}<div class="node ${cls}"><span class="nd"></span><span class="nm">${name}</span><span class="ms">${ms}</span></div>`;
  }).join("")}</div>`;
}

// ------------------------------------------------------------------ answer
function goalOfAction(trace) {
  const gid = trace.action?.goal_id;
  return (trace.toolbox?.rules.buckets_after || []).find((g) => g.goal_id === gid);
}
function answerHtml(it) {
  const t = it.trace, r = t.result, v = vinfo(r.verdict), a = t.action || {}, tool = t.toolbox;
  const g = goalOfAction(t);
  const head = `${flowHtml(t)}
    <div class="v-head v-${v.cls}">
      <div><div class="v-tagline"><span class="vtag">${v.label}</span>${r.confidence && r.confidence !== "n/a" ? `<span class="muted">${esc(title(r.confidence))} confidence</span>` : ""}</div>
        <div class="v-title">${esc(r.headline)}</div><p class="v-sum">${esc(r.plain_summary)}</p></div>
      ${g ? budgetTile(g) : "<div></div>"}
    </div>
    ${r.verdict_adjustment ? `<p class="override">Rule override: ${esc(r.verdict_adjustment)}</p>` : ""}
    <div class="meta-row">
      ${tool ? `<span>Interpreted as <b>${esc(a.action)} ${money(+a.amount_cad)} of ${esc(a.ticker)}</b> · funded by <b>${esc(a.funding === "new_money" ? "new money" : a.funding)}</b> · goal <b>${esc(a.goal_id)}</b></span>` : r.understood ? `<span>Understood so far: <b>${esc(r.understood)}</b></span>` : ""}
      ${t.grounding?.summary ? `<span>Numbers verified <b>${esc(t.grounding.summary.replace(" figures traced to data", ""))}</b></span>` : ""}
      <span>Run <b>${esc(t.run_id)}</b> · ${t.elapsed_s}s</span></div>`;
  if (!tool) return `<div class="card answer">${head}</div>${followupHtml(it)}`;
  const tabs = [["overview", "Overview"], ["whatif", "What-if simulator"], ["rules", "Rules & limits"], ["xray", "Portfolio X-ray"], ["stress", "Stress tests"],
    ["asset", `About ${tool.security.ticker}`], ["debate", "Agent debate"], ["evidence", "Evidence & audit"]];
  return `<div class="card answer">${head}
    <div class="tabs">${tabs.map(([k, l]) => `<button data-tab="${k}">${esc(l)}</button>`).join("")}</div>
    <div class="tab-body" id="tb-${it.id}"></div>
    <div class="chat" id="ch-${it.id}"></div></div>`;
}

function budgetTile(g) {
  const used = g.risky_share / g.allowed_max_risky, over = used > 1, filled = Math.min(5, Math.round(used * 5));
  return `<div class="btile"><div class="bt-label">${esc(g.label.split("(")[0].trim())} · risk budget used</div>
    <div class="bt-val">${pct(used)} <span class="delta ${over ? "bad" : used > 0.85 ? "warn" : "good"}">${over ? "over limit" : "within limit"}</span></div>
    <div class="segbar">${[0, 1, 2, 3, 4].map((i) => `<span class="${i < filled ? (over ? "over" : "on") : ""}"></span>`).join("")}</div>
    <div class="segbar-scale"><span>${pct(g.risky_share)} of S&amp;P 500 risk</span><span>limit ${pct(g.allowed_max_risky)}</span></div></div>`;
}
function drawGauge(it) {
  const g = goalOfAction(it.trace), el = document.getElementById(`g-${it.id}`);
  if (!g || !el || !window.Chart) return;
  const used = g.risky_share / g.allowed_max_risky, col = used > 1 ? "#dc2626" : used > 0.85 ? "#d97706" : "#059669";
  state.charts[el.id]?.destroy();
  state.charts[el.id] = new Chart(el, { type: "doughnut",
    data: { datasets: [{ data: [Math.min(used, 1), Math.max(0, 1 - used)], backgroundColor: [col, "#e2e8f0"], borderWidth: 0 }] },
    options: { rotation: -90, circumference: 180, cutout: "74%", responsive: false, animation: false, plugins: { legend: { display: false }, tooltip: { enabled: false } } } });
}

function openTab(it, tab) {
  it.tab = tab;
  const root = document.getElementById(it.id);
  $$(".tabs button", root).forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  const body = document.getElementById(`tb-${it.id}`), t = it.trace;
  body.innerHTML = ({ overview: tabOverview, whatif: tabWhatif, rules: tabRules, xray: tabXray, stress: tabStress, asset: tabAsset, debate: tabDebate, evidence: tabEvidence })[tab](t, it);
  if (tab === "xray") bindXray(t, it);
  if (tab === "whatif") bindWhatif(t, it);
  if (tab === "stress") stressChart(t, it);
}

const pill = (verdict) => { const i = vinfo(verdict); return `<span class="status s-${i.cls}">${i.short}</span>`; };
const stepOut = (t, a) => (t.steps.find((s) => s.agent === a) || {}).output || {};

const clean = (x) => x.replace(/^(Hard constraint breached|Soft check \(preference\) worsened|Pre-existing breach not created by this action): /, "");
function variantRow(c) {
  const fix = c.fixes.map(clean), still = c.still.map(clean), fresh = c.new_issues.map(clean);
  return `<tr><td><b>${esc(c.variant)}</b></td>
    <td class="nowrap"><span class="vt-from">${vinfo(c.base_ceiling).short}</span> → <span class="vt-to t-${vinfo(c.ceiling).cls}">${vinfo(c.ceiling).short}</span></td>
    <td class="small">${fix.map((x) => `<div><span class="t-ok">Fixed:</span> ${esc(x)}</div>`).join("")}
      ${still.map((x) => `<div><span class="t-cond">Still:</span> ${esc(x)}</div>`).join("")}
      ${fresh.map((x) => `<div><span class="t-bad">New:</span> ${esc(x)}</div>`).join("")}</td></tr>`;
}
function tabOverview(t) {
  const r = t.result;
  const changed = (t.toolbox.counterfactuals || []).filter((c) => c.changes_result ?? c.ceiling !== t.toolbox.rules.ceiling);
  const better = changed.filter((c) => (c.direction || "better") === "better");
  const ol = (xs) => `<ol class="plain">${(xs || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`;
  return `<div class="ov">
      <div><h4 class="h">Why</h4>${ol(r.key_reasons)}</div>
      <div><h4 class="h">What would change this answer</h4>${ol(r.no_longer_valid_if)}</div>
    </div>
    ${changed.length ? `<h4 class="h" style="margin-top:22px">${better.length ? "Versions of this idea that would change the verdict" : "Versions that would make it worse"}
      <span class="muted small" style="font-weight:400"> · recomputed with the same rules · information, not advice</span></h4>
    <div class="table-wrap"><table class="data vtable"><thead><tr><th style="width:34%">Version</th><th>Verdict</th><th>What changes</th></tr></thead>
      <tbody>${changed.map(variantRow).join("")}</tbody></table></div>` : ""}
    ${r.debate_takeaway ? `<p class="takeaway"><b>Judge's takeaway.</b> ${esc(r.debate_takeaway)}</p>` : ""}`;
}

// ------------------------------------------------------------------ follow-up chat (grounded in this analysis)
const DEFAULT_QS = ["Why is this risky for me?", "Explain it in simple words", "How did this do in 2022?", "What would make this idea fit my profile?"];
function renderChat(it) {
  const el = document.getElementById(`ch-${it.id}`);
  if (!el) return;
  it.chat ||= [];
  const last = [...it.chat].reverse().find((m) => m.role === "ai" && m.suggested?.length);
  const sugg = it.chat.length ? (last?.suggested || []) : DEFAULT_QS;
  el.innerHTML = `<div class="chat-head">${AI_SVG.replace('stroke="#fff"', 'stroke="#2563eb"').replace('stroke="#fff"', 'stroke="#2563eb"')}<b>Ask a follow-up about this answer</b>
      <span class="small muted">answers only from this analysis · numbers verified</span></div>
    <div class="chat-msgs">${it.chat.map((m) => m.role === "user" ? `<div class="cm-user">${esc(m.text)}</div>` : m.pending
      ? `<div class="cm-ai"><span class="typing"><i></i><i></i><i></i></span></div>`
      : m.error ? `<div class="cm-ai err-inline"><b>${esc(m.error.title)}</b> ${esc(m.error.action || "")}</div>`
      : `<div class="cm-ai">${esc(m.text)}
          <div class="cm-meta">${esc(m.grounding?.checked || m.instant ? m.grounding.summary : "no figures cited")}${m.guardrail === "GUARDRAIL_INTERVENED" ? " · guardrail edited this answer" : ""}</div>
          ${m.instant ? instantCard(m.instant) : ""}
          ${m.rerun ? `<button class="btn cm-rerun" data-rerun="${esc(m.rerun)}">Run the full AI analysis: “${esc(m.rerun)}”</button>` : ""}</div>`).join("")}</div>
    ${sugg.length ? `<div class="pills">${sugg.map((q) => `<button class="pill" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>` : ""}
    <div class="followup-input"><input data-cin placeholder="e.g. What if I only put in half?"><button class="btn" data-csend>Ask</button></div>`;
  const send = (q) => { q = q.trim(); if (q) askChat(it, q); };
  $("[data-csend]", el).addEventListener("click", () => send($("[data-cin]", el).value));
  $("[data-cin]", el).addEventListener("keydown", (e) => { if (e.key === "Enter") send(e.target.value); });
  $$("[data-q]", el).forEach((b) => b.addEventListener("click", () => send(b.dataset.q)));
  $$("[data-rerun]", el).forEach((b) => b.addEventListener("click", () => ask(b.dataset.rerun)));
}
function instantCard(c) {
  const v = vinfo(c.ceiling), a = c.action, g = c.goal, over = g.after > g.limit + 1e-9;
  return `<div class="instant v-${v.cls}"><div class="split" style="margin:0 0 4px"><b>Instant check · ${esc(a.ticker)} ${money(a.amount_cad)} ${a.funding === "new_money" ? "new money" : `from ${esc(a.funding)}`}</b>${pill(c.ceiling)}</div>
    <div class="small">${esc(g.label)} risk: ${pct(g.before)} → <b style="color:${over ? "var(--bad)" : "inherit"}">${pct(g.after)}</b> (limit ${pct(g.limit)})</div>
    ${c.reasons.length ? `<ul class="vw">${c.reasons.map((x) => `<li>${esc(clean(x))}</li>`).join("")}</ul>` : `<div class="small muted">No limit or preference breached.</div>`}
    <div class="cm-meta">computed by the rules engine · no AI</div></div>`;
}
async function askChat(it, q) {
  const history = it.chat.filter((m) => !m.pending && !m.error).map((m) => ({ role: m.role, text: m.text }));
  it.chat.push({ role: "user", text: q }, { role: "ai", pending: true });
  renderChat(it);
  const slot = it.chat[it.chat.length - 1];
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: it.trace.run_id, question: q, history }) }).then(ok);
    if (r.error) Object.assign(slot, { pending: false, error: r.error });
    else Object.assign(slot, { pending: false, text: r.answer, rerun: r.rerun_request, instant: r.instant_check, suggested: r.suggested_questions, grounding: r.grounding, guardrail: r.guardrail });
  } catch (e) {
    Object.assign(slot, { pending: false, error: e.f || { title: "Couldn't answer", action: "Try again." } });
  }
  renderChat(it);
  document.getElementById(`ch-${it.id}`)?.querySelector(".chat-msgs")?.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ------------------------------------------------------------------ what-if simulator (deterministic, instant)
function tabWhatif(t, it) {
  const p = persona(t.persona_id), a = t.action, id = it.id;
  const amt = +a.amount_cad, max = Math.max(20000, Math.ceil((amt * 2) / 5000) * 5000);
  const goal = p.goals.find((g) => g.id === a.goal_id) || p.goals[0];
  const groups = {};
  Object.entries(state.meta.universe).filter(([k]) => k !== "CASH").forEach(([k, v]) => { (groups[title(v.asset_class)] ||= []).push([k, v.name]); });
  const holdings = [...new Map(p.holdings.map((h) => [h.ticker, h])).values()];
  return `<div class="whatif">
    <div class="wi-controls">
      <div class="wi-row"><label>Amount <b id="wa-${id}">${money(amt)}</b></label><input type="range" id="wamt-${id}" min="0" max="${max}" step="250" value="${amt}"></div>
      <div class="wi-row"><label>Asset</label><select id="wtk-${id}">${Object.entries(groups).map(([g, xs]) => `<optgroup label="${esc(g)}">${xs.map(([k, n]) => `<option value="${k}" ${k === a.ticker ? "selected" : ""}>${esc(k)} · ${esc(n)}</option>`).join("")}</optgroup>`).join("")}</select></div>
      <div class="wi-row"><label>Paid with</label><select id="wfd-${id}"><option value="new_money">New money</option>${holdings.map((h) => `<option value="${h.ticker}|${h.goal}" ${h.ticker === a.funding ? "selected" : ""}>Sell ${esc(h.ticker)} (${money(h.value_cad)} held)</option>`).join("")}</select></div>
      <div class="wi-row"><label>For goal</label><select id="wgl-${id}">${p.goals.map((g) => `<option value="${g.id}" ${g.id === goal.id ? "selected" : ""}>${esc(g.label)}</option>`).join("")}</select></div>
      <div class="wi-row"><label>Goal horizon <b id="wh-${id}">${goal.horizon_years} years</b></label><input type="range" id="whz-${id}" min="0" max="40" step="0.5" value="${goal.horizon_years}"></div>
      <div class="wi-row"><label>Risk profile</label><div class="seg" id="wrt-${id}">${Object.keys(RISK).map((k) => `<button data-v="${k}" class="${k === p.risk_tolerance ? "on" : ""}">${RISK[k]}</button>`).join("")}</div></div>
      <button class="link" id="wreset-${id}">Reset to the original idea</button>
    </div>
    <div class="wi-out" id="wout-${id}"><div class="skeleton"></div></div>
  </div>`;
}
function bindWhatif(t, it) {
  const p = persona(t.persona_id), id = it.id, q = (s) => document.getElementById(`${s}-${id}`);
  let timer, tol = p.risk_tolerance, horizonTouched = false;
  const syncHorizon = () => { const g = p.goals.find((x) => x.id === q("wgl").value); q("whz").value = g.horizon_years; q("wh").textContent = `${g.horizon_years} years`; horizonTouched = false; };
  const action = () => {
    const [fund, fgoal] = q("wfd").value.split("|");
    return { action: "buy", ticker: q("wtk").value, amount_cad: +q("wamt").value, goal_id: q("wgl").value, funding: fund, funding_goal_id: fgoal || null };
  };
  const run = () => {
    q("wa").textContent = money(+q("wamt").value);
    q("wh").textContent = `${q("whz").value} years`;
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        const r = await fetch("/api/whatif", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ persona_id: p.id, ...personaPayload(p), action: action(), horizon_years: horizonTouched ? +q("whz").value : null, risk_tolerance: tol }) }).then(ok);
        renderWhatif(t, it, r, action(), tol !== p.risk_tolerance || horizonTouched);
      } catch (e) { q("wout").innerHTML = errorCard(e.f || { title: "Couldn't recompute", technical: String(e) }); }
    }, 120);
  };
  ["wamt", "wtk", "wfd"].forEach((k) => q(k).addEventListener("input", run));
  q("wgl").addEventListener("input", () => { syncHorizon(); run(); });
  q("whz").addEventListener("input", () => { horizonTouched = true; run(); });
  $$(`#wrt-${id} button`).forEach((b) => b.addEventListener("click", () => { tol = b.dataset.v; $$(`#wrt-${id} button`).forEach((x) => x.classList.toggle("on", x === b)); run(); }));
  q("wreset").addEventListener("click", () => openTab(it, "whatif"));
  run();
}
function renderWhatif(t, it, r, a, profileChanged) {
  const p = persona(t.persona_id), v = vinfo(r.ceiling);
  const g = r.buckets_after.find((x) => x.goal_id === r.goal_id), b = r.buckets_before.find((x) => x.goal_id === r.goal_id);
  const sc = Math.max(0.3, g.risky_share, g.allowed_max_risky, b.risky_share) * 1.12, over = g.status === "over limit";
  const fundTxt = a.funding === "new_money" ? "with new money" : `paid by selling ${a.funding}`;
  const req = `Put $${Math.round(a.amount_cad).toLocaleString("en-US")} into ${a.ticker} ${fundTxt}, for my ${p.goals.find((x) => x.id === a.goal_id).label.toLowerCase()} goal.`;
  const orig = t.toolbox.rules.ceiling;
  document.getElementById(`wout-${it.id}`).innerHTML = `
    <div class="wi-verdict v-${v.cls}"><div class="badge-ring sm">${ICON[v.cls]}</div>
      <div><div class="v-label">${v.label}</div>
      <div class="small muted">${r.ceiling === orig ? "Same verdict as the original idea" : `Changed from <b>${vinfo(orig).short}</b>`}</div></div></div>
    <div class="wi-budget"><div class="split" style="margin:0 0 6px"><b>${esc(g.label)}</b><span class="small muted">${g.horizon_years}-year horizon · limit ${pct(g.allowed_max_risky)}</span></div>
      <div class="track"><div class="b" style="width:${(b.risky_share / sc) * 100}%"></div><div class="a ${over ? "over" : ""}" style="width:${(g.risky_share / sc) * 100}%"></div>
        <div class="lim" style="left:${(g.allowed_max_risky / sc) * 100}%"></div></div>
      <div class="small" style="margin-top:6px">${pct(b.risky_share)} → <b style="color:${over ? "var(--bad)" : "var(--ink)"}">${pct(g.risky_share)}</b> of S&amp;P 500 risk · ${a.ticker} is ${r.risk_units.toFixed(2)}× the S&amp;P 500</div></div>
    <div class="wi-reasons">${r.reasons.length ? `<ul class="list ${r.ceiling === "INCONSISTENT" ? "red" : "amber"}">${r.reasons.map((x) => `<li>${esc(clean(x))}</li>`).join("")}</ul>` : `<div class="alert alert-info" style="margin:0">No limit or preference is breached by this version.</div>`}</div>
    <div class="wi-foot"><span class="small muted">Instant · deterministic rules · no AI involved</span>
      ${profileChanged ? `<span class="small muted">Profile changes are hypothetical; the full analysis uses ${esc(p.name)}'s stated profile.</span>` : `<button class="btn" data-full>Run full AI analysis on this version</button>`}</div>`;
  document.querySelector(`#wout-${it.id} [data-full]`)?.addEventListener("click", () => ask(req));
}

function checkPill(c) {
  if (c.passed) return `<span class="status s-ok">Pass</span>`;
  if (c.blocking) return `<span class="status s-bad">Breach</span>`;
  if (c.status.startsWith("worsened")) return `<span class="status s-cond">Preference worsened</span>`;
  return `<span class="status s-cond">${esc(c.status.replace("pre-existing breach, ", "Pre-existing, "))}</span>`;
}
function tabRules(t) {
  const rules = t.toolbox.rules, bmap = Object.fromEntries(rules.buckets_before.map((g) => [g.goal_id, g]));
  const sc = Math.max(0.3, ...rules.buckets_after.map((g) => Math.max(g.risky_share, g.allowed_max_risky, bmap[g.goal_id]?.risky_share || 0))) * 1.12;
  return `<div class="sec-title" style="margin-top:0">Pre-trade checks <span class="muted small" style="font-weight:400">· hard limits veto · preferences add conditions</span></div>
    <div class="table-wrap"><table class="data"><thead><tr><th>Check</th><th>Type</th><th class="num">Before</th><th class="num">After</th><th>Result</th></tr></thead><tbody>
    ${rules.constraints.map((c) => `<tr><td>${esc(c.rule)}<span class="sub">${esc(c.origin && c.origin !== "stated" ? c.origin : "stated in the brief")}</span></td>
      <td>${c.severity === "hard" ? "Hard limit" : "Preference"}</td><td class="num">${fmtVal(c.before)}</td><td class="num"><b>${fmtVal(c.after)}</b></td><td>${checkPill(c)}</td></tr>`).join("")}
    </tbody></table></div>
    <div class="sec-title">Risk budget by goal <span class="muted small" style="font-weight:400">· S&amp;P 500 = 100%</span></div>
    <div class="box">${rules.buckets_after.map((g) => { const b = bmap[g.goal_id]?.risky_share || 0, over = g.status === "over limit";
      return `<div class="budget"><div><b>${esc(g.label)}</b><span class="sub">${g.horizon_years ? `${g.horizon_years}-year horizon` : "needed any time"} · bound by ${esc(g.binding_limit)}</span></div>
        <div class="track"><div class="b" style="width:${(b / sc) * 100}%"></div><div class="a ${over ? "over" : ""}" style="width:${(g.risky_share / sc) * 100}%"></div>
          <div class="lim" style="left:${(g.allowed_max_risky / sc) * 100}%"><span>limit ${pct(g.allowed_max_risky)}</span></div></div>
        <div class="num" style="text-align:right">${pct(b)} → <b>${pct(g.risky_share)}</b><span class="sub" style="color:${over ? "var(--bad)" : "var(--ok)"}">${over ? "over limit" : "within limit"}</span></div></div>`; }).join("")}
      <div class="key"><span><i style="background:var(--before)"></i>Before</span><span><i style="background:var(--after)"></i>After</span><span><i style="background:var(--ink);width:2px;height:12px"></i>Limit = lower of horizon capacity and stated tolerance</span></div></div>`;
}

function tabXray(t, it) {
  return `<div class="xray-charts">
      <div class="box"><h4>Before</h4><div class="donut-box"><canvas id="xb-${it.id}"></canvas></div></div>
      <div class="box"><h4>After</h4><div class="donut-box"><canvas id="xa-${it.id}"></canvas></div></div></div>
    <div class="split"><span class="sec-title" style="margin:0">Look-through exposure</span>
      <div class="seg" id="seg-${it.id}"><button data-k="asset_class" class="on">Asset class</button><button data-k="equity_sectors">Sector</button><button data-k="equity_geography">Region</button><button data-k="currency">Currency</button></div></div>
    <div class="table-wrap" id="xt-${it.id}"></div>`;
}
function bindXray(t, it) {
  donut(`xb-${it.id}`, t.toolbox.exposures_before.asset_class, "62%");
  donut(`xa-${it.id}`, t.toolbox.exposures_after.asset_class, "62%");
  const draw = (k) => {
    const b = t.toolbox.exposures_before[k] || {}, a = t.toolbox.exposures_after[k] || {};
    const keys = [...new Set([...Object.keys(b), ...Object.keys(a)])].sort((x, y) => Math.max(a[y] || 0, b[y] || 0) - Math.max(a[x] || 0, b[x] || 0)).slice(0, 10);
    const mx = Math.max(0.01, ...keys.map((x) => Math.max(a[x] || 0, b[x] || 0)));
    document.getElementById(`xt-${it.id}`).innerHTML = `<table class="data"><thead><tr><th>${k.includes("equity") ? "Share of equities (funds looked through)" : "Share of portfolio"}</th><th class="num">Before</th><th class="num">After</th><th class="num">Change</th><th style="width:34%"></th></tr></thead><tbody>
      ${keys.map((x) => { const bv = b[x] || 0, av = a[x] || 0, d = av - bv;
        return `<tr><td>${esc(title(x))}</td><td class="num">${pct(bv, 1)}</td><td class="num"><b>${pct(av, 1)}</b></td><td class="num" style="color:${Math.abs(d) < 5e-4 ? "var(--muted)" : "var(--ink)"}">${Math.abs(d) < 5e-4 ? "—" : pts(bv, av)}</td>
        <td><div class="hbar" style="width:${(bv / mx) * 100}%;background:var(--before)"></div><div class="hbar" style="width:${(av / mx) * 100}%;background:var(--after);margin-top:3px"></div></td></tr>`; }).join("")}</tbody></table>`;
  };
  $$(`#seg-${it.id} button`).forEach((btn) => btn.addEventListener("click", () => { $$(`#seg-${it.id} button`).forEach((x) => x.classList.toggle("on", x === btn)); draw(btn.dataset.k); }));
  draw("asset_class");
}

const metric = (k, v, d) => `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`;
function tabStress(t, it) {
  const rb = t.toolbox.risk_before, ra = t.toolbox.risk_after, eb = t.toolbox.exposures_before, ea = t.toolbox.exposures_after;
  const bmap = Object.fromEntries(t.toolbox.stress_before.map((s) => [s.id, s]));
  return `<div class="metrics">
      ${metric("Annual volatility", pct(ra.annual_volatility, 1), `${pct(rb.annual_volatility, 1)} before · ${pts(rb.annual_volatility, ra.annual_volatility)}`)}
      ${metric("Worst peak-to-trough", pct(ra.max_drawdown, 1), `${pct(rb.max_drawdown, 1)} before`)}
      ${metric("Worst 12 months", pct(ra.worst_12m_return, 1), `${pct(rb.worst_12m_return, 1)} before`)}
      ${metric("Foreign currency", pct(ea.foreign_currency_share), `${pct(eb.foreign_currency_share)} before`)}</div>
    <div class="chart-box"><canvas id="sc-${it.id}"></canvas></div>
    <div class="table-wrap" style="margin-top:14px"><table class="data"><thead><tr><th>Scenario</th><th class="num">Before</th><th class="num">After</th></tr></thead><tbody>
      ${t.toolbox.stress_after.map((s) => `<tr><td>${esc(s.label)}<span class="sub">${s.type === "historical replay" ? "Historical replay" : "Hypothetical"} · ${esc(s.basis)}</span></td>
        <td class="num">${pct(bmap[s.id].impact_pct, 1)}<span class="sub">${money(bmap[s.id].impact_cad)}</span></td><td class="num"><b>${pct(s.impact_pct, 1)}</b><span class="sub">${money(s.impact_cad)}</span></td></tr>`).join("")}
    </tbody></table></div><p class="small muted">Window ${esc(ra.window)} · CAD · describes the past, not a forecast.</p>`;
}
function stressChart(t, it) {
  if (!window.Chart) return;
  const id = `sc-${it.id}`, after = t.toolbox.stress_after, bmap = Object.fromEntries(t.toolbox.stress_before.map((s) => [s.id, s]));
  state.charts[id]?.destroy();
  state.charts[id] = new Chart(document.getElementById(id), { type: "bar",
    data: { labels: after.map((s) => (s.label.length > 38 ? `${s.label.slice(0, 36)}…` : s.label)),
      datasets: [{ label: "Before", data: after.map((s) => +(bmap[s.id].impact_pct * 100).toFixed(1)), backgroundColor: "#cbd5e1", borderRadius: 4 },
        { label: "After", data: after.map((s) => +(s.impact_pct * 100).toFixed(1)), backgroundColor: "#2563eb", borderRadius: 4 }] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10 } },
      tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.raw}%` } } },
      scales: { x: { ticks: { callback: (v) => `${v}%` }, grid: { color: "#f1f5f9" } }, y: { grid: { display: false } } } } });
}

function tabAsset(t) {
  const s = t.toolbox.security, f = s.company_snapshot;
  let html = `<div class="metrics">
      ${metric("Volatility per year", pct(s.annual_volatility, 1), `${(+s.risk_units_vs_spy).toFixed(2)}× the S&amp;P 500`)}
      ${metric("Worst peak-to-trough", pct(s.max_drawdown, 1), `low on ${esc(s.max_drawdown_date)}`)}
      ${metric("Worst 12 months", pct(s.worst_12m_return, 1), esc(s.window))}
      ${metric("Annualised return", pct(s.annualised_return, 1), "past only, not a forecast")}</div>`;
  if (f) html += `<div class="sec-title">Company snapshot <span class="muted small" style="font-weight:400">· ${esc(s.company_snapshot_source)}</span></div>
    <div class="metrics">${metric("Market cap", bigMoney(f.market_cap, esc(f.currency)), `listed since ${esc(f.listed_since || "—")}`)}
      ${metric("Profit margin", pct(f.profit_margin, 1), `return on equity ${pct(f.return_on_equity, 1)}`)}
      ${metric("Revenue growth", pct(f.revenue_growth_yoy, 1), "year over year")}
      ${metric("Dividend yield", f.dividend_yield_pct != null ? `${f.dividend_yield_pct}%` : "—", `debt/equity ${f.debt_to_equity_pct != null ? `${f.debt_to_equity_pct.toFixed(0)}%` : "—"}`)}</div>`;
  if (s.esg_screen) html += `<div class="alert ${s.esg_screen === "not held" ? "alert-warn" : "alert-info"}"><b>ESG screen:</b> ${esc(s.esg_screen)} by Vanguard ESG U.S. Stock ETF (SEC N-PORT filing, holdings as of 2026-05-31).</div>`;
  if (t.toolbox.esg_after) {
    const a = t.toolbox.esg_after, b = t.toolbox.esg_before;
    html += `<div class="sec-title">ESG: what the data can and cannot say</div><div class="cols">
      <div class="box"><dl class="kv"><dt>Screen</dt><dd>${esc(a.screen)}</dd><dt>Excluded-sector holdings</dt><dd>${esc(a.direct_holdings_in_excluded_sectors.join(", ") || "none")}</dd>
        <dt>Energy via funds &amp; stocks</dt><dd>${pct(b.energy_lookthrough_share_of_portfolio, 1)} → <b>${pct(a.energy_lookthrough_share_of_portfolio, 1)}</b></dd></dl>
        <div class="alert alert-warn">${esc(a.controversy_status)}</div></div>
      <div class="table-wrap"><table class="data"><thead><tr><th>Single stock</th><th>ESGV screen (SEC N-PORT)</th></tr></thead><tbody>
        ${Object.entries(a.esgv_screen_by_holding || {}).map(([k, v]) => `<tr><td><b>${esc(k)}</b></td><td>${esc(v)}</td></tr>`).join("") || '<tr><td colspan="2" class="muted">No single stocks</td></tr>'}</tbody></table></div></div>`;
  }
  if (s.note) html += `<p class="small muted">${esc(s.note)}</p>`;
  return html;
}

function tabDebate(t) {
  const side = (name, c, o, r) => `<div class="side" style="--c:${c}"><h4>${name}</h4><p class="pos">${esc(o.position)}</p>
    ${(o.arguments || []).map((x) => `<div class="arg"><b>${esc(x.claim)}</b><span class="sub">${esc(x.evidence)}</span></div>`).join("")}
    ${(r.rebuttals || []).length ? `<div class="sec-title" style="margin:12px 0 4px">Rebuttal round</div>${r.rebuttals.map((x) => `<div class="arg">${esc(x.response)}</div>`).join("")}` : ""}
    ${(r.concessions || []).map((x) => `<div class="concede">Concedes: ${esc(x)}</div>`).join("")}</div>`;
  const prof = stepOut(t, "profile"), grd = stepOut(t, "guardian");
  return `<div class="debate">${side("Advocate · case for", "#2563eb", stepOut(t, "advocate"), stepOut(t, "advocate_rebuttal"))}${side("Skeptic · case against", "#d97706", stepOut(t, "skeptic"), stepOut(t, "skeptic_rebuttal"))}</div>
    <div class="cols" style="margin-top:14px">
      <div class="box"><h4>Profile agent · tolerance vs capacity</h4>${esc(prof.tolerance_vs_capacity)}
        ${prof.question_for_investor ? `<div class="alert alert-info">Question for ${esc(persona(t.persona_id).name)}: ${esc(prof.question_for_investor)}</div>` : ""}</div>
      <div class="box"><h4>Guardian agent</h4>${esc(grd.hard_constraint_summary)}
        <ul class="list" style="margin-top:6px">${[...(grd.preference_conflicts || []), ...(grd.governance_flags || [])].map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div>`;
}

function tabEvidence(t) {
  const r = t.result, g = t.grounding || {}, gr = t.guardrail || {};
  const blob = URL.createObjectURL(new Blob([JSON.stringify(t, null, 2)], { type: "application/json" }));
  return `<div class="evidence">${[["Facts (from data)", r.facts], ["Assumptions", r.assumptions], ["Fictional", r.fictional], ["Limits of this analysis", r.limits]]
      .map(([h, xs]) => `<div class="box"><h4>${h}</h4><ul>${(xs || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`).join("")}</div>
    <div class="metrics" style="margin-top:14px">
      ${metric("Numbers verified", esc((g.summary || "—").replace(" figures traced to data", "")), g.ungrounded?.length ? `not found: ${esc(g.ungrounded.join(", "))}` : "every % and $ the agents wrote")}
      ${metric("Bedrock Guardrail", `${(gr.blocked || []).length} blocked`, `${(gr.flagged_not_blocked || []).length} flagged · ${gr.checked || 0} checked`)}
      ${metric("AI agent calls", t.steps.filter((s) => s.kind === "llm").length, `${(t.total_tokens || 0).toLocaleString()} tokens · Nova 2 Lite`)}
      ${metric("Audit record", t.s3_uri ? "Saved to S3" : "Local only", esc(t.s3_uri ? t.s3_uri.split("/").pop() : ""))}</div>
    ${(gr.blocked || []).map((b) => `<div class="alert alert-err">Guardrail blocked text in "${esc(b.field)}" (${esc([...(b.topics || []), ...(b.words || [])].join(", "))}). Original kept in the audit record.</div>`).join("")}
    ${(gr.flagged_not_blocked || []).map((b) => `<div class="alert alert-info">Guardrail flagged (not blocked) in "${esc(b.field)}": ${esc(b.text)}</div>`).join("")}
    <div class="sec-title">Execution trace</div>
    <div class="table-wrap"><table class="data"><thead><tr><th>#</th><th>Step</th><th>Kind</th><th class="num">Time</th><th class="num">Tokens</th><th>Numbers verified</th></tr></thead><tbody>
      ${t.steps.map((s, i) => `<tr><td>${i + 1}</td><td>${esc(title(s.agent))}</td><td>${s.kind === "llm" ? "Bedrock agent" : "Deterministic"}</td>
        <td class="num">${s.latency_ms ? `${(s.latency_ms / 1000).toFixed(1)}s` : "—"}</td><td class="num">${s.tokens ? s.tokens.toLocaleString() : "—"}</td>
        <td>${esc((t.grounding_by_agent || {})[s.agent]?.summary || "")}</td></tr>`).join("")}</tbody></table></div>
    <div class="sec-title">Data sources</div>
    <div class="box"><dl class="kv">${Object.entries(t.toolbox.provenance).map(([k, v]) => `<dt>${esc(title(k))}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
      ${t.s3_uri ? `<p class="small muted" style="margin:10px 0 0">Audit record: <code>${esc(t.s3_uri)}</code></p>` : ""}
      <p style="margin:10px 0 0"><a class="link" href="${blob}" download="secondlook_${esc(t.run_id)}.json">Download full trace (JSON)</a></p>
      <details class="raw"><summary>Show every agent's raw output</summary><pre class="json">${esc(JSON.stringify(t.steps, null, 2))}</pre></details></div>`;
}

// ------------------------------------------------------------------ follow-ups
function followupHtml(it) {
  const r = it.trace.result;
  const groups = r.universe_groups ? `<div class="universe">${Object.entries(r.universe_groups).map(([g, ts]) => `<div class="ugroup"><div class="lbl">${esc(g)}</div>
    <div class="pills">${ts.map((t) => `<button class="pill" data-pick="${esc(t)}" title="${esc(state.meta.universe[t]?.name || "")}">${esc(t)}</button>`).join("")}</div></div>`).join("")}</div>` : "";
  return `<div class="card followup" style="margin-top:10px"><b>${esc(r.followup_question || "What would you like to check?")}</b>
    ${(r.quick_answers || []).length ? `<div class="pills">${r.quick_answers.map((q) => `<button class="pill" data-answer="${esc(q)}">${esc(q)}</button>`).join("")}</div>` : ""}
    ${groups}
    <div class="followup-input"><input data-input placeholder="Or type your answer…"><button class="btn" data-go>Continue</button></div></div>`;
}
function bindFollowup(it, root) {
  const r = it.trace.result;
  const replace = (r.issues || []).some((i) => i === "override_attempt" || i === "unclear");
  const go = (ans) => { ans = ans.trim(); if (!ans) return; ask(replace ? ans : `${it.request.replace(/\s*\(Clarification:.*\)$/, "")} (Clarification: ${ans})`); };
  $("[data-go]", root).addEventListener("click", () => go($("[data-input]", root).value));
  $("[data-input]", root).addEventListener("keydown", (e) => { if (e.key === "Enter") go(e.target.value); });
  $$("[data-answer]", root).forEach((b) => b.addEventListener("click", () => go(b.dataset.answer)));
  $$("[data-pick]", root).forEach((b) => b.addEventListener("click", () => go(`I meant ${b.dataset.pick}`)));
}

// ------------------------------------------------------------------ compare
function renderComparePills() {
  const ps = ["Put $2,000 of new money into Bitcoin.", "Add $10,000 of new money to SPY.", "AI is the future. Put $15,000 of new money into NVIDIA.", "Put $10,000 of new money into Exxon (XOM) for the dividend."];
  $("#compareSuggestions").innerHTML = ps.map((s) => `<button class="pill">${esc(s)}</button>`).join("");
  $$("#compareSuggestions .pill").forEach((b) => b.addEventListener("click", () => { $("#compareRequest").value = b.textContent.trim(); compare(); }));
}
async function compare() {
  const req = $("#compareRequest").value.trim();
  if (!req) { $("#compareRequest").focus(); return; }
  $("#compareBtn").disabled = true;
  const who = (p) => `<div class="who"><div class="avatar" style="background:${pcolor(p)}">${initials(p)}</div><div><b>${esc(p.name)}, ${p.age}</b><span>${esc(RISK[p.risk_tolerance])} risk</span></div></div>`;
  $("#compareTable").innerHTML = "";
  $("#compareGrid").innerHTML = state.personas.map((p) => `<div class="card ccard" id="cc-${p.id}">${who(p)}<div class="skeleton" style="width:60%"></div><div class="skeleton"></div><div class="skeleton" style="width:80%"></div></div>`).join("");
  try {
    await sse("/api/compare", { request: req, custom_personas: state.personas.filter((x) => x.custom).slice(0, 3).map((x) => x.def) }, (ev, d) => {
      const p = persona(d.persona_id), el = document.getElementById(`cc-${p.id}`);
      if (ev === "error") { el.innerHTML = `${who(p)}${errorCard(d)}`; return; }
      const t = d.trace, r = t.result, v = vinfo(r.verdict), g = goalOfAction(t);
      el.style.setProperty("--vc", `var(--${v.cls})`);
      el.innerHTML = `${who(p)}<div>${pill(r.verdict)}</div><div class="hl">${esc(r.headline)}</div>
        ${g ? `<div class="small muted">Goal risk ${pct(g.risky_share)} vs limit ${pct(g.allowed_max_risky)}</div>` : ""}
        <ul>${(r.key_reasons || []).slice(0, 3).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <button class="link" data-open="${p.id}">Open full analysis →</button>`;
      el.querySelector("[data-open]").addEventListener("click", () => { showView("check"); selectPersona(p.id); addDone(p.id, req, t); });
    });
  } catch (e) { $("#compareGrid").innerHTML = errorCard(e.f || { title: "Comparison failed", technical: String(e) }); }
  finally { $("#compareBtn").disabled = false; }
}

// ------------------------------------------------------------------ custom investors (stored in this browser only)
const LS_KEY = "secondlook.customInvestors";
const readCustoms = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; } };
const writeCustoms = (xs) => { try { localStorage.setItem(LS_KEY, JSON.stringify(xs)); } catch { /* private mode */ } };
async function previewPersona(def) {
  const r = await fetch("/api/persona/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ persona: def }) });
  return ok(r);
}
async function loadCustoms() {
  for (const def of readCustoms()) {
    try { state.personas.push({ ...(await previewPersona(def)), def }); } catch { /* skip invalid saved profile */ }
  }
}
const TEMPLATES = {
  blank: { risk_tolerance: "moderate", knowledge_level: "intermediate", goals: [{ label: "Emergency fund", horizon_years: 0 }, { label: "Long-term growth", horizon_years: 15 }],
    holdings: [{ ticker: "CASH", value_cad: 10000, goal: "g1" }, { ticker: "XEQT.TO", value_cad: 30000, goal: "g2" }, { ticker: "XBB.TO", value_cad: 10000, goal: "g2" }],
    constraints: { min_liquid_cad: 10000, max_single_position_pct: 10, max_crypto_pct: 5, max_sector_pct: 50 } },
  house: { risk_tolerance: "moderate", knowledge_level: "novice", goals: [{ label: "Emergency fund", horizon_years: 0 }, { label: "House down payment", horizon_years: 3 }, { label: "Retirement", horizon_years: 30 }],
    holdings: [{ ticker: "CASH", value_cad: 8000, goal: "g1" }, { ticker: "CASH.TO", value_cad: 25000, goal: "g2" }, { ticker: "XBB.TO", value_cad: 10000, goal: "g2" }, { ticker: "XEQT.TO", value_cad: 12000, goal: "g3" }],
    constraints: { min_liquid_cad: 8000, max_single_position_pct: 10 } },
  retiree: { risk_tolerance: "low", knowledge_level: "sophisticated", goals: [{ label: "Cash reserve", horizon_years: 0 }, { label: "Retirement income", horizon_years: 2 }],
    holdings: [{ ticker: "CASH", value_cad: 30000, goal: "g1" }, { ticker: "ZST.TO", value_cad: 80000, goal: "g2" }, { ticker: "XBB.TO", value_cad: 120000, goal: "g2" }, { ticker: "VDY.TO", value_cad: 40000, goal: "g2" }, { ticker: "KO", value_cad: 15000, goal: "g2" }],
    constraints: { min_liquid_cad: 30000, max_single_position_pct: 8, exclude_crypto: true, avoid_volatile_names: true } },
  esg: { risk_tolerance: "high", knowledge_level: "intermediate", goals: [{ label: "Emergency fund", horizon_years: 0 }, { label: "Long-term growth", horizon_years: 20 }],
    holdings: [{ ticker: "CASH", value_cad: 6000, goal: "g1" }, { ticker: "ESGV", value_cad: 20000, goal: "g2" }, { ticker: "ICLN", value_cad: 5000, goal: "g2" }, { ticker: "XEF.TO", value_cad: 8000, goal: "g2" }],
    constraints: { min_liquid_cad: 6000, max_single_position_pct: 15, exclude_fossil_fuels: true } },
};
let draft = null;
function openBuilder(editId) {
  const existing = editId && state.personas.find((p) => p.id === editId);
  draft = existing ? JSON.parse(JSON.stringify(existing.def))
    : { id: `custom-${Math.random().toString(36).slice(2, 10)}`, name: "", age: 30, ...JSON.parse(JSON.stringify(TEMPLATES.blank)) };
  draft.editing = !!existing;
  showView("builder");
  renderBuilder();
}
function renderBuilder() {
  const d = draft, c = d.constraints || (d.constraints = {});
  const assetOpts = (sel) => Object.entries(state.meta.universe).map(([k, v]) => `<option value="${k}" ${k === sel ? "selected" : ""}>${esc(k)} · ${esc(v.name)}</option>`).join("");
  const goalOpts = (sel) => d.goals.map((g, i) => `<option value="g${i + 1}" ${`g${i + 1}` === sel ? "selected" : ""}>${esc(g.label || `Goal ${i + 1}`)}</option>`).join("");
  $("#builder").innerHTML = `
    <header class="page-head"><div><div class="crumb">${d.editing ? "Edit your investor" : "Create your own investor"}</div><h1>${esc(d.name || "New investor")}</h1>
      <div class="sub-head">Fictional profile, saved only in this browser. SecondLook then checks any idea against it, exactly like the official personas.</div></div></header>
    <div class="builder">
      <div class="b-form">
        ${d.editing ? "" : `<div class="card b-sec"><h3>Start from a template</h3><div class="pills">${[["blank", "Balanced saver"], ["house", "Saving for a house"], ["retiree", "Near retirement"], ["esg", "ESG-minded growth"]]
          .map(([k, l]) => `<button class="pill" data-tpl="${k}">${l}</button>`).join("")}</div></div>`}
        <div class="card b-sec"><h3>About the investor</h3>
          <div class="b-grid"><label>Name<input data-f="name" value="${esc(d.name)}" placeholder="e.g. Lea" maxlength="30"></label>
            <label>Age<input data-f="age" type="number" min="18" max="100" value="${d.age}"></label></div>
          <label>Risk profile</label><div class="seg wide" data-seg="risk_tolerance">${Object.keys(RISK).map((k) => `<button data-v="${k}" class="${d.risk_tolerance === k ? "on" : ""}">${RISK[k]}</button>`).join("")}</div>
          <label>Investing experience</label><div class="seg wide" data-seg="knowledge_level">${["novice", "intermediate", "sophisticated"].map((k) => `<button data-v="${k}" class="${d.knowledge_level === k ? "on" : ""}">${title(k)}</button>`).join("")}</div></div>
        <div class="card b-sec"><h3>Goals <span class="note">when will the money be needed?</span></h3>
          ${d.goals.map((g, i) => `<div class="b-row"><input data-g="${i}" data-k="label" value="${esc(g.label)}" placeholder="Goal name">
            <label class="inline"><input data-g="${i}" data-k="horizon_years" type="number" min="0" max="60" step="0.5" value="${g.horizon_years}"> years</label>
            ${d.goals.length > 1 ? `<button class="x" data-delg="${i}" title="Remove">×</button>` : ""}</div>`).join("")}
          ${d.goals.length < 4 ? `<button class="link" data-addg>+ Add a goal</button>` : ""}</div>
        <div class="card b-sec"><h3>Holdings <span class="note">fictional amounts in CAD</span></h3>
          ${d.holdings.map((h, i) => `<div class="b-row h"><select data-h="${i}" data-k="ticker">${assetOpts(h.ticker)}</select>
            <input data-h="${i}" data-k="value_cad" type="number" min="1" step="500" value="${h.value_cad}">
            <select data-h="${i}" data-k="goal">${goalOpts(h.goal)}</select>
            ${d.holdings.length > 1 ? `<button class="x" data-delh="${i}" title="Remove">×</button>` : ""}</div>`).join("")}
          ${d.holdings.length < 15 ? `<button class="link" data-addh>+ Add a holding</button>` : ""}</div>
        <div class="card b-sec"><h3>Limits &amp; preferences <span class="note">leave blank for none</span></h3>
          <div class="b-grid"><label>Minimum cash ($)<input data-c="min_liquid_cad" type="number" min="0" step="1000" value="${c.min_liquid_cad ?? ""}"></label>
            <label>Max in one stock / crypto (%)<input data-c="max_single_position_pct" type="number" min="0" max="100" value="${c.max_single_position_pct ?? ""}"></label>
            <label>Max in crypto (%)<input data-c="max_crypto_pct" type="number" min="0" max="100" value="${c.max_crypto_pct ?? ""}"></label>
            <label>Max in one sector (%)<input data-c="max_sector_pct" type="number" min="0" max="100" value="${c.max_sector_pct ?? ""}"></label></div>
          ${[["exclude_fossil_fuels", "Avoid fossil fuels and companies excluded by an ESG screen"], ["exclude_crypto", "No crypto at all"], ["avoid_volatile_names", "Prefer stable companies (flag single stocks over 2× S&P 500 volatility)"]]
            .map(([k, l]) => `<label class="check"><input type="checkbox" data-cb="${k}" ${c[k] ? "checked" : ""}> ${l}</label>`).join("")}</div>
      </div>
      <div class="b-preview"><div class="card b-sec sticky"><h3>Preview</h3><div id="bPreview" class="small muted">Fill in the profile to see the dashboard.</div>
        <div class="b-actions">${d.editing ? `<button class="link danger" id="bDelete">Delete investor</button>` : "<span></span>"}<button class="btn" id="bSave">${d.editing ? "Save changes" : "Save and start checking ideas"}</button></div></div></div>
    </div>`;
  bindBuilder();
  schedulePreview();
}
let previewT;
function schedulePreview() { clearTimeout(previewT); previewT = setTimeout(updatePreview, 250); }
async function updatePreview() {
  const el = $("#bPreview");
  if (!el) return;
  if (!draft.name) { el.innerHTML = `<span class="muted">Give the investor a name to see the preview.</span>`; return; }
  try {
    const p = await previewPersona(cleanDraft());
    const e = p.baseline.exposures;
    el.innerHTML = `<div class="b-kpi"><div><span>Portfolio</span><b>${money(e.total_value_cad)}</b></div><div><span>Past volatility</span><b>${pct(p.baseline.risk.annual_volatility, 1)}</b></div></div>
      ${p.baseline.goals.map((g) => { const sc = Math.max(g.allowed_max_risky, g.risky_share, 0.05) * 1.15, over = g.status === "over limit";
        return `<div class="row" style="display:block"><div style="display:flex;justify-content:space-between"><span>${esc(g.label)}</span><span class="r" style="color:${over ? "var(--bad)" : "inherit"}">${pct(g.risky_share)} of ${pct(g.allowed_max_risky)}</span></div>
        <div class="mini"><div class="f" style="width:${(g.risky_share / sc) * 100}%;background:${over ? "var(--bad)" : "var(--primary)"}"></div><div class="l" style="left:${(g.allowed_max_risky / sc) * 100}%"></div></div></div>`; }).join("")}
      ${p.baseline.goals.some((g) => g.status === "over limit") ? `<div class="alert alert-warn">A goal already starts over its risk limit. That's allowed, and SecondLook will point it out in every check.</div>` : ""}
      <div class="small muted" style="margin-top:8px">Risk = S&amp;P 500 equivalents · limit = lower of the goal's horizon capacity and the risk profile.</div>`;
    el.dataset.valid = "1";
  } catch (err) { el.innerHTML = `<div class="alert alert-err" style="margin:0">${esc(err.f?.title || "Check the profile")}</div>`; el.dataset.valid = ""; }
}
function cleanDraft() {
  const { editing, ...d } = draft;
  return { ...d, age: +d.age, goals: d.goals.map((g) => ({ label: g.label, horizon_years: +g.horizon_years })),
    holdings: d.holdings.map((h) => ({ ticker: h.ticker, value_cad: +h.value_cad, goal: h.goal })) };
}
function bindBuilder() {
  const B = $("#builder");
  $$("[data-tpl]", B).forEach((b) => b.addEventListener("click", () => { Object.assign(draft, JSON.parse(JSON.stringify(TEMPLATES[b.dataset.tpl]))); renderBuilder(); }));
  $$("[data-f]", B).forEach((i) => i.addEventListener("input", () => { draft[i.dataset.f] = i.value; if (i.dataset.f === "name") $("#builder h1").textContent = i.value || "New investor"; schedulePreview(); }));
  $$("[data-seg]", B).forEach((seg) => $$("button", seg).forEach((b) => b.addEventListener("click", () => { draft[seg.dataset.seg] = b.dataset.v; $$("button", seg).forEach((x) => x.classList.toggle("on", x === b)); schedulePreview(); })));
  $$("[data-g]", B).forEach((i) => i.addEventListener("input", () => { draft.goals[+i.dataset.g][i.dataset.k] = i.value; schedulePreview(); }));
  $$("[data-g][data-k=label]", B).forEach((i) => i.addEventListener("change", renderBuilder));
  $$("[data-h]", B).forEach((i) => i.addEventListener("input", () => { draft.holdings[+i.dataset.h][i.dataset.k] = i.value; schedulePreview(); }));
  $$("[data-c]", B).forEach((i) => i.addEventListener("input", () => { draft.constraints[i.dataset.c] = i.value === "" ? null : +i.value; schedulePreview(); }));
  $$("[data-cb]", B).forEach((i) => i.addEventListener("change", () => { draft.constraints[i.dataset.cb] = i.checked; schedulePreview(); }));
  $("[data-addg]", B)?.addEventListener("click", () => { draft.goals.push({ label: "", horizon_years: 5 }); renderBuilder(); });
  $("[data-addh]", B)?.addEventListener("click", () => { draft.holdings.push({ ticker: "SPY", value_cad: 5000, goal: `g${draft.goals.length}` }); renderBuilder(); });
  $$("[data-delg]", B).forEach((b) => b.addEventListener("click", () => {
    const i = +b.dataset.delg; draft.goals.splice(i, 1);
    draft.holdings = draft.holdings.map((h) => { const n = +h.goal.slice(1); return { ...h, goal: n - 1 === i ? "g1" : n - 1 > i ? `g${n - 1}` : h.goal }; });
    renderBuilder();
  }));
  $$("[data-delh]", B).forEach((b) => b.addEventListener("click", () => { draft.holdings.splice(+b.dataset.delh, 1); renderBuilder(); }));
  $("#bSave").addEventListener("click", saveDraft);
  $("#bDelete")?.addEventListener("click", () => {
    writeCustoms(readCustoms().filter((x) => x.id !== draft.id));
    state.personas = state.personas.filter((x) => x.id !== draft.id);
    showView("check"); selectPersona(state.personas[0].id);
  });
}
async function saveDraft() {
  const def = cleanDraft();
  try {
    const p = await previewPersona(def);
    const saved = readCustoms().filter((x) => x.id !== def.id);
    writeCustoms([...saved, def]);
    state.personas = state.personas.filter((x) => x.id !== def.id).concat([{ ...p, def }]);
    showView("check");
    selectPersona(def.id);
  } catch (err) {
    $("#bPreview").innerHTML = `<div class="alert alert-err" style="margin:0">${esc(err.f?.title || "Check the profile")}</div>`;
  }
}

// ------------------------------------------------------------------ method
function renderMethod() {
  const m = state.meta, ru = Object.entries(m.risk_units).sort((a, b) => a[1] - b[1]);
  const caps = m.capacity_rules.map(([lim, cap], i, arr) => `<tr><td>${i === 0 ? "Under 1 year" : lim >= 999 ? `${arr[i - 1][0]}+ years` : `${arr[i - 1][0]}–${lim} years`}</td><td class="num">${pct(cap)}</td></tr>`).join("");
  $("#method").innerHTML = `<div class="prose">
    <div class="crumb">How it works</div><h2>How SecondLook reaches a verdict</h2>
    <p>SecondLook does not pick investments. It checks whether an investor's <b>own idea</b> is consistent with what they told us about themselves
      (goals, horizons, risk profile, limits and preferences) and shows the evidence. Every number is computed by deterministic code on public data;
      nine AI agents on Amazon Bedrock interpret those numbers, argue both sides and explain the result. A rules engine sets the most permissive verdict
      allowed: the AI can be more cautious, never more lenient.</p>
    <h3>1. Risk is measured in S&amp;P 500 equivalents</h3>
    <p>Each asset's weekly volatility (2021-11-12 to 2026-11-12, in CAD) divided by the S&amp;P 500's. 100% = as risky as holding only the S&amp;P 500.</p>
    <div class="table-wrap"><table class="data"><thead><tr><th>Asset</th><th>Name</th><th class="num">Risk vs S&amp;P 500</th></tr></thead><tbody>
      ${ru.map(([t, v]) => `<tr><td><b>${esc(t)}</b></td><td>${esc(m.universe[t]?.name || "")}</td><td class="num"><span class="rx" style="background:${RISKBAND.find(([l]) => v <= l)[1]}">${v.toFixed(2)}×</span></td></tr>`).join("")}</tbody></table></div>
    <h3>2. Each goal has a risk limit</h3>
    <p>The lower of the <b>capacity</b> allowed by the goal's horizon and the investor's stated <b>tolerance</b>. Documented assumptions, not regulation.</p>
    <div class="cols"><div class="table-wrap"><table class="data"><thead><tr><th>Horizon</th><th class="num">Capacity limit</th></tr></thead><tbody>${caps}</tbody></table></div>
      <div class="table-wrap"><table class="data"><thead><tr><th>Stated risk profile</th><th class="num">Tolerance limit</th></tr></thead><tbody>
      ${Object.entries(m.tolerance_caps).map(([k, v]) => `<tr><td>${esc(RISK[k] || k)}</td><td class="num">${pct(v)}</td></tr>`).join("")}</tbody></table></div></div>
    <h3>3. Verdict rules</h3>
    <ul><li><b>Inconsistent</b>: the idea creates or worsens a breach of a hard limit or a goal's risk limit.</li>
      <li><b>Consistent with conditions</b>: no new breach, but a preference is worsened or a pre-existing gap remains.</li>
      <li><b>Consistent</b>: nothing is breached before or after.</li>
      <li><b>Needs more information</b>: ambiguous or outside the ${Object.keys(m.universe).length - 1}-asset universe; SecondLook asks a follow-up question.</li></ul>
    <h3>4. Data sources</h3><div class="box"><dl class="kv">${Object.entries(m.provenance).map(([k, v]) => `<dt>${esc(title(k))}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>
    <h3>5. Macro context (only data published by ${esc(m.macro.asof)})</h3>
    <div class="table-wrap"><table class="data"><thead><tr><th>Series</th><th class="num">Value</th><th>Date</th></tr></thead><tbody>
      ${Object.values(m.macro.series).map((s) => `<tr><td>${esc(s.label)}${s.note ? `<span class="sub">${esc(s.note)}</span>` : ""}</td><td class="num">${s.value}</td><td>${esc(s.date)}</td></tr>`).join("")}</tbody></table></div>
    <h3>6. AWS services</h3>
    <ul><li><b>Amazon Bedrock</b> (${esc(m.model)}): 9 agent calls per analysis.</li>
      <li><b>Amazon Bedrock Guardrails</b> (${esc(m.guardrail_id || "not configured")}): blocks guaranteed-return claims and personal data; logs trade-instruction language.</li>
      <li><b>Amazon S3</b> (${esc(m.bucket || "not configured")}): one audit record per analysis, plus the input data.</li></ul>
    <h3>7. Limits</h3><p>Rules of thumb, not suitability regulation · one action at a time · volatility over one 5-year window · ESG screen covers US stocks only · fictional investors · simulation only.</p></div>`;
}

let resizeT;
window.addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => { const p = persona(); if (p && $("#treemap")) treemap($("#treemap"), p); }, 150); });
boot();
