import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from backend.core.mock_mode import get_mock_mode_manager
from datetime import datetime

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
    mock_manager = get_mock_mode_manager()
    # Zoom routes seem to be already mocked or simple, but let's standardize
    if mock_manager.is_mock_mode("zoom", False): # Assuming no credentials check implemented here yet
         return {
            "ok": True,
            "status": "healthy",
            "service": "zoom",
            "timestamp": datetime.now().isoformat(),
            "is_mock": True
        }
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
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("zoom", False):
        return {
            "ok": True,
            "meetings": mock_manager.get_mock_data("zoom", "meetings"),
            "total": 5,
            "timestamp": datetime.now().isoformat(),
        }

    return {
        "ok": True,
        "meetings": [],
        "total": 0,
        "timestamp": datetime.now().isoformat(),
    }
