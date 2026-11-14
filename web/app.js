// SecondLook web UI (no framework). All text from agents is escaped before rendering.
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x, d = 0) => (x == null || isNaN(x) ? "—" : `${(x * 100).toFixed(d)}%`);
const money = (x) => (x == null ? "—" : `${x < 0 ? "−" : ""}$${Math.abs(Math.round(x)).toLocaleString("en-CA")}`);
const bigMoney = (x, ccy) => (x == null ? "—" : x >= 1e12 ? `${(x / 1e12).toFixed(2)} T ${ccy}` : `${(x / 1e9).toFixed(0)} B ${ccy}`);
const fmtVal = (v) => (v == null ? "—" : typeof v === "string" ? v : Math.abs(v) > 1.5 ? money(v) : pct(v, 1));
const pts = (a, b) => { const d = (b - a) * 100; return `${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(1)} pts`; };
const titleCase = (s) => String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const VERDICT = {
  CONSISTENT: { cls: "ok", label: "Consistent with stated profile" },
  CONSISTENT_WITH_CONDITIONS: { cls: "cond", label: "Consistent only under conditions" },
  INCONSISTENT: { cls: "bad", label: "Inconsistent with stated profile" },
  INSUFFICIENT_DATA: { cls: "na", label: "Needs more information" },
};
const vinfo = (v) => VERDICT[v] || VERDICT.INSUFFICIENT_DATA;
const STEPS = [
  ["Intake", "Intake"], ["Toolbox", "Toolbox"], ["Profile and market", "Profile + market"], ["Advocate vs skeptic", "Debate"],
  ["Constraint guardian", "Guardian"], ["Judge", "Judge"], ["Guardrail", "Guardrail"],
];
const RISK_LABEL = { low: "Low", low_moderate: "Low to moderate", moderate: "Moderate", high: "High" };
const CONSTRAINT_LABEL = {
  min_liquid_cad: ["Minimum cash & equivalents", money],
  max_single_position_pct: ["Max in one stock / crypto / commodity", (v) => `${v}%`],
  max_sector_pct: ["Max in one sector (of equities)", (v) => `${v}%`],
  max_crypto_pct: ["Max in crypto", (v) => `${v}%`],
  excluded_sectors: ["Excluded sectors (direct holdings)", (v) => v.join(", ")],
  excluded_asset_classes: ["Excluded asset classes", (v) => v.join(", ")],
  pref_max_security_risk_units: ["Avoid single names more volatile than", (v) => `${v}× S&P 500`],
  pref_pass_esg_screen: ["Prefer US stocks that pass the ESGV screen", () => "yes"],
};

const state = { personas: [], pid: null, meta: null, results: {}, followup: {} };

// ------------------------------------------------------------------ boot
async function boot() {
  let personas, meta;
  try {
    [personas, meta] = await Promise.all([fetch("/api/personas").then((r) => r.json()), fetch("/api/meta").then((r) => r.json())]);
  } catch (e) {
    $("#emptyState").classList.add("hidden");
    showError("#result", { ...SERVER_DOWN, technical: String(e) }, () => location.reload());
    return;
  }
  state.personas = personas;
  state.meta = meta;
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showView(t.dataset.view)));
  $("#runBtn").addEventListener("click", () => analyze());
  $("#request").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) analyze(); });
  $("#compareBtn").addEventListener("click", compare);
  renderCompareSuggestions();
  renderMethod();
  const qs = new URLSearchParams(location.search);
  selectPersona(qs.get("persona") && personas.some((p) => p.id === qs.get("persona")) ? qs.get("persona") : personas[0].id);
  if (qs.get("view")) showView(qs.get("view"));
  if (qs.get("compare")) { showView("compare"); $("#compareRequest").value = qs.get("compare"); compare(); }
  if (qs.get("q")) analyze(qs.get("q"));
  if (qs.get("run")) {
    const t = await fetch(`/api/trace/${encodeURIComponent(qs.get("run"))}`).then((r) => r.json());
    selectPersona(t.persona_id);
    state.results[t.persona_id] = t;
    $("#request").value = t.request;
    $("#emptyState").classList.add("hidden");
    finishPipeline(t);
    renderResult(t);
  }
}

function showView(v) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === v));
  document.querySelectorAll(".view").forEach((s) => s.classList.toggle("hidden", s.id !== `view-${v}`));
  const noSide = v !== "check";
  $("#sidebar").classList.toggle("hidden", noSide);
  $(".layout").classList.toggle("no-side", noSide);
}

const persona = () => state.personas.find((p) => p.id === state.pid);

// ------------------------------------------------------------------ sidebar
function selectPersona(pid) {
  state.pid = pid;
  $("#personaSwitch").innerHTML = state.personas.map((p) => `
    <button class="persona-btn ${p.id === pid ? "active" : ""}" data-pid="${p.id}">
      <div class="tag">${p.official_persona ? "OFFICIAL PERSONA" : "EXTRA SCENARIO"}</div>
      <div class="pname">${esc(p.name)}, ${p.age}</div>
      <div class="psub">${esc(RISK_LABEL[p.risk_tolerance] || p.risk_tolerance)} risk</div>
    </button>`).join("");
  document.querySelectorAll(".persona-btn").forEach((b) => b.addEventListener("click", () => selectPersona(b.dataset.pid)));
  renderProfile();
  const p = persona();
  $("#composerLabel").textContent = `What is ${p.name} thinking of doing?`;
  $("#suggestions").innerHTML = p.sample_requests.map((s) => `<button class="chip">${esc(s)}</button>`).join("");
  document.querySelectorAll("#suggestions .chip").forEach((c) => c.addEventListener("click", () => { $("#request").value = c.textContent; analyze(); }));
  $("#request").value = "";
  $("#pipeline").classList.add("hidden");
  const prev = state.results[pid];
  $("#result").innerHTML = "";
  $("#emptyState").classList.toggle("hidden", !!prev);
  if (prev) renderResult(prev);
}

function renderProfile() {
  const p = persona();
  const b = p.baseline;
  const total = b.exposures.total_value_cad;
  const horizons = p.goals.filter((g) => g.horizon_years > 0).map((g) => g.horizon_note ? g.horizon_note.split(";")[0].replace("stated horizon ", "") : `${g.horizon_years} years`);
  const goalRows = b.goals.map((g) => {
    const scale = Math.max(g.allowed_max_risky, g.risky_share, 0.05) * 1.15;
    return `<div class="side-row" style="display:block">
      <div style="display:flex;justify-content:space-between"><span>${esc(g.label)}</span><span class="r">${money(g.value_cad)}</span></div>
      <div class="sub">${g.horizon_years ? `${g.horizon_years}-year horizon` : "Needed any time"} · risk ${pct(g.risky_share)} of limit ${pct(g.allowed_max_risky)}</div>
      <div class="mini-track"><div class="mini-fill" style="width:${(g.risky_share / scale) * 100}%"></div>
      <div class="mini-limit" style="left:${(g.allowed_max_risky / scale) * 100}%"></div></div></div>`;
  }).join("");
  const holdings = [...p.holdings].sort((a, z) => z.value_cad - a.value_cad).map((h) => `
    <div class="side-row"><span><b>${esc(h.ticker)}</b> <span class="muted">${esc(p.holding_names[h.ticker] || "")}</span></span>
    <span class="r">${money(h.value_cad)} · ${pct(h.value_cad / total)}</span></div>`).join("");
  const c = p.constraints || {};
  const origin = c._origin || {};
  const cons = Object.entries(c).filter(([k]) => !k.startsWith("_")).map(([k, v]) => {
    const [label, f] = CONSTRAINT_LABEL[k] || [titleCase(k), String];
    const assumed = /derived|assumption/i.test(origin[k] || "");
    const soft = k.startsWith("pref_");
    return `<div class="side-row" title="${esc(origin[k] || "stated in the brief")}"><span>${esc(label)}
      <span class="tagline ${assumed ? "tag-assumed" : "tag-stated"}">${assumed ? "assumed" : "stated"}</span>
      ${soft ? '<span class="tagline tag-soft">preference</span>' : ""}</span><span class="r">${esc(f(v))}</span></div>`;
  }).join("");
  $("#profile").innerHTML = `
    <div class="profile-head"><h2>${esc(p.name)}, ${p.age}</h2><p>${esc(p.summary)}</p></div>
    <dl class="kv">
      <dt>Objective</dt><dd>${esc(p.objective)}</dd>
      <dt>Risk profile</dt><dd>${esc(RISK_LABEL[p.risk_tolerance])}</dd>
      <dt>Horizon</dt><dd>${esc(horizons.join(" · "))}</dd>
      <dt>Experience</dt><dd>${esc(titleCase(p.knowledge_level))}</dd>
      <dt>Portfolio</dt><dd>${money(total)} <span class="muted">(fictional)</span></dd>
    </dl>
    <div class="side-section"><h3>Goals · risk vs limit</h3>${goalRows}</div>
    <div class="side-section"><h3>Holdings</h3>${holdings}</div>
    <div class="side-section"><h3>Limits & preferences</h3>${cons}
      <p class="small muted" style="margin-top:8px">"Assumed" limits are our reading of the brief, to confirm with the investor.</p></div>`;
}

// ------------------------------------------------------------------ SSE helper
class UserError extends Error {
  constructor(f) { super(f.title); this.f = f; }
}
const SERVER_DOWN = { title: "Can't reach the SecondLook server", message: "The page couldn't connect to the analysis server.",
  action: "Make sure it is running (uvicorn server:app --port 8000), then try again.", retry: true, kind: "network" };

async function sse(url, body, on) {
  let res;
  try {
    res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch (e) { throw new UserError({ ...SERVER_DOWN, technical: String(e) }); }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail; } catch { detail = ""; }
    throw new UserError({ title: typeof detail === "string" && detail ? detail : "The request couldn't be processed",
      message: "", action: "", retry: false, technical: `HTTP ${res.status}`, kind: "request" });
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      const ev = (chunk.match(/^event: (.*)$/m) || [])[1];
      const data = (chunk.match(/^data: (.*)$/m) || [])[1];
      if (ev && data) on(ev, JSON.parse(data));
    }
  }
}

// ------------------------------------------------------------------ analyze
function renderPipeline(activeIdx, done = false, elapsed = null, stoppedAfter = null) {
  const el = $("#pipeline");
  el.classList.remove("hidden");
  el.innerHTML = STEPS.map(([, name], i) => {
    if (stoppedAfter != null && i > stoppedAfter) return `<div class="pstep"><b>${name}</b>not needed</div>`;
    const cls = done || i < activeIdx ? "done" : i === activeIdx ? "active" : "";
    return `<div class="pstep ${cls}"><b>${name}</b>${cls === "done" ? "done" : cls === "active" ? "running…" : "waiting"}</div>`;
  }).join("") + (elapsed ? `<div class="pstep done"><b>${elapsed}s</b>total</div>` : "");
}
const finishPipeline = (t) => renderPipeline(STEPS.length, true, t.elapsed_s, t.toolbox ? null : 0);

async function analyze(requestOverride) {
  const p = persona();
  const req = (requestOverride ?? $("#request").value).trim();
  if (!req) {
    $("#request").focus();
    $("#result").innerHTML = `<div class="alert alert-info">Type an idea in plain language, or pick one of the suggestions above.</div>`;
    return;
  }
  $("#request").value = req;
  $("#runBtn").disabled = true;
  $("#emptyState").classList.add("hidden");
  $("#result").innerHTML = "";
  renderPipeline(0);
  try {
    await sse("/api/analyze", { persona_id: p.id, request: req }, (ev, data) => {
      if (ev === "step") {
        const i = STEPS.findIndex(([k]) => data.label.startsWith(k));
        if (i >= 0) renderPipeline(i);
      } else if (ev === "result") {
        state.results[p.id] = data;
        finishPipeline(data);
        renderResult(data);
      } else if (ev === "error") {
        $("#pipeline").classList.add("hidden");
        showError("#result", data, () => analyze(req));
      }
    });
  } catch (e) {
    $("#pipeline").classList.add("hidden");
    showError("#result", e.f || { title: "Something went wrong", message: "", action: "Try again.", retry: true, technical: String(e) }, () => analyze(req));
  } finally {
    $("#runBtn").disabled = false;
  }
}

// ------------------------------------------------------------------ errors
function errorCard(f) {
  return `<div class="card errcard">
    <div class="err-title">${esc(f.title)}</div>
    ${f.message ? `<p>${esc(f.message)}</p>` : ""}
    ${f.action ? `<p class="err-action"><b>What to do:</b> ${esc(f.action)}</p>` : ""}
    <div class="err-row">${f.retry ? `<button class="btn-primary" data-retry>Try again</button>` : ""}
    ${f.technical ? `<details class="raw"><summary>Technical details</summary><pre class="json">${esc(f.technical)}</pre></details>` : ""}</div></div>`;
}
function showError(sel, f, retry) {
  $(sel).innerHTML = errorCard(f);
  const b = $(`${sel} [data-retry]`);
  if (b && retry) b.addEventListener("click", retry);
}

// ------------------------------------------------------------------ result rendering
function section(title, note, body, extra = "") {
  return `<div class="section"><div class="section-head"><h3>${title}</h3>${extra || (note ? `<span class="note">${note}</span>` : "")}</div>${body}</div>`;
}
const stepOut = (trace, agent) => (trace.steps.find((s) => s.agent === agent) || {}).output || {};

function renderResult(trace) {
  const r = trace.result;
  const v = vinfo(r.verdict);
  const tool = trace.toolbox;
  const a = trace.action || {};
  const g = trace.grounding || {};
  const gr = trace.guardrail || {};
  let html = `
  <div class="verdict v-${v.cls}">
    <div class="verdict-top"><div>
      <div class="verdict-label">${v.label}${r.confidence && r.confidence !== "n/a" ? ` · ${esc(r.confidence)} confidence` : ""}</div>
      <h2>${esc(r.headline)}</h2>
      <p>${esc(r.plain_summary)}</p>
    </div></div>
    ${r.verdict_adjustment ? `<p class="override">Rule override: ${esc(r.verdict_adjustment)}</p>` : ""}
    <div class="verdict-meta">
      ${!tool && r.understood ? `<span>Understood so far: <b>${esc(r.understood)}</b></span>` : ""}
      ${tool && a.ticker ? `<span>Interpreted as <b>${esc(a.action)} ${money(+a.amount_cad)} of ${esc(a.ticker)}</b>, funded by <b>${esc(a.funding === "new_money" ? "new money" : a.funding)}</b>, for goal <b>${esc(a.goal_id)}</b></span>` : ""}
      ${g.summary ? `<span>Numbers checked: <b>${esc(g.summary)}</b></span>` : ""}
      <span>Run <b>${esc(trace.run_id)}</b> · ${trace.elapsed_s}s</span>
    </div>
  </div>`;

  if (!tool) {
    html += followupBox(trace);
    $("#result").innerHTML = html;
    bindFollowup();
    return;
  }

  // Why
  html += section("Why", "", `<div class="two-col">
    <div class="card"><span class="eyebrow">Key reasons</span><ul class="list reasons">${(r.key_reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    <div class="card"><span class="eyebrow">This conclusion would change if</span><ul class="list ifs">${(r.no_longer_valid_if || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
  </div>`);

  // Variants
  const cfs = tool.counterfactuals || [];
  if (cfs.length) {
    html += section("Other versions of the same idea", "computed with the same rules · information, not advice",
      `<div class="card table-card"><div class="table-scroll"><table class="data"><thead><tr><th>Variant</th><th>Result</th><th>Why</th></tr></thead><tbody>
      ${cfs.map((c) => `<tr><td>${esc(c.variant)}</td><td>${statusPill(c.ceiling)}</td><td class="small">${esc((c.reasons || []).join("; ") || "No rule triggered")}</td></tr>`).join("")}
      </tbody></table></div></div>`);
  }

  // Pre-trade checks
  const checks = tool.rules.constraints;
  html += section("Pre-trade checks", "deterministic · hard limits veto, preferences add conditions",
    `<div class="card table-card"><div class="table-scroll"><table class="data"><thead><tr><th>Check</th><th>Type</th><th class="num">Before</th><th class="num">After</th><th>Result</th></tr></thead><tbody>
    ${checks.map((c) => `<tr><td>${esc(c.rule)}<span class="sub">${esc(c.origin && c.origin !== "stated" ? c.origin : "stated in the brief")}</span></td>
      <td>${c.severity === "hard" ? "Hard limit" : "Preference"}</td><td class="num">${fmtVal(c.before)}</td><td class="num">${fmtVal(c.after)}</td>
      <td>${checkPill(c)}</td></tr>`).join("")}
    </tbody></table></div></div>`);

  // Goal budget
  html += section("Risk budget by goal", "",
    `<div class="card">${budgetRows(tool.rules.buckets_before, tool.rules.buckets_after)}
     <div class="legend" style="margin-top:10px"><span><i style="background:var(--before)"></i>Before</span><span><i style="background:var(--after)"></i>After</span><span><i style="background:var(--limit);width:2px;height:12px"></i>Limit (lower of horizon capacity and stated tolerance)</span></div>
     <p class="small muted" style="margin:8px 0 0">Risk is measured in S&amp;P 500 equivalents: each dollar counts as its asset's historical volatility divided by the S&amp;P 500's (100% = as risky as holding only the S&amp;P 500).</p></div>`);

  // X-ray
  html += section("Portfolio X-ray: before and after", "",
    `<div class="card table-card" id="xray"></div>`,
    `<div class="seg" id="xraySeg"><button data-k="asset_class" class="on">Asset class</button><button data-k="equity_sectors">Sector</button><button data-k="equity_geography">Region</button><button data-k="currency">Currency</button></div>`);

  // Risk & stress
  const rb = tool.risk_before, ra = tool.risk_after;
  html += section("Risk and stress tests", `historical window ${esc(ra.window)} · CAD · not a forecast`,
    `<div class="metrics">
      ${metric("Annual volatility", pct(ra.annual_volatility, 1), `${pct(rb.annual_volatility, 1)} before · ${pts(rb.annual_volatility, ra.annual_volatility)}`)}
      ${metric("Worst peak-to-trough", pct(ra.max_drawdown, 1), `${pct(rb.max_drawdown, 1)} before`)}
      ${metric("Worst 12 months", pct(ra.worst_12m_return, 1), `${pct(rb.worst_12m_return, 1)} before`)}
      ${metric("Foreign currency", pct(tool.exposures_after.foreign_currency_share), `${pct(tool.exposures_before.foreign_currency_share)} before`)}
    </div>
    <div class="card table-card" style="margin-top:12px">${stressTable(tool.stress_before, tool.stress_after)}</div>`);

  // Security
  html += section(`About ${esc(tool.security.name)}`, esc(tool.security.terms), securityCard(tool.security));

  // ESG
  if (tool.esg_after) html += section("ESG: what the data can and cannot say", "", esgCard(tool.esg_before, tool.esg_after));

  // Debate
  const adv = stepOut(trace, "advocate"), skp = stepOut(trace, "skeptic");
  const advR = stepOut(trace, "advocate_rebuttal"), skpR = stepOut(trace, "skeptic_rebuttal");
  const prof = stepOut(trace, "profile"), grd = stepOut(trace, "guardian");
  html += section("How the agents argued", "two rounds · concessions recorded",
    `<div class="debate">${debateSide("Advocate", "var(--after)", adv, advR)}${debateSide("Skeptic", "var(--cond)", skp, skpR)}</div>
     ${r.debate_takeaway ? `<div class="card" style="margin-top:12px"><span class="eyebrow">Judge's takeaway</span>${esc(r.debate_takeaway)}</div>` : ""}
     <div class="two-col" style="margin-top:12px">
       <div class="card"><span class="eyebrow">Profile agent · tolerance vs capacity</span>${esc(prof.tolerance_vs_capacity)}
         ${prof.question_for_investor ? `<div class="alert alert-info">Question for ${esc(persona().name)}: ${esc(prof.question_for_investor)}</div>` : ""}</div>
       <div class="card"><span class="eyebrow">Guardian agent</span>${esc(grd.hard_constraint_summary)}
         <ul class="list" style="margin-top:6px">${[...(grd.preference_conflicts || []), ...(grd.governance_flags || [])].map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
     </div>`);

  // Evidence & audit
  html += section("Evidence and audit trail", "", auditBlock(trace));

  $("#result").innerHTML = html;
  bindXray(tool);
}

function statusPill(v) { const i = vinfo(v); return `<span class="status s-${i.cls}">${{ ok: "Consistent", cond: "With conditions", bad: "Inconsistent", na: "Needs info" }[i.cls]}</span>`; }
function checkPill(c) {
  if (c.passed) return `<span class="status s-ok">Pass</span>`;
  if (c.blocking) return `<span class="status s-bad">Breach</span>`;
  if (c.status.startsWith("worsened")) return `<span class="status s-cond">Preference worsened</span>`;
  return `<span class="status s-cond">${esc(c.status.replace("pre-existing breach, ", "Pre-existing, "))}</span>`;
}
const metric = (k, v, d) => `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`;

function budgetRows(before, after) {
  const bmap = Object.fromEntries(before.map((g) => [g.goal_id, g]));
  const scale = Math.max(0.3, ...after.map((g) => Math.max(g.risky_share, g.allowed_max_risky, (bmap[g.goal_id] || {}).risky_share || 0))) * 1.12;
  return after.map((g) => {
    const b = (bmap[g.goal_id] || {}).risky_share || 0;
    const over = g.status === "over limit";
    return `<div class="budget-row">
      <div><b>${esc(g.label)}</b><span class="sub">${g.horizon_years ? `${g.horizon_years}-year horizon` : "needed any time"} · bound by ${esc(g.binding_limit)}</span></div>
      <div class="track" title="Before ${pct(b)} · after ${pct(g.risky_share)} · limit ${pct(g.allowed_max_risky)}">
        <div class="before" style="width:${(b / scale) * 100}%"></div>
        <div class="after" style="width:${(g.risky_share / scale) * 100}%"></div>
        <div class="limit" style="left:${(g.allowed_max_risky / scale) * 100}%"><span>limit ${pct(g.allowed_max_risky)}</span></div>
      </div>
      <div class="num" style="text-align:right">${pct(b)} → <b>${pct(g.risky_share)}</b><span class="sub">${over ? '<span style="color:var(--bad)">over limit</span>' : "within limit"}</span></div>
    </div>`;
  }).join("");
}

function bindXray(tool) {
  const draw = (k) => {
    const b = tool.exposures_before[k] || {}, a = tool.exposures_after[k] || {};
    const keys = [...new Set([...Object.keys(b), ...Object.keys(a)])].sort((x, y) => Math.max(a[y] || 0, b[y] || 0) - Math.max(a[x] || 0, b[x] || 0)).slice(0, 10);
    const maxv = Math.max(0.01, ...keys.map((x) => Math.max(a[x] || 0, b[x] || 0)));
    const note = k === "equity_sectors" || k === "equity_geography" ? "share of the equity part, with funds looked through" : "share of the whole portfolio";
    $("#xray").innerHTML = `<div class="table-scroll"><table class="data"><thead><tr><th>${{ asset_class: "Asset class", equity_sectors: "Sector", equity_geography: "Region", currency: "Currency" }[k]} <span style="text-transform:none;letter-spacing:0;font-weight:400">· ${note}</span></th><th class="num">Before</th><th class="num">After</th><th class="num">Change</th><th style="width:34%"></th></tr></thead><tbody>
      ${keys.map((x) => {
        const bv = b[x] || 0, av = a[x] || 0, d = av - bv;
        return `<tr><td>${esc(titleCase(x))}</td><td class="num">${pct(bv, 1)}</td><td class="num"><b>${pct(av, 1)}</b></td>
        <td class="num ${Math.abs(d) < 0.0005 ? "muted" : d > 0 ? "delta-up" : "delta-down"}">${Math.abs(d) < 0.0005 ? "—" : pts(bv, av)}</td>
        <td><div class="hbar" style="width:${(bv / maxv) * 100}%;background:var(--before)"></div><div class="hbar" style="width:${(av / maxv) * 100}%;background:var(--after);margin-top:3px"></div></td></tr>`;
      }).join("")}</tbody></table></div>`;
  };
  document.querySelectorAll("#xraySeg button").forEach((btn) => btn.addEventListener("click", () => {
    document.querySelectorAll("#xraySeg button").forEach((x) => x.classList.toggle("on", x === btn));
    draw(btn.dataset.k);
  }));
  draw("asset_class");
}

function stressTable(before, after) {
  const bmap = Object.fromEntries(before.map((s) => [s.id, s]));
  const maxv = Math.max(0.01, ...after.map((s) => Math.abs(Math.min(s.impact_pct, bmap[s.id].impact_pct, 0))));
  return `<div class="table-scroll"><table class="data"><thead><tr><th>Scenario</th><th class="num">Before</th><th class="num">After</th><th style="width:30%"></th></tr></thead><tbody>
  ${after.map((s) => {
    const b = bmap[s.id];
    return `<tr><td>${esc(s.label)}<span class="sub">${s.type === "historical replay" ? "Historical replay · " : "Hypothetical · "}${esc(s.basis)}</span></td>
      <td class="num">${pct(b.impact_pct, 1)}<span class="sub">${money(b.impact_cad)}</span></td>
      <td class="num"><b>${pct(s.impact_pct, 1)}</b><span class="sub">${money(s.impact_cad)}</span></td>
      <td><div class="hbar" style="width:${(Math.abs(Math.min(b.impact_pct, 0)) / maxv) * 100}%;background:var(--before)"></div>
          <div class="hbar" style="width:${(Math.abs(Math.min(s.impact_pct, 0)) / maxv) * 100}%;background:var(--after);margin-top:3px"></div></td></tr>`;
  }).join("")}</tbody></table></div>`;
}

function securityCard(s) {
  const f = s.company_snapshot;
  const esg = s.esg_screen ? `<div class="alert ${s.esg_screen === "not held" ? "alert-warn" : "alert-info"}">ESG screen (Vanguard ESG U.S. Stock ETF holdings, SEC filing as of 2026-05-31): <b>${esc(s.esg_screen)}</b></div>` : "";
  return `<div class="card">
    <div class="metrics">
      ${metric("Volatility (per year)", pct(s.annual_volatility, 1), `${(+s.risk_units_vs_spy).toFixed(2)}× the S&amp;P 500`)}
      ${metric("Worst peak-to-trough", pct(s.max_drawdown, 1), `low on ${esc(s.max_drawdown_date)}`)}
      ${metric("Worst 12 months", pct(s.worst_12m_return, 1), esc(s.window))}
      ${metric("Annualised return", pct(s.annualised_return, 1), "past only, not a forecast")}
    </div>
    ${f ? `<div class="kv" style="margin-top:14px;grid-template-columns:repeat(4,auto 1fr)">
      <dt>Market cap</dt><dd>${f.market_cap ? bigMoney(f.market_cap, esc(f.currency)) : "—"}</dd>
      <dt>Profit margin</dt><dd>${pct(f.profit_margin, 1)}</dd>
      <dt>Revenue growth</dt><dd>${pct(f.revenue_growth_yoy, 1)}</dd>
      <dt>Dividend yield</dt><dd>${f.dividend_yield_pct != null ? `${f.dividend_yield_pct}%` : "—"}</dd>
      <dt>Return on equity</dt><dd>${pct(f.return_on_equity, 1)}</dd>
      <dt>Debt / equity</dt><dd>${f.debt_to_equity_pct != null ? `${f.debt_to_equity_pct.toFixed(0)}%` : "—"}</dd>
      <dt>Listed since</dt><dd>${esc(f.listed_since || "—")}</dd>
      <dt>Employees</dt><dd>${f.employees ? f.employees.toLocaleString("en-CA") : "—"}</dd>
    </div><p class="small muted" style="margin:0">Company snapshot: ${esc(s.company_snapshot_source)}. Context only.</p>` : ""}
    ${s.note ? `<p class="small muted">${esc(s.note)}</p>` : ""}${esg}</div>`;
}

function esgCard(b, a) {
  const rows = Object.entries(a.esgv_screen_by_holding || {}).map(([t, s]) => `<tr><td><b>${esc(t)}</b></td><td>${esc(s)}</td></tr>`).join("");
  return `<div class="two-col"><div class="card">
      <span class="eyebrow">Screen applied</span>${esc(a.screen)}
      <dl class="kv" style="margin-top:10px"><dt>Direct holdings in excluded sectors</dt><dd>${esc(a.direct_holdings_in_excluded_sectors.join(", ") || "none")}</dd>
      <dt>Energy exposure via funds and stocks</dt><dd>${pct(b.energy_lookthrough_share_of_portfolio, 1)} → <b>${pct(a.energy_lookthrough_share_of_portfolio, 1)}</b> of the portfolio</dd></dl>
      <div class="alert alert-warn">${esc(a.controversy_status)}</div></div>
    <div class="card table-card"><table class="data"><thead><tr><th>Single stock</th><th>ESGV screen (SEC N-PORT)</th></tr></thead><tbody>${rows || '<tr><td colspan="2" class="muted">No single stocks</td></tr>'}</tbody></table></div></div>`;
}

function debateSide(name, color, open, reb) {
  return `<div class="card side" style="--c:${color}"><h4>${name}</h4><p class="pos">${esc(open.position)}</p>
    ${(open.arguments || []).map((x) => `<div class="arg"><b>${esc(x.claim)}</b><span class="sub">${esc(x.evidence)}</span></div>`).join("")}
    ${(reb.rebuttals || []).length ? `<span class="eyebrow" style="margin-top:12px">Rebuttal round</span>${reb.rebuttals.map((x) => `<div class="arg">${esc(x.response)}</div>`).join("")}` : ""}
    ${(reb.concessions || []).map((x) => `<div class="concede">Concedes: ${esc(x)}</div>`).join("")}</div>`;
}

function auditBlock(trace) {
  const r = trace.result, g = trace.grounding || {}, gr = trace.guardrail || {};
  const lists = [["Facts (from data)", r.facts], ["Assumptions", r.assumptions], ["Fictional", r.fictional], ["Limits", r.limits]];
  const prov = trace.toolbox.provenance;
  const steps = trace.steps.map((s, i) => `<tr><td>${i + 1}</td><td>${esc(titleCase(s.agent))}</td><td>${s.kind === "llm" ? "Bedrock agent" : "Deterministic"}</td>
    <td class="num">${s.latency_ms ? `${(s.latency_ms / 1000).toFixed(1)}s` : "—"}</td><td class="num">${s.tokens ? s.tokens.toLocaleString() : "—"}</td>
    <td>${esc((trace.grounding_by_agent || {})[s.agent]?.summary || "")}</td></tr>`).join("");
  const blob = URL.createObjectURL(new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" }));
  return `<div class="card"><div class="evidence">${lists.map(([t, xs]) => `<div><h4>${t}</h4><ul>${(xs || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`).join("")}</div></div>
    <div class="metrics" style="margin-top:12px">
      ${metric("Numbers traced to data", esc((g.summary || "—").replace(" figures traced to data", "")), g.ungrounded?.length ? `not found: ${esc(g.ungrounded.join(", "))}` : "every % and $ written by agents")}
      ${metric("Bedrock Guardrail", `${(gr.blocked || []).length} blocked`, `${(gr.flagged_not_blocked || []).length} flagged · ${gr.checked || 0} strings checked`)}
      ${metric("Agent calls", trace.steps.filter((s) => s.kind === "llm").length, `${(trace.total_tokens || 0).toLocaleString()} tokens · ${esc(trace.model)}`)}
      ${metric("Audit record", trace.s3_uri ? "Stored in S3" : "Local only", esc(trace.s3_uri ? trace.s3_uri.split("/").slice(-1)[0] : ""))}
    </div>
    ${(gr.blocked || []).map((b) => `<div class="alert alert-err">Guardrail blocked text in “${esc(b.field)}” (${esc([...(b.topics || []), ...(b.words || [])].join(", "))}). Original kept in the audit record.</div>`).join("")}
    ${(gr.flagged_not_blocked || []).map((b) => `<div class="alert alert-info">Guardrail flagged (not blocked) in “${esc(b.field)}”: ${esc(b.text)}</div>`).join("")}
    <div class="card table-card" style="margin-top:12px"><div class="table-scroll"><table class="data"><thead><tr><th>#</th><th>Step</th><th>Kind</th><th class="num">Time</th><th class="num">Tokens</th><th>Grounding</th></tr></thead><tbody>${steps}</tbody></table></div></div>
    <div class="card" style="margin-top:12px"><span class="eyebrow">Data sources used</span>
      <dl class="kv">${Object.entries(prov).map(([k, v]) => `<dt>${esc(titleCase(k))}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
      ${trace.s3_uri ? `<p class="small muted" style="margin:0">Audit record: <code>${esc(trace.s3_uri)}</code></p>` : ""}
      <p style="margin:10px 0 0"><a class="btn-link" href="${blob}" download="secondlook_${esc(trace.run_id)}.json">Download full trace (JSON)</a></p>
      <details class="raw"><summary>Show every agent's raw output</summary><pre class="json">${esc(JSON.stringify(trace.steps, null, 2))}</pre></details></div>`;
}

// ------------------------------------------------------------------ follow-up (missing information)
function followupBox(trace) {
  const r = trace.result;
  const replace = (r.issues || []).some((i) => i === "override_attempt" || i === "unclear");
  const groups = r.universe_groups
    ? `<div class="universe">${Object.entries(r.universe_groups).map(([g, ts]) => `<div class="ugroup"><span class="eyebrow">${esc(g)}</span>
        <div class="chips">${ts.map((t) => `<button class="chip" data-pick="${esc(t)}" title="${esc(state.meta.universe[t]?.name || "")}">${esc(t)}</button>`).join("")}</div></div>`).join("")}</div>`
    : "";
  return `<div class="card followup" style="margin-top:14px"><span class="eyebrow">${esc(r.followup_question || "What would you like to check?")}</span>
    ${(r.quick_answers || []).length ? `<div class="chips" style="margin-bottom:10px">${r.quick_answers.map((q) => `<button class="chip" data-answer="${esc(q)}">${esc(q)}</button>`).join("")}</div>` : ""}
    ${groups}
    <div class="composer-row"><textarea id="followupAnswer" rows="1" placeholder="${replace ? "Type the idea again, e.g. Move $10,000 from XBB into SPY" : "Or type your answer, e.g. $10,000 of new money"}"></textarea>
    <button class="btn-primary" id="followupBtn">Continue</button></div></div>`;
}
function bindFollowup() {
  const r = (state.results[state.pid] || {}).result || {};
  const replace = (r.issues || []).some((i) => i === "override_attempt" || i === "unclear");
  const go = (ans) => {
    ans = ans.trim();
    if (!ans) { $("#followupAnswer").focus(); return; }
    analyze(replace ? ans : `${$("#request").value.trim().replace(/\s*\(Clarification:.*\)$/, "")} (Clarification: ${ans})`);
  };
  $("#followupBtn")?.addEventListener("click", () => go($("#followupAnswer").value));
  $("#followupAnswer")?.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go($("#followupAnswer").value); } });
  document.querySelectorAll("[data-answer]").forEach((b) => b.addEventListener("click", () => go(b.dataset.answer)));
  document.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => go(`I meant ${b.dataset.pick}`)));
}

// ------------------------------------------------------------------ compare
function renderCompareSuggestions() {
  const presets = ["Put $2,000 of new money into Bitcoin.", "Add $10,000 of new money to SPY.",
    "AI is the future. Put $15,000 of new money into NVIDIA.", "Put $10,000 of new money into Exxon (XOM) for the dividend."];
  $("#compareSuggestions").innerHTML = presets.map((s) => `<button class="chip">${esc(s)}</button>`).join("");
  document.querySelectorAll("#compareSuggestions .chip").forEach((c) => c.addEventListener("click", () => { $("#compareRequest").value = c.textContent; compare(); }));
}

async function compare() {
  const req = $("#compareRequest").value.trim();
  if (!req) return;
  $("#compareBtn").disabled = true;
  $("#compareGrid").innerHTML = state.personas.map((p) => `<div class="card ccard" id="cc-${p.id}"><h3>${esc(p.name)}, ${p.age}</h3>
    <div class="meta">${esc(RISK_LABEL[p.risk_tolerance])} risk · ${esc(p.objective)}</div><div class="skeleton">Analysing…</div></div>`).join("");
  try {
    await sse("/api/compare", { request: req }, (ev, data) => {
      const p = state.personas.find((x) => x.id === data.persona_id);
      const el = $(`#cc-${data.persona_id}`);
      if (ev === "error") {
        el.querySelector(".skeleton").innerHTML = `<b>${esc(data.title)}</b><br>${esc(data.action || data.message || "")}`;
        return;
      }
      const t = data.trace, r = t.result, v = vinfo(r.verdict);
      state.results[p.id] = t;
      el.style.setProperty("--v", `var(--${v.cls})`);
      el.innerHTML = `<h3>${esc(p.name)}, ${p.age}</h3><div class="meta">${esc(RISK_LABEL[p.risk_tolerance])} risk · ${esc(p.objective)}</div>
        <div>${statusPill(r.verdict)}</div><div class="head">${esc(r.headline)}</div>
        <ul>${(r.key_reasons || []).slice(0, 3).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        ${(t.toolbox?.counterfactuals || []).length ? `<div class="small muted">Variants: ${t.toolbox.counterfactuals.map((c) => `${esc(c.variant.split(":")[0])} → ${vinfo(c.ceiling).label.split(" ")[0].toLowerCase()}`).join(" · ")}</div>` : ""}
        <button class="btn-link" data-open="${p.id}">Open full analysis →</button>`;
      el.querySelector("[data-open]").addEventListener("click", () => { showView("check"); selectPersona(p.id); $("#request").value = req; });
    });
  } finally {
    $("#compareBtn").disabled = false;
  }
}

// ------------------------------------------------------------------ method
function renderMethod() {
  const m = state.meta;
  const ru = Object.entries(m.risk_units).sort((a, b) => a[1] - b[1]);
  const caps = m.capacity_rules.map(([lim, cap], i, arr) => `<tr><td>${i === 0 ? "Under 1 year" : lim >= 999 ? `${arr[i - 1][0]}+ years` : `${arr[i - 1][0]}–${lim} years`}</td><td class="num">${pct(cap)}</td></tr>`).join("");
  $("#method").innerHTML = `<div class="prose">
    <h2>How SecondLook reaches a verdict</h2>
    <p>SecondLook does not pick investments. It checks whether an investor's <em>own idea</em> is consistent with what they told us about
    themselves: goals, horizons, risk profile, limits and preferences. Every number comes from deterministic code on public data; AI agents
    on Amazon Bedrock interpret those numbers, argue both sides and explain the result. A rules engine sets the most permissive verdict
    allowed. The judge agent can be more cautious, never more lenient.</p>
    <h3>1. Risk is measured in S&amp;P 500 equivalents</h3>
    <p>Each asset's weekly volatility (2021-11-12 to 2026-11-12, in CAD) is divided by the S&amp;P 500's. A goal's risk is the value-weighted
    sum: 100% means "as risky as holding only the S&amp;P 500".</p>
    <div class="card table-card"><div class="table-scroll"><table class="data"><thead><tr><th>Asset</th><th>Name</th><th class="num">Risk vs S&amp;P 500</th></tr></thead><tbody>
      ${ru.map(([t, v]) => `<tr><td><b>${esc(t)}</b></td><td>${esc(m.universe[t]?.name || "")}</td><td class="num">${v.toFixed(2)}×</td></tr>`).join("")}</tbody></table></div></div>
    <h3>2. Each goal has a risk limit</h3>
    <p>The limit is the lower of the <em>capacity</em> allowed by the goal's horizon (money needed soon cannot ride out a downturn) and the
    investor's stated <em>tolerance</em>. These limits are documented assumptions, not regulation.</p>
    <div class="two-col"><div class="card table-card"><table class="data"><thead><tr><th>Horizon</th><th class="num">Capacity limit</th></tr></thead><tbody>${caps}</tbody></table></div>
    <div class="card table-card"><table class="data"><thead><tr><th>Stated risk profile</th><th class="num">Tolerance limit</th></tr></thead><tbody>
      ${Object.entries(m.tolerance_caps).map(([k, v]) => `<tr><td>${esc(RISK_LABEL[k] || k)}</td><td class="num">${pct(v)}</td></tr>`).join("")}</tbody></table></div></div>
    <h3>3. Verdict rules</h3>
    <ul><li><b>Inconsistent</b>: the idea creates or worsens a breach of a hard limit or a goal's risk limit.</li>
      <li><b>Consistent under conditions</b>: no new breach, but a preference is worsened or a pre-existing gap remains.</li>
      <li><b>Consistent</b>: no limit is breached before or after.</li>
      <li><b>Needs more information</b>: the request is ambiguous or outside the 31-asset universe; SecondLook asks a follow-up question.</li></ul>
    <h3>4. Data</h3>
    <div class="card"><dl class="kv">${Object.entries(m.provenance).map(([k, v]) => `<dt>${esc(titleCase(k))}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>
    <h3>5. Macro context (only data published by ${esc(m.macro.asof)})</h3>
    <div class="card table-card"><table class="data"><thead><tr><th>Series</th><th class="num">Value</th><th>Date</th></tr></thead><tbody>
      ${Object.values(m.macro.series).map((s) => `<tr><td>${esc(s.label)}${s.note ? `<span class="sub">${esc(s.note)}</span>` : ""}</td><td class="num">${s.value}</td><td>${esc(s.date)}</td></tr>`).join("")}</tbody></table></div>
    <h3>6. AWS services</h3>
    <ul><li><b>Amazon Bedrock</b> (${esc(m.model)}): 9 agent calls per analysis.</li>
      <li><b>Amazon Bedrock Guardrails</b> (${esc(m.guardrail_id || "not configured")}): blocks guaranteed-return claims and personal data; logs trade-instruction language.</li>
      <li><b>Amazon S3</b> (${esc(m.bucket || "not configured")}): one audit record per analysis, plus the input data.</li></ul>
    <h3>7. Limits</h3>
    <p>Rules of thumb, not suitability regulation · one action at a time · volatility over one 5-year window · ESG: only US stocks are
    checked against a public screen · fictional investors · simulation only.</p></div>`;
}

boot();
