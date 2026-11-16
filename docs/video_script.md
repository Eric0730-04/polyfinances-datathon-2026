# Demo video: click-by-click script (about 5 minutes, 2 speakers)

**Live app:** https://isybdeoz22wyqq4tccdermfuvq0zwugt.lambda-url.us-east-1.on.aws
It only works until the event's AWS account closes (Sunday about 11:30), so record before then.

**Speakers:**
- **KARIM:** the investor story (problem, Robert, what-if, Amira, compare, Mateo, closing line). No AWS or Bedrock talk.
- **FAIG:** the technical parts (how the agents work, chatbot, create your own investor, trust and AWS, test results).

**How to record with two people:**
- **Simplest:** one person drives the mouse the whole time, and each person speaks their own scenes live.
- **Or:** record the screen once without talking, then each records their voice over their scenes (iMovie, CapCut), and you edit them together.

---

## Before you record: preload (about 2 minutes, not filmed)

Keep this PDF open on a second screen or a phone. The script is not inside the app.

**Step 1. Open the app and wait about 10 seconds** (the first load is slow).

**Step 2. Preload the four analyses.** Each takes about 15–20 seconds.

**A. Robert and Tesla**

1. Left menu, under **INVESTORS**: click **Robert, 59**.
2. Under the question box: click the chip **TSLA · $60k from XBB**.
3. Wait for the red tag **Inconsistent with profile**.

**B. Mateo and J&J**

1. Left menu: click **Mateo, 41**.
2. Click the chip **JNJ · $8k new money**.
3. Wait for the orange tag **With conditions**.

**C. Amira and NVIDIA**

1. Left menu: click **Amira, 26**.
2. Click the chip **NVDA · $15k new money**.
3. Wait for the red tag **Inconsistent with profile**.

**D. Compare**

1. Left menu: click **Compare investors**.
2. Click the chip **Put $2,000 of new money into Bitcoin.**
3. Wait until all four columns (Robert, Amira, Mateo, Maya) show a result.

**Step 3. Go back to the start.** Left menu → **HISTORY** → click **Robert · Everyone is talking about Tesla…**, then scroll to the very top of the page.

**Check:** HISTORY lists Robert, Mateo and Amira.

**Do NOT refresh or close the tab from now on**, or the preloaded results disappear.

**Not preloaded (done live, instant or a few seconds):** the "Why" row, the What-if simulator, the chatbot, Create your own investor, Evidence & audit.

**Screen:** Chrome full screen, zoom 110% (Cmd +), other tabs closed, notifications off. Never show the terminal or AWS keys.

**Record:** Cmd + Shift + 5 → Record Entire Screen → Record. Stop with ⏹ in the top menu bar. Say "simulation", never "recommendation".

---

## Scene 1 · KARIM · The problem (0:00–0:20)

**Screen:** top of Robert's page.

> "Self-directed investors have more data than ever, but nobody tells them when an idea doesn't fit *them*. The challenge asks: can a system push back when a request conflicts with the investor's profile, instead of simply agreeing? This is SecondLook."

**Point at:** Robert's tags (low-moderate risk, 3–5 years horizon).

## Scene 2 · FAIG · How it works (0:20–0:50)

**Click:** **How it works** in the left menu. Scroll slowly through the first two sections.

> "Behind it, nine AI agents on Amazon Bedrock each have one job: read the request, check the profile, analyse the market impact, argue for and against in a debate, check the rules, and write the verdict. The key design choice: the AI never invents numbers. Plain code computes every figure from the official starter data, and a rules engine caps the verdict, so the AI can be stricter than the rules, never more lenient."

## Scene 3 · KARIM · Robert wants Tesla (0:50–1:40)

**Click:** **HISTORY → Robert · Everyone is talking about Tesla…** (preloaded; it opens instantly).

> "Robert is 59, low-to-moderate risk, a few years from retirement, and everyone is talking about Tesla. He wants to move $60,000 from his bond fund into Tesla."

**Point at, in order:**
1. The red tag **Inconsistent with profile** and the headline.
2. The **Before → after this idea** panel (top right of the answer):
   > "His retirement money would go from 56% to 111% of S&P 500-equivalent risk, against a 65% limit, and Tesla would become 15.6% of his portfolio, above his 10% single-stock limit."
3. **How the agents reached this:** the row of steps.
4. The table **Versions of this idea that would change the verdict**:
   > "SecondLook also recomputes other versions of the same idea. $10,000 instead of $60,000 fits his limits, but still conflicts with his preference for stable companies. This is information, not advice."
5. Scroll down to the box **Why this verdict, and what would change it** (just above "Ask a follow-up"). Click it to open, show it for 2 seconds, click again to close.

## Scene 4 · KARIM · What-if simulator (1:40–2:05)

**Click:** the **What-if simulator** tab (second tab).

1. Drag **Amount** slowly from $60,000 down to **$10,000**. The verdict flips to **With conditions**.
   > "You can change the idea and see the answer change instantly."
2. Drag back to $60,000, then in **Asset** pick **SPY · SPDR S&P 500 ETF Trust**. It flips to **Consistent**.
   > "The same $60,000 in the whole S&P 500, instead of one volatile stock, fits his profile."

## Scene 5 · FAIG · Follow-up chatbot (2:05–2:30)

**Click:** the **Overview** tab, scroll to **Ask a follow-up about this answer**, type **Should I buy Apple instead?**, click **Ask**. (A few seconds.)

> "You can ask follow-up questions. The chat only answers from this analysis, and what-if questions like this one are computed by the rules engine, not guessed by the AI. Here's the instant check, with a button to run the full analysis."

## Scene 6 · KARIM · Amira: high risk isn't "anything goes" (2:30–2:55)

**Click:** **HISTORY → Amira · AI is the future…** (preloaded).

> "Amira is 26, high risk, investing for 15+ years, and loves AI. She wants $15,000 in NVIDIA. Even for a high-risk investor, the answer is no: it would make NVIDIA 29% of her portfolio and push her tech share above the 50% she wants to stay under. But look at the versions: the same $15,000 through a diversified Nasdaq fund, QQQ, fits her profile."

**Point at:** the red tag, then the **QQQ** row in the versions table.

## Scene 7 · KARIM · Same idea, four investors (2:55–3:25)

**Click:** **Compare investors** in the left menu. The four results are already there. **Do not click the Bitcoin chip again.**

> "The challenge asks to show adaptation to context. Same idea, $2,000 of Bitcoin, four different answers. Amira: consistent, a small slice of long-term money. Robert and Mateo: consistent only under conditions, because it goes against what they said they prefer. Maya, saving for a condo: inconsistent, because it would push her small retirement pot over its risk limit."

## Scene 8 · KARIM · Mateo and ESG (3:25–3:55)

**Click:** **HISTORY → Mateo · Add $8,000…** (preloaded), then the **About JNJ** tab.

> "Mateo cares about ESG and wants to avoid controversial companies. We went beyond the starter data: from a public SEC filing, we know which US companies Vanguard's ESG fund actually holds, and Johnson & Johnson is not one of them. So SecondLook flags a conflict. And it's honest: the filing doesn't say why it's excluded, and Canadian stocks aren't covered."

## Scene 9 · FAIG · Create your own investor (3:55–4:20)

**Click:** **Create your own investor** (left menu, under the investors).

1. Click the template **Saving for a house**.
2. Type a name in **Name**, e.g. **Lea**.
3. Point at the **Preview** box on the right (it updates as you type).
4. Click **Save and start checking ideas**. Her dashboard appears.

> "SecondLook isn't limited to our personas. Anyone can describe their own goals, horizons and limits, see their risk budget instantly, and then check any idea against their own profile, the same way."

## Scene 10 · FAIG · Trust and AWS (4:20–4:45)

**Click:** **HISTORY → Robert · Everyone is talking about Tesla…**, then the **Evidence & audit** tab.

**Point at:** **Numbers verified**, **Bedrock Guardrail**, **AI agent calls**, **Audit record: Saved to S3**.

> "Every run is auditable. Every percentage and dollar figure the agents write is checked against the data. A Bedrock Guardrail screens the output for things like guaranteed returns, the full trace of every agent is saved to Amazon S3, and the app runs on AWS Lambda. We tested it on 36 live runs, including a prompt-injection attempt: every verdict matched the profile, and none was more lenient than the rules allow."

## Scene 11 · KARIM · Close (4:45–5:00)

**Screen:** scroll back to the top of Robert's answer (the red tag and the Before → after panel).

> "SecondLook doesn't tell you what to buy. It takes a second look at your own idea, explains why, and shows what would change the answer. It's an educational simulation, not financial advice: a second look before you act."

---

## If something goes wrong while recording

| Problem | What to do |
|---|---|
| "The AWS credentials have expired" | Get new credentials from the workshop page; Faig redeploys with `scripts/deploy_aws.py`. |
| You refreshed and HISTORY is empty | Redo the preload (2 minutes). |
| An answer takes long | Cut the wait in editing. |
| The AI's wording differs from this script | Normal. The text varies a little between runs, but the verdicts and the numbers in the "Before → after" panel come from the rules and stay the same. |
