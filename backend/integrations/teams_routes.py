import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])

class TeamsSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class TeamsSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def teams_status(user_id: str = "test_user"):
    """Get Teams integration status"""
    return {
        "ok": True,
        "service": "teams",
        "user_id": user_id,
        "status": "connected",
        "message": "Teams integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def teams_search(request: TeamsSearchRequest):
    """Search Teams content"""
    logger.info(f"Searching Teams for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Teams Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Teams for query: {request.query}",
        }
    ]

    return TeamsSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_teams_items(user_id: str = "test_user"):
    """List Teams items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Teams Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
