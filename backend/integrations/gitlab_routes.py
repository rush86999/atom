import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gitlab", tags=["gitlab"])

class GitlabSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class GitlabSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def gitlab_status(user_id: str = "test_user"):
    """Get Gitlab integration status"""
    return {
        "ok": True,
        "service": "gitlab",
        "user_id": user_id,
        "status": "connected",
        "message": "Gitlab integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def gitlab_search(request: GitlabSearchRequest):
    """Search Gitlab content"""
    logger.info(f"Searching Gitlab for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Gitlab Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Gitlab for query: {request.query}",
        }
    ]

    return GitlabSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_gitlab_items(user_id: str = "test_user"):
    """List Gitlab items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Gitlab Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
