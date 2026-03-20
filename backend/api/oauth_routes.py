"""
OAuth Integration Routes

Provides unified OAuth callback endpoints for all third-party integrations.
Handles OAuth flows for Google, LinkedIn, Microsoft, Salesforce, Slack, GitHub, Asana, Notion, Trello, and Dropbox.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import OAuthToken, User
from core.oauth_handler import (
    ASANA_OAUTH_CONFIG,
    DROPBOX_OAUTH_CONFIG,
    GITHUB_OAUTH_CONFIG,
    GOOGLE_OAUTH_CONFIG,
    LINKEDIN_OAUTH_CONFIG,
    MICROSOFT_OAUTH_CONFIG,
    NOTION_OAUTH_CONFIG,
    SALESFORCE_OAUTH_CONFIG,
    SLACK_OAUTH_CONFIG,
    TRELLO_OAUTH_CONFIG,
    OAuthHandler,
)

router = BaseAPIRouter(prefix="/api/v1/auth/oauth", tags=["OAuth"])
logger = logging.getLogger(__name__)

# ============================================================================
# Helpers
# ============================================================================

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Get current user from session/headers."""
    # Simplified for this context - should use the same logic as auth_routes.py
    user_id = request.headers.get("X-User-ID")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user
            
    # Fallback to dev user if allowed
    if os.getenv("ENVIRONMENT") == "development":
        user = db.query(User).first()
        if user:
            return user
            
    raise HTTPException(status_code=401, detail="Unauthorized")

async def _handle_callback_logic(provider: str, code: str, config: Any, request: Request, db: Session):
    """Common logic for handling OAuth callbacks."""
    try:
        oauth_handler = OAuthHandler(config)
        token_data = await oauth_handler.exchange_code_for_tokens(code)
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        token_type = token_data.get("token_type", "Bearer")
        scopes = token_data.get("scope", "").split(",") if isinstance(token_data.get("scope"), str) else []
        
        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
            
        current_user = get_current_user(request, db)
        
        # Upsert token
        existing_token = db.query(OAuthToken).filter(
            OAuthToken.user_id == current_user.id,
            OAuthToken.provider == provider
        ).first()
        
        if existing_token:
            existing_token.access_token = access_token
            if refresh_token:
                existing_token.refresh_token = refresh_token
            existing_token.scopes = scopes
            existing_token.expires_at = expires_at
            existing_token.last_used = datetime.utcnow()
            existing_token.status = "active"
        else:
            new_token = OAuthToken(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                provider=provider,
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                scopes=scopes,
                expires_at=expires_at,
                status="active"
            )
            db.add(new_token)
            
        db.commit()
        return token_data
        
    except Exception as e:
        logger.error(f"OAuth callback failed for {provider}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete {provider} OAuth flow")

# ============================================================================
# Generic OAuth Endpoints
# ============================================================================

@router.get("/{provider}/initiate")
async def oauth_initiate(provider: str):
    """Initiate OAuth flow for a specific provider."""
    configs = {
        "google": GOOGLE_OAUTH_CONFIG,
        "linkedin": LINKEDIN_OAUTH_CONFIG,
        "microsoft": MICROSOFT_OAUTH_CONFIG,
        "salesforce": SALESFORCE_OAUTH_CONFIG,
        "slack": SLACK_OAUTH_CONFIG,
        "github": GITHUB_OAUTH_CONFIG,
        "asana": ASANA_OAUTH_CONFIG,
        "notion": NOTION_OAUTH_CONFIG,
        "trello": TRELLO_OAUTH_CONFIG,
        "dropbox": DROPBOX_OAUTH_CONFIG,
    }
    
    if provider not in configs:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
        
    handler = OAuthHandler(configs[provider])
    auth_url = handler.get_authorization_url(state=f"{provider}_oauth")
    return RedirectResponse(url=auth_url)

@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Handle OAuth callback for all providers."""
    configs = {
        "google": GOOGLE_OAUTH_CONFIG,
        "linkedin": LINKEDIN_OAUTH_CONFIG,
        "microsoft": MICROSOFT_OAUTH_CONFIG,
        "salesforce": SALESFORCE_OAUTH_CONFIG,
        "slack": SLACK_OAUTH_CONFIG,
        "github": GITHUB_OAUTH_CONFIG,
        "asana": ASANA_OAUTH_CONFIG,
        "notion": NOTION_OAUTH_CONFIG,
        "trello": TRELLO_OAUTH_CONFIG,
        "dropbox": DROPBOX_OAUTH_CONFIG,
    }
    
    if provider not in configs:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
        
    await _handle_callback_logic(provider, code, configs[provider], request, db)
    
    # Redirect to frontend
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/oauth/success?provider={provider}")

# ============================================================================
# Management Endpoints
# ============================================================================

@router.get("/tokens")
async def list_oauth_tokens(
    request: Request,
    provider: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all connected OAuth integrations for the current user."""
    current_user = get_current_user(request, db)
    query = db.query(OAuthToken).filter(OAuthToken.user_id == current_user.id)
    
    if provider:
        query = query.filter(OAuthToken.provider == provider)
        
    tokens = query.all()
    return {
        "integrations": [
            {
                "provider": t.provider,
                "status": t.status,
                "expires_at": t.expires_at,
                "last_used": t.last_used
            } for t in tokens
        ]
    }

@router.delete("/tokens/{provider}")
async def revoke_oauth_token(
    provider: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Revoke an OAuth integration."""
    current_user = get_current_user(request, db)
    token = db.query(OAuthToken).filter(
        OAuthToken.user_id == current_user.id,
        OAuthToken.provider == provider
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail=f"No integration found for {provider}")
        
    token.status = "revoked"
    db.commit()
    return {"status": "success", "message": f"Revoked {provider} integration"}

@router.get("/config-status")
async def oauth_config_status():
    """Check configuration status of all OAuth providers."""
    configs = {
        "google": GOOGLE_OAUTH_CONFIG,
        "linkedin": LINKEDIN_OAUTH_CONFIG,
        "microsoft": MICROSOFT_OAUTH_CONFIG,
        "salesforce": SALESFORCE_OAUTH_CONFIG,
        "slack": SLACK_OAUTH_CONFIG,
        "github": GITHUB_OAUTH_CONFIG,
        "asana": ASANA_OAUTH_CONFIG,
        "notion": NOTION_OAUTH_CONFIG,
        "trello": TRELLO_OAUTH_CONFIG,
        "dropbox": DROPBOX_OAUTH_CONFIG,
    }
    
    return {
        provider: config.is_configured() for provider, config in configs.items()
    }
