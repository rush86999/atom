"""
OAuth Authentication Routes
Provides OAuth 2.0 authentication endpoints for all integrations
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from core.oauth_handler import (
    OAuthHandler,
    GOOGLE_OAUTH_CONFIG,
    MICROSOFT_OAUTH_CONFIG,
    SALESFORCE_OAUTH_CONFIG,
    SLACK_OAUTH_CONFIG,
    GITHUB_OAUTH_CONFIG,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["oauth"])


# Google OAuth Routes
@router.get("/google/initiate")
async def google_oauth_initiate():
    """Initiate Google OAuth flow"""
    try:
        handler = OAuthHandler(GOOGLE_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="google_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Google OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google/callback")
async def google_oauth_callback(request: Request):
    """Handle Google OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(GOOGLE_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)
        
        # TODO: Store tokens securely in database
        # For now, log success and return tokens (or success status)
        logger.info("Google OAuth successful - tokens received")
        logger.debug(f"Access token: {tokens.get('access_token', '')[:20]}...")
        
        return {"status": "success", "provider": "google", "tokens": tokens}
    
    except HTTPException as e:
        logger.error(f"Google OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Microsoft OAuth Routes
@router.get("/microsoft/initiate")
async def microsoft_oauth_initiate():
    """Initiate Microsoft OAuth flow"""
    try:
        handler = OAuthHandler(MICROSOFT_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="microsoft_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Microsoft OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/microsoft/callback")
async def microsoft_oauth_callback(request: Request):
    """Handle Microsoft OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(MICROSOFT_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)
        
        logger.info("Microsoft OAuth successful - tokens received")
        return {"status": "success", "provider": "microsoft", "tokens": tokens}
    
    except HTTPException as e:
        logger.error(f"Microsoft OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Microsoft OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Salesforce OAuth Routes
@router.get("/salesforce/initiate")
async def salesforce_oauth_initiate():
    """Initiate Salesforce OAuth flow"""
    try:
        handler = OAuthHandler(SALESFORCE_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="salesforce_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Salesforce OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/salesforce/callback")
async def salesforce_oauth_callback(request: Request):
    """Handle Salesforce OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(SALESFORCE_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)
        
        logger.info("Salesforce OAuth successful - tokens received")
        return {"status": "success", "provider": "salesforce", "tokens": tokens}
    
    except HTTPException as e:
        logger.error(f"Salesforce OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Salesforce OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Slack OAuth Routes
@router.get("/slack/initiate")
async def slack_oauth_initiate():
    """Initiate Slack OAuth flow"""
    try:
        handler = OAuthHandler(SLACK_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="slack_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Slack OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slack/callback")
async def slack_oauth_callback(request: Request):
    """Handle Slack OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(SLACK_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)
        
        logger.info("Slack OAuth successful - tokens received")
        return {"status": "success", "provider": "slack", "tokens": tokens}
    
    except HTTPException as e:
        logger.error(f"Slack OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Slack OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# GitHub OAuth Routes
@router.get("/github/initiate")
async def github_oauth_initiate():
    """Initiate GitHub OAuth flow"""
    try:
        handler = OAuthHandler(GITHUB_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="github_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"GitHub OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/github/callback")
async def github_oauth_callback(request: Request):
    """Handle GitHub OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(GITHUB_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)
        
        logger.info("GitHub OAuth successful - tokens received")
        return {"status": "success", "provider": "github", "tokens": tokens}
    
    except HTTPException as e:
        logger.error(f"GitHub OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@router.get("/health")
async def oauth_health():
    """Check OAuth configuration status"""
    from core.oauth_handler import (
        GOOGLE_OAUTH_CONFIG,
        MICROSOFT_OAUTH_CONFIG,
        SALESFORCE_OAUTH_CONFIG,
        SLACK_OAUTH_CONFIG,
        GITHUB_OAUTH_CONFIG,
    )
    
    return {
        "oauth_configured": {
            "google": GOOGLE_OAUTH_CONFIG.is_configured(),
            "microsoft": MICROSOFT_OAUTH_CONFIG.is_configured(),
            "salesforce": SALESFORCE_OAUTH_CONFIG.is_configured(),
            "slack": SLACK_OAUTH_CONFIG.is_configured(),
            "github": GITHUB_OAUTH_CONFIG.is_configured(),
        }
    }
