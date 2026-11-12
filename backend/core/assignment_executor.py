"""Generic durable assignment executor.

This module composes the EXISTING task lifecycle primitives; it does not
introduce a workflow engine, a business pipeline, or a quote-shaped result
schema. It knows:

- a persisted assignment plan (objective, teaching snapshot, deliverables,
  sources, authorized actions, dependency-ordered steps);
- supported operation classes from ``core.task_lifecycle``;
- a registry of technical adapters (workbook/document reads, deterministic
  calculation, artifact renderers, draft creation, external actions);
- the lifecycle's CAS task writes, database-arbitrated operation keys,
  execution claims, waiting/uncertain states, reconciliation and deliveries.

Business meaning stays in task definitions, teaching and adapter inputs. The
executor never branches on a domain label.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import logging
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from core.action_effects import (
    MUTATING_EFFECTS,
    declares_mutation as _declares_mutation,
    declares_plan_output as _declares_plan_output,
    declares_read_only as _declares_read_only,
)
from core.assignment_readiness import evaluate_step_readiness
from core.assignment_plan import (
    ASSIGNMENT_STATES,
    TERMINAL_ASSIGNMENT_STATES,
    assignment_projection,
    canonical_sha256,
    derive_state,
    downstream_step_ids,
    new_assignment,
    new_teaching_snapshot,
    ready_steps,
    step_by_id,
    validate_assignment,
)
from core.task_lifecycle import (
    TaskApprovalInvalidated,
    TaskLifecycle,
    TaskLifecycleError,
    _approval_payload_hash,
    open_unresolved_questions,
)

AdapterHandler = Callable[[Dict[str, Any], Dict[str, Any]], Any]
AdapterPreparer = Callable[[Dict[str, Any], Dict[str, Any]], Any]

logger = logging.getLogger(__name__)

#: Budget clock schema. Schema 2 credits assignment-level IDLE intervals
#: (periods where no branch can progress) instead of summing per-branch
#: waits. Overlapping waits therefore cannot inflate credited pause time.
IDLE_LEDGER_SCHEMA = 2


class AssignmentError(TaskLifecycleError):
    """A plan/execution error that leaves the durable assignment intact."""


class NeedsContext(AssignmentError):
    """The adapter determined that a material fact is missing."""

    def __init__(self, gap: Dict[str, Any]):
        self.gap = dict(gap or {})
        super().__init__(self.gap.get("question") or "context required")


class WaitingForExternal(AssignmentError):
    """The adapter is waiting for an authorized external response/timer."""

    def __init__(self, waiting: Dict[str, Any]):
        self.waiting = dict(waiting or {})
        super().__init__(self.waiting.get("detail") or "waiting for external")


class ExternalOutcomeUnknown(AssignmentError):
    """The provider may have accepted the effect before the call failed."""

    def __init__(self, reason: str, evidence: str = ""):
        self.reason = str(reason or "provider outcome unknown")
        self.evidence = str(evidence or "")
        self.effect_possible = True
        super().__init__(self.reason)


class ExternalOutcomeNotApplied(AssignmentError):
    """A trusted adapter established that no external effect was possible.

    Generic exceptions after an external dispatch are UNKNOWN, never
    "failed before effect": the call may have landed. Only this explicit
    contract (or ``effect_possible=False``) permits a safe retry.
    """

    def __init__(self, reason: str = "dispatch refused before effect"):
        self.effect_possible = False
        super().__init__(reason)


class _ExternalReplyStop(Exception):
    """Abort one external-reply CAS without writing.

    The callback raises this after re-reading the fresh assignment and
    deciding that the reply is an idempotent replay, an identity conflict, a
    terminal refusal, or unmatched. Carrying the public result out this way
    keeps all checks inside the lifecycle CAS while avoiding a task-version
    bump, decision entry, or effect for a refused/replayed reply.
    """

    def __init__(self, result: Dict[str, Any]):
        self.result = dict(result or {})
        super().__init__(
            str(self.result.get("message") or self.result.get("status") or
                "external reply stopped"))


@dataclass
class AdapterDefinition:
    name: str
    handler: AdapterHandler
    prepare: Optional[AdapterPreparer] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, AdapterDefinition] = {}

    def register(
        self,
        name: str,
        handler: AdapterHandler,
        *,
        prepare: Optional[AdapterPreparer] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AdapterDefinition:
        if not re.match(r"^[a-z][a-z0-9_.-]{0,80}$", str(name or "")):
            raise AssignmentError(f"invalid adapter name '{name}'")
        definition = AdapterDefinition(
            name=str(name), handler=handler, prepare=prepare,
            description=description or getattr(handler, "__doc__", "") or "",
            metadata=dict(metadata or {}))
        self._adapters[str(name)] = definition
        return definition

    def get(self, name: str) -> Optional[AdapterDefinition]:
        return self._adapters.get(str(name))

    def list_names(self) -> List[str]:
        return sorted(self._adapters)

    def clone(self) -> "AdapterRegistry":
        registry = AdapterRegistry()
        registry._adapters = dict(self._adapters)
        return registry


#: Process-wide default registry. Deployments may register action adapters
#: (email dispatch, provider reads) at startup; tests clone it and add
#: controlled adapters without touching production wiring.
default_adapter_registry = AdapterRegistry()


def register_assignment_adapter(
    name: str,
    *,
    prepare: Optional[AdapterPreparer] = None,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    registry: Optional[AdapterRegistry] = None,
):
    target = registry or default_adapter_registry

    def decorator(func: AdapterHandler) -> AdapterHandler:
        target.register(name, func, prepare=prepare, description=description,
                        metadata=metadata)
        return func

    return decorator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


#: One-shot bounded wakes for accepted-evidence claims whose recorded owner
#: cannot finish them (crashed after claiming, before continuation). Keyed by
#: run id so concurrent boots do not pile up duplicate waits. This is an
#: in-memory scheduling aid, NOT durable authority: the lease/marker on the
#: assignment remains the only claim truth, and a restarted process reschedules
#: from that marker. It is pruned as each task completes.
_EVIDENCE_RECOVERY_WAKES: Dict[str, "asyncio.Task[Any]"] = {}


def pending_evidence_recovery_wakes() -> List[str]:
    """Run ids with a live bounded recovery wake in this process."""
    return sorted(
        run_id for run_id, task in _EVIDENCE_RECOVERY_WAKES.items()
        if task is not None and not task.done())


async def await_evidence_recovery_wakes(timeout: float = 0.0) -> None:
    """Wait for bounded recovery wakes (startup-owner/test drain point).

    Production starts these as background work and never awaits them; the
    actual-process acceptance runs the startup owner in a long-lived child and
    needs an explicit boundary to observe the wake. Tasks from a different
    event loop are ignored rather than awaited across loops.
    """
    loop = asyncio.get_running_loop()
    tasks = [
        task for task in list(_EVIDENCE_RECOVERY_WAKES.values())
        if task is not None and not task.done() and task.get_loop() is loop
    ]
    if not tasks:
        return
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=(timeout if timeout > 0 else None))
    except asyncio.TimeoutError:
        return


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded(value: Any, limit: int = 500) -> str:
    return str(value or "")[:limit]


def _gap_binding_key(value: Any) -> str:
    """Stable identity for a durable obligation.

    Legacy gaps have no key and keep the original step/concept dedupe. A
    line-scoped quote gap carries one so two lines or two missing fields in
    the same step cannot collapse into a single question.
    """
    if not isinstance(value, dict):
        return ""
    inputs = value.get("inputs")
    key = value.get("binding_key")
    if not key and isinstance(inputs, dict):
        key = inputs.get("binding_key")
    return str(key or "").strip()


async def _invoke(func: Callable[..., Any], *args: Any) -> Any:
    result = func(*args)
    if inspect.isawaitable(result):
        return await result
    return result


def _authorization_revision(assignment: Dict[str, Any]) -> str:
    """What an approval is bound to beyond the payload itself.

    Plan revision, effective teaching and authorized actions. Appending
    evidence does not invalidate an approval; changing the plan, teaching or
    authority does.
    """
    snapshot = assignment.get("teaching_snapshot") or {}
    return canonical_sha256({
        "assignment_id": assignment.get("assignment_id"),
        "plan_revision": assignment.get("plan_revision"),
        "teaching_fingerprint": snapshot.get("fingerprint"),
        "authorized_actions": assignment.get("authorized_actions") or [],
        "standing_authority": assignment.get("standing_authority") or {},
        "workspace_id": assignment.get("workspace_id"),
    })[:32]


def _operation_id_for_step(
    record: Dict[str, Any], step: Dict[str, Any],
    plan_revision: Optional[int] = None,
) -> Optional[str]:
    direct = step.get("operation_id")
    if direct:
        for operation in record.get("operations") or []:
            if operation.get("operation_id") == direct:
                return direct
    assignment_id = (record.get("assignment") or {}).get("assignment_id")
    if plan_revision is None:
        plan_revision = (record.get("assignment") or {}).get(
            "plan_revision")
    status = step.get("status")
    if status == "pending":
        allowed = ("pending", "approved", "awaiting_approval")
    elif status == "running":
        allowed = ("pending", "running", "applied", "approved",
                   "awaiting_approval")
    else:
        allowed = ()
    for operation in reversed(record.get("operations") or []):
        if (operation.get("assignment_id") == assignment_id
                and operation.get("step_id") == step.get("step_id")
                and operation.get("status") in allowed
                and (plan_revision is None
                     or operation.get("plan_revision") == plan_revision)):
            return operation.get("operation_id")
    return None


def _operation_by_id(record: Dict[str, Any], operation_id: str) -> Optional[Dict[str, Any]]:
    for operation in record.get("operations") or []:
        if operation.get("operation_id") == operation_id:
            return operation
    return None


def _summarize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    summary = result.get("summary")
    if summary:
        return {"summary": _bounded(summary, 500)}
    for key in ("value", "message", "provider_ref", "path"):
        if result.get(key) not in (None, ""):
            return {"summary": _bounded(result[key], 500)}
    return {"summary": "step completed"}


class ExecutablePayloadTooLarge(ValueError):
    """An inline executable value exceeds the supported transfer bound."""


#: Fields whose contents are consumed by downstream work. They are never
#: silently sliced; an oversized value refuses explicitly.
_EXECUTABLE_FIELDS = frozenset({
    "rows", "items", "line_items", "records", "data", "payload", "payloads",
    "content", "content_b64", "documents", "attachments", "evidence",
    "provider_receipt", "read_receipt", "receipt", "verification", "conflicts",
})
_MAX_EXECUTABLE_STRING = 2_000_000
_MAX_EXECUTABLE_LIST = 10_000
_MAX_EXECUTABLE_DEPTH = 14
_MAX_EXECUTABLE_BYTES = 4 * 1024 * 1024
_MAX_EXECUTABLE_NODES = 100_000
_MAX_EXECUTABLE_ENTRIES = 100_000
_MAX_EXECUTABLE_KEY_CHARS = 512


class _SerializationBudget:
    """One budget shared by every node of an executable result."""

    def __init__(self) -> None:
        self.bytes = 0
        self.nodes = 0
        self.entries = 0

    def node(self) -> None:
        self.nodes += 1
        if self.nodes > _MAX_EXECUTABLE_NODES:
            raise ExecutablePayloadTooLarge(
                f"executable payload has more than "
                f"{_MAX_EXECUTABLE_NODES} nodes")

    def entry(self) -> None:
        self.entries += 1
        if self.entries > _MAX_EXECUTABLE_ENTRIES:
            raise ExecutablePayloadTooLarge(
                f"executable payload has more than "
                f"{_MAX_EXECUTABLE_ENTRIES} dictionary/list entries")

    def text(self, value: str, *, key: bool = False) -> None:
        if key and len(value) > _MAX_EXECUTABLE_KEY_CHARS:
            raise ExecutablePayloadTooLarge(
                f"executable dictionary key has {len(value)} characters; "
                f"limit is {_MAX_EXECUTABLE_KEY_CHARS}")
        self.bytes += len(value.encode("utf-8"))
        if self.bytes > _MAX_EXECUTABLE_BYTES:
            raise ExecutablePayloadTooLarge(
                f"executable payload exceeds {_MAX_EXECUTABLE_BYTES} UTF-8 "
                "bytes")


#: Persistence stores lifecycle JSON with the stdlib defaults:
#: ASCII-escaped strings and the default ``", "`` / ``": "`` separators.
#: Measuring this exact representation makes the bound hard for the bytes
#: SQLAlchemy actually writes, including escaping and punctuation.
_PERSISTENCE_JSON_KWARGS = {
    "ensure_ascii": True,
    "separators": (", ", ": "),
    "allow_nan": False,
}


def _check_serialized_size(value: Any) -> None:
    """Enforce the byte bound on the persisted executable representation.

    The node/text budget catches most payloads, but JSON punctuation, quoting,
    escaping and separators also consume bytes. A value just under the text
    budget can still exceed 4 MiB once serialized, so the final transferable
    form is measured with the persistence encoder. ``iterencode`` stops as
    soon as the bound is crossed rather than building the whole document.
    """
    encoder = json.JSONEncoder(**_PERSISTENCE_JSON_KWARGS)
    size = 0
    try:
        for chunk in encoder.iterencode(value):
            size += len(chunk.encode("utf-8"))
            if size > _MAX_EXECUTABLE_BYTES:
                raise ExecutablePayloadTooLarge(
                    "serialized executable payload exceeds "
                    f"{_MAX_EXECUTABLE_BYTES} UTF-8 bytes")
    except ExecutablePayloadTooLarge:
        raise
    except (TypeError, ValueError) as exc:
        raise ExecutablePayloadTooLarge(
            f"executable payload is not valid JSON: {exc}") from exc


def _json_safe(
    value: Any, *, depth: int = 0, executable: bool = False,
    budget: Optional[_SerializationBudget] = None,
) -> Any:
    """Serialize a result, preserving executable data under one budget.

    Diagnostics are bounded for lifecycle readability. Executable fields
    (rows, bytes, receipts) are preserved in full or refused explicitly; the
    aggregate budget counts every key, value and node, and the final
    serialized UTF-8 JSON is measured before the value can be stored.
    """
    finalize = budget is None and executable
    if finalize:
        budget = _SerializationBudget()
    result = _json_safe_inner(
        value, depth=depth, executable=executable, budget=budget)
    if finalize:
        _check_serialized_size(result)
    return result


def _json_safe_inner(
    value: Any, *, depth: int = 0, executable: bool = False,
    budget: Optional[_SerializationBudget] = None,
) -> Any:
    if depth > (_MAX_EXECUTABLE_DEPTH if executable else 6):
        if executable:
            raise ExecutablePayloadTooLarge(
                "executable payload exceeds the supported nesting depth")
        return "…"
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        if budget:
            budget.node()
        for key, item in value.items():
            key_text = str(key)
            if budget:
                budget.entry()
                budget.text(key_text, key=True)
            child_executable = executable or (
                key_text.strip().lower() in _EXECUTABLE_FIELDS)
            result[key_text if executable else key_text[:80]] = _json_safe_inner(
                item, depth=depth + 1, executable=child_executable,
                budget=budget)
        return result
    if isinstance(value, (list, tuple)):
        if budget:
            budget.node()
        if executable and len(value) > _MAX_EXECUTABLE_LIST:
            raise ExecutablePayloadTooLarge(
                f"executable list has {len(value)} items; limit is "
                f"{_MAX_EXECUTABLE_LIST}")
        limit = len(value) if executable else min(len(value), 80)
        items = []
        for item in list(value)[:limit]:
            if budget:
                budget.entry()
            items.append(_json_safe_inner(
                item, depth=depth + 1, executable=executable,
                budget=budget))
        return items
    if isinstance(value, float) and not math.isfinite(value):
        raise ExecutablePayloadTooLarge(
            "executable payload contains a non-finite number")
    if value is None or isinstance(value, (int, float, bool)):
        if budget:
            budget.node()
            budget.text(str(value))
        return value
    text = str(value)
    if budget:
        budget.node()
        budget.text(text)
        if len(text) > _MAX_EXECUTABLE_STRING:
            raise ExecutablePayloadTooLarge(
                f"executable string has {len(text)} characters; limit is "
                f"{_MAX_EXECUTABLE_STRING}")
        return text
    if executable:
        if len(text) > _MAX_EXECUTABLE_STRING:
            raise ExecutablePayloadTooLarge(
                f"executable string has {len(text)} characters; limit is "
                f"{_MAX_EXECUTABLE_STRING}")
        return text
    return text[:2000]


def _filter_records(
    records: List[Dict[str, Any]],
    filters: Any,
) -> List[Dict[str, Any]]:
    """Apply the same bounded predicates to in-memory records."""
    for predicate in filters or []:
        if not isinstance(predicate, dict):
            continue
        field = str(predicate.get("column") or "")
        operator = str(predicate.get("operator") or "eq")
        expected = predicate.get("value")

        def _matches(actual: Any) -> bool:
            if operator == "eq":
                return str(actual) == str(expected)
            if operator == "neq":
                return str(actual) != str(expected)
            if operator == "contains":
                return str(expected).lower() in str(actual).lower()
            if operator == "in":
                return actual in (expected or [])
            try:
                left = float(actual)
                right = float(expected)
            except (TypeError, ValueError):
                return False
            if operator == "gt":
                return left > right
            if operator == "gte":
                return left >= right
            if operator == "lt":
                return left < right
            if operator == "lte":
                return left <= right
            return False

        records = [record for record in records
                   if _matches(record.get(field))]
    return records


def _sheet_row(value: Any) -> Optional[int]:
    try:
        row = int(value)
    except (TypeError, ValueError):
        return None
    return row if row >= 2 else None


def _formula_rows(formulas: Dict[str, str], rows: set) -> Dict[str, str]:
    selected: Dict[str, str] = {}
    for cell, formula in (formulas or {}).items():
        match = re.match(r"^[A-Za-z]+(\d+)$", str(cell))
        if not match:
            continue
        if int(match.group(1)) in rows:
            selected[str(cell)] = str(formula)
        if len(selected) >= 500:
            break
    return selected


def _resource_gap(exc: Any, binding: Dict[str, Any]) -> "NeedsContext":
    code = str(getattr(exc, "code", "") or "resource_unavailable")
    message = str(exc)
    access_codes = {
        "source_permission_revoked", "source_disconnected", "unauthenticated",
        "workspace_scope_required", "resource_workspace_mismatch",
        "filesystem_path_not_allowed",
    }
    version_codes = {
        "stale_source_version", "inactive", "ambiguous_resource",
        "materialization_incomplete",
    }
    if code in access_codes:
        state = ("source_access_revoked" if "revoked" in code
                 else "source_access_required")
        question = (
            "The authorized source is no longer accessible. Reconnect or "
            "restore the grant, then retry.")
        resume_on = "source_reauthorized"
        party = "source owner"
    elif code in version_codes:
        state = "source_version_changed"
        question = (
            "The active source version changed or is incomplete. Confirm the "
            "current authorized version, then retry.")
        resume_on = "source_refreshed"
        party = "source owner"
    else:
        state = "source_unavailable"
        question = "The authorized source is unavailable. Restore it, then retry."
        resume_on = "resource_restored"
        party = "source owner"
    return NeedsContext({
        "concept": "source_access",
        "reason": f"{code}: {message}",
        "question": question,
        "checked_evidence": [
            f"resource={binding.get('dataset_name') or binding.get('resource_id')}",
            f"sheet={binding.get('sheet')}",
            f"version={str(binding.get('source_version') or '')[:12]}",
            code,
        ],
        "next_retrieval": "recheck source access and active version",
        "kind": "missing_evidence",
        "waiting": {
            "state": state,
            "party": party,
            "resume_on": resume_on,
            "since": _utc_now_iso(),
            "detail": message[:500],
            "code": code,
        },
    })


def _recheck_binding(
    binding: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve the typed binding again inside the authenticated scope."""
    if not isinstance(binding, dict) or not binding:
        raise NeedsContext({
            "concept": "resource_binding",
            "reason": "the assignment step has no typed resource binding",
            "question": "Which authorized resource should I read?",
            "kind": "missing_evidence",
        })
    employee_id = str(context.get("employee_id") or "")
    scope = dict(binding.get("access_scope") or {})
    # The binding was created from the authenticated requester's source grant.
    # A supervisor may assign the work to another employee, so the read must
    # recheck the requester's still-active grant, not the assignee's identity.
    reader_id = str(scope.get("user_id") or employee_id)
    if not reader_id:
        raise NeedsContext({
            "concept": "authenticated_principal",
            "reason": "the step has no authenticated employee identity",
            "question": "Who is authorized to read this resource?",
            "kind": "business_decision",
        })
    from core.assignment_resources import (
        AssignmentResourceError,
        recheck_resource_access,
    )
    from core.database import get_db_session
    from core.models import User

    with get_db_session() as db:
        user = db.query(User).filter(User.id == reader_id).first()
        if user is None or not bool(getattr(user, "is_active", True)):
            raise NeedsContext({
                "concept": "authenticated_principal",
                "reason": "the authorized reader identity is missing or inactive",
                "question": "Re-authenticate before reading this resource.",
                "kind": "missing_evidence",
                "waiting": {
                    "state": "source_access_required",
                    "party": "source owner",
                    "resume_on": "authentication",
                    "since": _utc_now_iso(),
                    "detail": reader_id,
                },
            })
        requested_workspace = str(context.get("workspace_id") or "")
        requested_tenant = str(context.get("tenant_id") or "")
        reader_workspace = str(user.workspace_id or "default")
        reader_tenant = str(user.tenant_id or "default")
        if ((requested_workspace and reader_workspace != requested_workspace)
                or (requested_tenant and reader_tenant != requested_tenant)):
            raise NeedsContext({
                "concept": "source_access",
                "reason": (
                    "the authorized reader's scope does not match this "
                    "assignment workspace/tenant"),
                "question": (
                    "The source authorization is outside this assignment's "
                    "scope. Which authorized grant should be used?"),
                "kind": "missing_evidence",
                "waiting": {
                    "state": "source_access_required",
                    "party": "source owner",
                    "resume_on": "source_reauthorized",
                    "since": _utc_now_iso(),
                    "detail": reader_id,
                },
            })
        try:
            return recheck_resource_access(db, user, binding)
        except AssignmentResourceError as exc:
            raise _resource_gap(exc, binding)


def _connected_source_block(
    resolved: Dict[str, Any],
    binding: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "resource_id": resolved.get("resource_id")
        or binding.get("resource_id"),
        "dataset_name": resolved.get("dataset_name")
        or binding.get("dataset_name"),
        "file_name": resolved.get("original_file_name")
        or binding.get("original_file_name"),
        "sheet": resolved.get("sheet") or binding.get("sheet"),
        "source_version": resolved.get("source_version")
        or binding.get("source_version"),
        "representation": resolved.get("representation")
        or binding.get("representation"),
        "coverage": dict(resolved.get("coverage")
                         or binding.get("coverage") or {}),
        "workspace_id": resolved.get("workspace_id"),
        "tenant_id": resolved.get("tenant_id"),
    }


def _source_label(source: Dict[str, Any]) -> str:
    file_name = str(source.get("file_name")
                    or source.get("dataset_name")
                    or source.get("resource_id") or "authorized source")
    sheet = str(source.get("sheet") or "").strip()
    return f"{file_name} / {sheet}" if sheet else file_name


def _evidence_rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = result.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(
        rows, list) else []


def _collect_evidence(
    context: Dict[str, Any],
    only_step_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    facts: List[Dict[str, Any]] = []
    row_sets: List[Dict[str, Any]] = []
    labels: List[str] = []
    selected = {
        str(item) for item in (only_step_ids or []) if str(item).strip()}

    def add_label(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in labels:
            labels.append(text)

    for source in context.get("sources") or []:
        if not isinstance(source, dict):
            continue
        binding = source.get("binding") if isinstance(
            source.get("binding"), dict) else source
        add_label(binding.get("dataset_name"))
        add_label(binding.get("original_file_name"))
        add_label(binding.get("sheet"))
        add_label(binding.get("resource_id"))

    for step_id, result in (context.get("previous_results") or {}).items():
        if not isinstance(result, dict):
            continue
        if selected and str(step_id) not in selected:
            continue
        if result.get("expression") and result.get("value") is not None:
            facts.append({
                "step_id": step_id,
                "label": (
                    f"{result.get('expression')} = {result.get('value')}"
                    f" {result.get('unit') or ''}".strip()),
                "value": result.get("value"),
                "unit": result.get("unit") or "",
                "required": True,
            })
        elif result.get("operation") and result.get("subtotals"):
            for currency, item in (result.get("subtotals") or {}).items():
                unit = "" if currency == "(unstated)" else str(currency)
                facts.append({
                    "step_id": step_id,
                    "label": (
                        f"{result.get('operation')} of "
                        f"{result.get('measure') or 'rows'}: "
                        f"{item.get('value')} {unit}".strip()),
                    "value": item.get("value"),
                    "unit": unit,
                    "required": True,
                })
        elif result.get("operation") and result.get("value") is not None:
            facts.append({
                "step_id": step_id,
                "label": (
                    f"{result.get('operation')} of "
                    f"{result.get('measure') or 'rows'}: "
                    f"{result.get('value')} {result.get('unit') or ''}".strip()),
                "value": result.get("value"),
                "unit": result.get("unit") or "",
                "required": True,
            })
        elif result.get("value") is not None and not result.get("text"):
            facts.append({
                "step_id": step_id,
                "label": (
                    f"{result.get('summary') or 'result'}: "
                    f"{result.get('value')} {result.get('unit') or ''}".strip()),
                "value": result.get("value"),
                "unit": result.get("unit") or "",
                "required": False,
            })
        rows = _evidence_rows(result)
        if not rows:
            text = str(result.get("text") or "")
            if text.strip():
                rows = [
                    {"excerpt": line.strip()}
                    for line in text.splitlines() if line.strip()
                ][:40]
        if rows:
            row_label = str(result.get("source_label") or "").strip()
            if not row_label:
                for evidence in result.get("evidence") or []:
                    if not isinstance(evidence, dict):
                        continue
                    path = str(evidence.get("path") or "").strip()
                    if path:
                        row_label = Path(path).name
                        break
            row_sets.append({
                "step_id": step_id,
                "rows": rows,
                "schema": list(result.get("schema") or []),
                "source_label": row_label,
                "source": result.get("source") or {},
            })
        for evidence in result.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            add_label(evidence.get("dataset_name"))
            add_label(evidence.get("file_name"))
            add_label(evidence.get("sheet"))
            path = str(evidence.get("path") or "").strip()
            if path and evidence.get("kind") not in (
                    "connected_dataset", "connected_aggregate"):
                add_label(Path(path).name)
        source = result.get("source") if isinstance(
            result.get("source"), dict) else {}
        add_label(source.get("dataset_name"))
        add_label(source.get("file_name"))
        add_label(source.get("sheet"))
        add_label(result.get("source_label"))

    return {"facts": facts, "row_sets": row_sets, "labels": labels}


def _row_columns(rows: List[Dict[str, Any]]) -> List[str]:
    columns: List[str] = []
    for row in rows[:1]:
        for key in row:
            if str(key) == "__sheet_row":
                continue
            columns.append(str(key))
    return columns[:8]


# Human-facing column labels for the values the typed adapters emit. Unknown
# columns keep their source header so an unfamiliar source is never relabelled
# silently.
_DOCUMENT_COLUMN_LABELS = {
    "item_id": "Item",
    "sku": "Item",
    "description": "Description",
    "quantity": "Qty",
    "unit": "Unit",
    "pack_size": "Pack size",
    "unit_price": "Unit price",
    "price_basis": "Price basis",
    "currency": "Currency",
    "gross": "Gross",
    "discount_rate": "Discount rate",
    "discount_amount": "Discount",
    "net": "Net",
    "received_quantity": "Received qty",
    "invoice_quantity": "Invoice qty",
    "value": "Value",
}
# Internal lineage stays in the audit section instead of the business table.
_DOCUMENT_AUDIT_COLUMNS = {
    "source_ref", "evidence", "discount_rule", "resource_id",
    "source_version", "version", "step_id"}
_DOCUMENT_SCALAR_TYPES = (str, int, float, bool)


_DOCUMENT_COLUMN_PRIORITY = (
    "item_id", "sku", "description", "quantity", "unit", "unit_price",
    "discount_amount", "net", "currency", "price_basis", "gross",
    "discount_rate", "pack_size", "received_quantity", "invoice_quantity",
    "value",
)


def _document_columns(rows: List[Dict[str, Any]]) -> List[str]:
    available: List[str] = []
    for key, value in (rows[0] if rows else {}).items():
        name = str(key)
        if name == "__sheet_row" or name in _DOCUMENT_AUDIT_COLUMNS:
            continue
        if value is not None and not isinstance(
                value, _DOCUMENT_SCALAR_TYPES):
            continue
        available.append(name)
    ordered = [
        column for column in _DOCUMENT_COLUMN_PRIORITY if column in available]
    ordered += [
        column for column in available if column not in ordered]
    return ordered[:8]


def _row_set_label(entry: Dict[str, Any]) -> str:
    label = str(entry.get("source_label") or "").strip()
    if label:
        return label
    source = entry.get("source") if isinstance(
        entry.get("source"), dict) else {}
    return str(source.get("file_name") or source.get("dataset_name")
               or entry.get("step_id") or "authorized source")


def _compose_evidence_content(
    kind: str,
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    only = inputs.get("result_step_ids")
    evidence = _collect_evidence(
        context, only if isinstance(only, list) else None)
    facts = evidence["facts"]
    row_sets = evidence["row_sets"]
    labels = evidence["labels"]
    if not facts and not row_sets:
        return ""
    title = str(inputs.get("title") or context.get("objective")
                or "Assignment result")[:200]
    objective = str(context.get("objective") or "").strip()
    if kind == "presentation":
        lines = [f"Slide 1: Overview", f"- {objective or title}"]
        slide = 2
        if facts:
            lines += ["", f"Slide {slide}: Result"]
            lines += [f"- {fact['label']}" for fact in facts[:5]]
            slide += 1
        if row_sets:
            lines += ["", f"Slide {slide}: Findings"]
            for entry in row_sets[:3]:
                lines.append(f"- {_row_set_label(entry)}")
                columns = _row_columns(entry["rows"])
                for row in entry["rows"][:4]:
                    cells = " | ".join(
                        str(row.get(column, "") or "") for column in columns)
                    row_number = row.get("__sheet_row")
                    prefix = f"row {row_number}: " if row_number else ""
                    lines.append(f"  - {prefix}{cells}")
            slide += 1
        lines += ["", f"Slide {slide}: Sources"]
        lines += [f"- {label}" for label in (labels[:8] or ["authorized source"])]
        return "\n".join(lines)

    lines = [f"# {title}", "", "## Objective", objective or title, "",
             "## Summary"]
    if facts:
        lines += [f"- {fact['label']}" for fact in facts]
    else:
        lines += ["- See the retrieved records below."]
    if row_sets:
        lines += ["", "## Findings"]
        for entry in row_sets[:3]:
            rows = entry["rows"]
            columns = _document_columns(rows)
            lines += ["", f"### {_row_set_label(entry)}"]
            if columns:
                lines.append("| Row | " + " | ".join(
                    _DOCUMENT_COLUMN_LABELS.get(column, column)
                    for column in columns) + " |")
                lines.append("|" + "---|" * (len(columns) + 1))
                for row in rows[:10]:
                    values = [
                        str(row.get(column, "") or "").replace("|", "/")
                        for column in columns
                    ]
                    lines.append(
                        "| " + str(row.get("__sheet_row") or "") + " | "
                        + " | ".join(values) + " |")
            else:
                lines += [f"- {row}" for row in rows[:10]]
    lines += ["", "## Sources"]
    lines += [f"- {label}" for label in (labels[:12] or ["authorized source"])]
    audit = _document_audit_lines(facts, row_sets)
    if audit:
        lines += ["", "## Audit"]
        lines += audit
    return "\n".join(lines)


def _document_audit_lines(
    facts: Sequence[Dict[str, Any]],
    row_sets: Sequence[Dict[str, Any]],
) -> List[str]:
    """Technical lineage kept out of the human-facing tables."""
    lines: List[str] = []
    for fact in facts[:8]:
        step_id = str(fact.get("step_id") or "").strip()
        if step_id:
            lines.append(f"- Calculation step: {step_id}")
    for entry in row_sets[:3]:
        step_id = str(entry.get("step_id") or "").strip()
        rows = entry.get("rows") or []
        summary = f"- Row set: {step_id or 'authorized source'}"
        if entry.get("source_label"):
            summary += f" · {entry['source_label']}"
        summary += f" · {len(rows)} row(s)"
        lines.append(summary)
        for row in rows[:10]:
            ref = row.get("source_ref") if isinstance(
                row.get("source_ref"), dict) else {}
            evidence = row.get("evidence") if isinstance(
                row.get("evidence"), list) else []
            parts: List[str] = []
            item = str(row.get("item_id") or "").strip()
            if item:
                parts.append(f"item={item}")
            if ref.get("resource_id"):
                parts.append(f"resource={ref['resource_id']}")
            if ref.get("source_version"):
                parts.append(f"version={ref['source_version']}")
            for entry_ref in evidence[:2]:
                if not isinstance(entry_ref, dict):
                    continue
                for key in ("row", "sheet", "resource_id", "source_version"):
                    if entry_ref.get(key) in (None, ""):
                        continue
                    parts.append(f"{key}={entry_ref[key]}")
            if parts:
                lines.append(f"  - " + " · ".join(parts))
    return lines


def _compose_evidence_text(
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    only = inputs.get("result_step_ids")
    evidence = _collect_evidence(
        context, only if isinstance(only, list) else None)
    if not evidence["facts"] and not evidence["row_sets"]:
        return ""
    lines: List[str] = []
    if evidence["facts"]:
        lines.append("Result:")
        lines += [f"- {fact['label']}" for fact in evidence["facts"]]
    if evidence["row_sets"]:
        lines.append("Findings:")
        for entry in evidence["row_sets"][:3]:
            rows = entry["rows"]
            columns = _row_columns(rows)
            lines.append(f"- {_row_set_label(entry)}")
            for row in rows[:10]:
                cells = " | ".join(str(row.get(column, "") or "")
                                   for column in columns)
                row_number = row.get("__sheet_row")
                lines.append(
                    f"  - row {row_number}: {cells}" if row_number
                    else f"  - {cells}")
    lines.append("Sources:")
    lines += [f"- {label}" for label in
              (evidence["labels"][:8] or ["authorized source"])]
    return "\n".join(lines)


def _compose_evidence_rows(
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    only = inputs.get("result_step_ids")
    evidence = _collect_evidence(
        context, only if isinstance(only, list) else None)
    if not evidence["row_sets"]:
        return []
    return list(evidence["row_sets"][0]["rows"])


def _normalized_fact_name(value: Any) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def _is_blank_fact_value(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "null", "n/a", "na", "unknown", "unstated"}


def _fact_resolution_from_records(
    records: Sequence[Dict[str, Any]],
    *,
    fact: str,
    column: str,
    source: Dict[str, Any],
    selected_rows: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    values: List[str] = []
    subjects: List[str] = []
    blank_subjects: List[str] = []
    per_record: List[Dict[str, Any]] = []
    for record in records:
        raw = record.get("value")
        subject = str(record.get("subject") or "record")
        if _is_blank_fact_value(raw):
            blank_subjects.append(subject)
            per_record.append({"subject": subject, "value": None,
                               "blank": True})
        else:
            text = str(raw).strip()
            if text not in values:
                values.append(text)
            subjects.append(subject)
            per_record.append({"subject": subject, "value": text,
                               "blank": False})
    if values and blank_subjects:
        status = "mixed"
    elif values:
        status = "established"
    else:
        status = "missing"
    return {
        "status": status,
        "fact": fact,
        "column": column,
        "values": values,
        "subjects": subjects,
        "blank_subjects": blank_subjects,
        "records": per_record,
        "selected_rows": list(selected_rows or []),
        "source": source,
        "source_version": source.get("source_version"),
    }


def _source_fact_resolution(record: Dict[str, Any], fact: str) -> Dict[str, Any]:
    """Resolve a wait fact through one validated evidence contract.

    Coverage and accepted population are checked before any representation
    is selected. Inline rows must cover the accepted identities exactly and
    must actually carry the fact field. Parquet reads are filtered to the
    accepted identities. Aggregate receipts must name their measure and the
    grouping dimension explicitly; a subtotal key never satisfies an
    unrelated measure. Status is ``missing`` (verified blanks),
    ``established``, ``mixed``, ``incomplete`` or ``unavailable``.
    """
    wanted = _normalized_fact_name(fact)
    if not wanted:
        return {"status": "unknown", "reason": "no_fact", "fact": fact}
    assignment = record.get("assignment") or {}
    for step in assignment.get("steps") or []:
        if str(step.get("status") or "") != "applied":
            continue
        inputs = step.get("inputs") or {}
        binding = inputs.get("resource_binding") or {}
        columns = list(binding.get("columns") or [])
        columns += list(inputs.get("columns") or [])
        result = step.get("result") or {}
        columns += list(result.get("columns") or [])
        # A structured record read (for example an authorized JSON receiving
        # record) carries the fact in one object rather than a column schema.
        # It qualifies only when the fact key is present and the read is not
        # truncated; the subject comes from the record's own identity.
        structured = result.get("data") if isinstance(
            result.get("data"), dict) else {}
        structured_key = next((
            key for key in structured
            if _normalized_fact_name(key) == wanted), None)
        if structured and structured_key is not None:
            if result.get("truncated") is True:
                return {
                    "status": "incomplete",
                    "reason": "accepted_coverage_incomplete",
                    "fact": fact,
                    "source": {
                        "resource_id": binding.get("resource_id"),
                        "dataset_name": binding.get("dataset_name"),
                        "file_name": binding.get("original_file_name"),
                        "source_version": binding.get("source_version"),
                    },
                    "source_version": binding.get("source_version"),
                }
            subject = str(
                structured.get("po_id")
                or structured.get("subject_id")
                or structured.get("id")
                or "record")
            source = {
                "resource_id": binding.get("resource_id"),
                "dataset_name": binding.get("dataset_name"),
                "file_name": binding.get("original_file_name"),
                "sheet": binding.get("sheet"),
                "source_version": binding.get("source_version"),
                "column": str(structured_key),
                "coverage": dict(binding.get("coverage") or {}),
            }
            return _fact_resolution_from_records(
                [{"subject": subject, "value": structured.get(structured_key)}],
                fact=fact, column=str(structured_key), source=source)
        column = next((
            item for item in columns
            if _normalized_fact_name(item) == wanted), None)
        if not column:
            continue
        evidence = [
            item for item in (result.get("evidence") or [])
            if isinstance(item, dict)
        ]
        path = str(binding.get("path") or next(
            (item.get("path") for item in evidence if item.get("path")),
            "") or "")
        coverage = dict(binding.get("coverage") or {})
        if not coverage:
            coverage = dict(next(
                (item.get("coverage") for item in evidence
                 if isinstance(item.get("coverage"), dict)), {}) or {})
        source = {
            "resource_id": binding.get("resource_id"),
            "dataset_name": binding.get("dataset_name"),
            "file_name": binding.get("original_file_name"),
            "sheet": binding.get("sheet"),
            "source_version": binding.get("source_version"),
            "column": column,
            "coverage": coverage,
        }

        # Validate coverage before choosing inline rows, Parquet or aggregate.
        # A receipt that declares itself truncated is incomplete regardless
        # of which representation it carries.
        if (coverage.get("known") is False
                or coverage.get("truncated") is True
                or result.get("truncated") is True):
            return {
                "status": "incomplete",
                "reason": "accepted_coverage_incomplete",
                "fact": fact,
                "column": column,
                "source": source,
                "source_version": source.get("source_version"),
            }

        selected_rows: List[Any] = []
        selected_count = result.get("selected_count")
        source_row_count = coverage.get("source_row_count")
        for item in evidence:
            selected_rows.extend(item.get("sheet_rows") or [])
            if selected_count is None:
                selected_count = item.get("selected_count")
        selected_rows = list(dict.fromkeys(selected_rows))
        if (selected_rows and selected_count is not None
                and len(selected_rows) != int(selected_count)):
            return {
                "status": "incomplete",
                "reason": "accepted_population_truncated",
                "fact": fact,
                "column": column,
                "accepted_count": selected_count,
                "identified_rows": len(selected_rows),
                "source": source,
                "source_version": source.get("source_version"),
            }
        all_rows_selected = (
            not selected_rows
            and selected_count is not None
            and source_row_count is not None
            and int(selected_count) == int(source_row_count)
        )
        accepted_known = bool(selected_rows) or all_rows_selected

        # 1. Inline rows: exact accepted population, and the field must be
        # present in every accepted row (absent is not blank).
        raw_rows = result.get("rows")
        inline_candidate = (
            isinstance(raw_rows, list) and raw_rows
            and any(isinstance(row, dict)
                    and row.get("__sheet_row") is not None
                    for row in raw_rows)
        )
        if inline_candidate:
            if not accepted_known:
                return {
                    "status": "unavailable",
                    "reason": "accepted_row_identities_missing",
                    "fact": fact,
                    "column": column,
                    "source": source,
                    "source_version": source.get("source_version"),
                }
            inline_rows = [row for row in raw_rows if isinstance(row, dict)]
            if selected_rows:
                inline_ids = [
                    str(row.get("__sheet_row"))
                    for row in inline_rows
                    if row.get("__sheet_row") is not None
                ]
                wanted_ids = [str(item) for item in selected_rows]
                if (len(inline_ids) != len(inline_rows)
                        or len(inline_ids) != len(wanted_ids)
                        or set(inline_ids) != set(wanted_ids)):
                    return {
                        "status": "incomplete",
                        "reason": "inline_rows_do_not_match_accepted_population",
                        "fact": fact,
                        "column": column,
                        "accepted_rows": wanted_ids,
                        "inline_rows": inline_ids,
                        "source": source,
                        "source_version": source.get("source_version"),
                    }
            elif len(inline_rows) != int(selected_count or 0):
                return {
                    "status": "incomplete",
                    "reason": "inline_rows_do_not_match_accepted_count",
                    "fact": fact,
                    "column": column,
                    "accepted_count": selected_count,
                    "inline_count": len(inline_rows),
                    "source": source,
                    "source_version": source.get("source_version"),
                }
            if any(column not in row for row in inline_rows):
                return {
                    "status": "incomplete",
                    "reason": "fact_field_absent_in_inline_rows",
                    "fact": fact,
                    "column": column,
                    "source": source,
                    "source_version": source.get("source_version"),
                }
            records = []
            for index, row in enumerate(inline_rows):
                subject = (
                    f"row {row.get('__sheet_row')}"
                    if row.get("__sheet_row") is not None
                    else f"row {index + 1}")
                records.append({"subject": subject, "value": row.get(column)})
            return _fact_resolution_from_records(
                records, fact=fact, column=column, source=source)

        # 2. Parquet: read only the accepted identities. Without identities,
        # do not scan the whole frame.
        if accepted_known:
            if not path or not Path(path).is_file():
                return {
                    "status": "unavailable",
                    "reason": "evidence_path_missing",
                    "fact": fact,
                    "column": column,
                    "source": source,
                    "source_version": source.get("source_version"),
                }
            try:
                import pyarrow.parquet as pq

                read_columns = [column]
                if "__sheet_row" in columns:
                    read_columns.append("__sheet_row")
                table = pq.read_table(path, columns=read_columns)
                frame = table.to_pylist()
            except Exception as exc:  # noqa: BLE001 — unavailable, never blank
                return {
                    "status": "unavailable",
                    "reason": "evidence_read_failed",
                    "detail": str(exc)[:300],
                    "fact": fact,
                    "column": column,
                    "source": source,
                    "source_version": source.get("source_version"),
                }
            if not selected_rows:
                records = []
                for index, row in enumerate(frame):
                    subject = (
                        f"row {row.get('__sheet_row')}"
                        if row.get("__sheet_row") is not None
                        else f"row {index + 1}")
                    records.append({"subject": subject,
                                    "value": row.get(column)})
                return _fact_resolution_from_records(
                    records, fact=fact, column=column, source=source)
            wanted_rows = {str(item) for item in selected_rows}
            records = []
            found_rows = set()
            for index, row in enumerate(frame):
                row_id = row.get("__sheet_row")
                subject = (
                    f"row {row_id}" if row_id is not None
                    else f"row {index + 1}")
                if row_id is None or str(row_id) not in wanted_rows:
                    continue
                found_rows.add(str(row_id))
                records.append({"subject": subject, "value": row.get(column)})
            missing_rows = sorted(wanted_rows - found_rows)
            if missing_rows:
                return {
                    "status": "incomplete",
                    "reason": "accepted_rows_not_found",
                    "missing_subjects": [f"row {item}" for item in missing_rows],
                    "fact": fact,
                    "column": column,
                    "source": source,
                    "source_version": source.get("source_version"),
                }
            return _fact_resolution_from_records(
                records, fact=fact, column=column, source=source,
                selected_rows=selected_rows)

        # 3. Aggregate: require an explicit measure and grouping dimension.
        # A subtotal key alone is not evidence for an unrelated measure, and
        # an aggregate can only establish the fact named by its declared
        # grouping dimension — never an arbitrary matching key.
        measure = str(result.get("measure") or "").strip()
        group_by = str(
            result.get("group_by")
            or result.get("grouping_dimension") or "").strip()
        if not measure:
            return {
                "status": "unavailable",
                "reason": "aggregate_measure_missing",
                "fact": fact,
                "column": column,
                "source": source,
                "source_version": source.get("source_version"),
            }
        if not group_by or _normalized_fact_name(group_by) != wanted:
            return {
                "status": "unavailable",
                "reason": "aggregate_dimension_unbound",
                "fact": fact,
                "column": column,
                "source": source,
                "source_version": source.get("source_version"),
            }
        aggregate_records: List[Dict[str, Any]] = []
        for item in result.get("values") or []:
            if not isinstance(item, dict):
                continue
            fact_key = next((
                key for key in item
                if _normalized_fact_name(key) == wanted), None)
            if fact_key is None:
                continue
            aggregate_records.append({
                "subject": "aggregate",
                "value": item.get(fact_key),
            })
        if (not aggregate_records
                and isinstance(result.get("subtotals"), dict)):
            for key in result["subtotals"]:
                aggregate_records.append({
                    "subject": "aggregate",
                    "value": key,
                })
        if not aggregate_records:
            return {
                "status": "unavailable",
                "reason": "aggregate_dimension_values_missing",
                "fact": fact,
                "column": column,
                "source": source,
                "source_version": source.get("source_version"),
            }
        return _fact_resolution_from_records(
            aggregate_records, fact=fact, column=column, source=source)
    return {"status": "missing", "fact": fact, "reason": "no_bound_column"}


def _canonical_fact_value(value: Any) -> str:
    """Canonical comparison form for one typed or textual fact value."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        try:
            return format(Decimal(str(value)).normalize(), "f")
        except (InvalidOperation, ValueError):
            return str(value).strip()
    text = str(value).strip()
    try:
        return format(Decimal(text).normalize(), "f")
    except (InvalidOperation, ValueError):
        return text


def _response_agrees_fact(
    response: str,
    values: Sequence[str],
    explicit_value: Any = None,
) -> bool:
    """Only an exact typed/canonical value can confirm an established fact.

    Free-form explanatory text is never scanned for a substring. A caller
    that wants to confirm while also explaining must supply ``explicit_value``
    separately; otherwise the whole response must equal one established value.
    """
    candidate = (
        _canonical_fact_value(explicit_value)
        if explicit_value is not None
        else _canonical_fact_value(response)
    )
    if not candidate:
        return False
    established = {
        _canonical_fact_value(value) for value in values
        if _canonical_fact_value(value)
    }
    return candidate in established


_EXTERNAL_REPLY_NUMERIC_TYPES = ("quantity", "amount", "price")


def _external_reply_identity_kind(reply_id: Optional[str]) -> str:
    """Explicit IDs stay exact; omitted IDs use material-derived identity."""
    return "explicit" if reply_id is not None else "legacy"


def _external_reply_receipts(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        dict(item) for item in (step.get("reply_receipts") or [])
        if isinstance(item, dict)
    ]


def _external_reply_material_sha256(
    *,
    correlation_id: str,
    waiting: Dict[str, Any],
    response: Any,
    source: Any,
    evidence: Any,
    value: Any,
) -> str:
    """Digest the complete reply material at one durable wait scope.

    Every caller-supplied semantic field participates. Text, opaque source
    refs, subjects and identities are used exactly as supplied: no case
    folding, whitespace collapse or Unicode rewriting. Only the typed numeric
    value uses the existing canonicalizer, so ``5.0`` and ``5`` compare equal
    when the wait explicitly binds a numeric answer type. The digest is never
    computed from a caller-supplied digest and never from a truncated display
    projection.
    """
    typed_binding = bool(waiting.get("typed_binding"))
    expected_type = str(waiting.get("expected_answer_type") or "")
    reply_value = value if value not in (None, "") else response
    if typed_binding and expected_type in _EXTERNAL_REPLY_NUMERIC_TYPES:
        canonical_value: Any = _canonical_fact_value(reply_value)
    elif value not in (None, ""):
        canonical_value = value
    else:
        canonical_value = response
    material = {
        "correlation_id": str(correlation_id or ""),
        "fact": str(waiting.get("fact") or ""),
        "subject": str(waiting.get("subject") or ""),
        "party": str(waiting.get("party") or ""),
        "typed_binding": typed_binding,
        "expected_answer_type": expected_type,
        "response": str(response if response is not None else ""),
        "source": str(source if source is not None else ""),
        "evidence": str(evidence if evidence is not None else ""),
        "value": canonical_value,
    }
    return canonical_sha256(material)


def _external_reply_scope_matches(
    receipt: Dict[str, Any],
    *,
    correlation_id: str,
    fact: str,
    subject: str,
) -> bool:
    return (
        str(receipt.get("correlation_id") or "") == str(correlation_id or "")
        and str(receipt.get("fact") or "") == str(fact or "")
        and str(receipt.get("subject") or "") == str(subject or "")
    )


def _external_reply_matching_receipts(
    receipts: Sequence[Dict[str, Any]],
    *,
    reply_id: Optional[str],
    digest: str,
    correlation_id: str,
    fact: str,
    subject: str,
) -> List[Dict[str, Any]]:
    kind = _external_reply_identity_kind(reply_id)
    matches: List[Dict[str, Any]] = []
    for receipt in receipts:
        if str(receipt.get("identity_kind") or "") != kind:
            continue
        if kind == "explicit":
            if str(receipt.get("reply_id") or "") != str(reply_id):
                continue
        elif str(receipt.get("material_sha256") or "") != digest:
            continue
        if not _external_reply_scope_matches(
                receipt, correlation_id=correlation_id,
                fact=fact, subject=subject):
            continue
        matches.append(receipt)
    return matches


def _external_reply_receipt(
    *,
    reply_id: Optional[str],
    digest: str,
    correlation_id: str,
    waiting: Dict[str, Any],
    outcome: str,
    reason: str = "",
    message: str = "",
    conflict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    receipt = {
        "reply_id": reply_id if reply_id is not None else "",
        "identity_kind": _external_reply_identity_kind(reply_id),
        "material_sha256": digest,
        "correlation_id": str(correlation_id or ""),
        "fact": str(waiting.get("fact") or ""),
        "subject": str(waiting.get("subject") or ""),
        "outcome": str(outcome or "conflict"),
        "reason": str(reason or ""),
        "message": str(message or ""),
        "at": _utc_now_iso(),
    }
    if conflict is not None:
        receipt["conflict"] = copy.deepcopy(conflict)
    return receipt


def _external_reply_replay_result(
    receipt: Dict[str, Any],
    step: Dict[str, Any],
    assignment_status: str,
    *,
    explicit: bool,
) -> Dict[str, Any]:
    outcome = str(receipt.get("outcome") or "conflict")
    if outcome == "resolved":
        # Explicit identities name the exact replay. Legacy identities keep
        # their historical "resumed" outcome while the job is still in flight
        # (old callers and concurrent tests expect it), but report the settled
        # outcome once the assignment is terminal. The route/event path uses
        # ``replayed`` to skip a second execute/advance in both cases.
        settled_legacy = (
            not explicit
            and assignment_status in TERMINAL_ASSIGNMENT_STATES
        )
        return {
            "status": (
                "already_applied"
                if explicit or settled_legacy else "resumed"),
            "assignment_status": assignment_status,
            "message": (
                "This authorized reply was already accepted for the durable "
                "wait; no second effect or resume was made."),
            "step_id": step.get("step_id"),
            "reply_id": receipt.get("reply_id") or "",
            "material_sha256": receipt.get("material_sha256"),
            "replayed": True,
            "already_applied": True,
        }
    result = {
        "status": outcome,
        "assignment_status": assignment_status,
        "message": receipt.get("message") or (
            "This reply identity already produced this result; the wait is "
            "unchanged."),
        "fact": receipt.get("fact"),
        "step_id": step.get("step_id"),
        "reply_id": receipt.get("reply_id") or "",
        "material_sha256": receipt.get("material_sha256"),
        "replayed": True,
    }
    if receipt.get("conflict") is not None:
        result["conflict"] = copy.deepcopy(receipt["conflict"])
    return result


def _gap_reply_scope(question: Dict[str, Any]) -> Tuple[str, str]:
    """Deterministic question/wait scope for a shared reply receipt.

    A question's concept and affected subjects are durable, structured fields;
    they are never derived from the human question text or from the bounded
    audit string. Subjects are de-duplicated and sorted so a re-derived
    question keeps the same identity.
    """
    fact = str(question.get("concept") or question.get("item") or "")
    subjects = sorted({
        str(subject).strip()
        for subject in (question.get("affected_subjects") or [])
        if str(subject).strip()
    })
    return fact, "|".join(subjects)


def _gap_reply_waiting_projection(question: Dict[str, Any]) -> Dict[str, Any]:
    """The canonical wait projection used by question reply material.

    Question waits are human/external answers, not typed direct-step waits, so
    the projection carries no invented typed binding. It still includes the
    durable party so the same opaque reply id cannot move to another channel.
    """
    fact, subject = _gap_reply_scope(question)
    waiting = question.get("waiting") or {}
    return {
        "fact": fact,
        "subject": subject,
        "party": str(waiting.get("party") or ""),
        "typed_binding": False,
        "expected_answer_type": "",
    }


def _step_for_gap_question(
    assignment: Dict[str, Any], question: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """The backing step for a question, by explicit step_id then gap_ids."""
    question_id = str(question.get("question_id") or "")
    step_id = str(question.get("step_id") or "")
    if step_id:
        step = step_by_id(assignment, step_id)
        if step is not None:
            return step
    if not question_id:
        return None
    for step in assignment.get("steps") or []:
        if question_id in (step.get("gap_ids") or []):
            return step
    return None


def _gap_question_binding_valid(
    record: Dict[str, Any], assignment: Dict[str, Any],
    question: Dict[str, Any], step: Optional[Dict[str, Any]],
) -> bool:
    """A declared binding cannot be replaced by a convenient gap-id match."""
    if not question.get("question_id"):
        return False
    declared_step = str(question.get("step_id") or "")
    actual_step = str((step or {}).get("step_id") or "")
    if declared_step and declared_step != actual_step:
        return False
    declared_operation = str(question.get("source_operation") or "")
    if declared_operation:
        operation = _operation_by_id(record, declared_operation)
        if not operation or not actual_step:
            return False
        if declared_operation != str(_operation_id_for_step(record, step) or ""):
            return False
        if (str(operation.get("assignment_id") or "")
                != str(assignment.get("assignment_id") or "")
                or str(operation.get("step_id") or "") != actual_step):
            return False
    return True


def _find_gap_reply_target(
    record: Dict[str, Any], correlation_id: str,
) -> Optional[Dict[str, Any]]:
    """Find the question (open or settled) bound to a correlation id.

    ``open_unresolved_questions`` intentionally stays open-only. A reply after
    closure still needs its durable receipt for exact replay/conflict checks,
    so this read also consults settled questions and the backing steps' wait
    records. An OPEN question always wins over its older settled twin.
    """
    correlation = str(correlation_id or "")
    if not correlation:
        return None
    questions = [
        dict(item) for item in
        (record.get("task_revision") or {}).get("unresolved") or []
        if isinstance(item, dict)
    ]

    def bound(question):
        waiting = question.get("waiting") or {}
        return str(waiting.get("correlation_id") or "") == correlation

    for question in questions:
        if question.get("status") == "open" and bound(question):
            return question
    for question in questions:
        if bound(question):
            return question
    # Legacy/questions whose waiting projection was cleared still have the
    # correlation on the backing step/receipt.
    assignment = record.get("assignment") or {}
    steps = [
        item for item in (assignment.get("steps") or [])
        if isinstance(item, dict)
    ]
    question_ids = {
        str(question.get("question_id") or "") for question in questions
    }
    for step in steps:
        waiting = step.get("waiting")
        external = step.get("external_response")
        wait_corr = str(
            (waiting or {}).get("correlation_id")
            if isinstance(waiting, dict) else "") or ""
        external_corr = str(
            (external or {}).get("correlation_id")
            if isinstance(external, dict) else "") or ""
        if correlation not in (wait_corr, external_corr):
            continue
        for question in questions:
            question_id = str(question.get("question_id") or "")
            if (question_id and question_id in question_ids
                    and (question_id in (step.get("gap_ids") or [])
                         or str(question.get("step_id") or "")
                         == str(step.get("step_id") or ""))):
                return question
    return None


def _reopen_resolved_gap_steps(
    new_plan: Dict[str, Any],
    question_id: str,
    *,
    mapping: Dict[str, Any],
    mapping_applied: bool,
    confirmed_mapping: Dict[str, Any],
) -> List[str]:
    """Apply a confirmed mapping and reopen the step(s) the gap blocked.

    Kept pure over the supplied plan so both the human /gaps route and the
    /responses settlement re-run it on fresh CAS state with identical rules.
    """
    reopened: List[str] = []
    if mapping_applied:
        missing = str(mapping.get("missing_column") or "")
        for step in new_plan.get("steps") or []:
            step["inputs"] = _replace_mapping_value(
                step.get("inputs") or {}, missing,
                str(confirmed_mapping.get("column") or ""))
        snapshot = dict(new_plan.get("teaching_snapshot") or {})
        mappings = [
            dict(item) for item in (snapshot.get("field_mappings") or [])
            if isinstance(item, dict)
        ]
        concept = str(mapping.get("concept") or missing)
        mappings = [
            item for item in mappings
            if not (str(item.get("concept") or "").lower()
                    == concept.lower()
                    and str(item.get("sheet") or "")
                    == str(mapping.get("sheet") or ""))
        ]
        mappings.append(dict(confirmed_mapping))
        snapshot = new_teaching_snapshot(
            revision=(
                str(snapshot.get("revision") or "untrained")
                + "+map"),
            effective_lesson_ids=snapshot.get("effective_lesson_ids") or [],
            applicable_conditions=snapshot.get("applicable_conditions") or {},
            matched_context=snapshot.get("matched_context") or {},
            unresolved_conditions=snapshot.get("unresolved_conditions") or [],
            conflicting_conditions=snapshot.get("conflicting_conditions") or [],
            field_mappings=mappings,
            source_versions=snapshot.get("source_versions") or {},
            output_requirements=snapshot.get("output_requirements") or {},
            decision_schema=snapshot.get("decision_schema") or [],
            artifact_requirements=snapshot.get("artifact_requirements") or {},
        )
        new_plan["teaching_snapshot"] = snapshot
    for step in new_plan.get("steps") or []:
        if question_id not in (step.get("gap_ids") or []):
            continue
        if step.get("status") in ("applied", "cancelled", "superseded"):
            continue
        step["status"] = "pending"
        step["attempts"] = int(step.get("attempts") or 0) + 1
        step["operation_id"] = None
        step["waiting"] = None
        step["updated_at"] = _utc_now_iso()
        reopened.append(step["step_id"])
    # A confirmed mapping changes evidence/calculation identity: reopen only
    # the affected step and its transitive dependants.
    if mapping_applied:
        roots = [
            step["step_id"] for step in new_plan.get("steps") or []
            if question_id in (step.get("gap_ids") or [])
        ]
        affected = set(downstream_step_ids(new_plan, roots))
        for step in new_plan.get("steps") or []:
            if step.get("step_id") not in affected:
                continue
            if step.get("status") in ("cancelled", "superseded"):
                continue
            step["operation_id"] = None
            step["status"] = "pending"
            step["result"] = None
            step["artifact_revision"] = None
            step["updated_at"] = _utc_now_iso()
            if step["step_id"] not in reopened:
                reopened.append(step["step_id"])
    new_plan["status"] = "planned"
    new_plan["updated_at"] = _utc_now_iso()
    return reopened


def _artifact_text(kind: str, path: str) -> str:
    if kind == "document":
        import docx

        document = docx.Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(part for part in parts if part.strip())
    if kind == "presentation":
        import pptx

        presentation = pptx.Presentation(path)
        parts: List[str] = []
        for slide in presentation.slides:
            for shape in slide.shapes:
                text = getattr(shape, "text", "")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    if kind == "spreadsheet":
        import openpyxl

        workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
        parts = []
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                values = [str(value) for value in row if value not in (None, "")]
                if values:
                    parts.append(" | ".join(values))
        return "\n".join(parts)
    return Path(path).read_text(errors="replace")


def _decimal_value(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _artifact_has_number(text: str, value: Any) -> bool:
    expected = _decimal_value(value)
    if expected is None:
        return str(value).lower() in text.lower()
    for match in re.finditer(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text):
        found = _decimal_value(match.group(0))
        if found is None:
            continue
        if found == expected:
            return True
        try:
            if abs(found - expected) < Decimal("0.000001"):
                return True
        except InvalidOperation:
            continue
    return False


def _label_in_text(label: str, text: str) -> bool:
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", str(label).lower()).split())
    tokens = [token for token in normalized.split()
              if len(token) >= 3 and token not in {
                  "the", "and", "file", "data", "sheet", "source"}]
    if not tokens:
        return False
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _verify_artifact_substance(
    kind: str,
    path: str,
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """A file opening is rendering, not task completion.

    The saved artifact must contain the accepted calculation/record facts and
    an actual source reference. Teaching is considered applied when the
    renderer accepted the resolved format spec (and, for DOCX, the named font
    is present in the saved file).
    """
    text = _artifact_text(kind, path)
    only = inputs.get("result_step_ids")
    evidence = _collect_evidence(
        context, only if isinstance(only, list) else None)
    facts = evidence["facts"]
    row_sets = evidence["row_sets"]
    labels = evidence["labels"]
    checks: Dict[str, Any] = {
        "result_present": False,
        "source_reference_present": not labels,
        "subjects_covered": False,
        "teaching_applied": True,
    }
    if facts:
        required = [fact for fact in facts
                    if bool(fact.get("required", True))]
        if required:
            checks["result_present"] = all(
                _artifact_has_number(text, fact.get("value"))
                for fact in required)
        else:
            checks["result_present"] = any(
                _artifact_has_number(text, fact.get("value"))
                for fact in facts)
        checks["subjects_covered"] = checks["result_present"]
    if row_sets:
        per_set_found: List[bool] = []
        single_values: List[str] = []
        single_found: List[str] = []
        for entry in row_sets:
            values = []
            for row in entry["rows"][:50]:
                for key, value in row.items():
                    if str(key) == "__sheet_row" or value in (None, ""):
                        continue
                    cell = str(value).strip()
                    if len(cell) >= 2:
                        values.append(cell)
            found = [value for value in values
                     if value.lower() in text.lower()]
            per_set_found.append(bool(found))
            single_values.extend(values)
            single_found.extend(found)
        if len(row_sets) > 1:
            checks["subjects_covered"] = all(per_set_found)
            if not facts:
                checks["result_present"] = all(per_set_found)
        elif not facts:
            checks["subjects_covered"] = len(set(single_found)) >= min(
                2, len(set(single_values)))
            checks["result_present"] = bool(single_found)
        else:
            checks["subjects_covered"] = checks["result_present"]
    if labels:
        checks["source_reference_present"] = any(
            _label_in_text(label, text) for label in labels)
    format_spec = _office_format_spec(inputs, context)
    if format_spec:
        checks["teaching_spec_applied"] = True
        font_name = str(format_spec.get("font_name") or "")
        if kind == "document" and font_name:
            try:
                import docx

                document = docx.Document(path)
                checks["teaching_applied"] = (
                    str(document.styles["Normal"].font.name or "")
                    == font_name)
            except Exception:  # noqa: BLE001 — unreadable artifact is a gap
                checks["teaching_applied"] = False
    checks["teaching_revision"] = str(
        (context.get("teaching") or {}).get("revision") or "")
    checks["ok"] = all(bool(checks[key]) for key in (
        "result_present", "source_reference_present", "subjects_covered",
        "teaching_applied"))
    condense = (
        f"result={checks['result_present']} "
        f"source={checks['source_reference_present']} "
        f"subjects={checks['subjects_covered']} "
        f"teaching={checks['teaching_applied']}"
    )
    checks["summary"] = condense
    if not checks["ok"]:
        raise NeedsContext({
            "concept": "artifact_substance",
            "reason": (
                "the saved artifact does not contain the accepted result, "
                "the actual source reference, or a covered subject"),
            "question": (
                "The prepared artifact is not grounded in the accepted "
                "result. Which facts or result should it contain?"),
            "checked_evidence": [condense],
            "next_retrieval": "read the accepted result and regenerate",
            "kind": "missing_evidence",
        })
    return checks


class AssignmentExecutor:
    """Advance one durable assignment plan through supported operations."""

    def __init__(
        self,
        lifecycle: TaskLifecycle,
        adapters: Optional[AdapterRegistry] = None,
        *,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.adapters = adapters or default_adapter_registry.clone()
        self.clock = clock or time.time

    # ------------------------------------------------------------ creation

    def create_assignment(
        self,
        conversation_id: str,
        objective_text: str,
        *,
        assignment: Optional[Dict[str, Any]] = None,
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
        entities: Optional[Sequence[Dict[str, Any]]] = None,
        requested_fields: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Create the task revision and persist the plan beside it."""
        plan = assignment or new_assignment(
            objective=objective_text,
            employee_id=employee_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            teaching_snapshot=teaching_snapshot,
            steps=steps,
            deliverables=deliverables,
            sources=sources,
            authorized_actions=authorized_actions,
            approval_policy=approval_policy,
            completion_criteria=completion_criteria,
            budget=budget,
            provenance=provenance,
        )
        if str(plan.get("objective") or "").strip() != str(objective_text or "").strip():
            raise AssignmentError(
                "the assignment objective must match the accepted objective")
        created = self.lifecycle.create_task(
            conversation_id,
            objective_text,
            entities=list(entities or []),
            requested_fields=list(requested_fields or []),
            authorized_actions=list(plan.get("authorized_actions") or []),
            completion_criteria=list(plan.get("completion_criteria") or []),
            provenance={
                **dict(plan.get("provenance") or {}),
                "assignment_id": plan.get("assignment_id"),
                "teaching_revision": (
                    (plan.get("teaching_snapshot") or {}).get("revision")),
            },
        )
        run_id = created["run_id"]
        plan["provenance"] = {
            **dict(plan.get("provenance") or {}),
            "run_id": run_id,
            "conversation_id": conversation_id,
        }
        self.lifecycle.put_assignment(
            run_id, plan, rationale="assignment planned")
        self._sync_run_plan(run_id, plan)
        return self.lifecycle.get_task(run_id) or {}

    def attach_assignment(
        self, run_id: str, assignment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Attach a plan to an existing task (inspection/import/tests)."""
        self.lifecycle.put_assignment(
            run_id, assignment, rationale="assignment attached")
        # Trusted ownership association: this is the only attach path and it
        # writes through the server-side decision log, never through caller
        # parameters. The native goal loop refuses the resulting projection.
        self.lifecycle.runs.append_decision(run_id, {
            "kind": "assignment_attached",
            "assignment_id": assignment.get("assignment_id"),
            "plan_revision": assignment.get("plan_revision"),
        })
        self._sync_run_plan(run_id, assignment)
        return self.lifecycle.get_task(run_id) or {}

    def _sync_run_plan(
        self, run_id: str, assignment: Dict[str, Any],
    ) -> None:
        """Keep the GoalRun plan linked to the assignment steps.

        The plan is an inspection/continuation projection, not a second
        execution truth: effect status still lives on the operation records.
        """
        from core.goals.goal_plan_validation import (
            validate_assignment_projection,
        )

        plan = []
        for step in assignment.get("steps") or []:
            plan.append({
                "id": step.get("step_id"),
                "kind": "operation",
                "title": step.get("title"),
                "description": step.get("instruction") or step.get("title"),
                "operation_type": step.get("operation_type"),
                "depends_on": list(step.get("depends_on") or []),
                "status": step.get("status"),
            })
        projection_errors = validate_assignment_projection(plan)
        if projection_errors:
            raise AssignmentError(
                "invalid assignment projection: "
                + "; ".join(projection_errors))
        try:
            self.lifecycle.runs.set_plan(run_id, plan)
        except Exception as exc:  # noqa: BLE001 — plan projection is auxiliary
            if "not found" not in str(exc).lower():
                raise

    def _set_run_status(self, run_id: str, state: str) -> None:
        """Mirror the assignment's terminal/holding state on its GoalRun.

        The task/operation ledger remains authoritative for work; this keeps
        the run row from claiming active work while the assignment is asleep
        or finished.
        """
        state = {"completed": "achieved"}.get(state, state)
        if state not in ("achieved", "failed", "cancelled", "waiting"):
            return
        try:
            run = self.lifecycle.runs.get_run(run_id) or {}
            current = str(run.get("status") or "").lower()
            if state == "achieved":
                if current == "waiting":
                    self.lifecycle.runs.transition(run_id, "active")
                    current = "active"
                if current in ("active", "paused_hitl", "planning"):
                    self.lifecycle.runs.transition(run_id, "achieved")
            elif state == "failed":
                if current in ("active", "waiting", "paused_hitl"):
                    if current == "waiting":
                        self.lifecycle.runs.transition(run_id, "active")
                    self.lifecycle.runs.transition(run_id, "failed")
            elif state == "cancelled":
                if current not in ("achieved", "failed", "cancelled"):
                    self.lifecycle.runs.transition(run_id, "cancelled")
        except Exception as exc:  # noqa: BLE001 — the ledger stays authoritative
            logger.warning(
                "assignment %s: goal-run status projection to %s failed: %s",
                run_id, state, exc)

    def _enter_wait(
        self,
        run_id: str,
        *,
        waiting: Dict[str, Any],
        summary: str = "",
    ) -> None:
        """Persist the same wait on the GoalRun event bridge.

        The assignment/operation rows remain the work record; this makes the
        run wakable through the existing ``consume_wake``/HITL path rather
        than a private polling loop.
        """
        spec = {
            "event": str(waiting.get("event") or "human_input"),
            "summary": summary or waiting.get("detail") or waiting.get("state"),
            "assignment_wait": {
                "correlation_id": waiting.get("correlation_id"),
                "question_id": waiting.get("gap_question_id"),
                "state": waiting.get("state"),
            },
        }
        if waiting.get("deadline"):
            spec["deadline"] = waiting["deadline"]
        exact = {}
        for key in ("correlation_id", "thread_id", "message_id", "hitl_id"):
            value = waiting.get(key)
            if value:
                exact[key] = value
        if exact:
            spec["match_exact"] = exact
        try:
            self.lifecycle.runs.set_wait(run_id, spec)
        except Exception as exc:  # noqa: BLE001 — work record is durable
            logger.warning(
                "assignment %s: goal-run wait projection failed: %s",
                run_id, exc)

    async def _request_hitl_approval(
        self,
        run_id: str,
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        operation_id: str,
        prepared: Dict[str, Any],
    ) -> Optional[str]:
        """File the concrete approval on the shared HITL surface.

        The row carries the run/operation identity and the exact payload
        digest, artifact revision and authorization revision. The approval
        route scopes it to the authenticated workspace/tenant and refuses a
        modified binding.
        """
        try:
            from core.intervention_service import intervention_service

            result = await intervention_service.request_intervention(
                workspace_id=assignment.get("workspace_id") or "default",
                tenant_id=assignment.get("tenant_id") or "default",
                action_type="assignment_approval",
                platform="assignment",
                params={
                    "run_id": run_id,
                    "assignment_id": assignment.get("assignment_id"),
                    "step_id": step.get("step_id"),
                    "operation_id": operation_id,
                    "payload_sha256": prepared.get("payload_sha256"),
                    "artifact_revision": prepared.get("artifact_revision"),
                    "authorization_revision": _authorization_revision(
                        assignment),
                    "workspace_id": assignment.get("workspace_id"),
                    "summary": step.get("title"),
                },
                reason=(
                    (step.get("approval") or {}).get("purpose")
                    or f"Approve '{step.get('title')}'"),
                user_id=assignment.get("employee_id"),
            )
            return result.get("action_id")
        except Exception as exc:  # noqa: BLE001 — the operation still waits
            logger.warning(
                "assignment %s: HITL approval filing failed: %s", run_id, exc)
            return None

    # -------------------------------------------------------------- status

    def status(self, run_id: str) -> Dict[str, Any]:
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        assignment = record.get("assignment")
        if assignment is None:
            raise AssignmentError(f"run {run_id} has no assignment plan")
        from core.task_lifecycle import open_unresolved_questions

        projected = assignment_projection(assignment)
        budget_view = dict(projected.get("budget") or {})
        started = self._parse_clock(budget_view.get("started_at"))
        if started is not None:
            wall = max(0.0, float(self.clock()) - started)
            working = min(wall, max(
                0.0, self._effective_wall_elapsed(budget_view)))
            budget_view["working_seconds"] = round(working, 3)
            budget_view["paused_seconds"] = round(max(0.0, wall - working), 3)
            budget_view["wall_seconds"] = round(wall, 3)
        projected["budget"] = budget_view
        steps = assignment.get("steps") or []
        required = [step for step in steps if step.get("required", True)]
        projected["progress"] = {
            "total_steps": len(steps),
            "required_steps": len(required),
            "completed_steps": sum(
                1 for step in required
                if step.get("status") in ("applied", "skipped")),
            "waiting_steps": sum(
                1 for step in steps
                if step.get("status") in ("waiting", "awaiting_approval")),
            "failed_steps": sum(
                1 for step in steps if step.get("status") == "failed"),
            "uncertain_steps": sum(
                1 for step in steps if step.get("status") == "uncertain"),
            "open_gap_count": len(open_unresolved_questions(record)),
        }
        return {
            "run_id": run_id,
            "assignment": projected,
            "open_gaps": open_unresolved_questions(record),
            "operations": [
                {
                    "operation_id": operation.get("operation_id"),
                    "step_id": operation.get("step_id"),
                    "type": operation.get("operation_type"),
                    "status": operation.get("status"),
                    "needs_reconciliation": bool(
                        operation.get("needs_reconciliation")),
                    "approval": copy.deepcopy(
                        operation.get("approval_request") or {}),
                    "uncertainty_reason": operation.get(
                        "uncertainty_reason"),
                    "remote_id": (
                        (operation.get("execution") or {}).get("remote_id")),
                    "provider_ref": (
                        (operation.get("execution") or {}).get(
                            "provider_ref")),
                    "result_summary": (
                        (operation.get("execution") or {}).get("summary")),
                }
                for operation in record.get("operations") or []
            ],
        }

    # ----------------------------------------------------------- execution

    @staticmethod
    def _source_gap(
        binding: Dict[str, Any],
        step: Dict[str, Any],
        *,
        code: str,
        detail: str,
        version: bool = False,
        access: bool = False,
    ) -> Dict[str, Any]:
        if access:
            state = ("source_access_revoked" if "revoked" in code
                     else "source_access_required")
            question = (
                "The accepted source is no longer authorized for this task. "
                "Reauthorize it, then retry the dependent work.")
            resume_on = "source_reauthorized"
        elif version:
            state = "source_version_changed"
            question = (
                "The accepted source version changed. Confirm and supply the "
                "current authorized version, then retry the dependent work.")
            resume_on = "source_refreshed"
        else:
            state = "source_unavailable"
            question = (
                "The accepted source is no longer available. Restore or "
                "re-upload it, or select a current authorized source, then "
                "retry the dependent work.")
            resume_on = "resource_restored"
        waiting = {
            "state": state,
            "party": "source owner",
            "resume_on": resume_on,
            "since": _utc_now_iso(),
            "detail": _bounded(detail, 500),
            "code": code,
        }
        return {
            "concept": "source_access",
            "reason": f"{code}: {_bounded(detail, 500)}",
            "question": question,
            "checked_evidence": [
                f"resource={binding.get('dataset_name') or binding.get('resource_id') or binding.get('document_id')}",
                f"sheet={binding.get('sheet')}",
                f"version={str(binding.get('source_version') or '')[:12]}",
                code,
            ],
            "next_retrieval": "recheck source access, availability and active version",
            "kind": "missing_evidence",
            "waiting": waiting,
        }

    def _source_consumption_gap(
        self,
        assignment: Dict[str, Any],
        record: Dict[str, Any],
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Reauthorize and recheck an accepted source before consumption.

        An applied read is not perpetual authority. The current principal and
        workspace/tenant are checked before touching bytes; the current
        resource row/grant and the accepted version pin are checked before any
        dependent step or final artifact may use the cached result. Missing,
        removed, unreadable, moved or changed sources produce a typed gap on
        the source step. This method never silently substitutes a replacement
        version.
        """
        provenance = assignment.get("provenance") or {}
        context = {
            "workspace_id": (
                assignment.get("workspace_id")
                or provenance.get("workspace_id") or ""),
            "tenant_id": (
                assignment.get("tenant_id")
                or provenance.get("tenant_id") or ""),
            "employee_id": (
                provenance.get("employee_id")
                or provenance.get("agent_id") or ""),
            "actor_id": (
                provenance.get("actor_id")
                or provenance.get("user_id") or ""),
        }
        source_adapters = (
            "workbook.read", "document.read", "document.text", "dataset.read")
        for step in assignment.get("steps") or []:
            if str(step.get("status") or "") != "applied":
                continue
            if str(step.get("adapter") or "") not in source_adapters:
                continue
            inputs = step.get("inputs") if isinstance(
                step.get("inputs"), dict) else {}
            binding = inputs.get("resource_binding") if isinstance(
                inputs.get("resource_binding"), dict) else {}
            result = step.get("result") if isinstance(
                step.get("result"), dict) else {}
            if not binding:
                return step, self._source_gap(
                    binding, step, code="resource_binding_missing",
                    detail="the applied source step has no typed binding",
                    access=True)
            document_id = str(
                binding.get("document_id")
                or (binding.get("resource_id")
                    if str(binding.get("source") or "").lower() == "upload"
                    else "") or "")
            expected = str(
                binding.get("source_version")
                or result.get("source_version") or "")
            accepted_sha = str(result.get("sha256") or "")
            try:
                if document_id:
                    # Uploaded document authority is the workspace-scoped
                    # IngestedDocument row, not a path handed in earlier.
                    from core.database import get_db_session
                    from core.models import IngestedDocument, User
                    scope = binding.get("access_scope") if isinstance(
                        binding.get("access_scope"), dict) else {}
                    expected_user = str(
                        scope.get("user_id") or context.get("actor_id")
                        or context.get("employee_id") or "")
                    expected_workspace = str(
                        scope.get("workspace_id")
                        or context.get("workspace_id") or "")
                    expected_tenant = str(
                        scope.get("tenant_id")
                        or context.get("tenant_id") or "")
                    with get_db_session() as db:
                        user_id = expected_user
                        if user_id:
                            user = db.query(User).filter(
                                User.id == user_id).first()
                            if user is None or not bool(
                                    getattr(user, "is_active", True)):
                                return step, self._source_gap(
                                    binding, step,
                                    code="authenticated_principal_unavailable",
                                    detail="the accepted reader is missing or inactive",
                                    access=True)
                            user_workspace = str(
                                getattr(user, "workspace_id", "") or "default")
                            user_tenant = str(
                                getattr(user, "tenant_id", "") or "default")
                            if ((expected_workspace
                                 and user_workspace != expected_workspace)
                                or (expected_tenant
                                    and user_tenant != expected_tenant)):
                                return step, self._source_gap(
                                    binding, step,
                                    code="resource_workspace_mismatch",
                                    detail="the accepted reader moved workspace/tenant",
                                    access=True)
                        row = db.query(IngestedDocument).filter(
                            IngestedDocument.id == document_id).first()
                    if row is None:
                        return step, self._source_gap(
                            binding, step, code="resource_not_found",
                            detail="the authoritative uploaded document row is gone")
                    if (expected_workspace
                            and str(row.workspace_id or "")
                            and str(row.workspace_id) != expected_workspace):
                        return step, self._source_gap(
                            binding, step, code="resource_workspace_mismatch",
                            detail="the uploaded document moved workspace",
                            access=True)
                    if (expected_tenant and row.tenant_id is not None
                            and str(row.tenant_id) != expected_tenant):
                        return step, self._source_gap(
                            binding, step, code="resource_workspace_mismatch",
                            detail="the uploaded document moved tenant",
                            access=True)
                    freshness = str(
                        getattr(row, "freshness_status", "fresh")
                        or "fresh").lower()
                    if freshness not in ("fresh", "current", "active"):
                        return step, self._source_gap(
                            binding, step, code="stale_source_version",
                            detail=f"the uploaded document is {freshness}",
                            version=True)
                    authoritative = str(
                        getattr(row, "source_content_hash", "") or "")
                    indexed = str(
                        result.get("source_version")
                        or ((result.get("extraction") or {}).get(
                            "indexed_version")
                            if isinstance(result.get("extraction"), dict)
                            else "")
                        or "")
                    accepted_revision = str(
                        binding.get("source_version")
                        or result.get("source_version")
                        or "")
                    if not accepted_revision:
                        return step, self._source_gap(
                            binding, step, code="source_revision_missing",
                            detail="the accepted source receipt has no revision pin",
                            version=True)
                    from core.doc_freshness_service import (
                        ExtractionIdentityError,
                        current_extraction_revision,
                    )
                    try:
                        current_extraction_revision(
                            indexed, authoritative, accepted_revision)
                    except ExtractionIdentityError as exc:
                        return step, self._source_gap(
                            binding, step, code="stale_source_version",
                            detail=str(exc), version=True)
                    path = str(
                        getattr(row, "file_path", "")
                        or inputs.get("path") or binding.get("path") or "")
                    if path:
                        if not os.path.isfile(path):
                            return step, self._source_gap(
                                binding, step, code="source_unavailable",
                                detail="the uploaded document file is missing")
                        try:
                            current = _sha256_file(path)
                        except (OSError, PermissionError):
                            return step, self._source_gap(
                                binding, step, code="source_unreadable",
                                detail="the uploaded document file is unreadable")
                        # Binary file bytes and indexed revisions are
                        # distinct namespaces. Compare a binary accepted
                        # sha256 only with file bytes; ev4:/manual opaque
                        # revisions are validated against the authoritative
                        # IngestedDocument row above, never hashed as bytes.
                        binary_pin = (
                            accepted_sha
                            if re.fullmatch(r"[0-9a-fA-F]{64}", accepted_sha)
                            else "")
                        if binary_pin and current != binary_pin:
                            return step, self._source_gap(
                                binding, step, code="stale_source_version",
                                detail="the uploaded document bytes changed after acceptance",
                                version=True)
                    continue

                if binding.get("internal_fixture"):
                    _recheck_binding(binding, context)
                    path = str(
                        inputs.get("path") or binding.get("path") or "")
                    if not path or not os.path.isfile(path):
                        return step, self._source_gap(
                            binding, step, code="source_unavailable",
                            detail="the accepted controlled source file is missing")
                    try:
                        current = _sha256_file(path)
                    except (OSError, PermissionError):
                        return step, self._source_gap(
                            binding, step, code="source_unreadable",
                            detail="the accepted controlled source is unreadable")
                    binary_pin = (
                        accepted_sha
                        if re.fullmatch(r"[0-9a-fA-F]{64}", accepted_sha)
                        else (expected if re.fullmatch(
                            r"[0-9a-fA-F]{64}", expected) else ""))
                    if binary_pin and current != binary_pin:
                        return step, self._source_gap(
                            binding, step, code="stale_source_version",
                            detail="the accepted controlled source bytes changed",
                            version=True)
                    continue

                # Connected dataset: re-resolve the current grant, scope,
                # resource and active version through the existing checker.
                resolved = _recheck_binding(binding, context)
                current_version = str(
                    resolved.get("source_version") or "")
                if expected and current_version and expected != current_version:
                    return step, self._source_gap(
                        binding, step, code="stale_source_version",
                        detail="the active connected source version changed",
                        version=True)
                path = str(resolved.get("path") or "")
                if not path or not os.path.isfile(path):
                    return step, self._source_gap(
                        binding, step, code="source_unavailable",
                        detail="the current materialized source is missing")
                try:
                    _sha256_file(path)
                except (OSError, PermissionError):
                    return step, self._source_gap(
                        binding, step, code="source_unreadable",
                        detail="the current materialized source is unreadable")
            except NeedsContext as exc:
                return step, exc.gap
        return None

    def _revalidate_waiting_sources(
        self,
        run_id: str,
        assignment: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], bool]:
        """Clear a durable source gap when the same accepted version returns.

        A previously applied source step is marked waiting with open gap_ids
        when its authority/bytes/version became unavailable. On a later normal
        retry (source route or advance), probe the same accepted pin again; if
        the source is permanently present and still the accepted version,
        restore the applied status and resolve only that step's gap questions.
        """
        source_adapters = (
            "workbook.read", "document.read", "document.text", "dataset.read")
        waiting = [
            step for step in assignment.get("steps") or []
            if str(step.get("status") or "") == "waiting"
            and step.get("gap_ids")
            and str(step.get("adapter") or "") in source_adapters
        ]
        if not waiting:
            return assignment, False
        changed = False
        restored_ids = []
        for step in waiting:
            probe = copy.deepcopy(assignment)
            target = step_by_id(probe, step["step_id"])
            if target is None:
                continue
            target["status"] = "applied"
            problem = self._source_consumption_gap(probe, {})
            if problem is not None:
                # A different/current source may still be blocked; do not
                # clear this gap unless this source itself is valid.
                continue
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "applied",
                "gap_ids": [],
                "waiting": None,
                "updated_at": _utc_now_iso(),
            })
            restored_ids.extend(str(q) for q in step.get("gap_ids") or [])
            changed = True
        if not changed:
            return assignment, False
        if restored_ids:
            from core.task_lifecycle import resolve_unresolved_questions
            resolve_unresolved_questions(
                self.lifecycle, run_id,
                question_ids=restored_ids,
                resolution=(
                    "authorized source restored at the same accepted "
                    "version; dependent work may resume"))
        self._persist_assignment(
            run_id, assignment, "applied source restored at accepted version")
        return assignment, True

    async def _record_applied_source_gap(
        self,
        run_id: str,
        record: Dict[str, Any],
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        gap: Dict[str, Any],
    ) -> None:
        """Persist a typed gap for an already-applied source.

        The source operation stays applied for audit; it cannot be moved back
        to running/waiting. The plan marks the source step waiting so only its
        dependents and the final artifact are blocked; unrelated branches stay
        runnable.
        """
        gap = dict(gap or {})
        waiting = gap.get("waiting") or {
            "state": "source_unavailable",
            "party": "source owner",
            "resume_on": "resource_restored",
            "since": _utc_now_iso(),
        }
        if not gap.get("question"):
            gap["question"] = (
                "The accepted source is unavailable; restore it before "
                "dependent work can continue.")
        if not gap.get("next_action"):
            gap["next_action"] = (
                gap.get("next_retrieval")
                or "Restore/re-authorize the source and retry.")
        binding_key = _gap_binding_key(gap)
        existing = [
            q for q in (record.get("task_revision") or {}).get(
                "unresolved") or []
            if isinstance(q, dict)
            and q.get("status") == "open"
            and q.get("step_id") == step.get("step_id")
            and str(q.get("concept") or "") == str(gap.get("concept") or "")
            and _gap_binding_key(q) == binding_key
        ]
        if existing:
            question_id = existing[0]["question_id"]
        else:
            question = {
                "question_id": gap.get("question_id"),
                "item": gap.get("item") or step.get("title") or "",
                "question": gap["question"],
                "kind": gap.get("kind") or "missing_evidence",
                "evidence": gap.get("evidence") or "",
                "next_action": gap.get("next_action"),
                "inputs": gap.get("inputs") or {},
                "concept": gap.get("concept") or "",
                "reason": gap.get("reason") or "",
                "affected_subjects": gap.get("affected_subjects") or [],
                "checked_evidence": gap.get("checked_evidence") or [],
                "next_retrieval": gap.get("next_retrieval") or "",
                "resolver": gap.get("resolver") or "",
                "step_id": step.get("step_id"),
                "waiting": waiting,
                "binding_key": binding_key,
            }
            self.lifecycle.apply_transition(run_id, {
                "kind": "record_unresolved",
                "requested_change": _bounded(gap["question"], 500),
                "questions": [question],
                "source_operation": str(step.get("operation_id") or ""),
            })
            refreshed = self.lifecycle.get_task(run_id) or record
            question_id = None
            for item in (refreshed.get("task_revision") or {}).get(
                    "unresolved") or []:
                if (item.get("status") == "open"
                        and item.get("step_id") == step.get("step_id")
                        and str(item.get("concept") or "")
                        == str(gap.get("concept") or "")
                        and _gap_binding_key(item) == binding_key):
                    question_id = item["question_id"]
            question_id = question_id or str(gap.get("question_id") or "")
        assignment = self._mark_step(assignment, step["step_id"], {
            "status": "waiting",
            "gap_ids": sorted(set(
                list(step.get("gap_ids") or []) + [question_id])),
            "waiting": _json_safe(waiting),
            "updated_at": _utc_now_iso()})
        self._enter_wait(
            run_id,
            waiting={**waiting, "gap_question_id": question_id},
            summary=gap["question"])
        self._persist_assignment(
            run_id, assignment, "applied source needs reauthorization")

    async def execute(
        self,
        run_id: str,
        *,
        max_steps: Optional[int] = None,
        expected_task_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Advance ready work until waiting, blocked, complete or budget.

        Ordinary execution never asserts that another worker is dead. A
        ``running`` operation owned by another worker is left intact; only
        the explicit recovery path may mark it uncertain.
        """
        limit = max(1, min(int(max_steps or 50), 200))
        steps_run = 0
        source_retry_checked = False
        while steps_run < limit:
            record = self.lifecycle.get_task(run_id)
            if record is None:
                raise AssignmentError(f"no task record on run {run_id}")
            assignment = record.get("assignment")
            if assignment is None:
                raise AssignmentError(
                    f"run {run_id} has no assignment plan")
            if expected_task_revision is not None and int(
                    (record.get("task_revision") or {}).get("revision") or 0
            ) != int(expected_task_revision):
                raise AssignmentError(
                    "stale task revision: the assignment changed after this "
                    "execution request was prepared")
            expected_task_revision = None

            assignment = self._sync_assignment(record, assignment)
            if not source_retry_checked:
                # A restoration retry is checked once per external advance,
                # not repeatedly inside one execution loop. This clears a
                # durable gap only when the same accepted version is valid
                # again, while an unavailable source yields immediately.
                assignment, source_restored = self._revalidate_waiting_sources(
                    run_id, assignment)
                source_retry_checked = True
                if source_restored:
                    record = self.lifecycle.get_task(run_id) or record
            source_problem = self._source_consumption_gap(assignment, record)
            if source_problem:
                source_step, source_gap = source_problem
                await self._record_applied_source_gap(
                    run_id, record, assignment, source_step, source_gap)
                continue
            task_authorization = str(
                (record.get("task_revision") or {}).get("authorization")
                or "read_only")
            state = derive_state(
                assignment, task_authorization=task_authorization)
            if state in ("failed", "partial") and ready_steps(
                    assignment, task_authorization=task_authorization):
                # Independent ready work may continue even when one branch
                # has failed; only the branch is blocked.
                state = "running"
            if state == "completed" and open_unresolved_questions(record):
                # A wait is not completion. An independent branch may have
                # finished and retained its receipt, but the job still owes a
                # targeted answer before its final deliverable can be called
                # complete.
                state = (
                    "waiting" if self._waiting_steps(assignment)
                    else "blocked")
            assignment = self._set_state(assignment, state)
            if state == "completed" and assignment.get(
                    "completion_criteria"):
                from core.task_outcome_contract import (
                    build_assignment_outcome,
                )
                business = build_assignment_outcome(
                    assignment, record, state=state)
                if business.get("verdict") is not True:
                    # Every step applied is necessary, never sufficient.
                    state = "partial" if any(
                        step.get("status") == "applied"
                        for step in assignment.get("steps") or []) else "blocked"
                    assignment = self._set_state(assignment, state)
            if state in TERMINAL_ASSIGNMENT_STATES:
                assignment = self._attach_outcome(
                    record, assignment, state)
                self._persist_assignment(run_id, assignment, "assignment terminal")
                self._set_run_status(run_id, state)
                return self.status(run_id)

            budget = assignment.get("budget") or {}
            if not budget.get("started_at"):
                budget = dict(budget)
                budget["started_at"] = (
                    assignment.get("provenance") or {}).get("started_at")
            if not budget.get("started_at"):
                budget["started_at"] = _utc_now_iso()
                assignment = {**assignment, "budget": budget,
                              "status": "running"}
                self._persist_assignment(
                    run_id, assignment, "assignment started")
                record = self.lifecycle.get_task(run_id) or record

            assignment = self._ensure_idle_ledger(assignment)
            assignment = self._checkpoint_idle(assignment)
            if self._deadline_exceeded(assignment):
                assignment = self._expire_assignment_deadline(assignment)
                self._persist_assignment(
                    run_id, assignment, "assignment business deadline passed")
                self._set_run_status(run_id, "blocked")
                return self.status(run_id)

            # Try eligible waiting/approval steps. A wait that is NOT yet
            # eligible must not return early: an independent branch whose
            # dependencies are satisfied can still do useful work.
            progress = False
            for waiting_step in self._waiting_steps(assignment):
                resumed = await self._resume_waiting_step(
                    run_id, record, assignment, waiting_step)
                if resumed:
                    steps_run += 1
                    progress = True
                    break
            if progress:
                continue

            # Re-read: a resumed step above may have changed the plan.
            record = self.lifecycle.get_task(run_id) or record
            assignment = self._sync_assignment(record, assignment)
            assignment = self._ensure_idle_ledger(assignment)
            assignment = self._checkpoint_idle(assignment)
            readiness = ready_steps(
                assignment, task_authorization=task_authorization)
            if open_unresolved_questions(record):
                # Final deliverables stay blocked while a material obligation
                # is open; independent ready branches are still allowed to
                # run. The declared deliverable steps are the authority.
                deliverable_steps = set(
                    self._final_deliverable_step_ids(assignment))
                readiness = [
                    step for step in readiness
                    if str(step.get("step_id")) not in deliverable_steps
                ]
            if not readiness:
                # Persist typed readiness blockers for pending work. A
                # scheduler miss is a business reason (unknown qualification,
                # missing receipt, expired evidence, authority), not a silent
                # idle state; the read projection exposes it.
                for pending_step in assignment.get("steps") or []:
                    if pending_step.get("status") != "pending":
                        continue
                    if not pending_step.get("requires"):
                        continue
                    decision = evaluate_step_readiness(
                        pending_step, assignment,
                        task_authorization=task_authorization)
                    if not decision["eligible"]:
                        pending_step["readiness"] = decision
                waiting = self._waiting_steps(assignment)
                # A durable information request is a wait too: the task needs
                # an authorized answer, not active execution. Without an idle
                # interval the elapsed wall budget would expire while the
                # owner is still gathering the missing fact, and a later
                # authorized answer could no longer resume the same task.
                information_wait = bool(open_unresolved_questions(record))
                assignment = self._set_state(
                    assignment, "waiting" if waiting else "blocked")
                if waiting or information_wait:
                    assignment = self._open_idle(
                        assignment,
                        reason=(
                            "all runnable branches are waiting" if waiting
                            else "waiting for an information answer"))
                    self._persist_assignment(
                        run_id, assignment,
                        "assignment waiting" if waiting
                        else "assignment waiting for information answer")
                else:
                    self._persist_assignment(
                        run_id, assignment,
                        "assignment blocked: no ready step")
                return self.status(run_id)

            # Work can progress: any open idle interval ends now, before the
            # next operation starts charging working time.
            assignment = self._close_idle(
                assignment, reason="ready work resumed")
            step = readiness[0]
            if not self._budget_allows(assignment, step):
                assignment = self._block_step(
                    assignment, step["step_id"],
                    reason="assignment_budget_exhausted",
                    message=(
                        "The assignment budget was reached before this step "
                        "could run. Increase the budget or resolve the "
                        "remaining work explicitly."))
                self._persist_assignment(
                    run_id, assignment, "assignment budget exhausted")
                return self.status(run_id)

            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "running",
                "pre_dispatch_budget_refusal": False,
                "readiness": None,
                "updated_at": _utc_now_iso(),
            })
            assignment = self._bump_steps_started(assignment)
            self._persist_assignment(
                run_id, assignment, f"step {step['step_id']} started")

            # Re-read after persisting intent: cancellation may have landed.
            record = self.lifecycle.get_task(run_id) or record
            if str((record.get("task_revision") or {}).get("authorization")
                   or "").lower() == "cancelled":
                return self._finish_cancelled(run_id, record)

            step = step_by_id(assignment, step["step_id"]) or step
            await self._run_step(run_id, record, assignment, step)
            steps_run += 1

        return self.status(run_id)

    async def resume(self, run_id: str, *, max_steps: Optional[int] = None) -> Dict[str, Any]:
        """Resume eligible pending/waiting work without asserting loss."""
        return await self.execute(run_id, max_steps=max_steps)

    async def recover_after_restart(
        self,
        run_id: str,
        *,
        lost_worker: Optional[str] = None,
        is_worker_live: Optional[Callable[[str], bool]] = None,
        max_steps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Explicit restart recovery for a DEMONSTRABLY lost worker.

        ``lost_worker`` names the previous owner; ``is_worker_live`` is the
        liveness probe. Without either proof, running operations are left
        untouched. Recovery never turns a timeout/expired lease into a
        confirmed non-effect.
        """
        self.mark_stranded_uncertain(
            run_id, lost_worker=lost_worker,
            is_worker_live=is_worker_live)
        self.replay_pending_wake(run_id)
        return await self.execute(run_id, max_steps=max_steps)

    def replay_pending_wake(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Recover a wake committed before the successor step ran.

        ``consume_wake`` writes the wake event into the run's decision log
        before returning. If the process dies before ``advance``, the next
        recovery pass reads that durable event and applies it to the matching
        assignment step. It never invents an event and never matches on prose.
        """
        record = self.lifecycle.get_task(run_id)
        if record is None or record.get("assignment") is None:
            return None
        try:
            decisions = self.lifecycle.runs.get_decisions(run_id)
        except Exception:
            return None
        wake = next((
            entry for entry in reversed(decisions or [])
            if entry.get("kind") == "wake"
            and isinstance(entry.get("event"), dict)
        ), None)
        if not wake:
            return None
        event = wake.get("event") or {}
        correlation = str(
            event.get("correlation_id")
            or event.get("thread_id") or "")
        if not correlation:
            return None
        for step in (record.get("assignment") or {}).get("steps") or []:
            if step.get("status") != "waiting":
                continue
            if str((step.get("waiting") or {}).get(
                    "correlation_id") or "") != correlation:
                continue
            return self.record_external_response(
                run_id, correlation,
                response=str(event.get("summary") or ""),
                source=str(event.get("source") or ""),
                evidence=str(event.get("message_id") or ""))
        return None

    def mark_stranded_uncertain(
        self,
        run_id: str,
        *,
        lost_worker: Optional[str] = None,
        is_worker_live: Optional[Callable[[str], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Mark operations owned by a DEMONSTRABLY lost worker unknown.

        No owner, no proof: an operation with no recorded owner, or one owned
        by this process, is left alone. An expired lease/timeout is not
        evidence of worker loss and is not consulted here. The honest result
        is ``uncertain`` (never ``failed``), so a possible provider effect is
        reconciled rather than retried blindly.
        """
        from core.task_lifecycle import _current_worker_fingerprint

        record = self.lifecycle.get_task(run_id)
        if record is None:
            return []
        assignment = record.get("assignment") or {}
        if not assignment:
            return []
        me = _current_worker_fingerprint()
        assignment_id = assignment.get("assignment_id")
        marked: List[Dict[str, Any]] = []
        for operation in record.get("operations") or []:
            if operation.get("assignment_id") != assignment_id:
                continue
            if operation.get("status") != "running":
                continue
            owner = str(operation.get("claimed_by") or "")
            if not owner or owner == me:
                continue
            if lost_worker and owner != str(lost_worker):
                continue
            if is_worker_live is not None:
                try:
                    live = bool(is_worker_live(owner))
                except Exception:  # noqa: BLE001 — inconclusive means live
                    live = True
                if live:
                    continue
            elif not lost_worker:
                # No explicit proof and no liveness probe: do not accuse a
                # live worker merely because a lease looks old.
                continue
            try:
                updated = self.lifecycle.record_uncertain_outcome(
                    run_id, operation["operation_id"],
                    reason=(
                        f"worker {owner} is demonstrably lost while this "
                        f"effect was in flight; the provider outcome is "
                        f"unknown"),
                    evidence=(
                        f"recovered on restart; claim was taken under task "
                        f"revision {operation.get('claimed_task_revision')} "
                        f"and operation revision "
                        f"{operation.get('claimed_operation_revision')}; "
                        f"no automatic replay performed"),
                    observed_by="assignment_restart_recovery",
                )
                marked.append(updated)
            except TaskLifecycleError:
                continue
        return marked

    def _unconsumed_evidence_key(
        self, record: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Active, model-driven evidence that no adaptation patch consumed."""
        from core.employee_job_runner import evidence_observations
        from core.task_lifecycle import open_unresolved_questions

        assignment = record.get("assignment") or {}
        if not assignment:
            return None
        if str(assignment.get("status") or "") in TERMINAL_ASSIGNMENT_STATES:
            return None
        provenance = assignment.get("provenance") or {}
        if provenance.get("use_model", True) is False:
            return None
        # This recovery seam owns employee-objective work only. An explicit
        # plan assignment (or another route's projection) must not acquire an
        # unrequested model adaptation merely because the process restarted.
        if str(provenance.get("started_from") or "") != "employee_objective":
            return None
        if str((record.get("task_revision") or {}).get(
                "authorization") or "").lower() == "cancelled":
            return None
        budget = assignment.get("budget") or {}
        deadline = str(budget.get("deadline") or "").strip()
        if deadline:
            try:
                expires = datetime.fromisoformat(
                    deadline.replace("Z", "+00:00"))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= expires:
                    return None
            except (TypeError, ValueError):
                pass
        if open_unresolved_questions(record):
            return None
        observations = evidence_observations(record)
        observation_ids = sorted({
            str(item.get("observation_id"))
            for item in observations
            if item.get("observation_id")
        })
        if not observation_ids:
            return None
        key = hashlib.sha256(
            "\n".join(observation_ids).encode("utf-8")).hexdigest()[:20]
        # A newly settled answer is material even when the retained evidence
        # rows did not change. It must not inherit an evidence-only retain /
        # attempted marker from before the question was answered. Preserve
        # historical keys exactly when there are no resolved answers.
        answers = sorted([
            {name: question.get(name) for name in (
                "question_id", "concept", "affected_subjects",
                "resolution_value", "resolution", "resolved_at")}
            for question in (record.get("task_revision") or {}).get("unresolved") or []
            if isinstance(question, dict)
            and question.get("status") == "resolved"
            and (question.get("resolution_value") or question.get("resolution"))
        ], key=lambda value: str(value.get("question_id") or ""))
        if answers:
            key = canonical_sha256({
                "observation_ids": observation_ids, "resolved_answers": answers,
            })[:20]
        # External waits use the step receipt ledger rather than the question
        # ledger. A new accepted fact is equally material to recovery, but raw
        # response text or an unaccepted candidate must not rearm inference.
        accepted_replies = []
        for step in assignment.get("steps") or []:
            if not isinstance(step, dict):
                continue
            external = step.get("external_response")
            if not isinstance(external, dict):
                continue
            identity = {name: external.get(name) for name in (
                "correlation_id", "reply_id", "identity_kind", "material_sha256")}
            digest = identity["material_sha256"]
            step_id = step.get("step_id")
            if (not isinstance(step_id, str) or not step_id
                    or not isinstance(identity["correlation_id"], str)
                    or not identity["correlation_id"]
                    or not isinstance(identity["reply_id"], str)
                    or identity["identity_kind"] not in ("explicit", "legacy")
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest)):
                continue
            if not any(
                receipt.get("outcome") == "resolved"
                and all(receipt.get(name) == value for name, value in identity.items())
                for receipt in _external_reply_receipts(step)
            ):
                continue
            accepted_replies.append({"step_id": step_id, **identity})
        if accepted_replies:
            accepted_replies.sort(key=lambda value: (
                value["step_id"], value["correlation_id"],
                value["identity_kind"], value["reply_id"], value["material_sha256"]))
            key = canonical_sha256({
                "prior_evidence_key": key,
                "accepted_external_replies": accepted_replies,
            })[:20]
        return {"key": key, "observation_ids": observation_ids}

    def _evidence_recovery_plan(
        self, record: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """The accepted evidence that a restart must hand to adaptation.

        Eligible only when the task is still active, the objective is
        model-driven, no obligation is open, and applied evidence results have
        not yet been consumed by an adaptation patch. A durable marker makes
        each evidence set a ONE-SHOT recovery: a retain/clarify attempt is not
        re-polled forever on every boot, and a bounded claim prevents two
        concurrent successors from adapting the same evidence twice.
        """
        base = self._unconsumed_evidence_key(record)
        if base is None:
            return None
        key = base["key"]
        marker = (record.get("assignment") or {}).get("evidence_recovery")
        marker = marker if isinstance(marker, dict) else {}
        if str(marker.get("key") or "") == key:
            state = str(marker.get("status") or "")
            if state in ("attempted", "completed", "model_unavailable"):
                return None
            if state == "claimed" and not self._evidence_recovery_takeover_ready(
                    marker):
                # Fresh lease, or a DIFFERENT live owner still adapting.
                return None
        return {**base, "marker": marker}

    def _evidence_recovery_deferral(
        self, record: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """The bounded wake a boot owes a claim whose owner cannot finish it.

        A one-shot boot that merely skips a fresh claim would strand accepted
        evidence when the claim's process died before continuation. When the
        recorded owner is dead/unknown, return the remaining lease so the same
        recovery owner can re-enter once at expiry (never a hot model poll).
        A live owner is left alone: it still owns its adaptation.
        """
        base = self._unconsumed_evidence_key(record)
        if base is None:
            return None
        marker = (record.get("assignment") or {}).get("evidence_recovery")
        marker = marker if isinstance(marker, dict) else {}
        if str(marker.get("key") or "") != base["key"]:
            return None
        if str(marker.get("status") or "") != "claimed":
            return None
        owner_state = self._evidence_recovery_owner_state(marker)
        if owner_state in ("live", "self"):
            # A live owner (including this process) still owns the lease.
            return None
        try:
            claimed_at = float(marker.get("at"))
            ttl = float(marker.get("ttl") or 0)
        except (TypeError, ValueError):
            return None
        if ttl <= 0:
            return None
        remaining = max(0.0, (claimed_at + ttl) - time.time())
        return {
            "key": base["key"],
            "owner_state": owner_state,
            "remaining": remaining,
            "claim_token": marker.get("claim_token"),
        }

    @staticmethod
    def _evidence_recovery_owner_state(marker: Dict[str, Any]) -> str:
        """Classify the claim owner with the existing process-liveness probe.

        ``live`` is decisive: another live process may still be adapting the
        accepted evidence, so a lease expiry is not permission to run a second
        model call behind it. ``self`` is the same process and may own a
        different, stale lease (a process fingerprint is not a generation).
        ``dead``/``unknown`` may be taken over only once the bounded TTL has
        elapsed -- the TTL bounds when takeover may happen; it never claims the
        old provider/process physically stopped.
        """
        from core.execution_ownership import owner_liveness

        owner_process = marker.get("owner_process")
        if not isinstance(owner_process, dict) or not owner_process.get("pid"):
            return "unknown"
        try:
            state, _detail = owner_liveness({"owner": owner_process})
        except Exception:  # noqa: BLE001 — inconclusive is not proof of death
            return "unknown"
        return str(state or "unknown")

    def _evidence_recovery_takeover_ready(
        self, marker: Dict[str, Any],
    ) -> bool:
        """May a successor replace this claim, per lease AND liveness?"""
        if str(marker.get("status") or "") != "claimed":
            return False
        try:
            claimed_at = float(marker.get("at"))
            ttl = float(marker.get("ttl") or 0)
        except (TypeError, ValueError):
            return False
        if ttl <= 0 or (time.time() - claimed_at) < ttl:
            return False
        # The lease has elapsed. A live owner is never displaced merely because
        # its adaptation outlived the claim; the claim token, not the clock,
        # remains the cleanup authority.
        return self._evidence_recovery_owner_state(marker) != "live"

    def _claim_evidence_recovery(
        self, run_id: str, key: str,
    ) -> Optional[Dict[str, Any]]:
        """CAS-claim one accepted-evidence recovery attempt.

        The claim is stored on the assignment plan (not a new table/daemon)
        and is bounded by its own recorded TTL. Every successful claim carries
        an opaque ``claim_token`` -- the generation proof used by finish,
        retain and cleanup. Two leases in the SAME process therefore remain
        distinguishable; a process fingerprint is not a generation.

        A different successor that loses the CAS, sees a fresh claim, or sees
        a live owner performs no model call.
        """
        from core.execution_ownership import record_os_start
        from core.task_lifecycle import _current_worker_fingerprint

        ttl = float(os.getenv(
            "ATOM_ASSIGNMENT_EVIDENCE_RECOVERY_CLAIM_TTL", "120") or 120)
        owner = _current_worker_fingerprint()
        owner_process = dict(
            (record_os_start({}) or {}).get("owner") or {})
        # Same opaque generation pattern as the runtime model-attempt claim:
        # cleanup is bound to this exact claim, never to a key or a pid.
        claim_token = uuid.uuid4().hex

        def compute(record, assignment):
            plan = self._evidence_recovery_plan(record)
            if plan is None or plan["key"] != key:
                raise TaskLifecycleError(
                    "accepted evidence changed before the recovery claim")
            claimed_at = time.time()
            updated = copy.deepcopy(assignment)
            updated["evidence_recovery"] = {
                "key": key,
                "status": "claimed",
                "owner": owner,
                "owner_process": owner_process,
                "claim_token": claim_token,
                "at": claimed_at,
                "ttl": ttl,
                "claimed_at": _utc_now_iso(),
                "observation_ids": list(plan["observation_ids"])[:20],
            }
            return updated, {
                "key": key,
                "owner": owner,
                "ttl": ttl,
                "claim_token": claim_token,
            }

        try:
            return self.lifecycle.mutate_assignment(
                run_id, compute,
                rationale="bounded accepted-evidence restart recovery claim")
        except TaskLifecycleError:
            return None

    def _retain_evidence_recovery(
        self,
        run_id: str,
        key: str,
        claim_token: Optional[str],
        *,
        seconds: float,
    ) -> bool:
        """Extend the EXACT live claim for an adaptation still in flight.

        The claim TTL is deliberately shorter than an adaptation deadline, so
        a live owner extends its own lease before calling the consumer. A
        stale token cannot extend a successor's claim, and an already-finished
        claim is never resurrected.
        """
        result: Dict[str, Any] = {"retained": False}

        def compute(record, assignment):
            marker = dict(assignment.get("evidence_recovery") or {})
            if (
                not claim_token
                or str(marker.get("key") or "") != key
                or str(marker.get("status") or "") != "claimed"
                or str(marker.get("claim_token") or "") != str(claim_token)
            ):
                return assignment, {"retained": False, "status": "stale"}
            try:
                keep = max(1.0, float(seconds))
            except (TypeError, ValueError):
                keep = max(1.0, float(marker.get("ttl") or 0))
            # Keep the original claim clock; the lease is at + ttl. A retain
            # can only widen the duration, never reset ownership.
            marker["ttl"] = max(float(marker.get("ttl") or 0), keep)
            marker["retained_at"] = _utc_now_iso()
            updated = copy.deepcopy(assignment)
            updated["evidence_recovery"] = marker
            result["retained"] = True
            return updated, {"retained": True, "ttl": marker["ttl"]}

        try:
            self.lifecycle.mutate_assignment(
                run_id, compute,
                rationale="accepted-evidence recovery claim retained")
        except TaskLifecycleError:
            return False
        return bool(result.get("retained"))

    def _finish_evidence_recovery(
        self,
        run_id: str,
        key: str,
        status: str,
        *,
        claim_token: Optional[str],
        rounds: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record the one-shot recovery outcome for ONE claim generation.

        The token is required and authoritative. A late finish from an expired
        claim must do nothing: overwriting the successor's ``claimed`` marker
        would make the next boot treat unconsumed accepted evidence as already
        attempted and strand it. Key/status/token are checked inside the same
        lifecycle CAS that writes the outcome.
        """
        def compute(record, assignment):
            marker = dict(assignment.get("evidence_recovery") or {})
            if (
                not claim_token
                or str(marker.get("key") or "") != key
                or str(marker.get("status") or "") != "claimed"
                or str(marker.get("claim_token") or "") != str(claim_token)
            ):
                return assignment, {"status": "stale"}
            marker["status"] = status
            marker["finished_at"] = _utc_now_iso()
            if error:
                marker["error"] = str(error)[:500]
            if rounds is not None:
                marker["rounds"] = [
                    {
                        "decision": item.get("decision"),
                        "source": item.get("source"),
                        "adoption_status": item.get("adoption_status"),
                        "execution_status": item.get("execution_status"),
                    }
                    for item in rounds[:3]
                    if isinstance(item, dict)
                ]
            updated = copy.deepcopy(assignment)
            updated["evidence_recovery"] = marker
            return updated, {"status": status}

        try:
            self.lifecycle.mutate_assignment(
                run_id, compute,
                rationale="accepted-evidence restart recovery outcome")
        except TaskLifecycleError:
            # The run moved on (or another writer won). The durable task is
            # authoritative; recovery must not force a stale marker.
            pass

    async def _continue_accepted_evidence(
        self, run_id: str, *, deadline_seconds: float = 180.0,
    ) -> List[Dict[str, Any]]:
        """Hand durable accepted evidence to the EXISTING adaptation consumer.

        No new planner/engine is introduced: this calls the same
        ``_advance_employee_work`` path the source route and ``/advance`` use,
        with an LLM service built from the run's durable workspace/tenant
        scope. Under the test environment the proposal transport is the
        repository's controlled fixture.
        """
        from api.assignment_routes import (
            _advance_employee_work,
            _employee_llm_for_scope,
            _employee_provider_model,
        )
        from core.database import get_db_session

        runs = self.lifecycle.runs
        workspace_id = str(
            getattr(runs, "workspace_id", "default") or "default")
        tenant_id = str(getattr(runs, "tenant_id", "default") or "default")
        with get_db_session() as db:
            llm = _employee_llm_for_scope(db, workspace_id, tenant_id)
            return await _advance_employee_work(
                self, run_id, llm, max_rounds=1,
                deadline_seconds=deadline_seconds,
                provider_model=_employee_provider_model())

    async def _recover_accepted_evidence(
        self, run_id: str, *, deadline_seconds: float = 180.0,
    ) -> Optional[Dict[str, Any]]:
        """Claim and continue ONE run's durable accepted evidence.

        A fresh claim is skipped. If its recorded owner is dead/unknown, a
        bounded wake is scheduled for lease expiry so a one-shot boot cannot
        strand the accepted input forever. A live owner is left alone.
        """
        record = self.lifecycle.get_task(run_id)
        if record is None or record.get("assignment") is None:
            return None
        if str((record.get("assignment") or {}).get("status") or "") in (
                TERMINAL_ASSIGNMENT_STATES):
            return None
        plan = self._evidence_recovery_plan(record)
        if plan is None:
            deferral = self._evidence_recovery_deferral(record)
            if deferral is not None:
                grace = 0.05
                self._schedule_evidence_recovery_wake(
                    run_id, float(deferral["remaining"]) + grace)
            return None
        claim = self._claim_evidence_recovery(run_id, plan["key"])
        if claim is None:
            return None
        claim_token = claim.get("claim_token")
        if not claim_token:
            return None
        # The adaptation deadline can legitimately exceed the base claim TTL.
        # Retain THIS generation before the consumer so a slow live owner is
        # never displaced by the lease while it is still adapting. If the
        # generation already changed, do NOT make the model call: the newer
        # owner is responsible for the accepted evidence.
        retained = self._retain_evidence_recovery(
            run_id, plan["key"], claim_token,
            seconds=max(float(claim.get("ttl") or 0.0),
                        float(deadline_seconds) + 60.0))
        if not retained:
            logger.info(
                "assignment %s: accepted-evidence claim generation changed "
                "before retention; leaving it to the current owner", run_id)
            return {"key": plan["key"], "status": "stale",
                    "claim_token": claim_token}
        try:
            rounds = await self._continue_accepted_evidence(
                run_id, deadline_seconds=deadline_seconds)
            remaining = self._unconsumed_evidence_key(
                self.lifecycle.get_task(run_id) or {})
            status = (
                "completed" if remaining is None
                or remaining["key"] != plan["key"] else "attempted")
            self._finish_evidence_recovery(
                run_id, plan["key"], status,
                claim_token=claim_token, rounds=rounds)
            return {"key": plan["key"], "status": status,
                    "claim_token": claim_token, "rounds": rounds}
        except Exception as exc:  # noqa: BLE001 — per-run isolation
            logger.warning(
                "assignment %s: accepted-evidence recovery failed: %s",
                run_id, exc)
            self._finish_evidence_recovery(
                run_id, plan["key"], "attempted",
                claim_token=claim_token,
                error=f"{type(exc).__name__}: {exc}")
            return {"key": plan["key"], "status": "attempted",
                    "claim_token": claim_token, "error": str(exc)}

    def _schedule_evidence_recovery_wake(
        self, run_id: str, delay: float,
    ) -> bool:
        """Schedule one bounded re-entry after a claim lease expires.

        Reuses the existing recovery owner; it is not a polling daemon and it
        never invents an advance/new task. The durable marker stays the only
        claim authority, so a process that dies before the wake simply leaves
        the same marker for the next boot to reschedule.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        existing = _EVIDENCE_RECOVERY_WAKES.get(run_id)
        if (existing is not None and not existing.done()
                and existing.get_loop() is loop):
            return False
        task = loop.create_task(
            self._deferred_evidence_recovery(run_id, max(0.0, delay)))

        def _forget(done: "asyncio.Task[Any]") -> None:
            if _EVIDENCE_RECOVERY_WAKES.get(run_id) is done:
                _EVIDENCE_RECOVERY_WAKES.pop(run_id, None)

        _EVIDENCE_RECOVERY_WAKES[run_id] = task
        task.add_done_callback(_forget)
        return True

    async def _deferred_evidence_recovery(
        self, run_id: str, delay: float,
    ) -> None:
        """Bounded wake: re-enter the existing recovery owner once at expiry."""
        try:
            await asyncio.sleep(max(0.0, delay))
            record = self.lifecycle.get_task(run_id)
            if record is None or record.get("assignment") is None:
                return
            if str((record.get("assignment") or {}).get("status") or "") in (
                    TERMINAL_ASSIGNMENT_STATES):
                return
            await self._recover_accepted_evidence(run_id)
            await self.execute(run_id, max_steps=20)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — the loop must survive
            logger.warning(
                "assignment %s: deferred accepted-evidence recovery failed: "
                "%s", run_id, exc)

    async def recover_ready_assignments(
        self, *, limit: int = 50, max_steps_per_assignment: int = 20,
    ) -> List[Dict[str, Any]]:
        """Ordinary re-entry pass over active assignments.

        This resumes eligible pending/waiting work from durable state. It
        does NOT assert worker loss and does not call restart recovery; a
        running operation owned by another worker is left intact. The
        explicit ``recover_after_restart`` path owns loss recovery.

        Before ordinary re-entry, an accepted evidence result that was
        committed before a process died is handed to the same employee
        adaptation consumer used by the source route (explicitly claimed and
        one-shot per evidence set). A genuinely missing prerequisite has an
        open obligation and is never model-polled here. A claim whose owner
        died after claiming is deferred to a bounded wake at lease expiry.
        """
        results: List[Dict[str, Any]] = []
        runs = self.lifecycle.runs.list_runs(
            include_terminal=False, limit=max(1, min(int(limit), 200)))
        for run in runs:
            record = self.lifecycle.get_task(run.get("id"))
            if record is None or record.get("assignment") is None:
                continue
            assignment = record["assignment"]
            if assignment.get("status") in TERMINAL_ASSIGNMENT_STATES:
                continue
            self.replay_pending_wake(run["id"])
            await self._recover_accepted_evidence(run["id"])
            execution = await self.execute(
                run["id"], max_steps=max_steps_per_assignment)
            results.append(execution)
        return results


    def _wake_run(self, run_id: str, event: Dict[str, Any]) -> None:
        """Try to consume the matching GoalRun wait (best effort).

        The wake event must match the spec's event type and exact identity
        constraints. An unmatched event leaves the run asleep; it never
        resumes unrelated work.
        """
        try:
            self.lifecycle.runs.consume_wake(run_id, event)
        except Exception as exc:  # noqa: BLE001 — the work record remains
            logger.warning(
                "assignment %s: goal-run wake projection failed: %s",
                run_id, exc)

    # ------------------------------------------------------------- approvals

    def approve_step(
        self,
        run_id: str,
        step_id: str,
        *,
        approved_by: str,
        note: str = "",
    ) -> Dict[str, Any]:
        """Approve the CURRENT prepared payload for one step.

        The prepared payload is recomputed first. If it changed since the
        request, the old request is replaced and this call returns
        ``approval_refreshed`` instead of approving changed content.
        """
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        assignment = record.get("assignment") or {}
        if str((record.get("task_revision") or {}).get("authorization")
               or "").lower() == "cancelled":
            raise AssignmentError(
                "the assignment is cancelled; approval cannot revive it")
        if str(assignment.get("status") or "") == "cancelled":
            raise AssignmentError(
                "the assignment is cancelled; approval cannot revive it")
        step = step_by_id(assignment, step_id)
        if step is None:
            raise AssignmentError(f"unknown step {step_id!r}")
        operation_id = _operation_id_for_step(record, step)
        if not operation_id:
            raise AssignmentError("step has no prepared operation to approve")
        operation = _operation_by_id(record, operation_id) or {}
        if operation.get("status") == "applied":
            return {
                "status": "already_applied",
                "operation": operation,
                "message": "The effect was already applied; no second send.",
            }
        if operation.get("status") != "awaiting_approval":
            raise AssignmentError(
                f"step {step_id} is {operation.get('status')}; "
                f"there is no pending approval")
        prepared = self._prepare_effect(assignment, step, record)
        request = operation.get("approval_request") or {}
        if (prepared["payload_sha256"] != request.get("payload_sha256")
                or str(prepared.get("artifact_revision") or "")
                != str(request.get("artifact_revision") or "")
                or _authorization_revision(assignment)
                != str(request.get("authorization_revision") or "")):
            self.lifecycle.request_operation_approval(
                run_id, operation_id,
                payload=prepared["payload"],
                artifact_revision=prepared.get("artifact_revision"),
                authorization_revision=_authorization_revision(assignment),
                requested_by=prepared.get("requested_by") or approved_by,
                purpose=(step.get("approval") or {}).get("purpose", ""),
            )
            return {
                "status": "approval_refreshed",
                "operation_id": operation_id,
                "message": (
                    "The effect changed after the previous request. Review "
                    "the new payload and approve it explicitly."),
            }
        approved = self.lifecycle.approve_operation(
            run_id, operation_id,
            approved_by=approved_by,
            payload_sha256=prepared["payload_sha256"],
            artifact_revision=prepared.get("artifact_revision"),
            authorization_revision=_authorization_revision(assignment),
            note=note,
        )
        request = approved.get("approval_request") or {}
        hitl_id = (
            (step.get("approval_request") or {}).get("hitl_action_id")
            or request.get("hitl_action_id"))
        self._wake_run(run_id, {
            "event": "human_input",
            "correlation_id": hitl_id,
            "hitl_id": hitl_id,
            "approved": True,
        })
        return {"status": "approved", "operation": approved}

    def reject_step(
        self,
        run_id: str,
        step_id: str,
        *,
        rejected_by: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Record a human rejection of the prepared effect.

        The operation moves to ``rejected`` (terminal); the step is
        cancelled. Downstream steps cannot run because their dependency is
        not applied, and the assignment remains partial/blocked with this
        concrete reason.
        """
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        assignment = record.get("assignment") or {}
        step = step_by_id(assignment, step_id)
        if step is None:
            raise AssignmentError(f"unknown step {step_id!r}")
        operation_id = _operation_id_for_step(record, step)
        if operation_id:
            self.lifecycle.transition_operation(
                run_id, operation_id, "rejected")

        def compute(record, current):
            new_plan = copy.deepcopy(current)
            item = step_by_id(new_plan, step_id)
            if item is not None:
                item["status"] = "failed"
                item["failure"] = {
                    "reason": "approval_rejected",
                    "message": _bounded(reason or "rejected by approver", 500),
                    "rejected_by": _bounded(rejected_by, 200),
                }
                item["updated_at"] = _utc_now_iso()
            new_plan["status"] = "blocked"
            new_plan["updated_at"] = _utc_now_iso()
            return new_plan, {"step_id": step_id, "status": "rejected"}

        result = self.lifecycle.mutate_assignment(
            run_id, compute, rationale=f"step {step_id} approval rejected")
        return {"status": "rejected", **result}

    def invalidate_step(
        self,
        run_id: str,
        step_id: str,
        *,
        reason: str,
    ) -> Dict[str, Any]:
        """Explicitly invalidate a step and all downstream results.

        Prior operation records and prior results are retained for audit;
        affected steps become pending under a new plan revision so the next
        run recomputes them with fresh inputs/teaching.
        """
        def compute(record, assignment):
            step = step_by_id(assignment, step_id)
            if step is None:
                raise AssignmentError(f"unknown step {step_id!r}")
            affected = downstream_step_ids(assignment, [step_id])
            new_plan = copy.deepcopy(assignment)
            new_plan["plan_revision"] = int(
                assignment.get("plan_revision") or 1) + 1
            for item in new_plan.get("steps") or []:
                if item.get("step_id") not in affected:
                    continue
                prior = item.get("prior_results") or []
                if item.get("result") is not None and item.get("status") in (
                        "applied", "failed", "uncertain"):
                    prior.append({
                        "plan_revision": assignment.get("plan_revision"),
                        "status": item.get("status"),
                        "result": copy.deepcopy(item.get("result")),
                        "artifact_revision": item.get("artifact_revision"),
                        "reason": _bounded(reason, 300),
                    })
                item["prior_results"] = prior[-10:]
                if str(item.get("adapter") or "") in (
                        "workbook.read", "document.read"):
                    inputs = item.get("inputs") if isinstance(
                        item.get("inputs"), dict) else {}
                    source_path = str(inputs.get("path") or "")
                    if source_path and os.path.isfile(source_path):
                        refreshed = _sha256_file(source_path)
                        binding = inputs.get("resource_binding")
                        if isinstance(binding, dict) and binding.get(
                                "source_version") not in (None, ""):
                            binding = dict(binding)
                            binding["source_version"] = refreshed
                            inputs["resource_binding"] = binding
                        if inputs.get("source_version") not in (None, ""):
                            inputs["source_version"] = refreshed
                        item["inputs"] = inputs
                item["status"] = "pending"
                item["operation_id"] = None
                item["result"] = None
                item["artifact_revision"] = None
                item["failure"] = None
                item["waiting"] = None
                item["gap_ids"] = []
                item["updated_at"] = _utc_now_iso()
            new_plan["status"] = "planned"
            new_plan["completed_at"] = None
            new_plan["last_transition"] = {
                "kind": "invalidate",
                "reason": _bounded(reason, 500),
                "affected_steps": affected,
                "at": _utc_now_iso(),
            }
            new_plan["updated_at"] = _utc_now_iso()
            return new_plan, {"affected_steps": affected}

        result = self.lifecycle.mutate_assignment(
            run_id, compute, rationale=f"invalidate {step_id}: {reason}")
        return {"status": "invalidated", **result}

    def reassess_teaching(
        self,
        run_id: str,
        teaching_snapshot: Dict[str, Any],
        *,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Adopt corrected teaching and invalidate only dependent work.

        Active work keeps its historical results and artifacts in
        ``prior_results``; steps whose behavior can depend on teaching (and
        their descendants) become pending under a NEW plan revision. Source
        reads and independent branches are preserved.
        """
        sensitive = {
            "quote.calculate", "formula.calculate", "artifact.document",
            "artifact.spreadsheet", "artifact.presentation", "email.draft",
            "action.registry", "assignment.controlled_outbox",
            "email.send_outlook", "external.research",
        }
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        assignment = record.get("assignment") or {}
        running = [step.get("step_id") for step in assignment.get("steps") or []
                   if step.get("status") == "running"]
        if running:
            raise AssignmentError(
                "reassessment cannot invalidate work while steps are running: "
                + ", ".join(str(item) for item in running))

        def compute(record, current):
            roots = [
                step["step_id"] for step in current.get("steps") or []
                if str(step.get("adapter") or "") in sensitive
            ]
            affected = downstream_step_ids(current, roots) if roots else []
            new_plan = copy.deepcopy(current)
            previous = copy.deepcopy(current.get("teaching_snapshot") or {})
            new_plan["plan_revision"] = int(
                current.get("plan_revision") or 1) + 1
            new_plan["teaching_snapshot"] = copy.deepcopy(teaching_snapshot)
            requirements = dict(
                (teaching_snapshot or {}).get("output_requirements") or {})
            for step in new_plan.get("steps") or []:
                adapter = str(step.get("adapter") or "")
                inputs = dict(step.get("inputs") or {})
                if adapter == "quote.calculate":
                    inputs["discount_rules"] = list(
                        requirements.get("line_discount_rules") or [])
                    step["inputs"] = inputs
                elif adapter.startswith("artifact."):
                    inputs["format_spec"] = dict(requirements)
                    step["inputs"] = inputs
            history = list(new_plan.get("teaching_history") or [])
            if previous:
                history.append({
                    "revision": previous.get("revision"),
                    "fingerprint": previous.get("fingerprint"),
                    "replaced_by": teaching_snapshot.get("revision"),
                    "reason": _bounded(reason, 300),
                    "at": _utc_now_iso(),
                })
            new_plan["teaching_history"] = history[-20:]
            for item in new_plan.get("steps") or []:
                if item.get("step_id") not in affected:
                    continue
                prior = item.get("prior_results") or []
                if item.get("result") is not None or item.get(
                        "artifact_revision"):
                    prior.append({
                        "plan_revision": current.get("plan_revision"),
                        "status": item.get("status"),
                        "result": copy.deepcopy(item.get("result")),
                        "artifact_revision": item.get("artifact_revision"),
                        "reason": _bounded(reason, 300),
                    })
                item["prior_results"] = prior[-10:]
                item["status"] = "pending"
                item["operation_id"] = None
                item["result"] = None
                item["artifact_revision"] = None
                item["failure"] = None
                item["waiting"] = None
                item["approval_request"] = None
                item["standing_authority_receipt"] = None
                item["gap_ids"] = []
                item["updated_at"] = _utc_now_iso()
            new_plan["status"] = "planned"
            new_plan["completed_at"] = None
            new_plan["last_transition"] = {
                "kind": "reassess_teaching",
                "reason": _bounded(reason, 500),
                "previous_revision": previous.get("revision"),
                "revision": teaching_snapshot.get("revision"),
                "affected_steps": affected,
                "at": _utc_now_iso(),
            }
            new_plan["updated_at"] = _utc_now_iso()
            return new_plan, {
                "previous_revision": previous.get("revision"),
                "revision": teaching_snapshot.get("revision"),
                "affected_steps": affected,
                "preserved_steps": [
                    step["step_id"] for step in new_plan.get("steps") or []
                    if step["step_id"] not in affected
                ],
            }

        result = self.lifecycle.mutate_assignment(
            run_id, compute,
            rationale=f"reassess teaching: {reason or 'explicit reassessment'}")
        return {"status": "reassessed", **result}

    # --------------------------------------------------------------- gaps

    def _build_gap_resolution_plan(
        self,
        record: Dict[str, Any],
        question: Dict[str, Any],
        *,
        resolution: str,
        current_source: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Read + validate one gap answer without mutating anything.

        This is the pure portion shared by the direct human answer route and
        the external-reply settlement. It re-runs on fresh CAS state; mapping,
        source, unit and teaching authority checks are unchanged from the
        original resolve_gap implementation.
        """
        question_id = str(question.get("question_id") or "")
        mapping = dict((question.get("inputs") or {}).get("mapping") or {})
        plan: Dict[str, Any] = {
            "question_id": question_id,
            "mapping": mapping,
            "mapping_applied": False,
            "confirmed_mapping": {},
            "selected_column": "",
            "selected_unit": "",
            "outcome": "resolved",
        }
        if not mapping:
            return plan
        try:
            parsed = json.loads(str(resolution))
        except (TypeError, ValueError):
            parsed = {"column": str(resolution or "").strip()}
        if not isinstance(parsed, dict):
            raise AssignmentError("a mapping resolution must be an object")
        request_id = str(parsed.get("request_id") or "").strip()
        assignment_id = str(parsed.get("assignment_id") or "").strip()
        if not request_id or request_id != question_id:
            raise AssignmentError(
                "the confirmation does not identify the outstanding mapping request")
        if not assignment_id or assignment_id != str(
                (record.get("assignment") or {}).get("assignment_id") or ""):
            raise AssignmentError(
                "the confirmation belongs to a different assignment")
        if parsed.get("rejected") is True:
            # Rejection is an acknowledgement, not a resolution: the same
            # request and candidate evidence stay outstanding so a restart
            # cannot fork a second clarification.
            plan["outcome"] = "rejected_candidates"
            return plan
        selected_column = str(parsed.get("column") or "").strip()
        selected_unit = str(parsed.get("unit") or "").strip()
        requested_source_version = str(
            parsed.get("source_version") or "").strip()
        if (requested_source_version
                and str(mapping.get("source_version") or "")
                and requested_source_version != str(
                    mapping.get("source_version") or "")):
            raise AssignmentError(
                "stale source version: reconfirm the mapping against "
                "the current schema")
        requested_teaching_revision = str(
            parsed.get("teaching_revision") or "").strip()
        proposal_teaching_revision = str(
            mapping.get("teaching_revision") or "").strip()
        snapshot_teaching_revision = str(
            ((record.get("assignment") or {}).get(
                "teaching_snapshot") or {}).get("revision") or "").strip()
        if requested_teaching_revision:
            if (proposal_teaching_revision
                    and requested_teaching_revision
                    != proposal_teaching_revision):
                raise AssignmentError(
                    "stale teaching revision: reconfirm the mapping "
                    "against the current teaching")
            if (snapshot_teaching_revision
                    and requested_teaching_revision
                    != snapshot_teaching_revision):
                raise AssignmentError(
                    "stale teaching revision: the assignment teaching "
                    "changed after this request was raised")
        candidates = [
            str(item.get("column") or "")
            for item in (mapping.get("candidates") or [])
            if isinstance(item, dict)
        ]
        if not selected_column or selected_column not in candidates:
            raise AssignmentError(
                "the confirmed mapping is not one of the current schema candidates")
        if current_source:
            current_sheet = str(current_source.get("sheet") or "")
            if (current_sheet and str(mapping.get("sheet") or "")
                    and current_sheet != str(mapping.get("sheet") or "")):
                raise AssignmentError(
                    "the current authorized source does not match this "
                    "mapping request")
            current_source_version = str(
                current_source.get("source_version") or "")
            if (current_source_version
                    and str(mapping.get("source_version") or "")
                    and current_source_version != str(
                        mapping.get("source_version") or "")):
                raise AssignmentError(
                    "stale source version: the current authorized source "
                    "changed after this request was raised")
            allowed_columns = [
                str(column) for column in
                current_source.get("columns") or []
                if str(column)
            ]
            if allowed_columns and selected_column not in allowed_columns:
                raise AssignmentError(
                    "the confirmed mapping is not in the current "
                    "authorized source schema")
        source = next((
            item for item in (record.get("assignment") or {}).get("sources") or []
            if str((item.get("binding") or {}).get("external_id") or "")
            == str(mapping.get("external_id") or "")
            and str((item.get("binding") or {}).get("sheet") or "")
            == str(mapping.get("sheet") or "")
        ), None)
        current_version = str(
            ((source or {}).get("binding") or {}).get("source_version") or "")
        if (str(mapping.get("source_version") or "")
                and current_version != str(mapping.get("source_version"))):
            raise AssignmentError(
                "the source version changed; reconfirm the mapping against the current schema")
        required_unit = str(mapping.get("required_unit") or "").strip()
        source_unit = str(mapping.get("source_unit") or "").strip()
        # Three separate authorities: taught requirement, source evidence,
        # and the user's explicit confirmation. A taught unit is never
        # substituted for missing source information, and a source unit is
        # not silently certified when the source does not establish one.
        unit_authority = ""
        if selected_unit:
            unit_authority = (
                "source_evidence" if source_unit else "user_confirmed")
        elif source_unit:
            selected_unit = source_unit
            unit_authority = "source_evidence"
        elif required_unit:
            raise AssignmentError(
                "the taught method requires an explicit unit confirmation")
        if source_unit and selected_unit and (
                source_unit.lower() != selected_unit.lower()):
            raise AssignmentError(
                f"the confirmed unit '{selected_unit}' conflicts with "
                f"the source evidence unit '{source_unit}'")
        if required_unit and selected_unit and (
                required_unit.lower() != selected_unit.lower()):
            raise AssignmentError(
                f"the confirmed unit '{selected_unit}' does not match "
                f"the taught unit '{required_unit}'; no conversion is authorized")
        source_mapping = dict(mapping.get("mapping_source") or {})
        confirmed_mapping = {
            "concept": str(
                mapping.get("concept")
                or mapping.get("missing_column") or ""),
            "sheet": str(mapping.get("sheet") or ""),
            "column": selected_column,
            "unit": selected_unit or str(source_mapping.get("unit") or ""),
            "unit_authority": unit_authority,
            "required_unit": required_unit,
            "source_unit": source_unit,
            "source_unit_column": str(
                mapping.get("source_unit_column") or ""),
            "source_version": str(mapping.get("source_version") or ""),
            "revision": int(source_mapping.get("revision") or 1) + 1,
        }
        if source_mapping.get("lesson_id"):
            confirmed_mapping["lesson_id"] = source_mapping["lesson_id"]
        plan.update({
            "mapping_applied": True,
            "confirmed_mapping": confirmed_mapping,
            "selected_column": selected_column,
            "selected_unit": selected_unit,
        })
        return plan

    def _persist_gap_mapping_lesson(
        self,
        lesson_id: str,
        agent_id: str,
        confirmed_mapping: Dict[str, Any],
    ) -> None:
        """Persist a confirmed mapping to the shared teaching point (best effort)."""
        if not lesson_id or not agent_id:
            return
        try:
            from core.database import get_db_session
            from core.student_learning_service import update_teaching_point

            with get_db_session() as db:
                update_teaching_point(
                    db, agent_id, lesson_id,
                    context={"field_mappings": [dict(confirmed_mapping)]},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "mapping lesson update skipped for %s: %s", lesson_id, exc)

    def resolve_gap(
        self,
        run_id: str,
        question_id: str,
        *,
        resolution: str,
        resolved_by: str = "",
        evidence: str = "",
        current_source: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a human/external answer and reopen the waiting step.

        The answer is evidence for the task. It never becomes teaching and
        never grants an action.
        """
        if not str(resolution or "").strip():
            raise AssignmentError("a gap resolution requires a value")
        record = self.lifecycle.get_task(run_id) or {}
        question = {}
        waiting = {}
        for item in (record.get("task_revision") or {}).get(
                "unresolved") or []:
            if item.get("question_id") == question_id:
                question = dict(item)
                waiting = dict(item.get("waiting") or {})
                break
        if not question:
            raise AssignmentError("the outstanding request was not found")
        if question.get("status") != "open":
            if resolution_matches(
                    question.get("resolution"), resolution,
                    question.get("resolution_value")):
                current = self.status(run_id)
                return {
                    "status": "already_resolved",
                    "assignment": current.get("assignment"),
                    "open_gaps": current.get("open_gaps") or [],
                }
            raise AssignmentError(
                "the gap was already resolved with a different answer")
        if not _gap_question_binding_valid(
                record, record.get("assignment") or {}, question,
                _step_for_gap_question(record.get("assignment") or {}, question)):
            raise AssignmentError("The question's declared step/operation binding is unavailable")
        plan = self._build_gap_resolution_plan(
            record, question, resolution=resolution,
            current_source=current_source)
        if plan.get("outcome") == "rejected_candidates":
            current = self.status(run_id)
            return {
                "status": "rejected_candidates",
                "assignment": current.get("assignment"),
                "open_gaps": current.get("open_gaps") or [],
            }
        mapping = plan["mapping"]
        mapping_applied = bool(plan.get("mapping_applied"))
        confirmed_mapping = plan.get("confirmed_mapping") or {}
        # Close the waiting attempt honestly; the reopened step gets a NEW
        # operation under the next attempt key. Reusing the waiting record
        # would make the executor believe it is still blocked.
        waiting_operation_id = ""
        for step in record.get("assignment", {}).get("steps") or []:
            if question_id not in (step.get("gap_ids") or []):
                continue
            waiting_operation_id = _operation_id_for_step(record, step) or ""
            break
        transition = {
            "kind": "record_unresolved",
            "requested_change": f"resolved {question_id}",
            "resolutions": [{
                "question_id": question_id,
                "resolution": _bounded(
                    f"{resolution}"
                    + (f" [by {resolved_by}]" if resolved_by else "")
                    + (f" [evidence: {evidence}]" if evidence else ""),
                    400),
                "value": _bounded(resolution, 400),
            }],
        }
        if waiting_operation_id:
            operation = _operation_by_id(record, waiting_operation_id) or {}
            if operation.get("status") == "waiting":
                transition["supersede_operations"] = [waiting_operation_id]

        def compute(record, assignment):
            fresh_question = next((
                item for item in (record.get("task_revision") or {}).get("unresolved") or []
                if item.get("question_id") == question_id), {})
            if not fresh_question:
                raise AssignmentError("The outstanding question changed before settlement")
            if fresh_question.get("status") != "open":
                if resolution_matches(
                        fresh_question.get("resolution"), resolution,
                        fresh_question.get("resolution_value")):
                    raise _ExternalReplyStop({
                        "status": "already_resolved",
                        "assignment": assignment_projection(assignment),
                        "open_gaps": open_unresolved_questions(record),
                    })
                raise AssignmentError("The question was settled with a different answer")
            material_keys = (
                "question_id", "kind", "concept", "question", "inputs",
                "waiting", "step_id", "source_operation", "affected_subjects")
            if canonical_sha256({key: fresh_question.get(key) for key in material_keys}) != (
                    canonical_sha256({key: question.get(key) for key in material_keys})):
                raise AssignmentError("The question material changed before settlement")
            if not _gap_question_binding_valid(
                    record, assignment, fresh_question,
                    _step_for_gap_question(assignment, fresh_question)):
                raise AssignmentError("The question's declared binding changed before settlement")
            new_plan = copy.deepcopy(assignment)
            reopened = _reopen_resolved_gap_steps(
                new_plan, question_id,
                mapping=mapping, mapping_applied=mapping_applied,
                confirmed_mapping=confirmed_mapping)
            return new_plan, {"reopened_steps": reopened}, transition

        try:
            result = self.lifecycle.mutate_assignment_and_task(
                run_id, compute, rationale=f"gap {question_id} resolved")
        except _ExternalReplyStop as stop:
            # A peer accepted the identical answer. Acknowledge its durable
            # settlement without another revision, reopen, wake or effect.
            return stop.result
        if mapping_applied:
            self._persist_gap_mapping_lesson(
                str((mapping.get("mapping_source") or {}).get("lesson_id") or ""),
                str(((record.get("assignment") or {}).get("provenance") or {}
                     ).get("agent_id") or ""),
                confirmed_mapping)
        self._wake_run(run_id, {
            "event": str(waiting.get("event") or "human_input"),
            "correlation_id": waiting.get("correlation_id"),
            "question_id": question_id,
            "source": "assignment_gap_resolution",
        })
        return {"status": "resolved", **result}

    def correct_mapping(
        self,
        run_id: str,
        *,
        concept: str,
        expected_revision: int,
        column: str,
        unit: str = "",
        corrected_by: str = "",
        current_source: Optional[Dict[str, Any]] = None,
        evidence: str = "",
        sheet: str = "",
        source_version: str = "",
    ) -> Dict[str, Any]:
        """Correct one confirmed mapping and its dependants.

        The mapping revision is an optimistic concurrency token. The current
        authorized source is re-read before mutation. Prior results and
        artifacts stay in step/deliverable history; affected work is re-run
        under a new plan revision. Applied external effects are never replayed
        automatically.
        """
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        assignment = record.get("assignment") or {}
        if not assignment:
            raise AssignmentError(f"run {run_id} has no assignment plan")
        if assignment.get("status") == "cancelled" or str(
                (record.get("task_revision") or {}).get("authorization")
                or "").lower() == "cancelled":
            raise AssignmentError(
                "the assignment is cancelled; a mapping cannot be corrected")
        concept_value = str(concept or "").strip()
        if not concept_value:
            raise AssignmentError("a mapping correction requires a concept")
        snapshot = assignment.get("teaching_snapshot") or {}
        mappings = [
            dict(item) for item in snapshot.get("field_mappings") or []
            if isinstance(item, dict)
        ]
        selection, selection_problem = select_confirmed_mapping(
            mappings, concept=concept_value, sheet=sheet,
            source_version=source_version)
        if selection_problem == "ambiguous":
            raise AssignmentError(
                f"more than one confirmed mapping exists for concept "
                f"'{concept_value}'; name the sheet or source version")
        if selection is None:
            raise AssignmentError(
                f"no confirmed mapping exists for concept '{concept_value}'")
        index, mapping = selection
        mapping_sheet = str(sheet or mapping.get("sheet") or "")
        mapping_version = str(
            source_version or mapping.get("source_version") or "")
        expected = int(expected_revision or 0)
        current_revision = int(mapping.get("revision") or 1)
        if expected != current_revision:
            raise AssignmentError(
                f"stale mapping revision: expected {expected}, current "
                f"{current_revision}")
        replacement = str(column or "").strip()
        if not replacement:
            raise AssignmentError("a mapping correction requires a column")
        if replacement.lower() == str(
                mapping.get("column") or "").strip().lower():
            raise AssignmentError(
                "the replacement column is already the current mapping")
        source_binding = {}
        for raw_source in assignment.get("sources") or []:
            binding = dict(raw_source.get("binding") or {})
            if str(binding.get("sheet") or "") != str(
                    mapping.get("sheet") or ""):
                continue
            mapped_version = str(mapping.get("source_version") or "")
            if mapped_version and str(
                    binding.get("source_version") or "") != mapped_version:
                continue
            source_binding = binding
            break
        if not source_binding:
            raise AssignmentError(
                "the mapping's authorized source is no longer part of this "
                "assignment")
        current = dict(current_source or {})
        if current:
            for field in ("external_id", "sheet"):
                expected_value = str(source_binding.get(field) or "")
                actual_value = str(current.get(field) or "")
                if expected_value and actual_value and (
                        expected_value != actual_value):
                    raise AssignmentError(
                        "the resolved source does not match the assignment "
                        "mapping")
            current_version = str(current.get("source_version") or "")
            binding_version = str(source_binding.get("source_version") or "")
            if not current_version or current_version != binding_version:
                raise AssignmentError(
                    "the source version changed; reconfirm the mapping "
                    "against the current schema")
            allowed_columns = [
                str(item) for item in current.get("columns") or []
                if str(item)
            ]
            numeric_columns = [
                str(item) for item in current.get("numeric_columns") or []
                if str(item)
            ]
        else:
            allowed_columns = [
                str(item) for item in source_binding.get("columns") or []
                if str(item)
            ]
            numeric_columns = [
                str(item)
                for item in source_binding.get("numeric_columns") or []
                if str(item)
            ]
        if replacement == "__sheet_row" or replacement not in allowed_columns:
            raise AssignmentError(
                "the replacement column is not in the current authorized "
                "source schema")
        roots = _mapping_affected_roots(
            assignment, column=str(mapping.get("column") or ""),
            concept=concept_value)
        if not roots:
            raise AssignmentError(
                "no assignment work depends on this mapping")
        affected = downstream_step_ids(assignment, roots)
        by_id = {
            step["step_id"]: step for step in assignment.get("steps") or []
        }
        numeric_required = any(
            by_id.get(step_id, {}).get("adapter") == "dataset.aggregate"
            and str((by_id.get(step_id, {}).get("inputs") or {}).get(
                "operation") or "sum").lower() == "sum"
            for step_id in affected
        )
        if numeric_required and numeric_columns and (
                replacement not in numeric_columns):
            raise AssignmentError(
                "the replacement column is not numeric for the affected "
                "calculation")
        for step_id in affected:
            step = by_id.get(step_id) or {}
            status = str(step.get("status") or "")
            if status == "running":
                raise AssignmentError(
                    "affected work is running; correct the mapping after it "
                    "settles")
            if str(step.get("effect") or "") == "external" and status in (
                    "applied", "failed", "uncertain", "awaiting_approval"):
                raise AssignmentError(
                    "correction would replay an external effect; the applied "
                    "effect is preserved and is not re-run automatically")
        source_unit, source_unit_column = "", ""
        if current.get("path"):
            try:
                source_unit, source_unit_column = _source_unit_from_path(
                    str(current["path"]))
            except Exception as exc:  # noqa: BLE001
                raise AssignmentError(
                    "the current authorized source could not be read for "
                    "correction") from exc
        else:
            source_unit = str(current.get("source_unit") or "").strip().upper()
            source_unit_column = str(
                current.get("source_unit_column") or "")
        required_unit = str(mapping.get("required_unit") or "").strip()
        if not required_unit and str(
                mapping.get("unit_authority") or "") == "user_confirmed":
            required_unit = str(mapping.get("unit") or "").strip()
        selected_unit = str(unit or "").strip()
        if selected_unit:
            unit_authority = (
                "source_evidence" if source_unit else "user_confirmed")
        elif source_unit:
            selected_unit = source_unit
            unit_authority = "source_evidence"
        elif required_unit:
            raise AssignmentError(
                "the taught method requires an explicit unit confirmation")
        else:
            unit_authority = str(mapping.get("unit_authority") or "")
        if source_unit and selected_unit and (
                source_unit.lower() != selected_unit.lower()):
            raise AssignmentError(
                f"the confirmed unit '{selected_unit}' conflicts with the "
                f"source evidence unit '{source_unit}'")
        if required_unit and selected_unit and (
                required_unit.lower() != selected_unit.lower()):
            raise AssignmentError(
                f"the confirmed unit '{selected_unit}' does not match the "
                f"taught unit '{required_unit}'; no conversion is authorized")
        effective_unit = selected_unit or str(mapping.get("unit") or "")
        new_revision = current_revision + 1
        corrected_at = _utc_now_iso()
        new_mapping = {
            **mapping,
            "column": replacement,
            "unit": effective_unit,
            "unit_authority": unit_authority,
            "required_unit": required_unit,
            "source_unit": source_unit,
            "source_unit_column": source_unit_column,
            "source_version": str(
                source_binding.get("source_version") or ""),
            "revision": new_revision,
            "corrected_from_revision": current_revision,
            "corrected_by": _bounded(corrected_by, 200),
            "corrected_at": corrected_at,
        }
        history_entry = {
            **mapping,
            "replaced_by_revision": new_revision,
            "corrected_by": _bounded(corrected_by, 200),
            "corrected_at": corrected_at,
            "reason": _bounded(evidence or "mapping corrected", 500),
        }

        def compute(record, current_assignment):
            current_mappings = [
                dict(item) for item in (
                    current_assignment.get("teaching_snapshot") or {}
                ).get("field_mappings") or [] if isinstance(item, dict)
            ]
            current_selection, current_problem = select_confirmed_mapping(
                current_mappings, concept=concept_value, sheet=mapping_sheet,
                source_version=mapping_version)
            if current_problem == "ambiguous":
                raise AssignmentError(
                    "more than one confirmed mapping matched during this "
                    "correction; name the sheet or source version")
            if current_selection is None:
                raise AssignmentError(
                    "the confirmed mapping disappeared before correction")
            current_index, _current_mapping = current_selection
            if int(current_mappings[current_index].get("revision") or 1) != expected:
                raise AssignmentError(
                    "stale mapping revision: the mapping changed during this "
                    "correction")
            new_plan = copy.deepcopy(current_assignment)
            new_snapshot = dict(new_plan.get("teaching_snapshot") or {})
            current_mappings[current_index] = new_mapping
            new_snapshot = new_teaching_snapshot(
                revision=(
                    str(new_snapshot.get("revision") or "untrained")
                    + "+corr"),
                effective_lesson_ids=new_snapshot.get(
                    "effective_lesson_ids") or [],
                applicable_conditions=new_snapshot.get(
                    "applicable_conditions") or {},
                matched_context=new_snapshot.get("matched_context") or {},
                unresolved_conditions=new_snapshot.get(
                    "unresolved_conditions") or [],
                conflicting_conditions=new_snapshot.get(
                    "conflicting_conditions") or [],
                field_mappings=current_mappings,
                source_versions=new_snapshot.get("source_versions") or {},
                output_requirements=new_snapshot.get(
                    "output_requirements") or {},
                decision_schema=new_snapshot.get("decision_schema") or [],
                artifact_requirements=new_snapshot.get(
                    "artifact_requirements") or {},
            )
            new_plan["teaching_snapshot"] = new_snapshot
            history = [
                dict(item) for item in new_plan.get("mapping_history") or []
                if isinstance(item, dict)
            ]
            history.append(history_entry)
            new_plan["mapping_history"] = history[-20:]
            new_plan["plan_revision"] = int(
                current_assignment.get("plan_revision") or 1) + 1
            roots_now = _mapping_affected_roots(
                new_plan, column=str(mapping.get("column") or ""),
                concept=concept_value)
            affected_now = downstream_step_ids(new_plan, roots_now)
            for step in new_plan.get("steps") or []:
                if step.get("step_id") not in affected_now:
                    continue
                status = str(step.get("status") or "")
                if str(step.get("effect") or "") == "external" and status in (
                        "applied", "failed", "uncertain", "awaiting_approval"):
                    raise AssignmentError(
                        "correction would replay an external effect; the "
                        "applied effect is preserved and is not re-run "
                        "automatically")
                prior = [
                    dict(item) for item in step.get("prior_results") or []
                    if isinstance(item, dict)
                ]
                if step.get("result") is not None and status in (
                        "applied", "failed", "uncertain"):
                    prior.append({
                        "plan_revision": current_assignment.get(
                            "plan_revision"),
                        "status": status,
                        "result": copy.deepcopy(step.get("result")),
                        "artifact_revision": step.get("artifact_revision"),
                        "reason": _bounded(
                            f"mapping {concept_value} corrected from "
                            f"'{mapping.get('column')}' to '{replacement}'",
                            300),
                    })
                inputs = copy.deepcopy(step.get("inputs") or {})
                inputs = _replace_mapping_value(
                    inputs, str(mapping.get("column") or ""), replacement)
                inputs = _replace_mapping_value(
                    inputs, concept_value, replacement)
                if str(step.get("adapter") or "").startswith("artifact."):
                    old_path = str(inputs.get("path") or "").strip()
                    if old_path:
                        inputs["path"] = _corrected_artifact_path(
                            old_path, new_plan["plan_revision"])
                step["inputs"] = inputs
                step["prior_results"] = prior[-10:]
                step["status"] = "pending"
                step["operation_id"] = None
                step["result"] = None
                step["artifact_revision"] = None
                step["failure"] = None
                step["waiting"] = None
                step["gap_ids"] = []
                step["updated_at"] = _utc_now_iso()
            affected_step_ids = set(affected_now)
            for deliverable in new_plan.get("deliverables") or []:
                if deliverable.get("step_id") not in affected_step_ids:
                    continue
                prior_artifacts = [
                    dict(item) for item in
                    deliverable.get("prior_artifacts") or []
                    if isinstance(item, dict)
                ]
                if deliverable.get("artifact_path") or deliverable.get(
                        "sha256"):
                    prior_artifacts.append({
                        "plan_revision": current_assignment.get(
                            "plan_revision"),
                        "artifact_path": deliverable.get("artifact_path"),
                        "sha256": deliverable.get("sha256"),
                        "artifact_revision": deliverable.get(
                            "artifact_revision"),
                        "reason": f"mapping correction {concept_value}",
                    })
                deliverable["prior_artifacts"] = prior_artifacts[-10:]
                deliverable["status"] = "pending"
                deliverable["artifact_revision"] = None
                deliverable["artifact_path"] = None
                deliverable["sha256"] = None
            new_plan["status"] = "planned"
            new_plan["completed_at"] = None
            new_plan["last_transition"] = {
                "kind": "mapping_correction",
                "concept": concept_value,
                "from_column": str(mapping.get("column") or ""),
                "to_column": replacement,
                "from_revision": current_revision,
                "to_revision": new_revision,
                "affected_steps": affected_now,
                "at": corrected_at,
            }
            new_plan["updated_at"] = corrected_at
            return new_plan, {
                "concept": concept_value,
                "column": replacement,
                "revision": new_revision,
                "affected_steps": affected_now,
            }

        result = self.lifecycle.mutate_assignment(
            run_id, compute,
            rationale=(
                f"correct mapping {concept_value} revision "
                f"{current_revision} -> {new_revision}"))
        lesson_id = str(mapping.get("lesson_id") or "")
        agent_id = str(
            (assignment.get("provenance") or {}).get("agent_id") or "")
        if lesson_id and agent_id:
            try:
                from core.database import get_db_session
                from core.models import AgentRegistry
                from core.student_learning_service import (
                    resolve_teaching_point,
                    update_teaching_point,
                )

                with get_db_session() as db:
                    agent = db.query(AgentRegistry).filter(
                        AgentRegistry.id == agent_id).first()
                    resolved_lesson = (
                        resolve_teaching_point(agent, lesson_id)
                        if agent is not None else None)
                    current_lesson_revision = 0
                    if resolved_lesson:
                        _index, lesson_entry = resolved_lesson
                        for item in ((lesson_entry.get("context") or {}).get(
                                "field_mappings") or []):
                            if (str(item.get("concept") or "").lower()
                                    == concept_value.lower()):
                                current_lesson_revision = int(
                                    item.get("revision") or 1)
                                break
                    if current_lesson_revision > new_revision:
                        # Another assignment already advanced the shared
                        # teaching point. Do not regress it from an older
                        # assignment snapshot; this assignment keeps its own
                        # corrected mapping.
                        logger.warning(
                            "mapping correction %s left teaching point %s at "
                            "newer revision %s (assignment revision %s)",
                            concept_value, lesson_id,
                            current_lesson_revision, new_revision)
                    else:
                        update_teaching_point(
                            db, agent_id, lesson_id,
                            context={"field_mappings": [dict(new_mapping)]})
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "mapping correction lesson update skipped for %s: %s",
                    lesson_id, exc)
        return {"status": "corrected", **result}

    def _compute_gap_external_response(
        self,
        record: Dict[str, Any],
        current: Dict[str, Any],
        question: Dict[str, Any],
        *,
        correlation_id: str,
        response: str,
        source: str,
        evidence: str,
        value: Any,
        reply_id: Optional[str],
    ):
        """Settle one question reply inside the shared lifecycle CAS.

        The question and any backing step are re-read from the fresh record.
        Clarification-only questions keep the same receipts on the existing
        assignment document; they never acquire a fabricated execution step.
        Identity/material checks, the accepted receipt, the question
        resolution, the reopened step and the superseded waiting operation all
        commit in one ``_mutate`` write. Non-resolving outcomes retain a
        receipt/conflict but never resolve, reopen or wake.
        """
        assignment_status = str(current.get("status") or "")
        question_id = str(question.get("question_id") or "")
        step = _step_for_gap_question(current, question)
        step_id = str((step or {}).get("step_id") or "")
        waiting = dict(question.get("waiting") or {})
        projection = _gap_reply_waiting_projection(question)
        fact = str(projection.get("fact") or "")
        subject = str(projection.get("subject") or "")
        try:
            digest = _external_reply_material_sha256(
                correlation_id=correlation_id, waiting=projection,
                response=response, source=source, evidence=evidence,
                value=value)
        except (TypeError, ValueError) as exc:
            raise _ExternalReplyStop({
                "status": "reply_conflict",
                "message": (
                    "The authorized reply material could not be bound "
                    "exactly; no question or wait state was changed."),
                "reason": "reply_material_unbindable",
                "step_id": step_id,
                "material_sha256": "",
                "detail": _bounded(str(exc), 300),
            })
        explicit = reply_id is not None
        steps = [
            item for item in (current.get("steps") or [])
            if isinstance(item, dict)
        ]

        def identity_conflict(reason, message, existing_digest=""):
            return {
                "status": "reply_conflict",
                "message": message,
                "reason": reason,
                "step_id": step_id,
                "question_id": question_id,
                "reply_id": reply_id if reply_id is not None else "",
                "material_sha256": digest,
                "expected_material_sha256": existing_digest,
            }

        # An explicit id names one run/wait scope. Question scope is its
        # structured concept + stable affected subjects + correlation, not the
        # backing step identity (a re-raised question on the same conceptual
        # wait is the same scope).
        if explicit:
            for other in [*steps, current]:
                for receipt in _external_reply_receipts(other):
                    if str(receipt.get("identity_kind") or "") != "explicit":
                        continue
                    if str(receipt.get("reply_id") or "") != str(reply_id):
                        continue
                    if not _external_reply_scope_matches(
                            receipt,
                            correlation_id=correlation_id,
                            fact=fact, subject=subject):
                        raise _ExternalReplyStop(identity_conflict(
                            "reply_scope_conflict",
                            "This reply identity is already bound to a "
                            "different durable question/wait; it was not used.",
                            str(receipt.get("material_sha256") or "")))

        # Receipts are append-only on the backing step, but a re-raised
        # question may legitimately live on a new step. Read the whole
        # assignment's question receipts so exact replay still works after the
        # original wait is cleared/closed.
        all_receipts: List[Dict[str, Any]] = []
        for item in [*steps, current]:
            all_receipts.extend(_external_reply_receipts(item))
        matches = _external_reply_matching_receipts(
            all_receipts, reply_id=reply_id, digest=digest,
            correlation_id=correlation_id, fact=fact, subject=subject)
        if matches:
            if any(str(item.get("material_sha256") or "") != digest
                   for item in matches):
                raise _ExternalReplyStop(identity_conflict(
                    "reply_id_material_conflict",
                    "This reply identity was already used with different "
                    "material; the changed reply was refused before any "
                    "question, step or receipt write.",
                    str(matches[-1].get("material_sha256") or "")))
            raise _ExternalReplyStop(
                _external_reply_replay_result(
                    matches[-1], step or {}, assignment_status,
                    explicit=explicit))

        # Exact receipt replay is checked first; only a new/changed reply can
        # meet a terminal assignment or an already-settled question.
        if (assignment_status in TERMINAL_ASSIGNMENT_STATES
                or str(question.get("status") or "") != "open"):
            raise _ExternalReplyStop({
                "status": "terminal",
                "assignment_status": assignment_status,
                "message": (
                    f"The assignment/question wait is {assignment_status or 'settled'}; "
                    "this new or changed reply identity was not used."),
            })

        if not _gap_question_binding_valid(record, current, question, step):
            raise _ExternalReplyStop({
                "status": "unmatched",
                "message": (
                    "No step carries this gap question. The response was not "
                    "used to resume work."),
            })

        resolution_text = str(response or "")
        if not resolution_text.strip() and value not in (None, ""):
            resolution_text = str(value)
        plan = self._build_gap_resolution_plan(
            record, question, resolution=resolution_text)
        if plan.get("outcome") != "resolved":
            outcome = str(plan.get("outcome") or "conflict")
            conflict = {
                "correlation_id": str(correlation_id or ""),
                "fact": fact,
                "subject": subject,
                "response": _bounded(response, 2000),
                "source": _bounded(source, 200),
                "evidence": _bounded(evidence, 500),
                "at": _utc_now_iso(),
                "reason": "candidates_rejected",
                "reply_id": reply_id if reply_id is not None else "",
                "identity_kind": _external_reply_identity_kind(reply_id),
                "material_sha256": digest,
                "rejected": True,
            }
            message = (
                "The reply rejected the current candidates; the question "
                "remains open and was not reopened or woken.")
            new_plan = copy.deepcopy(current)
            item = step_by_id(new_plan, step_id) if step is not None else new_plan
            if item is None:
                raise _ExternalReplyStop({"status": "unmatched",
                    "message": "The backing question step is unavailable."})
            item_receipts = _external_reply_receipts(item)
            item_receipts.append(_external_reply_receipt(
                reply_id=reply_id, digest=digest,
                correlation_id=correlation_id, waiting=projection,
                outcome=outcome, reason="candidates_rejected",
                message=message, conflict=conflict))
            item["reply_receipts"] = item_receipts
            if step is not None:
                waiting_now = dict(item.get("waiting") or {})
                conflicts = [
                    dict(entry) for entry in
                    (waiting_now.get("conflicts") or [])
                    if isinstance(entry, dict)
                ]
                conflicts.append(conflict)
                waiting_now["conflicts"] = conflicts[-10:]
                item["waiting"] = waiting_now
            item["updated_at"] = _utc_now_iso()
            new_plan["updated_at"] = _utc_now_iso()
            return new_plan, {
                "status": outcome,
                "message": message,
                "fact": fact,
                "conflict": conflict,
                "step_id": step_id,
                "question_id": question_id,
                "reply_id": reply_id if reply_id is not None else "",
                "material_sha256": digest,
                "replayed": False,
            }, None

        # Resolve the question, reopen the blocked step, keep the accepted
        # receipt and supersede the old waiting operation in ONE CAS write.
        operation_id = (
            (_operation_id_for_step(record, step) or "")
            if step is not None else "")
        accepted_at = _utc_now_iso()
        new_plan = copy.deepcopy(current)
        reopened = _reopen_resolved_gap_steps(
            new_plan, question_id,
            mapping=plan["mapping"],
            mapping_applied=bool(plan.get("mapping_applied")),
            confirmed_mapping=plan.get("confirmed_mapping") or {})
        item = step_by_id(new_plan, step_id) if step is not None else new_plan
        if item is None:
            raise _ExternalReplyStop({"status": "unmatched",
                "message": "The backing question step is unavailable."})
        accepted_response = {
            "correlation_id": correlation_id,
            "fact": fact,
            "subject": subject,
            "party": str(waiting.get("party") or ""),
            "typed_binding": False,
            "expected_answer_type": "",
            "response": _bounded(response, 2000),
            "source": _bounded(source, 200),
            "evidence": _bounded(evidence, 500),
            "fact_resolution": {},
            "reply_id": reply_id if reply_id is not None else "",
            "identity_kind": _external_reply_identity_kind(reply_id),
            "material_sha256": digest,
            "at": accepted_at,
        }
        if step is not None:
            item["external_response"] = accepted_response
        item_receipts = _external_reply_receipts(item)
        item_receipts.append(_external_reply_receipt(
            reply_id=reply_id, digest=digest,
            correlation_id=correlation_id, waiting=projection,
            outcome="resolved", reason="gap_resolved",
            message="The authorized reply resolved the durable question."))
        item["reply_receipts"] = item_receipts
        item["updated_at"] = accepted_at
        new_plan["status"] = "planned"
        new_plan["updated_at"] = accepted_at

        resolution_value = (
            value if value not in (None, "") else resolution_text)
        transition = {
            "kind": "record_unresolved",
            "requested_change": f"resolved {question_id}",
            "resolutions": [{
                "question_id": question_id,
                "resolution": _bounded(
                    f"{resolution_text}"
                    + (f" [by {source}]" if source else "")
                    + (f" [evidence: {evidence}]" if evidence else ""),
                    400),
                "value": _bounded(resolution_value, 400),
            }],
        }
        if operation_id:
            operation = _operation_by_id(record, operation_id) or {}
            if operation.get("status") == "waiting":
                transition["supersede_operations"] = [operation_id]
        result = {
            "status": "resolved",
            "reopened_steps": reopened,
            "step_id": step_id,
            "question_id": question_id,
            "operation_id": operation_id or None,
            "event": str(waiting.get("event") or "human_input"),
            "correlation_id": correlation_id,
            "reply_id": reply_id if reply_id is not None else "",
            "material_sha256": digest,
        }
        if plan.get("mapping_applied"):
            mapping = plan["mapping"]
            result["_mapping_lesson"] = {
                "lesson_id": str(
                    (mapping.get("mapping_source") or {}).get(
                        "lesson_id") or ""),
                "agent_id": str(
                    ((record.get("assignment") or {}).get("provenance") or {}
                     ).get("agent_id") or ""),
                "confirmed_mapping": plan.get("confirmed_mapping") or {},
            }
        return new_plan, result, transition

    def record_external_response(
        self,
        run_id: str,
        correlation_id: str,
        *,
        response: str,
        source: str = "",
        evidence: str = "",
        value: Any = None,
        reply_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Match an authorized external reply to the waiting question.

        Matching is by the durable correlation id, never by message wording.
        An unmatched response is kept as evidence only and does not resume
        work.

        An explicit opaque ``reply_id`` binds this run/wait scope to the exact
        canonical material. A replay of the same identity + material is
        idempotent; the same identity with any changed material is refused
        before a state transition. Omitted IDs retain legacy behaviour by
        deriving identity from the exact material digest + wait scope, so an
        identical unkeyed retry replays while a corrected unkeyed reply remains
        a new event. Reply IDs are identity, never authentication or scope
        authority.
        """
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")

        # Every identity, terminal, material and readiness decision is
        # re-evaluated inside the lifecycle CAS callback below, so a concurrent
        # writer cannot both wake. A question wait and a direct step wait share
        # the same append-only step receipts; they are not separate authority.
        def compute(record, current):
            gap_question = _find_gap_reply_target(record, correlation_id)
            if gap_question is not None:
                return self._compute_gap_external_response(
                    record, current, gap_question,
                    correlation_id=correlation_id, response=response,
                    source=source, evidence=evidence, value=value,
                    reply_id=reply_id)
            assignment_status = str(current.get("status") or "")
            steps = [
                step for step in (current.get("steps") or [])
                if isinstance(step, dict)
            ]
            step = None
            for candidate in steps:
                waiting_candidate = candidate.get("waiting")
                if not isinstance(waiting_candidate, dict):
                    waiting_candidate = {}
                if str(waiting_candidate.get("correlation_id") or "") == str(
                        correlation_id or ""):
                    step = candidate
                    break
            if step is None:
                for candidate in steps:
                    prior = candidate.get("external_response")
                    if not isinstance(prior, dict):
                        prior = {}
                    if str(prior.get("correlation_id") or "") == str(
                            correlation_id or ""):
                        step = candidate
                        break
            if step is None:
                if assignment_status in TERMINAL_ASSIGNMENT_STATES:
                    raise _ExternalReplyStop({
                        "status": "terminal",
                        "assignment_status": assignment_status,
                        "message": (
                            f"The assignment is {assignment_status}; the "
                            "response was not used to resume work."),
                    })
                raise _ExternalReplyStop({
                    "status": "unmatched",
                    "message": (
                        "No open gap carries this correlation id. The "
                        "response was not used to resume work."),
                })

            step_id = str(step.get("step_id") or "")
            waiting = step.get("waiting")
            if not isinstance(waiting, dict):
                waiting = {}
            external = step.get("external_response")
            if not isinstance(external, dict):
                external = {}
            fact = str(waiting.get("fact") or external.get("fact") or "")
            subject = str(
                waiting.get("subject") or external.get("subject") or "")
            open_wait = (
                bool(waiting)
                and str(step.get("status") or "") == "waiting"
            )
            # Once accepted, ``waiting`` is cleared so the resume loop cannot
            # treat the step as still blocked. Exact replay must still hash
            # against the ORIGINAL wait scope stored with the receipt.
            digest_waiting = dict(waiting)
            if not digest_waiting and external:
                digest_waiting = {
                    "fact": fact,
                    "subject": subject,
                    "party": str(external.get("party") or ""),
                    "typed_binding": bool(external.get("typed_binding")),
                    "expected_answer_type": str(
                        external.get("expected_answer_type") or ""),
                }
            try:
                digest = _external_reply_material_sha256(
                    correlation_id=correlation_id, waiting=digest_waiting,
                    response=response, source=source, evidence=evidence,
                    value=value)
            except (TypeError, ValueError) as exc:
                raise _ExternalReplyStop({
                    "status": "reply_conflict",
                    "message": (
                        "The authorized reply material could not be bound "
                        "exactly; no wait state was changed."),
                    "reason": "reply_material_unbindable",
                    "step_id": step_id,
                    "material_sha256": "",
                    "detail": _bounded(str(exc), 300),
                })
            explicit = reply_id is not None
            receipts = _external_reply_receipts(step)

            def identity_conflict(
                    reason, message, existing_digest=""):
                return {
                    "status": "reply_conflict",
                    "message": message,
                    "reason": reason,
                    "step_id": step_id,
                    "reply_id": reply_id if reply_id is not None else "",
                    "material_sha256": digest,
                    "expected_material_sha256": existing_digest,
                }

            # An explicit ID names one run/wait scope. Reusing it on another
            # correlation/fact/subject is a scope conflict, not a new reply.
            if explicit:
                for other in [*steps, current]:
                    for receipt in _external_reply_receipts(other):
                        if str(receipt.get("identity_kind") or "") != (
                                "explicit"):
                            continue
                        if str(receipt.get("reply_id") or "") != str(
                                reply_id):
                            continue
                        same_scope = (
                            other is step
                            and _external_reply_scope_matches(
                                receipt,
                                correlation_id=correlation_id,
                                fact=fact, subject=subject)
                        )
                        if not same_scope:
                            raise _ExternalReplyStop(identity_conflict(
                                "reply_scope_conflict",
                                "This reply identity is already bound to a "
                                "different durable wait; it was not used.",
                                str(receipt.get("material_sha256") or "")))

            matches = _external_reply_matching_receipts(
                receipts, reply_id=reply_id, digest=digest,
                correlation_id=correlation_id, fact=fact, subject=subject)
            if matches:
                if any(str(item.get("material_sha256") or "") != digest
                       for item in matches):
                    raise _ExternalReplyStop(identity_conflict(
                        "reply_id_material_conflict",
                        "This reply identity was already used with different "
                        "material; the changed reply was refused before any "
                        "state transition.",
                        str(matches[-1].get("material_sha256") or "")))
                receipt = matches[-1]
                outcome = str(receipt.get("outcome") or "conflict")
                if outcome == "resolved" or external:
                    raise _ExternalReplyStop(
                        _external_reply_replay_result(
                            receipt, step, assignment_status,
                            explicit=explicit))
                if assignment_status in TERMINAL_ASSIGNMENT_STATES:
                    raise _ExternalReplyStop({
                        "status": "terminal",
                        "assignment_status": assignment_status,
                        "message": (
                            f"The assignment is {assignment_status}; the "
                            "response was not used to resume work."),
                    })
                raise _ExternalReplyStop(
                    _external_reply_replay_result(
                        receipt, step, assignment_status,
                        explicit=explicit))

            # An omitted ID is still material-derived. Only the exact digest
            # matched above can certify a replay; changed terminal input is
            # a new event and must be refused, never credited to an older
            # accepted reply. Legacy partial -> corrected replies while the
            # wait is open remain separate, compatible events.
            if assignment_status in TERMINAL_ASSIGNMENT_STATES:
                raise _ExternalReplyStop({
                    "status": "terminal",
                    "assignment_status": assignment_status,
                    "message": (
                        f"The assignment is {assignment_status}; the "
                        "response was not used to resume work."),
                })
            if not open_wait:
                raise _ExternalReplyStop({
                    "status": "terminal",
                    "assignment_status": assignment_status,
                    "message": (
                        "The durable wait is already settled; this new reply "
                        "identity was not used to resume work."),
                })

            typed_binding = bool(waiting.get("typed_binding"))
            expected_type = str(
                waiting.get("expected_answer_type") or "").strip()
            reply_value = value if value not in (None, "") else response

            def conflict_entry(reason, message, **extra):
                entry = {
                    "correlation_id": str(correlation_id or ""),
                    "fact": fact,
                    "subject": subject,
                    "response": _bounded(response, 2000),
                    "source": _bounded(source, 200),
                    "evidence": _bounded(evidence, 500),
                    "at": _utc_now_iso(),
                    "reason": reason,
                    "reply_id": reply_id if reply_id is not None else "",
                    "identity_kind": _external_reply_identity_kind(reply_id),
                    "material_sha256": digest,
                }
                entry.update(extra)
                return entry

            def record_non_resolving(outcome, reason, message, conflict):
                new_plan = copy.deepcopy(current)
                item = step_by_id(new_plan, step_id)
                if item is None:
                    raise _ExternalReplyStop({
                        "status": "unmatched",
                        "message": (
                            "No open gap carries this correlation id. The "
                            "response was not used to resume work."),
                    })
                item_receipts = _external_reply_receipts(item)
                item_receipts.append(_external_reply_receipt(
                    reply_id=reply_id, digest=digest,
                    correlation_id=correlation_id, waiting=waiting,
                    outcome=outcome, reason=reason, message=message,
                    conflict=conflict))
                item["reply_receipts"] = item_receipts
                waiting_now = dict(item.get("waiting") or {})
                conflicts = [
                    dict(entry) for entry in
                    (waiting_now.get("conflicts") or [])
                    if isinstance(entry, dict)
                ]
                conflicts.append(conflict)
                waiting_now["conflicts"] = conflicts[-10:]
                item["waiting"] = waiting_now
                item["updated_at"] = _utc_now_iso()
                new_plan["updated_at"] = _utc_now_iso()
                return new_plan, {
                    "status": outcome,
                    "message": message,
                    "fact": fact,
                    "conflict": conflict,
                    "step_id": step_id,
                    "reply_id": reply_id if reply_id is not None else "",
                    "material_sha256": digest,
                }

            if typed_binding and expected_type in (
                    _EXTERNAL_REPLY_NUMERIC_TYPES):
                try:
                    parsed = Decimal(str(reply_value).strip())
                except (InvalidOperation, ValueError):
                    message = (
                        f"The authorized reply for '{fact}' does not carry "
                        f"the expected {expected_type}.")
                    conflict = conflict_entry(
                        "invalid_answer_type", message,
                        expected=expected_type)
                    return record_non_resolving(
                        "conflict", "invalid_answer_type", message, conflict)
                if not parsed.is_finite() or parsed < 0:
                    message = (
                        f"The authorized reply for '{fact}' must be a finite "
                        f"nonnegative {expected_type}.")
                    conflict = conflict_entry(
                        "invalid_answer_value", message,
                        expected=expected_type)
                    return record_non_resolving(
                        "conflict", "invalid_answer_value", message, conflict)

            expected_party = _normalized_fact_name(waiting.get("party"))
            actual_party = _normalized_fact_name(source)
            if (typed_binding and expected_party and actual_party
                    and expected_party not in actual_party
                    and actual_party not in expected_party):
                message = (
                    f"The reply came from '{source}', not the expected "
                    f"authorized source/channel '{waiting.get('party')}'.")
                conflict = conflict_entry(
                    "wrong_source_channel", message,
                    expected=waiting.get("party"), actual=source)
                return record_non_resolving(
                    "conflict", "wrong_source_channel", message, conflict)

            fact_resolution = (
                _source_fact_resolution(record, fact)
                if fact else {"status": "unknown", "fact": fact})
            fact_status = str(fact_resolution.get("status") or "unknown")
            fact_confirmation: Optional[Dict[str, Any]] = None
            if fact and fact_status in (
                    "established", "mixed", "unavailable", "incomplete"):
                agrees = _response_agrees_fact(
                    response, fact_resolution.get("values") or [],
                    explicit_value=value)
                if fact_status == "established" and agrees:
                    fact_confirmation = {
                        "correlation_id": correlation_id,
                        "fact": fact,
                        "response": _bounded(response, 2000),
                        "source": fact_resolution.get("source") or {},
                        "source_version": fact_resolution.get("source_version"),
                        "values": fact_resolution.get("values") or [],
                        "subjects": fact_resolution.get("subjects") or [],
                        "at": _utc_now_iso(),
                        "reason": "source_fact_confirmed",
                    }
                else:
                    conflict_status = {
                        "mixed": "partial",
                        "unavailable": "unavailable",
                        "incomplete": "incomplete",
                    }.get(fact_status, "conflict")
                    conflict_reason = {
                        "mixed": "source_fact_mixed",
                        "unavailable": "source_fact_unavailable",
                        "incomplete": "source_fact_incomplete",
                    }.get(fact_status, "source_fact_conflict")
                    if conflict_status == "conflict":
                        message = (
                            f"The source already establishes '{fact}' and the "
                            "reply conflicts with it.")
                    elif conflict_status == "partial":
                        message = (
                            f"The source has a partial '{fact}' value; some "
                            "records still need a record-specific answer.")
                    elif conflict_status == "unavailable":
                        message = (
                            f"The source evidence for '{fact}' is unavailable; "
                            "the reply was recorded but did not complete the "
                            "wait.")
                    else:
                        message = (
                            f"The accepted selection for '{fact}' has "
                            "incomplete coverage; the reply was recorded but "
                            "did not complete the wait.")
                    conflict = conflict_entry(
                        conflict_reason, message,
                        column=fact_resolution.get("column"),
                        established_values=(
                            fact_resolution.get("values") or []),
                        subjects=fact_resolution.get("subjects") or [],
                        blank_subjects=(
                            fact_resolution.get("blank_subjects") or []),
                        source_ref=fact_resolution.get("source") or {},
                        source_version=(
                            fact_resolution.get("source_version")),
                        detail=fact_resolution.get("detail"),
                        resolution_reason=fact_resolution.get("reason"))
                    return record_non_resolving(
                        conflict_status, conflict_reason, message, conflict)

            # The existing typed/source/fact readiness has verified this
            # reply. Accept it exactly once under the same CAS write.
            new_plan = copy.deepcopy(current)
            item = step_by_id(new_plan, step_id)
            if item is None:
                raise _ExternalReplyStop({
                    "status": "unmatched",
                    "message": (
                        "No open gap carries this correlation id. The "
                        "response was not used to resume work."),
                })
            operation_id = _operation_id_for_step(record, item)
            waiting_before = dict(item.get("waiting") or {})
            budget = dict(new_plan.get("budget") or {})
            active = dict(budget.get("active_wait") or {})
            current_operation = (
                _operation_by_id(record, operation_id)
                if operation_id else {}) or {}
            wait_id = active.get("id") or self._wait_credit_id(
                item, waiting_before, operation_id)
            wait_started = (
                active.get("started_at")
                or waiting_before.get("since")
                or current_operation.get("claimed_at"))
            accepted_at = _utc_now_iso()
            item["status"] = "pending"
            item["attempts"] = int(item.get("attempts") or 0) + 1
            item["operation_id"] = None
            item["waiting"] = None
            item["external_response"] = {
                "correlation_id": correlation_id,
                "fact": fact,
                "subject": subject,
                "party": str(waiting.get("party") or ""),
                "typed_binding": bool(waiting.get("typed_binding")),
                "expected_answer_type": str(
                    waiting.get("expected_answer_type") or ""),
                "response": _bounded(response, 2000),
                "source": _bounded(source, 200),
                "evidence": _bounded(evidence, 500),
                "fact_resolution": fact_resolution,
                "reply_id": reply_id if reply_id is not None else "",
                "identity_kind": _external_reply_identity_kind(reply_id),
                "material_sha256": digest,
                "at": accepted_at,
            }
            if fact_confirmation:
                item["external_response"]["fact_confirmation"] = (
                    fact_confirmation)
            item_receipts = _external_reply_receipts(item)
            item_receipts.append(_external_reply_receipt(
                reply_id=reply_id, digest=digest,
                correlation_id=correlation_id, waiting=waiting,
                outcome="resolved", reason="source_fact_confirmed",
                message="The authorized reply completed the durable wait."))
            item["reply_receipts"] = item_receipts
            # Credit the actual wait interval once, keyed by the durable wait
            # identity. This path clears ``waiting`` before the executor's
            # resume loop runs, so it must record the interval here; it never
            # extends to a later retry.
            self._credit_wait_once(
                budget, wait_id=wait_id or "",
                started_at=wait_started, ended_at=accepted_at)
            new_plan["budget"] = budget
            item["updated_at"] = accepted_at
            new_plan["status"] = "planned"
            new_plan["updated_at"] = accepted_at
            return new_plan, {
                "status": "resumed",
                "step_id": step_id,
                "operation_id": operation_id,
                "event": str(waiting.get("event") or "email"),
                "reply_id": reply_id if reply_id is not None else "",
                "material_sha256": digest,
            }

        try:
            result = self.lifecycle.mutate_assignment_and_task(
                run_id, compute,
                rationale=f"external response matched {correlation_id}")
        except _ExternalReplyStop as stop:
            result = stop.result
            if result.get("status") == "terminal":
                # A late reply must not match or wake terminal work, even when
                # a cancelled step still carries its historical wait record.
                try:
                    self.lifecycle.runs.append_decision(run_id, {
                        "kind": "external_response_refused",
                        "rationale": (
                            f"assignment {result.get('assignment_status')}: "
                            f"response for {correlation_id} not used"),
                        "correlation_id": str(correlation_id or ""),
                        "reply_id": reply_id if reply_id is not None else "",
                    })
                except Exception:  # noqa: BLE001 — refusal must still return
                    pass
            return result

        mapping_lesson = result.pop("_mapping_lesson", None)
        if mapping_lesson:
            self._persist_gap_mapping_lesson(
                mapping_lesson.get("lesson_id") or "",
                mapping_lesson.get("agent_id") or "",
                mapping_lesson.get("confirmed_mapping") or {})
        if str(result.get("status") or "") == "resolved":
            # A question settlement already reopened the step in the same CAS;
            # wake once, exactly like the direct human-answer path.
            self._wake_run(run_id, {
                "event": str(result.get("event") or "human_input"),
                "correlation_id": correlation_id,
                "question_id": result.get("question_id"),
                "source": "assignment_gap_resolution",
            })
            return result

        if str(result.get("status") or "") != "resumed":
            return result

        operation_id = str(result.get("operation_id") or "")
        if operation_id:
            try:
                fresh = self.lifecycle.get_task(run_id) or {}
                operation = _operation_by_id(fresh, operation_id) or {}
                if operation.get("status") == "waiting":
                    self.lifecycle.transition_operation(
                        run_id, operation_id, "superseded")
            except TaskLifecycleError:
                pass
        self._wake_run(run_id, {
            "event": str(result.get("event") or "email"),
            "correlation_id": correlation_id,
            "source": "assignment_external_response",
        })
        return result

    def retry_step(
        self, run_id: str, step_id: str, *, reason: str = "",
    ) -> Dict[str, Any]:
        """Explicitly retry a failed step as a NEW operation attempt."""
        def compute(record, assignment):
            step = step_by_id(assignment, step_id)
            if step is None:
                raise AssignmentError(f"unknown step {step_id!r}")
            failure = step.get("failure") or {}
            # A pre-dispatch budget refusal is not an execution attempt. It
            # must not consume the retry budget or permanently wedge a step
            # that never reached the adapter.
            budget_blocked = (
                failure.get("reason") == "assignment_budget_exhausted")
            if (not budget_blocked
                    and int(step.get("attempts") or 0) >= int(
                        step.get("max_attempts") or 3)):
                raise AssignmentError(
                    f"step {step_id} exhausted its attempt budget")
            # Migration/recovery: assignments created before wait time was
            # excluded could fail a completed durable wait with
            # ``assignment_budget_exhausted``. Credit only the actual interval
            # recorded by the wait operation and the external response; never
            # infer it from unrelated steps or extend it to this retry.
            if (budget_blocked
                    and step.get("external_response")):
                budget = dict(assignment.get("budget") or {})
                operation_id = (
                    step.get("wait_operation_id")
                    or _operation_id_for_step(record, step))
                operation = (
                    _operation_by_id(record, operation_id)
                    if operation_id else {}) or {}
                active = dict(budget.get("active_wait") or {})
                waiting_before = dict(step.get("waiting") or {})
                wait_id = active.get("id") or self._wait_credit_id(
                    step, waiting_before, operation_id)
                wait_started = (
                    active.get("started_at")
                    or waiting_before.get("since")
                    or operation.get("claimed_at"))
                response = step.get("external_response") or {}
                wait_ended = response.get("at")
                self._credit_wait_once(
                    budget, wait_id=wait_id or "",
                    started_at=wait_started, ended_at=wait_ended,
                    legacy=True)
                if operation_id and not step.get("wait_operation_id"):
                    step["wait_operation_id"] = operation_id
                assignment["budget"] = budget
            step["status"] = "pending"
            if budget_blocked:
                # A pre-dispatch refusal did not execute; keep the real
                # attempt count and let the gate admit the repair retry.
                step["pre_dispatch_budget_refusal"] = True
            else:
                step["attempts"] = int(step.get("attempts") or 0) + 1
                step["pre_dispatch_budget_refusal"] = False
            step["operation_id"] = None
            step["failure"] = None
            step["waiting"] = None
            step["updated_at"] = _utc_now_iso()
            step["last_retry_reason"] = _bounded(reason, 300)
            assignment["status"] = "planned"
            return assignment, {"attempts": step["attempts"]}

        return self.lifecycle.mutate_assignment(
            run_id, compute, rationale=f"retry {step_id}: {reason}")

    def reconcile_step(
        self,
        run_id: str,
        step_id: str,
        verdict: str,
        *,
        evidence: str,
        evidence_ref: Optional[str] = None,
        provider_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        step = step_by_id(record.get("assignment") or {}, step_id)
        if step is None:
            raise AssignmentError(f"unknown step {step_id!r}")
        operation_id = _operation_id_for_step(record, step)
        if not operation_id:
            raise AssignmentError("step has no operation to reconcile")
        result = self.lifecycle.reconcile_uncertain_operation(
            run_id, operation_id, verdict,
            evidence=evidence, evidence_ref=evidence_ref)
        if verdict == "applied":
            execution = _json_safe(result.get("execution") or {
                "summary": "reconciled applied",
                "evidence": [evidence],
            })
            if provider_ref:
                execution = {
                    **execution,
                    "summary": execution.get("summary")
                    or "reconciled applied",
                    "provider_state": "accepted",
                    "provider_ref": str(provider_ref),
                    "remote_id": str(provider_ref),
                    "verification": {
                        "status": "verified",
                        "provider_ref": str(provider_ref),
                    },
                }
            assignment = self._mark_step(
                (self.lifecycle.get_assignment(run_id) or {}),
                step_id,
                {
                    "status": "applied",
                    "result": execution,
                    "failure": None,
                })
            assignment = self._apply_deliverables(
                assignment, step, execution)
            self._persist_assignment(
                run_id, assignment, f"step {step_id} reconciled applied")
        elif verdict == "not_applied":
            # No effect landed. Clear the operation binding so the next
            # resume creates a NEW operation (the original failed record is
            # preserved); never rewind or overwrite the evidence.
            assignment = self.lifecycle.get_assignment(run_id) or {}
            assignment = self._mark_step(assignment, step_id, {
                "status": "pending",
                "operation_id": None,
                "attempts": int(step.get("attempts") or 0) + 1,
                "failure": {
                    "reason": "reconciled_not_applied",
                    "message": _bounded(evidence, 500),
                },
            })
            self._persist_assignment(
                run_id, assignment, f"step {step_id} reconciled not applied")
        return {
            "status": "reconciled",
            "verdict": verdict,
            "operation": result,
            "assignment": self.lifecycle.get_assignment(run_id) or {},
        }

    # ------------------------------------------------------------- cancel

    def cancel(
        self, run_id: str, *, reason: str, cancelled_by: str = "",
    ) -> Dict[str, Any]:
        """Cancel unstarted work; a running external effect is not undone."""
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        if str((record.get("assignment") or {}).get("status") or "") == (
                "cancelled"):
            # Repeated cancellation is a status read, not a second transition:
            # keep the first cancellation evidence and dispatch nothing.
            return self.status(run_id)
        self.lifecycle.apply_transition(run_id, {
            "kind": "cancel",
            "requested_change": _bounded(
                f"{reason} [by {cancelled_by}]" if cancelled_by else reason,
                500),
        })

        def compute(record, assignment):
            new_plan = copy.deepcopy(assignment)
            for step in new_plan.get("steps") or []:
                if step.get("status") in ("applied", "failed", "cancelled",
                                          "superseded"):
                    continue
                step["status"] = "cancelled"
                step["updated_at"] = _utc_now_iso()
            new_plan["status"] = "cancelled"
            new_plan["completed_at"] = _utc_now_iso()
            new_plan["last_transition"] = {
                "kind": "cancel",
                "reason": _bounded(reason, 500),
                "at": _utc_now_iso(),
            }
            return new_plan, {"status": "cancelled"}

        result = self.lifecycle.mutate_assignment(
            run_id, compute, rationale=f"assignment cancelled: {reason}")
        # Project the terminal state on the shared GoalRun row immediately.
        # The assignment/task ledger stays authoritative for history; this
        # clears the run's live waiting projection so public status cannot
        # claim a cancelled assignment is still waiting for input.
        self._set_run_status(run_id, "cancelled")
        return result

    # ------------------------------------------------------------ internals

    def _operation_receipt(
        self,
        operation: Dict[str, Any],
        step: Dict[str, Any],
        result: Dict[str, Any],
        *,
        observed_status: str,
        error_class: Optional[str] = None,
        reconciliation_required: bool = False,
    ) -> Dict[str, Any]:
        artifact = result.get("artifact") if isinstance(
            result.get("artifact"), dict) else {}
        remote_id = str(
            result.get("remote_id") or result.get("provider_ref") or "")
        provider_ref = str(
            result.get("provider_ref") or remote_id)
        provider_receipt = result.get("provider_receipt")
        verification = result.get("verification")
        conflicts = result.get("conflicts")
        remote_identity = {
            "provider": result.get("provider"),
            "operation": result.get("operation"),
            "remote_id": remote_id,
            "provider_ref": provider_ref,
            "payload_sha256": result.get("payload_sha256"),
            "provider_receipt": _json_safe(provider_receipt),
            "verification": _json_safe(verification),
            "conflicts": _json_safe(conflicts or []),
        }
        if not any(value not in (None, "", [], {}) for value in
                   remote_identity.values()):
            remote_identity = None
        return {
            "receipt_version": 1,
            "operation_id": operation.get("operation_id"),
            "execution_id": operation.get("execution_id"),
            "action": step.get("adapter"),
            "binding_sha256": operation.get("binding_sha256"),
            "observed_status": observed_status,
            "error_class": error_class,
            "reconciliation_required": bool(reconciliation_required),
            "oracle_verified": result.get("oracle_verified"),
            "oracle_evidence": result.get("oracle_evidence"),
            "at": _utc_now_iso(),
            "source": {
                "kind": artifact.get("kind"),
                "path": artifact.get("path"),
                "revision": artifact.get("revision"),
                "sha256": artifact.get("sha256"),
                "source_version": result.get("source_version"),
                "coverage": result.get("coverage"),
            },
            "calculation": {
                "expression": result.get("expression"),
                "value": result.get("value"),
                "unit": result.get("unit"),
                "steps": result.get("steps"),
            } if result.get("expression") or result.get("value") is not None
            else None,
            "outbound": {
                "provider_state": result.get("provider_state"),
                "provider_ref": provider_ref or None,
                "remote_id": remote_id or None,
            } if step.get("effect") == "external" else None,
            "remote_identity": remote_identity,
            "readback": {
                "revision": artifact.get("revision"),
                "sha256": artifact.get("sha256"),
            } if artifact else None,
            "summary": _bounded(result.get("summary") or "", 500),
            "evidence": _json_safe(result.get("evidence") or []),
        }

    def _attach_receipt(
        self,
        run_id: str,
        operation: Dict[str, Any],
        step: Dict[str, Any],
        result: Dict[str, Any],
        *,
        observed_status: str,
        error_class: Optional[str] = None,
        reconciliation_required: bool = False,
    ) -> Dict[str, Any]:
        receipt = self._operation_receipt(
            operation, step, result,
            observed_status=observed_status,
            error_class=error_class,
            reconciliation_required=reconciliation_required)
        try:
            self.lifecycle.attach_operation_field(
                run_id, operation["operation_id"], "receipt", receipt)
        except Exception as exc:  # noqa: BLE001 — execution already settled
            logger.warning(
                "assignment %s: receipt attach failed: %s", run_id, exc)
        return receipt

    def _attach_outcome(
        self,
        record: Dict[str, Any],
        assignment: Dict[str, Any],
        state: str,
    ) -> Dict[str, Any]:
        """Build the shared task outcome from durable step/operation facts.

        This is the one place completion is asserted. It reads applied
        operations, saved artifacts and the observed provider state — not a
        model's "DONE" text.
        """
        try:
            from core.task_lifecycle import open_unresolved_questions
            from core.task_outcome_contract import (
                build_task_outcome, sent_record_confirmed_evidence,
            )
            from core.employee_business_outcomes import (
                business_results_from_assignment,
            )
        except Exception:
            return assignment
        steps = assignment.get("steps") or []
        business_requirements = [
            dict(item) for item in
            assignment.get("business_requirements") or []
            if isinstance(item, dict)
        ]
        business_results = business_results_from_assignment(assignment)
        operations = {
            operation.get("operation_id"): operation
            for operation in record.get("operations") or []
        }
        tool_outcomes = []
        evidence_refs: List[Dict[str, Any]] = []
        delivery: Dict[str, Any] = {}
        calculation: Dict[str, Any] = {}
        actions = []
        for step in steps:
            operation = operations.get(step.get("operation_id")) or {}
            execution = operation.get("execution") or {}
            applied = step.get("status") == "applied"
            tool_outcomes.append({
                "tool": step.get("adapter"),
                "verified": applied,
                "outcome": (execution.get("summary")
                            or (step.get("failure") or {}).get("message") or ""),
                "required": bool(step.get("required", True)),
                "evidence_refs": list(step.get("evidence_refs") or []),
            })
            actions.append({
                "action_type": step.get("operation_type"),
                "status": step.get("status"),
                "required": bool(step.get("required", True)),
                "authorized": step.get("effect") != "external"
                or bool((step.get("approval") or {}).get("required")),
                "applied": applied,
                "evidence_refs": list(step.get("evidence_refs") or []),
            })
            for ref in step.get("evidence_refs") or []:
                if isinstance(ref, dict):
                    evidence_refs.append(ref)
            artifact = (step.get("result") or {}).get("artifact")
            if isinstance(artifact, dict) and applied:
                delivery["artifact_verified"] = bool(
                    artifact.get("sha256") and artifact.get("revision"))
                delivery["artifact_revision"] = artifact.get("revision")
                delivery["artifact_sha256"] = artifact.get("sha256")
            if step.get("adapter") == "email.draft" and applied:
                delivery["draft_saved"] = True
                delivery["draft_revision"] = (
                    step.get("result") or {}).get("artifact", {}).get(
                        "revision")
            if step.get("effect") == "external" and applied:
                result = step.get("result") or {}
                receipt = result.get("receipt") if isinstance(
                    result.get("receipt"), dict) else {}
                outbound = receipt.get("outbound") if isinstance(
                    receipt.get("outbound"), dict) else {}
                remote = result.get("remote_identity") if isinstance(
                    result.get("remote_identity"), dict) else {}
                provider_state = str(
                    result.get("provider_state")
                    or outbound.get("provider_state") or "")
                if provider_state:
                    accepted = provider_state.lower() in (
                        "sent", "accepted", "applied", "provider_accepted")
                    delivery["provider_accepted"] = accepted
                    delivery["provider_ref"] = (
                        result.get("provider_ref")
                        or outbound.get("provider_ref")
                        or outbound.get("remote_id")
                        or remote.get("provider_ref"))
                # Stronger observations stand on their own evidence. Neither
                # is inferred from provider acceptance; unobserved delivery
                # stays unknown instead of being asserted false.
                sent_record = sent_record_confirmed_evidence(step, result)
                if sent_record is not None:
                    delivery["sent_record_confirmed"] = sent_record
            if (step.get("result") or {}).get("value") is not None:
                calculation = {
                    "computed": (step.get("result") or {}).get("value"),
                    "unit": (step.get("result") or {}).get("unit"),
                    "verified": applied,
                }
        gaps = []
        for question in open_unresolved_questions(record):
            gaps.append({
                "criterion_id": question.get("step_id") or "",
                "status": (question.get("waiting") or {}).get(
                    "state") or "open",
                "reasons": [question.get("reason")
                            or question.get("question")],
                "next_evidence_needed": question.get("next_retrieval")
                or question.get("next_action"),
            })
        for step in steps:
            if step.get("status") in ("failed", "uncertain"):
                gaps.append({
                    "criterion_id": step.get("step_id"),
                    "status": step.get("status"),
                    "reasons": [
                        (step.get("failure") or {}).get("message")
                        or (step.get("failure") or {}).get("reason")],
                    "next_evidence_needed": "retry or resolve the named gap",
                })
        objective_met = None
        if assignment.get("completion_criteria"):
            from core.task_outcome_contract import build_assignment_outcome
            objective_met = build_assignment_outcome(
                assignment, record, state=state).get("verdict")
        else:
            objective_met = state == "completed"
        outcome = build_task_outcome(
            objective=assignment.get("objective") or "",
            completion_criteria=assignment.get("completion_criteria") or [],
            authorized_actions=assignment.get("authorized_actions") or [],
            tool_outcomes=tool_outcomes,
            evidence_refs=evidence_refs,
            delivery=delivery,
            gaps=gaps,
            actions=actions,
            calculation=calculation,
            business_requirements=business_requirements,
            business_results=business_results,
            objective_met=objective_met,
            scope={
                "workspace_id": assignment.get("workspace_id"),
                "teaching_revision": (
                    assignment.get("teaching_snapshot") or {}).get(
                        "revision"),
                "plan_revision": assignment.get("plan_revision"),
            },
            policy_version=(
                assignment.get("teaching_snapshot") or {}).get("fingerprint"),
        )
        updated = copy.deepcopy(assignment)
        updated["outcome_summary"] = {
            "objective_met": outcome.get("objective_met"),
            "success_kinds": outcome.get("success_kinds"),
            "failure": outcome.get("failure"),
            "delivery": outcome.get("delivery"),
            "gap_count": len(gaps),
            "evidence_count": len(evidence_refs),
            "built_at": _utc_now_iso(),
        }
        updated["outcome"] = _json_safe(outcome)
        return updated

    def _persist_assignment(
        self, run_id: str, assignment: Dict[str, Any], rationale: str,
    ) -> None:
        """Persist only if the plan actually changed (CAS-safe)."""
        current = self.lifecycle.get_assignment(run_id)
        if current == assignment:
            return
        self.lifecycle.put_assignment(run_id, assignment, rationale=rationale)

    def _set_state(self, assignment: Dict[str, Any], state: str) -> Dict[str, Any]:
        if assignment.get("status") == state:
            return assignment
        updated = copy.deepcopy(assignment)
        updated["status"] = state
        updated["updated_at"] = _utc_now_iso()
        if state == "completed":
            updated["completed_at"] = _utc_now_iso()
        return updated

    def _first_waiting_step(self, assignment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for step in assignment.get("steps") or []:
            if step.get("status") in ("waiting", "awaiting_approval"):
                return step
        return None

    def _waiting_steps(self, assignment: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            step for step in assignment.get("steps") or []
            if step.get("status") in ("waiting", "awaiting_approval")
        ]

    @staticmethod
    def _final_deliverable_step_ids(
        assignment: Dict[str, Any],
    ) -> List[str]:
        """Steps that produce the job's requested final outputs.

        A final deliverable is not independent work: while a material
        information obligation is open, its producing step must stay blocked
        even when its own dependencies are satisfied. The plan's declared
        deliverables are the authority; no adapter-name heuristic is needed.
        """
        return sorted({
            str(item.get("step_id"))
            for item in assignment.get("deliverables") or []
            if isinstance(item, dict) and item.get("step_id")
        })

    # ------------------------------------------------------ idle clock
    # Assignment time is charged only while at least one branch can make
    # progress. Waiting branches are not charged individually: the interval
    # is credited once, at the assignment level, so two overlapping waits do
    # not add up (and can never exceed wall time).

    def _ensure_idle_ledger(
        self, assignment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Upgrade a legacy per-wait budget to the idle-interval ledger.

        The old ``paused_seconds`` value remains the starting total. An open
        legacy wait is carried into an open idle interval so a restart does
        not lose or double-count it.
        """
        budget = dict(assignment.get("budget") or {})
        if budget.get("idle_ledger_schema") == IDLE_LEDGER_SCHEMA:
            return assignment
        budget["idle_ledger_schema"] = IDLE_LEDGER_SCHEMA
        budget["idle_intervals"] = dict(budget.get("idle_intervals") or {})
        budget["paused_seconds"] = float(budget.get("paused_seconds") or 0.0)
        legacy_wait = budget.get("waiting_since")
        if legacy_wait and not budget.get("idle_open"):
            credits = budget.get("wait_credits") or {}
            already_credited = any(
                isinstance(item, dict)
                and str(item.get("started_at") or "") == str(legacy_wait)
                for item in credits.values())
            # Legacy rows can still carry the open-wait timestamp after the
            # interval was added to paused_seconds. Do not invent a second
            # credit for it.
            ambiguous_legacy = (
                float(budget.get("paused_seconds") or 0.0) > 0
                and not budget.get("active_wait"))
            if not already_credited and not ambiguous_legacy:
                budget["idle_open"] = {
                    "id": f"migrated:{legacy_wait}",
                    "started_at": str(legacy_wait),
                    "reason": "migrated open wait",
                }
        budget["waiting_since"] = None
        budget["active_wait"] = None
        updated = copy.deepcopy(assignment)
        updated["budget"] = budget
        return updated

    def _checkpoint_idle(
        self, assignment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Materialize elapsed open-idle time into ``paused_seconds``.

        Keeping the live interval start at the checkpoint keeps persisted
        ``paused_seconds`` meaningful to ordinary readers while
        ``_effective_wall_elapsed`` still accounts for the short tail since
        the last checkpoint.
        """
        budget = dict(assignment.get("budget") or {})
        if budget.get("idle_ledger_schema") != IDLE_LEDGER_SCHEMA:
            return assignment
        opened = dict(budget.get("idle_open") or {})
        if not opened:
            return assignment
        started = self._parse_clock(opened.get("started_at"))
        now = float(self.clock())
        if started is None or now <= started:
            return assignment
        opened.setdefault("first_started_at", opened.get("started_at"))
        budget["paused_seconds"] = (
            float(budget.get("paused_seconds") or 0.0) + (now - started))
        opened["started_at"] = self._clock_iso(now)
        opened["checkpointed_at"] = _utc_now_iso()
        budget["idle_open"] = opened
        updated = copy.deepcopy(assignment)
        updated["budget"] = budget
        return updated

    def _open_idle(
        self, assignment: Dict[str, Any], *, reason: str,
    ) -> Dict[str, Any]:
        budget = dict(assignment.get("budget") or {})
        if budget.get("idle_ledger_schema") != IDLE_LEDGER_SCHEMA:
            assignment = self._ensure_idle_ledger(assignment)
            budget = dict(assignment.get("budget") or {})
        if budget.get("idle_open"):
            return assignment
        now = float(self.clock())
        budget["idle_open"] = {
            "id": f"{assignment.get('assignment_id')}:idle:{now}",
            "started_at": self._clock_iso(now),
            "reason": _bounded(reason, 300),
        }
        updated = copy.deepcopy(assignment)
        updated["budget"] = budget
        return updated

    def _close_idle(
        self, assignment: Dict[str, Any], *, reason: str,
    ) -> Dict[str, Any]:
        budget = dict(assignment.get("budget") or {})
        if budget.get("idle_ledger_schema") != IDLE_LEDGER_SCHEMA:
            return assignment
        opened = dict(budget.get("idle_open") or {})
        if not opened:
            return assignment
        now = float(self.clock())
        started = self._parse_clock(opened.get("started_at"))
        if started is not None and now > started:
            budget["paused_seconds"] = (
                float(budget.get("paused_seconds") or 0.0) + (now - started))
        first_started = opened.get("first_started_at") or opened.get("started_at")
        intervals = dict(budget.get("idle_intervals") or {})
        interval_id = str(opened.get("id") or "open")
        intervals[interval_id] = {
            "started_at": first_started,
            "ended_at": self._clock_iso(now),
            "reason": opened.get("reason"),
            "closed_by": _bounded(reason, 300),
        }
        # Bound the audit ledger while keeping the latest intervals.
        if len(intervals) > 200:
            intervals = dict(list(intervals.items())[-200:])
        budget["idle_intervals"] = intervals
        budget["idle_open"] = None
        updated = copy.deepcopy(assignment)
        updated["budget"] = budget
        return updated

    @staticmethod
    def _parse_clock(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return datetime.fromisoformat(str(value)).timestamp()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clock_iso(ts: float) -> str:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()

    def _sync_assignment(
        self, record: Dict[str, Any], assignment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Reconcile plan state with durable operation state after a crash."""
        updated = copy.deepcopy(assignment)
        changed = False
        for step in updated.get("steps") or []:
            operation_id = _operation_id_for_step(record, step)
            if not operation_id:
                if step.get("status") in ("running", "waiting",
                                          "awaiting_approval"):
                    step["status"] = "pending"
                    step["waiting"] = None
                    changed = True
                continue
            operation = _operation_by_id(record, operation_id) or {}
            status = operation.get("status")
            step["operation_id"] = operation_id
            mapping = {
                "applied": "applied",
                "failed": "failed",
                "cancelled": "cancelled",
                "superseded": "superseded",
                "uncertain": "uncertain",
                "waiting": "waiting",
                "awaiting_approval": "awaiting_approval",
                "approved": "awaiting_approval",
            }
            target = mapping.get(status)
            if target and step.get("status") != target:
                # A current source gap is a live wait, not an older applied
                # receipt. Keep the immutable operation result for audit but
                # do not let _sync_assignment overwrite the waiting state on
                # the next execute loop (that caused a busy loop and stale
                # completion). A normal applied step still maps to applied.
                current_source_gap = (
                    step.get("status") == "waiting"
                    and bool(step.get("gap_ids"))
                    and target == "applied")
                if current_source_gap:
                    pass
                elif not (step.get("status") == "applied"
                          and target != "applied"):
                    step["status"] = target
                    changed = True
            if status == "applied":
                execution = operation.get("execution") or {}
                if execution and not step.get("result"):
                    step["result"] = _json_safe(execution)
                    changed = True
                if execution.get("artifact_revision"):
                    step["artifact_revision"] = execution["artifact_revision"]
        return updated if changed else assignment

    def _mark_step(
        self, assignment: Dict[str, Any], step_id: str, values: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = copy.deepcopy(assignment)
        for step in updated.get("steps") or []:
            if step.get("step_id") == step_id:
                step.update(values)
                step["updated_at"] = _utc_now_iso()
                break
        updated["updated_at"] = _utc_now_iso()
        return updated

    def _block_step(
        self, assignment: Dict[str, Any], step_id: str, *,
        reason: str, message: str,
    ) -> Dict[str, Any]:
        return self._mark_step(assignment, step_id, {
            "status": "failed",
            "failure": {"reason": reason, "message": _bounded(message, 500)},
            "updated_at": _utc_now_iso(),
        })

    @staticmethod
    def _wait_credit_id(
        step: Dict[str, Any], waiting: Dict[str, Any],
        operation_id: Optional[str] = None,
    ) -> str:
        """Stable identity for one actual wait interval.

        The operation id is the durable execution identity. Legacy rows without
        one fall back to the step plus the persisted wait start, never to a
        later retry timestamp.
        """
        return str(
            operation_id
            or step.get("operation_id")
            or step.get("wait_operation_id")
            or waiting.get("wait_id")
            or f"{step.get('step_id')}:"
               f"{waiting.get('correlation_id') or waiting.get('since') or ''}")

    @staticmethod
    def _clear_active_wait(budget: Dict[str, Any], wait_id: str) -> None:
        """Clear the live wait projection only for the interval just closed."""
        active = dict(budget.get("active_wait") or {})
        if not active or str(active.get("id")) == str(wait_id):
            budget["active_wait"] = None
            budget.pop("waiting_since", None)

    def _credit_wait_once(
        self, budget: Dict[str, Any], *,
        wait_id: str,
        started_at: Any,
        ended_at: Any,
        legacy: bool = False,
    ) -> bool:
        """Credit one persisted wait interval exactly once under the CAS.

        New assignments carry ``wait_credits_schema=1`` and credit every real
        interval. Legacy assignments have no interval ledger; if they already
        carry ``paused_seconds`` we record the interval as already credited
        instead of adding it again. No interval is ever extended to "now".
        """
        if not wait_id or not started_at or not ended_at:
            return False
        credits = dict(budget.get("wait_credits") or {})
        if wait_id in credits:
            self._clear_active_wait(budget, wait_id)
            return False
        try:
            start_ts = datetime.fromisoformat(str(started_at)).timestamp()
            end_ts = datetime.fromisoformat(str(ended_at)).timestamp()
        except (TypeError, ValueError):
            return False
        if end_ts < start_ts:
            return False
        if (legacy
                and budget.get("wait_credits_schema") != 1
                and float(budget.get("paused_seconds") or 0.0) > 0):
            credits[wait_id] = {
                "seconds": 0.0,
                "started_at": str(started_at),
                "ended_at": str(ended_at),
                "already_credited": True,
            }
            budget["wait_credits"] = credits
            # The old ledger already counted this interval in paused_seconds.
            # Leaving the same interval as an open wait would subtract it a
            # second time in _effective_wall_elapsed, making genuinely
            # exhausted active work look unexhausted. Clear only this wait.
            self._clear_active_wait(budget, wait_id)
            return False
        seconds = end_ts - start_ts
        idle_authoritative = (
            budget.get("idle_ledger_schema") == IDLE_LEDGER_SCHEMA)
        credits[wait_id] = {
            "seconds": 0.0 if idle_authoritative else seconds,
            "started_at": str(started_at),
            "ended_at": str(ended_at),
            "idle_ledger_authoritative": idle_authoritative,
        }
        budget["wait_credits"] = credits
        budget["wait_credits_schema"] = 1
        if not idle_authoritative:
            budget["paused_seconds"] = (
                float(budget.get("paused_seconds") or 0.0) + seconds)
        self._clear_active_wait(budget, wait_id)
        return True

    def _effective_wall_elapsed(self, budget: Dict[str, Any]) -> float:
        """Wall time spent working, excluding durable external waits.

        A wait is persisted work, not CPU/transport time. Counting it against
        ``max_wall_seconds`` made a 15-minute assignment budget expire during a
        legitimate two-hour external wait. ``paused_seconds`` is accumulated
        when the wait resolves; ``waiting_since`` covers the currently open
        wait (including across a restart).
        """
        started = budget.get("started_at")
        if not started:
            return 0.0
        try:
            started_at = datetime.fromisoformat(str(started)).timestamp()
        except (TypeError, ValueError):
            return 0.0
        if budget.get("idle_ledger_schema") == IDLE_LEDGER_SCHEMA:
            paused = float(budget.get("paused_seconds") or 0.0)
            opened = budget.get("idle_open") or {}
            started_idle = self._parse_clock(opened.get("started_at"))
            if started_idle is not None:
                paused += max(0.0, float(self.clock()) - started_idle)
            return max(0.0, (self.clock() - started_at) - paused)
        paused = float(budget.get("paused_seconds") or 0.0)
        waiting_since = budget.get("waiting_since")
        if waiting_since:
            # A legacy/restarted row can still carry the open-wait timestamp
            # for an interval already counted in paused_seconds. Do not
            # subtract that interval twice; a genuinely exhausted run must
            # stay exhausted.
            credits = budget.get("wait_credits") or {}
            already_credited = any(
                isinstance(item, dict)
                and str(item.get("started_at") or "") == str(waiting_since)
                for item in credits.values())
            if (already_credited
                    or (budget.get("wait_credits_schema") != 1
                        and float(budget.get("paused_seconds") or 0.0) > 0
                        and not budget.get("active_wait"))):
                # Either the interval is in the credit ledger, or this is a
                # legacy ledger whose paused time already includes it and
                # which has no live active-wait identity. A new wait always
                # records active_wait in _enter_wait, so it is not skipped.
                waiting_since = None
        if waiting_since:
            try:
                paused += max(
                    0.0,
                    self.clock() - datetime.fromisoformat(
                        str(waiting_since)).timestamp())
            except (TypeError, ValueError):
                pass
        return max(0.0, (self.clock() - started_at) - paused)

    def _deadline_exceeded(self, assignment: Dict[str, Any]) -> bool:
        deadline = (assignment.get("budget") or {}).get("deadline")
        if not deadline:
            return False
        try:
            return float(self.clock()) >= datetime.fromisoformat(
                str(deadline)).timestamp()
        except (TypeError, ValueError):
            return False

    def _expire_assignment_deadline(
        self, assignment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """A business deadline is absolute: waits/restarts never extend it."""
        updated = copy.deepcopy(assignment)
        for step in updated.get("steps") or []:
            if step.get("status") in (
                    "applied", "skipped", "cancelled", "superseded"):
                continue
            step["status"] = "failed"
            step["failure"] = {
                "reason": "assignment_deadline_exceeded",
                "message": "The absolute business deadline for this "
                           "assignment has passed.",
            }
            step["waiting"] = None
            step["updated_at"] = _utc_now_iso()
        updated["status"] = "blocked"
        updated["completed_at"] = None
        updated["updated_at"] = _utc_now_iso()
        updated["last_transition"] = {
            "kind": "deadline_exceeded",
            "deadline": (updated.get("budget") or {}).get("deadline"),
            "at": _utc_now_iso(),
        }
        return updated

    def _budget_allows(
        self, assignment: Dict[str, Any], step: Dict[str, Any],
    ) -> bool:
        budget = assignment.get("budget") or {}
        if int(budget.get("steps_started") or 0) >= int(
                budget.get("max_steps") or 40):
            return False
        if (not step.get("pre_dispatch_budget_refusal")
                and int(step.get("attempts") or 0) >= int(
                    step.get("max_attempts") or budget.get(
                        "max_attempts_per_step") or 3)):
            return False
        if self._effective_wall_elapsed(budget) > float(
                budget.get("max_wall_seconds") or 3600.0):
            return False
        cost_limit = float(budget.get("max_cost_usd") or 0)
        if (cost_limit > 0
                and str(budget.get("cost_mode") or "hard") == "hard"
                and float(budget.get("cost_usd") or 0)
                + float(budget.get("reserved_cost_usd") or 0)
                >= cost_limit):
            return False
        return True

    def _remaining_wall_seconds(
        self, assignment: Dict[str, Any],
    ) -> Optional[float]:
        """Remaining assignment wall budget, or None when unbounded."""
        budget = assignment.get("budget") or {}
        limit = float(budget.get("max_wall_seconds") or 0)
        if limit <= 0:
            return None
        return max(0.0, limit - self._effective_wall_elapsed(budget))

    def _step_cost_bound(
        self, step: Dict[str, Any], adapter: Any,
    ) -> Optional[float]:
        """Conservative upper bound the adapter declares for one operation."""
        raw = step.get("max_cost_usd")
        if raw is None:
            raw = (getattr(adapter, "metadata", None) or {}).get(
                "max_cost_usd")
        if raw is None:
            return None
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return None

    def _cost_bearing(self, adapter: Any) -> bool:
        return bool((getattr(adapter, "metadata", None) or {}).get(
            "cost_bearing"))

    def _reserve_step_cost(
        self,
        run_id: str,
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        operation_id: str,
        bound: Optional[float],
        adapter: Any,
    ) -> Dict[str, Any]:
        """Reserve the declared upper bound before dispatch.

        Hard mode refuses an operation whose reservation would exceed the
        limit (including concurrent reservations) and refuses a cost-bearing
        adapter with no declared bound. Soft mode records an explicitly
        authorized overrun instead of pretending the limit held.
        """
        budget = assignment.get("budget") or {}
        limit = float(budget.get("max_cost_usd") or 0)
        mode = str(budget.get("cost_mode") or "hard").lower()
        cost_bearing = self._cost_bearing(adapter)
        if limit <= 0:
            return {"ok": True, "assignment": assignment, "bound": 0.0}
        if cost_bearing and bound is None and mode != "soft":
            return {
                "ok": False,
                "reason": "unbounded_cost_refused",
                "message": (
                    "This cost-bearing operation declares no upper bound; "
                    "refusing autonomous execution under a hard budget."),
            }
        reserve = float(bound or 0.0)

        def compute(record, current):
            current_budget = dict(current.get("budget") or {})
            committed = float(current_budget.get("cost_usd") or 0)
            reserved = float(current_budget.get("reserved_cost_usd") or 0)
            current_limit = float(current_budget.get("max_cost_usd") or 0)
            current_mode = str(current_budget.get("cost_mode") or "hard")
            existing = [
                item for item in (current_budget.get("cost_reservations")
                                  or [])
                if item.get("operation_id") == operation_id
            ]
            if existing:
                return current, {
                    "ok": True, "assignment": current,
                    "bound": reserve, "already": True,
                }
            if (current_limit > 0
                    and committed + reserved + reserve
                    > current_limit + 1e-9):
                if current_mode == "hard":
                    raise AssignmentError(
                        "assignment_cost_budget_exhausted: "
                        f"committed={committed:.6f} "
                        f"reserved={reserved:.6f} "
                        f"requested={reserve:.6f} "
                        f"limit={current_limit:.6f}")
                current_budget["soft_limit_exceeded"] = True
            reservations = list(
                current_budget.get("cost_reservations") or [])
            reservations.append({
                "operation_id": operation_id,
                "step_id": step.get("step_id"),
                "bound_usd": reserve,
                "reserved_at": _utc_now_iso(),
                "mode": current_mode,
            })
            current_budget["reserved_cost_usd"] = round(reserved + reserve, 6)
            current_budget["cost_reservations"] = reservations[-80:]
            current["budget"] = current_budget
            return current, {
                "ok": True, "assignment": current,
                "bound": reserve, "already": False,
            }

        try:
            return self.lifecycle.mutate_assignment(
                run_id, compute,
                rationale=(
                    f"reserve cost bound for {step.get('step_id')}"))
        except Exception as exc:  # noqa: BLE001 — refuse before dispatch
            return {
                "ok": False,
                "reason": "assignment_cost_budget_exhausted",
                "message": _bounded(str(exc), 500),
            }

    def _settle_step_cost(
        self,
        assignment: Dict[str, Any],
        run_id: str,
        step: Dict[str, Any],
        operation_id: str,
        bound: float,
        outcome: str,
        actual: float = 0.0,
    ) -> Dict[str, Any]:
        """Release the reservation and commit actual (or conservative) cost.

        ``applied`` commits the actual cost; ``uncertain`` commits the full
        reserved bound because the provider may have charged it; a proven
        no-effect failure releases the reservation. An actual overrun in hard
        mode is recorded as a budget violation, never hidden.
        """
        reserve = float(bound or 0.0)

        def compute(record, current):
            current_budget = dict(current.get("budget") or {})
            reservations = [
                item for item in (current_budget.get("cost_reservations")
                                  or [])
                if item.get("operation_id") != operation_id
            ]
            held = float(current_budget.get("reserved_cost_usd") or 0)
            current_budget["reserved_cost_usd"] = round(
                max(0.0, held - reserve), 6)
            current_budget["cost_reservations"] = reservations[-80:]
            if outcome == "applied":
                charge = max(0.0, float(actual or 0))
                if charge <= 0 and reserve > 0:
                    charge = reserve
            elif outcome == "uncertain":
                charge = reserve
            else:
                charge = 0.0
            committed = float(current_budget.get("cost_usd") or 0)
            current_budget["cost_usd"] = round(committed + charge, 6)
            if (str(current_budget.get("cost_mode") or "hard") == "hard"
                    and charge > reserve + 1e-9):
                current_budget["cost_overrun_usd"] = round(
                    float(current_budget.get("cost_overrun_usd") or 0)
                    + (charge - reserve), 6)
                current_budget["cost_violation"] = (
                    "actual cost exceeded the reserved bound")
            current["budget"] = current_budget
            return current, {"charged": charge, "assignment": current}

        try:
            result = self.lifecycle.mutate_assignment(
                run_id, compute,
                rationale=(
                    f"settle cost for {step.get('step_id')} ({outcome})"))
            settled = result.get("assignment") or {}
            # Preserve the caller's plan state (another branch may have moved
            # while the cost ledger was read). Only the budget is reconciled
            # from the CAS write.
            updated = copy.deepcopy(assignment)
            if settled.get("budget") is not None:
                updated["budget"] = copy.deepcopy(settled["budget"])
            return updated
        except Exception as exc:  # noqa: BLE001 — accounting is observable
            logger.error(
                "assignment %s: cost settlement failed for %s: %s",
                run_id, step.get("step_id"), exc)
            return assignment

    def _bump_steps_started(
        self, assignment: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = copy.deepcopy(assignment)
        budget = dict(updated.get("budget") or {})
        budget["steps_started"] = int(budget.get("steps_started") or 0) + 1
        updated["budget"] = budget
        updated["updated_at"] = _utc_now_iso()
        return updated

    def _operation_key(self, assignment: Dict[str, Any], step: Dict[str, Any]) -> str:
        attempt = int(step.get("attempts") or 0) + 1
        return (
            f"assignment:{assignment.get('assignment_id')}:"
            f"{step.get('step_id')}:r{assignment.get('plan_revision')}:"
            f"a{attempt}"
        )

    def _ensure_operation(
        self,
        run_id: str,
        record: Dict[str, Any],
        assignment: Dict[str, Any],
        step: Dict[str, Any],
    ) -> Dict[str, Any]:
        operation_id = _operation_id_for_step(record, step)
        if operation_id:
            operation = _operation_by_id(record, operation_id)
            if operation:
                return operation
        key = self._operation_key(assignment, step)
        existing = self.lifecycle.find_operation_by_key(run_id, key)
        if existing:
            return existing
        resolved_inputs = self._resolve_inputs(assignment, step)
        artifact_refs = []
        prerequisite_operations = []
        evidence_revisions = []
        for dependency in step.get("depends_on") or []:
            dep_step = step_by_id(assignment, dependency) or {}
            if dep_step.get("operation_id"):
                prerequisite_operations.append(dep_step["operation_id"])
            result = dep_step.get("result") or {}
            artifact = result.get("artifact")
            if isinstance(artifact, dict):
                artifact_refs.append({
                    "artifact_id": artifact.get("path")
                    or artifact.get("revision"),
                    "revision": artifact.get("revision"),
                    "sha256": artifact.get("sha256"),
                })
            if result.get("source_version"):
                evidence_revisions.append(result["source_version"])
            for ref in dep_step.get("evidence_refs") or []:
                if isinstance(ref, dict) and ref.get("content_hash"):
                    evidence_revisions.append(ref["content_hash"])
        binding = {
            "action_name": step.get("adapter"),
            "workspace_id": assignment.get("workspace_id"),
            "account_id": assignment.get("employee_id"),
            "task_revision": (record.get("task_revision") or {}).get(
                "revision"),
            "arguments": resolved_inputs,
            "artifact_refs": artifact_refs,
            "authorization_ref": (
                (step.get("approval") or {}).get("purpose")
                or step.get("standing_authorization") or ""),
            "prerequisite_operation_ids": prerequisite_operations,
            "prerequisite_evidence_revisions": evidence_revisions,
        }
        return self.lifecycle.create_operation(
            run_id,
            op_type=step.get("operation_type") or "retrieve",
            requested_change=_bounded(
                step.get("instruction") or step.get("title") or "", 500),
            idempotency_key=key,
            binding=binding,
            extra={
                "assignment_id": assignment.get("assignment_id"),
                "step_id": step.get("step_id"),
                "plan_revision": assignment.get("plan_revision"),
                "adapter": step.get("adapter"),
                "effect": step.get("effect"),
                "teaching_fingerprint": (
                    assignment.get("teaching_snapshot") or {}).get(
                        "fingerprint"),
                "authorization_revision": _authorization_revision(assignment),
            },
        )

    def _resolve_inputs(
        self, assignment: Dict[str, Any], step: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve explicit ``$ref`` values from completed step results.

        A reference is ``{"$ref": "step_id.path.to.value"}`` or the string
        ``${step_id.path.to.value}``. This is data wiring, not a workflow
        language: no expressions, predicates or code execution.
        """
        results = {
            item.get("step_id"): copy.deepcopy(item.get("result"))
            for item in assignment.get("steps") or []
            if item.get("status") in ("applied", "skipped")
        }

        def walk(value: Any) -> Any:
            if isinstance(value, dict) and set(value) == {"$ref"}:
                return lookup(str(value.get("$ref") or ""))
            if isinstance(value, str):
                if value.startswith("${") and value.endswith("}") \
                        and value.count("${") == 1:
                    return lookup(value[2:-1])

                def replace(match: "re.Match[str]") -> str:
                    resolved = lookup(match.group(1))
                    return "" if resolved is None else str(resolved)

                return re.sub(r"\$\{([^}]+)\}", replace, value)
            if isinstance(value, dict):
                return {key: walk(item) for key, item in value.items()}
            if isinstance(value, list):
                return [walk(item) for item in value]
            return value

        def lookup(reference: str) -> Any:
            step_id, _, path = reference.partition(".")
            current = results.get(step_id)
            if current is None:
                return None
            for part in [piece for piece in path.split(".") if piece]:
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list):
                    try:
                        current = current[int(part)]
                    except (ValueError, IndexError):
                        return None
                else:
                    return None
            return copy.deepcopy(current)

        return {
            key: walk(value)
            for key, value in (step.get("inputs") or {}).items()
        }

    def _prepare_effect(
        self,
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        adapter = self.adapters.get(step.get("adapter") or "")
        if adapter is None:
            raise AssignmentError(
                f"adapter '{step.get('adapter')}' is not registered")
        inputs = self._resolve_inputs(assignment, step)
        context = self._context(assignment, step, record)
        context["resolved_inputs"] = copy.deepcopy(inputs)
        if adapter.prepare is not None:
            prepared = adapter.prepare(dict(inputs), context)
            if inspect.isawaitable(prepared):
                # Preparation must be side-effect free; the executor is
                # already inside an async method at every call site.
                raise AssignmentError(
                    "async prepare hooks are not supported; prepare must "
                    "be synchronous and side-effect free")
            prepared = dict(prepared or {})
        else:
            prepared = {
                "payload": {
                    "adapter": step.get("adapter"),
                    "inputs": _json_safe(inputs, depth=0),
                    "dependency_results": [{
                        "step_id": dep,
                        "artifact_revision": (
                            (step_by_id(assignment, dep) or {}).get(
                                "artifact_revision")),
                        "value": _json_safe(
                            ((step_by_id(assignment, dep) or {}).get(
                                "result") or {}).get("value")),
                        "unit": _json_safe(
                            ((step_by_id(assignment, dep) or {}).get(
                                "result") or {}).get("unit")),
                        "summary": _json_safe(
                            ((step_by_id(assignment, dep) or {}).get(
                                "result") or {}).get("summary")),
                    } for dep in (step.get("depends_on") or [])],
                },
                "artifact_revision": step.get("artifact_revision"),
            }
        payload = prepared.get("payload")
        if payload is None:
            raise AssignmentError("a prepared effect requires a payload")
        prepared["payload_sha256"] = _approval_payload_hash(payload)
        prepared.setdefault("artifact_revision", step.get("artifact_revision"))
        prepared.setdefault(
            "requested_by", assignment.get("employee_id") or "")
        return prepared

    def _context(
        self,
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        prior = {
            other["step_id"]: copy.deepcopy(other.get("result"))
            for other in assignment.get("steps") or []
            if other.get("status") in ("applied", "skipped")
        }
        return {
            "run_id": record.get("run_id"),
            "assignment_id": assignment.get("assignment_id"),
            "plan_revision": assignment.get("plan_revision"),
            "workspace_id": assignment.get("workspace_id"),
            "tenant_id": assignment.get("tenant_id"),
            "agent_id": (assignment.get("provenance") or {}).get("agent_id"),
            "employee_id": assignment.get("employee_id"),
            "provenance": copy.deepcopy(
                assignment.get("provenance") or {}),
            "objective": assignment.get("objective"),
            "assignment": copy.deepcopy(assignment),
            "facts": copy.deepcopy(assignment.get("facts") or []),
            "teaching": copy.deepcopy(
                assignment.get("teaching_snapshot") or {}),
            "sources": copy.deepcopy(assignment.get("sources") or []),
            "deliverables": copy.deepcopy(
                assignment.get("deliverables") or []),
            "authorized_actions": list(
                assignment.get("authorized_actions") or []),
            "standing_authority": copy.deepcopy(
                assignment.get("standing_authority") or {}),
            "task_revision": copy.deepcopy(record.get("task_revision") or {}),
            "resolved_gaps": [
                copy.deepcopy(item)
                for item in (record.get("task_revision") or {}).get(
                    "unresolved") or []
                if item.get("status") == "resolved"
            ],
            "step": copy.deepcopy(step),
            "previous_results": prior,
        }

    def _resolve_waiting(self, record: Dict[str, Any], step: Dict[str, Any]) -> bool:
        """True when a waiting step is eligible to run again."""
        operation_id = _operation_id_for_step(record, step)
        operation = _operation_by_id(record, operation_id) if operation_id else None
        if operation is None:
            return True
        status = operation.get("status")
        if status == "approved":
            return True
        if status == "waiting":
            waiting = operation.get("waiting") or step.get("waiting") or {}
            deadline = waiting.get("deadline")
            if deadline:
                try:
                    if self.clock() >= datetime.fromisoformat(
                            str(deadline)).timestamp():
                        return True
                except (TypeError, ValueError):
                    pass
            return False
        return False

    async def _resume_waiting_step(
        self,
        run_id: str,
        record: Dict[str, Any],
        assignment: Dict[str, Any],
        step: Dict[str, Any],
    ) -> bool:
        if step.get("status") == "awaiting_approval":
            operation_id = _operation_id_for_step(record, step)
            operation = _operation_by_id(record, operation_id) if operation_id else None
            if not operation or operation.get("status") != "approved":
                return False
            assignment = self._close_idle(
                assignment, reason="approval arrived")
            # Approved: the executor re-prepares and verifies the payload
            # before running, so changed content cannot ride an old approval.
            updated = self._mark_step(assignment, step["step_id"], {
                "status": "running", "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, updated, f"step {step['step_id']} approved")
            record = self.lifecycle.get_task(run_id) or record
            step = step_by_id(updated, step["step_id"]) or step
            await self._run_step(run_id, record, updated, step)
            return True
        if not self._resolve_waiting(record, step):
            return False
        assignment = self._close_idle(
            assignment, reason="external wait resolved")
        operation_id = (
            step.get("wait_operation_id")
            or _operation_id_for_step(record, step))
        operation = (
            _operation_by_id(record, operation_id)
            if operation_id else {}) or {}
        budget = dict(assignment.get("budget") or {})
        active = dict(budget.get("active_wait") or {})
        waiting_before = dict(step.get("waiting") or {})
        wait_id = active.get("id") or self._wait_credit_id(
            step, waiting_before, operation_id)
        wait_started = (
            active.get("started_at")
            or waiting_before.get("since")
            or operation.get("claimed_at"))
        self._credit_wait_once(
            budget, wait_id=wait_id or "", started_at=wait_started,
            ended_at=_utc_now_iso())
        if operation_id and operation.get("status") == "waiting":
            # A timer expiry is a bounded re-entry. The old attempt's
            # operation is closed honestly and a new attempt is opened.
            try:
                self.lifecycle.transition_operation(
                    run_id, operation_id, "superseded")
            except TaskLifecycleError:
                pass
        updated = self._mark_step(assignment, step["step_id"], {
            "status": "pending",
            "operation_id": None,
            "attempts": int(step.get("attempts") or 0) + 1,
            "waiting": None,
            "updated_at": _utc_now_iso()})
        if budget:
            updated["budget"] = budget
        self._persist_assignment(
            run_id, updated, f"step {step['step_id']} waiting resolved")
        return True

    def _autonomy_topic_for_step(
        self, step: Dict[str, Any],
    ) -> Optional[str]:
        """The autonomy topic an unapproved step exercises, if any.

        Explicit ``autonomy_topic`` wins. Otherwise only mutating operation
        classes are mapped, and outbound adapters must name their surface —
        an unknown external adapter is governed by the approval/standing
        rules above, not guessed into a topic.
        """
        explicit = str(step.get("autonomy_topic") or "").strip()
        if explicit:
            return explicit
        operation_type = str(step.get("operation_type") or "").lower()
        adapter = str(step.get("adapter") or "").lower()
        if operation_type == "edit":
            return "canvas_edit"
        if (operation_type == "outbound"
                and str(step.get("effect") or "") == "external"):
            if "email" in adapter or "send" in adapter:
                return "send_email"
            if "crm" in adapter:
                return "crm_write"
        return None

    def _autonomy_gate(
        self,
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Re-evaluate runtime autonomy immediately before the effect claim.

        A durable wait/restart can outlive the decision that a hire was
        allowed to act. This consults the SAME gate a chat/canvas turn
        consults, using a fresh session so a revoked trust-calibration
        grant is observed without process state. When the run carries a
        repeat-task graduation route decision, the fresh evidence half is
        revalidated too: a stale benchmark observation or a missing/conflicting
        provider response identity demotes the effect to approval.
        """
        topic = self._autonomy_topic_for_step(step)
        if not topic:
            return None
        provenance = assignment.get("provenance") or {}
        agent_id = str(provenance.get("agent_id") or "").strip() or None
        user_id = (
            str(provenance.get("user_id") or "").strip()
            or str(assignment.get("employee_id") or "").strip()
            or None)
        try:
            from core.autonomy_policy import (
                OUTCOME_EXECUTE, gate_for_topic,
            )

            with self.lifecycle.runs._sessions()() as db:
                gate = gate_for_topic(db, user_id, topic, agent_id)
                if gate.get("outcome") == OUTCOME_EXECUTE:
                    route_revalidation = self._repeat_task_route_revalidation(
                        db, run_id, agent_id, topic, assignment=assignment)
                    if route_revalidation is not None:
                        return route_revalidation
                    return None
                return gate
        except Exception as exc:  # noqa: BLE001 — fail closed for mutating work
            logger.warning(
                "assignment %s: autonomy gate unavailable for %s: %s",
                assignment.get("assignment_id"), step.get("step_id"), exc)
            return {
                "topic": topic,
                "outcome": "propose",
                "reason": (
                    "Runtime autonomy could not be re-verified before this "
                    "mutating step; human approval is required."),
            }

    def _repeat_task_route_revalidation(
        self,
        db: Any,
        run_id: Optional[str],
        agent_id: Optional[str],
        topic: Optional[str] = None,
        assignment: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Demote the effect claim when repeat-task evidence no longer holds.

        Applicability is bound to independently durable assignment state: the
        ``repeat_task_route`` marker the resolver wrote onto the persisted
        plan survives a lost decision log. The decision log is the second,
        complementary source (it covers runs recorded before the marker
        existed and marker writes that failed). A persisted repeat
        assignment whose route records are missing after a restart, and any
        run whose decision log cannot be read, request supervision instead
        of an unconditional effect claim. Unrelated routing — no marker, no
        route decision — is untouched.
        """
        if not run_id or not agent_id:
            return None
        try:
            from core.autonomy_policy import OUTCOME_EXECUTE, OUTCOME_PROPOSE
            from core.llm.graduation_route import (
                ROUTE_DECISION_KIND, revalidate_repeat_task_effect,
            )

            marker = (
                assignment.get("repeat_task_route")
                if isinstance(assignment, dict) else None)
            if not isinstance(marker, dict):
                marker = None
            if marker is not None and str(
                    marker.get("agent_id") or "") not in (
                    "", str(agent_id or "")):
                return {
                    "topic": topic,
                    "outcome": OUTCOME_PROPOSE,
                    "reason": (
                        "The assignment's repeat-task route marker belongs "
                        "to a different agent; human approval is required."),
                    "source": "repeat_task_route_recheck",
                }

            # Server-owned compiled-work half: the workload stamp is bound to
            # the fingerprint of the compiled steps it was validated against.
            # After a plan change or a restart the CURRENT durable steps are
            # re-derived and re-checked here, before anything else is read.
            compiled_revalidation = self._compiled_work_revalidation(
                assignment, topic)
            if compiled_revalidation is not None:
                return compiled_revalidation

            try:
                decisions = self.lifecycle.runs.get_decisions(run_id)
            except Exception as exc:  # noqa: BLE001 — fail closed
                logger.warning(
                    "run %s: decision log unreadable before effect claim: %s",
                    run_id, exc)
                return {
                    "topic": topic,
                    "outcome": OUTCOME_PROPOSE,
                    "reason": (
                        "The run's route decision log could not be read "
                        "before this mutating step; human approval is "
                        "required."),
                    "source": "repeat_task_route_recheck",
                }
            has_route_context = any(
                isinstance(entry, dict)
                and str(entry.get("kind") or "") == ROUTE_DECISION_KIND
                for entry in decisions or [])
            if marker is not None and not has_route_context:
                # Durable assignment state says this run used a repeat-task
                # route, but its decision records are gone (lost records, a
                # failed log write): the requirement survives the log.
                return {
                    "topic": topic,
                    "outcome": OUTCOME_PROPOSE,
                    "reason": (
                        "This repeat-task assignment's route decision "
                        "records are missing; route eligibility must be "
                        "re-approved under supervision."),
                    "source": "repeat_task_route_recheck",
                }
            if marker is None and not has_route_context:
                return None
            revalidation = revalidate_repeat_task_effect(
                db, agent_id=agent_id, decisions=decisions,
                assignment=assignment)
            if revalidation is None:
                return None
            if str(revalidation.get("outcome") or "") == OUTCOME_EXECUTE:
                return None
            return {
                "topic": topic,
                "outcome": OUTCOME_PROPOSE,
                "reason": str(revalidation.get("reason") or (
                    "Repeat-task route evidence must be revalidated before "
                    "this mutating step; human approval is required.")),
                "route_state": revalidation.get("route_state"),
                "build_state": revalidation.get("build_state"),
                "source": "repeat_task_route_recheck",
            }
        except Exception as exc:  # noqa: BLE001 — fail closed
            logger.warning(
                "run %s: repeat-task route revalidation failed: %s",
                run_id, exc)
            from core.autonomy_policy import OUTCOME_PROPOSE
            return {
                "topic": topic,
                "outcome": OUTCOME_PROPOSE,
                "reason": (
                    "Repeat-task route evidence could not be revalidated "
                    "before this mutating step; human approval is required."),
                "source": "repeat_task_route_recheck",
            }

    def _compiled_work_revalidation(
        self,
        assignment: Optional[Dict[str, Any]],
        topic: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Revalidate the server-owned compiled-work contract before an effect.

        The workload stamp is bound (``workload_work``) to the fingerprint of
        the compiled steps it was validated against. After a plan change or a
        restart the CURRENT durable assignment is re-derived here: compiled
        work that no longer satisfies the registered task's contract — a
        different registered task's work, altered steps, or material that
        cannot be verified — cannot claim the effect autonomously. Plans the
        server did not fingerprint-bind (including every unstamped workload)
        are untouched.
        """
        if not isinstance(assignment, dict):
            return None
        binding = assignment.get("workload_work")
        if not isinstance(binding, dict):
            return None
        try:
            from core.canvas_capability_service import compiled_work_contract

            check = compiled_work_contract(
                assignment.get("workload_scope"), assignment, binding=binding)
        except Exception as exc:  # noqa: BLE001 — fail closed
            logger.warning(
                "assignment %s: compiled-work contract unavailable: %s",
                assignment.get("assignment_id"), exc)
            check = {"ok": False, "reasons": ["compiled_work_unavailable"]}
        if check.get("ok"):
            return None
        detail = ("; ".join(
            str(reason) for reason in check.get("reasons") or []))[:400]
        from core.autonomy_policy import OUTCOME_PROPOSE

        return {
            "topic": topic,
            "outcome": OUTCOME_PROPOSE,
            "reason": (
                "This repeat-task assignment's compiled work no longer "
                "satisfies the registered task's server-owned contract "
                f"({detail or 'compiled_work_unavailable'}); human approval "
                "is required."),
            "source": "repeat_task_route_recheck",
        }

    def _adapter_allows_standing(self, adapter: Any) -> bool:
        metadata = getattr(adapter, "metadata", None) or {}
        if metadata.get("allow_standing_authorization"):
            return True
        # The real Outlook transport opts in only when BOTH the live send and
        # bounded live standing authority are explicitly enabled. The shipped
        # default remains approval-only.
        return bool(
            getattr(adapter, "name", "") == "email.send_outlook"
            and os.getenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", "0") == "1"
            and os.getenv(
                "ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND", "0") == "1"
        )

    def _standing_grant_covers(
        self, assignment: Dict[str, Any], step: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """The explicit bounded grant covering this outbound step, if any.

        Coverage is deliberately narrow: outbound effects only, an adapter
        that opted in, an unexpired active grant with remaining uses, and
        every actual recipient inside the named recipient set.
        """
        grant = assignment.get("standing_authority")
        if not isinstance(grant, dict) or grant.get("status") != "active":
            return None
        if "outbound" not in (grant.get("actions") or []):
            return None
        if str(step.get("effect") or "") != "external" or str(
                step.get("operation_type") or "") != "outbound":
            return None
        adapter = self.adapters.get(step.get("adapter") or "")
        if adapter is None or not self._adapter_allows_standing(adapter):
            return None
        if int(grant.get("used_effects") or 0) >= int(
                grant.get("max_effects") or 0):
            return None
        expires_at = str(grant.get("expires_at") or "").strip()
        if expires_at:
            try:
                if self.clock() >= datetime.fromisoformat(expires_at).timestamp():
                    return None
            except (TypeError, ValueError):
                return None
        allowed = {
            str(item).strip().lower()
            for item in (grant.get("recipients") or []) if str(item).strip()
        }
        inputs = self._resolve_inputs(assignment, step)
        recipients = {
            str(item).strip().lower()
            for key in ("to", "cc")
            for item in (inputs.get(key) or [])
            if str(item).strip()
        }
        if not recipients or not recipients <= allowed:
            return None
        return grant

    def _reserve_standing_grant(
        self, run_id: str, assignment: Dict[str, Any], step: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Atomically consume one bounded grant use before dispatch.

        A lost CAS or an exhausted/out-of-scope grant returns None; the
        caller then falls back to the ordinary human approval path. The grant
        is never consumed by a step the grant does not cover.
        """
        grant_id = str(
            (assignment.get("standing_authority") or {}).get("grant_id") or "")
        if not grant_id:
            return None

        def compute(record, current):
            grant = self._standing_grant_covers(current, step)
            if not grant or str(grant.get("grant_id")) != grant_id:
                raise AssignmentError("standing authority is no longer usable")
            use = int(grant.get("used_effects") or 0) + 1
            updated = copy.deepcopy(current)
            next_grant = dict(updated.get("standing_authority") or {})
            next_grant["used_effects"] = use
            next_grant["usage"] = list(next_grant.get("usage") or []) + [{
                "use": use,
                "step_id": step.get("step_id"),
                "operation_id": step.get("operation_id"),
                "at": _utc_now_iso(),
            }]
            if use >= int(next_grant.get("max_effects") or 0):
                next_grant["status"] = "exhausted"
            updated["standing_authority"] = next_grant
            return updated, {
                "assignment": updated,
                "grant": next_grant,
                "use": use,
            }

        try:
            return self.lifecycle.mutate_assignment(
                run_id, compute,
                rationale=(
                    f"standing authority use for {step.get('step_id')}"))
        except Exception as exc:  # noqa: BLE001 — fall back to approval
            logger.warning(
                "assignment %s: standing authority reservation refused: %s",
                run_id, exc)
            return None

    async def _run_step(
        self,
        run_id: str,
        record: Dict[str, Any],
        assignment: Dict[str, Any],
        step: Dict[str, Any],
    ) -> None:
        # Re-evaluate business readiness against the CURRENT durable record
        # immediately before the operation claim. Scheduling is only a hint;
        # facts/qualifications may have changed since the scheduler read.
        fresh_record = self.lifecycle.get_task(run_id) or record
        fresh_assignment = self._sync_assignment(
            fresh_record, fresh_record.get("assignment") or assignment)
        fresh_step = step_by_id(
            fresh_assignment, step.get("step_id")) or step
        fresh_auth = str(
            (fresh_record.get("task_revision") or {}).get("authorization")
            or "read_only")
        decision = evaluate_step_readiness(
            fresh_step, fresh_assignment, task_authorization=fresh_auth)
        if not decision["eligible"]:
            fresh_assignment = self._mark_step(
                fresh_assignment, fresh_step["step_id"], {
                    "status": "pending",
                    "readiness_blocker": decision,
                    "updated_at": _utc_now_iso(),
                })
            self._persist_assignment(
                run_id, fresh_assignment,
                f"step {fresh_step['step_id']} readiness changed before claim")
            return
        record, assignment, step = fresh_record, fresh_assignment, fresh_step
        operation = self._ensure_operation(run_id, record, assignment, step)
        operation_id = operation["operation_id"]
        assignment = self._mark_step(assignment, step["step_id"], {
            "operation_id": operation_id,
            "updated_at": _utc_now_iso()})
        self._persist_assignment(
            run_id, assignment, f"step {step['step_id']} operation bound")
        step = step_by_id(assignment, step["step_id"]) or step

        external = step.get("effect") == "external"
        approval = step.get("approval") or {}
        standing = str(step.get("standing_authorization") or "").strip()
        standing_reservation = None
        if self._standing_grant_covers(assignment, step):
            try:
                prepared = self._prepare_effect(assignment, step, record)
            except Exception as exc:  # noqa: BLE001 — fall back to approval
                logger.warning(
                    "assignment %s: standing authority prepare refused for "
                    "%s: %s", run_id, step.get("step_id"), exc)
                prepared = None
            if prepared is not None:
                standing_reservation = self._reserve_standing_grant(
                    run_id, assignment, step)
            if standing_reservation:
                assignment = standing_reservation["assignment"]
                grant = standing_reservation["grant"]
                assignment = self._mark_step(assignment, step["step_id"], {
                    "standing_authority_receipt": {
                        "grant_id": grant.get("grant_id"),
                        "use": standing_reservation["use"],
                        "max_effects": grant.get("max_effects"),
                        "recipients": list(grant.get("recipients") or []),
                        "payload_sha256": prepared.get("payload_sha256"),
                        "authorized_at": _utc_now_iso(),
                    },
                })
                self._persist_assignment(
                    run_id, assignment,
                    f"step {step['step_id']} covered by standing authority")
                step = step_by_id(assignment, step["step_id"]) or step

        authorized_by_grant = standing_reservation is not None
        if external and not approval.get("required") and not (
                authorized_by_grant or (
                    standing
                    and standing in (assignment.get("authorized_actions") or [])
                )):
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "failed",
                "failure": {
                    "reason": "action_not_authorized",
                    "message": (
                        "This step changes an external system but the "
                        "assignment carries neither an explicit approval "
                        "requirement nor standing authority for it."),
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "step blocked: action not authorized")
            return

        # Re-verify runtime autonomy AFTER any durable wait and immediately
        # before the effect claim. A grant that was valid when the assignment
        # was prepared (or before a restart) is not assumed to still hold.
        if not approval.get("required") and not authorized_by_grant:
            autonomy_gate = self._autonomy_gate(
                assignment, step, run_id=run_id)
            if autonomy_gate is not None:
                assignment = self._mark_step(assignment, step["step_id"], {
                    "autonomy": {
                        "topic": autonomy_gate.get("topic"),
                        "outcome": autonomy_gate.get("outcome"),
                        "reason": autonomy_gate.get("reason"),
                    },
                    "updated_at": _utc_now_iso(),
                })
                self._persist_assignment(
                    run_id, assignment,
                    f"step {step['step_id']} re-gated by autonomy policy")
                step = step_by_id(assignment, step["step_id"]) or step
                approval = {
                    **approval,
                    "required": True,
                    "purpose": (
                        autonomy_gate.get("reason")
                        or "Runtime autonomy must be re-approved."),
                    "source": "autonomy_recheck",
                }

        if approval.get("required") and not authorized_by_grant:
            operation = _operation_by_id(
                self.lifecycle.get_task(run_id) or record, operation_id) or operation
            if operation.get("status") == "awaiting_approval":
                return
            if operation.get("status") in ("pending", "running"):
                try:
                    prepared = self._prepare_effect(assignment, step, record)
                except Exception as exc:  # noqa: BLE001 — durable refusal
                    assignment = self._mark_step(assignment, step["step_id"], {
                        "status": "failed",
                        "failure": {
                            "reason": "approval_payload_unavailable",
                            "message": _bounded(str(exc), 500),
                        },
                        "updated_at": _utc_now_iso()})
                    self._persist_assignment(
                        run_id, assignment, "approval payload unavailable")
                    return
                self.lifecycle.request_operation_approval(
                    run_id, operation_id,
                    payload=prepared["payload"],
                    artifact_revision=prepared.get("artifact_revision"),
                    authorization_revision=_authorization_revision(assignment),
                    requested_by=prepared.get("requested_by") or (
                        assignment.get("employee_id") or ""),
                    purpose=approval.get("purpose", ""),
                )
                hitl_action_id = await self._request_hitl_approval(
                    run_id, assignment, step, operation_id, prepared)
                approval_waiting = {
                    "state": "waiting_for_person",
                    "party": "approver",
                    "resume_on": "approval",
                    "correlation_id": hitl_action_id,
                    "hitl_id": hitl_action_id,
                    "since": _utc_now_iso(),
                    "detail": approval.get("purpose", ""),
                }
                self._enter_wait(
                    run_id, waiting=approval_waiting,
                    summary=f"approval required for {step.get('title')}")
                assignment = self._mark_step(assignment, step["step_id"], {
                    "status": "awaiting_approval",
                    "artifact_revision": prepared.get("artifact_revision"),
                    "approval_request": {
                        "payload_sha256": prepared["payload_sha256"],
                        "artifact_revision": prepared.get("artifact_revision"),
                        "authorization_revision": _authorization_revision(
                            assignment),
                        "hitl_action_id": hitl_action_id,
                        "purpose": approval.get("purpose", ""),
                    },
                    "updated_at": _utc_now_iso()})
                self._persist_assignment(
                    run_id, assignment, "step awaiting approval")
                return
            if operation.get("status") == "approved":
                # Verify the approval still covers the CURRENT payload.
                try:
                    prepared = self._prepare_effect(assignment, step, record)
                except Exception as exc:  # noqa: BLE001
                    self.lifecycle.invalidate_approval(
                        run_id, operation_id, reason=str(exc))
                    assignment = self._mark_step(assignment, step["step_id"], {
                        "status": "awaiting_approval",
                        "updated_at": _utc_now_iso()})
                    self._persist_assignment(
                        run_id, assignment, "approval payload unavailable")
                    return
                request = operation.get("approval_request") or {}
                if (prepared["payload_sha256"] != request.get("payload_sha256")
                        or str(prepared.get("artifact_revision") or "")
                        != str(request.get("artifact_revision") or "")
                        or _authorization_revision(assignment)
                        != str(request.get("authorization_revision") or "")):
                    self.lifecycle.invalidate_approval(
                        run_id, operation_id,
                        reason="payload, artifact or authorization changed "
                               "after approval")
                    self.lifecycle.request_operation_approval(
                        run_id, operation_id,
                        payload=prepared["payload"],
                        artifact_revision=prepared.get("artifact_revision"),
                        authorization_revision=_authorization_revision(
                            assignment),
                        requested_by=prepared.get("requested_by") or (
                            assignment.get("employee_id") or ""),
                        purpose=approval.get("purpose", ""),
                    )
                    hitl_action_id = await self._request_hitl_approval(
                        run_id, assignment, step, operation_id, prepared)
                    self._enter_wait(
                        run_id,
                        waiting={
                            "state": "waiting_for_person",
                            "party": "approver",
                            "resume_on": "approval",
                            "correlation_id": hitl_action_id,
                            "hitl_id": hitl_action_id,
                            "since": _utc_now_iso(),
                            "detail": approval.get("purpose", ""),
                        },
                        summary=(
                            f"approval required for {step.get('title')} "
                            f"(effect changed)"))
                    assignment = self._mark_step(assignment, step["step_id"], {
                        "status": "awaiting_approval",
                        "approval_request": {
                            "payload_sha256": prepared["payload_sha256"],
                            "artifact_revision": prepared.get(
                                "artifact_revision"),
                            "hitl_action_id": hitl_action_id,
                        },
                        "updated_at": _utc_now_iso()})
                    self._persist_assignment(
                        run_id, assignment,
                        "approval invalidated: changed effect")
                    return
            # Any other status is terminal; sync handles it on next loop.

        claimed = self.lifecycle.claim_execution(
            run_id, operation_id,
            execution_id=f"{assignment.get('assignment_id')}:"
                         f"{step['step_id']}:{int(step.get('attempts') or 0) + 1}")
        if not claimed.get("granted"):
            if claimed.get("already_complete"):
                return
            # Another worker holds the claim. Leave the plan durable; the
            # next pass re-reads the operation rather than duplicating it.
            return

        context = self._context(assignment, step, record)
        resolved_inputs = self._resolve_inputs(assignment, step)
        context["resolved_inputs"] = copy.deepcopy(resolved_inputs)
        adapter = self.adapters.get(step.get("adapter") or "")
        if adapter is None:
            self.lifecycle.transition_operation(
                run_id, operation_id, "failed")
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "failed",
                "failure": {
                    "reason": "adapter_unavailable",
                    "message": f"adapter '{step.get('adapter')}' is not "
                               f"registered",
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "adapter unavailable")
            return

        cost_bound = self._step_cost_bound(step, adapter)
        reservation = self._reserve_step_cost(
            run_id, assignment, step, operation_id, cost_bound, adapter)
        if not reservation.get("ok"):
            try:
                self.lifecycle.transition_operation(
                    run_id, operation_id, "failed")
            except TaskLifecycleError:
                pass
            self._attach_receipt(
                run_id, operation, step,
                {"summary": reservation.get("message") or
                 reservation.get("reason") or "cost budget refused"},
                observed_status="failed_before_effect",
                error_class=str(
                    reservation.get("reason") or "cost_budget_refused"))
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "failed",
                "failure": {
                    "reason": str(
                        reservation.get("reason")
                        or "assignment_cost_budget_exhausted"),
                    "message": _bounded(
                        reservation.get("message") or
                        "The operation was refused before dispatch by the "
                        "hard cost budget.", 500),
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "cost budget refused before dispatch")
            return
        assignment = reservation.get("assignment") or assignment
        cost_bound = float(reservation.get("bound") or 0.0)

        try:
            remaining = self._remaining_wall_seconds(assignment)
            if remaining is not None and remaining <= 0:
                raise AssignmentError(
                    "assignment wall budget was exhausted during an operation")
            invocation = _invoke(
                adapter.handler, dict(resolved_inputs), context)
            if remaining is None:
                result = await invocation
            else:
                result = await asyncio.wait_for(invocation, timeout=remaining)
            result = dict(result or {})
        except NeedsContext as exc:
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "released")
            await self._record_gap(run_id, record, assignment, step, operation_id, exc.gap)
            return
        except WaitingForExternal as exc:
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "released")
            now = _utc_now_iso()
            waiting = _json_safe(exc.waiting)
            waiting["since"] = waiting.get("since") or now
            self.lifecycle.set_operation_waiting(
                run_id, operation_id, waiting=waiting)
            self._enter_wait(
                run_id, waiting=waiting,
                summary=(waiting or {}).get("detail", ""))
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "waiting",
                "waiting": waiting,
                "wait_operation_id": operation_id,
                "updated_at": now})
            budget = dict(assignment.get("budget") or {})
            budget["wait_credits_schema"] = 1
            wait_id = self._wait_credit_id(step, waiting, operation_id)
            if not budget.get("active_wait"):
                budget["active_wait"] = {
                    "id": wait_id,
                    "step_id": step.get("step_id"),
                    "correlation_id": waiting.get("correlation_id"),
                    "started_at": waiting["since"],
                }
            if not budget.get("waiting_since"):
                budget["waiting_since"] = waiting["since"]
            assignment["budget"] = budget
            self._persist_assignment(
                run_id, assignment, "step waiting for external")
            return
        except ExternalOutcomeUnknown as exc:
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "uncertain")
            self.lifecycle.record_uncertain_outcome(
                run_id, operation_id, reason=exc.reason,
                evidence=exc.evidence, observed_by=step.get("adapter") or "")
            self._attach_receipt(
                run_id, operation, step,
                {"summary": exc.reason, "evidence": [exc.evidence]},
                observed_status="uncertain",
                error_class="external_outcome_unknown",
                reconciliation_required=True)
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "uncertain",
                "failure": {
                    "reason": "external_outcome_unknown",
                    "message": _bounded(exc.reason, 500),
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "external outcome uncertain")
            return
        except asyncio.CancelledError as exc:
            # Cancellation after an external dispatch is not proof of no
            # effect. Persist uncertainty before propagating the cancellation.
            if str(step.get("effect") or "") == "external":
                reason = (
                    f"dispatch cancelled after invocation "
                    f"({type(exc).__name__})")
                assignment = self._settle_step_cost(
                    assignment, run_id, step, operation_id, cost_bound,
                    "uncertain")
                self.lifecycle.record_uncertain_outcome(
                    run_id, operation_id, reason=reason,
                    evidence=reason,
                    observed_by=step.get("adapter") or "")
                self._attach_receipt(
                    run_id, operation, step,
                    {"summary": reason},
                    observed_status="uncertain",
                    error_class="external_dispatch_cancelled",
                    reconciliation_required=True)
                assignment = self._mark_step(assignment, step["step_id"], {
                    "status": "uncertain",
                    "failure": {
                        "reason": "external_outcome_unknown",
                        "message": reason,
                    },
                    "updated_at": _utc_now_iso()})
                self._persist_assignment(
                    run_id, assignment, "external dispatch cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 — durable failure state
            external = str(step.get("effect") or "") == "external"
            effect_possible = external and not (
                isinstance(exc, ExternalOutcomeNotApplied)
                or getattr(exc, "effect_possible", True) is False)
            if effect_possible:
                # The adapter was invoked but the exception does not prove the
                # effect was absent (parse error, timeout, ordinary runtime
                # error). Never label this failed-before-effect; a resend could
                # duplicate a real provider effect.
                reason = (
                    f"external dispatch raised {type(exc).__name__} after "
                    f"invocation; effect may have landed")
                assignment = self._settle_step_cost(
                    assignment, run_id, step, operation_id, cost_bound,
                    "uncertain")
                self.lifecycle.record_uncertain_outcome(
                    run_id, operation_id, reason=reason,
                    evidence=f"{type(exc).__name__}: {exc}",
                    observed_by=step.get("adapter") or "")
                self._attach_receipt(
                    run_id, operation, step,
                    {"summary": reason, "error": str(exc)[:500]},
                    observed_status="uncertain",
                    error_class="adapter_exception_after_dispatch",
                    reconciliation_required=True)
                assignment = self._mark_step(assignment, step["step_id"], {
                    "status": "uncertain",
                    "failure": {
                        "reason": "external_outcome_unknown",
                        "message": _bounded(reason, 500),
                    },
                    "updated_at": _utc_now_iso()})
                self._persist_assignment(
                    run_id, assignment, "external dispatch uncertain")
                return
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "failed_before_effect")
            try:
                self.lifecycle.transition_operation(
                    run_id, operation_id, "failed")
            except TaskLifecycleError:
                pass
            self._attach_receipt(
                run_id, operation, step,
                {"summary": str(exc)},
                observed_status="failed_before_effect",
                error_class="adapter_error")
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "failed",
                "failure": {
                    "reason": "adapter_error",
                    "message": _bounded(str(exc), 500),
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "adapter error")
            return

        outcome = str(result.get("status") or "applied")
        if outcome == "needs_context":
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "released")
            await self._record_gap(
                run_id, record, assignment, step, operation_id,
                result.get("gap") or {})
            return
        if outcome == "waiting":
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "released")
            waiting = result.get("waiting") or {}
            self.lifecycle.set_operation_waiting(
                run_id, operation_id, waiting=waiting)
            self._enter_wait(
                run_id, waiting=waiting,
                summary=(waiting or {}).get("detail", ""))
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "waiting",
                "waiting": _json_safe(waiting),
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "step waiting")
            return
        if outcome == "uncertain":
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "uncertain")
            # Preserve everything the provider did report -- especially a
            # readback-conflict remote identity -- so reconciliation settles
            # the ORIGINAL operation rather than guessing or resending.
            uncertain_execution = _json_safe({
                "status": "uncertain",
                "summary": _bounded(result.get("summary") or "", 500),
                "evidence": result.get("evidence") or [],
                "data": result.get("data"),
                "provider_ref": result.get("provider_ref"),
                "remote_id": result.get("remote_id"),
                "provider": result.get("provider"),
                "operation": result.get("operation"),
                "provider_receipt": result.get("provider_receipt"),
                "payload_sha256": result.get("payload_sha256"),
                "verification": result.get("verification"),
                "oracle_verified": result.get("oracle_verified"),
                "oracle_evidence": result.get("oracle_evidence"),
                "conflicts": result.get("conflicts") or [],
                "at": _utc_now_iso(),
            })
            try:
                self.lifecycle.attach_operation_field(
                    run_id, operation_id, "execution", uncertain_execution)
            except Exception as exc:  # noqa: BLE001 — receipt still records
                logger.warning(
                    "assignment %s: uncertain execution attach failed: %s",
                    run_id, exc)
            self.lifecycle.record_uncertain_outcome(
                run_id, operation_id,
                reason=_bounded(result.get("reason") or "provider outcome "
                                "unknown", 300),
                evidence=_bounded(result.get("evidence") or "", 500),
                observed_by=step.get("adapter") or "")
            self._attach_receipt(
                run_id, operation, step, result,
                observed_status="uncertain",
                error_class="external_outcome_unknown",
                reconciliation_required=True)
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "uncertain",
                "failure": {
                    "reason": "external_outcome_unknown",
                    "message": _bounded(result.get("reason") or "", 500),
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "external outcome uncertain")
            return
        if outcome == "unavailable":
            # A read that could not be performed is a failure, not an empty
            # result: never complete the step or fabricate data for it.
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "failed_before_effect")
            try:
                self.lifecycle.transition_operation(
                    run_id, operation_id, "failed")
            except TaskLifecycleError:
                pass
            error_class = _bounded(
                result.get("error_class") or "source_unavailable", 120)
            self._attach_receipt(
                run_id, operation, step, result,
                observed_status="unavailable",
                error_class=error_class)
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "failed",
                "failure": {
                    "reason": "source_unavailable",
                    "message": _bounded(
                        result.get("message")
                        or "the requested source was unavailable", 500),
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "source unavailable")
            return
        if outcome == "skipped":
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "released")
            self.lifecycle.transition_operation(
                run_id, operation_id, "cancelled")
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "skipped",
                "result": {"summary": _bounded(
                    result.get("summary") or "step not required", 500)},
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "step skipped")
            return
        if outcome not in ("applied", "completed"):
            assignment = self._settle_step_cost(
                assignment, run_id, step, operation_id, cost_bound,
                "failed_before_effect")
            self.lifecycle.transition_operation(
                run_id, operation_id, "failed")
            self._attach_receipt(
                run_id, operation, step, result,
                observed_status="failed_before_effect",
                error_class=_bounded(outcome, 120))
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "failed",
                "failure": {
                    "reason": _bounded(outcome, 120),
                    "message": _bounded(result.get("message") or "", 500),
                },
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "adapter returned failure")
            return

        # APPLIED: persist the operation result BEFORE advancing the plan.
        execution = _json_safe({
            "summary": _bounded(result.get("summary") or "", 500),
            "evidence": result.get("evidence") or [],
            "artifact": result.get("artifact"),
            "content_sha256": result.get("content_sha256"),
            "artifact_revision": (
                (result.get("artifact") or {}).get("revision")
                if isinstance(result.get("artifact"), dict) else None),
            # Preserve the material proof/coverage on the durable step result.
            # The operation receipt also carries it, but dependent readiness
            # evaluates the step result and must not lose the proof.
            "verification": result.get("verification"),
            "oracle_verified": result.get("oracle_verified"),
            "oracle_evidence": result.get("oracle_evidence"),
            "coverage": result.get("coverage"),
            "readback": result.get("readback"),
            "resource_id": result.get("resource_id"),
            "request_id": result.get("request_id"),
            "subject": result.get("subject"),
            "subject_id": result.get("subject_id"),
            "message_id": result.get("message_id"),
            "account": result.get("account"),
            "mailbox": result.get("mailbox"),
            "value": result.get("value"),
            "unit": result.get("unit"),
            "expression": result.get("expression"),
            "operation": result.get("operation"),
            "measure": result.get("measure"),
            "group_by": result.get("group_by"),
            "grouping_dimension": result.get("grouping_dimension"),
            "values": result.get("values"),
            "subtotals": result.get("subtotals"),
            "calculation_receipt": result.get("calculation_receipt"),
            "source": result.get("source"),
            "source_label": result.get("source_label"),
            "formulas": result.get("formulas"),
            "matched_count": result.get("matched_count"),
            "selected_count": result.get("selected_count"),
            "truncated": result.get("truncated"),
            "substantive": result.get("substantive"),
            "source_version": result.get("source_version"),
            "provider_ref": result.get("provider_ref"),
            "remote_id": result.get("remote_id"),
            "rows": result.get("rows"),
            "line_items": result.get("line_items"),
            "schema": result.get("schema"),
            "text": result.get("text"),
            "decision": result.get("decision"),
            "draft": result.get("draft"),
            "data": result.get("data"),
            "at": _utc_now_iso(),
        })
        current_op = _operation_by_id(
            self.lifecycle.get_task(run_id) or record, operation_id) or {}
        if current_op.get("status") != "applied":
            self.lifecycle.transition_operation(
                run_id, operation_id, "applied")
        observed = result.get("provider_state") or "confirmed"
        if observed == "sent":
            observed = "provider_accepted"
        receipt = self._attach_receipt(
            run_id, operation, step, result,
            observed_status=str(observed))
        execution["receipt"] = receipt
        self.lifecycle.attach_operation_field(
            run_id, operation_id, "execution", execution)

        artifact = result.get("artifact") if isinstance(
            result.get("artifact"), dict) else {}
        try:
            actual_cost = float(result.get("cost_usd") or 0)
        except (TypeError, ValueError):
            actual_cost = 0.0
        assignment = self._settle_step_cost(
            assignment, run_id, step, operation_id, cost_bound,
            "applied", actual_cost)
        assignment = self._mark_step(assignment, step["step_id"], {
            "status": "applied",
            "result": execution,
            "artifact_revision": artifact.get("revision"),
            "evidence_refs": list(result.get("evidence_refs") or []),
            "updated_at": _utc_now_iso()})
        assignment = self._apply_deliverables(assignment, step, result)
        self._persist_assignment(
            run_id, assignment, f"step {step['step_id']} applied")

    async def _record_gap(
        self,
        run_id: str,
        record: Dict[str, Any],
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        operation_id: str,
        gap: Dict[str, Any],
    ) -> None:
        gap = dict(gap or {})
        if not str(gap.get("question") or "").strip():
            gap["question"] = (
                f"Provide the missing information to continue "
                f"'{step.get('title')}'.")
        if not str(gap.get("next_action") or "").strip():
            gap["next_action"] = (
                str(gap.get("next_retrieval") or "").strip()
                or "Provide the missing evidence and retry the step.")
        waiting = gap.get("waiting") or {
            "state": "waiting_for_person",
            "party": gap.get("resolver") or "owner",
            "resume_on": "answer",
            "since": _utc_now_iso(),
        }
        binding_key = _gap_binding_key(gap)
        existing = [
            question for question in
            (record.get("task_revision") or {}).get("unresolved") or []
            if isinstance(question, dict)
            and question.get("status") == "open"
            and question.get("step_id") == step.get("step_id")
            and str(question.get("concept") or "")
            == str(gap.get("concept") or "")
            and _gap_binding_key(question) == binding_key
        ]
        if existing:
            question_id = existing[0]["question_id"]
        else:
            question = {
                "question_id": gap.get("question_id"),
                "item": gap.get("item") or step.get("title") or "",
                "question": gap["question"],
                "kind": gap.get("kind") or "missing_evidence",
                "evidence": gap.get("evidence") or "",
                "next_action": gap.get("next_action") or gap.get(
                    "next_retrieval"),
                "inputs": gap.get("inputs") or {},
                "concept": gap.get("concept") or "",
                "reason": gap.get("reason") or "",
                "affected_subjects": gap.get("affected_subjects") or [],
                "checked_evidence": gap.get("checked_evidence") or [],
                "next_retrieval": gap.get("next_retrieval") or "",
                "resolver": gap.get("resolver") or "",
                "step_id": step.get("step_id"),
                "waiting": waiting,
                "binding_key": binding_key,
            }
            self.lifecycle.apply_transition(run_id, {
                "kind": "record_unresolved",
                "requested_change": _bounded(gap["question"], 500),
                "questions": [question],
                "source_operation": operation_id,
            })
            refreshed = self.lifecycle.get_task(run_id) or record
            question_id = None
            for item in (refreshed.get("task_revision") or {}).get(
                    "unresolved") or []:
                if (item.get("status") == "open"
                        and item.get("step_id") == step.get("step_id")
                        and str(item.get("concept") or "")
                        == str(gap.get("concept") or "")
                        and _gap_binding_key(item) == binding_key):
                    question_id = item["question_id"]
            question_id = question_id or str(gap.get("question_id") or "")

        self.lifecycle.set_operation_waiting(
            run_id, operation_id, waiting={
                **waiting,
                "gap_question_id": question_id,
            })
        self._enter_wait(
            run_id,
            waiting={**waiting, "gap_question_id": question_id},
            summary=gap["question"])
        assignment = self._mark_step(assignment, step["step_id"], {
            "status": "waiting",
            "gap_ids": sorted(set(
                list(step.get("gap_ids") or []) + [question_id])),
            "waiting": _json_safe(waiting),
            "updated_at": _utc_now_iso()})
        self._persist_assignment(
            run_id, assignment, "step waiting for context")

    def _apply_deliverables(
        self,
        assignment: Dict[str, Any],
        step: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = copy.deepcopy(assignment)
        artifact = result.get("artifact") if isinstance(
            result.get("artifact"), dict) else None
        explicit = result.get("deliverables") or []
        delivered = [
            item for item in explicit if isinstance(item, dict)
        ]
        if not delivered:
            target_id = (step.get("inputs") or {}).get("deliverable_id")
            if target_id and not artifact:
                delivered.append({
                    "deliverable_id": target_id,
                    "status": "applied",
                })
        if artifact and not delivered:
            target_id = (step.get("inputs") or {}).get("deliverable_id")
            if target_id:
                delivered.append({
                    "deliverable_id": target_id,
                    "status": "applied",
                    "artifact_revision": artifact.get("revision"),
                    "artifact_path": artifact.get("path"),
                    "sha256": artifact.get("sha256"),
                })
            else:
                kind = artifact.get("kind")
                for deliverable in updated.get("deliverables") or []:
                    if (deliverable.get("required", True)
                            and deliverable.get("status") != "applied"
                            and (not kind or deliverable.get("kind") == kind
                                 or deliverable.get("step_id")
                                 == step.get("step_id"))):
                        delivered.append({
                            "deliverable_id": deliverable.get(
                                "deliverable_id"),
                            "status": "applied",
                            "artifact_revision": artifact.get("revision"),
                            "artifact_path": artifact.get("path"),
                            "sha256": artifact.get("sha256"),
                        })
                        break
        for item in delivered:
            for deliverable in updated.get("deliverables") or []:
                if deliverable.get("deliverable_id") != item.get(
                        "deliverable_id"):
                    continue
                deliverable.update({
                    "status": item.get("status") or "applied",
                    "artifact_revision": item.get("artifact_revision"),
                    "artifact_path": item.get("artifact_path"),
                    "sha256": item.get("sha256"),
                })
        return updated

    def _finish_cancelled(
        self, run_id: str, record: Dict[str, Any],
    ) -> Dict[str, Any]:
        assignment = record.get("assignment") or {}
        if assignment.get("status") != "cancelled":
            self.cancel(run_id, reason="task authorization cancelled")
        return self.status(run_id)


# ---------------------------------------------------------------------------
# Built-in technical adapters. These are generic capabilities, not business
# workflows. A deployment registers outbound adapters explicitly; nothing
# here can send a message on its own.
# ---------------------------------------------------------------------------


# Declared effect vocabulary is shared with the planner and the coverage
# inventory (``core.action_effects``). ``plan_produced`` (goals.decompose) is
# pure plan-shape output, not a durable mutation: it must not be counted as
# persisted execution proof.
_MUTATING_ACTION_EFFECTS = MUTATING_EFFECTS

# Registered actions that mutate local durable state without declaring an
# effect family in their registration metadata.  Keep this list aligned with
# the local postcondition families in core.oracle.postcondition_verifiers.
# Explicit registration effects are the primary declaration (and now cover
# every durable mutation in the registry); this legacy list remains because it
# protects deployed plans whose action metadata predates that declaration.
_LOCAL_MUTATING_ACTIONS = {
    "canvas.present_chart", "canvas.present_markdown", "canvas.restore_version",
    "canvas.update", "tasks.create", "goals.create", "goals.evaluate",
    "goal_runs.start",
}


def _registered_action_mutates(action: Any, context: Dict[str, Any]) -> bool:
    name = str(getattr(action, "name", "") or "")
    step_effect = str((context.get("step") or {}).get("effect") or "")
    if step_effect == "external":
        return True
    if name in _LOCAL_MUTATING_ACTIONS:
        return True
    if _declares_mutation(action):
        return True
    # Explicitly read-only or plan-only declarations are non-mutating. Empty
    # or unknown effect metadata is UNQUALIFIED, not an implicit read proof:
    # it must satisfy the same independent-verification gate or the action
    # could silently evade the oracle by omitting its declaration.
    if _declares_read_only(action) or _declares_plan_output(action):
        return False
    return True


def _action_result_outcome(result: Any, *, mutating: bool) -> str:
    """Classify a returned action envelope without inventing an outcome.

    Returns ``applied``, ``failed`` (trusted proof of no effect),
    ``uncertain`` (effect may have landed) or ``unavailable`` (a read could
    not be performed). A malformed or internally contradictory mutation is
    uncertain: an absent remote id is not proof that nothing landed.
    """
    if not isinstance(result, dict):
        return "uncertain" if mutating else "unavailable"

    action_result = str(result.get("action_result") or "").strip().lower()
    status = str(result.get("status") or "").strip().lower()
    success = result.get("success")
    verification = result.get("verification") if isinstance(
        result.get("verification"), dict) else {}
    verification_status = str(
        verification.get("status") or "").strip().lower()
    verified_flag = verification.get("verified")
    has_error = bool(result.get("error") or result.get("error_kind"))

    success_status = {"success", "applied", "completed", "ok", "settled"}
    failure_status = {
        "failed", "error", "refused", "rejected", "duplicate",
        "not_applied", "proven_not_applied",
    }
    uncertain_status = {"uncertain", "conflict", "unknown", "pending"}
    unavailable_status = {"unavailable"}
    verified_status = {"verified", "complete", "applied", "success", "ok"}
    failed_verification = {
        "failed", "not_applied", "proven_not_applied", "mismatch",
        "conflict", "incomplete", "unavailable", "unknown",
    }

    # Contradictions are never resolved in favour of "nothing happened".
    contradictory = False
    if action_result == "applied" and (
            status in failure_status | uncertain_status | unavailable_status
            or success is False
            or verification_status in failed_verification
            or verified_flag is False):
        contradictory = True
    if action_result in ("proven_not_applied", "not_applied") and (
            status in success_status
            or success is True
            or verification_status in verified_status):
        contradictory = True
    if status in success_status and (
            action_result in failure_status | uncertain_status
            | unavailable_status
            or success is False
            or verification_status in {
                "failed", "not_applied", "mismatch", "conflict",
                "incomplete", "unavailable"}
            or verified_flag is False):
        contradictory = True
    if status in failure_status and action_result == "applied":
        contradictory = True
    if success is True and has_error:
        contradictory = True
    if success is False and status in success_status:
        contradictory = True
    if contradictory:
        if not mutating and "unavailable" in {
                action_result, status, verification_status}:
            return "unavailable"
        return "uncertain" if mutating else "failed"

    if action_result:
        if action_result == "applied":
            return "applied"
        if action_result in ("proven_not_applied", "not_applied"):
            return "failed"
        if action_result in ("uncertain", "conflict", "unknown"):
            return "uncertain"
        if action_result in unavailable_status:
            return "uncertain" if mutating else "unavailable"
        return "uncertain" if mutating else "failed"

    if verification_status:
        if verification_status in ("conflict", "mismatch"):
            return "uncertain"
        if verification_status in ("failed", "not_applied",
                                   "proven_not_applied"):
            return "uncertain" if mutating else "failed"
        if verification_status in ("incomplete", "unavailable", "unknown"):
            return "uncertain" if mutating else "unavailable"
        if verified_flag is False:
            return "uncertain" if mutating else "failed"

    if status in ("conflict", "uncertain", "unknown", "pending"):
        return "uncertain"
    if status in unavailable_status:
        return "uncertain" if mutating else "unavailable"
    if status in success_status:
        return "applied"
    if status in failure_status:
        # A bare failure status is not proof that an outbound mutation did
        # not land; only the explicit action_result proof can say that.
        return "uncertain" if mutating else "failed"
    if success is False or has_error:
        return "uncertain" if mutating else "failed"
    if not mutating:
        # Legacy read actions return a bare payload with no status.
        return "applied" if result else "unavailable"
    return "uncertain"


@register_assignment_adapter(
    "action.registry",
    description="Dispatch one registered action through the shared registry",
    metadata={"effect": "declared", "required_actions": [],
              "allow_standing_authorization": False})
async def _action_registry_adapter(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    from core.action_registry import action_registry

    name = str(inputs.get("action") or "").strip()
    arguments = inputs.get("arguments") or {}
    if not name:
        raise NeedsContext({
            "concept": "registered_action",
            "reason": "the step names no registered action",
            "question": "Which supported action should run?",
            "kind": "missing_evidence",
        })
    if not isinstance(arguments, dict):
        return {
            "status": "failed",
            "message": "registered action arguments must be a mapping",
        }
    action = action_registry.get_action(name)
    if action is None:
        return {
            "status": "failed",
            "message": f"registered action '{name}' is not available",
            "error_class": "action_not_registered",
        }
    # Freeze the authorized request before any handler runs.  The handler gets
    # a separate deep copy, so in-place edits (including nested lists) cannot
    # change the expected payload, operation, organization or target.
    try:
        authorized_arguments = copy.deepcopy(arguments)
        dispatch_arguments = copy.deepcopy(authorized_arguments)
    except Exception as exc:  # noqa: BLE001 - refuse before dispatch
        return {
            "status": "failed",
            "message": (
                "the authorized request could not be frozen before dispatch: "
                f"{type(exc).__name__}"),
            "error_class": "request_snapshot_unavailable",
        }
    expected_binding: Dict[str, str] = {}
    try:
        from core.connected_actions import (
            is_connected_mutation,
            oracle_request_binding,
        )

        known_connected = is_connected_mutation(name)
        expected_binding = oracle_request_binding(name, authorized_arguments)
    except Exception as exc:  # noqa: BLE001 - malformed binding is a refusal
        known_connected = name.endswith(
            ("books.create_bill", "books.create_estimate",
             "outlook.create_draft", "shopify_create_product"))
        if known_connected:
            return {
                "status": "failed",
                "message": (
                    "the authorized request binding could not be constructed "
                    f"before dispatch: {type(exc).__name__}"),
                "error_class": "payload_binding_unavailable",
            }
    canonical_digest = str(
        expected_binding.get("payload_sha256") or "")
    supplied_digest = str(
        authorized_arguments.get("payload_sha256") or "")
    if known_connected:
        if not canonical_digest:
            return {
                "status": "failed",
                "message": (
                    "the connected mutation has no canonical request digest; "
                    "refusing before dispatch"),
                "error_class": "payload_binding_unavailable",
            }
        if supplied_digest and supplied_digest != canonical_digest:
            return {
                "status": "failed",
                "message": (
                    "the supplied payload digest does not match the frozen "
                    "authorized request"),
                "error_class": "payload_binding_mismatch",
                "evidence": [{
                    "kind": "request_binding",
                    "expected": canonical_digest,
                    "supplied": supplied_digest,
                }],
            }
    # A mutation is classified from its trusted registration metadata (plus
    # the legacy local list / an explicitly external step), never from a
    # business name or header.
    mutating = _registered_action_mutates(action, context)
    # Freeze a server-owned digest of the exact authorized request before the
    # handler runs. The handler receives a separate deep copy, so in-place
    # edits cannot change what the oracle compares against.
    server_request_sha256 = ""
    if mutating:
        try:
            server_request_sha256 = _approval_payload_hash(
                authorized_arguments)
        except Exception as exc:  # noqa: BLE001 - refuse before effect
            return {
                "status": "failed",
                "message": (
                    "the authorized request could not be frozen before "
                    f"dispatch: {type(exc).__name__}"),
                "error_class": "request_snapshot_unavailable",
                "effect": "none",
            }
    execution_context = {
        "workspace_id": context.get("workspace_id"),
        "user_id": context.get("employee_id"),
        "run_id": context.get("run_id"),
        "assignment_id": context.get("assignment_id"),
        "agent_id": context.get("agent_id"),
        "tenant_id": context.get("tenant_id"),
        # Propagate the caller's declared operating tier; registered handlers
        # such as mini_app_db_write enforce their own tier floor from it.
        "tier": context.get("tier"),
        "task_revision": (context.get("task_revision") or {}).get(
            "revision"),
        "operation_id": str(
            (context.get("step") or {}).get("operation_id")
            or context.get("operation_id") or ""),
    }
    failures = action.check_preconditions(execution_context)
    if failures:
        return {
            "status": "failed",
            "message": "one or more action preconditions are not satisfied",
            "error_class": "precondition_failed",
            "evidence": failures,
        }
    # Freeze the complete authorized presentation material BEFORE any
    # handler runs. Missing material is a pre-dispatch refusal, never an
    # applied presentation with a title/count fallback.
    expected_presentation_material = None
    expected_material_sha256 = ""
    if name in ("canvas.present_markdown", "canvas.present_chart"):
        from core.presentation_material import (
            material_sha256,
            presentation_material,
        )
        try:
            expected_presentation_material = presentation_material(
                name, authorized_arguments)
        except Exception as exc:  # noqa: BLE001 - refuse before effect
            return {
                "status": "failed",
                "message": (
                    "the authorized presentation material could not be "
                    f"normalized before dispatch: {type(exc).__name__}"),
                "error_class": "presentation_binding_unavailable",
            }
        if expected_presentation_material is None:
            return {
                "status": "failed",
                "message": (
                    "the canvas presentation has no complete authorized "
                    "material to verify; refusing before dispatch"),
                "error_class": "presentation_binding_unavailable",
            }
        material = expected_presentation_material or {}
        if material.get("kind") == "markdown" and not str(
                material.get("content") or "").strip():
            return {
                "status": "failed",
                "message": (
                    "the markdown presentation has no authorized content; "
                    "refusing before dispatch"),
                "error_class": "presentation_binding_unavailable",
            }
        if material.get("kind") == "chart" and (
                not str(material.get("chart_type") or "").strip()
                or not isinstance(material.get("data"), list)):
            return {
                "status": "failed",
                "message": (
                    "the chart presentation has no authorized type/data; "
                    "refusing before dispatch"),
                "error_class": "presentation_binding_unavailable",
            }
        expected_material_sha256 = material_sha256(
            expected_presentation_material)
        if not expected_material_sha256:
            return {
                "status": "failed",
                "message": (
                    "the canvas presentation has no complete authorized "
                    "material to verify; refusing before dispatch"),
                "error_class": "presentation_binding_unavailable",
            }
    try:
        result = await action_registry.execute_action(
            name, dispatch_arguments, execution_context)
    except ExternalOutcomeUnknown:
        # A provider action that may have applied must reconcile through the
        # shared operation record; it is never downgraded to a plain failure.
        raise
    except ExternalOutcomeNotApplied as exc:
        return {
            "status": "failed",
            "message": _bounded(str(exc), 500),
            "error_class": "proven_not_applied",
        }
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 — classify by effect possibility
        if mutating:
            # The handler was invoked; an ordinary runtime/parse error does
            # not prove the provider rejected the effect.
            raise ExternalOutcomeUnknown(
                f"registered action {name} raised {type(exc).__name__} "
                f"after dispatch; effect may have landed",
                evidence=_bounded(f"{type(exc).__name__}: {exc}", 500),
            ) from exc
        return {
            "status": "failed",
            "message": _bounded(str(exc), 500),
            "error_class": "action_dispatch_error",
        }

    try:
        safe = _json_safe(result, executable=True)
    except ExecutablePayloadTooLarge as exc:
        if mutating:
            remote = ""
            provider = operation = None
            if isinstance(result, dict):
                remote = str(
                    result.get("remote_id") or result.get("provider_ref")
                    or result.get("id") or "")
                provider = result.get("provider")
                operation = result.get("operation")
            return {
                "status": "uncertain",
                "action_result": "uncertain",
                "reason": (
                    f"registered action '{name}' returned an oversized "
                    f"executable result after dispatch: {exc}"),
                "evidence": _bounded(
                    "serialization refused after external dispatch"
                    + (f"; remote_id={remote}" if remote else ""), 500),
                "remote_id": remote,
                "provider": provider,
                "operation": operation,
                "provider_receipt": ({"remote_id": remote} if remote else {}),
            }
        return {
            "status": "failed",
            "error_class": "payload_too_large",
            "message": str(exc),
        }
    payload = safe if isinstance(safe, dict) else {"data": safe}
    read_receipt = payload.get("read_receipt") if isinstance(
        payload.get("read_receipt"), dict) else {}
    receipt_fields = read_receipt.get("fields") if isinstance(
        read_receipt.get("fields"), dict) else {}
    if not mutating and (
            receipt_fields.get("truncated") is True
            or str(read_receipt.get("coverage") or "").lower() in (
                "partial", "bounded", "truncated")):
        return {
            "status": "partial",
            "error_class": "partial_coverage",
            "message": (
                f"registered read action '{name}' returned partial coverage; "
                "full-population work is blocked until the complete source is "
                "available"),
            "data": safe,
            "evidence": [{"kind": "action_registry", "action": name,
                          "coverage": "partial"}],
        }
    outcome = _action_result_outcome(safe, mutating=mutating)
    oracle_verified = None
    oracle_evidence = ""
    oracle_failed_closed = False
    executor_operation_id = str(
        (context.get("step") or {}).get("operation_id")
        or context.get("operation_id") or "")
    # Freeze the proof expectations through the SAME builder the normal
    # Generic consumer uses.  The runtime identity is server-owned; the
    # authorized args are the only material source.
    from core.oracle.request_expectations import (
        build_request_expectations,
        strip_expected_fields,
    )

    oracle_expected = build_request_expectations(
        name,
        authorized_arguments,
        operation_id=executor_operation_id,
        tenant_id=str(context.get("tenant_id") or ""),
        workspace_id=str(context.get("workspace_id") or ""),
        actor_id=str(
            context.get("employee_id") or context.get("user_id")
            or authorized_arguments.get("user_id") or ""),
        agent_id=str(context.get("agent_id") or ""),
        request_sha256=server_request_sha256,
        binding=expected_binding,
    )
    # The pre-dispatch presentation freeze above is authoritative for this
    # adapter; keep its exact material/digest even when the shared builder
    # derives the same values.
    oracle_expected["_oracle_expected_material_sha256"] = (
        expected_material_sha256)
    oracle_expected["_oracle_expected_material"] = (
        expected_presentation_material)
    # Neither the caller's material nor a handler's return envelope may
    # inject an expectation key the server did not freeze.  Overlay the
    # trusted builder last.
    oracle_context = {
        **strip_expected_fields(authorized_arguments),
        **strip_expected_fields(payload),
        **oracle_expected,
    }
    oracle_db = context.get("db") or context.get("session")
    if oracle_db is not None:
        oracle_context.setdefault("db", oracle_db)
    try:
        from core.oracle import (
            get_postcondition,
            oracle_verifier_enabled,
            validate,
        )

        verifier = get_postcondition(name)
        if verifier is None:
            if mutating:
                # A declared mutation with no independent verifier can never
                # certify applied success. The effect may already have landed,
                # so it is uncertain (not "failed none") and is never resent.
                oracle_verified = False
                oracle_evidence = "no registered postcondition verifier"
                oracle_failed_closed = True
        elif not oracle_verifier_enabled():
            if mutating:
                oracle_verified = False
                oracle_evidence = "oracle verifier is disabled"
                oracle_failed_closed = True
        else:
            oracle = await validate(name, oracle_context)
            if oracle is None:
                oracle_verified = False
                oracle_evidence = "oracle returned no verdict"
                oracle_failed_closed = True
            else:
                oracle_verified = bool(oracle.verified)
                oracle_evidence = str(oracle.evidence or "")
                if not oracle_verified:
                    oracle_failed_closed = True
        # A mutating effect already dispatched without a usable verdict is
        # uncertain, never a proven success and never eligible for automatic
        # resend.
        if mutating and outcome == "applied" and oracle_failed_closed:
            outcome = "uncertain"
            payload = {
                **payload,
                "action_result": "uncertain",
                "verification": {
                    "status": "incomplete",
                    "missing_fields": ["oracle_verdict"],
                    "mismatches": ["oracle_postcondition"],
                },
            }
    except Exception as exc:  # noqa: BLE001 - oracle must not crash dispatch
        oracle_verified = False
        oracle_evidence = f"oracle unavailable: {type(exc).__name__}"
        if mutating and outcome == "applied":
            outcome = "uncertain"
            payload = {
                **payload,
                "action_result": "uncertain",
                "verification": {
                    "status": "incomplete",
                    "missing_fields": ["oracle_verdict"],
                    "mismatches": ["oracle_error"],
                },
            }
    # A local mutation may return only ``success: True`` (no self-reported
    # applied label). When the independent postcondition verifier confirms the
    # persisted effect, the oracle is authoritative and the envelope can be
    # applied. Without a verified verdict the conservative uncertain outcome
    # remains.
    if (oracle_verified is True and outcome == "uncertain"
            and payload.get("success") is True
            and not payload.get("error")
            and not payload.get("error_kind")):
        outcome = "applied"
        payload = {
            **payload,
            "action_result": "applied",
            "verification": {
                "status": "verified",
                "missing_fields": [],
                "mismatches": [],
            },
        }
    remote_id = str(
        payload.get("remote_id") or payload.get("provider_ref")
        or payload.get("id") or "")
    provider_ref = str(
        payload.get("provider_ref") or remote_id)
    identity = {
        "provider": payload.get("provider"),
        "operation": payload.get("operation"),
        "remote_id": remote_id,
        "provider_ref": provider_ref,
        "payload_sha256": payload.get("payload_sha256"),
        "provider_receipt": payload.get("provider_receipt"),
        "verification": payload.get("verification"),
    }
    if outcome == "applied":
        return {
            "status": "applied",
            "summary": f"registered action {name} completed",
            "data": safe,
            "evidence": [{"kind": "action_registry", "action": name}],
            "oracle_verified": oracle_verified,
            "oracle_evidence": oracle_evidence,
            **identity,
        }
    if outcome == "uncertain":
        return {
            "status": "uncertain",
            "action_result": "uncertain",
            "reason": (
                f"registered action {name} reported "
                f"{payload.get('action_result') or payload.get('status') or 'an unknown outcome'}"
                + (f"; oracle: {oracle_evidence}" if oracle_evidence else "")),
            "evidence": _bounded(str(result), 500),
            "data": safe,
            "conflicts": payload.get("conflicts") or [],
            "oracle_verified": oracle_verified,
            "oracle_evidence": oracle_evidence,
            **identity,
        }
    if outcome == "unavailable":
        return {
            "status": "unavailable",
            "message": (
                f"registered action {name} could not read the requested "
                "source"),
            "error_class": str(
                payload.get("error_kind") or "source_unavailable"),
            "evidence": _bounded(str(result), 500),
            "data": safe,
            **identity,
        }
    return {
        "status": "failed",
        "message": (
            f"registered action {name} did not apply: "
            f"{payload.get('error') or payload.get('status') or 'refused'}"),
        "error_class": str(
            payload.get("error_kind") or "proven_not_applied"),
        "data": _json_safe(result),
        **identity,
    }


_READ_ONLY_RESEARCH_ACTIONS = {
    "documents.search", "search_communications", "documents.ls",
    "documents.cat", "documents.read",
}


@register_assignment_adapter(
    "assignment.wait",
    description="Durably wait for one authorized external business fact",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "allow_standing_authorization": False})
async def _assignment_wait(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist a typed wait; an accepted reply becomes evidence.

    The compiler owns the correlation id and subject binding. This adapter
    never contacts a provider: it raises ``WaitingForExternal`` until the
    authorized reply arrives through the normal response route, then reports
    the received value as evidence for dependent work.
    """
    step = context.get("step") or {}
    response = step.get("external_response")
    if isinstance(response, dict) and response:
        fact = str(inputs.get("fact") or "").strip()
        value = response.get("value")
        confirmation = response.get("fact_confirmation") if isinstance(
            response.get("fact_confirmation"), dict) else {}
        confirmed_values = confirmation.get("values") or []
        if value in (None, "") and confirmed_values:
            value = confirmed_values[0]
        if value in (None, ""):
            value = response.get("response")
        return {
            "status": "applied",
            "summary": f"received {fact or 'the awaited fact'}",
            "value": value,
            "data": {
                "fact": fact,
                "subject": str(inputs.get("subject") or ""),
                "value": value,
            },
            "verification": {
                "status": "verified",
                "resource_id": str(response.get("source") or ""),
                "version": str(response.get("correlation_id") or ""),
            },
            "evidence": [{
                "kind": "external_response",
                "correlation_id": response.get("correlation_id"),
                "source": response.get("source"),
                "fact": fact,
                "subject": str(inputs.get("subject") or ""),
            }],
        }
    fact = str(inputs.get("fact") or "").strip()
    subject = str(inputs.get("subject") or "").strip()
    party = str(inputs.get("party") or "authorized source")
    detail = str(inputs.get("detail") or fact or "external fact")
    raise WaitingForExternal({
        "event": "external_fact",
        "state": "waiting_for_external",
        "party": party,
        "correlation_id": inputs.get("correlation_id"),
        "resume_on": "response",
        "detail": detail,
        "fact": fact,
        "subject": subject,
        "expected_answer_type": str(
            inputs.get("expected_answer_type") or ""),
        "blocks": str(inputs.get("blocks") or ""),
        "deadline": str(inputs.get("deadline") or ""),
        "validity": str(inputs.get("validity") or ""),
        # Only the compiler-owned await contract opts into strict subject,
        # source/channel and typed-answer binding. Legacy/controlled waits keep
        # their historical correlation-only matching.
        "typed_binding": True,
    })


@register_assignment_adapter(
    "external.research",
    description="Retrieve one missing fact through a bounded read-only action",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "allow_standing_authorization": False})
async def _external_research_adapter(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Bounded external-information retrieval through the shared registry.

    The action must be registered and read-only. Its result is validated
    before any downstream calculation or deliverable consumes it. A missing
    result becomes a typed ``external_research`` obligation; resolving that
    obligation supplies evidence, never teaching or authority.
    """
    from core.action_registry import action_registry

    name = str(inputs.get("action") or "").strip()
    arguments = inputs.get("arguments") or {}
    required_fields = [
        str(item).strip() for item in (inputs.get("required_fields") or [])
        if str(item).strip()
    ]
    if not name:
        raise NeedsContext({
            "concept": "external_research",
            "kind": "external_research",
            "question": "Which approved read-only source should be searched?",
            "reason": "the research step names no action",
            "resolver": "owner",
        })
    action = action_registry.get_action(name)
    if action is None:
        return {
            "status": "failed",
            "message": f"registered action '{name}' is not available",
            "error_class": "action_not_registered",
        }
    effects = [str((item or {}).get("effect") or "").lower()
               for item in (action.effects or [])]
    if any(effect not in ("", "read") for effect in effects):
        return {
            "status": "failed",
            "message": f"action '{name}' is not read-only; research cannot use it",
            "error_class": "research_action_not_read_only",
        }
    if not effects and name not in _READ_ONLY_RESEARCH_ACTIONS:
        return {
            "status": "failed",
            "message": f"action '{name}' is not in the read-only research allowlist",
            "error_class": "research_action_not_allowlisted",
        }
    if not required_fields:
        raise NeedsContext({
            "concept": "external_research",
            "kind": "external_research",
            "question": "Which fields must the retrieved evidence contain?",
            "reason": "the research step declares no required result fields",
            "resolver": "owner",
        })
    if not isinstance(arguments, dict):
        return {
            "status": "failed",
            "message": "research arguments must be a mapping",
            "error_class": "research_arguments_invalid",
        }
    dispatched = await _action_registry_adapter(
        {"action": name, "arguments": arguments}, context)
    if dispatched.get("status") != "applied":
        return dispatched
    data = dispatched.get("data")
    if not isinstance(data, dict):
        return {
            "status": "failed",
            "message": "research action returned no object",
            "error_class": "research_result_invalid",
        }
    missing = [
        field for field in required_fields
        if data.get(field) in (None, "", [], {})
    ]
    if missing:
        # A resolved obligation is evidence for this attempt. It never
        # rewrites teaching, permissions or the action result.
        gap_ids = set((context.get("step") or {}).get("gap_ids") or [])
        resolution = next((
            item for item in (context.get("resolved_gaps") or [])
            if item.get("question_id") in gap_ids
            and str(item.get("resolution") or "").strip()
        ), None)
        if resolution is not None:
            value = str(
                resolution.get("resolution_value")
                or resolution.get("resolution") or "").strip()
            return {
                "status": "applied",
                "summary": "missing information supplied as external evidence",
                "data": {
                    "value": value,
                    "source": "resolved_obligation",
                    "required_fields": required_fields,
                },
                "evidence": [{
                    "kind": "external_information",
                    "action": name,
                    "source": "resolved_obligation",
                    "value": _bounded(value, 2000),
                    "question_id": resolution.get("question_id"),
                    "resolved_by": resolution.get("resolved_by"),
                }],
                "provenance": {
                    "action": name,
                    "arguments": _json_safe(arguments),
                    "retrieved_at": _utc_now_iso(),
                    "required_fields": required_fields,
                },
            }
        raise NeedsContext({
            "concept": "external_research",
            "kind": "external_research",
            "question": str(inputs.get("question") or
                           "What is the missing information?"),
            "reason": (
                "the approved read-only source returned no usable evidence "
                f"for {', '.join(required_fields)}"),
            "resolver": str(inputs.get("resolver") or "owner"),
            "checked_evidence": [dispatched.get("evidence") or []],
            "next_retrieval": f"{name} with the approved arguments",
            "inputs": {
                "action": name,
                "arguments": _json_safe(arguments),
                "required_fields": required_fields,
                "purpose": str(inputs.get("purpose") or ""),
            },
        })
    return {
        "status": "applied",
        "summary": f"retrieved {', '.join(required_fields)} from {name}",
        "data": _json_safe(data),
        "evidence": [{
            "kind": "external_information",
            "action": name,
            "source": str(data.get("source") or name),
            "required_fields": required_fields,
            "retrieved_at": _utc_now_iso(),
        }],
        "provenance": {
            "action": name,
            "arguments": _json_safe(arguments),
            "retrieved_at": _utc_now_iso(),
            "required_fields": required_fields,
        },
    }


def _established_source_unit(
    records: Sequence[Dict[str, Any]],
) -> Tuple[str, str]:
    """Return the single unit the SOURCE establishes, and its column.

    Only unit/currency-named columns count. Numeric values are quantities
    (for example a ``Units`` count), not unit labels, so they never establish
    a unit. The first unit-like column with values is authoritative: mixed
    values there mean no single unit is established, and the confirmation
    must ask rather than fall through to another column.
    """
    for column in ("Currency", "Unit", "Units", "UOM"):
        values = set()
        for record in records:
            raw = str(record.get(column) or "").strip()
            if not raw:
                continue
            try:
                float(raw.replace(",", ""))
                continue
            except ValueError:
                pass
            values.add(raw.upper()[:40])
        if not values:
            continue
        if len(values) == 1:
            return next(iter(values)), column
        return "", column
    return "", ""


def resolution_matches(
    stored: Any,
    incoming: Any,
    stored_value: Any = None,
) -> bool:
    """Whether a replay is EXACTLY the same structured resolution.

    ``resolve_gap`` stores the caller's answer in ``resolution_value`` and a
    bounded human audit string (with ``[by ...]`` / ``[evidence: ...]``) in
    ``resolution``. Identity is the structured value, never a prefix of the
    audit text: a stored ``"price 100 [subject to approval]"`` must not match an
    incoming ``"price 100"``. Legacy records without ``resolution_value`` fail
    closed to byte equality; a truncated audit string never invents identity.
    """
    incoming_text = str(incoming or "")
    if not incoming_text:
        return False
    if stored_value is not None:
        return str(stored_value) == incoming_text
    return str(stored or "") == incoming_text


def select_confirmed_mapping(
    mappings: Sequence[Dict[str, Any]],
    *,
    concept: str,
    sheet: str = "",
    source_version: str = "",
) -> Tuple[Optional[Tuple[int, Dict[str, Any]]], str]:
    """Identify ONE confirmed mapping by concept and, when supplied, source.

    A concept alone is not an identity: the same concept can be confirmed on
    two sheets or two source versions in one assignment. Returning the first
    match would silently rewrite an unrelated mapping, so an underspecified
    match is refused as ambiguous instead.
    """
    wanted_concept = str(concept or "").strip().lower()
    matches: List[Tuple[int, Dict[str, Any]]] = []
    for index, item in enumerate(mappings):
        if not isinstance(item, dict):
            continue
        if str(item.get("concept") or "").strip().lower() != wanted_concept:
            continue
        if sheet and str(item.get("sheet") or "") != str(sheet):
            continue
        if source_version and str(
                item.get("source_version") or "") != str(source_version):
            continue
        matches.append((index, dict(item)))
    if not matches:
        return None, "missing"
    if len(matches) > 1:
        return None, "ambiguous"
    return matches[0], ""


def _mapping_affected_roots(
    assignment: Dict[str, Any], *, column: str, concept: str,
) -> List[str]:
    """Steps that consume the corrected column (or its concept)."""
    token = str(column or "").strip().lower()
    concept_token = str(concept or "").strip().lower()
    roots: List[str] = []
    for step in assignment.get("steps") or []:
        inputs = step.get("inputs") or {}
        if token and _value_mentions(inputs, token):
            roots.append(step["step_id"])
            continue
        if concept_token and _value_mentions(inputs, concept_token):
            roots.append(step["step_id"])
    if roots:
        return roots
    # Confirmed mappings are substituted into step inputs, so the old column
    # may survive only in the aggregate result itself.
    for step in assignment.get("steps") or []:
        result = step.get("result") or {}
        if str(result.get("measure") or "").strip().lower() == token:
            roots.append(step["step_id"])
    return roots


def _value_mentions(value: Any, token: str) -> bool:
    if isinstance(value, str):
        return bool(token) and value.strip().lower() == token
    if isinstance(value, list):
        return any(_value_mentions(item, token) for item in value)
    if isinstance(value, dict):
        return any(_value_mentions(item, token) for item in value.values())
    return False


def _source_unit_from_path(path: str) -> Tuple[str, str]:
    """Re-read the current authorized source before validating a correction."""
    import pandas as pd

    frame = pd.read_parquet(path)
    records = [
        {str(key): value for key, value in row.items()}
        for row in frame.head(50).to_dict(orient="records")
    ]
    return _established_source_unit(records)


def _corrected_artifact_path(path: str, plan_revision: int) -> str:
    """A sibling path for the recomputed artifact.

    The prior artifact is never overwritten; its path/hash stay in the
    invalidated step and deliverable history.
    """
    original = Path(path)
    candidate = original.with_name(
        f"{original.stem}-corr-{plan_revision}{original.suffix}")
    if candidate.exists():
        candidate = original.with_name(
            f"{original.stem}-corr-{plan_revision}-"
            f"{uuid.uuid4().hex[:8]}{original.suffix}")
    return str(candidate)


def _mapping_proposal(
    *,
    binding: Dict[str, Any],
    missing: str,
    columns: Sequence[str],
    records: Sequence[Dict[str, Any]],
    teaching: Dict[str, Any],
) -> Dict[str, Any]:
    """Schema candidates for a missing concept. Candidates are proposals only."""
    mappings = [
        dict(item) for item in (teaching.get("field_mappings") or [])
        if isinstance(item, dict)
    ]
    source_mapping = next((
        item for item in mappings
        if str(item.get("concept") or "").strip().lower()
        == str(missing or "").strip().lower()
    ), None)
    concept = str((source_mapping or {}).get("concept") or missing or "").strip()
    candidate_columns = [
        str(column) for column in columns
        if str(column).strip() and str(column) != "__sheet_row"
    ][:24]
    candidates = []
    for column in candidate_columns:
        samples = []
        for record in records:
            value = record.get(column)
            if value is None or str(value).strip() == "":
                continue
            samples.append(str(value)[:80])
            if len(samples) >= 3:
                break
        numeric = 0
        for sample in samples:
            try:
                float(str(sample).replace(",", ""))
                numeric += 1
            except ValueError:
                pass
        candidates.append({
            "column": column,
            "sample_values": samples,
            "inferred_type": "number" if samples and numeric == len(samples)
            else "text",
        })
    source_unit, source_unit_column = _established_source_unit(records)
    return {
        "concept": concept,
        "required_unit": str((source_mapping or {}).get("unit") or ""),
        "source_unit": source_unit,
        "source_unit_column": source_unit_column,
        "missing_column": str(missing or ""),
        "source": str(binding.get("source") or ""),
        "external_id": str(binding.get("external_id") or ""),
        "dataset_name": str(binding.get("dataset_name") or ""),
        "resource_id": str(binding.get("resource_id") or ""),
        "sheet": str(binding.get("sheet") or ""),
        "source_version": str(binding.get("source_version") or ""),
        "teaching_revision": str(teaching.get("revision") or ""),
        "mapping_source": source_mapping,
        "candidates": candidates,
    }


def _replace_mapping_value(value: Any, old: str, new: str) -> Any:
    """Replace an exact physical column/concept string in plan inputs."""
    if isinstance(value, str):
        return new if value.strip() == str(old).strip() else value
    if isinstance(value, list):
        return [_replace_mapping_value(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _replace_mapping_value(item, old, new)
                for key, item in value.items()}
    return value


@register_assignment_adapter(
    "dataset.read", description="Read rows from a materialized Parquet dataset",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "requires_resource": True})
async def _dataset_read(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    binding = dict(inputs.get("resource_binding") or {})
    resolved = await asyncio.to_thread(_recheck_binding, binding, context)
    path = str(resolved.get("path") or "").strip()
    if not path or not os.path.isfile(path):
        raise NeedsContext({
            "concept": "dataset_resource",
            "reason": "the materialized dataset is not available",
            "question": "The authorized dataset copy is unavailable.",
            "next_retrieval": "refresh the connected source, then retry",
            "kind": "missing_evidence",
            "waiting": {
                "state": "source_unavailable",
                "party": "source owner",
                "resume_on": "resource_restored",
                "since": _utc_now_iso(),
                "detail": path,
            },
        })
    import pandas as pd

    try:
        frame = await asyncio.to_thread(pd.read_parquet, path)
    except Exception as exc:  # noqa: BLE001 — corrupt copy is a refusal
        raise NeedsContext({
            "concept": "dataset_resource",
            "reason": f"the materialized copy could not be read: {type(exc).__name__}",
            "question": "The authorized dataset copy is unreadable.",
            "next_retrieval": "rematerialize the source, then retry",
            "kind": "missing_evidence",
        })
    physical = [str(column) for column in frame.columns]
    if "__sheet_row" not in physical:
        raise NeedsContext({
            "concept": "row_provenance",
            "reason": (
                "the materialized frame has no __sheet_row; positional row "
                "numbers are forbidden because they cite the wrong cell"),
            "question": "Which original sheet rows should the result cite?",
            "checked_evidence": [f"columns={physical[:40]}"],
            "kind": "missing_evidence",
        })
    wanted = [str(column).strip() for column in inputs.get("columns") or []
              if str(column).strip()]
    missing = [column for column in wanted if column not in physical]
    if missing:
        proposal = _mapping_proposal(
            binding=binding,
            missing=missing[0],
            columns=physical,
            records=[
                {str(key): value for key, value in row.items()}
                for row in frame.head(20).to_dict(orient="records")
            ],
            teaching=context.get("teaching") or {},
        )
        raise NeedsContext({
            "concept": "column",
            "reason": f"required column(s) not found: {missing}",
            "question": "Which column should supply " + ", ".join(missing) + "?",
            "checked_evidence": [f"columns={physical[:40]}"],
            "next_retrieval": "read the materialized schema and confirm the mapping",
            "kind": "missing_evidence",
            "inputs": {"mapping": proposal},
        })
    records = [
        {str(key): value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    records = _filter_records(records, inputs.get("filters") or [])
    for record in records:
        row_number = _sheet_row(record.get("__sheet_row"))
        if row_number is None:
            raise NeedsContext({
                "concept": "row_provenance",
                "reason": (
                    "a selected row has no usable original sheet-row number; "
                    "no positional fallback is used"),
                "question": "Which original sheet rows should be cited?",
                "kind": "missing_evidence",
            })
        record["__sheet_row"] = row_number
    records.sort(key=lambda item: int(item["__sheet_row"]))
    matched = len(records)
    limit = max(1, min(int(inputs.get("max_rows") or 500), 5000))
    rows = records[:limit]
    if wanted:
        projection = list(dict.fromkeys(wanted + ["__sheet_row"]))
        rows = [{column: row.get(column) for column in projection}
                for row in rows]
    from core.sheet_dataset_service import load_formulas_for_parquet

    row_numbers = {int(row["__sheet_row"]) for row in rows}
    formulas = _formula_rows(
        load_formulas_for_parquet(path), row_numbers)
    source = _connected_source_block(resolved, binding)
    source_label = _source_label(source)
    truncated = matched > limit
    coverage = dict(source.get("coverage") or {})
    expected_count = coverage.get(
        "source_row_count", coverage.get("expected_count"))
    coverage.update({
        "complete": not truncated,
        "known": True,
        "truncated": truncated,
        "expected_count": expected_count if expected_count is not None else matched,
        "observed_count": matched,
    })
    resource_id = str(source.get("resource_id") or "")
    version = str(source.get("source_version") or "")
    return {
        "status": "applied",
        "summary": (
            f"read {len(rows)} of {matched} matching row(s) from "
            f"{source_label}"),
        "rows": _json_safe(rows),
        "schema": [{"column": column} for column in physical if column],
        "formulas": formulas,
        "matched_count": matched,
        "truncated": truncated,
        "source_version": source["source_version"],
        "resource_id": resource_id,
        "coverage": coverage,
        "verification": {
            "status": "verified",
            "resource_id": resource_id,
            "version": version,
            "coverage": coverage,
        },
        "source": source,
        "source_label": source_label,
        "evidence": [{
            "kind": "connected_dataset",
            **source,
            "path": path,
            "sheet_rows": sorted(row_numbers)[:2000],
            "row_count": len(rows),
        }],
    }


@register_assignment_adapter(
    "dataset.aggregate",
    description="Aggregate rows from a materialized Parquet dataset",
    metadata={"effect": "local",
              "required_actions": ["retrieve", "calculate"],
              "requires_resource": True,
              "allow_standing_authorization": False})
async def _dataset_aggregate(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    binding = dict(inputs.get("resource_binding") or {})
    resolved = await asyncio.to_thread(_recheck_binding, binding, context)
    path = str(resolved.get("path") or "").strip()
    if not path or not os.path.isfile(path):
        raise NeedsContext({
            "concept": "dataset_resource",
            "reason": "the materialized dataset is not available",
            "question": "The authorized dataset copy is unavailable.",
            "kind": "missing_evidence",
        })
    import pandas as pd

    from core.dataset_aggregation import (
        _infer_roles,
        _numeric_measure_candidates,
        aggregate_selected_rows,
    )

    frame = await asyncio.to_thread(pd.read_parquet, path)
    columns = [str(column) for column in frame.columns]
    if "__sheet_row" not in columns:
        raise NeedsContext({
            "concept": "row_provenance",
            "reason": "the materialized frame has no original sheet-row column",
            "question": "Which original sheet rows should the result cite?",
            "kind": "missing_evidence",
        })
    records = [
        {str(key): value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    records = _filter_records(records, inputs.get("filters") or [])
    for record in records:
        row_number = _sheet_row(record.get("__sheet_row"))
        if row_number is None:
            raise NeedsContext({
                "concept": "row_provenance",
                "reason": "a selected row has no usable original sheet-row number",
                "question": "Which original sheet rows should be cited?",
                "kind": "missing_evidence",
            })
        record["__sheet_row"] = row_number
    operation = str(inputs.get("operation") or "sum").strip().lower()
    if operation not in ("sum", "count"):
        raise NeedsContext({
            "concept": "calculation_method",
            "reason": f"unsupported aggregate operation '{operation}'",
            "question": "Which calculation should the source supply?",
            "kind": "business_decision",
        })
    value_column = str(inputs.get("value_column") or "").strip()
    if operation == "sum" and not value_column:
        candidates = _numeric_measure_candidates(frame, columns)
        if len(candidates) == 1:
            value_column = candidates[0]
        else:
            raise NeedsContext({
                "concept": "value_column",
                "reason": "no single numeric measure was named",
                "question": "Which column should be summed?",
                "checked_evidence": [
                    f"numeric_columns={candidates[:20]}"],
                "kind": "missing_evidence",
            })
    if operation == "sum" and value_column not in columns:
        proposal = _mapping_proposal(
            binding=binding,
            missing=value_column,
            columns=columns,
            records=records,
            teaching=context.get("teaching") or {},
        )
        raise NeedsContext({
            "concept": "value_column",
            "reason": f"the named measure '{value_column}' is not in the frame",
            "question": "Which column should be summed?",
            "checked_evidence": [f"columns={columns[:40]}"],
            "next_retrieval": (
                "select the matching column from the current schema and confirm"),
            "kind": "missing_evidence",
            "inputs": {"mapping": proposal},
        })
    roles = _infer_roles({"value_column": value_column}, columns)
    source = _connected_source_block(resolved, binding)
    source_label = _source_label(source)
    coverage = dict(source.get("coverage") or {})
    result = await asyncio.to_thread(
        aggregate_selected_rows,
        records,
        columns,
        roles,
        sheet=str(source.get("sheet") or ""),
        file_name=str(source.get("file_name") or ""),
        version=str(source.get("source_version") or ""),
        source_row_count=coverage.get("source_row_count"),
        coverage=coverage,
        operation=operation,
        value_column=value_column,
    )
    status = str(result.get("status") or "")
    if status != "complete":
        gaps = result.get("gaps") or []
        raise NeedsContext({
            "concept": "calculation_input",
            "reason": str(result.get("answer") or result.get("block")
                          or "the aggregate could not be certified"),
            "question": (
                "The source rows cannot certify this calculation yet. Which "
                "rows or values should be corrected?"),
            "affected_subjects": [
                f"row {item.get('row')} missing {item.get('missing')}"
                for item in gaps[:20]
            ],
            "checked_evidence": [
                f"operation={operation}", f"measure={value_column or 'rows'}",
                f"selected_rows={len(records)}",
            ],
            "kind": "missing_evidence",
        })
    subtotals = dict(result.get("subtotals") or {})
    if operation == "sum" and not records:
        raise NeedsContext({
            "concept": "records",
            "reason": (
                "the accepted filters selected no eligible source rows, so "
                "the requested sum has no evidence"),
            "question": (
                "Which eligible rows should the calculation cover? The bound "
                "source has no rows matching the accepted scope."),
            "checked_evidence": [
                f"operation={operation}", f"measure={value_column or 'rows'}",
                "selected_rows=0",
                f"source_rows={coverage.get('source_row_count')}",
            ],
            "kind": "missing_evidence",
        })
    values = [
        {
            "currency": currency,
            "value": item.get("value"),
            "rows": item.get("rows"),
        }
        for currency, item in subtotals.items()
    ]
    if operation == "count":
        value = str(sum(int(item.get("rows") or 0)
                        for item in subtotals.values()))
        unit = "rows"
    elif len(values) == 1:
        unit = values[0]["currency"]
        value = str(values[0]["value"])
        unit = "" if unit == "(unstated)" else unit
    else:
        value = None
        unit = ""
    row_numbers = sorted({
        int(row.get("row")) for row in result.get("rows") or []
        if _sheet_row(row.get("row")) is not None
    })
    from core.sheet_dataset_service import load_formulas_for_parquet

    formulas = _formula_rows(
        load_formulas_for_parquet(path), set(row_numbers))
    measure = value_column or "rows"
    summary = (
        f"{operation} of {measure} = {value} {unit} across "
        f"{len(records)} row(s) from {source_label}".strip()
        if value is not None else
        f"{operation} of {measure} across {len(records)} row(s) from "
        f"{source_label} (per-currency subtotals)")
    return {
        "status": "applied",
        "summary": summary,
        "operation": operation,
        "measure": measure,
        "group_by": str(roles.get("currency_column") or ""),
        "value": value,
        "unit": unit,
        "values": values,
        "rows": _json_safe((result.get("rows") or [])[:500]),
        "subtotals": _json_safe(subtotals),
        "formulas": formulas,
        "selected_count": len(records),
        "source_version": source["source_version"],
        "source": source,
        "source_label": source_label,
        "evidence": [{
            "kind": "connected_aggregate",
            **source,
            "path": path,
            "operation": operation,
            "measure": measure,
            "subtotals": _json_safe(subtotals),
            "sheet_rows": row_numbers[:2000],
            "selected_count": len(records),
        }],
    }


@register_assignment_adapter(
    "workbook.read", description="Read workbook rows",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "requires_resource": True})
async def _workbook_read(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    path = str(inputs.get("path") or "").strip()
    if not path:
        raise NeedsContext({
            "concept": "workbook_path",
            "reason": "the assignment did not name a workbook resource",
            "question": "Which authorized workbook should I read?",
            "next_retrieval": "resolve the source resource and retry",
            "kind": "missing_evidence",
        })
    if not os.path.isfile(path):
        raise NeedsContext({
            "concept": "workbook_resource",
            "reason": "the named resource is not currently available",
            "question": "The workbook resource is unavailable.",
            "next_retrieval": "reconnect or restore the source, then retry",
            "kind": "missing_evidence",
            "waiting": {
                "state": "source_unavailable",
                "party": "source owner",
                "resume_on": "resource_restored",
                "since": _utc_now_iso(),
                "detail": path,
            },
        })
    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheet_name = str(inputs.get("sheet") or "").strip()
    try:
        sheet = workbook[sheet_name] if sheet_name else workbook[
            workbook.sheetnames[0]]
    except KeyError:
        raise NeedsContext({
            "concept": "worksheet",
            "reason": f"sheet '{sheet_name}' does not exist in the workbook",
            "question": f"Which worksheet contains the records? "
                        f"Available: {', '.join(workbook.sheetnames[:20])}",
            "checked_evidence": [f"sheets={workbook.sheetnames[:20]}"],
            "kind": "missing_evidence",
        })
    header_row = max(1, int(inputs.get("header_row") or 1))
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) < header_row:
        raise NeedsContext({
            "concept": "records",
            "reason": "the worksheet has no header/data rows",
            "question": "The worksheet contains no records to work from.",
            "kind": "missing_evidence",
        })
    header = [str(cell).strip() if cell is not None else ""
              for cell in rows[header_row - 1]]
    wanted = [str(item).strip() for item in inputs.get("columns") or []
              if str(item).strip()]
    missing = [column for column in wanted if column not in header]
    if missing:
        raise NeedsContext({
            "concept": "column",
            "reason": f"required column(s) not found: {missing}",
            "question": (
                "Which column should supply "
                + ", ".join(missing) + "?"),
            "checked_evidence": [f"columns={header[:40]}"],
            "next_retrieval": "read the schema and confirm the mapping",
            "kind": "missing_evidence",
        })
    records: List[Dict[str, Any]] = []
    for values in rows[header_row:]:
        record = {
            header[index]: value
            for index, value in enumerate(values)
            if index < len(header) and header[index]
        }
        if any(value not in (None, "") for value in record.values()):
            records.append(record)
    filters = inputs.get("filters") or []
    for predicate in filters:
        if not isinstance(predicate, dict):
            continue
        field = str(predicate.get("column") or "")
        operator = str(predicate.get("operator") or "eq")
        expected = predicate.get("value")

        def _matches(actual: Any) -> bool:
            if operator == "eq":
                return str(actual) == str(expected)
            if operator == "neq":
                return str(actual) != str(expected)
            if operator == "contains":
                return str(expected).lower() in str(actual).lower()
            if operator == "in":
                return actual in (expected or [])
            try:
                left = float(actual)
                right = float(expected)
            except (TypeError, ValueError):
                return False
            if operator == "gt":
                return left > right
            if operator == "gte":
                return left >= right
            if operator == "lt":
                return left < right
            if operator == "lte":
                return left <= right
            return False

        records = [record for record in records
                   if _matches(record.get(field))]
    limit = max(1, min(int(inputs.get("max_rows") or 500), 5000))
    content_hash = _sha256_file(path)
    truncated = len(records) > limit
    binding = next((
        inputs.get(key) for key in (
            "resource_binding", "source_binding", "binding", "source")
        if isinstance(inputs.get(key), dict)), {})
    resource_id = str(
        inputs.get("resource_id") or inputs.get("source_id")
        or binding.get("resource_id") or binding.get("source_id")
        or binding.get("id") or f"file:{path}")
    source_version = str(
        inputs.get("source_version") or inputs.get("version")
        or binding.get("source_version") or binding.get("version")
        or content_hash)
    version = source_version
    coverage = {"complete": not truncated, "known": True,
                "truncated": truncated}
    return {
        "status": "applied",
        "summary": (
            f"read {min(len(records), limit)} of {len(records)} matching "
            f"record(s) from {sheet.title}"),
        "rows": _json_safe(records[:limit]),
        "schema": [{"column": column} for column in header if column],
        "matched_count": len(records),
        "truncated": truncated,
        "source_version": source_version,
        "sha256": content_hash,
        "resource_id": resource_id,
        "coverage": coverage,
        "verification": {
            "status": "verified",
            "resource_id": resource_id,
            "version": version,
            "coverage": coverage,
        },
        "evidence": [{
            "kind": "workbook",
            "path": path,
            "sheet": sheet.title,
            "content_hash": content_hash,
        }],
    }


@register_assignment_adapter(
    "document.read", description="Read a document",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "requires_resource": True})
async def _document_read(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    path = str(inputs.get("path") or "").strip()
    if not path or not os.path.isfile(path):
        raise NeedsContext({
            "concept": "document_resource",
            "reason": "the named document is not available",
            "question": "The document resource is unavailable.",
            "next_retrieval": "reconnect or restore the source, then retry",
            "kind": "missing_evidence",
            "waiting": {
                "state": "source_unavailable",
                "party": "source owner",
                "resume_on": "resource_restored",
                "since": _utc_now_iso(),
                "detail": path,
            },
        })
    suffix = Path(path).suffix.lower()
    text = ""
    structured = None
    if suffix == ".docx":
        import docx

        document = docx.Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(part for part in parts if part.strip())
    else:
        text = Path(path).read_text(errors="replace")
        if suffix == ".json":
            try:
                payload = json.loads(text)
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                structured = payload
                text = json.dumps(payload, indent=2, sort_keys=True)
    content_hash = _sha256_file(path)
    truncated = len(text) > 20000
    data = None
    if suffix == ".json":
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            data = _json_safe(parsed)
    binding = next((
        inputs.get(key) for key in (
            "resource_binding", "source_binding", "binding", "source")
        if isinstance(inputs.get(key), dict)), {})
    resource_id = str(
        inputs.get("resource_id") or inputs.get("source_id")
        or binding.get("resource_id") or binding.get("source_id")
        or binding.get("id") or f"file:{path}")
    source_version = str(
        inputs.get("source_version") or inputs.get("version")
        or binding.get("source_version") or binding.get("version")
        or content_hash)
    version = source_version
    coverage = {"complete": not truncated, "known": True,
                "truncated": truncated}
    result = {
        "status": "applied",
        "summary": (
            f"read structured {Path(path).name}"
            if structured is not None
            else f"read {len(text)} characters from {Path(path).name}"),
        "text": text[:20000],
        "truncated": truncated,
        "source_version": source_version,
        "sha256": content_hash,
        "resource_id": resource_id,
        "coverage": coverage,
        "data": data or {},
        "schema": [
            {"column": str(key)} for key in (data or {})
        ],
        "verification": {
            "status": "verified",
            "resource_id": resource_id,
            "version": version,
            "coverage": coverage,
        },
        "evidence": [{
            "kind": "document",
            "path": path,
            "content_hash": content_hash,
        }],
    }
    if structured is not None:
        result["data"] = structured
    return result


@register_assignment_adapter(
    "document.text", description="Read an uploaded document's extracted text",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "requires_resource": True})
async def _document_text_read(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    binding = inputs.get("resource_binding") if isinstance(
        inputs.get("resource_binding"), dict) else {}
    document_id = str(
        binding.get("resource_id") or inputs.get("document_id") or "").strip()
    path = str(inputs.get("path") or binding.get("path") or "").strip()
    if path and os.path.isfile(path):
        result = await _document_read(inputs, context)
        text = str(result.get("text") or "")
        if text.strip().startswith("{"):
            try:
                payload = json.loads(text)
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                result["data"] = payload
        return result
    if not document_id:
        raise NeedsContext({
            "concept": "document_identity",
            "reason": "the assignment did not name an uploaded document",
            "question": "Which authorized document should I read?",
            "next_retrieval": "resolve the uploaded document and retry",
            "kind": "missing_evidence",
        })
    workspace_id = context.get("workspace_id") or "default"
    document = None
    try:
        from core.lancedb_handler import get_lancedb_handler

        for candidate_workspace in (workspace_id, "default_shared"):
            handler = get_lancedb_handler(candidate_workspace)
            document = await asyncio.to_thread(
                handler.get_document_by_id, "documents", document_id)
            if document:
                break
    except Exception as exc:  # noqa: BLE001 - durable evidence unavailable
        raise NeedsContext({
            "concept": "document_resource",
            "reason": f"the uploaded document could not be read: {exc}",
            "question": "The uploaded document is unavailable.",
            "next_retrieval": "reconnect the document store and retry",
            "kind": "missing_evidence",
        }) from exc
    if not document:
        raise NeedsContext({
            "concept": "document_resource",
            "reason": "the uploaded document is not in this workspace",
            "question": "The uploaded document is unavailable.",
            "next_retrieval": "re-upload or select the document again",
            "kind": "missing_evidence",
        })
    text = str(document.get("text") or "")
    if not text.strip():
        raise NeedsContext({
            "concept": "document_text",
            "reason": "the uploaded document has no extracted text",
            "question": "The document contains no readable text.",
            "next_retrieval": "supply a readable document",
            "kind": "missing_evidence",
        })
    data = None
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            data = payload
    from core.database import get_db_session
    from core.models import IngestedDocument

    metadata = document.get("metadata") if isinstance(
        document.get("metadata"), dict) else {}
    indexed_version = str(
        metadata.get("source_content_hash")
        or metadata.get("content_hash")
        or metadata.get("version") or "").strip()
    if not indexed_version:
        raise NeedsContext({
            "concept": "document_extraction_version",
            "reason": (
                "the indexed extraction does not prove which source version "
                "produced it"),
            "question": (
                "Which current source version should be read for this "
                "document?"),
            "next_retrieval": "re-index the authorized document and retry",
            "kind": "missing_evidence",
        })
    indexed_document_id = str(metadata.get("pg_document_id") or "").strip()
    if indexed_document_id and indexed_document_id != document_id:
        raise NeedsContext({
            "concept": "document_identity",
            "reason": "the indexed extraction belongs to a different document",
            "question": "Which authorized document should be read?",
            "next_retrieval": "re-index the document and retry",
            "kind": "missing_evidence",
        })
    try:
        with get_db_session() as db:
            row = db.query(IngestedDocument).filter(
                IngestedDocument.id == document_id).first()
    except Exception as exc:  # noqa: BLE001 - unverifiable authority
        raise NeedsContext({
            "concept": "document_authority",
            "reason": f"the authoritative document record is unavailable: {exc}",
            "question": "The document authority is unavailable.",
            "next_retrieval": "restore the document store and retry",
            "kind": "missing_evidence",
        }) from exc
    if row is None:
        raise NeedsContext({
            "concept": "document_authority",
            "reason": "the authoritative document record is missing",
            "question": "The document authority is unavailable.",
            "next_retrieval": "re-upload or re-index the document",
            "kind": "missing_evidence",
        })
    authoritative_version = str(row.source_content_hash or "").strip()
    if not authoritative_version:
        raise NeedsContext({
            "concept": "document_authority",
            "reason": "the authoritative document has no source version",
            "question": "Which current document version should be read?",
            "next_retrieval": "re-index the document and retry",
            "kind": "missing_evidence",
        })
    expected_version = str(
        binding.get("source_version") or inputs.get("source_version")
        or "").strip()
    from core.doc_freshness_service import (
        ExtractionIdentityError, current_extraction_revision,
    )

    try:
        source_version = current_extraction_revision(
            indexed_version, authoritative_version, expected_version or None)
    except ExtractionIdentityError as exc:
        raise NeedsContext({
            "concept": "document_extraction_stale",
            "reason": str(exc),
            "question": "The cached document text is stale; re-index it now?",
            "next_retrieval": "re-extract the current authorized document",
            "kind": "missing_evidence",
        }) from exc
    expected_workspace = str(
        binding.get("workspace_id") or context.get("workspace_id") or "")
    expected_tenant = str(
        binding.get("tenant_id") or context.get("tenant_id") or "")
    row_workspace = str(getattr(row, "workspace_id", "") or "")
    row_tenant = str(getattr(row, "tenant_id", "") or "")
    if expected_workspace and row_workspace and (
            row_workspace != expected_workspace):
        raise NeedsContext({
            "concept": "document_scope",
            "reason": "the document belongs to another workspace",
            "question": "Which authorized document should be read?",
            "next_retrieval": "select a document in this workspace",
            "kind": "missing_evidence",
        })
    if expected_tenant and row_tenant and row_tenant != expected_tenant:
        raise NeedsContext({
            "concept": "document_scope",
            "reason": "the document belongs to another tenant",
            "question": "Which authorized document should be read?",
            "next_retrieval": "select a document in this tenant",
            "kind": "missing_evidence",
        })
    freshness = str(
        getattr(row, "freshness_status", "fresh") or "fresh").lower()
    if freshness not in ("fresh", "current", "active"):
        raise NeedsContext({
            "concept": "document_freshness",
            "reason": f"the authoritative document is {freshness}",
            "question": "Should the stale document be refreshed before use?",
            "next_retrieval": "refresh the authorized source and retry",
            "kind": "missing_evidence",
        })
    truncated = len(text) > 20000
    coverage = {"complete": not truncated, "known": True,
                "truncated": truncated}
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # ``indexed_version`` may carry an extraction-format prefix (ev3:/ev4:);
    # the source version consumed by readiness is the normalized authoritative
    # source hash. The raw indexed label stays in the extraction lineage.
    result = {
        "status": "applied",
        "summary": f"read extracted text from {document.get('source') or document_id}",
        "text": text[:20000],
        "truncated": truncated,
        "source_version": source_version,
        "resource_id": document_id,
        "coverage": coverage,
        "extraction": {
            "indexed_version": indexed_version,
            "source_version": source_version,
            "authoritative_version": authoritative_version,
            "extractor_version": (
                "opaque" if not str(source_version).startswith("ev")
                else str(source_version).split(":", 1)[0]),
            "text_sha256": text_hash,
            "source": document.get("source"),
        },
        "verification": {
            "status": "verified",
            "resource_id": document_id,
            "version": source_version,
            "coverage": coverage,
        },
        "evidence": [{
            "kind": "document_extraction",
            "resource_id": document_id,
            "version": source_version,
            "text_sha256": text_hash,
        }],
    }
    if data is not None:
        result["data"] = data
    return result


@register_assignment_adapter(
    "formula.calculate", description="Evaluate a deterministic expression",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "allow_standing_authorization": False})
async def _formula_calculate(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.formula_engine import evaluate_expression

    expression = str(inputs.get("expression") or "").strip()
    if not expression:
        raise NeedsContext({
            "concept": "calculation_method",
            "reason": "no explicit calculation expression was supplied",
            "question": "Which calculation method should I use?",
            "kind": "business_decision",
            "resolver": "method owner",
        })
    bindings = inputs.get("bindings") or {}
    if not isinstance(bindings, dict):
        raise NeedsContext({
            "concept": "calculation_inputs",
            "reason": "calculation bindings must be a mapping",
            "question": "Which values should the calculation use?",
            "kind": "missing_evidence",
        })
    result = evaluate_expression(
        expression, bindings,
        units=inputs.get("units") if isinstance(inputs.get("units"), dict)
        else None,
        output_unit=str(inputs.get("output_unit") or ""),
        origin={str(k): str(v) for k, v in (
            inputs.get("origin") or {}).items()},
    )
    if result.status != "computed":
        detail = result.missing or result.unsupported or result.status
        raise NeedsContext({
            "concept": "calculation_input",
            "reason": detail,
            "question": (
                "I need the missing value before I can calculate: "
                f"{detail}"),
            "checked_evidence": [
                str(dependency) for dependency in result.dependencies
            ][:20],
            "next_retrieval": "read the named source field, then retry",
            "kind": "missing_evidence",
        })
    return {
        "status": "applied",
        "summary": f"calculated {result.value} {result.unit}".strip(),
        "value": str(result.value),
        "unit": result.unit,
        "expression": result.expression,
        "steps": _json_safe(result.steps),
        "source_version": None,
        "evidence": [{
            "kind": "calculation",
            "expression": result.expression,
            "value": str(result.value),
            "unit": result.unit,
        }],
    }


def _office_format_spec(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    explicit = inputs.get("format_spec")
    if isinstance(explicit, dict) and explicit:
        return dict(explicit)
    teaching = context.get("teaching") or {}
    for key in ("output_requirements", "artifact_requirements"):
        value = teaching.get(key)
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _refuse_unresolved_business_results(context: Dict[str, Any]) -> None:
    """A requested output is not published before its required results.

    The requirement check is exact and namespaced; a receipt for another
    business subject leaves the requirement unresolved and must not create a
    downloadable report for this objective.
    """
    assignment = context.get("assignment")
    if not isinstance(assignment, dict) or not assignment.get(
            "business_requirements"):
        return
    try:
        from core.employee_business_outcomes import business_requirement_views
    except Exception:  # noqa: BLE001 — legacy path without requirements
        return
    unresolved = [
        view for view in business_requirement_views(assignment)
        if str(view.get("status") or "") != "satisfied"
    ]
    if not unresolved:
        return
    first = unresolved[0]
    action = str(first.get("next_action") or "").strip()
    raise NeedsContext({
        "concept": "business_result",
        "reason": (
            "the requested output cannot be published before the required "
            "business result is verified"),
        "question": action or (
            f"Complete the {first.get('label') or 'required result'} first."),
        "next_action": action or None,
        "next_retrieval": (
            "complete the authorized dependent work and retry the output"),
        "kind": "missing_evidence",
    })


@register_assignment_adapter(
    "artifact.document", description="Render a DOCX",
    metadata={"effect": "local", "required_actions": ["present"],
              "allow_standing_authorization": False})
async def _artifact_document(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    _refuse_unresolved_business_results(context)
    from core.office_service import OfficeService

    path = str(inputs.get("path") or "").strip()
    content = str(inputs.get("content") or "")
    if not content.strip() and inputs.get("compose_from_results"):
        content = _compose_evidence_content("document", inputs, context)
    if not path or not content.strip():
        raise NeedsContext({
            "concept": "artifact_content",
            "reason": "the document needs both a path and grounded content",
            "question": "What content should the document contain?",
            "kind": "missing_evidence",
        })
    spec = _office_format_spec(inputs, context)
    service = OfficeService()
    result = await asyncio.to_thread(
        service.word.create_from_markdown,
        path, content, title=str(inputs.get("title") or ""),
        sources=list(inputs.get("sources") or []),
        format_spec=spec,
    )
    if not result.get("success"):
        findings = result.get("teaching_findings") or []
        return {
            "status": "failed",
            "message": str(result.get("error") or "document render failed"),
            "evidence": findings,
        }
    checks = _verify_artifact_substance("document", path, inputs, context)
    digest = _sha256_file(path)
    return {
        "status": "applied",
        "summary": f"rendered {Path(path).name}",
        "content_sha256": hashlib.sha256(
            content.encode("utf-8")).hexdigest(),
        "artifact": {
            "kind": "document",
            "path": path,
            "sha256": digest,
            "revision": digest[:16],
        },
        "substantive": checks,
        "evidence_refs": [{"kind": "artifact", "sha256": digest}],
    }


@register_assignment_adapter(
    "artifact.spreadsheet", description="Render an XLSX",
    metadata={"effect": "local", "required_actions": ["present"],
              "allow_standing_authorization": False})
async def _artifact_spreadsheet(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    _refuse_unresolved_business_results(context)
    from core.office_service import OfficeService

    path = str(inputs.get("path") or "").strip()
    rows = inputs.get("rows")
    if (not isinstance(rows, list) or not rows) and inputs.get(
            "compose_from_results"):
        rows = _compose_evidence_rows(inputs, context)
    if not path or not isinstance(rows, list) or not rows:
        raise NeedsContext({
            "concept": "artifact_rows",
            "reason": "the spreadsheet needs a path and grounded row data",
            "question": "Which rows should the spreadsheet contain?",
            "kind": "missing_evidence",
        })
    spec = _office_format_spec(inputs, context)
    service = OfficeService()
    result = await asyncio.to_thread(
        service.excel.create_spreadsheet, path, rows, spec)
    if not result.get("success"):
        return {
            "status": "failed",
            "message": str(result.get("error") or "spreadsheet render failed"),
        }
    checks = _verify_artifact_substance(
        "spreadsheet", path, inputs, context)
    digest = _sha256_file(path)
    return {
        "status": "applied",
        "summary": f"rendered {Path(path).name}",
        "artifact": {
            "kind": "spreadsheet",
            "path": path,
            "sha256": digest,
            "revision": digest[:16],
        },
        "substantive": checks,
        "evidence_refs": [{"kind": "artifact", "sha256": digest}],
    }


@register_assignment_adapter(
    "artifact.presentation", description="Render a PPTX",
    metadata={"effect": "local", "required_actions": ["present"],
              "allow_standing_authorization": False})
async def _artifact_presentation(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    _refuse_unresolved_business_results(context)
    from core.office_service import OfficeService

    path = str(inputs.get("path") or "").strip()
    content = str(inputs.get("content") or "")
    if not content.strip() and inputs.get("compose_from_results"):
        content = _compose_evidence_content("presentation", inputs, context)
    if not path or not content.strip():
        raise NeedsContext({
            "concept": "artifact_content",
            "reason": "the presentation needs a path and a grounded outline",
            "question": "What outline should the presentation contain?",
            "kind": "missing_evidence",
        })
    spec = _office_format_spec(inputs, context)
    service = OfficeService()
    result = await asyncio.to_thread(
        service.pptx.create_from_markdown,
        path, content, title=str(inputs.get("title") or ""),
        sources=list(inputs.get("sources") or []),
        format_spec=spec,
    )
    if not result.get("success"):
        findings = result.get("teaching_findings") or []
        return {
            "status": "failed",
            "message": str(result.get("error") or "presentation render failed"),
            "evidence": findings,
        }
    checks = _verify_artifact_substance(
        "presentation", path, inputs, context)
    digest = _sha256_file(path)
    return {
        "status": "applied",
        "summary": f"rendered {Path(path).name}",
        "content_sha256": hashlib.sha256(
            content.encode("utf-8")).hexdigest(),
        "artifact": {
            "kind": "presentation",
            "path": path,
            "sha256": digest,
            "revision": digest[:16],
        },
        "substantive": checks,
        "evidence_refs": [{"kind": "artifact", "sha256": digest}],
    }


def compose_outbound_content(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Compose one outbound email payload with the applicable teaching.

    Both the approval preparation and the eventual send call this function,
    so the approved payload and the outgoing payload cannot diverge on the
    greeting, signature or subject prefix. The function is deterministic and
    applies the protocol idempotently.
    """
    from core.artifact_teaching import apply_email_teaching

    body = str(inputs.get("body") or "")
    if not body.strip() and inputs.get("compose_from_results"):
        body = _compose_evidence_text(inputs, context)
    if not body.strip():
        raise NeedsContext({
            "concept": "email_content",
            "reason": "the outbound message has no grounded body",
            "question": "What grounded result should the outbound message carry?",
            "kind": "missing_evidence",
        })
    content = {
        "to": inputs.get("to") or [],
        "cc": inputs.get("cc") or [],
        "subject": str(inputs.get("subject") or ""),
        "body": body,
    }
    if isinstance(content["to"], str):
        content["to"] = [content["to"]]
    content, findings = apply_email_teaching(
        content, _office_format_spec(inputs, context))
    blocked = [
        finding for finding in findings
        if finding.get("code") == "prohibited_internal_information"
    ]
    if blocked:
        raise AssignmentError(
            "the outbound message contains prohibited internal information")
    return content


def _email_draft_prepare(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    draft = _compose_email_draft(inputs, context)
    return {
        "payload": draft,
        "artifact_revision": draft.get("draft_revision"),
        "requested_by": context.get("employee_id") or "",
    }


def _compose_email_draft(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.artifact_teaching import apply_email_teaching

    spec = _office_format_spec(inputs, context)
    body = str(inputs.get("body") or "")
    if not body.strip() and inputs.get("compose_from_results"):
        body = _compose_evidence_text(inputs, context)
    if not body.strip():
        raise NeedsContext({
            "concept": "email_content",
            "reason": "the draft has no grounded body",
            "question": "What should the email draft say?",
            "kind": "missing_evidence",
        })
    content = {
        "to": inputs.get("to") or [],
        "cc": inputs.get("cc") or [],
        "subject": str(inputs.get("subject") or ""),
        "body": body,
        "attachments": list(inputs.get("attachments") or []),
    }
    if isinstance(content["to"], str):
        content["to"] = [content["to"]]
    content, findings = apply_email_teaching(content, spec)
    digest = canonical_sha256(content)
    blocked = [
        finding for finding in findings
        if finding.get("code") == "prohibited_internal_information"
    ]
    content["draft_revision"] = digest[:16]
    content["draft_revision_version"] = 2
    content["draft_only"] = True
    content["send_performed"] = False
    content["teaching_revision"] = (context.get("teaching") or {}).get(
        "revision") or ""
    if blocked:
        content["blocked"] = True
        content["findings"] = findings
    return content


async def _email_draft(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    draft = _compose_email_draft(inputs, context)
    if draft.get("blocked"):
        return {
            "status": "failed",
            "message": "the draft contains prohibited internal information",
            "evidence": draft.get("findings") or [],
        }
    return {
        "status": "applied",
        "summary": f"prepared draft {draft.get('draft_revision')}",
        "artifact": {
            "kind": "email_draft",
            "revision": draft["draft_revision"],
            "path": None,
            "sha256": canonical_sha256(draft),
        },
        "draft": _json_safe(draft),
        "evidence_refs": [{
            "kind": "draft",
            "revision": draft["draft_revision"],
        }],
    }


default_adapter_registry.register(
    "email.draft", _email_draft, prepare=_email_draft_prepare,
    description="Prepare an email draft without sending",
    metadata={"effect": "local", "required_actions": ["edit"],
              "allow_standing_authorization": False})


def _outlook_send_prepare(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    attachment_ids = list(inputs.get("attachment_ids") or [])
    attachment_hashes = {
        str(key): str(value)
        for key, value in (inputs.get("attachment_hashes") or {}).items()
    }
    if attachment_ids and not attachment_hashes:
        raise NeedsContext({
            "concept": "attachment_binding",
            "reason": (
                "sending attachments requires the exact sha256 binding that "
                "was approved; attachment ids alone can resolve to changed bytes"),
            "question": "Which attachment sha256 binding authorizes this send?",
            "kind": "missing_evidence",
        })
    content = (
        compose_outbound_content(inputs, context)
        if str(inputs.get("body") or "").strip()
        or inputs.get("compose_from_results")
        else None
    )
    payload = {
        "canvas_id": inputs.get("canvas_id"),
        "to": (content or {}).get("to") or inputs.get("to") or [],
        "cc": (content or {}).get("cc") or inputs.get("cc") or [],
        "subject": (content or {}).get("subject")
        or inputs.get("subject") or "",
        "body": (content or {}).get("body") or inputs.get("body") or "",
        "attachment_ids": attachment_ids,
        "attachment_hashes": attachment_hashes,
        "thread_id": inputs.get("thread_id"),
        "reply_all": bool(inputs.get("reply_all")),
    }
    return {
        "payload": payload,
        "artifact_revision": inputs.get("draft_revision")
        or inputs.get("artifact_revision"),
        "requested_by": context.get("employee_id") or "",
    }


async def _outlook_send(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Send through the authorized Outlook/canvas path, not a generic SES
    fallback. Provider acceptance and reconciliation are recorded on the
    task operation by EmailCanvasService."""
    if os.getenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", "0") != "1":
        return {
            "status": "failed",
            "message": (
                "production email sending is not authorized in this release; "
                "the assignment must remain draft-and-approval only"),
            "evidence": [{"kind": "outbound",
                          "provider_state": "not_sent",
                          "policy": "live_send_disabled"}],
        }
    from core.canvas_email_service import EmailCanvasService
    from core.database import get_db_session

    canvas_id = str(inputs.get("canvas_id") or "")
    step = context.get("step") or {}
    if not canvas_id or not step.get("operation_id"):
        raise NeedsContext({
            "concept": "send_operation",
            "reason": "the send step lacks a canvas or operation identity",
            "question": "Which prepared draft should be sent?",
            "kind": "missing_evidence",
        })
    content = (
        compose_outbound_content(inputs, context)
        if str(inputs.get("body") or "").strip()
        or inputs.get("compose_from_results")
        else None
    )
    recipients = (content or {}).get("to") or inputs.get("to") or []
    if isinstance(recipients, str):
        recipients = [item.strip() for item in recipients.split(",")
                      if item.strip()]
    subject = (content or {}).get("subject") or inputs.get("subject") or ""
    body = (content or {}).get("body") or inputs.get("body") or ""
    with get_db_session() as db:
        service = EmailCanvasService(db)
        result = await service.send_email(
            canvas_id=canvas_id,
            user_id=str(context.get("employee_id") or ""),
            to_emails=list(recipients),
            cc_emails=list((content or {}).get("cc")
                           or inputs.get("cc") or []),
            subject=str(subject),
            body=str(body),
            agent_id=str(context.get("agent_id") or "") or None,
            tenant_id=str(context.get("tenant_id") or "default"),
            attachment_ids=list(inputs.get("attachment_ids") or []) or None,
            expected_attachment_hashes=(
                dict(inputs.get("attachment_hashes") or {}) or None),
            thread_id=(str(inputs.get("thread_id") or "").strip() or None),
            reply_all=bool(inputs.get("reply_all")),
            run_id=str(context.get("run_id") or "") or None,
            operation_id=str(step.get("operation_id") or "") or None,
            workspace_id=str(context.get("workspace_id") or "") or None,
        )
    if result.get("success"):
        return {
            "status": "applied",
            "summary": f"provider accepted message ({result.get('status')})",
            "provider_state": result.get("provider_state") or "sent",
            "provider_ref": result.get("reply_to_message_id")
            or result.get("message_id"),
            "evidence": [{"kind": "outbound", "provider_state": "sent"}],
        }
    if result.get("outcome_uncertain"):
        raise ExternalOutcomeUnknown(
            "the provider may have accepted the message before the "
            "connection failed",
            evidence=str(result.get("error") or ""))
    return {
        "status": "failed",
        "message": str(result.get("error") or "Outlook send failed"),
        "evidence": [{"kind": "outbound", "provider_state": "not_sent"}],
    }


default_adapter_registry.register(
    "email.send_outlook", _outlook_send, prepare=_outlook_send_prepare,
    description="Send through the authorized Outlook/canvas path",
    metadata={"effect": "external", "required_actions": ["outbound"],
              "requires_approval": True,
              "allow_standing_authorization": False})

# Importing the line-item calculator registers ``quote.calculate`` on the
# default registry. It is imported last to avoid a module-initialization
# cycle; registries cloned after this point carry the adapter.
import core.assignment_quote  # noqa: E402,F401
import core.quote_rows  # noqa: E402,F401
import core.assignment_invoice  # noqa: E402,F401
import core.canvas_assignment  # noqa: E402,F401
