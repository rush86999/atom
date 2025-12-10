"""
Social Platform Store API Routes
Handles storage and management of social platform OAuth tokens and data
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.security import HTTPBearer
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import logging
from datetime import datetime

from social_store import get_social_store, SocialPlatform, SocialProfile
from core.token_storage import token_storage

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/integrations/social", tags=["social-store"])

# Security
security = HTTPBearer()

class StoreTokenRequest(BaseModel):
    platform: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    scope: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None

class StoreProfileRequest(BaseModel):
    platform: str
    username: str
    display_name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    profile_url: Optional[str] = None
    bio: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    verified: bool = False
    public_metrics: Optional[Dict[str, Any]] = None

@router.post("/store", response_model=Dict[str, Any])
async def store_social_token(
    request: StoreTokenRequest,
    http_request: Request
):
    """
    Store social platform OAuth token
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")
        user_id = http_request.headers.get("X-User-ID", "unknown")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Validate platform
        try:
            platform = SocialPlatform(request.platform)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform: {request.platform}. Supported platforms: {[p.value for p in SocialPlatform]}"
            )

        # Get social store
        store = get_social_store()

        # Store token
        success = await store.store_token(
            platform=platform.value,
            user_email=user_email,
            user_id=user_id,
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            expires_in=request.expires_in,
            scope=request.scope,
            user_info=request.user_info
        )

        if success:
            return {
                "success": True,
                "message": f"Token stored successfully for {platform.value}",
                "platform": platform.value,
                "user_email": user_email
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to store token"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing social token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/token/{platform}", response_model=Dict[str, Any])
async def get_social_token(
    platform: str,
    http_request: Request
):
    """
    Retrieve stored token for a social platform
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Validate platform
        try:
            SocialPlatform(platform)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform: {platform}"
            )

        # Get social store
        store = get_social_store()

        # Retrieve token
        token = await store.get_token(platform, user_email)

        if token:
            # Return token data without sensitive information
            return {
                "platform": token.platform,
                "user_email": token.user_email,
                "scope": token.scope,
                "token_type": token.token_type,
                "expires_at": token.expires_at,
                "user_info": token.user_info,
                "timestamp": token.timestamp,
                "has_refresh_token": token.refresh_token is not None
            }
        else:
            return {
                "platform": platform,
                "user_email": user_email,
                "message": "No token found",
                "connected": False
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving social token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile", response_model=Dict[str, Any])
async def store_social_profile(
    request: StoreProfileRequest,
    http_request: Request
):
    """
    Store user profile data from social platform
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Validate platform
        try:
            platform = SocialPlatform(request.platform)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform: {request.platform}"
            )

        # Create profile object
        profile = SocialProfile(
            platform=platform.value,
            user_id=user_email,  # Using email as user ID for this example
            username=request.username,
            display_name=request.display_name,
            email=request.email,
            avatar_url=request.avatar_url,
            profile_url=request.profile_url,
            bio=request.bio,
            followers_count=request.followers_count,
            following_count=request.following_count,
            verified=request.verified,
            public_metrics=request.public_metrics
        )

        # Get social store
        store = get_social_store()

        # Store profile
        success = await store.store_profile(platform.value, user_email, profile)

        if success:
            return {
                "success": True,
                "message": f"Profile stored successfully for {platform.value}",
                "platform": platform.value,
                "user_email": user_email
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to store profile"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing social profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profile/{platform}", response_model=Dict[str, Any])
async def get_social_profile(
    platform: str,
    http_request: Request
):
    """
    Retrieve stored profile data for a social platform
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Validate platform
        try:
            SocialPlatform(platform)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform: {platform}"
            )

        # Get social store
        store = get_social_store()

        # Retrieve profile
        profile = await store.get_profile(platform, user_email)

        if profile:
            return profile.__dict__
        else:
            return {
                "platform": platform,
                "user_email": user_email,
                "message": "No profile found"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving social profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connected", response_model=Dict[str, Any])
async def get_connected_platforms(
    http_request: Request
):
    """
    List all connected social platforms for the user
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Get social store
        store = get_social_store()

        # Get connected platforms
        platforms = await store.list_connected_platforms(user_email)

        return {
            "user_email": user_email,
            "connected_platforms": platforms,
            "total_connected": len(platforms),
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing connected platforms: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/data", response_model=Dict[str, Any])
async def get_all_user_data(
    http_request: Request
):
    """
    Get all stored data for the user across all social platforms
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Get social store
        store = get_social_store()

        # Get all user data
        user_data = await store.get_all_user_data(user_email)

        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving all user data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/disconnect/{platform}", response_model=Dict[str, Any])
async def disconnect_social_platform(
    platform: str,
    http_request: Request
):
    """
    Remove social platform integration and all stored data
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Validate platform
        try:
            SocialPlatform(platform)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform: {platform}"
            )

        # Get social store
        store = get_social_store()

        # Remove platform
        success = await store.remove_platform(platform, user_email)

        if success:
            return {
                "success": True,
                "message": f"Successfully disconnected from {platform}",
                "platform": platform,
                "user_email": user_email
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to disconnect platform"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting social platform: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check for social platform store
    """
    try:
        store = get_social_store()
        health = await store.health_check()
        return health

    except Exception as e:
        logger.error(f"Social store health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "social_platform_store",
            "error": str(e)
        }

@router.post("/cleanup", response_model=Dict[str, Any])
async def cleanup_expired_tokens():
    """
    Clean up expired tokens (maintenance endpoint)
    """
    try:
        store = get_social_store()
        result = await store.cleanup_expired_tokens()
        return result

    except Exception as e:
        logger.error(f"Token cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/platforms", response_model=Dict[str, Any])
async def get_supported_platforms():
    """
    Get list of supported social platforms
    """
    try:
        return {
            "supported_platforms": [p.value for p in SocialPlatform],
            "total_platforms": len(SocialPlatform),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error listing supported platforms: {e}")
        raise HTTPException(status_code=500, detail=str(e))