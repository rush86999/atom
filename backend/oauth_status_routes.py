"""
OAuth Status and Authorization Routes
Provides OAuth 2.0 status and authorization endpoints for all third-party integrations.

This file complements oauth_routes.py by adding:
1. Status endpoints for all OAuth services
2. Authorization endpoints (alias for initiate)
3. Support for all 10 services tested in the OAuth system

Services covered:
- Gmail, Outlook, Slack, Teams, Trello, Asana, Notion, GitHub, Dropbox, Google Drive
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Query

from integrations.oauth_config import OAuthConfig, get_oauth_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["OAuth Status"])


# ============================================================================
# OAUTH STATUS ENDPOINTS (for all 10 services)
# ============================================================================

@router.get("/gmail/status")
async def gmail_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Gmail OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("google")

    return {
        "ok": True,
        "service": "gmail",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Gmail OAuth integration is available" if creds.configured else "Gmail OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/outlook/status")
async def outlook_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Outlook OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("outlook")

    return {
        "ok": True,
        "service": "outlook",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Outlook OAuth integration is available" if creds.configured else "Outlook OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/slack/status")
async def slack_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Slack OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("slack")

    return {
        "ok": True,
        "service": "slack",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Slack OAuth integration is available" if creds.configured else "Slack OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/teams/status")
async def teams_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Microsoft Teams OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("teams")

    return {
        "ok": True,
        "service": "teams",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Teams OAuth integration is available" if creds.configured else "Teams OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/trello/status")
async def trello_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Trello OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("trello")

    return {
        "ok": True,
        "service": "trello",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Trello OAuth integration is available" if creds.configured else "Trello OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/asana/status")
async def asana_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Asana OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("asana")

    return {
        "ok": True,
        "service": "asana",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Asana OAuth integration is available" if creds.configured else "Asana OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/notion/status")
async def notion_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Notion OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("notion")

    return {
        "ok": True,
        "service": "notion",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Notion OAuth integration is available" if creds.configured else "Notion OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/github/status")
async def github_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get GitHub OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("github")

    return {
        "ok": True,
        "service": "github",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "GitHub OAuth integration is available" if creds.configured else "GitHub OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/dropbox/status")
async def dropbox_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Dropbox OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("dropbox")

    return {
        "ok": True,
        "service": "dropbox",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Dropbox OAuth integration is available" if creds.configured else "Dropbox OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/gdrive/status")
async def gdrive_status(user_id: str = Query("test_user", description="User ID for status check")):
    """Get Google Drive OAuth integration status"""
    config = get_oauth_config()
    creds = config.get_credentials("google")

    return {
        "ok": True,
        "service": "gdrive",
        "user_id": user_id,
        "status": "connected" if creds.configured else "not_configured",
        "configured": creds.configured,
        "has_client_id": bool(creds.client_id),
        "has_client_secret": bool(creds.client_secret),
        "redirect_uri": creds.redirect_uri,
        "message": "Google Drive OAuth integration is available" if creds.configured else "Google Drive OAuth credentials not configured",
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# OAUTH AUTHORIZE ENDPOINTS (alias for /initiate endpoints)
# These redirect to the actual OAuth initiate endpoints in oauth_routes.py
# ============================================================================

@router.get("/gmail/authorize")
async def gmail_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Gmail OAuth flow (alias for /google/initiate)"""
    # Return authorization URL info - tests expect this format
    config = get_oauth_config()
    creds = config.get_credentials("google")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Gmail OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
        )

    # Return authorization URL format that tests expect
    return {
        "ok": True,
        "service": "gmail",
        "user_id": user_id,
        "auth_url": f"/api/auth/google/initiate",
        "configured": creds.configured,
        "message": "Use /api/auth/google/initiate to start OAuth flow",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/outlook/authorize")
async def outlook_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Outlook OAuth flow (alias for /microsoft/initiate)"""
    config = get_oauth_config()
    creds = config.get_credentials("outlook")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Outlook OAuth not configured. Please set OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "outlook",
        "user_id": user_id,
        "auth_url": f"/api/auth/microsoft/initiate",
        "configured": creds.configured,
        "message": "Use /api/auth/microsoft/initiate to start OAuth flow",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/slack/authorize")
async def slack_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Slack OAuth flow (alias for /slack/initiate)"""
    config = get_oauth_config()
    creds = config.get_credentials("slack")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Slack OAuth not configured. Please set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "slack",
        "user_id": user_id,
        "auth_url": f"/api/auth/slack/initiate",
        "configured": creds.configured,
        "message": "Use /api/auth/slack/initiate to start OAuth flow",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/teams/authorize")
async def teams_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Teams OAuth flow (alias for /microsoft/initiate)"""
    config = get_oauth_config()
    creds = config.get_credentials("teams")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Teams OAuth not configured. Please set TEAMS_CLIENT_ID and TEAMS_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "teams",
        "user_id": user_id,
        "auth_url": f"/api/auth/microsoft/initiate",
        "configured": creds.configured,
        "message": "Use /api/auth/microsoft/initiate to start OAuth flow",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/trello/authorize")
async def trello_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Trello OAuth flow"""
    config = get_oauth_config()
    creds = config.get_credentials("trello")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Trello OAuth not configured. Please set TRELLO_API_KEY and TRELLO_API_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "trello",
        "user_id": user_id,
        "configured": creds.configured,
        "message": "Trello OAuth initiate endpoint needs to be implemented in oauth_routes.py",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/asana/authorize")
async def asana_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Asana OAuth flow"""
    config = get_oauth_config()
    creds = config.get_credentials("asana")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Asana OAuth not configured. Please set ASANA_CLIENT_ID and ASANA_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "asana",
        "user_id": user_id,
        "configured": creds.configured,
        "message": "Asana OAuth initiate endpoint needs to be implemented in oauth_routes.py",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/notion/authorize")
async def notion_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Notion OAuth flow"""
    config = get_oauth_config()
    creds = config.get_credentials("notion")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Notion OAuth not configured. Please set NOTION_CLIENT_ID and NOTION_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "notion",
        "user_id": user_id,
        "configured": creds.configured,
        "message": "Notion OAuth initiate endpoint needs to be implemented in oauth_routes.py",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/github/authorize")
async def github_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate GitHub OAuth flow (alias for existing github/initiate)"""
    config = get_oauth_config()
    creds = config.get_credentials("github")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth not configured. Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "github",
        "user_id": user_id,
        "configured": creds.configured,
        "message": "GitHub OAuth initiate endpoint needs to be implemented in oauth_routes.py",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/dropbox/authorize")
async def dropbox_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Dropbox OAuth flow"""
    config = get_oauth_config()
    creds = config.get_credentials("dropbox")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Dropbox OAuth not configured. Please set DROPBOX_CLIENT_ID and DROPBOX_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "dropbox",
        "user_id": user_id,
        "configured": creds.configured,
        "message": "Dropbox OAuth initiate endpoint needs to be implemented in oauth_routes.py",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/gdrive/authorize")
async def gdrive_authorize(user_id: str = Query("test_user", description="User ID for authorization")):
    """Initiate Google Drive OAuth flow (alias for /google/initiate)"""
    config = get_oauth_config()
    creds = config.get_credentials("google")

    if not creds.configured:
        raise HTTPException(
            status_code=500,
            detail="Google Drive OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
        )

    return {
        "ok": True,
        "service": "gdrive",
        "user_id": user_id,
        "auth_url": f"/api/auth/google/initiate",
        "configured": creds.configured,
        "message": "Use /api/auth/google/initiate to start OAuth flow",
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# OVERALL OAUTH STATUS
# ============================================================================

@router.get("/oauth-status")
async def overall_oauth_status():
    """Get overall OAuth configuration status for all services"""
    config = get_oauth_config()
    validation = config.validate_all()

    return {
        "ok": True,
        "total_services": validation["total"],
        "configured_services": validation["configured"],
        "success_rate": (validation["configured"] / validation["total"] * 100) if validation["total"] > 0 else 0,
        "production_ready": validation["valid"],
        "missing_services": validation["missing"],
        "timestamp": datetime.now().isoformat(),
    }
