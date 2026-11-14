"""Custom investors: validate a user-built profile into the same shape as the official persona files.

Custom profiles live in the visitor's browser and are sent with each request; the server keeps no state.
Every field is checked so a malformed or hostile profile cannot break the toolbox or the agents.
"""
import re

from src.analytics import TOLERANCE_CAP
from src.universe import UNIVERSE

KNOWLEDGE = ("novice", "intermediate", "sophisticated")
MAX_GOALS, MAX_HOLDINGS = 4, 15
ID_RE = re.compile(r"^custom-[a-z0-9]{4,16}$")


class PersonaError(ValueError):
    """Message is shown to the user as-is."""


def _num(v, lo, hi, what):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise PersonaError(f"{what} must be a number.")
    if not lo <= x <= hi:
        raise PersonaError(f"{what} must be between {lo:,g} and {hi:,g}.")
    return x


def _text(v, what, max_len=60, required=True):
    s = re.sub(r"\s+", " ", str(v or "")).strip()
    if required and not s:
        raise PersonaError(f"{what} is required.")
    return s[:max_len]


def validate(d: dict) -> dict:
    if not isinstance(d, dict):
        raise PersonaError("The investor profile is not valid.")
    pid = str(d.get("id") or "")
    if not ID_RE.match(pid):
        raise PersonaError("The investor profile has an invalid id. Recreate it.")
    name = _text(d.get("name"), "Name", 30)
    age = int(_num(d.get("age"), 18, 100, "Age"))
    tol = d.get("risk_tolerance")
    if tol not in TOLERANCE_CAP:
        raise PersonaError("Pick a risk profile.")
    know = d.get("knowledge_level") if d.get("knowledge_level") in KNOWLEDGE else "intermediate"

    goals_in = d.get("goals") or []
    if not 1 <= len(goals_in) <= MAX_GOALS:
        raise PersonaError(f"Add between 1 and {MAX_GOALS} goals.")
    goals = []
    for i, g in enumerate(goals_in):
        goals.append({"id": f"g{i + 1}", "label": _text(g.get("label"), f"Goal {i + 1} name", 50),
                      "type": "custom", "target_cad": None, "priority": i + 1,
                      "horizon_years": round(_num(g.get("horizon_years"), 0, 60, f"Horizon of goal {i + 1}"), 1)})
    gids = {g["id"] for g in goals}

    hold_in = d.get("holdings") or []
    if not 1 <= len(hold_in) <= MAX_HOLDINGS:
        raise PersonaError(f"Add between 1 and {MAX_HOLDINGS} holdings.")
    holdings = []
    for i, h in enumerate(hold_in):
        t = h.get("ticker")
        if t not in UNIVERSE:
            raise PersonaError(f"Holding {i + 1}: pick an asset from the list.")
        if h.get("goal") not in gids:
            raise PersonaError(f"Holding {i + 1}: pick which goal it belongs to.")
        holdings.append({"ticker": t, "value_cad": round(_num(h.get("value_cad"), 1, 10_000_000, f"Holding {i + 1} amount"), 2),
                         "goal": h["goal"]})

    c_in, c = d.get("constraints") or {}, {}
    if c_in.get("min_liquid_cad") not in (None, ""):
        c["min_liquid_cad"] = round(_num(c_in["min_liquid_cad"], 0, 10_000_000, "Minimum cash"))
    for k, what in (("max_single_position_pct", "Max in one stock"), ("max_crypto_pct", "Max in crypto"),
                    ("max_sector_pct", "Max in one sector")):
        if c_in.get(k) not in (None, ""):
            c[k] = round(_num(c_in[k], 0, 100, what), 1)
    if c_in.get("exclude_fossil_fuels"):
        c["excluded_sectors"] = ["Energy"]
    if c_in.get("avoid_volatile_names"):
        c["pref_max_security_risk_units"] = 2.0
    if c_in.get("exclude_crypto"):
        c["excluded_asset_classes"] = ["crypto"]
        c.pop("max_crypto_pct", None)  # a ban makes the cap redundant
    c["_origin"] = {k: "stated by the user (custom investor)" for k in c}
    esg = bool(c_in.get("exclude_fossil_fuels"))
    if esg:
        c["pref_pass_esg_screen"] = True
        c["_origin"]["pref_pass_esg_screen"] = "derived from the fossil-fuel exclusion (assumption: ESGV screen as proxy)"

    total = sum(h["value_cad"] for h in holdings)
    top = max(holdings, key=lambda h: h["value_cad"])["ticker"]
    long_goal = max(goals, key=lambda g: g["horizon_years"])
    return {
        "id": pid, "name": name, "age": age, "fictional": True, "official_persona": False, "custom": True,
        "summary": f"Custom investor built in SecondLook: {age} years old, {tol.replace('_', '-')} risk, "
                   f"{len(goals)} goal(s), ${total:,.0f} portfolio.",
        "objective": _text(d.get("objective"), "Objective", 120, required=False) or f"{long_goal['label']}",
        "knowledge_level": know, "risk_tolerance": tol,
        "risk_tolerance_note": "Stated by the user when building this custom investor.",
        "goals": goals, "holdings": holdings, "constraints": c,
        "preferences": {"likes": [], "esg_important": esg, "income_needed": False},
        "sample_requests": [
            f"Put $5,000 of new money into SPY for my {long_goal['label'].lower()} goal.",
            f"Move $10,000 from {top} into TSLA.",
            f"Put $3,000 of new money into Bitcoin.",
        ],
    }
