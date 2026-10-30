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
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

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
)

AdapterHandler = Callable[[Dict[str, Any], Dict[str, Any]], Any]
AdapterPreparer = Callable[[Dict[str, Any], Dict[str, Any]], Any]

logger = logging.getLogger(__name__)


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
        super().__init__(self.reason)


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


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded(value: Any, limit: int = 500) -> str:
    return str(value or "")[:limit]


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


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        return {str(k)[:80]: _json_safe(v, depth=depth + 1)
                for k, v in list(value.items())[:60]}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v, depth=depth + 1) for v in list(value)[:80]]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:2000]


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


def _collect_evidence(context: Dict[str, Any]) -> Dict[str, Any]:
    facts: List[Dict[str, Any]] = []
    row_sets: List[Dict[str, Any]] = []
    labels: List[str] = []

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
    evidence = _collect_evidence(context)
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
            columns = _row_columns(rows)
            lines += ["", f"### {_row_set_label(entry)}"]
            if columns:
                lines.append("| Row | " + " | ".join(columns) + " |")
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
    return "\n".join(lines)


def _compose_evidence_text(
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    evidence = _collect_evidence(context)
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
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    evidence = _collect_evidence(context)
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
    """Resolve the wait fact against the accepted read receipt's records.

    The resolver never treats a column header as a value, never scans the
    whole frame when the receipt names selected rows, and never turns an
    unreadable/incomplete receipt into a blank cell. Status is one of:
    ``missing`` (verified blanks), ``established``, ``mixed``,
    ``incomplete`` or ``unavailable``.
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

        # A read adapter's result rows are already the accepted selection,
        # but only when those rows actually carry the requested column. An
        # aggregate may return rows containing only the measure; in that case
        # use the receipt's row identities and read the bound frame.
        raw_rows = result.get("rows")
        if (isinstance(raw_rows, list) and raw_rows
                and any(isinstance(row, dict) and column in row
                        for row in raw_rows)):
            records = []
            for index, row in enumerate(raw_rows):
                if not isinstance(row, dict):
                    continue
                subject = (
                    f"row {row.get('__sheet_row')}"
                    if row.get("__sheet_row") is not None
                    else f"row {index + 1}")
                records.append({"subject": subject, "value": row.get(column)})
            if records:
                return _fact_resolution_from_records(
                    records, fact=fact, column=column, source=source)

        selected_rows: List[Any] = []
        selected_count = result.get("selected_count")
        source_row_count = coverage.get("source_row_count")
        for item in evidence:
            selected_rows.extend(item.get("sheet_rows") or [])
            if selected_count is None:
                selected_count = item.get("selected_count")
        selected_rows = list(dict.fromkeys(selected_rows))
        all_rows_selected = (
            not selected_rows
            and selected_count is not None
            and source_row_count is not None
            and int(selected_count) == int(source_row_count)
        )
        if not selected_rows and not all_rows_selected:
            # An aggregate receipt may carry accepted grouping values (for
            # example currency keys) without per-row identities. Those values
            # are bounded to the accepted aggregate, not the whole frame.
            aggregate_records: List[Dict[str, Any]] = []
            for item in result.get("values") or []:
                if not isinstance(item, dict):
                    continue
                for key, val in item.items():
                    if _normalized_fact_name(key) == wanted:
                        aggregate_records.append({
                            "subject": "aggregate",
                            "value": val,
                        })
            if not aggregate_records and isinstance(
                    result.get("subtotals"), dict):
                for key in result["subtotals"]:
                    aggregate_records.append({
                        "subject": "aggregate",
                        "value": key,
                    })
            if aggregate_records:
                return _fact_resolution_from_records(
                    aggregate_records, fact=fact, column=column, source=source)
            return {
                "status": "unavailable",
                "reason": "accepted_row_identities_missing",
                "fact": fact,
                "column": column,
                "source": source,
                "source_version": source.get("source_version"),
            }
        if coverage.get("known") is False or coverage.get("truncated") is True:
            return {
                "status": "incomplete",
                "reason": "accepted_coverage_incomplete",
                "fact": fact,
                "column": column,
                "source": source,
                "source_version": source.get("source_version"),
            }
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
                records.append({"subject": subject, "value": row.get(column)})
            return _fact_resolution_from_records(
                records, fact=fact, column=column, source=source)
        wanted_rows = {str(item) for item in selected_rows}
        records = []
        found_rows = set()
        for index, row in enumerate(frame):
            row_id = row.get("__sheet_row")
            subject = (
                f"row {row_id}" if row_id is not None else f"row {index + 1}")
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
    evidence = _collect_evidence(context)
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
        self._sync_run_plan(run_id, assignment)
        return self.lifecycle.get_task(run_id) or {}

    def _sync_run_plan(
        self, run_id: str, assignment: Dict[str, Any],
    ) -> None:
        """Keep the GoalRun plan linked to the assignment steps.

        The plan is an inspection/continuation projection, not a second
        execution truth: effect status still lives on the operation records.
        """
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

        return {
            "run_id": run_id,
            "assignment": assignment_projection(assignment),
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
                }
                for operation in record.get("operations") or []
            ],
        }

    # ----------------------------------------------------------- execution

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
            task_authorization = str(
                (record.get("task_revision") or {}).get("authorization")
                or "read_only")
            state = derive_state(
                assignment, task_authorization=task_authorization)
            if state in ("failed", "partial") and ready_steps(assignment):
                # Independent ready work may continue even when one branch
                # has failed; only the branch is blocked.
                state = "running"
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

            # An approved operation whose step still says awaiting_approval
            # is ready to run. The sync above keeps them aligned.
            waiting_step = self._first_waiting_step(assignment)
            if waiting_step is not None:
                resumed = await self._resume_waiting_step(
                    run_id, record, assignment, waiting_step)
                if resumed:
                    steps_run += 1
                    continue
                self._persist_assignment(
                    run_id, assignment, "assignment waiting")
                return self.status(run_id)

            readiness = ready_steps(assignment)
            if not readiness:
                self._persist_assignment(
                    run_id, assignment, "assignment stopped: no ready step")
                return self.status(run_id)

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

    async def recover_ready_assignments(
        self, *, limit: int = 50, max_steps_per_assignment: int = 20,
    ) -> List[Dict[str, Any]]:
        """Ordinary re-entry pass over active assignments.

        This resumes eligible pending/waiting work from durable state. It
        does NOT assert worker loss and does not call restart recovery; a
        running operation owned by another worker is left intact. The
        explicit ``recover_after_restart`` path owns loss recovery.
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
            results.append(await self.execute(
                run["id"], max_steps=max_steps_per_assignment))
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
        self._wake_run(run_id, {
            "event": "human_checkpoint",
            "hitl_id": request.get("hitl_action_id"),
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

    # --------------------------------------------------------------- gaps

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
            if resolution_matches(question.get("resolution"), resolution):
                current = self.status(run_id)
                return {
                    "status": "already_resolved",
                    "assignment": current.get("assignment"),
                    "open_gaps": current.get("open_gaps") or [],
                }
            raise AssignmentError(
                "the gap was already resolved with a different answer")
        mapping = dict((question.get("inputs") or {}).get("mapping") or {})
        selected_column = ""
        selected_unit = ""
        mapping_applied = False
        if mapping:
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
                # Rejection is an acknowledgement, not a resolution: the
                # same request and candidate evidence stay outstanding so a
                # restart cannot fork a second clarification.
                current = self.status(run_id)
                return {
                    "status": "rejected_candidates",
                    "assignment": current.get("assignment"),
                    "open_gaps": current.get("open_gaps") or [],
                }
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
            mapping_applied = True
        self.lifecycle.apply_transition(run_id, {
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
        })
        # Close the waiting attempt honestly; the reopened step gets a NEW
        # operation under the next attempt key. Reusing the waiting record
        # would make the executor believe it is still blocked.
        for step in record.get("assignment", {}).get("steps") or []:
            if question_id not in (step.get("gap_ids") or []):
                continue
            operation_id = _operation_id_for_step(record, step)
            if not operation_id:
                continue
            operation = _operation_by_id(record, operation_id) or {}
            if operation.get("status") == "waiting":
                try:
                    self.lifecycle.transition_operation(
                        run_id, operation_id, "superseded")
                except TaskLifecycleError:
                    pass

        def compute(record, assignment):
            new_plan = copy.deepcopy(assignment)
            reopened: List[str] = []
            if mapping_applied:
                missing = str(mapping.get("missing_column") or "")
                for step in new_plan.get("steps") or []:
                    step["inputs"] = _replace_mapping_value(
                        step.get("inputs") or {}, missing, selected_column)
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
            # A confirmed mapping changes evidence/calculation identity:
            # reopen only the affected step and its transitive dependants.
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
            return new_plan, {"reopened_steps": reopened}

        result = self.lifecycle.mutate_assignment(
            run_id, compute, rationale=f"gap {question_id} resolved")
        if mapping_applied:
            lesson_id = str(
                (mapping.get("mapping_source") or {}).get("lesson_id") or "")
            agent_id = str(
                ((record.get("assignment") or {}).get("provenance") or {}
                 ).get("agent_id") or "")
            if lesson_id and agent_id:
                try:
                    from core.database import get_db_session
                    from core.student_learning_service import update_teaching_point

                    source_mapping = dict(mapping.get("mapping_source") or {})
                    with get_db_session() as db:
                        update_teaching_point(
                            db, agent_id, lesson_id,
                            context={"field_mappings": [
                                dict(confirmed_mapping)]},
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "mapping lesson update skipped for %s: %s",
                        lesson_id, exc)
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

    def record_external_response(
        self,
        run_id: str,
        correlation_id: str,
        *,
        response: str,
        source: str = "",
        evidence: str = "",
        value: Any = None,
    ) -> Dict[str, Any]:
        """Match an authorized external reply to the waiting question.

        Matching is by the durable correlation id, never by message wording.
        An unmatched response is kept as evidence only and does not resume
        work.
        """
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
        from core.task_lifecycle import open_unresolved_questions

        for question in open_unresolved_questions(record):
            waiting = question.get("waiting") or {}
            if str(waiting.get("correlation_id") or "") != str(
                    correlation_id or ""):
                continue
            return self.resolve_gap(
                run_id, question["question_id"],
                resolution=response, resolved_by=source, evidence=evidence)

        # A step may wait directly on an external correlation without a
        # human question (e.g. a controlled reply). Match the step's durable
        # correlation id, never the message wording.
        assignment = record.get("assignment") or {}
        fact_confirmation: Optional[Dict[str, Any]] = None
        for step in assignment.get("steps") or []:
            waiting = step.get("waiting") or {}
            if str(waiting.get("correlation_id") or "") != str(
                    correlation_id or ""):
                continue
            fact = str(waiting.get("fact") or "").strip()
            fact_resolution = (
                _source_fact_resolution(record, fact)
                if fact else {"status": "unknown", "fact": fact})
            fact_status = str(fact_resolution.get("status") or "unknown")
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
                    conflict = {
                        "correlation_id": correlation_id,
                        "fact": fact,
                        "response": _bounded(response, 2000),
                        "source": _bounded(source, 200),
                        "evidence": _bounded(evidence, 500),
                        "at": _utc_now_iso(),
                        "reason": conflict_reason,
                        "column": fact_resolution.get("column"),
                        "established_values": (
                            fact_resolution.get("values") or []),
                        "subjects": fact_resolution.get("subjects") or [],
                        "blank_subjects": (
                            fact_resolution.get("blank_subjects") or []),
                        "source_ref": fact_resolution.get("source") or {},
                        "source_version": (
                            fact_resolution.get("source_version")),
                        "detail": fact_resolution.get("detail"),
                        "resolution_reason": fact_resolution.get("reason"),
                    }

                    def record_conflict(record, current):
                        new_plan = copy.deepcopy(current)
                        item = step_by_id(new_plan, step["step_id"])
                        if item is None:
                            return new_plan, {}
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
                        return new_plan, {"step_id": step["step_id"]}

                    result = self.lifecycle.mutate_assignment(
                        run_id, record_conflict,
                        rationale=(
                            f"external response did not resolve {fact}; "
                            f"source fact status is {fact_status}"))
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
                    return {
                        "status": conflict_status,
                        "message": message,
                        "fact": fact,
                        "conflict": conflict,
                        **result,
                    }
            operation_id = _operation_id_for_step(record, step)
            if operation_id:
                operation = _operation_by_id(record, operation_id) or {}
                if operation.get("status") == "waiting":
                    try:
                        self.lifecycle.transition_operation(
                            run_id, operation_id, "superseded")
                    except TaskLifecycleError:
                        pass

            def compute(record, current):
                new_plan = copy.deepcopy(current)
                item = step_by_id(new_plan, step["step_id"])
                if item is None:
                    return new_plan, {}
                item["status"] = "pending"
                item["attempts"] = int(item.get("attempts") or 0) + 1
                item["operation_id"] = None
                item["waiting"] = None
                item["external_response"] = {
                    "correlation_id": correlation_id,
                    "fact": fact,
                    "response": _bounded(response, 2000),
                    "source": _bounded(source, 200),
                    "evidence": _bounded(evidence, 500),
                    "fact_resolution": fact_resolution,
                    "at": _utc_now_iso(),
                }
                if fact_confirmation:
                    item["external_response"]["fact_confirmation"] = (
                        fact_confirmation)
                item["updated_at"] = _utc_now_iso()
                new_plan["status"] = "planned"
                new_plan["updated_at"] = _utc_now_iso()
                return new_plan, {"step_id": step["step_id"]}

            result = self.lifecycle.mutate_assignment(
                run_id, compute,
                rationale=f"external response matched {correlation_id}")
            self._wake_run(run_id, {
                "event": str(waiting.get("event") or "email"),
                "correlation_id": correlation_id,
                "source": "assignment_external_response",
            })
            return {"status": "resumed", **result}
        return {
            "status": "unmatched",
            "message": (
                "No open gap carries this correlation id. The response was "
                "not used to resume work."),
        }

    def retry_step(
        self, run_id: str, step_id: str, *, reason: str = "",
    ) -> Dict[str, Any]:
        """Explicitly retry a failed step as a NEW operation attempt."""
        def compute(record, assignment):
            step = step_by_id(assignment, step_id)
            if step is None:
                raise AssignmentError(f"unknown step {step_id!r}")
            if int(step.get("attempts") or 0) >= int(
                    step.get("max_attempts") or 3):
                raise AssignmentError(
                    f"step {step_id} exhausted its attempt budget")
            step["status"] = "pending"
            step["attempts"] = int(step.get("attempts") or 0) + 1
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
        return {"status": "reconciled", "operation": result}

    # ------------------------------------------------------------- cancel

    def cancel(
        self, run_id: str, *, reason: str, cancelled_by: str = "",
    ) -> Dict[str, Any]:
        """Cancel unstarted work; a running external effect is not undone."""
        record = self.lifecycle.get_task(run_id)
        if record is None:
            raise AssignmentError(f"no task record on run {run_id}")
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

        return self.lifecycle.mutate_assignment(
            run_id, compute, rationale=f"assignment cancelled: {reason}")

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
        return {
            "receipt_version": 1,
            "operation_id": operation.get("operation_id"),
            "execution_id": operation.get("execution_id"),
            "action": step.get("adapter"),
            "binding_sha256": operation.get("binding_sha256"),
            "observed_status": observed_status,
            "error_class": error_class,
            "reconciliation_required": bool(reconciliation_required),
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
                "provider_ref": result.get("provider_ref"),
            } if step.get("effect") == "external" else None,
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
            from core.task_outcome_contract import build_task_outcome
        except Exception:
            return assignment
        steps = assignment.get("steps") or []
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
                            or step.get("failure", {}).get("message") or ""),
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
            if step.get("adapter") in (
                    "email.send_outlook", "outbound.send") and applied:
                result = step.get("result") or {}
                provider_state = str(
                    result.get("provider_state") or "sent")
                delivery["provider_accepted"] = provider_state == "sent"
                delivery["provider_ref"] = result.get("provider_ref")
                delivery["sent_record_confirmed"] = provider_state == "sent"
                delivery["delivery_confirmed"] = False
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
            objective_met=state == "completed",
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
                # Never downgrade an applied step to awaiting because an
                # older operation row was re-read.
                if not (step.get("status") == "applied"
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

    def _budget_allows(
        self, assignment: Dict[str, Any], step: Dict[str, Any],
    ) -> bool:
        budget = assignment.get("budget") or {}
        if int(budget.get("steps_started") or 0) >= int(
                budget.get("max_steps") or 40):
            return False
        if int(step.get("attempts") or 0) >= int(
                step.get("max_attempts") or budget.get(
                    "max_attempts_per_step") or 3):
            return False
        started = budget.get("started_at")
        if started:
            try:
                started_at = datetime.fromisoformat(str(started)).timestamp()
                if self.clock() - started_at > float(
                        budget.get("max_wall_seconds") or 3600.0):
                    return False
            except (TypeError, ValueError):
                pass
        return True

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
                    "inputs": _json_safe(inputs),
                    "depends_on_results": {
                        dep: _json_safe(
                            (step_by_id(assignment, dep) or {}).get("result"))
                        for dep in (step.get("depends_on") or [])
                    },
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
            "objective": assignment.get("objective"),
            "teaching": copy.deepcopy(
                assignment.get("teaching_snapshot") or {}),
            "sources": copy.deepcopy(assignment.get("sources") or []),
            "deliverables": copy.deepcopy(
                assignment.get("deliverables") or []),
            "authorized_actions": list(
                assignment.get("authorized_actions") or []),
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
        operation_id = _operation_id_for_step(record, step)
        if operation_id:
            operation = _operation_by_id(record, operation_id) or {}
            if operation.get("status") == "waiting":
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
        self._persist_assignment(
            run_id, updated, f"step {step['step_id']} waiting resolved")
        return True

    async def _run_step(
        self,
        run_id: str,
        record: Dict[str, Any],
        assignment: Dict[str, Any],
        step: Dict[str, Any],
    ) -> None:
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
        if external and not approval.get("required") and not (
                standing and standing in (assignment.get("authorized_actions") or [])):
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

        if approval.get("required"):
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

        try:
            result = await _invoke(
                adapter.handler, dict(resolved_inputs), context)
            result = dict(result or {})
        except NeedsContext as exc:
            await self._record_gap(run_id, record, assignment, step, operation_id, exc.gap)
            return
        except WaitingForExternal as exc:
            self.lifecycle.set_operation_waiting(
                run_id, operation_id, waiting=exc.waiting)
            self._enter_wait(
                run_id, waiting=exc.waiting,
                summary=(exc.waiting or {}).get("detail", ""))
            assignment = self._mark_step(assignment, step["step_id"], {
                "status": "waiting",
                "waiting": _json_safe(exc.waiting),
                "updated_at": _utc_now_iso()})
            self._persist_assignment(
                run_id, assignment, "step waiting for external")
            return
        except ExternalOutcomeUnknown as exc:
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
        except Exception as exc:  # noqa: BLE001 — durable failure state
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
            await self._record_gap(
                run_id, record, assignment, step, operation_id,
                result.get("gap") or {})
            return
        if outcome == "waiting":
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
        if outcome == "skipped":
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
            "artifact_revision": (
                (result.get("artifact") or {}).get("revision")
                if isinstance(result.get("artifact"), dict) else None),
            "value": result.get("value"),
            "unit": result.get("unit"),
            "expression": result.get("expression"),
            "operation": result.get("operation"),
            "measure": result.get("measure"),
            "values": result.get("values"),
            "subtotals": result.get("subtotals"),
            "source": result.get("source"),
            "source_label": result.get("source_label"),
            "formulas": result.get("formulas"),
            "matched_count": result.get("matched_count"),
            "selected_count": result.get("selected_count"),
            "truncated": result.get("truncated"),
            "substantive": result.get("substantive"),
            "source_version": result.get("source_version"),
            "provider_ref": result.get("provider_ref"),
            "rows": result.get("rows"),
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
        waiting = gap.get("waiting") or {
            "state": "waiting_for_person",
            "party": gap.get("resolver") or "owner",
            "resume_on": "answer",
            "since": _utc_now_iso(),
        }
        existing = [
            question for question in
            (record.get("task_revision") or {}).get("unresolved") or []
            if isinstance(question, dict)
            and question.get("status") == "open"
            and question.get("step_id") == step.get("step_id")
            and str(question.get("concept") or "")
            == str(gap.get("concept") or "")
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
                        == str(gap.get("concept") or "")):
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
    execution_context = {
        "workspace_id": context.get("workspace_id"),
        "user_id": context.get("employee_id"),
        "run_id": context.get("run_id"),
        "assignment_id": context.get("assignment_id"),
        "agent_id": context.get("agent_id"),
        "tenant_id": context.get("tenant_id"),
        "task_revision": (context.get("task_revision") or {}).get(
            "revision"),
    }
    failures = action.check_preconditions(execution_context)
    if failures:
        return {
            "status": "failed",
            "message": "one or more action preconditions are not satisfied",
            "error_class": "precondition_failed",
            "evidence": failures,
        }
    try:
        result = await action_registry.execute_action(
            name, arguments, execution_context)
    except Exception as exc:  # noqa: BLE001 — receipt keeps the failure
        return {
            "status": "failed",
            "message": _bounded(str(exc), 500),
            "error_class": "action_dispatch_error",
        }
    return {
        "status": "applied",
        "summary": f"registered action {name} completed",
        "data": _json_safe(result),
        "evidence": [{"kind": "action_registry", "action": name}],
    }


_READ_ONLY_RESEARCH_ACTIONS = {
    "documents.search", "search_communications", "documents.ls",
    "documents.cat", "documents.read",
}


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


def resolution_matches(stored: Any, incoming: Any) -> bool:
    """Whether a replay is the same resolution, ignoring audit metadata.

    ``resolve_gap`` appends ``[by ...]`` and ``[evidence: ...]`` to the
    durable resolution. A byte-identical retry is still the same request,
    while a different answer remains a conflict.
    """
    stored_text = str(stored or "")
    incoming_text = str(incoming or "")
    if not incoming_text:
        return False
    if stored_text == incoming_text:
        return True
    return stored_text.startswith(incoming_text + " [")


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
    return {
        "status": "applied",
        "summary": (
            f"read {len(rows)} of {matched} matching row(s) from "
            f"{source_label}"),
        "rows": _json_safe(rows),
        "schema": [{"column": column} for column in physical if column],
        "formulas": formulas,
        "matched_count": matched,
        "truncated": matched > limit,
        "source_version": source["source_version"],
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
    source_version = _sha256_file(path)
    return {
        "status": "applied",
        "summary": (
            f"read {min(len(records), limit)} of {len(records)} matching "
            f"record(s) from {sheet.title}"),
        "rows": _json_safe(records[:limit]),
        "schema": [{"column": column} for column in header if column],
        "matched_count": len(records),
        "truncated": len(records) > limit,
        "source_version": source_version,
        "evidence": [{
            "kind": "workbook",
            "path": path,
            "sheet": sheet.title,
            "content_hash": source_version,
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
    source_version = _sha256_file(path)
    return {
        "status": "applied",
        "summary": f"read {len(text)} characters from {Path(path).name}",
        "text": text[:20000],
        "truncated": len(text) > 20000,
        "source_version": source_version,
        "evidence": [{
            "kind": "document",
            "path": path,
            "content_hash": source_version,
        }],
    }


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


@register_assignment_adapter(
    "artifact.document", description="Render a DOCX",
    metadata={"effect": "local", "required_actions": ["present"],
              "allow_standing_authorization": False})
async def _artifact_document(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
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
    from core.office_service import OfficeService

    path = str(inputs.get("path") or "").strip()
    rows = inputs.get("rows")
    if (not isinstance(rows, list) or not rows) and inputs.get(
            "compose_from_results"):
        rows = _compose_evidence_rows(context)
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
