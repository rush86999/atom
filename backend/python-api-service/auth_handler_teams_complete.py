"""
Microsoft Teams OAuth Authentication Handler
Complete OAuth 2.0 implementation for Microsoft Teams integration
"""

import os
import sys
import json
import logging
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

# Mock Flask for local testing
try:
    from flask import (
        Blueprint,
        request,
        redirect,
        url_for,
        session,
        jsonify,
        current_app,
    )
except ImportError:
    # Mock Flask classes
    class Blueprint:
        def __init__(self, name, import_name):
            self.name = name
            self.import_name = import_name
            self.routes = {}

        def route(self, rule, **options):
            def decorator(f):
                self.routes[rule] = f
                return f

            return decorator

    class MockRequest:
        args = {"user_id": "mock_user", "state": "mock_state"}
        url = "http://localhost/callback?code=mock_code&state=mock_state"

    class MockSession(dict):
        pass

    class MockCurrentApp:
        config = {"DB_CONNECTION_POOL": None}

    request = MockRequest()
    session = MockSession()
    current_app = MockCurrentApp()

    def redirect(url):
        return f"Redirect to: {url}"

    def url_for(endpoint, **kwargs):
        return f"http://localhost:5000/{endpoint}"

    def jsonify(data):
        return json.dumps(data)

logger = logging.getLogger(__name__)

# Microsoft OAuth Configuration
TEAMS_CLIENT_ID = os.getenv('TEAMS_CLIENT_ID', 'mock_teams_client_id')
TEAMS_CLIENT_SECRET = os.getenv('TEAMS_CLIENT_SECRET', 'mock_teams_client_secret')
TEAMS_REDIRECT_URI = os.getenv('TEAMS_REDIRECT_URI', 'http://localhost:3000/integrations/teams/callback')
TEAMS_SCOPE = os.getenv('TEAMS_SCOPE', 'offline_access,Channel.ReadBasic.All,ChannelMessage.Send.All,Chat.ReadWrite,User.Read.All,Team.ReadBasic.All')
TEAMS_TENANT_ID = os.getenv('TEAMS_TENANT_ID', 'common')

# Microsoft OAuth URLs
TEAMS_OAUTH_AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TEAMS_OAUTH_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
TEAMS_API_BASE_URL = "https://graph.microsoft.com/v1.0"

# Security configuration
ATOM_OAUTH_ENCRYPTION_KEY = os.getenv('ATOM_OAUTH_ENCRYPTION_KEY', 'default-oauth-key-change-in-production')

# Import encryption utilities
try:
    from atom_encryption import decrypt_data, encrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logger.warning("atom_encryption not available, tokens will be stored in plaintext")

# Import database operations
try:
    from db_oauth_teams_complete import (
        save_tokens, get_tokens, delete_tokens, save_user_teams_tokens,
        get_user_teams_tokens, delete_user_teams_tokens, save_teams_user,
        get_teams_user, is_token_expired
    )
    TEAMS_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Teams database operations not available: {e}")
    TEAMS_DB_AVAILABLE = False

# Create Flask blueprint
auth_teams_bp = Blueprint("auth_teams_bp", __name__)

class TeamsAuthManager:
    """Microsoft Teams Authentication Manager"""
    
    def __init__(self):
        self.client_id = TEAMS_CLIENT_ID
        self.client_secret = TEAMS_CLIENT_SECRET
        self.redirect_uri = TEAMS_REDIRECT_URI
        self.token_url = TEAMS_OAUTH_TOKEN_URL
        self.authorize_url = TEAMS_OAUTH_AUTHORIZE_URL
        self.api_base_url = TEAMS_API_BASE_URL
        self.tenant_id = TEAMS_TENANT_ID
        self.scope = TEAMS_SCOPE
    
    def get_authorization_url(self, user_id: str, scopes: list = None, redirect_uri: str = None) -> str:
        """
        Generate Microsoft Teams OAuth authorization URL
        """
        try:
            # Use provided parameters or defaults
            scopes_list = scopes or self.scope.split(',')
            callback_uri = redirect_uri or self.redirect_uri
            
            # Generate state parameter for security
            state_data = {
                "user_id": user_id,
                "timestamp": int(datetime.utcnow().timestamp()),
                "random": os.urandom(8).hex(),
                "integration": "teams"
            }
            state_json = json.dumps(state_data)
            state_encoded = json.dumps(state_json)
            
            # Build authorization URL
            auth_url = (
                f"{self.authorize_url}?"
                f"response_type=code&"
                f"client_id={self.client_id}&"
                f"redirect_uri={callback_uri}&"
                f"scope={' '.join(scopes_list)}&"
                f"state={state_encoded}&"
                f"response_mode=query"
            )
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating Teams authorization URL: {e}")
            raise
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        """
        try:
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.token_url,
                    data=token_data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                )
                response.raise_for_status()
                
                token_response = response.json()
                
                if "error" in token_response:
                    raise Exception(f"Teams OAuth error: {token_response.get('error_description', token_response.get('error', 'Unknown error'))}")
                
                # Get user information from the access token
                user_info = await self.get_user_info_from_token(token_response.get('access_token'))
                
                return {
                    "ok": True,
                    "access_token": token_response.get("access_token"),
                    "token_type": token_response.get("token_type", "Bearer"),
                    "scope": token_response.get("scope"),
                    "refresh_token": token_response.get("refresh_token"),
                    "expires_in": token_response.get("expires_in", 3600),
                    "id_token": token_response.get("id_token"),
                    "user": user_info
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Error exchanging code for token: {e}")
            raise Exception(f"Token exchange failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in token exchange: {e}")
            raise
    
    async def get_user_info_from_token(self, access_token: str) -> Dict[str, Any]:
        """
        Get authenticated Microsoft Teams user information from access token
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Get user profile
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me",
                    headers=headers
                )
                response.raise_for_status()
                
                user_data = response.json()
                
                # Get user photo
                try:
                    photo_response = await client.get(
                        f"{self.api_base_url}/me/photo/$value",
                        headers=headers
                    )
                    if photo_response.status_code == 200:
                        user_data['photo_available'] = True
                except:
                    user_data['photo_available'] = False
                
                return {
                    "id": user_data.get("id"),
                    "displayName": user_data.get("displayName"),
                    "givenName": user_data.get("givenName"),
                    "surname": user_data.get("surname"),
                    "mail": user_data.get("mail"),
                    "userPrincipalName": user_data.get("userPrincipalName"),
                    "jobTitle": user_data.get("jobTitle"),
                    "officeLocation": user_data.get("officeLocation"),
                    "businessPhones": user_data.get("businessPhones", []),
                    "mobilePhone": user_data.get("mobilePhone"),
                    "photo_available": user_data.get("photo_available", False)
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Error getting Teams user info: {e}")
            raise Exception(f"Failed to get user info: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting Teams user info: {e}")
            raise
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh Microsoft Teams access token
        """
        try:
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.token_url,
                    data=token_data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                )
                response.raise_for_status()
                
                token_response = response.json()
                
                if "error" in token_response:
                    raise Exception(f"Teams token refresh error: {token_response.get('error_description', token_response.get('error', 'Unknown error'))}")
                
                # Calculate expiration time
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_response.get("expires_in", 3600))
                
                return {
                    "ok": True,
                    "access_token": token_response.get("access_token"),
                    "token_type": token_response.get("token_type", "Bearer"),
                    "scope": token_response.get("scope"),
                    "refresh_token": token_response.get("refresh_token", refresh_token),  # Use old refresh token if new one not provided
                    "expires_in": token_response.get("expires_in", 3600),
                    "expires_at": expires_at.isoformat(),
                    "id_token": token_response.get("id_token")
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Error refreshing Teams token: {e}")
            raise Exception(f"Token refresh failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error refreshing Teams token: {e}")
            raise

# Create Teams auth manager instance
teams_auth_manager = TeamsAuthManager()

@auth_teams_bp.route("/api/auth/teams/authorize", methods=["POST"])
async def authorize():
    """Start Microsoft Teams OAuth 2.0 flow"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        scopes = data.get("scopes", self.scope.split(','))
        redirect_uri = data.get("redirect_uri", TEAMS_REDIRECT_URI)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Generate state parameter
        state_data = {
            "user_id": user_id,
            "timestamp": int(datetime.utcnow().timestamp()),
            "random": os.urandom(8).hex(),
            "integration": "teams"
        }
        state_json = json.dumps(state_data)
        state_encoded = json.dumps(state_json)
        
        # Build authorization URL
        auth_url = (
            f"{TEAMS_OAUTH_AUTHORIZE_URL}?"
            f"response_type=code&"
            f"client_id={TEAMS_CLIENT_ID}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={' '.join(scopes)}&"
            f"state={state_encoded}&"
            f"response_mode=query"
        )
        
        logger.info(f"Teams OAuth authorization started for user {user_id}")
        
        return jsonify({
            "ok": True,
            "authorization_url": auth_url,
            "client_id": TEAMS_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "state": state_encoded
        })
        
    except Exception as e:
        logger.error(f"Teams OAuth authorize error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_teams_bp.route("/api/auth/teams/callback", methods=["POST"])
async def callback():
    """Handle Microsoft Teams OAuth 2.0 callback"""
    try:
        data = request.get_json()
        code = data.get("code")
        state = data.get("state")
        
        if not code:
            return jsonify({
                "ok": False,
                "error": "Authorization code is required"
            }), 400
        
        # Decode and verify state
        if state:
            try:
                state_data = json.loads(state)
                user_id = state_data.get("user_id")
                
                if not user_id:
                    return jsonify({
                        "ok": False,
                        "error": "Invalid state parameter"
                    }), 400
                
                # Verify state timestamp (prevent replay attacks)
                state_timestamp = state_data.get("timestamp", 0)
                current_timestamp = int(datetime.utcnow().timestamp())
                if current_timestamp - state_timestamp > 600:  # 10 minutes
                    return jsonify({
                        "ok": False,
                        "error": "State parameter expired"
                    }), 400
                    
            except Exception as e:
                logger.error(f"State decode error: {e}")
                return jsonify({
                    "ok": False,
                    "error": "Invalid state parameter"
                }), 400
        else:
            user_id = "default_user"  # Fallback for testing
        
        # Exchange authorization code for access token
        token_data = {
            "client_id": TEAMS_CLIENT_ID,
            "client_secret": TEAMS_CLIENT_SECRET,
            "code": code,
            "redirect_uri": TEAMS_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(TEAMS_OAUTH_TOKEN_URL, data=token_data,
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
            response.raise_for_status()
            
            token_response = response.json()
            
            if "error" in token_response:
                return jsonify({
                    "ok": False,
                    "error": token_response.get("error_description", token_response.get("error", "Unknown error"))
                }), 400
            
            # Get additional user information
            access_token = token_response.get("access_token")
            user_info = await teams_auth_manager.get_user_info_from_token(access_token)
            
            # Calculate expiration time
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_response.get("expires_in", 3600))
            
            # Encrypt tokens
            if ENCRYPTION_AVAILABLE:
                access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
                refresh_token = encrypt_data(token_response.get("refresh_token", ''), ATOM_OAUTH_ENCRYPTION_KEY)
            else:
                refresh_token = token_response.get("refresh_token", "")
            
            # Save tokens and user info to database
            if TEAMS_DB_AVAILABLE:
                await save_user_teams_tokens(
                    None,  # db_conn_pool - will be passed in production
                    user_id,
                    {
                        'access_token': access_token,
                        'token_type': token_response.get("token_type", "Bearer"),
                        'scope': token_response.get("scope"),
                        'refresh_token': refresh_token,
                        'expires_at': expires_at.isoformat(),
                        'id_token': token_response.get("id_token"),
                        'user_info': user_info
                    }
                )
            
            logger.info(f"Teams OAuth completed successfully for user {user_id}")
            
            return jsonify({
                "ok": True,
                "message": "Teams authentication successful",
                "user": {
                    "id": user_info.get("id"),
                    "displayName": user_info.get("displayName"),
                    "mail": user_info.get("mail"),
                    "jobTitle": user_info.get("jobTitle"),
                    "photo_available": user_info.get("photo_available", False)
                },
                "token_info": {
                    "scope": token_response.get("scope"),
                    "token_type": token_response.get("token_type"),
                    "expires_at": expires_at.isoformat()
                }
            })
        
    except Exception as e:
        logger.error(f"Teams OAuth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_teams_bp.route("/api/auth/teams/refresh", methods=["POST"])
async def refresh():
    """Refresh Microsoft Teams OAuth tokens"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Get refresh token from database
        if not TEAMS_DB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Database not available"
            }), 503
        
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        if not tokens:
            return jsonify({
                "ok": False,
                "error": "No tokens found for user"
            }), 404
        
        refresh_token = tokens.get('refresh_token')
        if ENCRYPTION_AVAILABLE and isinstance(refresh_token, bytes):
            refresh_token = decrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        if not refresh_token:
            return jsonify({
                "ok": False,
                "error": "Refresh token not available"
            }), 400
        
        # Refresh the token
        refreshed_tokens = await teams_auth_manager.refresh_token(refresh_token)
        
        if not refreshed_tokens.get('ok'):
            return jsonify({
                "ok": False,
                "error": refreshed_tokens.get("error", "Token refresh failed")
            }), 400
        
        # Save refreshed tokens
        if ENCRYPTION_AVAILABLE:
            access_token = encrypt_data(refreshed_tokens.get('access_token'), ATOM_OAUTH_ENCRYPTION_KEY)
            new_refresh_token = encrypt_data(refreshed_tokens.get('refresh_token', refresh_token), ATOM_OAUTH_ENCRYPTION_KEY)
        else:
            access_token = refreshed_tokens.get('access_token')
            new_refresh_token = refreshed_tokens.get('refresh_token', refresh_token)
        
        await save_tokens(None, user_id, {  # db_conn_pool - will be passed in production
            'access_token': access_token,
            'token_type': refreshed_tokens.get('token_type'),
            'scope': refreshed_tokens.get('scope'),
            'refresh_token': new_refresh_token,
            'expires_at': refreshed_tokens.get('expires_at'),
            'id_token': refreshed_tokens.get('id_token')
        })
        
        logger.info(f"Teams token refreshed successfully for user {user_id}")
        
        return jsonify({
            "ok": True,
            "message": "Tokens refreshed successfully",
            "token_info": {
                "scope": refreshed_tokens.get("scope"),
                "token_type": refreshed_tokens.get("token_type"),
                "expires_at": refreshed_tokens.get("expires_at")
            }
        })
        
    except Exception as e:
        logger.error(f"Teams OAuth refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_teams_bp.route("/api/auth/teams/disconnect", methods=["POST"])
async def disconnect():
    """Disconnect Microsoft Teams integration"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Delete tokens from database
        if TEAMS_DB_AVAILABLE:
            await delete_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        logger.info(f"Teams disconnected for user {user_id}")
        
        return jsonify({
            "ok": True,
            "message": "Teams integration disconnected successfully"
        })
        
    except Exception as e:
        logger.error(f"Teams OAuth disconnect error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_teams_bp.route("/api/auth/teams/webhook/<webhook_id>", methods=["POST"])
async def webhook_handler(webhook_id):
    """Handle Microsoft Teams webhooks"""
    try:
        data = request.get_json()
        logger.info(f"Teams webhook {webhook_id} received: {data}")
        
        # Handle different event types
        event_type = data.get("value", [{}])[0].get("changeType") if data.get("value") else "unknown"
        
        if event_type == "created":
            await handle_message_created(data, webhook_id)
        elif event_type == "updated":
            await handle_message_updated(data, webhook_id)
        elif event_type == "deleted":
            await handle_message_deleted(data, webhook_id)
        else:
            logger.info(f"Unknown Teams event type: {event_type}")
        
        return jsonify({
            "ok": True,
            "message": "Webhook processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Teams webhook error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_message_created(event_data: Dict[str, Any], webhook_id: str):
    """Handle Teams message created event"""
    try:
        messages = event_data.get("value", [])
        for message_data in messages:
            if message_data.get("changeType") == "created":
                logger.info(f"Teams message created: {message_data.get('resource')}")
        
    except Exception as e:
        logger.error(f"Error handling Teams message created event: {e}")

async def handle_message_updated(event_data: Dict[str, Any], webhook_id: str):
    """Handle Teams message updated event"""
    try:
        messages = event_data.get("value", [])
        for message_data in messages:
            if message_data.get("changeType") == "updated":
                logger.info(f"Teams message updated: {message_data.get('resource')}")
        
    except Exception as e:
        logger.error(f"Error handling Teams message updated event: {e}")

async def handle_message_deleted(event_data: Dict[str, Any], webhook_id: str):
    """Handle Teams message deleted event"""
    try:
        messages = event_data.get("value", [])
        for message_data in messages:
            if message_data.get("changeType") == "deleted":
                logger.info(f"Teams message deleted: {message_data.get('resource')}")
        
    except Exception as e:
        logger.error(f"Error handling Teams message deleted event: {e}")

@auth_teams_bp.route("/api/auth/teams/status", methods=["GET"])
async def status():
    """Get Teams OAuth status"""
    try:
        return jsonify({
            "ok": True,
            "status": "available",
            "client_id": TEAMS_CLIENT_ID,
            "redirect_uri": TEAMS_REDIRECT_URI,
            "default_scopes": TEAMS_SCOPE.split(','),
            "tenant_id": TEAMS_TENANT_ID,
            "database_available": TEAMS_DB_AVAILABLE,
            "encryption_available": ENCRYPTION_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Teams OAuth status error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility functions
async def get_validated_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get and validate Teams tokens for user
    """
    try:
        if not TEAMS_DB_AVAILABLE:
            return None
        
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        if not tokens:
            return None
        
        # Check if token is expired
        expires_at = tokens.get('expires_at')
        if expires_at and is_token_expired(expires_at):
            logger.warning(f"Teams tokens expired for user {user_id}")
            return None
        
        return tokens
        
    except Exception as e:
        logger.error(f"Error validating Teams tokens for user {user_id}: {e}")
        return None

async def ensure_valid_tokens(user_id: str) -> Optional[str]:
    """
    Ensure user has valid Teams tokens, return access token
    """
    try:
        tokens = await get_validated_tokens(user_id)
        
        if not tokens:
            return None
        
        # Decrypt access token if needed
        access_token = tokens.get('access_token')
        if ENCRYPTION_AVAILABLE and isinstance(access_token, bytes):
            access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        return access_token
        
    except Exception as e:
        logger.error(f"Error ensuring valid Teams tokens for user {user_id}: {e}")
        return None

# Export for use in other modules
__all__ = [
    'teams_auth_manager',
    'auth_teams_bp',
    'get_validated_tokens',
    'ensure_valid_tokens'
]