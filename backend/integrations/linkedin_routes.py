from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
        raise HTTPException(
            status_code=501,
            detail="LinkedIn service not available. Please install required dependencies."
        )

    # Validate access token
    if not access_token or access_token == "mock" or access_token == "fake_token":
        raise HTTPException(
            status_code=401,
            detail="Invalid LinkedIn access token. Please authenticate with LinkedIn."
        )

    try:
        service = get_linkedin_service()
        profile = await service.get_profile(access_token)

        # Transform response to match expected format
        return {
            "id": profile.get("id"),
            "name": f"{profile.get('localizedFirstName', '')} {profile.get('localizedLastName', '')}".strip(),
            "firstName": profile.get("localizedFirstName"),
            "lastName": profile.get("localizedLastName"),
            "profilePicture": profile.get("profilePicture", {}).get("displayImage~", {}).get("elements", [{}])[0].get("identifiers", [{}])[0].get("identifier") if profile.get("profilePicture") else None,
            "headline": profile.get("headline", {}).get("default") if profile.get("headline") else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get LinkedIn profile: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/share")
async def share_update(access_token: str, text: str, visibility: str = "PUBLIC"):
    """Share an update on LinkedIn"""
    if not LINKEDIN_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="LinkedIn service not available. Please install required dependencies."
        )

    # Validate access token
    if not access_token or access_token == "mock" or access_token == "fake_token":
        raise HTTPException(
            status_code=401,
            detail="Invalid LinkedIn access token. Please authenticate with LinkedIn."
        )

    # Validate text content
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Post content cannot be empty"
        )

    # Validate visibility
    valid_visibilities = ["PUBLIC", "CONNECTIONS", "CONTAINER"]
    if visibility.upper() not in valid_visibilities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid visibility. Must be one of: {', '.join(valid_visibilities)}"
        )

    try:
        service = get_linkedin_service()
        result = await service.share_update(text, access_token, visibility.upper())

        return {
            "ok": True,
            "id": result.get("id"),
            "message": "Update shared successfully on LinkedIn",
            "postUrn": result.get("id"),
            "status": "published"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to share LinkedIn update: {e}")
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
