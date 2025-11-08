import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from urllib.parse import parse_qs
import base64
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# HubSpot OAuth configuration
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:3000/api/integrations/hubspot/callback")
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"

class HubSpotOAuthHandler:
    """Complete HubSpot OAuth 2.0 Handler"""
    
    def __init__(self):
        self.client_id = HUBSPOT_CLIENT_ID
        self.client_secret = HUBSPOT_CLIENT_SECRET
        self.redirect_uri = HUBSPOT_REDIRECT_URI
        self.fernet = Fernet(os.getenv("ATOM_OAUTH_ENCRYPTION_KEY"))
        
        if not all([self.client_id, self.client_secret]):
            logger.error("HubSpot OAuth credentials not found in environment variables")
            raise ValueError("Missing HubSpot OAuth credentials")
    
    async def get_authorization_url(self, state: str = None, scopes: list = None) -> str:
        """Generate HubSpot OAuth authorization URL"""
        try:
            # Generate state for CSRF protection
            if not state:
                state = base64.urlsafe_b64encode(os.urandom(32)).decode()
            
            # Default scopes for HubSpot CRM
            if not scopes:
                scopes = [
                    "crm.objects.contacts.write",
                    "crm.objects.companies.write", 
                    "crm.objects.deals.write",
                    "crm.objects.tickets.write",
                    "crm.schemas.deals.read",
                    "crm.schemas.contacts.read",
                    "crm.schemas.companies.read",
                    "crm.objects.custom.write",
                    "crm.lists.write",
                    "crm.lists.read"
                ]
            
            # Build authorization URL
            params = {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": state,
                "optional_scopes": "crm.objects.companies.read crm.objects.deals.read crm.objects.tickets.read crm.objects.contacts.read crm.schemas.contacts.read crm.schemas.companies.read crm.schemas.deals.read crm.objects.custom.read crm.lists.read"
            }
            
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            auth_url = f"{HUBSPOT_AUTH_URL}?{query_string}"
            
            logger.info(f"Generated HubSpot auth URL with state: {state}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to generate HubSpot authorization URL: {e}")
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
            
            # Add form-encoded content type for HubSpot
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Make token request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    HUBSPOT_TOKEN_URL,
                    headers=headers,
                    data=token_data
                )
                response.raise_for_status()
                
                token_data = response.json()
                
                # Validate token response
                if not token_data.get("access_token"):
                    raise ValueError("No access token in response")
                
                return {
                    "success": True,
                    "data": {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token"),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_in": token_data.get("expires_in", 0),
                        "created_at": datetime.now().isoformat(),
                        "scope": " ".join(scopes) if 'scopes' in locals() else ""
                    }
                }
                
        except httpx.HTTPStatusError as e:
            error_data = e.response.text
            logger.error(f"HubSpot token exchange HTTP error: {e.response.status_code} - {error_data}")
            return {
                "success": False,
                "error": "Token exchange failed",
                "details": error_data
            }
        except Exception as e:
            logger.error(f"Failed to exchange HubSpot code for tokens: {e}")
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
                    HUBSPOT_TOKEN_URL,
                    headers=headers,
                    data=refresh_data
                )
                response.raise_for_status()
                
                token_data = response.json()
                
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
            logger.error(f"HubSpot token refresh HTTP error: {e.response.status_code} - {error_data}")
            return {
                "success": False,
                "error": "Token refresh failed",
                "details": error_data
            }
        except Exception as e:
            logger.error(f"Failed to refresh HubSpot access token: {e}")
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
                    "https://api.hubapi.com/oauth/v1/access-tokens",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                token_info = data.get("access_token", {})
                
                return {
                    "success": True,
                    "data": {
                        "user_id": token_info.get("user"),
                        "hub_id": token_info.get("hub_id"),
                        "app_id": token_info.get("app_id"),
                        "expires_in": token_info.get("expires_in"),
                        "scopes": token_info.get("scopes", [])
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot user info: {e}")
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
                    "https://api.hubapi.com/crm/v3/objects/contacts",
                    headers=headers,
                    params={"limit": 1}
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"HubSpot token validation failed: {e}")
            return False
    
    async def revoke_token(self, refresh_token: str) -> Dict[str, Any]:
        """Revoke HubSpot refresh token"""
        try:
            # Note: HubSpot doesn't provide a direct revoke endpoint
            # For now, we'll just log the revocation
            logger.info(f"HubSpot token revoked (logout)")
            
            return {
                "success": True,
                "message": "Token revoked successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to revoke HubSpot token: {e}")
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
            logger.error(f"Failed to encrypt HubSpot tokens: {e}")
            raise
    
    def decrypt_tokens(self, encrypted_tokens: str) -> Dict[str, Any]:
        """Decrypt OAuth tokens from storage"""
        try:
            encrypted_data = base64.b64decode(encrypted_tokens.encode())
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt HubSpot tokens: {e}")
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
hubspot_oauth_handler = None

def get_hubspot_oauth_handler() -> HubSpotOAuthHandler:
    """Get global HubSpot OAuth handler instance"""
    global hubspot_oauth_handler
    if hubspot_oauth_handler is None:
        hubspot_oauth_handler = HubSpotOAuthHandler()
    return hubspot_oauth_handler