# SecondLook: a multi-agent second look before a self-directed investor acts

**PolyFinances Datathon 2026 · AlphaForge AI · Team 10**

SecondLook takes an investor's own idea, for example *"everyone is talking about Tesla, move $60k from my bond fund into TSLA"*. It checks whether that idea is consistent with the investor's **own** goals, horizons, constraints and preferences, and it explains why. Specialised agents on **Amazon Bedrock** reason over numbers computed deterministically from the official starter dataset. A rules engine guarantees the verdict can never be more permissive than the profile allows. A **Bedrock Guardrail** screens every output, and every run is stored as an auditable trace in **Amazon S3**.

> ⚠️ Educational simulation. No real transactions, no personalised financial advice, fictional personas, public data.
> Past performance does not guarantee future results.

| Deliverable | Where |
|---|---|
| Prototype | `app.py` (Streamlit) + `src/` |
| Technical documentation | [`docs/technical_documentation.md`](docs/technical_documentation.md) |
| Evaluation results | [`docs/evaluation.md`](docs/evaluation.md) |
| One-pager | [`docs/one_pager.md`](docs/one_pager.md) |
| Video script | [`docs/video_script.md`](docs/video_script.md) |

## What it shows (official personas)

| Persona | Request | Verdict |
|---|---|---|
| Robert, 59, low-moderate, 3–5y | Move $60k from XBB into TSLA | ✖ breaks his risk budget (56% → 111% vs 65%) and 10% single-name cap. Computed variant: $10k → ◐ (conflicts with his stated preference for stability) |
| Amira, 26, high risk, 15y+ | $15k new money into NVDA | ✖ "high risk ≠ anything goes": single name 29% > 15%, tech 59% > 50%, risk 184% > 150% |
| Mateo, 41, moderate, ESG | Switch $20k from ESGV to SPY | ◐ fossil-fuel exposure through SPY rises; controversy data explicitly "not verified" |
| Maya (optional near-term purchase) | $15k of condo money into QQQ | ✖ tolerance is high, but capacity for a 2.5-year goal is not |

## Architecture

```
request ─► Intake agent ─► validator ─► Deterministic toolbox (exposures, risk, stress, goal capacity,
                                          constraints, ESG view, macro, rule ceiling, counterfactuals)
                                              │
                         ┌────────────────────┴───────────────────┐
                    Profile agent                          Market analyst agent
                         └──────────► Advocate ⇄ Skeptic (2 rounds) ◄──────────┘
                                              │
                                     Guardian agent ─► Judge / explainer
                                              │
                    rule-ceiling enforcement ─► Bedrock Guardrail ─► UI + S3 audit trace
                                              + numeric grounding check
```

Each component and the reason it exists are described in [`docs/technical_documentation.md`](docs/technical_documentation.md) §2.

## AWS services

- **Amazon Bedrock** (`global.amazon.nova-2-lite-v1:0`, Converse API) for all 9 agent calls per analysis.
- **Amazon Bedrock Guardrails**:
  - blocks guaranteed-return claims and PII;
  - detects and logs trade-instruction language without blocking it.
- **Amazon S3**:
  - private, versioned, encrypted bucket;
  - one JSON audit trace per analysis, plus a copy of the input data.

## Setup

Requirements: Python 3.10+ and AWS credentials for the Team 10 account in `us-east-1`.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# AWS credentials: use a profile or export the AWS_* variables. Never commit them.
export AWS_PROFILE=team10 AWS_DEFAULT_REGION=us-east-1

.venv/bin/python scripts/check_aws.py        # identity + Bedrock smoke test
.venv/bin/python scripts/setup_aws.py        # (once) S3 bucket + Bedrock Guardrail → aws_resources.json
.venv/bin/streamlit run app.py               # the prototype
```

Other entry points:

```bash
.venv/bin/python -m pytest -q                                   # 29 deterministic tests (no AWS needed)
.venv/bin/python scripts/run_case.py robert "Move \$60,000 from XBB into TSLA"   # one analysis from the CLI
.venv/bin/python scripts/evaluate.py --repeats 2                # end-to-end evaluation → docs/evaluation.md
.venv/bin/python scripts/fetch_supplemental.py                  # refresh ETF sector weights (supplemental data)
```

Configuration:
- `BEDROCK_MODEL_ID` overrides the model.
- `SECONDLOOK_BUCKET` and `SECONDLOOK_GUARDRAIL_ID` override `aws_resources.json`.
- The app runs without S3 or the Guardrail; the UI then says they are "not configured".

## Data

| Data | Source | Notes |
|---|---|---|
| `data/starter/` | Official AlphaForge starter pack: Yahoo Finance (yfinance), Bank of Canada Valet, FRED | 2021-11-12 to 2026-11-12. Terms in `data/starter/sources_metadata.csv` |
| `data/supplemental/etf_sector_weights.json` | Yahoo fund sector breakdown via yfinance | Snapshot; look-through for XIU.TO, SPY, QQQ, ESGV |
| `personas/` | Fictional, based on the official brief | Amira, Mateo, Robert + optional Maya |

Processing is documented in the technical documentation §4:
- `adj_close` total returns;
- Bank of Canada USD→CAD conversion;
- weekly Friday alignment;
- CPI publication lag;
- volatility-based risk units.

## Repository layout

```
app.py                  Streamlit UI
src/universe.py         31-asset starter universe + look-through metadata (assumptions labelled)
src/analytics.py        deterministic toolbox (all numbers)
src/rules.py            verdict ceiling + computed counterfactuals
src/agents.py           role agents (Bedrock)
src/orchestrator.py     pipeline, parallelism, trace, guardrail, S3
src/grounding.py        numeric grounding check
src/aws.py, src/bedrock.py   AWS integration
personas/               fictional personas (JSON)
scripts/                setup, CLI, evaluation, data refresh
tests/                  deterministic tests
docs/                   documentation, evaluation, one-pager, video script, official case
```
