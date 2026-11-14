"""Supplemental public data not in the starter pack: equity-ETF sector weights (look-through).

Source: Yahoo Finance fund holdings breakdown via yfinance (`Ticker.funds_data.sector_weightings`).
Used for: sector concentration and ESG (fossil-fuel / Energy) look-through of XIU.TO, SPY, QQQ, ESGV.
Limitation: a single snapshot as of the fetch date; weights drift over time and are applied to the whole window.

Usage: python scripts/fetch_supplemental.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

OUT = Path(__file__).resolve().parents[1] / "data" / "supplemental" / "etf_sector_weights.json"
YAHOO_TO_GICS = {
    "technology": "Information Technology", "financial_services": "Financials", "healthcare": "Health Care",
    "consumer_cyclical": "Consumer Discretionary", "consumer_defensive": "Consumer Staples",
    "communication_services": "Communication Services", "industrials": "Industrials", "energy": "Energy",
    "utilities": "Utilities", "realestate": "Real Estate", "basic_materials": "Materials",
}
out = {"source": "Yahoo Finance via yfinance funds_data.sector_weightings",
       "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "mapping": "Yahoo sector names mapped to GICS sector names used in assets_universe.csv", "etfs": {}}
for t in ["XIU.TO", "SPY", "QQQ", "ESGV"]:
    sw = yf.Ticker(t).funds_data.sector_weightings
    w = {YAHOO_TO_GICS.get(k, k): round(float(v), 4) for k, v in sw.items() if v}
    s = sum(w.values())
    out["etfs"][t] = {k: round(v / s, 4) for k, v in sorted(w.items(), key=lambda kv: -kv[1])}
    print(t, "raw sum", round(s, 3), list(out["etfs"][t].items())[:3], "Energy", out["etfs"][t].get("Energy"))
OUT.write_text(json.dumps(out, indent=2))
