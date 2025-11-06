"""
Enhanced Slack Service - Unified API Interface
Complete Slack service with consistent error handling and rate limiting
"""

import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
import hmac
import hashlib

# Configure logging
logger = logging.getLogger(__name__)

# Slack API configuration
SLACK_API_BASE_URL = "https://slack.com/api"

class SlackOperationType(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SEARCH = "search"

@dataclass
class SlackRateLimit:
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None

class SlackError(Exception):
    """Base Slack error class"""
    pass

class SlackAPIError(SlackError):
    """Slack API returned an error"""
    pass

class SlackRateLimitError(SlackError):
    """Rate limit exceeded"""
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after

class SlackNetworkError(SlackError):
    """Network-related error"""
    pass

class SlackHTTPError(SlackError):
    """HTTP error"""
    pass

class SlackServiceError(SlackError):
    """Service-level error"""
    pass

class SlackUnifiedService:
    """Unified Slack service with consistent API and error handling"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.api_base_url = self.config.get('api_base_url', SLACK_API_BASE_URL)
        self.client_id = self.config.get('client_id') or os.getenv('SLACK_CLIENT_ID')
        self.client_secret = self.config.get('client_secret') or os.getenv('SLACK_CLIENT_SECRET')
        self.signing_secret = self.config.get('signing_secret') or os.getenv('SLACK_SIGNING_SECRET')
        
        # HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.api_base_url,
            timeout=30.0
        )
        
        # Rate limiting
        self.rate_limits: Dict[str, SlackRateLimit] = {}
        
        # Caching
        self._cache = {}
        self._cache_ttl = self.config.get('cache_ttl', 300)  # 5 minutes default
        
        logger.info(f"Slack unified service initialized with base URL: {self.api_base_url}")
    
    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        operation_type: SlackOperationType = SlackOperationType.READ
    ) -> Dict[str, Any]:
        """Unified request method with rate limiting and error handling"""
        
        try:
            # Check rate limits
            if endpoint in self.rate_limits:
                rate_limit = self.rate_limits[endpoint]
                if rate_limit.remaining <= 1:
                    wait_time = (rate_limit.reset_time - datetime.utcnow()).total_seconds()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
            
            # Make request
            headers = {}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            # Add content-type for POST/PUT requests
            if method.upper() in ['POST', 'PUT', 'PATCH']:
                headers['Content-Type'] = 'application/json'
            
            response = await self.client.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
                headers=headers
            )
            
            # Update rate limits
            self._update_rate_limits(endpoint, response)
            
            # Handle response
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    return result
                else:
                    error_msg = result.get('error', 'Unknown Slack API error')
                    raise SlackAPIError(error_msg)
            elif response.status_code == 429:
                # Rate limited
                retry_after = int(response.headers.get('Retry-After', 60))
                raise SlackRateLimitError(f"Rate limited. Retry after {retry_after}s", retry_after)
            else:
                raise SlackHTTPError(f"HTTP {response.status_code}: {response.text}")
                
        except httpx.RequestError as e:
            raise SlackNetworkError(f"Network error: {str(e)}")
        except SlackError:
            # Re-raise our own errors
            raise
        except Exception as e:
            raise SlackServiceError(f"Unexpected error: {str(e)}")
    
    def _update_rate_limits(self, endpoint: str, response: httpx.Response):
        """Update rate limit information from response headers"""
        try:
            limit = response.headers.get('X-RateLimit-Limit')
            remaining = response.headers.get('X-RateLimit-Remaining')
            reset = response.headers.get('X-RateLimit-Reset')
            
            if limit and remaining and reset:
                self.rate_limits[endpoint] = SlackRateLimit(
                    limit=int(limit),
                    remaining=int(remaining),
                    reset_time=datetime.fromtimestamp(int(reset))
                )
        except Exception as e:
            logger.warning(f"Failed to update rate limits: {e}")
    
    async def get_oauth_url(self, user_id: str, scopes: List[str], state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL"""
        try:
            import secrets
            import urllib.parse
            
            # Generate state if not provided
            if not state:
                state = secrets.token_urlsafe(16)
            
            # Build parameters
            params = {
                'client_id': self.client_id,
                'scope': ' '.join(scopes),
                'redirect_uri': self.config.get('redirect_uri', 'http://localhost:3000/integrations/slack/callback'),
                'state': state,
                'user': user_id
            }
            
            # Generate URL
            auth_url = f"https://slack.com/oauth/v2/authorize?{urllib.parse.urlencode(params)}"
            
            return auth_url
            
        except Exception as e:
            raise SlackServiceError(f"Failed to generate OAuth URL: {str(e)}")
    
    async def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'redirect_uri': self.config.get('redirect_uri', 'http://localhost:3000/integrations/slack/callback')
            }
            
            if state:
                data['state'] = state
            
            result = await self.make_request('POST', 'oauth.v2.access', data=data)
            
            return {
                'access_token': result['access_token'],
                'token_type': result['token_type'],
                'scope': result['scope'],
                'bot_user_id': result['bot_user_id'],
                'team_id': result['team']['id'],
                'team_name': result['team']['name'],
                'enterprise_id': result.get('enterprise', {}).get('id'),
                'enterprise_name': result.get('enterprise', {}).get('name'),
                'authed_user': result.get('authed_user', {}),
                'expires_in': result.get('expires_in'),
                'refresh_token': result.get('refresh_token')
            }
            
        except Exception as e:
            raise SlackServiceError(f"Failed to exchange code for token: {str(e)}")
    
    async def verify_webhook_signature(self, request_body: bytes, timestamp: str, signature: str) -> bool:
        """Verify Slack webhook signature"""
        try:
            if not self.signing_secret:
                raise SlackServiceError("Signing secret not configured")
            
            # Check timestamp (prevent replay attacks)
            request_time = int(timestamp)
            current_time = int(datetime.now().timestamp())
            if abs(current_time - request_time) > 300:  # 5 minutes
                return False
            
            # Create signature
            sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
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
    
    async def test_connection(self, token: str) -> Dict[str, Any]:
        """Test API connection"""
        try:
            result = await self.make_request('GET', 'auth.test', token=token)
            
            return {
                'connected': True,
                'user_id': result.get('user_id'),
                'user': result.get('user'),
                'team_id': result.get('team_id'),
                'team': result.get('team'),
                'bot_id': result.get('bot_id'),
                'url': result.get('url'),
                'response_metadata': result.get('response_metadata', {})
            }
            
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    async def get_user_info(self, token: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get user information"""
        try:
            if user_id:
                params = {'user': user_id}
                result = await self.make_request('GET', 'users.info', params=params, token=token)
                return result.get('user', {})
            else:
                result = await self.make_request('GET', 'auth.test', token=token)
                return {
                    'id': result.get('user_id'),
                    'name': result.get('user'),
                    'team_id': result.get('team_id'),
                    'team': result.get('team')
                }
                
        except Exception as e:
            raise SlackServiceError(f"Failed to get user info: {str(e)}")
    
    async def get_team_info(self, token: str) -> Dict[str, Any]:
        """Get team information"""
        try:
            result = await self.make_request('GET', 'team.info', token=token)
            return result.get('team', {})
            
        except Exception as e:
            raise SlackServiceError(f"Failed to get team info: {str(e)}")
    
    async def list_channels(self, token: str, types: str = "public_channel,private_channel") -> List[Dict[str, Any]]:
        """List channels"""
        try:
            params = {'types': types}
            result = await self.make_request('GET', 'conversations.list', params=params, token=token)
            return result.get('channels', [])
            
        except Exception as e:
            raise SlackServiceError(f"Failed to list channels: {str(e)}")
    
    async def get_channel_info(self, token: str, channel_id: str) -> Dict[str, Any]:
        """Get channel information"""
        try:
            params = {'channel': channel_id}
            result = await self.make_request('GET', 'conversations.info', params=params, token=token)
            return result.get('channel', {})
            
        except Exception as e:
            raise SlackServiceError(f"Failed to get channel info: {str(e)}")
    
    async def get_channel_history(
        self,
        token: str,
        channel_id: str,
        limit: int = 100,
        latest: Optional[str] = None,
        oldest: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get channel message history"""
        try:
            params = {
                'channel': channel_id,
                'limit': min(limit, 1000)  # Slack API limit
            }
            
            if latest:
                params['latest'] = latest
            if oldest:
                params['oldest'] = oldest
            
            result = await self.make_request('GET', 'conversations.history', params=params, token=token)
            return result
            
        except Exception as e:
            raise SlackServiceError(f"Failed to get channel history: {str(e)}")
    
    async def post_message(
        self,
        token: str,
        channel_id: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Post a message to a channel"""
        try:
            data = {
                'channel': channel_id,
                'text': text
            }
            
            if thread_ts:
                data['thread_ts'] = thread_ts
            
            if blocks:
                data['blocks'] = blocks
            
            result = await self.make_request('POST', 'chat.postMessage', data=data, token=token)
            return result
            
        except Exception as e:
            raise SlackServiceError(f"Failed to post message: {str(e)}")
    
    async def update_message(
        self,
        token: str,
        channel_id: str,
        message_ts: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Update a message"""
        try:
            data = {
                'channel': channel_id,
                'ts': message_ts,
                'text': text
            }
            
            if blocks:
                data['blocks'] = blocks
            
            result = await self.make_request('POST', 'chat.update', data=data, token=token)
            return result
            
        except Exception as e:
            raise SlackServiceError(f"Failed to update message: {str(e)}")
    
    async def delete_message(self, token: str, channel_id: str, message_ts: str) -> Dict[str, Any]:
        """Delete a message"""
        try:
            data = {
                'channel': channel_id,
                'ts': message_ts
            }
            
            result = await self.make_request('POST', 'chat.delete', data=data, token=token)
            return result
            
        except Exception as e:
            raise SlackServiceError(f"Failed to delete message: {str(e)}")
    
    async def search_messages(
        self,
        token: str,
        query: str,
        sort: str = "timestamp",
        sort_dir: str = "desc",
        count: int = 100
    ) -> Dict[str, Any]:
        """Search messages"""
        try:
            params = {
                'query': query,
                'sort': sort,
                'sort_dir': sort_dir,
                'count': min(count, 1000)
            }
            
            result = await self.make_request('GET', 'search.messages', params=params, token=token)
            return result
            
        except Exception as e:
            raise SlackServiceError(f"Failed to search messages: {str(e)}")
    
    async def list_files(
        self,
        token: str,
        channel_id: Optional[str] = None,
        user_id: Optional[str] = None,
        count: int = 100
    ) -> Dict[str, Any]:
        """List files"""
        try:
            params = {
                'count': min(count, 1000)
            }
            
            if channel_id:
                params['channel'] = channel_id
            if user_id:
                params['user'] = user_id
            
            result = await self.make_request('GET', 'files.list', params=params, token=token)
            return result
            
        except Exception as e:
            raise SlackServiceError(f"Failed to list files: {str(e)}")
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "name": "Slack Unified Service",
            "version": "2.0.0",
            "description": "Unified Slack service with consistent API and error handling",
            "capabilities": [
                "oauth_flow",
                "webhook_verification",
                "rate_limiting",
                "error_handling",
                "caching",
                "user_management",
                "channel_operations",
                "message_operations",
                "search",
                "file_management"
            ],
            "api_endpoints": [
                "oauth.v2.access",
                "auth.test",
                "users.info",
                "team.info",
                "conversations.list",
                "conversations.info",
                "conversations.history",
                "chat.postMessage",
                "chat.update",
                "chat.delete",
                "search.messages",
                "files.list"
            ],
            "initialized_at": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Close HTTP client and cleanup"""
        await self.client.aclose()
        logger.info("Slack unified service closed")

# Create singleton instance
slack_unified_service = SlackUnifiedService()