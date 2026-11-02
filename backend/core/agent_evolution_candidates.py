"""MEM-07: capture a tool failure as a PENDING evolution candidate.

A candidate is a HITL approval row, not a code change. This module never edits
files and never applies a proposal: a human decides whether the failure is
worth acting on, and any fix happens through the normal reviewed path.

The capture is opt-in (``ATOM_AGENT_EVOLUTION_ENABLED=true``) and idempotent
per (agent, tool, error), so a retry loop cannot flood the approval queue.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

CANDIDATE_ACTION = "agent_evolution_candidate"
CANDIDATE_PLATFORM = "agent_evolution"


def evolution_capture_enabled() -> bool:
    raw = os.getenv("ATOM_AGENT_EVOLUTION_ENABLED", "false")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _fingerprint(agent_id: Any, tool_name: Any, error: Any) -> str:
    payload = json.dumps({
        "agent_id": str(agent_id or ""),
        "tool": str(tool_name or ""),
        "error": str(error or "")[:2000],
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def capture_tool_failure(
    *,
    agent_id: Any,
    tool_name: Any,
    error: Any,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """Queue one pending candidate; return its id, or None when not captured."""
    if not evolution_capture_enabled() or not agent_id or not tool_name:
        return None
    from core.database import get_db_session
    from core.models import HITLAction, HITLActionStatus

    fingerprint = _fingerprint(agent_id, tool_name, error)
    try:
        with get_db_session() as db:
            pending = (
                db.query(HITLAction)
                .filter(
                    HITLAction.action_type == CANDIDATE_ACTION,
                    HITLAction.status == HITLActionStatus.PENDING.value,
                )
                .all()
            )
            for row in pending:
                params = row.params or {}
                if (isinstance(params, dict)
                        and params.get("fingerprint") == fingerprint):
                    return row.id
            candidate = HITLAction(
                workspace_id=workspace_id or None,
                tenant_id=tenant_id or None,
                agent_id=str(agent_id),
                action_type=CANDIDATE_ACTION,
                platform=CANDIDATE_PLATFORM,
                params={
                    "fingerprint": fingerprint,
                    "tool": str(tool_name),
                    "error": str(error)[:2000],
                    "proposed_scope": (
                        "review the tool contract and propose a bounded fix; "
                        "no code or configuration change is applied"),
                },
                status=HITLActionStatus.PENDING.value,
                reason=(
                    f"Tool {tool_name} failed; a pending evolution candidate "
                    "needs human review."),
                user_id=user_id or None,
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            return candidate.id
    except Exception as exc:  # never break the tool result path
        logger.warning("evolution candidate capture failed: %s", exc)
        return None
