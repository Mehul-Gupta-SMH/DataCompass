import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend import balance


class TestCheckClaudeCode(unittest.TestCase):
    def _make_process(self, stdout_text="Claude Code CLI 1.2.3"):
        return SimpleNamespace(returncode=0, stdout=stdout_text + "\n", stderr="")

    def test_cli_not_installed(self):
        with patch("backend.balance.subprocess.run", side_effect=FileNotFoundError):
            info = balance._check_claude_code(None)

        self.assertFalse(info["available"])
        self.assertEqual(info["status"], "unavailable")
        self.assertEqual(info["label"], "CLI not installed")

    def test_cli_available_without_usage(self):
        process = self._make_process("Claude Code CLI 1.2.3")
        stats = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        with patch("backend.balance.subprocess.run", return_value=process), \
             patch("backend.usage_tracker.get_claude_code_stats", return_value=stats):
            info = balance._check_claude_code(None)

        self.assertTrue(info["available"])
        self.assertEqual(info["status"], "ok")
        self.assertEqual(info["label"], "CLI Claude Code CLI 1.2.3")

    def test_cli_available_with_usage_label(self):
        process = self._make_process("Claude Code CLI 1.2.3")
        stats = {"calls": 3, "input_tokens": 1234, "output_tokens": 56, "cost_usd": 0.047}

        with patch("backend.balance.subprocess.run", return_value=process), \
             patch("backend.usage_tracker.get_claude_code_stats", return_value=stats):
            info = balance._check_claude_code(None)

        self.assertTrue(info["available"])
        self.assertEqual(info["status"], "ok")
        self.assertEqual(info["label"], "CLI Claude Code CLI 1.2.3 · 1,234↑ 56↓ tok · $0.0470")


class TestCheckAnthropic(unittest.TestCase):
    _HEADERS = {"x-api-key": "test-key", "anthropic-version": "2023-06-01"}

    def _mock_get(self, status_code, json_body=None):
        r = SimpleNamespace(status_code=status_code)
        r.json = lambda: (json_body or {})
        return r

    def _mock_post(self, status_code, json_body=None):
        r = SimpleNamespace(status_code=status_code)
        r.json = lambda: (json_body or {})
        return r

    def test_invalid_key(self):
        with patch("backend.balance.requests.get", return_value=self._mock_get(401)), \
             patch("backend.balance.requests.post"):
            info = balance._check_anthropic("bad-key")

        self.assertFalse(info["available"])
        self.assertEqual(info["status"], "invalid_key")
        self.assertEqual(info["label"], "Invalid key")

    def test_no_credits(self):
        billing_err = {"error": {"message": "Your account has run out of credits."}}
        with patch("backend.balance.requests.get", return_value=self._mock_get(200)), \
             patch("backend.balance.requests.post", return_value=self._mock_post(400, billing_err)):
            info = balance._check_anthropic("valid-key")

        self.assertFalse(info["available"])
        self.assertEqual(info["status"], "no_balance")
        self.assertEqual(info["label"], "No credits")

    def test_valid_key_balance_unavailable(self):
        with patch("backend.balance.requests.get", return_value=self._mock_get(200)), \
             patch("backend.balance.requests.post", return_value=self._mock_post(200)):
            info = balance._check_anthropic("valid-key")

        self.assertTrue(info["available"])
        self.assertEqual(info["status"], "unavailable")
        self.assertEqual(info["label"], "N/A")

    def test_network_error_on_models_probe(self):
        import requests as req
        with patch("backend.balance.requests.get", side_effect=req.RequestException("timeout")), \
             patch("backend.balance.requests.post", return_value=self._mock_post(200)):
            info = balance._check_anthropic("any-key")

        self.assertTrue(info["available"])
        self.assertEqual(info["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
