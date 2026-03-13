# CLAUDE.md — Poly-QL

Guidelines and context for AI-assisted development on this project.

---

## Git Workflow

- **Never push directly to `master`**
- Use branch `Claude/Playground/Dev` (or create a feature branch)
- Commit and push branch only; let the user merge via GitHub PR

---

## Project Identity

- App name: **Poly-QL** (header/branding)
- Repo/package names still say `SQLCoder` — do not rename those

---

## Backend

- Entry point: `backend/app.py` (FastAPI)
- Business logic: `main.py` (`gatherRequirements`, `generateQuery`, `generate_pipeline_dict`)
- Balance checks: `backend/balance.py` — concurrent, one checker per provider
- Run: `uvicorn backend.app:app --reload` from project root

## Frontend

- Vite + React (`frontend/`)
- Run: `npm run dev` from `frontend/`
- Sessions stored in `localStorage` under `poly_ql_sessions` (max 30)

---

## Key Conventions

- **Code fence regex** for LLM responses: `r'```(?:\w+)?\s*(.*?)\s*```'`
- **generateQuery signature**: `(userQuery, LLMservice, query_type, conversation=None)`
- **Balance checker return shape**: `{balance, currency, available, status, label}`
  - `available: False` greys out the provider in the UI
  - `status` values: `ok | no_balance | invalid_key | unavailable | no_config | error`
- **OpenAI secret keys** (`sk-...`) cannot access `/dashboard/billing/credit_grants` — returns 403.
  The checker falls back to `/v1/models` for key validity and returns `label: "N/A"`.
- **Claude Code provider** uses `subprocess.run(["claude", "-p", ...])` — no API key, uses local CLI session.
  Balance check runs `claude --version`.

---

## Testing

- Test suite lives in `tests/`
- `conftest.py` pre-mocks heavy ML packages (torch, chromadb, sentence-transformers, FlagEmbedding)
- Run all tests: `pytest tests/`
- Balance tests use `unittest.mock.patch("requests.get")` / `patch("requests.post")` — no real HTTP calls

---

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-07 | `backend/balance.py` | Fixed OpenAI `credit_grants` URL (`/dashboard/` → `/v1/dashboard/`); added key-validity fallback via `/v1/models` when balance endpoints return 403 |
| 2026-03-07 | `backend/usage_tracker.py` | New: thread-safe in-memory token usage tracker for Claude Code CLI |
| 2026-03-07 | `APIManager/AllAPICaller.py` | Claude Code: switched to `--output-format json`, records token usage |
| 2026-03-07 | `main.py` | `gatherRequirements`: re-prompt on non-JSON LLM response; extract + return `options` array |
| 2026-03-07 | `taskRequirementGather.txt` | Added `options` array to clarify format; enforced JSON-only output |
| 2026-03-07 | `backend/app.py` | Pass `options` through in clarify response |
| 2026-03-07 | `frontend/…/ChatInterface.jsx` | Retry strips assistant clarify history; `handleOptionSelect` for pill button clicks |
| 2026-03-07 | `frontend/…/ChatMessage.jsx` | Clarify bubble renders clickable option pill buttons |
| 2026-03-13 | `APIManager/AllAPICaller.py` | P1: Added `CallServiceStream()` generator — SSE token streaming for OpenAI/Codex/GROQ/Anthropic/Google; CLI providers fall back to batch |
| 2026-03-13 | `main.py` | P1: Added `generateQueryStream()` generator — yields `{event:token}` chunks + final `{event:done}` with validated result |
| 2026-03-13 | `backend/app.py` | P1: New `POST /api/chat/stream` SSE endpoint — Phase 1 (gather) runs sync, Phase 2 streams tokens; clarify returns single done event |
| 2026-03-13 | `frontend/…/ChatInterface.jsx` | P1: `_callApiStream()` — fetch ReadableStream SSE consumer; streaming bubble updated token-by-token, finalised on done event |
| 2026-03-13 | `frontend/…/ChatMessage.jsx` | P1: New `streaming` bubble type — dark code block with `●●●` placeholder while tokens arrive |
| 2026-03-13 | `main.py` | R1: `_adaptive_retrieval()` + `_is_retrieval_confident()` — LLM rewrites ChromaDB search query when retrieval is weak; up to 3 rounds, stagnation/empty/failure early exits; replaces 2-line fallback in `generateQuery` and `generateQueryStream` |
| 2026-03-13 | `Utilities/retrieval_config.YAML` | R1: Added `re_retrieval` config section: `max_rounds`, `min_direct_tables`, `rewrite_provider` |
| 2026-03-13 | `tests/test_adaptive_retrieval.py` | R1: 9 new tests covering confident-first-round, rewrite-improves, stagnation, empty-schema, rewriter-exception |
| 2026-03-13 | `tests/test_kuzu.py` | Fix: test isolation — patch `_kuzu_base_dir` directly and clear `_DB_POOL`/`_SCHEMA_READY` in migration test to prevent lru_cache poisoning across test runs |
