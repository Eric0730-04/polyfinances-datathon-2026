"""Deterministic governance rules: verdict ceilings and counterfactual what-ifs.

Verdict logic (same for hard constraints and goal risk limits):
- creates or worsens a breach                    -> INCONSISTENT
- leaves a pre-existing breach in place/reduced  -> CONSISTENT_WITH_CONDITIONS
- no breach before or after                      -> CONSISTENT

The LLM judge may choose a verdict that is equal to or more cautious than the rule ceiling,
never more permissive. Counterfactuals are computed, not generated, so "what would change
the answer" is backed by numbers.
"""
from src.analytics import UNIVERSE, apply_action, check_constraints, goal_buckets

VERDICTS = ["CONSISTENT", "CONSISTENT_WITH_CONDITIONS", "INCONSISTENT"]  # order = increasing caution
SPECIAL = "INSUFFICIENT_DATA"


def evaluate(persona, holdings, action):
    """Rule-based assessment of one action: constraints, destination-goal capacity, ceiling."""
    after, warnings = apply_action(holdings, action)
    checks = check_constraints(persona, holdings, after)
    gb = {g["goal_id"]: g for g in goal_buckets(persona, holdings)}
    ga = {g["goal_id"]: g for g in goal_buckets(persona, after)}
    reasons, ceiling = [], "CONSISTENT"

    def cap(level, why):
        nonlocal ceiling
        reasons.append(why)
        if VERDICTS.index(level) > VERDICTS.index(ceiling):
            ceiling = level

    for c in checks:
        if c["blocking"]:
            cap("INCONSISTENT", f"Hard constraint breached: {c['rule']} (before {c['before']}, after {c['after']})")
    if warnings:
        cap("INCONSISTENT", "; ".join(warnings))
    for gid in {action.get("goal_id"), action.get("funding_goal_id")} - {None}:
        b, a = gb.get(gid), ga.get(gid)
        if not a:
            continue
        b_share = b["risky_share"] if b else 0.0
        if a["status"] == "over limit" and (not b or b["status"] == "within limit"):
            cap("INCONSISTENT", f"Goal '{a['label']}' ({a['horizon_years']}y horizon) moves from within to over its "
                                f"risky-asset limit: {b_share:.0%} -> {a['risky_share']:.0%} (limit {a['allowed_max_risky']:.0%}, "
                                f"bound by {a['binding_limit']})")
        elif a["status"] == "over limit" and a["risky_share"] > b_share + 1e-6:
            cap("INCONSISTENT", f"Goal '{a['label']}' was already over its risky-asset limit and this action increases "
                                f"it further: {b_share:.0%} -> {a['risky_share']:.0%} (limit {a['allowed_max_risky']:.0%})")
        elif a["status"] == "over limit":
            cap("CONSISTENT_WITH_CONDITIONS", f"Goal '{a['label']}' is already over its risky-asset limit; this action does "
                                              f"not increase it ({b_share:.0%} -> {a['risky_share']:.0%}, limit "
                                              f"{a['allowed_max_risky']:.0%}) but the pre-existing gap remains")
    for c in checks:
        if not c["passed"] and not c["blocking"]:
            if c["severity"] == "soft" and c["status"].startswith("worsened"):
                cap("CONSISTENT_WITH_CONDITIONS", f"Soft check (preference) worsened: {c['rule']} "
                                                  f"({c['before']} -> {c['after']})")
            else:
                cap("CONSISTENT_WITH_CONDITIONS", f"Pre-existing breach not created by this action: {c['rule']} "
                                                  f"({c['status']}: {c['before']} -> {c['after']})")
    return {"after": after, "warnings": warnings, "constraints": checks, "ceiling": ceiling,
            "ceiling_reasons": reasons, "buckets_before": list(gb.values()), "buckets_after": list(ga.values())}


def counterfactuals(persona, holdings, action):
    """Alternative versions of the same idea, each evaluated with the same rules."""
    out = []
    base = evaluate(persona, holdings, action)
    if action.get("action", "buy") != "buy":
        return out

    def summarize(label, act, ev):
        return {"variant": label, "action": act, "ceiling": ev["ceiling"], "reasons": ev["ceiling_reasons"]}

    # 1. same purchase with new money
    if action.get("funding") not in (None, "new_money"):
        a = {**action, "funding": "new_money", "funding_goal_id": None}
        out.append(summarize("Funded with new money instead", a, evaluate(persona, holdings, a)))

    # 2. swap: fund by trimming the largest single-stock position in the destination goal
    goal = action.get("goal_id")
    stocks = [h for h in holdings if h.get("goal") == goal and not UNIVERSE[h["ticker"]]["diversified"]
              and h["ticker"] != action["ticker"]]
    if stocks:
        top = max(stocks, key=lambda h: h["value_cad"])
        amt = min(float(action["amount_cad"]), top["value_cad"])
        a = {**action, "amount_cad": amt, "funding": top["ticker"], "funding_goal_id": goal}
        out.append(summarize(f"Swap: fund by trimming {top['ticker']} (largest single-security position in this goal)", a,
                             evaluate(persona, holdings, a)))

    # 3. largest amount (same funding) that keeps the rule ceiling at least as good as CONSISTENT_WITH_CONDITIONS
    if base["ceiling"] == "INCONSISTENT":
        lo, hi, step = 0.0, float(action["amount_cad"]), 250.0
        while hi - lo > step:
            mid = (lo + hi) / 2
            ev = evaluate(persona, holdings, {**action, "amount_cad": mid})
            lo, hi = (mid, hi) if ev["ceiling"] != "INCONSISTENT" else (lo, mid)
        amt = int(lo // step * step)
        a = {**action, "amount_cad": amt}
        if amt > 0:
            out.append(summarize(f"Smaller amount: ${amt:,} instead of ${float(action['amount_cad']):,.0f}", a,
                                 evaluate(persona, holdings, a)))
        else:
            out.append({"variant": "Smaller amount", "action": a, "ceiling": "INCONSISTENT",
                        "reasons": ["No positive amount of this purchase, funded this way, stays within the rules."]})
    return out


def enforce(judge_verdict, ceiling):
    """Apply the ceiling: the final verdict can never be more permissive than the rules allow."""
    if judge_verdict == SPECIAL:
        return judge_verdict, False
    if judge_verdict not in VERDICTS:
        return ceiling, True
    if VERDICTS.index(judge_verdict) < VERDICTS.index(ceiling):
        return ceiling, True
    return judge_verdict, False
