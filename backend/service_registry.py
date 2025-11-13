
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter()

# Basic service registry
SERVICES = [
    {
        "id": "slack",
        "name": "Slack",
        "description": "Team communication platform",
        "status": "available",
        "oauth_required": True
    },
    {
        "id": "gmail",
        "name": "Gmail",
        "description": "Email service",
        "status": "available",
        "oauth_required": True
    },
    {
        "id": "google_calendar",
        "name": "Google Calendar",
        "description": "Calendar and scheduling",
        "status": "available",
        "oauth_required": True
    },
    {
        "id": "github",
        "name": "GitHub",
        "description": "Code repository and collaboration",
        "status": "available",
        "oauth_required": True
    },
    {
        "id": "asana",
        "name": "Asana",
        "description": "Project management",
        "status": "available",
        "oauth_required": True
    },
    {
        "id": "notion",
        "name": "Notion",
        "description": "Note-taking and documentation",
        "status": "available",
        "oauth_required": True
    }
]

@router.get("/api/services/registry")
async def get_service_registry():
    """Get available services"""
    return {
        "services": SERVICES,
        "total_services": len(SERVICES),
        "active_services": len([s for s in SERVICES if s["status"] == "available"])
    }

@router.get("/api/services/{service_id}")
async def get_service(service_id: str):
    """Get specific service details"""
    service = next((s for s in SERVICES if s["id"] == service_id), None)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service
