# -*- coding: utf-8 -*-
"""Durable background delivery for strict WorkDrive workbook reads (issue 620).

WHY THIS EXISTS
---------------
The strict WorkDrive read is deliberately expensive: it downloads the exact
resource, parses every sheet from those bytes, and emits a receipt that binds
the answer to the download's SHA-256 and the execution that performed it.  On
the real 46-sheet workbook that work measured well beyond the interactive
25s tool deadline.  The interactive turn must keep that deadline (a user
cannot wait minutes for one bubble), but the read itself is still authorized
and worth finishing.

This module is the bridge between the two tiers.  It reuses the project's
existing durable machinery instead of adding a scheduler:

* the durable job record is an ``AgentExecution`` row (``triggered_by`` =
  ``workdrive_read``) stamped with the same ownership evidence used by
  ``async_turn_continuation`` and reconciled by
  ``core.execution_recovery.reconcile_orphaned_executions``;
* delivery recovery reads the same boot-time integrity slot;
* the completed result is persisted into an assistant ``ChatMessage`` row's
  ``metadata_json["pending_file_result"]`` — the exact carrier
  ``ChatOrchestrator._load_pending_file_result`` already uses for re-delivery
  without a re-read;
* delivery arbitration uses ``DeliveryEvent``'s database-enforced primary key
  (the ``job_delivery`` mechanism).  The SAME single-writer gate arbitrates
  all three lifecycle phases: one scheduled job per accepted request (with a
  terminal release), one run lease per attempt (a compare-and-swap), and one
  terminal result per job (success OR failure, never both).

IDENTITY / AUTHORIZATION CONTRACT
---------------------------------
The background attempt is NOT a continuation of the interactive execution id.
It owns a fresh execution id (the job row id).  Its download receipt and its
strict proof must both carry that id, so a proof from the interactive attempt
can never stand in for the background download.

Two independent gates run before any download and again before a persisted
result may be served:

* authorization — the acting user's WorkDrive grant must not be revoked or
  disconnected;
* the original-request digest — a canonical SHA-256 over the accepted request
  scope (user, workspace, session, resource, original ask, requested targets
  and fields).  A mutated job or a persisted row for a different objective
  fails closed.

Nothing in this module reads an actual workbook from disk or talks to a
provider by itself; it delegates to the existing
``read_workdrive_workbook_direct`` / ``_strict_named_workdrive_block`` path.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA = "workdrive-strict-background-1"
TRIGGERED_BY = "workdrive_read"
JOB_METADATA_KEY = "workdrive_read"
BACKGROUND_DELIVERY_KEY = "background_delivery"
PROVIDER = "zoho_workdrive"
OPERATION = "read_storage_file"

#: Background reads may take longer than the interactive tier, but they are
#: still bounded.  This is a wall-clock budget, never an interactive deadline.
_BACKGROUND_BUDGET_SECONDS = float(
    os.getenv("ATOM_WORKDRIVE_BACKGROUND_BUDGET", "600") or 600)

#: Retry bound used only by the restart-recovery pass.  A job that has already
#: persisted its result is re-delivered, never re-downloaded.
_MAX_RECOVERY_ATTEMPTS = int(
    os.getenv("ATOM_WORKDRIVE_BACKGROUND_MAX_ATTEMPTS", "2") or 2)

#: GHOST-RUN BOUND (2026-11-12 review finding 3).  ``owner_liveness`` reports
#: ``unknown`` for a missing stamp and for an owner on another host — and
#: "unknown" is deliberately NOT evidence of death, so a container restart with
#: a changed hostname leaves a RUNNING row that no pass may take over and no
#: pass may finish: its schedule gate stays held, every re-ask collapses onto
#: it, and the read never delivers.  An attempt older than twice the run budget
#: cannot still be inside that budget, so it is treated as a ghost REGARDLESS
#: of the liveness verdict: recovery may claim it and, when its retry budget is
#: exhausted, finish it (which releases the gate).
_STALE_RUN_SECONDS = max(_BACKGROUND_BUDGET_SECONDS * 2.0, 120.0)

_JOB_STATUS_SCHEDULED = "scheduled"
_JOB_STATUS_RUNNING = "running"
_JOB_STATUS_COMPLETED = "completed"
_JOB_STATUS_FAILED = "failed"

#: One job is one read, so its RESULT delivery is arbitrated per job — not
#: per downloaded sha.  Two concurrent reruns that saw different bytes must
#: still collapse to exactly one terminal message.
_TERMINAL_EVENT_TYPE = "workdrive_read"
_TERMINAL_REVISION = "terminal"

#: The run lease and the duplicate-scheduling gate ride the SAME
#: database-enforced single-writer gate as delivery (``DeliveryEvent``'s
#: primary key, see ``core.job_delivery``).  One arbitration mechanism, three
#: lifecycle phases: schedule once, run once, deliver one terminal result.
_CLAIM_EVENT_TYPE = "workdrive_read_claim"
_SCHEDULE_EVENT_TYPE = "workdrive_read_schedule"
_SCHEDULE_GATE_REVISION = "scheduled"

#: Strong references to spawned tasks (asyncio only keeps weak references).
_background_tasks: Dict[str, asyncio.Task] = {}

#: In-process session handles for the live turn that scheduled the read.  This
#: is a fast path only; durable delivery is the ChatMessage row.
_live_sessions: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Identity helpers
# ---------------------------------------------------------------------------

def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        values = [values]
    out: List[str] = []
    for value in values:
        text = _text(value)
        if text:
            out.append(text)
    return out


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_safe(value: Any) -> Any:
    """Make a value safe for the durable JSON column without truncating it."""
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:  # noqa: BLE001 — a non-serializable value is dropped
        return None


def request_scope_from_task(
    *,
    session_id: Optional[str],
    user_id: Optional[str],
    workspace_id: Optional[str],
    resource_id: Optional[str],
    file_name: Optional[str],
    original_message: Optional[str],
    requested_targets: Any = None,
    requested_fields: Any = None,
) -> Dict[str, Any]:
    """The immutable part of the accepted request.

    Only values that decide WHAT was authorized are here.  Transient UI or
    retry bookkeeping must never change the digest.
    """
    return {
        "session_id": _text(session_id),
        "user_id": _text(user_id),
        "workspace_id": _text(workspace_id),
        "resource_id": _text(resource_id),
        "file_name": _text(file_name).lower(),
        "original_message": " ".join(_text(original_message).split()),
        "requested_targets": _clean_list(requested_targets),
        "requested_fields": _clean_list(requested_fields),
    }


def canonical_request_digest(scope: Any) -> str:
    """SHA-256 of the accepted request scope (the "original digest")."""
    return _sha256_json(scope if isinstance(scope, dict) else {})


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def _authorization_state(user_id: Optional[str]) -> str:
    """Read the existing connected-source grant state (never refreshes).

    ``unknown`` keeps the project's established legacy behavior: the caller
    supplied no connected-source identity, so this check cannot make a
    positive/negative decision.  The strict read itself still has to resolve
    a real token, so an unauthenticated download fails there.
    """
    uid = _text(user_id)
    if not uid:
        return "unauthorized"
    try:
        from core.integrations import token_store

        return str(token_store.connected_source_grant_state(
            PROVIDER, uid) or "unknown").lower()
    except Exception as exc:  # noqa: BLE001 — check must not crash a read
        logger.warning(
            "[workdrive-background] grant state check failed for %s: %r",
            uid, exc)
        return "unknown"


def authorization_allows(state: Any) -> bool:
    """A revoked/disconnected grant is a denial; unknown stays legacy-safe."""
    return str(state or "unknown").lower() not in (
        "revoked", "disconnected", "unauthorized")


def _authorization_blocked(state: str) -> bool:
    return not authorization_allows(state)


# ---------------------------------------------------------------------------
# Durable job storage (AgentExecution rows)
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata_job(meta: Any) -> Optional[Dict[str, Any]]:
    if isinstance(meta, str):
        try:
            meta = json.loads(meta or "{}")
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(meta, dict):
        return None
    job = meta.get(JOB_METADATA_KEY)
    return job if isinstance(job, dict) else None


def _write_job_metadata(row: Any, job: Dict[str, Any], meta: Any = None) -> None:
    base = dict(meta or {}) if isinstance(meta, dict) else {}
    base[JOB_METADATA_KEY] = job
    row.metadata_json = base
    try:
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(row, "metadata_json")
    except Exception:  # noqa: BLE001 — best effort
        pass


def _get_job(job_id: str) -> "tuple[Optional[Any], Optional[Dict[str, Any]]]":
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == str(job_id)).first()
        if row is None:
            return None, None
        return row, _metadata_job(row.metadata_json)


def _active_job_for(
    session_id: str, original_digest: str,
) -> Optional[Dict[str, Any]]:
    """An existing unfinished job for the same accepted request.

    The durable row is the authority, so this is correct across processes and
    restarts.  The in-process map is not consulted for decision-making.
    """
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            rows = (
                db.query(AgentExecution)
                .filter(AgentExecution.triggered_by == TRIGGERED_BY)
                .order_by(AgentExecution.started_at.desc())
                .limit(200)
                .all()
            )
        for row in rows:
            job = _metadata_job(row.metadata_json)
            if not isinstance(job, dict):
                continue
            if (_text(job.get("session_id")) == _text(session_id)
                    and _text(job.get("original_digest"))
                    == _text(original_digest)
                    and str(job.get("status") or "") != _JOB_STATUS_FAILED
                    and str(row.status or "") not in ("failed", "completed",
                                                      "cancelled")):
                return job
    except Exception as exc:  # noqa: BLE001 — best effort
        logger.debug("[workdrive-background] active job scan skipped: %r", exc)
    return None


def _scope_identity_agrees(job: Dict[str, Any], scope: Dict[str, Any]) -> bool:
    """Full identity agreement (the restart fallback's only widening is the
    omitted ``original_message`` / ``file_name``).

    Every field that decides WHAT the user asked for stays in the comparison;
    the ask's wording and the file-name spelling are excluded because a
    filename confirmation restates them and would otherwise mint a new digest
    for the very same authorization (2026-11-12 review).
    """
    stored = job.get("request_scope")
    if not isinstance(stored, dict) or not stored:
        return False
    for field in ("user_id", "workspace_id", "resource_id"):
        if _text(stored.get(field)) != _text(scope.get(field)):
            return False
    for field in ("requested_targets", "requested_fields"):
        if _clean_list(stored.get(field)) != _clean_list(scope.get(field)):
            return False
    return True


def _confirmation_attach_allowed(
    job: Dict[str, Any], scope: Dict[str, Any],
) -> bool:
    """Owner/workspace/resource boundary for attaching by durable job id.

    The job id already proves this is the same scheduled request.  What it
    must NOT do is let a redirected read continue the old job: a confirmation
    that pins a DIFFERENT resource, or states a different target/field set, is
    a distinct request and keeps its own scope.
    """
    stored = job.get("request_scope")
    stored = stored if isinstance(stored, dict) else {}
    job_user = _text(job.get("user_id"))
    job_workspace = _text(job.get("workspace_id"))
    if job_user and _text(scope.get("user_id")) != job_user:
        return False
    if job_workspace and _text(scope.get("workspace_id")) != job_workspace:
        return False
    pinned = _text(stored.get("resource_id")) or _text(job.get("resource_id"))
    asked = _text(scope.get("resource_id"))
    if pinned and asked and pinned != asked:
        # The user redirected the read to another file: finishing the old
        # job under the new identity would answer the wrong question.
        return False
    for field in ("requested_targets", "requested_fields"):
        left = _clean_list(stored.get(field))
        right = _clean_list(scope.get(field))
        if left and right and left != right:
            return False
    return True


def _in_flight_job_for_confirmation(
    session_id: str,
    scope: Dict[str, Any],
    *,
    attach_job_id: Optional[str] = None,
) -> "tuple[Optional[Dict[str, Any]], str]":
    """Find the unfinished job this CONFIRMATION continues, if any.

    Primary: the durable job id the carrier kept across restarts.  Fallback
    (no job id survived): scan this session's unfinished jobs for one whose
    scope agrees on every identity field except the ask wording and the
    file-name spelling.  Both paths validate the job's own digest, so a
    tampered row is never attached to.
    """
    session = _text(session_id)
    if not session:
        return None, ""
    job_id = _text(attach_job_id)
    if job_id:
        row = _get_job(job_id)[0]
        job = _job_from_row(row) if row is not None else None
        if (isinstance(job, dict)
                and _job_is_in_flight(job, row)
                and _text(job.get("session_id")) == session
                and _confirmation_attach_allowed(job, scope)
                and _validate_job(job, row_id=str(row.id)).get("ok")):
            return job, "job_id"
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            rows = (
                db.query(AgentExecution)
                .filter(AgentExecution.triggered_by == TRIGGERED_BY)
                .order_by(AgentExecution.started_at.desc())
                .limit(200)
                .all()
            )
    except Exception as exc:  # noqa: BLE001 — no scan, no attachment
        logger.debug(
            "[workdrive-background] confirmation scan skipped: %r", exc)
        return None, ""
    for row in rows:
        job = _job_from_row(row)
        if not isinstance(job, dict) or not _job_is_in_flight(job, row):
            continue
        if _text(job.get("session_id")) != session:
            continue
        if not _scope_identity_agrees(job, scope):
            continue
        if not _validate_job(job, row_id=str(row.id)).get("ok"):
            continue
        return job, "identity_scan"
    return None, ""


def _record_confirmation_on_job(
    job_id: str,
    *,
    message: str = "",
    mention: str = "",
    attach_mode: str = "",
) -> None:
    """Record the confirmation on the durable job (bookkeeping, not scope).

    ``confirmed_mention`` and the bounded ``confirmations`` log never enter
    the request digest: they tell the delivery side which confirmation-era
    carrier this job answers, while ``task_id`` remains the binding key.
    """
    from core.database import get_db_session
    from core.models import AgentExecution

    entry = {
        "message": _text(message)[:500],
        "mention": _text(mention).lower()[:200],
        "attach": _text(attach_mode),
        "at": _now_iso(),
    }
    try:
        with get_db_session() as db:
            # LOCK-FIRST: see ``_lock_job_row``.  The runner mutates this same
            # JSON column from another transaction/process; reading before the
            # lock is what allowed a stale confirmation copy to overwrite a
            # fresh claim (attempts reset, owner lost, lease unreachable).
            if not _lock_job_row(db, job_id):
                return
            row = db.query(AgentExecution).filter(
                AgentExecution.id == str(job_id)).first()
            if row is None:
                return
            job = _job_from_row(row)
            if not isinstance(job, dict) or not _job_is_in_flight(job, row):
                return
            if entry["mention"]:
                job["confirmed_mention"] = entry["mention"]
            history = [
                item for item in (job.get("confirmations") or [])
                if isinstance(item, dict)
            ]
            if not (history
                    and _text(history[-1].get("message")) == entry["message"]
                    and _text(history[-1].get("mention"))
                    == entry["mention"]):
                history.append(entry)
            job["confirmations"] = history[-8:]
            job["confirmation_count"] = int(
                job.get("confirmation_count") or 0) + 1
            job["last_confirmed_at"] = entry["at"]
            _write_job_metadata(row, job, row.metadata_json)
            db.commit()
    except Exception as exc:  # noqa: BLE001 — bookkeeping must not block reuse
        logger.debug(
            "[workdrive-background] confirmation record skipped for job %s: "
            "%r", str(job_id)[:12], exc)


def _job_from_row(row: Any) -> Optional[Dict[str, Any]]:
    job = _metadata_job(row.metadata_json)
    if not isinstance(job, dict):
        return None
    job.setdefault("job_id", str(row.id))
    job.setdefault("execution_id", str(row.id))
    return job


def _lock_job_row(db: Any, job_id: str) -> bool:
    """Take this job row's write lock BEFORE reading it.

    WHY: confirmation bookkeeping used to be a plain read-modify-write of the
    whole ``metadata_json`` blob.  A confirmation arrives WHILE the runner is
    claiming/storing in another transaction, so the read could snapshot a
    scheduled row (``attempts=0``, no owner) and then commit that stale copy
    LAST — reverting the runner's claim.  The next claim then recomputed
    ``run:1``, hit the lease that already existed, and the job was wedged
    forever.

    A no-op self-assignment UPDATE is portable (PostgreSQL row lock, SQLite
    write lock) and runs as the FIRST statement of the transaction, so the
    read that follows observes the runner's committed state and no writer can
    commit between our read and our write.
    """
    from core.models import AgentExecution

    updated = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == str(job_id))
        .update(
            {AgentExecution.status: AgentExecution.status},
            synchronize_session=False,
        )
    )
    return bool(updated)


def _parse_timestamp(value: Any) -> Optional[float]:
    """Epoch seconds for an ISO-8601 string / datetime / numeric stamp."""
    if isinstance(value, datetime):
        moment = value
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.timestamp()
    if isinstance(value, (int, float)) and value:
        return float(value)
    text = _text(value)
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _run_started_at(job: Dict[str, Any], row: Any) -> Optional[float]:
    """When the CURRENT run attempt began (fallbacks for legacy rows)."""
    for candidate in (
        job.get("last_attempt_at"),
        job.get("started_at"),
        job.get("created_at"),
        getattr(row, "started_at", None),
    ):
        stamp = _parse_timestamp(candidate)
        if stamp:
            return stamp
    return None


def _run_is_stale(job: Dict[str, Any], row: Any, *, now: Optional[float] = None) -> bool:
    """Whether this run has outlived any possible in-budget execution."""
    started = _run_started_at(job, row)
    if not started:
        return False
    return (time.time() if now is None else now) - started >= _STALE_RUN_SECONDS


def _job_is_in_flight(job: Any, row: Any) -> bool:
    """Whether this durable job is still unfinished (scheduled/running)."""
    if not isinstance(job, dict):
        return False
    if str(job.get("status") or "") in (
            _JOB_STATUS_FAILED, _JOB_STATUS_COMPLETED):
        return False
    return str(getattr(row, "status", "") or "") not in (
        "failed", "completed", "cancelled")


def _schedule_gate_event_id(session_id: Any, original_digest: Any) -> Optional[str]:
    """Deterministic schedule gate for one accepted request in one session."""
    session = _text(session_id)
    digest = _text(original_digest)
    if not session or not digest:
        return None
    from core.job_delivery import job_event_id

    return job_event_id(
        f"{session}|{digest}", _SCHEDULE_GATE_REVISION, _SCHEDULE_EVENT_TYPE)


def _job_row_is_terminal(row: Any) -> bool:
    """Whether this durable job row can never run/deliver again."""
    status = str(getattr(row, "status", "") or "")
    if status in ("failed", "completed", "cancelled"):
        return True
    job = _metadata_job(getattr(row, "metadata_json", None))
    return str((job or {}).get("status") or "") in (
        _JOB_STATUS_FAILED, _JOB_STATUS_COMPLETED)


def _release_terminal_schedule_gate(
    gate_id: Optional[str], *, expected_job_id: Optional[str] = None,
) -> bool:
    """Release a schedule gate whose owning job row is terminal (or gone).

    The gate's only normal release point is ``_finish_job``.  A row failed by
    the GENERIC boot sweep (``core.execution_recovery``) is terminal without
    passing through this module, so its gate is orphaned: a re-ask conflicts,
    ``_active_job_for`` correctly finds no active job, and the request can
    never be scheduled again (review finding 4).

    Only a gate whose owner is provably terminal is removed; a live job's gate
    is never touched.  ``expected_job_id`` makes the caller's intent explicit:
    never delete a gate a newer re-ask has since re-pointed elsewhere.
    """
    gate = _text(gate_id)
    if not gate:
        return False
    try:
        from core.database import get_db_session
        from core.models import AgentExecution, DeliveryEvent

        with get_db_session() as db:
            event = db.query(DeliveryEvent).filter(
                DeliveryEvent.event_id == gate).first()
            if event is None:
                return False
            owner = _text(event.job_id)
            if expected_job_id and owner != _text(expected_job_id):
                return False
            row = (
                db.query(AgentExecution)
                .filter(AgentExecution.id == owner)
                .first()
                if owner else None
            )
            if row is not None and not _job_row_is_terminal(row):
                return False
            deleted = (
                db.query(DeliveryEvent)
                .filter(
                    DeliveryEvent.event_id == gate,
                    DeliveryEvent.job_id == owner,
                )
                .delete(synchronize_session=False)
            )
            db.commit()
            if deleted:
                logger.info(
                    "[workdrive-background] released orphaned schedule gate "
                    "held by terminal job %s", (owner or "<missing>")[:12])
            return bool(deleted)
    except Exception as exc:  # noqa: BLE001 — a failed release must not crash
        logger.debug(
            "[workdrive-background] schedule gate release skipped: %r", exc)
        return False


def _sweep_terminal_schedule_gates() -> int:
    """Boot sweep: drop gates whose owning job can never finish.

    Same root cause as ``_release_terminal_schedule_gate`` (the gate's only
    release point is ``_finish_job``), handled in bulk so a restart repairs
    gates orphaned while no workdrive pass was running.  A gate whose job row
    no longer exists can never be released by that row either, so it is swept
    as well; the gate and its job row are always written in one transaction,
    so a visible gate without its row means the row is gone, not in flight.
    """
    released = 0
    try:
        from core.database import get_db_session
        from core.models import AgentExecution, DeliveryEvent

        with get_db_session() as db:
            gates = (
                db.query(DeliveryEvent)
                .filter(DeliveryEvent.result_revision
                        == _SCHEDULE_GATE_REVISION)
                .limit(500)
                .all()
            )
            for gate in gates:
                owner = _text(gate.job_id)
                row = (
                    db.query(AgentExecution)
                    .filter(AgentExecution.id == owner)
                    .first()
                    if owner else None
                )
                if row is not None and not _job_row_is_terminal(row):
                    continue
                released += (
                    db.query(DeliveryEvent)
                    .filter(
                        DeliveryEvent.event_id == gate.event_id,
                        DeliveryEvent.job_id == owner,
                    )
                    .delete(synchronize_session=False)
                )
            if released:
                db.commit()
                logger.info(
                    "[workdrive-background] swept %s orphaned schedule "
                    "gate(s) held by terminal/missing jobs", released)
    except Exception as exc:  # noqa: BLE001 — boot pass must never crash
        logger.debug(
            "[workdrive-background] schedule gate sweep skipped: %r", exc)
    return released


def _claim_run_lease(
    db: Any, *, job_id: str, attempt: int, session_id: str,
    takeover: bool = False,
) -> bool:
    """Arbitrate one run attempt on the shared delivery-event primary key.

    Returns True only when THIS caller inserted the lease.  Two processes that
    both read ``attempts = n`` both try ``run:n+1``; exactly one insert can
    win, so only one of them may download.  A crash leaves the lease behind,
    but the next recovery pass reads the incremented attempt and therefore
    acquires ``run:n+2`` — restart recovery is preserved.

    ``takeover`` adds ONE deterministic fallback revision.  It is used only
    when this caller is deliberately replacing a stale/verified-dead owner,
    and it exists because a lease can outlive the attempt counter that named
    it (the 2026-11-12 review's wedged-job case: a reverted ``attempts`` made
    every pass retry ``run:1`` and hit its own leftover lease forever).  The
    fallback id is still deterministic, so even two simultaneous repairers
    cannot both win.
    """
    from core.job_delivery import job_event_id
    from core.models import DeliveryEvent
    from sqlalchemy.exc import IntegrityError

    revisions = [f"run:{int(attempt)}"]
    if takeover:
        revisions.append(f"run:{int(attempt)}:takeover")
    for index, revision in enumerate(revisions):
        db.add(DeliveryEvent(
            event_id=job_event_id(job_id, revision, _CLAIM_EVENT_TYPE),
            conversation_id=_text(session_id) or f"job:{_text(job_id)}",
            job_id=_text(job_id),
            result_revision=revision,
        ))
        try:
            db.flush()
            return True
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            if not isinstance(exc, IntegrityError):
                raise
            if index == len(revisions) - 1:
                return False  # another process owns this run
    return False


def _owner_allows_takeover(
    row: Any, *, allow_live_owner: bool, stale: bool = False,
) -> bool:
    """Whether a claimed job may be taken over by THIS process.

    Only a VERIFIED dead owner is replaceable.  ``live``/``self`` is another
    runner, and ``unknown`` (another host, missing stamp, failed inspection —
    see ``core.execution_ownership``) is explicitly NOT evidence of death.

    The one exception is ``stale``: a run whose attempt began longer ago than
    twice its own hard budget cannot still be inside that budget, so the
    verdict no longer identifies a runner that can deliver.  That is what
    bounds an ``unknown``-owner zombie (review finding 3) without weakening
    the "we cannot tell, do not touch" stance for a fresh attempt.
    """
    if allow_live_owner or stale:
        return True
    try:
        from core.execution_ownership import owner_liveness

        state, _info = owner_liveness(row.metadata_json)
        return state == "dead"
    except Exception:  # noqa: BLE001 — cannot tell means "do not touch"
        return False


def _claim_job_for_run(
    job_id: str, *, allow_live_owner: bool = False,
    allow_failed: bool = False,
) -> Optional[Dict[str, Any]]:
    """Claim the next run attempt for this job, or return None.

    The claim is a compare-and-swap on the shared database arbiter: the fresh
    row is read, a ``run:<attempt>`` lease is inserted, and only the winner
    mutates the row.  A live (or unknowable) owner is never replaced — the
    liveness verdict is re-read from the FRESH row, not from the recovery
    scan's snapshot.  On success the CURRENT process is stamped as owner.

    TERMINALITY (review finding 5): ``failed`` is terminal for this module
    everywhere else (``_job_is_in_flight``/``_active_job_for`` and every
    confirmation gate), so it is terminal here too.  Only the restart-recovery
    pass may revive a failed row, and only by passing ``allow_failed`` for an
    owner it can prove is gone (dead or stale): that keeps the generic boot
    sweep's externally-failed row repairable without letting a racing loser
    turn an announced failure into a success.

    The lease insert is the FIRST statement of its transaction (a small read
    phase precedes it).  That ordering matters on SQLite: taking the write
    lock directly avoids a read→write upgrade deadlock between two racing
    claimers.
    """
    from core.database import get_db_session
    from core.models import AgentExecution

    # --- read phase: snapshot the attempt + owner verdict, no writes --------
    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == str(job_id)).first()
        if row is None:
            return None
        job = _job_from_row(row)
        if job is None:
            return None
        if _terminal_delivery(job, db=db) is not None:
            # Another writer already produced this job's ONE terminal message.
            # Re-running it can only write a second (or clobber the durable
            # result behind the one the user already saw).
            logger.info(
                "[workdrive-background] claim refused for job %s: its terminal "
                "delivery is already written", str(job_id)[:12])
            return None
        attempts = int(job.get("attempts") or 0)
        job_status = str(job.get("status") or "")
        row_status = str(row.status or "")
        if row_status in ("completed", "cancelled") or (
                job_status == _JOB_STATUS_COMPLETED):
            return None
        failed = (row_status == "failed"
                  or job_status == _JOB_STATUS_FAILED)
        if failed and not allow_failed:
            logger.info(
                "[workdrive-background] claim refused for job %s: the job is "
                "failed (terminal)", str(job_id)[:12])
            return None
        stale_run = attempts > 0 and _run_is_stale(job, row)
        # A scheduled job's first attempt (attempts == 0) has no runner yet.
        # Every later attempt must prove its predecessor is gone (verified
        # dead, or stale beyond any possible in-budget run).  A failed row
        # with NO attempt was never in a runner's hands (a boot sweep
        # terminalized a job that never started), so recovery may re-run it
        # without displacing anyone.
        takeover = bool(
            allow_live_owner
            or (failed and allow_failed and attempts == 0)
        )
        if (attempts > 0 or failed) and not takeover:
            takeover = _owner_allows_takeover(
                row, allow_live_owner=False, stale=stale_run)
        if failed and not takeover:
            logger.info(
                "[workdrive-background] claim refused for job %s: failed row "
                "and its owner cannot be verified gone", str(job_id)[:12])
            return None
        if attempts > 0 and not takeover:
            logger.info(
                "[workdrive-background] claim refused for job %s: owner is "
                "still live or cannot be verified dead",
                str(job_id)[:12])
            return None
        if stale_run:
            logger.info(
                "[workdrive-background] claim for job %s takes over a stale "
                "run (attempt %s older than %.0fs)",
                str(job_id)[:12], attempts, _STALE_RUN_SECONDS)
        session_id = _text(job.get("session_id"))

    # --- write phase: lease first, then (only if won) the row mutation ------
    from core.execution_ownership import current_owner
    from core.models import ExecutionStatus
    from sqlalchemy.exc import OperationalError, ProgrammingError

    attempt = attempts + 1
    try:
        with get_db_session() as db:
            won = _claim_run_lease(
                db, job_id=str(job_id), attempt=attempt,
                session_id=session_id, takeover=takeover)
            if not won:
                # A legitimate loser of the lease sees the winner's committed
                # attempt bump on the fresh row.  An UNCHANGED counter with a
                # taken lease is an orphan from a corrupted job record (the
                # 2026-11-12 review's wedged shape: a reverted ``attempts``
                # made every pass retry its own leftover ``run:1`` forever).
                # Self-repair once with the deterministic takeover revision.
                fresh_row = db.query(AgentExecution).filter(
                    AgentExecution.id == str(job_id)).first()
                fresh_job = (
                    _job_from_row(fresh_row)
                    if fresh_row is not None else None)
                orphan_lease = (
                    isinstance(fresh_job, dict)
                    and int(fresh_job.get("attempts") or 0) == attempts)
                if orphan_lease and not takeover:
                    logger.warning(
                        "[workdrive-background] job %s attempt %s lease is "
                        "orphaned (counter still %s); repairing it",
                        str(job_id)[:12], attempt, attempts)
                    won = _claim_run_lease(
                        db, job_id=str(job_id), attempt=attempt,
                        session_id=session_id, takeover=True)
                if not won:
                    logger.info(
                        "[workdrive-background] claim for job %s attempt %s "
                        "lost to another process", str(job_id)[:12], attempt)
                    return None
            row = db.query(AgentExecution).filter(
                AgentExecution.id == str(job_id)).first()
            job = _job_from_row(row) if row is not None else None
            if job is None:
                db.rollback()
                return None
            # Defensive: the lease serializes claims, so if the attempt moved
            # someone else already took over; never run under a stale claim.
            if int(job.get("attempts") or 0) != attempts:
                db.rollback()
                logger.info(
                    "[workdrive-background] claim for job %s attempt %s "
                    "superseded while acquiring its lease",
                    str(job_id)[:12], attempt)
                return None
            if str(row.status or "") in ("completed", "cancelled"):
                db.rollback()
                return None
            if (str(row.status or "") == "failed"
                    or str(job.get("status") or "") == _JOB_STATUS_FAILED):
                if not allow_failed:
                    db.rollback()
                    return None
            job["status"] = _JOB_STATUS_RUNNING
            job["attempts"] = attempt
            job["last_attempt_at"] = _now_iso()
            meta = dict(row.metadata_json or {})
            meta["owner"] = current_owner()
            row.status = ExecutionStatus.RUNNING.value
            row.error_message = None
            row.completed_at = None
            _write_job_metadata(row, job, meta)
            db.commit()
            db.refresh(row)
            return dict(job)
    except (OperationalError, ProgrammingError) as exc:
        # The arbiter itself is unavailable (locked / minimal store).  Fail
        # closed: the durable job stays scheduled and the boot pass retries.
        logger.warning(
            "[workdrive-background] claim arbitration unavailable for job "
            "%s: %r", str(job_id)[:12], exc)
        return None


def _store_job_result(job_id: str, result_row: Dict[str, Any]) -> None:
    """Persist the complete delivery row on the durable job BEFORE delivery.

    A crash after this write and before the assistant message is written is
    recoverable without a second download: recovery re-delivers this row.

    TERMINAL GUARD (review finding 7): if another attempt has already written
    this job's ONE terminal message (typically the failure notice that won the
    terminal primary key), storing this result would leave the durable row
    claiming ``completed`` with bytes the user never saw, while the message
    they did see says the read failed.  The delivered message is authoritative,
    so this becomes a no-op.
    """
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == str(job_id)).first()
        if row is None:
            return
        job = _job_from_row(row) or {}
        terminal = _terminal_delivery(job, db=db)
        if terminal is not None:
            logger.info(
                "[workdrive-background] not storing a result for job %s: its "
                "terminal delivery (%s) is already written",
                str(job_id)[:12], terminal)
            return
        job["status"] = _JOB_STATUS_COMPLETED
        job["result"] = result_row
        job["completed_at"] = _now_iso()
        job["error"] = ""
        _write_job_metadata(row, job, row.metadata_json)
        db.commit()


def _finish_job(job_id: str, status: str, *, error: str = "",
                summary: str = "", respect_terminal: bool = False) -> None:
    """Write the job's durable terminal state and release its schedule gate.

    ``respect_terminal`` is for the POST-DELIVERY call sites only: when a
    concurrent attempt's failure notice won the terminal primary key while this
    one was running, this pass must not overwrite that job as ``completed`` —
    it has to record the state the user was actually told (review finding 7).
    """
    if respect_terminal and status == _JOB_STATUS_COMPLETED:
        _row, current = _get_job(job_id)
        terminal = (
            _terminal_delivery(current) if isinstance(current, dict) else None)
        if terminal == "failed":
            logger.info(
                "[workdrive-background] job %s keeps its announced failure: "
                "another attempt's failure notice is terminal",
                str(job_id)[:12])
            status = _JOB_STATUS_FAILED
            error = error or "another attempt's failure notice is terminal"
            summary = "terminal failure already delivered"
    from core.database import get_db_session
    from core.models import AgentExecution, DeliveryEvent, ExecutionStatus

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == str(job_id)).first()
        if row is None:
            return
        job = _job_from_row(row) or {}
        job["status"] = status
        if error:
            job["error"] = error[:1000]
        if summary:
            job["summary"] = summary[:1000]
        _write_job_metadata(row, job, row.metadata_json)
        row.status = (
            ExecutionStatus.COMPLETED.value if status == _JOB_STATUS_COMPLETED
            else ExecutionStatus.FAILED.value)
        row.completed_at = datetime.now(timezone.utc)
        row.result_summary = (summary or "")[:400] or None
        row.error_message = error[:1000] or None
        # TERMINAL RELEASE: the duplicate-scheduling gate is held only while
        # this accepted request has an unfinished job.  Releasing it in the
        # same transaction as the terminal state means a re-ask after
        # completion schedules a fresh job, while a re-ask during the run is
        # still collapsed onto it.
        gate = _schedule_gate_event_id(
            job.get("session_id"), job.get("original_digest"))
        if gate:
            # Only THIS job's gate: a concurrent recovery finishing an older
            # job must never delete the gate a newer re-ask already holds.
            db.query(DeliveryEvent).filter(
                DeliveryEvent.event_id == gate,
                DeliveryEvent.job_id == _text(job_id)).delete(
                synchronize_session=False)
        db.commit()


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def _workbook_like(file_name: Optional[str], resource_id: Optional[str]) -> bool:
    name = _text(file_name).lower()
    if name.endswith((".xlsx", ".xlsm")):
        return True
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    # An extensionless resolved resource can still be a workbook: the read
    # derives its extension from the downloaded magic bytes.  A KNOWN
    # non-workbook extension is not a strict-workbook request.
    return bool(resource_id) and not ext


def _reused_schedule(
    existing: Dict[str, Any],
    *,
    digest: str,
    authorization: str,
    execution_id: Optional[str],
    session: Optional[Dict[str, Any]],
    attached: bool = False,
    attach_mode: str = "",
) -> Dict[str, Any]:
    """The shape returned when an unfinished job already owns this request."""
    job_id = str(existing["job_id"])
    _live_sessions.setdefault(job_id, session or {})
    result = {
        "ok": True,
        "reused": True,
        "job_id": job_id,
        "execution_id": str(existing.get("execution_id") or job_id),
        "origin_execution_id": _text(execution_id),
        "original_digest": digest,
        "authorization": authorization,
        "status": existing.get("status"),
    }
    if attached:
        # A CONFIRMATION was attached to this job.  The returned digest is
        # the job's ORIGINAL digest (D1), so every later join — the persisted
        # delivery loader, the terminal delivery event — uses the same key
        # as the job that is actually running.
        result["attached"] = True
        result["attach_mode"] = _text(attach_mode)
    return result


def reuse_in_flight_workdrive_read(
    *,
    session_id: Optional[str],
    user_id: Optional[str],
    workspace_id: Optional[str],
    resource_id: Optional[str] = None,
    file_name: Optional[str] = None,
    requested_targets: Any = None,
    requested_fields: Any = None,
    attach_job_id: Optional[str] = None,
    confirmation_message: Optional[str] = None,
    confirmed_mention: Optional[str] = None,
) -> Dict[str, Any]:
    """A CONFIRMATION continues the read already running for this request.

    Callers must have proven continuity first (the confirmation lanes gate on
    ``is_filename_confirmation`` + the stored task match).  Returns the
    reused schedule shape — carrying the EXISTING job id and ORIGINAL digest
    — or an explicit ``no_in_flight_job`` refusal so the caller can fall
    through to its ordinary lane.  No digest is minted and no read starts.
    """
    if not _text(session_id) or not _text(user_id):
        return {"ok": False, "reason": "missing_session_or_user",
                "job_id": None}
    state = _authorization_state(user_id)
    if _authorization_blocked(state):
        return {"ok": False, "reason": f"authorization_{state}",
                "authorization": state, "job_id": None}
    scope = request_scope_from_task(
        session_id=session_id,
        user_id=user_id,
        workspace_id=workspace_id,
        resource_id=resource_id,
        file_name=file_name,
        original_message=confirmation_message,
        requested_targets=requested_targets,
        requested_fields=requested_fields,
    )
    existing, attach_mode = _in_flight_job_for_confirmation(
        _text(session_id), scope, attach_job_id=attach_job_id)
    if not isinstance(existing, dict) or not existing.get("job_id"):
        return {"ok": False, "reason": "no_in_flight_job", "job_id": None}
    _record_confirmation_on_job(
        str(existing["job_id"]),
        message=_text(confirmation_message),
        mention=_text(confirmed_mention or file_name),
        attach_mode=attach_mode,
    )
    logger.info(
        "[workdrive-background] confirmation attached to job %s (%s); "
        "zero live reads", str(existing["job_id"])[:12], attach_mode)
    return _reused_schedule(
        existing,
        digest=_text(existing.get("original_digest")),
        authorization=state,
        execution_id=None,
        session=None,
        attached=True,
        attach_mode=attach_mode,
    )


def schedule_strict_workdrive_read(
    *,
    session_id: Optional[str],
    user_id: Optional[str],
    workspace_id: Optional[str],
    execution_id: Optional[str],
    original_message: Optional[str],
    query: Optional[str] = None,
    mention: Optional[str] = None,
    resource_id: Optional[str] = None,
    file_name: Optional[str] = None,
    requested_targets: Any = None,
    requested_fields: Any = None,
    identity: Optional[Dict[str, Any]] = None,
    pending_task: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    canvas: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    request_id: Optional[str] = None,
    expected_content_sha256: Optional[str] = None,
    attach_job_id: Optional[str] = None,
    confirmation_turn: bool = False,
    confirmation_message: Optional[str] = None,
    confirmed_mention: Optional[str] = None,
    session: Optional[Dict[str, Any]] = None,
    spawn: bool = True,
    read_runner: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Create the durable job for a strict read that outlived its deadline.

    Returns ``{"ok": True, "job_id": ..., ...}`` when a job is (or already was)
    durably scheduled.  Refusals are explicit and carry a stable ``reason`` —
    nothing is silently downgraded to a materialized-copy read.
    """
    identity = dict(identity or {})
    resource = _text(resource_id or identity.get("resource_id")
                     or identity.get("file_id"))
    name = _text(file_name or identity.get("file_name") or mention)
    if not _workbook_like(name, resource):
        # Strict proof is a workbook contract.  Other file types keep their
        # existing behavior.
        return {"ok": False, "reason": "not_a_workbook", "job_id": None}
    if not _text(session_id) or not _text(user_id):
        return {"ok": False, "reason": "missing_session_or_user",
                "job_id": None}

    state = _authorization_state(user_id)
    if _authorization_blocked(state):
        return {
            "ok": False,
            "reason": f"authorization_{state}",
            "authorization": state,
            "job_id": None,
        }

    scope = request_scope_from_task(
        session_id=session_id,
        user_id=user_id,
        workspace_id=workspace_id,
        resource_id=resource,
        file_name=name,
        original_message=original_message or query,
        requested_targets=requested_targets,
        requested_fields=requested_fields,
    )
    digest = canonical_request_digest(scope)
    # CONFIRMATION REUSE (2026-11-12 review): a confirmation/re-delivery turn
    # continues the job already running for this request — by durable job id,
    # or by identity when the id did not survive a restart.  This is the ONLY
    # widened join: the ordinary exact-digest dedupe below still treats two
    # different asks on the same workbook as separate requests.
    if confirmation_turn:
        attached, attach_mode = _in_flight_job_for_confirmation(
            _text(session_id), scope, attach_job_id=attach_job_id)
        if isinstance(attached, dict) and attached.get("job_id"):
            _record_confirmation_on_job(
                str(attached["job_id"]),
                message=_text(confirmation_message or original_message),
                mention=_text(confirmed_mention or name),
                attach_mode=attach_mode,
            )
            return _reused_schedule(
                attached,
                digest=_text(attached.get("original_digest")) or digest,
                authorization=state,
                execution_id=execution_id,
                session=session,
                attached=True,
                attach_mode=attach_mode,
            )
    existing = _active_job_for(_text(session_id), digest)
    if isinstance(existing, dict) and existing.get("job_id"):
        return _reused_schedule(
            existing, digest=digest, authorization=state,
            execution_id=execution_id, session=session)

    job_id = uuid.uuid4().hex
    job = {
        "schema": SCHEMA,
        "job_id": job_id,
        # The background attempt owns this id.  The interactive attempt's id
        # is retained only as provenance and is never accepted on a receipt.
        "execution_id": job_id,
        "origin_execution_id": _text(execution_id),
        "session_id": _text(session_id),
        "user_id": _text(user_id),
        "workspace_id": _text(workspace_id),
        "tenant_id": _text(tenant_id),
        "agent_id": _text(agent_id),
        "request_id": _text(request_id),
        "provider": PROVIDER,
        "operation": OPERATION,
        "resource_id": resource,
        "file_name": name,
        "mention": _text(mention),
        "source_metadata": _json_safe(
            identity.get("source_metadata") or {}) or {},
        "source_version": _text(
            identity.get("version")
            or identity.get("content_hash")
            or identity.get("source_version")),
        "query": _text(query or original_message),
        "original_message": _text(original_message or query),
        "requested_targets": _clean_list(requested_targets),
        "requested_fields": _clean_list(requested_fields),
        "request_scope": scope,
        "original_digest": digest,
        "expected_content_sha256": _text(expected_content_sha256).lower(),
        "authorization": {
            "provider": PROVIDER,
            "user_id": _text(user_id),
            "state": state,
            "checked_at": _now_iso(),
        },
        "status": _JOB_STATUS_SCHEDULED,
        "attempts": 0,
        "created_at": _now_iso(),
        "history": _json_safe([
            entry for entry in (history or [])[-6:]
            if isinstance(entry, dict)
        ]) or [],
        "canvas": _json_safe(canvas) if isinstance(canvas, dict) else None,
        "task": _json_safe(pending_task)
        if isinstance(pending_task, dict) else None,
        "interactive_deadline_exceeded": True,
    }

    gate_id = _schedule_gate_event_id(_text(session_id), digest)
    scheduled = False
    # The gate closes the read-then-insert window in ``_active_job_for``: two
    # near-simultaneous identical asks can both miss the scan, but only one
    # can insert this primary key.  The retry only runs when the winner's job
    # turned out to be terminal already (its gate was released), which is the
    # legitimate "re-ask after completion" path.
    for _attempt in range(3):
        gate_conflict = False
        try:
            from core.database import get_db_session
            from core.execution_ownership import record_os_start
            from core.models import (
                AgentExecution,
                DeliveryEvent,
                ExecutionStatus,
            )

            with get_db_session() as db:
                db.add(DeliveryEvent(
                    event_id=gate_id,
                    conversation_id=_text(session_id),
                    job_id=job_id,
                    result_revision=_SCHEDULE_GATE_REVISION,
                ))
                try:
                    db.flush()
                except Exception as flush_exc:  # noqa: BLE001
                    from sqlalchemy.exc import IntegrityError

                    db.rollback()
                    if not isinstance(flush_exc, IntegrityError):
                        raise
                    gate_conflict = True
                if not gate_conflict:
                    db.add(AgentExecution(
                        id=job_id,
                        agent_id=_text(agent_id) or None,
                        workspace_id=_text(workspace_id) or None,
                        # Tenant/agent/workspace FKs are optional on this row;
                        # the durable job metadata carries the exact scope.
                        # Runner scope is never inferred from an FK that may
                        # not exist yet.
                        tenant_id=None,
                        status=ExecutionStatus.RUNNING.value,
                        input_summary=(
                            f"strict WorkDrive read {name or resource} "
                            f"for session {_text(session_id)}"
                        )[:300],
                        triggered_by=TRIGGERED_BY,
                        metadata_json=record_os_start(
                            {JOB_METADATA_KEY: job}),
                    ))
                    db.commit()
                    scheduled = True
        except Exception as exc:  # noqa: BLE001 — no durable job, no promise
            logger.error(
                "[workdrive-background] could not persist job for %s: %r",
                name or resource, exc)
            return {
                "ok": False,
                "reason": "durable_record_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "job_id": None,
            }
        if scheduled:
            break
        # The gate is held: another process scheduled this accepted request
        # after our scan missed it.  Re-read (fresh database session) and
        # collapse onto its job, exactly as the ordinary dedupe path does.
        winner = _active_job_for(_text(session_id), digest)
        if isinstance(winner, dict) and winner.get("job_id"):
            logger.info(
                "[workdrive-background] schedule for %s lost the gate to "
                "job %s; reusing it",
                name or resource, str(winner["job_id"])[:12])
            return _reused_schedule(
                winner, digest=digest, authorization=state,
                execution_id=execution_id, session=session)
        # A gate held by a job that is already terminal (typically failed by
        # the generic boot sweep, which never touches this module) can never
        # be released by ``_finish_job``.  Release it here instead of failing
        # this request forever, then retry the insert.
        if _release_terminal_schedule_gate(gate_id):
            continue

    if not scheduled:
        logger.warning(
            "[workdrive-background] schedule gate for %s stayed held with "
            "no active job; leaving the request unscheduled",
            name or resource)
        return {
            "ok": False,
            "reason": "schedule_conflict",
            "job_id": None,
        }

    if session is not None:
        _live_sessions[job_id] = session

    logger.info(
        "[workdrive-background] scheduled job %s for %s "
        "(origin execution %s, digest %s)",
        job_id[:12], name or resource, _text(execution_id)[:12] or "-",
        digest[:12])

    if spawn:
        spawn_background_read(
            job_id, session=session, read_runner=read_runner)

    return {
        "ok": True,
        "reused": False,
        "job_id": job_id,
        "execution_id": job_id,
        "origin_execution_id": _text(execution_id),
        "original_digest": digest,
        "authorization": state,
        "status": _JOB_STATUS_SCHEDULED,
        "schema": SCHEMA,
    }


# Alias: the import site reads naturally as a background-read schedule.
schedule_background_workdrive_read = schedule_strict_workdrive_read


def _spawn(coro: Any, key: str) -> bool:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning(
            "[workdrive-background] no running event loop; job %s stays "
            "durable and will be recovered by the boot pass", key[:12])
        return False
    task = loop.create_task(coro)
    _background_tasks[key] = task

    def _reap(_task: Any) -> None:
        _background_tasks.pop(key, None)

    task.add_done_callback(_reap)
    return True


def spawn_background_read(
    job_id: str,
    *,
    session: Optional[Dict[str, Any]] = None,
    read_runner: Optional[Callable[..., Any]] = None,
) -> bool:
    """Start the durable job in this process (durable even if it cannot)."""
    if job_id in _background_tasks and not _background_tasks[job_id].done():
        return False
    if session is not None:
        _live_sessions[job_id] = session
    return _spawn(
        execute_background_read(
            job_id, session=session, read_runner=read_runner),
        job_id,
    )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _validation_failure(job: Dict[str, Any], reason: str,
                        **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "job_id": job.get("job_id"), "reason": reason, **extra}


def _validate_job(job: Dict[str, Any], row_id: Optional[str] = None) -> Dict[str, Any]:
    """Recompute the original-request digest from the persisted scope."""
    scope = job.get("request_scope")
    if not isinstance(scope, dict) or not scope:
        return _validation_failure(job, "original_scope_missing")
    recomputed = canonical_request_digest(scope)
    if recomputed != _text(job.get("original_digest")):
        return _validation_failure(job, "original_digest_mismatch")
    if _text(job.get("job_id")) != _text(job.get("execution_id")):
        return _validation_failure(job, "job_execution_identity_mismatch")
    if row_id and _text(job.get("job_id")) != _text(row_id):
        return _validation_failure(job, "job_row_identity_mismatch")
    return {"ok": True}


def _resolve_resource(job: Dict[str, Any]) -> "tuple[str, str]":
    resource = _text(job.get("resource_id"))
    name = _text(job.get("file_name"))
    if resource:
        return resource, name
    try:
        from core.named_file_resolution import resolve_named_file_intent

        intent = resolve_named_file_intent(
            _text(job.get("query") or job.get("original_message")),
            _text(job.get("user_id")),
            _text(job.get("workspace_id")),
            pinned_mention=_text(job.get("mention")) or None,
        )
        for source in intent.get("sources") or []:
            dataset = (source or {}).get("dataset") or {}
            file_id = _text(dataset.get("file_id"))
            if not file_id:
                continue
            if "|" in file_id:
                provider, rid = file_id.split("|", 1)
                if _text(provider) != PROVIDER:
                    continue
            else:
                rid = file_id
            if rid:
                return rid, _text(dataset.get("file_name")) or name
    except Exception as exc:  # noqa: BLE001 — resolution failure is explicit
        logger.warning(
            "[workdrive-background] resource resolution failed for %s: %r",
            job.get("job_id"), exc)
    return "", name


def _default_read_runner(
    job: Dict[str, Any],
    *,
    llm_service: Any = None,
) -> Any:
    """Download + receipt through the existing strict read path.

    The ``execution_id`` handed to the read is the BACKGROUND job id, so the
    receipt and strict proof are produced by this execution and cannot be
    confused with the interactive attempt's.
    """
    return _run_strict_read_block(job)


async def _run_strict_read_block(job: Dict[str, Any]) -> Dict[str, Any]:
    from core.answer_presentation import new_attempt_id
    from core.chat_tool_planner import (
        _named_file_targets,
        _strict_named_workdrive_block,
    )

    resource_id, file_name = await asyncio.to_thread(_resolve_resource, job)
    if not resource_id:
        return {"ok": False, "error": "WorkDrive resource id could not be resolved"}
    job_id = _text(job.get("job_id") or job.get("execution_id"))
    query = _text(job.get("query") or job.get("original_message"))
    context = {
        "user_id": _text(job.get("user_id")) or None,
        "workspace_id": _text(job.get("workspace_id")) or "default",
        "tenant_id": _text(job.get("tenant_id")) or None,
        "session_id": _text(job.get("session_id")),
        "execution_id": job_id,
        # The strict contract is explicit and cannot be inherited from a
        # caller that merely wanted a cached read.
        "strict_workdrive_proof": True,
        "requested_targets": list(job.get("requested_targets") or []),
        "history": list(job.get("history") or []),
        "canvas": job.get("canvas"),
    }
    item_tokens = list(job.get("requested_targets") or [])
    if not item_tokens:
        try:
            item_tokens = _named_file_targets(query, context, None)
        except Exception:  # noqa: BLE001 — empty target set is honest
            item_tokens = []

    key = (PROVIDER, resource_id)
    plan = SimpleNamespace(_result_meta={})
    block = await _strict_named_workdrive_block(
        plan=plan,
        key=key,
        names={key: file_name},
        item_tokens=item_tokens,
        query=query,
        msg_text=_text(job.get("original_message")),
        context=context,
        catalog_truncated=False,
        scan_attempt_id=new_attempt_id(),
    )
    meta = dict(getattr(plan, "_result_meta", None) or {})
    storage = meta.get("storage_read") if isinstance(
        meta.get("storage_read"), dict) else {}
    proof = meta.get("direct_source_proof") or storage.get(
        "direct_source_proof")
    structured = meta.get("structured_result") or storage.get(
        "structured_result")
    if not isinstance(proof, dict) or proof.get("status") != "verified":
        return {
            "ok": False,
            "error": "strict WorkDrive proof was not produced",
            "block": block,
            "meta": meta,
        }
    if proof.get("execution_id") != job_id:
        return {
            "ok": False,
            "error": "strict WorkDrive proof was not produced by this job",
            "block": block,
            "meta": meta,
        }
    if not isinstance(structured, dict):
        return {
            "ok": False,
            "error": "downloaded workbook produced no structured result",
            "block": block,
            "meta": meta,
        }
    return {"ok": True, "block": block, "meta": meta, "error": ""}


def _proof_sha(proof: Dict[str, Any]) -> str:
    return _text(proof.get("downloaded_sha256")).lower()


def _validate_read_result(
    job: Dict[str, Any], result: Dict[str, Any],
) -> Dict[str, Any]:
    """Bind the download receipt + proof + artifact to the job id and digest."""
    if not isinstance(result, dict) or not result.get("ok"):
        return _validation_failure(
            job, "read_failed",
            error=_text((result or {}).get("error")) or "strict read failed")
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    proof = meta.get("direct_source_proof") or (
        meta.get("storage_read") or {}).get("direct_source_proof")
    if not isinstance(proof, dict) or proof.get("status") != "verified":
        return _validation_failure(job, "strict_proof_missing")
    job_id = _text(job.get("job_id"))
    if _text(proof.get("execution_id")) != job_id:
        return _validation_failure(job, "proof_execution_mismatch")
    receipt = proof.get("receipt") if isinstance(
        proof.get("receipt"), dict) else {}
    if _text(receipt.get("execution_id")) != job_id:
        return _validation_failure(job, "receipt_execution_mismatch")
    resource = _text(job.get("resource_id"))
    if not resource:
        resolved, _name = _resolve_resource(job)
        resource = resolved
    if resource and _text(proof.get("resource_id")) != resource:
        return _validation_failure(job, "proof_resource_mismatch")
    if not resource:
        return _validation_failure(job, "resource_id_missing")
    sha = _proof_sha(proof)
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        return _validation_failure(job, "proof_digest_invalid")
    if _text(receipt.get("sha256")).lower() != sha:
        return _validation_failure(job, "receipt_digest_mismatch")
    storage = meta.get("storage_read") if isinstance(
        meta.get("storage_read"), dict) else {}
    if _text(storage.get("content_sha256")).lower() not in ("", sha):
        return _validation_failure(job, "storage_digest_mismatch")
    structured = meta.get("structured_result") or storage.get(
        "structured_result")
    if not isinstance(structured, dict):
        return _validation_failure(job, "structured_result_missing")
    source_identity = structured.get("source_identity") if isinstance(
        structured.get("source_identity"), dict) else {}
    if _text(source_identity.get("content_hash")).lower() not in ("", sha):
        return _validation_failure(job, "artifact_digest_mismatch")
    expected = _text(job.get("expected_content_sha256")).lower()
    if expected and expected != sha:
        return _validation_failure(job, "source_digest_mismatch")
    return {
        "ok": True,
        "proof": proof,
        "meta": meta,
        "structured": structured,
        "content_sha256": sha,
        "resource_id": resource,
    }


def _persisted_row(
    job: Dict[str, Any],
    validated: Dict[str, Any],
    rendered: str,
) -> Dict[str, Any]:
    from core.answer_presentation import mark_delivered
    from core.workbook_read_artifact import TARGET_EXTRACTION_VERSION

    meta = validated["meta"]
    storage = meta.get("storage_read") if isinstance(
        meta.get("storage_read"), dict) else {}
    structured = validated["structured"]
    proof = validated["proof"]
    sha = validated["content_sha256"]
    resource = validated["resource_id"]
    job_id = _text(job["job_id"])
    identity = {
        "service": PROVIDER,
        "file_id": resource,
        "resource_id": resource,
        "file_name": _text(job.get("file_name")) or None,
        "source": PROVIDER,
        "content_hash": sha,
        "content_hash_algorithm": "sha256",
        "content_sha256": sha,
        "evidence_kind": "downloaded_bytes",
        "source_metadata": dict(job.get("source_metadata") or {}),
        "ingested_at": None,
        "source_modified_at": None,
        "version_verified": bool(job.get("source_version")),
        "identity_verified": True,
        "coverage_complete": bool(storage.get("coverage_complete")),
        "coverage_limits": dict(storage.get("coverage_limits") or {}),
        "workbook_read": storage.get("workbook_read"),
        "execution_id": job_id,
        "source_execution_id": job_id,
        "origin_execution_id": _text(job.get("origin_execution_id")),
        "direct_source_proof": proof,
    }
    row = {
        # The assistant row this row rides IS the user-visible delivery.
        "status": "delivered",
        "target_extraction_version": TARGET_EXTRACTION_VERSION,
        "rendered": rendered[:24000],
        "rendered_core": rendered[:24000],
        "identity": identity,
        "workbook_read": storage.get("workbook_read"),
        "coverage_complete": bool(storage.get("coverage_complete")),
        "retrieval_finished": True,
        "calculation_complete": True,
        "open_requirements": [],
        "execution_id": job_id,
        "source_execution_id": job_id,
        "origin_execution_id": _text(job.get("origin_execution_id")),
        "job_id": job_id,
        "retrieved_at": time.time(),
        "structured_result": structured,
        "attempt_id": structured.get("attempt_id"),
        "evidence_revision": structured.get("evidence_revision"),
        "evidence_action": structured.get("evidence_action"),
        "direct_source_proof": proof,
        "strict_read_receipt": (
            proof.get("receipt") or storage.get("strict_read_receipt")),
        "content_sha256": sha,
        "content_hash": sha,
        "evidence_kind": "downloaded_bytes",
        "original_digest": _text(job.get("original_digest")),
        BACKGROUND_DELIVERY_KEY: {
            "schema": SCHEMA,
            "job_id": job_id,
            "execution_id": job_id,
            "origin_execution_id": _text(job.get("origin_execution_id")),
            "user_id": _text(job.get("user_id")),
            "workspace_id": _text(job.get("workspace_id")),
            "session_id": _text(job.get("session_id")),
            "resource_id": resource,
            "original_digest": _text(job.get("original_digest")),
            "request_scope": dict(job.get("request_scope") or {}),
            # Enforced on every re-delivery: the row can never drift from
            # the bytes this job's receipt names.
            "content_sha256": sha,
            "proof_execution_id": _text(proof.get("execution_id")),
            "interactive_deadline_exceeded": True,
            "delivered_at": _now_iso(),
        },
    }
    try:
        return dict(mark_delivered(row, rendered[:24000]))
    except Exception:  # noqa: BLE001 — pin is optional
        return row


def _current_pending_task(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The conversation's current task, if a newer objective superseded ours.

    Background delivery must never resurrect the objective it was scheduled
    from when the user has since moved on.
    """
    session_id = _text(job.get("session_id"))
    if not session_id:
        return None
    try:
        from core.database import get_db_session
        from core.models import ChatMessage

        with get_db_session() as db:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.conversation_id == session_id,
                    ChatMessage.role == "assistant",
                )
                .order_by(ChatMessage.created_at.desc(),
                          ChatMessage.id.desc())
                .limit(24)
                .all()
            )
        for row in rows:
            try:
                meta = json.loads(row.metadata_json or "{}")
            except Exception:  # noqa: BLE001
                continue
            task = meta.get("pending_file_task") or meta.get(
                "_pending_file_task")
            if isinstance(task, dict) and task.get("task_id"):
                return task
    except Exception as exc:  # noqa: BLE001 — best effort
        logger.debug("[workdrive-background] current task lookup skipped: %r",
                     exc)
    return None


def _same_task(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    lid = _text(left.get("task_id"))
    rid = _text(right.get("task_id"))
    if lid and rid and lid == rid:
        return True
    lmsg = " ".join(_text(left.get("original_message")).split()).lower()
    rmsg = " ".join(_text(right.get("original_message")).split()).lower()
    return bool(lmsg and rmsg and lmsg == rmsg)


def _delivery_metadata(job: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    task = dict(job.get("task") or {}) if isinstance(job.get("task"), dict) else {}
    identity = dict(row.get("identity") or {})
    current = _current_pending_task(job)
    if current and task and not _same_task(current, task):
        # A NEWER objective owns the conversation.  Deliver the result it
        # asked for, but do not overwrite that objective's durable task.
        task = current
        identity_out = None
    else:
        if current:
            task = {**current, **task}
        if task:
            task["status"] = "retrieved"
            task["resolved_file"] = identity
            task["retrieved_at"] = time.time()
            task["updated_at"] = time.time()
            task["retrieval_finished"] = True
            task["answer_delivered"] = True
        identity_out = identity
    return {
        "pending_file_result": row,
        "pending_file_task": task,
        "_pending_file_task": task,
        **({"resolved_file_identity": identity_out}
           if identity_out is not None else {}),
        "workdrive_background_read": {
            "schema": SCHEMA,
            "job_id": _text(job.get("job_id")),
            "execution_id": _text(job.get("execution_id")),
            "origin_execution_id": _text(job.get("origin_execution_id")),
            "original_digest": _text(job.get("original_digest")),
            "content_sha256": _text(
                (row.get(BACKGROUND_DELIVERY_KEY) or {}).get("content_sha256")),
            "status": "delivered",
            "delivered_at": _now_iso(),
        },
    }


def _terminal_delivery(
    job: Dict[str, Any], *, db: Any = None,
) -> Optional[str]:
    """Status of this job's already-written terminal delivery, if any.

    Both the successful result (``delivered``) and the honest failure notice
    (``failed``) are TERMINAL for one job: at most one of them may ever be
    written.  Recovery consults this so an announced failure is not re-run
    into a second message.

    Pass ``db`` to read through a caller's session.  That matters on a
    single-connection store (and keeps every check inside the one transaction
    that acts on it); omit it to open a short-lived session of its own.
    """
    job_id = _text(job.get("job_id"))
    session_id = _text(job.get("session_id"))
    if not job_id or not session_id:
        return None
    try:
        from core.database import get_db_session
        from core.models import ChatMessage

        if db is not None:
            return _terminal_delivery_in_session(db, job_id, session_id,
                                                 ChatMessage)
        with get_db_session() as own:
            return _terminal_delivery_in_session(own, job_id, session_id,
                                                 ChatMessage)
    except Exception as exc:  # noqa: BLE001 — best effort
        logger.debug("[workdrive-background] delivered check skipped: %r", exc)
    return None


def _terminal_delivery_in_session(
    db: Any, job_id: str, session_id: str, model: Any,
) -> Optional[str]:
    rows = (
        db.query(model)
        .filter(
            model.conversation_id == session_id,
            model.role == "assistant",
            model.metadata_json.like(f"%{job_id}%"),
        )
        .order_by(model.created_at.desc(), model.id.desc())
        .limit(12)
        .all()
    )
    for row in rows:
        try:
            meta = json.loads(row.metadata_json or "{}")
        except Exception:  # noqa: BLE001
            continue
        marker = meta.get("workdrive_background_read")
        if isinstance(marker, dict) and _text(
                marker.get("job_id")) == job_id:
            status = _text(marker.get("status"))
            if status in ("delivered", "failed"):
                return status
    return None


def _already_delivered(job: Dict[str, Any]) -> bool:
    return _terminal_delivery(job) == "delivered"


def deliver_persisted_result(
    job: Dict[str, Any], row: Dict[str, Any],
    *, session: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist one completed result on the existing assistant-row carrier.

    Idempotent by ``DeliveryEvent`` primary key (the shared job-delivery
    arbitration).  Returns True when this call wrote the delivery.
    """
    from core.database import get_db_session
    from core.job_delivery import job_event_id
    from core.models import ChatMessage, DeliveryEvent

    job_id = _text(job.get("job_id"))
    session_id = _text(job.get("session_id"))
    content_sha = _text(
        (row.get(BACKGROUND_DELIVERY_KEY) or {}).get("content_sha256"))
    if not job_id or not session_id or not content_sha:
        return False
    if _already_delivered(job):
        return False
    # TERMINAL RESULT PER JOB: the revision is the job identity, not the
    # downloaded sha.  A job is exactly one read, so two concurrent reruns
    # that saw different workbook bytes (or two recovery passes) race for ONE
    # primary key and exactly one assistant message is written.  The served
    # row stays self-consistent because ``persisted_delivery_is_valid``
    # re-binds it to its own marker sha.
    event_id = job_event_id(job_id, _TERMINAL_REVISION, _TERMINAL_EVENT_TYPE)
    text = _text(row.get("rendered")) or (
        "The strict Workbook read finished in the background.")
    metadata = _delivery_metadata(job, row)
    try:
        with get_db_session() as db:
            db.add(DeliveryEvent(
                event_id=event_id,
                conversation_id=session_id,
                job_id=job_id,
                result_revision=_TERMINAL_REVISION,
            ))
            try:
                db.flush()
            except Exception as flush_exc:  # noqa: BLE001
                from sqlalchemy.exc import IntegrityError

                db.rollback()
                if isinstance(flush_exc, IntegrityError):
                    return False  # another writer delivered it
                raise
            db.add(ChatMessage(
                conversation_id=session_id,
                tenant_id=_text(job.get("tenant_id")) or "default",
                role="assistant",
                content=text[:24000],
                metadata_json=json.dumps(metadata, default=str),
            ))
            db.commit()
    except Exception as exc:  # noqa: BLE001 — try again on recovery
        from sqlalchemy.exc import OperationalError, ProgrammingError

        if isinstance(exc, (OperationalError, ProgrammingError)):
            # A minimal/test store may not carry the shared delivery-events
            # table.  The durable carrier is still writable; losing the
            # reason for a missing ledger must not lose the answer.  The
            # prior idempotency check narrows the duplicate window.
            try:
                with get_db_session() as db:
                    db.add(ChatMessage(
                        conversation_id=session_id,
                        tenant_id=_text(job.get("tenant_id")) or "default",
                        role="assistant",
                        content=text[:24000],
                        metadata_json=json.dumps(metadata, default=str),
                    ))
                    db.commit()
                logger.warning(
                    "[workdrive-background] delivered without the "
                    "delivery-events ledger (%r)", exc)
            except Exception as carrier_exc:  # noqa: BLE001
                logger.warning(
                    "[workdrive-background] delivery write failed for %s: %r",
                    job_id[:12], carrier_exc)
                return False
        else:
            logger.warning(
                "[workdrive-background] delivery write failed for %s: %r",
                job_id[:12], exc)
            return False

    # Live-session fast path (same process): the very next turn sees the
    # result even before the DB loader runs.  The durable row is authoritative.
    live = session if session is not None else _live_sessions.get(job_id)
    if isinstance(live, dict):
        live["_pending_file_result"] = row
        task = metadata.get("pending_file_task")
        if isinstance(task, dict) and task:
            live["_pending_file_task"] = task
            live["_pending_file_task"]["status"] = "retrieved"
        live["_resolved_file_identity"] = metadata.get(
            "resolved_file_identity")
    try:
        from core.websockets import get_connection_manager

        awaitable = get_connection_manager().broadcast_event(
            f"user:{_text(job.get('user_id'))}",
            "workdrive_read_complete",
            {
                "job_id": job_id,
                "execution_id": _text(job.get("execution_id")),
                "session_id": session_id,
                "status": "delivered",
                "resource_id": _text(job.get("resource_id")),
                "content_sha256": content_sha,
            },
        )
        if asyncio.iscoroutine(awaitable):
            # This function is sync by design (recovery may call it from a
            # non-async boundary); the in-process event loop owns the task.
            try:
                asyncio.get_running_loop().create_task(awaitable)
            except RuntimeError:
                awaitable.close()
    except Exception as exc:  # noqa: BLE001 — notification is best effort
        logger.debug("[workdrive-background] WS broadcast skipped: %r", exc)
    return True


def _failure_row(job: Dict[str, Any], error: str) -> Dict[str, Any]:
    message = (
        "The background WorkDrive workbook read could not complete: "
        f"{_text(error)[:300]}. No cached-copy answer was substituted."
    )
    return {
        "status": "failed",
        "rendered": message,
        "identity": {
            "service": PROVIDER,
            "resource_id": _text(job.get("resource_id")) or None,
            "file_name": _text(job.get("file_name")) or None,
            "execution_id": _text(job.get("job_id")),
            "origin_execution_id": _text(job.get("origin_execution_id")),
        },
        "execution_id": _text(job.get("job_id")),
        BACKGROUND_DELIVERY_KEY: {
            "schema": SCHEMA,
            "job_id": _text(job.get("job_id")),
            "execution_id": _text(job.get("job_id")),
            "original_digest": _text(job.get("original_digest")),
            "status": "failed",
            "error": _text(error)[:1000],
            "interactive_deadline_exceeded": True,
        },
    }


def _deliver_failure(job: Dict[str, Any], error: str) -> None:
    """Deliver an honest failure on the same durable carrier.

    A failed background read must never disappear into a log line: the user
    who waited for it gets a message, and no stale successful result is
    attributed to this job.
    """
    from core.database import get_db_session
    from core.job_delivery import job_event_id
    from core.models import ChatMessage, DeliveryEvent

    job_id = _text(job.get("job_id"))
    session_id = _text(job.get("session_id"))
    if not (job_id and session_id):
        return
    # SAME terminal primary key as the success path: a job may produce ONE
    # terminal message, whether that is its result or this failure notice.
    # A success that was already delivered therefore cannot be followed by a
    # failure notice, and vice versa.
    event_id = job_event_id(job_id, _TERMINAL_REVISION, _TERMINAL_EVENT_TYPE)
    row = _failure_row(job, error)
    try:
        with get_db_session() as db:
            db.add(DeliveryEvent(
                event_id=event_id,
                conversation_id=session_id,
                job_id=job_id,
                result_revision="failed",
            ))
            try:
                db.flush()
            except Exception as flush_exc:  # noqa: BLE001
                from sqlalchemy.exc import IntegrityError

                db.rollback()
                if isinstance(flush_exc, IntegrityError):
                    return
                raise
            db.add(ChatMessage(
                conversation_id=session_id,
                tenant_id=_text(job.get("tenant_id")) or "default",
                role="assistant",
                content=row["rendered"][:4000],
                metadata_json=json.dumps({
                    "workdrive_background_read": {
                        **row[BACKGROUND_DELIVERY_KEY],
                        "status": "failed",
                    },
                }, default=str),
            ))
            db.commit()
    except Exception as exc:  # noqa: BLE001
        from sqlalchemy.exc import OperationalError, ProgrammingError

        if isinstance(exc, (OperationalError, ProgrammingError)):
            try:
                with get_db_session() as db:
                    db.add(ChatMessage(
                        conversation_id=session_id,
                        tenant_id=_text(job.get("tenant_id")) or "default",
                        role="assistant",
                        content=row["rendered"][:4000],
                        metadata_json=json.dumps({
                            "workdrive_background_read": {
                                **row[BACKGROUND_DELIVERY_KEY],
                                "status": "failed",
                            },
                        }, default=str),
                    ))
                    db.commit()
                return
            except Exception as carrier_exc:  # noqa: BLE001
                logger.warning(
                    "[workdrive-background] failure notice skipped for %s: "
                    "%r", job_id[:12], carrier_exc)
                return
        logger.warning(
            "[workdrive-background] failure notice skipped for %s: %r",
            job_id[:12], exc)


async def execute_background_read(
    job_id: str,
    *,
    session: Optional[Dict[str, Any]] = None,
    read_runner: Optional[Callable[..., Any]] = None,
    allow_live_owner: bool = False,
    allow_failed: bool = False,
) -> Dict[str, Any]:
    """Run one durable strict WorkDrive read to completion.

    Idempotent: an already-persisted result is re-delivered without any
    download; a job that already produced its ONE terminal message (success
    or failure) is a no-op.
    """
    row, job = _get_job(job_id)
    if row is None or not isinstance(job, dict):
        return {"ok": False, "job_id": job_id, "reason": "job_not_found"}
    durable_row_id = str(row.id)
    job["job_id"] = _text(job.get("job_id")) or durable_row_id

    terminal = _terminal_delivery(job)
    if terminal is not None:
        if terminal == "delivered":
            if str(row.status or "") != "completed":
                _finish_job(job["job_id"], _JOB_STATUS_COMPLETED,
                            summary="already delivered")
            return {"ok": True, "job_id": job["job_id"], "delivered": False,
                    "reason": "already_delivered"}
        # An announced failure is terminal for this job: re-running it would
        # write a SECOND terminal message for the same job.
        if str(row.status or "") != "failed":
            _finish_job(
                job["job_id"], _JOB_STATUS_FAILED,
                error=_text(job.get("error"))
                or "terminal failure already delivered")
        return {"ok": False, "job_id": job["job_id"],
                "reason": "terminal_failure_already_delivered"}

    valid = _validate_job(job, row_id=durable_row_id)
    if not valid.get("ok"):
        error = f"original request digest failed: {valid.get('reason')}"
        _finish_job(job["job_id"], _JOB_STATUS_FAILED, error=error)
        _deliver_failure(job, error)
        return {"ok": False, "job_id": job["job_id"],
                "reason": valid.get("reason")}

    state = _authorization_state(job.get("user_id"))
    if _authorization_blocked(state):
        error = f"authorization {state}; no download was attempted"
        _finish_job(job["job_id"], _JOB_STATUS_FAILED, error=error)
        _deliver_failure(job, error)
        return {"ok": False, "job_id": job["job_id"],
                "reason": f"authorization_{state}",
                "authorization": state}

    stored = job.get("result")
    if isinstance(stored, dict) and stored.get("rendered"):
        # Crash after durable result commit, before the assistant row: finish
        # the delivery WITHOUT touching the provider again — but only after
        # the same authorization + original-digest + workspace gates a live
        # run passes.
        if not persisted_delivery_is_valid(
                stored, user_id=job.get("user_id"),
                expected_original_digest=job.get("original_digest"),
                workspace_id=job.get("workspace_id")):
            error = "persisted background result failed authorization/digest validation"
            _finish_job(job["job_id"], _JOB_STATUS_FAILED, error=error)
            _deliver_failure(job, error)
            return {"ok": False, "job_id": job["job_id"],
                    "reason": "persisted_result_invalid"}
        delivered = deliver_persisted_result(job, stored, session=session)
        _finish_job(job["job_id"], _JOB_STATUS_COMPLETED,
                    summary="recovered persisted delivery",
                    respect_terminal=True)
        return {
            "ok": True,
            "job_id": job["job_id"],
            "delivered": bool(delivered),
            "result": stored,
            "recovered": True,
            "reread": False,
        }

    claimed = _claim_job_for_run(
        job["job_id"], allow_live_owner=allow_live_owner,
        allow_failed=allow_failed)
    if not isinstance(claimed, dict):
        return {"ok": False, "job_id": job["job_id"],
                "reason": "job_claim_failed"}
    job = claimed
    job["job_id"] = _text(job.get("job_id")) or str(job_id)

    runner = read_runner or _default_read_runner
    try:
        _pending_result = runner(job)
        if inspect.isawaitable(_pending_result):
            result = await asyncio.wait_for(
                _pending_result, timeout=_BACKGROUND_BUDGET_SECONDS)
        else:
            result = _pending_result
    except asyncio.TimeoutError:
        error = (
            "background read did not finish within its "
            f"{_BACKGROUND_BUDGET_SECONDS:.0f}s budget")
        _finish_job(job["job_id"], _JOB_STATUS_FAILED, error=error)
        _deliver_failure(job, error)
        return {"ok": False, "job_id": job["job_id"],
                "reason": "background_timeout"}
    except Exception as exc:  # noqa: BLE001 — record honestly, deliver notice
        error = f"{type(exc).__name__}: {exc}"
        _finish_job(job["job_id"], _JOB_STATUS_FAILED, error=error)
        _deliver_failure(job, error)
        return {"ok": False, "job_id": job["job_id"],
                "reason": "background_exception", "error": error}

    validated = _validate_read_result(job, result)
    if not validated.get("ok"):
        error = f"strict read verification failed: {validated.get('reason')}"
        _finish_job(job["job_id"], _JOB_STATUS_FAILED, error=error)
        _deliver_failure(job, error)
        return {"ok": False, "job_id": job["job_id"],
                "reason": validated.get("reason"),
                "error": _text((result or {}).get("error"))}

    rendered = _text((validated.get("meta") or {}).get("rendered_answer"))
    if not rendered:
        rendered = _text((result or {}).get("block"))
    if not rendered:
        error = "downloaded workbook produced no answer text"
        _finish_job(job["job_id"], _JOB_STATUS_FAILED, error=error)
        _deliver_failure(job, error)
        return {"ok": False, "job_id": job["job_id"],
                "reason": "empty_answer"}

    row_out = _persisted_row(job, validated, rendered)
    # Durable result FIRST, then delivery: a crash between the two is
    # recoverable without a re-read.
    _store_job_result(job["job_id"], row_out)
    delivered = deliver_persisted_result(job, row_out, session=session)
    _finish_job(
        job["job_id"], _JOB_STATUS_COMPLETED,
        summary=f"strict WorkDrive read delivered from {rendered[:80]!r}",
        respect_terminal=True)
    logger.info(
        "[workdrive-background] job %s completed: bytes=%s sha256=%s "
        "execution=%s delivered=%s",
        job["job_id"][:12], len(_text(rendered)),
        _text((row_out.get(BACKGROUND_DELIVERY_KEY) or {}).get(
            "content_sha256"))[:12],
        job["job_id"][:12], delivered)
    return {
        "ok": True,
        "job_id": job["job_id"],
        "delivered": bool(delivered),
        "result": row_out,
        "reread": True,
        "content_sha256": _text(
            (row_out.get(BACKGROUND_DELIVERY_KEY) or {}).get(
                "content_sha256")),
    }


# Alias for callers that name the provider explicitly.
execute_strict_workdrive_background_read = execute_background_read


# ---------------------------------------------------------------------------
# Persisted-delivery validation / loading
# ---------------------------------------------------------------------------

def persisted_delivery_is_valid(
    result: Any,
    *,
    user_id: Optional[str] = None,
    expected_original_digest: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> bool:
    """Whether a persisted background result may be served again.

    Re-checks authorization, the original digest, and (when the serving turn
    names a workspace) WORKSPACE SCOPE, and re-binds the artifact digest to
    the receipt/proof.  Rows written by the older direct path have no
    background marker and are NOT affected by this gate.
    """
    if not isinstance(result, dict):
        return False
    marker = result.get(BACKGROUND_DELIVERY_KEY)
    if not isinstance(marker, dict):
        return True  # not a background-delivery row: existing path unchanged
    if _text(marker.get("status")) not in ("", "delivered"):
        return False
    job_id = _text(marker.get("job_id"))
    digest = _text(marker.get("original_digest"))
    scope = marker.get("request_scope")
    if not job_id or not digest or not isinstance(scope, dict):
        return False
    if canonical_request_digest(scope) != digest:
        return False
    # WORKSPACE SCOPE AT SAVED DELIVERY: a result retrieved for another
    # workspace must never be replayed into this turn's conversation.  Both
    # the marker copy and the digest-bound scope must agree with the caller;
    # an absent stored workspace cannot be proven to match, so it fails
    # closed when the caller supplies one.
    expected_workspace = _text(workspace_id)
    if expected_workspace:
        if _text(marker.get("workspace_id")) != expected_workspace:
            return False
        if _text(scope.get("workspace_id")) != expected_workspace:
            return False
    owner = _text(marker.get("user_id"))
    if user_id and owner and _text(user_id) != owner:
        return False
    if expected_original_digest and _text(
            expected_original_digest) != digest:
        return False
    state = _authorization_state(owner)
    if _authorization_blocked(state):
        return False
    proof = result.get("direct_source_proof")
    if not isinstance(proof, dict) or proof.get("status") != "verified":
        return False
    if bool(proof.get("materialized")):
        return False
    sha = _text(marker.get("content_sha256")).lower()
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        return False
    if _proof_sha(proof) != sha:
        return False
    receipt = proof.get("receipt") if isinstance(
        proof.get("receipt"), dict) else {}
    if _text(receipt.get("sha256")).lower() != sha:
        return False
    if _text(receipt.get("execution_id")) != _text(
            marker.get("proof_execution_id") or proof.get("execution_id")):
        return False
    if _text(proof.get("execution_id")) != job_id:
        return False
    structured = result.get("structured_result")
    if isinstance(structured, dict):
        source_identity = structured.get("source_identity")
        if isinstance(source_identity, dict):
            got = _text(source_identity.get("content_hash")).lower()
            if got and got != sha:
                return False
    identity = result.get("identity")
    if isinstance(identity, dict):
        got = _text(identity.get("content_sha256")).lower()
        if got and got != sha:
            return False
    return True


def load_persisted_workdrive_delivery(
    session_id: Optional[str],
    *,
    user_id: Optional[str] = None,
    expected_original_digest: Optional[str] = None,
    workspace_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Load a validated background delivery from assistant-row metadata.

    This is the re-delivery-without-re-read seam.  It touches no provider and
    performs no workbook inspection.
    """
    if not _text(session_id):
        return None
    try:
        from core.database import get_db_session
        from core.models import ChatMessage

        with get_db_session() as db:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.conversation_id == _text(session_id),
                    ChatMessage.role == "assistant",
                )
                .order_by(ChatMessage.created_at.desc(),
                          ChatMessage.id.desc())
                .limit(24)
                .all()
            )
        for row in rows:
            try:
                meta = json.loads(row.metadata_json or "{}")
            except Exception:  # noqa: BLE001
                continue
            result = meta.get("pending_file_result")
            if not isinstance(result, dict):
                continue
            marker = result.get(BACKGROUND_DELIVERY_KEY)
            if not isinstance(marker, dict):
                continue
            if job_id and _text(marker.get("job_id")) != _text(job_id):
                continue
            if persisted_delivery_is_valid(
                    result, user_id=user_id,
                    expected_original_digest=expected_original_digest,
                    workspace_id=workspace_id):
                return result
    except Exception as exc:  # noqa: BLE001 — loader is best effort
        logger.debug(
            "[workdrive-background] persisted delivery load skipped: %r", exc)
    return None


# ---------------------------------------------------------------------------
# Restart recovery
# ---------------------------------------------------------------------------

def _job_rows() -> List[Any]:
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        return list(
            db.query(AgentExecution)
            .filter(AgentExecution.triggered_by == TRIGGERED_BY)
            .all()
        )


def _owner_is_live(row: Any) -> bool:
    try:
        from core.execution_ownership import owner_liveness

        state, _info = owner_liveness(row.metadata_json)
        return state in ("live", "self")
    except Exception:  # noqa: BLE001 — unknown means "do not touch"
        return True


async def recover_pending_strict_workdrive_reads(
    *,
    read_runner: Optional[Callable[..., Any]] = None,
    allow_live_owner: bool = False,
) -> Dict[str, int]:
    """Boot/restart recovery for durable strict WorkDesk read jobs.

    * A persisted result is re-delivered with ZERO provider reads.
    * An unfinished job is re-run only when no live owner holds it and its
      retry budget is not exhausted.
    * Every action is idempotent; a second pass is safe.
    """
    stats = {
        "candidates": 0,
        "delivered": 0,
        "reused_result": 0,
        "rerun": 0,
        "skipped_live": 0,
        "skipped_delivered": 0,
        "skipped_terminal": 0,
        "failed": 0,
        "gates_released": 0,
        "details": [],
    }
    # Reclaim gates orphaned by rows terminalized outside ``_finish_job``
    # (generic boot sweep) BEFORE the per-job pass, so a job that this pass
    # repairs is never blocked by its own stale gate.
    stats["gates_released"] = _sweep_terminal_schedule_gates()
    try:
        rows = _job_rows()
    except Exception as exc:  # noqa: BLE001 — boot pass must never crash
        logger.warning(
            "[workdrive-background] recovery scan failed: %r", exc)
        return stats

    for row in rows:
        job = _job_from_row(row)
        if not isinstance(job, dict):
            continue
        stats["candidates"] += 1
        job_id = _text(job.get("job_id")) or str(row.id)
        job["job_id"] = job_id
        try:
            terminal = _terminal_delivery(job)
            if terminal is not None:
                if terminal == "delivered":
                    if str(row.status or "") != "completed":
                        _finish_job(job_id, _JOB_STATUS_COMPLETED,
                                    summary="already delivered")
                    stats["skipped_delivered"] += 1
                else:
                    # The user was already told this job failed.  Re-running
                    # it would write a SECOND terminal message for the same
                    # job, so the announced failure is terminal.
                    if str(row.status or "") != "failed":
                        _finish_job(
                            job_id, _JOB_STATUS_FAILED,
                            error=_text(job.get("error"))
                            or "terminal failure already delivered")
                    stats["skipped_terminal"] += 1
                continue
            stored = job.get("result")
            if isinstance(stored, dict) and stored.get("rendered"):
                if not persisted_delivery_is_valid(
                        stored, user_id=job.get("user_id"),
                        expected_original_digest=job.get("original_digest"),
                        workspace_id=job.get("workspace_id")):
                    error = (
                        "persisted background result failed "
                        "authorization/digest validation")
                    _finish_job(job_id, _JOB_STATUS_FAILED, error=error)
                    _deliver_failure(job, error)
                    stats["failed"] += 1
                    stats["details"].append({
                        "job_id": job_id,
                        "failed": "persisted_result_invalid"})
                    continue
                if deliver_persisted_result(job, stored):
                    stats["delivered"] += 1
                    stats["reused_result"] += 1
                _finish_job(job_id, _JOB_STATUS_COMPLETED,
                            summary="recovered persisted delivery")
                continue
            if (not allow_live_owner
                    and str(row.status or "") == "running"
                    and str(job.get("status") or "") == _JOB_STATUS_RUNNING
                    and int(job.get("attempts") or 0) > 0
                    and _owner_is_live(row)
                    and not _run_is_stale(job, row)):
                stats["skipped_live"] += 1
                stats["details"].append({
                    "job_id": job_id, "skipped": "live_owner"})
                continue
            if int(job.get("attempts") or 0) >= _MAX_RECOVERY_ATTEMPTS:
                error = (
                    "background read exhausted its restart recovery "
                    f"attempts ({_MAX_RECOVERY_ATTEMPTS})")
                _finish_job(job_id, _JOB_STATUS_FAILED, error=error)
                _deliver_failure(job, error)
                stats["failed"] += 1
                stats["details"].append({
                    "job_id": job_id, "failed": "attempts_exhausted"})
                continue
            out = await execute_background_read(
                job_id, read_runner=read_runner,
                allow_live_owner=allow_live_owner,
                # THIS pass is the repair lane: a row the generic boot sweep
                # failed while its owner died is claimable by the recovery
                # pass (the claim still requires a gone/stale owner).
                allow_failed=True)
            if out.get("ok"):
                stats["rerun"] += 1
                if out.get("delivered"):
                    stats["delivered"] += 1
            else:
                stats["failed"] += 1
                stats["details"].append({
                    "job_id": job_id,
                    "failed": out.get("reason") or "read_failed"})
        except Exception as exc:  # noqa: BLE001 — per-job isolation
            stats["failed"] += 1
            stats["details"].append({
                "job_id": job_id, "error": f"{type(exc).__name__}: {exc}"})
            logger.warning(
                "[workdrive-background] recovery for %s failed: %r",
                job_id[:12], exc)
    if stats["candidates"]:
        logger.info(
            "[workdrive-background] recovery: %s",
            {k: v for k, v in stats.items() if k != "details"})
    return stats


recover_pending_workdrive_reads = recover_pending_strict_workdrive_reads
recover_workdrive_background_reads = recover_pending_strict_workdrive_reads
execute_workdrive_background_read = execute_background_read
load_workdrive_background_delivery = load_persisted_workdrive_delivery


def schedule_recovery_at_startup() -> bool:
    """Schedule the one-shot recovery pass from the lifespan (idempotent)."""
    return _spawn(
        recover_pending_strict_workdrive_reads(),
        "__startup_recovery__",
    )


start_background_delivery_recovery = schedule_recovery_at_startup
