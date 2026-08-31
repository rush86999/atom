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
from fastapi import Depends, HTTPException
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
    # Forms/Flow are webhook-push apps (no public read API) — the webhook
    # secret is the credential that makes their data flow, so it is the
    # honest "connected via env" signal. Never added to _PING_SPEC.
    "zoho-forms": ["ZOHOFORMS_WEBHOOK_SECRET"],
    "zoho-flow": ["ZOHOFLOW_WEBHOOK_SECRET"],
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
    "google": ["gmail", "gdrive", "google-workspace"],
    # One Zoho app grant covers the suite (same fan-out as the callback).
    # Forms/Flow are webhook-push, but they are part of the same Zoho
    # account, so the suite grant lights their cards like the siblings.
    "zoho": [
        "zoho-books",
        "zoho-crm",
        "zoho-inventory",
        "zoho-mail",
        "zoho-projects",
        "zoho-workdrive",
        "zoho-forms",
        "zoho-flow",
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
    "zoho-forms": ("Zoho Forms", "productivity"),
    "zoho-flow": ("Zoho Flow", "automation"),
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


# =============================================================================
# Data-ingestion status (communication memory pipeline)
# =============================================================================

# Catalog provider id -> app_type in the communication ingestion pipeline
# (integrations/atom_communication_ingestion_pipeline.CommunicationAppType).
# Only these integrations ingest records into the memory store today.
_INGESTION_APP_TYPES: Dict[str, str] = {
    "outlook": "outlook",
    "gmail": "gmail",
    "slack": "slack",
    "teams": "microsoft_teams",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "discord": "discord",
    "notion": "notion",
    "linear": "linear",
    "dropbox": "dropbox",
    "box": "box",
    "asana": "asana",
    "salesforce": "salesforce",
    "zoom": "zoom",
    "xero": "xero",
    "quickbooks": "quickbooks",
    "zoho-books": "zoho",
    "zoho-crm": "zoho",
    "zoho-inventory": "zoho",
    "zoho-mail": "zoho",
    "zoho-projects": "zoho",
    "zoho-workdrive": "zoho",
}

# Integrations with a restartable polling stream — every app that has a
# real _fetch_new_messages implementation in the pipeline (which is what
# makes polling meaningful). The start endpoint maps catalog id -> memory
# app_type and calls ingestion_pipeline.start_poller(app_type).
_POLLER_APP_TYPES: Dict[str, str] = {
    "outlook": "outlook",
    "gmail": "gmail",
    "slack": "slack",
    "teams": "microsoft_teams",
    "whatsapp": "whatsapp",
    "discord": "discord",
}

# Integrations that sync records through HybridDataIngestionService (its
# DEFAULT_SYNC_CONFIGS keys). These report last_synced/auto-sync state even
# though they have no communication-memory poller.
_HYBRID_SYNC_INTEGRATIONS = frozenset(
    {
        "salesforce",
        "hubspot",
        "slack",
        "gmail",
        "notion",
        "jira",
        "google_calendar",
        "zendesk",
        "zoho",
        "shopify",
        "onedrive",
        "google_drive",
        "telegram",
    }
)


def _hybrid_sync_entry(current_user: User, integration_id: str) -> Dict[str, Any]:
    """Hybrid sync-service state for one integration (may be all-None).

    Complements the communication memory pipeline: business integrations
    (salesforce, hubspot, jira, zendesk, …) sync records through
    HybridDataIngestionService rather than the memory pollers. Never raises.
    """
    empty = {
        "last_synced": None,
        "auto_sync_enabled": False,
        "sync_frequency_minutes": None,
    }
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        from core.personal_scope import resolve_workspace_id

        service = get_hybrid_ingestion_service(resolve_workspace_id(current_user))
        stats = service.usage_stats.get(integration_id)
        if not stats:
            return empty
        return {
            "last_synced": _iso_or_none(getattr(stats, "last_synced", None)),
            "auto_sync_enabled": bool(getattr(stats, "auto_sync_enabled", False)),
            "sync_frequency_minutes": getattr(stats, "sync_frequency_minutes", None),
        }
    except Exception as e:
        logger.debug(f"Hybrid sync status unavailable for {integration_id}: {e}")
        return empty


def _iso_or_none(value: Any) -> Optional[str]:
    """Serialize LanceDB/pandas timestamps (datetime, Timestamp, NaT, None)."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return None
    text = str(value)
    if text.lower() in ("nat", "none", ""):
        return None
    return text


def _ingestion_snapshot() -> Dict[str, Any]:
    """Stats from the communication memory pipeline, or an unavailable marker.

    Never raises — LanceDB or the pipeline being down must not 500 the
    Integrations page; the UI degrades to "ingestion unavailable".
    """
    unavailable = {
        "available": False,
        "active_streams": [],
        "app_stats": {},
    }
    try:
        from integrations.atom_communication_ingestion_pipeline import (
            ingestion_pipeline,
        )
    except Exception as e:
        logger.warning(f"Communication ingestion pipeline unavailable: {e}")
        return unavailable
    try:
        stats = ingestion_pipeline.get_ingestion_stats()
    except Exception as e:
        logger.warning(f"get_ingestion_stats failed: {e}")
        return unavailable
    if not isinstance(stats, dict) or "error" in stats:
        logger.warning(f"get_ingestion_stats error: {stats}")
        return unavailable
    return {
        "available": True,
        "active_streams": stats.get("active_streams") or [],
        "app_stats": stats.get("app_stats") or {},
    }


def _app_entry(app_stats: Dict[str, Any], app_type: str) -> Dict[str, Any]:
    entry = app_stats.get(app_type) or {}
    return {
        "records_ingested": int(entry.get("total_messages") or 0),
        "last_ingested": _iso_or_none(entry.get("last_ingested")),
        "ingestion_status": entry.get("status"),
    }


def _integration_ingestion_payload(
    integration_id: str,
    sources: Dict[str, Dict[str, Any]],
    snapshot: Dict[str, Any],
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    source = sources.get(integration_id) or {"connected": False, "source": "none"}
    app_type = _INGESTION_APP_TYPES.get(integration_id)
    payload: Dict[str, Any] = {
        "integration_id": integration_id,
        "app_type": app_type,
        "connected": bool(source.get("connected")),
        "connection_source": source.get("source"),
        "ingestion_available": snapshot["available"],
        "stream_running": False,
        "records_ingested": 0,
        "last_ingested": None,
        "ingestion_status": None,
    }
    if app_type:
        payload["stream_running"] = app_type in (snapshot["active_streams"] or [])
        payload.update(_app_entry(snapshot["app_stats"], app_type))
    # Hybrid sync state (business integrations sync through
    # HybridDataIngestionService, not the memory pollers).
    payload.update(_hybrid_sync_entry(current_user, integration_id))
    return payload


@router.get("/ingestion-status")
async def get_ingestion_status_all(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Batch ingestion progress for the Integrations page cards.

    Keyed by catalog integration id (app_types with no catalog id pass
    through unchanged), so clients can look cards up directly. Every mapped
    integration is present (zero-filled when it has no data yet), plus any
    hybrid-sync-only integrations that have sync state.
    """
    snapshot = _ingestion_snapshot()
    id_by_app_type = {v: k for k, v in _INGESTION_APP_TYPES.items()}
    apps: Dict[str, Dict[str, Any]] = {}

    # Zero-fill every mapped integration so clients can rely on the shape.
    for key, app_type in _INGESTION_APP_TYPES.items():
        apps[key] = {
            "app_type": app_type,
            "records_ingested": 0,
            "last_ingested": None,
            "ingestion_status": None,
            "stream_running": False,
            "last_synced": None,
            "auto_sync_enabled": False,
            "sync_frequency_minutes": None,
        }
    # Memory-pipeline stats override the zero fill; uncatalogued app types
    # (crm_lead, sms, …) pass through with their raw app_type as the key.
    for app_type in snapshot["app_stats"].keys():
        key = id_by_app_type.get(app_type, app_type)
        apps.setdefault(
            key,
            {
                "app_type": app_type,
                "last_synced": None,
                "auto_sync_enabled": False,
                "sync_frequency_minutes": None,
            },
        )
        apps[key].update(
            {
                "app_type": app_type,
                **_app_entry(snapshot["app_stats"], app_type),
                "stream_running": app_type in (snapshot["active_streams"] or []),
            }
        )
    # Hybrid sync state for integrations without memory stats.
    if current_user is not None:
        for integration_id in set(apps.keys()) | _HYBRID_SYNC_INTEGRATIONS:
            entry = _hybrid_sync_entry(current_user, integration_id)
            if not any(entry.values()):
                continue
            apps.setdefault(
                integration_id,
                {
                    "app_type": _INGESTION_APP_TYPES.get(integration_id),
                    "records_ingested": 0,
                    "last_ingested": None,
                    "ingestion_status": None,
                    "stream_running": False,
                },
            )
            apps[integration_id].update(entry)
    return {
        "available": snapshot["available"],
        "active_streams": snapshot["active_streams"],
        "total_records_ingested": sum(
            a["records_ingested"] for a in apps.values()
        ),
        "apps": apps,
    }


@router.get("/{integration_id}/ingestion-status")
async def get_integration_ingestion_status(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Connection truth + ingestion progress for one integration."""
    sources = _connection_sources(current_user, tenant, db)
    snapshot = _ingestion_snapshot()
    return _integration_ingestion_payload(
        integration_id, sources, snapshot, current_user
    )


@router.post("/{integration_id}/ingestion/start")
async def start_integration_ingestion(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """(Re)start the ingestion poller for an integration.

    The poller otherwise starts only at the OAuth callback or on backend
    startup — if it dies or the backend predates the connection, this is
    the recovery path. Idempotent: an already-running stream is a no-op.
    """
    app_type = _POLLER_APP_TYPES.get(integration_id)
    if app_type is None:
        raise HTTPException(
            status_code=404,
            detail=f"No restartable ingestion poller for '{integration_id}'",
        )

    sources = _connection_sources(current_user, tenant, db)
    if not (sources.get(integration_id) or {}).get("connected"):
        raise HTTPException(
            status_code=409,
            detail="No active connection for this integration — connect it first",
        )

    try:
        from integrations.atom_communication_ingestion_pipeline import (
            ingestion_pipeline,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Ingestion pipeline unavailable: {e}"
        )

    started = bool(ingestion_pipeline.start_poller(app_type))
    snapshot = _ingestion_snapshot()
    payload = _integration_ingestion_payload(
        integration_id, sources, snapshot, current_user
    )
    payload["start_attempted"] = True
    payload["stream_running"] = payload["stream_running"] or started
    return payload
