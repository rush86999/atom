import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

class GmailSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"
    max_results: int = 10

class GmailSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    total_results: int
    timestamp: str

@router.get("/status")
async def gmail_status(user_id: str = "test_user"):
    """Get Gmail integration status"""
    return {
        "ok": True,
        "service": "gmail",
        "user_id": user_id,
        "status": "connected",
        "message": "Gmail integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def gmail_search(request: GmailSearchRequest):
    """Search Gmail messages"""
    logger.info(f"Searching Gmail for: {request.query}")

    mock_results = [
        {
            "id": f"msg_{i}",
            "subject": f"Email about {request.query} - Message {i}",
            "sender": f"sender{i}@example.com",
            "snippet": f"This email discusses {request.query}...",
            "date": f"2025-11-{9 - i}T10:00:00Z",
        }
        for i in range(1, request.max_results + 1)
    ]

    return GmailSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        total_results=len(mock_results),
        timestamp="2025-11-09T17:25:00Z",
    )
