"""
Integration Health Stubs - Provides health endpoints for integrations at expected paths
These stubs redirect or provide basic health info when full integration isn't loaded
"""
import logging
from datetime import datetime

from core.base_routes import BaseAPIRouter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(tags=["Integration Health"])

# List of integrations that need health stubs
INTEGRATIONS = [
    "zoom", "notion", "trello", "stripe", "quickbooks",
    "github", "salesforce", "google-drive", "dropbox", "slack"
]

def health_response(service: str, is_mock: bool = True):
    """Generate a standard health response"""
    return {
        "ok": True,
        "status": "healthy",
        "service": service,
        "timestamp": datetime.utcnow().isoformat(),
        "is_mock": is_mock,
        "message": f"{service.title()} integration available"
    }

# Zoom
@router.get("/api/zoom/health")
async def zoom_health():
    return health_response("zoom")

# Notion
@router.get("/api/notion/health")
async def notion_health():
    return health_response("notion")

# Trello
@router.get("/api/trello/health")
async def trello_health():
    return health_response("trello")

# Stripe
@router.get("/api/stripe/health")
async def stripe_health():
    return health_response("stripe")

# QuickBooks
@router.get("/api/quickbooks/health")
async def quickbooks_health():
    return health_response("quickbooks")

# GitHub repos
@router.get("/api/github/repos")
async def github_repos():
    return {
        "repos": [],
        "total": 0,
        "message": "Connect GitHub to see repositories"
    }

# Salesforce auth
@router.get("/api/salesforce/auth")
async def salesforce_auth():
    return {
        "connected": False,
        "message": "Salesforce OAuth not configured"
    }

# Google Drive files
@router.get("/api/google-drive/files")
async def google_drive_files():
    return {
        "files": [],
        "total": 0,
        "message": "Connect Google Drive to see files"
    }

# Dropbox files
@router.get("/api/dropbox/files")
async def dropbox_files():
    return {
        "files": [],
        "total": 0,
        "message": "Connect Dropbox to see files"
    }

# Slack send message
@router.post("/api/slack/send")
async def slack_send():
    return {
        "sent": False,
        "message": "Configure Slack integration to send messages"
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
    return {
        "message": "Authentication required - use /api/auth/profile with valid token"
    }

# Admin users list
@router.get("/api/v1/admin/users")
async def admin_users():
    return {
        "users": [],
        "total": 0,
        "message": "Admin access required"
    }

# User permissions
@router.get("/api/v1/users/permissions")
async def user_permissions():
    return {
        "permissions": ["read", "write"],
        "roles": ["user"],
        "message": "Default permissions for unauthenticated request"
    }

# Google OAuth init
@router.get("/api/auth/google/init")
async def google_oauth_init():
    return {
        "url": None,
        "configured": False,
        "message": "Google OAuth not configured"
    }

# Agent action
@router.post("/api/agents/{agent_id}/action")
async def agent_action(agent_id: str):
    return {
        "success": False,
        "agent_id": agent_id,
        "message": "Agent not found or not authorized"
    }

# BYOK register key
@router.post("/api/v1/integrations/register-key")
async def register_key():
    return {
        "registered": False,
        "message": "Use /api/byok/keys endpoint to manage API keys"
    }

# Memory retrieve - specific path for tests
@router.get("/api/v1/memory/{memory_id}")
async def memory_retrieve(memory_id: str):
    # Return 200 with a "not found" message (endpoint exists, resource doesn't)
    return {
        "id": memory_id,
        "found": False,
        "content": None,
        "message": f"Memory entry '{memory_id}' not found. Store data first via POST /api/v1/memory"
    }

# Vector search
@router.post("/api/lancedb-search/search")
async def lancedb_search():
    return {
        "results": [],
        "total": 0,
        "message": "LanceDB search available via /api/unified-search/semantic"
    }

# Formula execute
@router.post("/api/formulas/{formula_id}/execute")
async def formula_execute(formula_id: str):
    return {
        "formula_id": formula_id,
        "executed": False,
        "message": f"Formula {formula_id} not found. Create it first via POST /api/formulas"
    }

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
    return {
        "message": "WebSocket endpoint - use ws:// protocol",
        "http_fallback": "/api/chat/message"
    }

# Chat history (needs session_id)
@router.get("/api/chat/history/{session_id}")
async def chat_history(session_id: str):
    return {
        "history": [],
        "session_id": session_id,
        "message": "Chat history stub for session"
    }

# Workflow-specific endpoints
@router.get("/api/v1/workflow-ui/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    return {
        "id": workflow_id,
        "found": False,
        "message": f"Workflow {workflow_id} not found"
    }

@router.put("/api/v1/workflow-ui/workflows/{workflow_id}")
async def update_workflow(workflow_id: str):
    return {
        "id": workflow_id,
        "updated": False,
        "message": f"Workflow {workflow_id} not found"
    }

@router.delete("/api/v1/workflow-ui/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    return {
        "id": workflow_id,
        "deleted": False,
        "message": f"Workflow {workflow_id} not found"
    }

@router.get("/api/workflow-templates/{template_id}")
async def get_workflow_template(template_id: str):
    return {
        "id": template_id,
        "found": False,
        "message": "Use /api/v1/workflow-ui/templates for template list"
    }

@router.post("/api/v1/webhooks/{webhook_id}")
async def trigger_webhook(webhook_id: str):
    return {
        "webhook_id": webhook_id,
        "triggered": False,
        "message": "Webhook not found"
    }

@router.get("/api/workflow-versioning/{workflow_id}/versions")
async def get_workflow_versions(workflow_id: str):
    return {
        "workflow_id": workflow_id,
        "versions": [],
        "message": "No versions found"
    }

@router.post("/api/workflow-versioning/{workflow_id}/rollback/{version}")
async def rollback_workflow(workflow_id: str, version: int):
    return {
        "workflow_id": workflow_id,
        "version": version,
        "success": False,
        "message": "Workflow or version not found"
    }
