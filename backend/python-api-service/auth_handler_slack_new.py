import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from urllib.parse import parse_qs
import base64
from cryptography.fernet import Fernet
from datetime import datetime

logger = logging.getLogger(__name__)

# Slack OAuth configuration
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI", "http://localhost:3000/api/integrations/slack/callback")
SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

class SlackOAuthHandler:
    """Complete Slack OAuth 2.0 Handler"""
    
    def __init__(self):
        self.client_id = SLACK_CLIENT_ID
        self.client_secret = SLACK_CLIENT_SECRET
        self.redirect_uri = SLACK_REDIRECT_URI
        self.fernet = Fernet(os.getenv("ATOM_OAUTH_ENCRYPTION_KEY"))
        
        if not all([self.client_id, self.client_secret]):
            logger.error("Slack OAuth credentials not found in environment variables")
            raise ValueError("Missing Slack OAuth credentials")
    
    async def get_authorization_url(self, state: str = None, scopes: list = None, team: str = None) -> str:
        """Generate Slack OAuth authorization URL"""
        try:
            # Generate state for CSRF protection
            if not state:
                state = base64.urlsafe_b64encode(os.urandom(32)).decode()
            
            # Default scopes for Slack
            if not scopes:
                scopes = [
                    "channels:history",
                    "channels:read",
                    "chat:write",
                    "files:read",
                    "groups:history",
                    "groups:read",
                    "im:history",
                    "im:read",
                    "mpim:history",
                    "mpim:read",
                    "users:read",
                    "users:read.email",
                    "team:read"
                ]
            
            # Build authorization URL
            params = {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": state
            }
            
            if team:
                params["team"] = team
            
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            auth_url = f"{SLACK_AUTH_URL}?{query_string}"
            
            logger.info(f"Generated Slack auth URL with state: {state}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to generate Slack authorization URL: {e}")
            raise
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            # Prepare token request
            token_data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code
            }
            
            # Add form-encoded content type for Slack
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Make token request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    SLACK_TOKEN_URL,
                    headers=headers,
                    data=token_data
                )
                response.raise_for_status()
                
                token_data = response.json()
                
                # Validate token response
                if not token_data.get("ok"):
                    raise ValueError(f"Slack token exchange failed: {token_data}")
                
                return {
                    "success": True,
                    "data": {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token"),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_in": token_data.get("expires_in", 0),
                        "created_at": datetime.now().isoformat(),
                        "scope": " ".join(scopes) if 'scopes' in locals() else "",
                        "team_id": token_data.get("team", {}).get("id"),
                        "team_name": token_data.get("team", {}).get("name"),
                        "bot_user_id": token_data.get("bot_user_id"),
                        "bot_access_token": token_data.get("bot_access_token")
                    }
                }
                
        except httpx.HTTPStatusError as e:
            error_data = e.response.text
            logger.error(f"Slack token exchange HTTP error: {e.response.status_code} - {error_data}")
            return {
                "success": False,
                "error": "Token exchange failed",
                "details": error_data
            }
        except Exception as e:
            logger.error(f"Failed to exchange Slack code for tokens: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            # Prepare refresh request
            refresh_data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Make refresh request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    SLACK_TOKEN_URL,
                    headers=headers,
                    data=refresh_data
                )
                response.raise_for_status()
                
                token_data = response.json()
                
                if not token_data.get("ok"):
                    raise ValueError(f"Slack token refresh failed: {token_data}")
                
                return {
                    "success": True,
                    "data": {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token", refresh_token),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_in": token_data.get("expires_in", 0),
                        "created_at": datetime.now().isoformat(),
                        "scope": token_data.get("scope", "")
                    }
                }
                
        except httpx.HTTPStatusError as e:
            error_data = e.response.text
            logger.error(f"Slack token refresh HTTP error: {e.response.status_code} - {error_data}")
            return {
                "success": False,
                "error": "Token refresh failed",
                "details": error_data
            }
        except Exception as e:
            logger.error(f"Failed to refresh Slack access token: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information after authentication"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/auth.test",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                
                if not data.get("ok"):
                    raise ValueError(f"Slack user info failed: {data}")
                
                return {
                    "success": True,
                    "data": {
                        "user_id": data.get("user_id"),
                        "team_id": data.get("team_id"),
                        "team": data.get("team"),
                        "user": data.get("user"),
                        "bot_id": data.get("bot_id"),
                        "url": data.get("url"),
                        "is_enterprise_install": data.get("is_enterprise_install", False)
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get Slack user info: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate if the access token is still valid"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://slack.com/api/auth.test",
                    headers=headers
                )
                data = response.json()
                return response.status_code == 200 and data.get("ok", False)
                
        except Exception as e:
            logger.error(f"Slack token validation failed: {e}")
            return False
    
    async def revoke_token(self, token: str) -> Dict[str, Any]:
        """Revoke Slack access token"""
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/auth.revoke",
                    headers=headers,
                    data={"token": token}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok", True):
                    logger.info(f"Slack token revoked successfully")
                    return {
                        "success": True,
                        "message": "Token revoked successfully"
                    }
                else:
                    raise Exception(f"Slack token revoke failed: {data}")
                
        except Exception as e:
            logger.error(f"Failed to revoke Slack token: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def encrypt_tokens(self, tokens: Dict[str, Any]) -> str:
        """Encrypt OAuth tokens for secure storage"""
        try:
            token_json = json.dumps(tokens)
            encrypted_data = self.fernet.encrypt(token_json.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt Slack tokens: {e}")
            raise
    
    def decrypt_tokens(self, encrypted_tokens: str) -> Dict[str, Any]:
        """Decrypt OAuth tokens from storage"""
        try:
            encrypted_data = base64.b64decode(encrypted_tokens.encode())
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt Slack tokens: {e}")
            raise
    
    def validate_state(self, received_state: str, expected_state: str) -> bool:
        """Validate OAuth state for CSRF protection"""
        try:
            return received_state == expected_state
        except Exception as e:
            logger.error(f"State validation failed: {e}")
            return False
    
    def generate_state(self) -> str:
        """Generate secure state parameter"""
        try:
            return base64.urlsafe_b64encode(os.urandom(32)).decode()
        except Exception as e:
            logger.error(f"Failed to generate state: {e}")
            raise
    
    def parse_callback_params(self, query_string: str) -> Dict[str, Any]:
        """Parse OAuth callback parameters"""
        try:
            params = parse_qs(query_string)
            return {
                "code": params.get("code", [None])[0],
                "state": params.get("state", [None])[0],
                "error": params.get("error", [None])[0],
                "error_description": params.get("error_description", [None])[0]
            }
        except Exception as e:
            logger.error(f"Failed to parse callback parameters: {e}")
            return {}

# Global handler instance
slack_oauth_handler = None

def get_slack_oauth_handler() -> SlackOAuthHandler:
    """Get global Slack OAuth handler instance"""
    global slack_oauth_handler
    if slack_oauth_handler is None:
        slack_oauth_handler = SlackOAuthHandler()
    return slack_oauth_handler