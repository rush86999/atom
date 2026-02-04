from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from .calendly_service import get_calendly_service
    CALENDLY_AVAILABLE = True
except ImportError:
    CALENDLY_AVAILABLE = False

# Auth Type: OAuth2
router = APIRouter(prefix="/api/calendly", tags=["calendly"])

class CalendlyAuthRequest(BaseModel):
    code: str
    redirect_uri: str

@router.get("/auth/url")
async def get_auth_url(redirect_uri: str = "http://localhost:3000/integrations/calendly/callback"):
    """Get Calendly OAuth URL"""
    if not CALENDLY_AVAILABLE:
        return {
            "url": f"https://auth.calendly.com/oauth/authorize?client_id=INSERT_CLIENT_ID&response_type=code&redirect_uri={redirect_uri}",
            "timestamp": datetime.now().isoformat()
        }
    
    service = get_calendly_service()
    url = service.get_authorization_url(redirect_uri)
    
    return {
        "url": url,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/callback")
async def handle_oauth_callback(auth_request: CalendlyAuthRequest):
    """Handle Calendly OAuth callback"""
    if not CALENDLY_AVAILABLE:
        return {
            "ok": True,
            "status": "success",
            "code": auth_request.code,
            "message": "Calendly authentication successful (mock)",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        service = get_calendly_service()
        token_data = await service.exchange_token(auth_request.code, auth_request.redirect_uri)
        
        return {
            "ok": True,
            "status": "success",
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "message": "Calendly authentication successful",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user/me")
async def get_current_user(access_token: str):
    """Get current Calendly user"""
    if not CALENDLY_AVAILABLE:
        return {"id": "mock_user_id", "name": "Mock User"}
    
    try:
        service = get_calendly_service()
        user = await service.get_current_user(access_token)
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/event-types")
async def get_event_types(user_uri: str, access_token: str, count: int = 20):
    """Get event types for a user"""
    if not CALENDLY_AVAILABLE:
        return []
    
    try:
        service = get_calendly_service()
        events = await service.get_event_types(user_uri, access_token, count)
        return events
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/scheduled-events")
async def get_scheduled_events(
    user_uri: Optional[str] = None,
    access_token: str = None,
    count: int = 20,
    status: str = "active"
):
    """Get scheduled events"""
    if not CALENDLY_AVAILABLE:
        return []
    
    try:
        service = get_calendly_service()
        events = await service.get_scheduled_events(user_uri, access_token, count, status)
        return events
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def calendly_status():
    """Status check for Calendly integration"""
    return {
        "status": "active",
        "service": "calendly",
        "version": "1.0.0",
        "available": CALENDLY_AVAILABLE,
        "business_value": {
            "scheduling_automation": True,
            "availability_management": True,
            "meeting_booking": True
        }
    }

@router.get("/health")
async def calendly_health():
    """Health check for Calendly integration"""
    if CALENDLY_AVAILABLE:
        service = get_calendly_service()
        return await service.health_check()
    return await calendly_status()
