#!/usr/bin/env python3
"""
🚀 ATOM Phase 3: Real API Implementation & Enterprise Features
Connects to real APIs and implements enterprise-grade capabilities
"""

import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import secrets
import base64

logger = logging.getLogger(__name__)

class APIServiceStatus(Enum):
    """Real API service status"""
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated" 
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    NOT_CONFIGURED = "not_configured"

@dataclass
class APIResponse:
    """Standard API response structure"""
    success: bool
    data: Any
    error: Optional[str] = None
    status_code: Optional[int] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None
    request_id: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

class BaseAPIConnector(ABC):
    """Base class for real API connectors"""
    
    def __init__(self, client_id: str, client_secret: str, base_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.rate_limit_remaining: Optional[int] = None
        self.rate_limit_reset: Optional[datetime] = None
        self.last_request_time: Optional[datetime] = None
        
    async def authenticate(self, code: Optional[str] = None, user_token: Optional[str] = None) -> APIResponse:
        """Authenticate with the service"""
        if code:
            return await self._exchange_code_for_token(code)
        elif user_token:
            self.access_token = user_token
            return APIResponse(success=True, data={'authenticated': True})
        else:
            return APIResponse(success=False, error="No authentication method provided")
    
    @abstractmethod
    async def _exchange_code_for_token(self, code: str) -> APIResponse:
        """Exchange authorization code for access token"""
        pass
    
    @abstractmethod
    async def refresh_access_token(self) -> APIResponse:
        """Refresh access token"""
        pass
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> APIResponse:
        """Make authenticated API request"""
        
        # Check rate limiting
        if self._is_rate_limited():
            return APIResponse(
                success=False,
                error=f"Rate limited. Reset at {self.rate_limit_reset}",
                status_code=429
            )
        
        # Prepare request headers
        request_headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json',
            'User-Agent': 'ATOM-Integration-Platform/3.0.0'
        }
        
        if headers:
            request_headers.update(headers)
        
        # Make request
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with httpx.AsyncClient(timeout=httpx.ClientTimeout(total=30.0)) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, params=params, headers=request_headers)
                elif method.upper() == 'POST':
                    response = await client.post(url, json=data, params=params, headers=request_headers)
                elif method.upper() == 'PUT':
                    response = await client.put(url, json=data, params=params, headers=request_headers)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, params=params, headers=request_headers)
                else:
                    return APIResponse(success=False, error=f"Unsupported HTTP method: {method}")
                
                # Update rate limiting info
                self._update_rate_limiting(response)
                
                # Process response
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                return APIResponse(
                    success=response.status_code < 400,
                    data=response_data,
                    status_code=response.status_code,
                    rate_limit_remaining=self.rate_limit_remaining,
                    rate_limit_reset=self.rate_limit_reset,
                    request_id=response.headers.get('x-request-id')
                )
        
        except httpx.TimeoutException:
            return APIResponse(success=False, error="Request timeout", status_code=408)
        except httpx.NetworkError as e:
            return APIResponse(success=False, error=f"Network error: {str(e)}", status_code=500)
        except Exception as e:
            return APIResponse(success=False, error=f"Unexpected error: {str(e)}", status_code=500)
    
    def _is_rate_limited(self) -> bool:
        """Check if currently rate limited"""
        if self.rate_limit_remaining and self.rate_limit_reset:
            if self.rate_limit_remaining <= 0 and datetime.now(timezone.utc) < self.rate_limit_reset:
                return True
        return False
    
    def _update_rate_limiting(self, response: httpx.Response):
        """Update rate limiting information from response headers"""
        # GitHub rate limiting
        if 'x-ratelimit-remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['x-ratelimit-remaining'])
        if 'x-ratelimit-reset' in response.headers:
            reset_timestamp = int(response.headers['x-ratelimit-reset'])
            self.rate_limit_reset = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
        
        # Notion rate limiting
        elif 'x-ratelimit-remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['x-ratelimit-remaining'])
        elif 'retry-after' in response.headers:
            retry_after = int(response.headers['retry-after'])
            self.rate_limit_reset = datetime.now(timezone.utc) + timedelta(seconds=retry_after)

class GitHubAPIConnector(BaseAPIConnector):
    """Real GitHub API connector"""
    
    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, "https://api.github.com")
    
    async def _exchange_code_for_token(self, code: str) -> APIResponse:
        """Exchange GitHub authorization code for access token"""
        url = "https://github.com/login/oauth/access_token"
        headers = {'Accept': 'application/json'}
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=headers)
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data['access_token']
                    self.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=token_data.get('expires_in', 3600))
                    
                    return APIResponse(success=True, data={
                        'access_token': token_data['access_token'],
                        'token_type': token_data['token_type'],
                        'scope': token_data['scope']
                    })
                else:
                    return APIResponse(success=False, error=f"GitHub OAuth failed: {response.text}", status_code=response.status_code)
        
        except Exception as e:
            return APIResponse(success=False, error=f"GitHub OAuth error: {str(e)}")
    
    async def refresh_access_token(self) -> APIResponse:
        """Refresh GitHub access token"""
        return APIResponse(success=False, error="GitHub doesn't support refresh tokens for this flow")
    
    async def get_user_repositories(self, user: str = None, type: str = 'all', sort: str = 'updated') -> APIResponse:
        """Get user repositories"""
        params = {'type': type, 'sort': sort, 'per_page': 100}
        endpoint = f"user/{user}/repos" if user else "user/repos"
        return await self._make_request('GET', endpoint, params=params)
    
    async def get_repository(self, owner: str, repo: str) -> APIResponse:
        """Get specific repository"""
        return await self._make_request('GET', f"repos/{owner}/{repo}")
    
    async def get_issues(self, owner: str, repo: str, state: str = 'open') -> APIResponse:
        """Get repository issues"""
        params = {'state': state, 'per_page': 100}
        return await self._make_request('GET', f"repos/{owner}/{repo}/issues", params=params)
    
    async def create_issue(self, owner: str, repo: str, title: str, body: str = None, labels: List[str] = None) -> APIResponse:
        """Create an issue"""
        data = {'title': title}
        if body:
            data['body'] = body
        if labels:
            data['labels'] = labels
        
        return await self._make_request('POST', f"repos/{owner}/{repo}/issues", data=data)
    
    async def get_user_info(self) -> APIResponse:
        """Get authenticated user information"""
        return await self._make_request('GET', 'user')

class NotionAPIConnector(BaseAPIConnector):
    """Real Notion API connector"""
    
    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, "https://api.notion.com/v1")
    
    async def _exchange_code_for_token(self, code: str) -> APIResponse:
        """Exchange Notion authorization code for access token"""
        url = "https://api.notion.com/v1/oauth/token"
        headers = {'Authorization': f'Basic {base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()}'}
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': os.getenv('NOTION_REDIRECT_URI', 'http://localhost:10000/api/oauth/notion/callback')
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=headers)
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data['access_token']
                    
                    return APIResponse(success=True, data={
                        'access_token': token_data['access_token'],
                        'workspace_name': token_data.get('workspace_name'),
                        'workspace_id': token_data.get('workspace_id')
                    })
                else:
                    return APIResponse(success=False, error=f"Notion OAuth failed: {response.text}", status_code=response.status_code)
        
        except Exception as e:
            return APIResponse(success=False, error=f"Notion OAuth error: {str(e)}")
    
    async def refresh_access_token(self) -> APIResponse:
        """Refresh Notion access token"""
        return APIResponse(success=False, error="Notion requires re-authorization")
    
    async def get_databases(self) -> APIResponse:
        """Get Notion databases"""
        return await self._make_request('POST', 'search', data={'filter': {'property': 'object', 'value': 'database'}})
    
    async def get_database_pages(self, database_id: str) -> APIResponse:
        """Get pages from a database"""
        return await self._make_request('POST', f'databases/{database_id}/query')
    
    async def create_page(self, parent: Dict, properties: Dict, children: List[Dict] = None) -> APIResponse:
        """Create a Notion page"""
        data = {'parent': parent, 'properties': properties}
        if children:
            data['children'] = children
        
        return await self._make_request('POST', 'pages', data=data)
    
    async def get_page(self, page_id: str) -> APIResponse:
        """Get a Notion page"""
        return await self._make_request('GET', f'pages/{page_id}')
    
    async def update_page(self, page_id: str, properties: Dict) -> APIResponse:
        """Update a Notion page"""
        return await self._make_request('PATCH', f'pages/{page_id}', data={'properties': properties})
    
    async def search_pages(self, query: str = None) -> APIResponse:
        """Search Notion pages"""
        data = {'filter': {'property': 'object', 'value': 'page'}}
        if query:
            data['query'] = query
        
        return await self._make_request('POST', 'search', data=data)

class SlackAPIConnector(BaseAPIConnector):
    """Real Slack API connector"""
    
    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, "https://slack.com/api")
    
    async def _exchange_code_for_token(self, code: str) -> APIResponse:
        """Exchange Slack authorization code for access token"""
        url = "https://slack.com/api/oauth.v2.access"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': os.getenv('SLACK_REDIRECT_URI', 'http://localhost:10000/api/oauth/slack/callback')
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data)
                
                if response.status_code == 200:
                    token_data = response.json()
                    
                    if token_data.get('ok'):
                        self.access_token = token_data['access_token']
                        if 'refresh_token' in token_data:
                            self.refresh_token = token_data['refresh_token']
                        
                        return APIResponse(success=True, data={
                            'access_token': token_data['access_token'],
                            'team': token_data.get('team'),
                            'user': token_data.get('authed_user'),
                            'scope': token_data.get('scope')
                        })
                    else:
                        return APIResponse(success=False, error=f"Slack OAuth error: {token_data.get('error')}")
                else:
                    return APIResponse(success=False, error=f"Slack OAuth failed: {response.text}", status_code=response.status_code)
        
        except Exception as e:
            return APIResponse(success=False, error=f"Slack OAuth error: {str(e)}")
    
    async def refresh_access_token(self) -> APIResponse:
        """Refresh Slack access token"""
        if not self.refresh_token:
            return APIResponse(success=False, error="No refresh token available")
        
        url = "https://slack.com/api/oauth.v2.access"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data)
                
                if response.status_code == 200:
                    token_data = response.json()
                    
                    if token_data.get('ok'):
                        self.access_token = token_data['access_token']
                        return APIResponse(success=True, data={
                            'access_token': token_data['access_token']
                        })
                    else:
                        return APIResponse(success=False, error=f"Slack token refresh error: {token_data.get('error')}")
                else:
                    return APIResponse(success=False, error=f"Slack token refresh failed: {response.text}", status_code=response.status_code)
        
        except Exception as e:
            return APIResponse(success=False, error=f"Slack token refresh error: {str(e)}")
    
    async def get_channels(self, types: str = 'public_channel,private_channel') -> APIResponse:
        """Get Slack channels"""
        params = {'types': types, 'exclude_archived': True, 'limit': 200}
        return await self._make_request('GET', 'conversations.list', params=params)
    
    async def get_messages(self, channel: str, limit: int = 100, oldest: str = None, latest: str = None) -> APIResponse:
        """Get channel messages"""
        params = {'channel': channel, 'limit': limit}
        if oldest:
            params['oldest'] = oldest
        if latest:
            params['latest'] = latest
        
        return await self._make_request('GET', 'conversations.history', params=params)
    
    async def send_message(self, channel: str, text: str, blocks: List[Dict] = None) -> APIResponse:
        """Send message to channel"""
        data = {'channel': channel, 'text': text}
        if blocks:
            data['blocks'] = blocks
        
        return await self._make_request('POST', 'chat.postMessage', data=data)
    
    async def get_user_info(self, user: str) -> APIResponse:
        """Get user information"""
        params = {'user': user}
        return await self._make_request('GET', 'users.info', params=params)
    
    async def get_team_info(self) -> APIResponse:
        """Get team information"""
        return await self._make_request('GET', 'team.info')

class RealAPIManager:
    """Manager for all real API connectors"""
    
    def __init__(self):
        self.connectors: Dict[str, BaseAPIConnector] = {}
        self.connection_status: Dict[str, APIServiceStatus] = {}
        self._initialize_connectors()
    
    def _initialize_connectors(self):
        """Initialize all API connectors"""
        
        # GitHub
        if os.getenv('GITHUB_CLIENT_ID') and os.getenv('GITHUB_CLIENT_SECRET'):
            self.connectors['github'] = GitHubAPIConnector(
                os.getenv('GITHUB_CLIENT_ID'),
                os.getenv('GITHUB_CLIENT_SECRET')
            )
            self.connection_status['github'] = APIServiceStatus.NOT_CONFIGURED
        
        # Notion
        if os.getenv('NOTION_CLIENT_ID') and os.getenv('NOTION_CLIENT_SECRET'):
            self.connectors['notion'] = NotionAPIConnector(
                os.getenv('NOTION_CLIENT_ID'),
                os.getenv('NOTION_CLIENT_SECRET')
            )
            self.connection_status['notion'] = APIServiceStatus.NOT_CONFIGURED
        
        # Slack
        if os.getenv('SLACK_CLIENT_ID') and os.getenv('SLACK_CLIENT_SECRET'):
            self.connectors['slack'] = SlackAPIConnector(
                os.getenv('SLACK_CLIENT_ID'),
                os.getenv('SLACK_CLIENT_SECRET')
            )
            self.connection_status['slack'] = APIServiceStatus.NOT_CONFIGURED
    
    async def authenticate_service(self, service: str, code: str, user_id: str = None) -> APIResponse:
        """Authenticate a specific service"""
        if service not in self.connectors:
            return APIResponse(success=False, error=f"Service {service} not configured")
        
        try:
            connector = self.connectors[service]
            result = await connector.authenticate(code)
            
            if result.success:
                self.connection_status[service] = APIServiceStatus.AUTHENTICATED
                
                # Store authentication token for user
                # In production, this would be stored securely in database
                token_storage_key = f"{service}_token_{user_id}"
                self._store_user_token(token_storage_key, connector.access_token)
                
                return APIResponse(
                    success=True,
                    data={
                        'service': service,
                        'authenticated': True,
                        'user_id': user_id,
                        'status': self.connection_status[service].value
                    }
                )
            else:
                return result
        
        except Exception as e:
            logger.error(f"Authentication failed for {service}: {e}")
            return APIResponse(success=False, error=str(e))
    
    async def get_service_status(self, service: str, user_id: str = None) -> APIResponse:
        """Get status of a specific service"""
        if service not in self.connectors:
            return APIResponse(success=False, error=f"Service {service} not configured")
        
        connector = self.connectors[service]
        status = self.connection_status.get(service, APIServiceStatus.NOT_CONFIGURED)
        
        # Check if authenticated
        if status == APIServiceStatus.AUTHENTICATED and not connector.access_token:
            # Try to get stored token
            token_storage_key = f"{service}_token_{user_id}"
            stored_token = self._get_user_token(token_storage_key)
            if stored_token:
                await connector.authenticate(user_token=stored_token)
            else:
                status = APIServiceStatus.NOT_CONFIGURED
        
        return APIResponse(
            success=True,
            data={
                'service': service,
                'status': status.value,
                'has_token': connector.access_token is not None,
                'rate_limit_remaining': connector.rate_limit_remaining,
                'rate_limit_reset': connector.rate_limit_reset.isoformat() if connector.rate_limit_reset else None
            }
        )
    
    async def test_service_connection(self, service: str) -> APIResponse:
        """Test connection to a service"""
        if service not in self.connectors:
            return APIResponse(success=False, error=f"Service {service} not configured")
        
        connector = self.connectors[service]
        
        try:
            if service == 'github':
                result = await connector.get_user_info()
            elif service == 'notion':
                result = await connector.search_pages()
            elif service == 'slack':
                result = await connector.get_team_info()
            else:
                return APIResponse(success=False, error=f"Test not implemented for {service}")
            
            if result.success:
                self.connection_status[service] = APIServiceStatus.CONNECTED
                return APIResponse(
                    success=True,
                    data={
                        'service': service,
                        'connected': True,
                        'test_result': 'successful'
                    }
                )
            else:
                self.connection_status[service] = APIServiceStatus.ERROR
                return APIResponse(
                    success=False,
                    error=f"Connection test failed: {result.error}",
                    data={'service': service, 'connected': False}
                )
        
        except Exception as e:
            self.connection_status[service] = APIServiceStatus.ERROR
            return APIResponse(
                success=False,
                error=f"Connection test error: {str(e)}",
                data={'service': service, 'connected': False}
            )
    
    def get_service_connector(self, service: str) -> Optional[BaseAPIConnector]:
        """Get connector for a service"""
        return self.connectors.get(service)
    
    def get_all_service_status(self) -> Dict[str, Dict]:
        """Get status of all services"""
        status = {}
        for service_name in self.connectors.keys():
            status[service_name] = {
                'configured': True,
                'status': self.connection_status.get(service_name, APIServiceStatus.NOT_CONFIGURED).value,
                'has_client_credentials': bool(
                    os.getenv(f'{service_name.upper()}_CLIENT_ID') and 
                    os.getenv(f'{service_name.upper()}_CLIENT_SECRET')
                )
            }
        return status
    
    def _store_user_token(self, key: str, token: str):
        """Store user token securely (in production, use database)"""
        # For demo, store in memory
        if not hasattr(self, 'user_tokens'):
            self.user_tokens = {}
        self.user_tokens[key] = {
            'token': token,
            'stored_at': datetime.now(timezone.utc).isoformat()
        }
        logger.info(f"Stored token for key: {key}")
    
    def _get_user_token(self, key: str) -> Optional[str]:
        """Get stored user token (in production, use database)"""
        if not hasattr(self, 'user_tokens'):
            return None
        token_data = self.user_tokens.get(key)
        return token_data['token'] if token_data else None

# Global real API manager instance
real_api_manager = RealAPIManager()

# Export for use in routes
__all__ = [
    'RealAPIManager',
    'real_api_manager',
    'GitHubAPIConnector',
    'NotionAPIConnector', 
    'SlackAPIConnector',
    'APIResponse',
    'APIServiceStatus'
]