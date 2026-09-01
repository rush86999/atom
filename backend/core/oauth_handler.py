"""
Centralized OAuth 2.0 Handler
Provides reusable OAuth flow implementation for all integrations
"""

import os
import logging
import os
from typing import Dict, Optional
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
import httpx

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
        self._client_id_env = client_id_env
        self._client_secret_env = client_secret_env
        self._redirect_uri_env = redirect_uri_env
        self.auth_url = auth_url
        self.token_url = token_url
        self.scopes = scopes
        self.additional_params = additional_params or {}

        # Journey/e2e overrides: point any provider's endpoints at a local
        # mock (same pattern as MICROSOFT_AUTHORITY_BASE / ZOHO_ACCOUNTS_BASE,
        # generalized). Derived from the client-id env name — GOOGLE_CLIENT_ID
        # -> GOOGLE_AUTHORIZE_URL / GOOGLE_TOKEN_URL (TRELLO_API_KEY ->
        # TRELLO_AUTHORIZE_URL). Unset in production.
        if client_id_env.endswith("_CLIENT_ID"):
            _prefix = client_id_env[: -len("_CLIENT_ID")]
        elif client_id_env.endswith("_API_KEY"):
            _prefix = client_id_env[: -len("_API_KEY")]
        else:
            _prefix = client_id_env
        self.auth_url = os.getenv(f"{_prefix}_AUTHORIZE_URL", self.auth_url)
        self.token_url = os.getenv(f"{_prefix}_TOKEN_URL", self.token_url)

    @property
    def client_id(self) -> Optional[str]:
        return os.getenv(self._client_id_env)

    @property
    def client_secret(self) -> Optional[str]:
        return os.getenv(self._client_secret_env)

    @property
    def redirect_uri(self) -> Optional[str]:
        return os.getenv(self._redirect_uri_env)
    
    def is_configured(self) -> bool:
        """Check if OAuth credentials are configured"""
        is_missing = []
        if not self.client_id: is_missing.append("CLIENT_ID")
        if not self.client_secret: is_missing.append("CLIENT_SECRET")
        if not self.redirect_uri: is_missing.append("REDIRECT_URI")
        
        if is_missing:
            logger.warning(f"OAuth partly disabled. Missing: {', '.join(is_missing)}")
            return False
        return True


class OAuthHandler:
    """Handles OAuth 2.0 flow for integrations"""
    
    def __init__(self, config: OAuthConfig):
        self.config = config
    
    def get_authorization_url(self, state: Optional[str] = None, prompt: Optional[str] = None) -> str:
        """Generate OAuth authorization URL.

        Args:
            state: OAuth state token.
            prompt: Optional provider ``prompt`` parameter — e.g.
                ``select_account`` forces the provider's account picker
                instead of silently reusing the signed-in session (the
                "Switch Account" flow). Providers that don't support it are
                unaffected when the caller omits it.
        """
        if not self.config.is_configured():
            missing = []
            if not self.config.client_id: missing.append("CLIENT_ID")
            if not self.config.client_secret: missing.append("CLIENT_SECRET")
            if not self.config.redirect_uri: missing.append("REDIRECT_URI")
            
            error_msg = f"OAuth not configured. Missing environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail=error_msg
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
        
        if prompt:
            params["prompt"] = prompt
        
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
                    # Bug 8 fix: response.text may contain access_token or internal
                    # details. Don't leak to the client.
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to exchange code for tokens (HTTP {response.status_code})"
                    )
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"OAuth token request failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal error"
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
                    # Bug 8 (refresh path): response.text may contain access
                    # tokens or internal provider details; do NOT leak it to
                    # the client. (The exchange_code_for_tokens path was already
                    # fixed for this; the refresh path was missed.)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to refresh token (HTTP {response.status_code})"
                    )
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"OAuth refresh request failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal error"
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
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/userinfo.email",
    ]
)




# Tenant-aware endpoints: single-tenant app registrations MUST use their
# tenant-specific endpoint — Microsoft rejects /common for single-tenant
# apps created after 2018 (AADSTS50194). Set MICROSOFT_TENANT_ID (tenant
# GUID or verified domain); default 'common' only fits multi-tenant apps.
_MS_TENANT = os.getenv("MICROSOFT_TENANT_ID", "common")
# Authority override for self-contained journey/e2e environments (same
# pattern as ZOHO_ACCOUNTS_BASE): points the authorize/token endpoints at a
# local mock standing in for login.microsoftonline.com. Unset in production.
_MS_AUTHORITY = os.getenv(
    "MICROSOFT_AUTHORITY_BASE", "https://login.microsoftonline.com"
).rstrip("/")
MICROSOFT_OAUTH_CONFIG = OAuthConfig(
    client_id_env="MICROSOFT_CLIENT_ID",
    client_secret_env="MICROSOFT_CLIENT_SECRET",
    redirect_uri_env="MICROSOFT_REDIRECT_URI",
    auth_url=f"{_MS_AUTHORITY}/{_MS_TENANT}/oauth2/v2.0/authorize",
    token_url=f"{_MS_AUTHORITY}/{_MS_TENANT}/oauth2/v2.0/token",
    scopes=[
        "https://graph.microsoft.com/Calendars.ReadWrite",
        "https://graph.microsoft.com/Mail.ReadWrite",
        # Mail.Send is a SEPARATE Graph permission from Mail.ReadWrite —
        # without it /me/sendMail returns 403 notAllowed even though the
        # token can read and draft mail.
        "https://graph.microsoft.com/Mail.Send",
        "https://graph.microsoft.com/Files.ReadWrite.All",
        "https://graph.microsoft.com/Contacts.Read",
        "https://graph.microsoft.com/User.Read",
        "offline_access",
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

LINKEDIN_OAUTH_CONFIG = OAuthConfig(
    client_id_env="LINKEDIN_CLIENT_ID",
    client_secret_env="LINKEDIN_CLIENT_SECRET",
    redirect_uri_env="LINKEDIN_REDIRECT_URI",
    auth_url="https://www.linkedin.com/oauth/v2/authorization",
    token_url="https://www.linkedin.com/oauth/v2/accessToken",
    scopes=["r_liteprofile", "r_emailaddress", "w_member_social"]
)

WHATSAPP_OAUTH_CONFIG = OAuthConfig(
    client_id_env="WHATSAPP_CLIENT_ID",
    client_secret_env="WHATSAPP_CLIENT_SECRET",
    redirect_uri_env="WHATSAPP_REDIRECT_URI",
    auth_url="https://www.facebook.com/v17.0/dialog/oauth",
    token_url="https://graph.facebook.com/v17.0/oauth/access_token",
    scopes=["whatsapp_business_messaging", "whatsapp_business_management"]
)

# Zoho (Books + Inventory + CRM + WorkDrive) — server-based app OAuth flow.
# Requires a "Server-based application" client in the Zoho API console with
# redirect URI http://localhost:8001/api/v1/auth/oauth/zoho/callback (a
# "Self Client" has no redirect URI and can only hand out 10-min grant codes
# from the console UI, so it cannot drive the automatic flow).
_ZOHO_ACCOUNTS_BASE = os.getenv(
    "ZOHO_ACCOUNTS_BASE", "https://accounts.zoho.com"
).rstrip("/")
# ZOHO_OAUTH_SCOPES overrides the default grant (comma/space separated) — the
# .env documents "re-consent required after change", so the consent URL must
# reflect it. Keep ZohoProjects in the default set: the hybrid sync pulls
# Projects tasks alongside Books/Inventory/CRM.
_ZOHO_DEFAULT_SCOPES = [
    "ZohoBooks.fullaccess.all",
    "ZohoInventory.fullaccess.all",
    # CRM/Projects do NOT use the fullaccess.all pattern — Zoho rejects
    # unknown scope names with "Scope does not exist". Use the canonical
    # per-product names (verified in the pilot doc; same convention as
    # core/integrations/adapters/zoho.py).
    "ZohoCRM.modules.ALL",
    "ZohoProjects.portals.all",
    "ZohoProjects.projects.all",
    # WorkDrive scopes are `WorkDrive.` prefixed with `.ALL` permissions
    # (pilot doc §2). `ZohoWorkDrive.files.READ` / `...teamfolders.READ` are
    # NOT valid Zoho names — one unknown scope fails the whole consent URL.
    # WorkDrive.teams.READ is intentionally NOT in the defaults: the pilot
    # client (1000.9FTW…) rejects it with "Scope does not exist" until it is
    # enabled for the client in the Zoho API Console (api-console.zoho.ca →
    # client → scopes). Keep the defaults to the client-verified set.
    "WorkDrive.files.ALL",
    "WorkDrive.teamfolders.ALL",
]
_zoho_env_scopes = [
    s.strip()
    for s in os.getenv("ZOHO_OAUTH_SCOPES", "").replace(",", " ").split()
    if s.strip() and s.strip() != "offline_access"  # MS-ism; Zoho uses access_type=offline
]
ZOHO_OAUTH_CONFIG = OAuthConfig(
    client_id_env="ZOHO_CLIENT_ID",
    client_secret_env="ZOHO_CLIENT_SECRET",
    redirect_uri_env="ZOHO_REDIRECT_URI",
    auth_url=f"{_ZOHO_ACCOUNTS_BASE}/oauth/v2/auth",
    token_url=f"{_ZOHO_ACCOUNTS_BASE}/oauth/v2/token",
    scopes=_zoho_env_scopes or _ZOHO_DEFAULT_SCOPES,
)

BOX_OAUTH_CONFIG = OAuthConfig(
    client_id_env="BOX_CLIENT_ID",
    client_secret_env="BOX_CLIENT_SECRET",
    redirect_uri_env="BOX_REDIRECT_URI",
    auth_url="https://account.box.com/api/oauth2/authorize",
    token_url="https://api.box.com/oauth2/token",
    scopes=["root_readonly", "manage_app_users", "manage_webhook"],
)


# Provider → OAuthConfig map. Consumed by core/oauth_user_context for
# automatic token refresh. Configs snapshot the environment at import time,
# which matches when the individual *_OAUTH_CONFIG constants are read.
PROVIDER_CONFIGS: Dict[str, OAuthConfig] = {
    "google": GOOGLE_OAUTH_CONFIG,
    "microsoft": MICROSOFT_OAUTH_CONFIG,
    "salesforce": SALESFORCE_OAUTH_CONFIG,
    "slack": SLACK_OAUTH_CONFIG,
    "github": GITHUB_OAUTH_CONFIG,
    "asana": ASANA_OAUTH_CONFIG,
    "notion": NOTION_OAUTH_CONFIG,
    "trello": TRELLO_OAUTH_CONFIG,
    "dropbox": DROPBOX_OAUTH_CONFIG,
    "linkedin": LINKEDIN_OAUTH_CONFIG,
    "whatsapp": WHATSAPP_OAUTH_CONFIG,
    "zoho": ZOHO_OAUTH_CONFIG,
    "box": BOX_OAUTH_CONFIG,
}


