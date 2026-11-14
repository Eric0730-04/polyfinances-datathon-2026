"""Supplemental public data not in the starter pack. Each output records source, URL and fetch date.

1. etf_sector_weights.json: sector look-through of XIU.TO, SPY, QQQ, ESGV
   (Yahoo fund breakdown via yfinance).
2. fundamentals.json: company snapshot for the 20 single stocks
   (Yahoo quote summary via yfinance: size, profitability, leverage, growth, dividend, listing age).
   Used as context for "established company / quality" preferences; never as a forecast.
3. esg_screen.json: which US stocks are held by Vanguard ESG U.S. Stock ETF (ESGV), from its
   SEC Form N-PORT schedule of investments (public regulatory filing). ESGV tracks an index that excludes
   companies for fossil fuels, weapons, tobacco, controversial conduct, etc. Membership = passed that screen.
   Absence = excluded (reason not stated in the filing). Canadian stocks are not covered (US-only fund).

Usage: python scripts/fetch_supplemental.py
"""
import html as H
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "supplemental"
OUT.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")
universe = pd.read_csv(ROOT / "data" / "starter" / "assets_universe.csv")

# ---------------------------------------------------------------- 1. ETF sectors
YAHOO_TO_GICS = {
    "technology": "Information Technology", "financial_services": "Financials", "healthcare": "Health Care",
    "consumer_cyclical": "Consumer Discretionary", "consumer_defensive": "Consumer Staples",
    "communication_services": "Communication Services", "industrials": "Industrials", "energy": "Energy",
    "utilities": "Utilities", "realestate": "Real Estate", "basic_materials": "Materials",
}
sectors = {"source": "Yahoo Finance via yfinance funds_data.sector_weightings", "fetched_at_utc": NOW,
           "mapping": "Yahoo sector names mapped to GICS sector names used in assets_universe.csv", "etfs": {}}
for t in ["XIU.TO", "SPY", "QQQ", "ESGV"]:
    sw = yf.Ticker(t).funds_data.sector_weightings
    w = {YAHOO_TO_GICS.get(k, k): float(v) for k, v in sw.items() if v}
    s = sum(w.values())
    sectors["etfs"][t] = {k: round(v / s, 4) for k, v in sorted(w.items(), key=lambda kv: -kv[1])}
(OUT / "etf_sector_weights.json").write_text(json.dumps(sectors, indent=2))
print("sectors ok")

# ---------------------------------------------------------------- 2. fundamentals
FIELDS = {"marketCap": "market_cap", "profitMargins": "profit_margin", "returnOnEquity": "return_on_equity",
          "debtToEquity": "debt_to_equity_pct", "revenueGrowth": "revenue_growth_yoy", "dividendYield": "dividend_yield_pct",
          "fullTimeEmployees": "employees", "currency": "currency", "longBusinessSummary": "business_summary"}
fund = {"source": "Yahoo Finance quote summary via yfinance Ticker.info", "fetched_at_utc": NOW,
        "note": "Snapshot at fetch date (not point-in-time over the price window). Market cap in listing currency.",
        "companies": {}}
for t in universe[universe.asset_class == "equity"].ticker:
    i = yf.Ticker(t).info or {}
    rec = {v: i.get(k) for k, v in FIELDS.items()}
    if rec.get("business_summary"):
        rec["business_summary"] = rec["business_summary"][:400]
    ftd = i.get("firstTradeDateMilliseconds")
    rec["listed_since"] = pd.to_datetime(ftd, unit="ms").strftime("%Y") if ftd else None
    fund["companies"][t] = rec
(OUT / "fundamentals.json").write_text(json.dumps(fund, indent=2))
print("fundamentals ok:", len(fund["companies"]))

# ---------------------------------------------------------------- 3. ESGV holdings screen (SEC N-PORT)
FILING = {"accession": "0000052848-26-000891", "period": "2026-05-31", "filed": "2026-07-29",
          "url": "https://www.sec.gov/Archives/edgar/data/52848/000005284826000891/vg_esgusstocketf.htm"}
UA = {"User-Agent": "SecondLook datathon research team10 research@example.org"}
raw = urllib.request.urlopen(urllib.request.Request(FILING["url"], headers=UA), timeout=60).read().decode("utf-8", "ignore")
text = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", raw)))
NAMES = {"AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "NVDA": "NVIDIA Corp.", "GOOGL": "Alphabet Inc.",
         "AMZN": "Amazon.com Inc.", "TSLA": "Tesla Inc.", "JPM": "JPMorgan Chase & Co.", "JNJ": "Johnson & Johnson",
         "PG": "Procter & Gamble Co.", "XOM": "Exxon Mobil Corp."}
screen = {"source": "SEC EDGAR Form N-PORT, Vanguard World Fund: Vanguard ESG U.S. Stock ETF schedule of investments",
          **FILING, "fetched_at_utc": NOW,
          "method": "A company listed in the schedule passed the ESGV index screens; absence means excluded "
                    "(the filing does not state the reason). Non-US companies are outside ESGV's universe.",
          "screen_description": "ESGV tracks the FTSE US All Cap Choice Index, which excludes companies involved in e.g. "
                                "fossil fuels, weapons, tobacco, alcohol, gambling, adult content, nuclear power, and "
                                "companies failing controversy/diversity criteria (issuer methodology).",
          "tickers": {}}
for t, n in NAMES.items():
    screen["tickers"][t] = "held" if n.lower() in text.lower() else "not held"
for t in universe[(universe.asset_class == "equity") & (universe.market == "TSX")].ticker:
    screen["tickers"][t] = "not covered (non-US)"
(OUT / "esg_screen.json").write_text(json.dumps(screen, indent=2))
print("esg screen:", screen["tickers"])
