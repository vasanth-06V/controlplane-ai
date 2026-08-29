"""
Hallucination / groundedness detector.

There is rarely a reliable real-time ground truth to check a claim against —
the brief calls this out explicitly. This detector doesn't pretend to solve
that: it does retrieval verification against whatever source documents ARE
available (knowledge_base/*.txt, standing in for an internal doc store or
RAG index), and *separately* reports when confidence is low because nothing
relevant was retrieved at all ("unverifiable", not "false"). That distinction
is surfaced to the caller instead of collapsed into a single score.

depth="fast": cheap keyword-overlap check against the single best-matching
              document only (bounded cost, used on the real-time path).
depth="deep": full corpus retrieval + per-claim (sentence-level) verification
              + a rule-based stand-in for an "AI-as-judge" pass that flags
              specific unsupported factual assertions (numbers/dates/named
              entities) even when overall topic overlap looks fine.
"""
import re
import glob
import os
import math
from collections import Counter

_KB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base")

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
    "and", "or", "it", "this", "that", "with", "as", "by", "be", "has", "have",
    "at", "from", "will", "can", "may", "your", "you", "our", "we", "not", "no",
}

_CLAIM_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s?(%|percent|days?|hours?|years?|months?|weeks?|grams?|degrees?|business days?)\b"
    r"|\b\d{1,4}[/-]\d{1,4}([/-]\d{2,4})?\b"
    r"|\$\d+(\.\d+)?",
    re.IGNORECASE,
)


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9%]+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def _load_corpus() -> list[tuple[str, str]]:
    docs = []
    for path in glob.glob(os.path.join(_KB_DIR, "*.txt")):
        with open(path, "r", encoding="utf-8") as f:
            docs.append((os.path.basename(path), f.read()))
    return docs


_CORPUS = _load_corpus()


def _cosine_overlap(a_tokens: list[str], b_tokens: list[str]) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    ca, cb = Counter(a_tokens), Counter(b_tokens)
    common = set(ca) & set(cb)
    dot = sum(ca[w] * cb[w] for w in common)
    norm_a = math.sqrt(sum(v * v for v in ca.values()))
    norm_b = math.sqrt(sum(v * v for v in cb.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _best_match(response_tokens: list[str]) -> tuple[str, float, str]:
    best_doc, best_score, best_text = "", 0.0, ""
    for name, text in _CORPUS:
        score = _cosine_overlap(response_tokens, _tokenize(text))
        if score > best_score:
            best_doc, best_score, best_text = name, score, text
    return best_doc, best_score, best_text


def _extract_claims(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if _CLAIM_PATTERN.search(s)]


def _claim_supported(claim: str, source_text: str) -> bool:
    # A claim is "supported" if its numeric/date tokens AND enough of its
    # surrounding wording actually appear in the retrieved source text.
    claim_numbers = set(re.findall(r"\d+(?:\.\d+)?", claim))
    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source_text))
    if claim_numbers and not (claim_numbers & source_numbers):
        return False
    overlap = _cosine_overlap(_tokenize(claim), _tokenize(source_text))
    return overlap >= 0.25


def run(response_text: str, depth: str) -> dict:
    response_tokens = _tokenize(response_text)
    findings: list[str] = []

    if not _CORPUS:
        return {
            "category": "hallucination",
            "score": 0.4,
            "confidence": 0.2,
            "depth_used": depth,
            "findings": ["No reference knowledge base available — groundedness unverifiable"],
            "redacted_text": None,
        }

    best_doc, best_score, best_text = _best_match(response_tokens)

    if best_score < 0.08:
        # No relevant source retrieved at all: this is the "no ground truth
        # available" case from the brief. We do NOT call this a hallucination
        # outright — we flag it as unverifiable with lower confidence so the
        # policy layer can decide how conservative to be.
        return {
            "category": "hallucination",
            "score": 0.55,
            "confidence": 0.35,
            "depth_used": depth,
            "findings": ["No matching source document retrieved — claims are unverifiable, not confirmed false"],
            "redacted_text": None,
        }

    topic_risk = max(0.0, 1.0 - best_score) * 0.6
    findings.append(f"Best-matching source: {best_doc} (topical overlap {best_score:.2f})")

    if depth == "fast":
        score = round(min(1.0, topic_risk), 3)
        confidence = 0.5
        return {
            "category": "hallucination",
            "score": score,
            "confidence": confidence,
            "depth_used": depth,
            "findings": findings,
            "redacted_text": None,
        }

    # Deep pass: per-claim verification against the full corpus (not just the
    # best doc) — a specific fact might be grounded in a different document.
    claims = _extract_claims(response_text)
    unsupported = []
    full_corpus_text = " ".join(text for _, text in _CORPUS)
    for claim in claims:
        if not _claim_supported(claim, full_corpus_text):
            unsupported.append(claim)

    if claims:
        unsupported_ratio = len(unsupported) / len(claims)
        findings.append(f"{len(unsupported)}/{len(claims)} specific factual claims unsupported by any source document")
        for c in unsupported[:3]:
            findings.append(f"Unsupported claim: \"{c}\"")
        claim_risk = unsupported_ratio * 0.9
    else:
        claim_risk = 0.0
        findings.append("No specific numeric/date claims detected to verify")

    score = round(min(1.0, max(topic_risk, claim_risk)), 3)
    confidence = 0.85

    return {
        "category": "hallucination",
        "score": score,
        "confidence": confidence,
        "depth_used": depth,
        "findings": findings,
        "redacted_text": None,
    }
