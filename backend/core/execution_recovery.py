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
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import (
    AgentExecution,
    AgentRegistry,
    ChainLink,
    DelegationChain,
    ExecutionStatus,
    WorkflowExecution,
    WorkflowExecutionStatus,
)

logger = logging.getLogger(__name__)

RECOVERY_ENABLED = os.getenv("ATOM_EXECUTION_RECOVERY_ENABLED", "true").lower() == "true"

_CRASH_ERROR_MESSAGE = "Process restarted while execution was running (crashed)"

#: Chain statuses that are already resolved. A chain in one of these states has
#: nothing left to recover, even if it still points at a dead root execution.
_TERMINAL_CHAIN_STATUSES = frozenset({"completed", "failed", "cancelled", "canceled"})

#: Link statuses whose work is already resolved. ``completed`` means the
#: specialist's work really happened and must never be rewritten by recovery;
#: the failure/cancel/skip states are equally terminal. Everything else
#: (pending, in_progress, processing, active, ...) is orphaned by definition
#: once the chain's root execution is verified dead.
_TERMINAL_LINK_STATUSES = _TERMINAL_CHAIN_STATUSES | frozenset({"skipped"})



def _recover_workflow_executions(session: Session) -> int:
    """Mark orphaned RUNNING WorkflowExecution rows as FAILED.

    Returns the count recovered.
    """
    rows = (
        session.query(WorkflowExecution)
        .filter(WorkflowExecution.status == WorkflowExecutionStatus.RUNNING.value)
        .all()
    )
    now = datetime.now(timezone.utc)
    recovered = 0
    for row in rows:
        row.status = WorkflowExecutionStatus.FAILED.value
        row.error = _CRASH_ERROR_MESSAGE
        row.completed_at = now
        # Stamp a recovery marker in context (JSON-stored) so operators can
        # distinguish crash-recovered failures from genuine logic failures.
        ctx = {}
        if row.context:
            try:
                ctx = json.loads(row.context) if isinstance(row.context, str) else dict(row.context)
            except (ValueError, TypeError):
                ctx = {}
        ctx.setdefault("recovery", {})
        ctx["recovery"] = {"crashed": True, "recovered_at": now.isoformat()}
        row.context = json.dumps(ctx)
        recovered += 1
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
           "agent_untouched_live": int, "agent_untouched_detail": [...],
           "agent_unknown_owner": int, "agent_unknown_detail": [...],
           "fleet_chains_recovered": int, "fleet_links_reconciled": int,
           "fleet_chain_scope_skipped": [...],
           "chat_requests_released": int, "enabled": bool}``
    """
    if not RECOVERY_ENABLED:
        logger.info("Execution recovery disabled (ATOM_EXECUTION_RECOVERY_ENABLED=false)")
        return {"workflow_recovered": 0, "agent_recovered": 0,
                "agent_untouched_live": 0, "agent_untouched_detail": [],
                "agent_unknown_owner": 0, "agent_unknown_detail": [],
                "fleet_chains_recovered": 0, "fleet_links_reconciled": 0,
                "fleet_chain_scope_skipped": [],
                "chat_requests_released": 0, "enabled": False}

    session: Session = SessionLocal()
    try:
        wf_count = _recover_workflow_executions(session)
        (agent_count, untouched, untouched_detail,
         unknown, recovered_ids) = _recover_agent_executions(session)
        (chain_count, link_count,
         chain_scope_skipped) = _recover_fleet_chains(session, recovered_ids)
        released = _release_crashed_chat_requests(session, recovered_ids)
        session.commit()
        if wf_count or agent_count or released or chain_count or link_count:
            logger.warning(
                f"Crash recovery: reconciled {wf_count} workflow execution(s) and "
                f"{agent_count} agent execution(s) with a VERIFIED dead owner; "
                f"failed {chain_count} fleet delegation chain(s) and "
                f"{link_count} non-terminal chain link(s) bound to them; "
                f"released {released} in-progress chat request(s); left "
                f"{untouched} alone (live owner) and {len(unknown)} UNKNOWN "
                f"(ownership not established -- not touched, not declared crashed)"
            )
        else:
            # "no orphaned executions found" is only true when there was nothing
            # to look at. With candidates deliberately LEFT ALONE it is false,
            # and it was the reason the finish-line F11 investigation (2026-09-29)
            # could not see why a killed continuation's row stayed `running`:
            # the sweep reported success while a running row sat right there.
            # Name the rows and the verdict for each.
            if untouched or unknown:
                # `untouched` is a COUNT; the rows themselves are in
                # `untouched_detail` / `unknown`. Formatting the count as if it
                # were the list raised TypeError inside the sweep, which the
                # outer handler turned into "Execution recovery sweep failed" --
                # the sweep then reconciled nothing and reported nothing, the
                # same silence this branch exists to remove.
                logger.warning(
                    f"Crash recovery: no executions reconciled, but "
                    f"{untouched} running execution(s) were LEFT ALONE "
                    f"(live owner) and {len(unknown)} are UNKNOWN (ownership "
                    f"not established): "
                    f"live={untouched_detail[:5]} unknown={unknown[:5]}"
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
            "agent_untouched_live": untouched,
            "agent_untouched_detail": untouched_detail,
            "agent_unknown_owner": len(unknown),
            "agent_unknown_detail": unknown,
            "fleet_chains_recovered": chain_count,
            "fleet_links_reconciled": link_count,
            "fleet_chain_scope_skipped": chain_scope_skipped,
            "chat_requests_released": released,
            "enabled": True,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Execution recovery sweep failed: {e}")
        return {"workflow_recovered": 0, "agent_recovered": 0,
                "agent_untouched_live": 0, "agent_untouched_detail": [],
                "agent_unknown_owner": 0, "agent_unknown_detail": [],
                "fleet_chains_recovered": 0, "fleet_links_reconciled": 0,
                "fleet_chain_scope_skipped": [],
                "chat_requests_released": 0, "enabled": True, "error": str(e)}
    finally:
        session.close()
