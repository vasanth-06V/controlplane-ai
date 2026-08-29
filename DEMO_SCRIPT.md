# Demo Video Script (~3 minutes)

Record your screen at `http://127.0.0.1:8000` after running:

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --app-dir backend
```

## Beats

**0:00–0:20 — The problem (talk over the Policy Registry tab)**
"Enterprises run multiple AI use cases at once — a customer chatbot, an internal copilot, a regulated
decision-support tool — each with a different risk tolerance and latency budget. ControlPlane.ai is
one checking engine governed by per-use-case policy, not a one-size-fits-all filter." Show the Policy
Registry tab briefly to establish the three profiles and their different weights/thresholds.

**0:20–1:10 — Customer chatbot: PII + hallucination together**
Go to Live Console → select "Customer-Facing Support Chatbot" → click "Load example" until the refund
example loads (card number + false "100% refund, no questions asked" claim) → Run check.
Narrate the result: PII detector caught and auto-redacted the card number; hallucination detector
escalated from a fast pass to a deep pass because the score was borderline, then found the specific
claim unsupported against the actual refund policy document. Point out the decision:
`flag_for_review`, routed to human review, with the final text already redacted.

**1:10–1:50 — Internal copilot: a plausible-sounding but wrong internal fact**
Load the PTO example under "Internal Employee Knowledge Copilot" → Run check. Narrate: no PII risk
here, but the hallucination detector — running at full "deep" depth for this use case because bad
internal facts propagate into real employee decisions — checked "25 days PTO, no waiting period"
against the actual PTO policy doc and found it unsupported.

**1:50–2:30 — Decision-support: bias**
Load the loan-committee example under "Decision-Support Tool" → Run check. Narrate: the bias detector
caught the stereotyped generalization tied to a protected attribute; this use case's policy has the
tightest thresholds and the lowest human-review bar of the three, by design — under-flagging here is
the real liability.

**2:30–2:50 — Feedback loop + metrics**
Submit a reviewer override on one of the results → switch to the Metrics tab → show the override rate,
false-positive/negative-like counts, and per-use-case latency. Narrate: this is how the
over-flag/under-flag tradeoff gets tuned over time instead of guessed once.

**2:50–3:00 — Close**
"Full detection trace, per-decision audit trail, and policy config are in the GitHub repo, along with
the business case and roadmap." Show the Audit Log tab briefly.

## Recording tips
- Any free screen recorder works: Windows Game Bar (`Win+G`), OBS Studio, or the browser's own
  screen-capture. No special tooling required.
- Zoom the browser to ~110% before recording so on-screen text reads clearly in a compressed video.
- Keep total runtime under 3–4 minutes — judges skim.
