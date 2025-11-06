"""
Enhanced Outlook Service with Comprehensive Microsoft Graph API Integration
Complete enterprise-grade Outlook integration for the ATOM platform
"""

import logging
import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import base64
import hashlib
import hmac

logger = logging.getLogger(__name__)

# Microsoft Graph API constants
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_API_SCOPES = [
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.ReadWrite",
    "Contacts.ReadWrite",
    "Tasks.ReadWrite",
    "User.Read",
    "User.ReadBasic.All",
    "Files.ReadWrite.All",
    "Sites.ReadWrite.All",
]


class EmailImportance(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EventSensitivity(Enum):
    NORMAL = "normal"
    PERSONAL = "personal"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


class TaskStatus(Enum):
    NOT_STARTED = "notStarted"
    IN_PROGRESS = "inProgress"
    COMPLETED = "completed"
    WAITING_ON_OTHERS = "waitingOnOthers"
    DEFERRED = "deferred"


@dataclass
class OutlookUser:
    """Enhanced Outlook user representation"""

    id: str
    display_name: str
    email: str
    job_title: str
    department: str
    office_location: str
    mobile_phone: str
    business_phones: List[str]
    user_principal_name: str
    mail: str
    account_enabled: bool
    user_type: str
    preferred_language: str
    timezone: str
    usage_location: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class OutlookEmail:
    """Enhanced Outlook email representation"""

    id: str
    conversation_id: str
    subject: str
    body_preview: str
    body: Dict[str, Any]
    importance: str
    has_attachments: bool
    is_read: bool
    is_draft: bool
    web_link: str
    created_datetime: str
    last_modified_datetime: str
    received_datetime: str
    sent_datetime: str
    from_address: Dict[str, str]
    to_recipients: List[Dict[str, str]]
    cc_recipients: List[Dict[str, str]]
    bcc_recipients: List[Dict[str, str]]
    reply_to: List[Dict[str, str]]
    categories: List[str]
    flag: Dict[str, Any]
    internet_message_headers: List[Dict[str, str]]
    attachments: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class OutlookCalendarEvent:
    """Enhanced Outlook calendar event representation"""

    id: str
    subject: str
    body_preview: str
    body: Dict[str, Any]
    start: Dict[str, str]
    end: Dict[str, str]
    location: Dict[str, str]
    locations: List[Dict[str, str]]
    attendees: List[Dict[str, Any]]
    organizer: Dict[str, Any]
    is_all_day: bool
    is_cancelled: bool
    is_organizer: bool
    response_requested: bool
    response_status: Dict[str, str]
    sensitivity: str
    show_as: str
    type: str
    web_link: str
    online_meeting: Dict[str, Any]
    recurrence: Dict[str, Any]
    reminder_minutes_before_start: int
    categories: List[str]
    extensions: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class OutlookContact:
    """Enhanced Outlook contact representation"""

    id: str
    display_name: str
    given_name: str
    surname: str
    job_title: str
    department: str
    company_name: str
    business_phones: List[str]
    mobile_phone: str
    home_phones: List[str]
    email_addresses: List[Dict[str, str]]
    im_addresses: List[str]
    home_address: Dict[str, str]
    business_address: Dict[str, str]
    other_address: Dict[str, str]
    personal_notes: str
    birthday: str
    anniversary: str
    spouse_name: str
    children: List[str]
    manager: str
    assistant_name: str
    profession: str
    categories: List[str]
    created_date_time: str
    last_modified_date_time: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class OutlookTask:
    """Enhanced Outlook task representation"""

    id: str
    subject: str
    body: Dict[str, Any]
    importance: str
    status: str
    completed_date_time: Dict[str, str]
    due_date_time: Dict[str, str]
    start_date_time: Dict[str, str]
    created_date_time: str
    last_modified_date_time: str
    is_reminder_on: bool
    reminder_date_time: Dict[str, str]
    categories: List[str]
    assigned_to: str
    parent_folder_id: str
    conversation_id: str
    conversation_index: str
    flag: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class OutlookFolder:
    """Outlook folder representation"""

    id: str
    display_name: str
    parent_folder_id: str
    child_folder_count: int
    unread_item_count: int
    total_item_count: int
    folder_type: str
    is_hidden: bool
    well_known_name: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class OutlookAttachment:
    """Outlook attachment representation"""

    id: str
    name: str
    content_type: str
    size: int
    is_inline: bool
    content_id: str
    content_bytes: str
    last_modified_date_time: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class OutlookEnhancedService:
    """Enhanced Outlook service with comprehensive Microsoft Graph API integration"""

    def __init__(
        self, client_id: str = None, client_secret: str = None, tenant_id: str = None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None

        # Cache for storing data
        self.users_cache = {}
        self.emails_cache = {}
        self.events_cache = {}
        self.contacts_cache = {}
        self.tasks_cache = {}
        self.folders_cache = {}

        # Session for HTTP requests
        self.session = None

        logger.info("OutlookEnhancedService initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _close_session(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _get_access_token(self, user_id: str) -> str:
        """Get access token for user (implementation depends on token storage)"""
        # In production, this would retrieve tokens from secure storage
        # For now, return the stored access token
        if (
            self.access_token
            and self.token_expiry
            and datetime.now() < self.token_expiry
        ):
            return self.access_token

        # Token expired or not available
        raise Exception("Access token not available or expired")

    async def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token"""
        try:
            if not self.refresh_token:
                raise Exception("No refresh token available")

            url = (
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            )
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(GRAPH_API_SCOPES),
            }

            session = await self._get_session()
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data["access_token"]
                    self.refresh_token = token_data.get(
                        "refresh_token", self.refresh_token
                    )
                    self.token_expiry = datetime.now() + timedelta(
                        seconds=token_data["expires_in"] - 300
                    )
                    logger.info("Access token refreshed successfully")
                    return True
                else:
                    logger.error(f"Token refresh failed: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return False

    async def _make_graph_request(
        self,
        method: str,
        endpoint: str,
        user_id: str,
        data: Dict[str, Any] = None,
        params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Make request to Microsoft Graph API"""
        try:
            access_token = await self._get_access_token(user_id)
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "ATOM-Platform/1.0",
            }

            url = f"{GRAPH_API_BASE_URL}/{endpoint}"
            session = await self._get_session()

            if method.upper() == "GET":
                async with session.get(url, headers=headers, params=params) as response:
                    return await self._handle_response(response, url)
            elif method.upper() == "POST":
                async with session.post(
                    url, headers=headers, json=data, params=params
                ) as response:
                    return await self._handle_response(response, url)
            elif method.upper() == "PUT":
                async with session.put(url, headers=headers, json=data) as response:
                    return await self._handle_response(response, url)
            elif method.upper() == "PATCH":
                async with session.patch(url, headers=headers, json=data) as response:
                    return await self._handle_response(response, url)
            elif method.upper() == "DELETE":
                async with session.delete(url, headers=headers) as response:
                    return await self._handle_response(response, url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error in Graph API request: {e}")
            raise Exception(f"HTTP client error: {str(e)}")
        except Exception as e:
            logger.error(f"Error making Graph API request: {e}")
            raise

    async def _handle_response(
        self, response: aiohttp.ClientResponse, url: str
    ) -> Dict[str, Any]:
        """Handle HTTP response"""
        try:
            if response.status == 401:
                # Token might be expired, try to refresh
                if await self._refresh_access_token():
                    # Retry the request with new token
                    return await self._make_graph_request(
                        response.request_info.method,
                        url.replace(GRAPH_API_BASE_URL + "/", ""),
                        "retry_user",  # This would need proper user context
                        await response.request_info.json()
                        if response.request_info.method in ["POST", "PUT", "PATCH"]
                        else None,
                        dict(response.request_info.url.query),
                    )
                else:
                    raise Exception(
                        "Authentication failed and token refresh unsuccessful"
                    )

            if response.status == 429:
                # Rate limiting - implement backoff
                retry_after = int(response.headers.get("Retry-After", 5))
                logger.warning(f"Rate limited, waiting {retry_after} seconds")
                await asyncio.sleep(retry_after)
                # Retry the request
                return await self._make_graph_request(
                    response.request_info.method,
                    url.replace(GRAPH_API_BASE_URL + "/", ""),
                    "retry_user",
                    await response.request_info.json()
                    if response.request_info.method in ["POST", "PUT", "PATCH"]
                    else None,
                    dict(response.request_info.url.query),
                )

            response.raise_for_status()

            if response.status == 204:  # No content
                return {"success": True}

            return await response.json()

        except aiohttp.ClientResponseError as e:
            logger.error(f"Graph API response error: {e.status} - {e.message}")
            raise Exception(f"Graph API error: {e.status} - {e.message}")
        except Exception as e:
            logger.error(f"Error handling Graph API response: {e}")
            raise

    # Enhanced Email Operations
    async def get_user_emails_enhanced(
        self,
        user_id: str,
        folder: str = "inbox",
        query: str = None,
        max_results: int = 50,
        skip: int = 0,
        include_attachments: bool = False,
        order_by: str = "receivedDateTime DESC",
    ) -> List[OutlookEmail]:
        """Get user emails with enhanced filtering and options"""
        try:
            cache_key = f"{user_id}:{folder}:{query}:{max_results}:{skip}"
            if cache_key in self.emails_cache:
                return self.emails_cache[cache_key]

            endpoint = f"users/{user_id}/mailFolders/{folder}/messages"
            params = {
                "$top": max_results,
                "$skip": skip,
                "$orderby": order_by,
                "$select": "id,conversationId,subject,bodyPreview,body,importance,hasAttachments,isRead,isDraft,webLink,createdDateTime,lastModifiedDateTime,receivedDateTime,sentDateTime,from,toRecipients,ccRecipients,bccRecipients,replyTo,categories,flag,internetMessageHeaders",
            }

            if query:
                params["$filter"] = query

            if include_attachments:
                params["$expand"] = "attachments"

            result = await self._make_graph_request(
                "GET", endpoint, user_id, params=params
            )
            emails = []

            for email_data in result.get("value", []):
                email = OutlookEmail(
                    id=email_data.get("id", ""),
                    conversation_id=email_data.get("conversationId", ""),
                    subject=email_data.get("subject", ""),
                    body_preview=email_data.get("bodyPreview", ""),
                    body=email_data.get("body", {}),
                    importance=email_data.get("importance", "normal"),
                    has_attachments=email_data.get("hasAttachments", False),
                    is_read=email_data.get("isRead", True),
                    is_draft=email_data.get("isDraft", False),
                    web_link=email_data.get("webLink", ""),
                    created_datetime=email_data.get("createdDateTime", ""),
                    last_modified_datetime=email_data.get("lastModifiedDateTime", ""),
                    received_datetime=email_data.get("receivedDateTime", ""),
                    sent_datetime=email_data.get("sentDateTime", ""),
                    from_address=email_data.get("from", {}),
                    to_recipients=email_data.get("toRecipients", []),
                    cc_recipients=email_data.get("ccRecipients", []),
                    bcc_recipients=email_data.get("bccRecipients", []),
                    reply_to=email_data.get("replyTo", []),
                    categories=email_data.get("categories", []),
                    flag=email_data.get("flag", {}),
                    internet_message_headers=email_data.get(
                        "internetMessageHeaders", []
                    ),
                    attachments=email_data.get("attachments", []),
                    metadata={
                        "accessed_at": datetime.now().isoformat(),
                        "source": "microsoft_graph",
                    },
                )
                emails.append(email)

            self.emails_cache[cache_key] = emails
            logger.info(f"Retrieved {len(emails)} emails for user {user_id}")
            return emails

        except Exception as e:
            logger.error(f"Error getting user emails: {e}")
            return []

    async def send_email_enhanced(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        body_type: str = "HTML",
        cc_recipients: List[str] = None,
        bcc_recipients: List[str] = None,
        importance: str = "normal",
        attachments: List[Dict[str, Any]] = None,
        save_to_sent_items: bool = True,
    ) -> bool:
        """Send email with enhanced options"""
        try:
            endpoint = f"users/{user_id}/sendMail"

            message = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": body_type, "content": body},
                    "toRecipients": [
                        {"emailAddress": {"address": addr}} for addr in to_recipients
                    ],
                    "importance": importance,
                },
                "saveToSentItems": save_to_sent_items,
            }

            if cc_recipients:
                message["message"]["ccRecipients"] = [
                    {"emailAddress": {"address": addr}} for addr in cc_recipients
                ]

            if bcc_recipients:
                message["message"]["bccRecipients"] = [
                    {"emailAddress": {"address": addr}} for addr in bcc_recipients
                ]

            if attachments:
                message["message"]["attachments"] = attachments

            result = await self._make_graph_request(
                "POST", endpoint, user_id, data=message
            )

            logger.info(f"Email sent successfully for user {user_id}")

            # Clear email cache
            self._clear_email_cache()

            return True

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    async def create_calendar_event_enhanced(
        self,
        user_id: str,
        subject: str,
        start_time: str,
        end_time: str,
        location: str = None,
        body: str = None,
        attendees: List[str] = None,
        is_all_day: bool = False,
        sensitivity: str = "normal",
        show_as: str = "busy",
        reminder_minutes: int = 15,
    ) -> Optional[OutlookCalendarEvent]:
        """Create calendar event with enhanced options"""
        try:
            endpoint = f"users/{user_id}/events"

            event_data = {
                "subject": subject,
                "start": {"dateTime": start_time, "timeZone": "UTC"},
                "end": {"dateTime": end_time, "timeZone": "UTC"},
                "isAllDay": is_all_day,
                "sensitivity": sensitivity,
                "showAs": show_as,
                "reminderMinutesBeforeStart": reminder_minutes,
            }

            if location:
                event_data["location"] = {"displayName": location}

            if body:
                event_data["body"] = {"contentType": "HTML", "content": body}

            if attendees:
                event_data["attendees"] = [
                    {"emailAddress": {"address": addr}} for addr in attendees
                ]

            result = await self._make_graph_request(
                "POST", endpoint, user_id, data=event_data
            )

            if not result:
                return None

            event = OutlookCalendarEvent(
                id=result.get("id", ""),
                subject=result.get("subject", ""),
                body_preview=result.get("bodyPreview", ""),
                body=result.get("body", {}),
                start=result.get("start", {}),
                end=result.get("end", {}),
                location=result.get("location", {}),
                locations=result.get("locations", []),
                attendees=result.get("attendees", []),
                organizer=result.get("organizer", {}),
                is_all_day=result.get("isAllDay", False),
                is_cancelled=result.get("isCancelled", False),
                is_organizer=result.get("isOrganizer", True),
                response_requested=result.get("responseRequested", True),
                response_status=result.get("responseStatus", {}),
                sensitivity=result.get("sensitivity", "normal"),
                show_as=result.get("showAs", "busy"),
                type=result.get("type", "singleInstance"),
                web_link=result.get("webLink", ""),
                online_meeting=result.get("onlineMeeting", {}),
                recurrence=result.get("recurrence", {}),
                reminder_minutes_before_start=result.get(
                    "reminderMinutesBeforeStart", 15
                ),
                categories=result.get("categories", []),
                extensions=result.get("extensions", []),
                metadata={
                    "created_at": datetime.now().isoformat(),
                    "source": "microsoft_graph",
                },
            )

            # Clear events cache
            self._clear_events_cache()

            logger.info(f"Calendar event created: {event.id}")
            return event

        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None

    async def create_contact_enhanced(
        self,
        user_id: str,
        display_name: str,
        given_name: str = None,
        surname: str = None,
        email_addresses: List[str] = None,
        business_phones: List[str] = None,
        mobile_phone: str = None,
        job_title: str = None,
        company_name: str = None,
    ) -> Optional[OutlookContact]:
        """Create contact with enhanced options"""
        try:
            endpoint = f"users/{user_id}/contacts"

            contact_data = {"displayName": display_name}

            if given_name:
                contact_data["givenName"] = given_name

            if surname:
                contact_data["surname"] = surname

            if email_addresses:
                contact_data["emailAddresses"] = [
                    {"address": email, "name": display_name}
                    for email in email_addresses
                ]

            if business_phones:
                contact_data["businessPhones"] = business_phones

            if mobile_phone:
                contact_data["mobilePhone"] = mobile_phone

            if job_title:
                contact_data["jobTitle"] = job_title

            if company_name:
                contact_data["companyName"] = company_name

            result = await self._make_graph_request(
                "POST", endpoint, user_id, data=contact_data
            )

            if not result:
                return None

            contact = OutlookContact(
                id=result.get("id", ""),
                display_name=result.get("displayName", ""),
                given_name=result.get("givenName", ""),
                surname=result.get("surname", ""),
                job_title=result.get("jobTitle", ""),
                department=result.get("department", ""),
                company_name=result.get("companyName", ""),
                business_phones=result.get("businessPhones", []),
                mobile_phone=result.get("mobilePhone", ""),
                home_phones=result.get("homePhones", []),
                email_addresses=result.get("emailAddresses", []),
                im_addresses=result.get("imAddresses", []),
                home_address=result.get("homeAddress", {}),
                business_address=result.get("businessAddress", {}),
                other_address=result.get("otherAddress", {}),
                personal_notes=result.get("personalNotes", ""),
                birthday=result.get("birthday", ""),
                anniversary=result.get("anniversary", ""),
                spouse_name=result.get("spouseName", ""),
                children=result.get("children", []),
                manager=result.get("manager", ""),
                assistant_name=result.get("assistantName", ""),
                profession=result.get("profession", ""),
                categories=result.get("categories", []),
                created_date_time=result.get("createdDateTime", ""),
                last_modified_date_time=result.get("lastModifiedDateTime", ""),
                metadata={
                    "created_at": datetime.now().isoformat(),
                    "source": "microsoft_graph",
                },
            )

            # Clear contacts cache
            self._clear_contacts_cache()

            logger.info(f"Contact created: {contact.id}")
            return contact

        except Exception as e:
            logger.error(f"Error creating contact: {e}")
            return None

    async def create_task_enhanced(
        self,
        user_id: str,
        subject: str,
        body: str = None,
        importance: str = "normal",
        due_date: str = None,
        start_date: str = None,
        reminder_date: str = None,
        categories: List[str] = None,
    ) -> Optional[OutlookTask]:
        """Create task with enhanced options"""
        try:
            endpoint = f"users/{user_id}/tasks"

            task_data = {"subject": subject, "importance": importance}

            if body:
                task_data["body"] = {"contentType": "HTML", "content": body}

            if due_date:
                task_data["dueDateTime"] = {"dateTime": due_date, "timeZone": "UTC"}

            if start_date:
                task_data["startDateTime"] = {"dateTime": start_date, "timeZone": "UTC"}

            if reminder_date:
                task_data["reminderDateTime"] = {
                    "dateTime": reminder_date,
                    "timeZone": "UTC",
                }
                task_data["isReminderOn"] = True

            if categories:
                task_data["categories"] = categories

            result = await self._make_graph_request(
                "POST", endpoint, user_id, data=task_data
            )

            if not result:
                return None

            task = OutlookTask(
                id=result.get("id", ""),
                subject=result.get("subject", ""),
                body=result.get("body", {}),
                importance=result.get("importance", "normal"),
                status=result.get("status", "notStarted"),
                completed_date_time=result.get("completedDateTime", {}),
                due_date_time=result.get("dueDateTime", {}),
                start_date_time=result.get("startDateTime", {}),
                created_date_time=result.get("createdDateTime", ""),
                last_modified_date_time=result.get("lastModifiedDateTime", ""),
                is_reminder_on=result.get("isReminderOn", False),
                reminder_date_time=result.get("reminderDateTime", {}),
                categories=result.get("categories", []),
                assigned_to=result.get("assignedTo", ""),
                parent_folder_id=result.get("parentFolderId", ""),
                conversation_id=result.get("conversationId", ""),
                conversation_index=result.get("conversationIndex", ""),
                flag=result.get("flag", {}),
                metadata={
                    "created_at": datetime.now().isoformat(),
                    "source": "microsoft_graph",
                },
            )

            # Clear tasks cache
            self._clear_tasks_cache()

            logger.info(f"Task created: {task.id}")
            return task

        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None

    async def get_user_folders(
        self, user_id: str, folder_type: str = None
    ) -> List[OutlookFolder]:
        """Get user email folders"""
        try:
            cache_key = f"{user_id}:{folder_type or 'all'}"
            if cache_key in self.folders_cache:
                return self.folders_cache[cache_key]

            endpoint = f"users/{user_id}/mailFolders"
            params = {}

            if folder_type:
                params["$filter"] = f"displayName eq '{folder_type}'"

            result = await self._make_graph_request(
                "GET", endpoint, user_id, params=params
            )

            folders = []
            for folder_data in result.get("value", []):
                folder = OutlookFolder(
                    id=folder_data.get("id", ""),
                    display_name=folder_data.get("displayName", ""),
                    parent_folder_id=folder_data.get("parentFolderId", ""),
                    child_folder_count=folder_data.get("childFolderCount", 0),
                    unread_item_count=folder_data.get("unreadItemCount", 0),
                    total_item_count=folder_data.get("totalItemCount", 0),
                    folder_type=folder_data.get("folderType", ""),
                    is_hidden=folder_data.get("isHidden", False),
                    well_known_name=folder_data.get("wellKnownName", ""),
                    metadata={
                        "accessed_at": datetime.now().isoformat(),
                        "source": "microsoft_graph",
                    },
                )
                folders.append(folder)

            self.folders_cache[cache_key] = folders
            logger.info(f"Retrieved {len(folders)} folders for user {user_id}")
            return folders

        except Exception as e:
            logger.error(f"Error getting user folders: {e}")
            return []

    async def search_entities_enhanced(
        self,
        user_id: str,
        query: str,
        entity_types: List[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Enhanced search across multiple entity types"""
        try:
            endpoint = f"users/{user_id}/search/query"

            search_data = {
                "requests": [
                    {
                        "entityTypes": entity_types or ["message", "event", "contact"],
                        "query": {"queryString": query},
                        "from": 0,
                        "size": max_results,
                    }
                ]
            }

            result = await self._make_graph_request(
                "POST", endpoint, user_id, data=search_data
            )

            search_results = []
            for hit in result.get("value", []):
                for hit_result in hit.get("hitsContainers", []):
                    for search_hit in hit_result.get("hits", []):
                        search_results.append(
                            {
                                "id": search_hit.get("id", ""),
                                "entityType": search_hit.get("resource", {})
                                .get("@odata.type", "")
                                .replace("#microsoft.graph.", ""),
                                "subject": search_hit.get("resource", {}).get(
                                    "subject", ""
                                ),
                                "webLink": search_hit.get("resource", {}).get(
                                    "webLink", ""
                                ),
                                "score": search_hit.get("summary", {}).get("score", 0),
                            }
                        )

            logger.info(
                f"Search completed: {len(search_results)} results for query '{query}'"
            )
            return search_results

        except Exception as e:
            logger.error(f"Error performing enhanced search: {e}")
            return []

    async def get_user_profile_enhanced(self, user_id: str) -> Optional[OutlookUser]:
        """Get enhanced user profile information"""
        try:
            cache_key = f"profile:{user_id}"
            if cache_key in self.users_cache:
                return self.users_cache[cache_key]

            endpoint = f"users/{user_id}"
            result = await self._make_graph_request("GET", endpoint, user_id)

            if not result:
                return None

            profile = OutlookUser(
                id=result.get("id", ""),
                display_name=result.get("displayName", ""),
                email=result.get("mail", ""),
                job_title=result.get("jobTitle", ""),
                department=result.get("department", ""),
                office_location=result.get("officeLocation", ""),
                mobile_phone=result.get("mobilePhone", ""),
                business_phones=result.get("businessPhones", []),
                user_principal_name=result.get("userPrincipalName", ""),
                mail=result.get("mail", ""),
                account_enabled=result.get("accountEnabled", True),
                user_type=result.get("userType", ""),
                preferred_language=result.get("preferredLanguage", ""),
                timezone=result.get("mailboxSettings", {}).get("timeZone", ""),
                usage_location=result.get("usageLocation", ""),
                metadata={
                    "accessed_at": datetime.now().isoformat(),
                    "source": "microsoft_graph",
                },
            )

            self.users_cache[cache_key] = profile
            logger.info(f"Retrieved enhanced profile for user {user_id}")
            return profile

        except Exception as e:
            logger.error(f"Error getting enhanced user profile: {e}")
            return None

    async def get_upcoming_events(
        self, user_id: str, days: int = 7, max_results: int = 50
    ) -> List[OutlookCalendarEvent]:
        """Get upcoming calendar events"""
        try:
            cache_key = f"{user_id}:upcoming:{days}"
            if cache_key in self.events_cache:
                return self.events_cache[cache_key]

            start_date = datetime.now()
            end_date = start_date + timedelta(days=days)

            endpoint = f"users/{user_id}/calendar/calendarView"
            params = {
                "startDateTime": start_date.isoformat(),
                "endDateTime": end_date.isoformat(),
                "$top": max_results,
                "$orderby": "start/dateTime",
            }

            result = await self._make_graph_request(
                "GET", endpoint, user_id, params=params
            )

            events = []
            for event_data in result.get("value", []):
                event = OutlookCalendarEvent(
                    id=event_data.get("id", ""),
                    subject=event_data.get("subject", ""),
                    body_preview=event_data.get("bodyPreview", ""),
                    body=event_data.get("body", {}),
                    start=event_data.get("start", {}),
                    end=event_data.get("end", {}),
                    location=event_data.get("location", {}),
                    locations=event_data.get("locations", []),
                    attendees=event_data.get("attendees", []),
                    organizer=event_data.get("organizer", {}),
                    is_all_day=event_data.get("isAllDay", False),
                    is_cancelled=event_data.get("isCancelled", False),
                    is_organizer=event_data.get("isOrganizer", True),
                    response_requested=event_data.get("responseRequested", True),
                    response_status=event_data.get("responseStatus", {}),
                    sensitivity=event_data.get("sensitivity", "normal"),
                    show_as=event_data.get("showAs", "busy"),
                    type=event_data.get("type", "singleInstance"),
                    web_link=event_data.get("webLink", ""),
                    online_meeting=event_data.get("onlineMeeting", {}),
                    recurrence=event_data.get("recurrence", {}),
                    reminder_minutes_before_start=event_data.get(
                        "reminderMinutesBeforeStart", 15
                    ),
                    categories=event_data.get("categories", []),
                    extensions=event_data.get("extensions", []),
                    metadata={
                        "accessed_at": datetime.now().isoformat(),
                        "source": "microsoft_graph",
                    },
                )
                events.append(event)

            self.events_cache[cache_key] = events
            logger.info(f"Retrieved {len(events)} upcoming events for user {user_id}")
            return events

        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            return []

    async def get_unread_email_count(self, user_id: str) -> int:
        """Get count of unread emails"""
        try:
            endpoint = f"users/{user_id}/mailFolders/inbox"
            params = {"$select": "unreadItemCount"}

            result = await self._make_graph_request(
                "GET", endpoint, user_id, params=params
            )

            count = result.get("unreadItemCount", 0)
            logger.info(f"Retrieved unread email count for user {user_id}: {count}")
            return count

        except Exception as e:
            logger.error(f"Error getting unread email count: {e}")
            return 0

    async def mark_emails_read(self, user_id: str, email_ids: List[str]) -> bool:
        """Mark emails as read"""
        try:
            for email_id in email_ids:
                endpoint = f"users/{user_id}/messages/{email_id}"
                update_data = {"isRead": True}
                result = await self._make_graph_request(
                    "PATCH", endpoint, user_id, data=update_data
                )
                if not result:
                    logger.error(f"Failed to mark email {email_id} as read")
                    return False

            # Clear email cache
            self._clear_email_cache()

            logger.info(f"Marked {len(email_ids)} emails as read for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error marking emails as read: {e}")
            return False

    # Cache management methods
    def _clear_cache(self):
        """Clear all caches"""
        self.users_cache.clear()
        self.emails_cache.clear()
        self.events_cache.clear()
        self.contacts_cache.clear()
        self.tasks_cache.clear()
        self.folders_cache.clear()

    def _clear_email_cache(self):
        """Clear email cache"""
        self.emails_cache.clear()

    def _clear_events_cache(self):
        """Clear events cache"""
        self.events_cache.clear()

    def _clear_contacts_cache(self):
        """Clear contacts cache"""
        self.contacts_cache.clear()

    def _clear_tasks_cache(self):
        """Clear tasks cache"""
        self.tasks_cache.clear()

    def _clear_folders_cache(self):
        """Clear folders cache"""
        self.folders_cache.clear()

    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "service": "outlook",
            "version": "2.0.0",
            "capabilities": [
                "email_management",
                "calendar_management",
                "contact_management",
                "task_management",
                "search_and_filtering",
                "folder_management",
                "attachment_handling",
                "event_reminders",
                "enhanced_search",
                "upcoming_events",
                "unread_count",
                "mark_as_read",
            ],
            "api_endpoints": [
                "/api/integrations/outlook/health",
                "/api/integrations/outlook/emails/enhanced",
                "/api/integrations/outlook/emails/send/enhanced",
                "/api/integrations/outlook/calendar/events/enhanced",
                "/api/integrations/outlook/contacts/enhanced",
                "/api/integrations/outlook/tasks/enhanced",
                "/api/integrations/outlook/folders",
                "/api/integrations/outlook/search/enhanced",
                "/api/integrations/outlook/user/profile/enhanced",
                "/api/integrations/outlook/calendar/events/upcoming",
                "/api/integrations/outlook/emails/unread/count",
                "/api/integrations/outlook/emails/mark-read",
                "/api/integrations/outlook/info",
            ],
            "initialized_at": datetime.now().isoformat(),
        }
