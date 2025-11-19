import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zoom", tags=["zoom"])

class ZoomMeetingRequest(BaseModel):
    topic: str
    user_id: str = "test_user"

@router.get("/status")
async def zoom_status(user_id: str = "test_user"):
    """Get Zoom integration status"""
    return {
        "ok": True,
        "service": "zoom",
        "user_id": user_id,
        "status": "connected",
        "message": "Zoom integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }


@router.get("/health")
async def zoom_health(user_id: str = "test_user"):
    """Health check endpoint (alias for status)"""
    return await zoom_status(user_id)

@router.post("/meetings")
async def create_zoom_meeting(request: dict):
    """Create a Zoom meeting"""
    topic = request.get("topic", "Meeting")
    return {
        "ok": True,
        "meeting_id": f"zoom_meeting_{topic.lower().replace(' ', '_')}",
        "topic": topic,
        "join_url": f"https://zoom.us/j/mock_meeting_{topic.lower().replace(' ', '_')}",
        "timestamp": "2025-11-09T17:25:00Z",
    }


@router.get("/meetings")
async def list_zoom_meetings(user_id: str = "test_user"):
    """List Zoom meetings"""
    return {
        "ok": True,
        "meetings": [],
        "total": 0,
        "timestamp": "2025-11-09T17:25:00Z",
    }
