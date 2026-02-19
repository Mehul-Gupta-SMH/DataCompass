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
