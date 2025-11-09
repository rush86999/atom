import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notion", tags=["notion"])

class NotionSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class NotionSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def notion_status(user_id: str = "test_user"):
    """Get Notion integration status"""
    return {
        "ok": True,
        "service": "notion",
        "user_id": user_id,
        "status": "connected",
        "message": "Notion integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def notion_search(request: NotionSearchRequest):
    """Search Notion pages and databases"""
    logger.info(f"Searching Notion for: {request.query}")

    mock_results = [
        {
            "id": "page_001",
            "title": f"Meeting Notes - {request.query}",
            "type": "page",
            "url": "https://notion.so/mock-page",
            "last_edited": "2025-11-09T10:00:00Z",
            "snippet": f"Discussion about {request.query} and project planning",
        }
    ]

    return NotionSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/pages/{page_id}")
async def get_notion_page(page_id: str, user_id: str = "test_user"):
    """Get a specific Notion page"""
    return {
        "ok": True,
        "page_id": page_id,
        "title": f"Sample Notion Page - {page_id}",
        "content": f"This is the content of Notion page {page_id}.",
        "timestamp": "2025-11-09T17:25:00Z",
    }
