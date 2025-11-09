import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zendesk", tags=["zendesk"])

class ZendeskSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class ZendeskSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def zendesk_status(user_id: str = "test_user"):
    """Get Zendesk integration status"""
    return {
        "ok": True,
        "service": "zendesk",
        "user_id": user_id,
        "status": "connected",
        "message": "Zendesk integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def zendesk_search(request: ZendeskSearchRequest):
    """Search Zendesk content"""
    logger.info(f"Searching Zendesk for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Zendesk Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Zendesk for query: {request.query}",
        }
    ]

    return ZendeskSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_zendesk_items(user_id: str = "test_user"):
    """List Zendesk items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Zendesk Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
