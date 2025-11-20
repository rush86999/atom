"""
Unified Search Endpoints for ATOM Application
Provides hybrid semantic + keyword search across user documents, meetings, and notes using LanceDB.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lancedb-search", tags=["search"])

# Mock search data for seeding
MOCK_DOCUMENTS = [
    {
        "id": "doc_1",
        "title": "Q4 Project Requirements Document",
        "content": "This document outlines the key requirements for our Q4 projects including user authentication, dashboard redesign, and API integration improvements.",
        "doc_type": "document",
        "source_uri": "/documents/q4_requirements.pdf",
        "metadata": {
            "created_at": "2025-09-15T10:30:00Z",
            "author": "Jane Smith",
            "tags": ["project", "requirements", "Q4"],
            "file_size": 245760
        }
    },
    {
        "id": "doc_2",
        "title": "Weekly Team Meeting Notes - Oct 15",
        "content": "Discussed sprint progress, API performance issues, and upcoming feature releases. Action items assigned to development team.",
        "doc_type": "meeting",
        "source_uri": "/meetings/team_meeting_oct15.md",
        "metadata": {
            "created_at": "2025-10-15T14:00:00Z",
            "author": "John Doe",
            "tags": ["meeting", "team", "sprint"],
            "participants": ["Jane Smith", "John Doe", "Alice Johnson"]
        }
    },
    {
        "id": "doc_3",
        "title": "API Documentation v2.0",
        "content": "Complete API reference documentation including authentication endpoints, data models, and integration examples.",
        "doc_type": "document",
        "source_uri": "/docs/api_v2.md",
        "metadata": {
            "created_at": "2025-10-01T09:00:00Z",
            "author": "Tech Team",
            "tags": ["api", "documentation", "reference"]
        }
    },
    {
        "id": "doc_4",
        "title": "Customer Feedback Summary",
        "content": "Analysis of customer feedback from Q3 showing high satisfaction with new features but requests for better mobile support.",
        "doc_type": "note",
        "source_uri": "/notes/customer_feedback_q3.txt",
        "metadata": {
            "created_at": "2025-09-30T16:45:00Z",
            "author": "Product Team",
            "tags": ["feedback", "customer", "Q3"]
        }
    },
    {
        "id": "doc_5",
        "title": "Financial Report Q3 2025",
        "content": "Quarterly financial report showing revenue growth, expense breakdown, and projections for Q4.",
        "doc_type": "pdf",
        "source_uri": "/reports/financial_q3_2025.pdf",
        "metadata": {
            "created_at": "2025-10-05T11:20:00Z",
            "author": "Finance Team",
            "tags": ["financial", "report", "Q3", "revenue"],
            "file_size": 512000
        }
    },
    {
        "id": "doc_6",
        "title": "Email: Product Launch Update",
        "content": "Update on the upcoming product launch schedule, marketing materials, and coordination with sales team.",
        "doc_type": "email",
        "source_uri": "/emails/product_launch_update.eml",
        "metadata": {
            "created_at": "2025-10-18T08:30:00Z",
            "author": "Marketing Team",
            "tags": ["email", "product", "launch", "marketing"]
        }
    }
]

# Seed data on module load (for demo/validation purposes)
try:
    handler = get_lancedb_handler()
    # Check if table exists and has data
    stats = handler.get_table_stats("documents")
    if not stats or stats.get("document_count", 0) == 0:
        logger.info("Seeding LanceDB with mock documents...")
        # Flatten metadata for LanceDB
        seeded_docs = []
        for doc in MOCK_DOCUMENTS:
            doc_copy = doc.copy()
            # Ensure text field exists for embedding
            doc_copy["text"] = doc["title"] + "\n" + doc["content"]
            doc_copy["source"] = doc["source_uri"]
            seeded_docs.append(doc_copy)
        
        handler.seed_mock_data(seeded_docs)
        logger.info("LanceDB seeding complete.")
except Exception as e:
    logger.error(f"Failed to seed LanceDB: {e}")

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
    Perform hybrid search combining semantic and keyword matching using LanceDB.
    """
    try:
        handler = get_lancedb_handler()
        
        # Construct filter expression if needed
        filter_expr = None
        if request.filters:
            conditions = []
            if request.filters.doc_type:
                types = ", ".join([f"'{t}'" for t in request.filters.doc_type])
                conditions.append(f"doc_type IN ({types})")
            # Note: Tag filtering would require more complex SQL or post-processing in LanceDB
            
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
            # In a real production setup, we'd use LanceDB's FTS or a separate index
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
                content=res.get("text", ""), # Or truncate/extract snippet
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
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    query: str = Query(..., min_length=1),
    user_id: str = Query(...),
    limit: int = Query(default=5, ge=1, le=10)
):
    """
    Get search suggestions based on partial query.
    """
    try:
        # For suggestions, we can still use the static list + some DB queries if needed
        # Keeping it simple for now to ensure speed
        
        query_lower = query.lower()
        
        # Generate suggestions from document titles and common searches
        all_suggestions = [
            "project requirements",
            "meeting notes",
            "API documentation",
            "financial reports",
            "customer feedback",
            "team meeting",
            "product launch",
            "Q4 planning",
            "sprint review",
            "user authentication"
        ]
        
        # Add titles from LanceDB if possible (would require a different query type)
        # For now, we'll stick to the static list + mock titles we know exist
        for doc in MOCK_DOCUMENTS:
            if query_lower in doc["title"].lower():
                all_suggestions.append(doc["title"])
        
        # Filter and deduplicate
        suggestions = []
        seen = set()
        for suggestion in all_suggestions:
            if query_lower in suggestion.lower() and suggestion.lower() not in seen:
                suggestions.append(suggestion)
                seen.add(suggestion.lower())
                if len(suggestions) >= limit:
                    break
        
        return SuggestionsResponse(
            success=True,
            suggestions=suggestions
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")
