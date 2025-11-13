#!/usr/bin/env python3
"""
🔐 Unified OAuth Middleware System
Provides standardized authentication across all ATOM integrations
"""

import os
import json
import logging
import secrets
import hashlib
import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, redirect, session, url_for
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class OAuthConfig:
    """OAuth configuration for an integration"""
    client_id: str
    client_secret: str
    redirect_uri: str
    authorization_url: str
    token_url: str
    scope: str
    state_timeout: int = 600  # 10 minutes

@dataclass
class OAuthToken:
    """OAuth token information"""
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_at: Optional[datetime]
    scope: str
    user_id: str
    integration: str

class OAuthProvider(ABC):
    """Abstract base class for OAuth providers"""
    
    def __init__(self, name: str, config: OAuthConfig):
        self.name = name
        self.config = config
    
    @abstractmethod
    def get_authorization_url(self, user_id: str, state: str) -> str:
        """Generate OAuth authorization URL"""
        pass
    
    @abstractmethod
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        pass
    
    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        pass
    
    @abstractmethod
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information using access token"""
        pass

class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth provider"""
    
    def get_authorization_url(self, user_id: str, state: str) -> str:
        params = {
            'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_uri,
            'scope': self.config.scope,
            'state': state,
            'allow_signup': 'true'
        }
        return f"{self.config.authorization_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        import httpx
        
        data = {
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'code': code,
            'redirect_uri': self.config.redirect_uri
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(self.config.token_url, data=data)
                response.raise_for_status()
                token_data = response.json()
                
                # Get user info
                user_info = self.get_user_info(token_data['access_token'])
                
                return {
                    'success': True,
                    'token': OAuthToken(
                        access_token=token_data['access_token'],
                        refresh_token=token_data.get('refresh_token'),
                        token_type=token_data['token_type'],
                        expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_data.get('expires_in', 3600)),
                        scope=token_data['scope'],
                        user_id=user_info.get('id'),
                        integration='github'
                    ),
                    'user_info': user_info
                }
        except Exception as e:
            logger.error(f"GitHub OAuth token exchange failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        import httpx
        
        data = {
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(self.config.token_url, data=data)
                response.raise_for_status()
                token_data = response.json()
                
                return {
                    'success': True,
                    'access_token': token_data['access_token'],
                    'expires_in': token_data.get('expires_in', 3600),
                    'token_type': token_data.get('token_type', 'bearer')
                }
        except Exception as e:
            logger.error(f"GitHub OAuth token refresh failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        import httpx
        
        headers = {'Authorization': f'token {access_token}'}
        
        try:
            with httpx.Client() as client:
                response = client.get('https://api.github.com/user', headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"GitHub user info fetch failed: {e}")
            return {}

class NotionOAuthProvider(OAuthProvider):
    """Notion OAuth provider"""
    
    def get_authorization_url(self, user_id: str, state: str) -> str:
        return f"{self.config.authorization_url}?owner=user&response_type=code&client_id={self.config.client_id}&redirect_uri={self.config.redirect_uri}&state={state}"
    
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        import httpx
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.config.redirect_uri,
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(self.config.token_url, json=data)
                response.raise_for_status()
                token_data = response.json()
                
                # Get user info using workspace info
                user_info = self.get_user_info(token_data['access_token'])
                
                return {
                    'success': True,
                    'token': OAuthToken(
                        access_token=token_data['access_token'],
                        refresh_token=token_data.get('duplicated_template_id'),  # Notion uses this for refresh
                        token_type='bearer',
                        expires_at=datetime.now(timezone.utc) + timedelta(hours=token_data.get('expires_in', 8) * 3600),
                        scope=token_data.get('workspace_name', ''),
                        user_id=user_info.get('user_id'),
                        integration='notion'
                    ),
                    'user_info': user_info
                }
        except Exception as e:
            logger.error(f"Notion OAuth token exchange failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        # Notion doesn't support refresh tokens in the same way
        return {'success': False, 'error': 'Notion requires re-authorization'}
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        import httpx
        
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            with httpx.Client() as client:
                # Get user info from Notion API
                response = client.get('https://api.notion.com/v1/users/me', headers=headers)
                response.raise_for_status()
                user_data = response.json()
                
                return {
                    'user_id': user_data.get('id'),
                    'name': user_data.get('name'),
                    'email': user_data.get('person', {}).get('email')
                }
        except Exception as e:
            logger.error(f"Notion user info fetch failed: {e}")
            return {}

class SlackOAuthProvider(OAuthProvider):
    """Slack OAuth provider"""
    
    def get_authorization_url(self, user_id: str, state: str) -> str:
        params = {
            'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_uri,
            'scope': self.config.scope,
            'state': state,
            'user': user_id
        }
        return f"{self.config.authorization_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        import httpx
        
        data = {
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'code': code,
            'redirect_uri': self.config.redirect_uri
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(self.config.token_url, data=data)
                response.raise_for_status()
                token_data = response.json()
                
                # Get user info
                user_info = self.get_user_info(token_data['access_token'])
                
                return {
                    'success': True,
                    'token': OAuthToken(
                        access_token=token_data['access_token'],
                        refresh_token=token_data.get('refresh_token'),
                        token_type=token_data['token_type'],
                        expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_data.get('expires_in', 43200)),
                        scope=token_data['scope'],
                        user_id=user_info.get('user_id'),
                        integration='slack'
                    ),
                    'user_info': user_info
                }
        except Exception as e:
            logger.error(f"Slack OAuth token exchange failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        import httpx
        
        data = {
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(self.config.token_url, data=data)
                response.raise_for_status()
                token_data = response.json()
                
                return {
                    'success': True,
                    'access_token': token_data['access_token'],
                    'expires_in': token_data.get('expires_in', 43200),
                    'token_type': token_data.get('token_type', 'bearer')
                }
        except Exception as e:
            logger.error(f"Slack OAuth token refresh failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        import httpx
        
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            with httpx.Client() as client:
                response = client.get('https://slack.com/api/auth.test', headers=headers)
                response.raise_for_status()
                user_data = response.json()
                
                if user_data.get('ok'):
                    return {
                        'user_id': user_data.get('user_id'),
                        'team_id': user_data.get('team_id'),
                        'user': user_data.get('user'),
                        'team': user_data.get('team')
                    }
                return {}
        except Exception as e:
            logger.error(f"Slack user info fetch failed: {e}")
            return {}

class UnifiedOAuthManager:
    """Unified OAuth management system"""
    
    def __init__(self, app: Flask):
        self.app = app
        self.providers: Dict[str, OAuthProvider] = {}
        self.states: Dict[str, Dict[str, Any]] = {}
        
        # Configure app secret for state signing
        if not app.secret_key:
            app.secret_key = os.urandom(32)
    
    def register_provider(self, name: str, provider: OAuthProvider):
        """Register an OAuth provider"""
        self.providers[name] = provider
        logger.info(f"✅ Registered OAuth provider: {name}")
    
    def create_oauth_state(self, user_id: str, integration: str, additional_data: Optional[Dict] = None) -> str:
        """Create a secure OAuth state"""
        state = secrets.token_urlsafe(32)
        
        state_data = {
            'user_id': user_id,
            'integration': integration,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'additional_data': additional_data or {}
        }
        
        # Hash the state for security
        state_hash = hashlib.sha256((state + json.dumps(state_data, sort_keys=True)).encode()).hexdigest()
        
        # Store state data with timeout
        self.states[state] = {
            'data': state_data,
            'hash': state_hash,
            'expires_at': datetime.now(timezone.utc) + timedelta(minutes=10)
        }
        
        return state
    
    def validate_oauth_state(self, state: str, received_hash: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        """Validate OAuth state"""
        if state not in self.states:
            return False, None
        
        state_info = self.states[state]
        
        # Check expiration
        if datetime.now(timezone.utc) > state_info['expires_at']:
            del self.states[state]
            return False, None
        
        # Validate hash if provided
        if received_hash and state_info['hash'] != received_hash:
            del self.states[state]
            return False, None
        
        # Return state data and cleanup
        state_data = state_info['data'].copy()
        del self.states[state]
        
        return True, state_data
    
    def init_oauth_routes(self):
        """Initialize OAuth routes for all providers"""
        
        @self.app.route('/api/oauth/<provider>/authorize', methods=['GET'])
        def oauth_authorize(provider):
            """Initiate OAuth flow for a provider"""
            if provider not in self.providers:
                return jsonify({'error': f'Provider {provider} not supported'}), 400
            
            user_id = request.args.get('user_id', 'unknown')
            redirect_uri = request.args.get('redirect_uri', request.referrer)
            
            # Create secure state
            state = self.create_oauth_state(user_id, provider, {'redirect_uri': redirect_uri})
            
            # Get authorization URL
            oauth_provider = self.providers[provider]
            auth_url = oauth_provider.get_authorization_url(user_id, state)
            
            return jsonify({
                'success': True,
                'authorization_url': auth_url,
                'state': state,
                'provider': provider
            })
        
        @self.app.route('/api/oauth/<provider>/callback', methods=['POST'])
        def oauth_callback(provider):
            """Handle OAuth callback for a provider"""
            if provider not in self.providers:
                return jsonify({'error': f'Provider {provider} not supported'}), 400
            
            data = request.get_json()
            code = data.get('code')
            state = data.get('state')
            
            if not code or not state:
                return jsonify({'error': 'Authorization code and state required'}), 400
            
            # Validate state
            is_valid, state_data = self.validate_oauth_state(state)
            if not is_valid:
                return jsonify({'error': 'Invalid or expired state'}), 400
            
            # Exchange code for token
            oauth_provider = self.providers[provider]
            result = oauth_provider.exchange_code_for_token(code, state)
            
            if not result.get('success'):
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Unknown OAuth error'),
                    'provider': provider
                }), 400
            
            # Store token securely
            token = result.get('token')
            if token:
                self.store_token(provider, token, state_data.get('user_id'))
            
            return jsonify({
                'success': True,
                'provider': provider,
                'user_info': result.get('user_info'),
                'token_info': {
                    'token_type': token.token_type,
                    'scope': token.scope,
                    'expires_at': token.expires_at.isoformat() if token.expires_at else None
                },
                'redirect_to': state_data.get('additional_data', {}).get('redirect_uri')
            })
        
        @self.app.route('/api/oauth/<provider>/refresh', methods=['POST'])
        def oauth_refresh(provider):
            """Refresh OAuth token for a provider"""
            if provider not in self.providers:
                return jsonify({'error': f'Provider {provider} not supported'}), 400
            
            data = request.get_json()
            refresh_token = data.get('refresh_token')
            
            if not refresh_token:
                return jsonify({'error': 'Refresh token required'}), 400
            
            # Refresh token
            oauth_provider = self.providers[provider]
            result = oauth_provider.refresh_access_token(refresh_token)
            
            return jsonify(result)
        
        @self.app.route('/api/oauth/<provider>/status', methods=['GET'])
        def oauth_status(provider):
            """Get OAuth status for a provider"""
            if provider not in self.providers:
                return jsonify({'error': f'Provider {provider} not supported'}), 400
            
            user_id = request.args.get('user_id', 'unknown')
            token = self.get_stored_token(provider, user_id)
            
            if not token:
                return jsonify({
                    'connected': False,
                    'provider': provider,
                    'user_id': user_id
                })
            
            # Check if token is expired
            is_expired = token.expires_at and datetime.now(timezone.utc) > token.expires_at
            
            return jsonify({
                'connected': True,
                'provider': provider,
                'user_id': user_id,
                'token_info': {
                    'token_type': token.token_type,
                    'scope': token.scope,
                    'expires_at': token.expires_at.isoformat() if token.expires_at else None,
                    'is_expired': is_expired
                }
            })
        
        logger.info("✅ Unified OAuth routes initialized")
    
    def store_token(self, provider: str, token: OAuthToken, user_id: str):
        """Store OAuth token securely"""
        # In production, this would store in encrypted database
        # For now, store in memory (development only)
        storage_key = f"oauth_token_{provider}_{user_id}"
        
        token_data = {
            'access_token': token.access_token,
            'refresh_token': token.refresh_token,
            'token_type': token.token_type,
            'expires_at': token.expires_at.isoformat() if token.expires_at else None,
            'scope': token.scope,
            'user_id': token.user_id,
            'integration': token.integration,
            'stored_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Store in app context (in production, use database)
        if not hasattr(self.app, 'oauth_tokens'):
            self.app.oauth_tokens = {}
        
        self.app.oauth_tokens[storage_key] = token_data
        logger.info(f"✅ Stored OAuth token for {provider} user {user_id}")
    
    def get_stored_token(self, provider: str, user_id: str) -> Optional[OAuthToken]:
        """Get stored OAuth token"""
        storage_key = f"oauth_token_{provider}_{user_id}"
        
        if not hasattr(self.app, 'oauth_tokens'):
            return None
        
        token_data = self.app.oauth_tokens.get(storage_key)
        if not token_data:
            return None
        
        return OAuthToken(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            token_type=token_data['token_type'],
            expires_at=datetime.fromisoformat(token_data['expires_at']) if token_data.get('expires_at') else None,
            scope=token_data['scope'],
            user_id=token_data['user_id'],
            integration=token_data['integration']
        )

def create_unified_oauth_manager(app: Flask) -> UnifiedOAuthManager:
    """Create and configure unified OAuth manager"""
    
    manager = UnifiedOAuthManager(app)
    
    # Register OAuth providers with configuration from environment variables
    
    # GitHub
    github_config = OAuthConfig(
        client_id=os.getenv('GITHUB_CLIENT_ID', ''),
        client_secret=os.getenv('GITHUB_CLIENT_SECRET', ''),
        redirect_uri=os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:9000/api/oauth/github/callback'),
        authorization_url='https://github.com/login/oauth/authorize',
        token_url='https://github.com/login/oauth/access_token',
        scope='user repo read:org'
    )
    manager.register_provider('github', GitHubOAuthProvider('github', github_config))
    
    # Notion
    notion_config = OAuthConfig(
        client_id=os.getenv('NOTION_CLIENT_ID', ''),
        client_secret=os.getenv('NOTION_CLIENT_SECRET', ''),
        redirect_uri=os.getenv('NOTION_REDIRECT_URI', 'http://localhost:9000/api/oauth/notion/callback'),
        authorization_url='https://api.notion.com/v1/oauth/authorize',
        token_url='https://api.notion.com/v1/oauth/token',
        scope='users.read:email'
    )
    manager.register_provider('notion', NotionOAuthProvider('notion', notion_config))
    
    # Slack
    slack_config = OAuthConfig(
        client_id=os.getenv('SLACK_CLIENT_ID', ''),
        client_secret=os.getenv('SLACK_CLIENT_SECRET', ''),
        redirect_uri=os.getenv('SLACK_REDIRECT_URI', 'http://localhost:9000/api/oauth/slack/callback'),
        authorization_url='https://slack.com/oauth/v2/authorize',
        token_url='https://slack.com/api/oauth.v2.access',
        scope='channels:read users:read chat:write'
    )
    manager.register_provider('slack', SlackOAuthProvider('slack', slack_config))
    
    # Initialize OAuth routes
    manager.init_oauth_routes()
    
    return manager

# Export for use in main app
__all__ = [
    'UnifiedOAuthManager',
    'create_unified_oauth_manager',
    'OAuthProvider',
    'GitHubOAuthProvider',
    'NotionOAuthProvider',
    'SlackOAuthProvider'
]