"""
QT1 — Query Outcome Store

Appends a structured outcome record to outcomes.jsonl after every /api/execute
call and maintains a SQLite index for efficient lookups by date/provider/outcome.

Record shape:
    {
        "query_id":      str   — UUID generated at execute time
        "session_id":    str   — passed from frontend (optional)
        "nl_query":      str   — original natural-language question (optional)
        "generated_sql": str   — the SQL/code that was executed
        "provider":      str   — LLM provider that generated it (optional)
        "query_type":    str   — "sql" | "spark_sql"
        "outcome":       str   — "success" | "empty" | "failure"
        "error_type":    str   — short error class name, or "" on success
        "error_msg":     str   — full error message, or "" on success
        "row_count":     int   — rows returned, or -1 on failure
        "latency_ms":    float — execution wall-clock time in milliseconds
        "ts":            str   — ISO-8601 UTC timestamp
    }

outcome semantics:
    "success" — query ran and returned ≥1 row
    "empty"   — query ran without error but returned 0 rows (logic issue, not syntax)
    "failure" — query raised an exception
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BASE_DIR    = Path(__file__).parent
_JSONL_PATH  = _BASE_DIR / "corpus" / "outcomes.jsonl"
_SQLITE_PATH = _BASE_DIR / "corpus" / "outcomes.db"

_jsonl_lock  = Lock()
_sqlite_lock = Lock()

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS query_outcomes (
    query_id     TEXT PRIMARY KEY,
    session_id   TEXT,
    nl_query     TEXT,
    generated_sql TEXT,
    provider     TEXT,
    query_type   TEXT,
    outcome      TEXT,
    error_type   TEXT,
    error_msg    TEXT,
    row_count    INTEGER,
    latency_ms   REAL,
    ts           TEXT
);
CREATE INDEX IF NOT EXISTS idx_outcome_ts       ON query_outcomes (ts);
CREATE INDEX IF NOT EXISTS idx_outcome_outcome  ON query_outcomes (outcome);
CREATE INDEX IF NOT EXISTS idx_outcome_provider ON query_outcomes (provider);
"""


def _ensure_db():
    _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SQLITE_PATH))
    conn.executescript(_CREATE_TABLE)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record(
    *,
    generated_sql: str,
    query_type: str,
    outcome: str,
    latency_ms: float,
    row_count: int = -1,
    error_type: str = "",
    error_msg: str = "",
    nl_query: str = "",
    provider: str = "",
    session_id: str = "",
    query_id: str = "",
) -> str:
    """
    Write one outcome record to outcomes.jsonl and the SQLite index.

    Returns the query_id (generated if not supplied).
    All fields except generated_sql, query_type, outcome, and latency_ms
    are optional — partial records are still useful for corpus building.
    """
    if not query_id:
        query_id = str(uuid.uuid4())

    ts = datetime.now(timezone.utc).isoformat()

    entry = {
        "query_id":      query_id,
        "session_id":    session_id,
        "nl_query":      nl_query,
        "generated_sql": generated_sql,
        "provider":      provider,
        "query_type":    query_type,
        "outcome":       outcome,
        "error_type":    error_type,
        "error_msg":     error_msg,
        "row_count":     row_count,
        "latency_ms":    round(latency_ms, 2),
        "ts":            ts,
    }

    # Append to JSONL (thread-safe)
    _JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _jsonl_lock:
        with open(_JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # Upsert into SQLite index (thread-safe)
    _ensure_db()
    with _sqlite_lock:
        conn = sqlite3.connect(str(_SQLITE_PATH))
        conn.execute(
            """
            INSERT OR REPLACE INTO query_outcomes
            (query_id, session_id, nl_query, generated_sql, provider,
             query_type, outcome, error_type, error_msg, row_count, latency_ms, ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                entry["query_id"], entry["session_id"], entry["nl_query"],
                entry["generated_sql"], entry["provider"], entry["query_type"],
                entry["outcome"], entry["error_type"], entry["error_msg"],
                entry["row_count"], entry["latency_ms"], entry["ts"],
            ),
        )
        conn.commit()
        conn.close()

    return query_id
