# Poly-QL — Ingest Pipeline Flow

How a pipeline SQL statement becomes a documented table in the schema.

```mermaid
flowchart TD
    A["👤 User pastes SQL\nINSERT INTO ... SELECT ...\nor CREATE TABLE ... AS SELECT ..."]

    subgraph Preview ["POST /api/ingest/preview"]
        B["parse_pipeline(sql)\nbackend/ingestion.py"]
        C["Extracted:\n• target table name\n• column list + mappings\n• source table names"]
        D["get_source_schema(source_tables)\nFetch column metadata from SQLite"]
        E["format_source_schemas()\nBuild LLM-readable schema block"]
        F["generate_pipeline_dict(sql, source_schemas, column_mappings)\nLLM call: taskIngestPipeline.txt"]
        G["LLM returns:\n{tableDesc, columns[{name, DataType,\nDesc, logic, type_of_logic, base_table}]}"]
    end

    H["Frontend shows review UI\n• Edit table/column descriptions\n• Confirm source relationships"]

    subgraph Commit ["POST /api/ingest/commit"]
        I["store_table(table_dict, instance_name)"]
        J1["SQLite\ntableDesc + tableColMetadata\n(source_expr stored in logic column)"]
        J2["ChromaDB\nTable description embedding\n(mxbai-embed-large-v1)"]
        J3["Kuzu graph\nsource_table → target_table edges\n(derivation lineage)"]
    end

    K["Table available in schema\n• Queryable via /api/chat\n• Visible in Schema/ERD tab\n• Lineage visible in Join Path tab"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J1
    I --> J2
    I --> J3
    J1 & J2 & J3 --> K
```

## Qualified Name Support (C4)

Pipeline SQL can reference tables with fully-qualified names (`database.schema.table`).
`parse_pipeline()` uses alternation regex to capture quoted and unquoted forms:

```
backtick:      `database.schema.table`
double-quote:  "database.schema.table"
bracket:       [database.schema.table]
bare:          database.schema.table  (dot-separated \w+ tokens)
```

All four forms are normalised to a plain string and stored as-is in the metadata tables.
The `_extract_name()` helper selects the first non-None capture group from the regex match.

## Supported SQL Forms

| Form | Example |
|------|---------|
| `INSERT INTO ... SELECT` | `INSERT INTO target (col1, col2) SELECT a, b FROM source` |
| CTAS | `CREATE TABLE target AS SELECT ...` |
| CTAS with IF NOT EXISTS | `CREATE TABLE IF NOT EXISTS target AS SELECT ...` |
| Qualified target | `INSERT INTO db.schema.target (...)` |
| Qualified sources | `FROM prod.sales.orders o JOIN prod.dim.customers c ON ...` |
