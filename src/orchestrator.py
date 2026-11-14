"""Orchestrates the SecondLook pipeline and records a complete audit trace."""
from __future__ import annotations

import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from src import agents, aws
from src.analytics import (esg_view, exposures, macro_context, portfolio_risk, provenance, security_metrics,
                           stress_tests)
from src.bedrock import DEFAULT_MODEL
from src.grounding import check as grounding_check
from src.rules import counterfactuals, enforce, evaluate
from src.universe import UNIVERSE

UNIVERSE_BRIEF = {t: f"{m['name']} [{m['asset_class']}]" for t, m in UNIVERSE.items()}


class Trace:
    def __init__(self, persona, request):
        self.data = {"run_id": uuid.uuid4().hex[:12], "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "model": DEFAULT_MODEL, "persona_id": persona["id"], "request": request, "steps": [],
                     "persona_snapshot": persona}

    def step(self, agent, kind, output, meta=None, note=None):
        s = {"agent": agent, "kind": kind, "output": output}
        if meta:
            s.update(latency_ms=meta.get("latency_ms"), tokens=meta.get("usage", {}).get("totalTokens"))
        if note:
            s["note"] = note
        self.data["steps"].append(s)
        return output


OVERRIDE_RE = re.compile(r"ignore (all |your |previous )*(rules|instructions)|say (this|it) is consistent|"
                         r"override|disregard (the |your )?(rules|instructions)", re.I)


def _validate_action(a, persona, request=""):
    """Return a list of issue codes (kept in the audit trail; never shown raw to the user)."""
    goals = {g["id"] for g in persona["goals"]}
    issues = []
    if OVERRIDE_RE.search(request):
        issues.append("override_attempt")
    if a.get("ticker") not in UNIVERSE:
        named = a.get("security_mentioned") or a.get("ticker")
        issues.append("out_of_universe" if named and str(named).lower() not in ("none", "null", "unknown") else "unclear")
    try:
        if float(a.get("amount_cad") or 0) <= 0:
            issues.append("missing_amount")
    except (TypeError, ValueError):
        issues.append("missing_amount")
    if a.get("goal_id") not in goals:
        issues.append("unknown_goal")
    if not a.get("in_scope", True) and not issues:
        issues.append("unclear")
    if a.get("funding_goal_id") not in goals:
        a["funding_goal_id"] = None
    if a.get("funding") not in UNIVERSE:
        a["funding"] = "new_money"
    return issues


def _universe_groups():
    groups = {"Canadian stocks": [], "US stocks": [], "Funds (ETFs)": [], "Crypto": []}
    for t, m in UNIVERSE.items():
        if t == "CASH":
            continue
        if m["asset_class"] == "crypto":
            groups["Crypto"].append(t)
        elif m["diversified"] or m["asset_class"] in ("fixed_income", "cash_equivalent", "commodity"):
            groups["Funds (ETFs)"].append(t)
        elif t.endswith(".TO"):
            groups["Canadian stocks"].append(t)
        else:
            groups["US stocks"].append(t)
    return groups


def _needs_info(a, issues, persona):
    """Plain-language answer when the request can't be analysed yet: what we understood, what's missing,
    one specific question, and one-click answers."""
    name = persona["name"]
    asked = a.get("security_mentioned") or (a.get("ticker") if a.get("ticker") in UNIVERSE else None)
    understood = []
    if a.get("ticker") in UNIVERSE:
        understood.append(f"{a.get('action', 'buy')} {UNIVERSE[a['ticker']]['name']} ({a['ticker']})")
    try:
        if float(a.get("amount_cad") or 0) > 0:
            understood.append(f"${float(a['amount_cad']):,.0f}")
    except (TypeError, ValueError):
        pass
    res = {"verdict": "INSUFFICIENT_DATA", "confidence": "n/a", "issues": issues,
           "understood": " · ".join(understood) or None, "quick_answers": [], "universe_groups": None}
    if "override_attempt" in issues:
        res.update(headline="SecondLook's rules can't be switched off.",
                   plain_summary="The request asks to ignore the rules or to force a verdict. The rules are what make the "
                                 "answer trustworthy, so they always apply. Ask the same question without that part and "
                                 "SecondLook will check it normally.",
                   followup_question="What would you like to check?")
        tail = OVERRIDE_RE.split(a.get("investor_rationale") or "")[-1].strip(" :.,-") if a.get("investor_rationale") else ""
        if tail and len(tail) > 10:
            res["quick_answers"] = [tail[0].upper() + tail[1:]]
        return res
    if "out_of_universe" in issues:
        what = asked or "That security"
        n = len(UNIVERSE) - 1  # excluding the synthetic CASH line
        res.update(headline=f"{what} isn't one of the {n} assets SecondLook can analyse.",
                   plain_summary="This prototype only analyses assets with documented, validated price history (the "
                                 "official starter universe plus our supplemental assets), so every number can be "
                                 "computed. Pick one of the assets below, or a similar one.",
                   followup_question="Which of these did you mean?", universe_groups=_universe_groups())
        return res
    if "unclear" in issues:
        res.update(headline="SecondLook couldn't tell what the idea is.",
                   plain_summary="Describe it like you would to a friend: what to buy or sell, how much, and where the money "
                                 "comes from. For example: \"Move $10,000 from my XBB bond fund into SPY.\"",
                   followup_question="What would you like to do?", quick_answers=persona.get("sample_requests", [])[:2])
        return res
    if "missing_amount" in issues:
        sec = UNIVERSE[a["ticker"]]["name"] if a.get("ticker") in UNIVERSE else "it"
        res.update(headline="How much would you like to put in?",
                   plain_summary=f"SecondLook understood the idea but needs an amount to check it against {name}'s limits, "
                                 f"and to know where the money comes from (new money or an existing holding).",
                   followup_question=f"How much, in Canadian dollars, for {sec}?",
                   quick_answers=["$5,000 of new money", "$10,000 of new money", "$20,000 of new money"])
        return res
    if "unknown_goal" in issues:
        res.update(headline="Which goal is this money for?",
                   plain_summary=f"{name} has several goals with different time horizons, and the answer depends on which "
                                 "one this money belongs to.",
                   followup_question="Which goal?", quick_answers=[f"For my {g['label'].lower()}" for g in persona["goals"]])
        return res
    res.update(headline="SecondLook couldn't tell what the idea is.",
               plain_summary="Describe it like you would to a friend: what to buy or sell, how much, and where the money "
                             "comes from. For example: \"Move $10,000 from my XBB bond fund into SPY.\"",
               followup_question="What would you like to do?", quick_answers=persona.get("sample_requests", [])[:2])
    return res


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
    errs = _validate_action(action, persona, request)
    if re.search(r"\bnew money\b|\bfresh money\b", request, re.I) and action.get("funding") != "new_money" and not errs:
        tr.step("validator", "deterministic", {"correction": f"request says 'new money': funding {action.get('funding')} -> new_money"})
        action["funding"], action["funding_goal_id"] = "new_money", None
    if errs:
        tr.step("validator", "deterministic", {"issues": errs, "intake_ambiguities": action.get("ambiguities", [])})
        tr.data["result"] = _needs_info(action, errs, persona)
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
        "macro_context": macro_context(),
        "esg_before": esg_view(persona, holdings), "esg_after": esg_view(persona, after),
    }
    ev["esg_view"] = {"before": tool["esg_before"], "after": tool["esg_after"]} if tool["esg_after"] else None
    tr.step("toolbox", "deterministic", {"rule_ceiling": ev["ceiling"], "ceiling_reasons": ev["ceiling_reasons"],
                                          "n_counterfactuals": len(tool["counterfactuals"])})
    tr.data["toolbox"] = tool

    # 3. Profile + analyst in parallel
    notify("Profile and market analyst agents")
    with ThreadPoolExecutor(2) as ex:
        fp = ex.submit(agents.profile, persona, ev, action)
        fa = ex.submit(agents.analyst, action, tool["security"], tool["exposures_before"], tool["exposures_after"],
                       tool["risk_before"], tool["risk_after"], tool["stress_before"], tool["stress_after"], tool["provenance"],
                       tool["macro_context"], ev["esg_view"])
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
    bundle = {"investor": {k: persona[k] for k in ("name", "age", "objective", "knowledge_level", "risk_tolerance", "goals", "constraints", "preferences")},
              "request": request, "action": action, "rule_ceiling": ev["ceiling"], "ceiling_reasons": ev["ceiling_reasons"],
              "profile": prof, "market_analysis": ana,
              "debate": {"advocate": adv, "skeptic": skp, "advocate_rebuttal": adv_r, "skeptic_rebuttal": skp_r},
              "guardian": grd, "counterfactuals": tool["counterfactuals"], "data_provenance": tool["provenance"],
              "macro_context": tool["macro_context"], "esg_view": ev["esg_view"],
              "security": {k: tool["security"][k] for k in ("name", "annual_volatility", "max_drawdown", "worst_12m_return",
                                                            "risk_units_vs_spy", "window", "note")}}
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
        from src.errors import friendly
        tr.data["s3_uri"] = None
        tr.data["s3_error"] = friendly(e)["title"]
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
    blocked, flagged = [], []
    for (f, i, k, original), o in zip(jobs, outs):
        if o.get("detected_only"):
            flagged.append({"field": f, "index": i, "topics": o["detected_only"], "text": original})
        if o["action"] == "GUARDRAIL_INTERVENED":
            blocked.append({"field": f, "index": i, "topics": o.get("topics"), "words": o.get("words"),
                            "original_text": original})
            if i is None:
                res[f] = o["text"]
            elif k:
                res[f][i][k] = o["text"]
            else:
                res[f][i] = o["text"]
    return {"status": "active", "checked": len(jobs), "blocked": blocked, "flagged_not_blocked": flagged}
