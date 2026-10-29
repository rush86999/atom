"""The product surface this deployment exposes.

2026-10-27 product decision: the first release is a **company data +
trained agent** workspace, not the whole application. This module is the one
explicit capability configuration the rest of the product consults:

* the frontend fetches ``/api/product/profile`` and uses it for navigation,
  dashboard links and direct-page access;
* startup applies its worker defaults (autonomous scheduling and external
  ingestion sync are off in the core release);
* documentation quotes the same capability list.

Deferred code and recorded data stay in place. Switching
``ATOM_PRODUCT_PROFILE=full`` (or ``ATOM_PRODUCT_PROFILE_PATH=/path.json``)
restores the wider surface without a rewrite.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

PROFILE_ENV = "ATOM_PRODUCT_PROFILE"
PROFILE_PATH_ENV = "ATOM_PRODUCT_PROFILE_PATH"
DEFAULT_PROFILE = "core"
PROFILE_VERSION = "2026-10-27"

#: Capability ids, their release state and the user-facing job they promise.
CAPABILITIES: Dict[str, Dict[str, Any]] = {
    # ---- core release -----------------------------------------------------
    "chat": {
        "label": "Chat",
        "enabled": True,
        "job": "Ask questions and direct work.",
    },
    "documents": {
        "label": "Data",
        "enabled": True,
        "job": "Upload, find and inspect company records.",
    },
    "canvas": {
        "label": "Workspace",
        "enabled": True,
        "job": "Review and edit deliverables: documents, tables, email "
               "drafts and presentations.",
    },
    "agents": {
        "label": "Agents",
        "enabled": True,
        "job": "Create, teach and correct an agent.",
    },
    "activity": {
        "label": "Activity",
        "enabled": True,
        "job": "See results, failures and unfinished work.",
    },
    "settings": {
        "label": "Settings",
        "enabled": True,
        "job": "Sign-in, providers and data configuration.",
    },
    "approvals": {
        "label": "Approvals",
        "enabled": True,
        "nav": False,  # safeguard, not an ordinary work surface
        "min_role": "team_lead",
        "job": "Supervise work that is waiting for a human decision.",
    },
    # ---- deferred ---------------------------------------------------------
    "search": {
        "label": "Search",
        "enabled": False,
        "job": "Cross-surface search (documents search stays available).",
    },
    "tasks": {
        "label": "Tasks",
        "enabled": False,
        "job": "Task tracking.",
    },
    "boards": {
        "label": "Kanban",
        "enabled": False,
        "job": "Kanban boards.",
    },
    "automations": {
        "label": "Automations",
        "enabled": False,
        "job": "Workflow builder, scheduling and unattended automation.",
    },
    "marketplace": {
        "label": "Marketplace",
        "enabled": False,
        "job": "Agent/template marketplace.",
    },
    "command_centers": {
        "label": "Command Centers",
        "enabled": False,
        "job": "Projects, sales, support and knowledge dashboards.",
    },
    "business_dashboards": {
        "label": "Business Dashboards",
        "enabled": False,
        "job": "Sales, marketing, finance and analytics dashboards.",
    },
    "productivity": {
        "label": "Productivity",
        "enabled": False,
        "job": "Calendar, business health and voice.",
    },
    "governance": {
        "label": "Governance",
        "enabled": False,
        "job": "Admin, audit, forensics and self-healing tools.",
    },
    "connectors": {
        "label": "Connector Management",
        "enabled": False,
        "job": "Broad third-party connector setup (providers stay in Settings).",
    },
    "team_chat": {
        "label": "Team Chat",
        "enabled": False,
        "job": "Internal team messaging.",
    },
}

#: Longest-prefix match wins. Everything not listed is deferred in core so a
#: newly added page cannot silently appear in the release.
ROUTE_CAPABILITY: Dict[str, str] = {
    "/dashboard": "chat",
    "/chat": "chat",
    "/documents": "documents",
    "/canvas": "canvas",
    "/agents": "agents",
    "/goal-runs": "activity",
    "/execution-history": "activity",
    "/activity": "activity",
    "/assignments": "activity",
    "/approvals": "approvals",
    "/settings/harness-evolution": "governance",
    "/settings": "settings",
    "/login": "core",
    "/auth": "core",
    "/not-in-release": "core",
    "/search": "search",
    "/tasks": "tasks",
    "/boards": "boards",
    "/automations": "automations",
    "/workflows": "automations",
    "/scheduling": "automations",
    "/marketplace": "marketplace",
    "/dashboards": "command_centers",
    "/communication": "command_centers",
    "/sales": "business_dashboards",
    "/marketing": "business_dashboards",
    "/finance": "business_dashboards",
    "/analytics": "business_dashboards",
    "/calendar": "productivity",
    "/health": "productivity",
    "/voice": "productivity",
    "/admin": "governance",
    "/audit-trail": "governance",
    "/dashboard/owner": "governance",
    "/dashboard/forensics": "governance",
    "/dashboard/risk": "governance",
    "/system-status": "governance",
    "/dev-studio": "governance",
    "/intelligence": "governance",
    "/integrations": "connectors",
    "/google-drive": "connectors",
    "/onedrive": "connectors",
    "/team-chat": "team_chat",
}

_AUTH_PREFIXES = ("/login", "/auth", "/api", "/_next", "/favicon")
_PROFILE_CACHE: Optional[Dict[str, Any]] = None


def _profile_config_path() -> Optional[Path]:
    override = os.getenv(PROFILE_PATH_ENV)
    if override:
        return Path(override).expanduser()
    # backend/core/product_profile.py -> <package root>/config/product_profile.json
    candidate = Path(__file__).resolve().parents[2] / "config" / "product_profile.json"
    return candidate if candidate.is_file() else None


def _load_overrides() -> Dict[str, Any]:
    path = _profile_config_path()
    if not path or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001 — never break startup on config
        logger.warning("product profile override ignored (%s): %s", path, exc)
        return {}


def active_profile() -> str:
    raw = os.getenv(PROFILE_ENV, DEFAULT_PROFILE).strip().lower()
    return raw if raw in {"core", "full"} else DEFAULT_PROFILE


def _resolved_capabilities() -> Dict[str, Dict[str, Any]]:
    overrides = _load_overrides().get("capabilities", {})
    resolved: Dict[str, Dict[str, Any]] = {}
    for cap_id, meta in CAPABILITIES.items():
        merged = dict(meta)
        if active_profile() == "full":
            merged["enabled"] = True
        merged.update(overrides.get(cap_id, {}))
        resolved[cap_id] = merged
    return resolved


def capability_enabled(capability: str) -> bool:
    if capability == "core":
        return True
    return bool(_resolved_capabilities().get(capability, {}).get("enabled", False))


def route_capability(pathname: str) -> str:
    path = (pathname or "/").split("?", 1)[0].rstrip("/") or "/"
    # Exact/deepest match first so /settings/harness-evolution beats /settings.
    for prefix in sorted(ROUTE_CAPABILITY, key=len, reverse=True):
        if path == prefix or path.startswith(prefix + "/"):
            return ROUTE_CAPABILITY[prefix]
    return "deferred"


def route_enabled(pathname: str) -> bool:
    return capability_enabled(route_capability(pathname))


def for_role(capability: str, role_level: int = 0) -> bool:
    meta = _resolved_capabilities().get(capability, {})
    minimum = {"member": 3, "team_lead": 4, "workspace_admin": 5, "admin": 6, "owner": 7}
    required = meta.get("min_role")
    return capability_enabled(capability) and (
        not required or role_level <= 0 or role_level >= minimum.get(required, 0)
    )


def enabled_capabilities() -> List[str]:
    return [c for c, m in _resolved_capabilities().items() if m.get("enabled")]


def deferred_capabilities() -> List[str]:
    return [c for c, m in _resolved_capabilities().items() if not m.get("enabled")]


def profile_document() -> Dict[str, Any]:
    """The JSON contract read by the frontend and quoted by docs."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is None:
        caps = _resolved_capabilities()
        _PROFILE_CACHE = {
            "profile": active_profile(),
            "version": PROFILE_VERSION,
            "statement": (
                "Company data + trained agent workspace"
                if active_profile() == "core"
                else "Full product surface"
            ),
            "capabilities": caps,
            "enabled_capabilities": [c for c, m in caps.items() if m.get("enabled")],
            "deferred_capabilities": [c for c, m in caps.items() if not m.get("enabled")],
            "routes": dict(ROUTE_CAPABILITY),
        }
    return _PROFILE_CACHE


def apply_runtime_defaults() -> Dict[str, str]:
    """Disable deferred background workers for the core release.

    Explicit operator settings still win where they are needed for a
    supported verification (the isolated acceptance world, for example, may
    want the scheduler on to test a core-adjacent path), but a shipped core
    installation starts with autonomous scheduling and external ingestion
    sync off rather than quietly running deferred machinery.
    """
    applied: Dict[str, str] = {}
    if active_profile() != "core":
        return applied
    defaults = {
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "false",
    }
    for key, value in defaults.items():
        if key not in os.environ:
            os.environ[key] = value
            applied[key] = value
        else:
            applied[key] = os.environ[key]
    logger.info("core product profile worker defaults: %s", applied)
    return applied
