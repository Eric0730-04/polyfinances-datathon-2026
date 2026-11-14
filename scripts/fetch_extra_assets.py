"""Extend the investable universe beyond the 31 starter assets (supplemental, documented).

Same source, window and format as the official starter pack (Yahoo Finance via yfinance, 2021-11-12 to 2026-11-12,
columns date,ticker,open,high,low,close,adj_close,volume,currency), so the toolbox treats both identically.
Why these assets: they close gaps the personas expose (international diversification, Canadian ESG,
established income names, the "hyped" names investors ask about). See docs/technical_documentation.md §4.

Usage: python scripts/fetch_extra_assets.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "supplemental"
START, END = "2021-11-12", "2026-11-13"  # END exclusive in yfinance -> last row 2026-11-12

# asset_id, ticker, name, asset_class (starter vocabulary), market, currency, sector, why
EXTRA = [
    ("X01", "META", "Meta Platforms", "equity", "NASDAQ", "USD", "Communication Services", "AI / big tech (Amira)"),
    ("X02", "AMD", "Advanced Micro Devices", "equity", "NASDAQ", "USD", "Information Technology", "AI chips (Amira)"),
    ("X03", "PLTR", "Palantir Technologies", "equity", "NASDAQ", "USD", "Information Technology", "highly publicised AI name"),
    ("X04", "LLY", "Eli Lilly", "equity", "NYSE", "USD", "Health Care", "non-tech growth (Amira)"),
    ("X05", "COST", "Costco Wholesale", "equity", "NASDAQ", "USD", "Consumer Staples", "established quality (Robert)"),
    ("X06", "BRK-B", "Berkshire Hathaway (Class B)", "equity", "NYSE", "USD", "Financials", "established quality (Robert)"),
    ("X07", "KO", "Coca-Cola", "equity", "NYSE", "USD", "Consumer Staples", "established income (Robert)"),
    ("X08", "BNS.TO", "Bank of Nova Scotia", "equity", "TSX", "CAD", "Financials", "Canadian income (Robert)"),
    ("X09", "BCE.TO", "BCE Inc.", "equity", "TSX", "CAD", "Communication Services", "Canadian income (Robert)"),
    ("X10", "L.TO", "Loblaw Companies", "equity", "TSX", "CAD", "Consumer Staples", "Canadian defensive (Robert, Mateo)"),
    ("X11", "XEF.TO", "iShares Core MSCI EAFE IMI Index ETF", "etf_equity", "TSX", "CAD", "Broad market (International developed)", "international diversification"),
    ("X12", "XEC.TO", "iShares Core MSCI Emerging Markets IMI Index ETF", "etf_equity", "TSX", "CAD", "Broad market (Emerging markets)", "international diversification"),
    ("X13", "XEQT.TO", "iShares Core Equity ETF Portfolio", "etf_equity", "TSX", "CAD", "Broad market (Global all-equity)", "one-ticket global equity"),
    ("X14", "VDY.TO", "Vanguard FTSE Canadian High Dividend Yield Index ETF", "etf_equity", "TSX", "CAD", "Broad market (Canada dividend)", "income (Robert)"),
    ("X15", "XESG.TO", "iShares ESG Aware MSCI Canada Index ETF", "etf_equity", "TSX", "CAD", "Broad market (Canada, ESG-screened)", "Canadian ESG (Mateo)"),
    ("X16", "ICLN", "iShares Global Clean Energy ETF", "etf_equity", "NASDAQ", "USD", "Clean energy (Global)", "thematic ESG (Mateo)"),
    ("X17", "CASH.TO", "Global X High Interest Savings ETF", "etf_cash", "TSX", "CAD", "Cash (high-interest savings)", "tradable cash alternative"),
    ("X18", "SOL-USD", "Solana", "crypto", "Crypto (24/7)", "USD", "Crypto asset", "crypto beyond BTC/ETH (Amira)"),
    ("X19", "ABX.TO", "Barrick Mining Corporation", "equity", "TSX", "CAD", "Materials", "Canadian materials / gold miner"),
]

tickers = [e[1] for e in EXTRA]
raw = yf.download(tickers, start=START, end=END, auto_adjust=False, progress=False, group_by="ticker", actions=False)
rows = []
for aid, t, name, ac, mkt, ccy, sector, why in EXTRA:
    df = raw[t].dropna(subset=["Close"]).reset_index()
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={"adj_close": "adj_close"})
    df["ticker"], df["currency"] = t, ccy
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    rows.append(df[["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "currency"]])
prices = pd.concat(rows).sort_values(["ticker", "date"])

# validation, same spirit as the starter build script
assert not prices.duplicated(["date", "ticker"]).any(), "duplicate rows"
assert (prices[["close", "adj_close"]] > 0).all().all(), "non-positive prices"
counts = prices.groupby("ticker").date.agg(["count", "min", "max"])
short = counts[counts["count"] < 1000]
assert short.empty, f"short history: {short}"

prices.round(6).to_csv(OUT / "prices_extra.csv", index=False)
pd.DataFrame([e[:7] for e in EXTRA], columns=["asset_id", "ticker", "name", "asset_class", "market", "currency", "sector"]) \
    .to_csv(OUT / "assets_extra.csv", index=False)
(OUT / "assets_extra_manifest.json").write_text(json.dumps({
    "source": "Yahoo Finance via yfinance (same as starter prices_daily.csv)",
    "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "window": f"{START} to 2026-11-12", "adj_close": "split and dividend adjusted (Yahoo method)",
    "why": {e[1]: e[7] for e in EXTRA},
    "rows": int(len(prices)), "per_ticker": counts.astype(str).to_dict(orient="index"),
}, indent=2))
print(counts.to_string())
print("rows:", len(prices))
