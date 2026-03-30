"""
Microsoft 365 Integration Adapter

Provides OAuth-based integration with Microsoft 365 for productivity apps.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class Microsoft365Adapter:
    """
    Adapter for Microsoft 365 OAuth integration.

    Supports:
    - OAuth 2.0 authentication (Microsoft Graph API)
    - Outlook email and calendar
    - Teams chat and meetings
    - OneDrive and SharePoint
    - Tasks and notes
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "microsoft365"
        self.base_url = "https://graph.microsoft.com/v1.0"

        # OAuth credentials from environment
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Microsoft OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Microsoft OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("MICROSOFT_CLIENT_ID not configured")

        # Microsoft OAuth endpoint
        auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

        # Build authorization URL with comprehensive scopes
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "Mail.ReadWrite Mail.Send Calendars.ReadWrite Tasks.ReadWrite "
                     "Files.ReadWrite.All offline_access User.Read",
            "state": self.workspace_id,
            "response_mode": "query"
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Microsoft 365 OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Microsoft OAuth credentials not configured")

        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")

                # Calculate token expiration
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                logger.info(f"Successfully obtained Microsoft 365 access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Microsoft 365 token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Microsoft 365 API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting user info
                response = await client.get(
                    f"{self.base_url}/me",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Microsoft 365 connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Microsoft 365 connection test failed: {e}")
            return False

    async def get_emails(self, folder_id: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve emails from Outlook.

        Args:
            folder_id: Folder ID (empty for inbox)
            limit: Maximum number of results

        Returns:
            List of email objects
        """
        if not self._access_token:
            raise ValueError("Microsoft 365 access token not available")

        try:
            # Build URL for messages
            if folder_id:
                url = f"{self.base_url}/me/mailFolders/{folder_id}/messages"
            else:
                url = f"{self.base_url}/me/mailFolders/Inbox/messages"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={"$top": limit}
                )
                response.raise_for_status()

                data = response.json()
                emails = data.get("value", [])

                logger.info(f"Retrieved {len(emails)} Microsoft 365 emails for workspace {self.workspace_id}")
                return emails

        except Exception as e:
            logger.error(f"Failed to retrieve Microsoft 365 emails: {e}")
            raise

    async def send_email(self, to: List[str], subject: str, body: str,
                        cc: List[str] = None, attachments: List[Dict] = None) -> Dict[str, Any]:
        """
        Send an email via Outlook.

        Args:
            to: Recipient email addresses
            subject: Email subject
            body: Email body (HTML)
            cc: CC recipients
            attachments: List of attachment objects

        Returns:
            Sent message object
        """
        if not self._access_token:
            raise ValueError("Microsoft 365 access token not available")

        try:
            # Build recipients
            to_recipients = [{"emailAddress": {"address": email}} for email in to]
            cc_recipients = [{"emailAddress": {"address": email}} for email in cc] if cc else []

            # Build message
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body
                    },
                    "toRecipients": to_recipients,
                    "ccRecipients": cc_recipients
                }
            }

            if attachments:
                message["message"]["attachments"] = attachments

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/me/sendMail",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=message
                )
                response.raise_for_status()

                logger.info(f"Sent Microsoft 365 email for workspace {self.workspace_id}")
                return {"status": "sent"}

        except Exception as e:
            logger.error(f"Failed to send Microsoft 365 email: {e}")
            raise

    async def get_calendar_events(self, start_date: str = None, end_date: str = None,
                                  limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve calendar events from Outlook.

        Args:
            start_date: Start date (ISO 8601 format)
            end_date: End date (ISO 8601 format)
            limit: Maximum number of results

        Returns:
            List of event objects
        """
        if not self._access_token:
            raise ValueError("Microsoft 365 access token not available")

        try:
            # Build calendar view URL
            url = f"{self.base_url}/me/calendarView"

            params = {"$top": limit}
            if start_date and end_date:
                params["startDateTime"] = start_date
                params["endDateTime"] = end_date

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                events = data.get("value", [])

                logger.info(f"Retrieved {len(events)} Microsoft 365 calendar events for workspace {self.workspace_id}")
                return events

        except Exception as e:
            logger.error(f"Failed to retrieve Microsoft 365 calendar events: {e}")
            raise

    async def create_calendar_event(self, subject: str, start: str, end: str,
                                   body: str = None, attendees: List[str] = None) -> Dict[str, Any]:
        """
        Create a calendar event in Outlook.

        Args:
            subject: Event subject
            start: Start time (ISO 8601 format)
            end: End time (ISO 8601 format)
            body: Event body
            attendees: List of attendee email addresses

        Returns:
            Created event object
        """
        if not self._access_token:
            raise ValueError("Microsoft 365 access token not available")

        try:
            # Build event
            event = {
                "subject": subject,
                "start": {
                    "dateTime": start,
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end,
                    "timeZone": "UTC"
                }
            }

            if body:
                event["body"] = {
                    "contentType": "HTML",
                    "content": body
                }

            if attendees:
                event["attendees"] = [
                    {
                        "emailAddress": {
                            "address": email
                        },
                        "type": "required"
                    }
                    for email in attendees
                ]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/me/events",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=event
                )
                response.raise_for_status()

                event_data = response.json()

                logger.info(f"Created Microsoft 365 calendar event for workspace {self.workspace_id}")
                return event_data

        except Exception as e:
            logger.error(f"Failed to create Microsoft 365 calendar event: {e}")
            raise

    async def get_tasks(self, list_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve tasks from Microsoft To Do.

        Args:
            list_id: Task list ID (empty for default list)

        Returns:
            List of task objects
        """
        if not self._access_token:
            raise ValueError("Microsoft 365 access token not available")

        try:
            # Build URL for tasks
            if list_id:
                url = f"{self.base_url}/me/todo/lists/{list_id}/tasks"
            else:
                url = f"{self.base_url}/me/todo/tasks"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                tasks = data.get("value", [])

                logger.info(f"Retrieved {len(tasks)} Microsoft 365 tasks for workspace {self.workspace_id}")
                return tasks

        except Exception as e:
            logger.error(f"Failed to retrieve Microsoft 365 tasks: {e}")
            raise

    async def create_task(self, title: str, body: str = None,
                         due_date: str = None, list_id: str = None) -> Dict[str, Any]:
        """
        Create a task in Microsoft To Do.

        Args:
            title: Task title
            body: Task body/description
            due_date: Due date (ISO 8601 format)
            list_id: Task list ID

        Returns:
            Created task object
        """
        if not self._access_token:
            raise ValueError("Microsoft 365 access token not available")

        try:
            # Build task
            task = {
                "title": title
            }

            if body:
                task["body"] = {
                    "content": body,
                    "contentType": "text"
                }

            if due_date:
                task["dueDateTime"] = {
                    "dateTime": due_date,
                    "timeZone": "UTC"
                }

            # Build URL
            if list_id:
                url = f"{self.base_url}/me/todo/lists/{list_id}/tasks"
            else:
                url = f"{self.base_url}/me/todo/tasks"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=task
                )
                response.raise_for_status()

                task_data = response.json()

                logger.info(f"Created Microsoft 365 task for workspace {self.workspace_id}")
                return task_data

        except Exception as e:
            logger.error(f"Failed to create Microsoft 365 task: {e}")
            raise

    async def get_teams_chats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve Teams chats.

        Args:
            limit: Maximum number of results

        Returns:
            List of chat objects
        """
        if not self._access_token:
            raise ValueError("Microsoft 365 access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me/chats",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={"$top": limit}
                )
                response.raise_for_status()

                data = response.json()
                chats = data.get("value", [])

                logger.info(f"Retrieved {len(chats)} Microsoft Teams chats for workspace {self.workspace_id}")
                return chats

        except Exception as e:
            logger.error(f"Failed to retrieve Microsoft Teams chats: {e}")
            raise
