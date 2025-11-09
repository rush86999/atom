import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/figma", tags=["figma"])

class FigmaSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class FigmaSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def figma_status(user_id: str = "test_user"):
    """Get Figma integration status"""
    return {
        "ok": True,
        "service": "figma",
        "user_id": user_id,
        "status": "connected",
        "message": "Figma integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def figma_search(request: FigmaSearchRequest):
    """Search Figma content"""
    logger.info(f"Searching Figma for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Figma Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Figma for query: {request.query}",
        }
    ]

    return FigmaSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_figma_items(user_id: str = "test_user"):
    """List Figma items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Figma Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
