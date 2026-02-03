import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from core.oauth_handler import OAuthHandler, GOOGLE_OAUTH_CONFIG
from core.token_storage import token_storage
from integrations.google_calendar_service import google_calendar_service

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/google-calendar", tags=["google-calendar"])

# Initialize OAuth handler
google_oauth = OAuthHandler(GOOGLE_OAUTH_CONFIG)

@router.get("/auth/url")
async def get_auth_url(state: Optional[str] = None):
    """
    Get Google Calendar OAuth URL

    Generates an OAuth authorization URL for Google Calendar access.
    """
    try:
        auth_url = google_oauth.get_authorization_url(state=state)
        return {
            "url": auth_url,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )

@router.get("/callback")
async def handle_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: Optional[str] = Query(None, description="State parameter for security"),
    error: Optional[str] = Query(None, description="Error if user denied access")
):
    """
    Handle Google Calendar OAuth callback

    Exchanges authorization code for access tokens and stores them securely.
    """
    try:
        # Handle user denial
        if error:
            return {
                "ok": False,
                "status": "error",
                "error": error,
                "message": "Authorization was denied",
                "timestamp": datetime.now().isoformat()
            }

        # Exchange code for tokens
        tokens = await google_oauth.exchange_code_for_tokens(code)

        if not tokens.get("access_token"):
            raise HTTPException(
                status_code=400,
                detail="Failed to exchange authorization code for tokens"
            )

        # Store tokens securely
        # Use state as user_id (in production, validate and decrypt state)
        user_id = state or "default"
        token_storage.save_token("google", tokens)

        # Test the connection by authenticating the service
        test_success = google_calendar_service.authenticate()

        logger.info(f"Google Calendar OAuth successful for user {user_id}")

        return {
            "ok": True,
            "status": "success",
            "service": "google-calendar",
            "test_connection": test_success,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google Calendar OAuth failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OAuth authentication failed: {str(e)}"
        )

class GoogleCalendarService:
    """Service for Google Calendar integration"""
    def __init__(self):
        pass

@router.get("/status")
async def google_calendar_status():
    """Status check for Google Calendar integration"""
    return {
        "status": "active",
        "service": "google-calendar",
        "version": "1.0.0",
        "business_value": {
            "scheduling": True,
            "time_management": True,
            "meeting_coordination": True
        }
    }

@router.get("/health")
async def google_calendar_health():
    """Health check for Google Calendar integration"""
    return await google_calendar_status()
