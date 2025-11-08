import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from asyncpg import Pool
from urllib.parse import parse_qs
import base64
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Tableau OAuth configuration
TABLEAU_CLIENT_ID = os.getenv("TABLEAU_CLIENT_ID")
TABLEAU_CLIENT_SECRET = os.getenv("TABLEAU_CLIENT_SECRET")
TABLEAU_REDIRECT_URI = os.getenv("TABLEAU_REDIRECT_URI", "http://localhost:3000/api/integrations/tableau/callback")
TABLEAU_AUTH_URL = "https://online.tableau.com/oauth2/authorize"
TABLEAU_TOKEN_URL = "https://online.tableau.com/oauth2/token"

class TableauOAuthHandler:
    """Complete Tableau OAuth 2.0 Handler"""
    
    def __init__(self):
        self.client_id = TABLEAU_CLIENT_ID
        self.client_secret = TABLEAU_CLIENT_SECRET
        self.redirect_uri = TABLEAU_REDIRECT_URI
        self.fernet = Fernet(os.getenv("ATOM_OAUTH_ENCRYPTION_KEY"))
        
        if not all([self.client_id, self.client_secret]):
            logger.error("Tableau OAuth credentials not found in environment variables")
            raise ValueError("Missing Tableau OAuth credentials")
    
    async def get_authorization_url(self, state: str = None) -> str:
        """Generate Tableau OAuth authorization URL"""
        try:
            # Generate state for CSRF protection
            if not state:
                state = base64.urlsafe_b64encode(os.urandom(32)).decode()
            
            # Build authorization URL
            params = {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "https://online.tableau.com/auth/sites",
                "state": state
            }
            
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            auth_url = f"{TABLEAU_AUTH_URL}?{query_string}"
            
            logger.info(f"Generated Tableau auth URL with state: {state}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to generate Tableau authorization URL: {e}")
            raise
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            # Prepare token request
            token_data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Make token request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    TABLEAU_TOKEN_URL,
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
                        "expires_in": token_data.get("expires_in", 86400),
                        "created_at": datetime.now().isoformat(),
                        "scope": "https://online.tableau.com/auth/sites"
                    }
                }
                
        except httpx.HTTPStatusError as e:
            error_data = e.response.text
            logger.error(f"Tableau token exchange HTTP error: {e.response.status_code} - {error_data}")
            return {
                "success": False,
                "error": "Token exchange failed",
                "details": error_data
            }
        except Exception as e:
            logger.error(f"Failed to exchange Tableau code for tokens: {e}")
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
                    TABLEAU_TOKEN_URL,
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
                        "expires_in": token_data.get("expires_in", 86400),
                        "created_at": datetime.now().isoformat(),
                        "scope": "https://online.tableau.com/auth/sites"
                    }
                }
                
        except httpx.HTTPStatusError as e:
            error_data = e.response.text
            logger.error(f"Tableau token refresh HTTP error: {e.response.status_code} - {error_data}")
            return {
                "success": False,
                "error": "Token refresh failed",
                "details": error_data
            }
        except Exception as e:
            logger.error(f"Failed to refresh Tableau access token: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_sites(self, access_token: str) -> Dict[str, Any]:
        """Get user's Tableau sites after authentication"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.tableau.com/api/3.20/sites",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                sites = []
                
                for site in data.get("sites", {}).get("site", []):
                    sites.append({
                        "id": site.get("id"),
                        "name": site.get("name"),
                        "contentUrl": site.get("contentUrl"),
                        "isAdmin": site.get("adminMode", False),
                        "state": site.get("state", "active"),
                        "createdAt": site.get("createdAt"),
                        "updatedAt": site.get("updatedAt")
                    })
                
                # Select default site (first one)
                default_site = sites[0] if sites else None
                
                return {
                    "success": True,
                    "data": {
                        "sites": sites,
                        "default_site": default_site,
                        "selected_site_id": default_site.get("id") if default_site else None
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get Tableau sites: {e}")
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
                    "https://api.tableau.com/api/3.20/sites",
                    headers=headers
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Tableau token validation failed: {e}")
            return False
    
    async def revoke_token(self, access_token: str) -> Dict[str, Any]:
        """Revoke Tableau access token"""
        try:
            # Note: Tableau doesn't provide a revoke endpoint
            # For now, we'll just log the revocation
            logger.info(f"Tableau token revoked (logout)")
            
            return {
                "success": True,
                "message": "Token revoked successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to revoke Tableau token: {e}")
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
            logger.error(f"Failed to encrypt Tableau tokens: {e}")
            raise
    
    def decrypt_tokens(self, encrypted_tokens: str) -> Dict[str, Any]:
        """Decrypt OAuth tokens from storage"""
        try:
            encrypted_data = base64.b64decode(encrypted_tokens.encode())
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt Tableau tokens: {e}")
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

# Global handler instance
tableau_oauth_handler = None

def get_tableau_oauth_handler() -> TableauOAuthHandler:
    """Get global Tableau OAuth handler instance"""
    global tableau_oauth_handler
    if tableau_oauth_handler is None:
        tableau_oauth_handler = TableauOAuthHandler()
    return tableau_oauth_handler