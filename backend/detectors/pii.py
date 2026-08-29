"""
PII / entity detector.

Enterprises consume the foundation model over an API and usually can't inspect
model internals, so this operates purely at the output-text layer: regex +
lightweight heuristics for structured PII, no model access required. This is
deliberately the "fast, always-on" detector — it's cheap enough to run on
every single interaction regardless of latency budget.
"""
import re

PATTERNS = {
    "email": (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), 0.55),
    "phone": (re.compile(r"(?<!\d)(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"), 0.5),
    "ssn": (re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"), 0.95),
    "credit_card": (re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)"), 0.9),
    "ip_address": (re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"), 0.35),
    "passport_like": (re.compile(r"(?<![A-Za-z0-9])[A-Z]{1,2}\d{6,9}(?![A-Za-z0-9])"), 0.6),
    "dob": (re.compile(r"(?<!\d)(0[1-9]|1[0-2])[/-](0[1-9]|[12]\d|3[01])[/-](19|20)\d{2}(?!\d)"), 0.45),
}

LABELS = {
    "email": "Email address",
    "phone": "Phone number",
    "ssn": "Social Security Number",
    "credit_card": "Payment card number",
    "ip_address": "IP address",
    "passport_like": "Government ID-like identifier",
    "dob": "Date of birth",
}


def _redact(text: str) -> tuple[str, list[str]]:
    findings = []
    redacted = text
    for key, (pattern, _severity) in PATTERNS.items():
        matches = list(pattern.finditer(redacted))
        if matches:
            findings.append(f"{LABELS[key]} detected x{len(matches)}")
            redacted = pattern.sub(f"[REDACTED_{key.upper()}]", redacted)
    return redacted, findings


def run(response_text: str, depth: str, severity_multiplier: float = 1.0) -> dict:
    findings: list[str] = []
    max_severity = 0.0
    hit_count = 0

    for key, (pattern, severity) in PATTERNS.items():
        matches = pattern.findall(response_text)
        if matches:
            hit_count += len(matches)
            findings.append(f"{LABELS[key]} detected x{len(matches)}")
            max_severity = max(max_severity, severity)

    # Score combines worst-single-category severity with a small bump for
    # multiple distinct PII types appearing together (compounding exposure).
    distinct_types = len(findings)
    score = min(1.0, max_severity * severity_multiplier + 0.05 * max(0, distinct_types - 1))

    redacted_text, _ = _redact(response_text) if findings else (response_text, [])

    confidence = 0.95 if depth == "deep" or findings else 0.8

    return {
        "category": "pii",
        "score": round(score, 3),
        "confidence": confidence,
        "depth_used": depth,
        "findings": findings if findings else ["No structured PII patterns detected"],
        "redacted_text": redacted_text if findings else None,
    }
