"""Execution crash-recovery sweep.

On startup, find executions that were ``RUNNING`` when the process died and
mark them as failed so they become visible to failure dashboards and retry
logic. Without this, a process crash mid-run orphans the row in ``RUNNING``
forever — neither completed, failed, nor retried (the "ghost run" problem).

This is **reconcile-only** (safe): it marks crashed runs as ``FAILED``; it
does NOT auto-resume them. Re-entering a crashed run risks double-firing
side effects (emails sent, cards charged) from a partially-completed step.
The workflow engine already has resume-skip logic
(workflow_engine.py:614, :253) for the future auto-resume path, but that
should only be enabled once steps declare idempotency.

WORKFLOW EVENT RUNS
Rows whose execution id starts with ``evt_`` are dispatched event actions.
They are never replayed by this sweep. A claimed event row is reconciled only
when the claim/admission records an owner that ``owner_liveness`` can VERIFY
DEAD; the resulting marker says the action outcome is
``action-outcome-uncertain`` and requires reconciliation. A live, self,
cross-host or UNKNOWN owner is left ``RUNNING`` and reported, as is every
claimed event row for which no ownership stamp exists. Requeueing PENDING
event rows belongs to the separate dispatcher, not to this startup sweep.

A row whose owner is VERIFIED ALIVE is left alone, and a row whose ownership
cannot be established is also left alone -- this sweep must never fail another
live worker's execution, and "I cannot see who owns this" is not evidence that it
died. Only a VERIFIED dead owner (no such pid, or a confirmed pid reuse) is
reconciled. Ownership is recorded on every ORM insert by
``core.execution_ownership``; rows it cannot account for are reported in
``agent_unknown_detail`` rather than acted on.

FLEET CHAINS RIDE THE SAME VERDICT
A fleet run is a ``DelegationChain`` rooted at the ``AgentExecution`` that
started it. ``DelegationChain.root_execution_id`` is that durable parent-to-chain
binding (unlike in-memory fleet state, it survives the crash). If startup fails
the root execution but leaves the chain ``active`` and its ``in_progress`` links
untouched, the fleet dashboard reports a live fleet that no worker can ever
advance -- the exact "ghost run" this module exists to remove, one layer up.

So the *same* recovered ids drive chain reconciliation. Only a chain whose
``root_execution_id`` exactly equals a reconciliation id from THIS sweep is
touched; a chain rooted at a live or UNKNOWN owner is left alone, as is an
unlinked/legacy chain and a chain in a different tenant or workspace. Completed
links are preserved (their work really happened); only non-terminal links are
failed. The chain and its links are written in one transaction, and an
already-terminal chain is skipped, so a second sweep is a no-op.

Gated by ``ATOM_EXECUTION_RECOVERY_ENABLED`` (default true).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import update
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.execution_state_manager import (
    EVENT_CLAIM_CONTEXT_KEY,
    decode_json_object,
    is_event_execution_id,
)
from core.models import (
    AgentExecution,
    AgentJob,
    AgentJobStatus,
    AgentRegistry,
    AgentStatus,
    ChainLink,
    DelegationChain,
    ExecutionStatus,
    WorkflowExecution,
    WorkflowExecutionStatus,
)

logger = logging.getLogger(__name__)

RECOVERY_ENABLED = os.getenv("ATOM_EXECUTION_RECOVERY_ENABLED", "true").lower() == "true"

_CRASH_ERROR_MESSAGE = "Process restarted while execution was running (crashed)"

#: Workflow-event rows use a reserved id prefix and a server-owned admission
#: record in the existing JSON ``context`` column. They are recovered on the
#: same sweep, but with an explicit "outcome may already have happened" marker
#: instead of the ordinary crash verdict. No migration is required.
EVENT_ACTION_OUTCOME_UNCERTAIN = "action-outcome-uncertain"


#: Chain statuses that are already resolved. A chain in one of these states has
#: nothing left to recover, even if it still points at a dead root execution.
_TERMINAL_CHAIN_STATUSES = frozenset({"completed", "failed", "cancelled", "canceled"})

#: Link statuses whose work is already resolved. ``completed`` means the
#: specialist's work really happened and must never be rewritten by recovery;
#: the failure/cancel/skip states are equally terminal. Everything else
#: (pending, in_progress, processing, active, ...) is orphaned by definition
#: once the chain's root execution is verified dead.
_TERMINAL_LINK_STATUSES = _TERMINAL_CHAIN_STATUSES | frozenset({"skipped"})

#: AgentJob statuses that can be orphaned by a dead worker. A waiting job is
#: deliberately absent: it is a durable pause, not an in-flight claim.
_ACTIVE_JOB_STATUSES = (
    AgentJobStatus.PENDING.value,
    AgentJobStatus.RUNNING.value,
)

# The registry stores the agent's pre-run status. These are the values this
# recovery path is prepared to restore when a newer AgentStatus enum is not
# available; "running" is never a valid *prior* status (it is the state being
# recovered from).
_SAFE_REGISTRY_PRIOR_STATUSES = frozenset({
    "idle", "active", "inactive", "enabled", "disabled", "available",
    "offline", "online", "ready", "busy", "paused", "suspended",
    "stopped", "failed", "error", "success", "completed",
    "student", "intern", "supervised", "autonomous",
    "new", "draft", "archived",
})


def _owner_dict(value: Any) -> Any:
    """Normalize a persisted ownership value, tolerating JSON-string form."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    return dict(value) if isinstance(value, dict) else None


def _event_claim_owner(context: Dict[str, Any]) -> Tuple[Any, Any]:
    """Locate the owner recorded by the event claim itself.

    There is exactly one claim context path: ``_atom_event_claim``.  An
    admission record may describe who admitted the run, but it is not proof of
    which process currently owns it.  No claim entry means UNKNOWN, not dead.
    """
    owner = _owner_dict(context.get(EVENT_CLAIM_CONTEXT_KEY))
    if owner and owner.get("pid"):
        return owner, "claim"
    return None, None


def _event_owner_verdict(owner: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Run the normal ownership liveness check for one claimed event owner."""
    try:
        from core.execution_ownership import owner_liveness
    except Exception as exc:  # noqa: BLE001
        return "unknown", {
            "reason": f"ownership-dependency-unavailable: {exc}",
        }
    try:
        state, info = owner_liveness({"owner": owner})
    except Exception as exc:  # noqa: BLE001
        return "unknown", {"reason": f"ownership-check-failed: {exc}"}
    if not isinstance(info, dict):
        info = {}
    return state, info


def _mark_event_execution_reconciled(
    session: Session, row: WorkflowExecution, now: datetime, owner_state: str,
    owner_info: Dict[str, Any], owner_source: Any,
    observed_context: Any, observed_version: Any,
) -> bool:
    """Fail one event run while explicitly preserving action-outcome doubt.

    Event actions are external side effects.  A worker that finds a verified
    dead owner cannot know whether the action landed, so the recovery marker
    says so instead of implying a clean crash or scheduling a replay.

    The verdict is followed by the sweep's commit, so this transition is a
    single conditional UPDATE rather than an ORM attribute write.  It matches
    the exact execution id, observed RUNNING status, observed version and exact
    observed context.  A concurrent product action (such as cancellation) that
    commits while the liveness verdict is in flight therefore wins: its row is
    not rewritten, its version is not replaced and the sweep does not count a
    recovery.  Returns whether this update won.
    """
    ctx = decode_json_object(observed_context)
    marker = {
        "crashed": True,
        "recovered_at": now.isoformat(),
        "action_outcome": "uncertain",
        "action_outcome_uncertain": True,
        "action_outcome_status": EVENT_ACTION_OUTCOME_UNCERTAIN,
        "outcome": "uncertain",
        "status": EVENT_ACTION_OUTCOME_UNCERTAIN,
        "reason": EVENT_ACTION_OUTCOME_UNCERTAIN,
        "requires_reconciliation": True,
        "next_action": "reconcile_operation",
        "event": True,
        "owner_state": owner_state,
        "owner_source": owner_source,
    }
    for key in ("pid", "host", "token"):
        if owner_info.get(key) is not None:
            marker[key] = owner_info.get(key)
    ctx["recovery"] = marker
    # A second, event-namespaced copy makes the uncertainty machine-readable
    # without forcing readers of the generic ``recovery`` marker to know about
    # event runs.
    ctx["_atom_event_recovery"] = dict(marker)

    conditions = [
        WorkflowExecution.execution_id == row.execution_id,
        WorkflowExecution.status == WorkflowExecutionStatus.RUNNING.value,
        WorkflowExecution.version == observed_version,
    ]
    if observed_context is None:
        conditions.append(WorkflowExecution.context.is_(None))
    elif not isinstance(observed_context, (dict, list)):
        conditions.append(WorkflowExecution.context == observed_context)

    result = session.execute(
        update(WorkflowExecution)
        .where(*conditions)
        .values(
            status=WorkflowExecutionStatus.FAILED.value,
            error=_CRASH_ERROR_MESSAGE,
            completed_at=now,
            context=json.dumps(ctx),
            version=WorkflowExecution.version + 1,
        )
    )
    return result.rowcount == 1


def _recover_workflow_executions(
    session: Session, event_report: Optional[Dict[str, Any]] = None,
) -> int:
    """Reconcile orphaned RUNNING WorkflowExecution rows.

    Manual/cron rows keep the original sweep behaviour: a RUNNING row at
    startup is failed with the crash marker.  Event rows are different: their
    action may be an external side effect owned by another live worker.  They
    are reconciled only when the claim/admission records a VERIFIED dead owner;
    a live, self, cross-host or otherwise UNKNOWN owner is left RUNNING and
    reported.  When no owner was recorded at all, the row is left for explicit
    reconciliation and the dependency on a dispatcher/ownership stamp is
    reported instead of treating "this process just started" as proof of death.

    Returns the count recovered.  When ``event_report`` is supplied it receives
    the event-specific counts and deferred-row details for the caller.
    """
    rows = (
        session.query(WorkflowExecution)
        .filter(WorkflowExecution.status == WorkflowExecutionStatus.RUNNING.value)
        .all()
    )
    now = datetime.now(timezone.utc)
    recovered = 0
    event_recovered = 0
    event_left: List[Dict[str, Any]] = []

    for row in rows:
        if is_event_execution_id(row.execution_id):
            # Capture the row as observed before the liveness verdict; the CAS
            # below must compare against this exact state, not anything a
            # concurrent writer may have done while the verdict was running.
            observed_context = row.context
            observed_version = row.version
            ctx = decode_json_object(observed_context)
            owner, owner_source = _event_claim_owner(ctx)
            if owner is None:
                event_left.append({
                    "execution_id": row.execution_id,
                    "owner_state": "unknown",
                    "reason": "event-owner-not-recorded",
                    "owner_source": None,
                    "requires_reconciliation": True,
                })
                continue
            owner_state, owner_info = _event_owner_verdict(owner)
            if owner_state != "dead":
                # Do not fail another active worker merely because this process
                # started.  UNKNOWN is not dead either.
                event_left.append({
                    "execution_id": row.execution_id,
                    "owner_state": owner_state,
                    "owner_source": owner_source,
                    "requires_reconciliation": owner_state == "unknown",
                    **owner_info,
                })
                continue
            # Only count the row when the CAS won.  If a product action already
            # moved it out of RUNNING, that later state is authoritative.
            if _mark_event_execution_reconciled(
                session, row, now, owner_state, owner_info, owner_source,
                observed_context, observed_version,
            ):
                event_recovered += 1
                recovered += 1
            continue

        # Manual/cron path: unchanged semantics.
        row.status = WorkflowExecutionStatus.FAILED.value
        row.error = _CRASH_ERROR_MESSAGE
        row.completed_at = now
        # Stamp a recovery marker in context (JSON-stored) so operators can
        # distinguish crash-recovered failures from genuine logic failures.
        ctx = decode_json_object(row.context)
        ctx.setdefault("recovery", {})
        ctx["recovery"] = {"crashed": True, "recovered_at": now.isoformat()}
        row.context = json.dumps(ctx)
        recovered += 1

    if event_report is not None:
        dependency = any(
            row.get("reason") == "event-owner-not-recorded"
            or row.get("owner_state") == "unknown"
            for row in event_left
        )
        event_report.update({
            "workflow_event_recovered": event_recovered,
            "workflow_event_left_running": len(event_left),
            "workflow_event_detail": event_left,
            "workflow_event_ownership_dependency": dependency,
            "workflow_event_reconciliation_required": bool(event_left),
        })
    return recovered


def _recover_agent_executions(session: Session) -> Tuple[int, int, List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Mark orphaned running AgentExecution rows as failed.

    Returns ``(recovered, untouched, detail, unknown, recovered_ids)``.

    Three verdicts, from `core.execution_ownership.owner_liveness`:

    * VERIFIED live owner (``live`` / ``self``) -> untouched. A second process
      on this database must never fail a turn another live process is running.
    * VERIFIED dead owner (``dead``: no such pid, or a CONFIRMED pid reuse) ->
      reconciled.
    * Anything else (``unknown``) -> untouched AND reported. A missing stamp, an
      owner on another host, and a failed liveness inspection are all "cannot
      tell". Treating them as dead is how a running turn gets failed by a
      process that simply could not see who owned it -- and the earlier version
      of this function did exactly that for the first two cases.

    Only reconciled ids reach `_release_crashed_chat_requests`, so a key is never
    released on the strength of an unverified owner.
    """
    from core.execution_ownership import owner_liveness

    rows = (
        session.query(AgentExecution)
        .filter(AgentExecution.status == ExecutionStatus.RUNNING.value)
        .all()
    )
    now = datetime.now(timezone.utc)
    recovered: List[str] = []
    untouched: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []
    for row in rows:
        state, info = owner_liveness(row.metadata_json)
        if state == "unknown":
            unknown.append({"execution_id": row.id, "owner_state": state, **info})
            continue
        if state in ("live", "self"):
            untouched.append({"execution_id": row.id, "owner_state": state, **info})
            continue
        row.status = ExecutionStatus.FAILED.value
        row.error_message = _CRASH_ERROR_MESSAGE
        row.completed_at = now
        # Stamp a recovery marker in metadata_json (JSON-stored) so operators can
        # distinguish crash-recovered failures from genuine logic failures
        # — mirroring the workflow path which stamps ``context``. Without this,
        # recovered runs are indistinguishable from real failures.
        meta = {}
        if row.metadata_json:
            try:
                # dict(...) copies so the stamped dict is a NEW object; mutating
                # and re-assigning the ORM's own JSON dict in place does not
                # register a change, so the recovery marker would never persist.
                meta = dict(row.metadata_json)
            except (ValueError, TypeError):
                meta = {}
        meta.setdefault("recovery", {})
        meta["recovery"] = {"crashed": True, "recovered_at": now.isoformat(),
                            "owner_state": state}
        row.metadata_json = meta
        recovered.append(row.id)
    return len(recovered), len(untouched), untouched, unknown, recovered


def _metadata_value(metadata: Any, key: str) -> Any:
    """Read one key out of a metadata blob of unknown shape.

    `metadata_json` is a JSON column, so it can be a dict, a JSON *string*, or
    (in rows written by older code) a scalar. Every reader here has to survive
    all three; the recovery path below already does, and a helper keeps the
    attribution path from being the one that raises on a weird row.
    """
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            return None
    if isinstance(metadata, dict):
        return metadata.get(key)
    return None


def _release_crashed_chat_requests(session: Session, recovered_ids: List[str]) -> int:
    """Resolve keyed chat requests whose execution this sweep just terminated.

    `ChatRequestRecord` deliberately holds `in_progress` rather than risk
    repeating a possibly-completed side effect when a turn dies mid-flight --
    the documented client contract was "mint a fresh request_id". That policy is
    sound on its own, but it collides with the sweep: once the sweep marks the
    execution failed, the truth is known (this turn did not complete here) while
    the key stays `in_progress` forever, so a client retrying the SAME id is told
    "already in progress" indefinitely. An indefinite in-progress answer is not a
    recovery policy, it is the absence of one.

    So the key moves to the terminal `crashed` state carrying that truth. It is
    deliberately NOT a successful pin: the sweep cannot know whether a side
    effect landed before the crash, so it must not hand back a response claiming
    one, and it must not re-execute. `chat_transport.check` turns a `crashed`
    record into an explicit 409, so a same-id retry is told the truth and a fresh
    id starts a new turn.

    ATTRIBUTION, NOT RECENCY. `ChatRequestRecord.execution_id` is written only at
    finalization, so a crashed turn's key has NULL there and cannot be joined on
    it. The join is on the request id the turn recorded at claim time
    (`metadata_json.request_id`). A recovered execution with no recorded request
    id releases nothing rather than guessing -- a key resolved on a guess would
    tell a client its turn crashed when it may have completed under another id.

    Idempotent: only rows still `in_progress` are touched.
    """
    if not recovered_ids:
        return 0
    try:
        from core.chat_transport import CRASHED, IN_PROGRESS
        from core.models import AgentExecution, ChatRequestRecord
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"crashed chat-request release skipped: {exc}")
        return 0
    request_ids = [
        rid for rid in (
            _metadata_value(row.metadata_json, "request_id")
            for row in session.query(AgentExecution)
            .filter(AgentExecution.id.in_(recovered_ids)).all()
        ) if rid
    ]
    if not request_ids:
        return 0
    released = 0
    now = datetime.now(timezone.utc)
    for record in (session.query(ChatRequestRecord)
                   .filter(ChatRequestRecord.request_id.in_(request_ids))
                   .all()):
        if record.state != IN_PROGRESS:
            continue
        record.state = CRASHED
        record.error = ("the process restarted while this turn was in flight; "
                        "it did not complete. Send a new request_id to try again.")
        record.updated_at = now
        released += 1
    return released



def _metadata_dict(metadata: Any) -> Dict[str, Any]:
    """Return a metadata blob as a mutable dict, tolerating every stored shape."""
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    return {}


def _job_payload(summary: Any) -> Any:
    """Parse an AgentJob's persisted JSON payload without losing its shape.

    Returns a dict for a valid object (or an empty job), and ``None`` when a
    non-empty summary cannot be understood. The caller treats ``None`` as
    UNKNOWN and leaves the row alone: rewriting an unreadable payload would
    discard the only copy of whatever it contained.
    """
    if summary is None or summary == "":
        return {}
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except (ValueError, TypeError):
            return None
    if isinstance(summary, dict):
        return dict(summary)
    return None


def _valid_registry_prior_status(value: Any) -> bool:
    """Whether ``value`` is a safe, non-active AgentRegistry status to restore."""
    if not isinstance(value, str):
        return False
    token = value.strip().lower()
    if not token or token == ExecutionStatus.RUNNING.value:
        return False
    allowed = set(_SAFE_REGISTRY_PRIOR_STATUSES)
    try:
        allowed.update(
            str(member.value).strip().lower() for member in AgentStatus)
    except (TypeError, AttributeError):
        pass
    return token in allowed


def _restore_registry_after_job_recovery(
    session: Session, *, job_id: Any, agent_id: Any, prior_status: Any,
) -> bool:
    """Restore an agent that admission changed to ``running`` for this job.

    Every guard is required: this job's exact CAS must have won (the caller
    only invokes this after a rowcount of one), the recorded prior status must
    be valid and non-active, the registry must still be ``running``, and no
    other active job may exist for the same agent. The registry update runs in
    the caller's transaction, so the job transition and the restoration are
    one durable decision.
    """
    if not agent_id or not _valid_registry_prior_status(prior_status):
        return False
    other_active = (
        session.query(AgentJob.id)
        .filter(
            AgentJob.agent_id == agent_id,
            AgentJob.id != job_id,
            AgentJob.status.in_(_ACTIVE_JOB_STATUSES),
        )
        .first()
    )
    if other_active is not None:
        return False
    restored = session.execute(
        update(AgentRegistry)
        .where(
            AgentRegistry.id == agent_id,
            AgentRegistry.status == ExecutionStatus.RUNNING.value,
        )
        .values(status=prior_status)
    )
    return restored.rowcount == 1


def _recover_agent_jobs(session: Session) -> int:
    """Terminally fail AgentJobs whose admitted/dispatched owner is dead.

    Only ``pending`` and ``running`` jobs are candidates. The owner is the
    persisted JSON ``dispatch_owner`` once ``dispatch_started`` is true, and
    the persisted ``admission_owner`` before dispatch. ``owner_liveness`` is
    the sole authority: a live, self, cross-host or otherwise UNKNOWN owner
    leaves the row exactly as it was, waiting rows are never selected, and an
    unreadable payload is preserved rather than rewritten.

    The transition is an exact CAS on id, agent, original status and original
    summary. The existing payload is copied forward, then only the terminal
    outcome fields are replaced. A dispatched job is explicitly uncertain and
    must be reconciled; nothing here retries work or claims that no side effect
    occurred.

    Returns the number of jobs recovered.
    """
    from core.execution_ownership import HOSTNAME, owner_liveness

    rows = (
        session.query(AgentJob)
        .filter(AgentJob.status.in_(_ACTIVE_JOB_STATUSES))
        .all()
    )
    now = datetime.now(timezone.utc)
    recovered = 0
    for job in rows:
        original_status = str(job.status or "")
        if original_status not in _ACTIVE_JOB_STATUSES:
            continue
        original_summary = job.result_summary
        payload = _job_payload(original_summary)
        if payload is None:
            continue

        # Information-wait recovery owns jobs carrying a resume claim: the claim
        # transaction settles both the linked job and execution and never resends.
        # Skip them here so the generic dead-job sweep cannot terminalize them.
        resume_claim = payload.get("resume_claim")
        if isinstance(resume_claim, dict) and resume_claim:
            continue

        if "dispatch_started" in payload:
            dispatched = bool(payload.get("dispatch_started"))
        else:
            dispatched = bool(getattr(job, "dispatch_started", False))
        owner_key = "dispatch_owner" if dispatched else "admission_owner"
        owner = payload.get(owner_key)
        if owner is None:
            # Some deployments persist the owner in a JSON column beside the
            # summary. Both forms are the same durable claim.
            owner = getattr(job, owner_key, None)
        if isinstance(owner, str):
            try:
                owner = json.loads(owner)
            except (ValueError, TypeError):
                continue
        if not isinstance(owner, dict) or not owner.get("pid"):
            continue
        owner_host = owner.get("host")
        if owner_host != HOSTNAME:
            # A pid on another host is not evidence about this host.
            continue

        state, info = owner_liveness({"owner": owner})
        if state != "dead":
            continue
        if info.get("host") and info.get("host") != HOSTNAME:
            continue

        new_payload = dict(payload)
        new_payload["status"] = AgentJobStatus.FAILED.value
        new_payload["reason"] = "worker_crashed"
        if dispatched:
            # The process may have completed effects before dying. Record the
            # uncertainty; never retry and never assert a no-effect outcome.
            new_payload["outcome"] = "uncertain"
            new_payload["next_action"] = "reconcile_operation"
            new_payload["requires_reconciliation"] = True
        else:
            new_payload["outcome"] = "worker_crashed"
            new_payload["next_action"] = "review_failure"
            new_payload["requires_reconciliation"] = False
        new_payload["finished"] = True
        new_payload["waiting"] = False
        new_payload["recovery"] = {
            "crashed": True,
            "recovered_at": now.isoformat(),
            "owner_state": state,
            "owner_source": owner_key,
            "prior_job_status": original_status,
        }
        new_summary = json.dumps(new_payload, sort_keys=True)

        conditions = [
            AgentJob.id == job.id,
            AgentJob.agent_id == job.agent_id,
            AgentJob.status == original_status,
        ]
        if original_summary is None:
            conditions.append(AgentJob.result_summary.is_(None))
        else:
            conditions.append(AgentJob.result_summary == original_summary)
        claimed = session.execute(
            update(AgentJob)
            .where(*conditions)
            .values(
                status=AgentJobStatus.FAILED.value,
                result_summary=new_summary,
                end_time=now,
            ))
        if claimed.rowcount != 1:
            # A peer changed the job between the read and this CAS. Its state
            # wins; do not restore the registry on the strength of a lost claim.
            continue

        _restore_registry_after_job_recovery(
            session,
            job_id=job.id,
            agent_id=job.agent_id,
            prior_status=payload.get("prior_status"),
        )
        recovered += 1
    return recovered


def _scope_text(value: Any) -> Any:
    """Normalize a tenant/workspace value for comparison.

    ``None`` and an empty string both mean "not recorded". They are kept
    distinct from a real value so "one side did not record a scope" is not
    mistaken for "the scopes differ".
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _chain_workspace(chain: DelegationChain, root_agent: Any) -> Any:
    """The chain's workspace, from its blackboard or its root agent."""
    workspace = _scope_text(
        _metadata_dict(chain.metadata_json).get("workspace_id"))
    if workspace is None and root_agent is not None:
        workspace = _scope_text(getattr(root_agent, "workspace_id", None))
    return workspace


def _fleet_scope_conflicts(
    chain: DelegationChain, execution: AgentExecution, root_agent: Any,
) -> List[str]:
    """Which scopes DISAGREE between a chain and its purported root execution.

    A durable id match is the positive link, but an id is not a permission: if
    both sides record a tenant or workspace and they differ, this execution is
    not the owner of that chain in any scope-aware sense. The chain is left
    alone (and reported) rather than failed across a tenant/workspace boundary.
    A missing value on either side is not a disagreement -- older rows did not
    always record scope.
    """
    conflicts: List[str] = []
    chain_tenant = _scope_text(chain.tenant_id)
    execution_tenant = _scope_text(execution.tenant_id)
    if chain_tenant and execution_tenant and chain_tenant != execution_tenant:
        conflicts.append("tenant")
    chain_workspace = _chain_workspace(chain, root_agent)
    execution_workspace = _scope_text(execution.workspace_id)
    if (chain_workspace and execution_workspace
            and chain_workspace != execution_workspace):
        conflicts.append("workspace")
    return conflicts


def _duration_ms(started_at: Any, completed_at: datetime) -> Any:
    """Milliseconds between a link's DB timestamp and ``completed_at``.

    SQLite returns naive datetimes even for ``DateTime(timezone=True)``; mixing
    one with an aware ``completed_at`` raised TypeError in
    ``AgentFleetService.update_link_status``. Normalize before subtracting.
    """
    if started_at is None:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return max(0, int((completed_at - started_at).total_seconds() * 1000))


def _recover_fleet_chains(
    session: Session, recovered_ids: List[str],
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """Resolve fleet chains whose durable root execution this sweep just failed.

    ``DelegationChain.root_execution_id`` is the durable parent-to-chain
    binding; it is written when the fleet is initialized and survives a restart.
    Only a chain bound to an id in ``recovered_ids`` -- which contains ONLY
    executions whose owner was VERIFIED dead in this same sweep -- is touched.
    A live owner, an UNKNOWN owner, an unlinked chain and a chain whose scope
    disagrees with the execution are all left exactly as they are.

    Within a reconciled chain:

    * links whose work is already terminal (``completed`` above all) are kept;
      completed work really happened and recovery must not rewrite it;
    * links still waiting/running are marked ``failed`` with the crash truth,
      so no dashboard reports a fleet that can never advance;
    * the chain becomes ``failed`` with a ``recovery`` marker naming the dead
      root execution.

    Idempotent: a terminal chain is skipped, and only non-terminal links are
    rewritten, so re-running cannot restamp completed work.

    Returns ``(chains_recovered, links_reconciled, scope_skipped_detail)``.
    """
    execution_ids = [str(rid) for rid in recovered_ids if rid]
    if not execution_ids:
        return 0, 0, []

    executions = {
        str(row.id): row
        for row in session.query(AgentExecution)
        .filter(AgentExecution.id.in_(execution_ids))
        .all()
    }
    if not executions:
        return 0, 0, []

    chains = (
        session.query(DelegationChain)
        .filter(DelegationChain.root_execution_id.in_(list(executions)))
        .all()
    )
    if not chains:
        return 0, 0, []

    root_agent_ids = {
        str(chain.root_agent_id) for chain in chains if chain.root_agent_id
    }
    root_agents = {
        str(row.id): row
        for row in session.query(AgentRegistry)
        .filter(AgentRegistry.id.in_(list(root_agent_ids)))
        .all()
    } if root_agent_ids else {}

    now = datetime.now(timezone.utc)
    chains_recovered = 0
    links_reconciled = 0
    scope_skipped: List[Dict[str, Any]] = []

    for chain in chains:
        root_execution_id = _scope_text(chain.root_execution_id)
        execution = executions.get(root_execution_id)
        # Only a POSITIVE binding counts: no id, or an id outside this sweep's
        # verified-dead set, is not linked evidence.
        if execution is None:
            continue
        if str(chain.status or "").strip().lower() in _TERMINAL_CHAIN_STATUSES:
            continue

        root_agent = root_agents.get(str(chain.root_agent_id or ""))
        conflicts = _fleet_scope_conflicts(chain, execution, root_agent)
        if conflicts:
            scope_skipped.append({
                "chain_id": chain.id,
                "root_execution_id": root_execution_id,
                "tenant_id": chain.tenant_id,
                "workspace_id": _chain_workspace(chain, root_agent),
                "execution_tenant_id": execution.tenant_id,
                "execution_workspace_id": execution.workspace_id,
                "conflicts": conflicts,
            })
            continue

        links = (
            session.query(ChainLink)
            .filter(ChainLink.chain_id == chain.id)
            .all()
        )
        chain_link_failures = 0
        for link in links:
            if str(link.status or "").strip().lower() in _TERMINAL_LINK_STATUSES:
                continue
            link.status = "failed"
            link.error_message = (
                f"Parent execution {root_execution_id} crashed while this link "
                "was in progress (owner VERIFIED dead; recovered after restart)"
            )
            link.completed_at = now
            link.duration_ms = _duration_ms(link.started_at, now)
            chain_link_failures += 1

        metadata = _metadata_dict(chain.metadata_json)
        metadata["recovery"] = {
            "crashed": True,
            "recovered_at": now.isoformat(),
            "owner_state": "dead",
            "root_execution_id": root_execution_id,
            "links_failed": chain_link_failures,
        }
        chain.metadata_json = metadata
        chain.status = "failed"
        chain.completed_at = now

        chains_recovered += 1
        links_reconciled += chain_link_failures

    return chains_recovered, links_reconciled, scope_skipped



def reconcile_orphaned_executions() -> dict:
    """Find and fail executions orphaned by a process crash.

    Runs once at startup. Idempotent: only touches rows still in a running
    state, so re-running is a no-op once they've been reconciled.

    Returns:
        ``{"workflow_recovered": int, "agent_recovered": int,
           "agent_jobs_recovered": int,
           "agent_untouched_live": int, "agent_untouched_detail": [...],
           "agent_unknown_owner": int, "agent_unknown_detail": [...],
           "fleet_chains_recovered": int, "fleet_links_reconciled": int,
           "fleet_chain_scope_skipped": [...],
           "chat_requests_released": int, "enabled": bool}``

        Event-run additions: ``workflow_event_recovered`` (uncertain outcomes
        reconciled), ``workflow_event_left_running`` / ``workflow_event_detail``
        (left for explicit reconciliation),
        ``workflow_event_ownership_dependency`` and
        ``workflow_event_reconciliation_required``.  The separate dispatcher
        owns requeueing PENDING rows; this startup sweep never does that.
    """
    if not RECOVERY_ENABLED:
        logger.info("Execution recovery disabled (ATOM_EXECUTION_RECOVERY_ENABLED=false)")
        return {"workflow_recovered": 0, "agent_recovered": 0,
                "agent_jobs_recovered": 0,
                "agent_untouched_live": 0, "agent_untouched_detail": [],
                "agent_unknown_owner": 0, "agent_unknown_detail": [],
                "fleet_chains_recovered": 0, "fleet_links_reconciled": 0,
                "fleet_chain_scope_skipped": [],
                "workflow_event_recovered": 0,
                "workflow_event_left_running": 0,
                "workflow_event_detail": [],
                "workflow_event_ownership_dependency": False,
                "workflow_event_reconciliation_required": False,
                "chat_requests_released": 0, "enabled": False}

    session: Session = SessionLocal()
    event_report: Dict[str, Any] = {}
    try:
        wf_count = _recover_workflow_executions(
            session, event_report=event_report)
        (agent_count, untouched, untouched_detail,
         unknown, recovered_ids) = _recover_agent_executions(session)
        job_count = _recover_agent_jobs(session)
        (chain_count, link_count,
         chain_scope_skipped) = _recover_fleet_chains(session, recovered_ids)
        released = _release_crashed_chat_requests(session, recovered_ids)
        session.commit()
        event_recovered = event_report.get("workflow_event_recovered", 0)
        event_left = event_report.get("workflow_event_detail", [])
        if (wf_count or agent_count or job_count or released
                or chain_count or link_count or event_recovered):
            logger.warning(
                f"Crash recovery: reconciled {wf_count} workflow execution(s) "
                f"({event_recovered} event action(s) with UNCERTAIN outcomes), "
                f"{agent_count} agent execution(s) and {job_count} agent job(s) "
                f"with a VERIFIED dead owner; "
                f"failed {chain_count} fleet delegation chain(s) and "
                f"{link_count} non-terminal chain link(s) bound to them; "
                f"released {released} in-progress chat request(s); left "
                f"{untouched} alone (live owner), {len(unknown)} UNKNOWN "
                f"(ownership not established) and {len(event_left)} event "
                f"row(s) for explicit reconciliation"
            )
        else:
            # "no orphaned executions found" is only true when there was nothing
            # to look at. With candidates deliberately LEFT ALONE it is false,
            # and it was the reason the finish-line F11 investigation (2026-09-29)
            # could not see why a killed continuation's row stayed `running`:
            # the sweep reported success while a running row sat right there.
            # Name the rows and the verdict for each.
            if untouched or unknown or event_left:
                # `untouched` is a COUNT; the rows themselves are in
                # `untouched_detail` / `unknown`. Formatting the count as if it
                # were the list raised TypeError inside the sweep, which the
                # outer handler turned into "Execution recovery sweep failed" --
                # the sweep then reconciled nothing and reported nothing, the
                # same silence this branch exists to remove.
                logger.warning(
                    f"Crash recovery: no executions reconciled, but "
                    f"{untouched} running execution(s) were LEFT ALONE "
                    f"(live owner), {len(unknown)} are UNKNOWN (ownership "
                    f"not established) and {len(event_left)} event row(s) "
                    f"await explicit reconciliation: live={untouched_detail[:5]} "
                    f"unknown={unknown[:5]} events={event_left[:5]}"
                )
            else:
                logger.info("Crash recovery: no orphaned executions found")
        if unknown:
            # Loud on purpose: these are rows this process cannot account for.
            # They are NOT reconciled, so somebody has to be able to see them.
            for row in unknown:
                logger.warning(
                    "Crash recovery: ownership UNKNOWN, left running and NOT "
                    "declared crashed: execution=%s reason=%s owner=%s",
                    row.get("execution_id"), row.get("reason"),
                    {k: row.get(k) for k in ("pid", "host", "token")})
        for row in event_left:
            # A claimed event row is not replayed and is not failed on the
            # strength of "this process started".  Name it so the separate
            # dispatcher/reconciler can decide with the action-outcome context.
            logger.warning(
                "Crash recovery: event execution %s left RUNNING for explicit "
                "reconciliation (owner_state=%s owner_source=%s reason=%s)",
                row.get("execution_id"), row.get("owner_state"),
                row.get("owner_source"), row.get("reason"),
            )
        for row in chain_scope_skipped:
            # A durable id matched but the recorded scope did not. Failing the
            # chain across that boundary would be a cross-tenant write on the
            # strength of an id alone, so it is reported instead.
            logger.warning(
                "Crash recovery: fleet chain %s is bound to dead execution %s "
                "but its scope disagrees (%s); left untouched: chain_tenant=%s "
                "chain_workspace=%s execution_tenant=%s execution_workspace=%s",
                row.get("chain_id"), row.get("root_execution_id"),
                ",".join(row.get("conflicts") or []), row.get("tenant_id"),
                row.get("workspace_id"), row.get("execution_tenant_id"),
                row.get("execution_workspace_id"))
        return {
            "workflow_recovered": wf_count,
            "agent_recovered": agent_count,
            "agent_jobs_recovered": job_count,
            "agent_untouched_live": untouched,
            "agent_untouched_detail": untouched_detail,
            "agent_unknown_owner": len(unknown),
            "agent_unknown_detail": unknown,
            "fleet_chains_recovered": chain_count,
            "fleet_links_reconciled": link_count,
            "fleet_chain_scope_skipped": chain_scope_skipped,
            "chat_requests_released": released,
            "workflow_event_recovered": event_report.get(
                "workflow_event_recovered", 0),
            "workflow_event_left_running": event_report.get(
                "workflow_event_left_running", 0),
            "workflow_event_detail": event_report.get(
                "workflow_event_detail", []),
            "workflow_event_ownership_dependency": event_report.get(
                "workflow_event_ownership_dependency", False),
            "workflow_event_reconciliation_required": event_report.get(
                "workflow_event_reconciliation_required", False),
            "enabled": True,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Execution recovery sweep failed: {e}")
        return {"workflow_recovered": 0, "agent_recovered": 0,
                "agent_jobs_recovered": 0,
                "agent_untouched_live": 0, "agent_untouched_detail": [],
                "agent_unknown_owner": 0, "agent_unknown_detail": [],
                "fleet_chains_recovered": 0, "fleet_links_reconciled": 0,
                "fleet_chain_scope_skipped": [],
                "workflow_event_recovered": 0,
                "workflow_event_left_running": 0,
                "workflow_event_detail": [],
                "workflow_event_ownership_dependency": False,
                "workflow_event_reconciliation_required": False,
                "chat_requests_released": 0, "enabled": True, "error": str(e)}
    finally:
        session.close()
