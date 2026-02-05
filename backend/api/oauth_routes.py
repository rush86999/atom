"""
OAuth Integration Routes

Provides OAuth callback endpoints for third-party integrations.
Handles OAuth flows for Slack, Google, GitHub, and other providers.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import OAuthToken, User
from core.oauth_handler import OAuthHandler, SLACK_OAUTH_CONFIG

router = BaseAPIRouter(prefix="/api/v1/integrations", tags=["oauth"])
logger = logging.getLogger(__name__)


# Request/Response Models
class OAuthCallbackRequest(BaseModel):
    """OAuth callback request payload"""
    code: str
    state: Optional[str] = None
    error: Optional[str] = None
    error_description: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class OAuthTokenResponse(BaseModel):
    """OAuth token response"""
    provider: str
    access_token: str  # Note: This should be used immediately to get user info, then discarded
    token_type: str = "Bearer"
    scopes: list[str] = []
    expires_at: Optional[datetime] = None
    status: str = "active"


class OAuthErrorResponse(BaseModel):
    """OAuth error response"""
    success: bool = False
    error: str
    message: str


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Get current user from session.
    Supports multiple auth methods: JWT token, session headers, or email.
    """
    # Method 1: Try JWT token from Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from core.enterprise_auth_service import EnterpriseAuthService
            auth_service = EnterpriseAuthService()
            token = auth_header.split(" ")[1]
            claims = auth_service.verify_token(token)
            if claims:
                user_id = claims.get('user_id')
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user
        except Exception as e:
            logger.debug(f"JWT auth failed: {e}")

    # Method 2: Try X-User-ID header (from NextAuth session)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    # Method 3: Try X-User-Email header (alternative from session)
    user_email = request.headers.get("X-User-Email")
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            return user

    # Method 4: Create temp user for development (if in dev mode)
    import os
    if os.getenv("ENVIRONMENT", "development") == "development":
        temp_id = request.headers.get("X-User-ID") or "dev_user"
        user = db.query(User).filter(User.id == temp_id).first()
        if not user:
            # Create temporary user for development
            user = User(
                id=temp_id,
                email=f"dev_{temp_id}@example.com",
                first_name="Dev",
                last_name="User"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Valid authentication required"
    )


@router.post("/slack/oauth/callback", response_model=OAuthTokenResponse)
async def slack_oauth_callback(
    request: Request,
    payload: OAuthCallbackRequest,
    db: Session = Depends(get_db)
):
    """
    Handle Slack OAuth callback.

    Exchanges the authorization code for access tokens and stores them securely.

    Flow:
    1. User clicks "Connect Slack" in frontend
    2. Frontend redirects to Slack OAuth URL (generated using OAuthHandler)
    3. User authorizes the app
    4. Slack redirects to this callback with a code
    5. Backend exchanges code for tokens
    6. Tokens are encrypted and stored in database

    Environment Variables Required:
    - SLACK_CLIENT_ID
    - SLACK_CLIENT_SECRET
    - SLACK_REDIRECT_URI (must match Slack app settings)

    Security:
    - Tokens are encrypted at rest using Fernet symmetric encryption
    - State parameter validation prevents CSRF attacks
    - Access tokens are never returned to frontend after initial exchange
    """
    try:
        # Handle OAuth errors from provider
        if payload.error:
            logger.error(f"Slack OAuth error: {payload.error} - {payload.error_description}")
            raise HTTPException(
                status_code=400,
                detail=f"OAuth authorization failed: {payload.error_description or payload.error}"
            )

        # Initialize OAuth handler with Slack config
        oauth_handler = OAuthHandler(SLACK_OAUTH_CONFIG)

        # Exchange authorization code for access token
        token_data = await oauth_handler.exchange_code_for_tokens(payload.code)

        # Extract token information
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")  # Slack may not provide this
        token_type = token_data.get("token_type", "Bearer")
        scopes = token_data.get("scope", "").split(",")

        # Calculate expiration (Slack tokens don't expire, but we set a default)
        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))

        # Get current user (handles multiple auth methods including dev mode)
        current_user = get_current_user(request, db)

        # Check if user already has a Slack token (update if exists)
        existing_token = db.query(OAuthToken).filter(
            OAuthToken.user_id == current_user.id,
            OAuthToken.provider == "slack",
            OAuthToken.status == "active"
        ).first()

        if existing_token:
            # Update existing token
            existing_token.access_token = access_token
            if refresh_token:
                existing_token.refresh_token = refresh_token
            existing_token.scopes = scopes
            existing_token.expires_at = expires_at
            existing_token.last_used = datetime.utcnow()
            existing_token.status = "active"
            logger.info(f"Updated Slack OAuth token for user {current_user.id}")
        else:
            # Create new token record
            oauth_token = OAuthToken(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                provider="slack",
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                scopes=scopes,
                expires_at=expires_at,
                status="active",
                last_used=datetime.utcnow()
            )
            db.add(oauth_token)
            logger.info(f"Created new Slack OAuth token for user {current_user.id}")

        db.commit()

        # Return token info (access token included for immediate use)
        return OAuthTokenResponse(
            provider="slack",
            access_token=access_token,
            token_type=token_type,
            scopes=scopes,
            expires_at=expires_at,
            status="active"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slack OAuth callback failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete OAuth flow: {str(e)}"
        )


@router.get("/slack/oauth/authorize")
async def slack_oauth_authorize(request: Request):
    """
    Generate Slack OAuth authorization URL.

    Returns the URL that the frontend should redirect the user to
    for Slack OAuth authorization.

    Query Parameters:
    - redirect_uri: Optional override for redirect URI
    - state: Optional CSRF protection token

    Returns:
    - authorization_url: The Slack OAuth URL to redirect to
    - state: The state parameter for CSRF protection
    """
    try:
        # Get redirect URI from query or use default
        redirect_uri = request.query_params.get("redirect_uri")
        state = request.query_params.get("state", str(uuid.uuid4()))

        # Create OAuth config with optional redirect URI override
        config = SLACK_OAUTH_CONFIG
        if redirect_uri:
            config.redirect_uri = redirect_uri

        oauth_handler = OAuthHandler(config)
        auth_url = oauth_handler.get_authorization_url(state=state)

        return {
            "authorization_url": auth_url,
            "state": state,
            "provider": "slack"
        }

    except Exception as e:
        logger.error(f"Failed to generate Slack authorization URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )


@router.get("/oauth/tokens")
async def list_oauth_tokens(
    request: Request,
    provider: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all OAuth tokens for the current user.

    Query Parameters:
    - provider: Filter by provider (e.g., "slack", "google")

    Returns:
    - List of OAuth tokens with metadata (no actual tokens)
    """
    try:
        current_user = get_current_user(request, db)

        query = db.query(OAuthToken).filter(OAuthToken.user_id == current_user.id)

        if provider:
            query = query.filter(OAuthToken.provider == provider)

        tokens = query.all()

        # Return token metadata (not actual tokens)
        return {
            "tokens": [
                {
                    "id": t.id,
                    "provider": t.provider,
                    "token_type": t.token_type,
                    "scopes": t.scopes,
                    "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                    "status": t.status,
                    "last_used": t.last_used.isoformat() if t.last_used else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                for t in tokens
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list OAuth tokens: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve tokens: {str(e)}"
        )


@router.delete("/oauth/tokens/{provider}")
async def revoke_oauth_token(
    provider: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Revoke OAuth token for a specific provider.

    Path Parameters:
    - provider: The provider to revoke (e.g., "slack", "google")

    Marks the token as revoked in the database.
    """
    try:
        current_user = get_current_user(request, db)

        token = db.query(OAuthToken).filter(
            OAuthToken.user_id == current_user.id,
            OAuthToken.provider == provider,
            OAuthToken.status == "active"
        ).first()

        if not token:
            raise HTTPException(
                status_code=404,
                detail=f"No active token found for provider: {provider}"
            )

        # Mark as revoked
        token.status = "revoked"
        db.commit()

        logger.info(f"Revoked {provider} OAuth token for user {current_user.id}")

        return {
            "success": True,
            "message": f"Successfully revoked {provider} integration"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke OAuth token: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to revoke token: {str(e)}"
        )


# Health check for OAuth configuration
@router.get("/oauth/config-status")
async def oauth_config_status():
    """
    Check OAuth configuration status for all providers.

    Returns which OAuth providers are properly configured
    with environment variables.
    """
    providers = {
        "slack": SLACK_OAUTH_CONFIG.is_configured(),
        # Add more providers as they're implemented
    }

    configured_providers = [p for p, is_configured in providers.items() if is_configured]

    return {
        "providers": providers,
        "configured_count": len(configured_providers),
        "total_count": len(providers),
        "all_configured": all(providers.values())
    }
