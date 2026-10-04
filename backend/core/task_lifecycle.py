"""Durable task lifecycle — Step 0/1 owner module (TASK_LIFECYCLE_SCHEMA v1).

A conversation UPDATES a persisted task instead of reconstructing it from
the transcript every turn. This module owns the three versioned schemas
(task revision, operation, delivery) and persists them through
GoalRunService rows — no second goal engine, no new framework.

Domain-independent by contract (04_CONTRACTS): entities, fields, and
values are opaque labels here. No business vocabulary lives in this file.

Storage (no migration): the task record rides
``GoalRun.parameters["task_lifecycle"]`` as
``{"task_revision": {...}, "operations": [...]}`` plus a
``conversation_id`` binding. Every revision and operation change is also
appended to the run's ``decision_log`` (append-only audit). Dicts are
always rebuilt before assignment — in-place mutation of JSON column
members is invisible to SQLAlchemy.
"""
from __future__ import annotations

import copy
import functools
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 1

# Same-process mutation lock (reentrant): every read-compute-persist
# sequence below holds it, so overlapping turns in one process cannot
# interleave a find-or-create or a revision bump into a lost update or
# a duplicate task. Cross-WORKER races need durable arbitration (row
# versioning or a workflow engine — explicitly Temporal territory in
# the work order's framework decision, not emulated here).
_MUTATION_LOCK = threading.RLock()


def _guarded(fn):
    """Hold the mutation lock for the whole read-compute-persist call."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _MUTATION_LOCK:
            return fn(*args, **kwargs)
    return wrapper


def _lock_dir() -> str:
    import tempfile

    return os.getenv("ATOM_TASK_LOCK_DIR") or os.path.join(
        tempfile.gettempdir(), "atom-task-locks")


@contextmanager
def _creation_guard(timeout_seconds: float = 30.0):
    """Cross-process mutual exclusion for find-or-create sequences.

    The version-counter CAS protects mutations of an EXISTING task, but
    creation itself (find → absent → create) can race across processes
    into duplicate tasks. This file lock serializes exactly that window.
    Platforms without ``fcntl`` fall back to no locking (documented,
    same-process safety still holds via ``_MUTATION_LOCK``). Always
    acquired INSIDE ``_MUTATION_LOCK`` (helpers are ``@_guarded``) so
    lock ordering is consistent everywhere.
    """
    try:
        import fcntl
    except ImportError:
        yield
        return
    os.makedirs(_lock_dir(), exist_ok=True)
    path = os.path.join(_lock_dir(), "creation.lock")
    with open(path, "a+b") as handle:
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        while True:
            try:
                fcntl.flock(handle.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TaskLifecycleConcurrencyError(
                        "task creation lock timeout")
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass

TRANSITION_KINDS = (
    "revise_fields",
    "change_presentation",
    "research_and_present",
    "revise_objective",
    "authorize_execute",
    "attach_evidence",
    "record_unresolved",
    "cancel",
)

# ---------------------------------------------------------------------------
# Job-work ledger (2026-10-04 reviewer assignment). Two records the reply
# leg may NOT invent, because the 2026-10-04 starvation incident showed a
# model narrating "unverifiable" about a lookup that never dispatched:
#
# - EXECUTION FACTS: what the execution path observed about a planned
#   lookup — invoked (did it run at all), outcome, served basis, failure
#   stage. Two-dimensional by design: a successful saved-copy read is
#   not a failed refresh, and a lookup that never dispatched is not a
#   lookup that ran and missed.
# - UNRESOLVED QUESTIONS: the durable open-work set. An entry names the
#   item, the question, the evidence behind it, the next action OR the
#   decision owner, and its status. Resolved entries stop resurfacing.
#
# Item MATCH status (single/multiple/none) is a different dimension from
# every one of these and never substitutes for them: a found item can
# still carry an open freshness question, and a saved-copy read settles
# nothing about the live source.
# ---------------------------------------------------------------------------

#: Did the planned lookup run, and what came back. ``not_dispatched`` is
#: distinct from ``read_failed``: starvation (empty planner pool, declined
#: dispatch) and dispatch-then-failure are different facts with different
#: recoveries — the incident class this vocabulary exists to separate.
EXEC_OUTCOMES = (
    "read_succeeded",   # file read dispatched and returned content
    "read_failed",      # dispatched; no content came back
    "not_dispatched",   # never ran (pool starved / planner declined)
    "search_succeeded", # non-file lookup (mailbox, store) returned hits
    "search_failed",    # non-file lookup ran and failed
)

#: Which basis served a SUCCESSFUL read — independent of outcome, because
#: the reviewer's correction is exactly that these must not collapse:
#: "read_succeeded on the saved copy" and "refresh_failed" are both true
#: on the same turn, and only the pair tells the truth.
EXEC_SERVED_BASES = ("saved_copy", "refreshed", "live", "none")

#: Open-question kinds. ``business_decision`` is settleable only by the
#: owner (which row is the right one; whether an offer applies) — it is
#: SURFACED, never auto-executed. ``verification`` and
#: ``missing_evidence`` carry agent-runnable next actions and may be
#: selected for continuation within the attempt budget.
UNRESOLVED_KINDS = ("business_decision", "verification", "missing_evidence")
UNRESOLVED_STATUSES = ("open", "resolved")

#: How many times continuation may act on one open question before it is
#: reported as exhausted instead of retried (bounded attempts: an open
#: question must not become an infinite retry loop).
UNRESOLVED_ATTEMPT_CAP = 3

OPERATION_TYPES = (
    "retrieve",
    "edit",
    "outbound",
    "present",
    "stop",
)

OPERATION_STATUSES = (
    "pending", "running", "waiting", "awaiting_approval", "applied",
    "failed", "cancelled", "superseded", "conflict", "rejected",
    "uncertain",
)
# ``uncertain`` is the honest terminal state for an operation whose worker
# was CONFIRMED lost: the effect may or may not have happened, and the
# system does not know which. It deliberately has no path back to
# ``pending`` — a retry must be a new operation reconciled against
# evidence, because silently re-running an edit whose mutation may
# already have landed is exactly the duplicate this whole mechanism
# exists to prevent.
OPERATION_TRANSITIONS: Dict[str, set] = {
    "pending": {"running", "cancelled", "superseded"},
    "running": {"waiting", "awaiting_approval", "applied", "conflict",
                "failed", "cancelled", "superseded", "uncertain"},
    "uncertain": {"applied", "failed", "cancelled", "superseded",
                  "conflict", "rejected"},
    "waiting": {"running", "failed", "cancelled", "superseded"},
    "awaiting_approval": {"applied", "rejected", "cancelled", "superseded"},
    "rejected": {"cancelled", "superseded"},
    "applied": set(),
    "conflict": set(),
    "failed": set(),
    "cancelled": set(),
    "superseded": set(),
}

_PRESENTATION_STYLES = ("default", "compact", "table")

_LIFECYCLE_KEY = "task_lifecycle"


class TaskLifecycleError(ValueError):
    """Raised on unknown transitions or illegal operation status changes."""


class TaskLifecycleConcurrencyError(TaskLifecycleError):
    """A concurrent writer changed the task between read and write and
    retries were exhausted. The caller must re-read and decide again —
    never silently overwrite."""


_CAS_RETRIES = 5


def _contract_version() -> int:
    try:
        from core.task_outcome_contract import CONTRACT_VERSION
        return int(CONTRACT_VERSION)
    except Exception:
        return 0


def _bounded_text(value: Any, limit: int) -> str:
    return str(value or "")[:limit]


def new_task_revision(
    *,
    objective_text: str,
    entities: Optional[List[Dict[str, Any]]] = None,
    requested_fields: Optional[List[str]] = None,
    source_requirements: Optional[Dict[str, Any]] = None,
    output_preferences: Optional[Dict[str, Any]] = None,
    authorized_actions: Optional[List[str]] = None,
    completion_criteria: Optional[List[Dict[str, Any]]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create revision 1 of a task. Never fabricates: empty objective text
    is rejected rather than defaulted."""
    if not str(objective_text or "").strip():
        raise TaskLifecycleError("objective_text is required")
    style = (output_preferences or {}).get("style") or "default"
    if style not in _PRESENTATION_STYLES:
        style = "default"
    return {
        "schema_version": SCHEMA_VERSION,
        "objective_id": str(uuid.uuid4()),
        "revision": 1,
        "supersedes_revision": None,
        "goal_text": _bounded_text(objective_text, 4000),
        "entities": [dict(e) for e in (entities or [])],
        "requested_fields": list(requested_fields or []),
        "source_requirements": copy.deepcopy(source_requirements or {}),
        "output_preferences": {
            "style": style,
            "field": (output_preferences or {}).get("field"),
        },
        "authorized_actions": list(authorized_actions or []),
        "completion_criteria": copy.deepcopy(completion_criteria or []),
        "clarifications": [],
        "unresolved": [],
        "evidence": [],
        "new_attempt_required": False,
        "provenance": copy.deepcopy(provenance or {}),
    }


def apply_transition(
    task: Dict[str, Any],
    transition: Dict[str, Any],
    operations: Optional[List[Dict[str, Any]]] = None,
) -> tuple:
    """Apply one structured transition; returns ``(new_task, operations)``.

    The transition is explicit structured input (kind + payload) resolved
    upstream — this function interprets no free text. Inputs are never
    mutated; the new revision carries ``supersedes_revision`` lineage.
    """
    if not isinstance(task, dict) or not isinstance(transition, dict):
        raise TaskLifecycleError("task and transition must be dicts")
    kind = transition.get("kind")
    if kind not in TRANSITION_KINDS:
        raise TaskLifecycleError(f"unknown transition kind '{kind}'")
    new_task = copy.deepcopy(task)
    new_task["revision"] = int(task.get("revision") or 0) + 1
    new_task["supersedes_revision"] = task.get("revision")
    ops = [copy.deepcopy(o) for o in (operations or [])]

    if kind == "revise_fields":
        fields = transition.get("requested_fields")
        if fields is not None:
            new_task["requested_fields"] = list(fields)
        # Evidence is retained; the next read re-selects from it.
        new_task["new_attempt_required"] = False
    elif kind == "change_presentation":
        prefs = transition.get("output_preferences") or {}
        style = prefs.get("style") or "default"
        new_task["output_preferences"] = {
            "style": style if style in _PRESENTATION_STYLES else "default",
            "field": prefs.get("field"),
        }
        new_task["new_attempt_required"] = False
    elif kind == "research_and_present":
        prefs = transition.get("output_preferences") or {}
        style = prefs.get("style") or "default"
        new_task["output_preferences"] = {
            "style": style if style in _PRESENTATION_STYLES else "default",
            "field": prefs.get("field"),
        }
        new_task["new_attempt_required"] = True
    elif kind == "revise_objective":
        removed = set(transition.get("removed_entity_ids") or [])
        if "entities" in transition:
            new_task["entities"] = [dict(e) for e in transition["entities"]]
        if "requested_fields" in transition:
            new_task["requested_fields"] = list(
                transition["requested_fields"] or [])
        # Invalidate evidence bound to removed entities; the rest is reused.
        live_ids = {str(e.get("id")) for e in new_task["entities"]}
        invalidated = []
        kept = []
        for ev in new_task.get("evidence") or []:
            bound = {str(i) for i in (ev.get("entity_ids") or [])}
            if bound & removed or (bound and not (bound & live_ids)):
                invalidated.append(ev.get("evidence_id"))
            else:
                kept.append(ev)
        new_task["evidence"] = kept
        new_task["invalidated_evidence_ids"] = invalidated
        new_task["new_attempt_required"] = bool(invalidated)
    elif kind == "authorize_execute":
        if transition.get("authorized_actions") is not None:
            new_task["authorized_actions"] = list(
                transition["authorized_actions"] or [])
        new_task["authorization"] = transition.get("approval") or "authorized"
        if transition.get("provenance") is not None:
            new_task["provenance"] = copy.deepcopy(
                transition["provenance"])
        new_task["new_attempt_required"] = False
    elif kind == "attach_evidence":
        # Evidence arrival is a task change: the new revision carries the
        # accumulated evidence list. Later revise_objective transitions
        # invalidate against exactly this list.
        evidence = transition.get("evidence") or {}
        if evidence.get("evidence_id"):
            new_task["evidence"] = list(new_task.get("evidence") or []) + [
                copy.deepcopy(evidence)]
        new_task["new_attempt_required"] = False
    elif kind == "record_unresolved":
        # JOB-WORK LEDGER: questions are appended (validated, never
        # guessed); resolutions and attempt increments settle OPEN
        # entries in place — a resolved question keeps its text for
        # audit but never resurfaces in the open set again.
        existing = list(new_task.get("unresolved") or [])
        fresh_questions = []
        for q in (transition.get("questions") or []):
            if isinstance(q, dict):
                fresh_questions.append(_normalize_question(
                    q, operation=transition.get("source_operation")))
        if fresh_questions:
            existing = existing + fresh_questions
        for r in (transition.get("resolutions") or []):
            if not isinstance(r, dict):
                continue
            resolution = _bounded_text(r.get("resolution"), 400)
            if not resolution:
                continue
            for index, entry in enumerate(existing):
                if (entry.get("status") == "open"
                        and entry.get("question_id") == r.get(
                            "question_id")):
                    settled = dict(entry)
                    settled.update({
                        "status": "resolved",
                        "resolved_at": _utc_now_iso(),
                        "resolution": resolution,
                    })
                    existing[index] = settled
        for bump in (transition.get("attempts") or []):
            if not isinstance(bump, dict):
                continue
            for index, entry in enumerate(existing):
                if (entry.get("status") == "open"
                        and entry.get("question_id") == bump.get(
                            "question_id")):
                    counted = dict(entry)
                    counted["attempts"] = int(
                        entry.get("attempts") or 0) + max(
                        1, int(bump.get("increment") or 1))
                    existing[index] = counted
        new_task["unresolved"] = existing
        new_task["new_attempt_required"] = bool(fresh_questions)
    elif kind == "cancel":
        new_task["authorization"] = "cancelled"
        for op in ops:
            if op.get("status") not in ("applied", "failed", "cancelled",
                                        "superseded", "conflict", "rejected"):
                op["status"] = "cancelled"
        new_task["new_attempt_required"] = False
    new_task["last_transition"] = {
        "kind": kind,
        "requested_change": _bounded_text(
            transition.get("requested_change"), 500),
    }
    return new_task, ops


def new_operation(
    *,
    task: Dict[str, Any],
    op_type: str,
    requested_change: str,
    idempotency_key: Optional[str] = None,
    parent_operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create one operation bound to a task revision. Retries are new
    operations linked by ``parent_operation_id`` — completed operations
    are never mutated. Mutations (``outbound``) require an idempotency
    key; it is generated when the caller does not supply one."""
    if op_type not in OPERATION_TYPES:
        raise TaskLifecycleError(f"unknown operation type '{op_type}'")
    if op_type == "outbound" and not idempotency_key:
        idempotency_key = str(uuid.uuid4())
    return {
        "schema_version": SCHEMA_VERSION,
        "operation_id": str(uuid.uuid4()),
        "objective_id": task.get("objective_id"),
        "objective_revision": task.get("revision"),
        "execution_id": None,
        "operation_type": op_type,
        "requested_change": _bounded_text(requested_change, 500),
        "idempotency_key": idempotency_key,
        "parent_operation_id": parent_operation_id,
        "evidence_revision": None,
        "status": "pending",
        "authorization": "authorized" if op_type != "outbound"
        else "pending_approval",
    }


def transition_operation(
    operation: Dict[str, Any],
    to_status: str,
    *,
    evidence_revision: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move one operation to a new status through the guarded table."""
    to_status = (to_status or "").strip()
    if to_status not in OPERATION_STATUSES:
        raise TaskLifecycleError(f"unknown operation status '{to_status}'")
    current = operation.get("status")
    if to_status not in OPERATION_TRANSITIONS.get(current, set()):
        raise TaskLifecycleError(
            f"illegal operation transition {current} -> {to_status}")
    updated = copy.deepcopy(operation)
    updated["status"] = to_status
    if evidence_revision is not None:
        updated["evidence_revision"] = evidence_revision
    if execution_id is not None:
        updated["execution_id"] = execution_id
    return updated


def new_delivery(
    *,
    execution_id: str,
    operation_ids: List[str],
    message_id: str,
    content_sha256: str,
    finalization_version: str,
    evidence_refs: Optional[List[str]] = None,
    status: str = "persisted_for_delivery",
) -> Dict[str, Any]:
    """Build one delivery record binding execution, operations, the exact
    message row, and the content hash.

    ``status`` distinguishes what the SERVER can prove from what it
    cannot. "persisted_for_delivery" is the only state the server asserts
    on its own authority: the bytes were written and are available.
    "receipt_acknowledged" requires an out-of-band acknowledgement from
    the client, because a server cannot prove a response was received —
    a 200 proves only that the request was handled. "superseded" marks a
    delivery a later re-finalization replaced.
    """
    if not execution_id or not message_id or not content_sha256:
        raise TaskLifecycleError(
            "execution_id, message_id, and content_sha256 are required")
    if status not in DELIVERY_STATUSES:
        raise TaskLifecycleError(f"unknown delivery status '{status}'")
    if status == "receipt_acknowledged":
        # A delivery cannot be born acknowledged: acknowledgement is an
        # event that happens after the bytes are written, and only
        # acknowledge_receipt() may record it, with evidence.
        raise TaskLifecycleError(
            "a delivery is created persisted_for_delivery; receipt "
            "acknowledgement is a later, evidenced event")
    return {
        "schema_version": SCHEMA_VERSION,
        "delivery_id": str(uuid.uuid4()),
        "execution_id": execution_id,
        "operation_ids": list(operation_ids or []),
        "message_id": message_id,
        "content_sha256": content_sha256,
        "finalization_version": finalization_version,
        "evidence_refs": list(evidence_refs or []),
        "status": status,
        "receipt_confirmed": False,
    }


def _operation_payload_hash(*, op_type: str, requested_change: str,
                            parent_operation_id: Optional[str]) -> str:
    """Canonical hash of what an operation MEANS.

    Bound to the idempotency key so a key can never be reused for a
    different effect. Canonical by construction: the three fields that
    define the operation's identity, length-prefixed so no combination
    of values can produce the same digest as a different combination.
    """
    import hashlib as _hashlib

    parts = [str(op_type or ""), str(requested_change or ""),
             str(parent_operation_id or "")]
    blob = "".join(f"{len(part)}:{part}\x1f" for part in parts)
    return _hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_task_revision(task: Dict[str, Any]) -> None:
    for key in ("objective_id", "revision", "goal_text"):
        if task.get(key) in (None, ""):
            raise TaskLifecycleError(f"task_revision missing '{key}'")
    if task.get("schema_version") != SCHEMA_VERSION:
        raise TaskLifecycleError("task_revision schema_version mismatch")


def _question_key(question: Dict[str, Any]) -> Tuple[str, str]:
    """Identity of a question for dedupe: (normalized item, normalized
    text). Item-scoped and job-scoped questions about the same subject
    stay distinct; the same question re-derived by a later read is the
    SAME question, not a new one."""
    item = re.sub(r"\s+", " ", str(question.get("item") or
                                   "").strip().lower())
    text = re.sub(r"\s+", " ", str(question.get("question") or
                                   "").strip().lower())
    return (item, text)


def _normalize_question(question: Dict[str, Any],
                        *, operation: Any = None) -> Dict[str, Any]:
    """Validate and bound one unresolved-question entry. Never guesses:
    an unknown kind or empty question text is rejected, an executable
    kind without a next action is rejected (persisting a question the
    system cannot act on or surface is noise, not state), and a business
    decision always names the owner as its settler."""
    kind = str(question.get("kind") or "")
    if kind not in UNRESOLVED_KINDS:
        raise TaskLifecycleError(f"unknown unresolved kind '{kind}'")
    text = _bounded_text(question.get("question"), 400)
    if not text.strip():
        raise TaskLifecycleError("an unresolved question requires text")
    next_action = _bounded_text(question.get("next_action"), 400)
    if kind in ("verification", "missing_evidence") and not next_action.strip():
        raise TaskLifecycleError(
            f"a {kind} question requires the next action to run")
    attempts = question.get("attempts")
    try:
        attempts = max(0, int(attempts)) if attempts is not None else 0
    except (TypeError, ValueError):
        attempts = 0
    return {
        "question_id": str(question.get("question_id") or uuid.uuid4()),
        "item": _bounded_text(question.get("item"), 80),
        "question": text,
        "kind": kind,
        "evidence": _bounded_text(question.get("evidence"), 500),
        "next_action": next_action.strip() or None,
        "decision_owner": ("owner" if kind == "business_decision" else None),
        "status": "open",
        "attempts": attempts,
        "opened_at": _utc_now_iso(),
        "resolved_at": None,
        "resolution": None,
        "source_operation": (
            str(operation)[:64] if operation else None),
    }


def normalize_execution_facts(raw: Any) -> Dict[str, Any]:
    """Clamp caller-supplied execution facts to the closed vocabulary.

    The record may only state what the execution path observed. An
    unknown outcome falls back along the ONE fact that is known —
    whether the lookup was invoked — and the caller's raw wording is
    kept in ``raw_outcome`` so nothing is silently rewritten."""
    raw = raw if isinstance(raw, dict) else {}
    invoked = bool(raw.get("invoked"))
    outcome = str(raw.get("outcome") or "")
    raw_outcome = outcome or None
    if outcome not in EXEC_OUTCOMES:
        outcome = "read_succeeded" if (invoked and outcome == "") else (
            "not_dispatched" if not invoked else "read_failed")
    basis = str(raw.get("served_basis") or "")
    if basis not in EXEC_SERVED_BASES:
        basis = "none"
    items_raw = raw.get("items")
    items = {str(k): str(v) for k, v in (items_raw or {}).items()
             if str(k).strip()} if isinstance(items_raw, dict) else {}
    stage = raw.get("failure_stage")
    freshness = raw.get("freshness_status")
    # PLANNING PROVENANCE passthrough (2026-10-04 reviewer correction 2):
    # how the plan came to be — a failure the fallback machinery recovered
    # (repair pass, deterministic rung) is ATTEMPT HISTORY on a successful
    # outcome, never a license to record not_dispatched.
    planning_raw = raw.get("planning")
    planning = None
    if isinstance(planning_raw, dict):
        planning = {
            "source": str(planning_raw.get("source") or "")[:60] or None,
            "recovered": bool(planning_raw.get("recovered")),
        }
    return {
        "invoked": invoked,
        "outcome": outcome,
        "served_basis": basis,
        "failure_stage": str(stage)[:80] if stage else None,
        "freshness_status": str(freshness)[:40] if freshness else None,
        "items": items,
        "planning": planning,
        "raw_outcome": raw_outcome,
        "at": _utc_now_iso(),
    }


def validate_operation(operation: Dict[str, Any]) -> None:
    for key in ("operation_id", "objective_id", "operation_type", "status"):
        if operation.get(key) in (None, ""):
            raise TaskLifecycleError(f"operation missing '{key}'")
    if operation.get("schema_version") != SCHEMA_VERSION:
        raise TaskLifecycleError("operation schema_version mismatch")


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _current_worker_fingerprint() -> str:
    """Identify the process that is claiming an operation.

    Used only to tell a CONFIRMED-lost owner from a live one. It is
    deliberately cheap and dependency-free: it always returns something
    identifiable, and a caller that cannot establish that the recorded
    owner is gone must treat the loss as UNCONFIRMED rather than
    guessing.
    """
    try:
        from core.runtime_identity import get_runtime_identity

        identity = get_runtime_identity()
        as_dict = getattr(identity, "as_dict", None)
        if callable(as_dict):
            data = as_dict()
            for key in ("instance_id", "instance", "host_pid", "pid"):
                if data.get(key):
                    return f"{key}:{data[key]}"
    except Exception:
        pass
    import os

    return f"pid:{os.getpid()}"


# Verdicts a caller may reach after inspecting durable evidence. The
# lifecycle never infers an outcome: it records what the caller could
# actually observe.
RECONCILIATION_VERDICTS = ("applied", "not_applied", "insufficient")


class TaskLifecycle:
    """GoalRun-backed persistence for the task record.

    The task revision and operation list live in
    ``GoalRun.parameters["task_lifecycle"]``; every change also appends a
    ``decision_log`` entry (``task_created`` / ``task_revision`` /
    ``operation`` / ``delivery``). One owner, one write path.
    """

    def __init__(self, run_service, goal_service=None):
        import threading
        self.runs = run_service
        self.goals = goal_service
        self._lock = threading.Lock()

    # ------------------------------------------------------------ creation

    @_guarded
    def create_task(
        self,
        conversation_id: str,
        objective_text: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create the objective, the run, and revision 1; bind the
        conversation. Returns ``{"run_id", "task_revision"}``."""
        if not str(conversation_id or "").strip():
            raise TaskLifecycleError("conversation_id is required")
        revision = new_task_revision(objective_text=objective_text, **kwargs)
        goal_id = self._ensure_goal(objective_text, kwargs)
        run = self.runs.create_run(
            goal_id,
            plan=[],
            parameters={
                "task_lifecycle": {
                    "task_version": 1,
                    "task_revision": revision,
                    "operations": [],
                    "conversation_id": conversation_id,
                }
            },
        )
        run_id = run["id"]
        self.runs.transition(run_id, "active")
        self.runs.append_decision(run_id, {
            "kind": "task_created",
            "rationale": _bounded_text(objective_text, 500),
            "revision": 1,
        })
        return {"run_id": run_id, "task_revision": revision}

    def _ensure_goal(self, objective_text: str,
                     kwargs: Dict[str, Any]) -> str:
        if self.goals is None:
            raise TaskLifecycleError(
                "goal_service is required to create the objective")
        goal = self.goals.create_goal(
            title=_bounded_text(objective_text, 500),
            description="",
            criteria=list(kwargs.get("completion_criteria") or []),
            source="chat",
        )
        return goal["id"]

    # -------------------------------------------------------------- lookup

    def get_task(self, run_id: str) -> Optional[Dict[str, Any]]:
        """The current task record for a run, or None."""
        run = self.runs.get_run(run_id)
        if not run:
            return None
        lifecycle = (run.get("parameters") or {}).get(_LIFECYCLE_KEY) or {}
        revision = lifecycle.get("task_revision")
        if not revision:
            return None
        return {
            "run_id": run_id,
            "task_revision": revision,
            "operations": list(lifecycle.get("operations") or []),
            "deliveries": list(lifecycle.get("deliveries") or []),
            "conversation_id": lifecycle.get("conversation_id"),
            "run_status": run.get("status"),
            "task_version": lifecycle.get("task_version") or 1,
        }

    def find_active_task(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Latest non-terminal run bound to a conversation, or None."""
        runs = self.runs.list_runs(include_terminal=False, limit=200)
        candidates = [
            r for r in runs
            if ((r.get("parameters") or {}).get(_LIFECYCLE_KEY) or {}).get(
                "conversation_id") == conversation_id
        ]
        if not candidates:
            return None
        return self.get_task(candidates[0]["id"])

    def find_active_task_for_canvas(
        self, canvas_id: str,
    ) -> Optional[Dict[str, Any]]:
        """The newest non-terminal task whose provenance binds this canvas.

        Cross-session continuation resolves THROUGH the canvas identity
        (2026-10-04 reviewer correction): a fresh session on the owner's
        quotation fork resumes that job — never 'the user's latest
        conversation', which can be an entirely different quotation. A
        task without a canvas binding never matches here."""
        canvas = str(canvas_id or "").strip()
        if not canvas:
            return None
        runs = self.runs.list_runs(include_terminal=False, limit=200)
        for run in runs:
            record = self.get_task(run["id"])
            if record is None:
                continue
            provenance = (record.get("task_revision") or {}).get(
                "provenance") or {}
            if str(provenance.get("canvas_id") or "") == canvas:
                return record
        return None

    # ------------------------------------------------- atomic mutation
    # Every state change below goes through _mutate: read the fresh
    # record, compute the new lifecycle purely, then apply it with a
    # single conditional UPDATE guarded on the version counter. A lost
    # race retries on fresh state; exhaustion raises instead of
    # silently overwriting. Same-process reentrancy stays safe via
    # the reentrant _MUTATION_LOCK held by @_guarded.

    def _mutate(self, run_id: str, compute, retries: int = _CAS_RETRIES):
        """Run compute(record) -> (result, new_lifecycle, decision) and
        commit it iff the version is unchanged. A None lifecycle means
        'nothing to write' (idempotent replay): return the result."""
        last_conflict = None
        for _ in range(max(1, retries)):
            record = self.get_task(run_id)
            if record is None:
                raise TaskLifecycleError(
                    f"no task record on run {run_id}")
            result, new_lifecycle, decision = compute(record)
            if new_lifecycle is None:
                return result
            expected = record.get("task_version") or 1
            lifecycle = dict(new_lifecycle)
            lifecycle["task_version"] = int(expected) + 1
            # Deliveries are an append-only ledger beside the revision and
            # operations; a transition rebuilds those two from `record`, so
            # carry the ledger forward here at the single choke point
            # rather than in every mutation site.
            lifecycle.setdefault("deliveries",
                                 list(record.get("deliveries") or []))
            if self._cas_write(run_id, int(expected), lifecycle, decision):
                return result
            last_conflict = TaskLifecycleConcurrencyError(
                f"concurrent modification of task on run {run_id} "
                f"(expected version {expected})")
        raise last_conflict

    def _cas_write(self, run_id: str, expected_version: int,
                   lifecycle: Dict[str, Any],
                   decision: Optional[Dict[str, Any]]) -> bool:
        """Single conditional UPDATE of parameters + decision log.
        Returns True iff exactly one row matched (version unchanged)."""
        from datetime import datetime, timezone

        from sqlalchemy import or_

        from core.models import GoalRun

        factory = None
        try:
            factory = self.runs._sessions()
        except Exception:
            factory = None
        if factory is None:
            from core.database import get_db_session as factory
        workspace_id = getattr(self.runs, "workspace_id", None)
        with factory() as session:
            row = session.query(GoalRun).filter(
                GoalRun.id == run_id).first()
            if row is None:
                return False
            log = list(row.decision_log or [])
            entry = {"ts": datetime.now(timezone.utc).isoformat()}
            entry.update(decision or {})
            log.append(entry)
            params = dict(row.parameters or {})
            params[_LIFECYCLE_KEY] = lifecycle
            version_col = (
                GoalRun.parameters[_LIFECYCLE_KEY][
                    "task_version"].as_integer()
            )
            conditions = [version_col == int(expected_version)]
            if int(expected_version) == 1:
                # Rows predating the counter read as version 1.
                conditions.append(version_col.is_(None))
            filters = [GoalRun.id == run_id, or_(*conditions)]
            if workspace_id:
                filters.append(GoalRun.workspace_id == workspace_id)
            updated = session.query(GoalRun).filter(*filters).update(
                {"parameters": params, "decision_log": log},
                synchronize_session=False)
            session.commit()
            return updated == 1

    # ----------------------------------------------------------- transitions

    @_guarded
    def apply_transition(
        self,
        run_id: str,
        transition: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persist a task revision; returns the new revision."""
        def compute(record):
            new_revision, updated_ops = apply_transition(
                record["task_revision"], transition, record["operations"])
            validate_task_revision(new_revision)
            # Rebuild (never in-place mutate JSON column members).
            lifecycle = {
                "task_revision": new_revision,
                "operations": updated_ops,
                "conversation_id": record.get("conversation_id"),
            }
            decision = {
                "kind": "task_revision",
                "rationale": _bounded_text(
                    transition.get("requested_change"), 500),
                "revision": new_revision["revision"],
                "transition": transition.get("kind"),
            }
            return new_revision, lifecycle, decision

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def _claim_operation_key(
        self,
        run_id: str,
        idempotency_key: str,
        payload_sha256: str,
        operation_id: str,
        operation_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Transactionally claim (workspace, run, idempotency_key).

        Returns None when this caller won the claim. When another
        process already holds the key, returns that holder's row so the
        caller can replay the same payload or reject a conflicting one.

        This is the cross-process arbiter: the task JSON alone cannot
        make two racing reservations of one key collapse to one effect,
        because both workers read "absent" before either writes. The
        database constraint is what actually decides.
        """
        from sqlalchemy.exc import IntegrityError

        from core.models import TaskOperationRecord

        factory = None
        try:
            factory = self.runs._sessions()
        except Exception:
            factory = None
        if factory is None:
            from core.database import get_db_session as factory
        workspace_id = getattr(self.runs, "workspace_id", None) or "default"
        tenant_id = getattr(self.runs, "tenant_id", None)
        with factory() as session:
            try:
                session.add(TaskOperationRecord(
                    workspace_id=workspace_id, tenant_id=tenant_id,
                    run_id=run_id, idempotency_key=idempotency_key,
                    payload_sha256=payload_sha256,
                    operation_id=operation_id,
                    operation_type=operation_type, status="pending"))
                session.commit()
                return None
            except IntegrityError:
                session.rollback()
            except Exception:
                session.rollback()
                raise
            existing = (
                session.query(TaskOperationRecord)
                .filter(
                    TaskOperationRecord.workspace_id == workspace_id,
                    TaskOperationRecord.run_id == run_id,
                    TaskOperationRecord.idempotency_key == idempotency_key,
                ).first())
            if existing is None:
                return None
            return {
                "operation_id": existing.operation_id,
                "operation_type": existing.operation_type,
                "idempotency_key": existing.idempotency_key,
                "payload_sha256": existing.payload_sha256,
                "status": existing.status,
            }

    def _adopt_claimed_operation(
        self,
        run_id: str,
        claim: Dict[str, Any],
        op_type: str,
        requested_change: str,
        parent_operation_id: Optional[str],
    ) -> Dict[str, Any]:
        """Materialize an operation whose key another process claimed.

        Normally the winner's operation is already in the task JSON and
        this simply returns it. The exception is a winner that crashed
        between claiming the key and writing the JSON: the claim is
        durable, so the operation is written NOW under the claimed id
        rather than minting a second one. A key that is claimed but has
        no operation must never become a new effect.
        """
        def compute(record):
            ops = list(record["operations"])
            for existing in ops:
                if existing.get("operation_id") == claim["operation_id"]:
                    return copy.deepcopy(existing), None, None
            operation = new_operation(
                task=record["task_revision"], op_type=op_type,
                requested_change=requested_change,
                idempotency_key=claim.get("idempotency_key"),
                parent_operation_id=parent_operation_id)
            operation["operation_id"] = claim["operation_id"]
            validate_operation(operation)
            lifecycle = {
                "task_revision": record["task_revision"],
                "operations": ops + [operation],
                "conversation_id": record.get("conversation_id"),
            }
            decision = {
                "kind": "operation",
                "rationale": _bounded_text(requested_change, 500),
                "operation_id": operation["operation_id"],
                "operation_type": op_type,
            }
            return operation, lifecycle, decision

        with self._lock:
            return self._mutate(run_id, compute)

    def create_operation(
        self,
        run_id: str,
        *,
        op_type: str,
        requested_change: str,
        idempotency_key: Optional[str] = None,
        parent_operation_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist one new operation on the task's current revision.

        ``extra`` carries caller-known provenance (e.g. an edit's
        invalidated evidence ids). It may only ADD keys — core identity
        and status fields are never overridden through it.

        Idempotency: when ``idempotency_key`` matches an existing
        operation on this task, the existing record is returned and NO
        duplicate is created — the same key replays the same operation
        (Stripe-style). The SAME key with a DIFFERENT payload (type or
        requested change) is a conflict and is rejected, never merged.
        Callers mint one key per intended external effect and reuse it
        only for retries of that same effect.

        The key is bound to a canonical payload hash and claimed in a
        TABLE with a uniqueness constraint, so two processes racing the
        same key produce one operation and one effect — the loser replays
        the winner's operation instead of creating a second one.
        """
        payload_sha256 = _operation_payload_hash(
            op_type=op_type, requested_change=requested_change,
            parent_operation_id=parent_operation_id)
        # Mint the operation's identity ONCE, before the claim, so the
        # claim row and the task JSON can never disagree about which
        # operation this key names.
        operation_id = str(uuid.uuid4())
        if idempotency_key:
            # Cheap in-memory replay first. Claiming a key we are about to
            # replay would leave a claim row pointing at an operation id
            # that never lands, which later looks like a missing winner.
            existing_record = self.get_task(run_id) or {}
            for existing in existing_record.get("operations") or []:
                if existing.get("idempotency_key") != idempotency_key:
                    continue
                if (existing.get("operation_type") != op_type
                        or existing.get("requested_change")
                        != requested_change):
                    raise TaskLifecycleError(
                        f"idempotency key {idempotency_key!r} already used "
                        f"for a different operation payload")
                return copy.deepcopy(existing)
            claim = self._claim_operation_key(
                run_id, idempotency_key, payload_sha256,
                operation_id, op_type)
            if claim is not None:
                if claim["payload_sha256"] != payload_sha256:
                    raise TaskLifecycleError(
                        f"idempotency key {idempotency_key!r} is already "
                        f"bound to a different operation payload")
                # Another process won this key: adopt its operation
                # rather than racing a second one into existence.
                for existing in (self.get_task(run_id) or {}).get(
                        "operations") or []:
                    if existing.get("operation_id") == claim[
                            "operation_id"]:
                        return copy.deepcopy(existing)
                return self._adopt_claimed_operation(
                    run_id, claim, op_type, requested_change,
                    parent_operation_id)

        def compute(record):
            ops = list(record["operations"])
            if idempotency_key:
                for existing in ops:
                    if existing.get("idempotency_key") == idempotency_key:
                        if (existing.get("operation_type") != op_type
                                or existing.get("requested_change")
                                != requested_change):
                            raise TaskLifecycleError(
                                f"idempotency key {idempotency_key!r} "
                                f"already used for a different operation "
                                f"payload")
                        return copy.deepcopy(existing), None, None
            operation = new_operation(
                task=record["task_revision"], op_type=op_type,
                requested_change=requested_change,
                idempotency_key=idempotency_key,
                parent_operation_id=parent_operation_id,
            )
            operation["operation_id"] = operation_id
            if extra:
                for key, value in extra.items():
                    if key not in operation:
                        operation[key] = copy.deepcopy(value)
            validate_operation(operation)
            updated_ops = ops + [operation]
            lifecycle = {
                "task_revision": record["task_revision"],
                "operations": updated_ops,
                "conversation_id": record.get("conversation_id"),
            }
            decision = {
                "kind": "operation",
                "rationale": _bounded_text(requested_change, 500),
                "operation_id": operation["operation_id"],
                "operation_type": op_type,
            }
            return operation, lifecycle, decision

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def attach_operation_field(
        self,
        run_id: str,
        operation_id: str,
        key: str,
        value: Any,
    ) -> Dict[str, Any]:
        """Add caller-known provenance to an existing operation record.

        Used when a fact is only known after execution (a canvas
        correction's invalidated evidence ids). Core identity and status
        fields can never be set through it — same rule as
        ``create_operation``'s ``extra``.
        """
        reserved = ("operation_id", "objective_id", "operation_type",
                    "status", "authorization", "idempotency_key",
                    "schema_version", "execution_id", "objective_revision")
        if key in reserved:
            raise TaskLifecycleError(
                f"'{key}' is a core operation field and cannot be attached")

        def compute(record):
            ops = list(record["operations"])
            for index, op in enumerate(ops):
                if op.get("operation_id") == operation_id:
                    ops[index] = {**copy.deepcopy(op), key: copy.deepcopy(value)}
                    lifecycle = {
                        "task_revision": record["task_revision"],
                        "operations": ops,
                        "conversation_id": record.get("conversation_id"),
                    }
                    decision = {
                        "kind": "operation",
                        "rationale": f"attached {key}",
                        "operation_id": operation_id,
                        "operation_type": op.get("operation_type"),
                    }
                    return ops[index], lifecycle, decision
            raise TaskLifecycleError(f"operation {operation_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def record_delivery(
        self,
        run_id: str,
        *,
        execution_id: str,
        operation_ids: Optional[List[str]] = None,
        message_id: str,
        content_sha256: str,
        finalization_version: str = "",
        evidence_refs: Optional[List[str]] = None,
        status: str = "persisted_for_delivery",
    ) -> Dict[str, Any]:
        """Append one delivery record to the task's ledger.
        The final boundary: a delivery binds the exact message row and
        content hash that left the system, the operations and evidence it
        was built from, and the finalizer version that froze it. The
        ledger is append-only — re-delivering the same execution, row,
        and bytes is an idempotent replay, never a second record, so a
        retried turn cannot fork the history of what was sent. Re-finalizing
        the same row with DIFFERENT bytes is a distinct delivery: the
        ledger records what actually left, rather than pretending an
        earlier send covered it.
        """
        if not execution_id or not message_id or not content_sha256:
            raise TaskLifecycleError(
                "execution_id, message_id, and content_sha256 are required")

        def compute(record):
            existing = list(record.get("deliveries") or [])
            for delivery in existing:
                if (str(delivery.get("execution_id")) == str(execution_id)
                        and str(delivery.get("message_id")) == str(message_id)
                        and str(delivery.get("content_sha256"))
                        == str(content_sha256)):
                    # Same execution, same row, same bytes: replay.
                    return delivery, None, None
            delivery = new_delivery(
                execution_id=execution_id,
                operation_ids=list(operation_ids or []),
                message_id=message_id, content_sha256=content_sha256,
                finalization_version=finalization_version or "",
                evidence_refs=list(evidence_refs or []), status=status)
            lifecycle = {
                "task_revision": record["task_revision"],
                "operations": record["operations"],
                "deliveries": existing + [delivery],
                "conversation_id": record.get("conversation_id"),
            }
            decision = {
                "kind": "delivery",
                "rationale": f"delivered execution {execution_id} "
                             f"as message {message_id}",
                "delivery_id": delivery["delivery_id"],
                "execution_id": execution_id,
            }
            return delivery, lifecycle, decision

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def claim_execution(
        self,
        run_id: str,
        operation_id: str,
        execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Win the exclusive right to execute one operation.

        Reserving a record and performing its effect are DIFFERENT acts.
        Two processes can legitimately hold the same operation id — the
        idempotency key replayed — and if both then mutate, the record is
        singular while the effect is not. This claim is the arbiter: the
        operation moves pending→running exactly once, under the same
        version-CAS that orders every other mutation, so exactly one
        caller is told ``granted``.

        The claim records WHO holds it (an owner fingerprint) and WHEN.
        That is what later lets a recovery routine distinguish *confirmed*
        worker loss — this owner can no longer be the one running it — from
        a merely slow one, which is the difference between marking an
        operation uncertain and falsely accusing a live worker.

        Losers get ``granted: False`` plus the operation's actual state,
        and must wait for it or replay its result. A terminal operation
        reports ``already_complete`` rather than granting, so a retry
        after a finished effect never re-runs it.
        """
        owner = _current_worker_fingerprint()
        claimed_at = _utc_now_iso()

        def compute(record):
            ops = list(record["operations"])
            for index, op in enumerate(ops):
                if op.get("operation_id") != operation_id:
                    continue
                status = op.get("status")
                if status == "pending":
                    updated = transition_operation(
                        op, "running", execution_id=execution_id)
                    updated["claimed_by"] = owner
                    updated["claimed_at"] = claimed_at
                    ops[index] = updated
                    lifecycle = {
                        "task_revision": record["task_revision"],
                        "operations": ops,
                        "conversation_id": record.get("conversation_id"),
                    }
                    decision = {
                        "kind": "operation",
                        "rationale": "execution claimed",
                        "operation_id": operation_id,
                        "operation_type": op.get("operation_type"),
                    }
                    return {
                        "granted": True,
                        "operation": copy.deepcopy(updated),
                    }, lifecycle, decision
                # Someone else holds it, or it is already done.
                return {
                    "granted": False,
                    "status": status,
                    "already_complete": status in (
                        "applied", "failed", "awaiting_approval",
                        "superseded", "cancelled", "conflict", "rejected",
                        "uncertain"),
                    "claimed_by": op.get("claimed_by"),
                    "operation": copy.deepcopy(op),
                }, None, None
            raise TaskLifecycleError(f"operation {operation_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def mark_operation_uncertain(
        self,
        run_id: str,
        operation_id: str,
        *,
        lost_worker: str,
        confirmed: bool,
        evidence: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Expose an operation whose worker was lost as OUTCOME UNKNOWN.

        A confirmed-lost worker (``confirmed=True``) moves the operation
        to ``uncertain`` and it stays there until durable evidence
        reconciles it. A TIMEOUT is not confirmation: with ``confirmed``
        False this raises, because a slow worker may still be mid-mutation
        and calling its outcome unknown would either lie about a live
        effect or invite a duplicate.

        ``uncertain`` is deliberately one-way out of ``running`` and has no
        path back to ``pending``: re-running an edit whose write may have
        landed is the exact failure the execution claim prevents.
        """
        if not confirmed:
            raise TaskLifecycleError(
                "a timeout does not prove an outcome; worker loss must be "
                "CONFIRMED before an operation is marked uncertain")
        if not str(lost_worker or "").strip():
            raise TaskLifecycleError(
                "marking an operation uncertain must name the lost worker")

        def compute(record):
            ops = list(record["operations"])
            for index, op in enumerate(ops):
                if op.get("operation_id") != operation_id:
                    continue
                if op.get("status") == "uncertain":
                    return copy.deepcopy(op), None, None
                if op.get("status") != "running":
                    raise TaskLifecycleError(
                        f"operation {operation_id} is {op.get('status')}, "
                        f"not running; nothing to mark uncertain")
                updated = transition_operation(op, "uncertain")
                updated["outcome"] = "unknown"
                updated["needs_reconciliation"] = True
                updated["lost_worker"] = str(lost_worker)[:200]
                updated["uncertainty_evidence"] = _bounded_text(evidence, 500)
                ops[index] = updated
                lifecycle = {
                    "task_revision": record["task_revision"],
                    "operations": ops,
                    "conversation_id": record.get("conversation_id"),
                }
                decision = {
                    "kind": "operation",
                    "rationale": f"worker {lost_worker} confirmed lost; "
                                 f"outcome unknown",
                    "operation_id": operation_id,
                    "operation_type": op.get("operation_type"),
                }
                return updated, lifecycle, decision
            raise TaskLifecycleError(f"operation {operation_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)

    def recover_confirmed_worker_loss(
        self,
        run_id: str,
        *,
        is_worker_live,
    ) -> List[Dict[str, Any]]:
        """Expose operations stranded by CONFIRMED-lost workers.

        ``is_worker_live(fingerprint) -> bool`` is the caller's liveness
        probe: it must return False only when the worker is *known* gone
        (a different instance answering, a dead registration), never on a
        timeout. Anything inconclusive must answer True, which leaves the
        operation running and untouched.

        Only operations this process is not itself holding are considered,
        so a live worker can never mark its own in-flight work uncertain.
        """
        me = _current_worker_fingerprint()
        record = self.get_task(run_id)
        if record is None:
            return []
        stranded: List[Dict[str, Any]] = []
        for operation in list(record.get("operations") or []):
            if operation.get("status") != "running":
                continue
            owner = operation.get("claimed_by")
            if not owner:
                # A claim with no owner predates owner stamping; treat it
                # as un-attributable rather than guessing.
                continue
            if owner == me:
                continue
            try:
                live = bool(is_worker_live(owner))
            except Exception:
                live = True
            if live:
                continue
            updated = self.mark_operation_uncertain(
                run_id, operation["operation_id"], lost_worker=owner,
                confirmed=True,
                evidence=f"{owner} is no longer reachable; the operation "
                         f"was left running by that worker")
            stranded.append(updated)
        return stranded

    @_guarded
    def reconcile_uncertain_operation(
        self,
        run_id: str,
        operation_id: str,
        verdict: str,
        *,
        evidence: str,
        evidence_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Settle an ``uncertain`` operation against durable evidence.

        The three verdicts mean three different things, and conflating
        them is how duplicates happen:

        * ``applied``      — evidence PROVES the effect landed. Record
          completion; a retry must not run it again.
        * ``not_applied``  — evidence PROVES it did not. The operation
          closes as failed and a retry is permitted, as a NEW operation
          linked by ``parent_operation_id``. The original record is
          never rewound, because the evidence describes a moment, not a
          rewindable state.
        * ``insufficient`` — the evidence proves neither. The operation
          STAYS uncertain and is reported as needing reconciliation. A
          timeout, an absent audit row, or "I could not tell" is not
          proof of absence: the write may have landed without leaving the
          trace being looked for.

        Every outcome requires evidence text, so an unexplained
        reconciliation cannot be recorded.
        """
        if verdict not in RECONCILIATION_VERDICTS:
            raise TaskLifecycleError(
                f"unknown reconciliation verdict '{verdict}'")
        if not str(evidence or "").strip():
            raise TaskLifecycleError(
                "reconciliation requires evidence; an unexplained outcome "
                "cannot be recorded")

        def compute(record):
            ops = list(record["operations"])
            for index, op in enumerate(ops):
                if op.get("operation_id") != operation_id:
                    continue
                if op.get("status") != "uncertain":
                    raise TaskLifecycleError(
                        f"operation {operation_id} is {op.get('status')}; "
                        f"only an uncertain operation is reconciled")
                record_entry = {
                    "verdict": verdict,
                    "evidence": _bounded_text(evidence, 500),
                    "evidence_ref": str(evidence_ref)[:200]
                    if evidence_ref else None,
                    "at": _utc_now_iso(),
                    "reconciled_by": _current_worker_fingerprint(),
                }
                if verdict == "insufficient":
                    updated = dict(copy.deepcopy(op))
                    updated["reconciliation"] = record_entry
                    updated["needs_reconciliation"] = True
                    ops[index] = updated
                else:
                    target = "applied" if verdict == "applied" else "failed"
                    updated = transition_operation(op, target)
                    updated["reconciliation"] = record_entry
                    updated["needs_reconciliation"] = False
                    updated.pop("uncertainty_evidence", None)
                ops[index] = updated
                lifecycle = {
                    "task_revision": record["task_revision"],
                    "operations": ops,
                    "conversation_id": record.get("conversation_id"),
                }
                decision = {
                    "kind": "operation",
                    "rationale": f"reconciled {verdict}",
                    "operation_id": operation_id,
                    "operation_type": op.get("operation_type"),
                }
                return updated, lifecycle, decision
            raise TaskLifecycleError(f"operation {operation_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def cancel_operation(
        self,
        run_id: str,
        operation_id: str,
    ) -> Dict[str, Any]:
        """Release a claimed-but-unperformed operation.

        Used when a lane reserved and claimed an operation and then
        declined to act: the effect did not happen, so the claim must not
        be left held (which would block every later attempt at the same
        key) and must not be recorded as applied.
        """
        return self.transition_operation(run_id, operation_id, "cancelled")

    @_guarded
    def acknowledge_receipt(
        self,
        run_id: str,
        delivery_id: str,
        *,
        acknowledgement: str,
        acknowledged_by: str,
    ) -> Dict[str, Any]:
        """Record an EXPLICIT client acknowledgement of one delivery.

        A server cannot prove a response was received: writing the bytes
        and returning HTTP 200 both prove only that the request was
        handled. Only an acknowledgement bound to this delivery — carrying
        its id, from a named acknowledger — may set
        ``receipt_acknowledged``, and the evidence is kept on the record
        so the claim is auditable rather than asserted.
        """
        if not str(acknowledgement or "").strip():
            raise TaskLifecycleError(
                "a receipt acknowledgement must carry evidence")
        if not str(acknowledged_by or "").strip():
            raise TaskLifecycleError(
                "a receipt acknowledgement must name who acknowledged")

        def compute(record):
            deliveries = list(record.get("deliveries") or [])
            for index, delivery in enumerate(deliveries):
                if delivery.get("delivery_id") != delivery_id:
                    continue
                if delivery.get("receipt_confirmed"):
                    return copy.deepcopy(delivery), None, None
                from datetime import datetime, timezone

                updated = dict(copy.deepcopy(delivery))
                updated["status"] = "receipt_acknowledged"
                updated["receipt_confirmed"] = True
                updated["receipt_acknowledgement"] = {
                    "evidence": _bounded_text(acknowledgement, 500),
                    "acknowledged_by": str(acknowledged_by)[:120],
                    "at": datetime.now(timezone.utc).isoformat(),
                }
                deliveries[index] = updated
                lifecycle = {
                    "task_revision": record["task_revision"],
                    "operations": record["operations"],
                    "deliveries": deliveries,
                    "conversation_id": record.get("conversation_id"),
                }
                decision = {
                    "kind": "delivery",
                    "rationale": f"receipt acknowledged for {delivery_id}",
                    "delivery_id": delivery_id,
                }
                return updated, lifecycle, decision
            raise TaskLifecycleError(f"delivery {delivery_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def transition_operation(
        self,
        run_id: str,
        operation_id: str,
        to_status: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Persist one operation status change through the guarded table."""
        def compute(record):
            ops = list(record["operations"])
            for index, op in enumerate(ops):
                if op.get("operation_id") == operation_id:
                    updated = transition_operation(op, to_status, **kwargs)
                    ops[index] = updated
                    lifecycle = {
                        "task_revision": record["task_revision"],
                        "operations": ops,
                        "conversation_id": record.get("conversation_id"),
                    }
                    decision = {
                        "kind": "operation",
                        "rationale": f"{op.get('status')} -> {to_status}",
                        "operation_id": operation_id,
                        "operation_type": op.get("operation_type"),
                    }
                    return updated, lifecycle, decision
            raise TaskLifecycleError(f"operation {operation_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def verify_operation(
        self,
        run_id: str,
        operation_id: str,
        outcome: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run the registered contract verifiers against an outcome and
        persist the verdict on the operation (Step 0 gap #4: verdicts
        bound to operation + evidence ids).

        The verdict NEVER changes the operation status — unknown stays
        unknown, and delivery claims remain the finalizer's job. Returns
        ``{"basis": ..., "met": True/False/None}``."""
        from core.task_outcome_contract import criteria_verdict

        def compute(record):
            ops = list(record["operations"])
            for index, op in enumerate(ops):
                if op.get("operation_id") == operation_id:
                    basis, met = criteria_verdict(outcome or {})
                    updated = copy.deepcopy(op)
                    updated["verification"] = {
                        "basis": basis,
                        "met": met,
                        "contract_version": _contract_version(),
                    }
                    ops[index] = updated
                    lifecycle = {
                        "task_revision": record["task_revision"],
                        "operations": ops,
                        "conversation_id": record.get("conversation_id"),
                    }
                    decision = {
                        "kind": "verification",
                        "rationale": f"{basis}: {met}",
                        "operation_id": operation_id,
                        "operation_type": op.get("operation_type"),
                    }
                    return updated["verification"], lifecycle, decision
            raise TaskLifecycleError(f"operation {operation_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)

    @_guarded
    def reconcile_outbound(
        self,
        run_id: str,
        operation_id: str,
        provider_state: str,
    ) -> Dict[str, Any]:
        """Reconcile an outbound operation against the provider's observed
        state (Step 3): ``sent`` → applied, ``not_sent`` → failed,
        ``unknown`` → stays in its current status with an explicit
        uncertainty marker. A timeout or lost response is therefore
        reported as outcome-uncertain — never claimed sent, never
        claimed failed without checking. Terminal operations are
        immutable: reconciling one is an error, not a silent overwrite.
        Returns the updated operation."""
        if provider_state not in ("sent", "not_sent", "unknown"):
            raise TaskLifecycleError(
                f"unknown provider state '{provider_state}'")

        def compute(record):
            ops = list(record["operations"])
            for index, op in enumerate(ops):
                if op.get("operation_id") != operation_id:
                    continue
                if op.get("status") in ("applied", "failed", "cancelled",
                                        "superseded", "conflict", "rejected"):
                    raise TaskLifecycleError(
                        f"cannot reconcile terminal operation "
                        f"{operation_id} ({op.get('status')})")
                import time as _time

                updated = copy.deepcopy(op)
                updated["reconciliation"] = {
                    "provider_state": provider_state,
                    "checked_at": _time.time(),
                }
                if provider_state == "unknown":
                    updated["outcome_uncertain"] = True
                    # Status untouched: uncertainty is a first-class outcome.
                else:
                    updated["outcome_uncertain"] = False
                    updated = transition_operation(
                        updated,
                        "applied" if provider_state == "sent" else "failed")
                ops[index] = updated
                lifecycle = {
                    "task_revision": record["task_revision"],
                    "operations": ops,
                    "conversation_id": record.get("conversation_id"),
                }
                decision = {
                    "kind": "reconciliation",
                    "rationale": f"{operation_id}: provider says "
                                 f"{provider_state}",
                    "operation_id": operation_id,
                    "operation_type": op.get("operation_type"),
                }
                return copy.deepcopy(updated), lifecycle, decision
            raise TaskLifecycleError(f"operation {operation_id} not found")

        with self._lock:
            return self._mutate(run_id, compute)


# ------------------------------------------------------- turn recording
# Thin adapters used by chat turn lanes (Step 1 wiring). They take the
# lane's already-computed facts — never recompute retrieval or rendering.

def _entities_from_items(items: List[str]) -> List[Dict[str, Any]]:
    return [{"id": str(item), "label": str(item), "aliases": [],
             "provenance_turn": None, "inferred": False}
            for item in (items or []) if str(item).strip()]


def _resolve_for_turn(lifecycle: "TaskLifecycle",
                      session: Dict[str, Any],
                      conversation_id: str) -> Optional[Dict[str, Any]]:
    """The conversation's active task preferring the turn-entry stashed
    run id, falling back to a fresh lookup. Cancelled tasks are
    terminal and resolve as absent (later work starts a new task)."""
    record = None
    stashed = (session or {}).get("_task_run_id") \
        if isinstance(session, dict) else None
    if stashed:
        try:
            record = lifecycle.get_task(stashed)
        except Exception:
            record = None
    if record is None:
        record = lifecycle.find_active_task(conversation_id)
    if (record is not None and
            (record.get("task_revision") or {}).get("authorization")
            == "cancelled"):
        return None
    return record


def _resolve_or_create(lifecycle: "TaskLifecycle",
                       session: Dict[str, Any],
                       conversation_id: str,
                       message: str,
                       entities: Optional[List[Dict[str, Any]]] = None,
                       requested_fields: Optional[List[str]] = None,
                       canvas_id: Optional[str] = None,
                       ) -> Tuple[str, Optional[Dict[str, Any]], bool]:
    """Find the active task or create one, atomically: the file lock
    serializes the find→create window across processes (the version
    counter cannot guard creation — there is no row yet), while the
    caller-held ``_MUTATION_LOCK`` covers threads. Returns
    ``(run_id, record_or_None_if_created, was_created)`` and stashes
    the run id on the session in both cases. ``canvas_id`` (when the
    turn carries one) rides the new task's provenance so cross-session
    continuation can resume THIS job through the canvas identity."""
    with _creation_guard():
        record = _resolve_for_turn(lifecycle, session or {},
                                   conversation_id)
        if record is not None:
            run_id = record["run_id"]
            was_created = False
        else:
            provenance = {"requested_change": _bounded_text(message, 500)}
            if canvas_id:
                provenance["canvas_id"] = str(canvas_id)
            created = lifecycle.create_task(
                conversation_id, message,
                entities=list(entities or []),
                requested_fields=list(requested_fields or []),
                provenance=provenance,
            )
            run_id = created["run_id"]
            record = None
            was_created = True
        if isinstance(session, dict):
            session["_task_run_id"] = run_id
        return run_id, record, was_created


class TaskAuthorizationError(TaskLifecycleError):
    """Raised when the current task revision does not authorize an action."""


class OperationExecutionClaimed(TaskLifecycleError):
    """Raised when another caller already holds the right to execute an
    operation. One operation RECORD is not one EFFECT: the caller that
    loses this claim must wait or replay, never mutate as well."""


READ_ONLY_ACTIONS = ("retrieve", "present")
MUTATING_ACTIONS = ("edit", "outbound")
_TERMINAL_AUTHORIZATION = ("cancelled", "revoked")
# A delivery the SERVER wrote, versus a delivery the CLIENT acknowledged.
# The server cannot prove a response was received, so it never writes the
# second state on its own authority.
DELIVERY_STATUSES = ("persisted_for_delivery", "receipt_acknowledged",
                     "superseded")


# Scope validators are REGISTERED CALLABLES, not labels. A caller naming a
# validator proves nothing; the lifecycle resolves the name and RUNS it.
# An unregistered name is refused, so permission can never be established
# by asserting who vouched for it.
_SCOPE_VALIDATORS: Dict[str, Any] = {}


def register_scope_validator(name: str):
    """Register the callable that may approve widening a task's scope."""
    def decorate(fn):
        _SCOPE_VALIDATORS[str(name)] = fn
        return fn
    return decorate


def _run_scope_validator(name: str, action: str, message: str,
                         context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve and run a registered scope validator."""
    validator = _SCOPE_VALIDATORS.get(str(name or ""))
    if validator is None:
        raise TaskAuthorizationError(
            f"scope validator {name!r} is not registered; permission "
            f"cannot be established by naming a validator")
    try:
        approved = validator(action, message, context or {})
    except Exception as exc:
        raise TaskAuthorizationError(
            f"scope validator {name!r} failed to decide: {exc}")
    if not approved:
        raise TaskAuthorizationError(
            f"scope validator {name!r} refused {action} for this request")
    return {"validator": str(name), "approved": True}


def expand_task_scope(
    lifecycle: "TaskLifecycle",
    run_id: str,
    action: str,
    *,
    granted_by_message: str,
    validator: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Widen a task's scope for one action, and persist WHY.

    A new user request may legitimately expand a previously granted scope:
    "fix the draft" on a task scoped to retrieval is a real widening. The
    widening requires the user's own text for this turn AND a registered
    validator that actually RUNS and approves that action for that text —
    naming a validator is not enough, and there is no free-form
    permission label. The grant is written as a task revision BEFORE
    execution, recording the words, the validator that approved them, and
    the revision it landed on.
    """
    if action not in MUTATING_ACTIONS:
        raise TaskLifecycleError(
            f"only mutating actions can be granted, not '{action}'")
    if not str(granted_by_message or "").strip():
        raise TaskAuthorizationError(
            "a scope grant must carry the user's own request text")
    record = lifecycle.get_task(run_id)
    if record is None:
        raise TaskAuthorizationError(f"task {run_id} is not resolvable")
    revision = record.get("task_revision") or {}
    if revision.get("authorization") in _TERMINAL_AUTHORIZATION:
        raise TaskAuthorizationError(
            f"task is {revision.get('authorization')}; scope cannot expand")
    scope = [str(a) for a in (revision.get("authorized_actions") or [])]
    if action in scope:
        return {"run_id": run_id, "action": action, "scope": scope,
                "expanded": False}
    # The validator must approve THIS action for THIS text.
    approval = _run_scope_validator(
        validator, action, granted_by_message, context)
    scope.append(action)
    provenance = copy.deepcopy(revision.get("provenance") or {})
    grants = list(provenance.get("scope_grants") or [])
    grants.append({
        "action": action,
        "granted_by_message": _bounded_text(granted_by_message, 500),
        "validator": approval["validator"],
        "validated": True,
        "at_revision": int(revision.get("revision") or 0) + 1,
    })
    provenance["scope_grants"] = grants
    lifecycle.apply_transition(run_id, {
        "kind": "authorize_execute",
        "requested_change": f"scope granted: {action}",
        "approval": "authorized",
        "authorized_actions": scope,
        "provenance": provenance,
    })
    return {"run_id": run_id, "action": action, "scope": scope,
            "expanded": True, "validator": approval["validator"]}


def check_turn_authorization(
    lifecycle: "TaskLifecycle",
    run_id: Optional[str],
    action: str,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    """Validate that the CURRENT task revision authorizes ``action``.

    The pre-execution gate: a turn consults the lifecycle before any tool
    runs, so an unauthorized or drifted turn never reaches the world.
    Returns a decision dict; raises ``TaskAuthorizationError`` when the
    action is not permitted. Permission is the PERSISTED task scope and
    nothing else — there is no per-call bypass. Rules, in order:

    * no task, cancelled, or revoked → denied (terminal);
    * ``expected_revision`` that no longer matches the persisted
      revision → denied as stale, so a turn that decided against an
      older revision cannot execute against a newer one;
    * a mutating action must be named by the task's scope; widen it
      first with ``expand_task_scope`` if the user's own request
      justifies it;
    * an operation awaiting approval may not execute;
    * read-only actions are allowed on any non-terminal task.
    """
    if action not in READ_ONLY_ACTIONS + MUTATING_ACTIONS:
        raise TaskLifecycleError(f"unknown action '{action}'")
    if not run_id:
        raise TaskAuthorizationError("no active task for this action")
    record = lifecycle.get_task(run_id)
    if record is None:
        raise TaskAuthorizationError(
            f"task {run_id} is not resolvable for {action}")
    revision = record.get("task_revision") or {}
    current = int(revision.get("revision") or 0)
    authorization = revision.get("authorization")
    if authorization in _TERMINAL_AUTHORIZATION:
        raise TaskAuthorizationError(
            f"task is {authorization}; {action} is not permitted")
    if expected_revision is not None and \
            int(expected_revision) != current:
        raise TaskAuthorizationError(
            f"revision drift: decision made against revision "
            f"{expected_revision}, current is {current}")
    granted = [str(a) for a in (revision.get("authorized_actions") or [])]
    if action in MUTATING_ACTIONS:
        if action not in granted:
            raise TaskAuthorizationError(
                f"task scope is {granted or 'empty'}; it does not name "
                f"{action}")
        if authorization == "pending_approval":
            raise TaskAuthorizationError(
                f"task authorization is pending_approval; {action} "
                "is not permitted")
    return {
        "run_id": run_id,
        "action": action,
        "allowed": True,
        "revision": current,
        "authorization": authorization or "read_only",
        "basis": "task_scope" if action in MUTATING_ACTIONS else "read_only",
        "scope": granted,
    }


def begin_retrieval_turn(
    lifecycle: "TaskLifecycle",
    session: Dict[str, Any],
    conversation_id: str,
    message: str,
    execution_id: Optional[str],
    items: Optional[List[str]] = None,
    requested_fields: Optional[List[str]] = None,
    canvas_id: Optional[str] = None,
) -> tuple:
    """Persist the retrieval INTENTION before execution (Step 2).

    Resolves the conversation's task (creating it on first contact,
    binding ``canvas_id`` into a new task's provenance when the turn
    carries one), applies ``research_and_present`` when continuing one,
    and opens a ``retrieve`` operation in ``pending`` — nothing has run
    yet. The caller executes, then settles with ``finish_retrieval_turn``.
    A failure between the two leaves a durable pending operation with
    zero tool effects. Returns ``(run_id, operation_id)``.
    """
    run_id, record, was_created = _resolve_or_create(
        lifecycle, session, conversation_id, message,
        entities=_entities_from_items(items),
        requested_fields=list(requested_fields or []),
        canvas_id=canvas_id)
    if not was_created:
        lifecycle.apply_transition(run_id, {
            "kind": "research_and_present",
            "requested_change": _bounded_text(message, 500),
            "output_preferences": (
                (record or {}).get("task_revision") or {}).get(
                    "output_preferences") or {},
        })
    # Pre-execution gate: after the revision this turn will act on is
    # settled, before the operation exists. A denial leaves the task
    # untouched — no operation, no tool effect.
    check_turn_authorization(lifecycle, run_id, "retrieve")
    operation = lifecycle.create_operation(
        run_id, op_type="retrieve",
        requested_change=_bounded_text(message, 500))
    return run_id, operation["operation_id"]


def finish_retrieval_turn(
    lifecycle: "TaskLifecycle",
    run_id: Optional[str],
    operation_id: Optional[str],
    structured_result: Optional[Dict[str, Any]],
    execution_id: Optional[str],
    complete: bool,
    execution: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Settle a begun retrieval after execution (Step 2).

    Moves the operation pending→running→applied (complete, binding the
    observed evidence) or pending→running (incomplete — started but
    partial). Reconciles entities against the observed items
    (additions/removals via ``revise_objective``) and fills requested
    fields when the task has none yet. Returns the run id, or None
    when there was nothing to settle.
    """
    if not run_id or not operation_id:
        return None
    structured_result = structured_result or {}
    observed = [str(item) for item in
                (structured_result.get("requested_items") or [])
                if str(item).strip()]
    record = lifecycle.get_task(run_id)
    if record is None:
        return None
    current_ids = [str(e.get("id")) for e in
                   (record["task_revision"].get("entities") or [])]
    needs_entities = bool(observed) and set(observed) != set(current_ids)
    needs_fields = bool(structured_result.get("requested_fields")) and not (
        record["task_revision"].get("requested_fields"))
    if needs_entities or needs_fields:
        # One revision binds what observation taught us (entities
        # and/or fields); invalidation is computed against the
        # pre-observation entities only.
        removed = [i for i in current_ids if i not in set(observed)] \
            if needs_entities else []
        lifecycle.apply_transition(run_id, {
            "kind": "revise_objective",
            "requested_change": "observed items differ from tasked items",
            "entities": _entities_from_items(observed)
            if needs_entities else list(
                record["task_revision"].get("entities") or []),
            "removed_entity_ids": removed,
            "requested_fields": list(
                structured_result.get("requested_fields") or [])
            if needs_fields else list(
                record["task_revision"].get("requested_fields") or []),
        })
        record = lifecycle.get_task(run_id) or record
    lifecycle.transition_operation(
        run_id, operation_id, "running", execution_id=execution_id)
    if not complete:
        return run_id
    lifecycle.transition_operation(
        run_id, operation_id, "applied",
        evidence_revision=structured_result.get("evidence_revision"),
        execution_id=execution_id)
    attempt = structured_result.get("attempt_id")
    lifecycle.apply_transition(run_id, {
        "kind": "attach_evidence",
        "requested_change": "observed retrieval evidence",
        "evidence": {
            "evidence_id": attempt or str(uuid.uuid4()),
            "entity_ids": observed,
            "evidence_revision": structured_result.get("evidence_revision"),
        },
    })
    if execution is not None:
        try:
            # EXECUTION FACTS ride the operation record (post-settle
            # provenance — same class as an edit's invalidated-evidence
            # ids: a recording failure must not unwind the settle).
            lifecycle.attach_operation_field(
                run_id, operation_id, "execution",
                normalize_execution_facts(execution))
        except Exception:  # noqa: BLE001 — facts are provenance, not status
            pass
    return run_id


def find_uncertain_operations(lifecycle: "TaskLifecycle",
                             conversation_id: Optional[str] = None
                             ) -> List[Dict[str, Any]]:
    """Operations whose outcome is unknown and which need reconciliation.

    This is what a conversation reads to tell the user the truth: an
    effect whose outcome is genuinely unknown, rather than a reply that
    implies everything either happened or did not.
    """
    found: List[Dict[str, Any]] = []
    runs = lifecycle.runs.list_runs(include_terminal=True, limit=500)
    for run in runs:
        record = lifecycle.get_task(run["id"])
        if record is None:
            continue
        if conversation_id and \
                record.get("conversation_id") != conversation_id:
            continue
        for operation in record.get("operations") or []:
            if operation.get("status") == "uncertain" or \
                    operation.get("needs_reconciliation"):
                found.append({
                    "run_id": record["run_id"],
                    "conversation_id": record.get("conversation_id"),
                    "operation": operation,
                })
    return found


def uncertainty_notice(operation: Dict[str, Any]) -> Dict[str, Any]:
    """The user-facing description of an operation of unknown outcome.

    Deliberately says the outcome is unknown and that a check is needed.
    It never claims the change did not happen (which would invite a
    duplicate) and never claims it did (which would be a lie).
    """
    op_type = operation.get("operation_type") or "change"
    lost = operation.get("lost_worker")
    return {
        "outcome": "unknown",
        "needs_reconciliation": True,
        "operation_id": operation.get("operation_id"),
        "operation_type": op_type,
        "message": (
            f"I started a {op_type} but lost contact before I could "
            f"confirm whether it was applied. I have not repeated it. "
            f"Check the current state, then tell me whether to try again."
        ),
        "lost_worker": lost,
        "retry_is_safe": False,
    }


# ---------------------------------------------------------------------------
# Job-work ledger — open questions, selection, and the settle-time recorder
# ---------------------------------------------------------------------------

def open_unresolved_questions(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The OPEN questions on a task record — the only set continuation
    and completion checks may read. A resolved question is history: it
    keeps its text on the revision for audit but never resurfaces."""
    if not isinstance(record, dict):
        return []
    revision = record.get("task_revision") or {}
    return [q for q in (revision.get("unresolved") or [])
            if isinstance(q, dict) and q.get("status") == "open"]


def _slim_question(question: Dict[str, Any]) -> Dict[str, Any]:
    """The selection-facing projection of one open question."""
    return {
        "question_id": question.get("question_id"),
        "item": question.get("item") or "",
        "question": question.get("question") or "",
        "kind": question.get("kind"),
        "next_action": question.get("next_action"),
        "decision_owner": question.get("decision_owner"),
        "attempts": int(question.get("attempts") or 0),
    }


def next_unfinished_work(
    record: Dict[str, Any],
    *,
    attempt_cap: int = UNRESOLVED_ATTEMPT_CAP,
    max_actions: int = 3,
) -> Dict[str, Any]:
    """Select the next useful work from the OPEN question set.

    Three classes, never conflated (2026-10-04 reviewer corrections):
    EXECUTABLE questions (verification, missing_evidence) carry an
    agent-runnable next action and stay selectable under the attempt
    budget; OWNER decisions are surfaced for the owner to settle —
    never auto-executed; EXHAUSTED questions spent their budget and are
    reported, not retried. Item match status, freshness, and owner
    approval are separate dimensions of completion — none of them
    substitutes for another here."""
    actions: List[Dict[str, Any]] = []
    owner_decisions: List[Dict[str, Any]] = []
    exhausted: List[Dict[str, Any]] = []
    for question in open_unresolved_questions(record):
        slim = _slim_question(question)
        if question.get("kind") == "business_decision":
            owner_decisions.append(slim)
        elif int(question.get("attempts") or 0) >= attempt_cap:
            exhausted.append(slim)
        elif question.get("next_action"):
            actions.append(slim)
    return {
        "actions": actions[:max_actions],
        "owner_decisions": owner_decisions,
        "exhausted": exhausted,
    }


def add_unresolved_questions(
    lifecycle: "TaskLifecycle",
    run_id: str,
    questions: List[Dict[str, Any]],
    *,
    source_operation: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Append NEW open questions to the task (durable, idempotent).

    A question already open with the same (item, text) is not re-added —
    a later read re-deriving the same gap is the same question, tracked
    by the attempts counter, not a growing list."""
    record = lifecycle.get_task(run_id)
    if record is None:
        return []
    already_open = {_question_key(q)
                    for q in open_unresolved_questions(record)}
    fresh: List[Dict[str, Any]] = []
    for question in questions:
        entry = _normalize_question(question, operation=source_operation)
        if _question_key(entry) in already_open:
            continue
        already_open.add(_question_key(entry))
        fresh.append(entry)
    if not fresh:
        return []
    lifecycle.apply_transition(run_id, {
        "kind": "record_unresolved",
        "requested_change": f"{len(fresh)} open question(s) recorded",
        "questions": fresh,
        "source_operation": source_operation,
    })
    return fresh


def resolve_unresolved_questions(
    lifecycle: "TaskLifecycle",
    run_id: str,
    *,
    question_ids: Optional[List[str]] = None,
    items: Optional[List[str]] = None,
    kinds: Optional[List[str]] = None,
    resolution: str,
) -> List[Dict[str, Any]]:
    """Mark matching OPEN questions resolved. The resolution text is
    required — an unexplained resolution cannot be recorded, because the
    audit must be able to say HOW each question settled. A resolved
    question never resurfaces in the open set."""
    if not str(resolution or "").strip():
        raise TaskLifecycleError(
            "resolving a question requires how it was resolved")
    record = lifecycle.get_task(run_id)
    if record is None:
        return []
    id_set = {str(q) for q in (question_ids or [])}
    item_set = {str(i) for i in (items or [])}
    kind_set = {str(k) for k in (kinds or [])}
    settled: List[Dict[str, Any]] = []
    for question in open_unresolved_questions(record):
        if id_set and question.get("question_id") not in id_set:
            continue
        if item_set and (question.get("item") or "") not in item_set:
            continue
        if kind_set and question.get("kind") not in kind_set:
            continue
        settled.append({
            "question_id": question.get("question_id"),
            "item": question.get("item") or "",
        })
    if not settled:
        return []
    lifecycle.apply_transition(run_id, {
        "kind": "record_unresolved",
        "requested_change": f"{len(settled)} question(s) resolved",
        "resolutions": [
            {"question_id": s["question_id"],
             "resolution": _bounded_text(resolution, 400)}
            for s in settled],
    })
    return settled


def record_denied_edit_attempt(
    lifecycle: "TaskLifecycle",
    run_id: Optional[str],
    requested_change: str,
    reason: str,
) -> Optional[Dict[str, Any]]:
    """Record an edit the authorization gate REFUSED (2026-10-04 reviewer
    correction 4): zero writes is the correct OUTCOME, but an attempted
    edit on a research-shaped ask is still a planning-quality failure
    worth recording. The operation ends ``cancelled`` — the effect did
    not happen — with the denial reason and the ask that prompted it,
    so the audit can distinguish 'nothing was attempted' from 'an edit
    was attempted and correctly refused'. The scope gate itself is NOT
    weakened; this only makes its decisions visible."""
    if not run_id:
        return None
    operation = lifecycle.create_operation(
        run_id, op_type="edit",
        requested_change=_bounded_text(requested_change, 500))
    lifecycle.transition_operation(
        run_id, operation["operation_id"], "cancelled")
    lifecycle.attach_operation_field(
        run_id, operation["operation_id"], "denied",
        {"reason": _bounded_text(reason, 300),
         "recorded": "attempted edit refused by the authorization gate"})
    return operation


def bump_question_attempts(
    lifecycle: "TaskLifecycle",
    run_id: str,
    question_ids: List[str],
) -> None:
    """Count one continuation attempt against each named open question —
    the bounded-attempt budget's ledger entry. Over-cap questions stop
    being selected by ``next_unfinished_work`` and are reported as
    exhausted instead."""
    ids = [str(i) for i in (question_ids or []) if str(i).strip()]
    if not ids:
        return
    lifecycle.apply_transition(run_id, {
        "kind": "record_unresolved",
        "requested_change": f"attempt counted on {len(ids)} question(s)",
        "attempts": [{"question_id": i, "increment": 1} for i in ids],
    })


def derive_read_questions(
    structured_result: Optional[Dict[str, Any]],
    freshness: Optional[Dict[str, Any]],
    *,
    bindings: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Derive the question adds and resolutions ONE read justifies.

    Dimensions stay separate (2026-10-04 reviewer correction #2): an
    item's identity match status describes MATCHING only. A 'single'
    match resolves a missing-evidence question for that item — it never
    resolves a freshness question or an owner decision. A freshness
    verdict resolves only verification questions. An owner-recorded
    binding resolves only the decision it settles. Nothing here asserts
    job completion; that is a separate judgment over all dimensions.

    ``freshness`` is the read lane's verdict dict (``status`` plus the
    stage-attributed ``refresh_outcome``); ``bindings`` are the
    workspace's user-asserted item bindings (owner decisions already
    settled by the owner's own earlier confirmation).
    """
    structured = structured_result if isinstance(
        structured_result, dict) else {}
    fresh = freshness if isinstance(freshness, dict) else {}
    questions: List[Dict[str, Any]] = []
    resolutions: List[Dict[str, Any]] = []
    bound_items = {str((b or {}).get("item") or "")
                   for b in (bindings or []) if isinstance(b, dict)}

    for target in (structured.get("targets") or []):
        if not isinstance(target, dict):
            continue
        item = str(target.get("item") or "").strip()
        identity = target.get("identity") or {}
        status = str(identity.get("status") or "")
        if not item or status not in ("single", "multiple", "none"):
            continue
        if status == "multiple":
            if item in bound_items:
                resolutions.append({
                    "items": [item], "kinds": ["business_decision"],
                    "resolution": "owner binding on file settles the pick",
                })
                continue
            questions.append({
                "item": item,
                "kind": "business_decision",
                "question": f"which {item} row/variant is the right one "
                            f"to use (the read matched more than one)",
                "evidence": _bounded_text(
                    identity.get("detail")
                    or "multiple candidate rows matched", 300),
            })
        elif status == "none":
            questions.append({
                "item": item,
                "kind": "missing_evidence",
                "question": f"no source on file carries {item}",
                "evidence": "the read ran and matched nothing for it",
                "next_action": f"search vendor correspondence and "
                               f"attachments for {item}",
            })
        elif status == "single":
            resolutions.append({
                "items": [item], "kinds": ["missing_evidence"],
                "resolution": "found on file by a completed read",
            })

    freshness_status = str(fresh.get("status") or "")
    if freshness_status:
        if freshness_status in ("refresh_failed", "unverified"):
            stage = str(((fresh.get("refresh_outcome") or {}).get(
                "stage")) or "unattributed")
            questions.append({
                "item": "",
                "kind": "verification",
                "question": "current-source verification did not "
                            "succeed",
                "evidence": f"freshness verdict {freshness_status} "
                            f"(stage: {stage})",
                "next_action": "retry live source verification",
            })
        elif freshness_status in ("refreshed", "current"):
            resolutions.append({
                "items": [], "kinds": ["verification"],
                "resolution": f"freshness verdict {freshness_status}",
            })
    return {"questions": questions, "resolutions": resolutions}


def record_read_outcome(
    lifecycle: "TaskLifecycle",
    run_id: Optional[str],
    operation_id: Optional[str],
    *,
    structured_result: Optional[Dict[str, Any]],
    freshness: Optional[Dict[str, Any]],
    execution: Optional[Dict[str, Any]] = None,
    bindings: Optional[List[Dict[str, Any]]] = None,
    extra_questions: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """The ONE settle-time call the read lanes make after
    ``finish_retrieval_turn``: derive what this read justifies, apply it,
    and return the open-work snapshot the reply's next steps and the
    completion check both read. Per-step failures are collected, not
    raised — the settle already happened; these are the ledger's
    bookkeeping, and the lanes log the errors."""
    if not run_id:
        return None
    errors: List[str] = []
    if execution is not None and operation_id:
        try:
            lifecycle.attach_operation_field(
                run_id, operation_id, "execution",
                normalize_execution_facts(execution))
        except Exception as exc:  # noqa: BLE001 — facts are provenance
            errors.append(f"execution: {exc!r}")
    derived = derive_read_questions(
        structured_result, freshness, bindings=bindings)
    if extra_questions:
        derived["questions"] = list(
            derived["questions"] or []) + [
                q for q in extra_questions if isinstance(q, dict)]
    try:
        if derived["questions"]:
            add_unresolved_questions(
                lifecycle, run_id, derived["questions"],
                source_operation=operation_id)
    except Exception as exc:  # noqa: BLE001 — bookkeeping, not status
        errors.append(f"questions: {exc!r}")
    for resolution in derived["resolutions"]:
        try:
            resolve_unresolved_questions(
                lifecycle, run_id,
                items=resolution.get("items") or None,
                kinds=resolution.get("kinds") or None,
                resolution=resolution["resolution"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"resolution: {exc!r}")
            break
    record = lifecycle.get_task(run_id)
    work = next_unfinished_work(record or {})
    if errors:
        work["ledger_errors"] = errors
    return work


@_guarded
def record_retrieval_turn(
    lifecycle: "TaskLifecycle",
    session: Dict[str, Any],
    conversation_id: str,
    message: str,
    structured_result: Optional[Dict[str, Any]],
    execution_id: Optional[str],
    complete: bool,
) -> Optional[str]:
    """Record one retrieval turn on the conversation's task.

    Convenience wrapper over ``begin_retrieval_turn`` +
    ``finish_retrieval_turn`` for callers whose execution already
    happened (tests, compat paths). Live lanes prefer the split form
    so the intention is durable before the tools run. First retrieval
    creates the task (revision 1) with the requested items as
    entities; later retrievals apply ``research_and_present``
    (revision +1, never a history union). Either way a new ``retrieve``
    operation is opened and moved to ``applied`` (complete, with the
    evidence revision) or left ``running``. The run id is stowed on the
    session as ``_task_run_id``. Returns the run id, or None when there
    is no structured result to record.
    """
    structured_result = structured_result or {}
    items = list(structured_result.get("requested_items") or [])
    if not items:
        return None
    run_id, operation_id = begin_retrieval_turn(
        lifecycle, session, conversation_id, message, execution_id,
        items=items,
        requested_fields=list(
            structured_result.get("requested_fields") or []))
    return finish_retrieval_turn(
        lifecycle, run_id, operation_id, structured_result,
        execution_id, complete)


@_guarded
def record_presentation_turn(
    lifecycle: "TaskLifecycle",
    session: Dict[str, Any],
    conversation_id: str,
    message: str,
    style: Optional[str] = None,
    field: Optional[str] = None,
    requested_fields: Optional[List[str]] = None,
) -> Optional[str]:
    """Record one formatting follow-up: a ``change_presentation``
    transition on the conversation's task, zero retrieval. When the turn
    also selects a field, a ``revise_fields`` transition narrows the
    requested fields so later renders re-select from retained evidence
    instead of re-reading. Returns the run id, or None when the
    conversation has no task to continue."""
    run_id = (session or {}).get("_task_run_id")
    if not run_id:
        record = lifecycle.find_active_task(conversation_id)
        if record is None:
            return None
        run_id = record["run_id"]
        if isinstance(session, dict):
            session["_task_run_id"] = run_id
    # Pre-execution gate: a halted line of work cannot be re-presented.
    check_turn_authorization(lifecycle, run_id, "present")
    lifecycle.apply_transition(run_id, {
        "kind": "change_presentation",
        "requested_change": _bounded_text(message, 500),
        "output_preferences": {"style": style or "default",
                               "field": field},
    })
    if requested_fields is not None:
        lifecycle.apply_transition(run_id, {
            "kind": "revise_fields",
            "requested_change": _bounded_text(message, 500),
            "requested_fields": list(requested_fields),
        })
    return run_id


@_guarded
def cancel_task(
    lifecycle: "TaskLifecycle",
    session: Dict[str, Any],
    conversation_id: str,
    message: str,
) -> Optional[str]:
    """Apply the ``cancel`` transition to the conversation's active task
    (a halt turn ends the line of work; completed operations are
    reported, outstanding ones marked cancelled). Returns the run id,
    or None when there is no task to stop."""
    run_id = (session or {}).get("_task_run_id")
    record = None
    if run_id:
        try:
            record = lifecycle.get_task(run_id)
        except Exception:
            record = None
    if record is None:
        record = lifecycle.find_active_task(conversation_id)
    if record is None:
        return None
    run_id = record["run_id"]
    lifecycle.apply_transition(run_id, {
        "kind": "cancel",
        "requested_change": _bounded_text(message, 500),
    })
    if isinstance(session, dict):
        session["_task_run_id"] = run_id
    return run_id


@_guarded
def begin_edit_turn(
    lifecycle: "TaskLifecycle",
    session: Dict[str, Any],
    conversation_id: str,
    message: str,
    execution_id: Optional[str],
    idempotency_key: Optional[str] = None,
    *,
    scope_grant: Optional[Dict[str, str]] = None,
) -> tuple:
    """Reserve a canvas ``edit`` before the mutation happens (Step 2).

    Mirrors ``begin_retrieval_turn`` for the mutating lane: the task is
    resolved (created on first contact), the ``edit`` action is checked
    against the current revision, and a ``pending`` operation is opened —
    so a crash between reservation and mutation leaves a durable pending
    operation rather than an unrecorded change.

    When the task's scope does not yet name ``edit``, a caller's
    ``scope_grant`` (``granted_by_message`` + ``validator``) may widen it
    through ``expand_task_scope``, which persists the grant as a revision
    BEFORE the operation is created. An empty scope is never widened on
    the caller's say-so alone: without the user's own request text and a
    named validator the gate denies.

    Returns ``(run_id, operation_id)``.
    """
    run_id, _, _ = _resolve_or_create(
        lifecycle, session, conversation_id, message)
    try:
        check_turn_authorization(lifecycle, run_id, "edit")
    except TaskAuthorizationError:
        grant = scope_grant or {}
        if not (grant.get("granted_by_message")
                and grant.get("validator")):
            raise
        expand_task_scope(
            lifecycle, run_id, "edit",
            granted_by_message=grant.get("granted_by_message") or "",
            validator=grant.get("validator") or "",
            context=grant.get("context"))
        check_turn_authorization(lifecycle, run_id, "edit")
    operation = lifecycle.create_operation(
        run_id, op_type="edit",
        requested_change=_bounded_text(message, 500),
        idempotency_key=idempotency_key or execution_id)
    # Reserve the RECORD, then win the right to perform its EFFECT. The
    # replayed key above can hand two callers the same operation id; only
    # one of them may mutate.
    claim = lifecycle.claim_execution(
        run_id, operation["operation_id"], execution_id=execution_id)
    if not claim.get("granted"):
        if claim.get("status") == "uncertain":
            raise OperationExecutionClaimed(
                f"operation {operation['operation_id']} has an UNKNOWN "
                f"outcome and needs reconciliation; it must not be "
                f"repeated until durable evidence settles it")
        raise OperationExecutionClaimed(
            f"operation {operation['operation_id']} is "
            f"{claim.get('status')}, held by another caller; this caller "
            f"must wait or replay rather than mutate again")
    return run_id, operation["operation_id"]


def finish_edit_turn(
    lifecycle: "TaskLifecycle",
    run_id: Optional[str],
    operation_id: Optional[str],
    execution_id: Optional[str],
    *,
    updated: bool,
    needs_review: bool,
    success: bool,
    invalidated_evidence_ids: Optional[List[str]] = None,
) -> Optional[str]:
    """Settle a reserved canvas edit after the mutation (Step 2).

    Declined edits (``updated`` False) record nothing further — the turn
    falls through to other lanes, which own the turn and its records.
    Status mapping: failed when the turn did not succeed,
    awaiting_approval for learning-mode/pending-review drafts, applied
    otherwise. ``invalidated_evidence_ids`` names revision evidence this
    edit supersedes (a correction invalidates what it replaces); the names
    ride the OPERATION record only, so revision evidence is never
    rewritten and the audit trail stays intact.
    """
    if not run_id or not operation_id or not updated:
        if run_id and operation_id and not updated:
            # The operation was reserved and its execution claimed, but
            # the lane declined — so NO effect happened. Release the claim
            # rather than leaving an operation running forever.
            try:
                lifecycle.cancel_operation(run_id, operation_id)
            except Exception:
                pass
        return None
    if invalidated_evidence_ids:
        try:
            lifecycle.attach_operation_field(
                run_id, operation_id, "invalidated_evidence_ids",
                list(invalidated_evidence_ids))
        except Exception:
            pass
    # The execution claim already moved the operation to running; settle
    # it from wherever it actually is rather than re-transitioning.
    to_status = ("failed" if not success
                 else "awaiting_approval" if needs_review else "applied")
    current = next(
        (op.get("status") for op in
         (lifecycle.get_task(run_id) or {}).get("operations") or []
         if op.get("operation_id") == operation_id), None)
    if current == to_status:
        return run_id
    lifecycle.transition_operation(
        run_id, operation_id, to_status, execution_id=execution_id)
    return run_id


def record_edit_turn(
    lifecycle: "TaskLifecycle",
    session: Dict[str, Any],
    conversation_id: str,
    message: str,
    execution_id: Optional[str],
    *,
    updated: bool,
    needs_review: bool,
    success: bool,
    idempotency_key: Optional[str] = None,
    invalidated_evidence_ids: Optional[List[str]] = None,
    scope_grant: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Record one handled canvas edit as an ``edit`` operation.

    Declined edits (``updated`` False) record nothing — the turn falls
    through to other lanes, which own the turn and its records. A
    cancelled task is terminal: the edit starts a new task. Status
    mapping: failed when the turn did not succeed, awaiting_approval
    for learning-mode/pending-review drafts, applied otherwise. The
    run id is stowed on the session as ``_task_run_id``.

    ``invalidated_evidence_ids`` names revision evidence this edit
    supersedes (a correction invalidates what it replaces). The names
    ride the OPERATION record only — revision evidence is never
    rewritten, so the audit trail stays intact. Callers that cannot
    map an edit to evidence ids pass nothing; a future
    canvas-correction producer (human PUT after an agent draft) will
    supply them from the canvas diff.
    """
    if not updated:
        return None
    run_id, operation_id = begin_edit_turn(
        lifecycle, session, conversation_id, message, execution_id,
        idempotency_key=idempotency_key, scope_grant=scope_grant)
    return finish_edit_turn(
        lifecycle, run_id, operation_id, execution_id,
        updated=updated, needs_review=needs_review, success=success,
        invalidated_evidence_ids=invalidated_evidence_ids)
