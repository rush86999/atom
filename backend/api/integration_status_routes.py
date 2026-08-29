"""Real per-integration connection status for the Integrations pages.

The Integrations page's cards previously showed "connected" based on
integration health-endpoint HTTP 200s — i.e. "the backend route exists",
not "this integration is actually connected". These endpoints aggregate
the real truth sources:

1. ``UserConnection`` rows — connections made through the app via
   connection_service (OAuth flows, API-key forms)
2. ``TenantIntegration`` rows — tenant-scoped connectors
3. ``IntegrationToken`` rows — OAuth grants persisted by the generic OAuth
   callback (api/oauth_routes.py): Microsoft ("microsoft" + "outlook"),
   Google, and the Zoho fan-out — not UserConnection rows
4. Provider credentials in the backend environment — integrations that work
   via API keys/tokens without an in-app connect flow. Only credential-type
   env vars count (tokens/API keys): CLIENT_ID/SECRET pairs are OAuth
   *setup*, not a connection.

``GET /health-status`` additionally *verifies* a connection by making one
real, read-only API call to the provider when a usable credential exists.
The legacy ``get_integration_health`` stubs (integration_health_endpoints.py
/ api_legacy_health.py) hardcode ``configured: True`` for every provider and
must not be used to decide "connected" or "healthy".
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from core.auth import get_current_tenant, get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import IntegrationToken, Tenant, TenantIntegration, UserConnection

router = BaseAPIRouter(prefix="/api/integrations", tags=["integration-status"])
logger = logging.getLogger(__name__)

# Catalog provider id -> credential env vars. ANY non-empty var marks the
# integration as connected via environment credentials. Keep these to
# secret/credential vars — client ids/secrets alone are not a connection.
_ENV_CREDENTIALS: Dict[str, list] = {
    "airtable": ["AIRTABLE_API_KEY", "AIRTABLE_ACCESS_TOKEN", "AIRTABLE_TOKEN"],
    "asana": ["ASANA_ACCESS_TOKEN"],
    "azure": ["AZURE_ACCESS_TOKEN", "AZURE_AD_TOKEN"],
    "bitbucket": ["BITBUCKET_API_TOKEN", "BITBUCKET_ACCESS_TOKEN", "BITBUCKET_APP_PASSWORD"],
    "discord": ["DISCORD_BOT_TOKEN"],
    "dropbox": ["DROPBOX_ACCESS_TOKEN"],
    "freshdesk": ["FRESHDESK_API_KEY"],
    "gdrive": ["GOOGLE_DRIVE_ACCESS_TOKEN"],
    "github": ["GITHUB_ACCESS_TOKEN", "GITHUB_TOKEN"],
    "gitlab": ["GITLAB_ACCESS_TOKEN", "GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_API_TOKEN"],
    "intercom": ["INTERCOM_ACCESS_TOKEN"],
    "jira": ["JIRA_API_TOKEN"],
    "mailchimp": ["MAILCHIMP_API_KEY"],
    "microsoft365": ["MICROSOFT_ACCESS_TOKEN", "MSGRAPH_ACCESS_TOKEN"],
    "monday": ["MONDAY_API_TOKEN", "MONDAY_ACCESS_TOKEN"],
    "notion": ["NOTION_ACCESS_TOKEN", "NOTION_API_KEY", "NOTION_TOKEN"],
    "onedrive": ["ONEDRIVE_ACCESS_TOKEN"],
    "outlook": ["OUTLOOK_ACCESS_TOKEN"],
    "quickbooks": ["QUICKBOOKS_ACCESS_TOKEN"],
    "salesforce": ["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_SECURITY_TOKEN"],
    "shopify": ["SHOPIFY_ACCESS_TOKEN", "SHOPIFY_API_KEY"],
    "slack": ["SLACK_BOT_TOKEN", "SLACK_TOKEN"],
    "stripe": ["STRIPE_API_KEY"],
    "tableau": ["TABLEAU_ACCESS_TOKEN", "TABLEAU_PERSONAL_ACCESS_TOKEN", "TABLEAU_TOKEN"],
    "teams": ["TEAMS_ACCESS_TOKEN"],
    "telegram": ["TELEGRAM_BOT_TOKEN"],
    "trello": ["TRELLO_ACCESS_TOKEN", "TRELLO_OAUTH_TOKEN", "TRELLO_API_KEY"],
    "whatsapp": ["WHATSAPP_ACCESS_TOKEN"],
    "xero": ["XERO_ACCESS_TOKEN"],
    "zendesk": ["ZENDESK_API_TOKEN", "ZENDESK_ACCESS_TOKEN"],
    "zoho-books": ["ZOHO_ACCESS_TOKEN", "ZOHO_REFRESH_TOKEN"],
    "zoho-crm": ["ZOHO_ACCESS_TOKEN", "ZOHO_REFRESH_TOKEN"],
    "zoho-inventory": ["ZOHO_ACCESS_TOKEN", "ZOHO_REFRESH_TOKEN"],
    "zoho-mail": ["ZOHO_ACCESS_TOKEN", "ZOHO_REFRESH_TOKEN"],
    "zoho-projects": ["ZOHO_ACCESS_TOKEN", "ZOHO_REFRESH_TOKEN"],
    "zoho-workdrive": ["ZOHO_ACCESS_TOKEN", "ZOHO_REFRESH_TOKEN"],
    "hubspot": ["HUBSPOT_ACCESS_TOKEN", "HUBSPOT_PRIVATE_APP_TOKEN", "HUBSPOT_TOKEN"],
}

# Providers that can appear in /health-status even without env credentials
# (they can still be connected via UserConnection / TenantIntegration).
_EXTRA_PROVIDERS = {"gmail"}

# IntegrationToken.provider -> catalog ids for names that don't map 1:1. The
# generic OAuth callback (api/oauth_routes.py) persists grants here as
# "microsoft"+"outlook", "google", and the zoho_* fan-out — NOT as
# UserConnection rows — so these rows are the real "connected via OAuth"
# signal for the Microsoft/Google/Zoho suites. Unlisted providers (slack,
# github, box, …) map to themselves.
_IT_PROVIDER_ALIASES: Dict[str, List[str]] = {
    # One Microsoft Graph consent covers every Graph-backed integration.
    "microsoft": ["microsoft365", "outlook", "onedrive", "teams"],
    "google": ["gmail", "gdrive"],
    # One Zoho app grant covers the suite (same fan-out as the callback).
    "zoho": [
        "zoho-books",
        "zoho-crm",
        "zoho-inventory",
        "zoho-mail",
        "zoho-projects",
        "zoho-workdrive",
    ],
    "zoho_books": ["zoho-books"],
    "zoho_crm": ["zoho-crm"],
    "zoho_inventory": ["zoho-inventory"],
    "zoho_workdrive": ["zoho-workdrive"],
}

# Provider id -> (display name, category) for clients rendering the catalog.
_PROVIDER_META: Dict[str, Tuple[str, str]] = {
    "airtable": ("Airtable", "productivity"),
    "asana": ("Asana", "productivity"),
    "azure": ("Azure", "cloud"),
    "bitbucket": ("Bitbucket", "development"),
    "discord": ("Discord", "communication"),
    "dropbox": ("Dropbox", "storage"),
    "freshdesk": ("Freshdesk", "support"),
    "gdrive": ("Google Drive", "storage"),
    "github": ("GitHub", "development"),
    "gitlab": ("GitLab", "development"),
    "gmail": ("Gmail", "communication"),
    "hubspot": ("HubSpot", "crm"),
    "intercom": ("Intercom", "support"),
    "jira": ("Jira", "productivity"),
    "mailchimp": ("Mailchimp", "marketing"),
    "microsoft365": ("Microsoft 365", "productivity"),
    "monday": ("Monday.com", "productivity"),
    "notion": ("Notion", "productivity"),
    "onedrive": ("OneDrive", "storage"),
    "outlook": ("Outlook", "communication"),
    "quickbooks": ("QuickBooks", "finance"),
    "salesforce": ("Salesforce", "crm"),
    "shopify": ("Shopify", "ecommerce"),
    "slack": ("Slack", "communication"),
    "stripe": ("Stripe", "finance"),
    "tableau": ("Tableau", "analytics"),
    "teams": ("Microsoft Teams", "communication"),
    "telegram": ("Telegram", "communication"),
    "trello": ("Trello", "productivity"),
    "whatsapp": ("WhatsApp", "communication"),
    "xero": ("Xero", "finance"),
    "zendesk": ("Zendesk", "support"),
    "zoho-books": ("Zoho Books", "finance"),
    "zoho-crm": ("Zoho CRM", "crm"),
    "zoho-inventory": ("Zoho Inventory", "ecommerce"),
    "zoho-mail": ("Zoho Mail", "communication"),
    "zoho-projects": ("Zoho Projects", "productivity"),
    "zoho-workdrive": ("Zoho WorkDrive", "storage"),
}

# Real, read-only "does this credential actually work" calls. A provider is
# only listed here when a single credential (bearer/API key) is sufficient —
# providers needing a subdomain/realm/instance (Zendesk, QuickBooks, Xero,
# Shopify, …) are reported connected-unverified instead of pretending.
_PING_SPEC: Dict[str, Dict[str, Any]] = {
    "airtable": {"method": "GET", "url": "https://api.airtable.com/v0/meta/whoami"},
    "asana": {"method": "GET", "url": "https://app.asana.com/api/1.0/users/me"},
    "azure": {"method": "GET", "url": "https://graph.microsoft.com/v1.0/organization"},
    "bitbucket": {"method": "GET", "url": "https://api.bitbucket.org/2.0/user"},
    "box": {"method": "GET", "url": "https://api.box.com/2.0/users/me"},
    "discord": {"method": "GET", "url": "https://discord.com/api/v10/users/@me"},
    "dropbox": {"method": "POST", "url": "https://api.dropboxapi.com/2/users/get_current_account"},
    "gdrive": {
        "method": "GET",
        "url": "https://www.googleapis.com/drive/v3/about?fields=user",
    },
    "github": {"method": "GET", "url": "https://api.github.com/user"},
    "gitlab": {"method": "GET", "url": "https://gitlab.com/api/v4/user"},
    "hubspot": {
        "method": "GET",
        "url": "https://api.hubapi.com/crm/v3/objects/contacts?limit=1",
    },
    "intercom": {"method": "GET", "url": "https://api.intercom.io/me"},
    "jira": {"method": "GET", "url": "https://api.atlassian.com/me"},
    "microsoft365": {"method": "GET", "url": "https://graph.microsoft.com/v1.0/me"},
    "monday": {
        "method": "POST",
        "url": "https://api.monday.com/v2",
        "json": {"query": "me { id }"},
    },
    "notion": {
        "method": "GET",
        "url": "https://api.notion.com/v1/users/me",
        "headers": {"Notion-Version": "2022-06-28"},
    },
    "onedrive": {"method": "GET", "url": "https://graph.microsoft.com/v1.0/me"},
    "outlook": {"method": "GET", "url": "https://graph.microsoft.com/v1.0/me"},
    "slack": {"method": "POST", "url": "https://slack.com/api/auth.test"},
    "stripe": {"method": "GET", "url": "https://api.stripe.com/v1/balance"},
    "teams": {"method": "GET", "url": "https://graph.microsoft.com/v1.0/me"},
    "telegram": {"method": "GET", "url": "https://api.telegram.org/bot{token}/getMe"},
    "trello": {"method": "GET", "url": "https://api.trello.com/1/members/me"},
    "whatsapp": {"method": "GET", "url": "https://graph.facebook.com/v18.0/me"},
}

_PING_TIMEOUT = 5.0

# Credential-key preferences when pulling a token out of a UserConnection
# credentials JSON blob (piece-specific key names vary).
_TOKEN_KEY_ORDER = (
    "access_token",
    "bot_token",
    "api_key",
    "apiKey",
    "api_token",
    "personal_access_token",
    "oauth_token",
    "token",
    "secret",
)


def _normalize_integration_id(raw: str) -> str:
    """Map Activepieces-style ids ("@activepieces/piece-slack") to catalog ids."""
    value = (raw or "").strip().lower()
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    return value.replace("piece-", "")


def _token_from_credentials(credentials: Any) -> Optional[str]:
    if not isinstance(credentials, dict):
        return None
    for key in _TOKEN_KEY_ORDER:
        value = credentials.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key, value in credentials.items():
        if (
            isinstance(value, str)
            and value.strip()
            and any(part in key.lower() for part in ("token", "key", "secret"))
        ):
            return value.strip()
    return None


def _connection_sources(
    current_user: User, tenant: Tenant, db: Session
) -> Dict[str, Dict[str, Any]]:
    """provider id -> {"connected": bool, "source": str} from real state."""
    providers: Dict[str, Dict[str, Any]] = {}

    def mark(provider_id: str, source: str) -> None:
        entry = providers.setdefault(provider_id, {"connected": False, "source": "none"})
        # DB connections are the strongest signal; keep the first one found.
        if not entry["connected"]:
            entry["connected"] = True
            entry["source"] = source

    # 1. In-app connections (connection_service writes UserConnection).
    try:
        for row in (
            db.query(UserConnection)
            .filter(UserConnection.user_id == current_user.id)
            .filter(UserConnection.status == "active")
            .all()
        ):
            mark(_normalize_integration_id(row.integration_id), "user_connection")
    except Exception as e:
        logger.warning(f"UserConnection lookup failed: {e}")

    # 2. Tenant-scoped connectors.
    try:
        for row in (
            db.query(TenantIntegration)
            .filter(TenantIntegration.tenant_id == tenant.id)
            .all()
        ):
            connector_id = getattr(row, "connector_id", None) or getattr(
                row, "integration_id", None
            )
            if connector_id:
                mark(_normalize_integration_id(connector_id), "tenant_integration")
    except Exception as e:
        logger.warning(f"TenantIntegration lookup failed: {e}")

    # 3. OAuth grants (IntegrationToken — written by the OAuth callback,
    #    not by connection_service).
    try:
        for row in (
            db.query(IntegrationToken)
            .filter(IntegrationToken.user_id == current_user.id)
            .filter(IntegrationToken.status == "active")
            .all()
        ):
            provider = _normalize_integration_id(getattr(row, "provider", "") or "")
            for provider_id in _IT_PROVIDER_ALIASES.get(provider, [provider]):
                if provider_id:
                    mark(provider_id, "oauth_token")
    except Exception as e:
        logger.warning(f"IntegrationToken lookup failed: {e}")

    # 4. Environment credentials.
    for provider_id, env_vars in _ENV_CREDENTIALS.items():
        if any(os.getenv(var) for var in env_vars):
            mark(provider_id, "env")

    return providers


def _resolve_token(
    provider_id: str, sources: Dict[str, Dict[str, Any]], db_tokens: Dict[str, str]
) -> Optional[str]:
    for env_var in _ENV_CREDENTIALS.get(provider_id, []):
        value = os.getenv(env_var)
        if value and value.strip():
            return value.strip()
    return db_tokens.get(provider_id)


async def _ping_provider(
    provider_id: str, token: str
) -> Tuple[bool, Optional[int], Optional[str]]:
    """One real provider API call. Returns (reachable, response_time_ms, error)."""
    spec = _PING_SPEC[provider_id]
    url = spec["url"].format(token=token)
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(spec.get("headers", {}))

    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=_PING_TIMEOUT) as client:
            response = await client.request(
                spec["method"],
                url,
                headers=headers,
                json=spec.get("json"),
            )
        elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)
        if response.status_code < 400:
            return True, elapsed_ms, None
        return False, elapsed_ms, f"HTTP {response.status_code}"
    except Exception as e:
        elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)
        return False, elapsed_ms, str(e) or type(e).__name__


@router.get("/connection-status")
async def get_connection_status(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Connected/not per integration, from real state — no health probes."""
    sources = _connection_sources(current_user, tenant, db)
    return {"providers": sources}


@router.get("/health-status")
async def get_health_status(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Real per-integration health for the health dashboard.

    status is one of:
    - "not_connected": no UserConnection / TenantIntegration / env credential
    - "connected":     connected, but the credential can't be exercised with
                       one call (subdomain/realm/refresh-flow providers) —
                       reported unverified, never as healthy
    - "healthy":       connected AND a real provider API call succeeded
    - "unreachable":   connected AND a real provider API call failed
    """
    now = datetime.now(timezone.utc).isoformat()
    sources = _connection_sources(current_user, tenant, db)

    # Tokens stored on in-app connections, for providers without env creds.
    db_tokens: Dict[str, str] = {}
    try:
        for row in (
            db.query(UserConnection)
            .filter(UserConnection.user_id == current_user.id)
            .filter(UserConnection.status == "active")
            .all()
        ):
            provider_id = _normalize_integration_id(row.integration_id)
            if provider_id in db_tokens:
                continue
            token = _token_from_credentials(getattr(row, "credentials", None))
            if token:
                db_tokens[provider_id] = token
    except Exception as e:
        logger.warning(f"UserConnection token lookup failed: {e}")

    catalog: List[str] = list(_ENV_CREDENTIALS.keys()) + sorted(
        _EXTRA_PROVIDERS - set(_ENV_CREDENTIALS.keys())
    )

    async def build(provider_id: str) -> Tuple[str, Dict[str, Any]]:
        name, category = _PROVIDER_META.get(
            provider_id, (provider_id.replace("-", " ").title(), "other")
        )
        entry: Dict[str, Any] = {
            "name": name,
            "category": category,
            "connected": False,
            "source": "none",
            "status": "not_connected",
            "verified": False,
            "response_time_ms": None,
            "error": None,
            "checked_at": None,
        }
        source = sources.get(provider_id)
        if not source or not source.get("connected"):
            return provider_id, entry

        entry.update(connected=True, source=source["source"], checked_at=now)
        token = _resolve_token(provider_id, sources, db_tokens)
        if provider_id not in _PING_SPEC or not token:
            entry["status"] = "connected"
            return provider_id, entry

        reachable, elapsed_ms, error = await _ping_provider(provider_id, token)
        entry.update(
            verified=True,
            response_time_ms=elapsed_ms,
            error=error,
            status="healthy" if reachable else "unreachable",
        )
        return provider_id, entry

    results = await asyncio.gather(*(build(pid) for pid in catalog))
    providers = dict(results)
    return {"checked_at": now, "providers": providers}
