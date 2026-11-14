"""SecondLook: Streamlit UI.  Run:  AWS_PROFILE=team10 streamlit run app.py"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.orchestrator import run
from src.universe import UNIVERSE

ROOT = Path(__file__).parent
PERSONAS = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "personas").glob("*.json"))}

# palette (validated reference instance): before = blue 250, after = blue 450; status colours reserved for verdicts
C_BEFORE, C_AFTER, C_LIMIT = "#86b6ef", "#2a78d6", "#52514e"
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
VERDICT_STYLE = {
    "CONSISTENT": ("#0ca30c", "✔", "Consistent with your stated profile"),
    "CONSISTENT_WITH_CONDITIONS": ("#fab219", "◐", "Consistent only under conditions"),
    "INCONSISTENT": ("#d03b3b", "✖", "Inconsistent with your stated profile"),
    "INSUFFICIENT_DATA": ("#898781", "?", "Not enough information"),
}

st.set_page_config(page_title="SecondLook", page_icon="🔎", layout="wide")
st.markdown("""<style>
.verdict{border-radius:10px;padding:18px 22px;margin:4px 0 14px 0;border-left:8px solid var(--c);background:#f9f9f7}
.verdict h2{margin:0 0 4px 0;font-size:1.45rem}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.78rem;background:#eceae4;color:#52514e;margin-right:6px}
.small{color:#52514e;font-size:.85rem}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers

def pct(x, d=0):
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def bar_before_after(before: dict, after: dict, title: str, top=8):
    keys = sorted(set(before) | set(after), key=lambda k: -max(before.get(k, 0), after.get(k, 0)))[:top][::-1]
    fig = go.Figure()
    for name, d, c in (("Before", before, C_BEFORE), ("After", after, C_AFTER)):
        vals = [d.get(k, 0) * 100 for k in keys]
        fig.add_bar(y=[k.replace("_", " ") for k in keys], x=vals, name=name, orientation="h", marker_color=c,
                    marker_line=dict(color="#fcfcfb", width=2),
                    hovertemplate="%{y}: %{x:.1f}%<extra>" + name + "</extra>")
    fig.update_layout(title=dict(text=title, font=dict(size=14, color=INK)), barmode="group", height=60 + 42 * len(keys),
                      margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
                      legend=dict(orientation="h", y=1.12, x=1, xanchor="right"), bargap=0.25, bargroupgap=0.08,
                      xaxis=dict(ticksuffix="%", gridcolor=GRID, zerolinecolor="#c3c2b7", color=MUTED), yaxis=dict(color=INK))
    return fig


def goal_chart(before, after):
    labels = [g["label"] for g in after][::-1]
    b = {g["goal_id"]: g for g in before}
    fig = go.Figure()
    fig.add_bar(y=labels, x=[b.get(g["goal_id"], {}).get("risky_share", 0) * 100 for g in after][::-1], name="Before",
                orientation="h", marker_color=C_BEFORE, hovertemplate="%{y}: %{x:.0f}%<extra>Before</extra>")
    fig.add_bar(y=labels, x=[g["risky_share"] * 100 for g in after][::-1], name="After", orientation="h",
                marker_color=C_AFTER, hovertemplate="%{y}: %{x:.0f}%<extra>After</extra>")
    fig.add_scatter(y=labels, x=[g["allowed_max_risky"] * 100 for g in after][::-1], mode="markers", name="Limit",
                    marker=dict(symbol="line-ns", size=26, line=dict(width=3, color=C_LIMIT)),
                    hovertemplate="%{y} limit: %{x:.0f}%<extra></extra>")
    fig.update_layout(title=dict(text="Risky share of each goal vs. its limit (risk units, crypto = 3x)", font=dict(size=14)),
                      barmode="group", height=110 + 60 * len(labels), margin=dict(l=10, r=10, t=40, b=10),
                      plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", legend=dict(orientation="h", y=1.15, x=1, xanchor="right"),
                      xaxis=dict(ticksuffix="%", gridcolor=GRID, color=MUTED))
    return fig


def stress_chart(before, after):
    labels = [s["label"] for s in after][::-1]
    bmap = {s["id"]: s for s in before}
    fig = go.Figure()
    fig.add_bar(y=labels, x=[bmap[s["id"]]["impact_pct"] * 100 for s in after][::-1], name="Before", orientation="h",
                marker_color=C_BEFORE, customdata=[bmap[s["id"]]["impact_cad"] for s in after][::-1],
                hovertemplate="%{y}: %{x:.1f}% ($%{customdata:,.0f})<extra>Before</extra>")
    fig.add_bar(y=labels, x=[s["impact_pct"] * 100 for s in after][::-1], name="After", orientation="h",
                marker_color=C_AFTER, customdata=[s["impact_cad"] for s in after][::-1],
                hovertemplate="%{y}: %{x:.1f}% ($%{customdata:,.0f})<extra>After</extra>")
    fig.update_layout(title=dict(text="Portfolio impact under stress scenarios", font=dict(size=14)), barmode="group",
                      height=120 + 52 * len(labels), margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="#fcfcfb",
                      paper_bgcolor="#fcfcfb", legend=dict(orientation="h", y=1.1, x=1, xanchor="right"),
                      xaxis=dict(ticksuffix="%", gridcolor=GRID, zerolinecolor="#c3c2b7", color=MUTED))
    return fig


def verdict_card(res):
    color, icon, label = VERDICT_STYLE.get(res.get("verdict"), VERDICT_STYLE["INSUFFICIENT_DATA"])
    st.markdown(f"""<div class="verdict" style="--c:{color}">
      <div class="small">{icon} <b>{label}</b> · confidence: {res.get('confidence', 'n/a')}</div>
      <h2>{res.get('headline', '')}</h2>
      <div>{res.get('plain_summary', '')}</div></div>""", unsafe_allow_html=True)
    if res.get("verdict_adjustment"):
        st.info("⚖️ Rule override: " + res["verdict_adjustment"])


def persona_sidebar(p):
    st.sidebar.markdown(f"### {p['name']}, {p['age']}  \n<span class='badge'>fictional persona</span>"
                        f"<span class='badge'>{p['knowledge_level']}</span><span class='badge'>tolerance: {p['risk_tolerance']}</span>",
                        unsafe_allow_html=True)
    st.sidebar.caption(p["summary"])
    st.sidebar.markdown("**Goals**")
    st.sidebar.dataframe(pd.DataFrame([{"Goal": g["label"], "Horizon (y)": g["horizon_years"]} for g in p["goals"]]),
                         hide_index=True, width="stretch")
    st.sidebar.markdown("**Holdings (simulated)**")
    st.sidebar.dataframe(pd.DataFrame([{"Ticker": h["ticker"], "Value $": f"{h['value_cad']:,.0f}", "Goal": h["goal"]}
                                       for h in p["holdings"]]), hide_index=True, width="stretch")
    st.sidebar.markdown("**Hard constraints**")
    st.sidebar.json(p.get("constraints", {}), expanded=False)
    st.sidebar.markdown("**Preferences** (operate inside constraints)")
    st.sidebar.json(p.get("preferences", {}), expanded=False)


def render_result(trace, persona):
    res = trace["result"]
    verdict_card(res)
    if "toolbox" not in trace:
        st.warning("Analysis stopped at intake. " + res.get("plain_summary", ""))
        return
    tool = trace["toolbox"]
    a = trace["action"]
    st.caption(f"Interpreted as: **{a['action']} ${float(a['amount_cad']):,.0f} of {a['ticker']}** "
               f"({UNIVERSE[a['ticker']]['name']}) for goal *{a['goal_id']}*, funded by *{a['funding']}*"
               + (f" from goal *{a['funding_goal_id']}*" if a.get("funding_goal_id") else ""))

    t1, t2, t3, t4, t5 = st.tabs(["Why", "Portfolio impact", "Goals & rules", "Agent debate", "Audit trail"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Key reasons")
            for r in res.get("key_reasons", []):
                st.markdown(f"- {r}")
            st.markdown("#### This conclusion no longer holds if…")
            for r in res.get("no_longer_valid_if", []):
                st.markdown(f"- {r}")
        with c2:
            st.markdown("#### Variants of the same idea (computed, not advice)")
            rows = []
            for cf in tool["counterfactuals"]:
                color, icon, _ = VERDICT_STYLE[cf["ceiling"]]
                rows.append({"Variant": cf["variant"], "Rule result": f"{icon} {cf['ceiling'].replace('_', ' ').lower()}",
                             "Why": "; ".join(cf["reasons"]) or "no rule triggered"})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch") if rows else st.caption("No variants.")
            if res.get("debate_takeaway"):
                st.markdown("#### Debate takeaway")
                st.write(res["debate_takeaway"])
        st.markdown("#### Facts, assumptions, fiction")
        f1, f2, f3, f4 = st.columns(4)
        for col, key, title in ((f1, "facts", "📊 Facts (market data)"), (f2, "assumptions", "🧩 Assumptions"),
                                (f3, "fictional", "🎭 Fictional"), (f4, "limits", "⚠️ Limits")):
            with col:
                st.markdown(f"**{title}**")
                for x in res.get(key, []):
                    st.markdown(f"<div class='small'>• {x}</div>", unsafe_allow_html=True)
    with t2:
        eb, ea = tool["exposures_before"], tool["exposures_after"]
        rb, ra = tool["risk_before"], tool["risk_after"]
        m = st.columns(4)
        m[0].metric("Annual volatility", pct(ra["annual_volatility"], 1), f"{(ra['annual_volatility'] - rb['annual_volatility']) * 100:+.1f} pts", delta_color="inverse")
        m[1].metric("Max drawdown", pct(ra["max_drawdown"], 1), f"{(ra['max_drawdown'] - rb['max_drawdown']) * 100:+.1f} pts")
        m[2].metric("Worst 12 months", pct(ra["worst_12m_return"], 1), f"{(ra['worst_12m_return'] - rb['worst_12m_return']) * 100:+.1f} pts")
        m[3].metric("Foreign currency", pct(ea["foreign_currency_share"]), f"{(ea['foreign_currency_share'] - eb['foreign_currency_share']) * 100:+.1f} pts", delta_color="off")
        st.caption(f"Historical, {ra['window']}; {ra['method']}.")
        c1, c2 = st.columns(2)
        c1.plotly_chart(bar_before_after(eb["asset_class"], ea["asset_class"], "Asset class"), width="stretch")
        c2.plotly_chart(bar_before_after(eb["equity_geography"], ea["equity_geography"], "Equity by geography"), width="stretch")
        c1.plotly_chart(bar_before_after(eb["equity_sectors"], ea["equity_sectors"], "Equity by sector (top 8)"), width="stretch")
        c2.plotly_chart(bar_before_after(eb["currency"], ea["currency"], "Currency exposure (after hedging)"), width="stretch")
        st.plotly_chart(stress_chart(tool["stress_before"], tool["stress_after"]), width="stretch")
        st.dataframe(pd.DataFrame([{"Scenario": s["label"], "Type": s["type"], "Impact after": f"{s['impact_pct'] * 100:.1f}%",
                                    "Basis": s["basis"]} for s in tool["stress_after"]]), hide_index=True, width="stretch")
        sec = tool["security"]
        st.markdown(f"**{sec['name']} ({sec['ticker']})**: volatility {pct(sec['annual_volatility'], 1)}/yr, "
                    f"max drawdown {pct(sec['max_drawdown'], 1)} ({sec['max_drawdown_date']}), worst 12 months "
                    f"{pct(sec['worst_12m_return'], 1)}, fee (MER) {sec['mer'] if sec['mer'] is not None else 'n/a'}%. "
                    + (sec.get("note") or ""))
        with st.expander("Analyst observations"):
            for o in next(s["output"] for s in trace["steps"] if s["agent"] == "analyst").get("observations", []):
                st.markdown(f"- {o['statement']}")
    with t3:
        st.plotly_chart(goal_chart(tool["rules"]["buckets_before"], tool["rules"]["buckets_after"]), width="stretch")
        st.dataframe(pd.DataFrame([{"Goal": g["label"], "Horizon": g["horizon_years"], "Capacity limit": pct(g["capacity_max_risky"]),
                                    "Tolerance limit": pct(g["tolerance_max_risky"]), "Binding": g["binding_limit"],
                                    "After": pct(g["risky_share"]), "Status": g["status"]} for g in tool["rules"]["buckets_after"]]),
                     hide_index=True, width="stretch")
        st.markdown("#### Hard constraints (deterministic checks)")
        icon = lambda c: "✔ pass" if c["passed"] else ("✖ " if c["blocking"] else "◐ ") + c["status"]  # noqa: E731
        st.dataframe(pd.DataFrame([{"Rule": c["rule"], "Before": c["before"], "After": c["after"], "Result": icon(c),
                                    "Detail": c["detail"]} for c in tool["rules"]["constraints"]]), hide_index=True, width="stretch")
        prof = next(s["output"] for s in trace["steps"] if s["agent"] == "profile")
        grd = next(s["output"] for s in trace["steps"] if s["agent"] == "guardian")
        st.markdown("#### Profile agent: tolerance vs. capacity")
        st.write(prof.get("tolerance_vs_capacity"))
        if prof.get("question_for_investor"):
            st.info("❓ " + prof["question_for_investor"])
        st.markdown("#### Guardian")
        st.write(grd.get("hard_constraint_summary"))
        for x in grd.get("preference_conflicts", []) + grd.get("governance_flags", []):
            st.markdown(f"- {x}")
    with t4:
        steps = {s["agent"]: s["output"] for s in trace["steps"]}
        c1, c2 = st.columns(2)
        for col, side, title in ((c1, "advocate", "🟦 Advocate: the case for the idea"), (c2, "skeptic", "🟧 Skeptic: the case against")):
            with col:
                st.markdown(f"#### {title}")
                o = steps.get(side, {})
                st.write(o.get("position", ""))
                for arg in o.get("arguments", []):
                    st.markdown(f"- **{arg.get('claim')}**  \n  <span class='small'>{arg.get('evidence')}</span>", unsafe_allow_html=True)
                r = steps.get(f"{side}_rebuttal", {})
                st.markdown("**Rebuttal round**")
                for rb in r.get("rebuttals", []):
                    st.markdown(f"- ↪ {rb.get('response')}")
                for cc in r.get("concessions", []):
                    st.markdown(f"- 🤝 Concedes: {cc}")
    with t5:
        g = trace.get("grounding", {})
        gr = trace.get("guardrail", {})
        m = st.columns(4)
        m[0].metric("Numbers traced to data", g.get("summary", "n/a"))
        m[1].metric("Guardrail", f"{gr.get('status')}", f"{len(gr.get('blocked', []))} blocked of {gr.get('checked', 0)}", delta_color="off")
        m[2].metric("Agent calls / tokens", f"{sum(1 for s in trace['steps'] if s['kind'] == 'llm')} / {trace.get('total_tokens', 0):,}")
        m[3].metric("Run time", f"{trace.get('elapsed_s')} s")
        if g.get("ungrounded"):
            st.warning("Figures not found in the data: " + ", ".join(g["ungrounded"]))
        st.caption(f"Run `{trace['run_id']}` · model `{trace['model']}` · stored at `{trace.get('s3_uri') or 'local only'}`")
        st.json(tool["provenance"], expanded=False)
        st.dataframe(pd.DataFrame([{"Step": i + 1, "Agent": s["agent"], "Kind": s["kind"], "Latency ms": s.get("latency_ms"),
                                    "Tokens": s.get("tokens"),
                                    "Grounding": trace.get("grounding_by_agent", {}).get(s["agent"], {}).get("summary", "")}
                                   for i, s in enumerate(trace["steps"])]), hide_index=True, width="stretch")
        for s in trace["steps"]:
            with st.expander(f"{s['agent']} ({s['kind']})"):
                st.json(s["output"])
        st.download_button("Download full trace (JSON)", json.dumps(trace, indent=2, default=str),
                           file_name=f"secondlook_{trace['run_id']}.json")


# ------------------------------------------------------------------ page

st.title("🔎 SecondLook")
st.markdown("**A multi-agent second look before a self-directed investor acts.** It checks whether *your own idea* is "
            "consistent with *your own* goals, horizons and constraints, and explains why.")
st.caption("⚠️ Educational simulation. No real transactions, no personalised financial advice, fictional personas, public market data. "
           "Past performance does not guarantee future results.")

mode = st.sidebar.radio("Mode", ["Single investor", "Compare personas"], horizontal=True)
pid = st.sidebar.selectbox("Persona", list(PERSONAS), format_func=lambda k: f"{PERSONAS[k]['name']} ({PERSONAS[k]['age']})")
persona = PERSONAS[pid]
persona_sidebar(persona)

if mode == "Single investor":
    st.markdown(f"#### What is {persona['name']} thinking of doing?")
    cols = st.columns(len(persona["sample_requests"]))
    for i, (c, s) in enumerate(zip(cols, persona["sample_requests"])):
        if c.button(s[:60] + ("…" if len(s) > 60 else ""), key=f"s{pid}{i}", width="stretch"):
            st.session_state[f"req_{pid}"] = s
    req = st.text_area("Request (free text)", key=f"req_{pid}", height=80,
                       placeholder="e.g. I want to put $15,000 of my savings into XSP")
    if st.button("Take a second look", type="primary", disabled=not req):
        with st.status("Agents at work…", expanded=True) as status:
            trace = run(persona, req, on_step=lambda s: status.write(s))
            status.update(label=f"Done in {trace['elapsed_s']} s", state="complete", expanded=False)
        st.session_state[f"trace_{pid}"] = trace
    if st.session_state.get(f"trace_{pid}"):
        render_result(st.session_state[f"trace_{pid}"], persona)
else:
    st.markdown("#### Same request, different investors")
    st.caption("The kickoff asked for at least two contrasting personas. The same idea gets a different answer when goals, "
               "horizons and constraints differ.")
    presets = ["I want to put $15,000 of my cash into XSP.",
               "Move $20,000 of my cash into the Purpose Bitcoin ETF, crypto is about to explode.",
               "Add $5,000 of new money to ZQQ, tech has been doing great."]
    req = st.selectbox("Request sent to every persona (or type your own below)", presets)
    req = st.text_input("Custom request (optional)", "") or req
    if st.button("Run for all personas", type="primary"):
        with st.spinner("Running all personas in parallel…"):
            with ThreadPoolExecutor(len(PERSONAS)) as ex:
                futs = {k: ex.submit(run, p, req) for k, p in PERSONAS.items()}
                st.session_state["compare"] = {k: f.result() for k, f in futs.items()}
    if st.session_state.get("compare"):
        cols = st.columns(len(st.session_state["compare"]))
        for col, (k, tr) in zip(cols, st.session_state["compare"].items()):
            with col:
                p = PERSONAS[k]
                st.markdown(f"### {p['name']}, {p['age']}")
                st.caption(p["summary"])
                verdict_card(tr["result"])
                for r in tr["result"].get("key_reasons", [])[:4]:
                    st.markdown(f"- {r}")
                if tr.get("toolbox"):
                    for cf in tr["toolbox"]["counterfactuals"]:
                        _, icon, _ = VERDICT_STYLE[cf["ceiling"]]
                        st.markdown(f"<div class='small'>{icon} {cf['variant']}</div>", unsafe_allow_html=True)
        st.divider()
        pick = st.selectbox("Open full analysis for", list(st.session_state["compare"]), format_func=lambda k: PERSONAS[k]["name"])
        render_result(st.session_state["compare"][pick], PERSONAS[pick])
