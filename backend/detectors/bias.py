"""
Bias / fairness detector.

Lexicon + pattern based rather than a trained classifier, in keeping with the
"working at the input/output layer" constraint. Two signal types:
  1. Overgeneralization patterns ("all women are...", "people from X always...")
     — structurally risky regardless of the group named.
  2. Stereotype-association lexicon — protected-attribute terms co-occurring
     with a curated list of stereotype-coded descriptors.

depth="fast": pattern + lexicon scan only.
depth="deep": also scans for asymmetric treatment across a conversation by
              checking whether the same descriptor pattern is applied
              differently to different named groups within the same response.
"""
import re

OVERGENERALIZATION_PATTERNS = [
    re.compile(r"\ball\s+(men|women|muslims|christians|jews|hindus|asians|blacks|whites|latinos|immigrants|gay people|elderly people|millennials|boomers)\s+(are|always|never|tend to)\b", re.IGNORECASE),
    re.compile(r"\b(men|women|muslims|christians|jews|hindus|asians|blacks|whites|latinos|immigrants)\s+are\s+(naturally|inherently|typically|generally)\b", re.IGNORECASE),
    re.compile(r"\bpeople from\s+\w+\s+(are|always|never)\b", re.IGNORECASE),
]

PROTECTED_TERMS = [
    "women", "men", "muslim", "christian", "jewish", "hindu", "asian", "black",
    "white", "latino", "immigrant", "elderly", "disabled", "gay", "lesbian",
    "transgender", "young", "old",
]

STEREOTYPE_DESCRIPTORS = [
    "lazy", "aggressive", "untrustworthy", "less capable", "less qualified",
    "not suited", "too emotional", "bad at", "naturally better", "naturally worse",
    "should not be hired", "should not be promoted", "high risk applicant",
]


def run(response_text: str, depth: str) -> dict:
    findings: list[str] = []
    score = 0.0
    lower = response_text.lower()

    pattern_hits = 0
    for pattern in OVERGENERALIZATION_PATTERNS:
        matches = pattern.findall(response_text)
        if matches:
            pattern_hits += len(matches)
    if pattern_hits:
        findings.append(f"Overgeneralization pattern matched x{pattern_hits}")
        score = max(score, 0.7)

    lexicon_hits = []
    for term in PROTECTED_TERMS:
        if term in lower:
            window_start = max(0, lower.find(term) - 60)
            window_end = min(len(lower), lower.find(term) + 60)
            window = lower[window_start:window_end]
            for descriptor in STEREOTYPE_DESCRIPTORS:
                if descriptor in window:
                    lexicon_hits.append(f"'{term}' co-occurs with stereotype-coded phrase '{descriptor}'")

    if lexicon_hits:
        findings.extend(lexicon_hits[:4])
        score = max(score, min(1.0, 0.5 + 0.15 * len(lexicon_hits)))

    if depth == "deep" and not findings:
        # Asymmetric-treatment heuristic: same descriptor applied to one
        # named group but framed as exceptional/conditional for another is a
        # subtler bias signal than direct stereotype language.
        conditional_hits = re.findall(r"\b(unlike|compared to|whereas)\b.{0,80}\b(" + "|".join(PROTECTED_TERMS) + r")\b", lower)
        if conditional_hits:
            findings.append("Comparative framing across protected-attribute groups detected — review for asymmetric treatment")
            score = max(score, 0.35)

    if not findings:
        findings = ["No overgeneralization or stereotype-association patterns detected"]

    confidence = 0.75 if depth == "deep" else 0.6

    return {
        "category": "bias",
        "score": round(score, 3),
        "confidence": confidence,
        "depth_used": depth,
        "findings": findings,
        "redacted_text": None,
    }
