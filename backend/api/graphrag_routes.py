"""
GraphRAG API Routes - Phase 42
Endpoints for GraphRAG queries.
"""

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel

from core.base_routes import BaseAPIRouter

router = BaseAPIRouter(prefix="/api/graphrag", tags=["GraphRAG"])

class IngestRequest(BaseModel):
    doc_id: str
    text: str
    source: str = "api"
    user_id: str = "default_user"

class QueryRequest(BaseModel):
    query: str
    user_id: str
    mode: str = "auto"  # auto, global, local

@router.post("/ingest")
async def ingest_document(request: IngestRequest):
    """Ingest a document into GraphRAG"""
    from core.graphrag_engine import graphrag_engine

    result = graphrag_engine.ingest_document(
        user_id=request.user_id,
        doc_id=request.doc_id,
        text=request.text,
        source=request.source
    )
    return router.success_response(
        data=result,
        message="Document ingested successfully"
    )

@router.post("/build-communities")
async def build_communities(user_id: str):
    """Build communities for a user"""
    from core.graphrag_engine import graphrag_engine

    count = graphrag_engine.build_communities(user_id)
    return router.success_response(
        data={"user_id": user_id},
        message=f"Built {count} communities"
    )

@router.post("/query")
async def query_graphrag(request: QueryRequest):
    """Query GraphRAG (global or local search)"""
    from core.graphrag_engine import graphrag_engine

    result = graphrag_engine.query(request.user_id, request.query, request.mode)
    return router.success_response(
        data=result,
        message="Query executed successfully"
    )

@router.get("/context")
async def get_ai_context(user_id: str, query: str):
    """Get context for AI nodes"""
    from core.graphrag_engine import get_graphrag_context

    context = get_graphrag_context(user_id, query)
    return router.success_response(
        data={"user_id": user_id, "context": context},
        message="Context retrieved successfully"
    )

@router.get("/stats")
async def get_stats(user_id: str = None):
    """Get GraphRAG stats"""
    from core.graphrag_engine import graphrag_engine

    result = graphrag_engine.get_stats(user_id)
    return router.success_response(
        data=result,
        message="Stats retrieved successfully"
    )
