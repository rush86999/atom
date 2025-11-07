"""
ATOM HubSpot Authentication Handler
OAuth 2.0 authentication for HubSpot marketing integration
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
hubspot_auth_bp = Blueprint('hubspot_auth', __name__)

# HubSpot OAuth endpoints configuration
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"

class HubSpotAuthHandler:
    """HubSpot OAuth 2.0 authentication handler"""
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.client_id = os.getenv("HUBSPOT_CLIENT_ID")
        self.client_secret = os.getenv("HUBSPOT_CLIENT_SECRET")
        self.redirect_uri = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:5058/auth/hubspot/callback")
        self.scopes = [
            "contacts",
            "crm.objects.companies.read",
            "crm.objects.companies.write",
            "crm.objects.contacts.read",
            "crm.objects.contacts.write",
            "crm.objects.deals.read",
            "crm.objects.deals.write",
            "marketing.campaigns.read",
            "marketing.campaigns.write",
            "crm.lists.read",
            "crm.lists.write",
            "crm.exports.read",
            "crm.schemas.contacts.read",
            "crm.schemas.companies.read",
            "crm.schemas.deals.read",
            "crm.objects.marketing_events.read",
            "crm.objects.marketing_events.write",
            "crm.objects.owners.read",
            "crm.pipelines.deals.read",
            "crm.objects.quotes.read",
            "crm.objects.line_items.read",
            "crm.objects.products.read",
            "crm.objects.custom.read",
            "crm.objects.custom.write",
            "settings.users.read",
            "settings.users.write",
            "tickets",
            "e-commerce",
            "accounting",
            "sales-email-read",
            "sales-email-write"
        ]
        
        if not all([self.client_id, self.client_secret]):
            logger.error("HubSpot OAuth credentials not properly configured")
    
    def generate_auth_url(self, user_id: str, state: Optional[str] = None) -> Tuple[str, str]:
        """Generate HubSpot OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Build the authorization URL with proper parameters
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": f"{user_id}:{state}",
            "optional_scopes": "",
            "token_type": "refresh_token"  # Ensure we get refresh token
        }
        
        auth_url = f"{HUBSPOT_AUTH_URL}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"Generated HubSpot auth URL for user {user_id}")
        return auth_url, f"{user_id}:{state}"
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "ATOM-HubSpot-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    HUBSPOT_TOKEN_URL,
                    data=data,
                    headers=headers
                ) as response:
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
                        "user_id": user_id,
                        "created_at": datetime.utcnow().isoformat(),
                        "hub_id": token_data.get("hub_id"),
                        "hub_domain": token_data.get("hub_domain"),
                        "app_id": token_data.get("app_id"),
                        "scope": token_data.get("scope", "").split()
                    }
                    
                    logger.info(f"Successfully exchanged tokens for user {user_id}")
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            raise
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "ATOM-HubSpot-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    HUBSPOT_TOKEN_URL,
                    data=data,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Token refresh failed: {response.status} - {error_text}")
                    
                    token_data = await response.json()
                    
                    result = {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token", refresh_token),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_in": token_data.get("expires_in", 3600),
                        "created_at": datetime.utcnow().isoformat(),
                        "hub_id": token_data.get("hub_id"),
                        "hub_domain": token_data.get("hub_domain")
                    }
                    
                    logger.info("Successfully refreshed HubSpot access token")
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise
    
    async def get_user_info(self, access_token: str, hub_id: str) -> Dict[str, Any]:
        """Get user/account information from HubSpot API"""
        try:
            api_url = f"https://api.hubapi.com/integrations/v1/me"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "ATOM-HubSpot-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to get user info: {response.status} - {error_text}")
                    
                    user_data = await response.json()
                    
                    return {
                        "hub_id": hub_id,
                        "user_id": user_data.get("userId"),
                        "user_email": user_data.get("email"),
                        "user_name": user_data.get("firstName", "") + " " + user_data.get("lastName", "").strip(),
                        "first_name": user_data.get("firstName"),
                        "last_name": user_data.get("lastName"),
                        "portal_id": user_data.get("portalId"),
                        "account_type": user_data.get("accountType"),
                        "time_zone": user_data.get("timeZone"),
                        "currency": user_data.get("currency"),
                        "super_admin": user_data.get("superAdmin"),
                        "scopes": user_data.get("scopes", [])
                    }
                    
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
            revoke_url = "https://api.hubapi.com/oauth/v1/refresh-tokens/delete"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ATOM-HubSpot-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(revoke_url, headers=headers) as response:
                    if response.status in [200, 204]:
                        logger.info("Successfully revoked HubSpot access token")
                        return True
                    else:
                        logger.warning(f"Failed to revoke token: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False
    
    async def get_account_info(self, access_token: str) -> Dict[str, Any]:
        """Get account information from HubSpot API"""
        try:
            api_url = "https://api.hubapi.com/settings/v3/users/me"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "ATOM-HubSpot-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to get account info: {response.status} - {error_text}")
                    
                    account_data = await response.json()
                    
                    return {
                        "user_id": account_data.get("id"),
                        "email": account_data.get("email"),
                        "first_name": account_data.get("firstName"),
                        "last_name": account_data.get("lastName"),
                        "user_type": account_data.get("type"),
                        "is_super_admin": account_data.get("isSuperAdmin"),
                        "is_primary_user": account_data.get("isPrimaryUser"),
                        "role_id": account_data.get("roleId"),
                        "role_name": account_data.get("roleName"),
                        "hub_id": account_data.get("hubId"),
                        "user_teams": account_data.get("userTeams", []),
                        "permissions": account_data.get("permissions", {})
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise
    
    async def get_portal_info(self, access_token: str) -> Dict[str, Any]:
        """Get portal/company information from HubSpot API"""
        try:
            api_url = "https://api.hubapi.com/crm/v3/objects/owners/paged"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "ATOM-HubSpot-Integration/1.0"
            }
            
            params = {
                "limit": 1,
                "properties": ["portalId", "companyName", "domain", "currency", "timeZone"]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to get portal info: {response.status} - {error_text}")
                    
                    portal_data = await response.json()
                    
                    if "results" in portal_data and len(portal_data["results"]) > 0:
                        owner = portal_data["results"][0]
                        return {
                            "portal_id": owner.get("portalId"),
                            "company_name": owner.get("companyName"),
                            "domain": owner.get("domain"),
                            "currency": owner.get("currency"),
                            "time_zone": owner.get("timeZone")
                        }
                    
                    raise Exception("Invalid portal response format")
                    
        except Exception as e:
            logger.error(f"Failed to get portal info: {e}")
            raise

# Flask route handlers
@hubspot_auth_bp.route("/auth/hubspot", methods=["GET"])
def hubspot_auth_start():
    """Start HubSpot OAuth flow"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id parameter is required"
            }), 400
        
        handler = HubSpotAuthHandler()
        auth_url, state = handler.generate_auth_url(user_id)
        
        # Store state in session or database (simplified here)
        # In production, use Redis or secure session storage
        
        return jsonify({
            "ok": True,
            "auth_url": auth_url,
            "state": state,
            "scopes": handler.scopes,
            "message": "Please visit the authorization URL to continue"
        })
        
    except Exception as e:
        logger.error(f"HubSpot auth start error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Failed to start authentication: {str(e)}"
        }), 500

@hubspot_auth_bp.route("/auth/hubspot/callback", methods=["GET"])
def hubspot_auth_callback():
    """Handle HubSpot OAuth callback"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        
        if error:
            logger.error(f"HubSpot OAuth error: {error}")
            return jsonify({
                "ok": False,
                "error": f"OAuth error: {error}"
            }), 400
        
        if not code or not state:
            return jsonify({
                "ok": False,
                "error": "Missing required OAuth parameters"
            }), 400
        
        handler = HubSpotAuthHandler()
        
        # Exchange code for tokens
        # This is synchronous, but in production use async
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        token_data = loop.run_until_complete(handler.exchange_code_for_tokens(code, state))
        
        # Get account information
        account_info = loop.run_until_complete(handler.get_account_info(token_data["access_token"]))
        portal_info = loop.run_until_complete(handler.get_portal_info(token_data["access_token"]))
        
        # Merge account and portal info with token data
        token_data.update({
            "account_info": account_info,
            "portal_info": portal_info
        })
        
        return jsonify({
            "ok": True,
            "tokens": token_data,
            "account": account_info,
            "portal": portal_info,
            "message": "Authentication successful"
        })
        
    except Exception as e:
        logger.error(f"HubSpot auth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Authentication failed: {str(e)}"
        }), 500

@hubspot_auth_bp.route("/auth/hubspot/refresh", methods=["POST"])
def hubspot_refresh_token():
    """Refresh access token"""
    try:
        data = request.get_json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            return jsonify({
                "ok": False,
                "error": "refresh_token is required"
            }), 400
        
        handler = HubSpotAuthHandler()
        
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
        logger.error(f"HubSpot token refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Token refresh failed: {str(e)}"
        }), 500

@hubspot_auth_bp.route("/auth/hubspot/revoke", methods=["POST"])
def hubspot_revoke_token():
    """Revoke access token"""
    try:
        data = request.get_json()
        access_token = data.get("access_token")
        
        if not access_token:
            return jsonify({
                "ok": False,
                "error": "access_token is required"
            }), 400
        
        handler = HubSpotAuthHandler()
        
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
        logger.error(f"HubSpot token revoke error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Token revocation failed: {str(e)}"
        }), 500

# Export blueprint
def register_hubspot_auth_routes(app):
    """Register HubSpot authentication routes"""
    app.register_blueprint(hubspot_auth_bp)