"""Deterministic toolbox: every number shown to the user is computed here, never by an LLM.

Each result carries provenance (source, data window, assumption flags).
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.universe import FX_TICKER, GEO_LABELS, UNIVERSE

MARKET_DIR = Path(__file__).resolve().parents[1] / "data" / "market"
RISKY = {"equity", "crypto"}

# ---------------------------------------------------------------- market data


@lru_cache(maxsize=1)
def load_market():
    px = pd.read_csv(MARKET_DIR / "prices.csv", index_col="date", parse_dates=True).sort_index()
    manifest = json.loads((MARKET_DIR / "manifest.json").read_text())
    # convert USD-quoted securities to CAD
    fx = px[FX_TICKER].ffill()
    for t, m in manifest["tickers"].items():
        if m.get("currency") == "USD":
            px[t] = px[t] * fx
    px = px.drop(columns=[FX_TICKER])
    # weekly (Friday) closes avoid TSX/NYSE holiday mismatches
    weekly = px.resample("W-FRI").last().ffill(limit=2)
    # label each week by its last real trading date (not the future Friday bin edge)
    weekly.index = pd.DatetimeIndex(px.index.to_series().resample("W-FRI").last().values)
    return px, weekly, manifest


def provenance():
    _, weekly, manifest = load_market()
    return {
        "source": manifest["source"],
        "fetched_at_utc": manifest["fetched_at_utc"],
        "price_field": manifest["price_field"],
        "last_price_date": str(weekly.index.max().date()),
        "conversion": "USD-quoted prices converted to CAD with Yahoo CAD=X daily rate",
        "frequency": "weekly (Friday) closes for risk metrics",
    }


def security_metrics(ticker: str, years: int = 5) -> dict:
    _, weekly, manifest = load_market()
    s = weekly[ticker].dropna()
    s5 = s[s.index >= s.index.max() - pd.DateOffset(years=years)]
    r = s5.pct_change().dropna()
    dd = s / s.cummax() - 1
    roll12 = s.pct_change(52).dropna()
    yrs = (s5.index[-1] - s5.index[0]).days / 365.25
    meta = UNIVERSE[ticker]
    return {
        "ticker": ticker,
        "name": meta["name"],
        "asset_class": meta["asset_class"],
        "annual_volatility": round(float(r.std() * np.sqrt(52)), 4),
        "annualised_return": round(float((s5.iloc[-1] / s5.iloc[0]) ** (1 / yrs) - 1), 4),
        "max_drawdown": round(float(dd.min()), 4),
        "max_drawdown_date": str(dd.idxmin().date()),
        "worst_12m_return": round(float(roll12.min()), 4),
        "metrics_window": f"{s5.index[0].date()} to {s5.index[-1].date()}",
        "drawdown_window": f"{s.index[0].date()} to {s.index[-1].date()}",
        "mer": meta.get("mer"),
        "sectors": manifest["tickers"][ticker].get("sectors"),
        "note": meta.get("note"),
        "lookthrough_source": meta.get("source", "issuer description"),
    }


# ---------------------------------------------------------------- portfolio


def _mix(ticker):
    m = UNIVERSE[ticker]
    return m.get("asset_mix") or {m["asset_class"]: 1.0}


def total_value(holdings):
    return sum(h["value_cad"] for h in holdings)


def exposures(holdings: list[dict]) -> dict:
    """Asset class / geography / currency / sector / position weights (fractions of total)."""
    _, _, manifest = load_market()
    tot = total_value(holdings)
    ac, geo, cur, sec, pos = {}, {}, {}, {}, {}
    eq_val = 0.0
    for h in holdings:
        t, v = h["ticker"], h["value_cad"]
        w = v / tot
        pos[t] = pos.get(t, 0) + w
        meta = UNIVERSE[t]
        for k, x in _mix(t).items():
            ac[k] = ac.get(k, 0) + w * x
        eq_share = _mix(t).get("equity", 0)
        if eq_share:
            for k, x in meta["geography"].items():
                geo[k] = geo.get(k, 0) + w * eq_share * x
            sectors = manifest["tickers"][t].get("sectors") or {"unknown": 1.0}
            ssum = sum(sectors.values())
            for k, x in sectors.items():
                sec[k] = sec.get(k, 0) + w * eq_share * x / ssum
            eq_val += w * eq_share
        for k, x in meta["currency"].items():
            cur[k] = cur.get(k, 0) + w * x
    r = lambda d: {k: round(v, 4) for k, v in sorted(d.items(), key=lambda kv: -kv[1])}  # noqa: E731
    # equity geography/sector are expressed as share of the equity sleeve
    geo_eq = {GEO_LABELS.get(k, k): v / eq_val for k, v in geo.items()} if eq_val else {}
    sec_eq = {k: v / eq_val for k, v in sec.items()} if eq_val else {}
    top_t = max(pos, key=pos.get)
    return {
        "total_value_cad": round(tot, 2),
        "asset_class": r(ac),
        "equity_geography": r(geo_eq),
        "equity_sectors": r(sec_eq),
        "currency": r(cur),
        "positions": r(pos),
        "largest_position": {"ticker": top_t, "weight": round(pos[top_t], 4),
                             "is_single_stock": UNIVERSE[top_t].get("mer") is None},
        "risky_share": round(sum(v for k, v in ac.items() if k in RISKY), 4),
        "foreign_currency_share": round(1 - cur.get("CAD", 0), 4),
    }


def portfolio_risk(holdings: list[dict], years: int = 5) -> dict:
    """Historical risk of the current weights held constant (rebalanced weekly)."""
    _, weekly, _ = load_market()
    tot = total_value(holdings)
    w = pd.Series({})
    for h in holdings:
        w[h["ticker"]] = w.get(h["ticker"], 0) + h["value_cad"] / tot
    px = weekly[list(w.index)]
    px = px[px.index >= px.index.max() - pd.DateOffset(years=years)]
    rets = px.pct_change().iloc[1:]
    avail = rets.notna()
    # securities with shorter history: renormalise weights over available ones (documented)
    wr = (rets.fillna(0) * w).sum(axis=1) / (avail * w).sum(axis=1)
    nav = (1 + wr).cumprod()
    dd = nav / nav.cummax() - 1
    roll12 = nav.pct_change(52).dropna()
    return {
        "annual_volatility": round(float(wr.std() * np.sqrt(52)), 4),
        "max_drawdown": round(float(dd.min()), 4),
        "max_drawdown_date": str(dd.idxmin().date()),
        "worst_12m_return": round(float(roll12.min()), 4) if len(roll12) else None,
        "window": f"{rets.index[0].date()} to {rets.index[-1].date()}",
        "method": "constant weights, weekly rebalanced, CAD terms; past behaviour, not a forecast",
    }


# ---------------------------------------------------------------- actions


def apply_action(holdings: list[dict], action: dict) -> tuple[list[dict], list[str]]:
    """Simulate an action (no real transaction). Returns (new holdings, warnings).

    action: {action: buy|sell, ticker, amount_cad, goal_id (goal the position serves),
             funding: "new_money" | ticker sold to pay, funding_goal_id (goal the money comes from)}
    """
    h = copy.deepcopy(holdings)
    warnings = []
    t, amt = action["ticker"], float(action["amount_cad"])
    goal = action.get("goal_id")
    fgoal = action.get("funding_goal_id") or goal
    buy = action.get("action", "buy") == "buy"

    def change(ticker, delta, goal_id):
        rows = [x for x in h if x["ticker"] == ticker and x.get("goal") == goal_id]
        if delta >= 0:
            if rows:
                rows[0]["value_cad"] += delta
            else:
                h.append({"ticker": ticker, "value_cad": delta, "goal": goal_id})
            return
        need = -delta
        rows = rows or [x for x in h if x["ticker"] == ticker]  # fall back to any goal
        for x in rows:
            take = min(need, x["value_cad"])
            x["value_cad"] -= take
            need -= take
        if need > 0.5:
            warnings.append(f"Not enough {ticker} to fund ${-delta:,.0f}: short by ${need:,.0f}")

    if buy:
        change(t, amt, goal)
        funding = action.get("funding") or "new_money"
        if funding != "new_money":
            change(funding, -amt, fgoal)
    else:
        change(t, -amt, goal)
        dest = action.get("funding") or "CASH.TO"  # proceeds go to cash by default
        change(dest, amt, fgoal)
    return [x for x in h if x["value_cad"] > 0.5], warnings


# ---------------------------------------------------------------- stress tests

HYPOTHETICAL = [
    dict(id="equity_crash", label="Severe equity bear market",
         shocks={"equity": -0.35, "fixed_income": 0.03, "cash": 0.0, "crypto": -0.60},
         basis="Assumption, sized near the 2008-09 S&P/TSX peak-to-trough (about -45%), rounded down"),
    dict(id="rate_shock", label="Rapid interest-rate rise",
         shocks={"equity": -0.12, "fixed_income": -0.10, "cash": 0.0, "crypto": -0.30},
         basis="Assumption, sized near 2022 (Canadian universe bonds about -12%)"),
    dict(id="cad_up", label="CAD strengthens 10% vs USD and others",
         currency_shocks={"USD": -0.10, "OTHER": -0.07},
         basis="Assumption: translation loss on unhedged foreign holdings"),
    dict(id="canada_down", label="Canada-specific downturn",
         geo_shocks={"CA": -0.25, "US": -0.05, "INTL_DEV": -0.05, "EM": -0.05},
         basis="Assumption: domestic shock (banks/energy) with mild global spillover"),
    dict(id="crypto_winter", label="Crypto winter",
         shocks={"crypto": -0.75},
         basis="Assumption, near the 2021-22 bitcoin drawdown (about -75%)"),
]

HISTORICAL = [
    dict(id="covid_2020", label="COVID crash (Feb 19 - Mar 23, 2020)", start="2020-02-19", end="2020-03-23"),
    dict(id="rates_2022", label="2022 rate shock (Jan 3 - Oct 12, 2022)", start="2022-01-03", end="2022-10-12"),
]


def stress_tests(holdings: list[dict]) -> list[dict]:
    px, _, _ = load_market()
    tot = total_value(holdings)
    out = []
    for sc in HYPOTHETICAL:
        loss = 0.0
        for h in holdings:
            m, v = UNIVERSE[h["ticker"]], h["value_cad"]
            for ac, x in _mix(h["ticker"]).items():
                loss += v * x * sc.get("shocks", {}).get(ac, 0)
            for c, x in m["currency"].items():
                loss += v * x * sc.get("currency_shocks", {}).get(c, 0)
            if "geo_shocks" in sc:
                eq = _mix(h["ticker"]).get("equity", 0)
                for g, x in m["geography"].items():
                    loss += v * eq * x * sc["geo_shocks"].get(g, 0)
        out.append({"id": sc["id"], "label": sc["label"], "type": "hypothetical",
                    "impact_cad": round(loss, 0), "impact_pct": round(loss / tot, 4), "basis": sc["basis"]})
    for sc in HISTORICAL:
        loss, missing = 0.0, []
        for h in holdings:
            s = px[h["ticker"]].dropna()
            a, b = s[: sc["start"]], s[: sc["end"]]
            if not len(a) or a.index[-1] < pd.Timestamp(sc["start"]) - pd.Timedelta(days=7):
                missing.append(h["ticker"])
                continue
            loss += h["value_cad"] * (b.iloc[-1] / a.iloc[-1] - 1)
        out.append({"id": sc["id"], "label": sc["label"], "type": "historical replay",
                    "impact_cad": round(loss, 0), "impact_pct": round(loss / tot, 4),
                    "basis": "Actual price changes of current holdings over the period"
                             + (f"; no history for {missing} (counted as 0)" if missing else "")})
    return out


# ---------------------------------------------------------------- goals: capacity vs tolerance

# max share of a goal's money in risky assets (equity + crypto), by horizon.
# Assumption: rules of thumb consistent with the kickoff's horizon guidance
# (<3y cannot ride out a cycle, 3-10y partial, 10y+ can absorb a cycle).
CAPACITY_RULES = [(1, 0.0), (3, 0.20), (5, 0.40), (10, 0.70), (999, 1.0)]
TOLERANCE_CAP = {"low": 0.40, "medium": 0.70, "high": 1.0}


def capacity_for_horizon(years: float) -> float:
    for limit, cap in CAPACITY_RULES:
        if years < limit:
            return cap
    return 1.0


def goal_buckets(persona: dict, holdings: list[dict]) -> list[dict]:
    tol = persona["risk_tolerance"]
    out = []
    for g in persona["goals"]:
        hs = [h for h in holdings if h.get("goal") == g["id"]]
        val = total_value(hs) if hs else 0.0
        risky = sum(h["value_cad"] * sum(x for ac, x in _mix(h["ticker"]).items() if ac in RISKY) for h in hs)
        cap = capacity_for_horizon(g["horizon_years"])
        allowed = min(cap, TOLERANCE_CAP[tol])
        share = risky / val if val else 0.0
        out.append({
            "goal_id": g["id"], "label": g["label"], "horizon_years": g["horizon_years"],
            "value_cad": round(val, 0), "risky_share": round(share, 4),
            "capacity_max_risky": cap, "tolerance_max_risky": TOLERANCE_CAP[tol],
            "allowed_max_risky": allowed,
            "binding_limit": "capacity (horizon)" if cap < TOLERANCE_CAP[tol] else "tolerance",
            "status": "over limit" if share > allowed + 1e-9 else "within limit",
        })
    return out


# ---------------------------------------------------------------- hard constraints


def check_constraints(persona: dict, before: list[dict], after: list[dict]) -> list[dict]:
    c = persona.get("constraints", {})
    eb, ea = exposures(before), exposures(after)
    checks = []

    def add(rule, ok, b, a, detail, higher_is_better=False):
        if ok:
            status = "pass"
        elif (a > b) if higher_is_better else (a < b):
            status = "pre-existing breach, reduced by this action"
        elif a == b:
            status = "pre-existing breach, unchanged"
        else:
            status = "BREACH created or worsened by this action"
        checks.append({"rule": rule, "passed": bool(ok), "status": status, "before": b, "after": a,
                       "detail": detail, "severity": "hard",
                       "blocking": status.startswith("BREACH")})

    if "max_single_position_pct" in c:
        lim = c["max_single_position_pct"] / 100
        single = {t: w for t, w in ea["positions"].items() if UNIVERSE[t].get("mer") is None or UNIVERSE[t]["asset_class"] == "crypto"}
        worst = max(single.items(), key=lambda kv: kv[1]) if single else (None, 0)
        sb = {t: w for t, w in eb["positions"].items() if UNIVERSE[t].get("mer") is None or UNIVERSE[t]["asset_class"] == "crypto"}
        add(f"No single stock or crypto position above {c['max_single_position_pct']}%",
            worst[1] <= lim + 1e-9, round(max(sb.values(), default=0), 4), round(worst[1], 4),
            f"largest after: {worst[0]}")
    if "min_liquid_cad" in c:
        liq = lambda hs: sum(h["value_cad"] for h in hs if UNIVERSE[h["ticker"]]["asset_class"] == "cash")  # noqa: E731
        add(f"Keep at least ${c['min_liquid_cad']:,} in cash (emergency fund)",
            liq(after) >= c["min_liquid_cad"], round(liq(before)), round(liq(after)), "cash-class holdings only",
            higher_is_better=True)
    for ac in c.get("excluded_asset_classes", []):
        add(f"No {ac} holdings", ea["asset_class"].get(ac, 0) == 0,
            eb["asset_class"].get(ac, 0), ea["asset_class"].get(ac, 0), "investor-declared exclusion")
    if "max_foreign_currency_pct" in c:
        lim = c["max_foreign_currency_pct"] / 100
        add(f"Foreign-currency exposure at most {c['max_foreign_currency_pct']}%",
            ea["foreign_currency_share"] <= lim + 1e-9, eb["foreign_currency_share"], ea["foreign_currency_share"],
            "after hedging")
    if "max_sector_pct" in c:
        lim = c["max_sector_pct"] / 100
        top_b = max(eb["equity_sectors"].values(), default=0)
        k, v = max(ea["equity_sectors"].items(), key=lambda kv: kv[1]) if ea["equity_sectors"] else ("-", 0)
        add(f"No sector above {c['max_sector_pct']}% of equities", v <= lim + 1e-9, round(top_b, 4), round(v, 4),
            f"largest after: {k}")
    return checks
