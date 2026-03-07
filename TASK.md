# Data Compass — Project Task Reference

## What is this project?
**Data Compass** (formerly SQLCoder) is a full-stack AI-powered data query and metadata management tool.
Users describe questions in natural language; the system retrieves the relevant schema context, calls an LLM, and returns SQL / Spark SQL / PySpark DataFrame code. It also supports ingesting new pipeline tables and browsing data lineage.

---

## Architecture

```
frontend/ (Vite + React)          backend/ (FastAPI)            Storage
──────────────────────            ──────────────────            ───────
ChatInterface                     POST /api/query               ChromaDB (vector embeddings)
  └─ ChatMessage                    └─ generateQuery()           NetworkX graph (Relations.pickle)
SchemaERD                               └─ getRelevantContext()  SQLite (tableMetadata.db)
  └─ TableNode                              1. RAG table lookup
IngestTable                               2. Graph join paths
DataLineage                               3. Column metadata
                                  POST /api/ingest/preview
                                    └─ parse_pipeline()
                                    └─ get_source_schema()
                                    └─ generate_pipeline_dict()
                                  POST /api/ingest/commit
                                    └─ store_table() → SQLite + ChromaDB + NetworkX
                                  POST /api/execute
                                    └─ execute_query() → SQLAlchemy
                                  GET  /api/schema
                                  GET  /api/lineage/{table}
                                  GET  /api/providers
```

---

## Key Files

| File | Role |
|------|------|
| `main.py` | `generateQuery()`, `generate_pipeline_dict()`, `validate_sql()`, `validate_pyspark()` |
| `backend/app.py` | FastAPI routes |
| `backend/ingestion.py` | `parse_pipeline()`, `get_source_schema()`, `store_table()` |
| `backend/executor.py` | SQLAlchemy query execution (500 row cap) |
| `SQLBuilderComponents.py` | 3-step RAG retrieval (ChromaDB → NetworkX → SQLite) |
| `APIManager/PromptBuilder.py` | Maps prompt type strings to `.txt` template files |
| `APIManager/AllAPICaller.py` | Multi-provider LLM caller (OpenAI, Anthropic, Google, GROQ) |
| `MetadataManager/MetadataStore/RAGPipeline.py` | Embedding + reranking pipeline |
| `MetadataManager/MetadataStore/ManageRelations.py` | NetworkX graph wrapper |
| `MetadataManager/MetadataStore/relationdb/networkxDB.py` | Graph load/save/query |
| `MetadataManager/MetadataBuilder/importExisting/importData.py` | `importDD` — SQLite metadata writer |
| `Utilities/base_utils.py` | `accessDB` (SQLite CRUD), `get_config_val` (YAML config) |

---

## Prompt Templates (`APIManager/Prompts/`)

| File | Prompt Type | Params | Returns |
|------|-------------|--------|---------|
| `taskGenerateSQL.txt` | `generate sql` | `SCHEMA` | JSON `{type: sql\|clarify, content}` |
| `taskGenerateSparkSQL.txt` | `generate spark sql` | `SCHEMA` | JSON `{type: sql\|clarify, content}` |
| `taskGenerateDataframeAPI.txt` | `generate dataframe api` | `SCHEMA` | JSON `{type: code\|clarify, content}` |
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

## Query Generation Flow (3-Step Retrieval)

```
User question
  │
  ▼  Step 1 — Table Discovery
  SQLBuilderSupport.__getRelevantTables__()
    → embed question with SentenceTransformer (mxbai-embed-large-v1)
    → ChromaDB cosine search (top 3)
    → FlagReranker + BM25 scoring + threshold filter
  │
  ▼  Step 2 — Join Path Resolution
  SQLBuilderSupport.__getTableRelations__()
    → NetworkX: shortest path between discovered tables
    → __getInterTablesDesc__() adds intermediate tables
  │
  ▼  Step 3 — Column Metadata
  SQLBuilderSupport.__getTablesColList__()
    → SQLite: fetch all columns for direct + intermediate tables
    → BM25 column-level filtering
  │
  ▼  Prompt Assembly
  PromptBuilder.format_schema(context) → markdown schema string
  PromptBuilder('generate sql').build({'SCHEMA': schema_str}) → filled prompt
  │
  ▼  LLM Call + Response Handling
  CallLLMApi.CallService(prompt)
  validate_sql() / validate_pyspark()
    → parses JSON envelope {type, content}
    → if type == "clarify": returns question to user (no SQL validation)
    → if type == "sql":     validates with sqlparse, returns SQL
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

## Frontend Tabs

| Tab | Component | Description |
|-----|-----------|-------------|
| Query | `ChatInterface` + `ChatMessage` | Chat UI — sends questions, receives SQL or clarifying questions |
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

- **NetworkX graph type**: Existing `Relations.pickle` may be an undirected `nx.Graph` (not `DiGraph`). The lineage endpoint uses `graph.is_directed()` to pick the right neighbor accessor.
- **LLM response format**: All three query prompts now return JSON `{type, content}`. `validate_sql` falls back gracefully if the LLM returns raw SQL instead.
- **SQLAlchemy driver**: `sqlalchemy>=2.0` is in `requirements.txt` but DB-specific drivers (e.g. `psycopg2`, `pymysql`) must be installed separately by the user.
- **Row cap**: `/api/execute` returns at most 500 rows via `fetchmany(500)`.
- **Embedding model**: `mixedbread-ai/mxbai-embed-large-v1` loaded from local path in `retrieval_config.YAML`.
