"""
Mock Search Endpoints - LanceDB Alternative
Provides search functionality without Python 3.13 compatibility issues
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from .mock_hybrid_search import get_mock_search

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

@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(request: SearchRequest):
    """
    Perform hybrid search using mock implementation (no LanceDB required)
    """
    try:
        mock_search = get_mock_search()
        
        # Perform search
        results = mock_search.search(request.query, limit=request.limit)
        
        search_results = []
        for res in results:
            metadata = res.get("metadata", {})
            score = res.get("score", 0.0)
            
            search_results.append(SearchResult(
                id=res["id"],
                title=metadata.get("title", "Untitled"),
                content=res.get("text", ""),
                doc_type=metadata.get("type", "unknown"),
                source_uri=res.get("source", ""),
                similarity_score=score,
                keyword_score=score,  # Same for mock
                combined_score=score,
                metadata=metadata
            ))
        
        return SearchResponse(
            success=True,
            results=search_results,
            total_count=len(search_results),
            query=request.query,
            search_type=request.search_type
        )
    
    except Exception as e:
        logger.error(f"Mock search failed: {e}")
        return SearchResponse(
            success=False,
            results=[],
            total_count=0,
            query=request.query,
            search_type=request.search_type
        )

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    query: str = Query(..., min_length=1),
    user_id: str = Query(...),
    limit: int = Query(default=5, ge=1, le=10)
):
    """
    Get search suggestions based on partial query
    """
    try:
        query_lower = query.lower()
        
        # Common suggestions
        all_suggestions = [
            "API documentation",
            "meeting notes",
            "project requirements",
            "frontend architecture",
            "database migration",
            "client feedback",
            "marketing strategy",
            "task management",
        ]
        
        # Filter suggestions
        suggestions = [s for s in all_suggestions if query_lower in s.lower()][:limit]
        
        return SuggestionsResponse(
            success=True,
            suggestions=suggestions
        )
    
    except Exception as e:
        logger.error(f"Suggestions failed: {e}")
        return SuggestionsResponse(
            success=False,
            suggestions=[]
        )
