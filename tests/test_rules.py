"""Deterministic regression tests: toolbox and governance rules (no LLM, no AWS)."""
import json
from pathlib import Path

import pytest

from src.analytics import apply_action, capacity_for_horizon, exposures, stress_tests
from src.rules import counterfactuals, enforce, evaluate

P = {p.stem: json.loads(p.read_text()) for p in (Path(__file__).parents[1] / "personas").glob("*.json")}


def act(t, amt, goal, funding="new_money", fgoal=None, a="buy"):
    return dict(action=a, ticker=t, amount_cad=amt, goal_id=goal, funding=funding, funding_goal_id=fgoal)


@pytest.mark.parametrize("pid,action,expected", [
    ("maya", act("XSP.TO", 15000, "condo", "CASH.TO", "condo"), "INCONSISTENT"),          # short horizon
    ("maya", act("BTCC-B.TO", 20000, "condo", "CASH.TO", "condo"), "INCONSISTENT"),       # crypto + short horizon
    ("maya", act("XEQT.TO", 3000, "retirement"), "CONSISTENT"),                           # long horizon
    ("maya", act("BTCC-B.TO", 1000, "retirement"), "CONSISTENT"),                         # small crypto sleeve, 38y
    ("robert", act("XSP.TO", 15000, "retirement", "CASH.TO", "emergency"), "INCONSISTENT"),  # breaks emergency fund
    ("robert", act("XSP.TO", 15000, "retirement", "RY.TO", "retirement"), "CONSISTENT_WITH_CONDITIONS"),  # swap: no new risk, old gap remains
    ("robert", act("BTCC-B.TO", 5000, "retirement"), "INCONSISTENT"),                     # excluded asset class
    ("sofia", act("XSP.TO", 15000, "retirement", "CASH.TO", "retirement"), "CONSISTENT"),
    ("sofia", act("ZQQ.TO", 10000, "education", "VBAL.TO", "education"), "INCONSISTENT"),  # 60% -> 80% vs 70% (9y)
    ("robert", act("XSP.TO", 15000, "retirement"), "INCONSISTENT"),                       # worsens an existing over-limit goal
])
def test_rule_ceiling(pid, action, expected):
    assert evaluate(P[pid], P[pid]["holdings"], action)["ceiling"] == expected


def test_capacity_rules_monotonic():
    caps = [capacity_for_horizon(y) for y in (0, 0.5, 2, 4, 8, 15, 40)]
    assert caps == sorted(caps)
    assert capacity_for_horizon(0) == 0.0


def test_apply_action_conserves_value_when_swapping():
    p = P["robert"]
    after, warn = apply_action(p["holdings"], act("XSP.TO", 15000, "retirement", "RY.TO", "retirement"))
    assert not warn
    assert abs(sum(h["value_cad"] for h in after) - sum(h["value_cad"] for h in p["holdings"])) < 1e-6


def test_insufficient_funds_flagged():
    p = P["maya"]
    _, warn = apply_action(p["holdings"], act("XSP.TO", 500000, "retirement", "CASH.TO", "retirement"))
    assert warn


def test_exposures_sum_to_one():
    e = exposures(P["sofia"]["holdings"])
    for k in ("asset_class", "currency", "positions"):
        assert abs(sum(e[k].values()) - 1) < 1e-3
    assert abs(sum(e["equity_geography"].values()) - 1) < 1e-3


def test_hedged_etf_adds_no_currency_risk():
    p = P["robert"]
    after, _ = apply_action(p["holdings"], act("XSP.TO", 15000, "retirement"))
    assert exposures(after)["foreign_currency_share"] <= exposures(p["holdings"])["foreign_currency_share"] + 1e-9


def test_stress_tests_cover_scenarios():
    ids = {s["id"] for s in stress_tests(P["maya"]["holdings"])}
    assert {"equity_crash", "rate_shock", "covid_2020", "rates_2022"} <= ids


def test_counterfactual_swap_offered_for_robert():
    cfs = counterfactuals(P["robert"], P["robert"]["holdings"], act("XSP.TO", 15000, "retirement", "CASH.TO", "emergency"))
    assert any(c["variant"].startswith("Swap") and c["ceiling"] == "CONSISTENT_WITH_CONDITIONS" for c in cfs)


@pytest.mark.parametrize("judge,ceiling,expected,adjusted", [
    ("CONSISTENT", "INCONSISTENT", "INCONSISTENT", True),        # judge can't be more permissive
    ("INCONSISTENT", "CONSISTENT", "INCONSISTENT", False),       # judge can be more cautious
    ("INSUFFICIENT_DATA", "CONSISTENT", "INSUFFICIENT_DATA", False),
    ("garbage", "CONSISTENT_WITH_CONDITIONS", "CONSISTENT_WITH_CONDITIONS", True),
])
def test_enforce_ceiling(judge, ceiling, expected, adjusted):
    assert enforce(judge, ceiling) == (expected, adjusted)
