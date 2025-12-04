from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

try:
    from .linkedin_service import get_linkedin_service
    LINKEDIN_AVAILABLE = True
except ImportError:
    LINKEDIN_AVAILABLE = False

# Auth Type: OAuth2
router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])

class LinkedInAuthRequest(BaseModel):
    code: str
    redirect_uri: str

@router.get("/auth/url")
async def get_auth_url(redirect_uri: str = "http://localhost:3000/integrations/linkedin/callback"):
    """Get LinkedIn OAuth URL"""
    if not LINKEDIN_AVAILABLE:
        return {
            "url": f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=INSERT_CLIENT_ID&redirect_uri={redirect_uri}&scope=r_liteprofile%20r_emailaddress",
            "timestamp": datetime.now().isoformat()
        }
    
    service = get_linkedin_service()
    url = service.get_authorization_url(redirect_uri)
    
    return {
        "url": url,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/callback")
async def handle_oauth_callback(auth_request: LinkedInAuthRequest):
    """Handle LinkedIn OAuth callback"""
    if not LINKEDIN_AVAILABLE:
        return {
            "ok": True,
            "status": "success",
            "code": auth_request.code,
            "message": "LinkedIn authentication successful (mock)",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        service = get_linkedin_service()
        token_data = await service.exchange_token(auth_request.code, auth_request.redirect_uri)
        
        return {
            "ok": True,
            "status": "success",
            "access_token": token_data.get("access_token"),
            "message": "LinkedIn authentication successful",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/profile")
async def get_profile(access_token: str):
    """Get LinkedIn user profile"""
    if not LINKEDIN_AVAILABLE:
        return {"name": "Mock User", "id": "mock_id"}
    
    try:
        service = get_linkedin_service()
        profile = await service.get_profile(access_token)
        return profile
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/share")
async def share_update(access_token: str, text: str, visibility: str = "PUBLIC"):
    """Share an update on LinkedIn"""
    if not LINKEDIN_AVAILABLE:
        return {"ok": True, "message": "Update shared (mock)"}
    
    try:
        service = get_linkedin_service()
        result = await service.share_update(text, access_token, visibility)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def linkedin_status():
    """Status check for LinkedIn integration"""
    return {
        "status": "active",
        "service": "linkedin",
        "version": "1.0.0",
        "available": LINKEDIN_AVAILABLE,
        "business_value": {
            "networking": True,
            "lead_generation": True,
            "brand_awareness": True
        }
    }

@router.get("/health")
async def linkedin_health():
    """Health check for LinkedIn integration"""
    if LINKEDIN_AVAILABLE:
        service = get_linkedin_service()
        return await service.health_check()
    return await linkedin_status()
