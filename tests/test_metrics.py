"""
tests/test_metrics.py — B3: Structured logging & metrics

Covers:
  - _Metrics.record_request() increments counters correctly
  - _Metrics.record_llm_call() tracks calls and errors per provider
  - render_prometheus() emits valid Prometheus text format
  - GET /metrics endpoint is accessible and returns text/plain
  - Request logging middleware increments metrics on real endpoint calls
"""

import pytest

from fastapi.testclient import TestClient
from backend.app import app
from backend.metrics import _Metrics


client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests: _Metrics class
# ---------------------------------------------------------------------------

@pytest.fixture()
def m():
    """Return a fresh _Metrics instance for isolation."""
    return _Metrics()


class TestMetricsRecord:

    def test_record_request_increments_count(self, m):
        m.record_request("GET", "/api/providers", 200, 12.5)
        assert m._request_counts[("GET", "/api/providers", 200)] == 1

    def test_record_request_accumulates(self, m):
        m.record_request("POST", "/api/chat", 200, 100.0)
        m.record_request("POST", "/api/chat", 200, 200.0)
        assert m._request_counts[("POST", "/api/chat", 200)] == 2

    def test_record_request_tracks_latency_sum(self, m):
        m.record_request("GET", "/api/schema", 200, 50.0)
        m.record_request("GET", "/api/schema", 200, 150.0)
        assert m._latency_sum[("GET", "/api/schema")] == 200.0

    def test_record_request_tracks_latency_count(self, m):
        m.record_request("GET", "/api/schema", 200, 50.0)
        assert m._latency_count[("GET", "/api/schema")] == 1

    def test_record_request_fills_histogram_buckets(self, m):
        m.record_request("GET", "/api/providers", 200, 75.0)
        # 75ms should increment the 100ms bucket (first bucket >= 75)
        assert m._latency_hist[("GET", "/api/providers", 100)] == 1

    def test_record_llm_call_increments(self, m):
        m.record_llm_call("open_ai")
        assert m._llm_calls["open_ai"] == 1

    def test_record_llm_call_error_increments_both(self, m):
        m.record_llm_call("anthropic", error=True)
        assert m._llm_calls["anthropic"] == 1
        assert m._llm_errors["anthropic"] == 1

    def test_record_llm_call_no_error_does_not_increment_errors(self, m):
        m.record_llm_call("groq", error=False)
        assert m._llm_errors["groq"] == 0

    def test_reset_clears_all(self, m):
        m.record_request("GET", "/api/providers", 200, 10.0)
        m.record_llm_call("open_ai")
        m.reset()
        assert len(m._request_counts) == 0
        assert len(m._llm_calls) == 0


class TestRenderPrometheus:

    def test_contains_request_counter_help(self, m):
        output = m.render_prometheus()
        assert "polyql_http_requests_total" in output

    def test_contains_llm_counter_help(self, m):
        output = m.render_prometheus()
        assert "polyql_llm_calls_total" in output

    def test_request_line_after_recording(self, m):
        m.record_request("GET", "/api/providers", 200, 20.0)
        output = m.render_prometheus()
        assert 'polyql_http_requests_total{method="GET",path="/api/providers",status="200"} 1' in output

    def test_llm_line_after_recording(self, m):
        m.record_llm_call("open_ai")
        output = m.render_prometheus()
        assert 'polyql_llm_calls_total{provider="open_ai"} 1' in output

    def test_llm_error_line_after_recording(self, m):
        m.record_llm_call("groq", error=True)
        output = m.render_prometheus()
        assert 'polyql_llm_errors_total{provider="groq"} 1' in output

    def test_empty_metrics_has_no_data_lines(self, m):
        output = m.render_prometheus()
        # Only HELP/TYPE lines, no data lines with labels
        data_lines = [line for line in output.splitlines() if "{" in line]
        assert data_lines == []

    def test_output_ends_with_newline(self, m):
        assert m.render_prometheus().endswith("\n")

    def test_histogram_bucket_present(self, m):
        m.record_request("POST", "/api/chat", 200, 300.0)
        output = m.render_prometheus()
        assert "polyql_http_request_duration_ms_bucket" in output


# ---------------------------------------------------------------------------
# Integration: GET /metrics endpoint
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:

    def test_metrics_endpoint_returns_200(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type_is_text_plain(self):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]

    def test_metrics_body_contains_help_lines(self):
        resp = client.get("/metrics")
        assert "# HELP" in resp.text

    def test_metrics_body_contains_polyql_prefix(self):
        resp = client.get("/metrics")
        assert "polyql_" in resp.text


# ---------------------------------------------------------------------------
# Integration: middleware increments request counters
# ---------------------------------------------------------------------------

class TestRequestMiddleware:

    def test_get_providers_increments_counter(self):
        from backend.metrics import metrics
        metrics.reset()
        client.get("/api/providers")
        total = sum(
            v for (method, path, status), v in metrics._request_counts.items()
            if path == "/api/providers" and method == "GET"
        )
        assert total >= 1

    def test_latency_recorded_for_request(self):
        from backend.metrics import metrics
        metrics.reset()
        client.get("/api/providers")
        assert metrics._latency_count.get(("GET", "/api/providers"), 0) >= 1
