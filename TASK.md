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
DataLineage                       POST /api/ingest/commit
                                  POST /api/execute
                                  GET  /api/schema
                                  GET  /api/lineage/{table}
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
| `ANTHROPIC` | claude-2.0 | API key → x-api-key (legacy `/v1/complete`) |
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

## Change Log

| Date | Branch | File | Change |
|------|--------|------|--------|
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

## Known Behaviours / Notes

- **Two-agent loop**: `gatherRequirements()` runs up to 5 `get_schema` tool calls before forcing a final answer. The code fence regex strips any language tag (```json, ```sql, etc.) before JSON parsing.
- **NetworkX graph type**: Existing `Relations.pickle` may be an undirected `nx.Graph`. The lineage endpoint uses `graph.is_directed()` to pick the right neighbor accessor.
- **LLM response format**: All query prompts return JSON `{type, content}`. `validate_sql` falls back gracefully if the LLM returns raw SQL.
- **SQLAlchemy driver**: `sqlalchemy>=2.0` is in `requirements.txt` but DB-specific drivers (e.g. `psycopg2`, `pymysql`) must be installed separately.
- **Row cap**: `/api/execute` returns at most 500 rows via `fetchmany(500)`.
- **Embedding model**: `mixedbread-ai/mxbai-embed-large-v1` loaded from local path in `retrieval_config.YAML`.
- **Claude Code CLI**: Requires `claude` on PATH (`npm install -g @anthropic-ai/claude-code`). Subprocess uses `encoding="utf-8"` to avoid Windows cp1252 decode errors.
- **Conversation history**: Stored in `localStorage` under key `data_compass_sessions`. Sessions include full message list, provider, and query type so they can be fully resumed.
- **Anthropic legacy vs Messages API**: `anthropic` provider uses old `/v1/complete` + `claude-2.0`. `claude_code` uses the CLI (bypasses API entirely). A future migration to `/v1/messages` for the `anthropic` provider is recommended.
