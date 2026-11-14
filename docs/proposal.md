# SecondLook — a multi-agent "second look" before a self-directed investor acts

> Simulation only. No real transactions, no personalised financial advice, no real client or banking data. All personas are fictional.

## 1. Problem (the niche)

Self-directed investors (e.g. on National Bank Direct Brokerage) have plenty of data but no advisor. When they get an idea ("put $15k into XSP", "move my condo savings into a Bitcoin ETF"), nothing checks whether that idea is coherent with **their own** goals, horizons and constraints. Brokerage platforms show the security; they don't show the investor what changes in *their* portfolio.

The brief: *don't just give Robert what he wants.* Flag inconsistencies with the profile, separate **risk tolerance** from **risk capacity**, enforce **constraints over preferences**, and explain everything.

**SecondLook** takes one proposed action plus a profile and portfolio. It returns a coherence verdict with a fully traceable explanation:
- what changes in the portfolio (before/after exposures, stress tests)
- which goal the money belongs to, and whether that goal's horizon can absorb the risk
- the best case *for* and *against* the idea (an agent debate)
- hard-constraint violations, which veto preferences
- "this conclusion no longer holds if…" conditions
- facts vs. assumptions vs. fictional elements, each labelled, with data sources and dates

It does not tell the investor what to buy. It tells them whether their own idea is consistent with what they told us about themselves, and why.

## 2. Architecture

```
 Investor request (free text) + Persona (goals, horizons, tolerance, constraints, preferences) + Holdings
        │
        ▼
 [Intake agent]  ── parses the request → structured action (ticker, amount, funding goal)
        │
        ▼
 Deterministic toolbox (Python, no LLM) — the single source of numbers
   • market data snapshot (prices, sector weights; date, currency and source on every value)
   • exposures before/after: asset class, geography, sector, currency, single-position concentration
   • risk metrics: annualised volatility, max drawdown, worst 12-month return
   • stress scenarios: equity crash, rate shock, CAD/USD move, crypto crash
   • risk capacity per goal bucket (horizon + liquidity rules)
        │
        ▼
 [Profile agent]    tolerance vs. capacity per goal, mismatch flags
 [Market analyst]   observations from the computed numbers only
        │
        ▼
 [Advocate] ⇄ [Skeptic]   debate (one rebuttal round)
        │
        ▼
 [Constraint guardian]  hard rules (deterministic) + review; constraints override preferences
        │
        ▼
 [Judge / explainer]   verdict + confidence + "no longer valid if…" + facts/assumptions/fiction + sources
        │
        ▼
 Bedrock Guardrail (no personalised advice / no guarantees)  →  UI + audit trace saved to S3
```

**Design rule:** the LLM never invents a number. Agents only reason over toolbox outputs, which are passed in as JSON with provenance attached. Every agent output is stored in the trace.

## 3. AWS services (what each is for)

| Service | Why it's the right tool |
|---|---|
| Amazon Bedrock (Nova 2 Lite, `global.amazon.nova-2-lite-v1:0`) | Agent reasoning. Small, cheap and fast; the workshop recommends starting there. A larger model is only used if Nova 2 Lite shows a demonstrable flaw. |
| Amazon Bedrock Guardrails | Responsible-AI layer: blocks personalised-advice and guaranteed-return phrasing on the final output. |
| Amazon S3 | Versioned market-data snapshot plus one JSON audit trace per analysis (reproducibility, governance). |
| (optional) SageMaker Studio | Exploratory notebooks on the starter dataset. |

## 4. Personas (fictional, contrasting)

The same request runs against different profiles and should get different answers:

- **Maya, 27**: saving for a condo down payment in about 2.5 years, plus long-term retirement. High self-declared tolerance, low capacity for the down-payment money.
- **Robert, 58**: retires in about 7 years, wants income. Portfolio concentrated in Canadian banks and energy. Moderate tolerance. Asks whether adding XSP improves diversification (the kickoff demo scenario).

## 5. Mapping to judging criteria

| Criterion | Weight | How we address it |
|---|---|---|
| Relevance / innovation / prototype | 20% | Focused niche; coherence check instead of a stock picker; debate + veto design |
| Multi-agent, architecture, explainability | 20% | 6 role agents, deterministic toolbox, full trace, "valid unless" |
| Rigor, data sources, validation, viz | 20% | Provenance on every number; stress tests; persona contrast tests |
| UX | 10% | One screen: persona → request → verdict card → "why" drill-down |
| AWS integration | 15% | Bedrock + Guardrails + S3, each with a clear role |
| Pitch / docs | 15% | One-pager, 5-minute video script, architecture doc |

## 6. Known limits (to be expanded)

- Look-through geography and currency for ETFs are approximations from issuer descriptions (labelled as assumptions).
- Historical volatility is not a forecast. Past performance does not guarantee future results.
- Taxes and account types (TFSA/RRSP) are out of scope.
- Market data comes from Yahoo Finance via `yfinance` (public, unofficial), snapshotted with a fetch date.
