# SecondLook: a second look before you act

**PolyFinances Datathon 2026 · AlphaForge AI · Team 10**

### The problem
Self-directed investors have more data than ever, but no one to tell them when an idea doesn't fit *them*. "Everyone is talking about Tesla." "AI is the future." "Exxon pays a great dividend." Platforms show the security, not whether it matches the investor's own goals, horizon and values. Tools that simply agree are dangerous. Tools that hand out picks are not allowed.

### What SecondLook does
The investor states their idea in plain language. SecondLook answers one question: **is this idea consistent with what you told us about yourself, and why?**

- **Verdict:** ✔ consistent / ◐ consistent only under conditions / ✖ inconsistent / ? insufficient data.
- **Explanation:** specific reasons, "this no longer holds if…", and before/after charts. Facts, assumptions and fiction are labelled separately.
- **Computed variants** of the same idea: a smaller amount, a different funding source, a swap. These are information, not advice.

### Agentic approach
- **9 Amazon Bedrock calls per analysis** (Nova 2 Lite), each with one job:
  - Intake parses the request.
  - Profile compares tolerance with capacity.
  - The Market analyst says what changes.
  - Advocate and Skeptic debate in two rounds.
  - The Guardian checks constraints vs preferences.
  - The Judge explains.
- **A deterministic toolbox computes every number.** Agents reason only over it. A numeric grounding check traces each % and $ they write back to the data.
- **A rules engine sets a verdict ceiling.** The judge can be more cautious, never more permissive.

### Originality
- **Challenges instead of agreeing.** Robert's $60k Tesla idea is ✖: his retirement money's risk goes 56% → 111% against a 65% limit. A $10k variant is ◐ because it conflicts with his stated preference for stability.
- **"High risk ≠ anything goes".** Amira's $15k NVIDIA idea breaks her own single-name, tech-sector and risk limits.
- **Beyond risk and return.** Mateo's switch from ESGV to SPY raises his indirect fossil-fuel exposure. SecondLook also says plainly that controversy data is *not verified*.
- **Tolerance ≠ capacity.** A high-tolerance saver still can't put condo money due in 2.5 years into QQQ.

### Data
Official starter pack (31 assets, adjusted prices 2021–2026, Bank of Canada exchange rates and rates, FRED), plus 19 documented supplemental assets from the same source and window (international and emerging-market funds, Canadian ESG, established income names, the AI names investors ask about). Also ETF sector weights, company fundamentals, and an ESG screen from SEC filings. All in CAD.

Risk units are measured volatility relative to the S&P 500. Stress tests include historical replays such as 2022, when stocks and bonds fell together, and CPI is used only once it was published. Survivorship bias, the CNQ split anomaly and ESG gaps are disclosed.

### Explainability and trust
- Every run produces an audit trace stored in **Amazon S3**, with each agent's output, latency, tokens and the data provenance.
- An **Amazon Bedrock Guardrail** blocks guaranteed-return claims and PII, and logs trade-instruction language.
- **Evaluation:** 36 live end-to-end runs. The verdict matched the expected one in 36/36 and was never more permissive than expected. Repeats agreed in 18/18 cases, and 845/847 figures traced to data. The runs included a prompt-injection attempt.

### User benefit
A 15-second second opinion that respects the investor's autonomy. It is clear enough for a novice and precise enough for an expert, and every claim is verifiable.

*Educational simulation · no real transactions · no personalised advice · fictional personas.*
