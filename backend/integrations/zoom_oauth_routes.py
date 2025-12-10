"""
Zoom OAuth API Routes
Handles Zoom OAuth 2.0 flow with PKCE support
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.security import HTTPBearer
from typing import Dict, Any, Optional
from pydantic import BaseModel
import secrets
from datetime import datetime, timedelta
import logging

from zoom_callback import get_zoom_oauth_callback
from core.token_storage import token_storage

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/zoom", tags=["zoom-oauth"])

# Security
security = HTTPBearer()

class OAuthURLRequest(BaseModel):
    redirect_uri: str
    use_pkce: bool = True
    state: Optional[str] = None

class TokenExchangeRequest(BaseModel):
    code: str
    redirect_uri: str
    state: str
    use_pkce: bool = True

@router.get("/oauth-url", response_model=Dict[str, Any])
async def get_oauth_url(
    request: OAuthURLRequest,
    http_request: Request
):
    """
    Generate Zoom OAuth authorization URL with optional PKCE support
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")
        user_id = http_request.headers.get("X-User-ID")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Generate state if not provided
        if not request.state:
            # Include user email in state for better tracking
            state_data = f"{secrets.token_urlsafe(32)}_{user_email}"
        else:
            state_data = request.state

        # Get OAuth callback handler
        callback_handler = get_zoom_oauth_callback()

        # Generate OAuth URL
        oauth_url = callback_handler.get_oauth_url(
            redirect_uri=request.redirect_uri,
            state=state_data,
            use_pkce=request.use_pkce
        )

        # Store state in cookie for CSRF protection (frontend side)
        # The PKCE code verifier is stored by the callback handler

        return {
            "oauth_url": oauth_url,
            "state": state_data,
            "use_pkce": request.use_pkce,
            "expires_in": 600,  # 10 minutes
        }

    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/exchange-code", response_model=Dict[str, Any])
async def exchange_code_for_token(
    request: TokenExchangeRequest,
    http_request: Request
):
    """
    Exchange authorization code for access token with PKCE support
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")
        user_id = http_request.headers.get("X-User-ID")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Get OAuth callback handler
        callback_handler = get_zoom_oauth_callback()

        # Exchange code for token
        result = await callback_handler.exchange_code_for_token(
            code=request.code,
            redirect_uri=request.redirect_uri,
            state=request.state,
            use_pkce=request.use_pkce
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exchanging code for token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh-token", response_model=Dict[str, Any])
async def refresh_access_token(
    refresh_token: str,
    http_request: Request
):
    """
    Refresh access token using refresh token
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")
        user_id = http_request.headers.get("X-User-ID")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Get OAuth callback handler
        callback_handler = get_zoom_oauth_callback()

        # Refresh token
        result = await callback_handler.refresh_tokens(refresh_token)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/revoke-token", response_model=Dict[str, Any])
async def revoke_access_token(
    access_token: str,
    http_request: Request
):
    """
    Revoke access token
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")
        user_id = http_request.headers.get("X-User-ID")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Get OAuth callback handler
        callback_handler = get_zoom_oauth_callback()

        # Revoke token
        result = await callback_handler.revoke_token(access_token)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=Dict[str, Any])
async def get_oauth_status(
    http_request: Request
):
    """
    Get current OAuth status and stored tokens
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")
        user_id = http_request.headers.get("X-User-ID")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Check if we have stored tokens
        try:
            stored_token = token_storage.get_token("zoom")
            if not stored_token:
                return {
                    "connected": False,
                    "service": "zoom",
                    "message": "No Zoom integration found"
                }

            # Check if token is expired
            if "expires_at" in stored_token:
                expiry_time = datetime.fromisoformat(stored_token["expires_at"])
                if datetime.utcnow() >= expiry_time:
                    return {
                        "connected": False,
                        "service": "zoom",
                        "message": "Zoom access token has expired"
                    }

            # Return connection status
            return {
                "connected": True,
                "service": "zoom",
                "user_email": user_email,
                "scope": stored_token.get("scope", ""),
                "token_type": stored_token.get("token_type", "Bearer"),
                "expires_at": stored_token.get("expires_at"),
                "has_refresh_token": "refresh_token" in stored_token,
                "connected_at": stored_token.get("timestamp")
            }

        except Exception as e:
            logger.error(f"Error checking OAuth status: {e}")
            return {
                "connected": False,
                "service": "zoom",
                "message": f"Error checking status: {str(e)}"
            }

    except Exception as e:
        logger.error(f"Error in OAuth status endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/disconnect", response_model=Dict[str, Any])
async def disconnect_zoom(
    http_request: Request
):
    """
    Disconnect Zoom integration and revoke tokens
    """
    try:
        # Get user information from request headers
        user_email = http_request.headers.get("X-User-Email")
        user_id = http_request.headers.get("X-User-ID")

        if not user_email:
            raise HTTPException(status_code=401, detail="User email is required")

        # Get stored token
        try:
            stored_token = token_storage.get_token("zoom")
            if stored_token and "access_token" in stored_token:
                # Revoke the token
                callback_handler = get_zoom_oauth_callback()
                await callback_handler.revoke_token(stored_token["access_token"])
        except Exception as e:
            logger.warning(f"Error revoking token during disconnect: {e}")

        # Remove stored token
        token_storage.delete_token("zoom")

        return {
            "success": True,
            "message": "Zoom integration disconnected successfully",
            "service": "zoom",
            "user_email": user_email
        }

    except Exception as e:
        logger.error(f"Error disconnecting Zoom: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check for Zoom OAuth service
    """
    try:
        # Check if OAuth callback handler is available
        callback_handler = get_zoom_oauth_callback()

        return {
            "status": "healthy",
            "service": "zoom-oauth",
            "timestamp": datetime.utcnow().isoformat(),
            "pkce_support": True,
            "callback_handler_available": True
        }

    except Exception as e:
        logger.error(f"Zoom OAuth health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "zoom-oauth",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }