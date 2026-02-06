"""
Unified Search Endpoints for ATOM Application
Provides hybrid semantic + keyword search across user documents, meetings, and notes using LanceDB.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lancedb-search", tags=["search"])

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
