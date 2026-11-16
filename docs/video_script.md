# Demo video: click-by-click script (about 5 minutes)

**Live app:** https://isybdeoz22wyqq4tccdermfuvq0zwugt.lambda-url.us-east-1.on.aws
It only works until the event's AWS account closes (Sunday about 11:30), so record before then.

## Before you record (not filmed)

**Keep this PDF open in a second window or on your phone. The script is not inside the app.**

### Step 1: Open and wake up the app
Open the live link above and wait about 10 seconds. The first load after a quiet period is slow; after that it's fast.

### Step 2: "Pre-click" the three analyses
Each analysis takes about 15 seconds. Run them once now, so during the video they reopen instantly from **History**.

**Pre-click A: Robert and Tesla**

1. Left menu, under **INVESTORS**: click **Robert, 59**.
2. Under the big question box: click the grey chip **TSLA · $60k from XBB**.
3. Wait until the answer shows the red tag **Inconsistent with profile**.

**Pre-click B: Mateo and J&J**

1. Left menu: click **Mateo, 41**.
2. Click the chip **JNJ · $8k new money**.
3. Wait until the answer shows the orange tag **With conditions**.

**Pre-click C: Compare**

1. Left menu: click **Compare investors**.
2. Click the chip **Put $2,000 of new money into Bitcoin.**
3. Wait until all four columns (Robert, Amira, Mateo, Maya) show a result.

**Check:** the left menu's **HISTORY** now lists *Robert · Everyone is talking about Tesla…* and *Mateo · Add $8,000…*. Clicking them reopens the answers instantly.

**Do not refresh or close the tab after this.** A refresh empties History, and you would have to pre-click again.

### Step 3: Set up the screen
- Chrome full screen, zoom 110% (Cmd +), other tabs closed, notifications off.
- Never show the terminal or anything with AWS keys.

### Step 4: Record
1. Press **Cmd + Shift + 5**, choose **Record Entire Screen** (or the Chrome window), then click **Record**.
2. Follow the scenes below. When a scene says *click the chip…* for Robert's Tesla or Mateo's J&J, click its entry in **HISTORY** instead, so it opens instantly.
3. Stop with the ⏹ button in the top menu bar. The video is saved to your Desktop.

Say "simulation", never "recommendation".

---

## Scene 1: The problem (0:00–0:25)

**Screen:** the app home page with **Robert, 59** selected (left menu → Investors → Robert).

**Say:**
> "Self-directed investors have more data than ever, but nobody tells them when an idea doesn't fit *them*. The challenge asks: can a system push back when a request conflicts with the investor's profile, instead of simply agreeing? This is SecondLook."

**Point at:** Robert's tags (low-moderate risk, 3–5 years horizon), then scroll to **Robert's portfolio today** (risk used 56% of 65% allowed, $385,000 portfolio).

## Scene 2: How it works (0:25–0:55)

**Click:** **How it works** in the left menu. Scroll slowly through the first two sections. (Or show `docs/architecture.png` for a few seconds.)

**Say:**
> "Nine AI agents on Amazon Bedrock each have one job: read the request, check the profile, analyse the market impact, argue for and against in a debate, check the rules, and write the verdict. The key design choice is that the AI never invents numbers. Plain code computes every figure from the official starter data, and a rules engine caps the verdict: the AI can be stricter than the rules, never more lenient."

## Scene 3: Robert wants Tesla (0:55–2:00)

**Click:** **Check an idea** → Robert → the chip **TSLA · $60k from XBB** (or reopen it from History).

**While the agents run, say:**
> "Robert is 59, low-to-moderate risk, a few years from retirement, and everyone is talking about Tesla."

**When the answer appears, point at, in order:**
1. The red tag **Inconsistent with profile**, and the headline.
2. The **Before → after this idea** panel:
   > "His retirement money would go from 56% to 111% of S&P 500-equivalent risk, against a 65% limit, and Tesla would become 15.6% of his portfolio, above his 10% single-stock limit."
3. **How the agents reached this:** the row of agent steps with their timings.
4. **Versions of this idea that would change the verdict:**
   > "SecondLook also recomputes other versions of the same idea. A $10,000 version fits his limits, but still conflicts with his preference for stable companies. This is information, not advice."
5. Click **Why this verdict, and what would change it** to open it, show it for 2 seconds, then close it.

## Scene 4: What-if simulator (2:00–2:35)

**Click:** the **What-if simulator** tab.

**Do:**
1. Drag **Amount** slowly from $60,000 down to **$10,000**. The verdict flips from **Inconsistent** to **With conditions**.
   > "Every change is recomputed instantly by the rules engine, with no AI needed."
2. Drag the amount back to $60,000, then change **Asset** to **SPY · SPDR S&P 500 ETF Trust**. The verdict flips to **Consistent**.
   > "The same $60,000 in the whole S&P 500, instead of one volatile stock, fits his profile."

## Scene 5: Follow-up chat (2:35–3:00)

**Do:** go back to the **Overview** tab and scroll to **Ask a follow-up about this answer**. Type **Should I buy Apple instead?** and click **Ask**.

**Say:**
> "You can ask follow-up questions. The chat answers only from this analysis, and what-if questions like this one are computed by the rules engine, not guessed by the AI. Here's the instant check, and a button to run the full analysis."

(Optional: click the chip **How did this do in 2022?**)

## Scene 6: Same idea, four investors (3:00–3:40)

**Click:** **Compare investors** → the chip **Put $2,000 of new money into Bitcoin.**

**Say, pointing at each column:**
> "The challenge asks to show adaptation to context. Same idea, four different answers. **Amira**, 26 and high risk: consistent, because it's a small slice of long-term money. **Robert** and **Mateo**: consistent with conditions, because it conflicts with their stated preferences. **Maya**, saving for a condo: inconsistent, because it would push her small retirement pot over its risk limit. And high risk isn't 'anything goes': Amira's $15,000 NVIDIA idea breaks her own limits."

## Scene 7: Mateo and ESG (3:40–4:10)

**Click:** left menu → **Mateo, 41** → chip **JNJ · $8k new money** (or reopen it from History). When it loads, click the **About JNJ** tab.

**Say:**
> "Mateo cares about ESG. We went beyond the starter data: from a public SEC filing, we know which US companies Vanguard's ESG fund actually holds. Johnson & Johnson is excluded, so SecondLook flags a conflict with his wish to avoid controversial companies. And it's honest: the filing doesn't say why it's excluded, and Canadian stocks aren't covered."

## Scene 8: Trust and AWS (4:10–4:40)

**Click:** the **Evidence & audit** tab.

**Point at:** **Numbers verified**, **Bedrock Guardrail**, **AI agent calls**, **Audit record: Saved to S3**.

**Say:**
> "Every run is auditable. Every percentage and dollar figure the agents write is checked against the data, a Bedrock Guardrail screens the output for things like guaranteed returns, and the full trace of every agent is saved to Amazon S3. The app itself runs on AWS Lambda."

(Optional, 5 seconds: click **Create your own investor** in the left menu to show the form: "Anyone can build their own investor and test ideas against it.")

## Scene 9: Results and close (4:40–5:00)

**Screen:** back to Robert's Tesla answer, or `docs/evaluation.md`.

**Say:**
> "We tested it on 36 live runs, including a prompt-injection attempt: every verdict matched what the profile implies, none was more lenient than the rules allow, and repeats were stable. SecondLook is an educational simulation, not financial advice. It's a second look before you act."

---

## If something goes wrong while recording

| Problem | What to do |
|---|---|
| "The AWS credentials have expired" | Get new credentials from the workshop page and redeploy with `scripts/deploy_aws.py`, or record on a laptop running the app locally. |
| An answer takes long | Cut the wait in editing, or reopen the pre-run analysis from **History**. |
| The AI's wording differs from this script | Normal. The text varies a little between runs, but the verdicts and the numbers in the "Before → after" panel come from the rules and stay the same. |
