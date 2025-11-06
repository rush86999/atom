"""
Slack Enhanced Service Implementation
Complete Slack team communication with API integration
"""

import os
import logging
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import httpx

# Configure logging
logger = logging.getLogger(__name__)

# Slack API configuration
SLACK_API_BASE_URL = "https://slack.com/api/v1"

@dataclass
class SlackWorkspace:
    """Slack workspace representation"""
    id: str
    name: str
    domain: str
    email_domain: str
    icon: Dict[str, Any]
    created: int
    plan: str
    enterprise_id: str
    enterprise_name: str
    is_verified: bool
    date_created: str
    url: str
    privacy: str
    limit: int
    account_tier: str
    total_users: int
    total_channels: int
    total_messages: int
    total_files: int
    features: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SlackChannel:
    """Slack channel representation"""
    id: str
    name: str
    name_normalized: str
    is_channel: bool
    is_group: bool
    is_im: bool
    is_mpim: bool
    is_private: bool
    is_archived: bool
    is_general: bool
    is_shared: bool
    is_org_shared: bool
    is_ext_shared: bool
    is_pending_ext_shared: bool
    topic: Dict[str, Any]
    purpose: Dict[str, Any]
    created: int
    creator: str
    members_count: int
    messages_count: int
    files_count: int
    last_read: str
    latest: str
    unread_count: int
    unread_count_display: int
    pinned_to: List[str]
    linked_channel_ids: List[str]
    shared_team_ids: List[str]
    previous_names: List[str]
    num_members: int
    locale: str
    user_count: int
    has_pins: bool
    pin_count: int
    is_threaded: bool
    thread_count: int
    workspace_id: str
    workspace_name: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SlackUser:
    """Slack user representation"""
    id: str
    team_id: str
    name: str
    deleted: bool
    color: str
    real_name: str
    tz: str
    tz_label: str
    tz_offset: int
    profile: Dict[str, Any]
    is_admin: bool
    is_owner: bool
    is_primary_owner: bool
    is_restricted: bool
    is_ultra_restricted: bool
    is_bot: bool
    is_app_user: bool
    is_stranger: bool
    is_invited_user: bool
    has_files: bool
    has_2fa: bool
    locale: str
    updated: int
    enterprise_id: str
    presence: str
    online: bool
    last_seen: str
    message_count: int
    file_count: int
    reaction_count: int
    mention_count: int
    workspace_id: str
    workspace_name: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SlackMessage:
    """Slack message representation"""
    id: str
    team: str
    channel: str
    user: str
    type: str
    subtype: str
    text: str
    ts: str
    thread_ts: str
    parent_user_id: str
    reply_count: int
    reply_users_count: int
    latest_reply: str
    reply_users: List[str]
    reactions: List[Dict[str, Any]]
    attachments: List[Dict[str, Any]]
    files: List[Dict[str, Any]]
    pinned_to: List[str]
    mentions: List[str]
    user_mentions: List[str]
    bot_id: str
    bot_profile: Dict[str, Any]
    app_id: str
    blocks: List[Dict[str, Any]]
    edited: Dict[str, Any]
    last_read: str
    unread_count: int
    subscribed: bool
    is_starred: bool
    has_reactions: bool
    reaction_count: int
    has_attachments: bool
    attachment_count: int
    has_files: bool
    file_count: int
    is_threaded: bool
    is_thread_parent: bool
    is_thread_reply: bool
    workspace_id: str
    workspace_name: str
    channel_name: str
    user_name: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SlackFile:
    """Slack file representation"""
    id: str
    created: int
    timestamp: int
    name: str
    title: str
    mimetype: str
    filetype: str
    pretty_type: str
    user: str
    mode: str
    editable: bool
    size: int
    is_external: bool
    external_type: str
    is_public: bool
    public_url_shared: bool
    display_as_bot: bool
    username: str
    url_private: str
    url_private_download: str
    thumb_64: str
    thumb_80: str
    thumb_360: str
    thumb_480: str
    thumb_720: str
    thumb_960: str
    thumb_1024: str
    original_w: int
    original_h: int
    thumb_w: int
    thumb_h: int
    image_exif_rotation: int
    permalink: str
    permalink_public: str
    comments_count: int
    shares: Dict[str, Any]
    channels: List[str]
    groups: List[str]
    ims: List[str]
    num_channels: int
    num_groups: int
    num_ims: int
    has_rich_preview: bool
    rich_preview: Dict[str, Any]
    workspace_id: str
    workspace_name: str
    uploader_name: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SlackReaction:
    """Slack reaction representation"""
    name: str
    count: int
    users: List[str]
    message_id: str
    channel_id: str
    workspace_id: str
    workspace_name: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SlackWebhook:
    """Slack webhook representation"""
    id: str
    team_id: str
    enterprise_id: str
    channel_id: str
    configuration_url: str
    url: str
    active: bool
    created_at: int
    updated_at: int
    trigger_id: str
    app_id: str
    app_name: str
    workspace_id: str
    workspace_name: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

class SlackEnhancedService:
    """Enhanced Slack service with complete team communication automation"""
    
    def __init__(self, bot_token: str = None, user_token: str = None):
        self.bot_token = bot_token or os.getenv('SLACK_BOT_TOKEN')
        self.user_token = user_token or os.getenv('SLACK_USER_TOKEN')
        self.api_base_url = SLACK_API_BASE_URL
        
        # Cache for storing data
        self.workspaces_cache = {}
        self.channels_cache = {}
        self.users_cache = {}
        self.messages_cache = {}
        self.files_cache = {}
        self.reactions_cache = {}
        self.webhooks_cache = {}
        
        # Common Slack channel types
        self.channel_types = {
            'public_channel': 'Public Channel',
            'private_channel': 'Private Channel',
            'im': 'Direct Message',
            'mpim': 'Group Direct Message',
            'shared_channel': 'Shared Channel',
            'org_shared_channel': 'Org Shared Channel'
        }
        
        # Common Slack message types
        self.message_types = {
            'message': 'Message',
            'bot_message': 'Bot Message',
            'me_message': 'Me Message',
            'file_share': 'File Share',
            'file_comment': 'File Comment',
            'message_changed': 'Message Changed',
            'message_deleted': 'Message Deleted',
            'channel_join': 'Channel Join',
            'channel_leave': 'Channel Leave',
            'channel_topic': 'Channel Topic',
            'channel_purpose': 'Channel Purpose',
            'channel_name': 'Channel Name',
            'channel_archive': 'Channel Archive',
            'channel_unarchive': 'Channel Unarchive',
            'group_join': 'Group Join',
            'group_leave': 'Group Leave',
            'group_topic': 'Group Topic',
            'group_purpose': 'Group Purpose',
            'group_name': 'Group Name',
            'group_archive': 'Group Archive',
            'group_unarchive': 'Group Unarchive'
        }
        
        # Common Slack file types
        self.file_types = {
            'auto': 'Auto',
            'jpg': 'JPEG Image',
            'jpeg': 'JPEG Image',
            'png': 'PNG Image',
            'gif': 'GIF Image',
            'bmp': 'Bitmap Image',
            'tiff': 'TIFF Image',
            'mp4': 'MP4 Video',
            'mov': 'MOV Video',
            'avi': 'AVI Video',
            'wmv': 'WMV Video',
            'mp3': 'MP3 Audio',
            'wav': 'WAV Audio',
            'pdf': 'PDF Document',
            'doc': 'Word Document',
            'docx': 'Word Document',
            'xls': 'Excel Spreadsheet',
            'xlsx': 'Excel Spreadsheet',
            'ppt': 'PowerPoint Presentation',
            'pptx': 'PowerPoint Presentation',
            'txt': 'Text File',
            'zip': 'ZIP Archive',
            'tar': 'TAR Archive',
            'gz': 'GZ Archive',
            'other': 'Other'
        }
    
    def _get_auth_headers(self, token_type: str = 'bot') -> Dict[str, str]:
        """Get authentication headers"""
        if token_type == 'bot':
            token = self.bot_token
        else:
            token = self.user_token
        
        if not token:
            raise ValueError('No Slack token available')
        
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def _build_url(self, endpoint: str) -> str:
        """Build complete API URL"""
        return f"{self.api_base_url}/{endpoint}"
    
    async def _make_request(self, method: str, endpoint: str, 
                          params: Dict[str, Any] = None,
                          data: Dict[str, Any] = None,
                          token_type: str = 'bot') -> Dict[str, Any]:
        """Make HTTP request to Slack API"""
        try:
            # Build URL
            url = self._build_url(endpoint)
            
            # Get auth headers
            headers = self._get_auth_headers(token_type)
            
            # Make request
            async with httpx.AsyncClient(timeout=30) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, params=params, headers=headers)
                elif method.upper() == 'POST':
                    response = await client.post(url, params=params, json=data, headers=headers)
                elif method.upper() == 'PUT':
                    response = await client.put(url, params=params, json=data, headers=headers)
                elif method.upper() == 'PATCH':
                    response = await client.patch(url, params=params, json=data, headers=headers)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, params=params, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Parse JSON response
                response_data = response.json()
                
                # Check if Slack API returned success
                if not response_data.get('ok', False):
                    error = response_data.get('error', 'Unknown error')
                    logger.error(f"Slack API error: {error}")
                    return {
                        'error': error,
                        'type': 'api_error'
                    }
                
                return response_data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Slack API HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                'error': f'HTTP {e.response.status_code}',
                'message': e.response.text,
                'type': 'http_error'
            }
        except Exception as e:
            logger.error(f"Slack API request error: {e}")
            return {
                'error': str(e),
                'type': 'request_error'
            }
    
    def _generate_cache_key(self, team_id: str, entity_id: str) -> str:
        """Generate cache key"""
        return f"{team_id}:{entity_id}"
    
    async def get_workspaces(self, user_id: str = None) -> List[SlackWorkspace]:
        """Get Slack workspaces (requires user token)"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', 'workspaces')
            if cache_key in self.workspaces_cache:
                return self.workspaces_cache[cache_key]
            
            # Try to get team info first
            team_result = await self._make_request('GET', 'team.info', token_type='user')
            
            workspaces = []
            
            if team_result.get('ok') and team_result.get('team'):
                team_data = team_result.get('team')
                
                # Get basic team info
                team = SlackWorkspace(
                    id=team_data.get('id', ''),
                    name=team_data.get('name', ''),
                    domain=team_data.get('domain', ''),
                    email_domain=team_data.get('email_domain', ''),
                    icon=team_data.get('icon', {}),
                    created=team_data.get('created', 0),
                    plan=team_data.get('plan', ''),
                    enterprise_id=team_data.get('enterprise_id', ''),
                    enterprise_name=team_data.get('enterprise_name', ''),
                    is_verified=team_data.get('is_verified', False),
                    date_created=datetime.fromtimestamp(team_data.get('created', 0)).isoformat() if team_data.get('created') else '',
                    url=f"https://{team_data.get('domain', '')}.slack.com",
                    privacy=team_data.get('privacy', ''),
                    limit=team_data.get('limit', 0),
                    account_tier=team_data.get('account_tier', ''),
                    total_users=0,  # Will be calculated
                    total_channels=0,  # Will be calculated
                    total_messages=0,  # Will be calculated
                    total_files=0,  # Will be calculated
                    features=team_data.get('features', {}),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                
                # Get user count
                users_result = await self._make_request('GET', 'users.list', token_type='user')
                if users_result.get('ok'):
                    team.total_users = len(users_result.get('members', []))
                
                # Get channel count
                channels_result = await self._make_request('GET', 'conversations.list', 
                                                          {'types': 'public_channel,private_channel'}, 
                                                          token_type='user')
                if channels_result.get('ok'):
                    team.total_channels = len(channels_result.get('channels', []))
                
                workspaces.append(team)
            
            # Cache workspaces
            self.workspaces_cache[cache_key] = workspaces
            
            logger.info(f"Slack workspaces retrieved: {len(workspaces)}")
            return workspaces
            
        except Exception as e:
            logger.error(f"Error getting Slack workspaces: {e}")
            return []
    
    async def get_workspace(self, team_id: str, user_id: str = None) -> Optional[SlackWorkspace]:
        """Get Slack workspace by ID"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'workspace_{team_id}')
            if cache_key in self.workspaces_cache:
                return self.workspaces_cache[cache_key]
            
            # Make request
            result = await self._make_request('GET', 'team.info', {}, token_type='user')
            
            if result.get('ok') and result.get('team'):
                team_data = result.get('team')
                
                if team_data.get('id') == team_id:
                    # Create workspace object
                    workspace = SlackWorkspace(
                        id=team_data.get('id', ''),
                        name=team_data.get('name', ''),
                        domain=team_data.get('domain', ''),
                        email_domain=team_data.get('email_domain', ''),
                        icon=team_data.get('icon', {}),
                        created=team_data.get('created', 0),
                        plan=team_data.get('plan', ''),
                        enterprise_id=team_data.get('enterprise_id', ''),
                        enterprise_name=team_data.get('enterprise_name', ''),
                        is_verified=team_data.get('is_verified', False),
                        date_created=datetime.fromtimestamp(team_data.get('created', 0)).isoformat() if team_data.get('created') else '',
                        url=f"https://{team_data.get('domain', '')}.slack.com",
                        privacy=team_data.get('privacy', ''),
                        limit=team_data.get('limit', 0),
                        account_tier=team_data.get('account_tier', ''),
                        total_users=0,
                        total_channels=0,
                        total_messages=0,
                        total_files=0,
                        features=team_data.get('features', {}),
                        metadata={
                            'accessed_at': datetime.utcnow().isoformat(),
                            'source': 'slack_api'
                        }
                    )
                    
                    # Get user count
                    users_result = await self._make_request('GET', 'users.list', token_type='user')
                    if users_result.get('ok'):
                        workspace.total_users = len(users_result.get('members', []))
                    
                    # Get channel count
                    channels_result = await self._make_request('GET', 'conversations.list', 
                                                              {'types': 'public_channel,private_channel'}, 
                                                              token_type='user')
                    if channels_result.get('ok'):
                        workspace.total_channels = len(channels_result.get('channels', []))
                    
                    # Cache workspace
                    self.workspaces_cache[cache_key] = workspace
                    
                    logger.info(f"Slack workspace retrieved: {team_id}")
                    return workspace
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Slack workspace: {e}")
            return None
    
    async def get_channels(self, team_id: str, user_id: str = None, types: str = None) -> List[SlackChannel]:
        """Get Slack channels from workspace"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'channels_{team_id}')
            if cache_key in self.channels_cache:
                return self.channels_cache[cache_key]
            
            # Get workspace info first
            workspace = await self.get_workspace(team_id, user_id)
            if not workspace:
                return []
            
            # Build request parameters
            params = {}
            if types:
                params['types'] = types
            else:
                params['types'] = 'public_channel,private_channel,mpim,im'
            
            # Make request
            result = await self._make_request('GET', 'conversations.list', params, token_type='user')
            
            if not result.get('ok'):
                return []
            
            # Create channel objects
            channels = []
            for channel_data in result.get('channels', []):
                # Count messages in channel
                messages_count = 0
                try:
                    # Get recent messages to estimate count
                    history_result = await self._make_request('GET', 'conversations.history', 
                                                               {'channel': channel_data.get('id'), 'limit': 1}, 
                                                               token_type='user')
                    if history_result.get('ok') and history_result.get('messages'):
                        # Slack doesn't provide total count directly, so we'll estimate
                        messages_count = 0  # Will be updated when messages are actually fetched
                except:
                    pass
                
                channel = SlackChannel(
                    id=channel_data.get('id', ''),
                    name=channel_data.get('name', ''),
                    name_normalized=channel_data.get('name_normalized', ''),
                    is_channel=channel_data.get('is_channel', False),
                    is_group=channel_data.get('is_group', False),
                    is_im=channel_data.get('is_im', False),
                    is_mpim=channel_data.get('is_mpim', False),
                    is_private=channel_data.get('is_private', False),
                    is_archived=channel_data.get('is_archived', False),
                    is_general=channel_data.get('is_general', False),
                    is_shared=channel_data.get('is_shared', False),
                    is_org_shared=channel_data.get('is_org_shared', False),
                    is_ext_shared=channel_data.get('is_ext_shared', False),
                    is_pending_ext_shared=channel_data.get('is_pending_ext_shared', False),
                    topic=channel_data.get('topic', {}),
                    purpose=channel_data.get('purpose', {}),
                    created=channel_data.get('created', 0),
                    creator=channel_data.get('creator', ''),
                    members_count=channel_data.get('num_members', 0),
                    messages_count=messages_count,
                    files_count=0,  # Will be calculated
                    last_read=channel_data.get('last_read', ''),
                    latest=json.dumps(channel_data.get('latest', {})),
                    unread_count=channel_data.get('unread_count', 0),
                    unread_count_display=channel_data.get('unread_count_display', 0),
                    pinned_to=channel_data.get('pinned_to', []),
                    linked_channel_ids=channel_data.get('linked_channel_ids', []),
                    shared_team_ids=channel_data.get('shared_team_ids', []),
                    previous_names=channel_data.get('previous_names', []),
                    num_members=channel_data.get('num_members', 0),
                    locale=channel_data.get('locale', ''),
                    user_count=channel_data.get('user_count', 0),
                    has_pins=channel_data.get('has_pins', False),
                    pin_count=channel_data.get('pin_count', 0),
                    is_threaded=False,  # Will be determined from messages
                    thread_count=0,  # Will be calculated
                    workspace_id=team_id,
                    workspace_name=workspace.name,
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                channels.append(channel)
            
            # Cache channels
            self.channels_cache[cache_key] = channels
            
            logger.info(f"Slack channels retrieved: {len(channels)}")
            return channels
            
        except Exception as e:
            logger.error(f"Error getting Slack channels: {e}")
            return []
    
    async def get_channel(self, team_id: str, channel_id: str, user_id: str = None) -> Optional[SlackChannel]:
        """Get Slack channel by ID"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'channel_{team_id}_{channel_id}')
            if cache_key in self.channels_cache:
                return self.channels_cache[cache_key]
            
            # Make request
            result = await self._make_request('GET', 'conversations.info', 
                                             {'channel': channel_id}, 
                                             token_type='user')
            
            if result.get('ok') and result.get('channel'):
                # Get workspace info for metadata
                workspace = await self.get_workspace(team_id, user_id)
                
                channel_data = result.get('channel')
                
                channel = SlackChannel(
                    id=channel_data.get('id', ''),
                    name=channel_data.get('name', ''),
                    name_normalized=channel_data.get('name_normalized', ''),
                    is_channel=channel_data.get('is_channel', False),
                    is_group=channel_data.get('is_group', False),
                    is_im=channel_data.get('is_im', False),
                    is_mpim=channel_data.get('is_mpim', False),
                    is_private=channel_data.get('is_private', False),
                    is_archived=channel_data.get('is_archived', False),
                    is_general=channel_data.get('is_general', False),
                    is_shared=channel_data.get('is_shared', False),
                    is_org_shared=channel_data.get('is_org_shared', False),
                    is_ext_shared=channel_data.get('is_ext_shared', False),
                    is_pending_ext_shared=channel_data.get('is_pending_ext_shared', False),
                    topic=channel_data.get('topic', {}),
                    purpose=channel_data.get('purpose', {}),
                    created=channel_data.get('created', 0),
                    creator=channel_data.get('creator', ''),
                    members_count=channel_data.get('num_members', 0),
                    messages_count=0,
                    files_count=0,
                    last_read=channel_data.get('last_read', ''),
                    latest=json.dumps(channel_data.get('latest', {})),
                    unread_count=channel_data.get('unread_count', 0),
                    unread_count_display=channel_data.get('unread_count_display', 0),
                    pinned_to=channel_data.get('pinned_to', []),
                    linked_channel_ids=channel_data.get('linked_channel_ids', []),
                    shared_team_ids=channel_data.get('shared_team_ids', []),
                    previous_names=channel_data.get('previous_names', []),
                    num_members=channel_data.get('num_members', 0),
                    locale=channel_data.get('locale', ''),
                    user_count=channel_data.get('user_count', 0),
                    has_pins=channel_data.get('has_pins', False),
                    pin_count=channel_data.get('pin_count', 0),
                    is_threaded=False,
                    thread_count=0,
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                
                # Cache channel
                self.channels_cache[cache_key] = channel
                
                logger.info(f"Slack channel retrieved: {channel_id}")
                return channel
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Slack channel: {e}")
            return None
    
    async def get_messages(self, team_id: str, channel_id: str, 
                          limit: int = 100, latest: str = None, 
                          oldest: str = None, inclusive: bool = True,
                          user_id: str = None) -> Dict[str, Any]:
        """Get Slack messages from channel"""
        try:
            # Build parameters
            params = {
                'channel': channel_id,
                'limit': min(limit, 1000),  # Slack API limit
                'inclusive': 'true' if inclusive else 'false'
            }
            
            if latest:
                params['latest'] = latest
            if oldest:
                params['oldest'] = oldest
            
            # Make request
            result = await self._make_request('GET', 'conversations.history', params, token_type='user')
            
            if not result.get('ok'):
                return {
                    'messages': [],
                    'has_more': False,
                    'error': result.get('error'),
                    'response_metadata': {}
                }
            
            # Get workspace and channel info for metadata
            workspace = await self.get_workspace(team_id, user_id)
            channel = await self.get_channel(team_id, channel_id, user_id)
            
            # Create message objects
            messages = []
            for message_data in result.get('messages', []):
                # Count reactions
                reactions = message_data.get('reactions', [])
                reaction_count = sum(reaction.get('count', 0) for reaction in reactions)
                
                # Count attachments
                attachments = message_data.get('attachments', [])
                attachment_count = len(attachments)
                
                # Count files
                files = message_data.get('files', [])
                file_count = len(files)
                
                # Count mentions
                text = message_data.get('text', '')
                mentions = []
                user_mentions = []
                
                # Simple mention extraction (could be improved)
                import re
                mention_pattern = r'<@([UW][A-Z0-9]+)>'
                for match in re.findall(mention_pattern, text):
                    mentions.append(match)
                    user_mentions.append(match)
                
                # Get user info
                user_name = ''
                if message_data.get('user'):
                    user_result = await self._make_request('GET', 'users.info', 
                                                         {'user': message_data.get('user')}, 
                                                         token_type='user')
                    if user_result.get('ok') and user_result.get('user'):
                        user_name = user_result.get('user', {}).get('name', '')
                elif message_data.get('bot_profile'):
                    user_name = message_data.get('bot_profile', {}).get('name', '')
                
                message = SlackMessage(
                    id=message_data.get('ts', ''),
                    team=team_id,
                    channel=channel_id,
                    user=message_data.get('user', ''),
                    type=message_data.get('type', ''),
                    subtype=message_data.get('subtype', ''),
                    text=message_data.get('text', ''),
                    ts=message_data.get('ts', ''),
                    thread_ts=message_data.get('thread_ts', ''),
                    parent_user_id=message_data.get('parent_user_id', ''),
                    reply_count=message_data.get('reply_count', 0),
                    reply_users_count=message_data.get('reply_users_count', 0),
                    latest_reply=message_data.get('latest_reply', ''),
                    reply_users=message_data.get('reply_users', []),
                    reactions=reactions,
                    attachments=attachments,
                    files=files,
                    pinned_to=message_data.get('pinned_to', []),
                    mentions=mentions,
                    user_mentions=user_mentions,
                    bot_id=message_data.get('bot_id', ''),
                    bot_profile=message_data.get('bot_profile', {}),
                    app_id=message_data.get('app_id', ''),
                    blocks=message_data.get('blocks', []),
                    edited=message_data.get('edited', {}),
                    last_read='',
                    unread_count=0,
                    subscribed=False,
                    is_starred=False,
                    has_reactions=reaction_count > 0,
                    reaction_count=reaction_count,
                    has_attachments=attachment_count > 0,
                    attachment_count=attachment_count,
                    has_files=file_count > 0,
                    file_count=file_count,
                    is_threaded=message_data.get('thread_ts') is not None,
                    is_thread_parent=message_data.get('reply_count', 0) > 0,
                    is_thread_reply=message_data.get('thread_ts') is not None and message_data.get('reply_count', 0) == 0,
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    channel_name=channel.name if channel else '',
                    user_name=user_name,
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                messages.append(message)
            
            return {
                'messages': messages,
                'has_more': result.get('has_more', False),
                'response_metadata': result.get('response_metadata', {}),
                'total': len(messages)
            }
            
        except Exception as e:
            logger.error(f"Error getting Slack messages: {e}")
            return {
                'messages': [],
                'has_more': False,
                'error': str(e),
                'response_metadata': {}
            }
    
    async def get_message(self, team_id: str, channel_id: str, message_ts: str, 
                        user_id: str = None) -> Optional[SlackMessage]:
        """Get Slack message by timestamp"""
        try:
            # Make request
            result = await self._make_request('GET', 'conversations.history', 
                                             {'channel': channel_id, 'latest': message_ts, 
                                              'limit': 1, 'inclusive': 'true'}, 
                                             token_type='user')
            
            if result.get('ok') and result.get('messages'):
                # Get the first message
                message_data = result.get('messages', [{}])[0]
                
                # Get workspace and channel info for metadata
                workspace = await self.get_workspace(team_id, user_id)
                channel = await self.get_channel(team_id, channel_id, user_id)
                
                # Count reactions
                reactions = message_data.get('reactions', [])
                reaction_count = sum(reaction.get('count', 0) for reaction in reactions)
                
                # Count attachments
                attachments = message_data.get('attachments', [])
                attachment_count = len(attachments)
                
                # Count files
                files = message_data.get('files', [])
                file_count = len(files)
                
                # Count mentions
                text = message_data.get('text', '')
                mentions = []
                user_mentions = []
                
                # Simple mention extraction
                import re
                mention_pattern = r'<@([UW][A-Z0-9]+)>'
                for match in re.findall(mention_pattern, text):
                    mentions.append(match)
                    user_mentions.append(match)
                
                # Get user info
                user_name = ''
                if message_data.get('user'):
                    user_result = await self._make_request('GET', 'users.info', 
                                                         {'user': message_data.get('user')}, 
                                                         token_type='user')
                    if user_result.get('ok') and user_result.get('user'):
                        user_name = user_result.get('user', {}).get('name', '')
                elif message_data.get('bot_profile'):
                    user_name = message_data.get('bot_profile', {}).get('name', '')
                
                message = SlackMessage(
                    id=message_data.get('ts', ''),
                    team=team_id,
                    channel=channel_id,
                    user=message_data.get('user', ''),
                    type=message_data.get('type', ''),
                    subtype=message_data.get('subtype', ''),
                    text=message_data.get('text', ''),
                    ts=message_data.get('ts', ''),
                    thread_ts=message_data.get('thread_ts', ''),
                    parent_user_id=message_data.get('parent_user_id', ''),
                    reply_count=message_data.get('reply_count', 0),
                    reply_users_count=message_data.get('reply_users_count', 0),
                    latest_reply=message_data.get('latest_reply', ''),
                    reply_users=message_data.get('reply_users', []),
                    reactions=reactions,
                    attachments=attachments,
                    files=files,
                    pinned_to=message_data.get('pinned_to', []),
                    mentions=mentions,
                    user_mentions=user_mentions,
                    bot_id=message_data.get('bot_id', ''),
                    bot_profile=message_data.get('bot_profile', {}),
                    app_id=message_data.get('app_id', ''),
                    blocks=message_data.get('blocks', []),
                    edited=message_data.get('edited', {}),
                    last_read='',
                    unread_count=0,
                    subscribed=False,
                    is_starred=False,
                    has_reactions=reaction_count > 0,
                    reaction_count=reaction_count,
                    has_attachments=attachment_count > 0,
                    attachment_count=attachment_count,
                    has_files=file_count > 0,
                    file_count=file_count,
                    is_threaded=message_data.get('thread_ts') is not None,
                    is_thread_parent=message_data.get('reply_count', 0) > 0,
                    is_thread_reply=message_data.get('thread_ts') is not None and message_data.get('reply_count', 0) == 0,
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    channel_name=channel.name if channel else '',
                    user_name=user_name,
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                
                logger.info(f"Slack message retrieved: {message_ts}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Slack message: {e}")
            return None
    
    async def send_message(self, team_id: str, channel_id: str, text: str, 
                          thread_ts: str = None, user_id: str = None) -> Optional[SlackMessage]:
        """Send Slack message"""
        try:
            # Build request data
            data = {
                'channel': channel_id,
                'text': text
            }
            
            if thread_ts:
                data['thread_ts'] = thread_ts
            
            # Make request
            result = await self._make_request('POST', 'chat.postMessage', data)
            
            if result.get('ok') and result.get('message'):
                # Get workspace and channel info for metadata
                workspace = await self.get_workspace(team_id, user_id)
                channel = await self.get_channel(team_id, channel_id, user_id)
                
                message_data = result.get('message')
                
                # Count reactions
                reactions = message_data.get('reactions', [])
                reaction_count = sum(reaction.get('count', 0) for reaction in reactions)
                
                # Count attachments
                attachments = message_data.get('attachments', [])
                attachment_count = len(attachments)
                
                # Count files
                files = message_data.get('files', [])
                file_count = len(files)
                
                # Count mentions
                text_content = message_data.get('text', '')
                mentions = []
                user_mentions = []
                
                # Simple mention extraction
                import re
                mention_pattern = r'<@([UW][A-Z0-9]+)>'
                for match in re.findall(mention_pattern, text_content):
                    mentions.append(match)
                    user_mentions.append(match)
                
                # Get user info
                user_name = ''
                if message_data.get('user'):
                    user_result = await self._make_request('GET', 'users.info', 
                                                         {'user': message_data.get('user')}, 
                                                         token_type='user')
                    if user_result.get('ok') and user_result.get('user'):
                        user_name = user_result.get('user', {}).get('name', '')
                elif message_data.get('bot_profile'):
                    user_name = message_data.get('bot_profile', {}).get('name', '')
                
                message = SlackMessage(
                    id=message_data.get('ts', ''),
                    team=team_id,
                    channel=channel_id,
                    user=message_data.get('user', ''),
                    type=message_data.get('type', ''),
                    subtype=message_data.get('subtype', ''),
                    text=message_data.get('text', ''),
                    ts=message_data.get('ts', ''),
                    thread_ts=message_data.get('thread_ts', ''),
                    parent_user_id=message_data.get('parent_user_id', ''),
                    reply_count=message_data.get('reply_count', 0),
                    reply_users_count=message_data.get('reply_users_count', 0),
                    latest_reply=message_data.get('latest_reply', ''),
                    reply_users=message_data.get('reply_users', []),
                    reactions=reactions,
                    attachments=attachments,
                    files=files,
                    pinned_to=message_data.get('pinned_to', []),
                    mentions=mentions,
                    user_mentions=user_mentions,
                    bot_id=message_data.get('bot_id', ''),
                    bot_profile=message_data.get('bot_profile', {}),
                    app_id=message_data.get('app_id', ''),
                    blocks=message_data.get('blocks', []),
                    edited=message_data.get('edited', {}),
                    last_read='',
                    unread_count=0,
                    subscribed=False,
                    is_starred=False,
                    has_reactions=reaction_count > 0,
                    reaction_count=reaction_count,
                    has_attachments=attachment_count > 0,
                    attachment_count=attachment_count,
                    has_files=file_count > 0,
                    file_count=file_count,
                    is_threaded=message_data.get('thread_ts') is not None,
                    is_thread_parent=message_data.get('reply_count', 0) > 0,
                    is_thread_reply=message_data.get('thread_ts') is not None and message_data.get('reply_count', 0) == 0,
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    channel_name=channel.name if channel else '',
                    user_name=user_name,
                    metadata={
                        'created_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                
                # Clear cache
                self._clear_message_cache()
                
                logger.info(f"Slack message sent: {message.id}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
            return None
    
    async def update_message(self, team_id: str, channel_id: str, message_ts: str, text: str,
                            user_id: str = None) -> Optional[SlackMessage]:
        """Update Slack message"""
        try:
            # Build request data
            data = {
                'channel': channel_id,
                'ts': message_ts,
                'text': text
            }
            
            # Make request
            result = await self._make_request('POST', 'chat.update', data)
            
            if result.get('ok') and result.get('message'):
                # Get workspace and channel info for metadata
                workspace = await self.get_workspace(team_id, user_id)
                channel = await self.get_channel(team_id, channel_id, user_id)
                
                message_data = result.get('message')
                
                # Count reactions
                reactions = message_data.get('reactions', [])
                reaction_count = sum(reaction.get('count', 0) for reaction in reactions)
                
                # Count attachments
                attachments = message_data.get('attachments', [])
                attachment_count = len(attachments)
                
                # Count files
                files = message_data.get('files', [])
                file_count = len(files)
                
                # Count mentions
                text_content = message_data.get('text', '')
                mentions = []
                user_mentions = []
                
                # Simple mention extraction
                import re
                mention_pattern = r'<@([UW][A-Z0-9]+)>'
                for match in re.findall(mention_pattern, text_content):
                    mentions.append(match)
                    user_mentions.append(match)
                
                # Get user info
                user_name = ''
                if message_data.get('user'):
                    user_result = await self._make_request('GET', 'users.info', 
                                                         {'user': message_data.get('user')}, 
                                                         token_type='user')
                    if user_result.get('ok') and user_result.get('user'):
                        user_name = user_result.get('user', {}).get('name', '')
                elif message_data.get('bot_profile'):
                    user_name = message_data.get('bot_profile', {}).get('name', '')
                
                message = SlackMessage(
                    id=message_data.get('ts', ''),
                    team=team_id,
                    channel=channel_id,
                    user=message_data.get('user', ''),
                    type=message_data.get('type', ''),
                    subtype=message_data.get('subtype', ''),
                    text=message_data.get('text', ''),
                    ts=message_data.get('ts', ''),
                    thread_ts=message_data.get('thread_ts', ''),
                    parent_user_id=message_data.get('parent_user_id', ''),
                    reply_count=message_data.get('reply_count', 0),
                    reply_users_count=message_data.get('reply_users_count', 0),
                    latest_reply=message_data.get('latest_reply', ''),
                    reply_users=message_data.get('reply_users', []),
                    reactions=reactions,
                    attachments=attachments,
                    files=files,
                    pinned_to=message_data.get('pinned_to', []),
                    mentions=mentions,
                    user_mentions=user_mentions,
                    bot_id=message_data.get('bot_id', ''),
                    bot_profile=message_data.get('bot_profile', {}),
                    app_id=message_data.get('app_id', ''),
                    blocks=message_data.get('blocks', []),
                    edited=message_data.get('edited', {}),
                    last_read='',
                    unread_count=0,
                    subscribed=False,
                    is_starred=False,
                    has_reactions=reaction_count > 0,
                    reaction_count=reaction_count,
                    has_attachments=attachment_count > 0,
                    attachment_count=attachment_count,
                    has_files=file_count > 0,
                    file_count=file_count,
                    is_threaded=message_data.get('thread_ts') is not None,
                    is_thread_parent=message_data.get('reply_count', 0) > 0,
                    is_thread_reply=message_data.get('thread_ts') is not None and message_data.get('reply_count', 0) == 0,
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    channel_name=channel.name if channel else '',
                    user_name=user_name,
                    metadata={
                        'updated_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                
                # Clear cache
                self._clear_message_cache()
                
                logger.info(f"Slack message updated: {message_ts}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating Slack message: {e}")
            return None
    
    async def delete_message(self, team_id: str, channel_id: str, message_ts: str) -> bool:
        """Delete Slack message"""
        try:
            # Build request data
            data = {
                'channel': channel_id,
                'ts': message_ts
            }
            
            # Make request
            result = await self._make_request('POST', 'chat.delete', data)
            
            if result.get('ok'):
                # Clear cache
                self._clear_message_cache()
                
                logger.info(f"Slack message deleted: {message_ts}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting Slack message: {e}")
            return False
    
    async def get_users(self, team_id: str, user_id: str = None) -> List[SlackUser]:
        """Get Slack users from workspace"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'users_{team_id}')
            if cache_key in self.users_cache:
                return self.users_cache[cache_key]
            
            # Get workspace info for metadata
            workspace = await self.get_workspace(team_id, user_id)
            
            # Make request
            result = await self._make_request('GET', 'users.list', token_type='user')
            
            if not result.get('ok'):
                return []
            
            # Create user objects
            users = []
            for user_data in result.get('members', []):
                user = SlackUser(
                    id=user_data.get('id', ''),
                    team_id=team_id,
                    name=user_data.get('name', ''),
                    deleted=user_data.get('deleted', False),
                    color=user_data.get('color', ''),
                    real_name=user_data.get('real_name', ''),
                    tz=user_data.get('tz', ''),
                    tz_label=user_data.get('tz_label', ''),
                    tz_offset=user_data.get('tz_offset', 0),
                    profile=user_data.get('profile', {}),
                    is_admin=user_data.get('is_admin', False),
                    is_owner=user_data.get('is_owner', False),
                    is_primary_owner=user_data.get('is_primary_owner', False),
                    is_restricted=user_data.get('is_restricted', False),
                    is_ultra_restricted=user_data.get('is_ultra_restricted', False),
                    is_bot=user_data.get('is_bot', False),
                    is_app_user=user_data.get('is_app_user', False),
                    is_stranger=user_data.get('is_stranger', False),
                    is_invited_user=user_data.get('is_invited_user', False),
                    has_files=user_data.get('has_files', False),
                    has_2fa=user_data.get('has_2fa', False),
                    locale=user_data.get('locale', ''),
                    updated=user_data.get('updated', 0),
                    enterprise_id=user_data.get('enterprise_id', ''),
                    presence=user_data.get('presence', 'offline'),
                    online=user_data.get('presence') == 'active',
                    last_seen='',
                    message_count=0,  # Will be calculated
                    file_count=user_data.get('has_files', False) ? 0 : 0,  # Will be calculated
                    reaction_count=0,  # Will be calculated
                    mention_count=0,  # Will be calculated
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                users.append(user)
            
            # Cache users
            self.users_cache[cache_key] = users
            
            logger.info(f"Slack users retrieved: {len(users)}")
            return users
            
        except Exception as e:
            logger.error(f"Error getting Slack users: {e}")
            return []
    
    async def get_user(self, team_id: str, user_id: str, user_id_token: str = None) -> Optional[SlackUser]:
        """Get Slack user by ID"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id_token or 'all', f'user_{team_id}_{user_id}')
            if cache_key in self.users_cache:
                return self.users_cache[cache_key]
            
            # Make request
            result = await self._make_request('GET', 'users.info', {'user': user_id}, token_type='user')
            
            if result.get('ok') and result.get('user'):
                # Get workspace info for metadata
                workspace = await self.get_workspace(team_id, user_id_token)
                
                user_data = result.get('user')
                
                user = SlackUser(
                    id=user_data.get('id', ''),
                    team_id=team_id,
                    name=user_data.get('name', ''),
                    deleted=user_data.get('deleted', False),
                    color=user_data.get('color', ''),
                    real_name=user_data.get('real_name', ''),
                    tz=user_data.get('tz', ''),
                    tz_label=user_data.get('tz_label', ''),
                    tz_offset=user_data.get('tz_offset', 0),
                    profile=user_data.get('profile', {}),
                    is_admin=user_data.get('is_admin', False),
                    is_owner=user_data.get('is_owner', False),
                    is_primary_owner=user_data.get('is_primary_owner', False),
                    is_restricted=user_data.get('is_restricted', False),
                    is_ultra_restricted=user_data.get('is_ultra_restricted', False),
                    is_bot=user_data.get('is_bot', False),
                    is_app_user=user_data.get('is_app_user', False),
                    is_stranger=user_data.get('is_stranger', False),
                    is_invited_user=user_data.get('is_invited_user', False),
                    has_files=user_data.get('has_files', False),
                    has_2fa=user_data.get('has_2fa', False),
                    locale=user_data.get('locale', ''),
                    updated=user_data.get('updated', 0),
                    enterprise_id=user_data.get('enterprise_id', ''),
                    presence=user_data.get('presence', 'offline'),
                    online=user_data.get('presence') == 'active',
                    last_seen='',
                    message_count=0,
                    file_count=user_data.get('has_files', False) ? 0 : 0,
                    reaction_count=0,
                    mention_count=0,
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                
                # Cache user
                self.users_cache[cache_key] = user
                
                logger.info(f"Slack user retrieved: {user_id}")
                return user
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Slack user: {e}")
            return None
    
    async def get_files(self, team_id: str, channel_id: str = None, user_id: str = None,
                       user_id_token: str = None, limit: int = 100) -> Dict[str, Any]:
        """Get Slack files from workspace or channel"""
        try:
            # Build parameters
            params = {
                'count': min(limit, 1000),  # Slack API limit
                'team_id': team_id
            }
            
            if channel_id:
                params['channel'] = channel_id
            if user_id:
                params['user'] = user_id
            
            # Make request
            result = await self._make_request('GET', 'files.list', params, token_type='user')
            
            if not result.get('ok'):
                return {
                    'files': [],
                    'paging': {},
                    'error': result.get('error')
                }
            
            # Get workspace info for metadata
            workspace = await self.get_workspace(team_id, user_id_token)
            
            # Create file objects
            files = []
            for file_data in result.get('files', []):
                # Get uploader name
                uploader_name = ''
                if file_data.get('user'):
                    user_result = await self._make_request('GET', 'users.info', 
                                                         {'user': file_data.get('user')}, 
                                                         token_type='user')
                    if user_result.get('ok') and user_result.get('user'):
                        uploader_name = user_result.get('user', {}).get('name', '')
                elif file_data.get('username'):
                    uploader_name = file_data.get('username', '')
                
                file = SlackFile(
                    id=file_data.get('id', ''),
                    created=file_data.get('created', 0),
                    timestamp=file_data.get('timestamp', 0),
                    name=file_data.get('name', ''),
                    title=file_data.get('title', ''),
                    mimetype=file_data.get('mimetype', ''),
                    filetype=file_data.get('filetype', ''),
                    pretty_type=file_data.get('pretty_type', ''),
                    user=file_data.get('user', ''),
                    mode=file_data.get('mode', ''),
                    editable=file_data.get('editable', False),
                    size=file_data.get('size', 0),
                    is_external=file_data.get('is_external', False),
                    external_type=file_data.get('external_type', ''),
                    is_public=file_data.get('is_public', False),
                    public_url_shared=file_data.get('public_url_shared', False),
                    display_as_bot=file_data.get('display_as_bot', False),
                    username=file_data.get('username', ''),
                    url_private=file_data.get('url_private', ''),
                    url_private_download=file_data.get('url_private_download', ''),
                    thumb_64=file_data.get('thumb_64', ''),
                    thumb_80=file_data.get('thumb_80', ''),
                    thumb_360=file_data.get('thumb_360', ''),
                    thumb_480=file_data.get('thumb_480', ''),
                    thumb_720=file_data.get('thumb_720', ''),
                    thumb_960=file_data.get('thumb_960', ''),
                    thumb_1024=file_data.get('thumb_1024', ''),
                    original_w=file_data.get('original_w', 0),
                    original_h=file_data.get('original_h', 0),
                    thumb_w=file_data.get('thumb_w', 0),
                    thumb_h=file_data.get('thumb_h', 0),
                    image_exif_rotation=file_data.get('image_exif_rotation', 0),
                    permalink=file_data.get('permalink', ''),
                    permalink_public=file_data.get('permalink_public', ''),
                    comments_count=file_data.get('comments_count', 0),
                    shares=file_data.get('shares', {}),
                    channels=file_data.get('channels', []),
                    groups=file_data.get('groups', []),
                    ims=file_data.get('ims', []),
                    num_channels=len(file_data.get('channels', [])),
                    num_groups=len(file_data.get('groups', [])),
                    num_ims=len(file_data.get('ims', [])),
                    has_rich_preview=file_data.get('has_rich_preview', False),
                    rich_preview=file_data.get('rich_preview', {}),
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    uploader_name=uploader_name,
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                files.append(file)
            
            return {
                'files': files,
                'paging': result.get('paging', {}),
                'total': len(files)
            }
            
        except Exception as e:
            logger.error(f"Error getting Slack files: {e}")
            return {
                'files': [],
                'paging': {},
                'error': str(e)
            }
    
    async def search_messages(self, team_id: str, query: str, channel_id: str = None,
                             user_id: str = None, sort: str = 'timestamp',
                             sort_dir: str = 'desc', count: int = 100,
                             user_id_token: str = None) -> Dict[str, Any]:
        """Search Slack messages"""
        try:
            # Build parameters
            params = {
                'query': query,
                'sort': sort,
                'sort_dir': sort_dir,
                'count': min(count, 1000),  # Slack API limit
                'team_id': team_id
            }
            
            if channel_id:
                params['channel'] = channel_id
            if user_id:
                params['user'] = user_id
            
            # Make request
            result = await self._make_request('GET', 'search.messages', params, token_type='user')
            
            if not result.get('ok'):
                return {
                    'messages': [],
                    'paging': {},
                    'error': result.get('error')
                }
            
            # Get workspace info for metadata
            workspace = await self.get_workspace(team_id, user_id_token)
            
            # Create message objects
            messages = []
            for message_data in result.get('messages', {}).get('matches', []):
                # Get channel info
                channel_id = message_data.get('channel', {}).get('id', '')
                channel_name = message_data.get('channel', {}).get('name', '')
                
                # Count reactions
                reactions = message_data.get('reactions', [])
                reaction_count = sum(reaction.get('count', 0) for reaction in reactions)
                
                # Count attachments
                attachments = message_data.get('attachments', [])
                attachment_count = len(attachments)
                
                # Count files
                files = message_data.get('files', [])
                file_count = len(files)
                
                # Count mentions
                text = message_data.get('text', '')
                mentions = []
                user_mentions = []
                
                # Simple mention extraction
                import re
                mention_pattern = r'<@([UW][A-Z0-9]+)>'
                for match in re.findall(mention_pattern, text):
                    mentions.append(match)
                    user_mentions.append(match)
                
                # Get user info
                user_name = ''
                if message_data.get('user'):
                    user_result = await self._make_request('GET', 'users.info', 
                                                         {'user': message_data.get('user')}, 
                                                         token_type='user')
                    if user_result.get('ok') and user_result.get('user'):
                        user_name = user_result.get('user', {}).get('name', '')
                elif message_data.get('bot_profile'):
                    user_name = message_data.get('bot_profile', {}).get('name', '')
                
                message = SlackMessage(
                    id=message_data.get('ts', ''),
                    team=team_id,
                    channel=channel_id,
                    user=message_data.get('user', ''),
                    type=message_data.get('type', ''),
                    subtype=message_data.get('subtype', ''),
                    text=message_data.get('text', ''),
                    ts=message_data.get('ts', ''),
                    thread_ts=message_data.get('thread_ts', ''),
                    parent_user_id=message_data.get('parent_user_id', ''),
                    reply_count=message_data.get('reply_count', 0),
                    reply_users_count=message_data.get('reply_users_count', 0),
                    latest_reply=message_data.get('latest_reply', ''),
                    reply_users=message_data.get('reply_users', []),
                    reactions=reactions,
                    attachments=attachments,
                    files=files,
                    pinned_to=message_data.get('pinned_to', []),
                    mentions=mentions,
                    user_mentions=user_mentions,
                    bot_id=message_data.get('bot_id', ''),
                    bot_profile=message_data.get('bot_profile', {}),
                    app_id=message_data.get('app_id', ''),
                    blocks=message_data.get('blocks', []),
                    edited=message_data.get('edited', {}),
                    last_read='',
                    unread_count=0,
                    subscribed=False,
                    is_starred=False,
                    has_reactions=reaction_count > 0,
                    reaction_count=reaction_count,
                    has_attachments=attachment_count > 0,
                    attachment_count=attachment_count,
                    has_files=file_count > 0,
                    file_count=file_count,
                    is_threaded=message_data.get('thread_ts') is not None,
                    is_thread_parent=message_data.get('reply_count', 0) > 0,
                    is_thread_reply=message_data.get('thread_ts') is not None and message_data.get('reply_count', 0) == 0,
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    channel_name=channel_name,
                    user_name=user_name,
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                messages.append(message)
            
            return {
                'messages': messages,
                'paging': result.get('messages', {}).get('paging', {}),
                'total': len(messages),
                'query': query,
                'search_filters': {
                    'channel_id': channel_id,
                    'user_id': user_id,
                    'sort': sort,
                    'sort_dir': sort_dir,
                    'count': count
                }
            }
            
        except Exception as e:
            logger.error(f"Error searching Slack messages: {e}")
            return {
                'messages': [],
                'paging': {},
                'error': str(e)
            }
    
    async def get_webhooks(self, team_id: str, user_id: str = None) -> List[SlackWebhook]:
        """Get Slack webhooks from workspace"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'webhooks_{team_id}')
            if cache_key in self.webhooks_cache:
                return self.webhooks_cache[cache_key]
            
            # Get workspace info for metadata
            workspace = await self.get_workspace(team_id, user_id)
            
            # Make request
            result = await self._make_request('GET', 'webhooks.list', token_type='user')
            
            if not result.get('ok'):
                return []
            
            # Create webhook objects
            webhooks = []
            for webhook_data in result.get('webhooks', []):
                webhook = SlackWebhook(
                    id=webhook_data.get('id', ''),
                    team_id=webhook_data.get('team_id', team_id),
                    enterprise_id=webhook_data.get('enterprise_id', ''),
                    channel_id=webhook_data.get('channel_id', ''),
                    configuration_url=webhook_data.get('configuration_url', ''),
                    url=webhook_data.get('url', ''),
                    active=webhook_data.get('active', False),
                    created_at=webhook_data.get('created_at', 0),
                    updated_at=webhook_data.get('updated_at', 0),
                    trigger_id=webhook_data.get('trigger_id', ''),
                    app_id=webhook_data.get('app_id', ''),
                    app_name=webhook_data.get('app_name', ''),
                    workspace_id=team_id,
                    workspace_name=workspace.name if workspace else '',
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'slack_api'
                    }
                )
                webhooks.append(webhook)
            
            # Cache webhooks
            self.webhooks_cache[cache_key] = webhooks
            
            logger.info(f"Slack webhooks retrieved: {len(webhooks)}")
            return webhooks
            
        except Exception as e:
            logger.error(f"Error getting Slack webhooks: {e}")
            return []
    
    def _clear_cache(self):
        """Clear all caches"""
        self.workspaces_cache.clear()
        self.channels_cache.clear()
        self.users_cache.clear()
        self.messages_cache.clear()
        self.files_cache.clear()
        self.reactions_cache.clear()
        self.webhooks_cache.clear()
    
    def _clear_workspace_cache(self):
        """Clear workspace cache"""
        self.workspaces_cache.clear()
    
    def _clear_channel_cache(self):
        """Clear channel cache"""
        self.channels_cache.clear()
    
    def _clear_user_cache(self):
        """Clear user cache"""
        self.users_cache.clear()
    
    def _clear_message_cache(self):
        """Clear message cache"""
        self.messages_cache.clear()
    
    def _clear_file_cache(self):
        """Clear file cache"""
        self.files_cache.clear()
    
    def _clear_reaction_cache(self):
        """Clear reaction cache"""
        self.reactions_cache.clear()
    
    def _clear_webhook_cache(self):
        """Clear webhook cache"""
        self.webhooks_cache.clear()
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "name": "Enhanced Slack Service",
            "version": "1.0.0",
            "description": "Complete Slack team communication automation",
            "capabilities": [
                "workspace_management",
                "channel_operations",
                "message_crud",
                "user_and_presence_management",
                "file_and_attachment_handling",
                "search_and_filtering",
                "realtime_events",
                "webhook_support",
                "reaction_tracking",
                "thread_analysis",
                "presence_tracking",
                "communication_analytics"
            ],
            "api_endpoints": [
                "/api/slack/enhanced/workspaces/list",
                "/api/slack/enhanced/workspaces/get",
                "/api/slack/enhanced/channels/list",
                "/api/slack/enhanced/channels/get",
                "/api/slack/enhanced/messages/list",
                "/api/slack/enhanced/messages/get",
                "/api/slack/enhanced/messages/send",
                "/api/slack/enhanced/messages/update",
                "/api/slack/enhanced/messages/delete",
                "/api/slack/enhanced/users/list",
                "/api/slack/enhanced/users/get",
                "/api/slack/enhanced/files/list",
                "/api/slack/enhanced/search/messages",
                "/api/slack/enhanced/webhooks/list",
                "/api/slack/enhanced/health"
            ],
            "channel_types": self.channel_types,
            "message_types": self.message_types,
            "file_types": self.file_types,
            "initialized_at": datetime.utcnow().isoformat()
        }

# Create singleton instance
slack_enhanced_service = SlackEnhancedService()