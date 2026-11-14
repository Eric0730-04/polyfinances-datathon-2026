"""SecondLook web server: JSON + Server-Sent Events API around the agent pipeline, and the static web UI.

Run:  AWS_PROFILE=team10 .venv/bin/uvicorn server:app --port 8000
"""
import copy
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import agents, aws
from src.analytics import exposures, goal_buckets, macro_context, portfolio_risk, provenance, risk_units
from src.analytics import CAPACITY_RULES, TOLERANCE_CAP
from src.bedrock import DEFAULT_MODEL
from src.errors import friendly
from src.grounding import check as grounding_check
from src.orchestrator import run
from src.rules import evaluate
from src.universe import UNIVERSE

ROOT = Path(__file__).parent
ORDER = ["robert", "amira", "mateo", "maya"]
PERSONAS = {p.stem: json.loads(p.read_text()) for p in (ROOT / "personas").glob("*.json")}
PERSONAS = {k: PERSONAS[k] for k in sorted(PERSONAS, key=lambda k: ORDER.index(k) if k in ORDER else 99)}

app = FastAPI(title="SecondLook")
TRACES: dict = {}  # in-memory cache of this session's analyses (S3 holds the durable copy)
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


def _dump(obj):
    return json.dumps(obj, default=str)


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/meta")
def meta():
    cfg = aws._cfg()
    return {"model": DEFAULT_MODEL, "bucket": cfg["bucket"], "guardrail_id": cfg["guardrail_id"],
            "provenance": provenance(), "macro": macro_context(),
            "capacity_rules": CAPACITY_RULES, "tolerance_caps": TOLERANCE_CAP,
            "risk_units": risk_units(),
            "universe": {t: {"name": m["name"], "asset_class": m["asset_class"], "sector": m.get("starter_sector")}
                         for t, m in UNIVERSE.items()}}


@app.get("/api/personas")
def personas():
    out = []
    for pid, p in PERSONAS.items():
        h = p["holdings"]
        out.append({**p, "baseline": {"exposures": exposures(h), "goals": goal_buckets(p, h), "risk": portfolio_risk(h)},
                    "holding_names": {x["ticker"]: UNIVERSE[x["ticker"]]["name"] for x in h}})
    return out


@app.get("/api/trace/{run_id}")
def trace(run_id: str):
    """Re-open a past analysis from its S3 audit record (falls back to the local runs/ folder)."""
    if not run_id.isalnum():
        raise HTTPException(400, "That run ID isn't valid.")
    t = _get_trace(run_id)
    if not t:
        raise HTTPException(404, "No saved analysis with that run ID.")
    return t


class AnalyzeIn(BaseModel):
    persona_id: str
    request: str


def _stream_run(persona, request):
    q: queue.Queue = queue.Queue()

    def work():
        try:
            trace = run(persona, request, on_step=lambda s: q.put(("step", {"label": s})))
            TRACES[trace["run_id"]] = trace
            q.put(("result", trace))
        except Exception as e:  # surface a readable error to the UI instead of hanging
            q.put(("error", friendly(e)))
        q.put(None)

    threading.Thread(target=work, daemon=True).start()
    while True:
        item = q.get()
        if item is None:
            break
        ev, data = item
        yield f"event: {ev}\ndata: {_dump(data)}\n\n"


@app.post("/api/analyze")
def analyze(body: AnalyzeIn):
    if body.persona_id not in PERSONAS:
        raise HTTPException(404, "That investor profile doesn't exist. Reload the page.")
    if not body.request.strip():
        raise HTTPException(400, "Type an idea first, or pick one of the suggestions.")
    if len(body.request) > 1000:
        raise HTTPException(400, "That's too long. Describe the idea in a sentence or two.")
    return StreamingResponse(_stream_run(PERSONAS[body.persona_id], body.request), media_type="text/event-stream")


class CompareIn(BaseModel):
    request: str


@app.post("/api/compare")
def compare(body: CompareIn):
    def gen():
        q: queue.Queue = queue.Queue()

        def one(pid):
            try:
                t = run(PERSONAS[pid], body.request)
                TRACES[t["run_id"]] = t
                q.put(("result", {"persona_id": pid, "trace": t}))
            except Exception as e:
                q.put(("error", {"persona_id": pid, **friendly(e)}))

        with ThreadPoolExecutor(len(PERSONAS)) as ex:
            for pid in PERSONAS:
                ex.submit(one, pid)
            for _ in PERSONAS:
                ev, data = q.get()
                yield f"event: {ev}\ndata: {_dump(data)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


class WhatIfIn(BaseModel):
    persona_id: str
    action: dict
    horizon_years: float | None = None
    risk_tolerance: str | None = None


@app.post("/api/whatif")
def whatif(body: WhatIfIn):
    """Instant deterministic recompute of the rules for a modified version of the idea (no AI involved)."""
    if body.persona_id not in PERSONAS:
        raise HTTPException(404, "That investor profile doesn't exist. Reload the page.")
    p = copy.deepcopy(PERSONAS[body.persona_id])
    a = dict(body.action)
    if a.get("ticker") not in UNIVERSE or a.get("ticker") == "CASH":
        raise HTTPException(400, "Pick one of the assets in the list.")
    goals = {g["id"]: g for g in p["goals"]}
    if a.get("goal_id") not in goals:
        raise HTTPException(400, "Pick one of the investor's goals.")
    if a.get("funding") not in UNIVERSE:
        a["funding"], a["funding_goal_id"] = "new_money", None
    a["amount_cad"] = max(0.0, float(a.get("amount_cad") or 0))
    if body.horizon_years is not None:
        goals[a["goal_id"]]["horizon_years"] = max(0.0, float(body.horizon_years))
    if body.risk_tolerance in TOLERANCE_CAP:
        p["risk_tolerance"] = body.risk_tolerance
    if a["amount_cad"] < 1:
        a["amount_cad"] = 1.0  # a zero trade is the baseline itself
    ev = evaluate(p, p["holdings"], a)
    return {"ceiling": ev["ceiling"], "reasons": ev["ceiling_reasons"], "constraints": ev["constraints"],
            "buckets_before": ev["buckets_before"], "buckets_after": ev["buckets_after"], "warnings": ev["warnings"],
            "goal_id": a["goal_id"], "risk_units": risk_units()[a["ticker"]]}


def _get_trace(run_id):
    if run_id in TRACES:
        return TRACES[run_id]
    local = ROOT / "runs" / f"{run_id}.json"
    t = json.loads(local.read_text()) if local.exists() else aws.load_trace(run_id)
    if t:
        TRACES[run_id] = t
    return t


def _chat_context(t):
    """Compact, grounded view of one analysis for the follow-up assistant."""
    tb, r = t.get("toolbox") or {}, t["result"]
    step = lambda a: next((s["output"] for s in t["steps"] if s["agent"] == a), {})  # noqa: E731
    ctx = {"request": t["request"], "action": t.get("action"),
           "verdict": {k: r.get(k) for k in ("verdict", "headline", "plain_summary", "key_reasons", "no_longer_valid_if",
                                              "facts", "assumptions", "limits")}}
    if tb:
        ctx.update({
            "rules": {k: tb["rules"][k] for k in ("ceiling", "ceiling_reasons", "buckets_before", "buckets_after")},
            "constraint_checks": [{k: c[k] for k in ("rule", "status", "before", "after", "severity")} for c in tb["rules"]["constraints"]],
            "variants": [{k: c.get(k) for k in ("variant", "ceiling", "changes_result", "fixes", "still")} for c in tb["counterfactuals"]],
            "security": tb["security"], "risk_before": tb["risk_before"], "risk_after": tb["risk_after"],
            "exposures_before": {k: tb["exposures_before"][k] for k in ("asset_class", "equity_geography", "currency")},
            "exposures_after": {k: tb["exposures_after"][k] for k in ("asset_class", "equity_geography", "currency")},
            "top_sectors_after": dict(list(tb["exposures_after"]["equity_sectors"].items())[:5]),
            "stress": [{"scenario": s["label"], "type": s["type"], "before_pct": b["impact_pct"], "after_pct": s["impact_pct"],
                        "after_cad": s["impact_cad"]} for s, b in zip(tb["stress_after"], tb["stress_before"])],
            "macro_context": tb.get("macro_context"), "esg": tb.get("esg_after"), "data_provenance": tb.get("provenance"),
            "debate": {"advocate": step("advocate").get("position"), "skeptic": step("skeptic").get("position"),
                       "judge_takeaway": r.get("debate_takeaway")},
        })
    return ctx


class ChatIn(BaseModel):
    run_id: str
    question: str
    history: list = []


@app.post("/api/chat")
def chat(body: ChatIn):
    if not body.question.strip():
        raise HTTPException(400, "Type a question first.")
    if len(body.question) > 600:
        raise HTTPException(400, "That question is too long. Ask it in a sentence or two.")
    t = _get_trace(body.run_id) if body.run_id.isalnum() else None
    if not t:
        raise HTTPException(404, "This analysis is no longer available. Run it again to ask follow-ups.")
    persona = PERSONAS.get(t["persona_id"], {})
    ctx = _chat_context(t)
    analysable = {t: m["name"] for t, m in UNIVERSE.items() if t != "CASH"}
    try:
        out, meta = agents.chat(persona, ctx, body.history, body.question, analysable)
    except Exception as e:
        return {"error": friendly(e)}
    g = grounding_check({"answer": out.get("answer", "")}, ctx, persona)
    try:
        gr = aws.guard(out.get("answer", ""))
        if gr["action"] == "GUARDRAIL_INTERVENED":
            out["answer"] = ("SecondLook doesn't predict prices or promise returns. What it can show is how this idea "
                             "behaved in past stress periods (see Stress tests) and whether it fits your goals and limits.")
    except Exception:
        gr = {"action": "error"}
    whatif = out.get("whatif")
    if not (isinstance(whatif, dict) and whatif.get("ticker") in UNIVERSE):
        mentioned = _mentioned_asset(body.question, exclude=(t.get("action") or {}).get("ticker"))
        whatif = {"ticker": mentioned} if mentioned else None
    instant = _instant_check(persona, t, whatif)
    if instant:  # the reply's numbers come from the rules engine, never from the model
        a, gg, v = instant["action"], instant["goal"], instant["ceiling"]
        label = {"CONSISTENT": "consistent with the profile", "CONSISTENT_WITH_CONDITIONS": "consistent only under conditions",
                 "INCONSISTENT": "inconsistent with the profile"}[v]
        fund = "with new money" if a["funding"] == "new_money" else f"by selling {a['funding']}"
        out["answer"] = (f"I ran an instant check of that version ({UNIVERSE[a['ticker']]['name']}, ${a['amount_cad']:,.0f} paid "
                         f"{fund}): it would be {label}. The '{gg['label']}' goal would go from {gg['before']:.0%} to "
                         f"{gg['after']:.0%} S&P 500-equivalent risk, against a {gg['limit']:.0%} limit. Details are below; "
                         f"you can also run the full AI analysis on it.")
        out["rerun_request"] = out.get("rerun_request") or (
            f"Put ${a['amount_cad']:,.0f} of {'new money' if a['funding'] == 'new_money' else 'my ' + a['funding']} into "
            f"{a['ticker']} for my {gg['label'].lower()} goal.")
        g = {"checked": 0, "ungrounded": [], "summary": "numbers computed by the rules engine"}
    return {"answer": out.get("answer", ""), "rerun_request": out.get("rerun_request"),
            "instant_check": instant,
            "suggested_questions": (out.get("suggested_questions") or [])[:3], "grounding": g,
            "guardrail": gr.get("action"), "latency_ms": meta.get("latency_ms")}


def _instant_check(persona, t, w):
    """Deterministic evaluation of a version the investor asked about in chat (numbers never come from the LLM)."""
    if not isinstance(w, dict) or w.get("ticker") not in UNIVERSE or w.get("ticker") == "CASH":
        return None
    base = t.get("action") or {}
    goals = {g["id"] for g in persona.get("goals", [])}
    try:
        amount = float(w.get("amount_cad") or base.get("amount_cad") or 0)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    a = {"action": "buy", "ticker": w["ticker"], "amount_cad": amount,
         "goal_id": w.get("goal_id") if w.get("goal_id") in goals else base.get("goal_id"),
         "funding": w.get("funding") if w.get("funding") in UNIVERSE or w.get("funding") == "new_money"
         else base.get("funding") or "new_money"}
    if a["goal_id"] not in goals:
        return None
    a["funding_goal_id"] = next((h["goal"] for h in persona["holdings"] if h["ticker"] == a["funding"]), None)
    ev = evaluate(persona, persona["holdings"], a)
    g = next(x for x in ev["buckets_after"] if x["goal_id"] == a["goal_id"])
    b = next(x for x in ev["buckets_before"] if x["goal_id"] == a["goal_id"])
    return {"action": a, "ceiling": ev["ceiling"], "reasons": ev["ceiling_reasons"],
            "goal": {"label": g["label"], "before": b["risky_share"], "after": g["risky_share"], "limit": g["allowed_max_risky"]}}


STOP = {"inc.", "inc", "corp.", "corp", "the", "ishares", "core", "index", "etf", "trust", "spdr", "vanguard", "bmo",
        "global", "class", "company", "companies", "co.", "bank", "of", "and", "&"}


def _aliases():
    out = {}
    for t, m in UNIVERSE.items():
        if t == "CASH":
            continue
        out[t.lower()] = t
        out[t.split(".")[0].split("-")[0].lower()] = t
        words = [w for w in m["name"].lower().replace("(", " ").replace(")", " ").split() if w not in STOP and len(w) >= 4]
        if words:
            out.setdefault(words[0], t)
    out.update({"google": "GOOGL", "ethereum": "ETH-USD", "bitcoin": "BTC-USD", "solana": "SOL-USD", "nasdaq": "QQQ",
                "s&p": "SPY", "gold": "GLD", "coke": "KO", "berkshire": "BRK-B"})
    return out


ALIASES = None


def _mentioned_asset(question, exclude=None):
    """Find an analysable asset named in a chat question (ticker or company name)."""
    global ALIASES
    ALIASES = ALIASES or _aliases()
    import re
    for w in re.findall(r"[A-Za-z][A-Za-z0-9&.\-]+", question):
        t = ALIASES.get(w.lower().strip(".,?!"))
        if t and t != exclude and (len(w) > 3 or w.isupper()):
            return t
    return None
