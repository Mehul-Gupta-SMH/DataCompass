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


if __name__ == "__main__":
    unittest.main()
