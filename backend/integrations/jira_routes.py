import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jira", tags=["jira"])

class JiraSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class JiraSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def jira_status(user_id: str = "test_user"):
    """Get Jira integration status"""
    return {
        "ok": True,
        "service": "jira",
        "user_id": user_id,
        "status": "connected",
        "message": "Jira integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def jira_search(request: JiraSearchRequest):
    """Search Jira content"""
    logger.info(f"Searching Jira for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Jira Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Jira for query: {request.query}",
        }
    ]

    return JiraSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_jira_items(user_id: str = "test_user"):
    """List Jira items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Jira Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
