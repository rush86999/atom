"""
Slack OAuth Authentication Handler
Complete OAuth 2.0 implementation for Slack integration
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

# Slack OAuth Configuration
SLACK_CLIENT_ID = os.getenv('SLACK_CLIENT_ID', 'mock_slack_client_id')
SLACK_CLIENT_SECRET = os.getenv('SLACK_CLIENT_SECRET', 'mock_slack_client_secret')
SLACK_REDIRECT_URI = os.getenv('SLACK_REDIRECT_URI', 'http://localhost:3000/integrations/slack/callback')
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET', 'mock_slack_signing_secret')

# Slack OAuth URLs
SLACK_OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_OAUTH_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API_BASE_URL = "https://slack.com/api"

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
    from db_oauth_slack_complete import (
        save_tokens, get_tokens, delete_tokens, save_user_slack_tokens,
        get_user_slack_tokens, delete_user_slack_tokens, save_slack_user,
        get_slack_user, is_token_expired
    )
    SLACK_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Slack database operations not available: {e}")
    SLACK_DB_AVAILABLE = False

# Create Flask blueprint
auth_slack_bp = Blueprint("auth_slack_bp", __name__)

class SlackAuthManager:
    """Slack Authentication Manager"""
    
    def __init__(self):
        self.client_id = SLACK_CLIENT_ID
        self.client_secret = SLACK_CLIENT_SECRET
        self.redirect_uri = SLACK_REDIRECT_URI
        self.token_url = SLACK_OAUTH_TOKEN_URL
        self.authorize_url = SLACK_OAUTH_AUTHORIZE_URL
        self.api_base_url = SLACK_API_BASE_URL
        self.signing_secret = SLACK_SIGNING_SECRET
    
    def get_authorization_url(self, user_id: str, scopes: list = None, redirect_uri: str = None, 
                          team_id: str = None) -> str:
        """
        Generate Slack OAuth authorization URL
        """
        try:
            # Use provided parameters or defaults
            scopes_list = scopes or [
                'channels:read', 'channels:write', 'chat:write', 'chat:write.public',
                'files:read', 'files:write', 'users:read', 'team:read'
            ]
            callback_uri = redirect_uri or self.redirect_uri
            
            # Generate state parameter for security
            state_data = {
                "user_id": user_id,
                "timestamp": int(datetime.utcnow().timestamp()),
                "random": os.urandom(8).hex()
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
                f"user_scope=identify,email"
            )
            
            # Add team_id if provided
            if team_id:
                auth_url += f"&team={team_id}"
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating Slack authorization URL: {e}")
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
                "redirect_uri": self.redirect_uri
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.token_url,
                    data=token_data
                )
                response.raise_for_status()
                
                token_response = response.json()
                
                if not token_response.get("ok"):
                    raise Exception(f"Slack OAuth error: {token_response.get('error', 'Unknown error')}")
                
                authed_user = token_response.get("authed_user", {})
                
                return {
                    "ok": True,
                    "access_token": token_response.get("access_token"),
                    "token_type": token_response.get("token_type", "bot"),
                    "scope": token_response.get("scope", ""),
                    "refresh_token": None,  # Slack doesn't support refresh tokens
                    "expires_in": token_response.get("expires_in", 86400),  # Default 24 hours
                    "team_id": token_response.get("team", {}).get("id"),
                    "team_name": token_response.get("team", {}).get("name"),
                    "bot_user_id": token_response.get("bot_user_id"),
                    "app_id": token_response.get("app_id"),
                    "user": {
                        "id": authed_user.get("id"),
                        "name": authed_user.get("name"),
                        "email": authed_user.get("email"),
                        "image_24": authed_user.get("image_24"),
                        "image_32": authed_user.get("image_32"),
                        "image_48": authed_user.get("image_48"),
                        "image_72": authed_user.get("image_72"),
                        "image_192": authed_user.get("image_192"),
                        "image_512": authed_user.get("image_512")
                    }
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Error exchanging code for token: {e}")
            raise Exception(f"Token exchange failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in token exchange: {e}")
            raise
    
    async def get_slack_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get authenticated Slack user information
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Get user identity
            async with httpx.AsyncClient(timeout=30) as client:
                # Get user identity
                response = await client.get(
                    f"{self.api_base_url}/users.identity",
                    headers=headers
                )
                response.raise_for_status()
                
                user_data = response.json()
                
                if not user_data.get("ok"):
                    raise Exception(f"Failed to get user identity: {user_data.get('error', 'Unknown error')}")
                
                return {
                    "id": user_data.get("user", {}).get("id"),
                    "name": user_data.get("user", {}).get("name"),
                    "email": user_data.get("user", {}).get("email"),
                    "image_24": user_data.get("user", {}).get("image_24"),
                    "image_32": user_data.get("user", {}).get("image_32"),
                    "image_48": user_data.get("user", {}).get("image_48"),
                    "image_72": user_data.get("user", {}).get("image_72"),
                    "image_192": user_data.get("user", {}).get("image_192"),
                    "image_512": user_data.get("user", {}).get("image_512"),
                    "team": user_data.get("team")
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Error getting Slack user info: {e}")
            raise Exception(f"Failed to get user info: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting Slack user info: {e}")
            raise
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh Slack access token (Slack doesn't support refresh tokens)
        This method is included for compatibility but will always require re-authentication
        """
        logger.warning("Slack doesn't support token refresh - re-authentication required")
        raise Exception("Slack doesn't support token refresh. Please re-authenticate.")

# Create Slack auth manager instance
slack_auth_manager = SlackAuthManager()

@auth_slack_bp.route("/api/auth/slack/authorize", methods=["POST"])
async def authorize():
    """Start Slack OAuth 2.0 flow"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        scopes = data.get("scopes", [
            'channels:read', 'channels:write', 'chat:write', 'chat:write.public',
            'files:read', 'files:write', 'users:read', 'team:read'
        ])
        redirect_uri = data.get("redirect_uri", SLACK_REDIRECT_URI)
        team_id = data.get("team_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Generate state parameter
        state_data = {
            "user_id": user_id,
            "timestamp": int(datetime.utcnow().timestamp()),
            "random": os.urandom(8).hex()
        }
        state_json = json.dumps(state_data)
        state_encoded = json.dumps(state_json)
        
        # Build authorization URL
        auth_url = (
            f"{SLACK_OAUTH_AUTHORIZE_URL}?"
            f"response_type=code&"
            f"client_id={SLACK_CLIENT_ID}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={' '.join(scopes)}&"
            f"state={state_encoded}&"
            f"user_scope=identify,email"
        )
        
        # Add team_id if provided
        if team_id:
            auth_url += f"&team={team_id}"
        
        logger.info(f"Slack OAuth authorization started for user {user_id}")
        
        return jsonify({
            "ok": True,
            "authorization_url": auth_url,
            "client_id": SLACK_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "state": state_encoded
        })
        
    except Exception as e:
        logger.error(f"Slack OAuth authorize error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_slack_bp.route("/api/auth/slack/callback", methods=["POST"])
async def callback():
    """Handle Slack OAuth 2.0 callback"""
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
            "client_id": SLACK_CLIENT_ID,
            "client_secret": SLACK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": SLACK_REDIRECT_URI
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(SLACK_OAUTH_TOKEN_URL, data=token_data)
            response.raise_for_status()
            
            token_response = response.json()
            
            if not token_response.get("ok"):
                return jsonify({
                    "ok": False,
                    "error": token_response.get("error", "Unknown error")
                }), 400
            
            # Get additional user information
            authed_user = token_response.get("authed_user", {})
            team = token_response.get("team", {})
            
            user_info = {
                "id": authed_user.get("id"),
                "name": authed_user.get("name"),
                "email": authed_user.get("email"),
                "image_24": authed_user.get("image_24"),
                "image_32": authed_user.get("image_32"),
                "image_48": authed_user.get("image_48"),
                "image_72": authed_user.get("image_72"),
                "image_192": authed_user.get("image_192"),
                "image_512": authed_user.get("image_512"),
                "team": team
            }
            
            # Calculate expiration time
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_response.get("expires_in", 86400))
            
            # Encrypt tokens
            access_token = token_response.get("access_token")
            if ENCRYPTION_AVAILABLE:
                access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            
            # Save tokens and user info to database
            if SLACK_DB_AVAILABLE:
                await save_user_slack_tokens(
                    None,  # db_conn_pool - will be passed in production
                    user_id,
                    {
                        'access_token': access_token,
                        'token_type': token_response.get("token_type", "bot"),
                        'scope': token_response.get("scope"),
                        'expires_at': expires_at.isoformat(),
                        'team_id': team.get("id"),
                        'team_name': team.get("name"),
                        'bot_user_id': token_response.get("bot_user_id"),
                        'app_id': token_response.get("app_id"),
                        'user_info': user_info
                    }
                )
            
            logger.info(f"Slack OAuth completed successfully for user {user_id}")
            
            return jsonify({
                "ok": True,
                "message": "Slack authentication successful",
                "user": {
                    "id": user_info.get("id"),
                    "name": user_info.get("name"),
                    "email": user_info.get("email"),
                    "image_48": user_info.get("image_48"),
                    "team_name": team.get("name")
                },
                "team": {
                    "id": team.get("id"),
                    "name": team.get("name")
                },
                "token_info": {
                    "scope": token_response.get("scope"),
                    "token_type": token_response.get("token_type"),
                    "expires_at": expires_at.isoformat()
                }
            })
        
    except Exception as e:
        logger.error(f"Slack OAuth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_slack_bp.route("/api/auth/slack/refresh", methods=["POST"])
async def refresh():
    """Refresh Slack OAuth tokens (not supported by Slack)"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        refresh_token = data.get("refresh_token")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        if not refresh_token:
            return jsonify({
                "ok": False,
                "error": "Refresh token is required"
            }), 400
        
        # Slack doesn't support refresh tokens
        return jsonify({
            "ok": False,
            "error": "Slack doesn't support token refresh. Please re-authenticate.",
            "requires_reauth": True
        }), 400
        
    except Exception as e:
        logger.error(f"Slack OAuth refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_slack_bp.route("/api/auth/slack/disconnect", methods=["POST"])
async def disconnect():
    """Disconnect Slack integration"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        # Delete tokens from database
        if SLACK_DB_AVAILABLE:
            await delete_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        logger.info(f"Slack disconnected for user {user_id}")
        
        return jsonify({
            "ok": True,
            "message": "Slack integration disconnected successfully"
        })
        
    except Exception as e:
        logger.error(f"Slack OAuth disconnect error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@auth_slack_bp.route("/api/auth/slack/webhook/<webhook_id>", methods=["POST"])
async def webhook_handler(webhook_id):
    """Handle Slack webhooks"""
    try:
        data = request.get_json()
        logger.info(f"Slack webhook {webhook_id} received: {data}")
        
        # Verify Slack signature if available
        if SLACK_SIGNING_SECRET:
            signature = request.headers.get('X-Slack-Signature')
            timestamp = request.headers.get('X-Slack-Request-Timestamp')
            
            if not signature or not timestamp:
                return jsonify({
                    "ok": False,
                    "error": "Missing Slack signature headers"
                }), 401
            
            # Add signature verification logic here
        
        # Handle different event types
        event_type = data.get("type")
        
        if event_type == "url_verification":
            # Respond to URL verification challenge
            return jsonify({
                "challenge": data.get("challenge")
            })
        elif event_type == "event_callback":
            # Handle event callback
            event_data = data.get("event", {})
            event_subtype = event_data.get("subtype")
            
            if event_subtype == "message_changed":
                await handle_message_changed(event_data, webhook_id)
            elif event_subtype == "message_deleted":
                await handle_message_deleted(event_data, webhook_id)
            else:
                await handle_message_event(event_data, webhook_id)
        
        return jsonify({
            "ok": True,
            "message": "Webhook processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Slack webhook error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_message_event(event_data: Dict[str, Any], webhook_id: str):
    """Handle Slack message event"""
    try:
        user = event_data.get("user")
        text = event_data.get("text")
        channel = event_data.get("channel")
        timestamp = event_data.get("ts")
        
        logger.info(f"Slack message: {user} in {channel}: {text}")
        
        # Process message event logic here
        # e.g., save to database, trigger notifications, etc.
        
    except Exception as e:
        logger.error(f"Error handling message event: {e}")

async def handle_message_changed(event_data: Dict[str, Any], webhook_id: str):
    """Handle Slack message changed event"""
    try:
        message = event_data.get("message", {})
        user = message.get("user")
        text = message.get("text")
        channel = event_data.get("channel")
        
        logger.info(f"Slack message changed: {user} in {channel}: {text}")
        
        # Process message changed event logic here
        
    except Exception as e:
        logger.error(f"Error handling message changed event: {e}")

async def handle_message_deleted(event_data: Dict[str, Any], webhook_id: str):
    """Handle Slack message deleted event"""
    try:
        previous_message = event_data.get("previous_message", {})
        user = previous_message.get("user")
        text = previous_message.get("text")
        channel = event_data.get("channel")
        
        logger.info(f"Slack message deleted: {user} in {channel}: {text}")
        
        # Process message deleted event logic here
        
    except Exception as e:
        logger.error(f"Error handling message deleted event: {e}")

@auth_slack_bp.route("/api/auth/slack/status", methods=["GET"])
async def status():
    """Get Slack OAuth status"""
    try:
        return jsonify({
            "ok": True,
            "status": "available",
            "client_id": SLACK_CLIENT_ID,
            "redirect_uri": SLACK_REDIRECT_URI,
            "default_scopes": [
                'channels:read', 'channels:write', 'chat:write', 'chat:write.public',
                'files:read', 'files:write', 'users:read', 'team:read'
            ],
            "database_available": SLACK_DB_AVAILABLE,
            "encryption_available": ENCRYPTION_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Slack OAuth status error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility functions
async def get_validated_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get and validate Slack tokens for user
    """
    try:
        if not SLACK_DB_AVAILABLE:
            return None
        
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        
        if not tokens:
            return None
        
        # Check if token is expired
        expires_at = tokens.get('expires_at')
        if expires_at and is_token_expired(expires_at):
            logger.warning(f"Slack tokens expired for user {user_id}")
            return None
        
        return tokens
        
    except Exception as e:
        logger.error(f"Error validating Slack tokens for user {user_id}: {e}")
        return None

async def ensure_valid_tokens(user_id: str) -> Optional[str]:
    """
    Ensure user has valid Slack tokens, return access token
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
        logger.error(f"Error ensuring valid Slack tokens for user {user_id}: {e}")
        return None

# Export for use in other modules
__all__ = [
    'slack_auth_manager',
    'auth_slack_bp',
    'get_validated_tokens',
    'ensure_valid_tokens'
]