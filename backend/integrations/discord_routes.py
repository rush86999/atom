import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discord", tags=["discord"])

class DiscordSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class DiscordSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def discord_status(user_id: str = "test_user"):
    """Get Discord integration status"""
    return {
        "ok": True,
        "service": "discord",
        "user_id": user_id,
        "status": "connected",
        "message": "Discord integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def discord_search(request: DiscordSearchRequest):
    """Search Discord content"""
    logger.info(f"Searching Discord for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Discord Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Discord for query: {request.query}",
        }
    ]

    return DiscordSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_discord_items(user_id: str = "test_user"):
    """List Discord items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Discord Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
