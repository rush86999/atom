"""Durable assignment plan — pure schema and state helpers.

An assignment is the employee's persisted line of work: the accepted
objective, the governing teaching snapshot, required deliverables, the
authorized sources/actions, and a dependency-ordered step plan. It lives
beside the task revision and operation list in the existing GoalRun
``task_lifecycle`` record. There is no second workflow engine here.

Domain independence is a hard contract: this module knows only opaque
labels ("item", "field", "source", "deliverable"), never business
vocabulary. A step's operation type is one of the lifecycle's supported
operation classes; the concrete work is supplied by a registered adapter.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.task_lifecycle import OPERATION_TYPES, TaskLifecycleError

ASSIGNMENT_SCHEMA_VERSION = 1
FINGERPRINT_VERSION = 2
FINGERPRINT_MAX_BYTES = 1024 * 1024
FINGERPRINT_MAX_DEPTH = 32
FINGERPRINT_MAX_ITEMS = 10000
FINGERPRINT_MAX_STRING = 100000

ASSIGNMENT_STATES = (
    "planned",
    "running",
    "waiting",
    "blocked",
    "partial",
    "completed",
    "failed",
    "cancelled",
)

#: A step's plan state. Effect truth still lives on the operation record;
#: these states describe whether the PLAN has finished with the step.
STEP_STATUSES = (
    "pending",
    "running",
    "waiting",
    "awaiting_approval",
    "applied",
    "failed",
    "uncertain",
    "cancelled",
    "superseded",
    "skipped",
)

TERMINAL_STEP_STATUSES = frozenset({
    "applied", "failed", "cancelled", "superseded", "skipped", "uncertain",
})

TERMINAL_ASSIGNMENT_STATES = frozenset({
    "completed", "failed", "cancelled",
})

_ADAPTER_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,80}$")
_GAP_KINDS = ("business_decision", "verification", "missing_evidence")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded(value: Any, limit: int) -> str:
    return str(value or "")[:limit]


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    """Bound and JSON-safe a caller value. No semantic rewriting."""
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        return {str(k)[:80]: _json_safe(v, depth=depth + 1)
                for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v, depth=depth + 1) for v in list(value)[:40]]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:1000]


def _validate_fingerprint_value(value: Any, *, depth: int = 0) -> None:
    """Validate the COMPLETE identity representation.

    Fingerprints are identity, not diagnostics. They reject unsupported or
    oversized input rather than hashing a truncated projection; otherwise two
    materially different snapshots can share a revision.
    """
    if depth > FINGERPRINT_MAX_DEPTH:
        raise ValueError("fingerprint value nesting is too deep")
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        if len(value) > FINGERPRINT_MAX_STRING:
            raise ValueError("fingerprint string exceeds the identity limit")
        return
    if isinstance(value, (list, tuple)):
        if len(value) > FINGERPRINT_MAX_ITEMS:
            raise ValueError("fingerprint list exceeds the identity limit")
        for item in value:
            _validate_fingerprint_value(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > FINGERPRINT_MAX_ITEMS:
            raise ValueError("fingerprint object exceeds the identity limit")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    "fingerprint keys must be non-empty strings")
            _validate_fingerprint_value(item, depth=depth + 1)
        return
    raise ValueError(
        f"unsupported fingerprint value type {type(value).__name__}")


def canonical_sha256(value: Any, *, version: int = FINGERPRINT_VERSION) -> str:
    """Deterministic identity hash.

    Version 2 hashes the complete validated representation; unsupported or
    oversized values raise. Version 1 is retained only to read/verify stored
    fingerprints written before this slice; new identity data uses v2.
    """
    if version == 1:
        payload = _json_safe(value)
    elif version == FINGERPRINT_VERSION:
        _validate_fingerprint_value(value)
        payload = value
    else:
        raise ValueError(f"unsupported fingerprint version {version}")
    blob = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, default=None,
    )
    if len(blob.encode("utf-8")) > FINGERPRINT_MAX_BYTES:
        raise ValueError("fingerprint representation exceeds 1 MiB")
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _clean_list(value: Any, *, limit: int = 40, text_limit: int = 200) -> List[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    out: List[str] = []
    for item in value:
        text = _bounded(item, text_limit).strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _clean_dict(value: Any, *, limit: int = 60) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _json_safe(dict(list(value.items())[:limit]))


def new_teaching_snapshot(
    *,
    revision: str = "",
    effective_lesson_ids: Optional[Sequence[Dict[str, Any]]] = None,
    applicable_conditions: Optional[Dict[str, Any]] = None,
    matched_context: Optional[Dict[str, Any]] = None,
    unresolved_conditions: Optional[Sequence[Dict[str, Any]]] = None,
    conflicting_conditions: Optional[Sequence[Dict[str, Any]]] = None,
    field_mappings: Optional[Sequence[Dict[str, Any]]] = None,
    source_versions: Optional[Dict[str, Any]] = None,
    output_requirements: Optional[Dict[str, Any]] = None,
    decision_schema: Optional[Sequence[Dict[str, Any]]] = None,
    artifact_requirements: Optional[Dict[str, Any]] = None,
    captured_at: Optional[str] = None,
) -> Dict[str, Any]:
    """One immutable execution-bound snapshot.

    Every downstream phase (generation, validation, rendering, approval and
    persistence) receives THIS object. It is stored on the assignment and is
    never re-resolved midway through execution.
    """
    snapshot = {
        "revision": _bounded(revision, 80),
        "effective_lesson_ids": [
            _clean_dict(item) for item in (effective_lesson_ids or [])
            if isinstance(item, dict)
        ][:40],
        "applicable_conditions": _clean_dict(applicable_conditions),
        "matched_context": _clean_dict(matched_context),
        "unresolved_conditions": [
            _clean_dict(item) for item in (unresolved_conditions or [])
            if isinstance(item, dict)
        ][:20],
        "conflicting_conditions": [
            _clean_dict(item) for item in (conflicting_conditions or [])
            if isinstance(item, dict)
        ][:20],
        "field_mappings": [
            _clean_dict(item) for item in (field_mappings or [])
            if isinstance(item, dict)
        ][:40],
        "source_versions": _clean_dict(source_versions),
        "output_requirements": _clean_dict(output_requirements),
        "decision_schema": [
            _clean_dict(item) for item in (decision_schema or [])
            if isinstance(item, dict)
        ][:40],
        "artifact_requirements": _clean_dict(artifact_requirements),
        "captured_at": captured_at or _utc_now_iso(),
        "fingerprint_version": FINGERPRINT_VERSION,
    }
    snapshot["fingerprint"] = canonical_sha256(snapshot)[:32]
    return snapshot


def new_step(
    *,
    step_id: Optional[str] = None,
    title: str,
    operation_type: str,
    adapter: str,
    depends_on: Optional[Sequence[str]] = None,
    inputs: Optional[Dict[str, Any]] = None,
    instruction: str = "",
    required: bool = True,
    effect: str = "local",
    approval_required: bool = False,
    approval_purpose: str = "",
    standing_authorization: str = "",
    max_attempts: int = 3,
    invalidate_on_revision_change: bool = True,
) -> Dict[str, Any]:
    """Build one dependency-ordered step.

    ``effect`` is a technical classification only: ``read_only`` (no
    external mutation), ``local`` (writes a local artifact/draft) or
    ``external`` (an outbound/third-party effect). Approval is demanded for
    effects the caller declares, never inferred from an adapter name.
    """
    op_type = str(operation_type or "").strip()
    if op_type not in OPERATION_TYPES:
        raise TaskLifecycleError(f"unsupported operation type '{op_type}'")
    adapter_name = str(adapter or "").strip()
    if not _ADAPTER_RE.match(adapter_name):
        raise TaskLifecycleError(f"invalid adapter name '{adapter_name}'")
    if effect not in ("read_only", "local", "external"):
        raise TaskLifecycleError(f"unknown effect class '{effect}'")
    identifier = str(step_id or f"step-{uuid.uuid4().hex[:12]}")
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,80}$", identifier):
        raise TaskLifecycleError(f"invalid step id '{identifier}'")
    title = _bounded(title, 200).strip()
    if not title:
        raise TaskLifecycleError("a step requires a title")
    return {
        "step_id": identifier,
        "title": title,
        "operation_type": op_type,
        "adapter": adapter_name,
        "depends_on": _clean_list(depends_on, limit=40, text_limit=80),
        "inputs": _clean_dict(inputs),
        "instruction": _bounded(instruction, 4000),
        "required": bool(required),
        "effect": effect,
        "approval": {
            "required": bool(approval_required),
            "purpose": _bounded(approval_purpose, 300),
        },
        "standing_authorization": _bounded(
            standing_authorization, 120) or None,
        "max_attempts": max(1, min(int(max_attempts or 3), 10)),
        "invalidate_on_revision_change": bool(
            invalidate_on_revision_change),
        "status": "pending",
        "operation_id": None,
        "attempts": 0,
        "result": None,
        "evidence_refs": [],
        "gap_ids": [],
        "artifact_revision": None,
        "prior_results": [],
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }


def new_deliverable(
    *,
    deliverable_id: Optional[str] = None,
    kind: str,
    description: str = "",
    required: bool = True,
    step_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "deliverable_id": str(
            deliverable_id or f"del-{uuid.uuid4().hex[:10]}"),
        "kind": _bounded(kind, 80).strip(),
        "description": _bounded(description, 500),
        "required": bool(required),
        "step_id": _bounded(step_id, 80) or None,
        "status": "pending",
        "artifact_revision": None,
        "artifact_path": None,
        "sha256": None,
    }


def new_assignment(
    *,
    objective: str,
    employee_id: str = "",
    workspace_id: str = "",
    tenant_id: str = "",
    teaching_snapshot: Optional[Dict[str, Any]] = None,
    steps: Optional[Sequence[Dict[str, Any]]] = None,
    deliverables: Optional[Sequence[Dict[str, Any]]] = None,
    sources: Optional[Sequence[Dict[str, Any]]] = None,
    authorized_actions: Optional[Sequence[str]] = None,
    approval_policy: Optional[Dict[str, Any]] = None,
    completion_criteria: Optional[Sequence[Dict[str, Any]]] = None,
    budget: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    assignment_id: Optional[str] = None,
) -> Dict[str, Any]:
    objective_text = _bounded(objective, 4000).strip()
    if not objective_text:
        raise TaskLifecycleError("an assignment requires an objective")
    assignment = {
        "schema_version": ASSIGNMENT_SCHEMA_VERSION,
        "assignment_id": str(
            assignment_id or f"asg-{uuid.uuid4().hex[:16]}"),
        "objective": objective_text,
        "employee_id": _bounded(employee_id, 120) or None,
        "workspace_id": _bounded(workspace_id, 120) or None,
        "tenant_id": _bounded(tenant_id, 120) or None,
        "plan_revision": 1,
        "status": "planned",
        "teaching_snapshot": copy.deepcopy(
            teaching_snapshot or new_teaching_snapshot()),
        "steps": [copy.deepcopy(step) for step in (steps or [])],
        "deliverables": [copy.deepcopy(item) for item in (deliverables or [])],
        "sources": [
            _clean_dict(item) for item in (sources or [])
            if isinstance(item, dict)
        ][:60],
        "authorized_actions": _clean_list(
            authorized_actions, limit=40, text_limit=120),
        "approval_policy": _clean_dict(approval_policy),
        "completion_criteria": [
            _clean_dict(item) for item in (completion_criteria or [])
            if isinstance(item, dict)
        ][:40],
        "budget": {
            "max_steps": max(1, min(int(
                (budget or {}).get("max_steps") or 40), 200)),
            "max_attempts_per_step": max(1, min(int(
                (budget or {}).get("max_attempts_per_step") or 3), 10)),
            "max_wall_seconds": max(1.0, float(
                (budget or {}).get("max_wall_seconds") or 3600.0)),
            "max_cost_usd": max(0.0, float(
                (budget or {}).get("max_cost_usd") or 0.0)),
            "steps_started": 0,
            "started_at": None,
            "elapsed_seconds": 0.0,
            "cost_usd": 0.0,
        },
        "provenance": _clean_dict(provenance),
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "completed_at": None,
        "last_transition": None,
    }
    validate_assignment(assignment)
    return assignment


def validate_assignment(assignment: Dict[str, Any]) -> None:
    if not isinstance(assignment, dict):
        raise TaskLifecycleError("assignment must be a dict")
    if assignment.get("schema_version") != ASSIGNMENT_SCHEMA_VERSION:
        raise TaskLifecycleError("assignment schema_version mismatch")
    if not str(assignment.get("assignment_id") or "").strip():
        raise TaskLifecycleError("assignment_id is required")
    if not str(assignment.get("objective") or "").strip():
        raise TaskLifecycleError("assignment objective is required")
    if assignment.get("status") not in ASSIGNMENT_STATES:
        raise TaskLifecycleError(
            f"unknown assignment status '{assignment.get('status')}'")
    steps = assignment.get("steps")
    if not isinstance(steps, list):
        raise TaskLifecycleError("assignment steps must be a list")
    ids: List[str] = []
    for step in steps:
        if not isinstance(step, dict):
            raise TaskLifecycleError("each assignment step must be a dict")
        step_id = str(step.get("step_id") or "").strip()
        if not step_id or step_id in ids:
            raise TaskLifecycleError(
                f"assignment step id '{step_id}' is missing or duplicated")
        ids.append(step_id)
        if step.get("operation_type") not in OPERATION_TYPES:
            raise TaskLifecycleError(
                f"step {step_id} has an unsupported operation type")
        if not _ADAPTER_RE.match(str(step.get("adapter") or "")):
            raise TaskLifecycleError(
                f"step {step_id} has an invalid adapter name")
        if step.get("status") not in STEP_STATUSES:
            raise TaskLifecycleError(
                f"step {step_id} has an unknown status")
    known = set(ids)
    for step in steps:
        for dependency in step.get("depends_on") or []:
            if dependency not in known:
                raise TaskLifecycleError(
                    f"step {step['step_id']} depends on unknown "
                    f"step {dependency}")
    _assert_acyclic(steps)


def _assert_acyclic(steps: Sequence[Dict[str, Any]]) -> None:
    graph = {
        step["step_id"]: list(step.get("depends_on") or [])
        for step in steps
    }
    visiting: set = set()
    visited: set = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise TaskLifecycleError(
                f"assignment dependency cycle at step {node}")
        visiting.add(node)
        for dependency in graph.get(node, []):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for step_id in graph:
        visit(step_id)


def step_by_id(assignment: Dict[str, Any], step_id: str) -> Optional[Dict[str, Any]]:
    for step in assignment.get("steps") or []:
        if step.get("step_id") == step_id:
            return step
    return None


def _dependency_done(step: Dict[str, Any], by_id: Dict[str, Dict[str, Any]]) -> bool:
    for dependency in step.get("depends_on") or []:
        target = by_id.get(dependency)
        if target is None:
            return False
        if target.get("status") not in ("applied", "skipped"):
            return False
    return True


def ready_steps(assignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pending steps whose declared dependencies are all satisfied."""
    by_id = {step["step_id"]: step for step in assignment.get("steps") or []}
    return [
        step for step in assignment.get("steps") or []
        if step.get("status") == "pending"
        and _dependency_done(step, by_id)
    ]


def downstream_step_ids(
    assignment: Dict[str, Any], step_ids: Iterable[str],
) -> List[str]:
    """The named steps plus every step transitively depending on them."""
    selected = {str(item) for item in step_ids}
    changed = True
    while changed:
        changed = False
        for step in assignment.get("steps") or []:
            if step.get("step_id") in selected:
                continue
            if selected & set(step.get("depends_on") or []):
                selected.add(step["step_id"])
                changed = True
    order = [step["step_id"] for step in assignment.get("steps") or []
             if step.get("step_id") in selected]
    return order


def derive_state(
    assignment: Dict[str, Any],
    *,
    task_authorization: str = "",
) -> str:
    """Derive the assignment state from plan and task facts.

    ``completed`` is deliberately strict: every REQUIRED step must have
    applied (or been explicitly skipped) and every required deliverable must
    exist. Partial progress never becomes completed.
    """
    if task_authorization == "cancelled" or assignment.get("status") == "cancelled":
        return "cancelled"
    steps = assignment.get("steps") or []
    required = [step for step in steps if step.get("required", True)]
    if any(step.get("status") == "awaiting_approval" for step in steps):
        return "waiting"
    if any(step.get("status") == "waiting" for step in steps):
        return "waiting"
    if any(step.get("status") == "uncertain" for step in steps):
        return "blocked"
    if any(step.get("status") == "failed" for step in required):
        return "partial" if any(
            step.get("status") == "applied" for step in required) else "failed"
    if any(step.get("status") in ("running",) for step in steps):
        return "running"
    if ready_steps(assignment):
        return "running"
    if all(step.get("status") in ("applied", "skipped") for step in required):
        deliverables = assignment.get("deliverables") or []
        if any(
            item.get("required", True)
            and item.get("status") != "applied"
            for item in deliverables
        ):
            return "partial"
        return "completed"
    if any(step.get("status") in ("applied", "skipped") for step in required):
        return "partial"
    return "blocked"


def assignment_projection(assignment: Dict[str, Any]) -> Dict[str, Any]:
    """Bounded read model — no raw source content or secrets."""
    if not isinstance(assignment, dict):
        return {}
    steps = []
    for step in assignment.get("steps") or []:
        status = step.get("status")
        recovery = {
            "applied": "terminal",
            "skipped": "terminal",
            "cancelled": "terminal",
            "superseded": "terminal",
            "failed": "terminal_failed",
            "awaiting_approval": "awaiting_approval",
            "waiting": "waiting_for_event",
            "uncertain": "uncertain_requires_reconciliation",
            "running": "safe_to_reenter_under_claim",
            "pending": "safe_to_resume",
        }.get(status, "unknown")
        steps.append({
            "step_id": step.get("step_id"),
            "title": step.get("title"),
            "operation_type": step.get("operation_type"),
            "adapter": step.get("adapter"),
            "depends_on": list(step.get("depends_on") or []),
            "required": bool(step.get("required", True)),
            "effect": step.get("effect"),
            "status": status,
            "recovery_class": recovery,
            "operation_id": step.get("operation_id"),
            "attempts": int(step.get("attempts") or 0),
            "result_summary": (
                (step.get("result") or {}).get("summary")
                if isinstance(step.get("result"), dict) else None),
            "artifact_revision": step.get("artifact_revision"),
            "gap_ids": list(step.get("gap_ids") or []),
            "waiting": copy.deepcopy(step.get("waiting") or {}),
            "approval_request": copy.deepcopy(
                step.get("approval_request") or {}),
            "failure": copy.deepcopy(step.get("failure") or {}),
        })
    return {
        "assignment_id": assignment.get("assignment_id"),
        "objective": assignment.get("objective"),
        "employee_id": assignment.get("employee_id"),
        "workspace_id": assignment.get("workspace_id"),
        "plan_revision": assignment.get("plan_revision"),
        "status": assignment.get("status"),
        "teaching_revision": (
            (assignment.get("teaching_snapshot") or {}).get("revision")),
        "teaching_fingerprint": (
            (assignment.get("teaching_snapshot") or {}).get("fingerprint")),
        "deliverables": copy.deepcopy(
            assignment.get("deliverables") or []),
        "sources": copy.deepcopy(assignment.get("sources") or []),
        "authorized_actions": list(assignment.get("authorized_actions") or []),
        "budget": copy.deepcopy(assignment.get("budget") or {}),
        "steps": steps,
        "created_at": assignment.get("created_at"),
        "updated_at": assignment.get("updated_at"),
        "completed_at": assignment.get("completed_at"),
    }
