"""Tests for R1: _adaptive_retrieval adaptive re-retrieval loop."""

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_EMPTY_CONTEXT = {"table_list": {"direct": {}, "intermediate": {}}, "join_keys": []}

def _ctx_with(n_direct):
    """Build a fake context with n_direct tables."""
    return {
        "table_list": {
            "direct": {f"table_{i}": {} for i in range(n_direct)},
            "intermediate": {},
        },
        "join_keys": [],
    }


def _run_adaptive(get_context_side_effects, rewrite_side_effect=None, table_dir="- **orders**: order table"):
    """
    Run _adaptive_retrieval with patched dependencies.

    get_context_side_effects: list of return values for getRelevantContext calls (in order).
    rewrite_side_effect: return value or exception for CallLLMApi().CallService().
    """
    api_instance = MagicMock()
    if rewrite_side_effect is None:
        api_instance.CallService.return_value = "rewritten query"
    elif isinstance(rewrite_side_effect, Exception):
        api_instance.CallService.side_effect = rewrite_side_effect
    else:
        api_instance.CallService.return_value = rewrite_side_effect

    with patch("main.getRelevantContext", side_effect=get_context_side_effects) as mock_ctx, \
         patch("main._get_table_directory", return_value=table_dir), \
         patch("main.CallLLMApi", return_value=api_instance) as mock_llm_cls, \
         patch("Utilities.base_utils.get_config_val", side_effect=_cfg):

        from main import _adaptive_retrieval
        result = _adaptive_retrieval("show me sales data", LLMservice="open_ai")

    return result, mock_ctx, mock_llm_cls, api_instance


def _cfg(section, keys=None, *args, **kwargs):
    """Minimal config stub: returns sensible defaults for re_retrieval keys."""
    if keys:
        if keys == ["re_retrieval", "max_rounds"]:
            return 3
        if keys == ["re_retrieval", "min_direct_tables"]:
            return 2
        if keys == ["re_retrieval", "rewrite_provider"]:
            return None
    return {}


# ---------------------------------------------------------------------------
# Test 1 — confident on first round: LLM rewriter is never called
# ---------------------------------------------------------------------------

class TestConfidentOnFirstRound:
    def test_no_rewrite_when_first_round_sufficient(self):
        """If first getRelevantContext call returns >= min_direct_tables, no LLM rewrite."""
        ctx = _ctx_with(2)  # meets min_direct_tables=2
        result, mock_ctx, mock_llm_cls, api_instance = _run_adaptive([ctx])

        assert mock_ctx.call_count == 1
        api_instance.CallService.assert_not_called()
        assert result == ctx

    def test_returns_first_context_directly(self):
        """Returned context is identical to the first retrieval result."""
        ctx = _ctx_with(3)
        result, *_ = _run_adaptive([ctx])
        assert len(result["table_list"]["direct"]) == 3


# ---------------------------------------------------------------------------
# Test 2 — rewrite improves results
# ---------------------------------------------------------------------------

class TestRewriteImprovesResults:
    def test_rewrite_called_once_when_round1_weak(self):
        """Round 1 finds 0 tables; round 2 after rewrite finds 2 — function returns round-2 context."""
        round1 = _ctx_with(0)
        round2 = _ctx_with(2)

        result, mock_ctx, mock_llm_cls, api_instance = _run_adaptive([round1, round2])

        assert mock_ctx.call_count == 2
        api_instance.CallService.assert_called_once()
        assert len(result["table_list"]["direct"]) == 2

    def test_best_context_tracked_across_rounds(self):
        """If round 2 has fewer tables than round 1, round 1 result is returned."""
        round1 = _ctx_with(1)
        round2 = _ctx_with(0)
        round3 = _ctx_with(0)

        result, mock_ctx, *_ = _run_adaptive([round1, round2, round3])

        # Should return the best (round1 with 1 table), not the last empty context
        assert len(result["table_list"]["direct"]) == 1


# ---------------------------------------------------------------------------
# Test 3 — stagnation stops early
# ---------------------------------------------------------------------------

class TestStagnationStopsEarly:
    def test_stops_when_same_tables_returned_twice(self):
        """If round N and round N+1 find the same direct table names, stop immediately."""
        # Same single table on every round — stagnation after round 2
        same_ctx = _ctx_with(1)  # table_0 only
        # Provide enough values to cover max_rounds (3), but loop should exit early
        result, mock_ctx, _, api_instance = _run_adaptive([same_ctx, same_ctx, same_ctx])

        # Round 1: retrieve, rewrite.  Round 2: retrieve, detect stagnation, stop.
        # getRelevantContext should be called at most 2 times.
        assert mock_ctx.call_count <= 2
        # CallService called once (for round 1 rewrite before stagnation check)
        assert api_instance.CallService.call_count <= 1


# ---------------------------------------------------------------------------
# Test 4 — empty schema skips loop
# ---------------------------------------------------------------------------

class TestEmptySchemaSkipsLoop:
    def test_single_retrieval_when_directory_empty(self):
        """When _get_table_directory returns '(no tables in schema yet)', skip loop."""
        ctx = _ctx_with(0)

        with patch("main.getRelevantContext", return_value=ctx) as mock_ctx, \
             patch("main._get_table_directory", return_value="(no tables in schema yet)"), \
             patch("main.CallLLMApi") as mock_llm_cls, \
             patch("Utilities.base_utils.get_config_val", side_effect=_cfg):

            from main import _adaptive_retrieval
            _adaptive_retrieval("show me sales data", LLMservice="open_ai")

        assert mock_ctx.call_count == 1
        mock_llm_cls.assert_not_called()

    def test_unavailable_directory_also_skips(self):
        """'(table directory unavailable)' should also skip the rewrite loop."""
        ctx = _ctx_with(0)

        with patch("main.getRelevantContext", return_value=ctx), \
             patch("main._get_table_directory", return_value="(table directory unavailable)"), \
             patch("main.CallLLMApi") as mock_llm_cls, \
             patch("Utilities.base_utils.get_config_val", side_effect=_cfg):

            from main import _adaptive_retrieval
            _adaptive_retrieval("show me sales data", LLMservice="open_ai")

        mock_llm_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 — rewriter exception falls back to best context so far
# ---------------------------------------------------------------------------

class TestRewriterExceptionFallback:
    def test_no_exception_propagated_on_llm_failure(self):
        """If the rewrite LLM call raises, _adaptive_retrieval returns best context without raising."""
        round1 = _ctx_with(1)

        result, mock_ctx, _, api_instance = _run_adaptive(
            [round1],
            rewrite_side_effect=ValueError("LLM timeout"),
        )

        # No exception raised
        assert isinstance(result, dict)
        assert "table_list" in result

    def test_returns_best_context_before_failure(self):
        """Best context seen before the LLM failure is returned."""
        round1 = _ctx_with(1)

        result, *_ = _run_adaptive(
            [round1],
            rewrite_side_effect=ValueError("LLM timeout"),
        )

        assert len(result["table_list"]["direct"]) == 1
