#!/usr/bin/env python3
"""
🚀 Zoom OAuth 2.0 Authentication Handler
Enterprise-grade Zoom integration with comprehensive OAuth flow
"""

import os
import json
import urllib.parse
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

import requests
import asyncpg
from flask import Blueprint, request, jsonify, session, redirect

logger = logging.getLogger(__name__)

# Zoom OAuth Configuration
ZOOM_AUTH_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_REVOKE_URL = "https://zoom.us/oauth/revoke"

# Required Zoom API Scopes
ZOOM_SCOPES = [
    "user:read:admin",        # Read user information
    "meeting:write:admin",    # Create and manage meetings
    "meeting:read:admin",     # Read meeting information
    "recording:write:admin",  # Manage recordings
    "recording:read:admin",   # Access recordings
    "webinar:write:admin",    # Manage webinars
    "webinar:read:admin",     # Read webinar information
    "user:write:admin",       # Manage users
    "report:read:admin",       # Access reports
    "dashboard:read:admin",    # Access dashboard data
]

ZOOM_REQUIRED_FIELDS = [
    "id", "email", "first_name", "last_name", "display_name", 
    "type", "role_name", "created_at"
]

@dataclass
class ZoomOAuthConfig:
    """Zoom OAuth configuration"""
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list
    environment: str = "production"

@dataclass 
class ZoomTokenInfo:
    """Zoom OAuth token information"""
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    scope: str
    user_id: str
    email: str
    account_id: str
    created_at: datetime

class ZoomOAuthHandler:
    """Enterprise-grade Zoom OAuth handler"""
    
    def __init__(self, db_pool: asyncpg.Pool = None):
        self.db_pool = db_pool
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> ZoomOAuthConfig:
        """Load Zoom OAuth configuration"""
        try:
            config = ZoomOAuthConfig(
                client_id=os.getenv("ZOOM_CLIENT_ID", ""),
                client_secret=os.getenv("ZOOM_CLIENT_SECRET", ""),
                redirect_uri=os.getenv(
                    "ZOOM_REDIRECT_URI", 
                    "http://localhost:3000/oauth/zoom/callback"
                ),
                scopes=ZOOM_SCOPES,
                environment=os.getenv("ZOOM_ENVIRONMENT", "production")
            )
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load Zoom OAuth config: {e}")
            raise ValueError(f"Zoom OAuth configuration error: {e}")
    
    def _validate_config(self) -> None:
        """Validate Zoom OAuth configuration"""
        if not self.config.client_id or self.config.client_id.startswith(("YOUR_", "mock_")):
            raise ValueError("ZOOM_CLIENT_ID is required and must be valid")
        
        if not self.config.client_secret or self.config.client_secret.startswith(("YOUR_", "mock_")):
            raise ValueError("ZOOM_CLIENT_SECRET is required and must be valid")
        
        if not self.config.redirect_uri:
            raise ValueError("ZOOM_REDIRECT_URI is required")
    
    def get_oauth_url(self, user_id: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate Zoom OAuth authorization URL
        
        Args:
            user_id: Optional user identifier
            state: Optional state parameter for security
            
        Returns:
            Dictionary with authorization URL and metadata
        """
        try:
            # Generate secure state if not provided
            if not state:
                state = self._generate_state()
                if self.db_pool and user_id:
                    self._store_state(user_id, state)
            
            # Build OAuth parameters
            params = {
                "response_type": "code",
                "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri,
                "scope": " ".join(self.config.scopes),
                "state": state,
            }
            
            # Generate authorization URL
            auth_url = f"{ZOOM_AUTH_URL}?{urllib.parse.urlencode(params)}"
            
            logger.info(f"Generated Zoom OAuth URL for user: {user_id}")
            
            return {
                "ok": True,
                "authorization_url": auth_url,
                "state": state,
                "provider": "zoom",
                "environment": self.config.environment,
                "client_id": self.config.client_id[:10] + "...",
                "redirect_uri": self.config.redirect_uri,
                "expires_in": 600
            }
            
        except Exception as e:
            logger.error(f"Failed to generate Zoom OAuth URL: {e}")
            return {
                "ok": False,
                "error": "oauth_url_generation_failed",
                "message": f"Failed to generate authorization URL: {str(e)}",
                "provider": "zoom"
            }
    
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from Zoom
            state: State parameter for security validation
            
        Returns:
            Dictionary with token information
        """
        try:
            # Validate state if database is available
            if self.db_pool:
                state_validation = self._validate_state(state)
                if not state_validation["valid"]:
                    return {
                        "ok": False,
                        "error": "invalid_state",
                        "message": "Invalid or expired state parameter",
                        "provider": "zoom"
                    }
            
            # Prepare token request
            token_data = {
                "grant_type": "authorization_code",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "redirect_uri": self.config.redirect_uri,
                "code": code
            }
            
            # Request token from Zoom
            response = requests.post(
                ZOOM_TOKEN_URL,
                data=token_data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=30
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_message = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                
                logger.error(f"Zoom token exchange failed: {response.status_code} - {error_message}")
                
                return {
                    "ok": False,
                    "error": "token_exchange_failed",
                    "message": f"Token exchange failed: {error_message}",
                    "status_code": response.status_code,
                    "provider": "zoom"
                }
            
            token_response = response.json()
            
            # Calculate expiration time
            expires_in = token_response.get("expires_in", 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Get user information
            user_info = self._get_user_info(token_response["access_token"])
            
            if not user_info.get("ok"):
                return {
                    "ok": False,
                    "error": "user_info_failed",
                    "message": "Failed to retrieve user information",
                    "provider": "zoom"
                }
            
            user_data = user_info["user_info"]
            
            # Create token info object
            token_info = ZoomTokenInfo(
                access_token=token_response["access_token"],
                refresh_token=token_response.get("refresh_token", ""),
                token_type=token_response.get("token_type", "Bearer"),
                expires_at=expires_at,
                scope=token_response.get("scope", ""),
                user_id=user_data.get("id"),
                email=user_data.get("email"),
                account_id=user_data.get("account_id"),
                created_at=datetime.now(timezone.utc)
            )
            
            logger.info(f"Successfully exchanged Zoom OAuth code for user: {token_info.user_id}")
            
            return {
                "ok": True,
                "tokens": {
                    "access_token": token_info.access_token,
                    "refresh_token": token_info.refresh_token,
                    "token_type": token_info.token_type,
                    "scope": token_info.scope,
                    "expires_in": expires_in,
                    "expires_at": expires_at.isoformat()
                },
                "user_info": {
                    "id": token_info.user_id,
                    "email": token_info.email,
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                    "display_name": user_data.get("display_name"),
                    "type": user_data.get("type"),
                    "role_name": user_data.get("role_name"),
                    "account_id": token_info.account_id,
                    "created_at": token_info.created_at.isoformat()
                },
                "provider": "zoom",
                "stored": False
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Zoom token request failed: {e}")
            return {
                "ok": False,
                "error": "network_error",
                "message": f"Network error during token exchange: {str(e)}",
                "provider": "zoom"
            }
        except Exception as e:
            logger.error(f"Unexpected error in Zoom token exchange: {e}")
            return {
                "ok": False,
                "error": "token_exchange_error",
                "message": f"Unexpected error during token exchange: {str(e)}",
                "provider": "zoom"
            }
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dictionary with new token information
        """
        try:
            token_data = {
                "grant_type": "refresh_token",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": refresh_token
            }
            
            response = requests.post(
                ZOOM_TOKEN_URL,
                data=token_data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=30
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_message = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                
                logger.error(f"Zoom token refresh failed: {response.status_code} - {error_message}")
                
                return {
                    "ok": False,
                    "error": "token_refresh_failed",
                    "message": f"Token refresh failed: {error_message}",
                    "provider": "zoom"
                }
            
            token_response = response.json()
            
            # Calculate new expiration
            expires_in = token_response.get("expires_in", 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            logger.info(f"Successfully refreshed Zoom token")
            
            return {
                "ok": True,
                "tokens": {
                    "access_token": token_response["access_token"],
                    "refresh_token": token_response.get("refresh_token", refresh_token),
                    "token_type": token_response.get("token_type", "Bearer"),
                    "scope": token_response.get("scope", ""),
                    "expires_in": expires_in,
                    "expires_at": expires_at.isoformat()
                },
                "provider": "zoom"
            }
            
        except Exception as e:
            logger.error(f"Zoom token refresh error: {e}")
            return {
                "ok": False,
                "error": "token_refresh_error",
                "message": f"Error during token refresh: {str(e)}",
                "provider": "zoom"
            }
    
    def revoke_token(self, access_token: str) -> Dict[str, Any]:
        """
        Revoke Zoom access token
        
        Args:
            access_token: Access token to revoke
            
        Returns:
            Dictionary with revocation result
        """
        try:
            token_data = {
                "token": access_token
            }
            
            response = requests.post(
                ZOOM_REVOKE_URL,
                data=token_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=30
            )
            
            # Zoom returns 200 on successful revocation
            success = response.status_code == 200
            
            if success:
                logger.info("Successfully revoked Zoom token")
            else:
                logger.warning(f"Zoom token revocation failed: {response.status_code}")
            
            return {
                "ok": success,
                "message": "Token revoked successfully" if success else "Token revocation failed",
                "status_code": response.status_code,
                "provider": "zoom"
            }
            
        except Exception as e:
            logger.error(f"Zoom token revocation error: {e}")
            return {
                "ok": False,
                "error": "token_revocation_error",
                "message": f"Error during token revocation: {str(e)}",
                "provider": "zoom"
            }
    
    def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get additional user information from Zoom
        
        Args:
            access_token: Valid access token
            
        Returns:
            Dictionary with user information
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            
            response = requests.get(
                "https://api.zoom.us/v2/users/me",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "ok": True,
                    "user_data": {
                        "id": user_data.get("id"),
                        "email": user_data.get("email"),
                        "first_name": user_data.get("first_name"),
                        "last_name": user_data.get("last_name"),
                        "display_name": user_data.get("display_name"),
                        "type": user_data.get("type"),
                        "role_name": user_data.get("role_name"),
                        "account_id": user_data.get("account_id"),
                        "created_at": user_data.get("created_at")
                    }
                }
            else:
                logger.warning(f"Failed to get Zoom user info: {response.status_code}")
                return {"ok": False, "error": "user_info_failed"}
                
        except Exception as e:
            logger.error(f"Error getting Zoom user info: {e}")
            return {"ok": False, "error": "user_info_error"}
    
    def _generate_state(self) -> str:
        """Generate secure state parameter"""
        return secrets.token_urlsafe(32)
    
    async def _store_state(self, user_id: str, state: str) -> None:
        """Store state parameter for validation"""
        try:
            if not self.db_pool:
                return
            
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO oauth_states (user_id, provider, state, expires_at, created_at)
                    VALUES ($1, 'zoom', $2, $3, $4)
                    ON CONFLICT (user_id, provider) 
                    DO UPDATE SET 
                        state = EXCLUDED.state,
                        expires_at = EXCLUDED.expires_at,
                        created_at = EXCLUDED.created_at
                    """,
                    user_id,
                    state,
                    datetime.now(timezone.utc) + timedelta(minutes=10),
                    datetime.now(timezone.utc)
                )
                
        except Exception as e:
            logger.error(f"Failed to store Zoom OAuth state: {e}")
    
    async def _validate_state(self, state: str) -> Dict[str, Any]:
        """Validate state parameter"""
        try:
            if not self.db_pool:
                return {"valid": True}
            
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT user_id, expires_at FROM oauth_states 
                    WHERE provider = 'zoom' AND state = $1
                    """,
                    state
                )
                
                if not result:
                    return {"valid": False, "error": "state_not_found"}
                
                if result["expires_at"] < datetime.now(timezone.utc):
                    return {"valid": False, "error": "state_expired"}
                
                # Clean up used state
                await conn.execute(
                    """
                    DELETE FROM oauth_states 
                    WHERE provider = 'zoom' AND state = $1
                    """,
                    state
                )
                
                return {"valid": True, "user_id": result["user_id"]}
                
        except Exception as e:
            logger.error(f"Failed to validate Zoom OAuth state: {e}")
            return {"valid": False, "error": "state_validation_error"}

# Flask Blueprint for Zoom OAuth
zoom_auth_bp = Blueprint("zoom_auth", __name__)

# Global OAuth handler (will be initialized with database pool)
zoom_oauth_handler = None

def init_zoom_oauth_handler(db_pool: asyncpg.Pool):
    """Initialize Zoom OAuth handler with database pool"""
    global zoom_oauth_handler
    zoom_oauth_handler = ZoomOAuthHandler(db_pool)

@zoom_auth_bp.route("/zoom/authorize", methods=["GET"])
def zoom_authorize():
    """Initiate Zoom OAuth flow"""
    user_id = request.args.get("user_id")
    state = request.args.get("state")
    
    if not zoom_oauth_handler:
        return jsonify({
            "ok": False,
            "error": "service_not_initialized",
            "message": "Zoom OAuth handler not initialized"
        }), 503
    
    result = zoom_oauth_handler.get_oauth_url(user_id, state)
    
    if result.get("ok"):
        return jsonify(result)
    else:
        return jsonify(result), 400

@zoom_auth_bp.route("/zoom/callback", methods=["POST"])
def zoom_callback():
    """Handle Zoom OAuth callback"""
    data = request.get_json()
    code = data.get('code')
    state = data.get('state')
    
    if not code:
        return jsonify({
            "ok": False,
            "error": "authorization_code_required",
            "message": "Authorization code is required",
            "provider": "zoom"
        }), 400
    
    if not zoom_oauth_handler:
        return jsonify({
            "ok": False,
            "error": "service_not_initialized",
            "message": "Zoom OAuth handler not initialized"
        }), 503
    
    result = zoom_oauth_handler.exchange_code_for_token(code, state)
    
    if result.get("ok"):
        # Store tokens in database
        try:
            from db_oauth_zoom import store_zoom_tokens
            
            if zoom_oauth_handler.db_pool:
                user_info = result.get("user_info", {})
                tokens = result.get("tokens", {})
                
                user_id = user_info.get("id")
                if user_id:
                    from datetime import datetime, timezone, timedelta
                    expires_at = datetime.fromisoformat(tokens["expires_at"].replace('Z', '+00:00'))
                    
                    store_result = asyncio.run(store_zoom_tokens(
                        zoom_oauth_handler.db_pool,
                        user_id,
                        tokens.get("access_token"),
                        tokens.get("refresh_token"),
                        expires_at,
                        tokens.get("scope"),
                        user_info.get("email"),
                        user_info.get("first_name"),
                        user_info.get("last_name"),
                        user_info.get("display_name"),
                        user_info.get("type"),
                        user_info.get("role_name"),
                        user_info.get("account_id")
                    ))
                    
                    if store_result.get("success"):
                        result["stored"] = True
                    else:
                        logger.error(f"Failed to store Zoom tokens: {store_result.get('error')}")
                        result["stored"] = False
        except Exception as e:
            logger.error(f"Error storing Zoom tokens: {e}")
            result["stored"] = False
    
    return jsonify(result)

@zoom_auth_bp.route("/zoom/refresh", methods=["POST"])
def zoom_refresh():
    """Refresh Zoom access token"""
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({
            "ok": False,
            "error": "refresh_token_required",
            "message": "Refresh token is required",
            "provider": "zoom"
        }), 400
    
    if not zoom_oauth_handler:
        return jsonify({
            "ok": False,
            "error": "service_not_initialized",
            "message": "Zoom OAuth handler not initialized"
        }), 503
    
    result = zoom_oauth_handler.refresh_token(refresh_token)
    
    return jsonify(result)

@zoom_auth_bp.route("/zoom/revoke", methods=["POST"])
def zoom_revoke():
    """Revoke Zoom access token"""
    data = request.get_json()
    access_token = data.get('access_token')
    
    if not access_token:
        return jsonify({
            "ok": False,
            "error": "access_token_required",
            "message": "Access token is required",
            "provider": "zoom"
        }), 400
    
    if not zoom_oauth_handler:
        return jsonify({
            "ok": False,
            "error": "service_not_initialized",
            "message": "Zoom OAuth handler not initialized"
        }), 503
    
    result = zoom_oauth_handler.revoke_token(access_token)
    
    return jsonify(result)

@zoom_auth_bp.route("/zoom/health", methods=["GET"])
def zoom_health():
    """Health check for Zoom OAuth service"""
    if not zoom_oauth_handler:
        return jsonify({
            "ok": False,
            "error": "service_not_initialized",
            "provider": "zoom"
        }), 503
    
    try:
        # Test basic configuration
        config_ok = bool(
            zoom_oauth_handler.config.client_id and
            zoom_oauth_handler.config.client_secret and
            zoom_oauth_handler.config.redirect_uri
        )
        
        return jsonify({
            "ok": True,
            "provider": "zoom",
            "environment": zoom_oauth_handler.config.environment,
            "configuration": "valid" if config_ok else "invalid",
            "database": "connected" if zoom_oauth_handler.db_pool else "disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": "health_check_failed",
            "message": str(e),
            "provider": "zoom"
        }), 500