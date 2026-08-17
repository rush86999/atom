"""Ontology API routes — schema inspection, validation, JSON-LD export (A9).

GET  /api/ontology                 — full schema (entity types + relations)
GET  /api/ontology/export.jsonld   — RDF interchange serialization (JSON-LD 1.1)
POST /api/ontology/validate        — test a (source, relation, target) triple
POST /api/ontology/seed            — idempotent system-ontology seeding
GET  /api/ontology/undeclared      — relation types in use but not declared
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()


def _ontology(tenant_id: str):
    from core.ontology import get_ontology_service
    return get_ontology_service(tenant_id)


@router.get("")
def get_ontology_schema(tenant_id: str = Query(default="default")) -> Dict[str, Any]:
    try:
        return _ontology(tenant_id).get_schema()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/export.jsonld")
def export_jsonld(
    tenant_id: str = Query(default="default"),
    include_graph: bool = Query(default=False),
    workspace_id: str = Query(default="default"),
) -> Dict[str, Any]:
    try:
        return _ontology(tenant_id).to_jsonld(
            include_graph=include_graph, workspace_id=workspace_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/validate")
def validate_triple(body: Dict[str, Any], tenant_id: str = Query(default="default")) -> Dict[str, Any]:
    source_type = body.get("source_type")
    relation = body.get("relation")
    target_type = body.get("target_type")
    if not (source_type and relation and target_type):
        raise HTTPException(status_code=422, detail="source_type, relation, target_type required")
    result = _ontology(tenant_id).validate_relationship(source_type, relation, target_type)
    return {"ok": result.ok, "declared": result.declared, "reason": result.reason}


@router.post("/seed")
def seed_ontology(tenant_id: str = Query(default="default")) -> Dict[str, Any]:
    try:
        return _ontology(tenant_id).ensure_seeded()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/undeclared")
def undeclared_relations(
    workspace_id: str = Query(default="default"),
    tenant_id: str = Query(default="default"),
    limit: int = Query(default=25, le=200),
) -> Dict[str, Any]:
    return {"undeclared": _ontology(tenant_id).undeclared_relations_in_use(workspace_id, limit)}
