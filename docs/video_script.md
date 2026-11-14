# Demo video script (about 5 minutes)

**Setup:** run `uvicorn server:app --port 8000` and open http://localhost:8000. Persona sidebar visible. AWS console tabs ready: S3 bucket and Bedrock Guardrail.

| Time | On screen | Voice-over (suggested) |
|---|---|---|
| 0:00–0:30 | Title, then the official brief's Robert page | "Self-directed investors have endless data but no one to tell them when an idea doesn't fit *them*. The brief asks: can a system challenge a request that conflicts with the investor's profile instead of simply agreeing? That's SecondLook." |
| 0:30–1:10 | Architecture diagram (technical documentation §2) | "Nine Amazon Bedrock calls, each with one job: intake, profile, market analyst, advocate and skeptic debating, a guardian, and a judge. The key design choice: agents never compute numbers. A deterministic toolbox on the official starter data does. A rules engine caps the verdict, so the AI can be more cautious but never more permissive." |
| 1:10–2:20 | Robert selected → "Everyone is talking about Tesla… move $60,000 from XBB into TSLA" → agents run → ✖ verdict | "Robert is 59, low-to-moderate risk, three to five years from retirement. SecondLook says inconsistent. His retirement money goes from 56% to 111% of S&P-500-equivalent risk, against a 65% limit, and Tesla would be 16% of his portfolio." Open **Why**: "Here's what would change the answer, and the computed variants. A $10,000 version fits his limits but still conflicts with his stated preference for stability. Information, not advice." |
| 2:20–2:50 | Scroll to **Risk budget by goal**, **Portfolio X-ray** and **Risk and stress tests** | "Every figure is computed on the starter data, in CAD: Tesla's volatility is 3.7 times the S&P 500's. Replaying 2022, his portfolio would have lost 14% instead of 10%." |
| 2:50–3:40 | **Compare investors**: "Put $2,000 of new money into Bitcoin.", then "AI is the future. Put $15,000 of new money into NVIDIA." | "Same idea, four investors, four different answers. A small bitcoin position fits Amira, conflicts with Robert's and Mateo's stated preferences, and breaks Maya's small retirement budget. And for NVIDIA: Amira is high-risk, but high risk isn't anything goes. It would be 29% of her portfolio and push tech above the 50% she implied." |
| 3:40–4:10 | Mateo: "Add $8,000 of new money to Johnson & Johnson" → ◐ → ESG section | "For Mateo, non-financial criteria matter. We went beyond the starter data: from a public SEC filing we know which US companies Vanguard's ESG fund holds. J&J is excluded, so SecondLook flags a conflict with his wish to avoid controversial companies. It is honest that the filing doesn't say why, and that Canadian stocks aren't covered." |
| 4:10–4:40 | **Evidence and audit trail** section → S3 trace in the AWS console → Guardrail page | "Every run is auditable: each agent's output, tokens, latency, and a grounding score. Every percentage and dollar figure is traced to the data. The trace is stored in Amazon S3, and a Bedrock Guardrail screens the output for guaranteed-return claims." |
| 4:40–5:00 | `docs/evaluation.md` table | "We tested it: 30 live runs including a prompt-injection attempt. 30 of 30 verdicts matched what the profile implies, none was more permissive, and repeats were stable. SecondLook: a second look before you act." |

**Recording tips**
- Run each scenario once before recording, so the results stay in session state and switching tabs is instant.
- Keep the disclaimer banner visible.
- Say "simulation", never "recommendation".
