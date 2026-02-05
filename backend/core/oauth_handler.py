"""
Centralized OAuth 2.0 Handler
Provides reusable OAuth flow implementation for all integrations
"""

import logging
import os
from typing import Dict, Optional
import httpx
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)


class OAuthConfig:
    """OAuth configuration for an integration"""
    
    def __init__(
        self,
        client_id_env: str,
        client_secret_env: str,
        redirect_uri_env: str,
        auth_url: str,
        token_url: str,
        scopes: list[str],
        additional_params: Optional[Dict] = None
    ):
        self.client_id = os.getenv(client_id_env)
        self.client_secret = os.getenv(client_secret_env)
        self.redirect_uri = os.getenv(redirect_uri_env)
        self.auth_url = auth_url
        self.token_url = token_url
        self.scopes = scopes
        self.additional_params = additional_params or {}
    
    def is_configured(self) -> bool:
        """Check if OAuth credentials are configured"""
        return bool(self.client_id and self.client_secret and self.redirect_uri)


class OAuthHandler:
    """Handles OAuth 2.0 flow for integrations"""
    
    def __init__(self, config: OAuthConfig):
        self.config = config
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL"""
        if not self.config.is_configured():
            raise HTTPException(
                status_code=500,
                detail="OAuth not configured. Please set environment variables."
            )
        
        scope_str = " ".join(self.config.scopes)
        
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": scope_str,
            "response_type": "code",
            "access_type": "offline",  # For refresh tokens
        }
        
        if state:
            params["state"] = state
        
        # Add any additional OAuth provider-specific params
        params.update(self.config.additional_params)
        
        # Build query string
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.config.auth_url}?{query}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict:
        """Exchange authorization code for access tokens"""
        if not self.config.is_configured():
            raise HTTPException(
                status_code=500,
                detail="OAuth not configured. Please set environment variables."
            )
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }
        
        headers = {"Accept": "application/json"}
        
        # Notion requires Basic Auth for exchanging code
        if "api.notion.com" in self.config.token_url:
            import base64
            auth_str = f"{self.config.client_id}:{self.config.client_secret}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_auth}"
        else:
            # Default: include client credentials in the body
            data["client_id"] = self.config.client_id
            data["client_secret"] = self.config.client_secret
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.token_url,
                    data=data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to exchange code for tokens: {response.text}"
                    )
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"OAuth token request failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to OAuth provider: {str(e)}"
            )
    
    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """Refresh access token using refresh token"""
        if not self.config.is_configured():
            raise HTTPException(
                status_code=500,
                detail="OAuth not configured. Please set environment variables."
            )
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.token_url,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Token refresh failed: {response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to refresh token: {response.text}"
                    )
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"OAuth refresh request failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to OAuth provider: {str(e)}"
            )


# Pre-configured OAuth handlers for major integrations

GOOGLE_OAUTH_CONFIG = OAuthConfig(
    client_id_env="GOOGLE_CLIENT_ID",
    client_secret_env="GOOGLE_CLIENT_SECRET",
    redirect_uri_env="GOOGLE_REDIRECT_URI",
    auth_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ]
)

MICROSOFT_OAUTH_CONFIG = OAuthConfig(
    client_id_env="MICROSOFT_CLIENT_ID",
    client_secret_env="MICROSOFT_CLIENT_SECRET",
    redirect_uri_env="MICROSOFT_REDIRECT_URI",
    auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    scopes=[
        "https://graph.microsoft.com/Calendars.ReadWrite",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Files.ReadWrite.All",
        "https://graph.microsoft.com/User.Read",
    ]
)

SALESFORCE_OAUTH_CONFIG = OAuthConfig(
    client_id_env="SALESFORCE_CLIENT_ID",
    client_secret_env="SALESFORCE_CLIENT_SECRET",
    redirect_uri_env="SALESFORCE_REDIRECT_URI",
    auth_url="https://login.salesforce.com/services/oauth2/authorize",
    token_url="https://login.salesforce.com/services/oauth2/token",
    scopes=["full", "refresh_token"]
)

SLACK_OAUTH_CONFIG = OAuthConfig(
    client_id_env="SLACK_CLIENT_ID",
    client_secret_env="SLACK_CLIENT_SECRET",
    redirect_uri_env="SLACK_REDIRECT_URI",
    auth_url="https://slack.com/oauth/v2/authorize",
    token_url="https://slack.com/api/oauth.v2.access",
    scopes=[
        "chat:write",
        "channels:read",
        "channels:history",
        "users:read",
        "files:write",
    ]
)

GITHUB_OAUTH_CONFIG = OAuthConfig(
    client_id_env="GITHUB_CLIENT_ID",
    client_secret_env="GITHUB_CLIENT_SECRET",
    redirect_uri_env="GITHUB_REDIRECT_URI",
    auth_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",
    scopes=["repo", "user", "workflow"]
)

ASANA_OAUTH_CONFIG = OAuthConfig(
    client_id_env="ASANA_CLIENT_ID",
    client_secret_env="ASANA_CLIENT_SECRET",
    redirect_uri_env="ASANA_REDIRECT_URI",
    auth_url="https://app.asana.com/-/oauth_authorize",
    token_url="https://app.asana.com/-/oauth_token",
    scopes=["default", "openid", "email", "profile"]
)

NOTION_OAUTH_CONFIG = OAuthConfig(
    client_id_env="NOTION_CLIENT_ID",
    client_secret_env="NOTION_CLIENT_SECRET",
    redirect_uri_env="NOTION_REDIRECT_URI",
    auth_url="https://api.notion.com/v1/oauth/authorize",
    token_url="https://api.notion.com/v1/oauth/token",
    scopes=[]  # Notion selects scopes during auth flow UI
)

TRELLO_OAUTH_CONFIG = OAuthConfig(
    client_id_env="TRELLO_API_KEY",
    client_secret_env="TRELLO_API_SECRET",
    redirect_uri_env="TRELLO_REDIRECT_URI",
    auth_url="https://trello.com/1/OAuthAuthorizeToken",
    token_url="https://trello.com/1/OAuthGetAccessToken",
    scopes=["read,write"],
    additional_params={"expiration": "never", "name": "Atom App"}
)

DROPBOX_OAUTH_CONFIG = OAuthConfig(
    client_id_env="DROPBOX_CLIENT_ID",
    client_secret_env="DROPBOX_CLIENT_SECRET",
    redirect_uri_env="DROPBOX_REDIRECT_URI",
    auth_url="https://www.dropbox.com/oauth2/authorize",
    token_url="https://api.dropboxapi.com/oauth2/token",
    scopes=["files.metadata.write", "files.content.write", "files.content.read"]
)
