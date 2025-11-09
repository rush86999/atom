import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quickbooks", tags=["quickbooks"])

class QuickbooksSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class QuickbooksSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def quickbooks_status(user_id: str = "test_user"):
    """Get Quickbooks integration status"""
    return {
        "ok": True,
        "service": "quickbooks",
        "user_id": user_id,
        "status": "connected",
        "message": "Quickbooks integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def quickbooks_search(request: QuickbooksSearchRequest):
    """Search Quickbooks content"""
    logger.info(f"Searching Quickbooks for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Quickbooks Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Quickbooks for query: {request.query}",
        }
    ]

    return QuickbooksSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_quickbooks_items(user_id: str = "test_user"):
    """List Quickbooks items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Quickbooks Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
