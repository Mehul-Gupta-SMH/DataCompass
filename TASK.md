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
