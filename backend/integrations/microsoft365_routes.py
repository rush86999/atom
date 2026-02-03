"""
Microsoft 365 Routes for ATOM Platform

This module provides FastAPI routes for Microsoft 365 integration.
It handles API endpoints for Teams, Outlook, Calendar, and other Microsoft 365 services.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .microsoft365_service import (
    Microsoft365AuthResponse,
    Microsoft365Channel,
    Microsoft365Service,
    Microsoft365Team,
    Microsoft365User,
)


class Microsoft365SubscriptionRequest(BaseModel):
    resource: str
    changeType: str
    notificationUrl: str
    expirationDateTime: str


class Microsoft365ActionRequest(BaseModel):
    action: str
    params: Dict[str, Any] = {}


# Initialize router
microsoft365_router = APIRouter(tags=["Microsoft 365"])

# Service instance
microsoft365_service = Microsoft365Service()

# Mock service for health check detection
class Microsoft365ServiceMock:
    def __init__(self):
        self.client_id = "mock_client_id"



@microsoft365_router.get("/auth")
async def microsoft365_auth(user_id: str):
    """Initiate Microsoft 365 OAuth flow."""
    result = await microsoft365_service.authenticate(user_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return Microsoft365AuthResponse(**result)


@microsoft365_router.get("/user")
async def get_microsoft365_user(access_token: str):
    """Get Microsoft 365 user profile."""
    result = await microsoft365_service.get_user_profile(access_token)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return Microsoft365User(**result["data"])


@microsoft365_router.get("/teams")
async def list_microsoft365_teams(access_token: str):
    """List Microsoft Teams."""
    result = await microsoft365_service.list_teams(access_token)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"teams": result["data"]["value"]}


@microsoft365_router.get("/teams/{team_id}/channels")
async def list_microsoft365_channels(team_id: str, access_token: str):
    """List channels in a Microsoft Team."""
    result = await microsoft365_service.list_channels(access_token, team_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"channels": result["data"]["value"]}


@microsoft365_router.get("/outlook/messages")
async def get_microsoft365_messages(
    access_token: str, folder_id: str = "inbox", top: int = 10
):
    """Get Outlook messages."""
    result = await microsoft365_service.get_outlook_messages(
        access_token, folder_id, top
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"messages": result["data"]["value"]}


@microsoft365_router.get("/calendar/events")
async def get_microsoft365_events(access_token: str, start_date: str, end_date: str):
    """Get calendar events."""
    result = await microsoft365_service.get_calendar_events(
        access_token, start_date, end_date
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"events": result["data"]["value"]}


@microsoft365_router.get("/services/status")
async def get_microsoft365_service_status(access_token: str):
    """Get Microsoft 365 service status."""
    result = await microsoft365_service.get_service_status(access_token)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@microsoft365_router.get("/health")
async def microsoft365_health():
    """Health check for Microsoft 365 service."""
    return {
        "status": "healthy",
        "service": "microsoft365",
        "timestamp": "2024-01-21T10:00:00Z",
    }


@microsoft365_router.get("/capabilities")
async def microsoft365_capabilities():
    """Get Microsoft 365 service capabilities."""
    return {
        "service": "microsoft365",
        "capabilities": [
            "teams_integration",
            "outlook_email",
            "calendar_events",
            "onedrive_files",
            "sharepoint_sites",
            "user_profile",
            "oauth_authentication",
            "service_status_monitoring",
        ],
        "supported_services": [
            "microsoft_teams",
            "outlook_email",
            "outlook_calendar",
            "onedrive",
            "sharepoint",
            "microsoft_graph",
        ],
        "integration_features": [
            "unified_microsoft_platform",
            "cross_service_workflows",
            "real_time_notifications",
            "enterprise_grade_security",
            "compliance_standards",
        ],
    }


@microsoft365_router.delete("/outlook/messages/{message_id}")
async def delete_microsoft365_message(message_id: str, access_token: str):
    """Delete an Outlook message."""
    result = await microsoft365_service.delete_item(access_token, "message", message_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"status": "success", "message": "Message deleted"}


@microsoft365_router.delete("/calendar/events/{event_id}")
async def delete_microsoft365_event(event_id: str, access_token: str):
    """Delete a calendar event."""
    result = await microsoft365_service.delete_item(access_token, "event", event_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"status": "success", "message": "Event deleted"}


@microsoft365_router.post("/excel/execute")
async def execute_excel_action(request: Microsoft365ActionRequest, access_token: str):
    """Execute generic Excel action."""
    return await microsoft365_service.execute_excel_action(access_token, request.action, request.params)


@microsoft365_router.post("/teams/execute")
async def execute_teams_action(request: Microsoft365ActionRequest, access_token: str):
    """Execute generic Teams action."""
    return await microsoft365_service.execute_teams_action(access_token, request.action, request.params)


@microsoft365_router.post("/outlook/execute")
async def execute_outlook_action(request: Microsoft365ActionRequest, access_token: str):
    """Execute generic Outlook action."""
    return await microsoft365_service.execute_outlook_action(access_token, request.action, request.params)


@microsoft365_router.post("/onedrive/execute")
async def execute_onedrive_action(request: Microsoft365ActionRequest, access_token: str):
    """Execute generic OneDrive action."""
    return await microsoft365_service.execute_onedrive_action(access_token, request.action, request.params)


@microsoft365_router.delete("/files/{item_id}")
async def delete_microsoft365_file(item_id: str, access_token: str):
    """Delete a file from OneDrive."""
    result = await microsoft365_service.delete_item(access_token, "file", item_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"status": "success", "message": "File deleted"}


@microsoft365_router.delete("/teams/{team_id}/channels/{channel_id}/messages/{message_id}")
async def delete_microsoft365_team_message(team_id: str, channel_id: str, message_id: str, access_token: str):
    """Delete a Teams message."""
    result = await microsoft365_service.delete_item(
        access_token, 
        "team_message", 
        message_id, 
        params={"team_id": team_id, "channel_id": channel_id}
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"status": "success", "message": "Message deleted"}


@microsoft365_router.post("/subscriptions")
async def create_microsoft365_subscription(
    subscription: Microsoft365SubscriptionRequest, access_token: str
):
    """Create a webhook subscription."""
    result = await microsoft365_service.create_subscription(
        access_token,
        subscription.resource,
        subscription.changeType,
        subscription.notificationUrl,
        subscription.expirationDateTime,
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@microsoft365_router.post("/webhook")
async def handle_microsoft365_webhook(validationToken: Optional[str] = None):
    """
    Handle Microsoft Graph webhooks.
    If validationToken is present, it's a verification request (return it back plain text).
    Otherwise it's a notification payload.
    """
    if validationToken:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(validationToken)
    
    # Process notification logic here
    # Ideally queue this for background processing
    return {"status": "received"}

