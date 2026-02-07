"""
OAuth Authentication Routes
Provides OAuth 2.0 authentication endpoints for all integrations
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

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
from core.token_storage import token_storage

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


@router.get("/google/callback")
async def google_oauth_callback_get(code: str = Query(...), state: str = Query(None)):
    """Handle Google OAuth callback (GET from OAuth provider)"""
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(GOOGLE_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)
        
        # Store tokens securely
        token_storage.save_token("google", tokens)
        
        logger.info("Google OAuth successful - tokens received and stored")
        logger.debug(f"Access token: {tokens.get('access_token', '')[:20]}...")
        
        # Redirect to frontend success page
        return RedirectResponse(url="http://localhost:3000/oauth/success?provider=google")
    
    except HTTPException as e:
        logger.error(f"Google OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={e.detail}")
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={str(e)}")


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
        
        # Store tokens securely
        token_storage.save_token("google", tokens)
        
        logger.info("Google OAuth successful - tokens received and stored")
        logger.debug(f"Access token: {tokens.get('access_token', '')[:20]}...")
        
        return {"status": "success", "provider": "google", "tokens": tokens}
    
    except HTTPException as e:
        logger.error(f"Google OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Legacy OAuth callback endpoints for compatibility
@router.get("/callback/google")
async def google_callback_legacy():
    """Legacy endpoint for Google OAuth callback"""
    return {"status": "redirect", "message": "Use /api/auth/google/callback"}

# LinkedIn OAuth Routes
@router.get("/linkedin/initiate")
async def linkedin_oauth_initiate():
    """Initiate LinkedIn OAuth flow"""
    try:
        handler = OAuthHandler(LINKEDIN_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="linkedin_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"LinkedIn OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/linkedin/callback")
async def linkedin_oauth_callback_get(code: str = Query(...), state: str = Query(None)):
    """Handle LinkedIn OAuth callback (GET from OAuth provider)"""
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(LINKEDIN_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("linkedin", tokens)

        logger.info("LinkedIn OAuth successful - tokens received and stored")
        logger.debug(f"Access token: {tokens.get('access_token', '')[:20]}...")

        # Redirect to frontend success page
        return RedirectResponse(url="http://localhost:3000/oauth/success?provider=linkedin")

    except HTTPException as e:
        logger.error(f"LinkedIn OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={e.detail}")
    except Exception as e:
        logger.error(f"LinkedIn OAuth callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={str(e)}")


@router.post("/linkedin/callback")
async def linkedin_oauth_callback(request: Request):
    """Handle LinkedIn OAuth callback (POST)"""
    try:
        data = await request.json()
        code = data.get("code")

        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(LINKEDIN_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("linkedin", tokens)

        logger.info("LinkedIn OAuth successful - tokens received and stored")
        return {"status": "success", "provider": "linkedin", "tokens": tokens}

    except HTTPException as e:
        logger.error(f"LinkedIn OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"LinkedIn OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Legacy OAuth callback endpoints for compatibility
@router.get("/callback/google")
async def google_callback_legacy():
    """Legacy endpoint for Google OAuth callback"""
    return {"status": "redirect", "message": "Use /api/auth/google/callback"}

@router.get("/callback/linkedin")
async def linkedin_callback_legacy():
    """Legacy endpoint for LinkedIn OAuth callback"""
    return {"status": "redirect", "message": "Use /api/auth/linkedin/callback"}

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
        
        # Store tokens securely
        token_storage.save_token("microsoft", tokens)
        
        logger.info("Microsoft OAuth successful - tokens received and stored")
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
        
        # Store tokens securely
        token_storage.save_token("salesforce", tokens)
        
        logger.info("Salesforce OAuth successful - tokens received and stored")
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
        
        # Store tokens securely
        token_storage.save_token("slack", tokens)
        
        logger.info("Slack OAuth successful - tokens received and stored")
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

        # Store tokens securely
        token_storage.save_token("github", tokens)

        logger.info("GitHub OAuth successful - tokens received and stored")
        return {"status": "success", "provider": "github", "tokens": tokens}

    except HTTPException as e:
        logger.error(f"GitHub OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/callback")
async def github_oauth_callback_get(code: str = Query(...), state: str = Query(None)):
    """Handle GitHub OAuth callback (GET from OAuth provider)"""
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(GITHUB_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("github", tokens)

        logger.info("GitHub OAuth successful - tokens received and stored")

        # Redirect to frontend success page
        return RedirectResponse(url="http://localhost:3000/oauth/success?provider=github")

    except HTTPException as e:
        logger.error(f"GitHub OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={e.detail}")
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={str(e)}")


# Asana OAuth Routes
@router.get("/asana/initiate")
async def asana_oauth_initiate():
    """Initiate Asana OAuth flow"""
    try:
        handler = OAuthHandler(ASANA_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="asana_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Asana OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/asana/callback")
async def asana_oauth_callback(request: Request):
    """Handle Asana OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")

        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(ASANA_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("asana", tokens)

        logger.info("Asana OAuth successful - tokens received and stored")
        return {"status": "success", "provider": "asana", "tokens": tokens}

    except HTTPException as e:
        logger.error(f"Asana OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Asana OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/asana/callback")
async def asana_oauth_callback_get(code: str = Query(...), state: str = Query(None)):
    """Handle Asana OAuth callback (GET from OAuth provider)"""
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(ASANA_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("asana", tokens)

        logger.info("Asana OAuth successful - tokens received and stored")

        # Redirect to frontend success page
        return RedirectResponse(url="http://localhost:3000/oauth/success?provider=asana")

    except HTTPException as e:
        logger.error(f"Asana OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={e.detail}")
    except Exception as e:
        logger.error(f"Asana OAuth callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={str(e)}")


# Notion OAuth Routes
@router.get("/notion/initiate")
async def notion_oauth_initiate():
    """Initiate Notion OAuth flow"""
    try:
        handler = OAuthHandler(NOTION_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="notion_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Notion OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notion/callback")
async def notion_oauth_callback(request: Request):
    """Handle Notion OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")

        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(NOTION_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("notion", tokens)

        logger.info("Notion OAuth successful - tokens received and stored")
        return {"status": "success", "provider": "notion", "tokens": tokens}

    except HTTPException as e:
        logger.error(f"Notion OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Notion OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/callback")
async def notion_oauth_callback_get(code: str = Query(...), state: str = Query(None)):
    """Handle Notion OAuth callback (GET from OAuth provider)"""
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(NOTION_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("notion", tokens)

        logger.info("Notion OAuth successful - tokens received and stored")

        # Redirect to frontend success page
        return RedirectResponse(url="http://localhost:3000/oauth/success?provider=notion")

    except HTTPException as e:
        logger.error(f"Notion OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={e.detail}")
    except Exception as e:
        logger.error(f"Notion OAuth callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={str(e)}")


# Trello OAuth Routes
@router.get("/trello/initiate")
async def trello_oauth_initiate():
    """Initiate Trello OAuth flow"""
    try:
        handler = OAuthHandler(TRELLO_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="trello_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Trello OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trello/callback")
async def trello_oauth_callback(request: Request):
    """Handle Trello OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")

        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(TRELLO_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("trello", tokens)

        logger.info("Trello OAuth successful - tokens received and stored")
        return {"status": "success", "provider": "trello", "tokens": tokens}

    except HTTPException as e:
        logger.error(f"Trello OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Trello OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trello/callback")
async def trello_oauth_callback_get(code: str = Query(...), state: str = Query(None)):
    """Handle Trello OAuth callback (GET from OAuth provider)"""
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(TRELLO_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("trello", tokens)

        logger.info("Trello OAuth successful - tokens received and stored")

        # Redirect to frontend success page
        return RedirectResponse(url="http://localhost:3000/oauth/success?provider=trello")

    except HTTPException as e:
        logger.error(f"Trello OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={e.detail}")
    except Exception as e:
        logger.error(f"Trello OAuth callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={str(e)}")


# Dropbox OAuth Routes
@router.get("/dropbox/initiate")
async def dropbox_oauth_initiate():
    """Initiate Dropbox OAuth flow"""
    try:
        handler = OAuthHandler(DROPBOX_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state="dropbox_oauth")
        return RedirectResponse(url=auth_url)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Dropbox OAuth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dropbox/callback")
async def dropbox_oauth_callback(request: Request):
    """Handle Dropbox OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")

        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(DROPBOX_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("dropbox", tokens)

        logger.info("Dropbox OAuth successful - tokens received and stored")
        return {"status": "success", "provider": "dropbox", "tokens": tokens}

    except HTTPException as e:
        logger.error(f"Dropbox OAuth callback failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Dropbox OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dropbox/callback")
async def dropbox_oauth_callback_get(code: str = Query(...), state: str = Query(None)):
    """Handle Dropbox OAuth callback (GET from OAuth provider)"""
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(DROPBOX_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens securely
        token_storage.save_token("dropbox", tokens)

        logger.info("Dropbox OAuth successful - tokens received and stored")

        # Redirect to frontend success page
        return RedirectResponse(url="http://localhost:3000/oauth/success?provider=dropbox")

    except HTTPException as e:
        logger.error(f"Dropbox OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={e.detail}")
    except Exception as e:
        logger.error(f"Dropbox OAuth callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/oauth/error?error={str(e)}")


@router.post("/{provider}/refresh")
async def refresh_provider_token(provider: str):
    """Refresh tokens for a specific provider"""
    try:
        stored_token = token_storage.get_token(provider)
        if not stored_token or not stored_token.get("refresh_token"):
            raise HTTPException(status_code=404, detail=f"No refresh token found for {provider}")

        # Get the appropriate config
        configs = {
            "google": GOOGLE_OAUTH_CONFIG,
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
        new_tokens = await handler.refresh_access_token(stored_token["refresh_token"])

        # Merge with old tokens to preserve refresh_token if not returned
        for key, value in stored_token.items():
            if key not in new_tokens:
                new_tokens[key] = value

        token_storage.save_token(provider, new_tokens)

        return {"status": "success", "message": f"Token refreshed for {provider}"}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Token refresh error for {provider}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@router.get("/health")
async def oauth_health():
    """Check OAuth configuration status"""
    from core.oauth_handler import (
        ASANA_OAUTH_CONFIG,
        DROPBOX_OAUTH_CONFIG,
        GITHUB_OAUTH_CONFIG,
        GOOGLE_OAUTH_CONFIG,
        MICROSOFT_OAUTH_CONFIG,
        NOTION_OAUTH_CONFIG,
        SALESFORCE_OAUTH_CONFIG,
        SLACK_OAUTH_CONFIG,
        TRELLO_OAUTH_CONFIG,
    )

    return {
        "oauth_configured": {
            "google": GOOGLE_OAUTH_CONFIG.is_configured(),
            "microsoft": MICROSOFT_OAUTH_CONFIG.is_configured(),
            "salesforce": SALESFORCE_OAUTH_CONFIG.is_configured(),
            "slack": SLACK_OAUTH_CONFIG.is_configured(),
            "github": GITHUB_OAUTH_CONFIG.is_configured(),
            "asana": ASANA_OAUTH_CONFIG.is_configured(),
            "notion": NOTION_OAUTH_CONFIG.is_configured(),
            "trello": TRELLO_OAUTH_CONFIG.is_configured(),
            "dropbox": DROPBOX_OAUTH_CONFIG.is_configured(),
        }
    }
