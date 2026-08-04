"""
OAuth Integration Routes

Provides unified OAuth callback endpoints for all third-party integrations.
Handles OAuth flows for Google, LinkedIn, Microsoft, Salesforce, Slack, GitHub, Asana, Notion, Trello, and Dropbox.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import OAuthToken, User
from core.security.auth_rate_limit import AuthRateLimiter
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
    WHATSAPP_OAUTH_CONFIG,
    OAuthHandler,
)

router = BaseAPIRouter(prefix="/api/v1/auth/oauth", tags=["OAuth"])
logger = logging.getLogger(__name__)

# Rate limit OAuth callbacks to prevent code brute-force / DoS
_oauth_limiter = AuthRateLimiter(limit=20, window_seconds=60)

def oauth_rate_limit(request: Request) -> None:
    """Rate limit OAuth callback attempts (20/min per IP)."""
    client_ip = request.client.host if request.client else "unknown"
    allowed, reason = _oauth_limiter.check(client_ip)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many OAuth attempts. Try again later.")

# ============================================================================
# Helpers
# ============================================================================

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Get current user from JWT Bearer token.

    SECURITY: Previously this function trusted a client-supplied ``X-User-ID``
    header with no verification, allowing any caller to impersonate any user
    by simply setting that header. This is a CVE-class authentication bypass.

    Now delegates to the unified ``core.auth.get_current_user`` which verifies
    a JWT (Bearer header or NextAuth cookie) and resolves the user from the DB.
    """
    from core.auth import get_current_user as _core_get_current_user

    return await _core_get_current_user(request=request, token=None, db=db)

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
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            
        # Bug 1+2 fix: the old code (a) called get_current_user without await,
        # binding a coroutine instead of a User, and (b) set non-existent
        # columns on OAuthToken (provider, access_token, refresh_token, scopes,
        # expires_at, status). The model has access_token_hash, refresh_token_hash,
        # scope (singular), client_id, tenant_id, is_active.
        # Now: await the call, hash the tokens, use the correct columns.
        import hashlib
        current_user = await get_current_user(request, db)

        _access_hash = hashlib.sha256(access_token.encode()).hexdigest()
        _refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest() if refresh_token else None

        existing_token = db.query(OAuthToken).filter(
            OAuthToken.user_id == current_user.id,
            OAuthToken.client_id == f"{provider}_client"
        ).first()

        if existing_token:
            existing_token.access_token_hash = _access_hash
            if _refresh_hash:
                existing_token.refresh_token_hash = _refresh_hash
            existing_token.scope = " ".join(scopes) if scopes else ""
            existing_token.access_token_expires_at = expires_at
            existing_token.is_active = True
        else:
            new_token = OAuthToken(
                id=str(uuid.uuid4()),
                client_id=f"{provider}_client",
                tenant_id=current_user.tenant_id or "default",
                user_id=current_user.id,
                access_token_hash=_access_hash,
                refresh_token_hash=_refresh_hash,
                scope=" ".join(scopes) if scopes else "",
                access_token_expires_at=expires_at,
                is_active=True
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
async def oauth_initiate(
    provider: str,
    current_user: User = Depends(get_current_user),
):
    """Initiate OAuth flow for a specific provider.

    B14: requires auth, mirroring the rest of this router (callback / tokens /
    config-status all depend on get_current_user) and the B7 fix on the alias
    router. Without it the canonical v1 /initiate URL was reachable
    unauthenticated, making the alias-router auth gate trivially bypassable."""
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
        "whatsapp": WHATSAPP_OAUTH_CONFIG,
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl: None = Depends(oauth_rate_limit),
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
        "whatsapp": WHATSAPP_OAUTH_CONFIG,
    }
    
    if provider not in configs:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # Bug 3 fix: validate the state parameter against what we sent at initiation.
    # The old code sent state=f"{provider}_oauth" but never checked it on
    # callback — classic OAuth CSRF (attacker forges a callback to bind a
    # victim's token to the attacker's account).
    if not state or state != f"{provider}_oauth":
        raise HTTPException(status_code=400, detail="Invalid or missing OAuth state parameter")

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all connected OAuth integrations for the current user.

    B15: OAuthToken has no provider/status/expires_at/last_used columns. The
    integration name is stored on client_id as ``{provider}_client`` (see
    _handle_callback_logic); liveness is is_active; expiry is
    access_token_expires_at; last-use is last_used_at."""
    current_user = await get_current_user(request, db)
    query = db.query(OAuthToken).filter(OAuthToken.user_id == current_user.id)

    if provider:
        query = query.filter(OAuthToken.client_id == f"{provider}_client")

    tokens = query.all()
    return {
        "integrations": [
            {
                # client_id is stored as "{provider}_client" at callback time.
                "provider": t.client_id[:-len("_client")] if t.client_id and t.client_id.endswith("_client") else t.client_id,
                "status": "active" if t.is_active else "revoked",
                "expires_at": t.access_token_expires_at.isoformat() if t.access_token_expires_at else None,
                "last_used": t.last_used_at.isoformat() if t.last_used_at else None,
            } for t in tokens
        ]
    }

@router.delete("/tokens/{provider}")
async def revoke_oauth_token(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke an OAuth integration.

    B15: OAuthToken has no provider/status columns. Filter on client_id
    (stored as ``{provider}_client``); revocation sets is_active=False."""
    current_user = await get_current_user(request, db)
    token = db.query(OAuthToken).filter(
        OAuthToken.user_id == current_user.id,
        OAuthToken.client_id == f"{provider}_client"
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail=f"No integration found for {provider}")

    token.is_active = False
    db.commit()
    return {"status": "success", "message": f"Revoked {provider} integration"}

@router.get("/config-status")
async def oauth_config_status(current_user: User = Depends(get_current_user)):
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
        "whatsapp": WHATSAPP_OAUTH_CONFIG,
    }
    
    return {
        provider: config.is_configured() for provider, config in configs.items()
    }
