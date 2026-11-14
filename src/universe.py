"""Investable universe used by the prototype, with static metadata.

Values marked source="assumption" are approximations we set by hand from issuer
descriptions (rounded), not fetched data. They are shown as assumptions in the UI.
Prices and sector weights are fetched separately (scripts/fetch_market_data.py).
"""

# geography / currency weights sum to 1.0
# currency = what the investor is exposed to after any hedging, from a CAD investor's view
UNIVERSE = {
    # ---- Cash & fixed income ----
    "CASH.TO": dict(name="Global X High Interest Savings ETF", asset_class="cash",
                    geography={"CA": 1.0}, currency={"CAD": 1.0}, mer=0.11),
    "XBB.TO": dict(name="iShares Core Canadian Universe Bond ETF", asset_class="fixed_income",
                   geography={"CA": 1.0}, currency={"CAD": 1.0}, mer=0.10),
    "ZAG.TO": dict(name="BMO Aggregate Bond Index ETF", asset_class="fixed_income",
                   geography={"CA": 1.0}, currency={"CAD": 1.0}, mer=0.09),
    # ---- Equity ETFs ----
    "XIC.TO": dict(name="iShares Core S&P/TSX Capped Composite ETF", asset_class="equity",
                   geography={"CA": 1.0}, currency={"CAD": 1.0}, mer=0.06),
    "XSP.TO": dict(name="iShares Core S&P 500 ETF (CAD-Hedged)", asset_class="equity",
                   geography={"US": 1.0}, currency={"CAD": 1.0}, mer=0.10,
                   note="Currency-hedged: US equity exposure without USD/CAD currency risk."),
    "VFV.TO": dict(name="Vanguard S&P 500 Index ETF (unhedged)", asset_class="equity",
                   geography={"US": 1.0}, currency={"USD": 1.0}, mer=0.09),
    "ZQQ.TO": dict(name="BMO Nasdaq 100 Equity Hedged to CAD ETF", asset_class="equity",
                   geography={"US": 1.0}, currency={"CAD": 1.0}, mer=0.39,
                   note="Concentrated in large US technology companies."),
    "XEF.TO": dict(name="iShares Core MSCI EAFE IMI ETF", asset_class="equity",
                   geography={"INTL_DEV": 1.0}, currency={"OTHER": 1.0}, mer=0.22),
    "XEC.TO": dict(name="iShares Core MSCI Emerging Markets IMI ETF", asset_class="equity",
                   geography={"EM": 1.0}, currency={"OTHER": 1.0}, mer=0.26),
    "ZEQT.TO": dict(name="BMO All-Equity ETF", asset_class="equity",
                    geography={"US": 0.45, "CA": 0.25, "INTL_DEV": 0.22, "EM": 0.08},
                    currency={"USD": 0.45, "CAD": 0.25, "OTHER": 0.30}, mer=0.20, source="assumption"),
    "XEQT.TO": dict(name="iShares Core Equity ETF Portfolio", asset_class="equity",
                    geography={"US": 0.45, "CA": 0.25, "INTL_DEV": 0.24, "EM": 0.06},
                    currency={"USD": 0.45, "CAD": 0.25, "OTHER": 0.30}, mer=0.20, source="assumption"),
    "VBAL.TO": dict(name="Vanguard Balanced ETF Portfolio (60/40)", asset_class="balanced",
                    asset_mix={"equity": 0.60, "fixed_income": 0.40},
                    geography={"US": 0.33, "CA": 0.40, "INTL_DEV": 0.20, "EM": 0.07},
                    currency={"USD": 0.25, "CAD": 0.55, "OTHER": 0.20}, mer=0.24, source="assumption"),
    # ---- Crypto ----
    "BTCC-B.TO": dict(name="Purpose Bitcoin ETF", asset_class="crypto",
                      geography={"GLOBAL": 1.0}, currency={"USD": 1.0}, mer=1.00,
                      note="Spot bitcoin. Very high volatility; currency treated as USD-linked (assumption)."),
    # ---- Canadian stocks ----
    "RY.TO": dict(name="Royal Bank of Canada", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "TD.TO": dict(name="Toronto-Dominion Bank", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "BNS.TO": dict(name="Bank of Nova Scotia", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "BMO.TO": dict(name="Bank of Montreal", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "ENB.TO": dict(name="Enbridge", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "CNQ.TO": dict(name="Canadian Natural Resources", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "SU.TO": dict(name="Suncor Energy", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "BCE.TO": dict(name="BCE Inc.", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    "SHOP.TO": dict(name="Shopify", asset_class="equity", geography={"CA": 1.0}, currency={"CAD": 1.0}),
    # ---- US stock (USD) ----
    "NVDA": dict(name="NVIDIA Corp.", asset_class="equity", geography={"US": 1.0}, currency={"USD": 1.0}),
}

FX_TICKER = "CAD=X"  # USD→CAD rate, used to convert USD prices

GEO_LABELS = {"CA": "Canada", "US": "United States", "INTL_DEV": "Intl developed",
              "EM": "Emerging markets", "GLOBAL": "Global / no country"}
