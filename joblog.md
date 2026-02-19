# SQLCoder — Job Log

One entry per session. Most recent at the top.

---

## Session 1 — 2026-02-18

### Done
- Full codebase exploration and architecture review
- Identified security issues: `eval()` usage (S1, S2), secrets in config (S3)
- Identified all architectural weaknesses across retrieval, prompt building, graph layer, and utilities
- Created `Tasks.md` with 15 tasks across 5 priority tiers
- Created `joblog.md`

### Notes
- `model_access_config.YAML` is in `.gitignore` but git history should be verified (S3)
- `__filterAdditionalColumns__()` is a confirmed no-op placeholder — needs proper implementation (C3)
- Scoring pipeline in `RAGPipeline.py` runs but output is discarded in `SQLBuilderComponents.py` (C2)
- Current branch: `dev_refactor_existing`

### Next Up
- S1, S2, S3 — security fixes (low complexity, should be first)

---

## Session 2 — 2026-02-18

### Done
- **S3**: Verified `model_access_config.YAML` was never committed — keys are safe
- **S1**: Replaced `eval()` with `json.loads()` in `AllAPICaller.py`
  - Also fixed trailing commas in `ANTHROPIC.json`, `GROQ.json`, `GOOGLE.json` (were invalid JSON — reason `eval` was used originally)
- **S2**: Replaced `eval()` with `ast.literal_eval()` in `base_utils.py` cache read; also narrowed bare `except` to `(ValueError, SyntaxError)`

### Notes
- All three JSON template files now valid JSON — can be linted/validated going forward
- `import ast` added to `base_utils.py`, `import json` added to `AllAPICaller.py`

### Next Up
- Q1 — remove hardcoded absolute paths
- Q2 — remove double `__set_apidict__()` call
- Q3 — fix `.gitignore` for nested `__pycache__`
- Q4 — replace `print()` with `logging`

---

## Session 3 — 2026-02-18

### Done
- **Q1**: Removed hardcoded absolute path in `base_utils.py`
  - Added `_UTILS_DIR`, `PROJECT_ROOT`, `_CONFIG_FILE` constants via `pathlib.Path(__file__)`
  - `get_config_val()` now resolves sub-config paths relative to `config.yaml` location
  - `config.yaml` updated to use relative filenames — no machine-specific paths in Python code
- **Q2**: Fixed double `__set_apidict__()` call in `AllAPICaller`
  - `__init__` was assigning the `None` return value (overwriting the side-effect set), then `CallService` re-called it to recover. Now `__init__` calls it correctly without assignment; `CallService` no longer calls it at all
- **Q3**: Fixed `.gitignore` — `/__pycache__` → `**/__pycache__` so nested cache dirs are excluded
- **Q4**: Replaced all `print()` with `logging.getLogger(__name__)` across:
  - `SQLBuilderComponents.py` (4 statements → `logger.debug`)
  - `MetadataManager/MetadataStore/vdb/Chroma.py` (3-line heartbeat block → `logger.debug`)
  - `MetadataManager/MetadataBuilder/importExisting/importData.py` (3 statements → `logger.debug/info/error`)
  - Also fixed bare `except` in `importData.py` — now chains original exception with `raise ... from e`

### Notes
- Paths inside `retrieval_config.YAML` and `database_config.YAML` (vectordb, models_repo, relationdb) are still absolute — these are user-configured and acceptable; `PROJECT_ROOT` is exported from `base_utils.py` for future use
- `SQLSource.py` in `MetadataRetriever/` appears to be an older unused copy — not touched

### Next Up
- C1 — structured prompt template
- C2 — wire reranker scores into filtering
- C3 — implement `__filterAdditionalColumns__()`

---

## Session 4 — 2026-02-18

### Done
- **C1**: Structured prompt template
  - Fixed hardcoded paths in `PromptBuilder.py` — now uses `pathlib.Path(__file__).parent / "Prompts"`
  - Added `'generate sql'` prompt type with `expected_params = ['SCHEMA']`
  - Added `PromptBuilder.format_schema(context)` static method — converts context dict into markdown with table descriptions, column tables, and join path section
  - Created `APIManager/Prompts/taskGenerateSQL.txt` prompt template
  - Updated `main.py` — removed raw f-string prompt, now uses `PromptBuilder.format_schema()` + `PromptBuilder('generate sql').build()`; added `logging.basicConfig`
- **C2**: Reranker score filtering now active
  - Added `reranker_threshold: 0.0` to `retrieval_config.YAML`
  - `__filterRelevantResults__` now filters by threshold, sorts remaining tables by reranker score descending, and logs how many passed
- **C3**: Column relevance filtering implemented
  - Added `column_score_threshold: 0.0` to `retrieval_config.YAML`
  - `__filterAdditionalColumns__` now uses BM25Okapi to score each column (name + description) against the user query
  - Key columns (PRIMARY KEY / FOREIGN KEY) always retained regardless of score
  - Falls back to all columns if none pass threshold (safety net)
  - Added `from rank_bm25 import BM25Okapi` to `SQLBuilderComponents.py`

### Notes
- Both thresholds default to `0.0` — tune upward if too many irrelevant tables/columns are passing through
- `PromptBuilder` previously had no pathlib dependency — that was also an instance of Q1 missed during the Q-tier pass; fixed here
- M2 (silent error swallowing in importData.py) was partially addressed in Q4 session — `raise ... from e` already added

### Next Up
- M1 — switch to DiGraph for directional JOIN relationships
- M2 — already partially done; verify fully resolved
- M3 — move module-level loading in RAGPipeline into __init__
- M4 — retry logic in CallService

---

## Session 5 — 2026-02-19

### Done
- **M1**: Switched `nx.Graph` → `nx.DiGraph` in `networkxDB.py`
  - `getObj()` now returns `nx.DiGraph()` for new graphs
  - `addRelations()` adds edges in both directions — JOINs are semantically bidirectional; DiGraph requires explicit reverse edges for `shortest_path` to work in both query directions
  - Updated all `nx.Graph` type hints to `nx.DiGraph` throughout the file
  - Backward compatible: existing pickled `nx.Graph` files still load and work; DiGraph only applies to newly created graphs
- **M2**: Removed redundant bare `except` wrapper around `validate_json()` in `importData.py`
  - `validate_json` already raises `ValueError` with exception chaining (`raise ... from e`); the outer `except` was re-raising a new ValueError that discarded that chain entirely
- **M3**: Moved all module-level `get_config_val` calls in `RAGPipeline.py` into class `__init__`
  - `FilterContext.__init__` now loads `models_repo` and `scoring_configs`
  - `ManageInformation.__init__` now loads `models_repo`, `indexing_configs`, and stores `vectordb_configs` as `self.vectordb_configs` (used by both `__init__` and `initialize_client`)
  - Removed unused imports: `Detoxify`, `AutoTokenizer`, `TFAutoModelForSequenceClassification`, `pipeline` (were only used in commented-out code)
- **M4**: Added exponential backoff retry to `CallLLMApi.CallService()`
  - Retries up to 3 times on status codes `{429, 500, 502, 503, 504}` (rate limits and transient server errors)
  - Delay doubles each attempt: 1s → 2s → 4s
  - Non-retryable errors (400, 401, etc.) fail immediately on first attempt
  - Error message now includes status code and first 200 chars of response body
  - Added `import logging`, `import time`, module-level constants `_MAX_RETRIES`, `_RETRY_BASE_DELAY`, `_RETRYABLE_STATUS_CODES`

### Notes
- All Tier 1–4 tasks are now complete
- Remaining: Tier 5 — F1 (VectorStore interface), F2 (metadata store interface), F3 (test suite), F4 (cachefunc.close() bug)

### Next Up
- F1–F4 — Tier 5 maintainability tasks

---

## Session 6 — 2026-02-19

### Done
- **F4**: Fixed `cachefunc.close()` — changed `self.connection.close()` to `self.DBObj.connection.close()`; the connection has always lived on `DBObj`, never directly on `cachefunc`
- **F2**: Created `Utilities/store_interface.py` with `BaseMetadataStore` ABC defining the full CRUD contract (`create_table`, `get_data`, `post_data`, `update_data`, `delete_data`); `accessDB` now inherits from it
- **F1**: Created `MetadataManager/MetadataStore/vdb/base.py` with `BaseVectorStore` ABC (`connect`, `add_data`, `get_data`); added `ChromaVectorStore` class to `Chroma.py` implementing the interface; updated `RAGPipeline.py` to use `ChromaVectorStore` instance (`self.vdb`) instead of calling module-level Chroma functions directly — `self.client` removed, `self.vdb.connect/add_data/get_data` used throughout
- **F3**: Created test suite in `tests/`:
  - `test_prompt_builder.py` — 12 tests covering `format_schema()` (table names, labels, columns, descriptions, joins, edge cases) and `build()` (placeholder replacement, wrong params, unknown type)
  - `test_filters.py` — 10 tests covering `__filterRelevantResults__` (threshold, ordering, empty output) and `__filterAdditionalColumns__` (key retention, BM25 relevance, fallback, None fields)
  - `test_base_utils.py` — 8 tests covering `accessDB` CRUD with in-memory SQLite, `cachefunc.close()` delegation, and `accessDB` interface conformance

### Notes
- All 15 tasks across all 5 tiers are now complete
- Existing module-level functions in `Chroma.py` (`getclient`, `addData`, `getData`) are preserved for backward compatibility
- Tests avoid all external dependencies (no ML models, no ChromaDB, no API keys) — all heavy deps mocked