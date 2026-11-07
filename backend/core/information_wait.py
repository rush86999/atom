"""Durable information waits for admitted agent jobs.

A missing fact is not an action approval.  This module creates the existing
``HITLAction`` durable wait receipt with a distinct action type and a
server-owned execution binding; it never grants effect authority.  The same
row is answered through the normal HITL input surface (or the job-scoped
answer route), and the resume bridge re-dispatches the SAME admitted job.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.models import HITLAction, HITLActionStatus

logger = logging.getLogger(__name__)

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


# Job states that still own the same run slot. Kept local (rather than
# importing api.agent_routes) to keep this core module import-light; they match
# the public job lifecycle constants.
_WAITING_JOB_STATUSES = frozenset({
    "waiting", "awaiting_information", "awaiting_input", "awaiting_approval",
})
_ACTIVE_JOB_STATUSES = frozenset({"pending", "running"})


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _recovery_binding(action: HITLAction) -> Optional[Dict[str, Any]]:
    """Resolve the exact server-owned wait identity from the durable snapshot.

    Recovery must not reconstruct authority from caller-supplied params or
    partially-populated rows: every identity/material field comes from the
    server-written ``context_snapshot``. The accepted answer is the durable
    ``user_feedback`` on the approved row.
    """
    snapshot = _json_object(getattr(action, "context_snapshot", None))
    job_id = str(snapshot.get("job_id") or "")
    execution_id = str(
        snapshot.get("execution_id") or snapshot.get("run_id") or "")
    agent_id = str(snapshot.get("agent_id") or "")
    workspace_id = str(snapshot.get("workspace_id") or "")
    tenant_id = snapshot.get("tenant_id")
    correlation_id = str(snapshot.get("correlation_id") or "")
    actor_id = str(
        snapshot.get("actor_id") or snapshot.get("user_id") or "") or None
    answer = str(getattr(action, "user_feedback", None) or "").strip()
    reviewer_id = getattr(action, "reviewed_by", None)
    if not (
        job_id and execution_id and agent_id and workspace_id
        and correlation_id and answer
    ):
        return None
    return {
        "job_id": job_id,
        "execution_id": execution_id,
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "tenant_id": None if tenant_id is None else str(tenant_id),
        "actor_id": actor_id,
        "correlation_id": correlation_id,
        "answer": answer,
        "reviewer_id": None if reviewer_id is None else str(reviewer_id),
    }


def _matches_tenant(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return True
    return str(left) == str(right)


def actor_authority_reason(
    actor: Any, *, workspace_id: Any, tenant_id: Any,
) -> str:
    """Return why an already-loaded actor may not continue a frozen scope.

    This is the shared current-authority contract for information waits: the
    accepted answer/admission receipt is *not* perpetual authority. It reuses
    the existing User status/role, RBAC ``AGENT_RUN`` permission and
    personal-scope workspace semantics. An empty string means the actor still
    matches the originally admitted target.

    Tenant/workspace absence keeps the supported legacy/personal behavior:
    a missing tenant wildcard-matches (``_matches_tenant``) and a missing
    workspace resolves through ``resolve_workspace_id`` to the Personal
    Edition default. That keeps the null/default bootstrap twin valid while
    still refusing a *moved* actor whose current workspace differs from the
    admitted target in another real workspace.
    """
    if actor is None:
        return "actor_unavailable"
    if (
        not bool(getattr(actor, "is_active", False))
        or str(getattr(actor, "status", "")) != "active"
    ):
        return "actor_unavailable"

    actor_tenant = getattr(actor, "tenant_id", None)
    if (
        actor_tenant is not None
        and tenant_id is not None
        and str(actor_tenant) != str(tenant_id)
    ):
        return "actor_tenant_mismatch"

    target_workspace = str(workspace_id or "").strip()
    if target_workspace:
        from core.personal_scope import resolve_workspace_id

        if str(resolve_workspace_id(actor)) != target_workspace:
            return "actor_workspace_mismatch"

    from core.rbac_service import Permission, RBACService

    if not RBACService.check_permission(actor, Permission.AGENT_RUN):
        return "actor_permission_revoked"
    return ""


def current_actor_authority(
    session, *, actor_id: Any, workspace_id: Any, tenant_id: Any,
) -> tuple:
    """Re-read the actor in ``session`` and return ``(actor, reason)``.

    ``populate_existing`` is deliberate: a cached identity-map User can be
    older than a move/deactivation committed by another writer.
    """
    actor_id = str(actor_id or "").strip()
    if not actor_id:
        # Every admitted information wait is actor-owned: admission requires
        # the actor, and the snapshot is written from that execution context.
        # A missing original actor is therefore missing authority, not an
        # actorless service grant. Legacy rows stay readable, but readability
        # is not an execution grant.
        return None, "actor_missing"
    from core.models import User

    actor = (
        session.query(User)
        .filter(User.id == actor_id)
        .populate_existing()
        .first()
    )
    return actor, actor_authority_reason(
        actor, workspace_id=workspace_id, tenant_id=tenant_id)


def actor_authority_conditions(
    *, actor_id: Any, workspace_id: Any, tenant_id: Any,
) -> list:
    """SQL conditions binding the same current-authority contract.

    Callers add these to the *same* conditional UPDATE that claims the waiting
    job, so a move/deactivation committed before that claim is observed by the
    write statement itself instead of a preceding read.
    """
    from sqlalchemy import false, or_

    from core.models import User, UserRole
    from core.personal_scope import PERSONAL_WORKSPACE_ID
    from core.rbac_service import Permission, get_role_permissions

    actor_id = str(actor_id or "").strip()
    if not actor_id:
        # Fail closed in the same statement that claims the job. The resume
        # consumer also refuses earlier with ``actor_missing``; this predicate
        # keeps any future claim site from turning an absent actor into a
        # wildcard authority match.
        return [false()]
    conditions = [
        User.id == actor_id,
        User.status == "active",
        User.is_active.is_(True),
    ]
    if tenant_id is not None:
        conditions.append(or_(
            User.tenant_id == str(tenant_id),
            User.tenant_id.is_(None),
        ))

    allowed_roles = {
        role.value
        for role, permissions in get_role_permissions().items()
        if Permission.AGENT_RUN in permissions
    }
    # SUPER_ADMIN is implicitly granted every permission by check_permission.
    allowed_roles.add(UserRole.SUPER_ADMIN.value)
    conditions.append(User.role.in_(sorted(allowed_roles)))

    target_workspace = str(workspace_id or "").strip()
    if target_workspace:
        if target_workspace == PERSONAL_WORKSPACE_ID:
            # Match ``resolve_workspace_id`` exactly: a Personal Edition actor
            # may carry NULL, the empty string, or the default id. Missing the
            # empty-string twin refuses a legitimate personal user at the very
            # claim UPDATE even though the Python pre-check accepts it.
            conditions.append(or_(
                User.workspace_id == target_workspace,
                User.workspace_id.is_(None),
                User.workspace_id == "",
            ))
        else:
            conditions.append(User.workspace_id == target_workspace)
    return conditions


def _validate_recovery_target(session, action, binding) -> tuple:
    """Return ``(job, execution, reason)`` after checking exact server facts.

    A malformed, foreign, settled or unrelated action must never reach the
    resume consumer. ``reason`` is empty only for a valid target.
    """
    from core.models import AgentExecution, AgentJob, AgentRegistry

    job = session.get(AgentJob, binding["job_id"])
    if job is None:
        return None, None, "job_not_found"
    if str(job.agent_id or "") != binding["agent_id"]:
        return None, None, "job_agent_mismatch"
    execution = session.get(AgentExecution, binding["execution_id"])
    if execution is None:
        return None, None, "execution_not_found"
    if str(execution.agent_id or "") != binding["agent_id"]:
        return None, None, "execution_agent_mismatch"
    agent = session.get(AgentRegistry, binding["agent_id"])
    if agent is None:
        return None, None, "agent_not_found"
    if getattr(action, "agent_id", None) not in (None, binding["agent_id"]):
        return None, None, "action_agent_mismatch"
    for entity in (agent, execution):
        workspace = getattr(entity, "workspace_id", None)
        if workspace is not None and str(workspace) != binding["workspace_id"]:
            return None, None, "workspace_mismatch"
    action_workspace = getattr(action, "workspace_id", None)
    if (
        action_workspace is not None
        and str(action_workspace) != binding["workspace_id"]
    ):
        return None, None, "workspace_mismatch"
    for entity in (job, agent, execution, action):
        if not _matches_tenant(
                getattr(entity, "tenant_id", None), binding["tenant_id"]):
            return None, None, "tenant_mismatch"

    # The admitted actor must still hold the current authority for the frozen
    # target scope. The accepted answer row is history, not a perpetual grant.
    # A missing actor is checked too: an actorless binding cannot borrow the
    # answerer/reviewer or any other principal as execution authority.
    _actor, authority_reason = current_actor_authority(
        session,
        actor_id=binding.get("actor_id"),
        workspace_id=binding["workspace_id"],
        tenant_id=binding.get("tenant_id"),
    )
    if authority_reason:
        return None, None, authority_reason

    payload = _json_object(getattr(job, "result_summary", None))
    job_execution = str(
        payload.get("execution_id")
        or payload.get("dispatch_execution_id") or "")
    if job_execution != binding["execution_id"]:
        return None, None, "job_execution_mismatch"
    receipt = payload.get("wait_receipt")
    receipt_action = (
        str(receipt.get("hitl_action_id") or receipt.get("id") or "")
        if isinstance(receipt, dict) else "")
    if receipt_action != str(action.id):
        return None, None, "wait_receipt_mismatch"
    return job, execution, ""


async def _reconcile_interrupted_resume_claim(binding) -> Dict[str, Any]:
    """Truthfully retire a claimed-but-unconfirmed continuation without replay.

    A dead process can die after the job CAS claim but before/while the resumed
    run executes. We cannot tell whether a side effect landed, so this must not
    re-dispatch. Verified-live owners are left alone; unknown ownership is
    reported, not asserted. Only a verified-dead owner is marked
    ``failed/uncertain`` with ``requires_reconciliation``.
    """
    from core.database import SessionLocal
    from core.execution_ownership import owner_liveness
    from core.models import AgentExecution, AgentJob

    session = SessionLocal()
    try:
        execution = session.get(AgentExecution, binding["execution_id"])
        if execution is None:
            return {"status": "skipped", "reason": "execution_not_found"}

        job = session.get(AgentJob, binding["job_id"])
        if job is None:
            return {"status": "skipped", "reason": "job_not_found"}
        if str(job.status or "") not in _ACTIVE_JOB_STATUSES:
            return {"status": "skipped", "reason": "job_already_settled"}
        payload = _json_object(job.result_summary)
        claim = payload.get("resume_claim")
        claim = dict(claim) if isinstance(claim, dict) else {}
        if (
            str(claim.get("action_id") or "") != str(binding["action_id"])
            or str(claim.get("execution_id") or "")
            != binding["execution_id"]
        ):
            return {"status": "skipped", "reason": "claim_not_for_this_wait"}

        # The claim records the process that won it. That is the authoritative
        # liveness signal: the execution owner stamp still names the original
        # waiting run, which is expected to be dead even when a successor is
        # actively resuming right now. Older claims without an owner fall back
        # to the execution stamp.
        claim_owner = claim.get("claim_owner")
        if isinstance(claim_owner, dict) and claim_owner.get("pid"):
            state, info = owner_liveness({"owner": claim_owner})
            owner_source = "resume_claim"
        else:
            state, info = owner_liveness(execution.metadata_json)
            owner_source = "execution"
        if state in ("live", "self"):
            return {
                "status": "skipped", "reason": "live_owner",
                "owner_source": owner_source, **info}
        if state == "unknown":
            return {
                "status": "skipped", "reason": "unknown_owner",
                "owner_source": owner_source, **info}

        if str(execution.status or "") not in ("waiting", "running"):
            return {"status": "skipped", "reason": "execution_already_settled"}

        now = datetime.now(timezone.utc)
        payload.update({
            "finished": True,
            "waiting": False,
            "status": "failed",
            "outcome": "uncertain",
            "reason": "execution_uncertain",
            "next_action": "reconcile_operation",
            "requires_reconciliation": True,
        })
        from sqlalchemy import update

        updated = session.execute(
            update(AgentJob)
            .where(
                AgentJob.id == binding["job_id"],
                AgentJob.status == job.status,
                AgentJob.result_summary == job.result_summary,
            )
            .values(
                status="failed",
                result_summary=json.dumps(payload, sort_keys=True),
                end_time=now,
            ))
        if updated.rowcount != 1:
            session.rollback()
            return {"status": "skipped", "reason": "job_changed_concurrently"}
        metadata = dict(execution.metadata_json or {})
        metadata["recovery"] = {
            "crashed": True,
            "recovered_at": now.isoformat(),
            "reason": "resume_claim_interrupted_uncertain",
            "owner_state": state,
        }
        # CAS the execution too: a peer that independently settled this
        # execution must win over stale cleanup. If it already left the
        # waiting/running states, roll the job update back rather than
        # recording a contradictory failed job over a completed execution.
        settled_execution = session.execute(
            update(AgentExecution)
            .where(
                AgentExecution.id == binding["execution_id"],
                AgentExecution.status.in_(("waiting", "running")),
            )
            .values(
                status="failed",
                error_message=(
                    "Process restarted after the answer was accepted and the "
                    "same job was claimed, but before a durable result. The "
                    "effect is uncertain; reconcile before retrying."),
                completed_at=now,
                metadata_json=metadata,
            ))
        if settled_execution.rowcount != 1:
            session.rollback()
            return {
                "status": "skipped",
                "reason": "execution_changed_concurrently",
            }
        session.commit()
        return {
            "status": "uncertain",
            "reason": "resume_claim_interrupted_uncertain",
            "job_status": "failed",
            "requires_reconciliation": True,
        }
    finally:
        session.close()


async def _recover_one_accepted_wait(action_id: str) -> Dict[str, Any]:
    from core.database import SessionLocal

    session = SessionLocal()
    try:
        action = session.get(HITLAction, str(action_id))
        if action is None:
            return {"status": "skipped", "reason": "wait_not_found"}
        if not is_information_wait_action(getattr(action, "action_type", None)):
            return {"status": "skipped", "reason": "not_information_wait"}
        if str(action.status or "") != HITLActionStatus.APPROVED.value:
            return {"status": "skipped", "reason": "not_approved"}
        binding = _recovery_binding(action)
        if binding is None:
            return {"status": "refused", "reason": "wait_binding_or_answer_missing"}
        job, execution, reason = _validate_recovery_target(
            session, action, binding)
        if reason:
            return {"status": "refused", "reason": reason}
        job_status = str(job.status or "")
        payload = _json_object(job.result_summary)
        claim = payload.get("resume_claim")
        claim = dict(claim) if isinstance(claim, dict) else {}
        claimed_here = (
            str(claim.get("action_id") or "") == str(action.id)
            and str(claim.get("execution_id") or "") == binding["execution_id"]
        )
    finally:
        session.close()

    binding["action_id"] = str(action_id)
    if job_status in _WAITING_JOB_STATUSES:
        from api.agent_routes import resume_information_wait_action
        from core.database import engine

        result = await resume_information_wait_action(
            str(action_id),
            approved=True,
            answer=None,
            reviewer_id=binding["reviewer_id"],
            bind=engine,
            correlation_id=binding["correlation_id"],
        )
        if result.get("resumed"):
            return {
                "status": "resumed",
                "job_id": binding["job_id"],
                "execution_id": binding["execution_id"],
                "job_status": result.get("job_status"),
            }
        return {
            "status": "skipped",
            "reason": result.get("reason") or result.get("status") or "not_resumed",
            "job_id": binding["job_id"],
            "execution_id": binding["execution_id"],
        }
    if job_status in _ACTIVE_JOB_STATUSES and claimed_here:
        return await _reconcile_interrupted_resume_claim(binding)
    if job_status in _ACTIVE_JOB_STATUSES:
        return {"status": "skipped", "reason": "job_active_without_this_claim"}
    return {"status": "skipped", "reason": "job_not_waiting"}


def _current_wait_action_id(payload: Dict[str, Any]) -> str:
    receipt = payload.get("wait_receipt")
    if isinstance(receipt, dict):
        action_id = str(
            receipt.get("hitl_action_id") or receipt.get("id") or "")
        if action_id:
            return action_id
    claim = payload.get("resume_claim")
    if isinstance(claim, dict):
        return str(claim.get("action_id") or "")
    return ""


def _eligible_accepted_page(
    session, *, after_id: str, batch: int, through_id: Optional[str] = None,
) -> tuple:
    """Return ``(eligible_action_ids, last_job_id, exhausted, scanned)`` for one page.

    Pages are keyed on ``AgentJob.id`` rather than an offset, so jobs that settle
    while a scan is running cannot shift later rows into a missed window.
    Unanswered/pending jobs are skipped without consuming the accepted-wait
    budget: the scan advances by one page and continues.
    """
    from core.models import AgentJob

    page_size = max(1, min(int(batch), 100))
    active_states = tuple(sorted(_WAITING_JOB_STATUSES | _ACTIVE_JOB_STATUSES))
    query = session.query(AgentJob).filter(
        AgentJob.status.in_(active_states))
    if after_id:
        query = query.filter(AgentJob.id > after_id)
    if through_id is not None:
        query = query.filter(AgentJob.id <= through_id)
    jobs = query.order_by(AgentJob.id.asc()).limit(page_size).all()
    if not jobs:
        return [], after_id, True, 0
    last_id = str(jobs[-1].id)
    exhausted = len(jobs) < page_size
    action_ids = []
    seen = set()
    for job in jobs:
        action_id = _current_wait_action_id(_json_object(job.result_summary))
        if action_id and action_id not in seen:
            seen.add(action_id)
            action_ids.append(action_id)
    if not action_ids:
        return [], last_id, exhausted, len(jobs)
    rows = (
        session.query(HITLAction)
        .filter(
            HITLAction.id.in_(action_ids),
            HITLAction.action_type.in_(
                tuple(sorted(INFORMATION_WAIT_ACTION_TYPES))),
            HITLAction.status == HITLActionStatus.APPROVED.value,
        )
        .all()
    )
    approved = {str(row.id) for row in rows}
    eligible = [action_id for action_id in action_ids if action_id in approved]
    return eligible, last_id, exhausted, len(jobs)


def _merge_recovery_detail(summary: Dict[str, Any], detail: Dict[str, Any]) -> None:
    summary["details"].append(detail)
    if detail.get("status") == "resumed":
        summary["resumed"] += 1
    elif detail.get("status") == "uncertain":
        summary["uncertain"] += 1
    elif detail.get("status") == "refused":
        summary["refused"] += 1
    else:
        summary["skipped"] += 1


def _empty_recovery_summary() -> Dict[str, Any]:
    return {
        "examined": 0,
        "resumed": 0,
        "skipped": 0,
        "refused": 0,
        "uncertain": 0,
        "details": [],
    }


async def recover_accepted_information_waits(*, limit: int = 20) -> Dict[str, Any]:
    """Process one bounded batch of accepted information waits.

    This is the batch API. The startup driver
    :func:`drain_accepted_information_waits` pages the finite active-job set
    until every accepted fact has been considered, so a normal boot is not
    limited to one batch.
    """
    from core.database import SessionLocal

    limit = max(0, min(int(limit), 100))
    if limit == 0:
        return _empty_recovery_summary()
    session = SessionLocal()
    try:
        action_ids, _last_id, _exhausted, _scanned = _eligible_accepted_page(
            session, after_id="", batch=limit)
    finally:
        session.close()

    summary = _empty_recovery_summary()
    summary["examined"] = len(action_ids)
    for action_id in action_ids:
        try:
            detail = await _recover_one_accepted_wait(action_id)
        except Exception as exc:  # noqa: BLE001 — one bad row must not stop boot
            logger.error(
                "Accepted information wait recovery failed for %s: %s",
                action_id, type(exc).__name__)
            detail = {"status": "refused", "reason": "recovery_error"}
        detail["action_id"] = action_id
        _merge_recovery_detail(summary, detail)
    if summary["resumed"] or summary["uncertain"]:
        logger.warning(
            "Accepted information wait recovery: resumed=%s uncertain=%s "
            "skipped=%s refused=%s",
            summary["resumed"], summary["uncertain"],
            summary["skipped"], summary["refused"])
    return summary


async def drain_accepted_information_waits(
    *, batch_size: int = 20, max_pages: int = 0,
) -> Dict[str, Any]:
    """Drain the finite boot backlog of accepted information waits.

    Starts at the first active job and keyset-pages forward, processing each
    page's eligible accepted waits before moving on. Unanswered/pending history
    therefore cannot block a later accepted fact, and a second startup sees no
    eligible work (the first pass settled or truthfully marked it). Work is
    still bounded per page and yields between pages; it is a one-shot startup
    pass, not a polling daemon or a second engine. ``max_pages`` is an optional
    safety bound for callers/tests; zero means drain the finite active set.
    """
    import asyncio

    from core.database import SessionLocal

    batch_size = max(1, min(int(batch_size), 100))
    max_pages = max(0, int(max_pages))
    summary = _empty_recovery_summary()
    summary.update({"pages": 0, "scanned_jobs": 0, "complete": True})
    # Freeze the boot backlog boundary. Jobs admitted while this pass runs
    # use their normal input consumer and cannot extend startup indefinitely.
    from sqlalchemy import func
    from core.models import AgentJob

    session = SessionLocal()
    try:
        through_id = session.query(func.max(AgentJob.id)).filter(
            AgentJob.status.in_(tuple(sorted(
                _WAITING_JOB_STATUSES | _ACTIVE_JOB_STATUSES)))).scalar()
    finally:
        session.close()
    if through_id is None:
        return summary
    after_id = ""
    complete = False
    while max_pages == 0 or summary["pages"] < max_pages:
        session = SessionLocal()
        try:
            action_ids, after_id, exhausted, scanned = _eligible_accepted_page(
                session, after_id=after_id, batch=batch_size,
                through_id=str(through_id))
        finally:
            session.close()
        summary["pages"] += 1
        summary["scanned_jobs"] += scanned
        summary["examined"] += len(action_ids)
        for action_id in action_ids:
            try:
                detail = await _recover_one_accepted_wait(action_id)
            except Exception as exc:  # noqa: BLE001 — one bad row must not stop boot
                logger.error(
                    "Accepted information wait recovery failed for %s: %s",
                    action_id, type(exc).__name__)
                detail = {"status": "refused", "reason": "recovery_error"}
            detail["action_id"] = action_id
            _merge_recovery_detail(summary, detail)
        if exhausted:
            complete = True
            break
        # Bound each burst and let the event loop run between pages.
        await asyncio.sleep(0)
    summary["complete"] = complete
    if not complete:
        logger.warning(
            "Accepted information wait recovery stopped at the page safety "
            "limit: pages=%s examined=%s", summary["pages"],
            summary["examined"])
    if summary["resumed"] or summary["uncertain"]:
        logger.warning(
            "Accepted information wait drain: resumed=%s uncertain=%s "
            "skipped=%s refused=%s pages=%s complete=%s",
            summary["resumed"], summary["uncertain"], summary["skipped"],
            summary["refused"], summary["pages"], summary["complete"])
    return summary
