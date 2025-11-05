import os
import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import urllib.parse

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


class OutlookService:
    """Comprehensive Outlook service for Microsoft Graph API integration"""

    def __init__(self):
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID")
        self.redirect_uri = os.getenv("OUTLOOK_REDIRECT_URI")

    async def _get_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user from database"""
        try:
            from backend.database_manager import DatabaseManager

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
            return datetime.now().astimezone() >= expires_dt
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
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to Microsoft Graph API"""
        access_token = await self._get_access_token(user_id)
        if not access_token:
            logger.error(f"No access token available for user {user_id}")
            return None

        headers = {
            "Authorization": f"Bearer {access_token}",
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

            result = await self._make_graph_request(user_id, endpoint)

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
                user_id, "/me/sendMail", "POST", email_data
            )
            return result
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return None

    async def create_draft_email(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
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
                user_id, "/me/messages", "POST", email_data
            )
            return result
        except Exception as e:
            logger.error(f"Error creating draft email: {e}")
            return None

    async def get_email_by_id(
        self, user_id: str, email_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get specific email by ID"""
        try:
            result = await self._make_graph_request(user_id, f"/me/messages/{email_id}")
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

    async def delete_email(self, user_id: str, email_id: str) -> bool:
        """Delete email by ID"""
        try:
            result = await self._make_graph_request(
                user_id, f"/me/messages/{email_id}", "DELETE"
            )
            return result is not None
        except Exception as e:
            logger.error(f"Error deleting email: {e}")
            return False

    # Calendar Operations
    async def get_calendar_events(
        self,
        user_id: str,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get calendar events with time range filtering"""
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

            result = await self._make_graph_request(user_id, endpoint)

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
    ) -> Optional[Dict[str, Any]]:
        """Create calendar event"""
        try:
            event_data = {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body or ""},
                "start": start
                or {"dateTime": datetime.now().isoformat(), "timeZone": "UTC"},
                "end": end
                or {
                    "dateTime": (datetime.now() + timedelta(hours=1)).isoformat(),
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
                user_id, "/me/events", "POST", event_data
            )
            return result
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None

    # Contact Operations
    async def get_user_contacts(
        self, user_id: str, query: Optional[str] = None, max_results: int = 50
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

            result = await self._make_graph_request(user_id, endpoint)

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
                user_id, "/me/contacts", "POST", contact_data
            )
            return result
        except Exception as e:
            logger.error(f"Error creating contact: {e}")
            return None

    # Task Operations
    async def get_user_tasks(
        self, user_id: str, status: Optional[str] = None, max_results: int = 50
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

            result = await self._make_graph_request(user_id, endpoint)

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
                user_id, "/me/todo/lists/tasks/tasks", "POST", task_data
            )
            return result
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None

    # User Profile Operations
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile information"""
        try:
            result = await self._make_graph_request(user_id, "/me")
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
        self, user_id: str, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Get unread emails"""
        try:
            params = {
                "$top": max_results,
                "$filter": "isRead eq false",
                "$orderby": "receivedDateTime desc",
            }
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"/me/messages?{query_string}"

            result = await self._make_graph_request(user_id, endpoint)

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
        self, user_id: str, query: str, max_results: int = 50
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

            result = await self._make_graph_request(user_id, endpoint)

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
