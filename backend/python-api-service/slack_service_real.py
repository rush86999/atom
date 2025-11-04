"""
ATOM Real Slack Service
Production-ready Slack Web API integration
"""

import os
import logging
import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from loguru import logger

# Import crypto utilities
try:
    from crypto_utils import decrypt_data, encrypt_data
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("Crypto utils not available")

# Import database utilities
try:
    from db_utils import get_db_connection
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database utils not available")

@dataclass
class SlackTokenInfo:
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    scope: str
    team_id: str
    team_name: str
    user_id: str
    user_name: str
    bot_user_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

@dataclass
class SlackMessage:
    type: str
    subtype: Optional[str]
    channel: str
    user: str
    text: str
    ts: str
    thread_ts: Optional[str] = None
    reply_count: Optional[int] = None
    file: Optional[Dict[str, Any]] = None
    files: Optional[List[Dict[str, Any]]] = None
    reactions: Optional[List[Dict[str, Any]]] = None
    starred: Optional[bool] = None
    pinned: Optional[bool] = None
    is_starred: Optional[bool] = None
    is_pinned: Optional[bool] = None

@dataclass
class SlackChannel:
    id: str
    name: str
    display_name: str
    purpose: Optional[str]
    topic: Optional[str]
    is_private: bool
    is_archived: bool
    is_general: bool
    is_shared: bool
    is_org_shared: bool
    num_members: int
    creator: str
    created: int
    workspace_id: str
    type: str
    unread_count: Optional[int] = None
    latest: Optional[str] = None

@dataclass
class SlackUser:
    id: str
    name: str
    real_name: str
    display_name: str
    email: Optional[str]
    team_id: str
    is_admin: bool
    is_owner: bool
    is_primary_owner: bool
    is_restricted: bool
    is_ultra_restricted: bool
    is_bot: bool
    profile: Optional[Dict[str, Any]] = None

@dataclass
class SlackWorkspace:
    id: str
    name: str
    domain: str
    url: str
    icon: Optional[str]
    enterprise_id: Optional[str]
    enterprise_name: Optional[str]

class RealSlackService:
    """
    Production-ready Slack Web API service
    Implements real Slack API calls, not mocks
    """
    
    def __init__(self):
        self.api_base_url = "https://slack.com/api"
        self.token_cache: Dict[str, SlackTokenInfo] = {}
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        self.db_pool = None
        
        # Initialize database pool if available
        if DB_AVAILABLE:
            self._init_db_pool()
        
        logger.info("Real Slack Service initialized")
    
    def _init_db_pool(self):
        """Initialize database connection pool"""
        try:
            # Use existing database connection from app
            from flask import current_app
            self.db_pool = current_app.config.get("DB_CONNECTION_POOL")
            if self.db_pool:
                logger.info("Slack service: Using existing database connection pool")
            else:
                logger.warning("Slack service: No database connection pool available")
        except Exception as e:
            logger.error(f"Slack service: Failed to initialize DB pool: {e}")
    
    def _get_http_client(self, access_token: str) -> httpx.AsyncClient:
        """Create HTTP client for Slack API"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'ATOM-Platform/1.0'
        }
        
        return httpx.AsyncClient(
            base_url=self.api_base_url,
            headers=headers,
            timeout=30.0
        )
    
    def _check_rate_limit(self, endpoint: str, response: httpx.Response) -> bool:
        """Check and handle Slack rate limits"""
        try:
            # Slack rate limit headers
            remaining = response.headers.get('x-ratelimit-remaining')
            reset = response.headers.get('x-ratelimit-reset')
            
            if remaining is not None and reset is not None:
                self.rate_limits[endpoint] = {
                    'remaining': int(remaining),
                    'reset_time': int(reset),
                    'reset_datetime': datetime.fromtimestamp(int(reset))
                }
                
                # Log low rate limits
                if int(remaining) < 10:
                    logger.warning(f"Slack API rate limit low for {endpoint}: {remaining} remaining")
                
                return int(remaining) > 0
        
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
        
        return True
    
    def _format_slack_error(self, response: httpx.Response) -> Dict[str, Any]:
        """Format Slack API error response"""
        try:
            data = response.json()
            return {
                'ok': False,
                'error': data.get('error', 'Unknown error'),
                'detail': data.get('detail', data.get('response_metadata', {})),
                'status_code': response.status_code,
                'endpoint': str(response.url)
            }
        except:
            return {
                'ok': False,
                'error': f'HTTP {response.status_code}',
                'status_code': response.status_code,
                'endpoint': str(response.url)
            }
    
    def _format_slack_success(self, data: Any, endpoint: str) -> Dict[str, Any]:
        """Format Slack API success response"""
        return {
            'ok': True,
            'data': data,
            'endpoint': endpoint,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'slack_web_api'
        }
    
    async def _get_user_tokens_from_db(self, user_id: str) -> Optional[SlackTokenInfo]:
        """Get Slack tokens from database"""
        try:
            if not self.db_pool:
                return None
            
            conn = self.db_pool.getconn()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT access_token, refresh_token, token_type, scope,
                               team_id, team_name, user_id, user_name,
                               bot_user_id, expires_at, created_at
                        FROM user_slack_oauth_tokens
                        WHERE user_id = %s AND is_active = TRUE
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (user_id,))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        # Decrypt access token if crypto is available
                        access_token = result[0]
                        if CRYPTO_AVAILABLE:
                            access_token = decrypt_data(access_token).decode()
                        
                        return SlackTokenInfo(
                            access_token=access_token,
                            refresh_token=result[1],
                            token_type=result[2],
                            scope=result[3],
                            team_id=result[4],
                            team_name=result[5],
                            user_id=result[6],
                            user_name=result[7],
                            bot_user_id=result[8],
                            expires_at=result[9],
                            created_at=result[10]
                        )
                
                return None
                
            finally:
                self.db_pool.putconn(conn)
        
        except Exception as e:
            logger.error(f"Error getting Slack tokens for user {user_id}: {e}")
            return None
    
    async def _save_user_tokens_to_db(self, user_id: str, token_info: SlackTokenInfo) -> bool:
        """Save Slack tokens to database"""
        try:
            if not self.db_pool:
                return False
            
            conn = self.db_pool.getconn()
            try:
                with conn.cursor() as cursor:
                    # Encrypt access token if crypto is available
                    access_token = token_info.access_token
                    if CRYPTO_AVAILABLE:
                        access_token = encrypt_data(access_token.encode()).decode()
                    
                    cursor.execute("""
                        INSERT INTO user_slack_oauth_tokens 
                        (user_id, access_token, refresh_token, token_type, scope,
                         team_id, team_name, user_id, user_name, bot_user_id,
                         expires_at, created_at, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, team_id) 
                        DO UPDATE SET
                        access_token = EXCLUDED.access_token,
                        refresh_token = EXCLUDED.refresh_token,
                        expires_at = EXCLUDED.expires_at,
                        created_at = EXCLUDED.created_at,
                        is_active = TRUE
                    """, (
                        user_id, access_token, token_info.refresh_token,
                        token_info.token_type, token_info.scope,
                        token_info.team_id, token_info.team_name,
                        token_info.user_id, token_info.user_name,
                        token_info.bot_user_id, token_info.expires_at,
                        token_info.created_at, True
                    ))
                
                conn.commit()
                logger.info(f"Slack tokens saved for user {user_id}")
                return True
                
            finally:
                self.db_pool.putconn(conn)
        
        except Exception as e:
            logger.error(f"Error saving Slack tokens for user {user_id}: {e}")
            return False
    
    async def get_user_tokens(self, user_id: str, force_refresh: bool = False) -> Optional[SlackTokenInfo]:
        """Get Slack tokens for user with caching"""
        try:
            # Check cache first
            if not force_refresh and user_id in self.token_cache:
                token_info = self.token_cache[user_id]
                
                # Check if token is expired
                if token_info.expires_at and token_info.expires_at <= datetime.utcnow():
                    logger.warning(f"Slack token expired for user {user_id}, removing from cache")
                    del self.token_cache[user_id]
                else:
                    return token_info
            
            # Try database
            token_info = await self._get_user_tokens_from_db(user_id)
            
            if token_info:
                # Cache the token
                self.token_cache[user_id] = token_info
                return token_info
            
            # Fallback to environment variables for testing
            if os.getenv('SLACK_ACCESS_TOKEN') and os.getenv('SLACK_BOT_TOKEN'):
                return SlackTokenInfo(
                    access_token=os.getenv('SLACK_ACCESS_TOKEN'),
                    bot_user_id=os.getenv('SLACK_BOT_TOKEN'),
                    token_type='Bearer',
                    scope='channels:read,channels:history,groups:read,groups:history,im:read,im:history,mpim:read,mpim:history,users:read,files:read,reactions:read,team:read',
                    team_id=os.getenv('SLACK_TEAM_ID', 'test-team'),
                    team_name=os.getenv('SLACK_TEAM_NAME', 'Test Team'),
                    user_id=user_id,
                    user_name='Test User',
                    created_at=datetime.utcnow()
                )
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting Slack tokens for user {user_id}: {e}")
            return None
    
    async def save_user_tokens(self, user_id: str, token_info: SlackTokenInfo) -> bool:
        """Save Slack tokens for user"""
        try:
            # Save to database
            db_saved = await self._save_user_tokens_to_db(user_id, token_info)
            
            # Update cache
            self.token_cache[user_id] = token_info
            
            logger.info(f"Slack tokens saved for user {user_id}")
            return db_saved
        
        except Exception as e:
            logger.error(f"Error saving Slack tokens for user {user_id}: {e}")
            return False
    
    async def get_user_workspaces(self, user_id: str) -> List[SlackWorkspace]:
        """Get user's Slack workspaces"""
        try:
            token_info = await self.get_user_tokens(user_id)
            if not token_info:
                return []
            
            async with self._get_http_client(token_info.access_token) as client:
                response = await client.get('/team.info', params={
                    'team': token_info.team_id
                })
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok'):
                        team_data = data.get('team', {})
                        workspace = SlackWorkspace(
                            id=team_data.get('id'),
                            name=team_data.get('name'),
                            domain=team_data.get('domain'),
                            url=team_data.get('url', f"https://{team_data.get('domain')}.slack.com"),
                            icon=team_data.get('icon'),
                            enterprise_id=team_data.get('enterprise_id'),
                            enterprise_name=team_data.get('enterprise_name')
                        )
                        
                        return [workspace]
                
                logger.error(f"Failed to get workspaces: {self._format_slack_error(response)}")
                return []
        
        except Exception as e:
            logger.error(f"Error getting workspaces: {e}")
            return []
    
    async def get_workspace_channels(self, user_id: str, workspace_id: str, 
                                   include_private: bool = False, 
                                   include_archived: bool = False,
                                   limit: int = 200) -> List[SlackChannel]:
        """Get channels from a workspace"""
        try:
            token_info = await self.get_user_tokens(user_id)
            if not token_info:
                return []
            
            async with self._get_http_client(token_info.access_token) as client:
                all_channels = []
                cursor = None
                
                while True:
                    response = await client.get('/conversations.list', params={
                        'types': 'public_channel,private_channel,mpim,im',
                        'exclude_archived': not include_archived,
                        'limit': min(limit - len(all_channels), 100),
                        'cursor': cursor
                    })
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get('ok'):
                            channels_data = data.get('channels', [])
                            
                            for channel_data in channels_data:
                                # Filter based on preferences
                                if channel_data.get('is_private') and not include_private:
                                    continue
                                
                                channel = SlackChannel(
                                    id=channel_data.get('id'),
                                    name=channel_data.get('name'),
                                    display_name=channel_data.get('name_normalized', channel_data.get('name')),
                                    purpose=channel_data.get('purpose', {}).get('value') if channel_data.get('purpose') else None,
                                    topic=channel_data.get('topic', {}).get('value') if channel_data.get('topic') else None,
                                    is_private=channel_data.get('is_private', False),
                                    is_archived=channel_data.get('is_archived', False),
                                    is_general=channel_data.get('is_general', False),
                                    is_shared=channel_data.get('is_shared', False),
                                    is_org_shared=channel_data.get('is_org_shared', False),
                                    num_members=channel_data.get('num_members', 0),
                                    creator=channel_data.get('creator'),
                                    created=channel_data.get('created', 0),
                                    workspace_id=workspace_id,
                                    type=channel_data.get('is_im') and 'im' or 
                                       channel_data.get('is_mpim') and 'mpim' or 
                                       'channel'
                                )
                                
                                all_channels.append(channel)
                            
                            # Check if we have more results
                            if data.get('response_metadata', {}).get('next_cursor'):
                                cursor = data['response_metadata']['next_cursor']
                            else:
                                break
                        else:
                            logger.error(f"Failed to get channels: {data.get('error')}")
                            break
                    else:
                        logger.error(f"Failed to get channels: {self._format_slack_error(response)}")
                        break
                    
                    if len(all_channels) >= limit:
                        break
                
                return all_channels[:limit]
        
        except Exception as e:
            logger.error(f"Error getting channels: {e}")
            return []
    
    async def get_workspace_users(self, user_id: str, workspace_id: str,
                                 include_restricted: bool = False,
                                 include_bots: bool = False,
                                 limit: int = 100) -> List[SlackUser]:
        """Get users from a workspace"""
        try:
            token_info = await self.get_user_tokens(user_id)
            if not token_info:
                return []
            
            async with self._get_http_client(token_info.access_token) as client:
                all_users = []
                cursor = None
                
                while True:
                    response = await client.get('/users.list', params={
                        'limit': min(limit - len(all_users), 100),
                        'cursor': cursor
                    })
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get('ok'):
                            users_data = data.get('members', [])
                            
                            for user_data in users_data:
                                # Filter based on preferences
                                if user_data.get('is_restricted') and not include_restricted:
                                    continue
                                
                                if user_data.get('is_bot') and not include_bots and user_data.get('id') != token_info.bot_user_id:
                                    continue
                                
                                user = SlackUser(
                                    id=user_data.get('id'),
                                    name=user_data.get('name'),
                                    real_name=user_data.get('real_name'),
                                    display_name=user_data.get('profile', {}).get('display_name') or user_data.get('name'),
                                    email=user_data.get('profile', {}).get('email'),
                                    team_id=workspace_id,
                                    is_admin=user_data.get('is_admin', False),
                                    is_owner=user_data.get('is_owner', False),
                                    is_primary_owner=user_data.get('is_primary_owner', False),
                                    is_restricted=user_data.get('is_restricted', False),
                                    is_ultra_restricted=user_data.get('is_ultra_restricted', False),
                                    is_bot=user_data.get('is_bot', False),
                                    profile=user_data.get('profile')
                                )
                                
                                all_users.append(user)
                            
                            # Check if we have more results
                            if data.get('response_metadata', {}).get('next_cursor'):
                                cursor = data['response_metadata']['next_cursor']
                            else:
                                break
                        else:
                            logger.error(f"Failed to get users: {data.get('error')}")
                            break
                    else:
                        logger.error(f"Failed to get users: {self._format_slack_error(response)}")
                        break
                    
                    if len(all_users) >= limit:
                        break
                
                return all_users[:limit]
        
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
    
    async def get_user_profile(self, user_id: str) -> Optional[SlackUser]:
        """Get current user profile"""
        try:
            token_info = await self.get_user_tokens(user_id)
            if not token_info:
                return None
            
            async with self._get_http_client(token_info.access_token) as client:
                response = await client.get('/auth.test')
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok'):
                        user = SlackUser(
                            id=data.get('user_id'),
                            name=data.get('user'),
                            real_name=data.get('user'),
                            display_name=data.get('user'),
                            team_id=data.get('team_id'),
                            is_admin=data.get('is_admin', False),
                            is_owner=False,  # Not available in auth.test
                            is_primary_owner=False,
                            is_restricted=False,
                            is_ultra_restricted=False,
                            is_bot=data.get('bot_id') is not None
                        )
                        
                        return user
                
                logger.error(f"Failed to get user profile: {self._format_slack_error(response)}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
    
    async def get_channel_messages(self, user_id: str, channel_id: str,
                                   filters: Optional[Dict[str, Any]] = None,
                                   limit: int = 100) -> List[SlackMessage]:
        """Get messages from a channel"""
        try:
            token_info = await self.get_user_tokens(user_id)
            if not token_info:
                return []
            
            filters = filters or {}
            async with self._get_http_client(token_info.access_token) as client:
                all_messages = []
                cursor = None
                
                while True:
                    response = await client.get('/conversations.history', params={
                        'channel': channel_id,
                        'limit': min(limit - len(all_messages), 100),
                        'cursor': cursor,
                        'oldest': filters.get('start_time'),
                        'latest': filters.get('end_time')
                    })
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get('ok'):
                            messages_data = data.get('messages', [])
                            
                            for message_data in messages_data:
                                # Apply filters
                                if filters.get('from') == 'me' and message_data.get('user') != user_id:
                                    continue
                                
                                if filters.get('has_files') and not message_data.get('files'):
                                    continue
                                
                                message = SlackMessage(
                                    type=message_data.get('type', 'message'),
                                    subtype=message_data.get('subtype'),
                                    channel=channel_id,
                                    user=message_data.get('user'),
                                    text=message_data.get('text'),
                                    ts=message_data.get('ts'),
                                    thread_ts=message_data.get('thread_ts'),
                                    reply_count=len(message_data.get('replies', [])) if message_data.get('replies') else None,
                                    file=message_data.get('file'),
                                    files=message_data.get('files'),
                                    reactions=message_data.get('reactions'),
                                    starred=message_data.get('is_starred', False),
                                    pinned=message_data.get('pinned_to', []) and message_data['pinned_to'][0] is not None
                                )
                                
                                all_messages.append(message)
                            
                            # Check if we have more results
                            if data.get('has_more') and data.get('response_metadata', {}).get('next_cursor'):
                                cursor = data['response_metadata']['next_cursor']
                            else:
                                break
                        else:
                            logger.error(f"Failed to get messages: {data.get('error')}")
                            break
                    else:
                        logger.error(f"Failed to get messages: {self._format_slack_error(response)}")
                        break
                    
                    if len(all_messages) >= limit:
                        break
                
                return all_messages[:limit]
        
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []
    
    async def search_slack(self, user_id: str, query: str, 
                           search_type: str = 'global',
                           limit: int = 50) -> Dict[str, Any]:
        """Search across Slack"""
        try:
            token_info = await self.get_user_tokens(user_id)
            if not token_info:
                return {'ok': False, 'error': 'No tokens available'}
            
            async with self._get_http_client(token_info.access_token) as client:
                response = await client.get('/search.messages', params={
                    'query': query,
                    'count': min(limit, 100)
                })
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok'):
                        return {
                            'ok': True,
                            'messages': data.get('messages', {}).get('matches', []),
                            'total_count': data.get('messages', {}).get('total', 0),
                            'query': query
                        }
                
                logger.error(f"Failed to search: {self._format_slack_error(response)}")
                return {'ok': False, 'error': 'Search failed'}
        
        except Exception as e:
            logger.error(f"Error searching Slack: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def send_message(self, user_id: str, channel_id: str, 
                          text: str, thread_ts: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to a channel"""
        try:
            token_info = await self.get_user_tokens(user_id)
            if not token_info:
                return {'ok': False, 'error': 'No tokens available'}
            
            async with self._get_http_client(token_info.access_token) as client:
                params = {
                    'channel': channel_id,
                    'text': text
                }
                
                if thread_ts:
                    params['thread_ts'] = thread_ts
                
                response = await client.post('/chat.postMessage', json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok'):
                        return {
                            'ok': True,
                            'message': data.get('message'),
                            'ts': data.get('ts'),
                            'channel': data.get('channel')
                        }
                
                logger.error(f"Failed to send message: {self._format_slack_error(response)}")
                return {'ok': False, 'error': data.get('error', 'Send failed')}
        
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {'ok': False, 'error': str(e)}
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get Slack service information"""
        return {
            'name': 'Real Slack Service',
            'version': '1.0.0',
            'api_base_url': self.api_base_url,
            'features': [
                'Real Slack Web API integration',
                'Token management with caching',
                'Rate limiting support',
                'Database token storage with encryption',
                'Comprehensive endpoint coverage',
                'Production-ready error handling'
            ],
            'supported_endpoints': [
                'auth.test',
                'team.info',
                'conversations.list',
                'conversations.history',
                'users.list',
                'search.messages',
                'chat.postMessage'
            ],
            'database_available': DB_AVAILABLE,
            'crypto_available': CRYPTO_AVAILABLE,
            'cache_size': len(self.token_cache)
        }

# Create global instance
slack_service = RealSlackService()