from fastapi import APIRouter
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

router = APIRouter()

@router.get("/workflows")
async def get_workflows(
    status: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """Get all automation workflows"""
    
    workflows = [
        {
            "id": "workflow-1",
            "name": "GitHub PR to Slack Notification",
            "description": "Send Slack notification when GitHub PR is created",
            "status": "active",
            "trigger": {
                "service": "github",
                "event": "pull_request",
                "conditions": {
                    "action": "opened",
                    "repository": "atom/platform"
                }
            },
            "actions": [
                {
                    "service": "slack",
                    "action": "send_message",
                    "parameters": {
                        "channel": "#dev-team",
                        "message": "New PR opened: {{pr.title}} by {{pr.author}}"
                    }
                }
            ],
            "execution_count": 15,
            "last_executed": "2024-01-15T14:30:00Z",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-15T14:30:00Z"
        },
        {
            "id": "workflow-2",
            "name": "Google Calendar to GitHub Issue",
            "description": "Create GitHub issue from Google Calendar event",
            "status": "active",
            "trigger": {
                "service": "google",
                "event": "calendar_event",
                "conditions": {
                    "summary_contains": "bug",
                    "calendar": "development"
                }
            },
            "actions": [
                {
                    "service": "github",
                    "action": "create_issue",
                    "parameters": {
                        "repository": "atom/platform",
                        "title": "{{event.summary}}",
                        "body": "Created from calendar event: {{event.description}}"
                    }
                }
            ],
            "execution_count": 8,
            "last_executed": "2024-01-14T09:15:00Z",
            "created_at": "2024-01-05T00:00:00Z",
            "updated_at": "2024-01-14T09:15:00Z"
        },
        {
            "id": "workflow-3",
            "name": "Slack Message to Google Drive",
            "description": "Save important Slack messages to Google Drive",
            "status": "inactive",
            "trigger": {
                "service": "slack",
                "event": "message",
                "conditions": {
                    "channel": "#important",
                    "reactions_count": "> 5"
                }
            },
            "actions": [
                {
                    "service": "google",
                    "action": "create_document",
                    "parameters": {
                        "folder_id": "automation_exports",
                        "title": "{{message.timestamp}} - {{message.text[:50]}}",
                        "content": "{{message.text}}"
                    }
                }
            ],
            "execution_count": 0,
            "last_executed": None,
            "created_at": "2024-01-10T00:00:00Z",
            "updated_at": "2024-01-10T00:00:00Z"
        }
    ]
    
    # Apply filters
    if status:
        workflows = [w for w in workflows if w["status"] == status]
    
    # Limit results
    limited_workflows = workflows[:limit]
    
    # Count status
    status_counts = {
        "active": len([w for w in workflows if w["status"] == "active"]),
        "inactive": len([w for w in workflows if w["status"] == "inactive"]),
        "total": len(workflows)
    }
    
    return {
        "workflows": limited_workflows,
        "total": len(workflows),
        "status_counts": status_counts,
        "filters": {
            "status": status,
            "limit": limit
        },
        "timestamp": datetime.now().isoformat()
    }
