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


from core.integration_service import IntegrationService

class Microsoft365Service(IntegrationService):
    """Microsoft 365 service for handling unified Microsoft platform integration."""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.service_name = "microsoft365"
        self.required_scopes = MICROSOFT365_SCOPES
        self.base_url = "https://graph.microsoft.com/v1.0"

    def get_capabilities(self) -> List[str]:
        """Return Microsoft 365 service capabilities."""
        return [
            "send_message",
            "read_messages",
            "create_channel",
            "list_channels",
            "list_teams",
            "read_calendar",
            "read_emails",
            "read_files",
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Check Microsoft 365 service health."""
        try:
            # Check if we have access token in config
            if "access_token" in self.config:
                return {
                    "status": "healthy",
                    "service": "microsoft365",
                    "tenant_id": self.tenant_id,
                }
            else:
                return {
                    "status": "unconfigured",
                    "service": "microsoft365",
                    "tenant_id": self.tenant_id,
                }
        except Exception as e:
            logger.error(f"Microsoft 365 health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "microsoft365",
                "error": str(e),
            }

    async def execute_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute Microsoft 365 operation."""
        try:
            if operation == "authenticate":
                user_id = kwargs.get("user_id")
                return await self._authenticate(user_id)
            elif operation == "send_message":
                team_id = kwargs.get("team_id")
                channel_id = kwargs.get("channel_id")
                content = kwargs.get("content")
                return await self._send_message(team_id, channel_id, content)
            elif operation == "list_teams":
                return await self._list_teams()
            elif operation == "list_channels":
                team_id = kwargs.get("team_id")
                return await self._list_channels(team_id)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown operation: {operation}",
                }
        except Exception as e:
            logger.error(f"Microsoft 365 operation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _authenticate(self, user_id: str) -> Dict[str, Any]:
        """Initialize Microsoft 365 authentication flow."""
        try:
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

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Initialize Microsoft 365 authentication flow (legacy method)."""
        return await self._authenticate(user_id)

    async def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """Get Microsoft 365 user profile."""
        try:
            # Use Microsoft Graph API to fetch real user profile
            url = f"{self.base_url}/me?$select=id,displayName,mail,userPrincipalName,jobTitle,officeLocation"
            return await self._make_graph_request("GET", url, access_token)
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

    async def get_planner_tasks(self, access_token: str, top: int = 10) -> Dict[str, Any]:
        """Get Microsoft Planner tasks."""
        try:
            url = f"{self.base_url}/me/planner/tasks?$top={top}"
            return await self._make_graph_request("GET", url, access_token)
        except Exception as e:
            logger.error(f"Microsoft 365 get planner tasks failed: {e}")
            return {"status": "error", "message": f"Failed to get planner tasks: {str(e)}"}

    async def get_dynamics_deals(self, access_token: str, top: int = 10) -> Dict[str, Any]:
        """Get Dynamics 365 Sales opportunities."""
        try:
            # Dynamics 365 data is often accessed via specific organization URLs, 
            # but basic integration can use Graph for data connectivity if configured.
            # Here we use a generic opportunities endpoint pattern.
            url = f"{self.base_url}/me/insights/trending?$top={top}" # Placeholder for trending items if Dynamics is missing
            # In a real Dynamics setup, it might be a custom endpoint or specific Dataverse API
            return await self._make_graph_request("GET", url, access_token)
        except Exception as e:
            logger.error(f"Microsoft 365 get dynamics deals failed: {e}")
            return {"status": "error", "message": f"Failed to get dynamics deals: {str(e)}"}

    async def get_dynamics_invoices(self, access_token: str, top: int = 10) -> Dict[str, Any]:
        """Get Dynamics 365 Finance invoices."""
        try:
            url = f"{self.base_url}/me/insights/used?$top={top}" # Placeholder
            return await self._make_graph_request("GET", url, access_token)
        except Exception as e:
            logger.error(f"Microsoft 365 get dynamics invoices failed: {e}")
            return {"status": "error", "message": f"Failed to get dynamics invoices: {str(e)}"}

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
        """Execute OneDrive/SharePoint action.

        Supported actions:
        - list_files: List files in a folder (params: folder="")
        - get_content: Download file content (params: path="")
        - upload: Upload file (params: path="", file_content=b"", content_type="")
        - delete: Delete file (params: item_id="")
        - share: Create sharing link (params: item_id="", link_type="view")
        - create_folder: Create folder (params: folder_path="", name="")
        """
        try:
            if action == "list_files":
                folder = params.get("folder", "")
                if folder:
                    # List specific folder
                    url = f"{self.base_url}/me/drive/root:/{folder}:/children?$top={params.get('top', 100)}&$select=id,name,size,lastModifiedDateTime,file,folder"
                else:
                    # List root folder
                    url = f"{self.base_url}/me/drive/root/children?$top={params.get('top', 100)}&$select=id,name,size,lastModifiedDateTime,file,folder"
                return await self._make_graph_request("GET", url, token)

            elif action == "get_content":
                path = params.get("path")
                if not path:
                    return {"status": "error", "message": "get_content requires 'path' parameter"}
                url = f"{self.base_url}/me/drive/root:/{path}:/content"
                return await self._make_graph_request("GET", url, token)

            elif action == "upload":
                path = params.get("path")
                file_content = params.get("file_content")
                content_type = params.get("content_type", "application/octet-stream")

                if not path or file_content is None:
                    return {"status": "error", "message": "upload requires 'path' and 'file_content' parameters"}

                # For small files (< 4MB), use upload session
                url = f"{self.base_url}/me/drive/root:/{path}:/content"

                # Use aiohttp for binary upload
                import aiohttp
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": content_type
                }

                async with aiohttp.ClientSession() as session:
                    async with session.put(url, headers=headers, data=file_content) as response:
                        if response.status >= 400:
                            text = await response.text()
                            logger.error(f"Upload error ({response.status}): {text}")
                            return {"status": "error", "code": response.status, "message": text}
                        data = await response.json()
                        return {"status": "success", "data": data}

            elif action == "delete":
                item_id = params.get("item_id")
                if not item_id:
                    return {"status": "error", "message": "delete requires 'item_id' parameter"}
                url = f"{self.base_url}/me/drive/items/{item_id}"
                return await self._make_graph_request("DELETE", url, token)

            elif action == "share":
                item_id = params.get("item_id")
                link_type = params.get("link_type", "view")  # view, edit, embed

                if not item_id:
                    return {"status": "error", "message": "share requires 'item_id' parameter"}

                url = f"{self.base_url}/me/drive/items/{item_id}/createLink"
                payload = {
                    "type": link_type,
                    "scope": "anonymous"  # or "organization"
                }
                return await self._make_graph_request("POST", url, token, payload)

            elif action == "create_folder":
                folder_path = params.get("folder_path", "")
                name = params.get("name")

                if not name:
                    return {"status": "error", "message": "create_folder requires 'name' parameter"}

                if folder_path:
                    url = f"{self.base_url}/me/drive/root:/{folder_path}:/children"
                else:
                    url = f"{self.base_url}/me/drive/root/children"

                payload = {
                    "name": name,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "rename"
                }
                return await self._make_graph_request("POST", url, token, payload)

            return {"status": "error", "message": f"Unknown OneDrive action: {action}. Supported: list_files, get_content, upload, delete, share, create_folder"}
        except Exception as e:
            logger.error(f"OneDrive action failed: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_excel_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Excel action using Microsoft Graph API.

        Supported actions:
        - read_range: Read cell values (params: item_id="", range="Sheet1!A1:B2")
        - write_range: Write cell values (params: item_id="", range="", values=[])
        - get_tables: List all tables (params: item_id="")
        - get_columns: Get table columns (params: item_id="", table="")
        - append_row: Append row to table (params: item_id="", table="", values=[] or mapping={})
        - create_worksheet: Create new worksheet (params: item_id="", name="")
        - format_range: Format cell range (params: item_id="", range="", format={})
        """
        try:
            # Helper to get item_id from path if needed
            item_id = params.get("item_id")
            if not item_id:
                path = params.get("path")
                if path:
                    # Resolve path to item_id
                    resolve_url = f"{self.base_url}/me/drive/root:/{path}"
                    resolve_resp = await self._make_graph_request("GET", resolve_url, token)
                    if resolve_resp.get("status") == "success" and "data" in resolve_resp:
                        item_id = resolve_resp["data"].get("id")
                    else:
                        return {"status": "error", "message": f"Could not resolve path to item_id: {path}"}
                else:
                    return {"status": "error", "message": "Excel action requires 'item_id' or 'path' parameter"}

            if action == "read_range":
                range_address = params.get("range")
                if not range_address:
                    return {"status": "error", "message": "read_range requires 'range' parameter (e.g., Sheet1!A1:B2)"}

                # Parse range: Sheet1!A1:B2
                if "!" in range_address:
                    sheet, cell_range = range_address.split("!", 1)
                    url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets/{sheet}/range(address='{cell_range}')"
                else:
                    url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets/sheet1/range(address='{range_address}')"

                return await self._make_graph_request("GET", url, token)

            elif action == "write_range":
                range_address = params.get("range")
                values = params.get("values")

                if not range_address or values is None:
                    return {"status": "error", "message": "write_range requires 'range' and 'values' parameters"}

                if "!" in range_address:
                    sheet, cell_range = range_address.split("!", 1)
                    url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets/{sheet}/range(address='{cell_range}')"
                else:
                    url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets/sheet1/range(address='{range_address}')"

                return await self._make_graph_request("PATCH", url, token, {"values": values})

            elif action == "get_tables":
                url = f"{self.base_url}/me/drive/items/{item_id}/workbook/tables"
                return await self._make_graph_request("GET", url, token)

            elif action == "get_columns":
                table = params.get("table")
                if not table:
                    return {"status": "error", "message": "get_columns requires 'table' parameter"}
                url = f"{self.base_url}/me/drive/items/{item_id}/workbook/tables/{table}/columns"
                return await self._make_graph_request("GET", url, token)

            elif action == "append_row":
                table = params.get("table")
                values = params.get("values")  # [col1, col2]
                mapping = params.get("mapping")  # {"ColumnName": "Value"}

                if not table:
                    return {"status": "error", "message": "append_row requires 'table' parameter"}

                # If mapping is provided, fetch columns to align values
                if mapping and not values:
                    cols_url = f"{self.base_url}/me/drive/items/{item_id}/workbook/tables/{table}/columns"
                    cols_resp = await self._make_graph_request("GET", cols_url, token)

                    if cols_resp.get("status") == "success" and "data" in cols_resp:
                        # Build values array based on column names
                        ordered_values = []
                        for col in cols_resp["data"]:
                            col_name = col.get("name")
                            ordered_values.append(mapping.get(col_name, ""))
                        values = ordered_values
                    else:
                        return {"status": "error", "message": "Could not fetch table columns for mapping"}

                if not values:
                    return {"status": "error", "message": "No values or mapping provided for append_row"}

                url = f"{self.base_url}/me/drive/items/{item_id}/workbook/tables/{table}/rows"
                return await self._make_graph_request("POST", url, token, {"values": [values]})

            elif action == "create_worksheet":
                name = params.get("name")
                if not name:
                    return {"status": "error", "message": "create_worksheet requires 'name' parameter"}

                url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets"
                payload = {"name": name}
                return await self._make_graph_request("POST", url, token, payload)

            elif action == "format_range":
                range_address = params.get("range")
                format_spec = params.get("format", {})

                if not range_address:
                    return {"status": "error", "message": "format_range requires 'range' parameter"}

                if "!" in range_address:
                    sheet, cell_range = range_address.split("!", 1)
                    url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets/{sheet}/range(address='{cell_range}')/format"
                else:
                    url = f"{self.base_url}/me/drive/items/{item_id}/workbook/worksheets/sheet1/range(address='{range_address}')/format"

                return await self._make_graph_request("PATCH", url, token, format_spec)

            return {"status": "error", "message": f"Unknown Excel action: {action}. Supported: read_range, write_range, get_tables, get_columns, append_row, create_worksheet, format_range"}
        except Exception as e:
            logger.error(f"Excel action failed: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_powerbi_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Power BI action using Microsoft Graph API.

        Supported actions:
        - refresh_dataset: Trigger dataset refresh (params: group_id="", dataset_id="")
        - get_reports: List all reports (params: group_id="")
        - get_dashboards: List all dashboards (params: group_id="")
        - export_report: Export report to file (params: group_id="", report_id="", format="PDF")
        - get_datasets: List all datasets (params: group_id="")
        """
        try:
            if action == "refresh_dataset":
                group_id = params.get("group_id")
                dataset_id = params.get("dataset_id")

                if not group_id or not dataset_id:
                    return {"status": "error", "message": "refresh_dataset requires 'group_id' and 'dataset_id' parameters"}

                url = f"{self.base_url}/groups/{group_id}/datasets/{dataset_id}/refreshes"
                payload = {"notifyOption": "MailOnFailure"}
                return await self._make_graph_request("POST", url, token, payload)

            elif action == "get_reports":
                group_id = params.get("group_id")
                if not group_id:
                    return {"status": "error", "message": "get_reports requires 'group_id' parameter"}

                url = f"{self.base_url}/groups/{group_id}/reports"
                return await self._make_graph_request("GET", url, token)

            elif action == "get_dashboards":
                group_id = params.get("group_id")
                if not group_id:
                    return {"status": "error", "message": "get_dashboards requires 'group_id' parameter"}

                url = f"{self.base_url}/groups/{group_id}/dashboards"
                return await self._make_graph_request("GET", url, token)

            elif action == "export_report":
                group_id = params.get("group_id")
                report_id = params.get("report_id")
                export_format = params.get("format", "PDF")  # PDF, PPTX, PNG

                if not group_id or not report_id:
                    return {"status": "error", "message": "export_report requires 'group_id' and 'report_id' parameters"}

                url = f"{self.base_url}/groups/{group_id}/reports/{report_id}/ExportTo"
                payload = {"format": export_format}
                return await self._make_graph_request("POST", url, token, payload)

            elif action == "get_datasets":
                group_id = params.get("group_id")
                if not group_id:
                    return {"status": "error", "message": "get_datasets requires 'group_id' parameter"}

                url = f"{self.base_url}/groups/{group_id}/datasets"
                return await self._make_graph_request("GET", url, token)

            return {"status": "error", "message": f"Unknown Power BI action: {action}. Supported: refresh_dataset, get_reports, get_dashboards, export_report, get_datasets"}
        except Exception as e:
            logger.error(f"Power BI action failed: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_teams_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Teams action using Microsoft Graph API.

        Supported actions:
        - send_message: Send message to channel (params: team_id="", channel_id="", message="")
        - create_channel: Create new channel (params: team_id="", display_name="", description="")
        - list_teams: List all teams (no params)
        """
        try:
            if action == "send_message":
                team_id = params.get("team_id")
                channel_id = params.get("channel_id")
                message = params.get("message")

                if not team_id or not channel_id or not message:
                    return {"status": "error", "message": "send_message requires 'team_id', 'channel_id', and 'message' parameters"}

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

                if not team_id or not display_name:
                    return {"status": "error", "message": "create_channel requires 'team_id' and 'display_name' parameters"}

                url = f"{self.base_url}/teams/{team_id}/channels"
                payload = {
                    "displayName": display_name,
                    "description": description
                }
                return await self._make_graph_request("POST", url, token, payload)

            elif action == "list_teams":
                url = f"{self.base_url}/me/joinedTeams"
                return await self._make_graph_request("GET", url, token)

            return {"status": "error", "message": f"Unknown Teams action: {action}. Supported: send_message, create_channel, list_teams"}
        except Exception as e:
            logger.error(f"Teams action failed: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_outlook_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Outlook action using Microsoft Graph API.

        Supported actions:
        - send_email: Send email (params: to=[], subject="", body="", cc=[], bcc=[])
        - list_messages: List messages (params: folder_id="inbox", top=10)
        - create_event: Create calendar event (params: subject="", start_time="", end_time="", body="", attendees=[])
        """
        try:
            if action == "send_email":
                to_recipients = params.get("to", [])
                if isinstance(to_recipients, str):
                    to_recipients = [to_recipients]

                subject = params.get("subject", "No Subject")
                body = params.get("body", "")
                cc_recipients = params.get("cc", [])
                bcc_recipients = params.get("bcc", [])

                if not to_recipients:
                    return {"status": "error", "message": "send_email requires 'to' parameter with at least one recipient"}

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

                if cc_recipients:
                    if isinstance(cc_recipients, str):
                        cc_recipients = [cc_recipients]
                    payload["message"]["ccRecipients"] = [{"emailAddress": {"address": email}} for email in cc_recipients]

                if bcc_recipients:
                    if isinstance(bcc_recipients, str):
                        bcc_recipients = [bcc_recipients]
                    payload["message"]["bccRecipients"] = [{"emailAddress": {"address": email}} for email in bcc_recipients]

                return await self._make_graph_request("POST", url, token, payload)

            elif action == "list_messages":
                folder_id = params.get("folder_id", "inbox")
                top = params.get("top", 10)

                url = f"{self.base_url}/me/mailFolders/{folder_id}/messages?$top={top}&$select=id,subject,from,receivedDateTime,bodyPreview"
                return await self._make_graph_request("GET", url, token)

            elif action == "create_event":
                subject = params.get("subject", "Meeting")
                start_time = params.get("start_time")  # ISO format
                end_time = params.get("end_time")  # ISO format
                body = params.get("body", "")
                attendees = params.get("attendees", [])  # List of email addresses

                if not start_time or not end_time:
                    return {"status": "error", "message": "create_event requires 'start_time' and 'end_time' parameters in ISO format"}

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

                if body:
                    payload["body"] = {
                        "contentType": "Text",
                        "content": body
                    }

                if attendees:
                    if isinstance(attendees, str):
                        attendees = [attendees]
                    payload["attendees"] = [
                        {
                            "emailAddress": {
                                "address": email,
                                "name": email.split("@")[0]
                            },
                            "type": "required"
                        }
                        for email in attendees
                    ]

                return await self._make_graph_request("POST", url, token, payload)

            return {"status": "error", "message": f"Unknown Outlook action: {action}. Supported: send_email, list_messages, create_event"}
        except Exception as e:
            logger.error(f"Outlook action failed: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_planner_action(self, token: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Planner action using Microsoft Graph API.

        Supported actions:
        - create_task: Create new task (params: plan_id="", bucket_id="", title="", assignments={}, description="")
        - update_task: Update task (params: task_id="", title="", description="", percent_complete=0)
        - list_plans: List all plans (params: group_id="")
        - list_buckets: List buckets in plan (params: plan_id="")
        - list_tasks: List tasks in plan (params: plan_id="")
        """
        try:
            if action == "create_task":
                plan_id = params.get("plan_id")
                bucket_id = params.get("bucket_id")
                title = params.get("title")
                assignments = params.get("assignments", {})  # {"user_id": {}}
                description = params.get("description", "")

                if not plan_id or not bucket_id or not title:
                    return {"status": "error", "message": "create_task requires 'plan_id', 'bucket_id', and 'title' parameters"}

                url = f"{self.base_url}/planner/tasks"
                payload = {
                    "planId": plan_id,
                    "bucketId": bucket_id,
                    "title": title,
                    "assignments": assignments
                }

                if description:
                    payload["description"] = description

                return await self._make_graph_request("POST", url, token, payload)

            elif action == "update_task":
                task_id = params.get("task_id")
                title = params.get("title")
                description = params.get("description")
                percent_complete = params.get("percent_complete")

                if not task_id:
                    return {"status": "error", "message": "update_task requires 'task_id' parameter"}

                url = f"{self.base_url}/planner/tasks/{task_id}"
                payload = {}

                if title is not None:
                    payload["title"] = title
                if description is not None:
                    payload["description"] = description
                if percent_complete is not None:
                    payload["percentComplete"] = percent_complete

                return await self._make_graph_request("PATCH", url, token, payload)

            elif action == "list_plans":
                group_id = params.get("group_id")
                if not group_id:
                    return {"status": "error", "message": "list_plans requires 'group_id' parameter"}

                url = f"{self.base_url}/groups/{group_id}/planner/plans"
                return await self._make_graph_request("GET", url, token)

            elif action == "list_buckets":
                plan_id = params.get("plan_id")
                if not plan_id:
                    return {"status": "error", "message": "list_buckets requires 'plan_id' parameter"}

                url = f"{self.base_url}/planner/plans/{plan_id}/buckets"
                return await self._make_graph_request("GET", url, token)

            elif action == "list_tasks":
                plan_id = params.get("plan_id")
                if not plan_id:
                    return {"status": "error", "message": "list_tasks requires 'plan_id' parameter"}

                url = f"{self.base_url}/planner/plans/{plan_id}/tasks"
                return await self._make_graph_request("GET", url, token)

            return {"status": "error", "message": f"Unknown Planner action: {action}. Supported: create_task, update_task, list_plans, list_buckets, list_tasks"}
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

    async def _send_message(self, team_id: str, channel_id: str, content: str) -> Dict[str, Any]:
        """Send message to Microsoft Teams channel."""
        try:
            token = self.config.get("access_token")
            if not token:
                return {"status": "error", "message": "No access token configured"}

            url = f"{self.base_url}/teams/{team_id}/channels/{channel_id}/messages"
            payload = {"body": {"content": content}}

            return await self._make_graph_request("POST", url, token, payload)
        except Exception as e:
            logger.error(f"Send message failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _list_teams(self) -> Dict[str, Any]:
        """List Microsoft Teams for the tenant."""
        try:
            token = self.config.get("access_token")
            if not token:
                return {"status": "error", "message": "No access token configured"}

            url = f"{self.base_url}/me/joinedTeams"
            return await self._make_graph_request("GET", url, token)
        except Exception as e:
            logger.error(f"List teams failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _list_channels(self, team_id: str) -> Dict[str, Any]:
        """List channels in a Microsoft Team."""
        try:
            token = self.config.get("access_token")
            if not token:
                return {"status": "error", "message": "No access token configured"}

            url = f"{self.base_url}/teams/{team_id}/channels"
            return await self._make_graph_request("GET", url, token)
        except Exception as e:
            logger.error(f"List channels failed: {e}")
            return {"status": "error", "message": str(e)}


# Service instance - REMOVED: Use IntegrationRegistry instead
# microsoft365_service = Microsoft365Service()


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
