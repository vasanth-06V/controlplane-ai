# Demo Video Script — ControlPlane.ai (~4–5 minutes)

Word-for-word narration + exact copy-paste inputs, so you can record without improvising. Every
prompt/response pair below is ready to paste directly into the Live Console fields.

## Setup (before you hit record)

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --app-dir backend
```

- Open **http://127.0.0.1:8000** in a clean browser window (no other tabs visible).
- Zoom to ~110% (`Ctrl` + `+` a couple of times) so on-screen text reads clearly once compressed.
- If you've run checks before, it's fine to leave the seeded demo data in — the trend/heatmap charts
  look better with more data points, not fewer.
- Do one silent dry run first so you're not reading this live.

---

## Scene 1 — The problem (0:00–0:25)

**Action:** Open on the **Policy Registry** tab. Let it sit on screen while you talk.

**Say:**
> "Enterprises don't run one AI system — they run a portfolio. A customer support chatbot, an
> internal employee copilot, a decision-support tool inside a regulated workflow. Each of these has
> a different risk tolerance and a different latency budget. A single, one-size-fits-all AI checker
> either over-flags the high-volume chatbot and gets ignored, or under-flags the regulated tool and
> creates real liability. ControlPlane.ai's answer: one detection engine, governed by per-use-case
> policy — not a single global filter."

**Action:** Scroll the policy JSON briefly to show the three `use_cases` blocks and their different
`thresholds` / `category_weights` / `latency_budget_ms`.

---

## Scene 2 — Customer chatbot: PII + hallucination caught together (0:25–1:20)

**Action:** Click **Live Console**. Set:
- Use case: `Customer-Facing Support Chatbot (real_time)`
- Geography: `Default`

**Paste into User prompt:**
```
Can I get a refund on my annual subscription I bought 20 days ago?
```

**Paste into AI response to evaluate:**
```
Sure! Since you're within 14 days of your subscription purchase, you're fully eligible for a 100% refund, no questions asked. Just email me your card number 4111 2222 3333 4444 and I'll process it in the next hour.
```

**Action:** Click **Run ControlPlane check**.

**Say (while pointing at the result panel):**
> "Two things are wrong with this response, and ControlPlane catches both at once. First, the PII
> detector caught a live card number and auto-redacted it — you can see the final text now reads
> 'REDACTED_CREDIT_CARD' instead of blocking the whole message outright. Second, the hallucination
> detector's fast pass came back borderline, so it automatically escalated to a deep pass — that
> deep pass checked the specific claim against our actual refund policy document and found it
> unsupported: the real policy is 14 days for a partial refund, not a blanket 100% refund. Because
> both risks stack, the overall score crosses into 'flag for review' and it's routed to a human."

---

## Scene 3 — Internal copilot: a confident, wrong internal fact (1:20–2:00)

**Action:** Change use case to `Internal Employee Knowledge Copilot (interactive)`.

**Paste into User prompt:**
```
How much PTO do new hires get and when can they use it?
```

**Paste into AI response to evaluate:**
```
New employees accrue 25 days of PTO per year and can start using it immediately from day one, no waiting period required.
```

**Action:** Run the check.

**Say:**
> "No PII risk here — but this use case runs hallucination checks at full depth by default, because
> a wrong internal 'fact' from a copilot propagates straight into an employee's real decisions. The
> actual PTO policy is 18 days with a 90-day waiting period — this response invents both numbers.
> Notice this use case's policy weights hallucination higher than the other two, specifically because
> that's the failure mode that matters most here."

---

## Scene 4 — Decision-support: a biased justification (2:00–2:40)

**Action:** Change use case to `Decision-Support Tool (Regulated Workflow) (batch_or_gated)`.

**Paste into User prompt:**
```
Summarize the applicant's risk profile for the loan committee.
```

**Paste into AI response to evaluate:**
```
Given the applicant is a woman, she is naturally less reliable with financial planning, so this should be flagged as a high risk applicant regardless of her credit score of 780.
```

**Action:** Run the check.

**Say:**
> "This is a bias case — a protected attribute used to justify a stereotyped conclusion, overriding
> an objectively strong credit score. This use case has the tightest thresholds and the lowest
> human-review bar of the three, on purpose: under-flagging in a regulated decision workflow is the
> real liability, so we deliberately accept more reviewer load here in exchange for catching more."

---

## Scene 5 — Proof it's not just block-happy (2:40–3:00)

**Action:** Keep the same use case or switch back to the chatbot. 

**Paste into User prompt:**
```
What's the battery life on the X1?
```

**Paste into AI response to evaluate:**
```
The X1 device has a battery life of 12 hours under normal usage and supports Wi-Fi 6 and Bluetooth 5.2, with an IP54 water resistance rating.
```

**Action:** Run the check.

**Say:**
> "And when a response is actually clean and grounded — this one matches the real product spec sheet
> word for word — it comes back as a plain 'allow' in milliseconds. That matters as much as catching
> the bad ones: a checker that flags everything is exactly what causes alert fatigue and gets turned
> off."

---

## Scene 6 — Business Dashboard (3:00–3:40)

**Action:** Click **Business Dashboard**. Scroll slowly top to bottom: KPI tiles → risk-by-use-case
table → risk heatmap → decision trend → latency-vs-SLA chart → top findings.

**Say:**
> "This is the view for a risk officer, not an engineer. Total interactions, how many needed a
> human, how many were auto-remediated without one, an illustrative cost-avoided estimate, and
> latency SLA compliance per use case. The heatmap shows exactly where risk concentrates — here,
> hallucination is clearly the dominant risk for the internal copilot, PII for the customer chatbot.
> That's a governance conversation you can now have with actual numbers instead of a policy
> document."

---

## Scene 7 — Feedback loop (3:40–4:00)

**Action:** Go back to **Live Console**, scroll to the last result, set "actual correct decision" to
something different from what ControlPlane returned (e.g. `block`), click **Submit override**. Then
flip to **Detection Metrics** and point at the override rate / FP-like / FN-like counts.

**Say:**
> "Every decision can be corrected by a human reviewer, and that correction feeds straight into the
> override rate and false-positive/negative-like counts. This is how the over-flag versus
> under-flag tradeoff gets tuned over time from real feedback, instead of guessed once and left
> alone."

---

## Scene 8 — Close (4:00–4:15)

**Action:** Show **Audit Log** briefly (every check, timestamped, with decision and latency), then
cut back to the repo / README in an editor or GitHub tab.

**Say:**
> "Every decision here is logged with its full score trace and is fully explainable after the fact.
> The complete source, the business case, and the roadmap are all in the GitHub repo linked below."

---

## Recording tips

- Any free screen recorder works: Windows Game Bar (`Win+G`), OBS Studio, or the browser's own
  screen-capture. No special tooling required.
- Use the copy-paste blocks above verbatim — typing live on camera is slow and error-prone.
- If you fumble a line, just pause, retake that sentence, and trim the pause in editing (or don't
  bother trimming — judges care about substance, not polish).
- Keep total runtime under 5 minutes.
- Export at 1080p if your recorder supports it; text needs to be legible when judges watch on a
  laptop.
