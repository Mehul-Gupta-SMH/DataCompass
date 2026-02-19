"""
Tests for input validation at the two public entry points:
  - generateQuery() in main.py
  - CallLLMApi.CallService() in APIManager/AllAPICaller.py

No ML models, databases, or API calls are made.
"""

import unittest
from unittest.mock import patch, MagicMock

# conftest.py pre-mocks heavy ML packages; main.py is safely importable.
from main import generateQuery, _VALID_PROVIDERS, _MAX_QUERY_LENGTH


# ---------------------------------------------------------------------------
# generateQuery() input validation
# ---------------------------------------------------------------------------

class TestGenerateQueryValidation(unittest.TestCase):

    def test_raises_on_none_query(self):
        with self.assertRaises(ValueError):
            generateQuery(None, "open_ai")

    def test_raises_on_empty_query(self):
        with self.assertRaises(ValueError):
            generateQuery("", "open_ai")

    def test_raises_on_whitespace_only_query(self):
        with self.assertRaises(ValueError):
            generateQuery("   \n\t  ", "open_ai")

    def test_raises_on_query_too_long(self):
        long_query = "a" * (_MAX_QUERY_LENGTH + 1)
        with self.assertRaises(ValueError) as ctx:
            generateQuery(long_query, "open_ai")
        self.assertIn(str(_MAX_QUERY_LENGTH), str(ctx.exception))

    def test_raises_on_none_provider(self):
        with self.assertRaises(ValueError):
            generateQuery("show me orders", None)

    def test_raises_on_unknown_provider(self):
        with self.assertRaises(ValueError) as ctx:
            generateQuery("show me orders", "unknown_llm")
        self.assertIn("unknown_llm", str(ctx.exception))

    def test_error_lists_valid_providers(self):
        with self.assertRaises(ValueError) as ctx:
            generateQuery("show me orders", "bad")
        for provider in _VALID_PROVIDERS:
            self.assertIn(provider, str(ctx.exception))

    def test_query_at_max_length_does_not_raise(self):
        """A query exactly at the limit should pass validation and reach the pipeline."""
        query = "a" * _MAX_QUERY_LENGTH
        with patch("main.getRelevantContext", side_effect=RuntimeError("pipeline")):
            with self.assertRaises(RuntimeError):
                generateQuery(query, "open_ai")

    def test_valid_provider_names_accepted(self):
        """Each recognized provider name should pass validation and reach the pipeline."""
        for provider in _VALID_PROVIDERS:
            # Patch the pipeline so only validation runs; a RuntimeError means
            # we got past the ValueError guards.
            with patch("main.getRelevantContext", side_effect=RuntimeError("pipeline")):
                with self.assertRaises(RuntimeError):
                    generateQuery("show me orders", provider)


# ---------------------------------------------------------------------------
# CallLLMApi.CallService() input validation
# ---------------------------------------------------------------------------

class TestCallServiceValidation(unittest.TestCase):

    def _make_caller(self, service="open_ai"):
        """Return a CallLLMApi with __set_apidict__ skipped."""
        with patch("APIManager.AllAPICaller.get_config_val"), \
             patch("builtins.open", MagicMock()):
            from APIManager.AllAPICaller import CallLLMApi
            obj = CallLLMApi.__new__(CallLLMApi)
            obj.llmService = service
            obj.api_temp_dict = {
                "endpoint": "http://example.com",
                "headers": {},
                "payload": {"messages": [{"content": ""}]}
            }
            return obj

    def test_raises_on_none_prompt(self):
        obj = self._make_caller()
        with self.assertRaises(ValueError):
            obj.CallService(None)

    def test_raises_on_empty_prompt(self):
        obj = self._make_caller()
        with self.assertRaises(ValueError):
            obj.CallService("")

    def test_raises_on_whitespace_only_prompt(self):
        obj = self._make_caller()
        with self.assertRaises(ValueError):
            obj.CallService("   ")

    def test_valid_prompt_proceeds_to_api_call(self):
        """A valid prompt should pass validation and attempt the HTTP call."""
        obj = self._make_caller()
        with patch("APIManager.AllAPICaller.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "SELECT 1"}}]}
            )
            result = obj.CallService("show me revenue")
        self.assertEqual(result, "SELECT 1")


if __name__ == "__main__":
    unittest.main()
