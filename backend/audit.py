import sqlite3
import json
import os
import threading
import uuid
from datetime import datetime, timezone

_DB_PATH = os.path.join(os.path.dirname(__file__), "controlplane_audit.db")
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                check_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                use_case TEXT NOT NULL,
                geo TEXT,
                conversation_id TEXT,
                prompt TEXT,
                response TEXT,
                overall_score REAL,
                decision TEXT,
                human_review_required INTEGER,
                latency_ms REAL,
                policy_version TEXT,
                categories_json TEXT,
                final_text TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id TEXT PRIMARY KEY,
                check_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewer TEXT,
                correct_decision TEXT,
                notes TEXT,
                FOREIGN KEY(check_id) REFERENCES checks(check_id)
            )
        """)
        conn.commit()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def log_check(check_id: str, use_case: str, geo: str, conversation_id, prompt: str,
              response: str, overall_score: float, decision: str,
              human_review_required: bool, latency_ms: float, policy_version: str,
              categories: list[dict], final_text: str):
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO checks
               (check_id, created_at, use_case, geo, conversation_id, prompt, response,
                overall_score, decision, human_review_required, latency_ms, policy_version,
                categories_json, final_text)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (check_id, datetime.now(timezone.utc).isoformat(), use_case, geo, conversation_id,
             prompt, response, overall_score, decision, int(human_review_required), latency_ms,
             policy_version, json.dumps(categories), final_text),
        )
        conn.commit()


def log_feedback(check_id: str, reviewer: str, correct_decision: str, notes: str | None):
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO feedback (feedback_id, check_id, created_at, reviewer, correct_decision, notes)
               VALUES (?,?,?,?,?,?)""",
            (new_id(), check_id, datetime.now(timezone.utc).isoformat(), reviewer, correct_decision, notes),
        )
        conn.commit()


def get_recent_checks(limit: int = 50, use_case: str | None = None) -> list[dict]:
    with _lock, _connect() as conn:
        if use_case:
            rows = conn.execute(
                "SELECT * FROM checks WHERE use_case = ? ORDER BY created_at DESC LIMIT ?",
                (use_case, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM checks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_metrics() -> dict:
    with _lock, _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM checks").fetchone()["c"]
        by_decision = {
            r["decision"]: r["c"]
            for r in conn.execute("SELECT decision, COUNT(*) AS c FROM checks GROUP BY decision").fetchall()
        }
        by_use_case = {
            r["use_case"]: r["c"]
            for r in conn.execute("SELECT use_case, COUNT(*) AS c FROM checks GROUP BY use_case").fetchall()
        }
        avg_latency = conn.execute(
            "SELECT use_case, AVG(latency_ms) AS avg_ms FROM checks GROUP BY use_case"
        ).fetchall()
        avg_latency_by_uc = {r["use_case"]: round(r["avg_ms"], 1) for r in avg_latency}

        feedback_rows = conn.execute(
            """SELECT f.correct_decision AS correct, c.decision AS original
               FROM feedback f JOIN checks c ON f.check_id = c.check_id"""
        ).fetchall()
        total_feedback = len(feedback_rows)
        overrides = sum(1 for r in feedback_rows if r["correct"] != r["original"])
        false_positive_like = sum(
            1 for r in feedback_rows
            if r["correct"] == "allow" and r["original"] in ("block", "flag_for_review")
        )
        false_negative_like = sum(
            1 for r in feedback_rows
            if r["correct"] in ("block", "flag_for_review") and r["original"] == "allow"
        )

        return {
            "total_checks": total,
            "by_decision": by_decision,
            "by_use_case": by_use_case,
            "avg_latency_ms_by_use_case": avg_latency_by_uc,
            "total_feedback": total_feedback,
            "override_rate": round(overrides / total_feedback, 3) if total_feedback else None,
            "false_positive_like_count": false_positive_like,
            "false_negative_like_count": false_negative_like,
        }
