"""
Enhanced Google Suite Services Implementation
Complete Google Workspace integration with advanced features
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import aiohttp
from cryptography.fernet import Fernet

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class GoogleUser:
    """Google user information"""
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    verified_email: bool = False
    hd: Optional[str] = None  # G Suite domain

@dataclass
class GoogleCalendar:
    """Google Calendar information"""
    id: str
    summary: str
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = 'UTC'
    primary: bool = False
    access_role: str = 'reader'
    color_id: Optional[str] = None
    background_color: Optional[str] = None
    foreground_color: Optional[str] = None

@dataclass
class GoogleCalendarEvent:
    """Google Calendar Event information"""
    id: str
    summary: str
    start: Dict[str, Any]
    end: Dict[str, Any]
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[Dict[str, Any]]] = None
    creator: Optional[Dict[str, Any]] = None
    organizer: Optional[Dict[str, Any]] = None
    hangout_link: Optional[str] = None
    visibility: str = 'default'
    transparency: str = 'opaque'
    i_cal_uid: Optional[str] = None
    sequence: int = 0
    recurrence: Optional[List[str]] = None
    recurring_event_id: Optional[str] = None
    original_start_time: Optional[Dict[str, Any]] = None
    status: str = 'confirmed'
    color_id: Optional[str] = None

@dataclass
class GmailMessage:
    """Gmail message information"""
    id: str
    thread_id: str
    snippet: str
    subject: str
    from_email: str
    to_emails: List[str]
    date: str
    is_read: bool = False
    is_starred: bool = False
    is_important: bool = False
    labels: List[str] = None
    attachments: List[Dict[str, Any]] = None
    body: Optional[str] = None

@dataclass
class GmailLabel:
    """Gmail label information"""
    id: str
    name: str
    message_list_visibility: str = 'show'
    label_list_visibility: str = 'labelShow'
    message_total: int = 0
    message_unread: int = 0
    threads_total: int = 0
    threads_unread: int = 0
    color: Optional[Dict[str, str]] = None

@dataclass
class GoogleDriveFile:
    """Google Drive file information"""
    id: str
    name: str
    mime_type: str
    size: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    parents: List[str] = None
    webViewLink: Optional[str] = None
    webContentLink: Optional[str] = None
    owners: List[Dict[str, Any]] = None
    permissions: List[Dict[str, Any]] = None
    thumbnailLink: Optional[str] = None
    is_folder: bool = False
    shared: bool = False

@dataclass
class GmailFilter:
    """Gmail filter information"""
    id: str
    criteria: Dict[str, Any]
    action: Dict[str, Any]

@dataclass
class GmailSettings:
    """Gmail settings information"""
    auto_forwarding: Optional[Dict[str, Any]] = None
    imap_enabled: bool = False
    pop_enabled: bool = False
    language: str = 'en'
    display_language: str = 'en'
    signature: Optional[str] = None
    vacation_settings: Optional[Dict[str, Any]] = None

class GoogleServicesEnhanced:
    """Enhanced Google Services implementation with advanced capabilities"""
    
    def __init__(self):
        self.encryption_key = os.getenv('ATOM_OAUTH_ENCRYPTION_KEY')
        self.mock_mode = not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET')
        self.base_urls = {
            'calendar': 'https://www.googleapis.com/calendar/v3',
            'gmail': 'https://www.googleapis.com/gmail/v1',
            'drive': 'https://www.googleapis.com/drive/v3',
            'people': 'https://people.googleapis.com/v1',
            'oauth': 'https://oauth2.googleapis.com'
        }
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _make_request(self, service: str, endpoint: str, method: str = 'GET', 
                           access_token: str = None, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Google API"""
        if self.mock_mode:
            return await self._mock_response(service, endpoint, method, **kwargs)
        
        session = await self._get_session()
        url = f"{self.base_urls[service]}/{endpoint}"
        headers = {'Authorization': f'Bearer {access_token}'} if access_token else {}
        
        try:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Google API error: {response.status} - {error_text}")
                    return {"error": error_text, "status": response.status}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}

    async def _mock_response(self, service: str, endpoint: str, method: str, **kwargs) -> Dict[str, Any]:
        """Mock response for development/testing"""
        if service == 'calendar' and 'calendars' in endpoint:
            if method == 'GET':
                return {
                    "items": [
                        {
                            "id": "primary",
                            "summary": "Primary Calendar",
                            "primary": True,
                            "accessRole": "owner",
                            "timeZone": "America/New_York"
                        }
                    ]
                }
            elif method == 'POST':
                return {
                    "id": "new_calendar_id",
                    "summary": kwargs.get('json', {}).get('summary', 'New Calendar'),
                    "timeZone": "America/New_York"
                }
        
        elif service == 'calendar' and 'events' in endpoint:
            return {
                "items": [
                    {
                        "id": "event_123",
                        "summary": "Team Meeting",
                        "start": {"dateTime": "2024-01-15T10:00:00-05:00"},
                        "end": {"dateTime": "2024-01-15T11:00:00-05:00"},
                        "status": "confirmed"
                    }
                ]
            }
        
        elif service == 'gmail' and 'messages' in endpoint:
            return {
                "messages": [
                    {"id": "msg_123", "threadId": "thread_123"},
                    {"id": "msg_456", "threadId": "thread_456"}
                ],
                "resultSizeEstimate": 2
            }
        
        elif service == 'drive' and 'files' in endpoint:
            return {
                "files": [
                    {
                        "id": "file_123",
                        "name": "Document.pdf",
                        "mimeType": "application/pdf",
                        "size": "1024000"
                    }
                ]
            }
        
        return {"mock": True, "service": service, "endpoint": endpoint}

    async def get_user_info(self, access_token: str) -> Optional[GoogleUser]:
        """Get Google user information"""
        data = await self._make_request('oauth', 'userinfo', access_token=access_token)
        if 'error' in data:
            return None
        
        return GoogleUser(
            id=data.get('id', ''),
            email=data.get('email', ''),
            name=data.get('name', ''),
            picture=data.get('picture'),
            verified_email=data.get('verified_email', False),
            hd=data.get('hd')
        )

    # Enhanced Calendar Methods
    async def list_calendars(self, access_token: str) -> List[GoogleCalendar]:
        """List user's calendars with enhanced metadata"""
        data = await self._make_request('calendar', 'users/me/calendarList', access_token=access_token)
        if 'error' in data:
            return []
        
        calendars = []
        for item in data.get('items', []):
            calendar = GoogleCalendar(
                id=item.get('id', ''),
                summary=item.get('summary', ''),
                description=item.get('description'),
                location=item.get('location'),
                timezone=item.get('timeZone', 'UTC'),
                primary=item.get('primary', False),
                access_role=item.get('accessRole', 'reader'),
                color_id=item.get('colorId'),
                background_color=item.get('backgroundColor'),
                foreground_color=item.get('foregroundColor')
            )
            calendars.append(calendar)
        
        return calendars

    async def create_calendar(self, access_token: str, summary: str, 
                             timezone: str = None, description: str = None) -> Optional[GoogleCalendar]:
        """Create a new calendar"""
        payload = {
            'summary': summary,
            'timeZone': timezone or 'America/New_York'
        }
        if description:
            payload['description'] = description
        
        data = await self._make_request('calendar', 'calendars', method='POST', 
                                       access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        return GoogleCalendar(
            id=data.get('id', ''),
            summary=data.get('summary', ''),
            description=data.get('description'),
            timezone=data.get('timeZone', 'UTC'),
            primary=data.get('primary', False),
            access_role='owner'
        )

    async def delete_calendar(self, access_token: str, calendar_id: str) -> bool:
        """Delete a calendar"""
        data = await self._make_request('calendar', f'calendars/{calendar_id}', 
                                       method='DELETE', access_token=access_token)
        return 'error' not in data

    async def update_calendar(self, access_token: str, calendar_id: str, 
                            updates: Dict[str, Any]) -> Optional[GoogleCalendar]:
        """Update calendar metadata"""
        data = await self._make_request('calendar', f'calendars/{calendar_id}', 
                                       method='PATCH', access_token=access_token, json=updates)
        if 'error' in data:
            return None
        
        return GoogleCalendar(
            id=data.get('id', calendar_id),
            summary=data.get('summary', ''),
            description=data.get('description'),
            timezone=data.get('timeZone', 'UTC'),
            primary=data.get('primary', False)
        )

    async def get_calendar_acl(self, access_token: str, calendar_id: str) -> List[Dict[str, Any]]:
        """Get calendar access control list"""
        data = await self._make_request('calendar', f'calendars/{calendar_id}/acl', 
                                       access_token=access_token)
        return data.get('items', [])

    async def share_calendar(self, access_token: str, calendar_id: str, 
                           email: str, role: str = 'reader') -> bool:
        """Share calendar with user"""
        payload = {
            'scope': {
                'type': 'user',
                'value': email
            },
            'role': role
        }
        
        data = await self._make_request('calendar', f'calendars/{calendar_id}/acl', 
                                       method='POST', access_token=access_token, json=payload)
        return 'error' not in data

    async def list_events(self, access_token: str, calendar_id: str = 'primary',
                         time_min: str = None, time_max: str = None, 
                         q: str = None, max_results: int = 100) -> List[GoogleCalendarEvent]:
        """List calendar events with advanced filtering"""
        params = {'maxResults': max_results, 'singleEvents': 'true', 'orderBy': 'startTime'}
        
        if time_min:
            params['timeMin'] = time_min
        if time_max:
            params['timeMax'] = time_max
        if q:
            params['q'] = q
        
        data = await self._make_request('calendar', f'calendars/{calendar_id}/events', 
                                       access_token=access_token, params=params)
        if 'error' in data:
            return []
        
        events = []
        for item in data.get('items', []):
            event = GoogleCalendarEvent(
                id=item.get('id', ''),
                summary=item.get('summary', ''),
                start=item.get('start', {}),
                end=item.get('end', {}),
                description=item.get('description'),
                location=item.get('location'),
                attendees=item.get('attendees'),
                creator=item.get('creator'),
                organizer=item.get('organizer'),
                hangout_link=item.get('hangoutLink'),
                visibility=item.get('visibility', 'default'),
                transparency=item.get('transparency', 'opaque'),
                i_cal_uid=item.get('iCalUID'),
                sequence=item.get('sequence', 0),
                recurrence=item.get('recurrence'),
                recurring_event_id=item.get('recurringEventId'),
                original_start_time=item.get('originalStartTime'),
                status=item.get('status', 'confirmed'),
                color_id=item.get('colorId')
            )
            events.append(event)
        
        return events

    async def create_event(self, access_token: str, calendar_id: str, 
                         event_data: Dict[str, Any]) -> Optional[GoogleCalendarEvent]:
        """Create a new calendar event"""
        data = await self._make_request('calendar', f'calendars/{calendar_id}/events', 
                                       method='POST', access_token=access_token, json=event_data)
        if 'error' in data:
            return None
        
        return GoogleCalendarEvent(
            id=data.get('id', ''),
            summary=data.get('summary', ''),
            start=data.get('start', {}),
            end=data.get('end', {}),
            description=data.get('description'),
            location=data.get('location'),
            attendees=data.get('attendees'),
            creator=data.get('creator'),
            organizer=data.get('organizer'),
            hangout_link=data.get('hangoutLink'),
            visibility=data.get('visibility', 'default'),
            transparency=data.get('transparency', 'opaque'),
            i_cal_uid=data.get('iCalUID'),
            sequence=data.get('sequence', 0),
            recurrence=data.get('recurrence'),
            status=data.get('status', 'confirmed'),
            color_id=data.get('colorId')
        )

    async def create_recurring_event(self, access_token: str, calendar_id: str,
                                   base_event: Dict[str, Any], 
                                   recurrence_rules: List[str]) -> Optional[GoogleCalendarEvent]:
        """Create a recurring event"""
        event_data = {
            **base_event,
            'recurrence': recurrence_rules
        }
        
        return await self.create_event(access_token, calendar_id, event_data)

    async def get_free_busy(self, access_token: str, user_ids: List[str],
                          time_min: str, time_max: str) -> Dict[str, Any]:
        """Get free/busy information for users"""
        payload = {
            'timeMin': time_min,
            'timeMax': time_max,
            'items': [{'id': user_id} for user_id in user_ids]
        }
        
        data = await self._make_request('calendar', 'freeBusy', 
                                       method='POST', access_token=access_token, json=payload)
        return data

    # Enhanced Gmail Methods
    async def list_messages(self, access_token: str, query: str = None,
                          max_results: int = 50, label_ids: List[str] = None) -> List[GmailMessage]:
        """List Gmail messages with advanced filtering"""
        params = {'maxResults': max_results}
        
        if query:
            params['q'] = query
        if label_ids:
            params['labelIds'] = label_ids
        
        data = await self._make_request('gmail', 'users/me/messages', 
                                       access_token=access_token, params=params)
        if 'error' in data:
            return []
        
        messages = []
        for msg_ref in data.get('messages', []):
            msg_data = await self.get_message(access_token, msg_ref['id'])
            if msg_data:
                messages.append(msg_data)
        
        return messages

    async def get_message(self, access_token: str, message_id: str, 
                         format: str = 'metadata') -> Optional[GmailMessage]:
        """Get Gmail message details"""
        params = {'format': format, 'metadataHeaders': ['From', 'To', 'Subject', 'Date']}
        
        data = await self._make_request('gmail', f'users/me/messages/{message_id}', 
                                       access_token=access_token, params=params)
        if 'error' in data:
            return None
        
        headers = {h['name']: h['value'] for h in data.get('payload', {}).get('headers', [])}
        
        return GmailMessage(
            id=data.get('id', ''),
            thread_id=data.get('threadId', ''),
            snippet=data.get('snippet', ''),
            subject=headers.get('Subject', ''),
            from_email=headers.get('From', ''),
            to_emails=[email.strip() for email in headers.get('To', '').split(',')],
            date=headers.get('Date', ''),
            is_read='UNREAD' not in data.get('labelIds', []),
            is_starred='STARRED' in data.get('labelIds', []),
            is_important='IMPORTANT' in data.get('labelIds', []),
            labels=data.get('labelIds', []),
            attachments=self._extract_attachments(data.get('payload', {}))
        )

    async def send_message(self, access_token: str, to_emails: List[str],
                         subject: str, body: str, cc_emails: List[str] = None,
                         bcc_emails: List[str] = None, is_html: bool = False) -> Dict[str, Any]:
        """Send Gmail message"""
        # Create message
        message_data = {
            'raw': self._create_message_raw(to_emails, subject, body, 
                                           cc_emails, bcc_emails, is_html)
        }
        
        data = await self._make_request('gmail', 'users/me/messages/send', 
                                       method='POST', access_token=access_token, json=message_data)
        return data

    async def create_label(self, access_token: str, name: str, 
                         message_visibility: str = 'show',
                         label_visibility: str = 'labelShow',
                         color: Dict[str, str] = None) -> Optional[GmailLabel]:
        """Create Gmail label"""
        payload = {
            'name': name,
            'messageListVisibility': message_visibility,
            'labelListVisibility': label_visibility
        }
        if color:
            payload['color'] = color
        
        data = await self._make_request('gmail', 'users/me/labels', 
                                       method='POST', access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        return GmailLabel(
            id=data.get('id', ''),
            name=data.get('name', ''),
            message_list_visibility=data.get('messageListVisibility', 'show'),
            label_list_visibility=data.get('labelListVisibility', 'labelShow'),
            message_total=data.get('messagesTotal', 0),
            message_unread=data.get('messagesUnread', 0),
            threads_total=data.get('threadsTotal', 0),
            threads_unread=data.get('threadsUnread', 0),
            color=data.get('color')
        )

    async def get_settings(self, access_token: str) -> Optional[GmailSettings]:
        """Get Gmail settings"""
        settings = GmailSettings()
        
        # Auto-forwarding
        auto_forwarding = await self._make_request('gmail', 'users/me/settings/autoForwarding', 
                                                  access_token=access_token)
        if 'error' not in auto_forwarding:
            settings.auto_forwarding = auto_forwarding
        
        # IMAP settings
        imap_settings = await self._make_request('gmail', 'users/me/settings/imap', 
                                               access_token=access_token)
        if 'error' not in imap_settings:
            settings.imap_enabled = imap_settings.get('enabled', False)
        
        # POP settings
        pop_settings = await self._make_request('gmail', 'users/me/settings/pop', 
                                              access_token=access_token)
        if 'error' not in pop_settings:
            settings.pop_enabled = pop_settings.get('enabled', False)
        
        # Language settings
        language_data = await self._make_request('gmail', 'users/me/settings/language', 
                                               access_token=access_token)
        if 'error' not in language_data:
            settings.language = language_data.get('language', 'en')
        
        return settings

    # Enhanced Google Drive Methods
    async def list_files(self, access_token: str, query: str = None,
                       page_size: int = 100, fields: str = None) -> List[GoogleDriveFile]:
        """List Google Drive files with advanced search"""
        params = {'pageSize': page_size}
        
        if query:
            params['q'] = query
        if not fields:
            fields = 'files(id,name,mimeType,size,createdTime,modifiedTime,parents,webViewLink,webContentLink,owners,permissions,thumbnailLink,shared)'
        params['fields'] = fields
        
        data = await self._make_request('drive', 'files', access_token=access_token, params=params)
        if 'error' in data:
            return []
        
        files = []
        for item in data.get('files', []):
            file_obj = GoogleDriveFile(
                id=item.get('id', ''),
                name=item.get('name', ''),
                mime_type=item.get('mimeType', ''),
                size=item.get('size'),
                created_time=item.get('createdTime'),
                modified_time=item.get('modifiedTime'),
                parents=item.get('parents', []),
                webViewLink=item.get('webViewLink'),
                webContentLink=item.get('webContentLink'),
                owners=item.get('owners', []),
                permissions=item.get('permissions', []),
                thumbnailLink=item.get('thumbnailLink'),
                is_folder=item.get('mimeType') == 'application/vnd.google-apps.folder',
                shared=item.get('shared', False)
            )
            files.append(file_obj)
        
        return files

    async def upload_file(self, access_token: str, file_path: str, 
                         folder_id: str = None, file_name: str = None) -> Optional[GoogleDriveFile]:
        """Upload file to Google Drive"""
        # Implementation would involve multipart upload
        # This is a simplified version
        metadata = {'name': file_name or os.path.basename(file_path)}
        if folder_id:
            metadata['parents'] = [folder_id]
        
        # In real implementation, would handle actual file upload
        # For now, return mock response
        if self.mock_mode:
            return GoogleDriveFile(
                id='uploaded_file_id',
                name=file_name or 'uploaded_file',
                mime_type='application/octet-stream',
                created_time=datetime.now(timezone.utc).isoformat()
            )
        
        return None

    async def create_folder(self, access_token: str, name: str, 
                          parent_id: str = None) -> Optional[GoogleDriveFile]:
        """Create folder in Google Drive"""
        metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            metadata['parents'] = [parent_id]
        
        data = await self._make_request('drive', 'files', method='POST', 
                                       access_token=access_token, json=metadata)
        if 'error' in data:
            return None
        
        return GoogleDriveFile(
            id=data.get('id', ''),
            name=data.get('name', ''),
            mime_type=data.get('mimeType', ''),
            created_time=data.get('createdTime'),
            is_folder=True
        )

    async def share_file(self, access_token: str, file_id: str, 
                        email: str, role: str = 'reader') -> bool:
        """Share file with user"""
        payload = {
            'role': role,
            'type': 'user',
            'emailAddress': email
        }
        
        data = await self._make_request('drive', f'files/{file_id}/permissions', 
                                       method='POST', access_token=access_token, json=payload)
        return 'error' not in data

    def _create_message_raw(self, to_emails: List[str], subject: str, body: str,
                          cc_emails: List[str] = None, bcc_emails: List[str] = None,
                          is_html: bool = False) -> str:
        """Create raw message for Gmail API"""
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        if is_html:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'html'))
        else:
            msg = MIMEText(body)
        
        msg['To'] = ', '.join(to_emails)
        if cc_emails:
            msg['Cc'] = ', '.join(cc_emails)
        msg['Subject'] = subject
        
        return base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

    def _extract_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attachment information from message payload"""
        attachments = []
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    attachments.append({
                        'filename': part.get('filename'),
                        'mimeType': part.get('mimeType'),
                        'size': part.get('body', {}).get('size', 0),
                        'attachmentId': part.get('body', {}).get('attachmentId')
                    })
        
        return attachments

    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "service": "google-services-enhanced",
            "version": "2.0.0",
            "mock_mode": self.mock_mode,
            "capabilities": [
                "calendar_management",
                "event_crud",
                "recurring_events",
                "free_busy_lookup",
                "gmail_operations",
                "label_management",
                "settings_management",
                "drive_operations",
                "file_sharing",
                "folder_operations"
            ],
            "base_urls": self.base_urls
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None

# Singleton instance
google_services_enhanced = GoogleServicesEnhanced()

# Export main class and instance
__all__ = [
    'GoogleServicesEnhanced',
    'google_services_enhanced',
    'GoogleUser',
    'GoogleCalendar', 
    'GoogleCalendarEvent',
    'GmailMessage',
    'GmailLabel',
    'GoogleDriveFile',
    'GmailFilter',
    'GmailSettings'
]