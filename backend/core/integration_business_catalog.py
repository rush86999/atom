"""Truthful business-integration catalog for the public integrations surface.

The historical ``GET /api/integrations`` response listed *API router modules*
(``workflow_ui``, ``atom_agent``, ``missing_endpoints``, …). That is an
implementation inventory, not the "46+ business integrations" a user is
promised, and counting it either overstates (97 internal modules) or
understates (41 connection-status cards).

This module derives a canonical provider catalog from evidence the product
actually ships, and records *why* each provider is listed:

  oauth      a provider OAuthConfig exists (real consent flow)
  adapter    a universal adapter module exists (service-layer execution)
  routes     a provider route module exists (callable API surface)
  env_key    a credential env var is wired (API-key provider)
  connection a provider id is served by connection-status

A provider is listed only when at least one of those resolves. Aliases and
duplicate adapter/route module names are canonicalised so the count is a count
of providers, not files.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Dict, List, Set

_BACKEND = Path(__file__).resolve().parents[1]

# Canonical id -> (display name, category, aliases)
_CANONICAL: Dict[str, tuple] = {
    "airtable": ("Airtable", "productivity", ()),
    "apollo": ("Apollo", "crm", ()),
    "asana": ("Asana", "productivity", ("asana_adapter",)),
    "azure": ("Azure", "cloud", ()),
    "bamboohr": ("BambooHR", "hr", ()),
    "bitbucket": ("Bitbucket", "development", ()),
    "box": ("Box", "storage", ()),
    "calendly": ("Calendly", "productivity", ()),
    "clickup": ("ClickUp", "productivity", ()),
    "confluence": ("Confluence", "productivity", ()),
    "deepgram": ("Deepgram", "ai", ()),
    "discord": ("Discord", "communication", ()),
    "dropbox": ("Dropbox", "storage", ()),
    "figma": ("Figma", "design", ()),
    "freshdesk": ("Freshdesk", "support", ()),
    "github": ("GitHub", "development", ()),
    "gitlab": ("GitLab", "development", ()),
    "gmail": ("Gmail", "communication", ()),
    "google_calendar": ("Google Calendar", "productivity", ()),
    "google_drive": ("Google Drive", "storage", ("gdrive",)),
    "google_workspace": ("Google Workspace", "productivity",
                         ("google", "google-workspace")),
    "gotomeeting": ("GoTo Meeting", "communication", ()),
    "hubspot": ("HubSpot", "crm", ("hubspot_adapter",)),
    "intercom": ("Intercom", "support", ()),
    "jira": ("Jira", "productivity", ()),
    "line": ("LINE", "communication", ("line_adapter",)),
    "linear": ("Linear", "productivity", ()),
    "linkedin": ("LinkedIn", "marketing", ()),
    "mailchimp": ("Mailchimp", "marketing", ()),
    "matrix": ("Matrix", "communication", ()),
    "messenger": ("Messenger", "communication", ("messenger_adapter",)),
    "microsoft365": ("Microsoft 365", "productivity", ("microsoft",)),
    "monday": ("Monday.com", "productivity", ()),
    "notion": ("Notion", "productivity", ("notion_adapter",)),
    "obsidian": ("Obsidian", "productivity", ()),
    "okta": ("Okta", "identity", ()),
    "onedrive": ("OneDrive", "storage", ()),
    "outlook": ("Outlook", "communication", ()),
    "plaid": ("Plaid", "finance", ()),
    "quickbooks": ("QuickBooks", "finance", ()),
    "salesforce": ("Salesforce", "crm", ()),
    "sendgrid": ("SendGrid", "communication", ()),
    "shopify": ("Shopify", "ecommerce", ()),
    "signal": ("Signal", "communication", ("signal_adapter",)),
    "slack": ("Slack", "communication", ("slack_adapter",)),
    "spotify": ("Spotify", "productivity", ()),
    "stripe": ("Stripe", "finance", ()),
    "tableau": ("Tableau", "analytics", ()),
    "teams": ("Microsoft Teams", "communication", ()),
    "telegram": ("Telegram", "communication", ()),
    "trello": ("Trello", "productivity", ()),
    "twilio": ("Twilio", "communication", ()),
    "twitter": ("X / Twitter", "marketing", ()),
    "webex": ("Webex", "communication", ()),
    "whatsapp": ("WhatsApp", "communication", ()),
    "workday": ("Workday", "hr", ()),
    "xero": ("Xero", "finance", ()),
    "zendesk": ("Zendesk", "support", ()),
    "zoho_books": ("Zoho Books", "finance", ("zoho-books",)),
    "zoho_crm": ("Zoho CRM", "crm", ("zoho-crm",)),
    "zoho_flow": ("Zoho Flow", "automation", ("zoho-flow",)),
    "zoho_forms": ("Zoho Forms", "productivity", ("zoho-forms",)),
    "zoho_inventory": ("Zoho Inventory", "ecommerce", ("zoho-inventory",)),
    "zoho_mail": ("Zoho Mail", "communication", ("zoho-mail",)),
    "zoho_projects": ("Zoho Projects", "productivity", ("zoho-projects",)),
    "zoho_workdrive": ("Zoho WorkDrive", "storage", ("zoho-workdrive",)),
    "zoom": ("Zoom", "communication", ()),
}

# Route modules that are product plumbing, not integrations.
_NON_BUSINESS_ROUTES = {
    "ai", "chat", "email", "historical_sync", "mcp", "token_refresh",
    "webhook_renewal", "workflow_approval", "workflow_automation",
    "onedrive_journey", "gdrive_journey", "slack_chat", "telegram_chat",
    "google_chat_enhanced_api", "whatsapp_fastapi", "outlook_enhanced",
    "system_status",
}


def _adapter_ids() -> Set[str]:
    out: Set[str] = set()
    for pattern in ("core/integrations/adapters/*.py", "integrations/adapters/*.py"):
        for path in glob.glob(str(_BACKEND / pattern)):
            stem = Path(path).stem
            if stem != "__init__":
                out.add(stem)
    return out


def _route_ids() -> Set[str]:
    out = set()
    for path in glob.glob(str(_BACKEND / "integrations" / "*_routes.py")):
        stem = Path(path).stem.replace("_routes", "")
        if stem not in _NON_BUSINESS_ROUTES:
            out.add(stem)
    return out


def _oauth_ids() -> Set[str]:
    try:
        from core.oauth_handler import PROVIDER_CONFIGS
        return set(PROVIDER_CONFIGS)
    except Exception:
        return set()


def _env_ids() -> Set[str]:
    try:
        from api.integration_status_routes import _ENV_CREDENTIALS
        return set(_ENV_CREDENTIALS)
    except Exception:
        return set()


def _connection_ids() -> Set[str]:
    try:
        from api.integration_status_routes import _PROVIDER_META
        return set(_PROVIDER_META)
    except Exception:
        return set()


def build_business_catalog() -> Dict[str, Any]:
    """Return the canonical provider catalog with per-provider evidence."""
    adapters = _adapter_ids()
    routes = _route_ids()
    oauth = _oauth_ids()
    env = _env_ids()
    connections = _connection_ids()

    providers: List[Dict[str, Any]] = []
    for cid, (name, category, aliases) in _CANONICAL.items():
        candidates = {cid, *aliases}
        evidence: List[str] = []
        if candidates & oauth:
            evidence.append("oauth")
        if candidates & adapters:
            evidence.append("adapter")
        if candidates & routes:
            evidence.append("routes")
        if candidates & env:
            evidence.append("env_key")
        if candidates & connections:
            evidence.append("connection")
        # Normalise the zoho hyphen/underscore and microsoft aliases once.
        if not evidence:
            continue
        providers.append({
            "id": cid,
            "name": name,
            "category": category,
            "evidence": evidence,
        })
    providers.sort(key=lambda p: p["name"].lower())
    by_category: Dict[str, int] = {}
    for provider in providers:
        by_category[provider["category"]] = by_category.get(provider["category"], 0) + 1
    return {
        "total": len(providers),
        "providers": providers,
        "by_category": dict(sorted(by_category.items())),
        "evidence_rule": "oauth|adapter|routes|env_key|connection",
        "note": (
            "Registration is not live qualification. A provider listed here has "
            "a shipped OAuth config, adapter, route module or wired credential; "
            "a live account has not been exercised."
        ),
    }
