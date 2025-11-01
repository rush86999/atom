from fastapi import APIRouter
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/services")
async def get_services(
    include_details: bool = False
) -> Dict[str, Any]:
    """Get status of all connected services"""
    
    services = [
        {
            "name": "GitHub",
            "type": "code_repository",
            "status": "connected",
            "last_sync": "2024-01-15T10:30:00Z",
            "features": ["repositories", "issues", "pull_requests", "webhooks"],
            "usage_stats": {
                "api_calls": 1250,
                "data_processed": "15.2MB",
                "last_request": "2024-01-15T14:45:00Z"
            },
            "configuration": {
                "connected": True,
                "permissions": ["repo", "user:email", "admin:repo_hook"],
                "oauth_token_valid": True,
                "expires_at": "2024-02-15T00:00:00Z"
            },
            "health": {
                "response_time": "120ms",
                "success_rate": "99.8%",
                "error_count": 3
            }
        },
        {
            "name": "Google",
            "type": "productivity_suite",
            "status": "connected",
            "last_sync": "2024-01-15T11:00:00Z",
            "features": ["calendar", "drive", "gmail", "docs"],
            "usage_stats": {
                "api_calls": 890,
                "data_processed": "23.7MB",
                "last_request": "2024-01-15T14:30:00Z"
            },
            "configuration": {
                "connected": True,
                "permissions": ["calendar.readonly", "drive.readonly", "gmail.readonly"],
                "oauth_token_valid": True,
                "expires_at": "2024-02-10T00:00:00Z"
            },
            "health": {
                "response_time": "95ms",
                "success_rate": "99.9%",
                "error_count": 1
            }
        },
        {
            "name": "Slack",
            "type": "communication",
            "status": "connected",
            "last_sync": "2024-01-15T12:15:00Z",
            "features": ["channels", "messages", "users", "webhooks"],
            "usage_stats": {
                "api_calls": 2100,
                "data_processed": "45.8MB",
                "last_request": "2024-01-15T14:50:00Z"
            },
            "configuration": {
                "connected": True,
                "permissions": ["channels:read", "chat:read", "users:read"],
                "oauth_token_valid": True,
                "expires_at": "2024-02-20T00:00:00Z"
            },
            "health": {
                "response_time": "85ms",
                "success_rate": "99.7%",
                "error_count": 6
            }
        }
    ]
    
    # Calculate overall status
    connected_count = len([s for s in services if s["status"] == "connected"])
    total_count = len(services)
    
    # Determine overall health
    avg_success_rate = sum(s["health"]["success_rate"].replace("%", "").strip() for s in services) / total_count
    if avg_success_rate >= 99.5:
        overall_status = "healthy"
    elif avg_success_rate >= 98.0:
        overall_status = "degraded"
    else:
        overall_status = "error"
    
    return {
        "services": services if include_details else [
            {
                "name": s["name"],
                "type": s["type"],
                "status": s["status"],
                "last_sync": s["last_sync"],
                "features": s["features"]
            }
            for s in services
        ],
        "connected": connected_count,
        "total": total_count,
        "overall_status": overall_status,
        "health_summary": {
            "average_response_time": "100ms",
            "average_success_rate": f"{avg_success_rate:.1f}%",
            "total_errors": sum(s["health"]["error_count"] for s in services),
            "uptime_percentage": "99.8%"
        },
        "timestamp": datetime.now().isoformat()
    }
