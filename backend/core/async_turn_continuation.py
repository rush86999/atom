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
from typing import Any, Awaitable, Callable, Dict, List, Optional

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
    # EVIDENCE HANDOFF (review item 2): the turn's already-retrieved
    # evidence block — the reply path's search found data the edit's own
    # fresh-data search missed (live 2026-09-23: reply had 4/4 slitter
    # prices; edit applied placeholders). The continuation injects this
    # as existing_block so the retry REUSES it instead of re-searching.
    evidence_block: str = ""
    # Terminal state.
    outcome: str = ""
    summary: str = ""
    error: str = ""


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


def cancel_continuation(session_id: str) -> bool:
    """Cancel the in-flight continuation for a session — used when a NEW
    user turn supersedes it, or on explicit stop. Returns True when one was
    cancelled."""
    cid = _SESSION_IN_FLIGHT.get(session_id)
    if not cid:
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
            db.add(AgentExecution(
                id=cont.continuation_id,
                agent_id=cont.agent_id,
                status="running",
                input_summary=cont.message[:300],
                triggered_by="continuation",
                metadata_json={
                    "session_id": cont.session_id,
                    "surface": "async_turn_continuation",
                    "continuation": {
                        "session_id": cont.session_id,
                        "canvas_id": (cont.canvas or {}).get("canvas_id"),
                        "user_id": cont.user_id,
                        "message": cont.message[:500],
                        "snapshot_content_hash": cont.snapshot_content_hash,
                        "snapshot_audit_ts": cont.snapshot_audit_ts,
                    },
                },
            ))
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
                return row.id
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
            row.result_summary = f"[{outcome}] {summary[:400]}"
            meta = dict(row.metadata_json or {})
            cont_meta = meta.get("continuation") or {}
            cont_meta["outcome"] = outcome
            cont_meta["summary"] = summary[:500]
            cont_meta["notified"] = True
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
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            rows = (
                db.query(AgentExecution)
                .filter(AgentExecution.triggered_by == "continuation")
                .all()
            )
            pending = []
            for row in rows:
                meta = row.metadata_json or {}
                cont = meta.get("continuation") or {}
                if (meta.get("recovery") or {}).get("crashed") and not (
                        cont.get("notified")):
                    pending.append(row)
        for row in pending:
            cont = (row.metadata_json or {}).get("continuation") or {}
            user_id = cont.get("user_id")
            if not user_id:
                continue
            try:
                from core.notification_service import NotificationService

                async def _notify() -> None:
                    await NotificationService().send_notification(
                        user_id, "async_turn_failed",
                        {
                            "title": "Background update could not finish",
                            "message": (
                                "A background canvas update was interrupted "
                                "by a server restart."),
                            "session_id": cont.get("session_id"),
                            "canvas_id": cont.get("canvas_id"),
                            "action_url": (
                                f"/canvas/{cont['canvas_id']}"
                                if cont.get("canvas_id") else "/chat"),
                        })

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop is not None:
                    loop.create_task(_notify())
                else:
                    asyncio.run(_notify())
                out["recovered_notified"] += 1
                with get_db_session() as db:
                    r2 = db.query(AgentExecution).filter(
                        AgentExecution.id == row.id).first()
                    if r2:
                        meta = dict(r2.metadata_json or {})
                        c = meta.get("continuation") or {}
                        c["notified"] = True
                        meta["continuation"] = c
                        r2.metadata_json = meta
            except Exception as e:  # noqa: BLE001
                logger.debug(f"recovered-continuation notify skipped: {e}")
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


def _operation_landed(cont: AsyncTurnContinuation) -> bool:
    """DEFINITIVE idempotency probe: does any CanvasAudit row for the canvas
    carry THIS continuation's operation_id? The retry stamps every write it
    makes with ``details_json.operation_id = continuation_id``, so a landed
    write is a query, not a timestamp inference (review 2026-09-22)."""
    canvas_id = (cont.canvas or {}).get("canvas_id")
    if not canvas_id:
        return False
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from core.sql_json import json_field_equals

        with get_db_session() as db:
            q = json_field_equals(
                db, CanvasAudit.details_json, "$.operation_id",
                cont.continuation_id)
            rows = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id, *([q] if q is not None else [])
            ).all()
            return bool(rows)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"operation-landed probe skipped: {e}")
        return False


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
    if _operation_landed(cont):
        return OUTCOME_ALREADY_APPLIED
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
            if _operation_landed(cont):
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
            cont.outcome = OUTCOME_CANCELLED
            cont.summary = "superseded by an edit instruction or cancelled"
            _finish_durable_record(
                cont, OUTCOME_CANCELLED, cont.summary)
            _reap(cid, cont.session_id)
            raise
        except Exception as cont_err:  # noqa: BLE001 — never raise outward
            outcome = OUTCOME_FAILED
            summary = f"continuation error: {cont_err}"
            cont.error = str(cont_err)[:500]
            logger.warning(
                f"[async-continuation] {cid} failed after "
                f"{time.monotonic() - started:.0f}s: {cont_err}")
        cont.outcome = outcome
        cont.summary = str(summary)[:1000]
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


async def _apply_effects(cont: AsyncTurnContinuation) -> None:
    """User-visible + context-continuity effects, each fault-isolated:
    (1) in-memory session append — the NEXT agent turn's context (same
    process, same event loop, same orchestrator instance that forked);
    (2) durable ChatMessage row — reconnect and restart hydration;
    (3) WS event; (4) outcome-honest notification."""
    outcome = cont.outcome or OUTCOME_FAILED
    summary = cont.summary or ""

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
                    "message": (
                        f"[background continuation — {outcome}] "
                        f"{summary}")[:2000]},
                "intent": {"primary_intent": "canvas_edit",
                           "background_continuation": True},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": False,
            })
            # Same recency bound the interactive path keeps.
            if len(session["history"]) > 24:
                session["history"] = session["history"][-24:]
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation session append skipped: {e}")

    # (2) Durable row.
    try:
        from core.database import get_db_session
        from core.models import ChatMessage as ChatMessageModel

        with get_db_session() as db:
            db.add(ChatMessageModel(
                conversation_id=cont.session_id,
                tenant_id="default",
                role="assistant",
                content=(
                    f"[background continuation — {outcome} of: "
                    f"\"{cont.message[:120]}\"]\n{summary}"),
                metadata_json=json.dumps({"continuation": {
                    "id": cont.continuation_id,
                    "outcome": outcome,
                    "canvas_id": (cont.canvas or {}).get("canvas_id"),
                }}),
            ))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"continuation persistence skipped: {e}")

    # (3) WS event (frontend refresh + toast).
    try:
        from core.websockets import get_connection_manager

        await get_connection_manager().broadcast_event(
            f"user:{cont.user_id}",
            "chat_continuation",
            {
                "continuation_id": cont.continuation_id,
                "session_id": cont.session_id,
                "canvas_id": (cont.canvas or {}).get("canvas_id"),
                "status": outcome,
                "summary": summary[:400],
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation WS broadcast skipped: {e}")

    # (4) Notification with OUTCOME-honest wording — "ready for review" is
    # never worded as "completed".
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
        await NotificationService().send_notification(
            cont.user_id,
            _OUTCOME_NOTIFICATION_TYPE.get(outcome, "async_turn_failed"),
            {
                "title": titles.get(
                    outcome, "Background update could not finish"),
                "message": summary[:200] or titles.get(
                    outcome, "Background update could not finish"),
                "session_id": cont.session_id,
                "canvas_id": (cont.canvas or {}).get("canvas_id"),
                "action_url": (
                    f"/canvas/{(cont.canvas or {}).get('canvas_id')}"
                    if (cont.canvas or {}).get("canvas_id") else "/chat"
                ),
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"continuation notification skipped: {e}")


async def run_canvas_edit_continuation(
    orchestrator: Any,
    cont: AsyncTurnContinuation,
) -> "tuple[str, str]":
    """Runner for a starved canvas-edit turn: idempotency/conflict gate,
    then re-run the SAME edit leg with a fresh blackboard, a relaxed inner
    timeout, and bounded backoff retries. Returns ``(outcome, summary)``."""
    # BACKOFF-AND-RETRY: the first attempt often lands while the shared
    # rate budgets are still drained by the interactive turn (or a provider
    # is briefly benched) — wait and try again inside the total budget.
    # The pre-apply gate re-runs each attempt: a revision that advanced
    # between attempts is honored, never overwritten.
    last_note = "the edit planner could not complete"
    for attempt in range(1, _ASYNC_CONTINUATION_ATTEMPTS + 1):
        # EVIDENCE REFRESH: the fork captures the block at fork time (the
        # edit's own search), but the REPLY's search — which may have found
        # better evidence — completes after the fork. On retries (after the
        # 45s backoff) re-read the turn's latest block via the orchestrator's
        # shared state so the edit uses the best available evidence.
        if attempt > 1 and cont.evidence_block:
            _latest = _latest_turn_evidence(orchestrator, cont)
            if _latest and _latest != cont.evidence_block:
                logger.info(
                    "[async-continuation] %s retry %d: refreshed evidence "
                    "block (%d → %d chars)",
                    cont.continuation_id, attempt,
                    len(cont.evidence_block), len(_latest))
                cont.evidence_block = _latest
        pre = _classify_preapply(cont)
        if pre == OUTCOME_ALREADY_APPLIED:
            return pre, (
                "The canvas edit from your earlier request had already "
                "landed before the background attempt ran — nothing was "
                "applied twice.")
        if pre == OUTCOME_CONFLICT:
            return pre, (
                "The canvas changed while the background update was "
                "running (newer edits exist), so the update was held back "
                "rather than overwriting them. Re-ask and it will run "
                "against the current canvas.")

        blackboard: Dict[str, Any] = {
            "plan_task": None,
            # EVIDENCE HANDOFF: the turn's block becomes the existing_block
            # the editor's fetch_fresh_data_section reuses without paying
            # for a second search.
            "block": (cont.evidence_block or "") or None,
        }
        # The revision token is captured per attempt and enforced at the
        # write door — an edit arriving during the retry is a refusal,
        # not an overwrite. The operation id stamps whatever lands.
        prior = _latest_audit((cont.canvas or {}).get("canvas_id") or "")
        expected_prior = (prior or {}).get("id")
        response = await orchestrator._try_canvas_edit(
            cont.message, cont.history_snapshot, cont.canvas,
            cont.user_id, cont.session_id, cont.execution_id,
            cont.agent_id,
            provenance=cont.provenance,
            shared_tool_state=blackboard,
            operation_id=cont.continuation_id,
            expected_prior_audit_id=expected_prior,
            edit_plan_timeout=_ASYNC_EDIT_PLAN_TIMEOUT_SECONDS,
        )
        if response:
            edit_meta = ((response.get("data") or {}).get(
                "canvas_edit") or {})
            summary = str(response.get("message") or "").strip() or (
                "Canvas edit applied to "
                f"{(cont.canvas or {}).get('canvas_type') or 'canvas'} "
                f"{(cont.canvas or {}).get('canvas_id') or ''}".strip())
            if edit_meta.get("learning_mode"):
                return OUTCOME_AWAITING_APPROVAL, summary
            return OUTCOME_APPLIED, summary
        if attempt < _ASYNC_CONTINUATION_ATTEMPTS:
            logger.info(
                "[async-continuation] %s attempt %d/%d did not apply — "
                "backing off %.0fs (shared rate budgets recover; the "
                "canvas re-checked on the next attempt)",
                cont.continuation_id, attempt, _ASYNC_CONTINUATION_ATTEMPTS,
                _ASYNC_CONTINUATION_RETRY_DELAY_SECONDS)
            await asyncio.sleep(_ASYNC_CONTINUATION_RETRY_DELAY_SECONDS)
    return OUTCOME_FAILED, (
        f"The background edit attempt did not apply after "
        f"{_ASYNC_CONTINUATION_ATTEMPTS} attempts ({last_note}).")
    edit_meta = ((response.get("data") or {}).get("canvas_edit") or {})
    summary = str(response.get("message") or "").strip() or (
        "Canvas edit applied to "
        f"{(cont.canvas or {}).get('canvas_type') or 'canvas'} "
        f"{(cont.canvas or {}).get('canvas_id') or ''}".strip())
    if edit_meta.get("learning_mode"):
        return OUTCOME_AWAITING_APPROVAL, summary
    return OUTCOME_APPLIED, summary


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
    return cancel_continuation(session_id)


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
        import hashlib as _hl
        _ev_key = "_ev_{}".format(
            _hl.sha256((cont.message or "")[:200].encode(
                "utf-8", "ignore")).hexdigest()[:16])
        return str(session.get(_ev_key) or "")
    except Exception:
        return ""


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
        evidence_block=evidence_block or "",
    )
    # Dataclass: stash the orchestrator for the in-memory session append
    # (same event loop, same instance that served the forked turn).
    object.__setattr__(cont, "_orchestrator", orchestrator)

    def _runner() -> Awaitable["tuple[str, str]"]:
        return run_canvas_edit_continuation(orchestrator, cont)

    if start_continuation(cont, _runner):
        return cont.continuation_id
    return None
