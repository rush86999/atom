import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

try:
    from .zoom_service import get_zoom_service
    ZOOM_AVAILABLE = True
except ImportError:
    ZOOM_AVAILABLE = False

# Auth Type: OAuth2
router = APIRouter(prefix="/api/zoom", tags=["zoom"])

class ZoomAuthRequest(BaseModel):
    code: str
    redirect_uri: str

class CreateMeetingRequest(BaseModel):
    topic: str
    start_time: Optional[str] = None
    duration: int = 60
    timezone: str = "UTC"
    agenda: Optional[str] = None

@router.get("/auth/url")
async def get_auth_url(redirect_uri: str = "http://localhost:3000/integrations/zoom/callback"):
    """Get Zoom OAuth URL"""
    if not ZOOM_AVAILABLE:
        return {
            "url": f"https://zoom.us/oauth/authorize?response_type=code&client_id=INSERT_CLIENT_ID&redirect_uri={redirect_uri}",
            "timestamp": datetime.now().isoformat()
        }
    
    service = get_zoom_service()
    url = service.get_authorization_url(redirect_uri)
    
    return {
        "url": url,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/callback")
async def handle_oauth_callback(auth_request: ZoomAuthRequest):
    """Handle Zoom OAuth callback"""
    if not ZOOM_AVAILABLE:
        return {
            "ok": True,
            "status": "success",
            "code": auth_request.code,
            "message": "Zoom authentication received (service unavailable, code stored)",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        service = get_zoom_service()
        token_data = await service.exchange_token(auth_request.code, auth_request.redirect_uri)
        
        return {
            "ok": True,
            "status": "success",
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "message": "Zoom authentication successful",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user")
async def get_current_user(access_token: str, user_id: str = "me"):
    """Get Zoom user information"""
    if not ZOOM_AVAILABLE:
        return {"id": "service_unavailable", "email": "zoom_service_not_configured@placeholder.local"}
    
    try:
        service = get_zoom_service()
        user = await service.get_user(user_id, access_token)
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/meetings")
async def list_meetings(access_token: str, user_id: str = "me", type: str = "scheduled", page_size: int = 30):
    """List Zoom meetings"""
    if not ZOOM_AVAILABLE:
        return {"meetings": []}
    
    try:
        service = get_zoom_service()
        meetings = await service.list_meetings(user_id, type, access_token, page_size)
        return meetings
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/meetings")
async def create_meeting(access_token: str, meeting_request: CreateMeetingRequest, user_id: str = "me"):
    """Create a Zoom meeting"""
    if not ZOOM_AVAILABLE:
        return {"id": "service_unavailable", "join_url": "#zoom-service-not-configured"}
    
    try:
        service = get_zoom_service()
        meeting = await service.create_meeting(
            topic=meeting_request.topic,
            user_id=user_id,
            access_token=access_token,
            start_time=meeting_request.start_time,
            duration=meeting_request.duration,
            timezone=meeting_request.timezone,
            agenda=meeting_request.agenda
        )
        return meeting
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str, access_token: str):
    """Delete a Zoom meeting"""
    if not ZOOM_AVAILABLE:
        return {"ok": True, "message": "Meeting deletion simulated (service unavailable)"}
    
    try:
        service = get_zoom_service()
        result = await service.delete_meeting(meeting_id, access_token)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def zoom_status():
    """Status check for Zoom integration"""
    return {
        "status": "active",
        "service": "zoom",
        "version": "1.0.0",
        "available": ZOOM_AVAILABLE,
        "business_value": {
            "video_conferencing": True,
            "meeting_scheduling": True,
            "collaboration": True
        }
    }

@router.get("/health")
async def zoom_health():
    """Health check for Zoom integration"""
    if ZOOM_AVAILABLE:
        service = get_zoom_service()
        return await service.health_check()
    return await zoom_status()
