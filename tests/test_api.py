"""
Integration tests for the FastAPI backend endpoints.

Uses FastAPI's TestClient (backed by httpx) to exercise the full request/response
cycle.  Heavy ML dependencies are already pre-mocked by tests/conftest.py so the
import of backend.app succeeds without installing torch, chromadb, etc.
"""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app
from main import SQLValidationError, _VALID_PROVIDERS


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_generate():
    """Patch generateQuery at the location it was imported in backend.app."""
    with patch("backend.app.generateQuery") as m:
        yield m


# ---------------------------------------------------------------------------
# GET /api/providers
# ---------------------------------------------------------------------------

class TestGetProviders:

    def test_returns_200(self, client):
        resp = client.get("/api/providers")
        assert resp.status_code == 200

    def test_response_has_providers_key(self, client):
        resp = client.get("/api/providers")
        assert "providers" in resp.json()

    def test_providers_is_sorted_list(self, client):
        resp = client.get("/api/providers")
        providers = resp.json()["providers"]
        assert isinstance(providers, list)
        assert providers == sorted(providers)

    def test_providers_match_valid_providers(self, client):
        resp = client.get("/api/providers")
        providers = resp.json()["providers"]
        assert set(providers) == _VALID_PROVIDERS


# ---------------------------------------------------------------------------
# POST /api/query — success path
# ---------------------------------------------------------------------------

class TestPostQuerySuccess:

    def test_returns_200_with_sql(self, client, mock_generate):
        mock_generate.return_value = "SELECT 1"
        resp = client.post(
            "/api/query",
            json={"query": "show me orders", "provider": "open_ai"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"sql": "SELECT 1"}

    def test_generatequery_called_with_correct_args(self, client, mock_generate):
        mock_generate.return_value = "SELECT 1"
        client.post(
            "/api/query",
            json={"query": "show me orders", "provider": "open_ai"},
        )
        mock_generate.assert_called_once_with("show me orders", "open_ai")


# ---------------------------------------------------------------------------
# POST /api/query — validation errors → 422
# ---------------------------------------------------------------------------

class TestPostQueryValidationError:

    def test_empty_query_returns_422(self, client, mock_generate):
        mock_generate.side_effect = ValueError("userQuery must be a non-empty string.")
        resp = client.post(
            "/api/query",
            json={"query": "", "provider": "open_ai"},
        )
        assert resp.status_code == 422

    def test_unknown_provider_returns_422(self, client, mock_generate):
        mock_generate.side_effect = ValueError("LLMservice must be one of ...")
        resp = client.post(
            "/api/query",
            json={"query": "show me orders", "provider": "unknown_llm"},
        )
        assert resp.status_code == 422

    def test_422_detail_matches_exception_message(self, client, mock_generate):
        msg = "some validation error message"
        mock_generate.side_effect = ValueError(msg)
        resp = client.post(
            "/api/query",
            json={"query": "foo", "provider": "open_ai"},
        )
        assert resp.json()["detail"] == msg

    def test_sql_validation_error_returns_422(self, client, mock_generate):
        mock_generate.side_effect = SQLValidationError("LLM response is not valid SQL.")
        resp = client.post(
            "/api/query",
            json={"query": "foo", "provider": "open_ai"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/query — unexpected server errors → 500
# ---------------------------------------------------------------------------

class TestPostQueryServerError:

    def test_unexpected_exception_returns_500(self, client, mock_generate):
        mock_generate.side_effect = RuntimeError("something unexpected")
        resp = client.post(
            "/api/query",
            json={"query": "foo", "provider": "open_ai"},
        )
        assert resp.status_code == 500

    def test_500_detail_is_generic(self, client, mock_generate):
        mock_generate.side_effect = RuntimeError("something unexpected")
        resp = client.post(
            "/api/query",
            json={"query": "foo", "provider": "open_ai"},
        )
        assert resp.json()["detail"] == "Internal server error"


# ---------------------------------------------------------------------------
# POST /api/query — Pydantic request-schema validation → 422
# ---------------------------------------------------------------------------

class TestPostQueryRequestSchema:

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/api/query", json={"provider": "open_ai"})
        assert resp.status_code == 422

    def test_missing_provider_field_returns_422(self, client):
        resp = client.post("/api/query", json={"query": "show me orders"})
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, client):
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422
