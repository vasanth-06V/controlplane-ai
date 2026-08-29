import time
import json
import asyncio
from collections import defaultdict, Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from models import CheckRequest, CheckResponse, CategoryResult, FeedbackRequest
from policy import PolicyRegistry, decide
import audit
from detectors import pii, hallucination, bias
from seed_data import SEED_CHECKS

app = FastAPI(title="ControlPlane.ai", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

registry = PolicyRegistry()
audit.init_db()

BORDERLINE_LOW, BORDERLINE_HIGH = 0.35, 0.65

# Illustrative, stated assumption (see BUSINESS_PROPOSAL.md): average avoided-incident
# cost per use case, used only to turn "checks that were edited or blocked" into a
# directional cost-avoidance figure for the business dashboard. Not a measured value.
COST_AVOIDANCE_USD = {
    "customer_support_chatbot": 120,
    "internal_knowledge_copilot": 600,
    "decision_support_regulated": 4000,
}

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/api/use-cases")
def list_use_cases():
    return registry.list_use_cases()


@app.get("/api/policies")
def get_policies():
    return {"version": registry.version, "use_cases": registry.use_cases, "geo_overrides": registry.geo_overrides}


async def _run_detector(fn, *args, depth: str, **kwargs):
    return await asyncio.to_thread(fn, *args, depth=depth, **kwargs)


@app.post("/api/check", response_model=CheckResponse)
async def check(req: CheckRequest):
    t0 = time.perf_counter()
    try:
        policy = registry.get(req.use_case)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    detectors_cfg = policy["detectors"]
    severity_mult = registry.severity_multiplier(req.geo)

    tasks = {}
    if detectors_cfg.get("pii", {}).get("enabled"):
        depth = detectors_cfg["pii"]["depth"]
        tasks["pii"] = _run_detector(pii.run, req.response, depth=depth, severity_multiplier=severity_mult)
    if detectors_cfg.get("hallucination", {}).get("enabled"):
        depth = detectors_cfg["hallucination"]["depth"]
        tasks["hallucination"] = _run_detector(hallucination.run, req.response, depth=depth)
    if detectors_cfg.get("bias", {}).get("enabled"):
        depth = detectors_cfg["bias"]["depth"]
        tasks["bias"] = _run_detector(bias.run, req.response, depth=depth)

    results = dict(zip(tasks.keys(), await asyncio.gather(*tasks.values())))

    # Tiered latency-aware escalation: a fast-path hallucination score that
    # lands in the borderline band gets re-run at full depth, since a wrong
    # answer here is exactly the "confidently unclear" case that's cheapest
    # to double-check and costliest to get wrong.
    if "hallucination" in results and results["hallucination"]["depth_used"] == "fast":
        score = results["hallucination"]["score"]
        if BORDERLINE_LOW <= score <= BORDERLINE_HIGH:
            deep_result = await _run_detector(hallucination.run, req.response, depth="deep")
            deep_result["findings"].insert(0, "Escalated from fast to deep check: fast-pass score was borderline")
            results["hallucination"] = deep_result

    weights = policy["category_weights"]
    overall = sum(results[cat]["score"] * weights.get(cat, 0) for cat in results)
    overall = round(min(1.0, overall), 3)

    thresholds = policy["thresholds"]
    decision = decide(overall, thresholds)

    human_review_required = (
        decision in ("flag_for_review", "block")
        or overall >= policy.get("human_review_required_above", 1.1)
    )

    final_text = req.response
    explanation = [f"Policy '{policy['label']}' (v{registry.version}) evaluated {len(results)} categories."]
    for cat, res in results.items():
        explanation.append(
            f"{cat}: score={res['score']} (weight {weights.get(cat,0)}, depth={res['depth_used']}) — {res['findings'][0]}"
        )
        if res.get("redacted_text") and decision in ("edit", "flag_for_review"):
            final_text = res["redacted_text"]
            explanation.append(f"{cat}: applied auto-redaction to output text.")

    explanation.append(f"Weighted overall score {overall} -> decision '{decision}'.")
    if human_review_required:
        explanation.append("Routed to human review queue.")
    if decision == "block":
        final_text = "[Response withheld by ControlPlane.ai — blocked pending review]"

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    check_id = audit.new_id()

    categories_payload = [
        CategoryResult(
            category=cat,
            score=res["score"],
            confidence=res["confidence"],
            depth_used=res["depth_used"],
            findings=res["findings"],
            redacted_text=res.get("redacted_text"),
        )
        for cat, res in results.items()
    ]

    audit.log_check(
        check_id=check_id, use_case=req.use_case, geo=req.geo,
        conversation_id=req.conversation_id, prompt=req.prompt, response=req.response,
        overall_score=overall, decision=decision, human_review_required=human_review_required,
        latency_ms=latency_ms, policy_version=registry.version,
        categories=[c.model_dump() for c in categories_payload], final_text=final_text,
    )

    return CheckResponse(
        check_id=check_id, use_case=req.use_case, decision=decision, overall_score=overall,
        latency_ms=latency_ms, categories=categories_payload, final_text=final_text,
        human_review_required=human_review_required, explanation=explanation,
        policy_version=registry.version,
    )


@app.on_event("startup")
async def seed_demo_data_if_empty():
    if audit.get_metrics()["total_checks"] > 0:
        return
    results = []
    for example in SEED_CHECKS:
        results.append(await check(CheckRequest(**example)))

    # Seed a realistic MIX of reviewer feedback: some confirmations (reviewer
    # agrees with ControlPlane's decision) and some overrides (reviewer
    # disagrees). Seeding only overrides would pin the override rate at a
    # misleading 100% on first load, which misrepresents the checker as
    # always wrong rather than showing what the metric actually tracks.
    audit.log_feedback(
        results[0].check_id, "demo-reviewer", "block",
        "Card number should have been blocked outright, not just flagged.",
    )
    audit.log_feedback(
        results[1].check_id, "demo-reviewer", results[1].decision,
        "Agreed — response is accurate and matches the product spec sheet.",
    )
    audit.log_feedback(
        results[3].check_id, "demo-reviewer", results[3].decision,
        "Agreed — hallucinated PTO figures correctly flagged for edit.",
    )
    audit.log_feedback(
        results[6].check_id, "demo-reviewer", "block",
        "Biased justification for a lending decision should be blocked, not just reviewed.",
    )


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    audit.log_feedback(req.check_id, req.reviewer, req.correct_decision, req.notes)
    return {"status": "recorded"}


@app.get("/api/checks")
def checks(limit: int = 50, use_case: str | None = None):
    return audit.get_recent_checks(limit=limit, use_case=use_case)


@app.get("/api/metrics")
def metrics():
    return audit.get_metrics()


@app.get("/api/business-metrics")
def business_metrics():
    rows = audit.get_all_checks_raw(limit=5000)
    total = len(rows)

    if total == 0:
        return {
            "kpis": {
                "total_interactions": 0, "use_cases_covered": 0,
                "auto_remediated_rate": None, "human_review_rate": None,
                "block_rate": None, "allow_rate": None, "avg_overall_risk_score": None,
                "override_rate": None, "estimated_incidents_prevented": 0,
                "estimated_cost_avoided_usd": 0, "latency_sla_compliance_pct": None,
            },
            "risk_by_use_case": [], "risk_heatmap": [], "category_averages": {},
            "decision_trend": [], "latency_compliance": [], "top_findings": [],
        }

    decision_counts = Counter(r["decision"] for r in rows)
    use_cases_seen = set(r["use_case"] for r in rows)
    human_review_count = sum(1 for r in rows if r["human_review_required"])
    avg_score = round(sum(r["overall_score"] for r in rows) / total, 3)

    incidents_prevented = decision_counts.get("edit", 0) + decision_counts.get("block", 0)
    cost_avoided = sum(
        COST_AVOIDANCE_USD.get(r["use_case"], 250)
        for r in rows if r["decision"] in ("edit", "block")
    )

    latency_hits, latency_total = 0, 0
    per_uc_latency = defaultdict(list)
    per_uc_scores = defaultdict(list)
    per_uc_decisions = defaultdict(Counter)
    category_scores = defaultdict(list)
    heatmap_scores = defaultdict(lambda: defaultdict(list))
    finding_counter = Counter()
    trend = defaultdict(Counter)

    for r in rows:
        uc = r["use_case"]
        per_uc_latency[uc].append(r["latency_ms"])
        per_uc_scores[uc].append(r["overall_score"])
        per_uc_decisions[uc][r["decision"]] += 1
        trend[r["created_at"][:10]][r["decision"]] += 1

        try:
            budget = registry.get(uc).get("latency_budget_ms")
        except KeyError:
            budget = None
        if budget:
            latency_total += 1
            if r["latency_ms"] <= budget:
                latency_hits += 1

        for cat in json.loads(r["categories_json"]):
            category_scores[cat["category"]].append(cat["score"])
            heatmap_scores[uc][cat["category"]].append(cat["score"])
            for finding in cat["findings"]:
                if finding.startswith("No ") or finding.startswith("Best-matching source") or finding.startswith("Escalated"):
                    continue
                finding_counter[finding.split(" x")[0].split(':')[0][:70]] += 1

    risk_by_use_case = []
    for uc, scores in per_uc_scores.items():
        label = registry.use_cases.get(uc, {}).get("label", uc)
        n = len(scores)
        risk_by_use_case.append({
            "use_case": uc, "label": label, "checks": n,
            "avg_score": round(sum(scores) / n, 3),
            "block_rate": round(per_uc_decisions[uc].get("block", 0) / n, 3),
            "human_review_rate": round(
                sum(1 for row in rows if row["use_case"] == uc and row["human_review_required"]) / n, 3
            ),
        })

    risk_heatmap = [
        {"use_case": uc, "category": cat, "avg_score": round(sum(v) / len(v), 3)}
        for uc, cats in heatmap_scores.items() for cat, v in cats.items()
    ]

    category_averages = {cat: round(sum(v) / len(v), 3) for cat, v in category_scores.items()}

    decision_trend = [
        {"date": date, **{d: counts.get(d, 0) for d in ("allow", "edit", "flag_for_review", "block")}}
        for date, counts in sorted(trend.items())
    ]

    latency_compliance = []
    for uc, latencies in per_uc_latency.items():
        try:
            budget = registry.get(uc).get("latency_budget_ms")
        except KeyError:
            budget = None
        compliant = sum(1 for l in latencies if budget and l <= budget)
        latency_compliance.append({
            "use_case": uc,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "budget_ms": budget,
            "compliant_pct": round(compliant / len(latencies) * 100, 1) if budget else None,
        })

    top_findings = [{"finding": f, "count": c} for f, c in finding_counter.most_common(8)]

    feedback_metrics = audit.get_metrics()

    return {
        "kpis": {
            "total_interactions": total,
            "use_cases_covered": len(use_cases_seen),
            "auto_remediated_rate": round(decision_counts.get("edit", 0) / total, 3),
            "human_review_rate": round(human_review_count / total, 3),
            "block_rate": round(decision_counts.get("block", 0) / total, 3),
            "allow_rate": round(decision_counts.get("allow", 0) / total, 3),
            "avg_overall_risk_score": avg_score,
            "override_rate": feedback_metrics["override_rate"],
            "estimated_incidents_prevented": incidents_prevented,
            "estimated_cost_avoided_usd": cost_avoided,
            "latency_sla_compliance_pct": round(latency_hits / latency_total * 100, 1) if latency_total else None,
        },
        "risk_by_use_case": risk_by_use_case,
        "risk_heatmap": risk_heatmap,
        "category_averages": category_averages,
        "decision_trend": decision_trend,
        "latency_compliance": latency_compliance,
        "top_findings": top_findings,
    }
