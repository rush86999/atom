import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from datetime import datetime
from fastapi import Request

from core.mock_mode import get_mock_mode_manager
from core.token_storage import token_storage
from integrations.auth_handler_zoom import zoom_auth_handler
from integrations.zoom_service import zoom_service

# Auth Type: OAuth2
router = APIRouter(prefix="/api/zoom/v1", tags=["zoom-v1"])

@router.get("/auth/url")
async def get_auth_url(state: Optional[str] = None):
    """Get Zoom OAuth URL"""
    try:
        url = zoom_auth_handler.get_authorization_url(state)
        return {
            "url": url,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to generate Zoom OAuth URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate OAuth URL")

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Zoom OAuth callback"""
    try:
        token_data = await zoom_auth_handler.exchange_code_for_token(code)
        return {
            "ok": True,
            "status": "success",
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Zoom OAuth callback failed: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth callback failed: {str(e)}")

class ZoomMeetingRequest(BaseModel):
    topic: str
    user_id: str = "me"
    start_time: Optional[str] = None
    duration: int = 60
    timezone: str = "UTC"
    agenda: Optional[str] = None

@router.get("/status")
async def zoom_status(user_id: str = "test_user"):
    """Get Zoom integration status"""
    try:
        status = zoom_auth_handler.get_connection_status()
        return {
            "ok": True,
            "service": "zoom",
            "user_id": user_id,
            "status": "connected" if status.get("connected") else "disconnected",
            "message": "Zoom integration is available" if status.get("connected") else "Zoom integration not connected",
            "timestamp": datetime.utcnow().isoformat(),
            "details": status
        }
    except Exception as e:
        logger.error(f"Failed to get Zoom status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get Zoom status")


@router.get("/health")
async def zoom_health(user_id: str = "test_user"):
    """Health check endpoint"""
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("zoom", False):
        return {
            "ok": True,
            "status": "healthy",
            "service": "zoom",
            "timestamp": datetime.utcnow().isoformat(),
            "is_mock": True
        }
    try:
        # Check service health
        health = await zoom_service.health_check()
        # Check OAuth connection status
        oauth_status = zoom_auth_handler.get_connection_status()
        return {
            "ok": health.get("ok", True),
            "status": health.get("status", "healthy"),
            "service": "zoom",
            "timestamp": datetime.utcnow().isoformat(),
            "is_mock": False,
            "oauth_connected": oauth_status.get("connected", False),
            "has_access_token": oauth_status.get("has_access_token", False)
        }
    except Exception as e:
        logger.error(f"Zoom health check failed: {e}")
        return {
            "ok": False,
            "status": "unhealthy",
            "service": "zoom",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/meetings")
async def create_zoom_meeting(meeting: ZoomMeetingRequest):
    """Create a Zoom meeting"""
    try:
        # Ensure we have a valid access token
        access_token = await zoom_auth_handler.ensure_valid_token()
        # Create meeting using zoom service
        meeting_data = await zoom_service.create_meeting(
            topic=meeting.topic,
            user_id=meeting.user_id,
            access_token=access_token,
            start_time=meeting.start_time,
            duration=meeting.duration,
            timezone=meeting.timezone,
            agenda=meeting.agenda
        )
        return {
            "ok": True,
            "meeting_id": meeting_data.get("id"),
            "topic": meeting_data.get("topic"),
            "join_url": meeting_data.get("join_url"),
            "start_time": meeting_data.get("start_time"),
            "duration": meeting_data.get("duration"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Zoom meeting: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create meeting: {str(e)}")


@router.get("/meetings")
async def list_zoom_meetings(user_id: str = "me", type: str = "scheduled", page_size: int = 30):
    """List Zoom meetings"""
    try:
        access_token = await zoom_auth_handler.ensure_valid_token()
        if not access_token:
            raise HTTPException(
                status_code=401, detail="Zoom credentials required. Please configure your Zoom integration."
            )
        meetings_data = await zoom_service.list_meetings(
            user_id=user_id,
            type=type,
            access_token=access_token,
            page_size=page_size
        )
        return {
            "ok": True,
            "meetings": meetings_data.get("meetings", []),
            "total": meetings_data.get("total_records", 0),
            "page_size": meetings_data.get("page_size", page_size),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
@router.get("/users")
async def list_zoom_users(status: str = "active", page_size: int = 30):
    """List Zoom users"""
    try:
        access_token = await zoom_auth_handler.ensure_valid_token()
        if not access_token:
            raise HTTPException(
                status_code=401, detail="Zoom credentials required. Please configure your Zoom integration."
            )
        users_data = await zoom_service.list_users(
            status=status,
            page_size=page_size,
            access_token=access_token
        )
        return {
            "ok": True,
            "users": users_data.get("users", []),
            "total_records": users_data.get("total_records", 0),
            "page_size": users_data.get("page_size", page_size),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list Zoom users: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@router.get("/recordings")
async def list_zoom_recordings(user_id: str = "me", from_date: str = None, to_date: str = None, page_size: int = 30):
    """List Zoom recordings"""
    try:
        access_token = await zoom_auth_handler.ensure_valid_token()
        if not access_token:
            raise HTTPException(
                status_code=401, detail="Zoom credentials required. Please configure your Zoom integration."
            )
        recordings_data = await zoom_service.list_recordings(
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            page_size=page_size,
            access_token=access_token
        )
        return {
            "ok": True,
            "recordings": recordings_data.get("meetings", []), # Zoom API returns recordings in "meetings" field for user recordings
            "total_records": recordings_data.get("total_records", 0),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list Zoom recordings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list recordings: {str(e)}")
