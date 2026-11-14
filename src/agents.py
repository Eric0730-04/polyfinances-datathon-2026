"""Role agents. Each is an LLM call (Amazon Bedrock) with a narrow objective and a JSON contract.

Agents never compute numbers: they receive toolbox outputs (with provenance) and reason over them.
"""
import json

from src.bedrock import chat_json

COMMON = """You are one agent inside SecondLook, an EDUCATIONAL SIMULATION that helps a self-directed investor
take a second look at an idea before acting. Non-negotiable rules:
- Use ONLY numbers present in the provided data. Never invent prices, returns, probabilities or forecasts.
  When you cite a number, copy it from the data (percentages may be rounded).
- No personalised financial advice, no instruction to buy or sell, no guarantee or prediction of returns.
  Speak about consistency with the investor's own stated goals, horizons and constraints.
- Past performance does not guarantee future results; historical figures describe the past only.
- Constraints are hard limits; preferences only operate inside constraints.
- Risk tolerance (willingness) is not risk capacity (ability, driven by horizon and liquidity needs).
- If data is missing or uncertain, say so explicitly instead of guessing.
Reply with ONLY one valid JSON object matching the requested schema. No markdown."""


def _call(role_prompt, payload, schema, temperature=0.2, max_tokens=2048):
    prompt = (f"{role_prompt}\n\nDATA (JSON):\n{json.dumps(payload, default=str)}\n\n"
              f"Return JSON with this schema:\n{schema}")
    return chat_json(prompt, system=COMMON, temperature=temperature, max_tokens=max_tokens)


# ------------------------------------------------------------------ intake

def intake(request_text, persona, universe_brief):
    role = ("ROLE: Intake agent. Translate the investor's free-text request into one structured action. "
            "Pick the ticker only from the universe list. goal_id = the goal the new position will serve; "
            "funding = 'new_money' or the ticker sold to pay for it (e.g. 'CASH.TO' when they say 'my cash/savings'); "
            "funding_goal_id = the goal whose money is used (e.g. 'condo' if they say 'my condo savings'). "
            "If they pay with cash and do not name a goal for the cash, use the goal that holds that cash. "
            "If the security is not in the universe or the amount is missing, set in_scope=false and explain in ambiguities.")
    payload = {"request": request_text,
               "goals": [{k: g[k] for k in ("id", "label", "horizon_years")} for g in persona["goals"]],
               "holdings": persona["holdings"], "universe": universe_brief}
    schema = ('{"in_scope": bool, "action": "buy"|"sell", "ticker": str, "amount_cad": number, "goal_id": str, '
              '"funding": str, "funding_goal_id": str|null, "investor_rationale": str (their stated reason, verbatim-ish), '
              '"interpretation": str (one sentence), "ambiguities": [str]}')
    return _call(role, payload, schema, temperature=0.0, max_tokens=800)


# ------------------------------------------------------------------ profile

def profile(persona, rule_eval, action):
    role = ("ROLE: Profile agent. Compare the investor's risk TOLERANCE (what they say) with their risk CAPACITY "
            "(what each goal's horizon and liquidity allow), before and after the proposed action. Focus on the goal(s) "
            "touched by the action. Point out any gap between tolerance and capacity in plain language.")
    payload = {"investor": {k: persona[k] for k in ("name", "age", "knowledge_level", "risk_tolerance", "risk_tolerance_note", "goals")},
               "action": action, "goal_buckets_before": rule_eval["buckets_before"],
               "goal_buckets_after": rule_eval["buckets_after"],
               "rule": "max risky share by horizon: <1y 0%, 1-3y 20%, 3-5y 40%, 5-10y 70%, 10y+ 125%; tolerance caps low 40%, medium 70%, high 125%; "
                       "risky share counts each crypto dollar as 3 risk units (volatility about 3x equities), so it can exceed 100%"}
    schema = ('{"tolerance_vs_capacity": str, "findings": [{"goal_id": str, "finding": str, "severity": "info"|"warning"|"critical"}], '
              '"question_for_investor": str}')
    return _call(role, payload, schema)


# ------------------------------------------------------------------ market analyst

def analyst(action, sec_metrics, exp_before, exp_after, risk_before, risk_after, stress_before, stress_after, provenance):
    role = ("ROLE: Market analyst agent. Describe what the action changes in the portfolio using only the numbers given: "
            "security risk profile, asset class, equity geography, sector concentration, currency exposure, historical "
            "portfolio volatility/drawdown and stress tests before vs after. Say whether diversification improves. "
            "Remember diversification means varied exposures (geography, sector, currency, asset class), not more line items.")
    payload = {"action": action, "security": sec_metrics, "exposures_before": exp_before, "exposures_after": exp_after,
               "portfolio_risk_before": risk_before, "portfolio_risk_after": risk_after,
               "stress_before": stress_before, "stress_after": stress_after, "data_provenance": provenance}
    schema = ('{"observations": [{"statement": str, "numbers_used": [str]}], '
              '"diversification_effect": "improves"|"neutral"|"worsens"|"mixed", "diversification_explanation": str, '
              '"data_caveats": [str]}')
    return _call(role, payload, schema, max_tokens=2500)


# ------------------------------------------------------------------ debate

def debater(side, context, opponent=None):
    stance = {"advocate": "Build the strongest HONEST case that the investor's idea is coherent with their profile and goals.",
              "skeptic": "Build the strongest HONEST case that the investor's idea is NOT coherent with their profile, "
                         "goals or constraints, or that a different variant of it would fit better."}[side]
    if opponent is None:
        role = f"ROLE: {side.capitalize()} agent in a structured debate. {stance} Use only evidence in the data."
        schema = '{"position": str, "arguments": [{"claim": str, "evidence": str}], "strongest_point": str}'
        return _call(role, context, schema, temperature=0.4)
    role = (f"ROLE: {side.capitalize()} agent, rebuttal round. {stance} Respond to the opponent's arguments below. "
            "Concede points that the evidence supports. Be honest: a concession is better than a weak rebuttal.")
    schema = '{"rebuttals": [{"to_claim": str, "response": str}], "concessions": [str], "updated_position": str}'
    return _call(role, {**context, "opponent_arguments": opponent}, schema, temperature=0.4)


# ------------------------------------------------------------------ guardian

def guardian(persona, rule_eval, action):
    role = ("ROLE: Constraint guardian agent. The hard-constraint checks below were computed deterministically and are "
            "authoritative. Summarise them, and check whether any investor PREFERENCE conflicts with a constraint or with "
            "goal capacity (preferences never override constraints). Flag whether the request itself could amount to "
            "speculation with money that has a short horizon.")
    payload = {"constraints_declared": persona.get("constraints"), "preferences": persona.get("preferences"),
               "constraint_checks": rule_eval["constraints"], "rule_ceiling": rule_eval["ceiling"],
               "ceiling_reasons": rule_eval["ceiling_reasons"], "action": action, "warnings": rule_eval["warnings"]}
    schema = ('{"hard_constraint_summary": str, "preference_conflicts": [str], "governance_flags": [str]}')
    return _call(role, payload, schema)


# ------------------------------------------------------------------ judge / explainer

def judge(persona, action, bundle):
    style = {"novice": "Write for a beginner: short sentences, define any jargon in a few words, use one concrete dollar example.",
             "intermediate": "Write for an investor who knows the basics (ETFs, diversification): clear, brief, light jargon.",
             "sophisticated": "Write for an experienced investor: concise, precise, you may use standard terms."}.get(
        persona["knowledge_level"], "Write clearly for a non-specialist.")
    role = ("ROLE: Judge and explainer agent. Weigh the profile findings, market analysis, the advocate/skeptic debate, the "
            "guardian's review, and the computed counterfactual variants. Decide whether the investor's OWN idea, as proposed, "
            "is consistent with their stated goals, horizons and constraints. The rule_ceiling is the most permissive verdict "
            "allowed by deterministic rules: you may be equally or more cautious, never more permissive. "
            "Explain clearly, separate facts (from market data), assumptions (our rules and approximations) and fictional "
            "elements (the persona). State the conditions under which your conclusion would no longer hold. "
            "Describe counterfactual variants as information, not as a recommendation to act. " + style)
    schema = ('{"verdict": "CONSISTENT"|"CONSISTENT_WITH_CONDITIONS"|"INCONSISTENT"|"INSUFFICIENT_DATA", '
              '"confidence": "low"|"medium"|"high", "headline": str (max 20 words), '
              '"plain_summary": str (3-5 sentences, adapted to the reader), '
              '"key_reasons": [str], "debate_takeaway": str, '
              '"no_longer_valid_if": [str] (concrete facts about THIS investor or market that, if different, would FLIP '
              'this verdict, e.g. a longer horizon for the goal, a different funding source; never conditions that would only '
              'reinforce it), '
              '"variants": [{"variant": str (copy from counterfactuals), "rule_result": str (copy its computed ceiling), '
              '"comment": str}] (ONLY the computed counterfactuals, in the same order; empty list if none), '
              '"facts": [str], "assumptions": [str], "fictional": [str], "limits": [str]}')
    return _call(role, bundle, schema, temperature=0.1, max_tokens=3000)
