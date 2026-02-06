"""
Unified Search Endpoints for ATOM Application
Provides hybrid semantic + keyword search across user documents, meetings, and notes using LanceDB.
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lancedb-search", tags=["search"])


# Pydantic Models
class SearchFilters(BaseModel):
    doc_type: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    date_range: Optional[Dict[str, str]] = None
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchRequest(BaseModel):
    query: str
    user_id: str
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
async def hybrid_search(request: SearchRequest):
    """
    Perform hybrid search combining semantic and keyword matching using LanceDB.
    """
    try:
        handler = get_lancedb_handler(request.workspace_id)
        
        # Check if LanceDB is available
        if not handler.db:
             logger.error("LanceDB not available for search")
             raise HTTPException(
                 status_code=503, 
                 detail="Search service is currently unavailable. Please ensure the database is initialized."
             )

        # Construct filter expression if needed
        filter_expr = None
        if request.filters:
            conditions = []
            if request.filters.doc_type:
                types = ", ".join([f"'{t}'" for t in request.filters.doc_type])
                conditions.append(f"doc_type IN ({types})")
            
            if conditions:
                filter_expr = " AND ".join(conditions)

        # Perform vector search
        results = handler.search("documents", request.query, limit=request.limit, filter_expression=filter_expr)
        
        search_results = []
        for res in results:
            # Reconstruct document structure
            metadata = res.get("metadata", {})
            
            # Calculate scores (LanceDB returns distance, we converted to similarity in handler)
            similarity_score = res.get("score", 0.0)
            
            # Simple keyword score for hybrid simulation (if not using FTS)
            keyword_score = 0.0
            content_lower = res.get("text", "").lower()
            query_lower = request.query.lower()
            if query_lower in content_lower:
                keyword_score = 0.5 + (0.1 * content_lower.count(query_lower))
                keyword_score = min(keyword_score, 1.0)
            
            # Combine scores
            if request.search_type == "hybrid":
                combined_score = (similarity_score * 0.7) + (keyword_score * 0.3)
            elif request.search_type == "semantic":
                combined_score = similarity_score
            else: # keyword
                combined_score = keyword_score
            
            # Filter by min_score
            min_score = request.filters.min_score if request.filters else 0.0
            if combined_score < min_score:
                continue

            search_results.append(SearchResult(
                id=res["id"],
                title=metadata.get("title", "Untitled"),
                content=res.get("text", ""),
                doc_type=metadata.get("doc_type", "unknown"),
                source_uri=res.get("source", ""),
                similarity_score=similarity_score,
                keyword_score=keyword_score,
                combined_score=combined_score,
                metadata=metadata
            ))
        
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
    user_id: str = Query(...),
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(default=5, ge=1, le=10)
):
    """
    Get search suggestions based on partial query.
    """
    try:
        # Check environment to disable suggestions if needed or use real data source
        # For now, we return empty or limited suggestions from the actual DB if available
        
        handler = get_lancedb_handler(workspace_id)
        if not handler.db:
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
