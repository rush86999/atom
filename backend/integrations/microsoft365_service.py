"""
Microsoft 365 Service Integration for ATOM Platform

This module provides Microsoft 365 operations for the main backend API.
It handles authentication and integration with Microsoft 365 services including
Teams, Outlook, OneDrive, SharePoint, and Power Platform.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Microsoft Graph API scopes for Microsoft 365
MICROSOFT365_SCOPES = [
    "User.Read",
    "Mail.Read",
    "Calendars.Read",
    "Files.Read.All",
    "Sites.Read.All",
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
    "ChannelMessage.Read",
]

# Initialize router
microsoft365_router = APIRouter(prefix="/microsoft365", tags=["Microsoft 365"])


# Pydantic models
class Microsoft365AuthResponse(BaseModel):
    auth_url: str
    state: str


class Microsoft365User(BaseModel):
    id: str
    displayName: str
    mail: str
    userPrincipalName: str


class Microsoft365Team(BaseModel):
    id: str
    displayName: str
    description: Optional[str] = None
    visibility: Optional[str] = None


class Microsoft365Channel(BaseModel):
    id: str
    displayName: str
    description: Optional[str] = None


class Microsoft365Service:
    """Microsoft 365 service for handling unified Microsoft platform integration."""

    def __init__(self):
        self.service_name = "microsoft365"
        self.required_scopes = MICROSOFT365_SCOPES
        self.base_url = "https://graph.microsoft.com/v1.0"

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Initialize Microsoft 365 authentication flow."""
        try:
            # In a real implementation, this would generate OAuth URL
            # For now, return mock auth URL
            import os
            import urllib.parse
            
            client_id = os.getenv("MICROSOFT_365_CLIENT_ID", "mock_client_id")
            redirect_uri = os.getenv("MICROSOFT_365_REDIRECT_URI", "http://localhost:3000/api/auth/callback/microsoft365")
            
            params = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "response_mode": "query",
                "scope": " ".join(self.required_scopes),
                "state": f"microsoft365_{user_id}"
            }
            
            auth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}"
            
            return {
                "status": "success",
                "auth_url": auth_url,
                "state": f"microsoft365_{user_id}",
            }
        except Exception as e:
            logger.error(f"Microsoft 365 authentication failed: {e}")
            return {"status": "error", "message": f"Authentication failed: {str(e)}"}

    async def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """Get Microsoft 365 user profile."""
        try:
            # Mock implementation
            mock_profile = {
                "id": "user123",
                "displayName": "John Doe",
                "mail": "john.doe@example.com",
                "userPrincipalName": "john.doe@example.com",
                "jobTitle": "Software Engineer",
                "officeLocation": "Seattle",
            }

            return {"status": "success", "data": mock_profile}
        except Exception as e:
            logger.error(f"Microsoft 365 get user profile failed: {e}")
            return {
                "status": "error",
                "message": f"Failed to get user profile: {str(e)}",
            }

    async def list_teams(self, access_token: str) -> Dict[str, Any]:
        """List Microsoft Teams the user is a member of."""
        try:
            url = f"{self.base_url}/me/joinedTeams"
            return await self._make_graph_request("GET", url, access_token)
        except Exception as e:
            logger.error(f"Microsoft 365 list teams failed: {e}")
            return {"status": "error", "message": f"Failed to list teams: {str(e)}"}

    async def list_channels(self, access_token: str, team_id: str) -> Dict[str, Any]:
        """List channels in a Microsoft Team."""
        try:
            url = f"{self.base_url}/teams/{team_id}/channels"
            return await self._make_graph_request("GET", url, access_token)
        except Exception as e:
            logger.error(f"Microsoft 365 list channels failed: {e}")
            return {"status": "error", "message": f"Failed to list channels: {str(e)}"}

    async def get_outlook_messages(
        self, access_token: str, folder_id: str = "inbox", top: int = 10
    ) -> Dict[str, Any]:
        """Get Outlook messages from specified folder."""
        try:
            url = f"{self.base_url}/me/mailFolders/{folder_id}/messages?$top={top}&$select=id,subject,from,receivedDateTime,bodyPreview"
            return await self._make_graph_request("GET", url, access_token)
        except Exception as e:
            logger.error(f"Microsoft 365 get outlook messages failed: {e}")
            return {"status": "error", "message": f"Failed to get messages: {str(e)}"}

    async def get_calendar_events(
        self, access_token: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Get calendar events for specified date range."""
        try:
            url = f"{self.base_url}/me/calendarView?startDateTime={start_date}&endDateTime={end_date}"
            return await self._make_graph_request("GET", url, access_token)
        except Exception as e:
            logger.error(f"Microsoft 365 get calendar events failed: {e}")
            return {"status": "error", "message": f"Failed to get events: {str(e)}"}

    async def _make_graph_request(self, method: str, url: str, token: str, json_data: Any = None) -> Dict[str, Any]:
        """Make an authenticated request to Microsoft Graph API."""
        import aiohttp
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Bypass for testing validation (ONLY in development)
        import os
        if token == "fake_token" and os.getenv("ATOM_ENV") == "development":
             logger.info(f"MOCK BYPASS: {method} {url}")
             return {"status": "success", "data": {"id": "mock_id_123"}}

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, json=json_data) as response:
                if response.status >= 400:
                    text = await response.text()
                    logger.error(f"Graph API Error ({response.status}): {text}")
                    return {"status": "error", "code": response.status, "message": text}
                
                if response.status == 204:
                    return {"status": "success", "data": None}
                    
                data = await response.json()
                return {"status": "success", "data": data}

    async def execute_onedrive_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute OneDrive/SharePoint action."""
        try:
            if action == "list_files":
                folder = params.get("folder", "")
                url = f"{self.base_url}/me/drive/root:/{folder}:/children" if folder else f"{self.base_url}/me/drive/root/children"
                return await self._make_graph_request("GET", url, token)
            elif action == "get_content":
                path = params.get("path")
                url = f"{self.base_url}/me/drive/root:/{path}:/content"
                # Note: Content handling might need stream processing, keeping simple for JSON APIs
                return await self._make_graph_request("GET", url, token)
            return {"status": "error", "message": f"Unknown OneDrive action: {action}"}
        except Exception as e:
            logger.error(f"OneDrive action failed: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_excel_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Excel action."""
        try:
            item_id = params.get("item_id") # Drive Item ID of the Excel file
            if not item_id:
                # Try to find by path if ID not provided
                path = params.get("path")
                if path:
                    # Logic to get ID from path would go here, omitting for brevity
                    pass
                else:
                     return {"status": "error", "message": "Excel action requires item_id or path"}

            if action == "update_range":
                range_address = params.get("range") # e.g. Sheet1!A1:B2
                values = params.get("values") # [[1, 2], [3, 4]]
                url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets/{range_address.split('!')[0]}/range(address='{range_address.split('!')[1]}')"
                return await self._make_graph_request("PATCH", url, token, {"values": values})
            elif action == "append_row":
                 sheet = params.get("sheet", "Sheet1")
                 values = params.get("values") # [col1, col2]
                 table = params.get("table")
                 
                 if table:
                     url = f"{self.base_url}/me/drive/items/{item_id}/workbook/tables/{table}/rows"
                 else:
                     # Identify used range and append... simplistic approach:
                     return {"status": "error", "message": "Append row requires a table defined in Excel"}
                 
                 return await self._make_graph_request("POST", url, token, {"values": [values]})
            
            return {"status": "error", "message": f"Unknown Excel action: {action}"}
        except Exception as e:
             logger.error(f"Excel action failed: {e}")
             return {"status": "error", "message": str(e)}

    async def execute_powerbi_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Power BI action."""
        try:
            if action == "refresh_dataset":
                group_id = params.get("group_id") # Workspace ID
                dataset_id = params.get("dataset_id")
                
                url = f"{self.base_url}/groups/{group_id}/datasets/{dataset_id}/refreshes"
                # NotifyOption: MailOnFailure
                return await self._make_graph_request("POST", url, token, {"notifyOption": "MailOnFailure"})
            
            return {"status": "error", "message": f"Unknown Power BI action: {action}"}
        except Exception as e:
             logger.error(f"Power BI action failed: {e}")
             return {"status": "error", "message": str(e)}

    async def execute_teams_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Teams action."""
        try:
            if action == "send_message":
                team_id = params.get("team_id")
                channel_id = params.get("channel_id")
                message = params.get("message")
                
                url = f"{self.base_url}/teams/{team_id}/channels/{channel_id}/messages"
                payload = {
                    "body": {
                        "content": message,
                        "contentType": "text"
                    }
                }
                return await self._make_graph_request("POST", url, token, payload)
            elif action == "create_channel":
                team_id = params.get("team_id")
                display_name = params.get("display_name")
                description = params.get("description", "")
                
                url = f"{self.base_url}/teams/{team_id}/channels"
                payload = {
                   "displayName": display_name,
                   "description": description
                }
                return await self._make_graph_request("POST", url, token, payload)

            return {"status": "error", "message": f"Unknown Teams action: {action}"}
        except Exception as e:
             logger.error(f"Teams action failed: {e}")
             return {"status": "error", "message": str(e)}

    async def execute_outlook_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Outlook action."""
        try:
            if action == "send_email":
                to_recipients = params.get("to", [])
                if isinstance(to_recipients, str):
                    to_recipients = [to_recipients]
                
                subject = params.get("subject", "No Subject")
                body = params.get("body", "")
                
                url = f"{self.base_url}/me/sendMail"
                payload = {
                    "message": {
                        "subject": subject,
                        "body": {
                            "contentType": "Text",
                            "content": body
                        },
                        "toRecipients": [{"emailAddress": {"address": email}} for email in to_recipients]
                    },
                    "saveToSentItems": "true"
                }
                return await self._make_graph_request("POST", url, token, payload)
            
            elif action == "create_event":
                subject = params.get("subject", "Meeting")
                start_time = params.get("start_time") # ISO format
                end_time = params.get("end_time") # ISO format
                
                url = f"{self.base_url}/me/events"
                payload = {
                    "subject": subject,
                    "start": {
                        "dateTime": start_time,
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": end_time,
                        "timeZone": "UTC"
                    }
                }
                return await self._make_graph_request("POST", url, token, payload)

            return {"status": "error", "message": f"Unknown Outlook action: {action}"}
        except Exception as e:
             logger.error(f"Outlook action failed: {e}")
             return {"status": "error", "message": str(e)}

    async def execute_planner_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Planner action."""
        try:
            if action == "create_task":
                plan_id = params.get("plan_id")
                bucket_id = params.get("bucket_id")
                title = params.get("title")
                
                url = f"{self.base_url}/planner/tasks"
                payload = {
                    "planId": plan_id,
                    "bucketId": bucket_id,
                    "title": title
                }
                return await self._make_graph_request("POST", url, token, payload)
            
            return {"status": "error", "message": f"Unknown Planner action: {action}"}
        except Exception as e:
             logger.error(f"Planner action failed: {e}")
             return {"status": "error", "message": str(e)}

    async def delete_item(self, token: str, item_type: str, item_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Delete an item (message, event, file)."""
        try:
            url = ""
            if item_type == "message":
                # For messages, we need user_id typically, but /me/messages works for logged in user
                url = f"{self.base_url}/me/messages/{item_id}"
            elif item_type == "event":
                url = f"{self.base_url}/me/events/{item_id}"
            elif item_type == "file":
                url = f"{self.base_url}/me/drive/items/{item_id}"
            elif item_type == "team_message":
                 team_id = params.get("team_id")
                 channel_id = params.get("channel_id")
                 if not team_id or not channel_id:
                     return {"status": "error", "message": "Team ID and Channel ID required for team message deletion"}
                 url = f"{self.base_url}/teams/{team_id}/channels/{channel_id}/messages/{item_id}"
            else:
                return {"status": "error", "message": f"Unknown item type for deletion: {item_type}"}

            return await self._make_graph_request("DELETE", url, token)

        except Exception as e:
            logger.error(f"Delete item failed: {e}")
            return {"status": "error", "message": str(e)}

    async def create_subscription(self, token: str, resource: str, change_type: str, notification_url: str, expiration_datetime: str) -> Dict[str, Any]:
        """Create a webhook subscription."""
        try:
            url = f"{self.base_url}/subscriptions"
            payload = {
                "changeType": change_type,
                "notificationUrl": notification_url,
                "resource": resource,
                "expirationDateTime": expiration_datetime,
                "clientState": "secretClientState" # verifying incoming notifications
            }
            return await self._make_graph_request("POST", url, token, payload)
        except Exception as e:
            logger.error(f"Create subscription failed: {e}")
            return {"status": "error", "message": str(e)}

    async def renew_subscription(self, token: str, subscription_id: str, expiration_datetime: str) -> Dict[str, Any]:
         """Renew a webhook subscription."""
         try:
            url = f"{self.base_url}/subscriptions/{subscription_id}"
            payload = {
                "expirationDateTime": expiration_datetime
            }
            return await self._make_graph_request("PATCH", url, token, payload)
         except Exception as e:
            logger.error(f"Renew subscription failed: {e}")
            return {"status": "error", "message": str(e)}

    async def delete_subscription(self, token: str, subscription_id: str) -> Dict[str, Any]:
        """Delete a webhook subscription."""
        try:
            url = f"{self.base_url}/subscriptions/{subscription_id}"
            return await self._make_graph_request("DELETE", url, token)
        except Exception as e:
            logger.error(f"Delete subscription failed: {e}")
            return {"status": "error", "message": str(e)}


# Service instance
microsoft365_service = Microsoft365Service()


# API Routes
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
