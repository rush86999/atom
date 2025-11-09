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

@router.post("/meetings/create")
async def create_zoom_meeting(request: ZoomMeetingRequest):
    """Create a Zoom meeting"""
    return {
        "ok": True,
        "meeting_id": f"zoom_meeting_{request.topic.lower().replace(' ', '_')}",
        "topic": request.topic,
        "join_url": f"https://zoom.us/j/mock_meeting_{request.topic.lower().replace(' ', '_')}",
        "timestamp": "2025-11-09T17:25:00Z",
    }
