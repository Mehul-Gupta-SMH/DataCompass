"""
backend/glossary.py — SL3: Business Glossary REST API

Routes (all under /api/glossary):
  POST   /api/glossary/terms          — add one term (or bulk list)
  GET    /api/glossary/terms          — list terms (?instance_name=&domain=)
  GET    /api/glossary/terms/{id}     — get term by ID
  PUT    /api/glossary/terms/{id}     — update term fields
  DELETE /api/glossary/terms/{id}     — delete term
  GET    /api/glossary/search         — lexical search (?q=&instance_name=)
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/glossary", tags=["glossary"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TermIn(BaseModel):
    term_id:       Optional[str]       = None
    term_name:     str
    full_name:     Optional[str]       = None
    definition:    Optional[str]       = None
    formula:       Optional[str]       = None
    formula_type:  Optional[str]       = None
    table_deps:    Optional[List[str]] = None
    column_deps:   Optional[List[str]] = None
    synonyms:      Optional[List[str]] = None
    example_value: Optional[str]       = None
    domain:        Optional[str]       = None
    instance_name: Optional[str]       = ""


class TermUpdate(BaseModel):
    full_name:     Optional[str]       = None
    definition:    Optional[str]       = None
    formula:       Optional[str]       = None
    formula_type:  Optional[str]       = None
    table_deps:    Optional[List[str]] = None
    column_deps:   Optional[List[str]] = None
    synonyms:      Optional[List[str]] = None
    example_value: Optional[str]       = None
    domain:        Optional[str]       = None
    instance_name: Optional[str]       = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/terms", status_code=201)
def create_terms(body):
    """
    Add one or more business terms.

    Accepts either a single TermIn object or a list of TermIn objects.
    Returns a list of created term_ids.
    """
    from MetadataManager.GlossaryStore import add_term

    # Accept both a single object and a list
    if isinstance(body, list):
        items = body
    else:
        items = [body]

    created = []
    for item in items:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        try:
            tid = add_term(data)
            created.append(tid)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    return {"created": created}


@router.post("/terms/bulk", status_code=201)
def create_terms_bulk(body: List[TermIn]):
    """Bulk-insert a list of business terms. Returns list of created term_ids."""
    from MetadataManager.GlossaryStore import add_term

    created = []
    for item in body:
        try:
            tid = add_term(item.model_dump())
            created.append(tid)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    return {"created": created}


@router.post("/terms/single", status_code=201)
def create_term_single(body: TermIn):
    """Add a single business term. Returns the created term_id."""
    from MetadataManager.GlossaryStore import add_term
    try:
        tid = add_term(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"term_id": tid}


@router.get("/terms")
def list_terms_endpoint(instance_name: Optional[str] = None, domain: Optional[str] = None):
    """
    List all business terms, optionally filtered by instance_name and/or domain.
    """
    from MetadataManager.GlossaryStore import list_terms
    terms = list_terms(instance_name=instance_name, domain=domain)
    return {"terms": terms}


@router.get("/terms/{term_id}")
def get_term_endpoint(term_id: str):
    """Fetch a single business term by ID."""
    from MetadataManager.GlossaryStore import get_term
    term = get_term(term_id)
    if term is None:
        raise HTTPException(status_code=404, detail=f"Term '{term_id}' not found.")
    return term


@router.put("/terms/{term_id}")
def update_term_endpoint(term_id: str, body: TermUpdate):
    """Update fields on an existing business term."""
    from MetadataManager.GlossaryStore import get_term, update_term
    if get_term(term_id) is None:
        raise HTTPException(status_code=404, detail=f"Term '{term_id}' not found.")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    update_term(term_id, updates)
    return {"ok": True, "term_id": term_id}


@router.delete("/terms/{term_id}", status_code=200)
def delete_term_endpoint(term_id: str):
    """Delete a business term by ID."""
    from MetadataManager.GlossaryStore import get_term, delete_term
    if get_term(term_id) is None:
        raise HTTPException(status_code=404, detail=f"Term '{term_id}' not found.")
    delete_term(term_id)
    return {"ok": True}


@router.get("/search")
def search_terms_endpoint(q: str, instance_name: Optional[str] = None):
    """Lexical search on term_name and full_name. Returns matching terms."""
    from MetadataManager.GlossaryStore import search_by_name
    if not q or not q.strip():
        raise HTTPException(status_code=422, detail="Query parameter 'q' must not be empty.")
    results = search_by_name(q.strip(), instance_name=instance_name)
    return {"results": results}
