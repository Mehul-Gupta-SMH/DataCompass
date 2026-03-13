# R1 — Adaptive Re-retrieval Agent: Implementation Plan

**Author**: OpenAI Codex (o4-mini), Planner+Tester agent
**Date**: 2026-03-13
**Branch**: `Claude/Playground/Dev`

---

## 1. Approach Decision — Where Should R1 Live?

**Decision: R1 logic belongs in `main.py`, encapsulated in a new helper function `_adaptive_retrieval()`.**

### Rationale

| Option | Pros | Cons |
|--------|------|------|
| Inside `generateQuery()` (inline) | No new call stack | `generateQuery` is already complex; harder to test in isolation |
| New helper in `main.py` | Same module as call site; easy access to `_get_table_directory()` and `CallLLMApi`; keeps `SQLBuilderComponents.py` infrastructure-only | Adds ~60 lines to `main.py` |
| New file `retrieval_agent.py` | Maximum isolation | Over-engineering for one function; requires cross-module imports |
| Inside `SQLBuilderComponents.py` | Co-located with ChromaDB call | `SQLBuilderComponents.py` should remain pure retrieval; injecting LLM calls there mixes concerns |

`SQLBuilderComponents.py` is intentionally infrastructure-only: ChromaDB query, graph traversal, column fetch. LLM query rewriting is a higher-level concern. The function `_get_table_directory()` already lives in `main.py` and is exactly what the rewriter prompt needs. Adding `_adaptive_retrieval()` to `main.py` keeps all LLM-facing orchestration in one file and lets `generateQuery` stay clean with a single call site replacement.

---

## 2. Files to Change

### `main.py`

**New function** — `_adaptive_retrieval()` (add after line 163, before `_PROMPT_MAP`):

```python
def _adaptive_retrieval(
    initial_query: str,
    LLMservice: str,
    model: str = None,
    instance_name: str = "default",
) -> dict:
    """
    Adaptive re-retrieval loop (R1).

    Runs `getRelevantContext` up to `re_retrieval.max_rounds` times (from
    retrieval_config.YAML). On each round where the confidence check fails,
    the LLM is asked to rewrite the search query using the table directory
    and the set of tables found so far.  Results are merged (union) across
    rounds before returning.

    Returns the best context dict obtained across all rounds.
    """
```

**Modified** — `generateQuery()`, lines 229–237: replace the existing two-step fallback with a call to `_adaptive_retrieval()`.

Before (lines 229–237):
```python
context = getRelevantContext(rag_query, instance_name=instance_name)

no_tables = not any(context["table_list"].get(k) for k in ("direct", "intermediate"))
if no_tables and rag_query != userQuery:
    logger.warning("RAG returned no tables using conversation query; retrying with requirements summary")
    context = getRelevantContext(userQuery, instance_name=instance_name)
    no_tables = not any(context["table_list"].get(k) for k in ("direct", "intermediate"))
```

After:
```python
context = _adaptive_retrieval(
    rag_query,
    LLMservice,
    model=model,
    instance_name=instance_name,
)
no_tables = not any(context["table_list"].get(k) for k in ("direct", "intermediate"))
```

The existing `if no_tables: logger.error(...)` block at line 239 is kept unchanged.

### `Utilities/retrieval_config.YAML`

Add a new top-level section (after `gather_requirements:`):

```yaml
re_retrieval:
  max_rounds: 3          # total query attempts (initial + up to 2 rewrites)
  min_direct_tables: 2   # stop early when this many direct tables are found
  rewrite_provider: null # null = use the provider passed to generateQuery
```

### `APIManager/Prompts/taskReRetrievalRewrite.txt` (new file)

A lightweight prompt template; no PromptBuilder template key needed — the rewriter prompt is built inline in `_adaptive_retrieval()` using an f-string because it does not need the full `PromptBuilder` infrastructure (it is a single-turn, low-latency call).

### `tests/test_adaptive_retrieval.py` (new file)

Five test cases (see Section 7).

---

## 3. Config Additions to `retrieval_config.YAML`

```yaml
re_retrieval:
  max_rounds: 3
  # Stop early when at least this many *direct* tables are found.
  # Set to 0 to always run max_rounds (useful for debugging).
  min_direct_tables: 2
  # Override the LLM provider used for query rewriting.
  # null means use the same provider as the caller (recommended default).
  rewrite_provider: null
```

Reading pattern (mirrors the A3 pattern for `gather_requirements`):

```python
try:
    _max_rounds = int(get_config_val("retrieval_config", ["re_retrieval", "max_rounds"]))
except (KeyError, AttributeError, TypeError, ValueError):
    _max_rounds = 3

try:
    _min_tables = int(get_config_val("retrieval_config", ["re_retrieval", "min_direct_tables"]))
except (KeyError, AttributeError, TypeError, ValueError):
    _min_tables = 2
```

---

## 4. LLM Prompt Design

The rewriter call should be cheap and fast — a single-turn, focused task with no conversation history.

```
You are a database search assistant. Your job is to rewrite a search query
to find relevant database tables.

Original user question:
"{original_query}"

Previous search query (did not find enough tables):
"{previous_query}"

Tables found so far: {found_tables_list or "none"}

Available tables in the database:
{table_directory}

Write ONE alternative search query (1-2 sentences) that uses different wording,
synonyms, or more general/specific terms to find the tables needed to answer
the original question. Output ONLY the rewritten query text — no explanation,
no JSON, no quotes.
```

**Design choices**:
- Single-turn, no JSON envelope — the response is just a string (the new query). Avoids JSON parse failures.
- Includes `table_directory` so the LLM can recognise domain-specific table names.
- Explicitly shows what was already tried to avoid repeating the same query.
- Kept short (< 300 tokens input) to minimise latency and cost.
- A lightweight model can handle this task; `rewrite_provider: null` defers to whatever the caller chose.

---

## 5. Confidence Check

### Primary threshold: count of direct tables

```python
def _is_retrieval_confident(context: dict, min_tables: int) -> bool:
    direct = context["table_list"].get("direct", {})
    return len(direct) >= min_tables
```

`min_direct_tables: 2` is a reasonable default because a useful SQL query almost always involves at least one fact table and usually a dimension. Setting `min_direct_tables: 1` would stop too eagerly; `3` could over-trigger rewrites on simple single-table queries.

### Secondary signal (logged only, not used for stopping): reranker scores

`SQLBuilderSupport.__filterRelevantResults__` already uses the cross-encoder reranker threshold (`scoring.reranker_threshold`). Tables that fail the reranker threshold are already excluded before `_adaptive_retrieval` ever sees them. The confidence check therefore only needs to count surviving direct tables.

### Why not use raw ChromaDB cosine distance?

ChromaDB distance is available in the scored results dict (`results_scored[uid]["distance"]`) but it is computed before reranking. The reranker score is the higher-quality signal; distance is a coarser pre-filter. Using the count of reranker-passing direct tables is consistent with what the rest of the pipeline already does.

---

## 6. Edge Cases

### 6a. Schema is genuinely empty (no tables ingestd yet)

`_get_table_directory()` returns `"(no tables in schema yet)"`. The rewriter prompt includes the table directory, so the LLM will see it is empty and any rewrite will be arbitrary. `_adaptive_retrieval` must detect this and skip the rewrite loop entirely:

```python
table_dir = _get_table_directory(instance_name=instance_name)
if "(no tables" in table_dir or not table_dir.strip():
    logger.warning("R1: table directory is empty — skipping adaptive retrieval")
    return getRelevantContext(initial_query, instance_name=instance_name)
```

### 6b. Re-retrieval returns the same tables every time (loop stagnation)

Track the set of direct table names found across rounds. If round N finds no new tables compared to round N-1, stop immediately:

```python
if set(new_direct_tables) == set(prev_direct_tables):
    logger.info("R1: no new tables found in round %d — stopping early", round_num)
    break
```

This prevents wasting LLM calls when the embedding space has genuinely converged.

### 6c. Rewriter returns an empty or whitespace-only query

Guard with:
```python
rewritten = rewritten.strip()
if not rewritten:
    logger.warning("R1: LLM returned empty rewrite on round %d — stopping", round_num)
    break
```

### 6d. Rewriter returns the same text as the previous query

Detect exact string equality and skip:
```python
if rewritten == current_query:
    logger.info("R1: LLM returned identical query on round %d — stopping", round_num)
    break
```

### 6e. LLM call fails (network error, provider down)

Wrap the rewriter `CallLLMApi.CallService()` in a try/except and fall back to the best context seen so far:

```python
try:
    rewritten = CallLLMApi(provider, model=model).CallService(rewrite_prompt)
except Exception as exc:
    logger.warning("R1: rewrite LLM call failed on round %d: %s — using best context so far", round_num, exc)
    break
```

### 6f. Max-retry cap exhausted

The loop runs at most `max_rounds` times. After exhaustion, the best accumulated context (most direct tables) is returned. Execution continues in `generateQuery` with whatever schema was found; the existing `if no_tables: logger.error(...)` fallback remains as the last-resort notice.

---

## 7. Tests Needed

File: `tests/test_adaptive_retrieval.py`

### Test 1 — `test_confident_on_first_round`

**What it tests**: If the first `getRelevantContext` call returns `min_direct_tables` or more direct tables, `_adaptive_retrieval` should return immediately without calling the LLM rewriter.

**Setup**: Mock `getRelevantContext` to return a context with 2 direct tables. Assert that `CallLLMApi.CallService` is never called. Assert returned context equals the mock.

### Test 2 — `test_rewrite_improves_results`

**What it tests**: If round 1 finds 0 tables but round 2 (after LLM rewrite) finds 2 tables, the function returns the round-2 context and logs the improvement.

**Setup**: Mock `getRelevantContext` to return empty on first call, then return 2 direct tables on second call. Mock `CallLLMApi.CallService` to return `"rewritten query text"`. Assert `CallService` was called once. Assert returned context has 2 direct tables.

### Test 3 — `test_stagnation_stops_early`

**What it tests**: If rounds 1, 2, 3 all return the same set of tables (stagnation), the loop exits after round 2 without exhausting `max_rounds`.

**Setup**: Mock `getRelevantContext` to always return `{"direct": {"orders": {...}}, "intermediate": {}}`. Set `max_rounds = 3`. Assert `getRelevantContext` is called at most 2 times (round 1 + round 2 finds same tables → stops).

### Test 4 — `test_empty_schema_skips_loop`

**What it tests**: When `_get_table_directory` returns `"(no tables in schema yet)"`, the loop is skipped and a single `getRelevantContext` call is made.

**Setup**: Mock `_get_table_directory` to return `"(no tables in schema yet)"`. Mock `getRelevantContext`. Assert `getRelevantContext` called exactly once with the initial query. Assert `CallLLMApi` never called.

### Test 5 — `test_rewriter_exception_uses_best_context`

**What it tests**: If the LLM rewriter raises an exception on round 2, the function returns the best context seen so far (round 1 result) rather than propagating the exception.

**Setup**: Mock `getRelevantContext` round 1 returns 1 direct table. Mock `CallLLMApi.CallService` to raise `ValueError("LLM timeout")`. Assert `_adaptive_retrieval` returns the round-1 context without raising. Assert no exception propagated to caller.

---

## 8. Integration with `gatherRequirements`

**Decision: R1 should NOT run inside `gatherRequirements`.**

### Reasoning

`gatherRequirements` already has its own schema discovery mechanism — the `get_schema` tool loop. The LLM in the gather phase can call `get_schema("table_name")` up to `max_tool_calls` times to inspect any specific table it wants. The gather phase also uses `_get_table_directory()` so the LLM always sees all available table names.

The RAG search inside `gatherRequirements` (lines 460–466) is a best-effort warm-start that pre-populates the `SCHEMA` section of the gather prompt. It is not the primary table-discovery mechanism there. Running R1's LLM-rewrite loop on top of an already-agentic loop would:

1. Double the LLM call count in the gathering phase (already costly at up to 5+1 calls).
2. Be redundant — the gather LLM can directly ask for any table schema it needs.
3. Increase end-to-end latency significantly for the clarification step.

The root failure mode R1 is solving — "generateQuery gets an empty schema" — is specifically a `generateQuery` problem. The gather phase always has a direct escape hatch (tool calls) and a full table directory. R1 is the right fix at the `generateQuery` boundary only.

**One optional enhancement** (not in R1 scope): After R1 runs in `generateQuery`, log the winning rewritten query into the session context so future `gatherRequirements` calls see it. This is a P2-level optimisation that can be done in a follow-up.

---

## Implementation Checklist (for Claude)

- [ ] Add `re_retrieval` section to `Utilities/retrieval_config.YAML`
- [ ] Write `_adaptive_retrieval()` function in `main.py` (after line 163)
- [ ] Write `_is_retrieval_confident()` helper in `main.py`
- [ ] Modify `generateQuery()` lines 229–237 to call `_adaptive_retrieval()`
- [ ] Add `tests/test_adaptive_retrieval.py` with 5 test cases
- [ ] Run `pytest tests/` and confirm all existing tests still pass
- [ ] Update `TASK.md` R1 status from `[ ]` to `[x]` when done

---

## Codex Recommendation

- **R1 lives entirely in `main.py`** as a new `_adaptive_retrieval()` helper, called from `generateQuery()` at the existing two-step fallback site (lines 229–237). `SQLBuilderComponents.py` stays infrastructure-only. This is the minimal-diff, minimal-risk placement.

- **The confidence check is table-count based** (`len(direct_tables) >= min_direct_tables`), not score-based. Reranker filtering already happens inside `SQLBuilderSupport.__filterRelevantResults__` before the context reaches `_adaptive_retrieval`, so counting surviving direct tables is the right signal at this abstraction level. Default `min_direct_tables: 2` with early-exit on stagnation prevents wasted LLM calls.

- **R1 must not run inside `gatherRequirements`**. The gather phase has the `get_schema` tool loop as its native schema-discovery mechanism. Adding R1 there would double LLM call costs, introduce redundancy, and increase clarification latency without addressing the actual failure point (empty schema in `generateQuery`).
