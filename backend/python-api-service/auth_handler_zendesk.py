"""
ATOM Zendesk Authentication Handler
OAuth 2.0 authentication for Zendesk integration
Following ATOM security and authentication patterns
"""

import os
import json
import hashlib
import secrets
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import aiohttp
from flask import Blueprint, request, jsonify, redirect, url_for
from loguru import logger
import urllib.parse

# Create blueprint
zendesk_auth_bp = Blueprint('zendesk_auth', __name__)

# Zendesk OAuth endpoints configuration
ZENDESK_AUTH_URL = "https://{subdomain}.zendesk.com/oauth/authorizations/new"
ZENDESK_TOKEN_URL = "https://{subdomain}.zendesk.com/oauth/tokens"

class ZendeskAuthHandler:
    """Zendesk OAuth 2.0 authentication handler"""
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.client_id = os.getenv("ZENDESK_CLIENT_ID")
        self.client_secret = os.getenv("ZENDESK_CLIENT_SECRET")
        self.redirect_uri = os.getenv("ZENDESK_REDIRECT_URI", "http://localhost:5058/auth/zendesk/callback")
        self.subdomain = os.getenv("ZENDESK_SUBDOMAIN")
        
        if not all([self.client_id, self.client_secret, self.subdomain]):
            logger.error("Zendesk OAuth credentials not properly configured")
    
    def generate_auth_url(self, user_id: str, state: Optional[str] = None) -> Tuple[str, str]:
        """Generate Zendesk OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Build the authorization URL with proper parameters
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "tickets:read tickets:write users:read organizations:read",
            "state": state
        }
        
        # Include user_id in state for tracking
        state_with_user = f"{user_id}:{state}"
        params["state"] = state_with_user
        
        auth_url = f"{ZENDESK_AUTH_URL.format(subdomain=self.subdomain)}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"Generated Zendesk auth URL for user {user_id}")
        return auth_url, state_with_user
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            token_url = ZENDESK_TOKEN_URL.format(subdomain=self.subdomain)
            
            data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ATOM-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Token exchange failed: {response.status} - {error_text}")
                    
                    token_data = await response.json()
                    
                    # Extract user_id from state
                    user_id = state.split(":", 1)[0] if ":" in state else None
                    
                    result = {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token"),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_in": token_data.get("expires_in", 3600),
                        "scope": token_data.get("scope", ""),
                        "user_id": user_id,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    logger.info(f"Successfully exchanged tokens for user {user_id}")
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            raise
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            token_url = ZENDESK_TOKEN_URL.format(subdomain=self.subdomain)
            
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ATOM-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Token refresh failed: {response.status} - {error_text}")
                    
                    token_data = await response.json()
                    
                    result = {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token", refresh_token),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_in": token_data.get("expires_in", 3600),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    logger.info("Successfully refreshed access token")
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Zendesk API"""
        try:
            api_url = f"https://{self.subdomain}.zendesk.com/api/v2/users/me.json"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "ATOM-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to get user info: {response.status} - {error_text}")
                    
                    user_data = await response.json()
                    
                    if "user" in user_data:
                        user = user_data["user"]
                        return {
                            "id": user.get("id"),
                            "email": user.get("email"),
                            "name": user.get("name"),
                            "role": user.get("role"),
                            "phone": user.get("phone"),
                            "organization_id": user.get("organization_id"),
                            "photo_url": user.get("photo", {}).get("url") if user.get("photo") else None,
                            "time_zone": user.get("time_zone")
                        }
                    
                    raise Exception("Invalid user response format")
                    
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise
    
    def validate_state(self, received_state: str, stored_state: str) -> bool:
        """Validate OAuth state parameter for security"""
        if not received_state or not stored_state:
            return False
        
        # Compare states securely
        return secrets.compare_digest(received_state, stored_state)
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke access token"""
        try:
            revoke_url = f"https://{self.subdomain}.zendesk.com/oauth/tokens/{access_token}.json"
            
            headers = {
                "Authorization": f"Basic {self._get_basic_auth()}",
                "User-Agent": "ATOM-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(revoke_url, headers=headers) as response:
                    if response.status in [200, 204]:
                        logger.info("Successfully revoked access token")
                        return True
                    else:
                        logger.warning(f"Failed to revoke token: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False
    
    def _get_basic_auth(self) -> str:
        """Get basic auth header for token revocation"""
        import base64
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        return base64.b64encode(auth_bytes).decode('ascii')

# Flask route handlers
@zendesk_auth_bp.route("/auth/zendesk", methods=["GET"])
def zendesk_auth_start():
    """Start Zendesk OAuth flow"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id parameter is required"
            }), 400
        
        handler = ZendeskAuthHandler()
        auth_url, state = handler.generate_auth_url(user_id)
        
        # Store state in session or database (simplified here)
        # In production, use Redis or secure session storage
        
        return jsonify({
            "ok": True,
            "auth_url": auth_url,
            "state": state,
            "message": "Please visit the authorization URL to continue"
        })
        
    except Exception as e:
        logger.error(f"Zendesk auth start error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Failed to start authentication: {str(e)}"
        }), 500

@zendesk_auth_bp.route("/auth/zendesk/callback", methods=["GET"])
def zendesk_auth_callback():
    """Handle Zendesk OAuth callback"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        
        if error:
            logger.error(f"Zendesk OAuth error: {error}")
            return jsonify({
                "ok": False,
                "error": f"OAuth error: {error}"
            }), 400
        
        if not code or not state:
            return jsonify({
                "ok": False,
                "error": "Missing required OAuth parameters"
            }), 400
        
        handler = ZendeskAuthHandler()
        
        # Exchange code for tokens
        # This is synchronous, but in production use async
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        token_data = loop.run_until_complete(handler.exchange_code_for_tokens(code, state))
        user_info = loop.run_until_complete(handler.get_user_info(token_data["access_token"]))
        
        return jsonify({
            "ok": True,
            "tokens": token_data,
            "user": user_info,
            "message": "Authentication successful"
        })
        
    except Exception as e:
        logger.error(f"Zendesk auth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Authentication failed: {str(e)}"
        }), 500

@zendesk_auth_bp.route("/auth/zendesk/refresh", methods=["POST"])
def zendesk_refresh_token():
    """Refresh access token"""
    try:
        data = request.get_json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            return jsonify({
                "ok": False,
                "error": "refresh_token is required"
            }), 400
        
        handler = ZendeskAuthHandler()
        
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        token_data = loop.run_until_complete(handler.refresh_access_token(refresh_token))
        
        return jsonify({
            "ok": True,
            "tokens": token_data,
            "message": "Token refreshed successfully"
        })
        
    except Exception as e:
        logger.error(f"Zendesk token refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Token refresh failed: {str(e)}"
        }), 500

@zendesk_auth_bp.route("/auth/zendesk/revoke", methods=["POST"])
def zendesk_revoke_token():
    """Revoke access token"""
    try:
        data = request.get_json()
        access_token = data.get("access_token")
        
        if not access_token:
            return jsonify({
                "ok": False,
                "error": "access_token is required"
            }), 400
        
        handler = ZendeskAuthHandler()
        
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        success = loop.run_until_complete(handler.revoke_token(access_token))
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Token revoked successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to revoke token"
            }), 400
        
    except Exception as e:
        logger.error(f"Zendesk token revoke error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Token revocation failed: {str(e)}"
        }), 500

# Export blueprint
def register_zendesk_auth_routes(app):
    """Register Zendesk authentication routes"""
    app.register_blueprint(zendesk_auth_bp)