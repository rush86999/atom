import os
import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import urllib.parse
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)


@dataclass
class OutlookUser:
    """Outlook user profile information"""

    id: str
    display_name: str
    mail: str
    user_principal_name: str
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    business_phones: Optional[List[str]] = None
    mobile_phone: Optional[str] = None


@dataclass
class OutlookEmail:
    """Outlook email message representation"""

    id: str
    subject: str
    body_preview: str
    body: Optional[Dict[str, Any]] = None
    sender: Optional[Dict[str, Any]] = None
    from_field: Optional[Dict[str, Any]] = None
    to_recipients: Optional[List[Dict[str, Any]]] = None
    cc_recipients: Optional[List[Dict[str, Any]]] = None
    bcc_recipients: Optional[List[Dict[str, Any]]] = None
    received_date_time: Optional[str] = None
    sent_date_time: Optional[str] = None
    has_attachments: bool = False
    importance: str = "normal"
    is_read: bool = False
    web_link: Optional[str] = None
    conversation_id: Optional[str] = None
    parent_folder_id: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


@dataclass
class OutlookCalendarEvent:
    """Outlook calendar event representation"""

    id: str
    subject: str
    body: Optional[Dict[str, Any]] = None
    start: Optional[Dict[str, Any]] = None
    end: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    attendees: Optional[List[Dict[str, Any]]] = None
    organizer: Optional[Dict[str, Any]] = None
    is_all_day: bool = False
    show_as: str = "busy"
    web_link: Optional[str] = None
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None


@dataclass
class OutlookContact:
    """Outlook contact representation"""

    id: str
    display_name: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    email_addresses: Optional[List[Dict[str, Any]]] = None
    business_phones: Optional[List[str]] = None
    mobile_phone: Optional[str] = None
    home_phones: Optional[List[str]] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None


@dataclass
class OutlookTask:
    """Outlook task representation"""

    id: str
    subject: str
    body: Optional[Dict[str, Any]] = None
    importance: str = "normal"
    status: str = "notStarted"
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None
    due_date_time: Optional[Dict[str, Any]] = None
    completed_date_time: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None


@dataclass
class OutlookAttachment:
    """Outlook attachment representation"""

    id: str
    name: str
    content_type: str
    size: int
    content_bytes: Optional[str] = None
    last_modified_date_time: Optional[str] = None


class OutlookService(IntegrationService):
    """Comprehensive Outlook service for Microsoft Graph API integration"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Outlook service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with credentials
        """
        super().__init__(tenant_id, config)
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.client_id = config.get("client_id") or os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id_config = config.get("tenant_id") or os.getenv("MICROSOFT_TENANT_ID")
        self.redirect_uri = config.get("redirect_uri") or os.getenv("OUTLOOK_REDIRECT_URI")

    async def _get_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user from database"""
        try:
            from database_manager import DatabaseManager

            db = DatabaseManager()

            # Get user tokens from database
            tokens = await db.get_user_tokens(user_id, "outlook")
            if tokens and tokens.get("access_token"):
                # Check if token needs refresh
                if self._is_token_expired(tokens):
                    return await self._refresh_access_token(user_id, tokens)
                return tokens["access_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting access token for user {user_id}: {e}")
            return None

    def _is_token_expired(self, tokens: Dict[str, Any]) -> bool:
        """Check if access token is expired"""
        expires_at = tokens.get("expires_at")
        if not expires_at:
            return True

        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc).astimezone() >= expires_dt
        except Exception:
            return True

    async def _refresh_access_token(
        self, user_id: str, tokens: Dict[str, Any]
    ) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                return None

            # Refresh token logic would go here
            # For now, return the existing token
            return tokens.get("access_token")
        except Exception as e:
            logger.error(f"Error refreshing token for user {user_id}: {e}")
            return None

    async def _make_graph_request(
        self,
        user_id: str,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to Microsoft Graph API"""
        token = access_token
        if not token:
            token = await self._get_access_token(user_id)
        
        if not token:
            logger.error(f"No access token available for user {user_id}")
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers) as response:
                        return await self._handle_response(response)
                elif method.upper() == "POST":
                    async with session.post(
                        url, headers=headers, json=data
                    ) as response:
                        return await self._handle_response(response)
                elif method.upper() == "PATCH":
                    async with session.patch(
                        url, headers=headers, json=data
                    ) as response:
                        return await self._handle_response(response)
                elif method.upper() == "DELETE":
                    async with session.delete(url, headers=headers) as response:
                        return await self._handle_response(response)
                else:
                    logger.error(f"Unsupported HTTP method: {method}")
                    return None
        except Exception as e:
            logger.error(f"Graph API request failed: {e}")
            return None

    async def _handle_response(self, response) -> Optional[Dict[str, Any]]:
        """Handle API response"""
        try:
            if response.status == 200 or response.status == 201:
                return await response.json()
            elif response.status == 204:
                return {"success": True}
            else:
                error_text = await response.text()
                logger.error(f"API request failed: {response.status} - {error_text}")
                return None
        except Exception as e:
            logger.error(f"Error handling response: {e}")
            return None

    # Email Operations
    async def get_user_emails(
        self,
        user_id: str,
        folder: str = "inbox",
        query: Optional[str] = None,
        max_results: int = 50,
        skip: int = 0,
        include_attachments: bool = False,
        token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user emails with filtering and pagination"""
        try:
            # Build query parameters
            params = {
                "$top": max_results,
                "$skip": skip,
                "$orderby": "receivedDateTime desc",
            }

            if query:
                params["$filter"] = (
                    f"contains(subject, '{query}') or contains(body/content, '{query}')"
                )

            if include_attachments:
                params["$expand"] = "attachments"

            # Build endpoint
            if folder == "inbox":
                endpoint = "/me/mailFolders/inbox/messages"
            elif folder == "sent":
                endpoint = "/me/mailFolders/sentitems/messages"
            elif folder == "drafts":
                endpoint = "/me/mailFolders/drafts/messages"
            else:
                endpoint = "/me/messages"

            if params:
                query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                endpoint = f"{endpoint}?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                emails = []
                for email_data in result["value"]:
                    email = OutlookEmail(
                        id=email_data.get("id"),
                        subject=email_data.get("subject", "No Subject"),
                        body_preview=email_data.get("bodyPreview", ""),
                        body=email_data.get("body"),
                        sender=email_data.get("sender"),
                        from_field=email_data.get("from"),
                        to_recipients=email_data.get("toRecipients", []),
                        cc_recipients=email_data.get("ccRecipients", []),
                        bcc_recipients=email_data.get("bccRecipients", []),
                        received_date_time=email_data.get("receivedDateTime"),
                        sent_date_time=email_data.get("sentDateTime"),
                        has_attachments=email_data.get("hasAttachments", False),
                        importance=email_data.get("importance", "normal"),
                        is_read=email_data.get("isRead", False),
                        web_link=email_data.get("webLink"),
                        conversation_id=email_data.get("conversationId"),
                        parent_folder_id=email_data.get("parentFolderId"),
                        attachments=email_data.get("attachments"),
                    )
                    emails.append(asdict(email))
                return emails

            return []
        except Exception as e:
            logger.error(f"Error getting user emails: {e}")
            return []

    async def send_email(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send email via Outlook"""
        try:
            # Prepare recipients
            to_recipients_data = [
                {"emailAddress": {"address": email}} for email in to_recipients
            ]
            cc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (cc_recipients or [])
            ]
            bcc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
            ]

            email_data = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": body},
                    "toRecipients": to_recipients_data,
                    "ccRecipients": cc_recipients_data,
                    "bccRecipients": bcc_recipients_data,
                },
                "saveToSentItems": True,
            }

            result = await self._make_graph_request(
                user_id, "/me/sendMail", "POST", email_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return None

    async def reply_to_email(
        self,
        user_id: str,
        message_id: str,
        comment: str,
        token: Optional[str] = None
    ) -> bool:
        """Reply to an email via Outlook"""
        try:
            reply_data = {
                "comment": comment
            }
            await self._make_graph_request(
                user_id, f"/me/messages/{message_id}/reply", "POST", reply_data, access_token=token
            )
            return True
        except Exception as e:
            logger.error(f"Error replying to email: {e}")
            return False

    async def create_draft_email(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create draft email"""
        try:
            # Prepare recipients
            to_recipients_data = [
                {"emailAddress": {"address": email}} for email in to_recipients
            ]
            cc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (cc_recipients or [])
            ]
            bcc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
            ]

            email_data = {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": to_recipients_data,
                "ccRecipients": cc_recipients_data,
                "bccRecipients": bcc_recipients_data,
            }

            result = await self._make_graph_request(
                user_id, "/me/messages", "POST", email_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating draft email: {e}")
            return None

    async def get_email_by_id(
        self, user_id: str, email_id: str, token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get specific email by ID"""
        try:
            result = await self._make_graph_request(user_id, f"/me/messages/{email_id}", access_token=token)
            if result:
                email = OutlookEmail(
                    id=result.get("id"),
                    subject=result.get("subject", "No Subject"),
                    body_preview=result.get("bodyPreview", ""),
                    body=result.get("body"),
                    sender=result.get("sender"),
                    from_field=result.get("from"),
                    to_recipients=result.get("toRecipients", []),
                    cc_recipients=result.get("ccRecipients", []),
                    bcc_recipients=result.get("bccRecipients", []),
                    received_date_time=result.get("receivedDateTime"),
                    sent_date_time=result.get("sentDateTime"),
                    has_attachments=result.get("hasAttachments", False),
                    importance=result.get("importance", "normal"),
                    is_read=result.get("isRead", False),
                    web_link=result.get("webLink"),
                    conversation_id=result.get("conversationId"),
                    parent_folder_id=result.get("parentFolderId"),
                )
                return asdict(email)
            return None
        except Exception as e:
            logger.error(f"Error getting email by ID: {e}")
            return None

    async def delete_email(self, user_id: str, email_id: str, token: Optional[str] = None) -> bool:
        """Delete email by ID"""
        try:
            result = await self._make_graph_request(
                user_id, f"/me/messages/{email_id}", "DELETE", access_token=token
            )
            return result is not None
        except Exception as e:
            logger.error(f"Error deleting email: {e}")
            return False

    async def get_attachment_content(
        self, user_id: str, message_id: str, attachment_id: str, token: Optional[str] = None
    ) -> Optional[bytes]:
        """Fetch attachment content for an email"""
        try:
            endpoint = f"/me/messages/{message_id}/attachments/{attachment_id}"
            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "contentBytes" in result:
                import base64

                return base64.b64decode(result["contentBytes"])

            logger.error(
                f"Failed to fetch content for attachment {attachment_id} in message {message_id}"
            )
            return None
        except Exception as e:
            logger.error(f"Error getting attachment content: {e}")
            return None

    # Calendar Operations
    async def get_calendar_events(
        self,
        user_id: str,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 50,
        token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get calendar events with time range filtering"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            # Build query parameters
            params = {"$top": max_results, "$orderby": "start/dateTime"}

            if time_min and time_max:
                params["$filter"] = (
                    f"start/dateTime ge '{time_min}' and end/dateTime le '{time_max}'"
                )
            elif time_min:
                params["$filter"] = f"start/dateTime ge '{time_min}'"
            elif time_max:
                params["$filter"] = f"end/dateTime le '{time_max}'"

            if params:
                query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                endpoint = f"/me/events?{query_string}"
            else:
                endpoint = "/me/events"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                events = []
                for event_data in result["value"]:
                    event = OutlookCalendarEvent(
                        id=event_data.get("id"),
                        subject=event_data.get("subject", "No Subject"),
                        body=event_data.get("body"),
                        start=event_data.get("start"),
                        end=event_data.get("end"),
                        location=event_data.get("location"),
                        attendees=event_data.get("attendees", []),
                        organizer=event_data.get("organizer"),
                        is_all_day=event_data.get("isAllDay", False),
                        show_as=event_data.get("showAs", "busy"),
                        web_link=event_data.get("webLink"),
                        created_date_time=event_data.get("createdDateTime"),
                        last_modified_date_time=event_data.get("lastModifiedDateTime"),
                    )
                    events.append(asdict(event))
                return events

            return []
        except Exception as e:
            logger.error(f"Error getting calendar events: {e}")
            return []

    async def create_calendar_event(
        self,
        user_id: str,
        subject: str,
        body: Optional[str] = None,
        start: Optional[Dict[str, Any]] = None,
        end: Optional[Dict[str, Any]] = None,
        location: Optional[Dict[str, Any]] = None,
        attendees: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create calendar event"""
        try:
            event_data = {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body or ""},
                "start": start
                or {"dateTime": datetime.now(timezone.utc).isoformat(), "timeZone": "UTC"},
                "end": end
                or {
                    "dateTime": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "timeZone": "UTC",
                },
            }

            if location:
                event_data["location"] = location

            if attendees:
                event_data["attendees"] = [
                    {"emailAddress": {"address": email}} for email in attendees
                ]

            result = await self._make_graph_request(
                user_id, "/me/events", "POST", event_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None

    async def update_calendar_event(
        self,
        user_id: str,
        event_id: str,
        event_data: Dict[str, Any],
        token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update calendar event"""
        try:
            result = await self._make_graph_request(
                user_id, f"/me/events/{event_id}", "PATCH", event_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error updating calendar event: {e}")
            return None

    # Contact Operations
    async def get_user_contacts(
        self, user_id: str, query: Optional[str] = None, max_results: int = 50, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get user contacts with optional search"""
        try:
            # Build query parameters
            params = {"$top": max_results, "$orderby": "displayName"}

            if query:
                params["$filter"] = (
                    f"contains(displayName, '{query}') or contains(givenName, '{query}') or contains(surname, '{query}')"
                )

            if params:
                query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                endpoint = f"/me/contacts?{query_string}"
            else:
                endpoint = "/me/contacts"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                contacts = []
                for contact_data in result["value"]:
                    contact = OutlookContact(
                        id=contact_data.get("id"),
                        display_name=contact_data.get("displayName", "Unknown"),
                        given_name=contact_data.get("givenName"),
                        surname=contact_data.get("surname"),
                        email_addresses=contact_data.get("emailAddresses", []),
                        business_phones=contact_data.get("businessPhones", []),
                        mobile_phone=contact_data.get("mobilePhone"),
                        home_phones=contact_data.get("homePhones", []),
                        company_name=contact_data.get("companyName"),
                        job_title=contact_data.get("jobTitle"),
                        office_location=contact_data.get("officeLocation"),
                        created_date_time=contact_data.get("createdDateTime"),
                        last_modified_date_time=contact_data.get(
                            "lastModifiedDateTime"
                        ),
                    )
                    contacts.append(asdict(contact))
                return contacts

            return []
        except Exception as e:
            logger.error(f"Error getting user contacts: {e}")
            return []

    async def create_contact(
        self,
        user_id: str,
        display_name: str,
        given_name: Optional[str] = None,
        surname: Optional[str] = None,
        email_addresses: Optional[List[Dict[str, Any]]] = None,
        business_phones: Optional[List[str]] = None,
        company_name: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create contact"""
        try:
            contact_data = {"displayName": display_name}

            if given_name:
                contact_data["givenName"] = given_name
            if surname:
                contact_data["surname"] = surname
            if email_addresses:
                contact_data["emailAddresses"] = email_addresses
            if business_phones:
                contact_data["businessPhones"] = business_phones
            if company_name:
                contact_data["companyName"] = company_name

            result = await self._make_graph_request(
                user_id, "/me/contacts", "POST", contact_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating contact: {e}")
            return None

    # Task Operations
    async def get_user_tasks(
        self, user_id: str, status: Optional[str] = None, max_results: int = 50, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get user tasks with optional status filtering"""
        try:
            # Build query parameters
            params = {"$top": max_results, "$orderby": "createdDateTime desc"}

            if status:
                params["$filter"] = f"status eq '{status}'"

            if params:
                query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                endpoint = f"/me/todo/lists/tasks/tasks?{query_string}"
            else:
                endpoint = "/me/todo/lists/tasks/tasks"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                tasks = []
                for task_data in result["value"]:
                    task = OutlookTask(
                        id=task_data.get("id"),
                        subject=task_data.get("subject", "No Subject"),
                        body=task_data.get("body"),
                        importance=task_data.get("importance", "normal"),
                        status=task_data.get("status", "notStarted"),
                        created_date_time=task_data.get("createdDateTime"),
                        last_modified_date_time=task_data.get("lastModifiedDateTime"),
                        due_date_time=task_data.get("dueDateTime"),
                        completed_date_time=task_data.get("completedDateTime"),
                        categories=task_data.get("categories", []),
                    )
                    tasks.append(asdict(task))
                return tasks

            return []
        except Exception as e:
            logger.error(f"Error getting user tasks: {e}")
            return []

    async def create_task(
        self,
        user_id: str,
        subject: str,
        body: Optional[str] = None,
        importance: str = "normal",
        due_date_time: Optional[Dict[str, Any]] = None,
        categories: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create task"""
        try:
            task_data = {"subject": subject, "importance": importance}

            if body:
                task_data["body"] = {"contentType": "text", "content": body}

            if due_date_time:
                task_data["dueDateTime"] = due_date_time

            if categories:
                task_data["categories"] = categories

            result = await self._make_graph_request(
                user_id, "/me/todo/lists/tasks/tasks", "POST", task_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None

    # User Profile Operations
    async def get_user_profile(self, user_id: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get user profile information"""
        try:
            result = await self._make_graph_request(user_id, "/me", access_token=token)
            if result:
                user = OutlookUser(
                    id=result.get("id"),
                    display_name=result.get("displayName", "Unknown"),
                    mail=result.get("mail"),
                    user_principal_name=result.get("userPrincipalName"),
                    job_title=result.get("jobTitle"),
                    office_location=result.get("officeLocation"),
                    business_phones=result.get("businessPhones", []),
                    mobile_phone=result.get("mobilePhone"),
                )
                return asdict(user)
            return None
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    async def get_unread_emails(
        self, user_id: str, max_results: int = 50, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get unread emails"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            params = {
                "$top": max_results,
                "$filter": "isRead eq false",
                "$orderby": "receivedDateTime desc",
            }
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"/me/messages?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                emails = []
                for email_data in result["value"]:
                    email = OutlookEmail(
                        id=email_data.get("id"),
                        subject=email_data.get("subject", "No Subject"),
                        body_preview=email_data.get("bodyPreview", ""),
                        body=email_data.get("body"),
                        sender=email_data.get("sender"),
                        from_field=email_data.get("from"),
                        to_recipients=email_data.get("toRecipients", []),
                        cc_recipients=email_data.get("ccRecipients", []),
                        bcc_recipients=email_data.get("bccRecipients", []),
                        received_date_time=email_data.get("receivedDateTime"),
                        sent_date_time=email_data.get("sentDateTime"),
                        has_attachments=email_data.get("hasAttachments", False),
                        importance=email_data.get("importance", "normal"),
                        is_read=email_data.get("isRead", False),
                        web_link=email_data.get("webLink"),
                        conversation_id=email_data.get("conversationId"),
                        parent_folder_id=email_data.get("parentFolderId"),
                    )
                    emails.append(asdict(email))
                return emails

            return []
        except Exception as e:
            logger.error(f"Error getting unread emails: {e}")
            return []

    async def search_emails(
        self, user_id: str, query: str, max_results: int = 50, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search emails across all folders"""
        try:
            params = {
                "$top": max_results,
                "$search": f'"{query}"',
                "$orderby": "receivedDateTime desc",
            }
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"/me/messages?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                emails = []
                for email_data in result["value"]:
                    email = OutlookEmail(
                        id=email_data.get("id"),
                        subject=email_data.get("subject", "No Subject"),
                        body_preview=email_data.get("bodyPreview", ""),
                        body=email_data.get("body"),
                        sender=email_data.get("sender"),
                        from_field=email_data.get("from"),
                        to_recipients=email_data.get("toRecipients", []),
                        cc_recipients=email_data.get("ccRecipients", []),
                        bcc_recipients=email_data.get("bccRecipients", []),
                        received_date_time=email_data.get("receivedDateTime"),
                        sent_date_time=email_data.get("sentDateTime"),
                        has_attachments=email_data.get("hasAttachments", False),
                        importance=email_data.get("importance", "normal"),
                        is_read=email_data.get("isRead", False),
                        web_link=email_data.get("webLink"),
                        conversation_id=email_data.get("conversationId"),
                        parent_folder_id=email_data.get("parentFolderId"),
                    )
                    emails.append(asdict(email))
                return emails

            return []
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Outlook integration capabilities"""
        return {
            "operations": [
                {"id": "send_email", "description": "Send email via Outlook"},
                {"id": "read_emails", "description": "Read emails from folders"},
                {"id": "create_calendar_event", "description": "Create calendar events"},
                {"id": "read_calendar", "description": "Read calendar events"},
                {"id": "create_contact", "description": "Create contacts"},
                {"id": "read_contacts", "description": "Read contacts"},
            ],
            "required_params": ["access_token"],
            "optional_params": ["folder", "max_results"],
            "rate_limits": {"requests_per_minute": 10000},
            "supports_webhooks": True,
        }

    def health_check(self) -> Dict[str, Any]:
        """Check if Outlook service is healthy"""
        try:
            return {
                "healthy": bool(self.client_id),
                "message": "Outlook service is configured" if self.client_id else "Missing client_id",
                "last_check": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": str(e),
                "last_check": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute an Outlook operation with tenant context.

        CRITICAL: Validates tenant_id from context to prevent cross-tenant access.
        """
        # Validate tenant context
        if context and "tenant_id" in context:
            if context["tenant_id"] != self.tenant_id:
                raise ValueError(f"Tenant ID mismatch: expected {self.tenant_id}, got {context['tenant_id']}")

        try:
            if operation == "send_email":
                result = await self.send_email(
                    user_id=parameters.get("user_id", self.tenant_id),
                    to_recipients=parameters["to_recipients"],
                    subject=parameters["subject"],
                    body=parameters["body"],
                    token=parameters.get("token"),
                )
                return {"success": result is not None, "result": result}

            elif operation == "read_emails":
                emails = await self.get_user_emails(
                    user_id=parameters.get("user_id", self.tenant_id),
                    folder=parameters.get("folder", "inbox"),
                    max_results=parameters.get("max_results", 50),
                    token=parameters.get("token"),
                )
                return {"success": True, "result": emails}

            elif operation == "create_calendar_event":
                result = await self.create_calendar_event(
                    user_id=parameters.get("user_id", self.tenant_id),
                    subject=parameters["subject"],
                    start=parameters.get("start"),
                    end=parameters.get("end"),
                    token=parameters.get("token"),
                )
                return {"success": result is not None, "result": result}

            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "details": f"Supported operations: send_email, read_emails, create_calendar_event",
                }

        except Exception as e:
            logger.error(f"Error executing Outlook operation {operation}: {e}")
            return {"success": False, "error": str(e)}
    async def sync_to_postgres_cache(self, user_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Sync Outlook analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get counts for Inbox
            inbox_res = await self._make_graph_request(user_id, "/me/mailFolders/inbox", access_token=token)
            if not inbox_res:
                return {"success": False, "error": "Failed to fetch Inbox stats"}
                
            total_messages = inbox_res.get('totalItemCount', 0)
            unread_messages = inbox_res.get('unreadItemCount', 0)
            
            # Get calendar events count (recent)
            events = await self.get_calendar_events(user_id, max_results=100, token=token)
            event_count = len(events)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("outlook_total_messages", total_messages, "count"),
                    ("outlook_unread_count", unread_messages, "count"),
                    ("outlook_event_count", event_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="outlook",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="outlook",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Outlook metrics to PostgreSQL cache for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving Outlook metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Outlook PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Outlook"""
        # Pipeline 1: Atom Memory
        # Triggered via outlook_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(user_id, token)
        
        return {
            "success": True,
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # --- NATIVE HUB SYNC METHODS (PHASE 37) ---

    async def fetch_recent_messages(self, user_id: str, max_results: int = 50, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch recent Outlook emails and ingest them into the Communication Hub pipeline"""
        from integrations.atom_communication_ingestion_pipeline import get_ingestion_pipeline
        
        try:
            # We use the existing get_user_emails method
            messages_list = await self.get_user_emails(user_id, max_results=max_results, token=token, include_attachments=True)
            if not messages_list:
                return []
            
            pipeline = get_ingestion_pipeline()
            # Outlook messages retrieved via get_emails are already somewhat normalized
            # but we need to match the Dict[str, Any] format the pipeline normalization expects
            
            for msg in messages_list:
                # Ingest into pipeline
                # The pipeline normalization for outlook expects body, from, to, date, etc.
                # outlook_service.get_emails returns objects that asdict turns into appropriate structures
                pipeline.ingest_message("outlook", msg)
            
            return messages_list
        except Exception as e:
            logger.error(f"Error in fetch_recent_messages: {e}")
            return []

    async def sync_calendar_events(self, user_id: str, days_ahead: int = 7, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Sync Outlook Calendar events and ingest them into the Calendar Hub pipeline"""
        from integrations.atom_communication_ingestion_pipeline import get_ingestion_pipeline
        
        try:
            events = await self.get_calendar_events(user_id, max_results=100, token=token)
            if not events:
                return []
            
            pipeline = get_ingestion_pipeline()
            
            for event in events:
                # Normalize for pipeline
                # Outlook events from get_calendar_events are dictionaries
                normalized_event = {
                    "id": event.get("id"),
                    "title": event.get("subject", "No Title"),
                    "description": event.get("bodyPreview"),
                    "location": event.get("location", {}).get("displayName"),
                    "start_time": datetime.fromisoformat(event["start"]["dateTime"].split('.')[0]),
                    "end_time": datetime.fromisoformat(event["end"]["dateTime"].split('.')[0]),
                    "attendees": [
                        {"email": a["emailAddress"]["address"], "name": a["emailAddress"]["name"]} 
                        for a in event.get("attendees", [])
                    ],
                    "organizer": event.get("organizer", {}).get("emailAddress", {}).get("address"),
                    "metadata": event,
                    "tenant_id": user_id
                }
                pipeline.ingest_calendar_event("outlook_calendar", normalized_event)
                
            return events
        except Exception as e:
            logger.error(f"Error in sync_calendar_events: {e}")
            return []

# Create a default instance for hub_sync_service compatibility
outlook_service = OutlookService("default", {})

