"""Investable universe = the official AlphaForge starter universe (31 assets) + 19 supplemental assets
(data/supplemental/assets_extra.csv, same source and window) + a synthetic CAD cash line.

Static look-through metadata below (geography, currency exposure, normalised asset class) is OUR
approximation from issuer descriptions, labelled source="assumption" and shown as such in the UI.
"""
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "data" / "starter"
SUPPLEMENTAL = ROOT / "data" / "supplemental"

CASH = "CASH"  # synthetic: CAD cash / high-interest savings, accrues the BoC overnight rate (assumption)

# normalised asset classes; "diversified" = a fund holding many securities (single-position limits don't apply)
CLASS_MAP = {"equity": "equity", "etf_equity": "equity", "etf_bond": "fixed_income",
             "etf_commodity": "commodity", "crypto": "crypto", "etf_cash": "cash_equivalent"}

# Look-through for funds (assumption, from issuer descriptions; rounded)
LOOKTHROUGH = {
    "XIU.TO": dict(geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "SPY": dict(geography={"US": 1.0}, currency={"USD": 1.0}),
    "QQQ": dict(geography={"US": 1.0}, currency={"USD": 1.0}),
    "ESGV": dict(geography={"US": 1.0}, currency={"USD": 1.0},
                 note="ESG-screened: excludes e.g. fossil fuels, weapons, tobacco per issuer methodology"),
    "XBB.TO": dict(geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "ZST.TO": dict(geography={"CA": 1.0}, currency={"CAD": 1.0}, asset_class="cash_equivalent",
                   note="Ultra short-term bonds; treated as cash-equivalent for liquidity checks (assumption)"),
    "AGG": dict(geography={"US": 1.0}, currency={"USD": 1.0}),
    "TLT": dict(geography={"US": 1.0}, currency={"USD": 1.0}, note="Long-duration Treasuries: very rate-sensitive"),
    "GLD": dict(geography={"GLOBAL": 1.0}, currency={"USD": 1.0}, diversified=False),
    "BTC-USD": dict(geography={"GLOBAL": 1.0}, currency={"USD": 1.0}),
    "ETH-USD": dict(geography={"GLOBAL": 1.0}, currency={"USD": 1.0}),
    # ---- supplemental assets (data/supplemental/assets_extra.csv) ----
    "XEF.TO": dict(geography={"INTL_DEV": 1.0}, currency={"OTHER": 1.0}, note="Developed markets ex North America (Europe, Japan, Australia...)"),
    "XEC.TO": dict(geography={"EM": 1.0}, currency={"OTHER": 1.0}, note="Emerging markets (China, India, Taiwan...)"),
    "XEQT.TO": dict(geography={"US": 0.45, "CA": 0.25, "INTL_DEV": 0.24, "EM": 0.06},
                    currency={"USD": 0.45, "CAD": 0.25, "OTHER": 0.30}, note="All-equity global portfolio in one fund"),
    "VDY.TO": dict(geography={"CA": 1.0}, currency={"CAD": 1.0}, note="Canadian high-dividend stocks (bank- and energy-heavy)"),
    "XESG.TO": dict(geography={"CA": 1.0}, currency={"CAD": 1.0}, note="Canadian equities with ESG screening and tilts (issuer methodology)"),
    "ICLN": dict(geography={"US": 0.45, "INTL_DEV": 0.40, "EM": 0.15}, currency={"USD": 0.45, "OTHER": 0.55},
                 note="Thematic clean-energy fund: concentrated, volatile"),
    "CASH.TO": dict(geography={"CA": 1.0}, currency={"CAD": 1.0}, note="High-interest savings ETF; treated as cash-equivalent"),
    "SOL-USD": dict(geography={"GLOBAL": 1.0}, currency={"USD": 1.0}),
}

GEO_LABELS = {"CA": "Canada", "US": "United States", "INTL_DEV": "International developed", "EM": "Emerging markets",
              "GLOBAL": "Global / no country"}

# Fossil-fuel screen used for ESG preferences: GICS Energy sector (assumption: ENB, CNQ, XOM are fossil-fuel
# businesses; this mirrors the fossil-fuel exclusion in ESGV's published methodology). Controversy status is NOT
# in the data and is reported as "not verified".
ESG_EXCLUDED_SECTORS_DEFAULT = ["Energy"]


@lru_cache(maxsize=1)
def etf_sectors():
    f = SUPPLEMENTAL / "etf_sector_weights.json"
    return json.loads(f.read_text()) if f.exists() else {"etfs": {}}


@lru_cache(maxsize=None)
def supplemental(name):
    f = SUPPLEMENTAL / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


@lru_cache(maxsize=1)
def load_universe() -> dict:
    df = pd.read_csv(STARTER / "assets_universe.csv")
    extra = SUPPLEMENTAL / "assets_extra.csv"
    if extra.exists():
        df = pd.concat([df.assign(source="starter"), pd.read_csv(extra).assign(source="supplemental")], ignore_index=True)
    else:
        df = df.assign(source="starter")
    uni = {}
    for r in df.itertuples():
        lt = LOOKTHROUGH.get(r.ticker, {})
        ac = lt.get("asset_class") or CLASS_MAP[r.asset_class]
        is_fund = r.asset_class.startswith("etf_")
        meta = {
            "name": r.name, "asset_class": ac, "listing_currency": r.currency, "market": r.market,
            "starter_sector": r.sector, "diversified": lt.get("diversified", is_fund),
            "geography": lt.get("geography", {"CA": 1.0} if r.market == "TSX" else {"US": 1.0}),
            "currency": lt.get("currency", {r.currency: 1.0}),
            "lookthrough_source": "assumption (issuer description)" if r.ticker in LOOKTHROUGH else "starter dataset",
            "note": lt.get("note"), "data_source": r.source,
        }
        if ac == "equity":
            if is_fund:
                meta["sectors"] = etf_sectors()["etfs"].get(r.ticker) or {r.sector: 1.0}
                meta["sector_source"] = "Yahoo fund breakdown (supplemental)" if r.ticker in etf_sectors()["etfs"] else "starter label"
            else:
                meta["sectors"] = {r.sector: 1.0}
                meta["sector_source"] = "starter dataset (GICS)"
        if r.ticker in supplemental("fundamentals").get("companies", {}):
            meta["fundamentals"] = supplemental("fundamentals")["companies"][r.ticker]
        if r.ticker in supplemental("esg_screen").get("tickers", {}):
            meta["esg_screen"] = supplemental("esg_screen")["tickers"][r.ticker]
        uni[r.ticker] = meta
    uni[CASH] = {"name": "Cash / high-interest savings (CAD)", "asset_class": "cash", "listing_currency": "CAD",
                 "market": "n/a", "starter_sector": "Cash", "diversified": True, "geography": {"CA": 1.0},
                 "currency": {"CAD": 1.0}, "lookthrough_source": "synthetic",
                 "note": "Synthetic: accrues the Bank of Canada overnight rate (assumption for a HISA)"}
    return uni


UNIVERSE = load_universe()
