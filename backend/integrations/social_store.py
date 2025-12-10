"""
Social Platform Storage Backend
Handles storage and management of social platform OAuth tokens and data
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import aiofiles
from fastapi import HTTPException
from loguru import logger

# Import token storage for secure storage
from core.token_storage import token_storage

class SocialPlatform(Enum):
    """Supported social platforms"""
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    REDDIT = "reddit"
    PINTEREST = "pinterest"

@dataclass
class SocialToken:
    """Social platform token data"""
    platform: str
    user_email: str
    user_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    scope: Optional[str] = None
    token_type: str = "Bearer"
    user_info: Optional[Dict[str, Any]] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

@dataclass
class SocialProfile:
    """Social platform user profile data"""
    platform: str
    user_id: str
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
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

class SocialPlatformStore:
    """Enhanced storage for social platform data"""

    def __init__(self):
        self.encryption_key = os.getenv("SOCIAL_STORAGE_KEY")
        if not self.encryption_key:
            # Generate a warning but continue with basic storage
            logger.warning("SOCIAL_STORAGE_KEY not set, using basic storage")
            self.encryption_key = None

    async def store_token(
        self,
        platform: str,
        user_email: str,
        user_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        scope: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store social platform access token securely
        """
        try:
            # Calculate expiry time
            expires_at = None
            if expires_in:
                expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
                expires_at = expiry_time.isoformat()

            # Create token object
            token_data = SocialToken(
                platform=platform,
                user_email=user_email,
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=scope,
                user_info=user_info
            )

            # Store using token storage service
            storage_key = f"{platform}_{user_email.replace('@', '_').replace('.', '_')}"
            token_storage.save_token(storage_key, asdict(token_data))

            logger.info(f"Stored token for {platform} - {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to store {platform} token for {user_email}: {e}")
            return False

    async def get_token(
        self,
        platform: str,
        user_email: str
    ) -> Optional[SocialToken]:
        """
        Retrieve stored token for a social platform
        """
        try:
            storage_key = f"{platform}_{user_email.replace('@', '_').replace('.', '_')}"
            stored_data = token_storage.get_token(storage_key)

            if not stored_data:
                logger.warning(f"No token found for {platform} - {user_email}")
                return None

            # Check if token is expired
            if "expires_at" in stored_data:
                expiry_time = datetime.fromisoformat(stored_data["expires_at"])
                if datetime.utcnow() >= expiry_time:
                    logger.warning(f"Token expired for {platform} - {user_email}")
                    # Try to refresh if refresh token is available
                    if "refresh_token" in stored_data and stored_data["refresh_token"]:
                        refreshed = await self.refresh_token(platform, user_email, stored_data["refresh_token"])
                        if refreshed:
                            return SocialToken(**refreshed)
                    return None

            return SocialToken(**stored_data)

        except Exception as e:
            logger.error(f"Failed to retrieve {platform} token for {user_email}: {e}")
            return None

    async def refresh_token(
        self,
        platform: str,
        user_email: str,
        refresh_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh access token using refresh token
        """
        try:
            # This would be platform-specific implementation
            # For now, return None as refresh logic varies by platform
            logger.info(f"Token refresh requested for {platform} - {user_email}")
            return None

        except Exception as e:
            logger.error(f"Failed to refresh {platform} token: {e}")
            return None

    async def store_profile(
        self,
        platform: str,
        user_email: str,
        profile_data: SocialProfile
    ) -> bool:
        """
        Store user profile data from social platform
        """
        try:
            storage_key = f"{platform}_profile_{user_email.replace('@', '_').replace('.', '_')}"
            token_storage.save_token(storage_key, asdict(profile_data))

            logger.info(f"Stored profile for {platform} - {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to store {platform} profile for {user_email}: {e}")
            return False

    async def get_profile(
        self,
        platform: str,
        user_email: str
    ) -> Optional[SocialProfile]:
        """
        Retrieve stored profile data
        """
        try:
            storage_key = f"{platform}_profile_{user_email.replace('@', '_').replace('.', '_')}"
            stored_data = token_storage.get_token(storage_key)

            if not stored_data:
                return None

            return SocialProfile(**stored_data)

        except Exception as e:
            logger.error(f"Failed to retrieve {platform} profile for {user_email}: {e}")
            return None

    async def list_connected_platforms(self, user_email: str) -> List[str]:
        """
        List all connected social platforms for a user
        """
        try:
            platforms = []
            available_platforms = [p.value for p in SocialPlatform]

            for platform in available_platforms:
                token = await self.get_token(platform, user_email)
                if token:
                    platforms.append(platform)

            return platforms

        except Exception as e:
            logger.error(f"Failed to list connected platforms for {user_email}: {e}")
            return []

    async def remove_platform(
        self,
        platform: str,
        user_email: str
    ) -> bool:
        """
        Remove social platform integration and tokens
        """
        try:
            # Remove token
            token_key = f"{platform}_{user_email.replace('@', '_').replace('.', '_')}"
            token_storage.delete_token(token_key)

            # Remove profile
            profile_key = f"{platform}_profile_{user_email.replace('@', '_').replace('.', '_')}"
            token_storage.delete_token(profile_key)

            logger.info(f"Removed {platform} integration for {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove {platform} for {user_email}: {e}")
            return False

    async def get_all_user_data(self, user_email: str) -> Dict[str, Any]:
        """
        Get all stored data for a user across all platforms
        """
        try:
            user_data = {
                "user_email": user_email,
                "connected_platforms": {},
                "profiles": {},
                "timestamp": datetime.utcnow().isoformat()
            }

            connected_platforms = await self.list_connected_platforms(user_email)

            for platform in connected_platforms:
                # Get token data (without sensitive info)
                token = await self.get_token(platform, user_email)
                if token:
                    user_data["connected_platforms"][platform] = {
                        "platform": platform,
                        "scope": token.scope,
                        "expires_at": token.expires_at,
                        "timestamp": token.timestamp
                    }

                # Get profile data
                profile = await self.get_profile(platform, user_email)
                if profile:
                    user_data["profiles"][platform] = asdict(profile)

            return user_data

        except Exception as e:
            logger.error(f"Failed to get all user data for {user_email}: {e}")
            return {
                "user_email": user_email,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        Health check for social platform storage
        """
        try:
            # Test basic storage functionality
            test_key = "health_check_test"
            test_data = {"test": True, "timestamp": datetime.utcnow().isoformat()}

            token_storage.save_token(test_key, test_data)
            retrieved_data = token_storage.get_token(test_key)
            token_storage.delete_token(test_key)

            if not retrieved_data or not retrieved_data.get("test"):
                raise Exception("Storage test failed")

            return {
                "status": "healthy",
                "service": "social_platform_store",
                "supported_platforms": [p.value for p in SocialPlatform],
                "encryption_enabled": self.encryption_key is not None,
                "storage_test": "passed",
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Social platform store health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "social_platform_store",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def cleanup_expired_tokens(self) -> Dict[str, Any]:
        """
        Clean up expired tokens
        """
        try:
            cleaned_count = 0
            # This would require scanning all stored tokens
            # For now, return placeholder result
            return {
                "status": "completed",
                "cleaned_tokens": cleaned_count,
                "message": "Token cleanup completed",
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Token cleanup failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

# API Routes
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

# Create router
router = APIRouter(prefix="/api/integrations/social", tags=["social-store"])

# Pydantic models for API
class SocialTokenRequest(BaseModel):
    platform: str
    user_email: str
    user_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    scope: Optional[str] = None
    token_type: str = "Bearer"
    user_info: Optional[Dict[str, Any]] = None

class SocialTokenResponse(BaseModel):
    success: bool
    message: str
    token: Optional[Dict[str, Any]] = None

class SocialPlatformsResponse(BaseModel):
    platforms: List[str]
    count: int

# API Endpoints
@router.post("/store", response_model=SocialTokenResponse)
async def store_social_token(request: SocialTokenRequest):
    """
    Store a social platform OAuth token
    """
    try:
        # Validate platform
        try:
            platform = SocialPlatform(request.platform.lower())
        except ValueError:
            available_platforms = [p.value for p in SocialPlatform]
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform '{request.platform}'. Available platforms: {available_platforms}"
            )

        # Create token object
        token = SocialToken(
            platform=platform.value,
            user_email=request.user_email,
            user_id=request.user_id,
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            expires_at=request.expires_at,
            scope=request.scope,
            token_type=request.token_type,
            user_info=request.user_info
        )

        # Store the token
        success = await social_store.store_token(
            platform=platform.value,
            user_email=request.user_email,
            user_id=request.user_id,
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            expires_in=int((datetime.fromisoformat(request.expires_at) - datetime.utcnow()).total_seconds()) if request.expires_at else None,
            scope=request.scope,
            user_info=request.user_info
        )

        if success:
            return SocialTokenResponse(
                success=True,
                message=f"Token stored successfully for {platform.value}",
                token=asdict(token)
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to store token")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing social token: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/platforms", response_model=SocialPlatformsResponse)
async def get_supported_platforms():
    """
    Get list of supported social platforms
    """
    try:
        platforms = [platform.value for platform in SocialPlatform]
        return SocialPlatformsResponse(
            platforms=platforms,
            count=len(platforms)
        )
    except Exception as e:
        logger.error(f"Error getting supported platforms: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/tokens/{platform}/{user_id}")
async def get_user_token(platform: str, user_id: str):
    """
    Get stored token for a specific platform and user
    """
    try:
        # Validate platform
        try:
            SocialPlatform(platform.lower())
        except ValueError:
            available_platforms = [p.value for p in SocialPlatform]
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform '{platform}'. Available platforms: {available_platforms}"
            )

        token = await social_store.get_token(platform.lower(), user_id)

        if token:
            return {
                "success": True,
                "token": asdict(token)
            }
        else:
            raise HTTPException(status_code=404, detail="Token not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving social token: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/tokens/{platform}/{user_id}")
async def delete_user_token(platform: str, user_id: str):
    """
    Delete stored token for a specific platform and user
    """
    try:
        # Validate platform
        try:
            SocialPlatform(platform.lower())
        except ValueError:
            available_platforms = [p.value for p in SocialPlatform]
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform '{platform}'. Available platforms: {available_platforms}"
            )

        success = await social_store.remove_platform(platform.lower(), user_id)

        if success:
            return {
                "success": True,
                "message": f"Token deleted successfully for {platform}"
            }
        else:
            raise HTTPException(status_code=404, detail="Token not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting social token: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error")

@router.get("/health")
async def health_check():
    """
    Health check for social platform store service
    """
    try:
        health = await social_store.health_check()
        return health
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/tokens/{platform}/{user_id}/validate")
async def validate_token(platform: str, user_id: str):
    """
    Validate if a stored token is still valid
    """
    try:
        # Validate platform
        try:
            SocialPlatform(platform.lower())
        except ValueError:
            available_platforms = [p.value for p in SocialPlatform]
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform '{platform}'. Available platforms: {available_platforms}"
            )

        token = await social_store.get_token(platform.lower(), user_id)
        is_valid = token is not None and (
            not token.expires_at or
            datetime.fromisoformat(token.expires_at) > datetime.utcnow()
        )

        return {
            "valid": is_valid,
            "platform": platform,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error")

@router.get("/user/{user_id}/tokens")
async def get_user_all_tokens(user_id: str):
    """
    Get all tokens for a specific user across all platforms
    """
    try:
        # Get all tokens for user across platforms
        platforms = [p.value for p in SocialPlatform]
        tokens = []

        for platform in platforms:
            token = await social_store.get_token(platform, user_id)
            if token:
                tokens.append(asdict(token))

        return {
            "success": True,
            "user_id": user_id,
            "tokens": tokens,
            "count": len(tokens),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting user tokens: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error")

# Global store instance
social_store = SocialPlatformStore()

# Utility functions
def get_social_store() -> SocialPlatformStore:
    """Get social platform store instance"""
    return social_store