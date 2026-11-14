# Demo video script (about 5 minutes)

**Setup:** app open in the browser. Persona sidebar visible. AWS console tabs ready: S3 bucket and Bedrock Guardrail.

| Time | On screen | Voice-over (suggested) |
|---|---|---|
| 0:00–0:30 | Title, then the official brief's Robert page | "Self-directed investors have endless data but no one to tell them when an idea doesn't fit *them*. The brief asks: can a system challenge a request that conflicts with the investor's profile instead of simply agreeing? That's SecondLook." |
| 0:30–1:10 | Architecture diagram (technical documentation §2) | "Nine Amazon Bedrock calls, each with one job: intake, profile, market analyst, advocate and skeptic debating, a guardian, and a judge. The key design choice: agents never compute numbers. A deterministic toolbox on the official starter data does. A rules engine caps the verdict, so the AI can be more cautious but never more permissive." |
| 1:10–2:20 | Robert selected → "Everyone is talking about Tesla… move $60,000 from XBB into TSLA" → agents run → ✖ verdict | "Robert is 59, low-to-moderate risk, three to five years from retirement. SecondLook says inconsistent. His retirement money goes from 56% to 111% of S&P-500-equivalent risk, against a 65% limit, and Tesla would be 16% of his portfolio." Open **Why**: "Here's what would change the answer, and the computed variants. A $10,000 version fits his limits but still conflicts with his stated preference for stability. Information, not advice." |
| 2:20–2:50 | **Portfolio impact** tab: before/after charts, 2022 replay | "Every figure is computed on the starter data, in CAD: Tesla's volatility is 3.7 times the S&P 500's. Replaying 2022, his portfolio would have lost 14% instead of 10%." |
| 2:50–3:40 | **Compare personas**: "AI is the future. Put $15,000 of new money into NVIDIA." | "Same request, different investors. Amira is high-risk, but high risk isn't anything goes: NVIDIA would be 29% of her portfolio and push tech above the 50% she implied. Mateo and Robert get different answers for their own reasons." |
| 3:40–4:10 | Mateo: "Switch $20,000 from ESGV to SPY" → ◐ → ESG panel | "For Mateo, non-financial criteria matter. The switch raises his indirect fossil-fuel exposure through SPY. And SecondLook is honest: the data has no controversy information, so it says *not verified* instead of inventing it." |
| 4:10–4:40 | **Audit trail** tab → S3 trace in the AWS console → Guardrail page | "Every run is auditable: each agent's output, tokens, latency, and a grounding score. Every percentage and dollar figure is traced to the data. The trace is stored in Amazon S3, and a Bedrock Guardrail screens the output for guaranteed-return claims." |
| 4:40–5:00 | `docs/evaluation.md` table | "We tested it: 28 live runs including a prompt-injection attempt. 28 of 28 verdicts matched what the profile implies, none was more permissive, and repeats were stable. SecondLook: a second look before you act." |

**Recording tips**
- Run each scenario once before recording, so the results stay in session state and switching tabs is instant.
- Keep the disclaimer banner visible.
- Say "simulation", never "recommendation".
