# SecondLook: a second look before you act

**PolyFinances Datathon 2026 · AlphaForge AI · Team 10**

### The problem
Self-directed investors have more data than ever, but no one tells them when an idea doesn't fit *them*. Platforms show the security, not whether it matches the investor's own goals, horizon and values. Tools that simply agree are dangerous; tools that hand out picks are not allowed.

### What SecondLook does
The investor states an idea in plain language. SecondLook answers one question: **is this consistent with what you told us about yourself, and why?**

- **Verdict:** ✔ consistent / ◐ with conditions / ✖ inconsistent / ? needs information.
- **Explanation:** specific reasons and the before → after numbers that decided it. Facts, assumptions and fiction are labelled.
- **Computed variants** that would change the verdict (smaller amount, new money, a swap, a diversified fund, a longer-term goal). Information, not advice.
- **Interactive:** instant what-if simulator, grounded follow-up chat, investor comparison, and **create your own investor**.

### Agentic approach
- **9 Amazon Bedrock calls per analysis** (Nova 2 Lite), one job each: intake, profile, market analyst, advocate ⇄ skeptic (2 rounds), guardian, judge.
- **A deterministic toolbox computes every number.** Agents only reason over it, and a grounding check traces each % and $ back to the data.
- **A rules engine caps the verdict:** the judge can be stricter, never more permissive.

### Originality
- **Challenges instead of agreeing:** Robert's $60k Tesla idea is ✖. His retirement money's risk goes 56% → 111% against a 65% limit.
- **"High risk ≠ anything goes":** Amira's $15k NVIDIA idea breaks her own single-name, tech and risk limits.
- **Beyond risk and return:** for Mateo, it checks indirect fossil-fuel exposure and a public ESG screen from an SEC filing (J&J is excluded), and says what it can't verify.
- **Tolerance ≠ capacity:** a high-tolerance saver still can't put condo money due in 2.5 years into QQQ.

### Data
Official starter pack (31 assets, 2021–2026, Bank of Canada, FRED) plus 19 documented supplemental assets, ETF sector weights, fundamentals and the SEC ESG screen. All in CAD; biases and gaps disclosed.

### Explainability and trust
Every run is an audit trace in **Amazon S3** (each agent's output, tokens, latency, data provenance). An **Amazon Bedrock Guardrail** blocks guaranteed-return claims and PII. The **public demo runs on AWS Lambda** (container in Amazon ECR), scaling to zero with usage caps. **Evaluation:** 36 live runs, 36/36 verdicts as expected and none more permissive, 18/18 stable on repeat, 768/775 figures traced to data, including a prompt-injection attempt.

**User benefit:** a 15-second second opinion that respects the investor's autonomy: clear for a novice, precise for an expert, every claim verifiable.

*Educational simulation · no real transactions · no personalised advice · fictional personas.*
