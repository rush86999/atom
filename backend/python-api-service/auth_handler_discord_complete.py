"""
Discord OAuth Handler Implementation
Complete Discord OAuth 2.0 flow with comprehensive authentication
"""

import os
import logging
import sys
import httpx
import hashlib
import secrets
import json
import base64
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlencode

# Import encryption utilities
try:
    from atom_encryption import encrypt_data, decrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Encryption not available: {e}")
    ENCRYPTION_AVAILABLE = False

# Import database operations
try:
    from db_oauth_discord_complete import (
        save_discord_user,
        get_discord_user,
        save_discord_tokens,
        get_discord_tokens,
        delete_discord_tokens,
        is_discord_token_valid,
        refresh_discord_token_if_needed
    )
    DISCORD_DB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Discord database operations not available: {e}")
    DISCORD_DB_AVAILABLE = False

# Flask imports
try:
    from flask import (
        Blueprint,
        request,
        redirect,
        url_for,
        session,
        jsonify,
        current_app,
        render_template_string
    )
except ImportError:
    # Mock Flask classes for local testing
    class Blueprint:
        def __init__(self, name, **kwargs):
            self.name = name
        
        def route(self, path, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        def before_request(self, func):
            return func
        
        def errorhandler(self, code_or_exception):
            def decorator(func):
                return func
            return decorator
    
    class MockRequest:
        def __init__(self):
            self.json = {}
            self.args = {}
            self.form = {}
            self.method = "GET"
            self.headers = {}
        
        def get_json(self, force=False, silent=False, cache=True):
            return self.json
        
        def get_data(self, cache=True, as_text=False, parse_form_data=False):
            return b""
    
    class MockSession(dict):
        def __init__(self):
            super().__init__()
            self.permanent = False
        
        def __getitem__(self, key):
            return super().__getitem__(key)
        
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
        
        def pop(self, key, default=None):
            return super().pop(key, default)
        
        def clear(self):
            super().clear()
    
    class MockCurrentApp:
        def __init__(self):
            self.logger = logging.getLogger(__name__)
    
    request = MockRequest()
    session = MockSession()
    current_app = MockCurrentApp()

# Discord OAuth configuration
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:3000/integrations/discord/callback')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', '')
DISCORD_BOT_ID = os.getenv('DISCORD_BOT_ID', '')
DISCORD_BOT_NAME = os.getenv('DISCORD_BOT_NAME', 'ATOM Bot')
DISCORD_BOT_PERMISSIONS = os.getenv('DISCORD_BOT_PERMISSIONS', '8')  # Administrator
DISCORD_SCOPES = ['identify', 'email', 'guilds', 'bot', 'messages.read', 'channels.read', 'webhook.incoming']
DISCORD_AUTH_URL = 'https://discord.com/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/v10/oauth2/token'
DISCORD_USER_INFO_URL = 'https://discord.com/api/v10/users/@me'
DISCORD_BOT_INFO_URL = 'https://discord.com/api/v10/applications/@me'

# Configure logging
logger = logging.getLogger(__name__)

class DiscordOAuthManager:
    """Discord OAuth manager"""
    
    def __init__(self):
        self.client_id = DISCORD_CLIENT_ID
        self.client_secret = DISCORD_CLIENT_SECRET
        self.redirect_uri = DISCORD_REDIRECT_URI
        self.bot_token = DISCORD_BOT_TOKEN
        self.bot_id = DISCORD_BOT_ID
        self.bot_name = DISCORD_BOT_NAME
        self.scopes = DISCORD_SCOPES
        self.permissions = DISCORD_BOT_PERMISSIONS
    
    def generate_state(self, user_id: str) -> str:
        """Generate OAuth state parameter"""
        if DISCORD_DB_AVAILABLE:
            # In production, store state in database with expiration
            timestamp = str(int(datetime.utcnow().timestamp()))
            state_data = f"{user_id}:{timestamp}"
            state = base64.urlsafe_b64encode(state_data.encode()).decode()
            return state
        else:
            # In development, use simple state with user ID
            state = f"discord_{user_id}_{secrets.token_hex(8)}"
            return state
    
    def validate_state(self, state: str) -> Optional[str]:
        """Validate OAuth state parameter"""
        if DISCORD_DB_AVAILABLE:
            try:
                decoded = base64.urlsafe_b64decode(state.encode()).decode()
                user_id, timestamp = decoded.split(':')
                
                # Check if state is expired (10 minutes)
                state_time = datetime.utcfromtimestamp(int(timestamp))
                if datetime.utcnow() - state_time > timedelta(minutes=10):
                    return None
                
                return user_id
            except Exception as e:
                logger.error(f"Discord state validation error: {e}")
                return None
        else:
            # In development, extract user ID from state
            if state.startswith('discord_'):
                parts = state.split('_')
                if len(parts) >= 2:
                    return parts[1]
            return None
    
    def get_authorization_url(self, user_id: str, scopes: list = None) -> str:
        """Generate Discord authorization URL"""
        state = self.generate_state(user_id)
        auth_scopes = scopes or self.scopes
        
        # Include bot permissions if bot scope is included
        permissions = self.permissions if 'bot' in auth_scopes else None
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(auth_scopes),
            'state': state
        }
        
        if permissions:
            params['permissions'] = permissions
        
        # Add bot ID for installation
        if 'bot' in auth_scopes and self.bot_id:
            params['integration_type'] = '1'
            params['scope'] = 'bot applications.commands'
        
        url = f"{DISCORD_AUTH_URL}?{urlencode(params)}"
        logger.info(f"Discord OAuth URL generated for user {user_id}")
        return url
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.redirect_uri,
                'scope': ' '.join(self.scopes)
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
                response.raise_for_status()
                
                token_data = response.json()
                
                # Calculate expiration times
                expires_in = token_data.get('expires_in', 0)
                refresh_expires_in = token_data.get('refresh_expires_in', 2592000)  # 30 days default
                
                token_data['expires_at'] = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                token_data['refresh_token_expires_at'] = (datetime.utcnow() + timedelta(seconds=refresh_expires_in)).isoformat()
                
                logger.info(f"Discord tokens exchanged successfully, expires in {expires_in}s")
                return token_data
                
        except httpx.HTTPError as e:
            logger.error(f"Discord token exchange error: {e}")
            return {'error': f'HTTP error: {e}'}
        except Exception as e:
            logger.error(f"Discord token exchange unexpected error: {e}")
            return {'error': f'Unexpected error: {e}'}
    
    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access tokens"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'scope': ' '.join(self.scopes)
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
                response.raise_for_status()
                
                token_data = response.json()
                
                # Calculate new expiration times
                expires_in = token_data.get('expires_in', 0)
                refresh_expires_in = token_data.get('refresh_expires_in', 2592000)
                
                token_data['expires_at'] = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                token_data['refresh_token_expires_at'] = (datetime.utcnow() + timedelta(seconds=refresh_expires_in)).isoformat()
                
                logger.info(f"Discord tokens refreshed successfully, expires in {expires_in}s")
                return token_data
                
        except httpx.HTTPError as e:
            logger.error(f"Discord token refresh error: {e}")
            return {'error': f'HTTP error: {e}'}
        except Exception as e:
            logger.error(f"Discord token refresh unexpected error: {e}")
            return {'error': f'Unexpected error: {e}'}
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get Discord user information"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(DISCORD_USER_INFO_URL, headers=headers)
                response.raise_for_status()
                
                user_data = response.json()
                logger.info(f"Discord user info retrieved: {user_data.get('username', 'unknown')}")
                return user_data
                
        except httpx.HTTPError as e:
            logger.error(f"Discord user info error: {e}")
            return {'error': f'HTTP error: {e}'}
        except Exception as e:
            logger.error(f"Discord user info unexpected error: {e}")
            return {'error': f'Unexpected error: {e}'}
    
    async def get_bot_info(self) -> Dict[str, Any]:
        """Get Discord bot information"""
        try:
            headers = {
                'Authorization': f'Bot {self.bot_token}',
                'Accept': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(DISCORD_BOT_INFO_URL, headers=headers)
                response.raise_for_status()
                
                bot_data = response.json()
                logger.info(f"Discord bot info retrieved: {bot_data.get('name', 'unknown')}")
                return bot_data
                
        except httpx.HTTPError as e:
            logger.error(f"Discord bot info error: {e}")
            return {'error': f'HTTP error: {e}'}
        except Exception as e:
            logger.error(f"Discord bot info unexpected error: {e}")
            return {'error': f'Unexpected error: {e}'}
    
    async def validate_access_token(self, access_token: str) -> bool:
        """Validate access token"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{DISCORD_USER_INFO_URL}/verify", headers=headers)
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Discord token validation error: {e}")
            return False

# Create Discord OAuth manager instance
discord_auth_manager = DiscordOAuthManager()

# Create Flask blueprint
auth_discord_bp = Blueprint("auth_discord_bp", __name__)

@auth_discord_bp.before_request
def setup_request():
    """Setup request logging"""
    logger.info(f"Discord OAuth request: {request.method} {request.path}")

@auth_discord_bp.errorhandler(Exception)
def handle_exception(e):
    """Handle exceptions"""
    logger.error(f"Discord OAuth exception: {e}")
    return jsonify({
        "ok": False,
        "error": str(e),
        "error_type": "server_error"
    }), 500

# Discord OAuth endpoints
@auth_discord_bp.route("/api/auth/discord/authorize", methods=["POST"])
async def discord_authorize():
    """Start Discord OAuth flow"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        scopes = data.get('scopes', ['identify', 'guilds'])
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required",
                "error_type": "validation_error"
            }), 400
        
        if not discord_auth_manager.client_id:
            return jsonify({
                "ok": False,
                "error": "Discord client ID not configured",
                "error_type": "configuration_error"
            }), 500
        
        # Generate authorization URL
        auth_url = discord_auth_manager.get_authorization_url(user_id, scopes)
        
        return jsonify({
            "ok": True,
            "authorization_url": auth_url,
            "scopes": scopes,
            "message": "Discord authorization URL generated"
        })
        
    except Exception as e:
        logger.error(f"Discord authorize error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "error_type": "server_error"
        }), 500

@auth_discord_bp.route("/api/auth/discord/callback", methods=["GET", "POST"])
async def discord_callback():
    """Handle Discord OAuth callback"""
    try:
        # Handle both GET and POST requests
        if request.method == "GET":
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')
        else:
            data = request.get_json()
            code = data.get('code')
            state = data.get('state')
            error = data.get('error')
        
        if error:
            logger.error(f"Discord OAuth error: {error}")
            return jsonify({
                "ok": False,
                "error": f"Discord authorization failed: {error}",
                "error_type": "oauth_error"
            }), 400
        
        if not code:
            return jsonify({
                "ok": False,
                "error": "Authorization code is required",
                "error_type": "validation_error"
            }), 400
        
        if not state:
            return jsonify({
                "ok": False,
                "error": "State parameter is required",
                "error_type": "validation_error"
            }), 400
        
        # Validate state
        user_id = discord_auth_manager.validate_state(state)
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "Invalid or expired state parameter",
                "error_type": "validation_error"
            }), 400
        
        # Exchange code for tokens
        token_data = await discord_auth_manager.exchange_code_for_tokens(code)
        
        if 'error' in token_data:
            return jsonify({
                "ok": False,
                "error": token_data['error'],
                "error_type": "token_error"
            }), 400
        
        # Get user information
        user_data = await discord_auth_manager.get_user_info(token_data['access_token'])
        
        if 'error' in user_data:
            return jsonify({
                "ok": False,
                "error": user_data['error'],
                "error_type": "user_info_error"
            }), 400
        
        # Save user and tokens to database
        if DISCORD_DB_AVAILABLE:
            # Save user data
            await save_discord_user(None, user_data)
            
            # Save tokens
            await save_discord_tokens(None, user_id, token_data)
        
        # Get bot info if available
        bot_info = {}
        if discord_auth_manager.bot_token:
            bot_info = await discord_auth_manager.get_bot_info()
        
        logger.info(f"Discord OAuth successful for user {user_id}")
        
        return jsonify({
            "ok": True,
            "user": {
                "id": user_data.get('id'),
                "username": user_data.get('username'),
                "discriminator": user_data.get('discriminator'),
                "global_name": user_data.get('global_name'),
                "display_name": user_data.get('display_name'),
                "avatar_hash": user_data.get('avatar'),
                "bot": user_data.get('bot', False),
                "verified": user_data.get('verified', False),
                "email": user_data.get('email'),
                "locale": user_data.get('locale'),
                "premium_type": user_data.get('premium_type', 0)
            },
            "tokens": {
                "access_token": token_data.get('access_token'),
                "token_type": token_data.get('token_type', 'Bearer'),
                "scope": token_data.get('scope', ''),
                "expires_at": token_data.get('expires_at'),
                "refresh_token": token_data.get('refresh_token')
            },
            "bot": bot_info,
            "message": "Discord authorization successful"
        })
        
    except Exception as e:
        logger.error(f"Discord callback error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "error_type": "server_error"
        }), 500

@auth_discord_bp.route("/api/auth/discord/refresh", methods=["POST"])
async def discord_refresh():
    """Refresh Discord tokens"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        refresh_token = data.get('refresh_token')
        
        if not user_id and not refresh_token:
            return jsonify({
                "ok": False,
                "error": "User ID or refresh token is required",
                "error_type": "validation_error"
            }), 400
        
        # Get refresh token from request or database
        if not refresh_token and DISCORD_DB_AVAILABLE:
            token_data = await get_discord_tokens(None, user_id)
            if token_data:
                refresh_token = token_data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({
                "ok": False,
                "error": "Refresh token not available",
                "error_type": "token_error"
            }), 400
        
        # Refresh tokens
        token_data = await discord_auth_manager.refresh_tokens(refresh_token)
        
        if 'error' in token_data:
            return jsonify({
                "ok": False,
                "error": token_data['error'],
                "error_type": "refresh_error"
            }), 400
        
        # Save new tokens to database
        if DISCORD_DB_AVAILABLE and user_id:
            await save_discord_tokens(None, user_id, token_data)
        
        logger.info(f"Discord tokens refreshed for user {user_id}")
        
        return jsonify({
            "ok": True,
            "tokens": {
                "access_token": token_data.get('access_token'),
                "token_type": token_data.get('token_type', 'Bearer'),
                "scope": token_data.get('scope', ''),
                "expires_at": token_data.get('expires_at'),
                "refresh_token": token_data.get('refresh_token')
            },
            "message": "Discord tokens refreshed successfully"
        })
        
    except Exception as e:
        logger.error(f"Discord refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "error_type": "server_error"
        }), 500

@auth_discord_bp.route("/api/auth/discord/status", methods=["POST"])
async def discord_status():
    """Check Discord authentication status"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required",
                "error_type": "validation_error"
            }), 400
        
        # Check tokens in database
        if DISCORD_DB_AVAILABLE:
            tokens = await get_discord_tokens(None, user_id)
            if not tokens:
                return jsonify({
                    "ok": True,
                    "authenticated": False,
                    "message": "No Discord tokens found for user"
                })
            
            # Check if tokens are valid
            is_valid = await is_discord_token_valid(None, user_id)
            if not is_valid:
                # Try to refresh tokens
                new_tokens = await refresh_discord_token_if_needed(None, user_id, discord_auth_manager.refresh_tokens)
                if new_tokens:
                    return jsonify({
                        "ok": True,
                        "authenticated": True,
                        "token_valid": False,
                        "tokens_refreshed": True,
                        "expires_at": new_tokens.get('expires_at')
                    })
                else:
                    return jsonify({
                        "ok": True,
                        "authenticated": False,
                        "message": "Discord tokens expired and refresh failed"
                    })
            
            return jsonify({
                "ok": True,
                "authenticated": True,
                "token_valid": True,
                "expires_at": tokens.get('expires_at')
            })
        else:
            # Mock response for development
            return jsonify({
                "ok": True,
                "authenticated": True,
                "token_valid": True,
                "mock_mode": True
            })
        
    except Exception as e:
        logger.error(f"Discord status error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "error_type": "server_error"
        }), 500

@auth_discord_bp.route("/api/auth/discord/disconnect", methods=["POST"])
async def discord_disconnect():
    """Disconnect Discord integration"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required",
                "error_type": "validation_error"
            }), 400
        
        # Delete tokens from database
        if DISCORD_DB_AVAILABLE:
            success = await delete_discord_tokens(None, user_id)
            if success:
                logger.info(f"Discord integration disconnected for user {user_id}")
                return jsonify({
                    "ok": True,
                    "message": "Discord integration disconnected successfully"
                })
            else:
                return jsonify({
                    "ok": False,
                    "error": "Failed to disconnect Discord integration",
                    "error_type": "database_error"
                }), 500
        else:
            # Mock response for development
            logger.info(f"Discord integration disconnected for user {user_id} (mock)")
            return jsonify({
                "ok": True,
                "message": "Discord integration disconnected successfully",
                "mock_mode": True
            })
        
    except Exception as e:
        logger.error(f"Discord disconnect error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "error_type": "server_error"
        }), 500

@auth_discord_bp.route("/api/auth/discord/webhook/<webhook_id>", methods=["POST"])
async def discord_webhook(webhook_id: str):
    """Handle Discord webhooks"""
    try:
        data = request.get_json() if request.is_json else {}
        
        # Get webhook type
        webhook_type = data.get("type", "unknown")
        
        if webhook_type == "GUILD_CREATE":
            logger.info(f"Discord webhook: Guild created - {data.get('name')}")
        elif webhook_type == "GUILD_DELETE":
            logger.info(f"Discord webhook: Guild deleted - {data.get('id')}")
        elif webhook_type == "MESSAGE_CREATE":
            logger.info(f"Discord webhook: Message created - {data.get('content')}")
        elif webhook_type == "CHANNEL_CREATE":
            logger.info(f"Discord webhook: Channel created - {data.get('name')}")
        elif webhook_type == "CHANNEL_DELETE":
            logger.info(f"Discord webhook: Channel deleted - {data.get('id')}")
        
        return jsonify({
            "ok": True,
            "message": "Webhook processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "error_type": "server_error"
        }), 500

# Export components
__all__ = [
    'discord_auth_manager',
    'auth_discord_bp'
]