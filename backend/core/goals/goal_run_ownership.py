"""Trusted driver ownership for a GoalRun.

A task-lifecycle run stores an assignment read model in
``GoalRun.parameters["task_lifecycle"]`` and a non-executable ``operation``
plan projection beside it. That projection belongs to the assignment executor;
the native goal loop must never execute it as canvas work.

Ownership cannot come from the presence of a caller-supplied parameters key:
public create/update callers may send any JSON. It comes from a durable
server-side association written only by the trusted lifecycle:

- ``TaskLifecycle.create_task`` appends a ``task_created`` decision-log entry
  after creating the run; and
- ``AssignmentExecutor.attach_assignment`` appends ``assignment_attached``
  when an assignment is attached to an existing run.

Both markers are written through the service append path, never accepted from
HTTP input. A caller can still shape a projection plan (native execution is
inert for unknown/projection kinds), but it cannot manufacture ownership.
"""
from __future__ import annotations

from typing import Any, Mapping

# Decision-log kinds written by trusted lifecycle entry points.
ASSIGNMENT_OWNER_LOG_KINDS = frozenset({
    "task_created",
    "assignment_attached",
})


def _value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def is_assignment_owned(run: Any) -> bool:
    """True only for a run created/attached by the trusted task lifecycle."""
    parameters = _value(run, "parameters", {}) or {}
    if not isinstance(parameters, Mapping):
        return False
    lifecycle = parameters.get("task_lifecycle")
    if not isinstance(lifecycle, Mapping):
        return False
    # A real lifecycle record always carries the durable task revision written
    # by TaskLifecycle. This is shape sanity, not the ownership proof.
    if not isinstance(lifecycle.get("task_revision"), Mapping):
        return False
    for entry in _value(run, "decision_log", []) or []:
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("kind") or "").strip() in ASSIGNMENT_OWNER_LOG_KINDS:
            return True
    return False
