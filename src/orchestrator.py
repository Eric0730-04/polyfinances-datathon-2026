"""Orchestrates the SecondLook pipeline and records a complete audit trace."""
from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from src import agents, aws
from src.analytics import (exposures, portfolio_risk, provenance, security_metrics, stress_tests)
from src.bedrock import DEFAULT_MODEL
from src.grounding import check as grounding_check
from src.rules import counterfactuals, enforce, evaluate
from src.universe import UNIVERSE

UNIVERSE_BRIEF = {t: f"{m['name']} [{m['asset_class']}]" for t, m in UNIVERSE.items()}


class Trace:
    def __init__(self, persona, request):
        self.data = {"run_id": uuid.uuid4().hex[:12], "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "model": DEFAULT_MODEL, "persona_id": persona["id"], "request": request, "steps": []}

    def step(self, agent, kind, output, meta=None, note=None):
        s = {"agent": agent, "kind": kind, "output": output}
        if meta:
            s.update(latency_ms=meta.get("latency_ms"), tokens=meta.get("usage", {}).get("totalTokens"))
        if note:
            s["note"] = note
        self.data["steps"].append(s)
        return output


def _validate_action(a, persona):
    goals = {g["id"] for g in persona["goals"]}
    errs = []
    if not a.get("in_scope", True):
        errs.append("Request is out of scope for the prototype universe")
    if a.get("ticker") not in UNIVERSE:
        errs.append(f"Unknown ticker {a.get('ticker')}")
    try:
        if float(a.get("amount_cad") or 0) <= 0:
            errs.append("Missing or non-positive amount")
    except (TypeError, ValueError):
        errs.append("Amount is not a number")
    if a.get("goal_id") not in goals:
        errs.append(f"Unknown goal {a.get('goal_id')}")
    if a.get("funding_goal_id") not in goals:
        a["funding_goal_id"] = None
    if a.get("funding") not in UNIVERSE:
        a["funding"] = "new_money"
    return errs


def run(persona: dict, request: str, action_override: dict | None = None, on_step=None) -> dict:
    """Run the full pipeline. on_step(name) is called as each stage starts (for UI progress)."""
    t0 = time.time()
    tr = Trace(persona, request)
    notify = on_step or (lambda *_: None)
    holdings = persona["holdings"]

    # 1. Intake
    notify("Intake agent: understanding the request")
    if action_override:
        action = tr.step("intake", "override", dict(action_override), note="action supplied directly")
    else:
        parsed, meta = agents.intake(request, persona, UNIVERSE_BRIEF)
        action = tr.step("intake", "llm", parsed, meta)
    errs = _validate_action(action, persona)
    if errs:
        tr.step("validator", "deterministic", {"errors": errs})
        tr.data["result"] = {"verdict": "INSUFFICIENT_DATA", "headline": "I need more details before taking a second look.",
                             "plain_summary": " ".join(errs + action.get("ambiguities", [])), "confidence": "low"}
        tr.data["elapsed_s"] = round(time.time() - t0, 1)
        return _finish(tr)

    # 2. Deterministic toolbox
    notify("Toolbox: computing exposures, risk, stress tests and rules")
    ev = evaluate(persona, holdings, action)
    after = ev["after"]
    tool = {
        "provenance": provenance(),
        "security": security_metrics(action["ticker"]),
        "exposures_before": exposures(holdings), "exposures_after": exposures(after),
        "risk_before": portfolio_risk(holdings), "risk_after": portfolio_risk(after),
        "stress_before": stress_tests(holdings), "stress_after": stress_tests(after),
        "rules": {k: ev[k] for k in ("constraints", "ceiling", "ceiling_reasons", "buckets_before", "buckets_after", "warnings")},
        "counterfactuals": counterfactuals(persona, holdings, action),
    }
    tr.step("toolbox", "deterministic", {"rule_ceiling": ev["ceiling"], "ceiling_reasons": ev["ceiling_reasons"],
                                          "n_counterfactuals": len(tool["counterfactuals"])})
    tr.data["toolbox"] = tool

    # 3. Profile + analyst in parallel
    notify("Profile and market analyst agents")
    with ThreadPoolExecutor(2) as ex:
        fp = ex.submit(agents.profile, persona, ev, action)
        fa = ex.submit(agents.analyst, action, tool["security"], tool["exposures_before"], tool["exposures_after"],
                       tool["risk_before"], tool["risk_after"], tool["stress_before"], tool["stress_after"], tool["provenance"])
        prof, pm = fp.result()
        ana, am = fa.result()
    tr.step("profile", "llm", prof, pm)
    tr.step("analyst", "llm", ana, am)

    # 4. Debate: opening statements in parallel, then one rebuttal round in parallel
    notify("Advocate vs skeptic debate")
    ctx = {"request": request, "action": action, "investor_summary": persona["summary"],
           "investor_rationale": action.get("investor_rationale"), "profile_findings": prof, "market_analysis": ana,
           "constraint_checks": ev["constraints"], "goal_buckets_after": ev["buckets_after"]}
    with ThreadPoolExecutor(2) as ex:
        fa_, fs_ = ex.submit(agents.debater, "advocate", ctx), ex.submit(agents.debater, "skeptic", ctx)
        adv, m1 = fa_.result()
        skp, m2 = fs_.result()
    tr.step("advocate", "llm", adv, m1)
    tr.step("skeptic", "llm", skp, m2)
    with ThreadPoolExecutor(2) as ex:
        fa_ = ex.submit(agents.debater, "advocate", ctx, skp.get("arguments"))
        fs_ = ex.submit(agents.debater, "skeptic", ctx, adv.get("arguments"))
        adv_r, m3 = fa_.result()
        skp_r, m4 = fs_.result()
    tr.step("advocate_rebuttal", "llm", adv_r, m3)
    tr.step("skeptic_rebuttal", "llm", skp_r, m4)

    # 5. Guardian
    notify("Constraint guardian")
    grd, gm = agents.guardian(persona, ev, action)
    tr.step("guardian", "llm", grd, gm)

    # 6. Judge
    notify("Judge: verdict and explanation")
    bundle = {"investor": {k: persona[k] for k in ("name", "age", "knowledge_level", "risk_tolerance", "goals", "constraints", "preferences")},
              "request": request, "action": action, "rule_ceiling": ev["ceiling"], "ceiling_reasons": ev["ceiling_reasons"],
              "profile": prof, "market_analysis": ana,
              "debate": {"advocate": adv, "skeptic": skp, "advocate_rebuttal": adv_r, "skeptic_rebuttal": skp_r},
              "guardian": grd, "counterfactuals": tool["counterfactuals"], "data_provenance": tool["provenance"],
              "security": {k: tool["security"][k] for k in ("name", "annual_volatility", "max_drawdown", "worst_12m_return", "metrics_window", "note")}}
    res, jm = agents.judge(persona, action, bundle)
    final, adjusted = enforce(res.get("verdict"), ev["ceiling"])
    if adjusted:
        res["verdict_from_judge"] = res.get("verdict")
        res["verdict_adjustment"] = (f"Judge proposed {res.get('verdict')}, but the deterministic rules cap this case at "
                                     f"{ev['ceiling']}: " + "; ".join(ev["ceiling_reasons"]))
    res["verdict"] = final
    res["rule_ceiling"] = ev["ceiling"]
    tr.step("judge", "llm", res, jm)

    tr.data["result"] = res
    tr.data["action"] = action
    # numeric grounding of everything the agents wrote vs. everything they were given
    sources = (tool, persona, action)
    tr.data["grounding"] = grounding_check(res, *sources)
    tr.data["grounding_by_agent"] = {s["agent"]: grounding_check(s["output"], *sources)
                                     for s in tr.data["steps"] if s["kind"] == "llm"}
    # 7. Bedrock Guardrail on every user-facing string
    notify("Guardrail: responsible-output screen")
    tr.data["guardrail"] = _guard_result(res)

    tr.data["elapsed_s"] = round(time.time() - t0, 1)
    tr.data["total_tokens"] = sum(s.get("tokens") or 0 for s in tr.data["steps"])
    return _finish(tr)


def _finish(tr):
    """Persist the audit trace to S3 (never lose the analysis because of storage)."""
    try:
        tr.data["s3_uri"] = aws.save_trace(tr.data)
    except Exception as e:
        tr.data["s3_uri"] = None
        tr.data["s3_error"] = str(e)[:200]
    return tr.data


GUARDED_FIELDS = ("headline", "plain_summary", "key_reasons", "debate_takeaway", "no_longer_valid_if", "variants")


def _guard_result(res):
    """Screen each user-facing string; replace any blocked string in place. Returns a summary."""
    jobs = []
    for f in GUARDED_FIELDS:
        v = res.get(f)
        if isinstance(v, str):
            jobs.append((f, None, None, v))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, str):
                    jobs.append((f, i, None, x))
                elif isinstance(x, dict) and isinstance(x.get("comment"), str):
                    jobs.append((f, i, "comment", x["comment"]))
    try:
        with ThreadPoolExecutor(8) as ex:
            outs = list(ex.map(lambda j: aws.guard(j[3]), jobs))
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], "checked": 0}
    if outs and outs[0]["action"] == "NOT_CONFIGURED":
        return {"status": "not configured", "checked": 0}
    blocked = []
    for (f, i, k, _), o in zip(jobs, outs):
        if o["action"] == "GUARDRAIL_INTERVENED":
            blocked.append({"field": f, "index": i, "topics": o.get("topics"), "words": o.get("words")})
            if i is None:
                res[f] = o["text"]
            elif k:
                res[f][i][k] = o["text"]
            else:
                res[f][i] = o["text"]
    return {"status": "active", "checked": len(jobs), "blocked": blocked}
