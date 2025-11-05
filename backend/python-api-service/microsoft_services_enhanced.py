"""
Enhanced Microsoft Services Implementation
Complete Microsoft 365 integration with advanced features
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
class MicrosoftUser:
    """Microsoft user information"""
    id: str
    displayName: str
    mail: str
    userPrincipalName: str
    jobTitle: Optional[str] = None
    officeLocation: Optional[str] = None
    businessPhones: List[str] = None
    mobilePhone: Optional[str] = None

@dataclass
class OutlookEmail:
    """Outlook email information"""
    id: str
    subject: str
    from_address: Dict[str, str]
    to_addresses: List[Dict[str, str]]
    cc_addresses: List[Dict[str, str]] = None
    bcc_addresses: List[Dict[str, str]] = None
    body: str
    bodyContentType: str = 'text'
    receivedDateTime: str
    sentDateTime: str = None
    isRead: bool = False
    isDraft: bool = False
    hasAttachments: bool = False
    importance: str = 'normal'
    conversationId: str = None
    webLink: str = None

@dataclass
class OutlookCalendar:
    """Outlook calendar information"""
    id: str
    name: str
    owner: Dict[str, str]
    canEdit: bool = False
    canView: bool = True
    isShared: bool = False
    isDefaultCalendar: bool = False
    color: str = None
    changeKey: str = None

@dataclass
class OutlookEvent:
    """Outlook calendar event information"""
    id: str
    subject: str
    start: Dict[str, str]
    end: Dict[str, str]
    body: str = None
    bodyContentType: str = 'text'
    location: Dict[str, str] = None
    attendees: List[Dict[str, Any]] = None
    organizer: Dict[str, str] = None
    isAllDay: bool = False
    sensitivity: str = 'normal'
    showAs: str = 'busy'
    responseStatus: Dict[str, str] = None
    recurrence: Dict[str, Any] = None
    seriesMasterId: str = None
    occurrenceId: str = None
    isCancelled: bool = False
    isOrganizer: bool = False
    onlineMeetingUrl: str = None

@dataclass
class OutlookContact:
    """Outlook contact information"""
    id: str
    displayName: str
    givenName: str = None
    surname: str = None
    emailAddresses: List[Dict[str, str]] = None
    businessPhones: List[str] = None
    mobilePhone: str = None
    homePhones: List[str] = None
    company_name: str = None
    department: str = None
    jobTitle: str = None
    officeLocation: str = None
    addresses: List[Dict[str, Any]] = None

@dataclass
class OneDriveFile:
    """OneDrive file information"""
    id: str
    name: str
    webUrl: str
    size: int = 0
    createdDateTime: str = None
    lastModifiedDateTime: str = None
    parentReference: Dict[str, str] = None
    file: Dict[str, Any] = None
    folder: Dict[str, Any] = None
    mimeType: str = None
    shared: bool = False
    createdBy: Dict[str, Any] = None
    lastModifiedBy: Dict[str, Any] = None
    @odata_type: str = None

@dataclass
class OneDriveFolder:
    """OneDrive folder information"""
    id: str
    name: str
    webUrl: str
    childCount: int = 0
    createdDateTime: str = None
    lastModifiedDateTime: str = None
    parentReference: Dict[str, str] = None
    shared: bool = False
    createdBy: Dict[str, Any] = None
    lastModifiedBy: Dict[str, Any] = None

@dataclass
class TeamsChannel:
    """Microsoft Teams channel information"""
    id: str
    displayName: str
    description: str = None
    isFavoriteByDefault: bool = False
    membershipType: str = 'standard'
    email: str = None
    webUrl: str = None
    tenantId: str = None

@dataclass
class TeamsMessage:
    """Microsoft Teams message information"""
    id: str
    messageType: str = 'message'
    createdDateTime: str = None
    lastModifiedDateTime: str = None
    subject: str = None
    summary: str = None
    importance: str = 'normal'
    locale: str = 'en-us'
    webUrl: str = None
    from_user: Dict[str, str] = None
    body: Dict[str, str] = None
    attachments: List[Dict[str, Any]] = None
    mentions: List[Dict[str, Any]] = None
    replies: List[Dict[str, Any]] = None

class MicrosoftServicesEnhanced:
    """Enhanced Microsoft Services implementation with advanced capabilities"""
    
    def __init__(self):
        self.encryption_key = os.getenv('ATOM_OAUTH_ENCRYPTION_KEY')
        self.mock_mode = not os.getenv('MICROSOFT_CLIENT_ID') or not os.getenv('MICROSOFT_CLIENT_SECRET')
        self.base_url = 'https://graph.microsoft.com/v1.0'
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _make_request(self, endpoint: str, method: str = 'GET', 
                           access_token: str = None, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Microsoft Graph API"""
        if self.mock_mode:
            return await self._mock_response(endpoint, method, **kwargs)
        
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        headers = {'Authorization': f'Bearer {access_token}'} if access_token else {}
        headers['Content-Type'] = 'application/json'
        
        try:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status == 200 or response.status == 201:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Microsoft Graph API error: {response.status} - {error_text}")
                    return {"error": error_text, "status": response.status}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}

    async def _mock_response(self, endpoint: str, method: str, **kwargs) -> Dict[str, Any]:
        """Mock response for development/testing"""
        if 'me' in endpoint:
            if method == 'GET':
                return {
                    "id": "user_123",
                    "displayName": "Test User",
                    "mail": "test@example.com",
                    "userPrincipalName": "test@example.com",
                    "jobTitle": "Software Engineer",
                    "officeLocation": "Remote"
                }
        
        elif 'calendars' in endpoint:
            if method == 'GET':
                return {
                    "value": [
                        {
                            "id": "calendar_primary",
                            "name": "Calendar",
                            "owner": {"address": "test@example.com"},
                            "isDefaultCalendar": True,
                            "canEdit": True
                        }
                    ]
                }
            elif method == 'POST':
                return {
                    "id": "new_calendar_id",
                    "name": kwargs.get('json', {}).get('name', 'New Calendar'),
                    "owner": {"address": "test@example.com"}
                }
        
        elif 'events' in endpoint:
            return {
                "value": [
                    {
                        "id": "event_123",
                        "subject": "Team Meeting",
                        "start": {"dateTime": "2024-01-15T10:00:00", "timeZone": "UTC"},
                        "end": {"dateTime": "2024-01-15T11:00:00", "timeZone": "UTC"},
                        "showAs": "busy"
                    }
                ]
            }
        
        elif 'messages' in endpoint:
            return {
                "value": [
                    {
                        "id": "msg_123",
                        "subject": "Test Message",
                        "from": {"emailAddress": {"address": "sender@example.com"}},
                        "toRecipients": [{"emailAddress": {"address": "test@example.com"}}],
                        "body": {"content": "Test body", "contentType": "text"},
                        "receivedDateTime": "2024-01-15T09:00:00Z",
                        "isRead": False
                    }
                ]
            }
        
        elif 'drive/root/children' in endpoint:
            return {
                "value": [
                    {
                        "id": "file_123",
                        "name": "Document.pdf",
                        "webUrl": "https://onedrive.live.com/?id=file_123",
                        "size": 1024000,
                        "file": {"mimeType": "application/pdf"},
                        "createdDateTime": "2024-01-01T00:00:00Z"
                    }
                ]
            }
        
        elif 'teams' in endpoint and 'channels' in endpoint:
            return {
                "value": [
                    {
                        "id": "channel_123",
                        "displayName": "General",
                        "description": "General channel",
                        "membershipType": "standard",
                        "webUrl": "https://teams.microsoft.com/l/channel/channel_123"
                    }
                ]
            }
        
        return {"mock": True, "endpoint": endpoint}

    # User Management
    async def get_user_info(self, access_token: str) -> Optional[MicrosoftUser]:
        """Get Microsoft user information"""
        data = await self._make_request('me', access_token=access_token)
        if 'error' in data:
            return None
        
        return MicrosoftUser(
            id=data.get('id', ''),
            displayName=data.get('displayName', ''),
            mail=data.get('mail', ''),
            userPrincipalName=data.get('userPrincipalName', ''),
            jobTitle=data.get('jobTitle'),
            officeLocation=data.get('officeLocation'),
            businessPhones=data.get('businessPhones', []),
            mobilePhone=data.get('mobilePhone')
        )

    # Enhanced Outlook Calendar Methods
    async def list_calendars(self, access_token: str) -> List[OutlookCalendar]:
        """List user's calendars"""
        data = await self._make_request('me/calendars', access_token=access_token)
        if 'error' in data:
            return []
        
        calendars = []
        for item in data.get('value', []):
            calendar = OutlookCalendar(
                id=item.get('id', ''),
                name=item.get('name', ''),
                owner=item.get('owner', {}),
                canEdit=item.get('canEdit', False),
                canView=item.get('canView', True),
                isShared=item.get('isShared', False),
                isDefaultCalendar=item.get('isDefaultCalendar', False),
                color=item.get('color'),
                changeKey=item.get('changeKey')
            )
            calendars.append(calendar)
        
        return calendars

    async def create_calendar(self, access_token: str, name: str) -> Optional[OutlookCalendar]:
        """Create a new calendar"""
        payload = {'name': name}
        
        data = await self._make_request('me/calendars', method='POST', 
                                       access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        return OutlookCalendar(
            id=data.get('id', ''),
            name=data.get('name', ''),
            owner=data.get('owner', {}),
            canEdit=data.get('canEdit', False),
            isDefaultCalendar=data.get('isDefaultCalendar', False)
        )

    async def delete_calendar(self, access_token: str, calendar_id: str) -> bool:
        """Delete a calendar"""
        data = await self._make_request(f'me/calendars/{calendar_id}', 
                                       method='DELETE', access_token=access_token)
        return 'error' not in data

    async def list_events(self, access_token: str, calendar_id: str = None,
                         start_date: str = None, end_date: str = None) -> List[OutlookEvent]:
        """List calendar events"""
        endpoint = f'me/calendars/{calendar_id}/events' if calendar_id else 'me/events'
        params = {}
        
        if start_date and end_date:
            params['$filter'] = f"start/dateTime ge '{start_date}' and end/dateTime le '{end_date}'"
        
        data = await self._make_request(endpoint, access_token=access_token, params=params)
        if 'error' in data:
            return []
        
        events = []
        for item in data.get('value', []):
            event = OutlookEvent(
                id=item.get('id', ''),
                subject=item.get('subject', ''),
                start=item.get('start', {}),
                end=item.get('end', {}),
                body=item.get('body', {}).get('content') if item.get('body') else None,
                bodyContentType=item.get('body', {}).get('contentType', 'text') if item.get('body') else 'text',
                location=item.get('location'),
                attendees=item.get('attendees', []),
                organizer=item.get('organizer', {}),
                isAllDay=item.get('isAllDay', False),
                sensitivity=item.get('sensitivity', 'normal'),
                showAs=item.get('showAs', 'busy'),
                responseStatus=item.get('responseStatus', {}),
                recurrence=item.get('recurrence'),
                seriesMasterId=item.get('seriesMasterId'),
                occurrenceId=item.get('occurrenceId'),
                isCancelled=item.get('isCancelled', False),
                isOrganizer=item.get('isOrganizer', False),
                onlineMeetingUrl=item.get('onlineMeetingUrl')
            )
            events.append(event)
        
        return events

    async def create_event(self, access_token: str, calendar_id: str = None,
                          event_data: Dict[str, Any]) -> Optional[OutlookEvent]:
        """Create a new calendar event"""
        endpoint = f'me/calendars/{calendar_id}/events' if calendar_id else 'me/events'
        
        data = await self._make_request(endpoint, method='POST', 
                                       access_token=access_token, json=event_data)
        if 'error' in data:
            return None
        
        return OutlookEvent(
            id=data.get('id', ''),
            subject=data.get('subject', ''),
            start=data.get('start', {}),
            end=data.get('end', {}),
            body=data.get('body', {}).get('content') if data.get('body') else None,
            bodyContentType=data.get('body', {}).get('contentType', 'text') if data.get('body') else 'text',
            location=data.get('location'),
            attendees=data.get('attendees', []),
            organizer=data.get('organizer', {}),
            isAllDay=data.get('isAllDay', False),
            sensitivity=data.get('sensitivity', 'normal'),
            showAs=data.get('showAs', 'busy'),
            responseStatus=data.get('responseStatus', {}),
            recurrence=data.get('recurrence'),
            isCancelled=data.get('isCancelled', False),
            isOrganizer=data.get('isOrganizer', False),
            onlineMeetingUrl=data.get('onlineMeetingUrl')
        )

    async def create_recurring_event(self, access_token: str, calendar_id: str = None,
                                   base_event: Dict[str, Any],
                                   recurrence_pattern: Dict[str, Any]) -> Optional[OutlookEvent]:
        """Create a recurring event"""
        event_data = {
            **base_event,
            'recurrence': recurrence_pattern
        }
        
        return await self.create_event(access_token, calendar_id, event_data)

    # Enhanced Outlook Email Methods
    async def list_messages(self, access_token: str, folder_id: str = None,
                           query: str = None, limit: int = 50) -> List[OutlookEmail]:
        """List emails with advanced filtering"""
        endpoint = f'me/mailFolders/{folder_id}/messages' if folder_id else 'me/messages'
        params = {'$top': limit}
        
        if query:
            params['$search'] = f'"{query}"'
        
        data = await self._make_request(endpoint, access_token=access_token, params=params)
        if 'error' in data:
            return []
        
        messages = []
        for item in data.get('value', []):
            message = OutlookEmail(
                id=item.get('id', ''),
                subject=item.get('subject', ''),
                from_address=item.get('from', {}),
                to_addresses=item.get('toRecipients', []),
                cc_addresses=item.get('ccRecipients', []),
                bcc_addresses=item.get('bccRecipients', []),
                body=item.get('body', {}).get('content', '') if item.get('body') else '',
                bodyContentType=item.get('body', {}).get('contentType', 'text') if item.get('body') else 'text',
                receivedDateTime=item.get('receivedDateTime', ''),
                sentDateTime=item.get('sentDateTime'),
                isRead=item.get('isRead', False),
                isDraft=item.get('isDraft', False),
                hasAttachments=item.get('hasAttachments', False),
                importance=item.get('importance', 'normal'),
                conversationId=item.get('conversationId'),
                webLink=item.get('webLink')
            )
            messages.append(message)
        
        return messages

    async def send_message(self, access_token: str, to_addresses: List[str],
                         subject: str, body: str, cc_addresses: List[str] = None,
                         bcc_addresses: List[str] = None, is_html: bool = False) -> Dict[str, Any]:
        """Send email message"""
        recipients = [{'emailAddress': {'address': addr}} for addr in to_addresses]
        cc_recipients = [{'emailAddress': {'address': addr}} for addr in cc_addresses] if cc_addresses else []
        
        message_data = {
            'message': {
                'subject': subject,
                'body': {
                    'content': body,
                    'contentType': 'html' if is_html else 'text'
                },
                'toRecipients': recipients,
                'ccRecipients': cc_recipients
            },
            'saveToSentItems': 'true'
        }
        
        if bcc_addresses:
            bcc_recipients = [{'emailAddress': {'address': addr}} for addr in bcc_addresses]
            message_data['message']['bccRecipients'] = bcc_recipients
        
        data = await self._make_request('me/sendMail', method='POST', 
                                       access_token=access_token, json=message_data)
        return data

    async def reply_to_message(self, access_token: str, message_id: str,
                              body: str, is_html: bool = False) -> Dict[str, Any]:
        """Reply to an email message"""
        reply_data = {
            'message': {
                'body': {
                    'content': body,
                    'contentType': 'html' if is_html else 'text'
                }
            }
        }
        
        data = await self._make_request(f'me/messages/{message_id}/reply', 
                                       method='POST', access_token=access_token, json=reply_data)
        return data

    # Enhanced OneDrive Methods
    async def list_files(self, access_token: str, folder_id: str = None,
                        query: str = None) -> List[OneDriveFile]:
        """List OneDrive files and folders"""
        endpoint = f'drive/items/{folder_id}/children' if folder_id else 'drive/root/children'
        params = {}
        
        if query:
            params['$search'] = f'"{query}"'
        
        data = await self._make_request(endpoint, access_token=access_token, params=params)
        if 'error' in data:
            return []
        
        files = []
        for item in data.get('value', []):
            if item.get('folder'):
                # Skip folders in files list, they could be handled separately
                continue
                
            file_obj = OneDriveFile(
                id=item.get('id', ''),
                name=item.get('name', ''),
                webUrl=item.get('webUrl', ''),
                size=item.get('size', 0),
                createdDateTime=item.get('createdDateTime'),
                lastModifiedDateTime=item.get('lastModifiedDateTime'),
                parentReference=item.get('parentReference', {}),
                file=item.get('file', {}),
                folder=item.get('folder', {}),
                mimeType=item.get('file', {}).get('mimeType'),
                shared=item.get('shared', {}).get('scope') == 'anonymous',
                createdBy=item.get('createdBy', {}),
                lastModifiedBy=item.get('lastModifiedBy', {}),
                @odata_type=item.get('@odata.type')
            )
            files.append(file_obj)
        
        return files

    async def list_folders(self, access_token: str, parent_folder_id: str = None) -> List[OneDriveFolder]:
        """List OneDrive folders"""
        endpoint = f'drive/items/{parent_folder_id}/children' if parent_folder_id else 'drive/root/children'
        
        data = await self._make_request(endpoint, access_token=access_token)
        if 'error' in data:
            return []
        
        folders = []
        for item in data.get('value', []):
            if item.get('folder'):
                folder_obj = OneDriveFolder(
                    id=item.get('id', ''),
                    name=item.get('name', ''),
                    webUrl=item.get('webUrl', ''),
                    childCount=item.get('folder', {}).get('childCount', 0),
                    createdDateTime=item.get('createdDateTime'),
                    lastModifiedDateTime=item.get('lastModifiedDateTime'),
                    parentReference=item.get('parentReference', {}),
                    shared=item.get('shared', {}).get('scope') == 'anonymous',
                    createdBy=item.get('createdBy', {}),
                    lastModifiedBy=item.get('lastModifiedBy', {})
                )
                folders.append(folder_obj)
        
        return folders

    async def create_folder(self, access_token: str, name: str, 
                           parent_folder_id: str = None) -> Optional[OneDriveFolder]:
        """Create folder in OneDrive"""
        endpoint = f'drive/items/{parent_folder_id}/children' if parent_folder_id else 'drive/root/children'
        
        payload = {
            'name': name,
            'folder': {},
            '@microsoft.graph.conflictBehavior': 'fail'
        }
        
        data = await self._make_request(endpoint, method='POST', 
                                       access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        return OneDriveFolder(
            id=data.get('id', ''),
            name=data.get('name', ''),
            webUrl=data.get('webUrl', ''),
            childCount=0,
            createdDateTime=data.get('createdDateTime'),
            parentReference=data.get('parentReference', {}),
            shared=data.get('shared', {}).get('scope') == 'anonymous',
            createdBy=data.get('createdBy', {}),
            lastModifiedBy=data.get('lastModifiedBy', {})
        )

    async def upload_file(self, access_token: str, file_content: bytes, 
                         file_name: str, folder_id: str = None) -> Optional[OneDriveFile]:
        """Upload file to OneDrive"""
        # Simple upload for files up to 4MB
        endpoint = f'drive/items/{folder_id}:/{file_name}:/content' if folder_id else f'drive/root:/{file_name}:/content'
        
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/octet-stream'
        }
        
        try:
            async with session.put(url, headers=headers, data=file_content) as response:
                if response.status == 200 or response.status == 201:
                    data = await response.json()
                    return OneDriveFile(
                        id=data.get('id', ''),
                        name=data.get('name', ''),
                        webUrl=data.get('webUrl', ''),
                        size=data.get('size', 0),
                        createdDateTime=data.get('createdDateTime'),
                        lastModifiedDateTime=data.get('lastModifiedDateTime'),
                        parentReference=data.get('parentReference', {}),
                        file=data.get('file', {}),
                        mimeType=data.get('file', {}).get('mimeType'),
                        shared=data.get('shared', {}).get('scope') == 'anonymous',
                        createdBy=data.get('createdBy', {}),
                        lastModifiedBy=data.get('lastModifiedBy', {})
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"OneDrive upload error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"OneDrive upload failed: {e}")
            return None

    async def share_item(self, access_token: str, item_id: str, 
                         recipients: List[str], role: str = 'view') -> Dict[str, Any]:
        """Share file or folder with users"""
        payload = {
            'requireSignIn': True,
            'sendInvitation': True,
            'roles': [role],
            'recipients': [{'email': recipient} for recipient in recipients]
        }
        
        data = await self._make_request(f'drive/items/{item_id}/invite', 
                                       method='POST', access_token=access_token, json=payload)
        return data

    # Enhanced Teams Methods
    async def list_teams(self, access_token: str) -> List[Dict[str, Any]]:
        """List user's Teams"""
        data = await self._make_request('me/joinedTeams', access_token=access_token)
        return data.get('value', [])

    async def list_channels(self, access_token: str, team_id: str) -> List[TeamsChannel]:
        """List channels in a Team"""
        data = await self._make_request(f'teams/{team_id}/channels', access_token=access_token)
        if 'error' in data:
            return []
        
        channels = []
        for item in data.get('value', []):
            channel = TeamsChannel(
                id=item.get('id', ''),
                displayName=item.get('displayName', ''),
                description=item.get('description'),
                isFavoriteByDefault=item.get('isFavoriteByDefault', False),
                membershipType=item.get('membershipType', 'standard'),
                email=item.get('email'),
                webUrl=item.get('webUrl'),
                tenantId=item.get('tenantId')
            )
            channels.append(channel)
        
        return channels

    async def get_messages(self, access_token: str, team_id: str, channel_id: str,
                           limit: int = 50) -> List[TeamsMessage]:
        """Get messages from Teams channel"""
        endpoint = f'teams/{team_id}/channels/{channel_id}/messages'
        params = {'$top': limit}
        
        data = await self._make_request(endpoint, access_token=access_token, params=params)
        if 'error' in data:
            return []
        
        messages = []
        for item in data.get('value', []):
            message = TeamsMessage(
                id=item.get('id', ''),
                messageType=item.get('messageType', 'message'),
                createdDateTime=item.get('createdDateTime'),
                lastModifiedDateTime=item.get('lastModifiedDateTime'),
                subject=item.get('subject'),
                summary=item.get('summary'),
                importance=item.get('importance', 'normal'),
                locale=item.get('locale', 'en-us'),
                webUrl=item.get('webUrl'),
                from_user=item.get('from', {}),
                body=item.get('body', {}),
                attachments=item.get('attachments', []),
                mentions=item.get('mentions', []),
                replies=item.get('replies', [])
            )
            messages.append(message)
        
        return messages

    async def send_message(self, access_token: str, team_id: str, channel_id: str,
                         content: str, content_type: str = 'text') -> Dict[str, Any]:
        """Send message to Teams channel"""
        message_data = {
            'body': {
                'contentType': content_type,
                'content': content
            }
        }
        
        data = await self._make_request(f'teams/{team_id}/channels/{channel_id}/messages', 
                                       method='POST', access_token=access_token, json=message_data)
        return data

    # Contacts Management
    async def list_contacts(self, access_token: str) -> List[OutlookContact]:
        """List Outlook contacts"""
        data = await self._make_request('me/contacts', access_token=access_token)
        if 'error' in data:
            return []
        
        contacts = []
        for item in data.get('value', []):
            contact = OutlookContact(
                id=item.get('id', ''),
                displayName=item.get('displayName', ''),
                givenName=item.get('givenName'),
                surname=item.get('surname'),
                emailAddresses=item.get('emailAddresses', []),
                businessPhones=item.get('businessPhones', []),
                mobilePhone=item.get('mobilePhone'),
                homePhones=item.get('homePhones', []),
                company_name=item.get('companyName'),
                department=item.get('department'),
                jobTitle=item.get('jobTitle'),
                officeLocation=item.get('officeLocation'),
                addresses=item.get('addresses', [])
            )
            contacts.append(contact)
        
        return contacts

    async def create_contact(self, access_token: str, contact_data: Dict[str, Any]) -> Optional[OutlookContact]:
        """Create new contact"""
        data = await self._make_request('me/contacts', method='POST', 
                                       access_token=access_token, json=contact_data)
        if 'error' in data:
            return None
        
        return OutlookContact(
            id=data.get('id', ''),
            displayName=data.get('displayName', ''),
            givenName=data.get('givenName'),
            surname=data.get('surname'),
            emailAddresses=data.get('emailAddresses', []),
            businessPhones=data.get('businessPhones', []),
            mobilePhone=data.get('mobilePhone'),
            homePhones=data.get('homePhones', []),
            company_name=data.get('companyName'),
            department=data.get('department'),
            jobTitle=data.get('jobTitle'),
            officeLocation=data.get('officeLocation'),
            addresses=data.get('addresses', [])
        )

    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "service": "microsoft-services-enhanced",
            "version": "2.0.0",
            "mock_mode": self.mock_mode,
            "capabilities": [
                "user_management",
                "calendar_management",
                "event_crud",
                "recurring_events",
                "email_operations",
                "contact_management",
                "onedrive_operations",
                "file_sharing",
                "teams_operations",
                "message_operations"
            ],
            "base_url": self.base_url
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None

# Singleton instance
microsoft_services_enhanced = MicrosoftServicesEnhanced()

# Export main class and instance
__all__ = [
    'MicrosoftServicesEnhanced',
    'microsoft_services_enhanced',
    'MicrosoftUser',
    'OutlookEmail',
    'OutlookCalendar', 
    'OutlookEvent',
    'OutlookContact',
    'OneDriveFile',
    'OneDriveFolder',
    'TeamsChannel',
    'TeamsMessage'
]