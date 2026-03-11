# Data Compass — Project Task Reference

## What is this project?
**Data Compass** (formerly SQLCoder) is a full-stack AI-powered data query and metadata management tool.
Users describe questions in natural language; a two-agent system gathers requirements then generates SQL / Spark SQL / PySpark DataFrame code. It also supports ingesting new pipeline tables and browsing data lineage.

---

## Architecture

```
frontend/ (Vite + React)          backend/ (FastAPI)            Storage
──────────────────────            ──────────────────            ───────
ChatInterface                     POST /api/chat                ChromaDB (vector embeddings)
  └─ SessionPane (history)          └─ gatherRequirements()     NetworkX graph (Relations.pickle)
  └─ ChatMessage                        └─ tool loop: get_schema SQLite (tableMetadata.db)
SchemaERD                               └─ generateQuery()
  └─ TableNode                    POST /api/query (legacy)
IngestTable                       POST /api/ingest/preview
JoinPathExplorer                  POST /api/ingest/commit
  └─ Join Path tab                POST /api/execute
  └─ Derivative Tables tab        GET  /api/schema?instance_name=
                                  GET  /api/joinpath?from_table=&to_table=
                                  GET  /api/derivatives/{table}
                                  GET  /api/instances
                                  GET  /api/lineage/{table}  (kept for compat)
                                  GET  /api/providers
                                  GET  /api/providers/balance
```

---

## Key Files

| File | Role |
|------|------|
| `main.py` | `generateQuery()`, `gatherRequirements()`, `generate_pipeline_dict()`, `validate_sql()`, `validate_pyspark()` |
| `backend/app.py` | FastAPI routes |
| `backend/ingestion.py` | `parse_pipeline()`, `get_source_schema()`, `store_table()` |
| `backend/executor.py` | SQLAlchemy query execution (500 row cap) |
| `backend/balance.py` | Provider credit / availability checks (concurrent) |
| `SQLBuilderComponents.py` | 3-step RAG retrieval (ChromaDB → NetworkX → SQLite) |
| `APIManager/PromptBuilder.py` | Maps prompt type strings to `.txt` template files |
| `APIManager/AllAPICaller.py` | Multi-provider LLM caller (OpenAI, Anthropic, Google, GROQ, Codex, Claude Code CLI) |
| `MetadataManager/MetadataStore/RAGPipeline.py` | Embedding + reranking pipeline |
| `MetadataManager/MetadataStore/ManageRelations.py` | NetworkX graph wrapper |
| `MetadataManager/MetadataStore/relationdb/networkxDB.py` | Graph load/save/query |
| `MetadataManager/MetadataBuilder/importExisting/importData.py` | `importDD` — SQLite metadata writer |
| `Utilities/base_utils.py` | `accessDB` (SQLite CRUD), `get_config_val` (YAML config) |

---

## Prompt Templates (`APIManager/Prompts/`)

| File | Prompt Type | Params | Returns |
|------|-------------|--------|---------|
| `taskRequirementGather.txt` | `gather requirements` | `TABLE_DIRECTORY, SCHEMA, FETCHED_SCHEMAS, CONVERSATION` | JSON `{action: get_schema, table}` or `{ready, question/summary}` |
| `taskGenerateSQL.txt` | `generate sql` | `CONVERSATION, SCHEMA` | JSON `{type: sql\|clarify, content}` |
| `taskGenerateSparkSQL.txt` | `generate spark sql` | `CONVERSATION, SCHEMA` | JSON `{type: sql\|clarify, content}` |
| `taskGenerateDataframeAPI.txt` | `generate dataframe api` | `CONVERSATION, SCHEMA` | JSON `{type: code\|clarify, content}` |
| `taskIngestPipeline.txt` | `ingest pipeline` | `SQL, SOURCE_SCHEMAS, COLUMN_MAPPINGS` | JSON `{tableDesc, columns[]}` |
| `taskExtractRelations.txt` | `extract relations` | `SQLQuery` | Relations list |
| `taskGenerateTableSummary.txt` | `create data dict` | — | Table summary |
| `taskGenerateColumnDesc.txt` | `create table summary` | — | Column descriptions |

---

## Storage Locations (from `Utilities/retrieval_config.YAML`)

| Store | Path |
|-------|------|
| SQLite metadata | `MetadataManager/MetadataStore/MetadataStorage/db/table/tableMetadata.db` |
| ChromaDB | `MetadataManager/MetadataStore/MetadataStorage/vdb/` |
| NetworkX pickle | `MetadataManager/MetadataStore/MetadataStorage/relationsdb/Relations.pickle` |
| Config root | `Utilities/config.yaml` → `database_config.YAML`, `retrieval_config.YAML`, `model_config.YAML` |

---

## Two-Agent Query Flow

```
User sends message (with full conversation history)
  │
  POST /api/chat  {messages, provider, query_type}
  │
  ▼  Phase 1 — Requirement Gathering Agent  (gatherRequirements)
  ├─ Sees: table directory (all tables + descriptions)
  ├─ Sees: RAG schema (ChromaDB search on recent user messages)
  ├─ Sees: full conversation history
  │
  │  Tool loop (up to 5 calls):
  ├─ LLM → {"action": "get_schema", "table": "X"}
  │    └─ _get_full_table_schema("X") → SQLite fetch → appended to FETCHED_SCHEMAS
  ├─ LLM → {"action": "get_schema", "table": "Y"}  (repeat as needed)
  │
  ├─ LLM → {"ready": false, "question": "I found table X with column Y — what threshold?"}
  │    └─ Returned to user as clarify bubble
  │
  └─ LLM → {"ready": true, "summary": "...complete requirements..."}
       │
       ▼  Phase 2 — Query Generation Agent  (generateQuery)
       ├─ Uses summary as search query for targeted schema fetch
       ├─ Sees: full conversation (<<CONVERSATION>>) + schema (<<SCHEMA>>)
       └─ Returns SQL / Spark SQL / PySpark code
```

---

## Ingest Pipeline Flow

```
User pastes INSERT…SELECT or CREATE TABLE AS SELECT
  │
  POST /api/ingest/preview
  ├─ parse_pipeline()        → target table, column mappings, source tables
  ├─ get_source_schema()     → fetch source column metadata from SQLite
  ├─ format_source_schemas() → format for LLM
  └─ generate_pipeline_dict() → LLM generates target table data dictionary
  │
  User reviews + edits descriptions + confirms relationships
  │
  POST /api/ingest/commit
  └─ store_table()
       ├─ SQLite: tableDesc + tableColMetadata (source_expr stored in `logic` column)
       ├─ ChromaDB: table description embedding
       └─ NetworkX: source_table → target_table edges
```

---

## Provider Configuration (`APIManager/model_access_config.YAML`)

| Key | Model | Auth |
|-----|-------|------|
| `OPEN_AI` | gpt-3.5-turbo | API key → Bearer token |
| `ANTHROPIC` | claude-3-5-haiku-20241022 | API key → x-api-key · `/v1/messages` |
| `GROQ` | gemma-7b-it | API key → Bearer token |
| `GOOGLE` | gemini-2.0-flash | API key → query param (`?key=`) via `v1beta` |
| `CODEX` | o4-mini | API key → Bearer token (same format as OPEN_AI) |
| `CLAUDE_CODE` | claude-sonnet-4-5 | **CLI subprocess** — uses local `claude` session, no API key |

Balance checking (`GET /api/providers/balance`):
- OpenAI/Codex: tries `/v1/organization/credits` → returns dollar amount
- Anthropic/Claude Code: probes `/v1/models` (key validity) + 1-token POST (credit check)
- GROQ: probes `/openai/v1/models`
- Google: probes models endpoint, checks error status codes
- Claude Code: runs `claude --version` — shows CLI version or "CLI not installed"

---

## Frontend Tabs

| Tab | Component | Description |
|-----|-----------|-------------|
| Query | `ChatInterface` + `SessionPane` + `ChatMessage` | Chat UI with left-pane history. Sessions auto-saved to localStorage (max 30). |
| Schema / ERD | `SchemaERD` + `TableNode` | Interactive React Flow diagram; click table → side pane data dictionary |
| Ingest Table | `IngestTable` | 2-step wizard: paste pipeline SQL → review LLM-generated data dictionary → commit |
| Data Lineage | `DataLineage` | Select table → React Flow neighborhood graph showing connected tables |

---

## Running the App

```bash
# Backend (from project root)
uvicorn backend.app:app --reload

# Frontend (from frontend/)
npm run dev
```

Backend: http://localhost:8000
Frontend: http://localhost:5173

---

## Agent Workflow

| Role | Agent | Responsibilities |
|------|-------|-----------------|
| Planning | Claude + Codex | Review backlog, agree on scope and approach |
| Development | Claude Sonnet 4.6 | Implement features, fix bugs |
| Testing + Commits | OpenAI Codex (o4-mini) | Run tests, add missing tests, git commit with both as co-authors |

Handoff: Claude marks task `[~]` and notes "ready for Codex" → Codex tests → Codex commits → marks `[x]`

---

## Change Log

| Date | Branch | File | Change |
|------|--------|------|--------|
| 2026-03-11 | `Claude/Playground/Dev` | `main.py` | P4: added `_preload_schemas_bulk()` — 2 SQLite queries upfront replace N×2 per-table queries in gather loop; `gatherRequirements` serves `get_schema` calls from cache |
| 2026-03-11 | `Claude/Playground/Dev` | `pyproject.toml` | New: proper project metadata, runtime deps, optional `dev` + `graph-db` extras, pytest config, ruff config |
| 2026-03-11 | `Claude/Playground/Dev` | `TASK.md` | Updated A2 to target Kuzu (embedded, no-server graph DB) instead of Neo4j; added Kuzu to `graph-db` optional extra |
| 2026-03-11 | `Claude/Playground/Dev` | `AGENTS.md`, `TASK.md` | Established two-agent workflow: Claude=developer, Codex=tester+git manager, both=planning |
| 2026-03-07 | `Claude/Playground/Dev` | `backend/balance.py` | Fixed OpenAI `credit_grants` URL: `/dashboard/billing/credit_grants` → `/v1/dashboard/billing/credit_grants`. Added key-validity fallback via `GET /v1/models` for secret keys that cannot access the billing endpoint (returns 403). Provider now correctly shows `N/A` (not greyed out) when key is valid but balance is inaccessible. |
| 2026-03-07 | `Claude/Playground/Dev` | `backend/usage_tracker.py` | New module. Thread-safe in-memory tracker for Claude Code CLI token usage (calls, input_tokens, output_tokens, cost_usd). Resets on backend restart. |
| 2026-03-07 | `Claude/Playground/Dev` | `APIManager/AllAPICaller.py` | Claude Code CLI: switched `--output-format text` → `--output-format json` to capture token usage per call. Records to `usage_tracker`. Falls back to raw stdout on JSON parse failure. |
| 2026-03-07 | `Claude/Playground/Dev` | `backend/balance.py` (`_check_claude_code`) | Label now shows session token usage after calls: `CLI 1.x.x · N↑ M↓ tok · $X.XXXX`. |
| 2026-03-07 | `Claude/Playground/Dev` | `main.py` (`gatherRequirements`) | Non-JSON response from LLM now triggers a one-shot re-prompt with strict JSON correction instruction before falling back. Extracts `options` array from clarify response and passes it through. |
| 2026-03-07 | `Claude/Playground/Dev` | `APIManager/Prompts/taskRequirementGather.txt` | Added `options` array to the clarify JSON format. Strengthened JSON-only enforcement with CRITICAL note. |
| 2026-03-07 | `Claude/Playground/Dev` | `backend/app.py` | `/api/chat` now passes `options` array in clarify responses when present. |
| 2026-03-07 | `Claude/Playground/Dev` | `frontend/src/components/ChatInterface.jsx` | Retry now sends only user `text` messages (strips assistant clarify history) so gathering agent re-evaluates fresh. Added `handleOptionSelect` to send clicked option as a user message. Passes `onOptionSelect` to `ChatMessage`. |
| 2026-03-07 | `Claude/Playground/Dev` | `frontend/src/components/ChatMessage.jsx` | Clarify bubble now renders clickable option buttons (`msg.options`) styled as pill buttons. Accepts `onOptionSelect` prop. |
| 2026-03-08 | `Claude/Playground/Dev` | `main.py` (`generateQuery`) | Fixed empty schema bug: RAG search now uses the original user conversation messages instead of the requirements summary. Summary text is too structured to match ChromaDB table-description embeddings, resulting in empty `## Database Schema`. Two-stage fallback: conversation → summary → log error. |
| 2026-03-08 | `Claude/Playground/Dev` | `APIManager/PromptBuilder.py` (`format_schema`) | Added fallback note when no tables are retrieved, so LLM gets an explicit signal instead of a blank schema section. |
| 2026-03-08 | `Claude/Playground/Dev` | `APIManager/AllAPICaller.py` (claude_code) | Fixed: Claude Code CLI was receiving the full task prompt via `-p` (user message), causing Claude to treat it as pasted content and respond conversationally. Now passes prompt via `--system-prompt` and sends a neutral activation trigger as `-p`. |
| 2026-03-08 | `Claude/Playground/Dev` | Multiple | Added Pandas as a query type: new prompt `taskGeneratePandas.txt`, `validate_pandas()` in `main.py`, registered in `PromptBuilder`, `_VALID_QUERY_TYPES`, `_PROMPT_MAP`, `app.py` Literal, frontend `QUERY_TYPE_LABELS` + `ChatMessage` label/notice. |

---

## Task Backlog

Tasks ordered by impact tier. Status: `[ ]` pending · `[~]` in progress · `[x]` done

### Tier 1 — Security

| ID | Status | Task | Files |
|----|--------|------|-------|
| S1 | [x] | Replace `eval()` with `json.loads()` for API template loading | `APIManager/AllAPICaller.py:68` |
| S2 | [x] | Replace `eval()` with `ast.literal_eval()` for cache deserialization | `Utilities/base_utils.py:308` |
| S3 | [x] | Verify `model_access_config.YAML` was never committed to git history | confirmed clean — no commits found |

### Tier 2 — High Impact, Low Complexity

| ID | Status | Task | Files |
|----|--------|------|-------|
| Q1 | [x] | Remove hardcoded absolute paths — move to env vars or relative paths | `Utilities/base_utils.py:33`, all `Utilities/*.YAML` |
| Q2 | [x] | Remove double `__set_apidict__()` call — called in both `__init__` and `CallService` | `APIManager/AllAPICaller.py` |
| Q3 | [x] | Fix `.gitignore` — replace `/__pycache__` with `**/__pycache__` to catch nested dirs | `.gitignore` |
| Q4 | [x] | Replace all `print()` debug statements with `logging` | `SQLBuilderComponents.py`, `MetadataBuilder/importExisting/importData.py` |

### Tier 3 — High Impact, High Complexity

| ID | Status | Task | Files |
|----|--------|------|-------|
| C1 | [x] | Build structured prompt template — format context as DDL/markdown, not raw dict repr | `main.py`, `APIManager/PromptBuilder.py`, `APIManager/Prompts/taskGenerateSQL.txt` |
| C2 | [x] | Wire reranker scores into actual filtering — threshold or top-k cut on scored results | `SQLBuilderComponents.py`, `Utilities/retrieval_config.YAML` |
| C3 | [x] | Implement `__filterAdditionalColumns__()` — filter columns by relevance to user query | `SQLBuilderComponents.py` |

### Tier 4 — Medium Impact, Medium Complexity

| ID | Status | Task | Files |
|----|--------|------|-------|
| M1 | [x] | Switch `nx.Graph` to `nx.DiGraph` for directional JOIN relationships | `MetadataManager/MetadataStore/relationdb/networkxDB.py` |
| M2 | [x] | Fix silent error swallowing in `importData.py` — preserve original exception | `MetadataManager/MetadataBuilder/importExisting/importData.py` |
| M3 | [x] | Move module-level config/model loading in `RAGPipeline.py` into class `__init__` | `MetadataManager/MetadataStore/RAGPipeline.py` |
| M4 | [x] | Add retry/fallback logic to `CallLLMApi.CallService()` | `APIManager/AllAPICaller.py` |

### Tier 5 — Maintainability & Future-Proofing

| ID | Status | Task | Files |
|----|--------|------|-------|
| F1 | [x] | Introduce `VectorStore` interface to abstract ChromaDB — prep for Pinecone/QDrant | `MetadataManager/MetadataStore/vdb/base.py`, `vdb/Chroma.py`, `RAGPipeline.py` |
| F2 | [x] | Introduce metadata store interface to abstract SQLite — prep for other backends | `Utilities/store_interface.py`, `Utilities/base_utils.py` |
| F3 | [x] | Add a test suite | `tests/test_prompt_builder.py`, `tests/test_filters.py`, `tests/test_base_utils.py` |
| F4 | [x] | Fix `cachefunc.close()` — references `self.connection` which doesn't exist on the class | `Utilities/base_utils.py` |

---

---

## Codex Ideas Backlog
Generated by `o4-mini` on 2026-03-08. Status: `[ ]` pending · `[~]` in progress · `[x]` done

### Performance & Latency

| ID | Status | Idea | Complexity |
|----|--------|------|------------|
| P1 | [ ] | **Streaming LLM responses** — implement token-by-token streaming in FastAPI (StreamingResponse) and show partial tokens in the chat bubble as they arrive | Medium |
| P2 | [ ] | **In-process RAG cache** — cache recent ChromaDB vector search results and NetworkX traversals (e.g. TTL dict) to skip repeated heavy retrievals for the same query | Medium |
| P3 | [ ] | **Async DB & I/O calls** — convert SQLite and ChromaDB interactions to async (aiosqlite / async ChromaDB client) to improve throughput under concurrent load | Low |
| P4 | [x] | **Batch schema fetching** — preload all tool-requested table schemas in one DB round-trip per gather cycle rather than one query per `get_schema` call | Low |
| P5 | [ ] | **Lazy-load ERD** — only fetch and render visible nodes in the Schema/ERD tab; virtualise large graphs (50+ tables) so initial load stays fast | Low |

### Architecture / Scalability

| ID | Status | Idea | Complexity |
|----|--------|------|------------|
| A1 | [ ] | **Migrate metadata to managed DB** — replace local SQLite with PostgreSQL/MySQL to support multi-instance writes, backups, and concurrent access | Medium |
| A2 | [ ] | **Replace NetworkX pickle with Kuzu (embedded graph DB)** — Kuzu is SQLite-style (no server), has Python bindings + Cypher support, and replaces the pickle file with a real persistent graph store. Swap `networkxDB.py` → `kuzuDB.py` behind the existing `ManageRelations` interface; auto-migrate existing pickle on first run. Add `kuzu` to `pyproject.toml` `graph-db` extra. | Medium |
| A3 | [ ] | **Configurable tool-loop cap** — externalise `gatherRequirements` iteration limit (currently hard-coded 5) and per-call timeout to `config.yaml` | Low |
| A4 | [ ] | **API rate limiting & request queuing** — add a token-bucket rate-limiter at the FastAPI layer (e.g. `slowapi`) to protect downstream LLM services | Medium |
| A5 | [ ] | **Authentication & multi-tenancy** — add OAuth2 / JWT auth and isolate per-user sessions and metadata | High |

### UX / Frontend

| ID | Status | Idea | Complexity |
|----|--------|------|------------|
| U1 | [ ] | **ERD search/filter** — add a search bar and tag-filter on the Schema/ERD tab to locate tables quickly in large schemas | Low |
| U2 | [ ] | **Streaming chat UI** — show SQL/code tokens incrementally with a "Stop" button; pairs with P1 | Medium |
| U3 | [ ] | **Session export/import** — allow exporting a session as JSON or Markdown and re-importing it, bypassing the localStorage 5 MB limit | Low |
| U4 | [ ] | **Ingest diff view** — side-by-side before/after diff of original vs LLM-suggested data dictionary fields during ingestion review | Medium |
| U5 | [ ] | **Mobile responsiveness** — ensure chat and schema views adapt to small screens | Low |
| U6 | [ ] | **ERD edge types** — render relationship arrows with directionality annotations (1:1, 1:n, n:1, n:m) instead of flat arrows in the Schema/ERD view | Medium |

### Backend Robustness

| ID | Status | Idea | Complexity |
|----|--------|------|------------|
| B1 | [ ] | **Circuit breakers for LLM providers** — halt requests to a failing provider after N consecutive errors and recover after a cooldown, using `pybreaker` or similar | Medium |
| B2 | [ ] | **Thread-safe graph store** — wrap NetworkX pickle load/save in a `threading.Lock` (or replace with an in-memory concurrent structure) to prevent race conditions on the server | Medium |
| B3 | [ ] | **Structured logging & metrics** — emit JSON log lines and expose a Prometheus endpoint for request latencies, error rates, and LLM call counts | Medium |
| B4 | [x] | **Migrate Anthropic to `/v1/messages`** — drop legacy `/v1/complete` + `claude-2.0`; update template and auth header; use `claude-haiku-4-5` or newer | Low |

### Testing Coverage Gaps

| ID | Status | Idea | Complexity |
|----|--------|------|------------|
| T1 | [ ] | **RAG pipeline integration tests** — spin up a temporary ChromaDB + NetworkX graph and validate retrieval accuracy end-to-end | Medium |
| T2 | [ ] | **Failure-scenario fixtures** — pytest fixtures that simulate LLM timeouts, rate-limit 429s, and malformed responses to verify graceful degradation | Low |
| T3 | [ ] | **Frontend component tests** — Jest + React Testing Library coverage for Chat bubble rendering, ERD node interactions, and Ingest Wizard steps | Medium |
| T4 | [ ] | **Load tests** — Locust scenarios for concurrent chat sessions to surface throughput bottlenecks before they hit production | Medium |

### Developer Experience

| ID | Status | Idea | Complexity |
|----|--------|------|------------|
| D1 | [ ] | **Docker Compose dev environment** — single `docker compose up` that starts the backend, frontend, and dependency stubs (mock LLM, ChromaDB, SQLite) | Medium |
| D2 | [ ] | **Pre-commit linting hooks** — add `black`, `isort`, `flake8`, and `mypy` as pre-commit hooks for consistent style and early type errors | Low |
| D3 | [ ] | **OpenAPI / Swagger playground** — enable FastAPI's auto-generated interactive docs at `/docs` for backend exploration without a running frontend | Low |
| D4 | [ ] | **Contributor onboarding guide** — architecture diagram + step-by-step local setup in `CONTRIBUTING.md` | Low |
| D5 | [ ] | **FastMCP wrapper** — publish this tool as a FastMCP server that exposes `generateQuery`, `generatePipelineDict`, and other helpers via typed tools/resources so Claude and other MCP clients can invoke them with schema validation | Medium |

---

## Known Behaviours / Notes

- **Two-agent loop**: `gatherRequirements()` runs up to 5 `get_schema` tool calls before forcing a final answer. The code fence regex strips any language tag (```json, ```sql, etc.) before JSON parsing.
- **NetworkX graph type**: Existing `Relations.pickle` may be an undirected `nx.Graph`. The lineage endpoint uses `graph.is_directed()` to pick the right neighbor accessor.
- **LLM response format**: All query prompts return JSON `{type, content}`. `validate_sql` falls back gracefully if the LLM returns raw SQL.
- **SQLAlchemy driver**: `sqlalchemy>=2.0` is in `requirements.txt` but DB-specific drivers (e.g. `psycopg2`, `pymysql`) must be installed separately.
- **Row cap**: `/api/execute` returns at most 500 rows via `fetchmany(500)`.
- **Embedding model**: `mixedbread-ai/mxbai-embed-large-v1` loaded from local path in `retrieval_config.YAML`.
- **Claude Code CLI**: Requires `claude` on PATH (`npm install -g @anthropic-ai/claude-code`). Subprocess uses `encoding="utf-8"` to avoid Windows cp1252 decode errors.
- **Conversation history**: Stored in `localStorage` under key `data_compass_sessions`. Sessions include full message list, provider, and query type so they can be fully resumed.
- **Anthropic Messages API**: `anthropic` provider uses `/v1/messages` with `claude-3-5-haiku-20241022`. `claude_code` uses the CLI (bypasses API entirely).

## Codex Work Log

### Requirements & Plan (Codex)
- Requirement (2026-03-08): Document all Codex work in this file. Review the Claude Code guidance, ensure Claude balance + clarify UX are covered, and reflect every step in tests and UI behaviour. Plan: inspect balance/usage modules, add `_check_claude_code` regression tests, extend ChatInterface clarify/provider tests (with a scroll-to-bottom stub), and rerun backend/frontend suites, logging results.

### Actions Completed
- 2026-03-08: Reviewed `backend/balance.py`, `backend/usage_tracker.py`, `APIManager/AllAPICaller.py`. Added `tests/test_balance.py` to cover CLI missing/available/usage labels (pytest run succeeded). Recorded the initial Vitest `esbuild` `EPERM` failure, then stubbed `scrollIntoView`, added `frontend/src/components/__tests__/ChatInterface.test.jsx` to confirm Claude dropdown labels, availability disabling, and clarify-option pills, and reran `npm test -- ChatInterface` successfully.

### Requirements & Plan (Codex)
- Requirement (2026-03-08): The lineage view is showing generic neighbor data instead of the actual lineage subgraph, and the ingest pipeline dropdown lacks the same provider formatting and balance-awareness as the query tab. Plan: expand `/api/lineage/{table}` to return the connected lineage subgraph (nodes + edges) so the UI can render true lineage, centralize provider labels/formatting, update ChatInterface + IngestTable selects to reuse them, fetch provider balances for ingest, and add component tests to lock in the new dropdown behavior.

### Actions Completed
- 2026-03-08: Updated `backend/app.py` so `/api/lineage/{table}` now returns every node/edge in the connected component via `networkx.node_connected_component`, removed the old neighbor-only logic, and kept the `joinKeys`. Added `frontend/src/constants/providerLabels.js`, wired `ChatInterface.jsx` and `IngestTable.jsx` to reuse the provider label helper, fetch provider balances for the ingest dropdown, and newly added `frontend/src/components/__tests__/IngestTable.test.jsx` to assert balance-aware rendering. Ran the backend and frontend suites (pytest + `npm test -- ChatInterface` + `npm test -- IngestTable`).

### Requirements & Plan (Codex)
- Requirement (2026-03-08): Integrate the OpenAI Codex provider into the Query Generation UI so users can select it alongside the other models, and ensure both query and ingest dropdowns stay in sync with the backend's finance data.
- Plan: make the App-level provider list include Codex, expand the App and IngestTable component tests to cover the Codex label/availability plumbing, and rerun the relevant Vitest suites before logging the results.

### Actions Completed
- 2026-03-08: Extended `App.test.jsx` so the mocked `/api/providers` response defaults to `['anthropic', 'codex', 'open_ai']` and verified the dropdown options now include Codex. Added a Codex-specific assertion to `frontend/src/components/__tests__/IngestTable.test.jsx` so the ingest dropdown renders the `OpenAI Codex` label from `providerLabels`. Ran `npm test -- App`, `npm test -- ChatInterface`, and `npm test -- IngestTable` to confirm coverage.
- 2026-03-08: Tightened the Codex test so it no longer relies on the encoded dash sequence; the assertion now matches any option whose accessible name contains `OpenAI Codex` and also checks the `$0.03` label, keeping the dropdown coverage resilient to minor spacing/encoding differences.

### Requirements & Plan (Codex)
- Requirement (2026-03-08): Package the query/ingest/lineage helpers as FastMCP tools so Claude (and other MCP clients) can call them with schema validation and streaming results.
- Plan: create FastMCP tool definitions for `generateQuery`, `generatePipelineDict`, and relevant fetch helpers, document their JSON schemas and prompt/resource expectations, and add a README entry that explains how to run the FastMCP server locally before publishing.

### Actions Completed — 2026-03-11 (B4)
- Confirmed `ANTHROPIC.json` already uses `/v1/messages` + `claude-3-5-haiku-20241022` (migration was complete but untracked). Updated `TASK.md` provider table and Known Behaviours note. Added `TestCheckAnthropic` (4 tests: invalid key, no credits, valid key/N/A, network error) to `tests/test_balance.py` — all pass.

### Actions Completed — 2026-03-11
- feat: multi-DB instance support across all storage layers (SQLite, ChromaDB, NetworkX)
  - `instance_name` + `db_type` columns added to `tableDesc` and `tableColMetadata` (with ALTER TABLE migration)
  - NetworkX pickle migrated to `{instance_name: DiGraph}` dict format (backward-compatible)
  - ChromaDB queries filter by `DB=instance_name` when not "default"
  - New `GET /api/instances` endpoint; all schema/chat/ingest endpoints accept `instance_name`
  - Frontend: instance selector in ChatInterface, SchemaERD; DB type + instance name in IngestTable
  - `DB_TYPES` constant added to `providerLabels.js`
- feat: replaced Data Lineage tab with Join Path Explorer
  - New `GET /api/joinpath?from_table=X&to_table=Y` returns shortest join path with cardinality
  - New `GET /api/derivatives/{table}` returns pipeline parent/child tables
  - `DataLineage.jsx` rewritten: Join Path tab + Derivative Tables tab
  - Tab renamed "Data Lineage" → "Join Path" in `App.jsx`
### Requirements & Plan (Codex)
- Requirement (2026-03-11): Review Claude's workspace changes, focus on the latest DataLineage/Join Path tweaks, rerun the frontend suites, and log the results so the change log matches reality.
- Plan: inspect the current buildFlow/edge rendering changes, run `npm test -- App ChatInterface IngestTable`, and capture both successes and the environment-level EPERM failures in this log.

### Actions Completed - 2026-03-11
- Confirmed `buildFlow` now accepts the optional `joinTypeFilter`, reuses the shared `joinTypeColors` map, and still shows the join key labels per edge.
- Tried `npm test -- App ChatInterface IngestTable` plus the standalone `ChatInterface`/`IngestTable` suites, but each run stops while `esbuild` tries to bundle `vite.config.js` because the spawned service is blocked with EPERM. Overriding `ESBUILD_BINARY_PATH` and redirecting `TMP`/`TEMP` to `./tmp` did not remove the restriction, so Vitest remains unable to start until the environment lets `esbuild` spawn again.
- Added `_preload_schemas_bulk` coverage (`tests/test_main_preload.py`), adjusted `tests/test_api.py` and `tests/test_filters.py` for the new `instance_name` plumbing, reran `pytest tests/` with `PYTHONPATH='.'` (all 101 tests pass), and committed the staged changes (main.py, pyproject.toml, TASK.md, DataLineage.jsx, plus the new tests) with both agents as co-authors.
