# Poly-QL — Storage Layer

All persistent stores and how they are accessed.

```mermaid
graph TB
    subgraph Access ["Access Layer (Python modules)"]
        A1["base_utils.accessDB\nSQLite CRUD via sqlite3"]
        A2["ChromaVectorStore\n(vdb/Chroma.py)\ninterface: BaseVectorStore"]
        A3["kuzuDB.py\nKuzu Cypher queries\nauto-migrates Relations.pickle"]
        A4["outcome_store.py\nappend-only writer"]
        A5["backend/auth.py\nJWT + session management"]
    end

    subgraph SQLiteDB ["SQLite — tableMetadata.db"]
        T1["tableDesc\n(tableName, tableDesc,\ninstance_name, db_type)"]
        T2["tableColMetadata\n(tableName, ColumnName,\nDataType, Constraints, Desc,\nlogic, type_of_logic, base_table,\ninstance_name, db_type)"]
    end

    subgraph AuthDB ["SQLite — auth.db"]
        T3["users\n(id, username, password_hash,\ngoogle_id, created_at)"]
        T4["sessions / conversations\n(per-user conversation history)"]
    end

    subgraph VDB ["ChromaDB — vdb/"]
        C1["Collection: table_descriptions\nEmbedding model: mxbai-embed-large-v1\nMetadata filter: DB=instance_name"]
    end

    subgraph GraphDB ["Kuzu — relationsdb/"]
        K1["Node: Table (name)\nEdge: JOINS (join_keys, cardinality)\nAuto-migrated from Relations.pickle\nOne DB per instance_name"]
    end

    subgraph OutcomeDB ["Outcome Store — validation/corpus/"]
        O1["outcomes.jsonl\nAppend-only; one JSON line per execution\n{session_id, nl_query, generated_sql,\nprovider, query_type, outcome,\nerror_type, row_count, latency_ms, ts}"]
        O2["outcomes.db\nSQLite index for date/provider/outcome\nread-optimised secondary store"]
    end

    A1 --> T1 & T2
    A2 --> C1
    A3 --> K1
    A4 --> O1 & O2
    A5 --> T3 & T4
```

## What lives where

| Data | Store | Why |
|------|-------|-----|
| Table + column metadata, descriptions | SQLite (`tableMetadata.db`) | Structured, relational, fast point lookups by table name |
| Table description embeddings | ChromaDB | Cosine similarity search for RAG retrieval |
| JOIN relationships | Kuzu (embedded graph) | Graph traversal for join-path finding and lineage |
| User accounts, auth tokens | SQLite (`auth.db`) | Simple relational; PyJWT for token generation |
| Query execution outcomes | JSONL + SQLite index | JSONL for durability / portability; SQLite index for analytics queries |
| Session conversation history | `localStorage` (frontend) | No server-side session storage needed; 30-session cap |

## Instance isolation

All stores support `instance_name` scoping so multiple database environments (e.g. `prod_snowflake`, `dev_databricks`) can coexist:

- **SQLite**: `instance_name` column on `tableDesc` and `tableColMetadata`; queries filter by `WHERE instance_name = ?`
- **ChromaDB**: metadata filter `{"DB": instance_name}` on every collection query
- **Kuzu**: separate database directory per instance (`relationsdb/{instance_name}/`)

## Migration notes

- **NetworkX → Kuzu**: `kuzuDB.py` auto-detects `Relations.pickle` on first run and migrates edges into Kuzu; pickle is preserved but no longer read after migration
- **SQLite schema evolution**: New columns added via `ALTER TABLE ... ADD COLUMN` (non-breaking; existing rows default to `''` or `NULL`)
