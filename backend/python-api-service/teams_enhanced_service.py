"""
Enhanced Microsoft Teams Service Implementation
Complete Teams integration with comprehensive API operations
"""

import os
import logging
import asyncio
import httpx
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Union

# Import encryption utilities
try:
    from atom_encryption import decrypt_data, encrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False

# Import database operations
try:
    from db_oauth_teams_complete import get_user_teams_tokens, get_teams_user
    TEAMS_DB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Teams database operations not available: {e}")
    TEAMS_DB_AVAILABLE = False

# Microsoft Graph API configuration
TEAMS_API_BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_TIMEOUT = 30

# Configure logging
logger = logging.getLogger(__name__)

# Data model classes
class TeamsMessage:
    """Microsoft Teams message data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.subject = data.get("subject", "")
        self.body = data.get("body", {}).get("content", "")
        self.summary = data.get("summary", "")
        self.importance = data.get("importance", "normal")
        self.locale = data.get("locale", "en-us")
        self.from_user = data.get("from", {}).get("user", {}).get("displayName", "")
        self.from_email = data.get("from", {}).get("user", {}).get("emailAddress", {}).get("address", "")
        self.conversation_id = data.get("conversationId")
        self.thread_id = data.get("threadId")
        self.created_at = data.get("createdDateTime")
        self.last_modified_at = data.get("lastModifiedDateTime")
        self.attachments = data.get("attachments", [])
        self.mentions = data.get("mentions", [])
        self.reactions = data.get("reactions", [])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'subject': self.subject,
            'body': self.body,
            'summary': self.summary,
            'importance': self.importance,
            'locale': self.locale,
            'from_user': self.from_user,
            'from_email': self.from_email,
            'conversationId': self.conversation_id,
            'threadId': self.thread_id,
            'createdDateTime': self.created_at,
            'lastModifiedDateTime': self.last_modified_at,
            'attachments': self.attachments,
            'mentions': self.mentions,
            'reactions': self.reactions
        }

class TeamsChannel:
    """Microsoft Teams channel data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.display_name = data.get("displayName")
        self.description = data.get("description", "")
        self.email = data.get("email")
        self.web_url = data.get("webUrl")
        self.membership_type = data.get("membershipType")  # user, shared, private
        self.tenant_id = data.get("tenantId")
        self.is_favorite_by_default = data.get("isFavoriteByDefault", False)
        self.team_id = data.get("teamId")
        self.created_at = data.get("createdDateTime")
        self.last_modified_at = data.get("lastModifiedDateTime")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'displayName': self.display_name,
            'description': self.description,
            'email': self.email,
            'webUrl': self.web_url,
            'membershipType': self.membership_type,
            'tenantId': self.tenant_id,
            'isFavoriteByDefault': self.is_favorite_by_default,
            'teamId': self.team_id,
            'createdDateTime': self.created_at,
            'lastModifiedDateTime': self.last_modified_at
        }

class TeamsUser:
    """Microsoft Teams user data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.display_name = data.get("displayName")
        self.given_name = data.get("givenName", "")
        self.surname = data.get("surname", "")
        self.mail = data.get("mail", "")
        self.user_principal_name = data.get("userPrincipalName", "")
        self.job_title = data.get("jobTitle", "")
        self.office_location = data.get("officeLocation", "")
        self.business_phones = data.get("businessPhones", [])
        self.mobile_phone = data.get("mobilePhone", "")
        self.photo_available = data.get("photo_available", False)
        self.account_enabled = data.get("accountEnabled", True)
        self.user_type = data.get("userType", "Member")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'displayName': self.display_name,
            'givenName': self.given_name,
            'surname': self.surname,
            'mail': self.mail,
            'userPrincipalName': self.user_principal_name,
            'jobTitle': self.job_title,
            'officeLocation': self.office_location,
            'businessPhones': self.business_phones,
            'mobilePhone': self.mobile_phone,
            'photo_available': self.photo_available,
            'accountEnabled': self.account_enabled,
            'userType': self.user_type
        }

class TeamsMeeting:
    """Microsoft Teams meeting data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.subject = data.get("subject", "")
        self.body = data.get("body", {}).get("content", "")
        self.start_time = data.get("start", {}).get("dateTime")
        self.end_time = data.get("end", {}).get("dateTime")
        self.location = data.get("location", {}).get("displayName", "")
        self.attendees = data.get("attendees", [])
        self.importance = data.get("importance", "normal")
        self.is_online_meeting = data.get("isOnlineMeeting", False)
        self.online_meeting_url = data.get("onlineMeetingUrl", "")
        self.join_url = data.get("joinWebUrl", "")
        self.created_at = data.get("createdDateTime")
        self.last_modified_at = data.get("lastModifiedDateTime")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'subject': self.subject,
            'body': self.body,
            'startDateTime': self.start_time,
            'endDateTime': self.end_time,
            'location': self.location,
            'attendees': self.attendees,
            'importance': self.importance,
            'isOnlineMeeting': self.is_online_meeting,
            'onlineMeetingUrl': self.online_meeting_url,
            'joinWebUrl': self.join_url,
            'createdDateTime': self.created_at,
            'lastModifiedDateTime': self.last_modified_at
        }

class TeamsFile:
    """Microsoft Teams file data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.size = data.get("size", 0)
        self.mime_type = data.get("file", {}).get("mimeType", "")
        self.file_type = data.get("file", {}).get("fileType", "")
        self.web_url = data.get("webUrl", "")
        self.created_by = data.get("createdBy", {}).get("user", {}).get("displayName", "")
        self.created_at = data.get("createdDateTime")
        self.last_modified_at = data.get("lastModifiedDateTime")
        self.parent_reference = data.get("parentReference", {})
        self.shared = data.get("shared", {})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'size': self.size,
            'mimeType': self.mime_type,
            'fileType': self.file_type,
            'webUrl': self.web_url,
            'createdBy': self.created_by,
            'createdDateTime': self.created_at,
            'lastModifiedDateTime': self.last_modified_at,
            'parentReference': self.parent_reference,
            'shared': self.shared
        }

class TeamsService:
    """Enhanced Microsoft Teams service class"""
    
    def __init__(self):
        self._mock_mode = True
        self.api_base_url = TEAMS_API_BASE_URL
        self.timeout = DEFAULT_TIMEOUT
        self._mock_db = {
            'channels': [],
            'messages': [],
            'users': [],
            'meetings': [],
            'files': []
        }
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data for testing"""
        # Mock channels
        self._mock_db['channels'] = [
            TeamsChannel({
                'id': '19:meeting_channel@thread.tacv2',
                'displayName': 'Project Discussions',
                'description': 'Channel for project-related discussions',
                'email': 'project-discussions@company.com',
                'webUrl': 'https://teams.microsoft.com/l/channel/19%3ameeting_channel%40thread.tacv2/Project%20Discussions',
                'membershipType': 'user',
                'tenantId': 'tenant-123',
                'isFavoriteByDefault': True,
                'teamId': 'team-123',
                'createdDateTime': '2023-01-15T10:30:00Z',
                'lastModifiedDateTime': '2023-11-04T14:20:00Z'
            }),
            TeamsChannel({
                'id': '19:general_channel@thread.tacv2',
                'displayName': 'General',
                'description': 'General team channel for announcements',
                'email': 'general@company.com',
                'webUrl': 'https://teams.microsoft.com/l/channel/19%3ageneral_channel%40thread.tacv2/General',
                'membershipType': 'user',
                'tenantId': 'tenant-123',
                'isFavoriteByDefault': False,
                'teamId': 'team-123',
                'createdDateTime': '2023-01-10T09:00:00Z',
                'lastModifiedDateTime': '2023-11-04T16:45:00Z'
            }),
            TeamsChannel({
                'id': '19:dev_team@thread.tacv2',
                'displayName': 'Development Team',
                'description': 'Development team collaboration',
                'email': 'dev-team@company.com',
                'webUrl': 'https://teams.microsoft.com/l/channel/19%3adev_team%40thread.tacv2/Development%20Team',
                'membershipType': 'user',
                'tenantId': 'tenant-123',
                'isFavoriteByDefault': True,
                'teamId': 'team-456',
                'createdDateTime': '2023-02-01T11:15:00Z',
                'lastModifiedDateTime': '2023-11-04T13:30:00Z'
            })
        ]
        
        # Mock users
        self._mock_db['users'] = [
            TeamsUser({
                'id': 'user-123',
                'displayName': 'Alex Johnson',
                'givenName': 'Alex',
                'surname': 'Johnson',
                'mail': 'alex.johnson@company.com',
                'userPrincipalName': 'alex.johnson@company.com',
                'jobTitle': 'Senior Software Engineer',
                'officeLocation': 'Seattle',
                'businessPhones': ['+1-206-555-0123'],
                'mobilePhone': '+1-206-555-9876',
                'photo_available': True,
                'accountEnabled': True,
                'userType': 'Member'
            }),
            TeamsUser({
                'id': 'user-456',
                'displayName': 'Sarah Williams',
                'givenName': 'Sarah',
                'surname': 'Williams',
                'mail': 'sarah.williams@company.com',
                'userPrincipalName': 'sarah.williams@company.com',
                'jobTitle': 'Product Manager',
                'officeLocation': 'San Francisco',
                'businessPhones': ['+1-415-555-0456'],
                'mobilePhone': '+1-415-555-8765',
                'photo_available': True,
                'accountEnabled': True,
                'userType': 'Member'
            }),
            TeamsUser({
                'id': 'user-789',
                'displayName': 'Michael Chen',
                'givenName': 'Michael',
                'surname': 'Chen',
                'mail': 'michael.chen@company.com',
                'userPrincipalName': 'michael.chen@company.com',
                'jobTitle': 'UX Designer',
                'officeLocation': 'Austin',
                'businessPhones': ['+1-512-555-0789'],
                'mobilePhone': '+1-512-555-4321',
                'photo_available': True,
                'accountEnabled': True,
                'userType': 'Member'
            })
        ]
        
        # Mock messages
        now = datetime.utcnow().isoformat() + 'Z'
        self._mock_db['messages'] = [
            TeamsMessage({
                'id': 'message-123',
                'subject': 'Development Update',
                'body': 'Hey team! Just pushed the latest updates to the feature branch. Ready for code review. 🚀',
                'importance': 'normal',
                'from': {
                    'user': {
                        'displayName': 'Alex Johnson',
                        'emailAddress': {
                            'address': 'alex.johnson@company.com'
                        }
                    }
                },
                'conversationId': '19:meeting_channel@thread.tacv2',
                'threadId': 'thread-123',
                'createdDateTime': now,
                'lastModifiedDateTime': now
            }),
            TeamsMessage({
                'id': 'message-456',
                'subject': 'Design Review Meeting',
                'body': 'Great work on the new UI mockups! The design system is looking really solid. 🎨',
                'importance': 'high',
                'from': {
                    'user': {
                        'displayName': 'Sarah Williams',
                        'emailAddress': {
                            'address': 'sarah.williams@company.com'
                        }
                    }
                },
                'conversationId': '19:dev_team@thread.tacv2',
                'threadId': 'thread-456',
                'createdDateTime': now,
                'lastModifiedDateTime': now
            }),
            TeamsMessage({
                'id': 'message-789',
                'subject': 'Team Standup',
                'body': 'Daily standup in 15 minutes. Please have your updates ready for the Sprint planning.',
                'importance': 'normal',
                'from': {
                    'user': {
                        'displayName': 'Michael Chen',
                        'emailAddress': {
                            'address': 'michael.chen@company.com'
                        }
                    }
                },
                'conversationId': '19:general_channel@thread.tacv2',
                'threadId': 'thread-789',
                'createdDateTime': now,
                'lastModifiedDateTime': now
            })
        ]
        
        # Mock meetings
        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'
        self._mock_db['meetings'] = [
            TeamsMeeting({
                'id': 'meeting-123',
                'subject': 'Sprint Planning',
                'body': 'Sprint planning meeting for the upcoming development cycle.',
                'start': {
                    'dateTime': tomorrow
                },
                'end': {
                    'dateTime': f"{datetime.utcnow() + timedelta(days=1, hours=2).isoformat()}Z"
                },
                'location': {
                    'displayName': 'Teams Meeting'
                },
                'importance': 'high',
                'isOnlineMeeting': True,
                'onlineMeetingUrl': 'https://teams.microsoft.com/l/meetup-join/meeting-123',
                'joinWebUrl': 'https://teams.microsoft.com/l/meetup-join/meeting-123',
                'attendees': [
                    {
                        'emailAddress': {
                            'address': 'alex.johnson@company.com',
                            'name': 'Alex Johnson'
                        }
                    },
                    {
                        'emailAddress': {
                            'address': 'sarah.williams@company.com',
                            'name': 'Sarah Williams'
                        }
                    }
                ],
                'createdDateTime': now,
                'lastModifiedDateTime': now
            })
        ]
        
        # Mock files
        self._mock_db['files'] = [
            TeamsFile({
                'id': 'file-123',
                'name': 'Project-Requirements.docx',
                'size': 2048000,
                'file': {
                    'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'fileType': 'docx'
                },
                'webUrl': 'https://company-my.sharepoint.com/personal/user/Documents/Project-Requirements.docx',
                'createdBy': {
                    'displayName': 'Sarah Williams'
                },
                'createdDateTime': now,
                'lastModifiedDateTime': now,
                'parentReference': {
                    'driveId': 'drive-123',
                    'driveType': 'business'
                }
            }),
            TeamsFile({
                'id': 'file-456',
                'name': 'UI-Mockups.sketch',
                'size': 5120000,
                'file': {
                    'mimeType': 'application/sketch',
                    'fileType': 'sketch'
                },
                'webUrl': 'https://company-my.sharepoint.com/personal/user/Documents/UI-Mockups.sketch',
                'createdBy': {
                    'displayName': 'Michael Chen'
                },
                'createdDateTime': now,
                'lastModifiedDateTime': now,
                'parentReference': {
                    'driveId': 'drive-123',
                    'driveType': 'business'
                }
            })
        ]
    
    def set_mock_mode(self, enabled: bool):
        """Set mock mode for testing"""
        self._mock_mode = enabled
        if enabled:
            self._init_mock_data()
    
    async def _get_user_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user"""
        if self._mock_mode:
            return os.getenv('TEAMS_ACCESS_TOKEN', 'mock_teams_token')
        
        # In real implementation, this would fetch from database
        if TEAMS_DB_AVAILABLE:
            tokens = await get_user_teams_tokens(None, user_id)
            if tokens:
                access_token = tokens.get('access_token', '')
                if ENCRYPTION_AVAILABLE and isinstance(access_token, bytes):
                    access_token = decrypt_data(access_token, os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                return access_token
        return None
    
    async def _make_api_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                             data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None,
                             access_token: Optional[str] = None) -> Dict[str, Any]:
        """Make API request to Microsoft Teams/Graph API"""
        if self._mock_mode:
            return await self._make_mock_request(method, endpoint, params, data, files)
        
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json' if files is None else None
            }
            
            url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == 'POST':
                    if files:
                        response = await client.post(url, headers=headers, data=data, files=files)
                    else:
                        response = await client.post(url, headers=headers, json=data)
                elif method.upper() == 'PUT':
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Teams API request error: {e}")
            return {'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected Teams API request error: {e}")
            return {'error': str(e)}
    
    async def _make_mock_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                               data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make mock API request"""
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        endpoint = endpoint.lower()
        
        # Mock channel operations
        if 'me/joinedteams' in endpoint:
            return {'value': [channel.to_dict() for channel in self._mock_db['channels']]}
        
        elif 'me/channels' in endpoint:
            return {'value': [channel.to_dict() for channel in self._mock_db['channels'] 
                           if channel.membership_type in ['user', 'shared']]}
        
        elif 'teams/' in endpoint and '/channels' in endpoint and 'GET' in method.upper():
            team_id = endpoint.split('teams/')[1].split('/channels')[0]
            return {'value': [channel.to_dict() for channel in self._mock_db['channels']
                           if channel.team_id == team_id]}
        
        # Mock message operations
        elif 'teams/' in endpoint and '/channels/' in endpoint and '/messages' in endpoint and 'POST' in method.upper():
            if not data:
                return {'error': 'Message data is required'}
            
            channel_id = endpoint.split('/channels/')[1].split('/messages')[0]
            
            # Create mock message
            message_id = f"message-{int(datetime.utcnow().timestamp())}"
            now = datetime.utcnow().isoformat() + 'Z'
            
            new_message = TeamsMessage({
                'id': message_id,
                'subject': data.get('subject', ''),
                'body': data.get('body', {}).get('content', ''),
                'importance': data.get('importance', 'normal'),
                'from': {
                    'user': {
                        'displayName': 'Current User',
                        'emailAddress': {
                            'address': 'user@company.com'
                        }
                    }
                },
                'conversationId': channel_id,
                'threadId': data.get('threadId'),
                'createdDateTime': now,
                'lastModifiedDateTime': now
            })
            
            self._mock_db['messages'].append(new_message)
            
            return new_message.to_dict()
        
        elif 'teams/' in endpoint and '/channels/' in endpoint and '/messages' in endpoint and 'GET' in method.upper():
            channel_id = endpoint.split('/channels/')[1].split('/messages')[0]
            
            messages = [msg.to_dict() for msg in self._mock_db['messages'] 
                       if msg.conversation_id == channel_id]
            
            # Apply filters
            if params:
                if '$top' in params:
                    limit = int(params['$top'])
                    messages = messages[:limit]
            
            return {'value': messages}
        
        # Mock user operations
        elif 'me/users' in endpoint or '/users' in endpoint:
            if 'me' in endpoint:
                # Return current user info
                current_user = self._mock_db['users'][0]
                return current_user.to_dict()
            else:
                # Return all users
                return {'value': [user.to_dict() for user in self._mock_db['users']]}
        
        elif '/users/' in endpoint and 'GET' in method.upper():
            user_id = endpoint.split('/users/')[1].split('/')[0]
            user = next((u for u in self._mock_db['users'] if u.id == user_id), None)
            if user:
                return user.to_dict()
            else:
                return {'error': 'User not found'}
        
        # Mock meeting operations
        elif 'me/events' in endpoint:
            if 'GET' in method.upper():
                meetings = [meeting.to_dict() for meeting in self._mock_db['meetings']]
                return {'value': meetings}
            elif 'POST' in method.upper():
                if not data:
                    return {'error': 'Meeting data is required'}
                
                meeting_id = f"meeting-{int(datetime.utcnow().timestamp())}"
                now = datetime.utcnow().isoformat() + 'Z'
                
                new_meeting = TeamsMeeting({
                    'id': meeting_id,
                    'subject': data.get('subject', ''),
                    'body': data.get('body', {}),
                    'start': data.get('start', {}),
                    'end': data.get('end', {}),
                    'location': data.get('location', {}),
                    'importance': data.get('importance', 'normal'),
                    'isOnlineMeeting': data.get('isOnlineMeeting', True),
                    'onlineMeetingUrl': data.get('onlineMeetingUrl', ''),
                    'joinWebUrl': data.get('joinWebUrl', ''),
                    'attendees': data.get('attendees', []),
                    'createdDateTime': now,
                    'lastModifiedDateTime': now
                })
                
                self._mock_db['meetings'].append(new_meeting)
                
                return new_meeting.to_dict()
        
        # Mock file operations
        elif 'me/drive/root/children' in endpoint:
            if 'GET' in method.upper():
                files = [file.to_dict() for file in self._mock_db['files']]
                return {'value': files}
            elif 'POST' in method.upper():
                # File upload simulation
                return {'error': 'File upload requires multipart form data'}
        
        elif '/drives/' in endpoint and '/items/' in endpoint and 'GET' in method.upper():
            file_id = endpoint.split('/items/')[1]
            file = next((f for f in self._mock_db['files'] if f.id == file_id), None)
            if file:
                return file.to_dict()
            else:
                return {'error': 'File not found'}
        
        # Default mock response
        return {
            'mock_response': True,
            'endpoint': endpoint,
            'method': method,
            'params': params,
            'data': data
        }
    
    # Channel operations
    async def list_channels(self, user_id: str, membership_filter: Optional[str] = None,
                         limit: int = 50) -> List[TeamsChannel]:
        """List channels accessible to user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            # Get user's teams and channels
            response = await self._make_api_request('GET', 'me/joinedTeams', access_token=access_token)
            
            channels = []
            if 'value' in response:
                for team in response['value']:
                    team_channels = await self._make_api_request('GET', f"teams/{team['id']}/channels", 
                                                            access_token=access_token)
                    if 'value' in team_channels:
                        channels.extend([TeamsChannel(channel) for channel in team_channels['value']])
            
            # Apply membership filter
            if membership_filter:
                channels = [ch for ch in channels if ch.membership_type == membership_filter]
            
            # Apply limit
            return channels[:limit] if limit > 0 else channels
            
        except Exception as e:
            logger.error(f"Unexpected error listing Teams channels: {e}")
            return []
    
    async def get_channel_info(self, user_id: str, channel_id: str) -> Optional[TeamsChannel]:
        """Get information about a specific channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            response = await self._make_api_request('GET', f"teams/{channel_id}/channels/{channel_id}", 
                                                access_token=access_token)
            
            if response and not response.get('error'):
                return TeamsChannel(response)
            else:
                logger.error(f"Error getting Teams channel info: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting Teams channel info: {e}")
            return None
    
    # Message operations
    async def send_message(self, user_id: str, channel_id: str, content: str,
                        subject: str = "", importance: str = "normal", thread_id: Optional[str] = None) -> Optional[TeamsMessage]:
        """Send a message to a Teams channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            data = {
                "body": {
                    "content": content
                },
                "subject": subject,
                "importance": importance
            }
            
            if thread_id:
                data["threadId"] = thread_id
            
            response = await self._make_api_request('POST', f"teams/{channel_id}/channels/{channel_id}/messages", 
                                                data=data, access_token=access_token)
            
            if response and not response.get('error'):
                return TeamsMessage(response)
            else:
                logger.error(f"Error sending Teams message: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error sending Teams message: {e}")
            return None
    
    async def list_messages(self, user_id: str, channel_id: str, limit: int = 50,
                         before: Optional[str] = None, after: Optional[str] = None) -> List[TeamsMessage]:
        """List messages from a Teams channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {}
            if limit > 0:
                params['$top'] = limit
            if before:
                params['$before'] = before
            if after:
                params['$after'] = after
            
            response = await self._make_api_request('GET', f"teams/{channel_id}/channels/{channel_id}/messages", 
                                                params=params, access_token=access_token)
            
            if 'value' in response:
                return [TeamsMessage(msg) for msg in response['value']]
            else:
                logger.error(f"Error listing Teams messages: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing Teams messages: {e}")
            return []
    
    # User operations
    async def list_users(self, user_id: str, limit: int = 100, 
                       search_query: Optional[str] = None) -> List[TeamsUser]:
        """List users in Teams organization"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {}
            if limit > 0:
                params['$top'] = limit
            if search_query:
                params['$search'] = f'"{search_query}"'
                params['$orderby'] = 'displayName'
            
            response = await self._make_api_request('GET', 'users', params=params, access_token=access_token)
            
            if 'value' in response:
                return [TeamsUser(user) for user in response['value']]
            else:
                logger.error(f"Error listing Teams users: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing Teams users: {e}")
            return []
    
    async def get_user_info(self, user_id: str, target_user_id: str) -> Optional[TeamsUser]:
        """Get information about a specific user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            response = await self._make_api_request('GET', f"users/{target_user_id}", access_token=access_token)
            
            if response and not response.get('error'):
                return TeamsUser(response)
            else:
                logger.error(f"Error getting Teams user info: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting Teams user info: {e}")
            return None
    
    # Meeting operations
    async def list_meetings(self, user_id: str, limit: int = 50, 
                         start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[TeamsMeeting]:
        """List meetings for user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {}
            if limit > 0:
                params['$top'] = limit
            if start_date:
                params['$startDateTime'] = start_date
            if end_date:
                params['$endDateTime'] = end_date
            
            response = await self._make_api_request('GET', 'me/events', params=params, access_token=access_token)
            
            if 'value' in response:
                return [TeamsMeeting(meeting) for meeting in response['value']]
            else:
                logger.error(f"Error listing Teams meetings: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing Teams meetings: {e}")
            return []
    
    async def create_meeting(self, user_id: str, subject: str, content: str,
                           start_time: str, end_time: str, attendees: List[Dict[str, Any]],
                           location: Optional[str] = None, importance: str = "normal") -> Optional[TeamsMeeting]:
        """Create a Teams meeting"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            data = {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": content
                },
                "start": {
                    "dateTime": start_time,
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": "UTC"
                },
                "attendees": attendees,
                "importance": importance,
                "isOnlineMeeting": True,
                "onlineMeetingProvider": "teamsForBusiness"
            }
            
            if location:
                data["location"] = {
                    "displayName": location
                }
            
            response = await self._make_api_request('POST', 'me/events', data=data, access_token=access_token)
            
            if response and not response.get('error'):
                return TeamsMeeting(response)
            else:
                logger.error(f"Error creating Teams meeting: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error creating Teams meeting: {e}")
            return None
    
    # File operations
    async def list_files(self, user_id: str, limit: int = 50,
                       folder_path: Optional[str] = None) -> List[TeamsFile]:
        """List files in user's OneDrive"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            endpoint = 'me/drive/root/children'
            if folder_path:
                endpoint = f"me/drive/root:/{folder_path}:/children"
            
            params = {}
            if limit > 0:
                params['$top'] = limit
            
            response = await self._make_api_request('GET', endpoint, params=params, access_token=access_token)
            
            if 'value' in response:
                return [TeamsFile(file) for file in response['value']]
            else:
                logger.error(f"Error listing Teams files: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing Teams files: {e}")
            return []
    
    async def upload_file(self, user_id: str, file_path: str, filename: Optional[str] = None,
                        folder_path: Optional[str] = None) -> Optional[TeamsFile]:
        """Upload a file to user's OneDrive"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            # Read file
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
            except FileNotFoundError:
                logger.error(f"File not found: {file_path}")
                return None
            except Exception as e:
                logger.error(f"Error reading file: {e}")
                return None
            
            if not filename:
                filename = os.path.basename(file_path)
            
            endpoint = 'me/drive/root/children'
            if folder_path:
                endpoint = f"me/drive/root:/{folder_path}:/children"
            
            data = {
                'name': filename,
                'file': file_content
            }
            
            response = await self._make_api_request('POST', endpoint, data=data, access_token=access_token)
            
            if response and not response.get('error'):
                return TeamsFile(response)
            else:
                logger.error(f"Error uploading Teams file: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error uploading Teams file: {e}")
            return None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'name': 'Enhanced Microsoft Teams Service',
            'version': '2.0.0',
            'mock_mode': self._mock_mode,
            'api_base_url': self.api_base_url,
            'timeout': self.timeout,
            'capabilities': [
                'List channels',
                'Get channel info',
                'Send messages',
                'List messages',
                'List users',
                'Get user info',
                'List meetings',
                'Create meetings',
                'List files',
                'Upload files'
            ]
        }

# Create singleton instance
teams_enhanced_service = TeamsService()