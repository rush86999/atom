"""Org-privilege axis — Permission ≠ Privilege (AGENT_ORG_POLITICS_PLAN.md P2).

Research basis R4 ("Fluid Structure, Rigid Record", arXiv 2608.08516):
*Permission* bounds what an agent can observe and touch (tools, documents);
*Privilege* bounds which **org-state changes** it may authorize — approve,
promote, publish, spawn, grant, halt. Atom's tier + capabilities system is
the permission axis; this module adds the missing privilege axis.

Storage: ``AgentRegistry.configuration["org_privileges"]`` maps privilege
name → lease dict (``{"expires_at": iso8601}`` or ``{}`` for no expiry).
Default-DENY: no entry means no privilege at ANY maturity tier — tiers raise
the ceiling, privileges grant specific rights inside it.

Enforcement: ``integrations/mcp_service.call_tool`` checks
``PRIVILEGED_ACTIONS`` right after the capability gate so every dispatch path
(agent loop, workflow, fleet, meta-agent) is gated identically.

Flag: ATOM_ORG_PRIVILEGES_ENABLED (default false until audited; kill switch
restores tier-only behavior instantly). Never raises on the check path.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PRIV_APPROVE_PROPOSAL = "approve_proposal"
PRIV_PROMOTE_AGENT = "promote_agent"
PRIV_PUBLISH_SKILL = "publish_skill"
PRIV_SPAWN_AGENT = "spawn_agent"
PRIV_GRANT_PRIVILEGE = "grant_privilege"
PRIV_HALT_RUN = "halt_run"

ORG_PRIVILEGES = {
    PRIV_APPROVE_PROPOSAL,
    PRIV_PROMOTE_AGENT,
    PRIV_PUBLISH_SKILL,
    PRIV_SPAWN_AGENT,
    PRIV_GRANT_PRIVILEGE,
    PRIV_HALT_RUN,
}

# Dispatch-layer map: action name -> required org privilege. Deliberately
# minimal and explicit — add entries only for actions that mutate shared org
# state (not per-workspace task data).
PRIVILEGED_ACTIONS: Dict[str, str] = {
    "mini_app_publish": PRIV_PUBLISH_SKILL,
    "mini_app_install": PRIV_PUBLISH_SKILL,
}


class PrivilegeDenied(PermissionError):
    """Raised by require_privilege when a gate must fail closed."""


def privileges_enabled() -> bool:
    """Env kill-switch wins; else consent-gated automation state (TTL-cached)."""
    env_val = os.getenv("ATOM_ORG_PRIVILEGES_ENABLED", "")
    if env_val.strip().lower() in ("true", "false"):
        return env_val.strip().lower() == "true"
    try:
        from core.org_politics_automation import resolved_flag

        return resolved_flag("org_privileges")
    except Exception:
        return False


def _lease_map(agent_row: Any) -> Dict[str, Any]:
    config = getattr(agent_row, "configuration", None)
    if not isinstance(config, dict):
        return {}
    privs = config.get("org_privileges")
    return privs if isinstance(privs, dict) else {}


def has_privilege(db: Any, agent_id: str, privilege: str) -> bool:
    """Expiry-aware default-deny check. Never raises."""
    try:
        from core.models import AgentRegistry

        row = (
            db.query(AgentRegistry).filter(AgentRegistry.id == str(agent_id)).first()
        )
        if row is None:
            return False
        lease = _lease_map(row).get(privilege)
        if not isinstance(lease, dict):
            # Legacy/absent entry: any non-dict truthy value counts as an
            # unexpired grant only if explicitly stored as {} by grant().
            return lease == {}
        expires_raw = lease.get("expires_at")
        if not expires_raw:
            return True
        expires = datetime.fromisoformat(str(expires_raw))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < expires
    except Exception as e:  # noqa: BLE001 — check path never raises
        logger.debug(f"has_privilege check failed: {e}")
        return False


def grant_privilege(
    db: Any,
    agent_id: str,
    privilege: str,
    *,
    expires_at: Optional[datetime] = None,
    granted_by: Optional[str] = None,
) -> bool:
    """Grant an org privilege (optionally as an expiring lease).

    Returns False for unknown privilege names or missing agents — callers
    should treat that as denial, not retry.
    """
    if privilege not in ORG_PRIVILEGES:
        logger.warning(
            "org_privileges grant rejected (unknown): %s for %s", privilege, agent_id
        )
        return False
    try:
        from core.models import AgentRegistry

        row = (
            db.query(AgentRegistry).filter(AgentRegistry.id == str(agent_id)).first()
        )
        if row is None:
            return False
        config = dict(row.configuration or {})
        privs = dict(config.get("org_privileges") or {})
        lease: Dict[str, Any] = {}
        if expires_at is not None:
            exp = expires_at if expires_at.tzinfo else expires_at.replace(
                tzinfo=timezone.utc
            )
            lease["expires_at"] = exp.isoformat()
        privs[privilege] = lease
        config["org_privileges"] = privs
        row.configuration = config  # reassign so JSON mutation is detected
        db.commit()
        logger.info(
            "org_privileges: %s granted %s%s",
            agent_id,
            privilege,
            f" (by {granted_by})" if granted_by else "",
        )
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"org_privileges grant failed: {e}")
        return False


def revoke_privilege(db: Any, agent_id: str, privilege: str) -> bool:
    try:
        from core.models import AgentRegistry

        row = (
            db.query(AgentRegistry).filter(AgentRegistry.id == str(agent_id)).first()
        )
        if row is None:
            return False
        config = dict(row.configuration or {})
        privs = dict(config.get("org_privileges") or {})
        if privilege not in privs:
            return False
        del privs[privilege]
        config["org_privileges"] = privs
        row.configuration = config
        db.commit()
        logger.info("org_privileges: %s revoked %s", agent_id, privilege)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"org_privileges revoke failed: {e}")
        return False


def require_privilege(db: Any, agent_id: str, privilege: str) -> None:
    """Fail-closed variant for call sites that must raise on denial."""
    if not has_privilege(db, agent_id, privilege):
        raise PrivilegeDenied(
            f"Agent '{agent_id}' lacks org privilege '{privilege}'"
        )


def check_action_privilege(
    tool_name: str, context: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Dispatch-gate helper: deny payload when the caller lacks the privilege.

    Returns None when the call may proceed (flag off, unmapped action, no
    agent identity in context — human/user-driven paths stay on role auth),
    or a blocked-result dict mirroring the capability gate's shape.
    """
    if not privileges_enabled():
        return None
    required = PRIVILEGED_ACTIONS.get(tool_name)
    if required is None:
        return None
    agent_id = (context or {}).get("agent_id")
    if not agent_id:
        return None
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            allowed = has_privilege(db, str(agent_id), required)
    except Exception as e:  # noqa: BLE001 — fail CLOSED for privileged actions
        logger.warning(
            "org_privileges check errored (%s); denying %s for %s",
            e, tool_name, agent_id,
        )
        allowed = False
    if allowed:
        return None
    logger.info(
        "Privilege gate BLOCKED action %s for agent %s (needs %s)",
        tool_name, agent_id, required,
    )
    return {
        "success": False,
        "error": f"Action '{tool_name}' requires org privilege '{required}'",
        "blocked_by": "privilege_gate",
    }
