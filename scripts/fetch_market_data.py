"""Snapshot public market data for the universe into data/market/.

Source: Yahoo Finance via the open-source `yfinance` package (public, unofficial).
Every file is stamped with the fetch timestamp so each number in the app can cite its date.

Usage: python scripts/fetch_market_data.py [--upload]   (--upload copies the snapshot to S3)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.universe import FX_TICKER, UNIVERSE  # noqa: E402

OUT = ROOT / "data" / "market"
OUT.mkdir(parents=True, exist_ok=True)

tickers = list(UNIVERSE) + [FX_TICKER]
fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

px = yf.download(tickers, period="10y", auto_adjust=True, progress=False)["Close"]
px.index = pd.to_datetime(px.index).date
px.index.name = "date"
px.round(4).to_csv(OUT / "prices.csv")

meta = {}
for t in UNIVERSE:
    info, sectors = {}, None
    tk = yf.Ticker(t)
    try:
        info = tk.info or {}
    except Exception:
        pass
    try:
        sw = tk.funds_data.sector_weightings
        sectors = {k: round(float(v), 4) for k, v in sw.items() if v} if sw else None
    except Exception:
        pass
    if not sectors and info.get("sector"):
        sectors = {info["sector"].lower().replace(" ", "_"): 1.0}
    col = px[t].dropna() if t in px else pd.Series(dtype=float)
    meta[t] = {
        "currency": info.get("currency"),
        "long_name": info.get("longName"),
        "quote_type": info.get("quoteType"),
        "sectors": sectors,
        "dividend_yield": info.get("dividendYield") or info.get("yield"),
        "history_start": str(col.index.min()) if len(col) else None,
        "history_end": str(col.index.max()) if len(col) else None,
        "n_obs": int(len(col)),
    }

manifest = {
    "source": "Yahoo Finance via yfinance (public, unofficial API)",
    "fetched_at_utc": fetched_at,
    "price_field": "Close, adjusted for splits and dividends (auto_adjust=True)",
    "fx": f"{FX_TICKER} = CAD per 1 USD",
    "tickers": meta,
}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))

missing = [t for t, m in meta.items() if m["n_obs"] < 250]
print(f"Saved {px.shape} prices, fetched {fetched_at}. Short/missing history: {missing}")
no_sector = [t for t, m in meta.items() if not m["sectors"]]
print("No sector data:", no_sector)

if "--upload" in sys.argv:
    from src.aws import upload_dir
    print(upload_dir(OUT, "market"))
