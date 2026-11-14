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


def _f(v):
    """Human format for check values: fractions as %, dollar amounts as $."""
    if isinstance(v, (int, float)):
        return f"${v:,.0f}" if abs(v) > 1.5 else f"{v * 100:.1f}%"
    return str(v)

VERDICTS = ["CONSISTENT", "CONSISTENT_WITH_CONDITIONS", "INCONSISTENT"]  # order = increasing caution
SPECIAL = "INSUFFICIENT_DATA"


def evaluate(persona, holdings, action):
    """Rule-based assessment of one action: constraints, destination-goal capacity, ceiling."""
    after, warnings = apply_action(holdings, action)
    checks = check_constraints(persona, holdings, after)
    gb = {g["goal_id"]: g for g in goal_buckets(persona, holdings)}
    ga = {g["goal_id"]: g for g in goal_buckets(persona, after)}
    reasons, keys, ceiling = [], [], "CONSISTENT"

    def cap(level, why, key):
        nonlocal ceiling
        reasons.append(why)
        keys.append(key)
        if VERDICTS.index(level) > VERDICTS.index(ceiling):
            ceiling = level

    for c in checks:
        if c["blocking"]:
            cap("INCONSISTENT", f"Hard constraint breached: {c['rule']} (before {_f(c['before'])}, after {_f(c['after'])})",
                f"hard:{c['rule']}")
    if warnings:
        cap("INCONSISTENT", "; ".join(warnings), "funds")
    for gid in {action.get("goal_id"), action.get("funding_goal_id")} - {None}:
        b, a = gb.get(gid), ga.get(gid)
        if not a:
            continue
        b_share = b["risky_share"] if b else 0.0
        if a["status"] == "over limit" and (not b or b["status"] == "within limit"):
            cap("INCONSISTENT", f"Goal '{a['label']}' ({a['horizon_years']}y horizon) moves from within to over its "
                                f"risky-asset limit: {b_share:.0%} -> {a['risky_share']:.0%} (limit {a['allowed_max_risky']:.0%}, "
                                f"bound by {a['binding_limit']})", f"goal:{gid}")
        elif a["status"] == "over limit" and a["risky_share"] > b_share + 1e-6:
            cap("INCONSISTENT", f"Goal '{a['label']}' was already over its risky-asset limit and this action increases "
                                f"it further: {b_share:.0%} -> {a['risky_share']:.0%} (limit {a['allowed_max_risky']:.0%})",
                f"goal:{gid}")
        elif a["status"] == "over limit":
            cap("CONSISTENT_WITH_CONDITIONS", f"Goal '{a['label']}' is already over its risky-asset limit; this action does "
                                              f"not increase it ({b_share:.0%} -> {a['risky_share']:.0%}, limit "
                                              f"{a['allowed_max_risky']:.0%}) but the pre-existing gap remains", f"goal:{gid}")
    for c in checks:
        if not c["passed"] and not c["blocking"]:
            if c["severity"] == "soft" and c["status"].startswith("worsened"):
                cap("CONSISTENT_WITH_CONDITIONS", f"Soft check (preference) worsened: {c['rule']} "
                                                  f"({_f(c['before'])} -> {_f(c['after'])})", f"soft:{c['rule']}")
            else:
                cap("CONSISTENT_WITH_CONDITIONS", f"Pre-existing breach not created by this action: {c['rule']} "
                                                  f"({c['status']}: {_f(c['before'])} -> {_f(c['after'])})", f"pre:{c['rule']}")
    return {"after": after, "warnings": warnings, "constraints": checks, "ceiling": ceiling,
            "ceiling_reasons": reasons, "ceiling_keys": keys, "buckets_before": list(gb.values()), "buckets_after": list(ga.values())}


# diversified fund carrying the same theme as a single security (assumption: closest broad fund in the universe)
THEME_FUND = {"US_TECH": "QQQ", "US": "SPY", "US_ESG": "ESGV", "CA": "XIU.TO"}
TECHY = {"Information Technology", "Communication Services", "Consumer Discretionary"}


def _theme_fund(persona, ticker):
    m = UNIVERSE[ticker]
    if m["diversified"] or m["asset_class"] != "equity":
        return None
    if ticker.endswith(".TO"):
        return THEME_FUND["CA"]
    if persona.get("preferences", {}).get("esg_important"):
        return THEME_FUND["US_ESG"]
    return THEME_FUND["US_TECH"] if m.get("starter_sector") in TECHY else THEME_FUND["US"]


def counterfactuals(persona, holdings, action):
    """Alternative versions of the same idea, each evaluated with the same rules.

    Each variant says whether it CHANGES the verdict, and which of the original issues it fixes,
    which remain and which new ones it creates (matched by rule key, not by text).
    """
    base = evaluate(persona, holdings, action)
    if action.get("action", "buy") != "buy":
        return []
    bkeys = dict(zip(base["ceiling_keys"], base["ceiling_reasons"]))
    out = []

    def add(label, act, ev, kind):
        vkeys = dict(zip(ev["ceiling_keys"], ev["ceiling_reasons"]))
        changed = ev["ceiling"] != base["ceiling"]
        vchecks = {c["rule"]: c for c in ev["constraints"]}
        vgoals = {g["goal_id"]: g for g in ev["buckets_after"]}

        def now(key):
            """The fixed issue, restated with this variant's own numbers."""
            kind, _, ref = key.partition(":")
            if kind == "goal" and ref in vgoals:
                g = vgoals[ref]
                return f"Risk budget of '{g['label']}': {g['risky_share']:.0%}, within its {g['allowed_max_risky']:.0%} limit"
            if ref in vchecks:
                return f"{ref}: {_f(vchecks[ref]['after'])} after this version"
            return bkeys[key]
        out.append({
            "variant": label, "kind": kind, "action": act, "ceiling": ev["ceiling"], "reasons": ev["ceiling_reasons"],
            "base_ceiling": base["ceiling"], "changes_result": changed,
            "direction": ("better" if VERDICTS.index(ev["ceiling"]) < VERDICTS.index(base["ceiling"]) else "worse") if changed else "same",
            "fixes": [now(k) for k in bkeys if k not in vkeys],
            "still": [vkeys[k] for k in vkeys if k in bkeys],
            "new_issues": [vkeys[k] for k in vkeys if k not in bkeys],
        })

    goal = action.get("goal_id")
    # 1. same purchase with new money
    if action.get("funding") not in (None, "new_money"):
        a = {**action, "funding": "new_money", "funding_goal_id": None}
        add("Pay with new money instead", a, evaluate(persona, holdings, a), "funding")

    # 2. swap: fund by trimming the largest single-security position in the destination goal
    stocks = [h for h in holdings if h.get("goal") == goal and not UNIVERSE[h["ticker"]]["diversified"]
              and h["ticker"] != action["ticker"]]
    if stocks:
        top = max(stocks, key=lambda h: h["value_cad"])
        amt = min(float(action["amount_cad"]), top["value_cad"])
        a = {**action, "amount_cad": amt, "funding": top["ticker"], "funding_goal_id": goal}
        add(f"Swap: pay for it by trimming {top['ticker']} (largest single position in this goal)", a,
            evaluate(persona, holdings, a), "swap")

    # 3. same theme through a diversified fund (single stocks only)
    fund = _theme_fund(persona, action["ticker"])
    if fund and fund in UNIVERSE:
        a = {**action, "ticker": fund}
        add(f"Same theme through a diversified fund: {fund} ({UNIVERSE[fund]['name']}) instead of {action['ticker']}", a,
            evaluate(persona, holdings, a), "fund")

    # 4. same purchase for the longest-horizon goal (when this money's goal is short-term)
    gh = {g["id"]: g for g in persona["goals"]}
    longer = [g for g in persona["goals"] if g["id"] != goal and g["horizon_years"] > gh.get(goal, {}).get("horizon_years", 0) + 2]
    if goal in gh and longer:
        g2 = max(longer, key=lambda g: g["horizon_years"])
        a = {**action, "goal_id": g2["id"], "funding": "new_money", "funding_goal_id": None}
        add(f"Same purchase for the '{g2['label']}' goal ({g2['horizon_years']}-year horizon), with new money", a,
            evaluate(persona, holdings, a), "goal")

    # 5. largest amount (same funding) that is no longer INCONSISTENT
    if base["ceiling"] == "INCONSISTENT":
        lo, hi, step = 0.0, float(action["amount_cad"]), 250.0
        while hi - lo > step:
            mid = (lo + hi) / 2
            ev = evaluate(persona, holdings, {**action, "amount_cad": mid})
            lo, hi = (mid, hi) if ev["ceiling"] != "INCONSISTENT" else (lo, mid)
        amt = int(lo // step * step)
        if amt > 0:
            a = {**action, "amount_cad": amt}
            add(f"Smaller amount: ${amt:,} instead of ${float(action['amount_cad']):,.0f}", a,
                evaluate(persona, holdings, a), "amount")

    order = {"better": 0, "worse": 1, "same": 2}
    return sorted(out, key=lambda c: order[c["direction"]])


def enforce(judge_verdict, ceiling):
    """Apply the ceiling: the final verdict can never be more permissive than the rules allow."""
    if judge_verdict == SPECIAL:
        return judge_verdict, False
    if judge_verdict not in VERDICTS:
        return ceiling, True
    if VERDICTS.index(judge_verdict) < VERDICTS.index(ceiling):
        return ceiling, True
    return judge_verdict, False
