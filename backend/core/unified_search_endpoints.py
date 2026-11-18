"""
Unified Search Endpoints for ATOM Application
Provides hybrid semantic + keyword search across user documents, meetings, and notes using LanceDB.
"""

import asyncio
from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import User
from .lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lancedb-search", tags=["search"])


def _resolve_authenticated_document_workspace(current_user: User) -> str:
    """Return the authoritative document workspace for the signed-in actor.

    Mirrors upload's ``personal_scope.resolve_document_workspace_id`` lookup
    (FK first, relationship second) and fails closed without a binding.
    Request bodies are never scope authority.
    """
    from core.personal_scope import (
        DocumentScopeResolutionError,
        DocumentScopeUnavailable,
        resolve_document_workspace_id,
    )

    try:
        workspace_id = resolve_document_workspace_id(current_user)
    except DocumentScopeUnavailable as scope_err:
        logger.warning(
            "Search workspace refused: no eligible scope; error_class=%s",
            type(scope_err).__name__)
        raise HTTPException(
            status_code=403,
            detail=(
                "This account has no document workspace binding, so search "
                "was refused."),
        ) from scope_err
    except DocumentScopeResolutionError as scope_err:
        logger.warning(
            "Search workspace refused: resolution failed; error_class=%s",
            type(scope_err).__name__)
        raise HTTPException(
            status_code=503,
            detail=(
                "The document workspace binding could not be resolved, so "
                "search was refused."),
        ) from scope_err

    if not workspace_id:
        # An authenticated principal with no authoritative workspace must not
        # fall through to the legacy shared store.
        raise HTTPException(
            status_code=403,
            detail=(
                "This account has no document workspace binding, so search "
                "was refused."),
        )
    return str(workspace_id)


# Pydantic Models
class SearchFilters(BaseModel):
    doc_type: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    date_range: Optional[Dict[str, str]] = None
    min_score: float = Field(default=-10.0, ge=-10.0, le=1.0)


class SearchRequest(BaseModel):
    query: str
    # Accepted for wire compatibility with existing callers. Neither field is
    # used for authorization or store routing: scope always comes from the
    # authenticated actor resolved in ``hybrid_search``.
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    filters: Optional[SearchFilters] = None
    limit: int = Field(default=20, ge=1, le=100)
    search_type: str = Field(default="hybrid", pattern="^(hybrid|semantic|keyword)$")


class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    doc_type: str
    source_uri: str
    similarity_score: float
    keyword_score: Optional[float] = None
    combined_score: Optional[float] = None
    metadata: Dict[str, Any]


class SearchResponse(BaseModel):
    success: bool
    results: List[SearchResult]
    total_count: int
    query: str
    search_type: str


class SuggestionsResponse(BaseModel):
    success: bool
    suggestions: List[str]


class HealthResponse(BaseModel):
    status: str
    lancedb_available: bool
    db_path: Optional[str] = None

@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Perform hybrid search combining semantic and keyword matching using LanceDB.
    Requires authentication.
    """
    try:
        # Route by the authenticated actor's upload workspace, never the body.
        workspace_id = _resolve_authenticated_document_workspace(current_user)
        actor_user_id = str(current_user.id)
        handler = get_lancedb_handler(workspace_id)

        handler._ensure_db()
        handler._ensure_embedder()

        if handler.db is None:
             logger.warning("LanceDB not available for search - returning empty results")
             # Keep the success shape so the UI does not break.
             return SearchResponse(
                 success=True,
                 results=[],
                 total_count=0,
                 query=request.query,
                 search_type=request.search_type
             )

        # metadata.doc_type is stored as JSON text, so filter it in Python.
        filter_expr = None

        # Over-fetch only when doc_type post-filtering may discard rows.
        search_limit = request.limit * 2 if request.filters and request.filters.doc_type else request.limit

        # handler.search() embeds synchronously; on the event loop the embed
        # guard returns None and every search is empty. Keep it off-loop.
        results = await asyncio.to_thread(
            handler.search,
            "documents",
            request.query,
            limit=search_limit,
            filter_str=filter_expr,
            user_id=actor_user_id,
        )

        search_results = []
        for res in results:
            metadata = res.get("metadata", {})

            doc_type = metadata.get("doc_type", "unknown")
            if request.filters and request.filters.doc_type:
                if doc_type not in request.filters.doc_type:
                    continue

            similarity_score = res.get("score", 0.0)

            # Lightweight keyword component for hybrid/semantic simulation.
            keyword_score = 0.0
            content_lower = res.get("text", "").lower()
            query_lower = request.query.lower()
            if query_lower in content_lower:
                keyword_score = 0.5 + (0.1 * content_lower.count(query_lower))
                keyword_score = min(keyword_score, 1.0)

            if request.search_type == "hybrid":
                combined_score = (similarity_score * 0.7) + (keyword_score * 0.3)
            elif request.search_type == "semantic":
                combined_score = similarity_score
            else: # keyword
                combined_score = keyword_score

            min_score = request.filters.min_score if request.filters else -10.0
            if combined_score < min_score:
                continue

            search_results.append(SearchResult(
                id=res["id"],
                title=metadata.get("title", "Untitled"),
                content=res.get("text", ""),
                doc_type=doc_type,
                source_uri=res.get("source", ""),
                similarity_score=similarity_score,
                keyword_score=keyword_score,
                combined_score=combined_score,
                metadata=metadata
            ))
            
            if len(search_results) >= request.limit:
                break

        
        # Sort by combined score
        search_results.sort(key=lambda x: x.combined_score or 0, reverse=True)
        
        return SearchResponse(
            success=True,
            results=search_results,
            total_count=len(search_results),
            query=request.query,
            search_type=request.search_type
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred during search.")

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    query: str = Query(..., min_length=1),
    user_id: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get search suggestions based on partial query.
    Requires authentication.
    """
    try:
        # Check environment to disable suggestions if needed or use real data source
        # For now, we return empty or limited suggestions from the actual DB if available
        
        handler = get_lancedb_handler(workspace_id)
        if handler.db is None:
            return SuggestionsResponse(success=True, suggestions=[])
            
        # In a real production setup, we'd query the 'documents' table for matching titles
        # or use a dedicated suggestions index. 
        # For this fix, we'll return an empty list until the suggestion engine is fully implemented.
        
        return SuggestionsResponse(
            success=True,
            suggestions=[]
        )
    
    except Exception as e:
        logger.error(f"Failed to get suggestions: {e}")
        return SuggestionsResponse(success=True, suggestions=[])


@router.get("/health", response_model=HealthResponse)
async def search_health():
    """
    Check search service health.

    Returns:
        - status: "healthy" if LanceDB is available, "unavailable" otherwise
        - lancedb_available: Whether LanceDB is initialized
        - db_path: Path to LanceDB database
    """
    try:
        # Check if LanceDB is disabled via env var
        if os.getenv("ATOM_DISABLE_LANCEDB", "false").lower() == "true":
            return HealthResponse(
                status="disabled",
                lancedb_available=False,
                db_path=None
            )

        handler = get_lancedb_handler()
        return HealthResponse(
            status="healthy" if handler.db else "unavailable",
            lancedb_available=handler.db is not None,
            db_path=handler.db_path if handler else None
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            lancedb_available=False,
            db_path=None
        )
