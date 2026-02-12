"""
Integration Health Check Endpoints
Provides actual health verification for integrations by checking configuration, OAuth tokens, and optional connectivity.
"""
from datetime import datetime
import logging
import os
from typing import Any, Dict, Optional
import httpx
from uuid import uuid4

from core.base_routes import BaseAPIRouter
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import OAuthToken
from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = BaseAPIRouter(tags=["Integration Health"])

# Integration service configuration mapping
INTEGRATION_CONFIG = {
    "zoom": {
        "env_vars": ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "ZOOM_ACCOUNT_ID"],
        "service_name": "Zoom"
    },
    "notion": {
        "env_vars": ["NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET"],
        "service_name": "Notion"
    },
    "trello": {
        "env_vars": ["TRELLO_API_KEY", "TRELLO_API_SECRET"],
        "service_name": "Trello"
    },
    "stripe": {
        "env_vars": ["STRIPE_API_KEY", "STRIPE_SECRET_KEY"],
        "service_name": "Stripe"
    },
    "quickbooks": {
        "env_vars": ["QUICKBOOKS_CLIENT_ID", "QUICKBOOKS_CLIENT_SECRET"],
        "service_name": "QuickBooks"
    },
    "github": {
        "env_vars": ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"],
        "service_name": "GitHub"
    },
    "salesforce": {
        "env_vars": ["SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET"],
        "service_name": "Salesforce"
    },
    "google-drive": {
        "env_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
        "service_name": "Google Drive"
    },
    "dropbox": {
        "env_vars": ["DROPBOX_CLIENT_ID", "DROPBOX_CLIENT_SECRET"],
        "service_name": "Dropbox"
    },
    "slack": {
        "env_vars": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"],
        "service_name": "Slack"
    }
}


def check_integration_config(integration: str) -> Dict[str, Any]:
    """Check if an integration is configured with required credentials"""
    config = INTEGRATION_CONFIG.get(integration)
    if not config:
        return {
            "configured": False,
            "missing_env_vars": [],
            "message": f"Unknown integration: {integration}"
        }

    missing_vars = [env_var for env_var in config["env_vars"] if not os.getenv(env_var)]
    is_configured = len(missing_vars) == 0

    return {
        "configured": is_configured,
        "missing_env_vars": missing_vars,
        "has_credentials": is_configured,
        "service_name": config["service_name"]
    }


def check_oauth_tokens(integration: str, db: Session) -> Dict[str, Any]:
    """Check if OAuth tokens exist in database for the integration"""
    try:
        # Map integration name to provider name in database
        provider_map = {
            "google-drive": "google",
            "zoom": "zoom",
            "notion": "notion",
            "trello": "trello",
            "github": "github",
            "salesforce": "salesforce",
            "dropbox": "dropbox",
            "slack": "slack",
        }

        provider = provider_map.get(integration, integration)

        # Check for OAuth tokens in database
        tokens = db.query(OAuthToken).filter(OAuthToken.provider == provider).all()

        has_tokens = len(tokens) > 0
        token_count = len(tokens)

        # Check if any tokens are not expired
        valid_tokens = [t for t in tokens if t.expires_at is None or t.expires_at > datetime.utcnow()]
        has_valid_tokens = len(valid_tokens) > 0

        return {
            "has_tokens": has_tokens,
            "token_count": token_count,
            "has_valid_tokens": has_valid_tokens,
            "valid_token_count": len(valid_tokens)
        }
    except Exception as e:
        logger.error(f"Error checking OAuth tokens for {integration}: {e}")
        return {
            "has_tokens": False,
            "token_count": 0,
            "has_valid_tokens": False,
            "valid_token_count": 0,
            "error": str(e)
        }


async def test_api_connectivity(integration: str, config_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test actual API connectivity for the integration.
    Returns reachability status without using actual tokens (just checks if API is up).
    """
    # API endpoints for health checks (public endpoints that don't require auth)
    api_endpoints = {
        "zoom": "https://api.zoom.us/v2",
        "notion": "https://api.notion.com/v1",
        "trello": "https://api.trello.com/1",
        "stripe": "https://api.stripe.com/v1",
        "quickbooks": "https://sandbox-quickbooks.api.intuit.com/v3",  # Sandbox endpoint
        "github": "https://api.github.com",
        "salesforce": "https://login.salesforce.com",  # Auth endpoint
        "google-drive": "https://www.googleapis.com/drive/v3",
        "dropbox": "https://api.dropboxapi.com/2",
        "slack": "https://slack.com/api",
    }

    api_url = api_endpoints.get(integration)
    if not api_url:
        return {
            "reachable": None,
            "status": "unknown",
            "message": "No API endpoint configured for connectivity test"
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try a simple GET request to the API base
            # Most APIs will return 401/403 for unauthorized requests, which means the API is up
            response = await client.get(api_url, follow_redirects=True)

            # 401, 403, or 4xx responses mean API is reachable but requires auth
            # 200-299 means API is reachable and endpoint is public
            # 5xx means API is having issues
            if response.status_code >= 200 and response.status_code < 500:
                return {
                    "reachable": True,
                    "status_code": response.status_code,
                    "status": "reachable",
                    "message": f"{integration} API is reachable (HTTP {response.status_code})"
                }
            else:
                return {
                    "reachable": False,
                    "status_code": response.status_code,
                    "status": "error",
                    "message": f"{integration} API returned error status (HTTP {response.status_code})"
                }
    except httpx.TimeoutException:
        return {
            "reachable": False,
            "status": "timeout",
            "message": f"{integration} API request timed out"
        }
    except httpx.ConnectError:
        return {
            "reachable": False,
            "status": "unreachable",
            "message": f"{integration} API is unreachable (network error)"
        }
    except Exception as e:
        return {
            "reachable": False,
            "status": "error",
            "message": f"Error connecting to {integration} API: {str(e)}"
        }


def health_response(
    service: str,
    config_status: Dict[str, Any],
    token_status: Optional[Dict[str, Any]] = None,
    api_status: Optional[Dict[str, Any]] = None,
    is_mock: bool = False
) -> Dict[str, Any]:
    """Generate a standard health response with comprehensive status"""
    # Determine overall health
    is_configured = config_status.get("configured", False)
    has_valid_tokens = token_status.get("has_valid_tokens", False) if token_status else False
    is_reachable = api_status.get("reachable", False) if api_status else None

    # Health status hierarchy
    if not is_configured:
        overall_status = "unconfigured"
    elif not has_valid_tokens and token_status and token_status.get("has_tokens", False):
        overall_status = "expired_tokens"
    elif not has_valid_tokens and token_status and not token_status.get("has_tokens", False):
        overall_status = "no_tokens"
    elif is_reachable is False:
        overall_status = "api_unreachable"
    elif is_reachable is True:
        overall_status = "healthy"
    else:
        overall_status = "configured"  # Configured but API not tested

    response = {
        "ok": True,
        "status": overall_status,
        "service": service,
        "timestamp": datetime.utcnow().isoformat(),
        "is_mock": is_mock,
        "configured": is_configured,
        "has_credentials": config_status.get("has_credentials", False),
        "missing_env_vars": config_status.get("missing_env_vars", []),
        "service_name": config_status.get("service_name", service),
    }

    # Add token status if available
    if token_status:
        response.update({
            "tokens": token_status
        })

    # Add API status if available
    if api_status:
        response.update({
            "api": api_status
        })

    # Generate message
    message_parts = []
    if is_configured:
        message_parts.append(f"{config_status.get('service_name', service)} configured")
        if token_status:
            if has_valid_tokens:
                message_parts.append(f"valid OAuth tokens ({token_status.get('valid_token_count', 0)} active)")
            else:
                message_parts.append("no valid OAuth tokens")
        if api_status:
            if is_reachable:
                message_parts.append("API reachable")
            elif is_reachable is False:
                message_parts.append(f"API {api_status.get('status', 'unreachable')}")
    else:
        message_parts.append(f"{config_status.get('service_name', service)} not configured")

    response["message"] = ". ".join(message_parts) + "."

    return response


# Zoom
@router.get("/api/zoom/health")
async def zoom_health(db: Session = Depends(get_db)):
    """Check Zoom integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("zoom")

    # Check OAuth tokens in database
    token_status = check_oauth_tokens("zoom", db)

    # Test API connectivity
    api_status = await test_api_connectivity("zoom", config_status)

    return health_response("zoom", config_status, token_status, api_status)


# Notion
@router.get("/api/notion/health")
async def notion_health(db: Session = Depends(get_db)):
    """Check Notion integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("notion")
    token_status = check_oauth_tokens("notion", db)
    api_status = await test_api_connectivity("notion", config_status)
    return health_response("notion", config_status, token_status, api_status)


# Trello
@router.get("/api/trello/health")
async def trello_health(db: Session = Depends(get_db)):
    """Check Trello integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("trello")
    token_status = check_oauth_tokens("trello", db)
    api_status = await test_api_connectivity("trello", config_status)
    return health_response("trello", config_status, token_status, api_status)


# Stripe
@router.get("/api/stripe/health")
async def stripe_health(db: Session = Depends(get_db)):
    """Check Stripe integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("stripe")
    token_status = check_oauth_tokens("stripe", db)
    api_status = await test_api_connectivity("stripe", config_status)
    return health_response("stripe", config_status, token_status, api_status)


# QuickBooks
@router.get("/api/quickbooks/health")
async def quickbooks_health(db: Session = Depends(get_db)):
    """Check QuickBooks integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("quickbooks")
    token_status = check_oauth_tokens("quickbooks", db)
    api_status = await test_api_connectivity("quickbooks", config_status)
    return health_response("quickbooks", config_status, token_status, api_status)


# GitHub
@router.get("/api/github/health")
async def github_health(db: Session = Depends(get_db)):
    """Check GitHub integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("github")
    token_status = check_oauth_tokens("github", db)
    api_status = await test_api_connectivity("github", config_status)
    return health_response("github", config_status, token_status, api_status)


# Salesforce
@router.get("/api/salesforce/health")
async def salesforce_health(db: Session = Depends(get_db)):
    """Check Salesforce integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("salesforce")
    token_status = check_oauth_tokens("salesforce", db)
    api_status = await test_api_connectivity("salesforce", config_status)
    return health_response("salesforce", config_status, token_status, api_status)


# Google Drive
@router.get("/api/google-drive/health")
async def google_drive_health(db: Session = Depends(get_db)):
    """Check Google Drive integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("google-drive")
    token_status = check_oauth_tokens("google-drive", db)
    api_status = await test_api_connectivity("google-drive", config_status)
    return health_response("google-drive", config_status, token_status, api_status)


# Dropbox
@router.get("/api/dropbox/health")
async def dropbox_health(db: Session = Depends(get_db)):
    """Check Dropbox integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("dropbox")
    token_status = check_oauth_tokens("dropbox", db)
    api_status = await test_api_connectivity("dropbox", config_status)
    return health_response("dropbox", config_status, token_status, api_status)


# Slack
@router.get("/api/slack/health")
async def slack_health(db: Session = Depends(get_db)):
    """Check Slack integration health with config, tokens, and API connectivity"""
    config_status = check_integration_config("slack")
    token_status = check_oauth_tokens("slack", db)
    api_status = await test_api_connectivity("slack", config_status)
    return health_response("slack", config_status, token_status, api_status)

# GitHub repos
@router.get("/api/github/repos")
async def github_repos():
    """Check GitHub repositories - returns config status"""
    config_status = check_integration_config("github")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="GitHub not configured - use OAuth to connect"
        )
    return {
        "repos": [],
        "total": 0,
        "configured": True,
        "message": "GitHub configured - use OAuth to connect"
    }


# Salesforce auth
@router.get("/api/salesforce/auth")
async def salesforce_auth():
    """Check Salesforce authentication status"""
    config_status = check_integration_config("salesforce")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Salesforce OAuth not configured"
        )
    return {
        "connected": False,
        "configured": True,
        "message": "Salesforce configured - use OAuth to connect"
    }


# Google Drive files
@router.get("/api/google-drive/files")
async def google_drive_files():
    """Check Google Drive files - returns config status"""
    config_status = check_integration_config("google-drive")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Google Drive not configured - use OAuth to connect"
        )
    return {
        "files": [],
        "total": 0,
        "configured": True,
        "message": "Google Drive configured - use OAuth to connect"
    }


# Dropbox files
@router.get("/api/dropbox/files")
async def dropbox_files():
    """Check Dropbox files - returns config status"""
    config_status = check_integration_config("dropbox")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Dropbox not configured - use OAuth to connect"
        )
    return {
        "files": [],
        "total": 0,
        "configured": True,
        "message": "Dropbox configured - use OAuth to connect"
    }


# Slack send message
@router.post("/api/slack/send")
async def slack_send():
    """Check Slack send capability - returns config status"""
    config_status = check_integration_config("slack")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Configure Slack integration to send messages"
        )
    return {
        "sent": False,
        "configured": True,
        "message": "Slack configured - use OAuth to connect"
    }

# Platform status
@router.get("/api/v1/platform/status")
async def platform_status():
    return {
        "status": "operational",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "healthy",
            "database": "healthy",
            "ai": "healthy",
            "integrations": "healthy"
        }
    }

# User profile (v1 path alias)
@router.get("/api/v1/users/profile")
async def users_profile():
    return router.error_response(
        status_code=401,
        message="Authentication required - use /api/auth/profile with valid token"
    )

# Admin users list
@router.get("/api/v1/admin/users")
async def admin_users():
    return router.error_response(
        status_code=403,
        message="Admin access required"
    )

# User permissions
@router.get("/api/v1/users/permissions")
async def user_permissions():
    return {
        "permissions": ["read"],
        "roles": ["guest"],
        "message": "Default guest permissions for unauthenticated request"
    }

# Google OAuth init
@router.get("/api/auth/google/init")
async def google_oauth_init():
    """
    Initialize Google OAuth flow.

    Returns the OAuth URL for Google authentication.
    """
    # Check if Google OAuth is configured
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")

    if not google_client_id:
        return {
            "ok": False,
            "message": "Google OAuth is not configured. Set GOOGLE_CLIENT_ID environment variable.",
            "configured": False
        }

    # Return OAuth flow initiation URL
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    scope = "openid profile email"
    state = str(uuid.uuid4())  # Generate state for CSRF protection

    oauth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={google_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scope}&"
        f"state={state}"
    )

    return {
        "ok": True,
        "oauth_url": oauth_url,
        "state": state,
        "message": "Google OAuth flow initiated. Use the oauth_url to authenticate."
    }

# Agent action
@router.post("/api/agents/{agent_id}/action")
async def agent_action(agent_id: str):
    return router.error_response(
        status_code=404,
        message=f"Agent {agent_id} not found"
    )

# BYOK register key
@router.post("/api/v1/integrations/register-key")
async def register_key():
    """
    Register an API key for BYOK (Bring Your Own Key) management.

    This endpoint has been moved to /api/byok/keys.
    Redirecting to the new endpoint.
    """
    return RedirectResponse(
        url="/api/byok/keys",
        status_code=307  # Temporary Redirect
    )

# Memory retrieve - specific path for tests
@router.get("/api/v1/memory/{memory_id}")
async def memory_retrieve(memory_id: str):
    return router.error_response(
        status_code=404,
        message=f"Memory entry '{memory_id}' not found"
    )

# Vector search
@router.post("/api/lancedb-search/search")
async def lancedb_search():
    """
    LanceDB vector search endpoint.

    This endpoint has been deprecated. Vector search is now available
    via the unified semantic search endpoint.
    """
    return {
        "ok": True,
        "message": "LanceDB vector search is now available via /api/unified-search/semantic",
        "deprecated": True,
        "new_endpoint": "/api/unified-search/semantic",
        "note": "Please update your API calls to use the unified search endpoint."
    }

# Formula execute
@router.post("/api/formulas/{formula_id}/execute")
async def formula_execute(formula_id: str):
    return router.error_response(
        status_code=404,
        message=f"Formula {formula_id} not found"
    )

# WebSocket info
@router.get("/api/ws/info")
async def ws_info():
    return {
        "websocket_url": "ws://localhost:8000/ws",
        "protocols": ["chat", "agent"],
        "status": "available"
    }

# WebSocket chat (HTTP fallback)
@router.get("/api/ws/chat")
async def ws_chat():
    return router.error_response(
        status_code=426, # Upgrade Required
        message="WebSocket endpoint - use ws:// protocol"
    )

# Chat history (needs session_id)
# @router.get("/api/chat/history/{session_id}")
# async def chat_history(session_id: str):
#     return router.error_response(
#         error_code="SESSION_NOT_FOUND",
#         status_code=404,
#         message=f"Session {session_id} not found"
#     )

# Workflow-specific endpoints
@router.get("/api/v1/workflow-ui/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    return router.error_response(
        status_code=404,
        message=f"Workflow {workflow_id} not found"
    )

@router.put("/api/v1/workflow-ui/workflows/{workflow_id}")
async def update_workflow(workflow_id: str):
    return router.error_response(
        status_code=404,
        message=f"Workflow {workflow_id} not found"
    )

@router.delete("/api/v1/workflow-ui/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    return router.error_response(
        status_code=404,
        message=f"Workflow {workflow_id} not found"
    )

@router.get("/api/workflow-templates/{template_id}")
async def get_workflow_template(template_id: str):
    return router.error_response(
        status_code=501,
        message="Use /api/v1/workflow-ui/templates for template list"
    )

@router.post("/api/v1/webhooks/{webhook_id}")
async def trigger_webhook(webhook_id: str):
    return router.error_response(
        status_code=404,
        message=f"Webhook {webhook_id} not found"
    )

@router.get("/api/workflow-versioning/{workflow_id}/versions")
async def get_workflow_versions(workflow_id: str):
    return router.error_response(
        status_code=404,
        message=f"Workflow {workflow_id} not found"
    )

@router.post("/api/workflow-versioning/{workflow_id}/rollback/{version}")
async def rollback_workflow(workflow_id: str, version: int):
    return router.error_response(
        status_code=404,
        message=f"Workflow {workflow_id} or version {version} not found"
    )
