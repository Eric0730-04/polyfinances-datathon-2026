"""Deterministic regression tests: data loading, toolbox and governance rules (no LLM, no AWS)."""
import json
from pathlib import Path

import pytest

from src.analytics import (apply_action, capacity_for_horizon, exposures, load_market, macro_context, risk_units,
                           stress_tests)
from src.rules import counterfactuals, enforce, evaluate
from src.universe import UNIVERSE

P = {p.stem: json.loads(p.read_text()) for p in (Path(__file__).parents[1] / "personas").glob("*.json")}


def act(t, amt, goal, funding="new_money", fgoal=None, a="buy"):
    return dict(action=a, ticker=t, amount_cad=amt, goal_id=goal, funding=funding, funding_goal_id=fgoal)


@pytest.mark.parametrize("pid,action,expected", [
    # Robert: challenge a high-profile request that conflicts with the profile
    ("robert", act("TSLA", 60000, "retirement", "XBB.TO", "retirement"), "INCONSISTENT"),
    ("robert", act("NVDA", 40000, "retirement"), "INCONSISTENT"),
    ("robert", act("TSLA", 10000, "retirement", "XBB.TO", "retirement"), "CONSISTENT_WITH_CONDITIONS"),  # size ok, preference not
    ("robert", act("JNJ", 20000, "retirement", "XBB.TO", "retirement"), "CONSISTENT"),
    # Amira: high risk is not "anything goes"
    ("amira", act("NVDA", 15000, "growth"), "INCONSISTENT"),
    ("amira", act("ETH-USD", 2000, "growth"), "CONSISTENT"),
    ("amira", act("ETH-USD", 6000, "growth"), "INCONSISTENT"),  # crypto cap / risk budget
    ("amira", act("XIU.TO", 10000, "growth"), "CONSISTENT"),
    # Mateo: non-financial criteria
    ("mateo", act("XOM", 10000, "balanced"), "INCONSISTENT"),
    ("mateo", act("SPY", 20000, "balanced", "ESGV", "balanced"), "CONSISTENT_WITH_CONDITIONS"),
    ("mateo", act("ESGV", 10000, "balanced"), "CONSISTENT"),
    ("mateo", act("JNJ", 8000, "balanced"), "CONSISTENT_WITH_CONDITIONS"),  # excluded by ESGV screen (SEC evidence)
    ("mateo", act("MSFT", 2000, "balanced"), "CONSISTENT"),                 # passes ESGV screen
    # Maya: tolerance is not capacity
    ("maya", act("QQQ", 15000, "condo", "ZST.TO", "condo"), "INCONSISTENT"),
    ("maya", act("SPY", 3000, "retirement"), "CONSISTENT"),
    # supplemental assets
    ("amira", act("XEF.TO", 10000, "growth"), "CONSISTENT"),                   # international diversification
    ("amira", act("SOL-USD", 5000, "growth"), "INCONSISTENT"),                 # crypto cap + risk budget
    ("robert", act("PLTR", 20000, "retirement", "XBB.TO", "retirement"), "INCONSISTENT"),
    ("mateo", act("XESG.TO", 10000, "balanced"), "CONSISTENT_WITH_CONDITIONS"),  # "ESG" fund still ~23% Energy
])
def test_rule_ceiling(pid, action, expected):
    assert evaluate(P[pid], P[pid]["holdings"], action)["ceiling"] == expected


def test_personas_start_within_limits():
    for pid, p in P.items():
        ev = evaluate(p, p["holdings"], act("CASH", 1, p["goals"][0]["id"]))
        assert all(c["passed"] for c in ev["constraints"]), pid
        assert all(g["status"] == "within limit" for g in ev["buckets_before"]), pid


def test_all_holdings_in_universe():
    for p in P.values():
        assert all(h["ticker"] in UNIVERSE for h in p["holdings"])


def test_market_data_window_and_currency():
    px, weekly, meta = load_market()
    assert meta["first_date"] == "2021-11-12" and meta["last_date"] == "2026-11-12"
    assert set(UNIVERSE) <= set(px.columns)
    assert weekly.index.max() <= px.index.max()  # no future-dated labels


def test_risk_units_ordering():
    ru = risk_units()
    assert ru["SPY"] == 1.0
    assert ru["CASH"] < ru["ZST.TO"] < ru["XBB.TO"] < ru["SPY"] < ru["NVDA"]
    assert ru["BTC-USD"] > 2.5 and ru["TSLA"] > 2.5


def test_macro_respects_publication_lag():
    cpi = macro_context("2026-11-12")["series"]["CA_CPI_YOY"]
    assert cpi["date"] == "reference month 2026-09"  # October CPI not yet published on Nov 12


def test_capacity_rules_monotonic():
    caps = [capacity_for_horizon(y) for y in (0, 0.5, 2, 4, 8, 15, 40)]
    assert caps == sorted(caps)


def test_apply_action_conserves_value_when_swapping():
    p = P["robert"]
    after, warn = apply_action(p["holdings"], act("JNJ", 20000, "retirement", "XBB.TO", "retirement"))
    assert not warn
    assert abs(sum(h["value_cad"] for h in after) - sum(h["value_cad"] for h in p["holdings"])) < 1e-6


def test_insufficient_funds_flagged():
    _, warn = apply_action(P["maya"]["holdings"], act("SPY", 500000, "retirement", "ZST.TO", "condo"))
    assert warn


def test_exposures_sum_to_one():
    e = exposures(P["mateo"]["holdings"])
    for k in ("asset_class", "currency", "positions"):
        assert abs(sum(e[k].values()) - 1) < 1e-3
    assert abs(sum(e["equity_sectors"].values()) - 1) < 1e-3


def test_esgv_has_no_energy_but_spy_does():
    assert UNIVERSE["ESGV"]["sectors"].get("Energy", 0) == 0
    assert UNIVERSE["SPY"]["sectors"].get("Energy", 0) > 0


def test_stress_tests_cover_scenarios():
    ids = {s["id"] for s in stress_tests(P["amira"]["holdings"])}
    assert {"equity_crash", "rate_shock", "tech_selloff", "stocks_bonds_2022", "crypto_2022"} <= ids


def test_counterfactual_smaller_amount_for_robert_tsla():
    cfs = counterfactuals(P["robert"], P["robert"]["holdings"], act("TSLA", 60000, "retirement", "XBB.TO", "retirement"))
    small = [c for c in cfs if c["variant"].startswith("Smaller")]
    assert small and small[0]["ceiling"] != "INCONSISTENT"


@pytest.mark.parametrize("judge,ceiling,expected,adjusted", [
    ("CONSISTENT", "INCONSISTENT", "INCONSISTENT", True),
    ("INCONSISTENT", "CONSISTENT", "INCONSISTENT", False),
    ("INSUFFICIENT_DATA", "CONSISTENT", "INSUFFICIENT_DATA", False),
    ("garbage", "CONSISTENT_WITH_CONDITIONS", "CONSISTENT_WITH_CONDITIONS", True),
])
def test_enforce_ceiling(judge, ceiling, expected, adjusted):
    assert enforce(judge, ceiling) == (expected, adjusted)


def test_esg_screen_evidence_loaded():
    assert UNIVERSE["XOM"]["esg_screen"] == "not held" and UNIVERSE["AAPL"]["esg_screen"] == "held"
    assert UNIVERSE["RY.TO"]["esg_screen"].startswith("not covered")


def test_supplemental_assets_loaded():
    px, _, _ = load_market()
    extra = ["XEF.TO", "XEC.TO", "XEQT.TO", "VDY.TO", "XESG.TO", "ICLN", "CASH.TO", "PLTR", "META", "AMD", "LLY",
             "BRK-B", "KO", "COST", "BNS.TO", "BCE.TO", "L.TO", "ABX.TO", "SOL-USD"]
    assert all(t in UNIVERSE and UNIVERSE[t]["data_source"] == "supplemental" for t in extra)
    assert all(px[t].first_valid_index().strftime("%Y-%m-%d") == "2021-11-12" for t in extra)
    assert len(UNIVERSE) == 51  # 31 starter + 19 supplemental + synthetic CASH


def test_esg_labelled_fund_is_not_fossil_free():
    assert UNIVERSE["XESG.TO"]["sectors"].get("Energy", 0) > 0.1   # ESG-aware tilt, not an exclusion
    assert UNIVERSE["PLTR"]["esg_screen"] == "not held"
