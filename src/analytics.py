"""Deterministic toolbox: every number shown to the user is computed here, never by an LLM.

Data: the official AlphaForge starter pack (data/starter) + documented supplements (data/supplemental).
Each result carries provenance (source, window, method, assumption flags).
"""
from __future__ import annotations

import copy
from functools import lru_cache

import numpy as np
import pandas as pd

from src.universe import CASH, GEO_LABELS, STARTER, UNIVERSE, etf_sectors

REFERENCE = "SPY"  # risk unit = volatility of SPY in CAD terms
LIQUID = {"cash", "cash_equivalent"}
CPI_PUBLICATION_LAG_DAYS = 50  # monthly CPI dated to reference month; assume available ~50 days after month start

# ---------------------------------------------------------------- market data


@lru_cache(maxsize=1)
def load_market():
    """Returns (daily CAD prices on a union calendar, weekly CAD prices, metadata).

    - adj_close (splits + dividends) for total-return series
    - USD prices converted with Bank of Canada USD/CAD, carried forward over Canadian holidays
    - calendars aligned by forward-filling at most 4 days (TSX/US holidays, weekends for non-crypto)
    - CASH accrues the Bank of Canada overnight target (V39079) daily (assumption for a HISA)
    """
    p = pd.read_csv(STARTER / "prices_daily.csv", parse_dates=["date"])
    extra = STARTER.parent / "supplemental" / "prices_extra.csv"
    if extra.exists():  # supplemental assets: same source, window and format as the starter pack
        p = pd.concat([p, pd.read_csv(extra, parse_dates=["date"])], ignore_index=True)
    px = p.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    cal = pd.date_range(px.index.min(), px.index.max(), freq="D")
    px = px.reindex(cal)
    fx = pd.read_csv(STARTER / "fx_usdcad_daily.csv", parse_dates=["date"]).set_index("date")["usdcad"]
    fx = fx.reindex(cal).ffill().bfill()
    ccy = p.groupby("ticker")["currency"].first()
    for t in px.columns:
        if ccy[t] == "USD":
            px[t] = px[t] * fx
    px = px.ffill(limit=4)
    macro = load_macro()
    on = macro[macro.series_id == "V39079"].set_index("date")["value"].reindex(cal).ffill().bfill()
    px[CASH] = (1 + on / 100 / 365).cumprod()
    weekly = px.resample("W-FRI").last()
    weekly.index = pd.DatetimeIndex(px.index.to_series().resample("W-FRI").last().values)
    meta = {"first_date": str(px.index.min().date()), "last_date": str(px.index.max().date()), "listing_currency": ccy.to_dict()}
    return px, weekly, meta


@lru_cache(maxsize=1)
def load_macro():
    return pd.read_csv(STARTER / "macro_rates.csv", parse_dates=["date"])


def provenance():
    _, _, meta = load_market()
    return {
        "prices": "AlphaForge starter pack (31 assets) + 19 supplemental assets, same source and window: Yahoo Finance via yfinance, adj_close (splits + dividends)",
        "fx": "Bank of Canada Valet FXUSDCAD, carried forward over Canadian holidays",
        "macro": "Bank of Canada Valet and FRED (starter pack macro_rates.csv)",
        "etf_sectors": f"Yahoo fund sector breakdown, fetched {etf_sectors().get('fetched_at_utc', 'n/a')} (supplemental)",
        "esg_screen": "SEC EDGAR Form N-PORT, Vanguard ESG U.S. Stock ETF holdings as of 2026-05-31 (filed 2026-07-29)",
        "fundamentals": "Yahoo quote summary via yfinance, snapshot (context only)",
        "window": f"{meta['first_date']} to {meta['last_date']}",
        "currency": "all values in CAD",
        "frequency": "weekly (Friday) closes for risk metrics; calendars aligned by carrying prices forward up to 4 days",
        "cash": "CASH accrues the Bank of Canada overnight target rate (assumption for a high-interest savings account)",
    }


@lru_cache(maxsize=1)
def risk_units() -> dict:
    """Equity-equivalent risk per dollar: asset volatility / SPY volatility (weekly, CAD, full window)."""
    _, weekly, _ = load_market()
    vol = weekly.pct_change().std() * np.sqrt(52)
    ref = vol[REFERENCE]
    return {t: round(float(vol[t] / ref), 3) for t in weekly.columns}


def security_metrics(ticker: str) -> dict:
    _, weekly, _ = load_market()
    s = weekly[ticker].dropna()
    r = s.pct_change().dropna()
    dd = s / s.cummax() - 1
    roll12 = s.pct_change(52).dropna()
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    m = UNIVERSE[ticker]
    return {
        "ticker": ticker, "name": m["name"], "asset_class": m["asset_class"],
        "listing_currency": m["listing_currency"], "sector": m.get("starter_sector"),
        "annual_volatility": round(float(r.std() * np.sqrt(52)), 4),
        "annualised_return": round(float((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1), 4),
        "max_drawdown": round(float(dd.min()), 4),
        "max_drawdown_date": str(dd.idxmin().date()),
        "worst_12m_return": round(float(roll12.min()), 4) if len(roll12) else None,
        "risk_units_vs_spy": risk_units()[ticker],
        "window": f"{s.index[0].date()} to {s.index[-1].date()}",
        "terms": "CAD, total return (adj_close); historical only, not a forecast",
        "diversified_fund": m["diversified"], "note": m.get("note"),
        "company_snapshot": ({k: v for k, v in m["fundamentals"].items() if k != "business_summary"}
                             if m.get("fundamentals") else None),
        "company_snapshot_source": "Yahoo quote summary via yfinance, snapshot (supplemental)" if m.get("fundamentals") else None,
        "esg_screen": m.get("esg_screen"),
    }


def macro_context(asof: str | None = None) -> dict:
    """Latest macro values that were actually available at `asof` (publication lag respected for CPI)."""
    m = load_macro()
    asof = pd.Timestamp(asof or load_market()[2]["last_date"])
    out = {}
    for sid, label in [("V39079", "Bank of Canada overnight target (%)"), ("BD.CDN.2YR.DQ.YLD", "Canada 2y yield (%)"),
                       ("BD.CDN.10YR.DQ.YLD", "Canada 10y yield (%)"), ("DFF", "US effective fed funds (%)"),
                       ("DGS10", "US 10y Treasury (%)")]:
        s = m[(m.series_id == sid) & (m.date <= asof)].sort_values("date")
        if len(s):
            out[sid] = {"label": label, "value": float(s.value.iloc[-1]), "date": str(s.date.iloc[-1].date())}
    cpi = m[(m.series_id == "STATIC_TOTALCPICHANGE") & (m.date + pd.Timedelta(days=CPI_PUBLICATION_LAG_DAYS) <= asof)]
    if len(cpi):
        c = cpi.sort_values("date").iloc[-1]
        out["CA_CPI_YOY"] = {"label": "Canada CPI, % y/y", "value": float(c.value),
                             "date": f"reference month {c.date:%Y-%m}",
                             "note": f"only months published by {asof.date()} (assumed {CPI_PUBLICATION_LAG_DAYS}-day lag)"}
    if "V39079" in out and "CA_CPI_YOY" in out:
        out["REAL_CASH_YIELD"] = {"label": "Real cash yield ≈ overnight rate − CPI (%)",
                                  "value": round(out["V39079"]["value"] - out["CA_CPI_YOY"]["value"], 2),
                                  "date": str(asof.date()), "note": "assumption: HISA ≈ overnight rate"}
    return {"asof": str(asof.date()), "series": out}


# ---------------------------------------------------------------- portfolio


def total_value(holdings):
    return sum(h["value_cad"] for h in holdings)


def _w(holdings):
    tot = total_value(holdings)
    w = {}
    for h in holdings:
        w[h["ticker"]] = w.get(h["ticker"], 0) + h["value_cad"] / tot
    return w


def exposures(holdings: list[dict]) -> dict:
    w = _w(holdings)
    ru = risk_units()
    ac, geo, cur, sec = {}, {}, {}, {}
    eq = 0.0
    for t, x in w.items():
        m = UNIVERSE[t]
        ac[m["asset_class"]] = ac.get(m["asset_class"], 0) + x
        for k, y in m["currency"].items():
            cur[k] = cur.get(k, 0) + x * y
        if m["asset_class"] == "equity":
            eq += x
            for k, y in m["geography"].items():
                geo[k] = geo.get(k, 0) + x * y
            for k, y in m["sectors"].items():
                sec[k] = sec.get(k, 0) + x * y
    r = lambda d, s=1.0: {k: round(v / s, 4) for k, v in sorted(d.items(), key=lambda kv: -kv[1]) if v > 1e-6}  # noqa: E731
    conc = {t: x for t, x in w.items() if not UNIVERSE[t]["diversified"]}
    top = max(conc, key=conc.get) if conc else None
    return {
        "total_value_cad": round(total_value(holdings), 2),
        "asset_class": r(ac),
        "equity_geography": {GEO_LABELS.get(k, k): v for k, v in r(geo, eq).items()} if eq else {},
        "equity_sectors": r(sec, eq) if eq else {},
        "currency": r(cur),
        "positions": r(w),
        "largest_concentrated_position": {"ticker": top, "weight": round(conc[top], 4)} if top else None,
        "crypto_share": round(ac.get("crypto", 0), 4),
        "liquid_share": round(sum(v for k, v in ac.items() if k in LIQUID), 4),
        "foreign_currency_share": round(1 - cur.get("CAD", 0), 4),
        "energy_lookthrough_share_of_portfolio": round(sec.get("Energy", 0), 4),
        "equity_equivalent_risk": round(sum(x * ru[t] for t, x in w.items()), 4),
    }


def portfolio_risk(holdings: list[dict]) -> dict:
    """Historical risk of current weights held constant (weekly rebalanced), CAD, full starter window."""
    _, weekly, _ = load_market()
    w = pd.Series(_w(holdings))
    rets = weekly[list(w.index)].pct_change().iloc[1:]
    avail = rets.notna()
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
        "method": "constant weights, weekly rebalanced, CAD total return; describes the past, not a forecast",
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
        change(action.get("funding") or CASH, amt, fgoal)  # proceeds to cash by default
    return [x for x in h if x["value_cad"] > 0.5], warnings


# ---------------------------------------------------------------- stress tests

HYPOTHETICAL = [
    dict(id="equity_crash", label="Severe equity bear market",
         shocks={"equity": -0.35, "fixed_income": 0.02, "crypto": -0.60, "commodity": 0.05},
         basis="Assumption, near the 2008-09 S&P 500 peak-to-trough (about -50%) scaled to a severe but not extreme case"),
    dict(id="rate_shock", label="Stocks and bonds fall together (rate shock)",
         shocks={"equity": -0.15, "fixed_income": -0.10, "crypto": -0.40, "commodity": -0.05},
         ticker_shocks={"TLT": -0.25, "ZST.TO": 0.0},
         basis="Assumption, sized near 2022 (see historical replay); long Treasuries hit harder, ultra-short spared"),
    dict(id="tech_selloff", label="Tech / AI sell-off",
         sector_shocks={"Information Technology": -0.35, "Communication Services": -0.25, "Consumer Discretionary": -0.20},
         other_equity=-0.08, shocks={"crypto": -0.40},
         basis="Assumption: concentrated drawdown in growth/tech sectors with spillover"),
    dict(id="canada_down", label="Canada-specific downturn",
         geo_shocks={"CA": -0.25, "US": -0.05},
         basis="Assumption: domestic shock (banks/energy) with mild spillover"),
    dict(id="cad_up", label="CAD strengthens 10% vs USD",
         currency_shocks={"USD": -0.10},
         basis="Assumption: translation loss on USD assets for a CAD investor"),
    dict(id="crypto_winter", label="Crypto winter", shocks={"crypto": -0.75},
         basis="Assumption, near the 2021-22 bitcoin drawdown"),
]


def _historical_scenarios():
    px, _, _ = load_market()
    out = [dict(id="stocks_bonds_2022", label="2022: stocks and bonds fell together", start="2022-01-03", end="2022-10-12"),
           dict(id="crypto_2022", label="2021-22 crypto winter", start="2021-11-12", end="2022-11-21")]
    for t, lab in (("SPY", "S&P 500"), ("QQQ", "Nasdaq-100")):
        s = px[t].dropna()
        dd = s / s.cummax() - 1
        end = dd.idxmin()
        start = s[:end].idxmax()
        if all(abs((pd.Timestamp(o["start"]) - start).days) > 45 for o in out):
            out.append(dict(id=f"worst_{t}", label=f"Worst {lab} drawdown in sample ({start.date()} to {end.date()})",
                            start=str(start.date()), end=str(end.date())))
    return out


def stress_tests(holdings: list[dict]) -> list[dict]:
    px, _, _ = load_market()
    tot = total_value(holdings)
    out = []
    for sc in HYPOTHETICAL:
        loss = 0.0
        for h in holdings:
            m, v = UNIVERSE[h["ticker"]], h["value_cad"]
            ac = m["asset_class"]
            if h["ticker"] in sc.get("ticker_shocks", {}):
                loss += v * sc["ticker_shocks"][h["ticker"]]
            elif ac == "equity" and "sector_shocks" in sc:
                loss += v * sum(y * sc["sector_shocks"].get(k, sc.get("other_equity", 0)) for k, y in m["sectors"].items())
            else:
                loss += v * sc.get("shocks", {}).get(ac, 0)
            for c, y in m["currency"].items():
                loss += v * y * sc.get("currency_shocks", {}).get(c, 0)
            if ac == "equity" and "geo_shocks" in sc:
                loss += v * sum(y * sc["geo_shocks"].get(g, 0) for g, y in m["geography"].items())
        out.append({"id": sc["id"], "label": sc["label"], "type": "hypothetical", "impact_cad": round(loss, 0),
                    "impact_pct": round(loss / tot, 4), "basis": sc["basis"]})
    for sc in _historical_scenarios():
        loss = 0.0
        for h in holdings:
            s = px[h["ticker"]].dropna()
            a, b = s[: sc["start"]], s[: sc["end"]]
            if len(a) and len(b):
                loss += h["value_cad"] * (b.iloc[-1] / a.iloc[-1] - 1)
        out.append({"id": sc["id"], "label": sc["label"], "type": "historical replay", "impact_cad": round(loss, 0),
                    "impact_pct": round(loss / tot, 4),
                    "basis": f"Actual CAD total-return change of current holdings, {sc['start']} to {sc['end']}"})
    return out


# ---------------------------------------------------------------- goals: capacity vs tolerance

# Max equity-equivalent risk of a goal's money (SPY = 100%), by horizon. Assumption, consistent with the kickoff
# (<3y cannot ride out a cycle, 3-10y partially, 10y+ can). Derived from a classic max-equity share E per horizon,
# with the rest in core bonds (~0.45 risk units, XBB/AGG): limit = E + (1 - E) * 0.45; for <3y the rest is assumed
# in short-term instruments (~0). >100% only for long horizons + high tolerance (room for a high-volatility sleeve).
CAPACITY_RULES = [(1, 0.05), (3, 0.20), (5, 0.65), (10, 0.85), (999, 1.50)]
TOLERANCE_CAP = {"low": 0.55, "low_moderate": 0.65, "moderate": 0.85, "high": 1.50}


def capacity_for_horizon(years: float) -> float:
    for limit, cap in CAPACITY_RULES:
        if years < limit:
            return cap
    return CAPACITY_RULES[-1][1]


def goal_buckets(persona: dict, holdings: list[dict]) -> list[dict]:
    tol = persona["risk_tolerance"]
    ru = risk_units()
    out = []
    for g in persona["goals"]:
        hs = [h for h in holdings if h.get("goal") == g["id"]]
        val = total_value(hs) if hs else 0.0
        risk = sum(h["value_cad"] * ru[h["ticker"]] for h in hs)
        cap = capacity_for_horizon(g["horizon_years"])
        allowed = min(cap, TOLERANCE_CAP[tol])
        share = risk / val if val else 0.0
        out.append({
            "goal_id": g["id"], "label": g["label"], "horizon_years": g["horizon_years"],
            "horizon_note": g.get("horizon_note"), "value_cad": round(val, 0), "risky_share": round(share, 4),
            "capacity_max_risky": cap, "tolerance_max_risky": TOLERANCE_CAP[tol], "allowed_max_risky": allowed,
            "binding_limit": ("capacity (horizon) and tolerance" if cap == TOLERANCE_CAP[tol]
                              else "capacity (horizon)" if cap < TOLERANCE_CAP[tol] else "tolerance"),
            "status": "over limit" if share > allowed + 1e-9 else "within limit",
        })
    return out


# ---------------------------------------------------------------- hard constraints & preferences


def check_constraints(persona: dict, before: list[dict], after: list[dict]) -> list[dict]:
    c = persona.get("constraints", {})
    eb, ea = exposures(before), exposures(after)
    checks = []

    def add(rule, ok, b, a, detail, higher_is_better=False, severity="hard", origin="stated"):
        if ok:
            status = "pass"
        elif (a > b) if higher_is_better else (a < b):
            status = "pre-existing breach, reduced by this action"
        elif a == b:
            status = "pre-existing breach, unchanged"
        else:
            status = "BREACH created or worsened by this action" if severity == "hard" else "worsened by this action (soft)"
        checks.append({"rule": rule, "passed": bool(ok), "status": status, "before": b, "after": a, "detail": detail,
                       "severity": severity, "origin": origin, "blocking": status.startswith("BREACH")})

    origin = lambda key: c.get("_origin", {}).get(key, "stated")  # noqa: E731
    if "max_single_position_pct" in c:
        lim = c["max_single_position_pct"] / 100
        lp_b, lp_a = eb["largest_concentrated_position"], ea["largest_concentrated_position"]
        add(f"No single stock / crypto / commodity above {c['max_single_position_pct']}%",
            (lp_a["weight"] if lp_a else 0) <= lim + 1e-9, lp_b["weight"] if lp_b else 0, lp_a["weight"] if lp_a else 0,
            f"largest after: {lp_a['ticker'] if lp_a else '-'}", origin=origin("max_single_position_pct"))
    if "min_liquid_cad" in c:
        liq = lambda hs: round(sum(h["value_cad"] for h in hs if UNIVERSE[h["ticker"]]["asset_class"] in LIQUID))  # noqa: E731
        add(f"Keep at least ${c['min_liquid_cad']:,} in cash or cash-equivalents", liq(after) >= c["min_liquid_cad"],
            liq(before), liq(after), "CASH + ZST.TO", higher_is_better=True, origin=origin("min_liquid_cad"))
    for acl in c.get("excluded_asset_classes", []):
        add(f"No {acl} holdings", ea["asset_class"].get(acl, 0) == 0, eb["asset_class"].get(acl, 0),
            ea["asset_class"].get(acl, 0), "investor-declared exclusion", origin=origin("excluded_asset_classes"))
    if "max_crypto_pct" in c and "crypto" not in c.get("excluded_asset_classes", []):  # a ban supersedes the cap
        add(f"Crypto at most {c['max_crypto_pct']}% of the portfolio", ea["crypto_share"] <= c["max_crypto_pct"] / 100 + 1e-9,
            eb["crypto_share"], ea["crypto_share"], "BTC + ETH", origin=origin("max_crypto_pct"))
    if "max_sector_pct" in c:
        lim = c["max_sector_pct"] / 100
        top_b = max(eb["equity_sectors"].values(), default=0)
        k, v = max(ea["equity_sectors"].items(), key=lambda kv: kv[1]) if ea["equity_sectors"] else ("-", 0)
        add(f"No sector above {c['max_sector_pct']}% of equities (look-through)", v <= lim + 1e-9, round(top_b, 4),
            round(v, 4), f"largest after: {k}", origin=origin("max_sector_pct"))
    if "pref_max_security_risk_units" in c:
        lim = c["pref_max_security_risk_units"]
        ru = risk_units()
        hv = lambda hs: round(sum(h["value_cad"] for h in hs if not UNIVERSE[h["ticker"]]["diversified"]  # noqa: E731
                                  and ru[h["ticker"]] > lim) / total_value(hs), 4)
        add(f"Preference: no more weight in single securities over {lim}x S&P 500 volatility", hv(after) <= hv(before) + 1e-6,
            hv(before), hv(after), "share of portfolio in high-volatility single names", severity="soft",
            origin=origin("pref_max_security_risk_units"))
    if c.get("pref_pass_esg_screen"):
        fail = lambda hs: round(sum(h["value_cad"] for h in hs if UNIVERSE[h["ticker"]].get("esg_screen") == "not held")  # noqa: E731
                                / total_value(hs), 4)
        add("Preference: no more weight in US stocks excluded by the ESGV screen (SEC N-PORT evidence)",
            fail(after) <= fail(before) + 1e-6, fail(before), fail(after),
            "screen excludes fossil fuels, weapons, controversies, etc.; exclusion reason not disclosed", severity="soft",
            origin=origin("pref_pass_esg_screen"))
    if c.get("excluded_sectors"):
        ex = set(c["excluded_sectors"])
        direct = lambda hs: round(sum(h["value_cad"] for h in hs if not UNIVERSE[h["ticker"]]["diversified"]  # noqa: E731
                                      and UNIVERSE[h["ticker"]].get("starter_sector") in ex) / total_value(hs), 4)
        add(f"No direct holdings in excluded sectors ({', '.join(sorted(ex))})", direct(after) == 0, direct(before),
            direct(after), "ESG screen on single securities", origin=origin("excluded_sectors"))
        lt = lambda e: round(sum(v for k, v in e["equity_sectors"].items() if k in ex) *  # noqa: E731
                             e["asset_class"].get("equity", 0), 4)
        add(f"Indirect exposure to excluded sectors via funds (should not increase)", lt(ea) <= lt(eb) + 1e-6,
            lt(eb), lt(ea), "share of total portfolio via ETFs and stocks; fund weights from Yahoo snapshot",
            severity="soft", origin=origin("excluded_sectors"))
    return checks


def esg_view(persona: dict, holdings: list[dict]) -> dict | None:
    """What we can and cannot say about ESG with the available data."""
    prefs = persona.get("preferences", {})
    if not prefs.get("esg_important"):
        return None
    ex = set(persona.get("constraints", {}).get("excluded_sectors", []))
    direct = sorted({h["ticker"] for h in holdings if UNIVERSE[h["ticker"]].get("starter_sector") in ex})
    singles = sorted({h["ticker"] for h in holdings if not UNIVERSE[h["ticker"]]["diversified"]
                      and UNIVERSE[h["ticker"]]["asset_class"] == "equity"})
    screen = {t: UNIVERSE[t].get("esg_screen", "n/a") for t in singles}
    return {"screen": f"Exclude GICS sectors: {', '.join(sorted(ex)) or 'none'} (fossil-fuel proxy, assumption)",
            "direct_holdings_in_excluded_sectors": direct,
            "energy_lookthrough_share_of_portfolio": exposures(holdings)["energy_lookthrough_share_of_portfolio"],
            "esgv_screen_by_holding": screen,
            "esgv_screen_source": "SEC N-PORT, Vanguard ESG U.S. Stock ETF holdings as of 2026-05-31 (filed 2026-07-29)",
            "controversy_status": "PARTIAL: US stocks checked against the ESGV screen (public SEC filing): held = passed, "
                                  "not held = excluded for an undisclosed reason. Canadian stocks are NOT VERIFIED (no "
                                  "public screen in our data); controversies themselves are not scored.",
            "esgv_note": UNIVERSE["ESGV"]["note"]}
