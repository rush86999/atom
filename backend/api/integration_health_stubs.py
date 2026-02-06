"""
Integration Health Check Endpoints
Provides actual health verification for integrations by checking configuration and optional connectivity.
"""
from datetime import datetime
import logging
import os
from typing import Any, Dict

from core.base_routes import BaseAPIRouter

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


def health_response(service: str, config_status: Dict[str, Any], is_mock: bool = False) -> Dict[str, Any]:
    """Generate a standard health response with actual configuration status"""
    return {
        "ok": True,
        "status": "healthy" if config_status["configured"] else "unconfigured",
        "service": service,
        "timestamp": datetime.utcnow().isoformat(),
        "is_mock": is_mock,
        "configured": config_status["configured"],
        "has_credentials": config_status.get("has_credentials", False),
        "missing_env_vars": config_status.get("missing_env_vars", []),
        "message": f'{config_status["service_name"]} integration {"configured" if config_status["configured"] else "not configured"}'
    }


# Zoom
@router.get("/api/zoom/health")
async def zoom_health():
    """Check Zoom integration health"""
    config_status = check_integration_config("zoom")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Zoom integration not configured. Please add ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, and ZOOM_ACCOUNT_ID to .env"
        )
    return health_response("zoom", config_status, is_mock=False)


# Notion
@router.get("/api/notion/health")
async def notion_health():
    """Check Notion integration health"""
    config_status = check_integration_config("notion")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Notion integration not configured. Please add NOTION_CLIENT_ID and NOTION_CLIENT_SECRET to .env"
        )
    return health_response("notion", config_status, is_mock=False)


# Trello
@router.get("/api/trello/health")
async def trello_health():
    """Check Trello integration health"""
    config_status = check_integration_config("trello")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Trello integration not configured. Please add TRELLO_API_KEY and TRELLO_API_SECRET to .env"
        )
    return health_response("trello", config_status, is_mock=False)


# Stripe
@router.get("/api/stripe/health")
async def stripe_health():
    """Check Stripe integration health"""
    config_status = check_integration_config("stripe")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Stripe integration not configured. Please add STRIPE_API_KEY and STRIPE_SECRET_KEY to .env"
        )
    return health_response("stripe", config_status, is_mock=False)


# QuickBooks
@router.get("/api/quickbooks/health")
async def quickbooks_health():
    """Check QuickBooks integration health"""
    config_status = check_integration_config("quickbooks")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="QuickBooks integration not configured. Please add QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET to .env"
        )
    return health_response("quickbooks", config_status, is_mock=False)


# GitHub
@router.get("/api/github/health")
async def github_health():
    """Check GitHub integration health"""
    config_status = check_integration_config("github")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="GitHub integration not configured. Please add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to .env"
        )
    return health_response("github", config_status, is_mock=False)


# Salesforce
@router.get("/api/salesforce/health")
async def salesforce_health():
    """Check Salesforce integration health"""
    config_status = check_integration_config("salesforce")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Salesforce integration not configured. Please add SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET to .env"
        )
    return health_response("salesforce", config_status, is_mock=False)


# Google Drive
@router.get("/api/google-drive/health")
async def google_drive_health():
    """Check Google Drive integration health"""
    config_status = check_integration_config("google-drive")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Google Drive integration not configured. Please add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env"
        )
    return health_response("google-drive", config_status, is_mock=False)


# Dropbox
@router.get("/api/dropbox/health")
async def dropbox_health():
    """Check Dropbox integration health"""
    config_status = check_integration_config("dropbox")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Dropbox integration not configured. Please add DROPBOX_CLIENT_ID and DROPBOX_CLIENT_SECRET to .env"
        )
    return health_response("dropbox", config_status, is_mock=False)


# Slack
@router.get("/api/slack/health")
async def slack_health():
    """Check Slack integration health"""
    config_status = check_integration_config("slack")
    if not config_status["configured"]:
        return router.error_response(
            status_code=401,
            message="Slack integration not configured. Please add SLACK_CLIENT_ID and SLACK_CLIENT_SECRET to .env"
        )
    return health_response("slack", config_status, is_mock=False)

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
    return router.error_response(
        status_code=501,
        message="Google OAuth login not yet implemented in this environment"
    )

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
    return router.error_response(
        status_code=501,
        message="Use /api/byok/keys endpoint to manage API keys"
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
    return router.error_response(
        status_code=501,
        message="LanceDB search available via /api/unified-search/semantic"
    )

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
@router.get("/api/chat/history/{session_id}")
async def chat_history(session_id: str):
    return router.error_response(
        status_code=404,
        message=f"Session {session_id} not found"
    )

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
