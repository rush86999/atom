import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monday", tags=["monday"])

class MondaySearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

@router.get("/status")
async def monday_status(user_id: str = "test_user"):
    """Get Monday integration status"""
    return {
        "ok": True,
        "service": "monday",
        "user_id": user_id,
        "status": "connected",
        "message": "Monday integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def monday_search(request: MondaySearchRequest):
    """Search Monday boards and items"""
    return {
        "ok": True,
        "query": request.query,
        "results": [
            {
                "id": "board_001",
                "title": f"Project Board - {request.query}",
                "type": "board",
                "items_count": 15,
            }
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
