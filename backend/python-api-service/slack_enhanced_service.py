"""
Enhanced Slack Service Implementation
Complete Slack integration with comprehensive API operations
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
    from db_oauth_slack_complete import get_user_slack_tokens, get_slack_user
    SLACK_DB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Slack database operations not available: {e}")
    SLACK_DB_AVAILABLE = False

# Slack API configuration
SLACK_API_BASE_URL = "https://slack.com/api"
DEFAULT_TIMEOUT = 30

# Configure logging
logger = logging.getLogger(__name__)

# Data model classes
class SlackMessage:
    """Slack message data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.ts = data.get("ts")
        self.text = data.get("text")
        self.user = data.get("user")
        self.channel = data.get("channel")
        self.thread_ts = data.get("thread_ts")
        self.username = data.get("username")
        self.bot_id = data.get("bot_id")
        self.files = data.get("files", [])
        self.reactions = data.get("reactions", [])
        self.pinned_to = data.get("pinned_to", [])
        self.message_type = data.get("type", "message")
        self.subtype = data.get("subtype")
        self.blocks = data.get("blocks", [])
        self.attachments = data.get("attachments", [])
        self.team = data.get("team")
        self.app_id = data.get("app_id")
        self.edited = data.get("edited", {})
        self.last_read = data.get("last_read")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ts': self.ts,
            'text': self.text,
            'user': self.user,
            'channel': self.channel,
            'thread_ts': self.thread_ts,
            'username': self.username,
            'bot_id': self.bot_id,
            'files': self.files,
            'reactions': self.reactions,
            'pinned_to': self.pinned_to,
            'type': self.message_type,
            'subtype': self.subtype,
            'blocks': self.blocks,
            'attachments': self.attachments,
            'team': self.team,
            'app_id': self.app_id,
            'edited': self.edited,
            'last_read': self.last_read
        }

class SlackChannel:
    """Slack channel data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.is_channel = data.get("is_channel", False)
        self.is_group = data.get("is_group", False)
        self.is_im = data.get("is_im", False)
        self.is_mpim = data.get("is_mpim", False)
        self.is_private = data.get("is_private", False)
        self.is_archived = data.get("is_archived", False)
        self.is_general = data.get("is_general", False)
        self.name_normalized = data.get("name_normalized")
        self.is_shared = data.get("is_shared", False)
        self.is_org_shared = data.get("is_org_shared", False)
        self.is_pending_ext_shared = data.get("is_pending_ext_shared", False)
        self.parent_conversation = data.get("parent_conversation")
        self.creator = data.get("creator")
        self.is_ext_shared = data.get("is_ext_shared", False)
        self.shared_team_ids = data.get("shared_team_ids", [])
        self.num_members = data.get("num_members")
        self.topic = data.get("topic", {}).get("value", "")
        self.purpose = data.get("purpose", {}).get("value", "")
        self.previous_names = data.get("previous_names", [])
        self.priority = data.get("priority")
        self.created = data.get("created")
        self.connected_team_ids = data.get("connected_team_ids", [])
        self.conversation_host_id = data.get("conversation_host_id")
        self.internal_team_ids = data.get("internal_team_ids", [])
        self.unlinked = data.get("unlinked", False)
        self.notifications = data.get("notifications")
        self.joined = data.get("is_member", True)
        self.pending_shared = data.get("is_pending_shared", [])
        self.date_last_read = data.get("date_last_read")
        self.unread_count = data.get("unread_count", 0)
        self.unread_count_display = data.get("unread_count_display", 0)
        self.user_limit = data.get("user_limit")
        self.who_can_post = data.get("who_can_post")
        self.slack_commands_enabled = data.get("slack_commands_enabled", True)
        self.blocks = data.get("blocks")
        self.attachments = data.get("attachments")
        self.team = data.get("team")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'is_channel': self.is_channel,
            'is_group': self.is_group,
            'is_im': self.is_im,
            'is_mpim': self.is_mpim,
            'is_private': self.is_private,
            'is_archived': self.is_archived,
            'is_general': self.is_general,
            'name_normalized': self.name_normalized,
            'is_shared': self.is_shared,
            'is_org_shared': self.is_org_shared,
            'is_pending_ext_shared': self.is_pending_ext_shared,
            'parent_conversation': self.parent_conversation,
            'creator': self.creator,
            'is_ext_shared': self.is_ext_shared,
            'shared_team_ids': self.shared_team_ids,
            'num_members': self.num_members,
            'topic': self.topic,
            'purpose': self.purpose,
            'previous_names': self.previous_names,
            'priority': self.priority,
            'created': self.created,
            'connected_team_ids': self.connected_team_ids,
            'conversation_host_id': self.conversation_host_id,
            'internal_team_ids': self.internal_team_ids,
            'unlinked': self.unlinked,
            'notifications': self.notifications,
            'joined': self.joined,
            'pending_shared': self.pending_shared,
            'date_last_read': self.date_last_read,
            'unread_count': self.unread_count,
            'unread_count_display': self.unread_count_display,
            'user_limit': self.user_limit,
            'who_can_post': self.who_can_post,
            'slack_commands_enabled': self.slack_commands_enabled,
            'blocks': self.blocks,
            'attachments': self.attachments,
            'team': self.team
        }

class SlackUser:
    """Slack user data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.real_name = data.get("real_name")
        self.display_name = data.get("profile", {}).get("display_name") or data.get("profile", {}).get("real_name")
        self.email = data.get("profile", {}).get("email")
        self.image_24 = data.get("profile", {}).get("image_24")
        self.image_32 = data.get("profile", {}).get("image_32")
        self.image_48 = data.get("profile", {}).get("image_48")
        self.image_72 = data.get("profile", {}).get("image_72")
        self.image_192 = data.get("profile", {}).get("image_192")
        self.image_512 = data.get("profile", {}).get("image_512")
        self.title = data.get("profile", {}).get("title")
        self.phone = data.get("profile", {}).get("phone")
        self.skype = data.get("profile", {}).get("skype")
        self.team_id = data.get("team_id")
        self.deleted = data.get("deleted", False)
        self.status = data.get("status")
        self.is_bot = data.get("is_bot", False)
        self.is_admin = data.get("is_admin", False)
        self.is_owner = data.get("is_owner", False)
        self.is_primary_owner = data.get("is_primary_owner", False)
        self.is_restricted = data.get("is_restricted", False)
        self.is_ultra_restricted = data.get("is_ultra_restricted", False)
        self.is_app_user = data.get("is_app_user", False)
        self.has_files = data.get("has_files", False)
        self.presence = data.get("presence")
        self.tz = data.get("tz")
        self.tz_label = data.get("tz_label")
        self.tz_offset = data.get("tz_offset")
        self.pronouns = data.get("profile", {}).get("pronouns")
        self.is_workflow_bot = data.get("is_workflow_bot", False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'real_name': self.real_name,
            'display_name': self.display_name,
            'email': self.email,
            'image_24': self.image_24,
            'image_32': self.image_32,
            'image_48': self.image_48,
            'image_72': self.image_72,
            'image_192': self.image_192,
            'image_512': self.image_512,
            'title': self.title,
            'phone': self.phone,
            'skype': self.skype,
            'team_id': self.team_id,
            'deleted': self.deleted,
            'status': self.status,
            'is_bot': self.is_bot,
            'is_admin': self.is_admin,
            'is_owner': self.is_owner,
            'is_primary_owner': self.is_primary_owner,
            'is_restricted': self.is_restricted,
            'is_ultra_restricted': self.is_ultra_restricted,
            'is_app_user': self.is_app_user,
            'has_files': self.has_files,
            'presence': self.presence,
            'tz': self.tz,
            'tz_label': self.tz_label,
            'tz_offset': self.tz_offset,
            'pronouns': self.pronouns,
            'is_workflow_bot': self.is_workflow_bot
        }

class SlackFile:
    """Slack file data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.created = data.get("created")
        self.timestamp = data.get("timestamp")
        self.name = data.get("name")
        self.title = data.get("title")
        self.mimetype = data.get("mimetype")
        self.filetype = data.get("filetype")
        self.pretty_type = data.get("pretty_type")
        self.user = data.get("user")
        self.mode = data.get("mode")
        self.editable = data.get("editable", False)
        self.size = data.get("size")
        self.is_public = data.get("is_public", False)
        self.public_url_shared = data.get("public_url_shared", False)
        self.url_private = data.get("url_private")
        self.url_private_download = data.get("url_private_download")
        self.display_as_bot = data.get("display_as_bot", False)
        self.comments_count = data.get("comments_count", 0)
        self.shares = data.get("shares", {})
        self.channels = data.get("channels", [])
        self.groups = data.get("groups", [])
        self.ims = data.get("ims", [])
        self.has_rich_preview = data.get("has_rich_preview", False)
        self.external_id = data.get("external_id")
        self.external_url = data.get("external_url")
        self.uploaded = data.get("uploaded")
        self.initial_comment = data.get("initial_comment", {})
        self.permalink = data.get("permalink")
        self.permalink_public = data.get("permalink_public")
        self.has_more = data.get("has_more", False)
        self.preview_highlight = data.get("preview_highlight")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'created': self.created,
            'timestamp': self.timestamp,
            'name': self.name,
            'title': self.title,
            'mimetype': self.mimetype,
            'filetype': self.filetype,
            'pretty_type': self.pretty_type,
            'user': self.user,
            'mode': self.mode,
            'editable': self.editable,
            'size': self.size,
            'is_public': self.is_public,
            'public_url_shared': self.public_url_shared,
            'url_private': self.url_private,
            'url_private_download': self.url_private_download,
            'display_as_bot': self.display_as_bot,
            'comments_count': self.comments_count,
            'shares': self.shares,
            'channels': self.channels,
            'groups': self.groups,
            'ims': self.ims,
            'has_rich_preview': self.has_rich_preview,
            'external_id': self.external_id,
            'external_url': self.external_url,
            'uploaded': self.uploaded,
            'initial_comment': self.initial_comment,
            'permalink': self.permalink,
            'permalink_public': self.permalink_public,
            'has_more': self.has_more,
            'preview_highlight': self.preview_highlight
        }

class SlackService:
    """Enhanced Slack service class"""
    
    def __init__(self):
        self._mock_mode = True
        self.api_base_url = SLACK_API_BASE_URL
        self.timeout = DEFAULT_TIMEOUT
        self._mock_db = {
            'channels': [],
            'messages': [],
            'users': [],
            'files': [],
            'webhooks': []
        }
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data for testing"""
        # Mock channels
        self._mock_db['channels'] = [
            SlackChannel({
                'id': 'C1234567890',
                'name': 'general',
                'is_channel': True,
                'is_private': False,
                'is_archived': False,
                'is_general': True,
                'topic': {'value': 'Team discussions and announcements'},
                'purpose': {'value': 'This channel is for team-wide communication and announcements.'},
                'num_members': 25,
                'created': 1234567890,
                'unread_count': 0,
                'unread_count_display': 0
            }),
            SlackChannel({
                'id': 'C0987654321',
                'name': 'random',
                'is_channel': True,
                'is_private': False,
                'is_archived': False,
                'is_general': False,
                'topic': {'value': 'Random discussions and fun'},
                'purpose': {'value': 'A place for non-work-related discussions.'},
                'num_members': 18,
                'created': 1234567895,
                'unread_count': 0,
                'unread_count_display': 0
            }),
            SlackChannel({
                'id': 'C1122334455',
                'name': 'dev-team',
                'is_channel': True,
                'is_private': False,
                'is_archived': False,
                'is_general': False,
                'topic': {'value': 'Development team discussions'},
                'purpose': {'value': 'Development discussions, code reviews, and technical updates.'},
                'num_members': 12,
                'created': 1234567900,
                'unread_count': 0,
                'unread_count_display': 0
            })
        ]
        
        # Mock users
        self._mock_db['users'] = [
            SlackUser({
                'id': 'U1234567890',
                'name': 'alex.dev',
                'real_name': 'Alex Developer',
                'profile': {
                    'display_name': 'Alex',
                    'email': 'alex@company.com',
                    'image_24': 'https://example.com/avatar_24.jpg',
                    'image_48': 'https://example.com/avatar_48.jpg',
                    'image_192': 'https://example.com/avatar_192.jpg',
                    'title': 'Senior Developer'
                },
                'is_admin': True,
                'is_owner': False,
                'deleted': False,
                'has_files': True,
                'presence': 'active'
            }),
            SlackUser({
                'id': 'U0987654321',
                'name': 'sarah.manager',
                'real_name': 'Sarah Manager',
                'profile': {
                    'display_name': 'Sarah',
                    'email': 'sarah@company.com',
                    'image_24': 'https://example.com/sarah_24.jpg',
                    'image_48': 'https://example.com/sarah_48.jpg',
                    'image_192': 'https://example.com/sarah_192.jpg',
                    'title': 'Project Manager'
                },
                'is_admin': False,
                'is_owner': True,
                'deleted': False,
                'has_files': False,
                'presence': 'away'
            }),
            SlackUser({
                'id': 'U1122334455',
                'name': 'mike.designer',
                'real_name': 'Mike Designer',
                'profile': {
                    'display_name': 'Mike',
                    'email': 'mike@company.com',
                    'image_24': 'https://example.com/mike_24.jpg',
                    'image_48': 'https://example.com/mike_48.jpg',
                    'image_192': 'https://example.com/mike_192.jpg',
                    'title': 'UI/UX Designer'
                },
                'is_admin': False,
                'is_owner': False,
                'deleted': False,
                'has_files': True,
                'presence': 'active'
            })
        ]
        
        # Mock messages
        now = datetime.utcnow().timestamp()
        self._mock_db['messages'] = [
            SlackMessage({
                'ts': str(now - 3600),  # 1 hour ago
                'text': 'Hey team! Just deployed the latest changes to staging. 🚀',
                'user': 'U1234567890',
                'channel': 'C1122334455',
                'reactions': [
                    {'name': 'rocket', 'count': 3},
                    {'name': 'thumbsup', 'count': 5}
                ]
            }),
            SlackMessage({
                'ts': str(now - 7200),  # 2 hours ago
                'text': 'The new designs look amazing! Great work Mike! 🎨',
                'user': 'U0987654321',
                'channel': 'C1122334455',
                'reactions': [
                    {'name': 'thumbsup', 'count': 2},
                    {'name': 'art', 'count': 1}
                ]
            }),
            SlackMessage({
                'ts': str(now - 10800),  # 3 hours ago
                'text': 'Daily standup in 15 minutes. Please have your updates ready!',
                'user': 'U0987654321',
                'channel': 'C1234567890',
                'pinned_to': ['C1234567890']
            })
        ]
        
        # Mock files
        self._mock_db['files'] = [
            SlackFile({
                'id': 'F1234567890',
                'name': 'project-specs.pdf',
                'title': 'Project Specifications',
                'mimetype': 'application/pdf',
                'filetype': 'pdf',
                'pretty_type': 'PDF',
                'user': 'U1234567890',
                'size': 2048576,
                'is_public': False,
                'url_private': 'https://files.slack.com/files-pri/T1234567890-F1234567890/project-specs.pdf',
                'url_private_download': 'https://files.slack.com/files-pri/T1234567890-F1234567890/download/project-specs.pdf',
                'created': now - 86400,
                'timestamp': now - 86400,
                'permalink': 'https://company.slack.com/files/U1234567890/F1234567890/project-specs.pdf',
                'comments_count': 2,
                'channels': ['C1122334455']
            }),
            SlackFile({
                'id': 'F0987654321',
                'name': 'mockup.sketch',
                'title': 'Design Mockup',
                'mimetype': 'image/png',
                'filetype': 'png',
                'pretty_type': 'PNG',
                'user': 'U1122334455',
                'size': 1536000,
                'is_public': False,
                'url_private': 'https://files.slack.com/files-pri/T1234567890-F0987654321/mockup.sketch',
                'url_private_download': 'https://files.slack.com/files-pri/T1234567890-F0987654321/download/mockup.sketch',
                'created': now - 43200,
                'timestamp': now - 43200,
                'permalink': 'https://company.slack.com/files/U1122334455/F0987654321/mockup.sketch',
                'comments_count': 5,
                'channels': ['C1122334455']
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
            return os.getenv('SLACK_ACCESS_TOKEN', 'mock_slack_token')
        
        # In real implementation, this would fetch from database
        if SLACK_DB_AVAILABLE:
            tokens = await get_user_slack_tokens(None, user_id)
            if tokens:
                access_token = tokens.get('access_token', '')
                if ENCRYPTION_AVAILABLE and isinstance(access_token, bytes):
                    access_token = decrypt_data(access_token, os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                return access_token
        return None
    
    async def _make_api_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                             data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None,
                             access_token: Optional[str] = None) -> Dict[str, Any]:
        """Make API request to Slack"""
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
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Slack API request error: {e}")
            return {'ok': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected Slack API request error: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def _make_mock_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                               data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make mock API request"""
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        endpoint = endpoint.lower()
        
        # Mock channel operations
        if 'conversations.list' in endpoint or 'channels.list' in endpoint:
            channels = [channel.to_dict() for channel in self._mock_db['channels']]
            if params and params.get('types'):
                types = params['types'].split(',')
                filtered_channels = []
                for channel in channels:
                    if 'public_channel' in types and channel['is_channel'] and not channel['is_private']:
                        filtered_channels.append(channel)
                    elif 'private_channel' in types and channel['is_channel'] and channel['is_private']:
                        filtered_channels.append(channel)
                    elif 'im' in types and channel['is_im']:
                        filtered_channels.append(channel)
                    elif 'mpim' in types and channel['is_mpim']:
                        filtered_channels.append(channel)
                channels = filtered_channels
            return {'ok': True, 'channels': channels}
        
        # Mock message operations
        elif 'conversations.history' in endpoint or 'channels.history' in endpoint:
            channel_id = params.get('channel') if params else data.get('channel')
            if not channel_id:
                return {'ok': False, 'error': 'Channel ID is required'}
            
            # Filter messages by channel
            messages = [msg.to_dict() for msg in self._mock_db['messages'] 
                        if msg.channel == channel_id]
            
            # Sort by timestamp (newest first)
            messages.sort(key=lambda x: float(x['ts']), reverse=True)
            
            # Apply limit
            limit = params.get('limit', 100) if params else data.get('limit', 100)
            messages = messages[:limit]
            
            return {'ok': True, 'messages': messages, 'has_more': False}
        
        # Mock message posting
        elif 'chat.postmessage' in endpoint or 'chat.postmessage' in endpoint:
            if not data:
                return {'ok': False, 'error': 'Message data is required'}
            
            channel_id = data.get('channel')
            text = data.get('text')
            
            if not channel_id or not text:
                return {'ok': False, 'error': 'Channel and text are required'}
            
            # Create mock message
            ts = str(datetime.utcnow().timestamp())
            new_message = SlackMessage({
                'ts': ts,
                'text': text,
                'user': 'U1234567890',  # Current user
                'channel': channel_id,
                'team': 'T1234567890'
            })
            
            self._mock_db['messages'].append(new_message)
            
            return {
                'ok': True,
                'ts': ts,
                'message': new_message.to_dict()
            }
        
        # Mock file upload
        elif 'files.upload' in endpoint:
            if not files:
                return {'ok': False, 'error': 'No files provided'}
            
            # Create mock file
            file_id = f"F{int(datetime.utcnow().timestamp())}"
            ts = datetime.utcnow().timestamp()
            
            mock_file = SlackFile({
                'id': file_id,
                'name': files.get('file', {}).get('filename', 'uploaded_file'),
                'mimetype': files.get('file', {}).get('content_type', 'application/octet-stream'),
                'size': len(files.get('file', {}).get('content', b'')),
                'user': 'U1234567890',
                'channels': data.get('channels', []),
                'timestamp': int(ts),
                'created': int(ts),
                'permalink': f"https://company.slack.com/files/U1234567890/{file_id}/uploaded_file",
                'url_private': f"https://files.slack.com/files-pri/T1234567890-{file_id}/uploaded_file"
            })
            
            self._mock_db['files'].append(mock_file)
            
            return {
                'ok': True,
                'file': mock_file.to_dict()
            }
        
        # Mock user operations
        elif 'users.list' in endpoint:
            users = [user.to_dict() for user in self._mock_db['users']]
            return {'ok': True, 'members': users}
        
        elif 'users.info' in endpoint:
            user_id = params.get('user') if params else data.get('user')
            if not user_id:
                return {'ok': False, 'error': 'User ID is required'}
            
            user = next((u for u in self._mock_db['users'] if u.id == user_id), None)
            if user:
                return {'ok': True, 'user': user.to_dict()}
            else:
                return {'ok': False, 'error': 'User not found'}
        
        # Mock file operations
        elif 'files.list' in endpoint:
            files = [file.to_dict() for file in self._mock_db['files']]
            if params and params.get('user'):
                user_id = params['user']
                files = [f for f in files if f['user'] == user_id]
            if params and params.get('channel'):
                channel_id = params['channel']
                files = [f for f in files if channel_id in f['channels']]
            return {'ok': True, 'files': files}
        
        elif 'files.info' in endpoint:
            file_id = params.get('file') if params else data.get('file')
            if not file_id:
                return {'ok': False, 'error': 'File ID is required'}
            
            file = next((f for f in self._mock_db['files'] if f.id == file_id), None)
            if file:
                return {'ok': True, 'file': file.to_dict()}
            else:
                return {'ok': False, 'error': 'File not found'}
        
        # Mock channel creation
        elif 'conversations.create' in endpoint:
            if not data:
                return {'ok': False, 'error': 'Channel data is required'}
            
            name = data.get('name')
            if not name:
                return {'ok': False, 'error': 'Channel name is required'}
            
            # Create mock channel
            channel_id = f"C{int(datetime.utcnow().timestamp())}"
            created = int(datetime.utcnow().timestamp())
            
            new_channel = SlackChannel({
                'id': channel_id,
                'name': name,
                'is_channel': True,
                'is_private': data.get('is_private', False),
                'is_archived': False,
                'is_general': False,
                'topic': {'value': data.get('topic', '')},
                'purpose': {'value': data.get('purpose', '')},
                'num_members': 1,
                'created': created
            })
            
            self._mock_db['channels'].append(new_channel)
            
            return {
                'ok': True,
                'channel': new_channel.to_dict()
            }
        
        # Default mock response
        return {
            'ok': True,
            'mock_response': True,
            'endpoint': endpoint,
            'method': method,
            'params': params,
            'data': data
        }
    
    # Channel operations
    async def list_channels(self, user_id: str, types: Optional[List[str]] = None, 
                          exclude_archived: bool = True, limit: int = 100) -> List[SlackChannel]:
        """List channels accessible to user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {}
            if types:
                params['types'] = ','.join(types)
            if exclude_archived:
                params['exclude_archived'] = 'true'
            params['limit'] = str(limit)
            
            response = await self._make_api_request('GET', 'conversations.list', params=params, 
                                                access_token=access_token)
            
            if response.get('ok'):
                return [SlackChannel(channel) for channel in response.get('channels', [])]
            else:
                logger.error(f"Error listing channels: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing channels: {e}")
            return []
    
    async def create_channel(self, user_id: str, name: str, is_private: bool = False,
                            topic: str = "", purpose: str = "") -> Optional[SlackChannel]:
        """Create a new channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            data = {
                'name': name,
                'is_private': is_private
            }
            
            if topic:
                data['topic'] = topic
            if purpose:
                data['purpose'] = purpose
            
            response = await self._make_api_request('POST', 'conversations.create', data=data,
                                                access_token=access_token)
            
            if response.get('ok'):
                return SlackChannel(response.get('channel', {}))
            else:
                logger.error(f"Error creating channel: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error creating channel: {e}")
            return None
    
    # Message operations
    async def send_message(self, user_id: str, channel: str, text: str, 
                          thread_ts: Optional[str] = None, parse: Optional[str] = None,
                          blocks: Optional[List[Dict[str, Any]]] = None,
                          attachments: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """Send a message to a channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            data = {
                'channel': channel,
                'text': text
            }
            
            if thread_ts:
                data['thread_ts'] = thread_ts
            if parse:
                data['parse'] = parse
            if blocks:
                data['blocks'] = blocks
            if attachments:
                data['attachments'] = attachments
            
            response = await self._make_api_request('POST', 'chat.postMessage', data=data,
                                                access_token=access_token)
            
            if response.get('ok'):
                return {
                    'ok': True,
                    'ts': response.get('ts'),
                    'message': response.get('message')
                }
            else:
                logger.error(f"Error sending message: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return None
    
    async def list_messages(self, user_id: str, channel: str, limit: int = 100,
                         oldest: Optional[str] = None, latest: Optional[str] = None,
                         inclusive: bool = False) -> List[SlackMessage]:
        """List messages from a channel"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {
                'channel': channel,
                'limit': str(limit)
            }
            
            if oldest:
                params['oldest'] = oldest
            if latest:
                params['latest'] = latest
            if inclusive:
                params['inclusive'] = 'true'
            
            response = await self._make_api_request('GET', 'conversations.history', params=params,
                                                access_token=access_token)
            
            if response.get('ok'):
                return [SlackMessage(msg) for msg in response.get('messages', [])]
            else:
                logger.error(f"Error listing messages: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing messages: {e}")
            return []
    
    # File operations
    async def upload_file(self, user_id: str, file_path: str, filename: Optional[str] = None,
                        title: Optional[str] = None, initial_comment: Optional[str] = None,
                        channels: Optional[List[str]] = None) -> Optional[SlackFile]:
        """Upload a file to Slack"""
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
            
            data = {}
            files = {
                'file': (filename, file_content)
            }
            
            if title:
                data['title'] = title
            if initial_comment:
                data['initial_comment'] = initial_comment
            if channels:
                data['channels'] = ','.join(channels)
            
            response = await self._make_api_request('POST', 'files.upload', data=data, files=files,
                                                access_token=access_token)
            
            if response.get('ok'):
                return SlackFile(response.get('file', {}))
            else:
                logger.error(f"Error uploading file: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            return None
    
    async def list_files(self, user_id: str, limit: int = 100, 
                       user_filter: Optional[str] = None, channel: Optional[str] = None,
                       types_filter: Optional[List[str]] = None) -> List[SlackFile]:
        """List files from Slack"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {
                'limit': str(limit)
            }
            
            if user_filter:
                params['user'] = user_filter
            if channel:
                params['channel'] = channel
            if types_filter:
                params['filetypes'] = ','.join(types_filter)
            
            response = await self._make_api_request('GET', 'files.list', params=params,
                                                access_token=access_token)
            
            if response.get('ok'):
                return [SlackFile(file) for file in response.get('files', [])]
            else:
                logger.error(f"Error listing files: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            return []
    
    # User operations
    async def list_users(self, user_id: str, limit: int = 1000, 
                       presence: bool = False, team_id: Optional[str] = None) -> List[SlackUser]:
        """List users from workspace"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return []
            
            params = {
                'limit': str(limit)
            }
            
            if presence:
                params['presence'] = 'true'
            if team_id:
                params['team_id'] = team_id
            
            response = await self._make_api_request('GET', 'users.list', params=params,
                                                access_token=access_token)
            
            if response.get('ok'):
                return [SlackUser(user) for user in response.get('members', [])]
            else:
                logger.error(f"Error listing users: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing users: {e}")
            return []
    
    async def get_user_info(self, user_id: str, target_user_id: str) -> Optional[SlackUser]:
        """Get information about a specific user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.error(f"No access token found for user {user_id}")
                return None
            
            params = {
                'user': target_user_id
            }
            
            response = await self._make_api_request('GET', 'users.info', params=params,
                                                access_token=access_token)
            
            if response.get('ok'):
                return SlackUser(response.get('user', {}))
            else:
                logger.error(f"Error getting user info: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting user info: {e}")
            return None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'name': 'Enhanced Slack Service',
            'version': '2.0.0',
            'mock_mode': self._mock_mode,
            'api_base_url': self.api_base_url,
            'timeout': self.timeout,
            'capabilities': [
                'List channels',
                'Create channel',
                'Send messages',
                'List messages',
                'Upload files',
                'List files',
                'List users',
                'Get user info'
            ]
        }

# Create singleton instance
slack_enhanced_service = SlackService()