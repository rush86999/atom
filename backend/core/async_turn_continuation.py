"""Durable, idempotent async turn continuation: finish starved edit turns
in the background.

SCOPE AND GROUNDING (2026-09-22). This addresses the SEPARATELY demonstrated
timeout case — canvas-edit turns whose edit leg died at its interactive
bound while the shared planner outran the cap (live traces: the
turn_budget_exceeded turn at uvicorn_8001_restart.log:4987065; the 65s/75s
edit-leg bound deaths with planners of 41.5–60.3s). It does NOT touch the
original evidence-validation incident, which is fixed and verified
(commits 73c9fe7c6…40f4d997e).

Acceptance criteria (each pinned by tests here):
- The synchronous turn returns inside its budget with an honest
  "finishing in the background" note.
- The background attempt ends in a DISTINCT honest outcome —
  ``applied`` | ``awaiting_approval`` (learning-mode draft, "ready for
  review", not "completed") | ``already_applied`` (idempotency: the timed-out
  attempt's write landed after all) | ``conflict`` (the canvas changed under
  us) | ``failed`` | ``cancelled`` — and never applies twice.
- The result is visible to the NEXT conversational turn (in-memory session
  append), after reconnect (DB row), and after restart (hydration) — not
  only as a notification.
- A restart mid-continuation ends honestly: the existing
  ``core.execution_recovery`` sweep marks the durable row failed, and this
  module's recovery pass notifies the user.

ARCHITECTURE (built on existing infrastructure — no new scheduler):
- Durable state rides ``AgentExecution`` rows (``triggered_by="continuation"``,
  payload in ``metadata_json["continuation"]``); the boot sweep
  ``reconcile_orphaned_executions()`` already converts crashed "running"
  rows to failed, and ``notify_recovered_continuations()`` (called from the
  lifespan recovery slot) adds the user notification for those.
- One-in-flight is enforced by the DURABLE row (a DB query — correct across
  restarts and workers), with the in-process map as a fast path.
- Idempotency: the fork snapshots the canvas content hash and the latest
  CanvasAudit timestamp. Before retrying, an audit advance attributed to the
  SAME session means the timed-out attempt's write landed after all
  (``already_applied``); a content-hash change from any other source is a
  ``conflict`` and the retry refuses to apply. The editor's own patch-match
  refusal (``ops_no_longer_match``) remains the innermost layer.
- A NEW user turn in the session SUPERSEDES: the orchestrator cancels any
  pending continuation at turn entry (new instruction wins).
- Background context is NOT interactive: provider calls here yield to live
  turns under the interactive rate reserve and latency gate, by design.
"""
import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

#: Total wall-clock budget for one continuation (the async tier — the
#: interactive TurnDeadline does not apply; the edit leg's internal waits
#: bound the realistic tail well below this).
_ASYNC_CONTINUATION_BUDGET_SECONDS = float(
    os.getenv("ATOM_ASYNC_CONTINUATION_BUDGET", "300") or 300)

#: The retry's EDIT-PLAN timeout. The interactive leg's 30s inner bound is
#: calibrated for the interactive tier; a slow-but-healthy provider rung
#: (deepseek-v4-pro thinking latency) routinely exceeds it — without this
#: scaling the async tier's 300s budget cannot rescue the very turns it
#: exists for (live 2026-09-22: continuations died at exactly dur=30s with
#: "edit planner could not complete" while the fleet served other calls).
_ASYNC_EDIT_PLAN_TIMEOUT_SECONDS = float(
    os.getenv("ATOM_ASYNC_EDIT_PLAN_TIMEOUT", "150") or 150)

#: BACKOFF-AND-RETRY (2026-09-22): the interactive turn that starved the
#: edit ALSO drains the shared per-model rate budgets — an immediate retry
#: can find zero dispatchable routes (live: continuation failed in 0s with
#: every route benched or rate-exhausted, while the same routes served
#: calls minutes later). Waiting IS the async tier's advantage: retry the
#: edit after a backoff, bounded by attempts and the total budget.
_ASYNC_CONTINUATION_RETRY_DELAY_SECONDS = float(
    os.getenv("ATOM_ASYNC_CONTINUATION_RETRY_DELAY", "45") or 45)
_ASYNC_CONTINUATION_ATTEMPTS = max(
    1, int(os.getenv("ATOM_ASYNC_CONTINUATION_ATTEMPTS", "3") or 3))

#: Outcome vocabulary (metadata_json.continuation.outcome). Deliberately
#: distinct: "awaiting_approval" is a draft ready for review, NOT a
#: completion; "already_applied" and "conflict" never re-apply.
OUTCOME_APPLIED = "applied"
OUTCOME_AWAITING_APPROVAL = "awaiting_approval"
OUTCOME_ALREADY_APPLIED = "already_applied"
OUTCOME_CONFLICT = "conflict"
OUTCOME_FAILED = "failed"
OUTCOME_CANCELLED = "cancelled"

_OUTCOME_TO_EXECUTION_STATUS = {
    OUTCOME_APPLIED: "completed",
    OUTCOME_AWAITING_APPROVAL: "completed",
    OUTCOME_ALREADY_APPLIED: "completed",
    OUTCOME_CONFLICT: "completed",   # decided honestly; nothing to apply
    OUTCOME_FAILED: "failed",
    OUTCOME_CANCELLED: "cancelled",
}

_OUTCOME_NOTIFICATION_TYPE = {
    OUTCOME_APPLIED: "async_turn_applied",
    OUTCOME_AWAITING_APPROVAL: "async_turn_awaiting_review",
    OUTCOME_ALREADY_APPLIED: "async_turn_applied",
    OUTCOME_CONFLICT: "async_turn_conflict",
    OUTCOME_FAILED: "async_turn_failed",
    OUTCOME_CANCELLED: "async_turn_cancelled",
}


def _m3_enabled() -> bool:
    return os.getenv("CHAT_FINALIZATION_M3") == "1"


def _mark_continuation_notified(continuation_id: str) -> bool:
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            row = db.query(AgentExecution).filter(
                AgentExecution.id == continuation_id).first()
            if row is None:
                return False
            meta = dict(row.metadata_json or {})
            cont_meta = dict(meta.get("continuation") or {})
            cont_meta["notified"] = True
            meta["continuation"] = cont_meta
            row.metadata_json = meta
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(row, "metadata_json")
        return True
    except Exception as e:  # noqa: BLE001 — marking is best-effort
        logger.debug(f"continuation notified-mark skipped: {e}")
        return False


@dataclass
class AsyncTurnContinuation:
    continuation_id: str
    user_id: str
    session_id: str
    message: str
    canvas: Dict[str, Any]
    execution_id: Optional[str]
    agent_id: Optional[str]
    history_snapshot: list
    provenance: Optional[Dict[str, Any]] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Idempotency snapshot, taken at fork time.
    snapshot_content_hash: str = ""
    snapshot_audit_ts: str = ""
    # IDENTITY CONTRACT (2026-09-27, acceptance c16 case 2). A canvas edit
    # carries FOUR distinct ids and they are equal by nothing:
    #   execution_id        the interactive turn that was answered
    #   origin_operation_id that turn's task-lifecycle reservation -- THIS is
    #                       the id the write path stamps into
    #                       CanvasAudit.details_json.operation_id
    #   continuation_id     this background continuation
    #   audit row id        the mutation itself
    # The interactive attempt that timed out structurally cannot know the
    # continuation_id, so a probe that assumed operation_id ==
    # continuation_id could never see the write that actually landed, and a
    # durably-applied edit was reported unconfirmed on every attempt (live:
    # audit b3cb9277 carried operation_id 1e57dfae while the continuation was
    # 3fe40fae). Carrying the origin operation id makes the relationship
    # explicit, so the mutation is located THROUGH it rather than guessed at.
    origin_operation_id: str = ""
    # EVIDENCE HANDOFF (review item 2): the turn's already-retrieved
    # evidence block — the reply path's search found data the edit's own
    # fresh-data search missed (live 2026-09-23: reply had 4/4 slitter
    # prices; edit applied placeholders). The continuation injects this
    # as existing_block so the retry REUSES it instead of re-searching.
    evidence_block: str = ""
    evidence_contract: Optional[Dict[str, Any]] = None
    # Terminal state.
    outcome: str = ""
    summary: str = ""
    error: str = ""
    failure_stage: str = ""
    readback_required: bool = False
    audit_id: str = ""
    postcondition_verified: Optional[bool] = None
    review_status: str = ""


#: In-process handles (fast path). The DURABLE record is the AgentExecution
#: row; the DB query is the authority for one-in-flight across restarts.
_continuations: Dict[str, AsyncTurnContinuation] = {}
_tasks: Dict[str, asyncio.Task] = {}
_SESSION_IN_FLIGHT: Dict[str, str] = {}


def continuation_in_flight(session_id: str) -> Optional[str]:
    """The continuation id currently running for ``session_id``. The CLAIM
    row is the authority (atomic insert; see _claim_session); the
    in-process map is a fast path."""
    local = _SESSION_IN_FLIGHT.get(session_id)
    if local:
        return local
    try:
        return _claimed_id(session_id)
    except Exception:  # noqa: BLE001 — best-effort guard
        return None


def _claim_session(cont: AsyncTurnContinuation) -> bool:
    """ATOMIC one-in-flight claim: INSERT a claim row keyed by session_id.
    The PRIMARY KEY makes the insert itself the exclusion — two racing
    workers cannot both succeed (review 2026-09-22: a durable ROW alone is
    check-then-act, not exclusivity). DB-less harnesses degrade to the
    in-process map only."""
    from core.database import get_db_session
    from core.models import AsyncContinuationClaim

    with get_db_session() as db:
        db.add(AsyncContinuationClaim(
            session_id=cont.session_id,
            continuation_id=cont.continuation_id,
            user_id=cont.user_id,
            canvas_id=(cont.canvas or {}).get("canvas_id"),
        ))
    return True


def _claimed_id(session_id: str) -> Optional[str]:
    from core.database import get_db_session
    from core.models import AsyncContinuationClaim

    with get_db_session() as db:
        row = db.query(AsyncContinuationClaim).filter(
            AsyncContinuationClaim.session_id == session_id).first()
        return row.continuation_id if row else None


def _release_claim(session_id: str) -> None:
    try:
        from core.database import get_db_session
        from core.models import AsyncContinuationClaim

        with get_db_session() as db:
            db.query(AsyncContinuationClaim).filter(
                AsyncContinuationClaim.session_id == session_id
            ).delete()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"claim release skipped: {e}")


def _claim_insert_refused(session_id: str) -> bool:
    """True when a claim already exists (used by start_continuation's race
    path: insert-failure = someone else owns the session)."""
    return _claimed_id(session_id) is not None


def get_continuation(continuation_id: str) -> Optional[AsyncTurnContinuation]:
    return _continuations.get(continuation_id)


def cancel_continuation(
    session_id: str, canvas_id: Optional[str] = None
) -> bool:
    """Cancel the in-flight continuation for a session — used when a NEW
    user turn supersedes it, or on explicit stop. Returns True when one was
    cancelled."""
    cid = _SESSION_IN_FLIGHT.get(session_id)
    if not cid:
        return False
    if canvas_id is not None:
        active = _continuations.get(cid)
        active_canvas = str((active.canvas or {}).get("canvas_id") or "") \
            if active is not None else ""
        if not active_canvas:
            try:
                from core.database import get_db_session
                from core.models import AsyncContinuationClaim

                with get_db_session() as db:
                    row = db.query(AsyncContinuationClaim).filter(
                        AsyncContinuationClaim.session_id == session_id
                    ).first()
                    active_canvas = str(
                        (row.canvas_id if row is not None else "") or ""
                    )
            except Exception:  # noqa: BLE001
                active_canvas = ""
        if active_canvas != str(canvas_id):
            return False
    task = _tasks.get(cid)
    if task and not task.done():
        task.cancel()
    return True


def _reap(continuation_id: str, session_id: str) -> None:
    _tasks.pop(continuation_id, None)
    if _SESSION_IN_FLIGHT.get(session_id) == continuation_id:
        _SESSION_IN_FLIGHT.pop(session_id, None)
    _release_claim(session_id)


def _bounded_evidence_contract(
    contract: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(contract, dict):
        return None
    coverage = contract.get("coverage") or {}
    def _action(item: Any) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        expected = item.get("expected")
        return {
            "action_type": item.get("action_type"),
            "entity_id": item.get("entity_id"),
            "field": item.get("field"),
            "current_value": item.get("current_value"),
            "proposed_value": item.get("proposed_value"),
            "status": item.get("status"),
            "authorized": item.get("authorized") is True,
            "applied": item.get("applied") is True,
            "evidence_ids": [
                str(value) for value in (item.get("evidence_ids") or [])[:16]
                if value
            ],
            "expected": {
                str(key): expected.get(key)
                for key in (
                    "raw_value", "currency", "unit", "basis",
                    "field_meaning", "destination_field_meaning",
                )
                if isinstance(expected, dict) and expected.get(key) is not None
            },
        }
    evidence_ids = [
        str(item.get("observation_id"))
        for item in contract.get("evidence") or []
        if isinstance(item, dict) and item.get("observation_id")
    ]
    return {
        "contract_version": contract.get("contract_version"),
        "coverage": {
            "requested_entities": [
                str(item) for item in (coverage.get("requested_entities") or [])[:64]
            ],
            "requested_fields": [
                str(item) for item in (coverage.get("requested_fields") or [])[:32]
            ],
            "outcome_count": coverage.get("outcome_count"),
            "complete": coverage.get("complete") is True,
        },
        "actions": [_action(item) for item in (contract.get("actions") or [])[:50]],
        "blocked_actions": [
            _action(item) for item in (contract.get("blocked_actions") or [])[:50]
        ],
        "evidence_ids": list(dict.fromkeys(evidence_ids))[:100],
        "implications": [
            str(item.get("statement"))[:500]
            for item in (contract.get("implications") or [])
            if isinstance(item, dict) and item.get("statement")
        ][:20],
    }


# ---------------------------------------------------------------------------
# Durable record (AgentExecution rows)
# ---------------------------------------------------------------------------

def _create_durable_record(cont: AsyncTurnContinuation) -> None:
    """Persist the continuation as a RUNNING AgentExecution row — the
    durable job record. ``reconcile_orphaned_executions`` at boot converts
    crashed rows to failed; ``notify_recovered_continuations`` then
    notifies. Best-effort: a DB-less harness simply runs without the
    durable layer (the in-process guard still holds within one process)."""
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            # OS OWNERSHIP EVIDENCE (2026-09-28): without a stamped owner
            # block the crash sweep cannot VERIFY this record's holder is
            # dead, leaves it `running` forever, and terminal recovery never
            # sees it — the user's chat stays stuck on the pre-crash
            # acknowledgement. Stamp pid + process start so a later sweep
            # can prove the owner is gone and reconcile the record.
            from core.execution_ownership import record_os_start

            db.add(AgentExecution(
                id=cont.continuation_id,
                agent_id=cont.agent_id,
                status="running",
                input_summary=cont.message[:300],
                triggered_by="continuation",
                metadata_json=record_os_start({
                    "session_id": cont.session_id,
                    "surface": "async_turn_continuation",
                    # EXACT ORIGIN BINDING (2026-09-25 review round 5): the
                    # canvas-claim guard verifies a write only against the
                    # operation set of THIS execution — itself plus the
                    # continuations it forked (which stamp their own
                    # continuation_id as operation_id).
                    "originating_execution_id": cont.execution_id,
                    # The identity contract, made DURABLE: the interactive
                    # turn's lifecycle operation id, which is the id the write
                    # path stamps on the audit row. Without it in the record
                    # the relationship between this continuation and the
                    # mutation it is responsible for is not reconstructable
                    # after a restart, and the mutation cannot be located.
                    "origin_operation_id": (
                        getattr(cont, "origin_operation_id", "") or None),
                    "continuation": {
                        "session_id": cont.session_id,
                        "canvas_id": (cont.canvas or {}).get("canvas_id"),
                        "user_id": cont.user_id,
                        "message": cont.message[:500],
                        "snapshot_content_hash": cont.snapshot_content_hash,
                        "snapshot_audit_ts": cont.snapshot_audit_ts,
                        "origin_operation_id": (
                            getattr(cont, "origin_operation_id", "") or None),
                        "failure_stage": cont.failure_stage,
                        "evidence_contract": _bounded_evidence_contract(
                            cont.evidence_contract
                        ),
                    },
                })))

    except Exception as e:  # noqa: BLE001 — durability is best-effort
        logger.debug(f"continuation durable record skipped: {e}")


def _durable_running_id(session_id: str) -> Optional[str]:
    """Any RUNNING continuation execution for this session (the
    cross-restart one-in-flight authority)."""
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        rows = (
            db.query(AgentExecution)
            .filter(
                AgentExecution.triggered_by == "continuation",
                AgentExecution.status == "running",
            )
            .all()
        )
        for row in rows:
            try:
                meta = row.metadata_json or {}
            except Exception:
                continue
            if (meta.get("continuation") or {}).get(
                    "session_id") == session_id:
                return str(row.id)
    return None


def _finish_durable_record(
    cont: AsyncTurnContinuation, outcome: str, summary: str
) -> None:
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        status = _OUTCOME_TO_EXECUTION_STATUS.get(outcome, "failed")
        with get_db_session() as db:
            row = db.query(AgentExecution).filter(
                AgentExecution.id == cont.continuation_id).first()
            if row is None:
                return
            row.status = status
            row.completed_at = datetime.now(timezone.utc)
            # READABLE TERMINAL OUTCOME (D5, 2026-09-28). This column is what a
            # reload renders, so it carries a sentence, not the internal
            # ``[outcome] <raw summary>`` diagnostic. The machine-readable
            # binding is already in the row's metadata (continuation.outcome,
            # .summary, .failure_stage, .audit_id, .review_status), so the
            # prefix duplicated metadata while reading as a debug line.
            row.result_summary = _readable_outcome_text(outcome, summary)[:400]
            meta = dict(row.metadata_json or {})
            cont_meta = meta.get("continuation") or {}
            cont_meta["outcome"] = outcome
            cont_meta["summary"] = summary[:500]
            if not _m3_enabled():
                cont_meta["notified"] = True
            cont_meta["failure_stage"] = cont.failure_stage
            cont_meta["evidence_contract"] = _bounded_evidence_contract(
                cont.evidence_contract
            )
            cont_meta["audit_id"] = cont.audit_id or None
            cont_meta["postcondition_verified"] = cont.postcondition_verified
            cont_meta["review_status"] = cont.review_status or None
            meta["continuation"] = cont_meta
            row.metadata_json = meta
            # JSON columns need an explicit dirty flag when the value is
            # reassigned from a read-back copy on some session states —
            # without it the status flip persists but the JSON does not
            # (observed live 2026-09-22: outcome=None in the row).
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(row, "metadata_json")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation durable finish skipped: {e}")


def _recovery_effect_status(cont: Dict[str, Any]) -> str:
    """Did THIS continuation's edit land before the interruption?

    Attribution is OPERATION-LINKED, never hash-based: a canvas hash change
    proves only that SOMETHING changed — another turn could have written it,
    and conversely this edit could have landed and later been superseded.
    The write path stamps the logical operation into the audit row
    (``canvas_audit.details_json.operation_id``), and the durable record
    carries that id as ``origin_operation_id``, so:

      "landed"     an audit row whose operation_id equals THIS
                   continuation's origin_operation_id OR its own
                   continuation id (a forked continuation stamps its own
                   id as the audit operation) exists
      "uncertain"  no linked row, but the canvas differs from the fork-time
                   snapshot — the change may be this edit (superseded later)
                   or another turn's; the record cannot tell. Recovery
                   reports UNCERTAINTY, never success or "nothing changed".
      "none"       canvas identical to the fork-time snapshot
      "unknown"    attribution unavailable (no canvas / no snapshot / error)
    """
    from sqlalchemy import text

    from core.database import get_db_session
    from core.models import Canvas

    canvas_id = cont.get("canvas_id")
    origin_op = str(cont.get("origin_operation_id") or "")
    own_id = str(cont.get("continuation_id") or "")
    # A forked continuation stamps ITS OWN id as the audit operation; the
    # interactive turn's operation id is the other legal linkage.
    op_ids = [o for o in (origin_op, own_id) if o]
    snapshot = str(cont.get("snapshot_content_hash") or "")
    if not canvas_id:
        return "unknown"
    try:
        if op_ids:
            with get_db_session() as db:
                linked = 0
                for op in op_ids:
                    linked += db.execute(
                        text("SELECT count(*) FROM canvas_audit "
                             "WHERE canvas_id = :cid AND "
                             "json_extract(details_json, "
                             "'$.operation_id') = :op"),
                        {"cid": canvas_id, "op": op},
                    ).fetchone()[0]
            if linked:
                return "landed"
        if snapshot:
            with get_db_session() as db:
                row = db.query(Canvas).filter(
                    Canvas.id == canvas_id).first()
                if row is not None:
                    try:
                        content = json.loads(row.content) if isinstance(
                            row.content, str) else row.content
                    except Exception:
                        content = None
                    if content is not None:
                        changed = _content_hash({"content": content}) != (
                            snapshot)
                        return "uncertain" if changed else "none"
        return "unknown" if not origin_op else "uncertain"
    except Exception:  # noqa: BLE001 — wording must never block recovery
        return "unknown"


def _recovered_terminal_continuations(session_ids=None):
    """Terminal continuations whose durable terminal message is MISSING.

    This is the population the recovery pass acts on. A continuation is
    terminal once its outcome is recorded on the AgentExecution row, and
    delivered once a ChatMessage carrying its id exists. The gap between the
    two is the stranded-acknowledgment case: the row says the turn finished, the
    user's history has nothing about it.

    The CANVAS MUTATION IS NOT REPLAYED. Only the terminal message is missing;
    the write it describes already happened, and re-running it would be the
    duplicate-mutation bug this whole area exists to prevent. Nothing here
    touches the canvas.
    """
    from core.database import get_db_session
    from core.models import AgentExecution, ChatMessage as ChatMessageModel

    out = []
    with get_db_session() as db:
        rows = db.query(AgentExecution).all()
        for row in rows:
            meta = row.metadata_json or {}
            if not isinstance(meta, dict):
                continue
            cm = meta.get("continuation") or {}
            if not isinstance(cm, dict):
                continue
            outcome = cm.get("outcome")
            crashed = bool((meta.get("recovery") or {}).get("crashed"))
            if not outcome and not (crashed and not cm.get("notified")):
                # Terminal rows are candidates; so are rows the crash sweep
                # marked failed before their outcome was ever recorded (the
                # kill window sits between the mutation and the record) --
                # those get effect-attributed wording at delivery time.
                continue
            if cm.get("notified") and not outcome:
                continue
            cid = str(row.id)
            delivered = db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == str(
                    cm.get("session_id") or ""),
                ChatMessageModel.metadata_json.like(f"%{cid}%"),
            ).first() is not None
            if delivered:
                continue
            if session_ids and str(cm.get("session_id") or "") not in session_ids:
                continue
            out.append({
                "continuation_id": cid,
                "session_id": str(cm.get("session_id") or ""),
                "canvas_id": cm.get("canvas_id"),
                "outcome": str(outcome or ""),
                "summary": str(cm.get("summary") or ""),
                "execution_id": str(cm.get("originating_execution_id")
                                    or row.id or ""),
                # ATTRIBUTION INPUTS: the effect wording is decided against
                # operation-linked audit evidence, not the canvas hash alone.
                "origin_operation_id": str(
                    meta.get("origin_operation_id")
                    or cm.get("origin_operation_id") or ""),
                "snapshot_content_hash": str(
                    cm.get("snapshot_content_hash") or ""),
                "user_id": str(cm.get("user_id") or ""),
                "claimed": bool(cm.get("terminal_delivered")),
                "claimed_at": float(cm.get("terminal_delivered_at") or 0.0),
            })
    return out


async def recover_missing_terminal_deliveries(session_ids=None) -> Dict[str, int]:
    """Re-deliver terminal outcomes whose message never landed (F09).

    REPEATABLE BY CONSTRUCTION. This is a pure scan of durable state, not a
    one-shot event: a pass that meets an UNEXPIRED lease defers that row (the
    claim inside `_apply_effects` refuses it as in-flight) and a later pass,
    after expiry, delivers it. Nothing is scheduled by the lease itself, so
    this must be invoked again -- which is why it takes no scheduler into
    account and is safe to call directly with the general scheduler disabled.

    Never replays the canvas mutation: only the terminal message is written.

    ``session_ids`` narrows the scan to specific sessions. Production wants the
    whole population; a targeted repair, or a test against a shared scratch
    database, wants only its own rows, because a global scan there would act on
    state another test owns.
    """
    stats = {"candidates": 0, "deferred_in_flight": 0, "delivered": 0,
             "failed": 0, "details": []}
    lease = _terminal_delivery_lease_seconds()
    now = time.time()
    for cand in _recovered_terminal_continuations(session_ids=session_ids):
        stats["candidates"] += 1
        if cand["claimed"]:
            age = (now - cand["claimed_at"]) if cand["claimed_at"] else None
            if age is not None and age < lease:
                stats["deferred_in_flight"] += 1
                stats["details"].append({
                    "continuation_id": cand["continuation_id"],
                    "deferred": f"claimed {age:.1f}s ago, lease {lease:.0f}s"})
                continue
        shim = _recovery_shim(cand)
        _apply_recovery_wording(shim, cand)
        try:
            await _apply_effects(shim)
        except Exception as e:  # noqa: BLE001 — one bad row must not stop the pass
            stats["failed"] += 1
            stats["details"].append({
                "continuation_id": cand["continuation_id"],
                "error": f"{type(e).__name__}: {e}"})
            continue
        if shim._recovery_delivered:
            stats["delivered"] += 1
            stats["details"].append({
                "continuation_id": cand["continuation_id"],
                "delivered": cand["outcome"]})
        else:
            stats["deferred_in_flight"] += 1
            stats["details"].append({
                "continuation_id": cand["continuation_id"],
                "deferred": "claim refused (another holder owns it)"})
    logger.info(
        "[async-continuation] terminal-delivery recovery: %s",
        {k: v for k, v in stats.items() if k != "details"})
    return stats


def _recovery_shim(cand: Dict[str, Any]):
    """A minimal stand-in for a continuation whose process is gone.

    Carries only what the delivery path reads. `execution` is left alone: the
    row is already terminal, so there is nothing to re-execute, and this is what
    keeps the canvas mutation from being replayed.
    """
    shim = SimpleNamespace(
        continuation_id=cand["continuation_id"],
        session_id=cand["session_id"],
        user_id=cand.get("user_id") or "",
        message="",
        canvas={"canvas_id": cand.get("canvas_id")},
        execution_id=cand.get("execution_id") or "",
        agent_id=None,
        history_snapshot=[],
        outcome=cand["outcome"],
        summary=cand.get("summary") or "",
        evidence_contract=None,
        audit_id=None,
        postcondition_verified=False,
        review_status=None,
        provenance=None,
        snapshot_content_hash="",
        snapshot_audit_ts="",
        origin_operation_id=None,
        evidence_block="",
        readback_required=True,
        failure_stage="recovery",
        _orchestrator=None,
    )
    shim._recovery_delivered = False
    return shim


def _apply_recovery_wording(shim: Any, cand: Dict[str, Any]) -> None:
    """Effect-attributed, honest outcome wording for a recovered delivery.

    The mutation and the completion report are separate commits, so the
    interruption wording must never imply the mutation did not land — and a
    changed canvas does not prove THIS edit landed. Attribution is
    operation-linked (canvas_audit.details_json.operation_id ==
    origin_operation_id); when attribution is unavailable but the canvas
    differs from the fork snapshot, the outcome says UNCERTAIN.
    """
    effect = _recovery_effect_status({
        "canvas_id": cand.get("canvas_id"),
        "origin_operation_id": cand.get("origin_operation_id"),
        "continuation_id": cand.get("continuation_id"),
        "snapshot_content_hash": cand.get("snapshot_content_hash"),
    })
    if effect == "landed" and not cand.get("outcome"):
        shim.outcome = OUTCOME_ALREADY_APPLIED
        shim.summary = ("the edit itself landed before a restart cut off "
                        "its confirmation — the change is on the canvas; "
                        "no re-run needed")
    elif effect == "uncertain" and not cand.get("outcome"):
        shim.outcome = OUTCOME_FAILED
        shim.summary = ("the canvas changed while this edit was in flight "
                        "and the record cannot attribute the change to "
                        "this edit — check the canvas before relying on "
                        "either outcome")
    elif not cand.get("outcome"):
        shim.outcome = OUTCOME_FAILED
        shim.summary = ("the process restarted while this background edit "
                        "was in flight")
    else:
        shim.outcome = cand["outcome"]
        shim.summary = cand.get("summary") or ""
    shim.effect_on_canvas = effect


#: The recurring task handle, so shutdown can stop it cleanly.
_TERMINAL_RECOVERY_TASK: Optional[Any] = None


def terminal_recovery_interval_seconds() -> float:
    """How often the recurring pass re-scans.

    Must be comfortably BELOW the lease, because a claim only becomes
    reclaimable once its lease expires. A pass that ran less often than the
    lease would still eventually deliver, but the outcome would sit stranded
    for up to a full interval after it became recoverable -- which is the
    behaviour this task exists to remove.
    """
    try:
        return max(5.0, float(os.getenv(
            "ATOM_TERMINAL_RECOVERY_INTERVAL_SECONDS", "60")))
    except (TypeError, ValueError):
        return 60.0


async def _terminal_recovery_loop() -> None:
    """Re-deliver stranded terminal outcomes, on startup and then repeatedly.

    A repeatable FUNCTION is not a guarantee that a later pass happens: a single
    startup pass meets leases that have not expired yet and defers them, and
    nothing would come back. So the pass is a recurring task, independent of
    ENABLE_SCHEDULER, because a user who lost a background turn is owed its
    outcome whether or not this process runs a scheduler.
    """
    interval = terminal_recovery_interval_seconds()
    logger.info(
        "[async-continuation] terminal-delivery recovery task started "
        "(interval %.0fs, lease %.0fs)", interval,
        _terminal_delivery_lease_seconds())
    while True:
        try:
            out = await recover_missing_terminal_deliveries()
            if out.get("delivered") or out.get("deferred_in_flight"):
                logger.info(
                    "[async-continuation] terminal-delivery recovery: "
                    "delivered=%d deferred=%d candidates=%d",
                    out.get("delivered", 0), out.get("deferred_in_flight", 0),
                    out.get("candidates", 0))
        except asyncio.CancelledError:
            logger.info("[async-continuation] terminal-delivery recovery task "
                        "stopping")
            raise
        except Exception as e:  # noqa: BLE001 — the loop must survive a bad pass
            logger.error(f"terminal-delivery recovery pass failed: {e}")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("[async-continuation] terminal-delivery recovery task "
                        "stopping")
            raise


def start_terminal_delivery_recovery() -> bool:
    """Start the recurring recovery task once. Idempotent."""
    global _TERMINAL_RECOVERY_TASK
    if _TERMINAL_RECOVERY_TASK is not None and not _TERMINAL_RECOVERY_TASK.done():
        return False
    try:
        # get_running_loop, not get_event_loop: this is started from the
        # FastAPI lifespan, and get_event_loop is deprecated there and can hand
        # back a loop that is not the one this coroutine runs on.
        _TERMINAL_RECOVERY_TASK = asyncio.get_running_loop().create_task(
            _terminal_recovery_loop())
        return True
    except RuntimeError:
        logger.debug("terminal-delivery recovery task not started: no running "
                     "event loop")
        return False


async def stop_terminal_delivery_recovery() -> None:
    """Cancel the recurring task and wait for it, so shutdown is clean."""
    global _TERMINAL_RECOVERY_TASK
    task = _TERMINAL_RECOVERY_TASK
    _TERMINAL_RECOVERY_TASK = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass


def notify_recovered_continuations() -> Dict[str, int]:
    """Boot pass (after ``reconcile_orphaned_executions``).

    PRECISE POLICY (review 2026-09-22): a restart does NOT resume
    continuation execution — the durable record survives, the running
    process did not. The execution sweep marks the record failed
    ("process restarted"); this pass (a) clears STALE CLAIM rows so the
    session is not permanently blocked (a claim whose execution is no
    longer running is garbage), and (b) sends the honest failure
    notification exactly once per row (``notified`` flag). Resumption, if
    ever wanted, is a separate mechanism."""
    out = {"recovered_notified": 0, "stale_claims_cleared": 0}

    # (a) Stale claims: delete any claim whose execution is not running.
    try:
        from core.database import get_db_session
        from core.models import AgentExecution, AsyncContinuationClaim

        with get_db_session() as db:
            claims = db.query(AsyncContinuationClaim).all()
            stale = []
            for claim in claims:
                ex = db.query(AgentExecution).filter(
                    AgentExecution.id == claim.continuation_id).first()
                if ex is None or ex.status != "running":
                    stale.append(claim)
            for claim in stale:
                db.delete(claim)
        out["stale_claims_cleared"] = len(stale)
    except Exception as e:  # noqa: BLE001 — boot pass must never fail boot
        logger.warning(f"stale-claim clearing skipped: {e}")
    try:
        # DELIVERY DELEGATES TO THE ONE AUTHORITATIVE PATH: the recurring
        # terminal-delivery scan (recover_missing_terminal_deliveries) owns
        # candidate selection, effect-attributed wording, the fenced
        # _apply_effects delivery, and lease/expiry arbitration. Duplicating
        # that logic here created two independent claims that could disagree
        # or suppress each other; this pass now clears stale fork claims and
        # then delegates.
        # The scan is async; this boot pass is a SYNC entry point. Without a
        # running loop, run it to completion; with one (never the case from
        # startup, but defensive), schedule it rather than nest a loop.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            delivered = asyncio.run(recover_missing_terminal_deliveries())
        else:
            delivered = {"delivered": 0, "deferred_in_flight": 0}
        out["recovered_notified"] = delivered.get("delivered", 0)
        out["delivery_skipped"] = delivered.get("deferred_in_flight", 0)
    except Exception as e:  # noqa: BLE001 — boot pass must never fail boot
        logger.warning(f"continuation recovery pass skipped: {e}")
    return out


# ---------------------------------------------------------------------------
# Idempotency snapshot + pre-apply checks
# ---------------------------------------------------------------------------

def _content_hash(canvas: Dict[str, Any]) -> str:
    try:
        blob = json.dumps(
            (canvas or {}).get("content"), sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
    except Exception:  # noqa: BLE001
        return ""


def _latest_audit(canvas_id: str) -> Optional[Dict[str, Any]]:
    """(id, created_at iso, session_id, action_type) of the newest
    CanvasAudit row, or None."""
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit

        with get_db_session() as db:
            row = (
                db.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(CanvasAudit.created_at.desc())
                .first()
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "created_at": row.created_at.isoformat()
                if row.created_at else "",
                "session_id": row.session_id or "",
                "action_type": row.action_type or "",
            }
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation audit probe skipped: {e}")
        return None


def _operation_identity(cont: AsyncTurnContinuation) -> List[str]:
    """Every operation id that can legitimately carry THIS request's mutation.

    The write path stamps ``CanvasAudit.details_json.operation_id`` with the
    task-lifecycle operation id of whichever turn performed the write. When the
    interactive turn's edit was already in flight when the interactive bound
    expired, that write is the one that lands -- and it is stamped with the
    ORIGIN operation, never with the continuation id, which the interactive
    attempt could not know. Probing for ``operation_id == continuation_id``
    alone therefore could not see a landed write, and reported a
    durably-applied edit as unconfirmed on every attempt (live 2026-09-27:
    audit b3cb9277 carried operation_id 1e57dfae while the continuation was
    3fe40fae, so the write was invisible to its own continuation).

    Locating the mutation through this relationship is not a relaxation of
    verification: an id must match EXACTLY one of these attributed ids, the
    canvas must match, and the caller still has to pass the revision door and
    the read-back gate. It is the difference between "whose operation is this"
    and "does this id happen to equal my own".
    """
    ids = [str(cont.continuation_id or "")]
    origin = str(getattr(cont, "origin_operation_id", "") or "")
    if origin and origin not in ids:
        ids.append(origin)
    return [i for i in ids if i]


def _matched_operation_row(
    cont: AsyncTurnContinuation,
) -> Optional[Dict[str, Any]]:
    """The audit row carrying THIS request's mutation, located through the
    identity relationship, or None.

    Returns the ROW rather than just its review_status, so a caller can check
    revision currency before trusting that the mutation it found is still the
    canvas's current state.
    """
    canvas_id = (cont.canvas or {}).get("canvas_id")
    if not canvas_id:
        return None
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from core.sql_json import json_field_equals

        with get_db_session() as db:
            for op_id in _operation_identity(cont):
                q = json_field_equals(
                    db, CanvasAudit.details_json, "$.operation_id", op_id)
                for row in db.query(CanvasAudit).filter(
                    CanvasAudit.canvas_id == canvas_id,
                    *([q] if q is not None else [])).all() or []:
                    details = row.details_json or {}
                    if isinstance(details, str):
                        try:
                            details = json.loads(details)
                        except Exception:  # noqa: BLE001
                            details = {}
                    if not isinstance(details, dict):
                        continue
                    # EXACT attribution. The JSON predicate is an optimisation;
                    # this comparison is the decision, so a row that merely
                    # mentions the id cannot be mistaken for this operation's
                    # mutation.
                    if str(details.get("operation_id") or "") != op_id:
                        continue
                    return {
                        "audit_id": str(row.id),
                        "created_at": (row.created_at.isoformat()
                                       if row.created_at else ""),
                        "action_type": str(row.action_type or ""),
                        "session_id": str(row.session_id or ""),
                        "review_status": str(
                            details.get("review_status") or "unknown"),
                        "operation_id": op_id,
                    }
        return None
    except Exception as e:  # noqa: BLE001
        logger.debug(f"operation-row probe skipped: {e}")
        return None


def _operation_status(cont: AsyncTurnContinuation) -> Optional[str]:
    canvas_id = (cont.canvas or {}).get("canvas_id")
    if not canvas_id:
        return None
    row = _matched_operation_row(cont)
    return str(row["review_status"]) if row else None


def _operation_landed(cont: AsyncTurnContinuation) -> bool:
    return _operation_status(cont) == "accepted"


def _classify_preapply(cont: AsyncTurnContinuation) -> Optional[str]:
    """Idempotency + conflict gate before the retry applies anything.

    Returns an OUTCOME_* when the retry must NOT run (already_applied /
    conflict), else None to proceed. Rules, in order:
    - DEFINTIVE: an audit row carrying THIS continuation's operation_id ⇒
      a prior retry attempt of this very operation already landed
      (duplicate execution, cancellation racing the write, a crash after
      apply) — never apply twice.
    - HEURISTIC (documented limit): the interactive attempt that timed out
      cannot stamp an operation_id it did not know; for its unknown-outcome
      write we fall back to revision attribution — an audit advance past
      the fork snapshot attributed to the SAME session reads as the timed-
      out attempt's write having landed (already_applied); any other
      source's advance is a conflict. The atomic revision door at the
      write itself (expected_prior_audit_id) is the enforcement layer;
      this gate is the early honest exit.
    - The revision token is enforced again AT THE WRITE: the retry captures
      the latest audit id when it starts and update_canvas_content refuses
      on mismatch, so an edit arriving DURING the retry cannot be
      overwritten."""
    canvas_id = (cont.canvas or {}).get("canvas_id")
    if not canvas_id:
        return None
    # DEFENSIVE RECONCILIATION (2026-09-27). Locating the mutation is not
    # enough to call the request satisfied: the row found must still BE the
    # canvas's current revision. If something wrote after it, the canvas no
    # longer says what this request applied, so reporting "already applied"
    # would be a false completion -- fall through to the revision/currency
    # rules below instead. This NARROWS what counts as done.
    #
    # `_operation_landed` stays the PREDICATE (it is the module's documented
    # seam and what the cancellation path consults); the currency check is an
    # ADDITIONAL condition on top of it, never a replacement -- replacing it
    # silently detached every existing stub of that seam from this gate.
    if _operation_landed(cont):
        row = _matched_operation_row(cont)
        latest = _latest_audit(canvas_id) if row else None
        if row is None or latest is None or str(
                latest.get("id") or "") == str(row.get("audit_id") or ""):
            return OUTCOME_ALREADY_APPLIED
        logger.info(
            "[async-continuation] %s matched operation %s is superseded by %s "
            "on canvas %s; not claiming already-applied",
            cont.continuation_id, (row or {}).get("audit_id"),
            latest.get("id"), canvas_id)
    operation_status = _operation_status(cont)
    if operation_status == "pending_review":
        return OUTCOME_AWAITING_APPROVAL
    if operation_status not in {None, "unknown"}:
        return OUTCOME_CONFLICT
    latest = _latest_audit(canvas_id)
    if latest and cont.snapshot_audit_ts and (
            latest["created_at"] > cont.snapshot_audit_ts):
        if latest["session_id"] == cont.session_id:
            return OUTCOME_ALREADY_APPLIED
        return OUTCOME_CONFLICT
    return None


# ---------------------------------------------------------------------------
# Runner + effects
# ---------------------------------------------------------------------------

def _verified_zero_effect(cont: AsyncTurnContinuation) -> Tuple[bool, Dict[str, Any]]:
    """Did this continuation verifiably change NOTHING on its canvas?

    "Nothing was changed on the canvas" is a claim about the world, and the two
    places that used to say it had no evidence for it: a run that exhausted its
    retry count, and a run that exhausted its budget. Either can end AFTER a write
    landed -- that is the whole D0 hazard, one layer up. An exhausted counter says
    "we stopped trying"; it does not say "nothing happened".

    So the claim is gated on two independent observations, both read from the
    durable store:

      1. no audit row for this canvas is newer than the fork snapshot, i.e. the
         canvas's audit trail has not advanced since this continuation started;
      2. no audit row carries an operation id this continuation legitimately owns
         (``_operation_identity``: its own, or its origin's).

    Either observation failing means the answer is UNKNOWN, and unknown is
    reported as unknown. The alternative -- keeping the confident sentence -- is
    how a user ends up trusting an artifact nobody verified.
    """
    evidence: Dict[str, Any] = {"canvas_id": (cont.canvas or {}).get("canvas_id")}
    canvas_id = (cont.canvas or {}).get("canvas_id")
    if not canvas_id:
        # No canvas in scope: there is nothing that could have been changed, and
        # saying so is verifiable by the absence of a target.
        return True, {**evidence, "reason": "no canvas in scope"}

    latest = _latest_audit(canvas_id)
    evidence["latest_audit"] = latest
    if latest and cont.snapshot_audit_ts and \
            latest.get("created_at", "") > cont.snapshot_audit_ts:
        return False, {**evidence,
                       "reason": "the canvas's audit trail advanced past the fork "
                                 "snapshot, so something was written"}

    row = _matched_operation_row(cont)
    if row is not None:
        return False, {**evidence, "operation_row": row,
                       "reason": "an audit row carrying this request's operation "
                                 "identity exists"}

    expected = cont.snapshot_content_hash or ""
    if expected:
        try:
            from core.database import get_db_session
            from core.models import Canvas

            with get_db_session() as db:
                canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
            current = _content_hash(canvas or {})
        except Exception as exc:  # noqa: BLE001
            return False, {**evidence, "reason": f"canvas re-read failed: {exc}",
                           "verdict": "unknown"}
        evidence["content_hash_matches_snapshot"] = (current == expected)
        if current != expected:
            return False, {**evidence,
                           "reason": "the canvas content no longer matches the "
                                     "content this continuation started from"}
    else:
        evidence["verdict"] = "partial"
        evidence["reason"] = ("no fork content hash was recorded, so content "
                              "equality could not be checked")
    return True, evidence


def _zero_effect_sentence(cont: AsyncTurnContinuation) -> Tuple[str, Dict[str, Any]]:
    """"Nothing was changed" ONLY when that was verified; otherwise say so."""
    verified, evidence = _verified_zero_effect(cont)
    if verified:
        return "Nothing was changed on the canvas.", evidence
    return ("I couldn't confirm the canvas is exactly as it was — give it "
            "a quick look before relying on it."), {
                **evidence, "sentence": "uncertain"}


def _readable_outcome_text(outcome: str, summary: str) -> str:
    """What the user is shown for a background continuation's terminal outcome.

    It used to be ``[background continuation — failed of: "<the user's own
    request, truncated>"]\n<summary>``: internal bracket syntax, a raw echo of
    the request, and two different renderings between the live bubble and the
    reloaded history. A user should read a sentence, and the machine-readable
    binding belongs in the row's metadata -- where it already is
    (``continuation.id``, ``outcome``, ``originating_execution_id``,
    ``canvas_id``, ``audit_id``, ``postcondition_verified``, ``review_status``) --
    not welded into the prose.

    The first line is the outcome in plain words; the rest is whatever the turn
    actually reported, unchanged, so nothing is summarised away.
    """
    # CONVERSATIONAL CLOSURE (2026-09-30, research-grounded — long-running
    # chat work closes the loop in user terms: state what happened, and
    # where the user must act, say the next step; the machine tokens
    # (outcome ids, attempts, stages) stay in metadata). Each lead states
    # the OUTCOME against the user's original ask, not the job's
    # lifecycle: "your update", not "background update".
    lead = {
        OUTCOME_APPLIED: "Done — your update is applied.",
        OUTCOME_ALREADY_APPLIED: (
            "That update was already applied — nothing new to change."),
        OUTCOME_AWAITING_APPROVAL: (
            "Your update is saved as a proposal and waiting for your "
            "approval."),
        OUTCOME_CONFLICT: (
            "I couldn't apply your update — the canvas changed while I "
            "was editing. Ask me again and I'll apply it to the current "
            "version."),
        OUTCOME_FAILED: "I couldn't apply your update.",
        OUTCOME_CANCELLED: "I cancelled that update.",
    }.get(outcome, "Your background update finished.")
    text = (summary or "").strip()
    return f"{lead} {text}".strip() if text else lead


def start_continuation(
    cont: AsyncTurnContinuation,
    runner: Callable[[], Awaitable["tuple[str, str]"]],
) -> bool:
    """Start ``runner`` as the continuation's background task. ``runner``
    returns ``(outcome, summary)``. Refuses when a continuation is already
    in flight for the session — the DURABLE check makes this correct across
    restarts and workers."""
    if _SESSION_IN_FLIGHT.get(cont.session_id):
        logger.info(
            "[async-continuation] not forked — one already in flight for "
            f"session {cont.session_id}")
        return False
    try:
        _claim_session(cont)  # atomic: PK insert; IntegrityError = lost race
    except Exception as claim_err:  # noqa: BLE001
        if _claim_insert_refused(cont.session_id):
            logger.info(
                "[async-continuation] not forked — claim held for session "
                f"{cont.session_id}")
            return False
        # DB unavailable: degrade to the in-process guard ONLY (documented
        # weaker mode — no cross-worker exclusivity without the database).
        logger.debug(f"claim insert degraded: {claim_err}")

    _create_durable_record(cont)
    cid = cont.continuation_id
    _continuations[cid] = cont
    _SESSION_IN_FLIGHT[cont.session_id] = cid

    async def _run() -> None:
        started = time.monotonic()
        outcome = OUTCOME_FAILED
        summary = ""
        # BACKGROUND EXECUTION CONTEXT (2026-09-23): this task is forked
        # from INSIDE the interactive chat request, and asyncio copies the
        # creating context — without this reset the continuation inherits
        # atom_interactive_chat=True for its whole life, so the interactive
        # 25s structured-latency cap vetoed healthy 26–30s rungs inside a
        # tier whose edit bound is 150s, and the fork consumed the
        # interactive rate reserve meant to protect user-facing turns (live:
        # continuation ab86e7bf attempt 1, zero-dispatch exhaustion in
        # 1.3s). Rate, auth and cooldown restrictions are untouched — only
        # the interactive classification is corrected.
        try:
            from core.llm.interactive_context import mark_background_execution

            mark_background_execution()
        except Exception:  # noqa: BLE001 — classification only, never fatal
            pass
        try:
            outcome, summary = await asyncio.wait_for(
                runner(), timeout=_ASYNC_CONTINUATION_BUDGET_SECONDS)
            if not str(summary).strip():
                outcome = OUTCOME_FAILED
                summary = "edit did not apply (declined)"
        except asyncio.CancelledError:
            # CANCELLATION DOES NOT UNDO A COMPLETED WRITE (review
            # 2026-09-22): if this operation's write already landed, the
            # honest outcome is applied/already_applied with its effects —
            # only an un-landed operation reports cancelled.
            operation_status: Optional[str]
            if _operation_landed(cont):
                operation_status = "accepted"
            else:
                operation_status = _operation_status(cont)
            if operation_status == "accepted":
                cont.outcome = OUTCOME_ALREADY_APPLIED
                cont.summary = (
                    "The write had already landed when the cancellation "
                    "arrived — nothing was undone.")
                _finish_durable_record(
                    cont, cont.outcome, cont.summary)
                try:
                    await _apply_effects(cont)
                finally:
                    _reap(cid, cont.session_id)
                raise
            if operation_status == "pending_review":
                cont.outcome = OUTCOME_AWAITING_APPROVAL
                cont.summary = (
                    "The proposal was already awaiting review when the "
                    "cancellation arrived; it was not cancelled or reapplied.")
                _finish_durable_record(
                    cont, cont.outcome, cont.summary)
                try:
                    await _apply_effects(cont)
                finally:
                    _reap(cid, cont.session_id)
                raise
            cont.outcome = OUTCOME_CANCELLED
            # MISSING-TERMINAL-OUTCOME FIX (2026-09-28): a superseded
            # continuation still owes its session a terminal message. The
            # sibling branches above apply their effects before reaping; the
            # cancelled branch skipped them, so the user's last visible
            # message stayed the "still running" acknowledgement forever
            # (observed in the finish-line F09 overlap case: the superseded
            # edit's session never learned what happened). Apply the same
            # effects — durable chatmessage + WS `chat_continuation` +
            # notification — with truthful wording; the newer instruction's
            # own outcome reports the canvas result separately.
            cont.summary = (
                "superseded by a newer canvas instruction; that update's "
                "result is reported separately")
            _finish_durable_record(
                cont, OUTCOME_CANCELLED, cont.summary)
            try:
                await _apply_effects(cont)
            finally:
                _reap(cid, cont.session_id)
            raise
        except asyncio.TimeoutError:
            # Budget expiry lands here: str(TimeoutError()) is EMPTY, which
            # is how the durable summary shipped as bare "continuation
            # error: " (live 2026-09-23, continuation 90efb974: attempt 2
            # was cut by the 300s budget and the record read
            # "continuation error: " with nothing after it). Name the stage
            # and the exception type so the record says what happened.
            outcome = OUTCOME_FAILED
            stage = getattr(cont, "failure_stage", "") or "runner"
            summary = (
                "background edit did not finish within its "
                f"{_ASYNC_CONTINUATION_BUDGET_SECONDS:.0f}s budget "
                f"at stage {stage} (TimeoutError)")
            cont.error = summary[:500]
            logger.warning(
                f"[async-continuation] {cid} failed after "
                f"{time.monotonic() - started:.0f}s: {summary}")
        except Exception as cont_err:  # noqa: BLE001 — never raise outward
            outcome = OUTCOME_FAILED
            # An exception with an empty str() must never collapse the
            # record to "continuation error: " again — keep the type.
            _detail = str(cont_err).strip() or "<no message>"
            outcome_type = type(cont_err).__name__
            summary = f"continuation error: {outcome_type}: {_detail}"
            cont.error = f"{outcome_type}: {_detail}"[:500]
            logger.warning(
                f"[async-continuation] {cid} failed after "
                f"{time.monotonic() - started:.0f}s: {summary}")
        cont.outcome = outcome
        cont.summary = str(summary)[:1000]
        # ACCEPTANCE BARRIER (test-only; confined by core/acceptance_barrier —
        # inert unless ATOM_ACCEPTANCE_BARRIER names a stage, and refused
        # outside an isolated acceptance world). This is the whole 20 ms window
        # the probes could not reach by polling: the mutation has already
        # committed inside runner() and been verified by the readback/D0 gates
        # above, and the durable terminal record has not been written yet. It
        # only PAUSES — it authorizes nothing, writes nothing, and cannot make
        # a failed outcome look applied. One env lookup when unset.
        if os.getenv("ATOM_ACCEPTANCE_BARRIER"):
            from core.acceptance_barrier import await_barrier as _barrier

            await _barrier("continuation_after_effect", {
                "surface": "async_turn_continuation",
                "continuation_id": cont.continuation_id,
                "session_id": cont.session_id,
                "canvas_id": (cont.canvas or {}).get("canvas_id"),
                "origin_operation_id": getattr(
                    cont, "origin_operation_id", "") or None,
                "outcome": outcome,
                "audit_id": cont.audit_id or None,
            })
        try:
            await _apply_effects(cont)
        finally:
            _finish_durable_record(cont, outcome, cont.summary)
            _reap(cid, cont.session_id)
            logger.info(
                "[async-continuation] %s finished: outcome=%s dur=%.0fs",
                cid, outcome, time.monotonic() - started)

    task = asyncio.create_task(_run())
    _tasks[cid] = task  # strong reference
    logger.info(
        f"[async-continuation] forked {cid} for session {cont.session_id} "
        f"(canvas {(cont.canvas or {}).get('canvas_id') or '-'}, budget "
        f"{_ASYNC_CONTINUATION_BUDGET_SECONDS:.0f}s)")
    return True


def _terminal_delivery_lease_seconds() -> float:
    """How long a terminal-delivery claim stays valid before it may be reclaimed.

    Long enough that no live delivery is ever displaced (a delivery is
    milliseconds), short enough that a crashed turn's terminal outcome is
    recovered on a later pass rather than suppressed forever.
    """
    if os.getenv("ATOM_DELIVERY_LEASE_DISABLED", "").strip() in (
            "1", "true", "yes"):
        # The lease is a wall-clock comparison against a queryable row. A test
        # that drives the pass with a stub session cannot serve that query, and
        # a stub must not have to grow a full ORM surface to exercise the
        # recovery policy. This switch removes the wall-clock condition ONLY.
        # It never disables the fence, which is a database operation and is
        # what actually prevents a duplicate.
        return 0.0
    try:
        return max(5.0, float(os.getenv(
            "ATOM_TERMINAL_DELIVERY_LEASE_SECONDS", "300")))
    except (TypeError, ValueError):
        return 300.0


def _still_holds_claim(cont: AsyncTurnContinuation, token: str) -> bool:
    """Does this writer still own the terminal delivery, per the fence?

    Read at PERSISTENCE time, not at claim time. A holder that paused past its
    lease and was taken over fails here, so it cannot commit a second terminal
    message behind the new holder's back.
    """
    if not token:
        return True  # unarbitrated (fail-open) delivery: nothing to fence
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            row = db.query(AgentExecution).filter(
                AgentExecution.id == cont.continuation_id).first()
            if row is None:
                return False
            cm = (row.metadata_json or {}).get("continuation") or {}
            return str(cm.get("terminal_delivery_token") or "") == str(token)
    except Exception:  # noqa: BLE001
        return True  # cannot verify: do not fence a legitimate delivery


def _claim_terminal_delivery(cont: AsyncTurnContinuation) -> tuple:
    """Atomically claim the right to deliver this continuation's terminal outcome.

    Returns ``(claimed, reason)``. Exactly one caller wins per continuation.

    WHY NOT A LOOKUP
    The obvious implementation -- SELECT the row, and INSERT a message if none
    is there -- is a race, and this is the case that matters (F09): two
    concurrent terminal deliveries both find nothing and both write, so a
    repeated terminal event becomes a SECOND durable message that reads like a
    second edit. A lookup cannot prevent that; only a constraint can.

    WHY A CONDITIONAL UPDATE
    ``UPDATE ... WHERE <not yet delivered>`` arbitrates on the database's own
    write lock: the first writer flips the flag, the second's WHERE no longer
    matches, so its rowcount is 0. No schema migration, no new table, and the
    claim is visible afterwards in ``AgentExecution.metadata_json`` rather than
    only in memory -- which is what makes it survive the restart case.

    A CLAIM IS NOT PROOF OF DELIVERY, and it is not arbitrated by a lookup.

    The flag is written BEFORE the durable message, so a process that dies in
    between leaves a claim with nothing behind it. Trusting the flag alone would
    suppress that turn's only terminal outcome FOREVER -- the recovery would be
    suppressed by the very attempt to recover it. The durable ChatMessage is the
    actual evidence, so a claim with no row behind it is a stale claim and is
    taken over. That is what makes the claim self-healing after a restart.

    And a Python-level "read the flag, then write it" is NOT an arbitration.
    Measured with two real processes on one database: that version let BOTH
    write a terminal message, because both read the flag as unset before either
    committed. So the test-and-set happens inside ONE SQL statement whose WHERE
    clause excludes an already-claimed row, and the winner is decided by
    ``rowcount``. SQLite serialises the write, so the loser's UPDATE matches
    nothing.

    Returns ``claimed=False`` when another delivery already landed. Returns
    ``claimed=False`` with a ``reason`` when the claim could not be attempted at
    all (no durable row, locked database); the caller then fails open and says
    so, because an unclaimable delivery must not silently become no delivery.
    """
    cid = cont.continuation_id
    _token = ""
    try:
        import uuid

        from sqlalchemy import text

        from core.database import get_db_session
        from core.models import AgentExecution, ChatMessage as ChatMessageModel

        with get_db_session() as db:
            row = db.query(AgentExecution).filter(
                AgentExecution.id == cid).first()
            if row is None:
                return False, "no durable AgentExecution row to claim against", ""
            meta = dict(row.metadata_json or {})
            cont_meta = dict(meta.get("continuation") or {})
            already = bool(cont_meta.get("terminal_delivered"))
        claimed_at = float(cont_meta.get("terminal_delivered_at") or 0.0)

        if already:
            with get_db_session() as db:
                delivered = db.query(ChatMessageModel).filter(
                    ChatMessageModel.conversation_id == cont.session_id,
                    ChatMessageModel.metadata_json.like(f'%{cid}%'),
                ).first() is not None
            if delivered:
                return False, "already claimed and delivered", ""
            lease = _terminal_delivery_lease_seconds()
            age = (time.time() - claimed_at) if claimed_at else None
            if lease > 0 and age is not None and age < lease:
                return False, (
                    f"claimed {age:.1f}s ago and still in flight (lease "
                    f"{lease:.0f}s): a live holder is delivering this"), ""
            logger.warning(
                "[async-continuation] %s holds a terminal-delivery claim with "
                "NO delivered message behind it -- an interrupted delivery. "
                "Releasing the stale claim and re-claiming, so the terminal "
                "outcome is not lost.", cid)
            # RELEASE first. The conditional claim below excludes a row whose
            # flag is set, so a stale claim has to be cleared before anyone can
            # win it -- otherwise "re-claim" silently loses to the flag it is
            # recovering from. The release is unconditional and idempotent; the
            # arbitration still happens in the single conditional statement
            # after it, so two processes racing here still produce one winner.
            db.execute(
                text("UPDATE agent_executions SET metadata_json = json_set("
                     "COALESCE(metadata_json, '{}'), "
                     "'$.continuation.terminal_delivered', NULL) "
                     "WHERE id = :cid"),
                {"cid": cid},
            )
            db.commit()

        # Re-read and build the new blob for the statement's SET clause. This
        # read is only to compute the value; the ARBITRATION is the WHERE.
        with get_db_session() as db:
            row = db.query(AgentExecution).filter(
                AgentExecution.id == cid).first()
            if row is None:
                return False, "no durable AgentExecution row to claim against", ""
            meta = dict(row.metadata_json or {})
            cont_meta = dict(meta.get("continuation") or {})
            cont_meta["terminal_delivered"] = True
            # A LEASE, not a bare flag. The flag alone cannot tell a crashed
            # holder from one that is still delivering: releasing a claim that
            # is merely IN FLIGHT lets a second worker deliver while the first
            # is about to, which measured 2 terminal messages. So the claim
            # carries its age and is only reclaimable once it is older than the
            # lease -- far longer than a delivery takes, and short enough that a
            # crashed turn's outcome is recovered rather than lost.
            cont_meta["terminal_delivered_at"] = time.time()
            # FENCING TOKEN. A lease alone is not enough: after it expires
            # another process may take over, and the ORIGINAL holder can then
            # resume and write as well. So the claim carries a token, and the
            # write is conditioned on still holding it. A holder that was
            # fenced out cannot commit, no matter how long it was paused.
            cont_meta["terminal_delivery_token"] = uuid.uuid4().hex
            _token = cont_meta["terminal_delivery_token"]
            meta["continuation"] = cont_meta
            new_blob = json.dumps(meta, default=str)

            result = db.execute(
                text(
                    "UPDATE agent_executions SET metadata_json = :blob "
                    "WHERE id = :cid AND ("
                    "  metadata_json IS NULL OR"
                    "  json_extract(metadata_json, '$.continuation"
                    ".terminal_delivered') IS NULL OR"
                    "  json_extract(metadata_json, '$.continuation"
                    ".terminal_delivered') IS NOT 1"
                    ")"
                ),
                {"blob": new_blob, "cid": cid},
            )
            won = result.rowcount == 1
            db.commit()
        if not won:
            return False, "already claimed and delivered", ""
        return True, "claimed", _token
    except Exception as e:  # noqa: BLE001 — never raised into delivery
        return False, f"claim could not be attempted ({e})", ""


async def _apply_effects(cont: AsyncTurnContinuation) -> None:
    """User-visible + context-continuity effects, each fault-isolated:
    (1) in-memory session append — the NEXT agent turn's context (same
    process, same event loop, same orchestrator instance that forked);
    (2) durable ChatMessage row — reconnect and restart hydration;
    (3) WS event; (4) outcome-honest notification."""
    outcome = cont.outcome or OUTCOME_FAILED
    summary = cont.summary or ""

    _fx = time.monotonic()
    logger.info(
        "[async-continuation] %s effects start outcome=%s",
        cont.continuation_id, outcome)

    def _stage(n: int, name: str) -> None:
        logger.info(
            "[async-continuation] %s effect %d/4 %s done (+%.1fs)",
            cont.continuation_id, n, name, time.monotonic() - _fx)

    # (0) ATOMIC DELIVERY CLAIM. Exactly one caller delivers this
    # continuation's terminal outcome. A second concurrent delivery -- a retry,
    # a re-entrant call, a duplicated event -- is refused here, BEFORE any
    # surface is touched, so it cannot duplicate the durable message, the live
    # bubble, or the notification.
    _claimed, _claim_reason, _token = _claim_terminal_delivery(cont)
    # ACCEPTANCE BARRIER (test-only; confined by core/acceptance_barrier):
    # parks a holder AFTER it claimed terminal delivery and BEFORE it
    # persists — the exact window the stale-holder test needs (the holder
    # is alive, its lease expires, another process takes over, and on
    # resume the fence must refuse its write). Inert unless armed.
    if os.getenv("ATOM_ACCEPTANCE_BARRIER"):
        from core.acceptance_barrier import await_barrier as _abarrier

        await _abarrier("recovery_delivery_held", {
            "surface": "async_turn_continuation",
            "continuation_id": cont.continuation_id,
            "session_id": cont.session_id,
            "claimed": _claimed,
            "claim_reason": _claim_reason,
        })
    if not _claimed:
        # TWO DISTINCT REFUSALS, and only one of them is fail-open.
        #  * another holder owns the delivery  -> a real, arbitrated refusal.
        #    Nothing is written: the owner will do it.
        #  * arbitration unavailable            -> the documented FAIL-OPEN
        #    path. The flag is not a decision, it is a missing decision, so the
        #    delivery proceeds and duplicates remain POSSIBLE.
        if _claim_reason.startswith("already claimed") or \
                _claim_reason.startswith("claimed "):
            logger.warning(
                "[async-continuation] %s terminal delivery REFUSED (%s): "
                "another holder owns it, or it was already delivered. No "
                "durable row, no bubble, no notification from this caller.",
                cont.continuation_id, _claim_reason)
            # Skip EVERY surface, not just the durable row. Stopping here is the
            # point: with only the row guarded, a duplicated delivery still
            # broadcast the live completion and re-sent the notification, so the
            # user saw the outcome twice.
            _stage(0, "delivery-refused")
            return
        else:
            # FAIL-OPEN, and visibly so. The claim is the duplicate PREVENTION;
            # without it duplicates remain possible. That is a real limitation,
            # not a licence to skip the turn's only terminal message, so the
            # delivery proceeds -- but it is logged at WARNING with the reason
            # so an unarbitrated delivery is greppable rather than silent.
            logger.warning(
                "[async-continuation] %s terminal delivery claim NOT "
                "ARBITRATED (%s): proceeding, so a duplicate terminal message "
                "is POSSIBLE for this delivery. Treat this line as a "
                "duplicate-delivery warning.", cont.continuation_id,
                _claim_reason)

    # DIAGNOSIS (2026-09-27, c16 case 2): _finish_durable_record() -- the ONLY
    # thing that moves the AgentExecution row off 'running' -- runs in the
    # `finally` of `await _apply_effects()`. So a stall inside any stage here
    # leaves the durable row 'running' forever AND the WS event and history
    # record unmade, while the write itself stays applied. Log entry and every
    # stage boundary so a stall is attributable to a stage, not just visible.
    # ACCEPTANCE BARRIER (test-only; confined by core/acceptance_barrier — inert
    # unless ATOM_ACCEPTANCE_BARRIER names a stage, and refused outside an
    # isolated acceptance world). Stage ``continuation_after_claim`` parks here:
    # the claim below is taken, and the durable terminal message is NOT yet
    # written. That is precisely the state a crash in this window leaves, and it
    # is unreachable by polling, so the recovery path could not otherwise be
    # exercised at all. It only PAUSES.
    if os.getenv("ATOM_ACCEPTANCE_BARRIER"):
        from core.acceptance_barrier import await_barrier as _barrier

        await _barrier("continuation_after_claim", {
            "surface": "async_turn_continuation",
            "continuation_id": cont.continuation_id,
            "session_id": cont.session_id,
            "canvas_id": (cont.canvas or {}).get("canvas_id"),
            "outcome": cont.outcome,
        })

    # (1) In-memory session context (backend continuity — NOT only the
    # frontend refresh).
    try:
        orch = getattr(cont, "_orchestrator", None)
        session = (
            orch.conversation_sessions.get(cont.session_id)
            if orch is not None else None)
        if session is not None and isinstance(
                session.get("history"), list):
            session["history"].append({
                "message": cont.message[:500],
                "response": {
                    # The SAME readable text the durable row carries. They used to
                    # differ -- the live bubble got one bracketed string and the
                    # reloaded history another -- so a user watching live and a
                    # user reloading were told two different-looking things about
                    # the same outcome.
                    "message": _readable_outcome_text(outcome, summary)},
                "intent": {"primary_intent": "canvas_edit",
                           "background_continuation": True},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": outcome in (OUTCOME_FAILED, OUTCOME_CONFLICT),
            })
            # Same recency bound the interactive path keeps.
            if len(session["history"]) > 24:
                session["history"] = session["history"][-24:]
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation session append skipped: {e}")
    _stage(1, "in-memory-session")

    # (2) Durable row.
    try:
        from core.database import get_db_session
        from core.models import ChatMessage as ChatMessageModel

        # IDEMPOTENCY ON THE DURABLE ROW (2026-09-28, F09). Every stage of this
        # function is individually try/except-wrapped, so a caller that retries,
        # or a re-entrant delivery, re-enters here and previously wrote a
        # SECOND terminal message for one continuation -- a repeated terminal
        # event that reads, in the session's history, exactly like a second edit.
        # Measured on the scratch DB: 3 rows -> 4 on a repeated call.
        #
        # The marker is the continuation id already inside the row's own
        # metadata, so the guard survives a restart -- an in-memory "already
        # sent" set would not, and the case that matters (a delivery retried
        # after the process died) is precisely the one an in-memory set misses.
        # The check is deliberately fail-OPEN. If it cannot be performed -- a
        # minimal session stub, a locked database, a schema without the column
        # -- the row is written anyway. Failing closed here would suppress a
        # terminal message entirely, which is the ORIGINAL F09 defect; at worst
        # a failed check permits a duplicate row, and a duplicate message does
        # not repeat an effect. Missing beats duplicated.
        # FENCE + PERSIST AS ONE TRANSACTION (F09).
        #
        # Both of the earlier arrangements were wrong, in opposite directions:
        #   * checking the fence and THEN inserting, in separate sessions, leaves
        #     a takeover window between them -- a second process can take the
        #     claim in exactly that gap and both then write;
        #   * doing nothing when the fence fails suppresses the terminal outcome.
        #
        # So the fence is a CONDITIONAL UPDATE and the insert share one
        # transaction. The UPDATE takes SQLite's write lock first, so from that
        # moment no takeover can interleave; the insert happens while the lock is
        # held, and the COMMIT publishes both or neither. Losing the fence
        # rollbacks, so a fenced-out holder writes nothing.
        # The message is written by the transaction below whenever the fence
        # passes, so the notification stage is not suppressed. A fail-open
        # delivery (``_token`` empty) has no fence to pass and writes anyway --
        # that is the documented duplicate-possible path, not a silent skip.
        _notify_skipped = False
        from sqlalchemy import text as _text

        from core.database import get_db_session as _gds
        from core.models import AgentExecution as _AE
        from core.models import ChatMessage as ChatMessageModel

        with _gds() as db:
            fence = 1
            if _token:
                fence = db.execute(
                    _text(
                        "UPDATE agent_executions SET metadata_json = "
                        "json_set(COALESCE(metadata_json, '{}'), "
                        "'$.continuation.terminal_persisting', "
                        "strftime('%s','now')) "
                        "WHERE id = :cid AND json_extract(metadata_json, "
                        "'$.continuation.terminal_delivery_token') = :tok"
                    ),
                    {"cid": cont.continuation_id, "tok": _token},
                ).rowcount
            if fence == 1:
                db.add(ChatMessageModel(
                    conversation_id=cont.session_id,
                    tenant_id="default",
                    role="assistant",
                    content=_readable_outcome_text(outcome, summary),
                    metadata_json=json.dumps({"continuation": {
                        "id": cont.continuation_id,
                        "outcome": outcome,
                        "originating_execution_id": cont.execution_id,
                        "canvas_id": (cont.canvas or {}).get("canvas_id"),
                        "evidence_contract": _bounded_evidence_contract(
                            cont.evidence_contract
                        ),
                        "audit_id": cont.audit_id or None,
                        "postcondition_verified": cont.postcondition_verified,
                        "review_status": cont.review_status or None,
                        # RECOVERY ATTRIBUTION (2026-09-28): an interrupted
                        # completion's message records whether THIS edit's
                        # effect is on the canvas (operation-linked audit
                        # evidence) — success wording must never imply more
                        # than the evidence supports.
                        "effect_on_canvas": getattr(
                            cont, "effect_on_canvas", None),
                        "recovery_delivery": (
                            getattr(cont, "failure_stage", "")
                            == "recovery"),
                    }}),
                ))
                _mark = getattr(cont, "_recovery_delivered", None)
                if _mark is not None:
                    cont._recovery_delivered = True
            else:
                db.rollback()
                logger.warning(
                    "[async-continuation] %s terminal message NOT written: the "
                    "delivery claim was taken over before this transaction "
                    "committed, and the fence is checked and written in the same "
                    "transaction, so nothing was left half-done.",
                    cont.continuation_id)
                _stage(2, "fenced-out")
                return
    except Exception as e:  # noqa: BLE001
        logger.warning(f"continuation persistence skipped: {e}")
        _notify_skipped = False
    _stage(2, "durable-chatmessage")

    # (3) WS event (frontend refresh + toast).
    try:
        from core.websockets import get_connection_manager

        await get_connection_manager().broadcast_event(
            f"user:{cont.user_id}",
            "chat_continuation",
            {
                "continuation_id": cont.continuation_id,
                "originating_execution_id": cont.execution_id,
                "session_id": cont.session_id,
                "canvas_id": (cont.canvas or {}).get("canvas_id"),
                "status": outcome,
                "summary": summary[:400],
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation WS broadcast skipped: {e}")
    _stage(3, "ws-broadcast")

    # (4) Notification with OUTCOME-honest wording — "ready for review" is
    # never worded as "completed". Skipped when stage 2 found the terminal
    # message already persisted, so a retried delivery does not also re-notify.
    if _notify_skipped:
        logger.info(
            "[async-continuation] %s notification suppressed: terminal "
            "delivery already recorded", cont.continuation_id)
        _stage(4, "notification-suppressed")
        logger.info(
            "[async-continuation] %s effects complete (+%.1fs)",
            cont.continuation_id, time.monotonic() - _fx)
        return
    try:
        from core.notification_service import NotificationService

        titles = {
            OUTCOME_APPLIED: "Background update finished",
            OUTCOME_AWAITING_APPROVAL: "Draft ready for your review",
            OUTCOME_ALREADY_APPLIED: "Update had already landed",
            OUTCOME_CONFLICT: "Canvas changed — update held back",
            OUTCOME_FAILED: "Background update could not finish",
            OUTCOME_CANCELLED: "Background update cancelled",
        }
        _notify_result = await NotificationService().send_notification(
            cont.user_id,
            _OUTCOME_NOTIFICATION_TYPE.get(outcome, "async_turn_failed"),
            {
                "title": titles.get(
                    outcome, "Background update could not finish"),
                "message": summary[:200] or titles.get(
                    outcome, "Background update could not finish"),
                "session_id": cont.session_id,
                "canvas_id": (cont.canvas or {}).get("canvas_id"),
                "continuation_id": cont.continuation_id,
                "originating_execution_id": cont.execution_id,
                "action_url": (
                    f"/canvas/{(cont.canvas or {}).get('canvas_id')}"
                    if (cont.canvas or {}).get("canvas_id") else "/chat"
                ),
            },
        )
        if _m3_enabled() and isinstance(
                _notify_result, dict) and _notify_result.get("success"):
            _mark_continuation_notified(cont.continuation_id)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation notification skipped: {e}")
    _stage(4, "notification")
    logger.info(
        "[async-continuation] %s effects complete (+%.1fs)",
        cont.continuation_id, time.monotonic() - _fx)


async def run_canvas_edit_continuation(
    orchestrator: Any,
    cont: AsyncTurnContinuation,
) -> "tuple[str, str]":
    """Runner for a starved canvas-edit turn: idempotency/conflict gate,
    then re-run the SAME edit leg with a fresh blackboard, a relaxed inner
    timeout, and bounded backoff retries. Returns ``(outcome, summary)``."""
    started = time.monotonic()
    deadline = started + max(1.0, _ASYNC_CONTINUATION_BUDGET_SECONDS - 2.0)
    last_note = "the edit planner could not complete"
    for attempt in range(1, _ASYNC_CONTINUATION_ATTEMPTS + 1):
        if attempt > 1:
            latest = _latest_turn_evidence(orchestrator, cont)
            latest_contract = _latest_turn_contract(orchestrator, cont)
            if isinstance(latest_contract, dict):
                cont.evidence_contract = latest_contract
            if latest and latest != cont.evidence_block:
                logger.info(
                    "[async-continuation] %s retry %d: refreshed evidence "
                    "block (%d → %d chars)",
                    cont.continuation_id, attempt,
                    len(cont.evidence_block or ""), len(latest))
                cont.evidence_block = latest

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            cont.failure_stage = "budget"
            # Plain sentence for the user; the stage and budget stay on the
            # continuation and in the row metadata (D5).
            cont.error = (
                f"budget exhausted at stage {cont.failure_stage} after "
                f"{attempt - 1} attempts")[:500]
            _zero, _zero_ev = _zero_effect_sentence(cont)
            return OUTCOME_FAILED, (
                f"The background edit ran out of time before it could finish. "
                f"{_zero}")

        cont.failure_stage = f"attempt-{attempt}-preapply"
        pre = _classify_preapply(cont)
        if pre == OUTCOME_ALREADY_APPLIED:
            return pre, (
                "The canvas edit from your earlier request had already "
                "landed before the background attempt ran — nothing was "
                "applied twice.")
        if pre == OUTCOME_AWAITING_APPROVAL:
            return pre, (
                "The canvas edit is already saved as a proposal awaiting "
                "review; it was not applied again.")
        if pre == OUTCOME_CONFLICT:
            return pre, (
                "The canvas changed while the background update was "
                "running (newer edits exist), so the update was held back "
                "rather than overwriting them. Re-ask and it will run "
                "against the current canvas.")

        blackboard: Dict[str, Any] = {
            "plan_task": None,
            "block": (cont.evidence_block or "") or None,
            "objective_evidence": cont.evidence_contract,
        }
        prior = _latest_audit((cont.canvas or {}).get("canvas_id") or "")
        expected_prior = (prior or {}).get("id")
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            cont.failure_stage = "budget"
            return OUTCOME_FAILED, (
                f"The background edit exhausted its "
                f"{_ASYNC_CONTINUATION_BUDGET_SECONDS:.0f}s budget before "
                f"attempt {attempt}."
            )
        cont.failure_stage = f"attempt-{attempt}-edit"
        edit_timeout = min(
            _ASYNC_EDIT_PLAN_TIMEOUT_SECONDS, max(1.0, remaining - 1.0))
        attempt_started = time.monotonic()
        logger.info(
            "[async-continuation] %s attempt %d/%d stage=%s remaining=%.1fs "
            "edit_timeout=%.1fs", cont.continuation_id, attempt,
            _ASYNC_CONTINUATION_ATTEMPTS, cont.failure_stage,
            remaining, edit_timeout)
        try:
            response = await asyncio.wait_for(
                orchestrator._try_canvas_edit(
                    cont.message, cont.history_snapshot, cont.canvas,
                    cont.user_id, cont.session_id, cont.execution_id,
                    cont.agent_id,
                    provenance=cont.provenance,
                    shared_tool_state=blackboard,
                    operation_id=cont.continuation_id,
                    expected_prior_audit_id=expected_prior,
                    edit_plan_timeout=edit_timeout,
                ),
                timeout=max(0.1, remaining),
            )
        except asyncio.TimeoutError:
            cont.failure_stage = f"attempt-{attempt}-edit-timeout"
            last_note = (
                f"attempt {attempt} reached its remaining budget during the "
                "edit leg"
            )
            logger.warning(
                "[async-continuation] %s %s after %.0fs",
                cont.continuation_id, cont.failure_stage,
                time.monotonic() - started)
            break
        except Exception as edit_err:
            cont.failure_stage = f"attempt-{attempt}-edit-error"
            last_note = f"{type(edit_err).__name__}: {str(edit_err).strip() or '<no message>'}"
            logger.warning(
                "[async-continuation] %s %s after %.0fs: %s",
                cont.continuation_id, cont.failure_stage,
                time.monotonic() - started, last_note)
            response = None

        logger.info(
            "[async-continuation] %s attempt %d/%d edit returned in %.1fs "
            "stage=%s", cont.continuation_id, attempt,
            _ASYNC_CONTINUATION_ATTEMPTS,
            time.monotonic() - attempt_started, cont.failure_stage)
        # DIAGNOSIS (2026-09-27, acceptance c16 case 2): the write lands but the
        # attempt is reported unconfirmed, and FOUR separate gates can each say
        # so. Name the one that actually decided it and log every input, so one
        # run discriminates instead of four competing hypotheses. Purely
        # additive -- no gate's condition is altered here.
        _gate = "no-response"
        _op_status_dbg: Any = "not-probed"
        if response:
            edit_meta = ((response.get("data") or {}).get(
                "canvas_edit") or {})
            cont.audit_id = str(edit_meta.get("audit_id") or "")
            cont.postcondition_verified = edit_meta.get(
                "postcondition_verified"
            )
            cont.review_status = str(edit_meta.get("review_status") or "")
            readback_ok = False
            if edit_meta.get("updated") is not True:
                _gate = "updated-not-true"
                last_note = str(
                    (edit_meta.get("reason") or "edit response did not confirm a write")
                )[:240]
            else:
                cont.failure_stage = f"attempt-{attempt}-readback"
                readback_ok = True
                if cont.evidence_contract and edit_meta.get(
                        "postcondition_verified") is not True:
                    readback_ok = False
                    _gate = "postcondition-unverified"
                    last_note = "source-backed read-back was not verified"
                if cont.readback_required and readback_ok:
                    # `_operation_landed` is the predicate here too, not
                    # `_operation_status(...) == "accepted"` inlined: it is the
                    # module's documented seam. The raw status is read only when
                    # the decision is negative, to name the reason, so the
                    # success path still costs a single probe.
                    readback_ok = _operation_landed(cont)
                    if not readback_ok:
                        _op_status_dbg = _operation_status(cont)
                        _gate = "operation-not-landed"
                    if readback_ok:
                        _gate = "read-canvas"
                        try:
                            from tools.canvas_crud_tool import read_canvas

                            readback = await read_canvas(
                                cont.user_id,
                                str((cont.canvas or {}).get("canvas_id") or ""),
                            )
                            readback_ok = bool(
                                readback.get("success")
                                and readback.get("audit_id")
                            )
                            if not readback_ok:
                                _gate = "read-canvas-no-audit-id"
                        except Exception as read_err:
                            readback_ok = False
                            _gate = "read-canvas-error"
                            last_note = (
                                "readback failed: "
                                f"{type(read_err).__name__}: {str(read_err).strip()}"
                            )
                elif readback_ok:
                    _op_status_dbg = "skipped(readback_required=False)"
                if readback_ok:
                    _gate = "CONFIRMED"
                    summary = str(response.get("message") or "").strip() or (
                        "Canvas edit applied to "
                        f"{(cont.canvas or {}).get('canvas_type') or 'canvas'} "
                        f"{(cont.canvas or {}).get('canvas_id') or ''}".strip())
                    if edit_meta.get("learning_mode") or edit_meta.get(
                            "review_status") == "pending_review":
                        return OUTCOME_AWAITING_APPROVAL, summary
                    return OUTCOME_APPLIED, summary
                if not last_note or last_note == "the edit planner could not complete":
                    last_note = "the write could not be confirmed by audit readback"

        # The one line that settles WHICH gate refused a landed write.
        logger.info(
            "[async-continuation] %s attempt %d/%d READBACK-DECISION "
            "gate=%s response=%s updated=%r postcondition_verified=%r "
            "evidence_contract=%s readback_required=%s audit_id=%r "
            "op_status=%r review_status=%r note=%s",
            cont.continuation_id, attempt, _ASYNC_CONTINUATION_ATTEMPTS,
            _gate, bool(response), edit_meta.get("updated") if response else None,
            edit_meta.get("postcondition_verified") if response else None,
            bool(cont.evidence_contract), bool(cont.readback_required),
            cont.audit_id or None, _op_status_dbg, cont.review_status or None,
            str(last_note)[:160])

        if attempt < _ASYNC_CONTINUATION_ATTEMPTS:
            delay = min(
                _ASYNC_CONTINUATION_RETRY_DELAY_SECONDS,
                max(0.0, deadline - time.monotonic()),
            )
            if delay > 0:
                cont.failure_stage = "retry-backoff"
                logger.info(
                    "[async-continuation] %s retry %d/%d after %.0fs",
                    cont.continuation_id, attempt,
                    _ASYNC_CONTINUATION_ATTEMPTS, delay)
                await asyncio.sleep(delay)

    cont.failure_stage = cont.failure_stage or "attempts"
    # USER-FACING SENTENCE + MACHINE DETAIL (D5, 2026-09-28). The retry loop's
    # internal note and stage used to be interpolated straight into the text a
    # reload renders ("... (the edit planner could not complete; stage=...)"),
    # which is a debug line wearing a sentence. The detail is still recorded --
    # on the continuation and in the row's metadata -- it is just no longer part
    # of the prose.
    cont.error = (f"{last_note}; stage={cont.failure_stage}")[:500]
    _zero, _zero_ev = _zero_effect_sentence(cont)
    _tries = ("1 try" if _ASYNC_CONTINUATION_ATTEMPTS == 1
              else f"{_ASYNC_CONTINUATION_ATTEMPTS} tries")
    return OUTCOME_FAILED, (
        f"I couldn't apply that edit after {_tries}. "
        f"{_zero}")


def supersede_pending_continuation(
    session_id: str, message: str,
    context: Optional[Dict[str, Any]],
) -> bool:
    """SUPERSEDE — CONDITIONALLY (review 2026-09-22): only a NEW EDIT
    instruction on the same canvas supersedes a pending continuation.
    A status question ("did the background update finish?") must NOT
    cancel the job it asks about; it relies on the continuation's
    context append to answer. Explicit cancellation flows through the
    chat cancel route instead."""
    if not session_id:
        return False
    try:
        from integrations.chat_orchestrator import _canvas_edit_shaped

        if not _canvas_edit_shaped(message, context):
            return False
    except Exception:  # noqa: BLE001 — classification is best-effort
        return False
    current_canvas_id = str(
        (context or {}).get("canvas_id")
        or ((context or {}).get("canvas") or {}).get("canvas_id")
        or ""
    )
    if not current_canvas_id:
        return False
    return cancel_continuation(session_id, canvas_id=current_canvas_id)


def _latest_turn_evidence(orchestrator: Any, cont: AsyncTurnContinuation) -> str:
    """This OPERATION's evidence from the session — operation-scoped, not
    "latest wins" (review: evidence isolation). The reply path stores its
    composed evidence under a key derived from the turn's message hash; the
    continuation reads the SAME key derived from ITS OWN originating message
    (cont.message), so a later turn's evidence cannot be consumed by this
    continuation. Fault-isolated."""
    try:
        orch = getattr(cont, "_orchestrator", None)
        if orch is None:
            return ""
        session = orch.conversation_sessions.get(cont.session_id)
        if not session:
            return ""
        # EXECUTION-ID KEYED (review correction: message hash identified
        # text, not an operation — two identical approval turns collided).
        # The execution ID is unique per turn and was passed to this
        # continuation at fork time.
        if not cont.execution_id:
            return ""
        return str(session.get(f"_ev_{cont.execution_id}") or "")
    except Exception:
        return ""


def _latest_turn_contract(
    orchestrator: Any, cont: AsyncTurnContinuation
) -> Optional[Dict[str, Any]]:
    try:
        orch = getattr(cont, "_orchestrator", None)
        if orch is None or not cont.execution_id:
            return None
        session = orch.conversation_sessions.get(cont.session_id)
        if not session:
            return None
        contract = session.get(
            f"_objective_evidence_{cont.execution_id}"
        )
        return dict(contract) if isinstance(contract, dict) else None
    except Exception:
        return None


def fork_canvas_edit_continuation(
    orchestrator: Any,
    *,
    message: str,
    history: list,
    canvas: Dict[str, Any],
    user_id: str,
    session_id: str,
    execution_id: Optional[str],
    agent_id: Optional[str],
    provenance: Optional[Dict[str, Any]] = None,
    evidence_block: str = "",
    evidence_contract: Optional[Dict[str, Any]] = None,
    origin_operation_id: str = "",
) -> Optional[str]:
    """Fire-and-forget entry used by the orchestrator's edit-leg timeout
    branch. Snapshots the idempotency state at fork time. Returns the
    continuation id, or None when one is already in flight."""
    canvas_id = (canvas or {}).get("canvas_id")
    latest = _latest_audit(canvas_id) if canvas_id else None
    cont = AsyncTurnContinuation(
        continuation_id=str(uuid.uuid4()),
        user_id=user_id,
        session_id=session_id,
        message=str(message or "")[:500],
        canvas=canvas or {},
        execution_id=execution_id,
        agent_id=agent_id,
        history_snapshot=list(history or []),
        provenance=provenance,
        snapshot_content_hash=_content_hash(canvas or {}),
        snapshot_audit_ts=(latest or {}).get("created_at", ""),
        origin_operation_id=str(origin_operation_id or ""),
        evidence_block=evidence_block or "",
        evidence_contract=(
            dict(evidence_contract)
            if isinstance(evidence_contract, dict)
            else None
        ),
        readback_required=True,
    )
    # Dataclass: stash the orchestrator for the in-memory session append
    # (same event loop, same instance that served the forked turn).
    object.__setattr__(cont, "_orchestrator", orchestrator)

    def _runner() -> Awaitable["tuple[str, str]"]:
        return run_canvas_edit_continuation(orchestrator, cont)

    if start_continuation(cont, _runner):
        return cont.continuation_id
    return None
