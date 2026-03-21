"""
Tests for QT1 — validation/outcome_store.py

Covers:
  - record() writes correct fields to JSONL and SQLite
  - outcome values: success, empty, failure
  - partial records (missing nl_query / provider / session_id)
  - query_id is auto-generated when not supplied
  - /api/execute endpoint calls the recorder on success, empty, and failure
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Isolated outcome_store tests (redirect paths to a temp dir)
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    """Redirect outcome_store file paths to a temporary directory."""
    import validation.outcome_store as store
    monkeypatch.setattr(store, "_JSONL_PATH",  tmp_path / "outcomes.jsonl")
    monkeypatch.setattr(store, "_SQLITE_PATH", tmp_path / "outcomes.db")
    return tmp_path


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _read_sqlite(path: Path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM query_outcomes").fetchall()
    conn.close()
    return [dict(r) for r in rows]


class TestRecordSuccess:
    def test_writes_jsonl_entry(self, tmp_store):
        from validation.outcome_store import record
        record(generated_sql="SELECT 1", query_type="sql",
               outcome="success", latency_ms=12.5, row_count=3)
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert len(entries) == 1
        e = entries[0]
        assert e["outcome"] == "success"
        assert e["row_count"] == 3
        assert e["latency_ms"] == 12.5
        assert e["error_type"] == ""
        assert e["error_msg"] == ""

    def test_writes_sqlite_entry(self, tmp_store):
        from validation.outcome_store import record
        record(generated_sql="SELECT 1", query_type="sql",
               outcome="success", latency_ms=5.0, row_count=1)
        rows = _read_sqlite(tmp_store / "outcomes.db")
        assert len(rows) == 1
        assert rows[0]["outcome"] == "success"

    def test_returns_query_id(self, tmp_store):
        from validation.outcome_store import record
        qid = record(generated_sql="SELECT 1", query_type="sql",
                     outcome="success", latency_ms=1.0)
        assert isinstance(qid, str) and len(qid) == 36  # UUID format

    def test_uses_supplied_query_id(self, tmp_store):
        from validation.outcome_store import record
        qid = record(generated_sql="SELECT 1", query_type="sql",
                     outcome="success", latency_ms=1.0, query_id="my-id-123")
        assert qid == "my-id-123"
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert entries[0]["query_id"] == "my-id-123"


class TestRecordEmpty:
    def test_empty_outcome(self, tmp_store):
        from validation.outcome_store import record
        record(generated_sql="SELECT * FROM t WHERE 1=0", query_type="sql",
               outcome="empty", latency_ms=8.0, row_count=0)
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert entries[0]["outcome"] == "empty"
        assert entries[0]["row_count"] == 0


class TestRecordFailure:
    def test_failure_stores_error_fields(self, tmp_store):
        from validation.outcome_store import record
        record(generated_sql="SELECT * FROM nonexistent", query_type="sql",
               outcome="failure", latency_ms=3.0,
               error_type="OperationalError", error_msg="no such table: nonexistent")
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        e = entries[0]
        assert e["outcome"] == "failure"
        assert e["error_type"] == "OperationalError"
        assert "nonexistent" in e["error_msg"]
        assert e["row_count"] == -1


class TestRecordPartialContext:
    def test_missing_optional_fields_default_to_empty(self, tmp_store):
        from validation.outcome_store import record
        record(generated_sql="SELECT 1", query_type="sql",
               outcome="success", latency_ms=1.0)
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        e = entries[0]
        assert e["nl_query"] == ""
        assert e["provider"] == ""
        assert e["session_id"] == ""

    def test_optional_fields_stored_when_provided(self, tmp_store):
        from validation.outcome_store import record
        record(generated_sql="SELECT 1", query_type="sql",
               outcome="success", latency_ms=1.0,
               nl_query="how many orders?", provider="codex", session_id="sess-1")
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        e = entries[0]
        assert e["nl_query"] == "how many orders?"
        assert e["provider"] == "codex"
        assert e["session_id"] == "sess-1"


# ---------------------------------------------------------------------------
# /api/execute endpoint integration tests
# ---------------------------------------------------------------------------

_EXECUTE_BODY = {
    "generated_query": "SELECT 1",
    "query_type": "sql",
    "connection_string": "sqlite:///:memory:",
    "nl_query": "give me one row",
    "provider": "codex",
    "session_id": "s1",
}




class TestExecuteEndpointRecordsOutcome:

    def test_success_outcome_recorded(self, tmp_store):
        with patch("backend.executor.execute_query",
                   return_value=(["col"], [[1]])):
            resp = client.post("/api/execute", json=_EXECUTE_BODY)
        assert resp.status_code == 200
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert len(entries) == 1
        assert entries[0]["outcome"] == "success"
        assert entries[0]["row_count"] == 1
        assert entries[0]["provider"] == "codex"
        assert entries[0]["nl_query"] == "give me one row"

    def test_empty_outcome_recorded(self, tmp_store):
        with patch("backend.executor.execute_query", return_value=(["col"], [])):
            resp = client.post("/api/execute", json=_EXECUTE_BODY)
        assert resp.status_code == 200
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert entries[0]["outcome"] == "empty"
        assert entries[0]["row_count"] == 0

    def test_failure_outcome_recorded(self, tmp_store):
        with patch("backend.executor.execute_query",
                   side_effect=Exception("no such table: orders")):
            resp = client.post("/api/execute", json=_EXECUTE_BODY)
        assert resp.status_code == 500
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert entries[0]["outcome"] == "failure"
        assert entries[0]["error_type"] == "Exception"
        assert "orders" in entries[0]["error_msg"]

    def test_422_failure_outcome_recorded(self, tmp_store):
        with patch("backend.executor.execute_query",
                   side_effect=ValueError("sql must be a non-empty string.")):
            resp = client.post("/api/execute", json=_EXECUTE_BODY)
        assert resp.status_code == 422
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert entries[0]["outcome"] == "failure"
        assert entries[0]["error_type"] == "ValueError"

    def test_outcome_recorded_without_optional_context(self, tmp_store):
        """Endpoint still works and records when nl_query/provider/session_id omitted."""
        body = {
            "generated_query": "SELECT 1",
            "query_type": "sql",
            "connection_string": "sqlite:///:memory:",
        }
        with patch("backend.executor.execute_query", return_value=(["c"], [[1]])):
            resp = client.post("/api/execute", json=body)
        assert resp.status_code == 200
        entries = _read_jsonl(tmp_store / "outcomes.jsonl")
        assert entries[0]["nl_query"] == ""
        assert entries[0]["provider"] == ""
