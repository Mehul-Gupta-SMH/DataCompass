"""
tests/test_failure_scenarios.py — T2: Failure-scenario fixtures

Verifies that the FastAPI endpoints degrade gracefully under:
  - LLM provider timeout
  - LLM rate-limit (HTTP 429 from the upstream provider)
  - Malformed / non-JSON LLM response
  - Empty LLM response
  - LLM connection error (network unreachable)

Each fixture patches `gatherRequirements` or `generateQuery` at the import
site in `backend.app` so no real HTTP calls are made.
"""

import requests as _requests
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

_CHAT_BODY = {
    "messages": [{"role": "user", "content": "show me all orders"}],
    "provider": "open_ai",
    "query_type": "sql",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_gather(side_effect=None, return_value=None):
    """Return a context manager patching gatherRequirements in backend.app."""
    kwargs = {}
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    if return_value is not None:
        kwargs["return_value"] = return_value
    return patch("backend.app.gatherRequirements", **kwargs)


def _patch_generate(side_effect=None, return_value=None):
    kwargs = {}
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    if return_value is not None:
        kwargs["return_value"] = return_value
    return patch("backend.app.generateQuery", **kwargs)


# ---------------------------------------------------------------------------
# T2-1  LLM provider timeout
# ---------------------------------------------------------------------------

class TestLLMTimeout:
    """gatherRequirements raises requests.exceptions.Timeout → 500 with detail."""

    def test_chat_returns_500(self):
        with _patch_gather(side_effect=_requests.exceptions.Timeout("upstream timed out")):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 500

    def test_chat_detail_mentions_gathering(self):
        with _patch_gather(side_effect=_requests.exceptions.Timeout("upstream timed out")):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        assert "Requirement gathering failed" in resp.json()["detail"]

    def test_generate_timeout_returns_500(self):
        """Timeout in generateQuery (Phase 2) also returns 500."""
        ready_gather = {"ready": True, "summary": "Show all orders"}
        with _patch_gather(return_value=ready_gather):
            with _patch_generate(side_effect=_requests.exceptions.Timeout("timed out")):
                resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 500

    def test_generate_timeout_detail(self):
        ready_gather = {"ready": True, "summary": "Show all orders"}
        with _patch_gather(return_value=ready_gather):
            with _patch_generate(side_effect=_requests.exceptions.Timeout("timed out")):
                resp = client.post("/api/chat", json=_CHAT_BODY)
        assert "Query generation failed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# T2-2  Rate-limit (429 from upstream)
# ---------------------------------------------------------------------------

class TestRateLimit:
    """Simulate a 429 response from the LLM provider as a raised exception."""

    def test_chat_returns_500_on_rate_limit(self):
        exc = Exception("HTTP 429 Too Many Requests — rate limit exceeded")
        with _patch_gather(side_effect=exc):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 500

    def test_chat_detail_contains_rate_limit_hint(self):
        exc = Exception("HTTP 429 Too Many Requests — rate limit exceeded")
        with _patch_gather(side_effect=exc):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        detail = resp.json()["detail"]
        assert "429" in detail or "rate limit" in detail.lower() or "Requirement gathering failed" in detail

    def test_generate_rate_limit_returns_500(self):
        ready_gather = {"ready": True, "summary": "Show all orders"}
        exc = Exception("HTTP 429 Too Many Requests")
        with _patch_gather(return_value=ready_gather):
            with _patch_generate(side_effect=exc):
                resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# T2-3  Malformed / non-JSON LLM response
# ---------------------------------------------------------------------------

class TestMalformedLLMResponse:
    """
    The LLM returns something that isn't valid JSON.

    main.py already re-prompts once for a JSON correction;
    if it still can't parse, it raises a ValueError (caught as 422)
    or propagates a generic Exception (caught as 500).
    """

    def test_value_error_returns_422(self):
        """ValueError (e.g. JSON parse failure after re-prompt) → 422."""
        with _patch_gather(side_effect=ValueError("LLM did not return valid JSON after re-prompt")):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 422

    def test_422_detail_is_accessible(self):
        msg = "LLM did not return valid JSON after re-prompt"
        with _patch_gather(side_effect=ValueError(msg)):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        assert msg in resp.json()["detail"]

    def test_generate_value_error_returns_422(self):
        ready_gather = {"ready": True, "summary": "Show all orders"}
        with _patch_gather(return_value=ready_gather):
            with _patch_generate(side_effect=ValueError("bad json from llm")):
                resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# T2-4  Empty LLM response
# ---------------------------------------------------------------------------

class TestEmptyLLMResponse:
    """The LLM returns an empty string — treated as a ValueError or Exception."""

    def test_empty_generate_result_raises(self):
        """generateQuery raising ValueError on empty content → 422."""
        ready_gather = {"ready": True, "summary": "Show all orders"}
        with _patch_gather(return_value=ready_gather):
            with _patch_generate(side_effect=ValueError("LLM returned empty response")):
                resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# T2-5  Network connection error
# ---------------------------------------------------------------------------

class TestConnectionError:
    """requests.ConnectionError (DNS/network failure) → 500."""

    def test_connection_error_returns_500(self):
        with _patch_gather(side_effect=_requests.exceptions.ConnectionError("name resolution failed")):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        assert resp.status_code == 500

    def test_connection_error_does_not_expose_traceback(self):
        """detail should be a string, not a raw traceback dict."""
        with _patch_gather(side_effect=_requests.exceptions.ConnectionError("unreachable")):
            resp = client.post("/api/chat", json=_CHAT_BODY)
        detail = resp.json()["detail"]
        assert isinstance(detail, str)
        assert "Traceback" not in detail


# ---------------------------------------------------------------------------
# T2-6  /api/execute failure scenarios
# ---------------------------------------------------------------------------

class TestExecuteFailureScenarios:
    """
    Verify /api/execute handles DB-level errors correctly and records outcome.
    These complement test_outcome_store.py which covers the recording logic;
    here we verify HTTP status codes and response shapes.
    """

    _BODY = {
        "generated_query": "SELECT * FROM orders",
        "query_type": "sql",
        "connection_string": "sqlite:///:memory:",
    }

    def test_execution_exception_returns_500(self):
        with patch("backend.executor.execute_query", side_effect=Exception("table not found")):
            resp = client.post("/api/execute", json=self._BODY)
        assert resp.status_code == 500

    def test_execution_value_error_returns_422(self):
        with patch("backend.executor.execute_query", side_effect=ValueError("empty query")):
            resp = client.post("/api/execute", json=self._BODY)
        assert resp.status_code == 422

    def test_execution_detail_is_string(self):
        with patch("backend.executor.execute_query", side_effect=Exception("oops")):
            resp = client.post("/api/execute", json=self._BODY)
        assert isinstance(resp.json()["detail"], str)


