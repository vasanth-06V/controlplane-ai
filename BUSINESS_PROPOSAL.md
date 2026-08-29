# ControlPlane.ai — Business Proposal

**Accenture Innovation Challenge — Round 2**
Responsible AI Checker for Multi-Use-Case Enterprise GenAI Deployments

---

## 1. Problem Framing

Enterprises no longer run one AI system — they run a *portfolio*. A typical mid-to-large enterprise
today operates, concurrently:

- **Customer-facing assistants** (support chat, product Q&A) — real-time, high volume, brand and
  regulatory exposure on every message.
- **Internal copilots** (employee knowledge assistants, coding assistants, HR/IT helpdesks) — lower
  external exposure, but bad answers propagate into real employee decisions and actions.
- **Decision-support tools embedded in regulated workflows** (credit, hiring, clinical triage,
  underwriting) — lower volume, but each output can carry direct legal/financial/human liability.

Each of these has a different **risk signature**: different latency tolerance, different consequence
of a false allow vs. a false block, different regulatory exposure, and different quality of the
underlying data feeding the model. A single "AI firewall" tuned for one of these either:

- **over-flags** the low-stakes, high-volume surface (customer chat) — causing alert fatigue, users
  routing around warnings, and support teams tuning the checker down until it's ineffective, or
- **under-flags** the high-stakes, low-volume surface (decision-support) — creating exactly the kind
  of liability event (a biased or fabricated basis for a credit/hiring decision) that responsible-AI
  programs exist to prevent.

Compounding this: bias, hallucination, and privacy risk are **not cleanly separable**. A model
fabricating a customer's order history is a hallucination *and* a privacy incident if it invents
plausible-sounding personal details. A model justifying a decision with a stereotyped generalization
is a bias incident that may also be an unverifiable (hallucinated) claim about the individual. Tools
that force a single-category verdict lose this signal.

Finally, most enterprises do **not** control model internals — they consume GPT/Claude/Gemini/etc. via
API. Any checking layer has to work at the input/output boundary, has to tolerate "no ground truth
available" as a normal condition rather than an edge case, and has to be governed by policy that can
change as regulation and business context evolve — without redeploying the checker itself.

## 2. Solution Design

**ControlPlane.ai is a policy-governed checking layer, not a single classifier.** One detection engine,
many *policies*. The mechanism (detailed in [`README.md`](README.md)) has five parts:

1. **Parallel, category-specific detectors** (PII, hallucination, bias) that each return a score,
   a confidence level, and human-readable findings — never a bare pass/fail.
2. **A policy registry** that maps `(use_case, geography)` to: which detectors run, at what depth
   (fast/deep), how their scores are weighted into one overall score, and where the
   allow/edit/flag/block thresholds sit.
3. **Tiered decisioning with a repair path** — `edit` isn't just a softer `block`; it's an
   auto-redaction path that lets a response ship with the actual leak removed, which is the single
   biggest lever against alert fatigue: most PII incidents don't need a human, they need a redaction.
4. **An audit trail** that captures the full trace (every category's score, confidence, and finding)
   behind every decision, so any decision is explainable after the fact — required for both internal
   trust and external regulatory defensibility.
5. **A feedback loop** where human reviewer overrides become the raw material for threshold tuning —
   turning the "over- vs under-flagging" tradeoff from a one-time design choice into a monitored,
   adjustable operating parameter.

### Why this generalizes

Adding a fourth use case, a fourth geography, or a fourth risk category does not require new
architecture — it requires a new policy entry (config) or a new detector module implementing the same
`{category, score, confidence, findings}` interface the other three already implement. This is the
core design bet: **the risk landscape will keep changing (new regs, new model behaviors, new use
cases); the mechanism for governing it should not need to.**

## 3. Target Users

| User | What ControlPlane gives them |
|---|---|
| **Chief Risk / Responsible AI Officer** | A single governance surface and audit trail across every AI use case in the enterprise, instead of per-team bespoke guardrails |
| **AI/Platform Engineering team** | A drop-in gateway/middleware they integrate once per use case (policy key + API call), not a bespoke integration per team |
| **Compliance / Legal** | Policy-as-config that can be updated per geography/sector as regulation evolves, with a defensible audit trail per decision |
| **Human reviewers / trust & safety ops** | A prioritized review queue (only `flag_for_review`/`block` cases) instead of reviewing every interaction |
| **Product teams building on GenAI** | Confidence to ship faster because the risk conversation with Legal/Risk has a concrete, demonstrable control instead of a policy document |

## 4. Business Case & Impact

**Assumed operating scale** (per the brief's reference parameters, stated as assumptions): tens of
thousands of interactions/week across a handful of concurrent use cases, mixed governed/ungoverned
source data.

- **Liability avoidance is the primary value driver, not efficiency.** One prevented regulatory
  incident (a leaked SSN in a support transcript, a biased basis for a hiring recommendation) is worth
  more than the cumulative cost of running the checker for a year. This proposal treats ControlPlane as
  risk-transfer infrastructure, similar in kind to how a WAF or DLP tool is justified — not as a
  feature that needs to prove ROI per-interaction.
- **Alert-fatigue cost is real and is designed against directly.** The tiered `edit` path removes the
  majority of PII incidents from the human queue *by fixing them automatically*, and per-use-case
  thresholds mean the high-volume, lower-stakes chatbot doesn't drown reviewers in low-value flags
  from a policy tuned for the regulated workflow.
- **Review capacity becomes a plannable, policy-driven cost.** Because `human_review_required_above`
  is a policy field, the enterprise can directly trade off reviewer headcount against risk tolerance
  per use case — a lever that doesn't exist with a single global threshold.
- **Faster, safer AI adoption velocity.** New GenAI use cases can launch under a conservative default
  policy on day one and have thresholds relaxed as the feedback loop demonstrates low override/FN
  rates, instead of every new use case needing a bespoke safety review from scratch.

## 5. Phased Roadmap

**Phase 1 — Prototype (this submission)**
Core detection + policy engine + tiered decisioning + audit trail + feedback capture, running against
illustrative data. Validates the mechanism end to end.

**Phase 2 — Pilot-ready (next 1–2 quarters)**
- Real semantic retrieval (embedding-based, not TF-overlap) against an actual enterprise document
  store/RAG index for hallucination checking.
- Named-entity PII detection (person names, addresses) beyond structured-pattern matching, likely via
  a lightweight NER model, to close the gap the brief calls out ("a fabricated detail about a person...
  simultaneously hallucination and privacy").
- Multi-turn conversation state: carry risk signal across turns so a compounding pattern (a model
  slowly building a fabricated profile of a user across several turns) is caught even when no single
  turn crosses a threshold.
- Pluggable "AI-as-judge" detector using a secondary model call for cases the deep-pass heuristics
  flag as ambiguous, with its own latency budget and cost accounting per use case.
- Real integration harness: a middleware SDK (drop-in decorator/proxy) instead of a direct API call,
  so onboarding a new use case is a config change, not new integration code.

**Phase 3 — Production hardening (2–4 quarters)**
- Closed-loop threshold auto-tuning from the feedback signal (currently visible but manually applied).
- Agentic-action risk: extend from "checking generated text" to "checking a proposed tool call /
  action" before execution, for AI agents that act rather than just respond — this is explicitly the
  compounding-risk case the brief flags for multi-step agents.
- Formal false-positive/negative measurement against a labeled evaluation set per use case, reported
  to stakeholders as a trustworthiness scorecard (not just raw override counts).
- SOC2-style controls around the audit trail itself (immutability, retention policy, access control).
- Per-sector policy packs (finance, healthcare, HR) as a starting point library, not a from-scratch
  policy write for every new deployment.

## 6. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Heuristic detectors (regex/lexicon) miss novel phrasing** and give false confidence | Detectors report confidence, not just score; low-confidence "unverifiable" is a distinct signal from "confirmed risky," and Phase 2 upgrades detection quality without changing the policy/decisioning architecture around it |
| **Alert fatigue if thresholds are miscalibrated** | Tiered `edit` path absorbs the majority of low-severity PII cases without a human; feedback loop surfaces override rate as an explicit, monitored metric rather than letting drift go unnoticed |
| **Under-flagging in the highest-stakes use case** | `decision_support_regulated` policy is deliberately tuned conservative (lowest thresholds, lowest human-review bar) — the tuning philosophy trades reviewer load for liability reduction specifically where liability is highest |
| **Policy sprawl as use cases multiply** | Policy config is structured and versioned (`policy_version` stamped on every audit record); a Phase 3 policy-pack library reduces bespoke config per new deployment |
| **Latency budget breach under load** | Fast/deep tiering plus parallel detector execution keeps the default path cheap; the metrics dashboard tracks per-use-case latency so budget breaches are visible, not silent |
| **Reviewer queue overwhelmed despite tiering** | `human_review_required_above` is a per-policy dial specifically so review capacity can be planned and traded off against risk tolerance per use case |
| **Checker becomes a single point of failure / bottleneck** | Checker is stateless per request (SQLite here is a prototype choice; production would use an async queue + horizontally scaled workers) — architecture doesn't preclude scaling out |
| **Regulatory requirements outpace hard-coded rules** | Everything that would otherwise be a hard-coded rule (thresholds, weights, which detectors run, geo multipliers) lives in policy config, not detector code — the brief's "rigid rules age quickly" concern is the primary reason the architecture is split this way |

## 7. Why This Approach (vs. alternatives considered)

- **A single global classifier/threshold** was rejected — it cannot simultaneously satisfy a 300ms
  customer-chat budget and a conservative decision-support risk posture; the brief explicitly warns
  against one-size-fits-all checking.
- **Fully manual human review of all flagged content** was rejected as the default path — it doesn't
  scale to tens of thousands of interactions/week, and the auto-redact `edit` tier removes the need for
  a human on the most common failure mode (structured PII leakage).
- **Post-hoc audit only (no pre-response gate)** was rejected as the sole mechanism — it protects
  the audit trail but not the user, and the brief's real-world complexities section makes clear that a
  gate is needed for the customer-facing and regulated-workflow cases specifically. ControlPlane keeps
  post-hoc audit as a *complement* (every decision is logged), not a replacement for the gate.
