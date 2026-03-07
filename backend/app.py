import sys
import os
from typing import Literal, List

# Ensure project root is on the path so `main` can be imported directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main import generateQuery, gatherRequirements, SQLValidationError, _VALID_PROVIDERS

app = FastAPI(title="SQLCoder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    provider: str
    query_type: Literal["sql", "spark_sql", "dataframe_api"] = "sql"


class ExecuteRequest(BaseModel):
    generated_query: str
    query_type: Literal["sql", "spark_sql"]
    connection_string: str


class ChatMessageItem(BaseModel):
    role: str      # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessageItem]
    provider: str
    query_type: Literal["sql", "spark_sql", "dataframe_api"] = "sql"


class IngestPreviewRequest(BaseModel):
    sql: str
    provider: str


class ColumnMeta(BaseModel):
    name: str
    type: str = ""
    constraints: str = ""
    desc: str = ""
    source_expr: str = ""   # pipeline lineage — stored in the `logic` field


class RelationshipMeta(BaseModel):
    source: str
    target: str
    join_keys: str = ""


class IngestCommitRequest(BaseModel):
    table_name: str
    table_desc: str
    columns: List[ColumnMeta]
    relationships: List[RelationshipMeta] = []


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------

@app.get("/api/providers")
def get_providers():
    return {"providers": sorted(_VALID_PROVIDERS)}


@app.get("/api/providers/balance")
def get_providers_balance():
    from backend.balance import get_all_balances
    balances = get_all_balances(list(_VALID_PROVIDERS))
    return {"balances": balances}


@app.post("/api/chat")
def post_chat(body: ChatRequest):
    """
    Two-phase chat endpoint.

    Phase 1 — Requirement Gathering Agent:
      Receives the full conversation history, sees all table names + retrieved schema,
      and either asks a clarifying question or declares it has enough information.

    Phase 2 — Query Generation Agent (only when Phase 1 is ready):
      Uses the requirements summary from Phase 1 as input to generate SQL / Spark SQL / PySpark.
    """
    messages = [m.model_dump() for m in body.messages]

    try:
        gather = gatherRequirements(messages, body.provider)
    except (ValueError, SQLValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Requirement gathering failed: {exc}")

    if not gather.get("ready"):
        return {
            "type": "clarify",
            "sql": gather.get("question", "Could you provide more details?"),
            "query_type": body.query_type,
        }

    try:
        result = generateQuery(gather["summary"], body.provider, body.query_type, messages)
    except (ValueError, SQLValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query generation failed: {exc}")

    return {
        "type": result["type"],
        "sql": result["content"],
        "query_type": body.query_type,
    }


@app.post("/api/query")
def post_query(body: QueryRequest):
    try:
        result = generateQuery(body.query, body.provider, body.query_type)
        # result = {"type": "sql"|"code"|"clarify", "content": str}
        return {
            "type": result["type"],          # "sql", "code", or "clarify"
            "sql": result["content"],         # keep "sql" key for compat
            "query_type": body.query_type,
        }
    except (ValueError, SQLValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/execute")
def post_execute(body: ExecuteRequest):
    from backend.executor import execute_query
    try:
        columns, rows = execute_query(body.generated_query, body.query_type, body.connection_string)
        return {"columns": columns, "rows": rows}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(exc)}")


@app.get("/api/schema")
def get_schema():
    from MetadataManager.MetadataStore.relationdb import networkxDB
    from Utilities.base_utils import accessDB, get_config_val

    graph = networkxDB.getObj()

    tmddb = get_config_val("retrieval_config", ["tableMDdb"], True)
    db = accessDB(tmddb["info_type"], tmddb["dbName"])

    tables = []
    for table in sorted(graph.nodes()):
        desc_row = db.get_data(tmddb["tableDescName"], {"tableName": table}, ["Desc"])
        cols = db.get_data(
            tmddb["tableColName"], {"TableName": table},
            ["ColumnName", "DataType", "Constraints", "Desc"], fetchtype="All"
        ) or []
        tables.append({
            "name": table,
            "description": desc_row[0] if desc_row else "",
            "columns": [
                {"name": c[0], "type": c[1] or "", "constraints": c[2] or "", "description": c[3] or ""}
                for c in cols
            ],
        })

    seen = set()
    relations = []
    for src, tgt, data in graph.edges(data=True):
        key = tuple(sorted([src, tgt]))
        if key not in seen:
            seen.add(key)
            relations.append({"source": src, "target": tgt, "joinKeys": data.get("JoinKeys", [])})

    return {"tables": tables, "relations": relations}


# ---------------------------------------------------------------------------
# Ingest endpoints
# ---------------------------------------------------------------------------

@app.post("/api/ingest/preview")
def post_ingest_preview(body: IngestPreviewRequest):
    """
    Parse a data pipeline SQL (INSERT...SELECT or CTAS), look up source table schemas,
    call the LLM to generate the target table data dictionary, and return a preview
    for the user to review before committing.
    """
    from backend.ingestion import (
        parse_pipeline, get_source_schema,
        format_source_schemas, format_column_mappings,
    )
    from main import generate_pipeline_dict

    try:
        parsed = parse_pipeline(body.sql)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    source_schema = get_source_schema(parsed["source_tables"])
    schemas_str = format_source_schemas(source_schema)
    mappings_str = format_column_mappings(parsed["column_mappings"])

    try:
        dd = generate_pipeline_dict(body.sql, schemas_str, mappings_str, body.provider)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(exc)}")

    desc_map = {c["name"]: c["desc"] for c in dd.get("columns", [])}
    columns = [
        {
            "name": m["target"],
            "type": "",           # type not available from SELECT — user can fill in
            "constraints": "",
            "desc": desc_map.get(m["target"], ""),
            "source_expr": m["source_expr"],
        }
        for m in parsed["column_mappings"]
    ]

    # Auto-build relationships: each source table → target table
    auto_relationships = [
        {"source": src, "target": parsed["target_table"], "join_keys": ""}
        for src in parsed["source_tables"]
    ]

    return {
        "table_name": parsed["target_table"],
        "table_desc": dd.get("tableDesc", ""),
        "columns": columns,
        "source_tables": parsed["source_tables"],
        "relationships": auto_relationships,
    }


@app.post("/api/ingest/commit")
def post_ingest_commit(body: IngestCommitRequest):
    """
    Store the reviewed table metadata to SQLite, ChromaDB, and NetworkX.
    """
    from backend.ingestion import store_table

    try:
        store_table(
            table_name=body.table_name,
            table_desc=body.table_desc,
            columns=[c.model_dump() for c in body.columns],
            relationships=[r.model_dump() for r in body.relationships],
        )
        return {"success": True, "table": body.table_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Commit error: {str(exc)}")


# ---------------------------------------------------------------------------
# Lineage endpoint
# ---------------------------------------------------------------------------

@app.get("/api/lineage/{table_name}")
def get_lineage(table_name: str):
    """
    Return the direct-neighbor lineage for a table from the NetworkX graph.
    Edges are bidirectional in the graph, so all neighbors are returned as 'related'.
    """
    from MetadataManager.MetadataStore.relationdb import networkxDB

    graph = networkxDB.getObj()
    name = table_name.lower()

    if name not in graph.nodes():
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found in schema.")

    # graph may be nx.Graph (undirected) or nx.DiGraph — neighbors() works on both.
    # For DiGraph, edges are stored bidirectionally so neighbors() covers all connections.
    get_neighbors = (
        (lambda n: set(graph.successors(n)) | set(graph.predecessors(n)))
        if graph.is_directed()
        else (lambda n: set(graph.neighbors(n)))
    )
    neighbors = get_neighbors(name) - {name}

    nodes = [{"id": name, "role": "center"}]
    nodes.extend({"id": n, "role": "related"} for n in sorted(neighbors))

    # Deduplicate edges (graph is bidirectional — each pair stored in both directions)
    seen_edges = set()
    edges = []
    for src, tgt, data in graph.edges(data=True):
        if name not in (src, tgt):
            continue
        key = tuple(sorted([src, tgt]))
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({
                "source": src,
                "target": tgt,
                "joinKeys": data.get("JoinKeys", ""),
            })

    return {"center": name, "nodes": nodes, "edges": edges}
