"""Durable information waits for admitted agent jobs.

A missing fact is not an action approval.  This module creates the existing
``HITLAction`` durable wait receipt with a distinct action type and a
server-owned execution binding; it never grants effect authority.  The same
row is answered through the normal HITL input surface (or the job-scoped
answer route), and the resume bridge re-dispatches the SAME admitted job.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from core.models import HITLAction, HITLActionStatus

INFORMATION_WAIT_ACTION_TYPE = "agent_information_request"
INFORMATION_WAIT_ACTION_TYPES = frozenset({
    INFORMATION_WAIT_ACTION_TYPE,
    "agent_missing_information",
})

_QUESTION_LIMIT = 400
_FACT_LIMIT = 200
_SUBJECT_LIMIT = 200


def _bounded(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def is_information_wait_action(action_type: Any) -> bool:
    return str(action_type or "") in INFORMATION_WAIT_ACTION_TYPES


def _server_binding(context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Resolve the server-owned identity from an admitted execution context."""
    ctx = dict(context or {})
    job_id = str(ctx.get("job_id") or "")
    execution_id = str(ctx.get("execution_id") or ctx.get("run_id") or "")
    agent_id = str(ctx.get("agent_id") or "")
    workspace = str(ctx.get("workspace_id") or "")
    if not (job_id and execution_id and agent_id and workspace):
        return None
    actor = str(ctx.get("actor_id") or ctx.get("user_id") or "")
    subject_label = _bounded(ctx.get("information_subject"), _SUBJECT_LIMIT)
    return {
        "job_id": job_id,
        "execution_id": execution_id,
        "run_id": execution_id,
        "agent_id": agent_id,
        "workspace_id": workspace,
        "tenant_id": (
            None if ctx.get("tenant_id") is None else str(ctx.get("tenant_id"))),
        "actor_id": actor or None,
        "user_id": actor or None,
        "subject": subject_label or None,
    }


def request_information_wait(
    context: Optional[Dict[str, Any]],
    *,
    question: Any,
    missing_fact: Any = None,
    requested_subject: Any = None,
) -> Optional[Dict[str, Any]]:
    """Create one durable, actionable information wait.

    Returns the verified receipt (the same shape exposed on the job) or
    ``None`` when the context is not an admitted job/execution.  A normal
    direct GenericAgent call has no durable job identity and therefore keeps
    its previous behavior instead of inventing a wait.
    """
    binding = _server_binding(context)
    if binding is None:
        return None
    text = _bounded(question, _QUESTION_LIMIT)
    if not text:
        return None

    correlation_id = str(uuid.uuid4())
    channel = (
        f"user:{binding['actor_id']}" if binding.get("actor_id")
        else f"workspace:{binding['workspace_id']}")
    subject = {
        "job_id": binding["job_id"],
        "execution_id": binding["execution_id"],
        "agent_id": binding["agent_id"],
        "workspace_id": binding["workspace_id"],
    }
    if binding.get("subject"):
        subject["label"] = binding["subject"]

    snapshot = {
        **binding,
        "correlation_id": correlation_id,
        "channel": channel,
        "question": text,
        "subject": dict(subject),
    }
    params = {
        "question": text,
        "missing_fact": _bounded(missing_fact, _FACT_LIMIT) or None,
        "requested_subject": _bounded(
            requested_subject, _SUBJECT_LIMIT) or None,
        "subject": dict(subject),
        "correlation_id": correlation_id,
        "channel": channel,
    }

    from core.database import get_db_session

    with get_db_session() as db:
        row = HITLAction(
            id=str(uuid.uuid4()),
            workspace_id=binding["workspace_id"],
            tenant_id=binding.get("tenant_id"),
            agent_id=binding["agent_id"],
            user_id=binding.get("actor_id"),
            action_type=INFORMATION_WAIT_ACTION_TYPE,
            platform="internal",
            params=params,
            reason=text,
            status=HITLActionStatus.PENDING.value,
            context_snapshot=snapshot,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    return {
        "hitl_action_id": str(row.id),
        "id": str(row.id),
        "kind": "information_request",
        "status": str(row.status),
        "verified": True,
        "question": text,
        "missing_fact": params["missing_fact"],
        "correlation_id": correlation_id,
        "channel": channel,
        "subject": dict(subject),
    }
