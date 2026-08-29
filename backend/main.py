import time
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from models import CheckRequest, CheckResponse, CategoryResult, FeedbackRequest
from policy import PolicyRegistry, decide
import audit
from detectors import pii, hallucination, bias

app = FastAPI(title="ControlPlane.ai", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

registry = PolicyRegistry()
audit.init_db()

BORDERLINE_LOW, BORDERLINE_HIGH = 0.35, 0.65

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
