"""
ATOM Slack Enhanced Service - Complete Production Implementation
Comprehensive Slack service with OAuth, messaging, files, webhooks, and advanced features
"""

import os
import json
import logging
import asyncio
import hashlib
import hmac
import base64
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
import redis
import jwt
from cryptography.fernet import Fernet

# Configure logging
logger = logging.getLogger(__name__)

class SlackEventType(Enum):
    """Slack event types"""
    MESSAGE = "message"
    FILE_UPLOAD = "file_shared"
    FILE_DELETE = "file_deleted"
    CHANNEL_CREATE = "channel_created"
    CHANNEL_DELETE = "channel_deleted"
    USER_JOIN = "team_join"
    USER_LEAVE = "team_leave"
    REACTION_ADD = "reaction_added"
    REACTION_REMOVE = "reaction_removed"
    BOT_MESSAGE = "message.bot"
    THREAD_REPLY = "message.thread"
    MENTION = "app_mention"

class SlackPermission(Enum):
    """Slack permission levels"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

class SlackConnectionStatus(Enum):
    """Slack connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"

@dataclass
class SlackWorkspace:
    """Slack workspace model"""
    team_id: str
    team_name: str
    domain: str
    url: str
    icon_url: Optional[str] = None
    enterprise_id: Optional[str] = None
    enterprise_name: Optional[str] = None
    access_token: Optional[str] = None
    bot_token: Optional[str] = None
    user_id: Optional[str] = None
    bot_id: Optional[str] = None
    scopes: List[str] = None
    created_at: datetime = None
    last_sync: Optional[datetime] = None
    is_active: bool = True
    settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.settings is None:
            self.settings = {}

@dataclass
class SlackChannel:
    """Slack channel model"""
    channel_id: str
    name: str
    display_name: Optional[str] = None
    purpose: Optional[str] = None
    topic: Optional[str] = None
    is_private: bool = False
    is_archived: bool = False
    is_general: bool = False
    is_shared: bool = False
    is_im: bool = False
    is_mpim: bool = False
    workspace_id: str = None
    num_members: int = 0
    created: datetime = None
    last_read: Optional[datetime] = None
    unread_count: int = 0
    is_muted: bool = False
    
    def __post_init__(self):
        if self.created is None:
            self.created = datetime.utcnow()

@dataclass
class SlackMessage:
    """Slack message model"""
    message_id: str
    text: str
    user_id: str
    user_name: str
    channel_id: str
    channel_name: str
    workspace_id: str
    timestamp: str
    thread_ts: Optional[str] = None
    reply_count: int = 0
    message_type: str = "message"
    subtype: Optional[str] = None
    reactions: List[Dict[str, Any]] = None
    files: List[Dict[str, Any]] = None
    pinned_to: List[str] = None
    is_starred: bool = False
    is_edited: bool = False
    edit_timestamp: Optional[str] = None
    blocks: List[Dict[str, Any]] = None
    mentions: List[str] = None
    bot_profile: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.reactions is None:
            self.reactions = []
        if self.files is None:
            self.files = []
        if self.pinned_to is None:
            self.pinned_to = []
        if self.blocks is None:
            self.blocks = []
        if self.mentions is None:
            self.mentions = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class SlackFile:
    """Slack file model"""
    file_id: str
    name: str
    title: str
    mimetype: str
    filetype: str
    pretty_type: str
    size: int
    url_private: str
    url_private_download: Optional[str] = None
    permalink: str
    permalink_public: Optional[str] = None
    user_id: str
    user_name: str
    channel_id: Optional[str] = None
    workspace_id: str = None
    timestamp: str
    created: datetime
    is_public: bool = False
    is_editable: bool = True
    external_type: Optional[str] = None
    external_url: Optional[str] = None
    preview: Optional[str] = None
    thumbnail: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        self.created = datetime.fromtimestamp(float(self.timestamp))
        if self.metadata is None:
            self.metadata = {}

class SlackRateLimiter:
    """Slack API rate limiter"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.local_limits: Dict[str, Dict[str, Any]] = {}
        self.default_limits = {
            'chat.postMessage': 1,  # per second
            'conversations.list': 1,  # per second
            'conversations.history': 50,  # per minute
            'files.upload': 1,  # per second
            'search.messages': 100  # per minute
        }
    
    async def check_limit(self, workspace_id: str, endpoint: str) -> bool:
        """Check if rate limit is exceeded"""
        key = f"slack_rate:{workspace_id}:{endpoint}"
        limit = self.default_limits.get(endpoint, 1)
        window = 60 if 'search' in endpoint or 'history' in endpoint else 1
        
        if self.redis:
            # Redis-based rate limiting
            current = self.redis.get(key)
            if current and int(current) >= limit:
                return False
            
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            pipe.execute()
            return True
        else:
            # Local rate limiting
            if key not in self.local_limits:
                self.local_limits[key] = {'count': 0, 'reset': time.time() + window}
            
            current_time = time.time()
            if current_time > self.local_limits[key]['reset']:
                self.local_limits[key]['count'] = 0
                self.local_limits[key]['reset'] = current_time + window
            
            if self.local_limits[key]['count'] >= limit:
                return False
            
            self.local_limits[key]['count'] += 1
            return True

class SlackEnhancedService:
    """Enhanced Slack service with full production capabilities"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client_id = config.get('client_id') or os.getenv('SLACK_CLIENT_ID')
        self.client_secret = config.get('client_secret') or os.getenv('SLACK_CLIENT_SECRET')
        self.signing_secret = config.get('signing_secret') or os.getenv('SLACK_SIGNING_SECRET')
        self.redirect_uri = config.get('redirect_uri') or os.getenv('SLACK_REDIRECT_URI')
        
        # Database connection
        self.db = config.get('database')
        
        # Redis for caching and rate limiting
        redis_config = config.get('redis', {})
        self.redis_client = redis.Redis(
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 0),
            decode_responses=True
        ) if redis_config.get('enabled') else None
        
        # Encryption for tokens
        self.encryption_key = config.get('encryption_key') or os.getenv('ENCRYPTION_KEY')
        self.cipher = Fernet(self.encryption_key.encode()) if self.encryption_key else None
        
        # Rate limiter
        self.rate_limiter = SlackRateLimiter(self.redis_client)
        
        # Slack clients cache
        self.clients: Dict[str, AsyncWebClient] = {}
        self.sync_clients: Dict[str, WebClient] = {}
        
        # Event handlers
        self.event_handlers: Dict[SlackEventType, List[Callable]] = {
            event_type: [] for event_type in SlackEventType
        }
        
        # Webhook handlers
        self.webhook_handlers: List[Callable] = []
        
        # Connection status
        self.connection_status: Dict[str, SlackConnectionStatus] = {}
        
        # Required scopes
        self.required_scopes = [
            'channels:read',
            'channels:history',
            'groups:read',
            'groups:history',
            'im:read',
            'im:history',
            'mpim:read',
            'mpim:history',
            'users:read',
            'users:read.email',
            'chat:write',
            'chat:write.public',
            'files:read',
            'files:write',
            'reactions:read',
            'reactions:write',
            'team:read',
            'channels:manage',
            'users:write'
        ]
        
        logger.info("Slack Enhanced Service initialized")
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt access token for storage"""
        if not self.cipher:
            return token
        return self.cipher.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt access token from storage"""
        if not self.cipher:
            return encrypted_token
        return self.cipher.decrypt(encrypted_token.encode()).decode()
    
    def _get_client(self, workspace_id: str, async_client: bool = True) -> Optional[AsyncWebClient]:
        """Get or create Slack client for workspace"""
        try:
            if workspace_id not in self.clients:
                # Get workspace from database
                workspace = self._get_workspace(workspace_id)
                if not workspace or not workspace.access_token:
                    logger.error(f"No access token for workspace: {workspace_id}")
                    return None
                
                token = self._decrypt_token(workspace.access_token)
                self.clients[workspace_id] = AsyncWebClient(token=token)
            
            return self.clients[workspace_id]
        except Exception as e:
            logger.error(f"Error creating Slack client: {e}")
            return None
    
    def _get_sync_client(self, workspace_id: str) -> Optional[WebClient]:
        """Get synchronous Slack client"""
        try:
            if workspace_id not in self.sync_clients:
                workspace = self._get_workspace(workspace_id)
                if not workspace or not workspace.access_token:
                    return None
                
                token = self._decrypt_token(workspace.access_token)
                self.sync_clients[workspace_id] = WebClient(token=token)
            
            return self.sync_clients[workspace_id]
        except Exception as e:
            logger.error(f"Error creating sync Slack client: {e}")
            return None
    
    def _get_workspace(self, workspace_id: str) -> Optional[SlackWorkspace]:
        """Get workspace from database"""
        try:
            if self.db:
                # Get from database
                result = self.db.execute(
                    "SELECT * FROM slack_workspaces WHERE team_id = ?",
                    (workspace_id,)
                ).fetchone()
                if result:
                    return SlackWorkspace(**result)
            else:
                # Get from cache (development)
                cached = self.redis_client.get(f"workspace:{workspace_id}")
                if cached:
                    return SlackWorkspace(**json.loads(cached))
        except Exception as e:
            logger.error(f"Error getting workspace {workspace_id}: {e}")
        return None
    
    def _save_workspace(self, workspace: SlackWorkspace) -> bool:
        """Save workspace to database"""
        try:
            if self.db:
                # Save to database
                self.db.execute(
                    """INSERT OR REPLACE INTO slack_workspaces 
                       (team_id, team_name, domain, url, icon_url, enterprise_id, 
                        enterprise_name, access_token, bot_token, user_id, bot_id, 
                        scopes, created_at, last_sync, is_active, settings)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        workspace.team_id,
                        workspace.team_name,
                        workspace.domain,
                        workspace.url,
                        workspace.icon_url,
                        workspace.enterprise_id,
                        workspace.enterprise_name,
                        self._encrypt_token(workspace.access_token) if workspace.access_token else None,
                        workspace.bot_token,
                        workspace.user_id,
                        workspace.bot_id,
                        json.dumps(workspace.scopes),
                        workspace.created_at.isoformat(),
                        workspace.last_sync.isoformat() if workspace.last_sync else None,
                        workspace.is_active,
                        json.dumps(workspace.settings)
                    )
                )
                self.db.commit()
            else:
                # Save to cache (development)
                self.redis_client.setex(
                    f"workspace:{workspace.team_id}",
                    3600,  # 1 hour
                    json.dumps(asdict(workspace))
                )
            
            # Update connection status
            self.connection_status[workspace.team_id] = SlackConnectionStatus.CONNECTED
            return True
        except Exception as e:
            logger.error(f"Error saving workspace: {e}")
            return False
    
    def generate_oauth_url(self, state: str, user_id: str, scopes: List[str] = None) -> str:
        """Generate OAuth authorization URL"""
        try:
            if not scopes:
                scopes = self.required_scopes
            
            params = {
                'client_id': self.client_id,
                'scope': ' '.join(scopes),
                'redirect_uri': self.redirect_uri,
                'state': state,
                'user': user_id
            }
            
            encoded_params = '&'.join([f"{k}={v}" for k, v in params.items()])
            return f"https://slack.com/oauth/v2/authorize?{encoded_params}"
        
        except Exception as e:
            logger.error(f"Error generating OAuth URL: {e}")
            raise
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://slack.com/api/oauth.v2.access',
                    data={
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'code': code,
                        'redirect_uri': self.redirect_uri
                    }
                )
                
                if response.status_code != 200:
                    raise SlackApiError(f"OAuth request failed: {response.text}")
                
                data = response.json()
                if not data.get('ok'):
                    raise SlackApiError(f"OAuth error: {data.get('error', 'Unknown error')}")
                
                # Create workspace model
                team = data.get('team', {})
                enterprise = data.get('enterprise', {})
                authed_user = data.get('authed_user', {})
                
                workspace = SlackWorkspace(
                    team_id=team.get('id'),
                    team_name=team.get('name'),
                    domain=team.get('domain'),
                    url=f"https://{team.get('domain')}.slack.com",
                    icon_url=team.get('icon', {}).get('image_132'),
                    enterprise_id=enterprise.get('id'),
                    enterprise_name=enterprise.get('name'),
                    access_token=data.get('access_token'),
                    bot_token=data.get('bot_user_id'),  # This needs to be extracted properly
                    user_id=authed_user.get('id'),
                    scopes=data.get('scope', '').split(','),
                    settings={}
                )
                
                # Save workspace
                if self._save_workspace(workspace):
                    return {
                        'ok': True,
                        'workspace': asdict(workspace),
                        'message': 'Workspace connected successfully'
                    }
                else:
                    return {
                        'ok': False,
                        'error': 'Failed to save workspace',
                        'message': 'Database error occurred'
                    }
        
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return {
                'ok': False,
                'error': str(e),
                'message': 'OAuth token exchange failed'
            }
    
    async def test_connection(self, workspace_id: str) -> Dict[str, Any]:
        """Test connection to Slack workspace"""
        try:
            self.connection_status[workspace_id] = SlackConnectionStatus.CONNECTING
            
            client = self._get_client(workspace_id)
            if not client:
                self.connection_status[workspace_id] = SlackConnectionStatus.ERROR
                return {
                    'connected': False,
                    'error': 'Failed to create Slack client',
                    'status': 'error'
                }
            
            # Test with auth.test
            response = await client.auth_test()
            
            if response['ok']:
                self.connection_status[workspace_id] = SlackConnectionStatus.CONNECTED
                workspace = self._get_workspace(workspace_id)
                if workspace:
                    workspace.last_sync = datetime.utcnow()
                    self._save_workspace(workspace)
                
                return {
                    'connected': True,
                    'workspace': {
                        'team_id': response['team_id'],
                        'team_name': response['team'],
                        'user_id': response['user_id'],
                        'user': response['user'],
                        'bot_id': response.get('bot_id')
                    },
                    'status': 'connected'
                }
            else:
                self.connection_status[workspace_id] = SlackConnectionStatus.ERROR
                return {
                    'connected': False,
                    'error': response.get('error', 'Connection test failed'),
                    'status': 'error'
                }
        
        except SlackApiError as e:
            self.connection_status[workspace_id] = SlackConnectionStatus.ERROR
            if e.response['error'] == 'ratelimited':
                self.connection_status[workspace_id] = SlackConnectionStatus.RATE_LIMITED
                return {
                    'connected': False,
                    'error': 'Rate limited',
                    'retry_after': e.response.headers.get('Retry-After', 60),
                    'status': 'rate_limited'
                }
            
            return {
                'connected': False,
                'error': str(e),
                'status': 'error'
            }
        
        except Exception as e:
            self.connection_status[workspace_id] = SlackConnectionStatus.ERROR
            return {
                'connected': False,
                'error': str(e),
                'status': 'error'
            }
    
    async def get_workspaces(self, user_id: str = None) -> List[SlackWorkspace]:
        """Get all workspaces or user's workspaces"""
        try:
            if self.db:
                # Get from database
                if user_id:
                    result = self.db.execute(
                        "SELECT * FROM slack_workspaces WHERE is_active = 1 AND user_id = ?",
                        (user_id,)
                    ).fetchall()
                else:
                    result = self.db.execute(
                        "SELECT * FROM slack_workspaces WHERE is_active = 1"
                    ).fetchall()
                return [SlackWorkspace(**row) for row in result]
            else:
                # Get from cache
                keys = self.redis_client.keys("workspace:*")
                workspaces = []
                for key in keys:
                    cached = self.redis_client.get(key)
                    if cached:
                        workspace = SlackWorkspace(**json.loads(cached))
                        if not user_id or workspace.user_id == user_id:
                            workspaces.append(workspace)
                return workspaces
        
        except Exception as e:
            logger.error(f"Error getting workspaces: {e}")
            return []
    
    async def get_channels(self, workspace_id: str, user_id: str = None,
                         include_private: bool = False, include_archived: bool = False,
                         limit: int = 100) -> List[SlackChannel]:
        """Get channels for workspace"""
        try:
            # Check rate limit
            if not await self.rate_limiter.check_limit(workspace_id, 'conversations.list'):
                raise SlackApiError("Rate limit exceeded for conversations.list")
            
            client = self._get_client(workspace_id)
            if not client:
                raise SlackApiError("Failed to create Slack client")
            
            # Determine channel types
            types = ['public_channel']
            if include_private:
                types.extend(['private_channel', 'mpim', 'im'])
            
            # Get channels
            response = await client.conversations_list(
                types=','.join(types),
                exclude_archived=not include_archived,
                limit=min(limit, 1000)
            )
            
            if not response['ok']:
                raise SlackApiError(f"Failed to get channels: {response.get('error')}")
            
            channels = []
            for channel_data in response['channels']:
                channel = SlackChannel(
                    channel_id=channel_data['id'],
                    name=channel_data['name'],
                    display_name=channel_data.get('name'),
                    purpose=channel_data.get('purpose', {}).get('value'),
                    topic=channel_data.get('topic', {}).get('value'),
                    is_private=channel_data.get('is_private', False),
                    is_archived=channel_data.get('is_archived', False),
                    is_general=channel_data.get('is_general', False),
                    is_shared=channel_data.get('is_shared', False),
                    is_im=channel_data.get('is_im', False),
                    is_mpim=channel_data.get('is_mpim', False),
                    workspace_id=workspace_id,
                    num_members=channel_data.get('num_members', 0),
                    created=datetime.fromtimestamp(channel_data.get('created', 0))
                )
                channels.append(channel)
            
            # Cache channels
            cache_key = f"channels:{workspace_id}"
            if self.redis_client:
                self.redis_client.setex(
                    cache_key,
                    1800,  # 30 minutes
                    json.dumps([asdict(c) for c in channels])
                )
            
            return channels
        
        except SlackApiError as e:
            logger.error(f"Error getting channels for {workspace_id}: {e}")
            if self.redis_client:
                # Try to return cached channels
                cache_key = f"channels:{workspace_id}"
                cached = self.redis_client.get(cache_key)
                if cached:
                    return [SlackChannel(**c) for c in json.loads(cached)]
            return []
        
        except Exception as e:
            logger.error(f"Unexpected error getting channels: {e}")
            return []
    
    async def send_message(self, workspace_id: str, channel_id: str, 
                         text: str, thread_ts: str = None,
                         blocks: List[Dict] = None, attachments: List[Dict] = None) -> Dict[str, Any]:
        """Send message to channel"""
        try:
            # Check rate limit
            if not await self.rate_limiter.check_limit(workspace_id, 'chat.postMessage'):
                raise SlackApiError("Rate limit exceeded for chat.postMessage")
            
            client = self._get_client(workspace_id)
            if not client:
                raise SlackApiError("Failed to create Slack client")
            
            message_data = {
                'channel': channel_id,
                'text': text
            }
            
            if thread_ts:
                message_data['thread_ts'] = thread_ts
            
            if blocks:
                message_data['blocks'] = blocks
            
            if attachments:
                message_data['attachments'] = attachments
            
            response = await client.chat_postMessage(**message_data)
            
            if response['ok']:
                # Cache message
                await self._cache_message(workspace_id, response['message'])
                
                return {
                    'ok': True,
                    'message_id': response['ts'],
                    'channel_id': response['channel'],
                    'timestamp': response['ts'],
                    'message': response['message']
                }
            else:
                raise SlackApiError(f"Failed to send message: {response.get('error')}")
        
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            return {
                'ok': False,
                'error': str(e),
                'message': 'Failed to send message'
            }
        
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return {
                'ok': False,
                'error': str(e),
                'message': 'Unexpected error occurred'
            }
    
    async def get_channel_history(self, workspace_id: str, channel_id: str,
                                limit: int = 100, latest: str = None,
                                oldest: str = None, include_threads: bool = True) -> List[SlackMessage]:
        """Get message history for channel"""
        try:
            # Check rate limit
            if not await self.rate_limiter.check_limit(workspace_id, 'conversations.history'):
                raise SlackApiError("Rate limit exceeded for conversations.history")
            
            client = self._get_client(workspace_id)
            if not client:
                raise SlackApiError("Failed to create Slack client")
            
            # Get history
            response = await client.conversations_history(
                channel=channel_id,
                limit=min(limit, 1000),
                latest=latest,
                oldest=oldest,
                include_all_threads=include_threads
            )
            
            if not response['ok']:
                raise SlackApiError(f"Failed to get channel history: {response.get('error')}")
            
            messages = []
            for msg_data in response['messages']:
                message = SlackMessage(
                    message_id=msg_data['ts'],
                    text=msg_data.get('text', ''),
                    user_id=msg_data.get('user', ''),
                    user_name='',  # Will be populated from user cache
                    channel_id=channel_id,
                    channel_name='',  # Will be populated from channel cache
                    workspace_id=workspace_id,
                    timestamp=msg_data['ts'],
                    thread_ts=msg_data.get('thread_ts'),
                    reply_count=msg_data.get('reply_count', 0),
                    message_type=msg_data.get('type', 'message'),
                    subtype=msg_data.get('subtype'),
                    reactions=msg_data.get('reactions', []),
                    files=msg_data.get('files', []),
                    pinned_to=msg_data.get('pinned_to', []),
                    is_starred=msg_data.get('is_starred', False),
                    is_edited='edited' in msg_data,
                    edit_timestamp=msg_data.get('edited', {}).get('ts'),
                    blocks=msg_data.get('blocks', []),
                    mentions=self._extract_mentions(msg_data.get('text', '')),
                    bot_profile=msg_data.get('bot_profile'),
                    metadata={}
                )
                messages.append(message)
            
            # Cache messages
            await self._cache_messages(workspace_id, channel_id, messages)
            
            return messages
        
        except SlackApiError as e:
            logger.error(f"Error getting channel history: {e}")
            return []
        
        except Exception as e:
            logger.error(f"Unexpected error getting channel history: {e}")
            return []
    
    async def upload_file(self, workspace_id: str, channel_id: str, file_path: str,
                        title: str = None, initial_comment: str = None) -> Dict[str, Any]:
        """Upload file to channel"""
        try:
            # Check rate limit
            if not await self.rate_limiter.check_limit(workspace_id, 'files.upload'):
                raise SlackApiError("Rate limit exceeded for files.upload")
            
            client = self._get_client(workspace_id)
            if not client:
                raise SlackApiError("Failed to create Slack client")
            
            upload_data = {
                'channels': channel_id,
                'file': file_path
            }
            
            if title:
                upload_data['title'] = title
            
            if initial_comment:
                upload_data['initial_comment'] = initial_comment
            
            response = await client.files_upload_v2(**upload_data)
            
            if response['ok']:
                file_data = response['file']
                slack_file = SlackFile(
                    file_id=file_data['id'],
                    name=file_data['name'],
                    title=file_data.get('title', ''),
                    mimetype=file_data['mimetype'],
                    filetype=file_data['filetype'],
                    pretty_type=file_data['pretty_type'],
                    size=file_data['size'],
                    url_private=file_data['url_private'],
                    url_private_download=file_data.get('url_private_download'),
                    permalink=file_data['permalink'],
                    permalink_public=file_data.get('permalink_public'),
                    user_id=file_data['user'],
                    user_name='',  # Will be populated from cache
                    channel_id=channel_id,
                    workspace_id=workspace_id,
                    timestamp=file_data['timestamp'],
                    is_public=file_data.get('is_public', False),
                    is_editable=file_data.get('is_editable', True),
                    external_type=file_data.get('external_type'),
                    external_url=file_data.get('external_url'),
                    metadata={}
                )
                
                # Cache file
                await self._cache_file(workspace_id, slack_file)
                
                return {
                    'ok': True,
                    'file': asdict(slack_file),
                    'message': 'File uploaded successfully'
                }
            else:
                raise SlackApiError(f"Failed to upload file: {response.get('error')}")
        
        except SlackApiError as e:
            logger.error(f"Error uploading file: {e}")
            return {
                'ok': False,
                'error': str(e),
                'message': 'Failed to upload file'
            }
        
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            return {
                'ok': False,
                'error': str(e),
                'message': 'Unexpected error occurred'
            }
    
    async def search_messages(self, workspace_id: str, query: str,
                           channel_id: str = None, user_id: str = None,
                           sort: str = 'timestamp', sort_dir: str = 'desc',
                           count: int = 100) -> Dict[str, Any]:
        """Search messages in workspace"""
        try:
            # Check rate limit
            if not await self.rate_limiter.check_limit(workspace_id, 'search.messages'):
                raise SlackApiError("Rate limit exceeded for search.messages")
            
            client = self._get_client(workspace_id)
            if not client:
                raise SlackApiError("Failed to create Slack client")
            
            search_params = {
                'query': query,
                'sort': sort,
                'sort_dir': sort_dir,
                'count': min(count, 1000)
            }
            
            if channel_id:
                search_params['channel'] = channel_id
            
            response = await client.search_messages(**search_params)
            
            if response['ok']:
                messages = []
                for match in response['messages']['matches']:
                    message = SlackMessage(
                        message_id=match['ts'],
                        text=match.get('text', ''),
                        user_id=match.get('user', ''),
                        user_name='',  # Will be populated from cache
                        channel_id=match['channel']['id'],
                        channel_name=match['channel']['name'],
                        workspace_id=workspace_id,
                        timestamp=match['ts'],
                        thread_ts=match.get('thread_ts'),
                        reply_count=match.get('reply_count', 0),
                        message_type='search_result',
                        reactions=match.get('reactions', []),
                        files=match.get('files', []),
                        pinned_to=match.get('pinned_to', []),
                        is_starred=match.get('is_starred', False),
                        is_edited=False,
                        blocks=match.get('blocks', []),
                        mentions=self._extract_mentions(match.get('text', '')),
                        metadata={'search_score': match.get('score')}
                    )
                    messages.append(message)
                
                return {
                    'ok': True,
                    'messages': messages,
                    'total': response['messages']['total'],
                    'paging': response['messages']['paging']
                }
            else:
                raise SlackApiError(f"Search failed: {response.get('error')}")
        
        except SlackApiError as e:
            logger.error(f"Error searching messages: {e}")
            return {
                'ok': False,
                'error': str(e),
                'messages': []
            }
        
        except Exception as e:
            logger.error(f"Unexpected error searching messages: {e}")
            return {
                'ok': False,
                'error': str(e),
                'messages': []
            }
    
    async def verify_webhook_signature(self, body: bytes, timestamp: str, signature: str) -> bool:
        """Verify Slack webhook signature"""
        try:
            if not self.signing_secret:
                return False
            
            # Check timestamp (prevent replay attacks)
            request_time = int(timestamp)
            current_time = int(time.time())
            if abs(current_time - request_time) > 300:  # 5 minutes
                return False
            
            # Create signature
            sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
            expected_signature = 'v0=' + hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
        
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    async def handle_webhook_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Slack webhook event"""
        try:
            event_type = event_data.get('event', {}).get('type')
            workspace_id = event_data.get('team_id')
            
            # Cache event for processing
            if self.redis_client:
                await self.redis_client.lpush(
                    f"slack_events:{workspace_id}",
                    json.dumps(event_data)
                )
                # Keep only last 1000 events
                await self.redis_client.ltrim(f"slack_events:{workspace_id}", 0, 999)
            
            # Find and call event handlers
            if event_type in [t.value for t in SlackEventType]:
                slack_event_type = SlackEventType(event_type)
                for handler in self.event_handlers.get(slack_event_type, []):
                    try:
                        await handler(event_data)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
            
            # Call webhook handlers
            for handler in self.webhook_handlers:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Error in webhook handler: {e}")
            
            return {
                'ok': True,
                'event_type': event_type,
                'handled': True
            }
        
        except Exception as e:
            logger.error(f"Error handling webhook event: {e}")
            return {
                'ok': False,
                'error': str(e),
                'handled': False
            }
    
    def register_event_handler(self, event_type: SlackEventType, handler: Callable):
        """Register event handler"""
        if handler not in self.event_handlers[event_type]:
            self.event_handlers[event_type].append(handler)
            logger.info(f"Registered handler for {event_type}")
    
    def register_webhook_handler(self, handler: Callable):
        """Register webhook handler"""
        if handler not in self.webhook_handlers:
            self.webhook_handlers.append(handler)
            logger.info("Registered webhook handler")
    
    async def _cache_message(self, workspace_id: str, message: Dict[str, Any]):
        """Cache message for quick access"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"message:{workspace_id}:{message['ts']}"
            await self.redis_client.setex(cache_key, 3600, json.dumps(message))
        except Exception as e:
            logger.error(f"Error caching message: {e}")
    
    async def _cache_messages(self, workspace_id: str, channel_id: str, messages: List[SlackMessage]):
        """Cache messages for channel"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"messages:{workspace_id}:{channel_id}"
            message_data = [asdict(m) for m in messages]
            await self.redis_client.setex(cache_key, 1800, json.dumps(message_data))
        except Exception as e:
            logger.error(f"Error caching messages: {e}")
    
    async def _cache_file(self, workspace_id: str, slack_file: SlackFile):
        """Cache file information"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"file:{workspace_id}:{slack_file.file_id}"
            await self.redis_client.setex(cache_key, 7200, json.dumps(asdict(slack_file)))
        except Exception as e:
            logger.error(f"Error caching file: {e}")
    
    def _extract_mentions(self, text: str) -> List[str]:
        """Extract user mentions from text"""
        import re
        pattern = r'<@([UW][A-Z0-9]+)>'
        return re.findall(pattern, text)
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "name": "Slack Enhanced Service",
            "version": "3.0.0",
            "description": "Production-ready Slack integration with full capabilities",
            "features": [
                "oauth_authentication",
                "message_management",
                "file_handling",
                "channel_operations",
                "search_functionality",
                "webhook_processing",
                "rate_limiting",
                "caching",
                "encryption",
                "error_handling",
                "real_time_events"
            ],
            "supported_operations": [
                "send_message",
                "get_channel_history",
                "upload_file",
                "search_messages",
                "list_channels",
                "handle_webhooks"
            ],
            "status": {
                "connected_workspaces": len([s for s in self.connection_status.values() if s == SlackConnectionStatus.CONNECTED]),
                "total_clients": len(self.clients),
                "redis_connected": self.redis_client is not None,
                "encryption_enabled": self.cipher is not None
            },
            "performance": {
                "rate_limiting": "enabled",
                "caching": "enabled",
                "async_operations": "enabled"
            }
        }
    
    async def close(self):
        """Close all connections and cleanup"""
        for client in self.clients.values():
            await client.close()
        
        for client in self.sync_clients.values():
            client.close()
        
        if self.redis_client:
            self.redis_client.close()
        
        logger.info("Slack Enhanced Service closed")

# Global service instance
slack_enhanced_service = SlackEnhancedService({
    'client_id': os.getenv('SLACK_CLIENT_ID'),
    'client_secret': os.getenv('SLACK_CLIENT_SECRET'),
    'signing_secret': os.getenv('SLACK_SIGNING_SECRET'),
    'redirect_uri': os.getenv('SLACK_REDIRECT_URI', 'http://localhost:3000/integrations/slack/callback'),
    'encryption_key': os.getenv('ENCRYPTION_KEY'),
    'redis': {
        'enabled': os.getenv('REDIS_ENABLED', 'false').lower() == 'true',
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': int(os.getenv('REDIS_PORT', 6379)),
        'db': int(os.getenv('REDIS_DB', 0))
    }
})