"""
Unified Search Endpoints for ATOM Application
Provides hybrid semantic + keyword search across user documents, meetings, and notes.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/api/lancedb-search", tags=["search"])

# Mock search data
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

def calculate_similarity_score(query: str, document: Dict[str, Any]) -> float:
    """
    Mock semantic similarity calculation.
    In production, this would use vector embeddings and cosine similarity.
    """
    query_lower = query.lower()
    content_lower = (document["title"] + " " + document["content"]).lower()
    
    # Simple keyword matching as a proxy for semantic similarity
    query_words = set(query_lower.split())
    content_words = set(content_lower.split())
    
    if not query_words:
        return 0.0
    
    # Calculate overlap
    overlap = len(query_words.intersection(content_words))
    score = min(overlap / len(query_words), 1.0)
    
    # Boost score if query appears in title
    if query_lower in document["title"].lower():
        score = min(score + 0.3, 1.0)
    
    return score

def calculate_keyword_score(query: str, document: Dict[str, Any]) -> float:
    """Simple keyword-based scoring"""
    query_lower = query.lower()
    content = (document["title"] + " " + document["content"]).lower()
    
    # Count occurrences
    count = content.count(query_lower)
    
    # Normalize by length
    score = min(count * 0.2, 1.0)
    
    return score

def apply_filters(documents: List[Dict[str, Any]], filters: Optional[SearchFilters]) -> List[Dict[str, Any]]:
    """Apply search filters to documents"""
    if not filters:
        return documents
    
    filtered = documents
    
    # Filter by document type
    if filters.doc_type:
        filtered = [d for d in filtered if d["doc_type"] in filters.doc_type]
    
    # Filter by tags
    if filters.tags:
        filtered = [
            d for d in filtered 
            if any(tag in d["metadata"].get("tags", []) for tag in filters.tags)
        ]
    
    return filtered

@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(request: SearchRequest):
    """
    Perform hybrid search combining semantic and keyword matching.
    """
    try:
        # Apply filters
        filtered_docs = apply_filters(MOCK_DOCUMENTS, request.filters)
        
        # Calculate scores
        results = []
        for doc in filtered_docs:
            similarity_score = calculate_similarity_score(request.query, doc)
            keyword_score = calculate_keyword_score(request.query, doc)
            
            # Combine scores based on search type
            if request.search_type == "hybrid":
                combined_score = (similarity_score * 0.7) + (keyword_score * 0.3)
            elif request.search_type == "semantic":
                combined_score = similarity_score
            else:  # keyword
                combined_score = keyword_score
            
            # Apply minimum score filter
            min_score = request.filters.min_score if request.filters else 0.5
            if combined_score >= min_score:
                results.append(SearchResult(
                    id=doc["id"],
                    title=doc["title"],
                    content=doc["content"],
                    doc_type=doc["doc_type"],
                    source_uri=doc["source_uri"],
                    similarity_score=similarity_score,
                    keyword_score=keyword_score,
                    combined_score=combined_score,
                    metadata=doc["metadata"]
                ))
        
        # Sort by combined score
        results.sort(key=lambda x: x.combined_score or 0, reverse=True)
        
        # Apply limit
        results = results[:request.limit]
        
        return SearchResponse(
            success=True,
            results=results,
            total_count=len(results),
            query=request.query,
            search_type=request.search_type
        )
    
    except Exception as e:
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
        
        # Add titles that match the query
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
