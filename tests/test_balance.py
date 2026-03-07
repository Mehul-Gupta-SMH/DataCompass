"""
Tests for backend/balance.py

All HTTP calls are mocked — no real network requests are made.
Run with: pytest tests/test_balance.py
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.balance import (
    _check_openai,
    _check_anthropic,
    _check_groq,
    _check_google,
    _check_claude_code,
    get_all_balances,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_body: dict = None, text: str = ""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body or {}
    r.text = text
    return r


# ---------------------------------------------------------------------------
# _check_openai
# ---------------------------------------------------------------------------

class TestCheckOpenAI:

    def test_valid_key_with_org_credits_balance(self):
        """200 from /v1/organization/credits with total_available → returns balance."""
        resp = _mock_response(200, {"total_available": 12.50})
        with patch("requests.get", return_value=resp):
            result = _check_openai("sk-test")
        assert result["status"] == "ok"
        assert result["balance"] == 12.50
        assert result["available"] is True
        assert result["label"] == "$12.50"

    def test_valid_key_with_credit_grants_balance(self):
        """200 from /v1/dashboard/billing/credit_grants with total_available."""
        responses = [
            _mock_response(404),  # /v1/organization/credits not found
            _mock_response(200, {"total_available": 5.00, "total_used": 1.00, "total_granted": 6.00}),
        ]
        with patch("requests.get", side_effect=responses):
            result = _check_openai("sk-test")
        assert result["status"] == "ok"
        assert result["balance"] == 5.00
        assert result["label"] == "$5.00"

    def test_zero_balance_greyed_out(self):
        """total_available == 0 → available False, status no_balance."""
        resp = _mock_response(200, {"total_available": 0.0})
        with patch("requests.get", return_value=resp):
            result = _check_openai("sk-test")
        assert result["status"] == "no_balance"
        assert result["available"] is False
        assert result["balance"] == 0.0
        assert result["label"] == "$0.00"

    def test_invalid_key_401(self):
        """401 on balance endpoint → invalid_key."""
        resp = _mock_response(401)
        with patch("requests.get", return_value=resp):
            result = _check_openai("sk-bad")
        assert result["status"] == "invalid_key"
        assert result["available"] is False

    def test_secret_key_403_falls_back_to_models_valid(self):
        """
        403 on both billing endpoints (secret key) → fallback /v1/models 200
        → available True, status unavailable, label N/A.
        """
        billing_403 = _mock_response(403)
        models_200 = _mock_response(200, {"data": []})
        with patch("requests.get", side_effect=[billing_403, billing_403, models_200]):
            result = _check_openai("sk-test")
        assert result["status"] == "unavailable"
        assert result["available"] is True
        assert result["label"] == "N/A"

    def test_secret_key_403_fallback_models_401_invalid(self):
        """403 on billing + 401 on /v1/models → invalid key."""
        billing_403 = _mock_response(403)
        models_401 = _mock_response(401)
        with patch("requests.get", side_effect=[billing_403, billing_403, models_401]):
            result = _check_openai("sk-bad")
        assert result["status"] == "invalid_key"
        assert result["available"] is False

    def test_network_error_returns_unavailable(self):
        """All requests raise RequestException → unavailable but available True."""
        import requests as req
        with patch("requests.get", side_effect=req.RequestException("timeout")):
            result = _check_openai("sk-test")
        assert result["available"] is True
        assert result["status"] == "unavailable"

    def test_balance_with_grants_data_array(self):
        """Response uses data[] array format instead of total_available scalar."""
        data = {
            "data": [
                {"grant_amount": 10.0, "used_amount": 3.0},
                {"grant_amount": 5.0,  "used_amount": 1.0},
            ]
        }
        resp = _mock_response(200, data)
        with patch("requests.get", return_value=resp):
            result = _check_openai("sk-test")
        assert result["status"] == "ok"
        assert result["balance"] == 11.0  # (10-3) + (5-1)


# ---------------------------------------------------------------------------
# _check_anthropic
# ---------------------------------------------------------------------------

class TestCheckAnthropic:

    def test_invalid_key_401_on_models(self):
        models_401 = _mock_response(401)
        with patch("requests.get", return_value=models_401):
            result = _check_anthropic("bad-key")
        assert result["status"] == "invalid_key"
        assert result["available"] is False

    def test_valid_key_no_billing_error(self):
        models_200 = _mock_response(200)
        probe_200 = _mock_response(200)
        with patch("requests.get", return_value=models_200), \
             patch("requests.post", return_value=probe_200):
            result = _check_anthropic("sk-ant-valid")
        assert result["available"] is True
        assert result["status"] == "unavailable"
        assert result["label"] == "N/A"

    def test_billing_error_400(self):
        models_200 = _mock_response(200)
        probe_400 = _mock_response(400, {"error": {"message": "You have exceeded your credit balance"}})
        with patch("requests.get", return_value=models_200), \
             patch("requests.post", return_value=probe_400):
            result = _check_anthropic("sk-ant-empty")
        assert result["status"] == "no_balance"
        assert result["available"] is False

    def test_network_error_returns_unavailable(self):
        import requests as req
        with patch("requests.get", side_effect=req.RequestException("timeout")), \
             patch("requests.post", side_effect=req.RequestException("timeout")):
            result = _check_anthropic("sk-ant-test")
        assert result["available"] is True
        assert result["status"] == "unavailable"


# ---------------------------------------------------------------------------
# _check_groq
# ---------------------------------------------------------------------------

class TestCheckGroq:

    def test_invalid_key_401(self):
        with patch("requests.get", return_value=_mock_response(401)):
            result = _check_groq("bad-key")
        assert result["status"] == "invalid_key"
        assert result["available"] is False

    def test_valid_key_200(self):
        with patch("requests.get", return_value=_mock_response(200, {"data": []})):
            result = _check_groq("gsk-valid")
        assert result["available"] is True
        assert result["label"] == "N/A"

    def test_network_error_returns_unavailable(self):
        import requests as req
        with patch("requests.get", side_effect=req.RequestException):
            result = _check_groq("gsk-test")
        assert result["available"] is True


# ---------------------------------------------------------------------------
# _check_google
# ---------------------------------------------------------------------------

class TestCheckGoogle:

    def test_invalid_key_403_permission_denied(self):
        body = {"error": {"status": "PERMISSION_DENIED"}}
        with patch("requests.get", return_value=_mock_response(403, body)):
            result = _check_google("bad-key")
        assert result["status"] == "invalid_key"
        assert result["available"] is False

    def test_invalid_key_400_invalid_argument(self):
        body = {"error": {"status": "INVALID_ARGUMENT"}}
        with patch("requests.get", return_value=_mock_response(400, body)):
            result = _check_google("bad-key")
        assert result["status"] == "invalid_key"
        assert result["available"] is False

    def test_valid_key_200(self):
        with patch("requests.get", return_value=_mock_response(200, {"models": []})):
            result = _check_google("AIzaSy-valid")
        assert result["available"] is True
        assert result["status"] == "unavailable"

    def test_network_error_returns_unavailable(self):
        import requests as req
        with patch("requests.get", side_effect=req.RequestException):
            result = _check_google("AIzaSy-test")
        assert result["available"] is True


# ---------------------------------------------------------------------------
# _check_claude_code
# ---------------------------------------------------------------------------

class TestCheckClaudeCode:

    def test_cli_available(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.2.3\n"
        with patch("subprocess.run", return_value=mock_result):
            result = _check_claude_code("")
        assert result["available"] is True
        assert result["status"] == "ok"
        assert "1.2.3" in result["label"]

    def test_cli_not_installed(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _check_claude_code("")
        assert result["available"] is False
        assert result["status"] == "unavailable"
        assert result["label"] == "CLI not installed"

    def test_cli_timeout(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 5)):
            result = _check_claude_code("")
        assert result["available"] is False
        assert result["status"] == "unavailable"

    def test_cli_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = _check_claude_code("")
        assert result["available"] is False

    def test_cli_label_shows_usage_after_calls(self):
        """After recording usage, label includes token counts."""
        from backend.usage_tracker import record_claude_code, get_claude_code_stats
        import backend.usage_tracker as ut

        # Save and reset state
        original = dict(ut._claude_code)
        ut._claude_code.update({"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})

        record_claude_code(input_tokens=100, output_tokens=50, cost_usd=0.002)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.2.3\n"
        with patch("subprocess.run", return_value=mock_result):
            result = _check_claude_code("")

        assert result["available"] is True
        assert "100" in result["label"]   # input tokens
        assert "50" in result["label"]    # output tokens
        assert "$0.0020" in result["label"]

        # Restore
        ut._claude_code.update(original)

    def test_cli_label_no_usage_when_no_calls(self):
        """With zero calls, label is just 'CLI <version>' with no usage stats."""
        import backend.usage_tracker as ut

        original = dict(ut._claude_code)
        ut._claude_code.update({"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.2.3\n"
        with patch("subprocess.run", return_value=mock_result):
            result = _check_claude_code("")

        assert result["label"] == "CLI 1.2.3"

        ut._claude_code.update(original)


# ---------------------------------------------------------------------------
# get_all_balances (integration of loader + checkers)
# ---------------------------------------------------------------------------

class TestGetAllBalances:

    def _make_yaml(self, tmp_path, providers: dict):
        """Write a minimal model_access_config.YAML and return its path."""
        import yaml
        p = tmp_path / "model_access_config.YAML"
        p.write_text(yaml.dump(providers))
        return str(p)

    def test_returns_entry_for_each_provider(self, tmp_path):
        fake_cfg = {
            "OPEN_AI": {"api_key": "sk-test"},
            "ANTHROPIC": {"api_key": "sk-ant-test"},
        }
        yaml_path = self._make_yaml(tmp_path, fake_cfg)

        models_ok = _mock_response(200, {"data": []})
        probe_ok  = _mock_response(200)

        with patch("backend.balance.get_config_val", return_value=yaml_path), \
             patch("requests.get", return_value=models_ok), \
             patch("requests.post", return_value=probe_ok):
            result = get_all_balances(["open_ai", "anthropic"])

        assert set(result.keys()) == {"open_ai", "anthropic"}
        for v in result.values():
            assert "available" in v
            assert "status" in v
            assert "label" in v

    def test_missing_key_returns_na_not_greyed_out(self, tmp_path):
        fake_cfg = {"OPEN_AI": {}}  # no api_key
        yaml_path = self._make_yaml(tmp_path, fake_cfg)

        with patch("backend.balance.get_config_val", return_value=yaml_path):
            result = get_all_balances(["open_ai"])

        assert result["open_ai"]["available"] is True
        assert result["open_ai"]["status"] == "no_config"
        assert result["open_ai"]["label"] == "N/A"

    def test_unknown_provider_returns_unavailable(self, tmp_path):
        fake_cfg = {"UNKNOWN_PROV": {"api_key": "key123"}}
        yaml_path = self._make_yaml(tmp_path, fake_cfg)

        with patch("backend.balance.get_config_val", return_value=yaml_path):
            result = get_all_balances(["unknown_prov"])

        assert result["unknown_prov"]["available"] is True
        assert result["unknown_prov"]["status"] == "unavailable"

    def test_checker_exception_returns_error_not_greyed_out(self, tmp_path):
        fake_cfg = {"OPEN_AI": {"api_key": "sk-test"}}
        yaml_path = self._make_yaml(tmp_path, fake_cfg)

        # _CHECKERS holds direct function references; patch the dict entry so
        # the exception is raised inside _check_one's outer try/except.
        import backend.balance as bal_mod
        original = bal_mod._CHECKERS["open_ai"]
        try:
            bal_mod._CHECKERS["open_ai"] = MagicMock(side_effect=RuntimeError("boom"))
            with patch("backend.balance.get_config_val", return_value=yaml_path):
                result = get_all_balances(["open_ai"])
        finally:
            bal_mod._CHECKERS["open_ai"] = original

        assert result["open_ai"]["available"] is True
        assert result["open_ai"]["status"] == "error"
