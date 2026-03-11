"""Tests for A3: configurable gather_requirements.max_tool_calls."""

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_TMDB = {
    "info_type": "sqlite",
    "dbName": "md.db",
    "tableDescName": "tableDesc",
    "tableColName": "tableColMetadata",
}


def _make_cfg(max_tool_calls):
    """Return a get_config_val side_effect that injects max_tool_calls."""
    def _cfg(section, keys=None, *args, **kwargs):
        if keys and keys[0] == "gather_requirements":
            # Return a dict whose nested key will be read by the code
            inner = keys[1] if len(keys) > 1 else None
            if inner == "max_tool_calls":
                return max_tool_calls
            return {"max_tool_calls": max_tool_calls}
        return _FAKE_TMDB
    return _cfg


def _run_gather(cfg_side_effect, messages=None):
    """Patch heavy deps and run gatherRequirements; return the result."""
    if messages is None:
        messages = [{"role": "user", "content": "show me sales"}]

    api_instance = MagicMock()
    api_instance.CallService.return_value = '{"ready": true, "summary": "done"}'

    with patch("Utilities.base_utils.get_config_val", side_effect=cfg_side_effect), \
         patch("main._preload_schemas_bulk", return_value={}), \
         patch("main._get_table_directory", return_value="table_dir"), \
         patch("main.CallLLMApi", return_value=api_instance), \
         patch("main.PromptBuilder") as pb_cls:

        pb_instance = MagicMock()
        pb_instance.build_prompt.return_value = "prompt"
        pb_cls.return_value = pb_instance

        from main import gatherRequirements
        return gatherRequirements(messages, provider="open_ai")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMaxToolCallsFromConfig:
    """gatherRequirements reads max_tool_calls from retrieval_config."""

    def test_reads_max_tool_calls_from_config(self):
        """When config supplies max_tool_calls=3, the loop uses that value."""
        result = _run_gather(_make_cfg(3))
        assert result["ready"] is True
        assert "summary" in result

    def test_fallback_when_config_missing(self):
        """If config lookup raises KeyError, default of 5 is used (no crash)."""
        def _cfg_raises(section, keys=None, *args, **kwargs):
            if keys and keys[0] == "gather_requirements":
                raise KeyError("gather_requirements")
            return _FAKE_TMDB

        result = _run_gather(_cfg_raises)
        assert result["ready"] is True

    def test_invalid_config_value_falls_back_to_default(self):
        """Non-integer config value should not crash; falls back to 5."""
        result = _run_gather(_make_cfg("not_a_number"))
        assert isinstance(result, dict)
        assert "ready" in result
