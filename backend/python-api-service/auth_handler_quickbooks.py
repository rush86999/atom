"""
ATOM QuickBooks Authentication Handler
OAuth 2.0 authentication for QuickBooks integration
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
quickbooks_auth_bp = Blueprint('quickbooks_auth', __name__)

# QuickBooks OAuth endpoints configuration
QUICKBOOKS_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QUICKBOOKS_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

class QuickBooksAuthHandler:
    """QuickBooks OAuth 2.0 authentication handler"""
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.client_id = os.getenv("QUICKBOOKS_CLIENT_ID")
        self.client_secret = os.getenv("QUICKBOOKS_CLIENT_SECRET")
        self.redirect_uri = os.getenv("QUICKBOOKS_REDIRECT_URI", "http://localhost:5058/auth/quickbooks/callback")
        self.environment = os.getenv("QUICKBOOKS_ENVIRONMENT", "sandbox")
        
        if not all([self.client_id, self.client_secret]):
            logger.error("QuickBooks OAuth credentials not properly configured")
    
    def generate_auth_url(self, user_id: str, state: Optional[str] = None) -> Tuple[str, str]:
        """Generate QuickBooks OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Build the authorization URL with proper parameters
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "com.intuit.quickbooks.accounting",
            "state": f"{user_id}:{state}"
        }
        
        auth_url = f"{QUICKBOOKS_AUTH_URL}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"Generated QuickBooks auth URL for user {user_id}")
        return auth_url, f"{user_id}:{state}"
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri
            }
            
            # Basic auth header for token exchange
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_header = {
                "Authorization": f"Basic {self._get_basic_auth()}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "ATOM-QuickBooks-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    QUICKBOOKS_TOKEN_URL,
                    data=data,
                    headers=auth_header
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
                        "x_refresh_token_expires_in": token_data.get("x_refresh_token_expires_in", 864000),
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
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            # Basic auth header for token refresh
            auth_header = {
                "Authorization": f"Basic {self._get_basic_auth()}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "ATOM-QuickBooks-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    QUICKBOOKS_TOKEN_URL,
                    data=data,
                    headers=auth_header
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
                        "x_refresh_token_expires_in": token_data.get("x_refresh_token_expires_in", 864000),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    logger.info("Successfully refreshed QuickBooks access token")
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise
    
    async def get_user_info(self, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Get company information from QuickBooks API"""
        try:
            api_url = f"https://{self.environment}.quickbooks.api.intuit.com/v3/company/{realm_id}/companyinfo/{realm_id}"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "ATOM-QuickBooks-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to get company info: {response.status} - {error_text}")
                    
                    company_data = await response.json()
                    
                    if "CompanyInfo" in company_data and len(company_data["CompanyInfo"]) > 0:
                        company = company_data["CompanyInfo"][0]
                        return {
                            "realm_id": realm_id,
                            "company_name": company.get("CompanyName"),
                            "legal_name": company.get("LegalName"),
                            "company_type": company.get("CompanyType"),
                            "domain": company.get("Domain"),
                            "email": company.get("Email"),
                            "phone": company.get("Phone"),
                            "website": company.get("WebAddr"),
                            "address": {
                                "line1": company.get("CompanyAddr", {}).get("Line1"),
                                "line2": company.get("CompanyAddr", {}).get("Line2"),
                                "city": company.get("CompanyAddr", {}).get("City"),
                                "state": company.get("CompanyAddr", {}).get("CountrySubDivisionCode"),
                                "postal_code": company.get("CompanyAddr", {}).get("PostalCode"),
                                "country": company.get("CompanyAddr", {}).get("Country")
                            }
                        }
                    
                    raise Exception("Invalid company response format")
                    
        except Exception as e:
            logger.error(f"Failed to get company info: {e}")
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
            revoke_url = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
            
            data = {
                "token": access_token
            }
            
            auth_header = {
                "Authorization": f"Basic {self._get_basic_auth()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ATOM-QuickBooks-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(revoke_url, json=data, headers=auth_header) as response:
                    if response.status in [200, 204]:
                        logger.info("Successfully revoked QuickBooks access token")
                        return True
                    else:
                        logger.warning(f"Failed to revoke token: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False
    
    def _get_basic_auth(self) -> str:
        """Get basic auth header for token operations"""
        import base64
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        return base64.b64encode(auth_bytes).decode('ascii')
    
    async def get_realm_info(self, access_token: str) -> Dict[str, Any]:
        """Get user's realm information from QuickBooks"""
        try:
            api_url = f"https://developer.api.intuit.com/v2/company"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "ATOM-QuickBooks-Integration/1.0"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to get realm info: {response.status} - {error_text}")
                    
                    realm_data = await response.json()
                    
                    if "company" in realm_data and len(realm_data["company"]) > 0:
                        company = realm_data["company"][0]
                        return {
                            "realm_id": company.get("Id"),
                            "company_name": company.get("Name"),
                            "environment": company.get("Id", "").split(".", 1)[0]
                        }
                    
                    raise Exception("Invalid realm response format")
                    
        except Exception as e:
            logger.error(f"Failed to get realm info: {e}")
            raise

# Flask route handlers
@quickbooks_auth_bp.route("/auth/quickbooks", methods=["GET"])
def quickbooks_auth_start():
    """Start QuickBooks OAuth flow"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id parameter is required"
            }), 400
        
        handler = QuickBooksAuthHandler()
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
        logger.error(f"QuickBooks auth start error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Failed to start authentication: {str(e)}"
        }), 500

@quickbooks_auth_bp.route("/auth/quickbooks/callback", methods=["GET"])
def quickbooks_auth_callback():
    """Handle QuickBooks OAuth callback"""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        realm_id = request.args.get("realmId")
        error = request.args.get("error")
        
        if error:
            logger.error(f"QuickBooks OAuth error: {error}")
            return jsonify({
                "ok": False,
                "error": f"OAuth error: {error}"
            }), 400
        
        if not code or not state or not realm_id:
            return jsonify({
                "ok": False,
                "error": "Missing required OAuth parameters"
            }), 400
        
        handler = QuickBooksAuthHandler()
        
        # Exchange code for tokens
        # This is synchronous, but in production use async
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        token_data = loop.run_until_complete(handler.exchange_code_for_tokens(code, state))
        
        # Get company information
        company_info = loop.run_until_complete(handler.get_user_info(token_data["access_token"], realm_id))
        
        # Merge company info with token data
        token_data.update({
            "realm_id": realm_id,
            "company_info": company_info
        })
        
        return jsonify({
            "ok": True,
            "tokens": token_data,
            "company": company_info,
            "message": "Authentication successful"
        })
        
    except Exception as e:
        logger.error(f"QuickBooks auth callback error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Authentication failed: {str(e)}"
        }), 500

@quickbooks_auth_bp.route("/auth/quickbooks/refresh", methods=["POST"])
def quickbooks_refresh_token():
    """Refresh access token"""
    try:
        data = request.get_json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            return jsonify({
                "ok": False,
                "error": "refresh_token is required"
            }), 400
        
        handler = QuickBooksAuthHandler()
        
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
        logger.error(f"QuickBooks token refresh error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Token refresh failed: {str(e)}"
        }), 500

@quickbooks_auth_bp.route("/auth/quickbooks/revoke", methods=["POST"])
def quickbooks_revoke_token():
    """Revoke access token"""
    try:
        data = request.get_json()
        access_token = data.get("access_token")
        
        if not access_token:
            return jsonify({
                "ok": False,
                "error": "access_token is required"
            }), 400
        
        handler = QuickBooksAuthHandler()
        
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
        logger.error(f"QuickBooks token revoke error: {e}")
        return jsonify({
            "ok": False,
            "error": f"Token revocation failed: {str(e)}"
        }), 500

# Export blueprint
def register_quickbooks_auth_routes(app):
    """Register QuickBooks authentication routes"""
    app.register_blueprint(quickbooks_auth_bp)