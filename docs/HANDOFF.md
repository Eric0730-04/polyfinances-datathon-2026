# Team hand-off: read this first (people and AI assistants)

> **For AI assistants:** this file is the shared project context. Read it, then `README.md` and
> `docs/technical_documentation.md`, before changing anything.
> Rules: never commit credentials; no AI or tool attribution in commits, docs or README (the work is credited to Team 10 only).

_Last updated: 2026-11-14 (Team 10)_

## 1. The challenge, in one paragraph

PolyFinances Datathon 2026, "AlphaForge AI" (National Bank × AWS × PolyFinances). Build a **self-explaining agentic tool** that uses public financial data to inform investment decisions for different investor profiles.

- **Personas:** three official ones.
  - **Amira**, 26, high risk, 15+ years. Tests that "high risk ≠ anything goes".
  - **Mateo**, 41, moderate, 8–12 years, ESG. Tests non-financial criteria.
  - **Robert**, 59, low-moderate, 3–5 years. Tests challenging a request that conflicts with the profile.
- **Rules:**
  - Simulation only: no real trades, no personalised advice.
  - Separate facts, assumptions and fiction.
  - **AWS use is mandatory**; without it the project is not eligible.
- **Deliverables:** prototype + code, a video of about 5 minutes, technical documentation, a one-pager.
- **Scoring:**

  | Area | Weight |
  |---|---|
  | Solution | 20% |
  | Agentic + explainability | 20% |
  | Data | 20% |
  | UX | 10% |
  | AWS | 15% |
  | Pitch | 15% |

- **Source files:** the official case is in `docs/case/`; the starter dataset is in `data/starter/`.

## 2. What we built: SecondLook

An investor types an idea ("move $60k from my bond fund into Tesla"). SecondLook checks whether it is **consistent with that investor's own goals, horizons, limits and preferences**, and explains why.

| Verdict | Meaning |
|---|---|
| ✔ Consistent | No limit is breached, before or after |
| ◐ Consistent with conditions | No new breach, but a preference is worsened or an old gap remains |
| ✖ Inconsistent | Creates or worsens a breach of a hard limit or a goal's risk limit |
| ? Needs more information | Asks a targeted follow-up question |

It never recommends what to buy.

**Pipeline:**
1. The intake agent parses the request.
2. A deterministic toolbox computes every number. It never uses an LLM.
3. A rules engine sets the most permissive verdict allowed and computes variants: smaller amount, new money, a swap.
4. Profile and market-analyst agents run in parallel.
5. Advocate and skeptic debate for 2 rounds.
6. The guardian checks constraints vs preferences.
7. The judge writes the explanation.
8. A Bedrock Guardrail screens the text, and the run is saved to S3 as an audit trace.

**Two safety locks:**
- The judge can be stricter than the rules, never more lenient.
- Every % and $ an agent writes is checked against the data ("grounding").

## 3. Current status

| Item | Status |
|---|---|
| Prototype (FastAPI + web UI) | ✅ done, `server.py` + `web/` |
| Official personas + Maya (optional near-term-purchase scenario) | ✅ `personas/` |
| Starter data + supplemental data (ETF sectors, SEC N-PORT ESG screen, fundamentals) | ✅ |
| AWS: Bedrock (Nova 2 Lite), Guardrails, S3 | ✅ |
| Tests | ✅ 43 deterministic tests |
| Evaluation | ✅ 36/36 correct, 18/18 stable, 845/847 numbers grounded, see `docs/evaluation.md` |
| Technical documentation, one-pager, video script | ✅ in `docs/` |
| **Video recording** | ⏳ to do, script in `docs/video_script.md` |
| **Team review of assumptions** (§5) | ⏳ to do |
| Hosting a public demo link | ⏳ optional (currently runs locally) |
| Confirm submission deadline and format | ⏳ to do |

## 4. How to run it

```bash
git clone https://github.com/Eric0730-04/polyfinances-datathon-2026 && cd polyfinances-datathon-2026
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# AWS: Team 10 shared event account (381491974104), us-east-1.
# Workshop page → "Get AWS CLI credentials" → paste the export lines in your terminal
# (or save them as profile team10). They expire after a few hours.
export AWS_DEFAULT_REGION=us-east-1   # plus the AWS_* lines from the workshop page

.venv/bin/python scripts/check_aws.py              # checks the credentials work
.venv/bin/uvicorn server:app --port 8000           # open http://localhost:8000
.venv/bin/python -m pytest -q                      # tests, no AWS needed
```

The S3 bucket and Guardrail already exist; their IDs are in `aws_resources.json`. Do **not** re-run `scripts/setup_aws.py` unless you change them.

**Handy demo links:**
- `/?persona=robert&q=...` runs an analysis.
- `/?compare=...` compares all investors.
- `/?run=<run_id>` re-opens a saved analysis from S3.

## 5. Decisions and assumptions (review these as a team)

Judges may ask about these. They are documented in `docs/technical_documentation.md` §5.

1. **Risk is measured in "S&P 500 equivalents":** each asset's volatility ÷ SPY's volatility, from the starter data. Examples: TSLA 3.7×, BTC 3.4×, XBB 0.44×, cash ≈ 0.
2. **Goal risk limits by horizon:** <1y 5%, 1–3y 20%, 3–5y 65%, 5–10y 85%, 10y+ 150%.
   - **Tolerance caps:** low 55%, low-moderate 65%, moderate 85%, high 150%.
   - The limit is the lower of the two. These are our rules of thumb, not regulation.
3. Horizon ranges use the **lower bound** (Robert 3–5 → 3, Mateo 8–12 → 8).
4. **Derived limits are labelled "assumed" in the UI:**
   - Amira: max 50% in one sector ("not exclusively tech"), max 10% crypto, max 15% in one name.
   - Robert: max 10% in one name; avoid names more than 2× as volatile as the S&P 500 (preference).
   - Mateo: no Energy-sector stocks (fossil-fuel proxy); prefer US stocks that pass Vanguard's ESG fund screen (from its SEC filing). XOM and JNJ are excluded by that screen.
5. **Personas' portfolios are fictional**, built from the starter universe.
6. **Guardrail:** blocks guaranteed-return claims and PII. "Trade instruction" language is only logged, because blocking it caused false positives.

## 6. Where things are

| Path | What |
|---|---|
| `src/analytics.py` | All numbers: data loading, exposures, risk, stress tests, goal limits, constraint checks, ESG view, macro |
| `src/rules.py` | Verdict ceiling + computed variants |
| `src/agents.py` | Agent prompts (Bedrock) |
| `src/orchestrator.py` | Runs the pipeline, follow-up questions, trace, guardrail, S3 |
| `src/errors.py` | Plain-language error messages |
| `src/universe.py` | 50-asset universe (31 official + 19 supplemental) + look-through assumptions |
| `server.py`, `web/` | API + UI |
| `personas/*.json` | Investor profiles, sample requests |
| `scripts/` | `check_aws`, `setup_aws`, `run_case` (CLI), `evaluate`, `fetch_supplemental` |
| `docs/` | Technical documentation, one-pager, video script, evaluation, official case |

## 7. Gotchas

- **Credentials expire.** "The AWS credentials have expired or are invalid" in the app means you need fresh ones from the workshop page and a server restart.
- **Restart the server after code changes.** `uvicorn` isn't started with `--reload`.
- **Cost:** a full evaluation (`scripts/evaluate.py`) is about 30 runs × 24k tokens. Fine, but don't loop it.
- **Data:**
  - Only the 50 assets (31 official + 19 supplemental, `data/supplemental/assets_extra.csv`) can be analysed; anything else gets a follow-up question. Add more with `scripts/fetch_extra_assets.py`.
  - The ESG screen covers US stocks only.

## 8. Ideas if we have time

- Host the demo on AWS (App Runner/ECS) so judges can click a link.
- Multi-step plans ("sell X and buy Y and Z").
- Let the investor confirm or edit the "assumed" limits in the UI.
- Canadian ESG evidence (e.g. holdings of a Canadian ESG ETF).
