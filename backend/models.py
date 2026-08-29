from typing import Optional, Literal
from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    use_case: str = Field(..., description="Key into the policy registry, e.g. 'customer_support_chatbot'")
    prompt: str = Field(..., description="The user-facing input that produced the AI response")
    response: str = Field(..., description="The AI-generated response to evaluate")
    geo: str = Field(default="DEFAULT", description="Geography key for policy overrides, e.g. 'EU'")
    conversation_id: Optional[str] = Field(default=None, description="Groups turns of a multi-turn conversation")


class CategoryResult(BaseModel):
    category: str
    score: float
    confidence: float
    depth_used: Literal["fast", "deep", "skipped"]
    findings: list[str]
    redacted_text: Optional[str] = None


class CheckResponse(BaseModel):
    check_id: str
    use_case: str
    decision: Literal["allow", "edit", "flag_for_review", "block"]
    overall_score: float
    latency_ms: float
    categories: list[CategoryResult]
    final_text: str
    human_review_required: bool
    explanation: list[str]
    policy_version: str


class FeedbackRequest(BaseModel):
    check_id: str
    reviewer: str
    correct_decision: Literal["allow", "edit", "flag_for_review", "block"]
    notes: Optional[str] = None
