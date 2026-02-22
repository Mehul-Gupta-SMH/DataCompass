import sys
import os

# Ensure project root is on the path so `main` can be imported directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main import generateQuery, SQLValidationError, _VALID_PROVIDERS

app = FastAPI(title="SQLCoder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class QueryRequest(BaseModel):
    query: str
    provider: str


@app.get("/api/providers")
def get_providers():
    return {"providers": sorted(_VALID_PROVIDERS)}


@app.post("/api/query")
def post_query(body: QueryRequest):
    from fastapi import HTTPException
    try:
        sql = generateQuery(body.query, body.provider)
        return {"sql": sql}
    except (ValueError, SQLValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/schema")
def get_schema():
    from MetadataManager.MetadataStore.relationdb import networkxDB
    from Utilities.base_utils import accessDB, get_config_val

    graph = networkxDB.getObj()   # loads Relations.pickle; empty DiGraph if file absent

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

    # Graph is bidirectional — keep one canonical edge per pair
    seen = set()
    relations = []
    for src, tgt, data in graph.edges(data=True):
        key = tuple(sorted([src, tgt]))
        if key not in seen:
            seen.add(key)
            relations.append({"source": src, "target": tgt, "joinKeys": data.get("JoinKeys", [])})

    return {"tables": tables, "relations": relations}
