"""Bounded employee work proposals over the existing assignment contracts.

The reasoning layer chooses *supported* next work from an ordinary objective
and the durable employee context. It never executes a tool, grants authority,
writes a receipt or supplies executable step JSON. Deterministic code
validates the proposal against the registered sources/actions and compiles it
through ``assignment_planner.plan_assignment`` for the existing
``AssignmentExecutor`` to own.

The module is deliberately small and pure. It is not another planner engine:
the compiler is the existing assignment planner, the state carrier is the
existing task lifecycle, and the executor remains the sole operation driver.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from core.assignment_resources import resource_binding
from core.employee_business_outcomes import business_requirement_views
from core.employee_work_requests import work_request_schemas

PROPOSAL_SCHEMA = "atom-employee-work-proposal-1"
MAX_EVIDENCE_READS = 5
MAX_CONTEXT_SOURCES = 10
MAX_CONTEXT_FACTS = 40
MAX_CONTEXT_OBLIGATIONS = 20


class EvidenceReadProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(default="", max_length=80)
    title: str = Field(default="", max_length=200)
    source_id: str = Field(default="", max_length=200)
    action: str = Field(default="", max_length=200)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requires: List[Dict[str, Any]] = Field(default_factory=list)
    reason: str = Field(default="", max_length=500)


class ClarificationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(max_length=400)
    concept: str = Field(default="", max_length=120)
    unblocks: str = Field(default="", max_length=300)
    expected_answer_type: str = Field(default="", max_length=80)
    # Typed, server-validated scope for a capability missing several declared
    # roles. The model names only the role(s) this one question requests; the
    # consumer intersects them with the capability contract instead of
    # inferring scope from human wording.
    missing_roles: List[str] = Field(default_factory=list, max_length=8)


class EmployeeWorkProposal(BaseModel):
    """One reasoning proposal. Never an effect or an authority grant."""

    model_config = ConfigDict(extra="forbid")

    proposal_kind: Literal[
        "evidence_read", "clarification", "evidence_and_clarification"]
    reason: str = Field(default="", max_length=800)
    evidence_reads: List[EvidenceReadProposal] = Field(default_factory=list)
    clarification: Optional[ClarificationProposal] = None


def _text(value: Any, limit: int = 400) -> str:
    return str(value or "").strip()[:limit]


_OBJECTIVE_IDENTITY_RE = re.compile(
    r"\b(INV|PO)-[A-Za-z0-9][A-Za-z0-9-]*", re.IGNORECASE)


def objective_identity_hints(objective: Any) -> Dict[str, str]:
    """Extract only unambiguous invoice/PO identifiers named by the user.

    This is a scope hint for candidate filtering, never an answer subset or a
    role mapping. Multiple identifiers for one namespace produce no hint.
    """
    found: Dict[str, List[str]] = {"invoice_id": [], "po_id": []}
    for match in _OBJECTIVE_IDENTITY_RE.finditer(str(objective or "")):
        value = match.group(0)
        key = (
            "invoice_id" if match.group(1).upper() == "INV"
            else "po_id")
        if value not in found[key]:
            found[key].append(value)
    return {
        key: values[0] for key, values in found.items()
        if len(values) == 1
    }


def source_handle(source: Mapping[str, Any]) -> str:
    """Stable, non-secret handle for an authorized source."""
    return _source_id(source)


def _source_id(source: Mapping[str, Any]) -> str:
    explicit = _text(source.get("source_id"), 200)
    if explicit:
        return explicit
    raw = dict(source) if isinstance(source, Mapping) else {}
    nested = raw.get("binding")
    if isinstance(nested, Mapping):
        for key, value in nested.items():
            raw.setdefault(key, value)
    binding = resource_binding(raw) if raw else {}
    for candidate in (
            binding.get("resource_id"),
            source.get("resource_id"),
            source.get("dataset_name"),
            source.get("external_id"),
            source.get("file_name"),
    ):
        if str(candidate or "").strip():
            return _text(candidate, 200)
    return ""


def _binding_source_identity(source: Mapping[str, Any]) -> str:
    binding = source.get("binding") if isinstance(
        source.get("binding"), Mapping) else {}
    return "|".join(str(binding.get(key) or source.get(key) or "")
                    for key in ("resource_id", "dataset_name", "source",
                                "external_id", "source_version", "sheet"))


def _step_source_identity(step: Mapping[str, Any]) -> str:
    inputs = step.get("inputs") if isinstance(
        step.get("inputs"), Mapping) else {}
    binding = inputs.get("resource_binding") if isinstance(
        inputs.get("resource_binding"), Mapping) else {}
    return "|".join(str(binding.get(key) or "") for key in (
        "resource_id", "dataset_name", "source", "external_id",
        "source_version", "sheet"))


def scoped_source_views(
    assignment: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Authorized source handles with a truthful read flag."""
    read_identities = {
        _step_source_identity(step)
        for step in assignment.get("steps") or []
        if isinstance(step, Mapping) and step.get("status") == "applied"
    }
    scoped = []
    for source in assignment.get("sources") or []:
        if not isinstance(source, Mapping):
            continue
        item = dict(source)
        item["read"] = _binding_source_identity(source) in read_identities
        scoped.append(item)
    return scoped


def _source_view(source: Mapping[str, Any]) -> Dict[str, Any]:
    raw = dict(source)
    nested = raw.get("binding")
    if isinstance(nested, Mapping):
        for key, value in nested.items():
            raw.setdefault(key, value)
    source = raw
    binding = resource_binding(raw)
    return {
        "source_id": _source_id(source),
        "kind": _text(source.get("kind"), 40),
        "representation": _text(
            source.get("representation") or binding.get("representation"), 40),
        "file_name": _text(
            source.get("file_name") or binding.get("file_name")
            or source.get("original_file_name"), 200),
        "sheet": _text(source.get("sheet") or binding.get("sheet"), 120),
        "columns": [
            _text(column, 120) for column in
            (source.get("columns") or binding.get("columns") or [])[:40]
            if str(column).strip()
        ],
        "numeric_columns": [
            _text(column, 120) for column in
            (source.get("numeric_columns")
             or binding.get("numeric_columns") or [])[:40]
            if str(column).strip()
        ],
        "row_count": source.get("row_count"),
        "coverage": dict(source.get("coverage") or {}),
        "source_version": _text(
            source.get("source_version") or binding.get("source_version"), 160),
        "read": bool(source.get("read")),
        "authorized": True,
        "preview": {
            "sampled": True,
            "kind": "source_metadata_not_rows",
            "total_count": source.get("row_count"),
            "shown_count": 0,
            "omitted_count": source.get("row_count"),
            "note": (
                "reasoning handle only; execution resolves full durable "
                "evidence under the existing proof rules"),
        },
    }


def _evidence_preview(item: Mapping[str, Any]) -> Dict[str, Any]:
    rows_all = [
        dict(row) for row in (item.get("rows") or [])
        if isinstance(row, Mapping)
    ]
    rows = rows_all[:20]
    total = item.get("total_count")
    if total is None:
        total = item.get("row_count")
    if total is None:
        total = len(rows_all)
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = len(rows_all)
    shown = len(rows)
    return {
        "step_id": _text(item.get("step_id"), 80),
        "adapter": _text(item.get("adapter"), 120),
        "status": _text(item.get("status"), 20),
        "summary": _text(item.get("summary"), 500),
        "value": item.get("value"),
        "unit": _text(item.get("unit"), 40) or None,
        "rows": rows,
        "data": dict(item.get("data") or {}),
        "data_keys": [
            str(key) for key in (item.get("data_keys") or [])[:40]
        ],
        "data_preview": {
            str(key): value
            for key, value in list(
                (item.get("data_preview") or {}).items())[:20]
            if isinstance(value, (str, int, float, bool, type(None)))
        },
        "business_role": _text(item.get("business_role"), 40) or None,
        "schema": [
            dict(field) for field in (item.get("schema") or [])[:40]
            if isinstance(field, Mapping)
        ],
        "coverage": dict(item.get("coverage") or {}),
        "verification": dict(item.get("verification") or {}),
        "artifact": dict(item.get("artifact") or {}),
        "truncated": bool(item.get("truncated")),
        "source_identity": {
            "resource_id": _text(
                item.get("resource_id")
                or (item.get("source") or {}).get("resource_id"), 200),
            "version": _text(
                item.get("source_version")
                or (item.get("source") or {}).get("source_version"), 160),
            "sha256": _text(
                item.get("sha256")
                or (item.get("source") or {}).get("sha256"), 160),
        },
        "preview": {
            "sampled": True,
            "total_count": total,
            "shown_count": shown,
            "omitted_count": max(0, total - shown),
            "note": (
                "preview rows for reasoning only; compiled execution resolves "
                "full durable evidence and must not use these rows as the "
                "calculation population"),
        },
    }


def build_employee_context(
    *,
    objective: str,
    employee_id: str = "",
    agent_id: Optional[str] = None,
    workspace_id: str = "",
    tenant_id: str = "",
    teaching: Optional[Mapping[str, Any]] = None,
    sources: Optional[Sequence[Mapping[str, Any]]] = None,
    task_context: Optional[Mapping[str, Any]] = None,
    criteria: Optional[Sequence[Mapping[str, Any]]] = None,
    facts: Optional[Sequence[Mapping[str, Any]]] = None,
    open_obligations: Optional[Sequence[Mapping[str, Any]]] = None,
    authorized_actions: Optional[Sequence[str]] = None,
    action_views: Optional[Sequence[Mapping[str, Any]]] = None,
    adapter_views: Optional[Sequence[Mapping[str, Any]]] = None,
    evidence_results: Optional[Sequence[Mapping[str, Any]]] = None,
    budget: Optional[Mapping[str, Any]] = None,
    task_version: Optional[int] = None,
    plan_revision: Optional[int] = None,
    existing_step_ids: Optional[Sequence[str]] = None,
    stage: str = "discovery",
    available_work_requests: Optional[Sequence[str]] = None,
    operation_eligibility: Optional[Sequence[Mapping[str, Any]]] = None,
    waiting: Optional[Sequence[Mapping[str, Any]]] = None,
    completed_operations: Optional[Sequence[Mapping[str, Any]]] = None,
    business_requirements: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Bounded context for the reasoning consumer, with stable handles only.

    File paths and raw document bodies are intentionally excluded. The model
    sees identities, schemas, coverage and typed facts; the executor resolves
    bytes from the binding when the proposed read actually runs.
    """
    teaching = dict(teaching or {})
    follow_up_stage = stage in ("follow_up", "adaptation", "result")
    eligibility = [
        dict(item) for item in (operation_eligibility or [])
        if isinstance(item, Mapping)
    ]
    if eligibility:
        operation_names = [
            str(item.get("operation") or "") for item in eligibility
            if str(item.get("status") or "") != "unavailable"
        ]
        ready_names = {
            str(item.get("operation") or "") for item in eligibility
            if str(item.get("status") or "") == "ready"
        }
    elif available_work_requests is None:
        operation_names = [
            item["operation"] for item in _operation_views(None)]
        ready_names = set(operation_names)
    else:
        operation_names = list(available_work_requests)
        ready_names = set(operation_names)
    operations = (
        _operation_views(available_work_requests, eligibility)
        if follow_up_stage else []
    )
    missing_prerequisites = [
        {
            "operation": item.get("operation"),
            "label": item.get("label") or item.get("operation"),
            "status": item.get("status"),
            "missing": list(item.get("missing") or []),
            "question_hint": item.get("question_hint") or "",
            "known_identities": dict(item.get("known_identities") or {}),
        }
        for item in operations
        if str(item.get("status") or "") in ("missing", "ambiguous")
    ]
    schemas = (
        [
            schema for schema in work_request_schemas()
            if (
                not eligibility
                and available_work_requests is None
            )
            or schema.get("operation") in ready_names
            # A material external fact is a valid typed intent whenever the
            # objective has a declared missing prerequisite, even though it is
            # not itself a business capability.
            or (
                schema.get("operation") == "await_evidence"
                and bool(missing_prerequisites) and bool(ready_names)
            )
        ]
        if follow_up_stage else []
    )
    return {
        "schema": PROPOSAL_SCHEMA,
        "objective": _text(objective, 4000),
        "identity": {
            "employee_id": _text(employee_id, 120) or None,
            "agent_id": _text(agent_id, 120) or None,
            "workspace_id": _text(workspace_id, 120) or None,
            "tenant_id": _text(tenant_id, 120) or None,
            "execution_owner": "assignment",
        },
        "authorized_source_count": len(sources or []),
        "unread_source_count": sum(
            1 for item in (sources or [])
            if isinstance(item, Mapping) and not item.get("read")),
        "task_version": (
            int(task_version) if task_version is not None else None),
        "plan_revision": (
            int(plan_revision) if plan_revision is not None else None),
        "criteria": [dict(item) for item in (criteria or [])[:20]
                     if isinstance(item, Mapping)],
        "teaching": {
            "revision": _text(teaching.get("revision"), 80),
            "effective_lesson_ids": list(
                teaching.get("effective_lesson_ids") or [])[:20],
            "applicable_conditions": dict(
                teaching.get("applicable_conditions") or {}),
            "rules": [
                _text(item, 500) for item in (teaching.get("rules") or [])[:20]
                if str(item or "").strip()
            ],
            "terms": {
                _text(key, 80): value
                for key, value in list(
                    (teaching.get("terms") or {}).items())[:20]
                if _text(key, 80) and isinstance(
                    value, (str, int, float, bool, type(None), dict, list))
            },
        },
        "task_context": dict(task_context or {}),
        "sources": [
            _source_view(item) for item in (sources or [])[:MAX_CONTEXT_SOURCES]
            if isinstance(item, Mapping) and _source_id(item)
        ],
        "unread_sources": [
            _source_view(item) for item in (sources or [])[:MAX_CONTEXT_SOURCES]
            if isinstance(item, Mapping) and _source_id(item)
            and not item.get("read")
        ],
        "facts": [
            {
                "fact_id": _text(item.get("fact_id"), 120),
                "subject": dict(item.get("subject") or {}),
                "field_id": _text(item.get("field_id"), 120) or None,
                "value": item.get("value"),
                "value_type": _text(item.get("value_type"), 40) or None,
                "evidence_state": _text(
                    item.get("evidence_state"), 20) or "unknown",
                "source_refs": [
                    dict(ref) for ref in (item.get("source_refs") or [])[:20]
                    if isinstance(ref, Mapping)],
                "authority_ref": _text(
                    item.get("authority_ref"), 200) or None,
                "validity": dict(item.get("validity") or {}),
            }
            for item in (facts or [])[:MAX_CONTEXT_FACTS]
            if isinstance(item, Mapping) and item.get("fact_id")
        ],
        "open_obligations": [
            {
                "question_id": _text(item.get("question_id"), 120),
                "question": _text(item.get("question"), 400),
                "concept": _text(item.get("concept"), 120) or None,
                "next_action": _text(item.get("next_action"), 400) or None,
                "kind": _text(item.get("kind"), 40),
            }
            for item in (open_obligations or [])[:MAX_CONTEXT_OBLIGATIONS]
            if isinstance(item, Mapping)
        ],
        "waiting": [
            {
                "step_id": _text(item.get("step_id"), 80),
                "fact": _text(item.get("fact"), 120),
                "subject": _text(item.get("subject"), 200),
                "party": _text(item.get("party"), 200),
                "detail": _text(item.get("detail"), 300),
                "blocks": _text(item.get("blocks"), 500),
                "expected_answer_type": _text(
                    item.get("expected_answer_type"), 40),
                "correlation_id": _text(item.get("correlation_id"), 120),
                "since": _text(item.get("since"), 40),
            }
            for item in (waiting or [])[:10]
            if isinstance(item, Mapping) and item.get("fact")
        ],
        "ready_operations": [
            _text(item.get("operation"), 120)
            for item in operations
            if str(item.get("status") or "") == "ready"
        ],
        "completed_operations": [
            {
                "operation": _text(item.get("operation"), 120),
                "reason": _text(item.get("reason"), 200),
            }
            for item in (completed_operations or [])[:10]
            if isinstance(item, Mapping)
        ],
        "business_requirements": [
            {
                "requirement_id": _text(item.get("requirement_id"), 120),
                "operation": _text(item.get("operation"), 120),
                "label": _text(item.get("label"), 200),
                "subject": _text(item.get("subject"), 200),
                "subject_identity": {
                    _text(key, 80): _text(value, 200)
                    for key, value in (
                        item.get("subject_identity") or {}).items()
                    if _text(key, 80) and _text(value, 200)
                },
                "fact": _text(item.get("fact"), 120),
                "status": _text(item.get("status"), 40),
                "next_action": _text(item.get("next_action"), 300) or None,
            }
            for item in (business_requirements or [])[:10]
            if isinstance(item, Mapping)
            and item.get("requirement_id")
        ],
        "authorized_actions": [
            _text(item, 120) for item in (authorized_actions or [])
            if str(item).strip()
        ][:40],
        "action_views": [
            {
                "action": _text(item.get("action") or item.get("name"), 200),
                "effect": _text(item.get("effect") or "read_only", 40),
                "description": _text(item.get("description"), 300),
            }
            for item in (action_views or [])[:40]
            if isinstance(item, Mapping)
        ],
        "adapter_views": [
            {
                "adapter": _text(item.get("adapter") or item.get("name"), 120),
                "effect": _text(item.get("effect") or "declared", 40),
                "operation_type": _text(item.get("operation_type"), 40),
                "required_actions": list(
                    item.get("required_actions") or [])[:10],
                "description": _text(item.get("description"), 300),
                "input_schema": dict(item.get("input_schema") or {}),
            }
            for item in (adapter_views or [])[:60]
            if isinstance(item, Mapping)
        ],
        "existing_step_ids": [
            _text(item, 80) for item in (existing_step_ids or [])
            if str(item).strip()
        ][:80],
        "evidence_results": [
            _evidence_preview(item)
            for item in (evidence_results or [])[:20]
            if isinstance(item, Mapping)
        ],
        "budget": dict(budget or {}),
        "stage": stage,
        "work_request_schemas": schemas,
        "available_business_operations": operations,
        "missing_prerequisites": missing_prerequisites,
        "rules": (
            {
                "allowed_proposal_kinds": (
                    ["replan", "clarify"] if missing_prerequisites
                    else ["replan"]),
                "allowed_work_requests": list(dict.fromkeys([
                    *[
                        item["operation"] for item in operations
                        if item.get("operation") in ready_names
                    ],
                    *(["await_evidence"]
                      if missing_prerequisites and ready_names else []),
                ])),
                "can_execute": False,
                "can_grant_authority": False,
                "can_supply_receipts": False,
                "can_propose_supported_work": bool(ready_names),
                "evidence_only": False,
                "clarify_only_when_material": True,
                "execution_mechanics": "compiler",
            }
            if schemas else (
                {
                    "allowed_proposal_kinds": ["clarify", "retain"],
                    "allowed_work_requests": [],
                    "can_execute": False,
                    "can_grant_authority": False,
                    "can_supply_receipts": False,
                    "can_propose_supported_work": False,
                    "evidence_only": False,
                    "clarify_only_when_material": True,
                }
                if follow_up_stage else {
                    "allowed_proposal_kinds": [
                        "evidence_read", "clarification",
                        "evidence_and_clarification"],
                    "can_execute": False,
                    "can_grant_authority": False,
                    "can_supply_receipts": False,
                    "can_propose_supported_work": False,
                    "evidence_only": True,
                    "clarify_only_when_material": True,
                }
            )
        ),
    }


def _operation_views(
    available: Optional[Sequence[str]],
    eligibility: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if available is None:
        available = []
        unrestricted = True
    else:
        unrestricted = False
    definitions = [
        {
            "operation": "quote_calculation",
            "when": (
                "accepted price rows and taught/authorized currency, freight "
                "and tax terms are available"),
            "supports": ["exact quote line items and total from full rows"],
        },
        {
            "operation": "invoice_reconciliation",
            "when": (
                "accepted invoice, purchase order and receiving evidence are "
                "available"),
            "supports": [
                "quantity/amount reconciliation",
                "one targeted correction obligation when mismatched"],
        },
    ]
    allowed = set(available or [])
    by_operation = {
        str(item.get("operation") or ""): dict(item)
        for item in (eligibility or []) if isinstance(item, Mapping)
    }
    if by_operation:
        merged = []
        for definition in definitions:
            extra = by_operation.get(definition["operation"])
            if extra is None:
                continue
            merged.append({**definition, **extra})
        return merged
    return [
        item for item in definitions
        if unrestricted or item["operation"] in allowed
    ]


_VERIFIED_PROOF = {
    "verified", "material_verified", "confirmed", "complete",
}


def _result_proven(result: Mapping[str, Any]) -> bool:
    verification = result.get("verification")
    status = (
        str(verification.get("status") or "").lower()
        if isinstance(verification, Mapping) else "")
    if status in _VERIFIED_PROOF:
        return True
    receipt = result.get("receipt")
    return bool(
        isinstance(receipt, Mapping)
        and str(receipt.get("status") or "").lower() in _VERIFIED_PROOF)


def _evidence_shapes(assignment: Mapping[str, Any]) -> Dict[str, List[Dict]]:
    tabular: List[Dict[str, Any]] = []
    structured: List[Dict[str, Any]] = []
    textual: List[Dict[str, Any]] = []
    for step in assignment.get("steps") or []:
        if not isinstance(step, Mapping) or step.get("status") != "applied":
            continue
        result = step.get("result")
        if not isinstance(result, Mapping) or not result:
            continue
        adapter = str(step.get("adapter") or "")
        if adapter.startswith((
                "quote.", "invoice.", "action.", "assignment.",
                "deliverable.", "document.write", "presentation.",
                "outbound.")):
            continue
        proven = _result_proven(result)
        base = {
            "step_id": str(step.get("step_id") or ""),
            "title": str(step.get("title") or ""),
            "verified": proven,
        }
        rows = result.get("rows")
        if (isinstance(rows, list) and rows
                and isinstance(rows[0], Mapping)):
            tabular.append({
                **base,
                "shape": "tabular",
                "columns": sorted(str(key) for key in rows[0])[:40],
            })
            continue
        data = result.get("data")
        if isinstance(data, Mapping) and data:
            structured.append({
                **base,
                "shape": "structured",
                "data_keys": sorted(str(key) for key in data)[:40],
                "data": dict(data),
            })
            continue
        if str(result.get("text") or "").strip():
            textual.append({**base, "shape": "text"})
    return {
        "tabular": tabular, "structured": structured, "textual": textual,
    }


def operation_capabilities(
    assignment: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Capabilities with eligibility/precondition status, not header filters.

    Accepted evidence is classified by its registered result contract
    (tabular rows, structured object, text), never by business column names.
    A missing role is named so the model can recognize what to retrieve; the
    capability description is not erased.
    """
    shapes = _evidence_shapes(assignment)
    tabular = shapes["tabular"]
    structured = shapes["structured"]
    textual = shapes["textual"]
    capabilities: List[Dict[str, Any]] = []

    if tabular:
        proven = [item for item in tabular if item["verified"]]
        capabilities.append({
            "operation": "quote_calculation",
            "label": "quote calculation",
            "status": "ready" if proven else "missing",
            "missing": [] if proven else ["verified tabular evidence"],
            "evidence": tabular,
            "question_hint": (
                "Which authorized source provides verified tabular price rows?"
                if not proven else ""),
        })
    elif textual and not structured:
        capabilities.append({
            "operation": "quote_calculation",
            "label": "quote calculation",
            "status": "missing",
            "missing": ["tabular price rows"],
            "evidence": textual,
            "question_hint": (
                "Which authorized source contains the tabular price rows "
                "needed for the quote?"),
        })
    else:
        capabilities.append({
            "operation": "quote_calculation",
            "label": "quote calculation",
            "status": "unavailable",
            "missing": [],
            "evidence": structured + textual,
            "question_hint": "",
        })

    from core.employee_work_compiler import (
        INVOICE_FIELD_DEFAULTS,
        INVOICE_ROLE_REQUIREMENTS,
        PURCHASE_ORDER_FIELD_DEFAULTS,
        RECEIVING_FIELD_DEFAULTS,
        _invoice_role_candidates,
    )

    role_fields = {
        "invoice": dict(INVOICE_FIELD_DEFAULTS),
        "purchase_order": dict(PURCHASE_ORDER_FIELD_DEFAULTS),
        "receiving": dict(RECEIVING_FIELD_DEFAULTS),
    }
    role_candidates = {
        role: _invoice_role_candidates(
            assignment, role_fields[role], INVOICE_ROLE_REQUIREMENTS[role])
        for role in INVOICE_ROLE_REQUIREMENTS
    }
    requirement_identity: Dict[str, Any] = {}
    for requirement in assignment.get("business_requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        if str(requirement.get("operation") or "") != (
                "invoice_reconciliation"):
            continue
        if str(requirement.get("status") or "") == "satisfied":
            continue
        requirement_identity = dict(
            requirement.get("subject_identity") or {})
        break
    provenance_identities = (
        assignment.get("provenance") or {}).get("objective_identities") or {}
    if isinstance(provenance_identities, Mapping):
        for key in ("invoice_id", "po_id"):
            value = str(provenance_identities.get(key) or "").strip()
            if value and not requirement_identity.get(key):
                requirement_identity[key] = value
    if structured:
        candidate_steps = {
            str(step.get("step_id")): step for step in structured
        }
        identity_missing: List[str] = []
        if requirement_identity:
            # Exact identity is the acceptance scope, not candidate
            # relevance. Keep distractors visible in the evidence previews,
            # but do not offer a wrong-PO/obsolete invoice as a role choice.
            filtered: Dict[str, List[str]] = {}
            expected_invoice = str(
                requirement_identity.get("invoice_id") or "").strip()
            expected_po = str(
                requirement_identity.get("po_id") or "").strip()
            for role, candidates in role_candidates.items():
                if not candidates:
                    filtered[role] = []
                    continue
                matching = []
                for step_id in candidates:
                    data = candidate_steps.get(
                        step_id, {}).get("data") or {}
                    if role == "invoice":
                        if expected_invoice and str(
                                data.get("invoice_id") or "") != (
                                    expected_invoice):
                            continue
                        if expected_po and str(
                                data.get("po_id") or "") != expected_po:
                            continue
                    elif role in ("purchase_order", "receiving"):
                        if expected_po and str(
                                data.get("po_id") or "") != expected_po:
                            continue
                    matching.append(step_id)
                if matching:
                    filtered[role] = matching
                else:
                    identity_missing.append(role)
                    filtered[role] = []
            role_candidates = filtered
        missing = [
            role for role, candidates in role_candidates.items()
            if not candidates
        ]
        if identity_missing:
            missing = list(dict.fromkeys([*missing, *identity_missing]))
        ambiguous = [
            role for role, candidates in role_candidates.items()
            if len(candidates) > 1
        ]
        unproven = [
            role for role, candidates in role_candidates.items()
            if candidates and not all(
                candidate_steps.get(candidate, {}).get("verified")
                for candidate in candidates)
        ]
        if missing:
            status = "missing"
        elif ambiguous:
            status = "ambiguous"
        elif unproven:
            status = "missing"
        else:
            status = "ready"
        known_identities: Dict[str, Any] = {}
        for role, candidates in role_candidates.items():
            for step_id in candidates:
                data = next((
                    item.get("data") for item in structured
                    if item["step_id"] == step_id), {}) or {}
                for key in ("po_id", "purchase_order_id", "vendor_id",
                            "invoice_id", "invoice_number"):
                    if data.get(key) not in (None, ""):
                        known_identities[f"{role}.{key}"] = data.get(key)
        missing_roles = missing or unproven
        hint = ""
        if missing_roles:
            subject = (
                known_identities.get("purchase_order.po_id")
                or known_identities.get("receiving.po_id")
                or known_identities.get("invoice.po_id")
                or str(requirement_identity.get("po_id") or ""))
            expected_invoice = str(
                requirement_identity.get("invoice_id") or "").strip()
            if expected_invoice and "invoice" in missing_roles:
                hint = (
                    f"Which authorized source contains invoice "
                    f"{expected_invoice}"
                    + (f" for purchase order {subject}" if subject else "")
                    + "?")
            else:
                hint = (
                    "Which authorized source contains the missing "
                    + ", ".join(missing_roles)
                    + " evidence"
                    + (f" for purchase order {subject}" if subject else "")
                    + "?")
        capabilities.append({
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": status,
            "missing": missing_roles,
            "ambiguous_roles": ambiguous,
            "evidence": structured,
            "roles": {
                role: list(candidates)
                for role, candidates in role_candidates.items()
            },
            "known_identities": known_identities,
            "question_hint": hint,
        })
    else:
        capabilities.append({
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": "unavailable",
            "missing": [],
            "evidence": [],
            "question_hint": "",
        })
    return capabilities


def _operations_from_evidence(assignment: Mapping[str, Any]) -> List[str]:
    return [
        item["operation"] for item in operation_capabilities(assignment)
        if item.get("status") != "unavailable"
    ]

def _binding_business_name(binding: Mapping[str, Any]) -> str:
    return str(
        binding.get("dataset_name") or binding.get("original_file_name")
        or binding.get("resource_id") or "").strip().lower()


def completed_operations(
    assignment: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Operations already applied for the current evidence population.

    A completed quote is not reopened by a wait reply or an unrelated read;
    a genuinely newer version of the same business source keeps it eligible
    for reassessment.
    """
    steps = [
        dict(step) for step in assignment.get("steps") or []
        if isinstance(step, Mapping)
    ]
    by_id = {str(step.get("step_id") or ""): step for step in steps}
    applied_sources = []
    for step in steps:
        if str(step.get("status") or "") != "applied":
            continue
        inputs = step.get("inputs") if isinstance(
            step.get("inputs"), dict) else {}
        binding = inputs.get("resource_binding") if isinstance(
            inputs.get("resource_binding"), dict) else {}
        name = _binding_business_name(binding)
        if name and str(step.get("adapter") or "") in (
                "dataset.read", "workbook.read", "document.read",
                "document.text"):
            applied_sources.append({
                "step_id": str(step.get("step_id") or ""),
                "name": name,
                "version": str(binding.get("source_version") or ""),
            })
    completed: List[Dict[str, Any]] = []
    quote_chains = [
        step for step in steps
        if str(step.get("adapter") or "") == "quote.calculate"
        and str(step.get("status") or "") == "applied"
    ]
    for chain in quote_chains:
        parent_id = (chain.get("depends_on") or [None])[0]
        parent = by_id.get(str(parent_id or "")) or {}
        source_id = (parent.get("depends_on") or [None])[0]
        source = by_id.get(str(source_id or "")) or {}
        source_binding = ((source.get("inputs") or {}).get(
            "resource_binding") or {})
        name = _binding_business_name(source_binding)
        version = str(source_binding.get("source_version") or "")
        newer_version = any(
            item["name"] == name and version
            and item["version"] not in ("", version)
            for item in applied_sources)
        if newer_version:
            continue
        completed.append({
            "operation": "quote_calculation",
            "reason": "applied for the current accepted evidence",
            "step_id": chain.get("step_id"),
        })
        break
    invoice_chains = [
        step for step in steps
        if str(step.get("adapter") or "") == "invoice.reconcile"
        and str(step.get("status") or "") == "applied"
    ]
    if invoice_chains:
        completed.append({
            "operation": "invoice_reconciliation",
            "reason": "applied for the current accepted evidence",
            "step_id": invoice_chains[0].get("step_id"),
        })
    return completed


def context_from_record(
    record: Mapping[str, Any],
    *,
    teaching: Optional[Mapping[str, Any]] = None,
    task_context: Optional[Mapping[str, Any]] = None,
    action_views: Optional[Sequence[Mapping[str, Any]]] = None,
    adapter_views: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build the bounded context from the durable task/assignment record.

    Includes only completed-evidence summaries and bounded row samples; large
    source content stays behind the existing resource handles.
    """
    assignment = dict(record.get("assignment") or {})
    evidence = []
    for step in assignment.get("steps") or []:
        result = step.get("result") if isinstance(
            step.get("result"), dict) else {}
        if not result:
            continue
        evidence_item = {
            "step_id": step.get("step_id"),
            "title": step.get("title"),
            "adapter": step.get("adapter"),
            "status": step.get("status"),
            "summary": result.get("summary"),
            "value": result.get("value"),
            "unit": result.get("unit"),
            "rows": result.get("rows") or [],
            "data": result.get("data") or {},
            "schema": result.get("schema") or [],
            "coverage": result.get("coverage") or {},
            "verification": result.get("verification") or {},
            "artifact": result.get("artifact") or {},
            "truncated": result.get("truncated"),
        }
        data = result.get("data")
        if isinstance(data, Mapping):
            keys = {str(key) for key in data}
            evidence_item["data_keys"] = sorted(keys)[:40]
            evidence_item["data_preview"] = {
                str(key): value for key, value in list(data.items())[:20]
                if isinstance(value, (str, int, float, bool, type(None)))
            }
            if "invoice_id" in keys or "invoice_number" in keys:
                evidence_item["business_role"] = "invoice"
            elif "received_quantity" in keys:
                evidence_item["business_role"] = "receiving"
            elif "po_id" in keys or "purchase_order_id" in keys:
                evidence_item["business_role"] = "purchase_order"
        elif evidence_item.get("rows"):
            evidence_item["business_role"] = "quote_rows"
        evidence.append(evidence_item)
    obligations = []
    for question in (record.get("task_revision") or {}).get(
            "unresolved") or []:
        if question.get("status") == "open":
            obligations.append(question)
    eligibility = operation_capabilities(assignment)
    try:
        from core.employee_business_outcomes import (
            business_requirement_views,
        )

        requirement_views = business_requirement_views(assignment)
    except Exception:  # noqa: BLE001 — read view must not crash
        requirement_views = []
    completed = completed_operations(assignment)
    completed_names = {
        str(item.get("operation") or "") for item in completed}
    for item in eligibility:
        if str(item.get("operation") or "") in completed_names:
            item["status"] = "completed"
            item["completed"] = True
    scoped_sources = scoped_source_views(assignment)
    waiting = []
    for step in assignment.get("steps") or []:
        item = step.get("waiting") if isinstance(
            step.get("waiting"), Mapping) else None
        if str(step.get("status") or "") != "waiting" or not item:
            continue
        waiting.append({"step_id": step.get("step_id"), **dict(item)})
    context = build_employee_context(
        objective=assignment.get("objective") or "",
        employee_id=assignment.get("employee_id") or "",
        agent_id=(assignment.get("provenance") or {}).get("agent_id"),
        workspace_id=assignment.get("workspace_id") or "",
        tenant_id=assignment.get("tenant_id") or "",
        teaching=teaching or assignment.get("teaching_snapshot") or {},
        sources=scoped_sources,
        task_context=task_context or {},
        criteria=assignment.get("completion_criteria") or [],
        facts=assignment.get("facts") or [],
        open_obligations=obligations,
        authorized_actions=assignment.get("authorized_actions") or [],
        action_views=action_views,
        adapter_views=adapter_views,
        evidence_results=evidence,
        budget=assignment.get("budget") or {},
        task_version=record.get("task_version"),
        plan_revision=assignment.get("plan_revision"),
        existing_step_ids=[
            str(step.get("step_id") or "")
            for step in assignment.get("steps") or []
            if step.get("step_id")
        ],
        stage="follow_up" if evidence else "discovery",
        available_work_requests=[
            item["operation"] for item in eligibility
            if item.get("status") != "unavailable"],
        operation_eligibility=eligibility,
        waiting=waiting,
        completed_operations=completed,
        business_requirements=requirement_views,
    )

    # Answers remain task evidence, not teaching, authority or completed work.
    # Keep the bounded, server-settled value visible after the OPEN question
    # leaves the obligation view. Otherwise a same-job continuation loses the
    # very information that caused it to resume.
    resolved = [
        {key: str(question.get(key) or "")[:limit]
         for key, limit in (
             ("question_id", 120), ("concept", 120), ("item", 200),
             ("question", 400), ("resolution", 400),
             ("resolution_value", 400), ("resolved_at", 80))}
        for question in (record.get("task_revision") or {}).get("unresolved") or []
        if isinstance(question, Mapping) and question.get("status") == "resolved"
    ][-MAX_CONTEXT_OBLIGATIONS:]
    if resolved:
        context["resolved_obligations"] = resolved
    return context


def _context_source(context: Mapping[str, Any], source_id: str) -> Optional[Dict]:
    for source in context.get("sources") or []:
        if str(source.get("source_id") or "") == source_id:
            return dict(source)
    return None


def _context_action(context: Mapping[str, Any], action: str) -> Optional[Dict]:
    for item in context.get("action_views") or []:
        if str(item.get("action") or "") == action:
            return dict(item)
    return None


def validate_employee_proposal(
    proposal: Any,
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return ``{"valid", "errors", "proposal"}``; never adopt on errors."""
    errors: List[str] = []
    if isinstance(proposal, BaseModel):
        proposal = proposal.model_dump()
    if not isinstance(proposal, Mapping):
        return {"valid": False, "errors": ["proposal must be an object"],
                "proposal": None}
    try:
        normalized = EmployeeWorkProposal.model_validate(dict(proposal))
    except Exception as exc:  # pydantic validation is the schema boundary
        return {"valid": False,
                "errors": [f"proposal schema: {_text(exc, 800)}"],
                "proposal": None}
    kind = normalized.proposal_kind
    if kind in ("evidence_read", "evidence_and_clarification"):
        if not normalized.evidence_reads:
            errors.append("evidence_read proposal requires at least one read")
    if kind in ("clarification", "evidence_and_clarification"):
        if normalized.clarification is None:
            errors.append("clarification proposal requires a question")
        elif not normalized.clarification.question.strip():
            errors.append("clarification question is empty")
    if len(normalized.evidence_reads) > MAX_EVIDENCE_READS:
        errors.append(f"at most {MAX_EVIDENCE_READS} evidence reads are allowed")
    seen_steps = set()
    for index, read in enumerate(normalized.evidence_reads):
        where = f"evidence_reads[{index}]"
        step_id = read.step_id.strip()
        if not step_id:
            errors.append(f"{where} requires a stable step_id")
        elif step_id in seen_steps:
            errors.append(f"duplicate evidence step_id {step_id!r}")
        else:
            seen_steps.add(step_id)
        source_id = read.source_id.strip()
        action = read.action.strip()
        if source_id and action.lower() in ("retrieve", "read"):
            # A source read plus the generic operation name is one intent, not
            # two capabilities. Normalize the redundant operation label.
            read.action = ""
            action = ""
        if source_id and action:
            errors.append(
                f"{where} must choose a source read or an action, not both")
        if not source_id and not action:
            errors.append(f"{where} requires source_id or action")
        if source_id and _context_source(context, source_id) is None:
            errors.append(f"{where} names unknown source_id {source_id!r}")
        if action:
            action_view = _context_action(context, action)
            if action_view is None:
                errors.append(f"{where} names unknown action {action!r}")
            elif str(action_view.get("effect") or "").lower() not in (
                    "read_only", "retrieve"):
                errors.append(
                    f"{where} action {action!r} is not read-only; effects "
                    "cannot be proposed by the reasoning layer")
            if not isinstance(read.arguments, dict):
                errors.append(f"{where} arguments must be an object")
        if read.requires:
            try:
                from core.assignment_readiness import normalize_requirements
                normalize_requirements(read.requires)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{where} requirements: {_text(exc, 300)}")
    return {
        "valid": not errors,
        "errors": errors,
        "proposal": normalized.model_dump() if not errors else None,
    }


def _deterministic_proposal(context: Mapping[str, Any]) -> Dict[str, Any]:
    sources = list(context.get("sources") or [])
    if sources:
        source = sources[0]
        return {
            "proposal_kind": "evidence_read",
            "reason": (
                "No model proposal is available; read the strongest "
                "authorized source so the employee can establish evidence "
                "without guessing."),
            "evidence_reads": [{
                "step_id": "evidence-1",
                "title": (
                    f"Read {source.get('file_name') or source.get('source_id')}"
                    f" ({source.get('sheet') or 'source'})"),
                "source_id": source.get("source_id"),
                "reason": "Authorized evidence is the safest useful first "
                          "step.",
            }],
        }
    return {
        "proposal_kind": "clarification",
        "reason": "No authorized source is available to establish the "
                  "objective's material evidence.",
        "clarification": {
            "question": (
                "Which authorized source should I use for this objective?"),
            "concept": "source_access",
            "unblocks": "Reading the governing evidence and preparing the "
                        "requested result.",
            "expected_answer_type": "resource selection",
        },
    }


def _proposal_prompt(context: Mapping[str, Any]) -> str:
    return (
        "You are the accountable employee's planning reasoner. Choose the "
        "next useful supported work from the bounded context below.\n\n"
        "Rules:\n"
        "- Propose at most five READ-ONLY evidence reads, one targeted "
        "business clarification, or both.\n"
        "- You cannot execute a tool, create an external effect, grant "
        "permission, invent source/action IDs, or provide receipts.\n"
        "- Each evidence read is EITHER a source read or a registered read "
        "action, never both: set source_id and leave action empty, or set "
        "action and leave source_id empty. Do not write 'retrieve' in action "
        "when using source_id.\n"
        "- Use only source_id values and action names present in the context.\n"
        "- Ask a question only when the missing fact materially changes the "
        "result or allowed action and cannot be read from an authorized "
        "source.\n"
        "- A question must name the exact fact/choice and what it unblocks.\n"
        "- Do not ask the user to choose implementation steps or provide "
        "data already available from an authorized source.\n"
        "- context.sources entries carry read:true/false. When the accepted "
        "evidence is incomplete and unread authorized sources remain, select "
        "those source_id handles instead of asking the user or re-reading a "
        "source already read.\n"
        "- When context.unread_sources is non-empty, every source_id in this "
        "proposal MUST come from that list. Do not select a source whose "
        "read flag is true.\n"
        "- Return JSON matching this shape: "
        '{"proposal_kind":"evidence_read|clarification|'
        'evidence_and_clarification","reason":"...",'
        '"evidence_reads":[{"step_id":"evidence-1","title":"...",'
        '"source_id":"..." OR "", "action":"..." OR "", '
        '"arguments":{},"requires":[],"reason":"..."}],'
        '"clarification":{"question":"...","concept":"...",'
        '"unblocks":"...","expected_answer_type":"..."}|null}\n\n'
        "CONTEXT:\n" + json.dumps(context, sort_keys=True, default=str)
    )


def _routing_snapshot(
    capture: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Routing view for a result, including an explicit child-task capture."""
    try:
        from core.llm.pinned_planning import routing_snapshot

        return routing_snapshot(capture)
    except Exception:  # noqa: BLE001 — diagnostics are optional
        return {"mode": "deterministic"}


def business_routing_notice(
    routing: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """A business-safe explanation for a reasoning route that was unavailable.

    Never includes provider exceptions, internal scores or model branding.
    A route failure is a configuration/availability fact: the employee's
    job, completed work and questions stay intact.
    """
    if not isinstance(routing, Mapping):
        return None
    error = routing.get("error")
    if not isinstance(error, Mapping) or not error.get("code"):
        return None
    code = str(error.get("code") or "")[:120]
    if code in ("no_suitable_configured_model", "pin_failed"):
        return {
            "state": "configuration_required",
            "code": code,
            "message": (
                "No configured model currently meets this work's "
                "requirements. The employee's job, completed work and "
                "questions are preserved."),
            "next_action": (
                "Add or enable an eligible model in settings, then resume "
                "the same job."),
        }
    return {
        "state": "reasoning_unavailable",
        "code": code,
        "message": (
            "The reasoning step is temporarily unavailable. The employee's "
            "job, completed work and questions are preserved."),
        "next_action": (
            "Resume the same job when the reasoning service is available, "
            "or supply the requested business answer."),
    }


async def propose_employee_work(
    context: Mapping[str, Any],
    *,
    llm_service: Any = None,
    deadline_seconds: float = 120.0,
    provider_model: Optional[Sequence[str]] = None,
    attempt_journal: Any = None,
    strict_pin: Optional[bool] = None,
) -> Dict[str, Any]:
    """Propose supported read/clarification work; never an effect.

    The model receives only the bounded context. A provider/protocol failure
    falls back to a deterministic authorized read (or a source-access
    clarification), and the result records which path produced it. The
    caller's deadline is enforced here, and the raw dispatch/parsed/failure
    events are journaled under one attempt id like adaptation.
    """
    journal = attempt_journal
    if journal is None:
        try:
            from core.employee_attempt_journal import AttemptJournal

            journal = AttemptJournal()
        except Exception:  # noqa: BLE001 — diagnostics are optional
            journal = None

    def _observe(event: str, **fields: Any) -> None:
        if journal is None:
            return
        if event == "failure":
            exc = fields.pop("exception", None)
            if exc is not None:
                journal.failure(exc, **fields)
                return
        journal.record(event, **fields)

    #: Request-owned provenance. The awaited call may run in a child task
    #: (asyncio.wait_for), whose ContextVar writes are not visible here. The
    #: wrapper writes the final attempt's receipt into this shared mapping.
    provenance: Dict[str, Any] = {}
    if llm_service is not None:
        # Seed only server-owned REQUEST facts for a call that will actually
        # be attempted. No LLM service means a genuinely deterministic result,
        # not an "unpinned" route.
        provenance["mode"] = "pinned" if provider_model else "unpinned"
        if provider_model and len(provider_model) >= 2:
            provenance["requested_route"] = {
                "provider": provider_model[0], "model": provider_model[1]}
        deadline_error: Optional[Dict[str, Any]] = None
        try:
            from core.llm.pinned_planning import pinned_structured_call
            call = pinned_structured_call(
                llm_service,
                prompt=_proposal_prompt(context),
                response_model=EmployeeWorkProposal,
                system_instruction=(
                    "You are a read-only employee work planner. You never "
                    "execute, authorize or invent facts. Return JSON only."),
                call_kwargs=(
                    {"provider_model": tuple(provider_model)}
                    if provider_model else None),
                extra_kwargs={
                    "output_mode": "json",
                    "cascade": False,
                    "allow_moa": False,
                    "max_tokens": 1800,
                },
                log_label="employee work proposal",
                task_type="planning",
                workspace_id=context.get("identity", {}).get("workspace_id"),
                tenant_id=context.get("identity", {}).get("tenant_id"),
                attempt_observer=_observe,
                provenance=provenance,
                strict_pin=strict_pin,
            )
            budget = max(0.0, float(deadline_seconds or 0.0))
            result = (
                await asyncio.wait_for(call, timeout=budget)
                if budget > 0 else await call)
        except asyncio.TimeoutError:
            deadline_error = {
                "code": "deadline_cancelled",
                "detail": (
                    "the employee evidence-selection stage exhausted its "
                    "caller deadline"),
            }
            try:
                from core.llm.model_provenance import set_routing_error

                set_routing_error(
                    deadline_error["code"], deadline_error["detail"])
            except Exception:  # noqa: BLE001 — diagnostics are optional
                pass
            result = None
        except Exception:  # noqa: BLE001 — the fallback remains explicit
            result = None
        routing = _routing_snapshot(provenance)
        if result is None:
            # A failed boundary must not lend a stale generation id or a
            # served route to the deterministic fallback.
            routing["served_route"] = None
            routing["routing_result_id"] = None
            if deadline_error is not None:
                routing["error"] = deadline_error
            elif not routing.get("error"):
                routing["error"] = {
                    "code": "provider_failure",
                    "detail": "the configured routes produced no usable result",
                }
        if result is not None:
            checked = validate_employee_proposal(result, context)
            if checked["valid"]:
                return {
                    "proposal": checked["proposal"],
                    "source": "model",
                    "technical_fallback": False,
                    "errors": [],
                    "attempt_id": getattr(journal, "attempt_id", None),
                    "routing_result_id": routing.get("routing_result_id"),
                    "routing": routing,
                }
            # The model produced an object that parsed but failed the
            # consumer's deterministic contract. Record THAT model attempt as
            # a semantic failure; the deterministic fallback below is not
            # credited as model success.
            evaluation = None
            try:
                from core.employee_routing_feedback import (
                    classify_evidence_errors,
                    record_attempt_evaluation,
                )

                evaluation = await record_attempt_evaluation(
                    {"source": "model", "routing": routing},
                    stage="employee_evidence_selection",
                    evaluation="failed",
                    failure_kind=classify_evidence_errors(
                        checked["errors"]),
                    detail="; ".join(checked["errors"]),
                    workspace_id=context.get("identity", {}).get(
                        "workspace_id"),
                    tenant_id=context.get("identity", {}).get("tenant_id"),
                    extra_features={
                        "proposal_errors": list(checked["errors"])[:8],
                        "attempt_id": getattr(journal, "attempt_id", None),
                    },
                )
            except Exception:  # noqa: BLE001 — evidence must not break work
                evaluation = None
            if journal is not None:
                journal.record(
                    "evaluation", stage="employee_evidence_selection",
                    evaluation=evaluation)
            fallback = _deterministic_proposal(context)
            return {
                "proposal": fallback,
                "source": "deterministic",
                "technical_fallback": True,
                "errors": checked["errors"],
                "attempt_id": getattr(journal, "attempt_id", None),
                "routing_result_id": routing.get("routing_result_id"),
                "evaluation": evaluation,
                "routing": routing,
            }
    fallback = _deterministic_proposal(context)
    routing = _routing_snapshot(provenance)
    errors = []
    routing_error = routing.get("error")
    if isinstance(routing_error, Mapping):
        detail = str(routing_error.get("detail") or "").strip()
        if detail:
            errors = [detail]
    if journal is not None:
        journal.record(
            "attempt-summary", source="deterministic", errors=errors)
    return {
        "proposal": fallback,
        "source": "deterministic",
        "technical_fallback": llm_service is not None,
        "errors": errors,
        "attempt_id": getattr(journal, "attempt_id", None),
        "routing_result_id": routing.get("routing_result_id"),
        "routing": routing,
    }


def compile_employee_proposal(
    proposal: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    sources: Sequence[Mapping[str, Any]],
    facts: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Turn a validated proposal into ``plan_assignment`` descriptors."""
    checked = validate_employee_proposal(proposal, context)
    if not checked["valid"]:
        return {"valid": False, "errors": checked["errors"], "plan_kwargs": None}
    normalized = checked["proposal"]
    reads = list(normalized.get("evidence_reads") or [])
    selected_sources: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    source_ids = {
        _source_id(source): source
        for source in (sources or [])
        if _source_id(source)
    }
    selected_ids = set()
    for read in reads:
        source_id = str(read.get("source_id") or "")
        if source_id:
            source = source_ids.get(source_id)
            if source is None:
                return {
                    "valid": False,
                    "errors": [f"compiled source {source_id!r} disappeared"],
                    "plan_kwargs": None,
                }
            if source_id in selected_ids:
                # The same handle selected twice is one durable read.
                continue
            if selected_ids:
                # The first proposal selects one evidence read. Other
                # authorized handles stay in the retained scope for the next
                # bounded proposal instead of being read in bulk or lost.
                break
            selected_ids.add(source_id)
            item = dict(source)
            item["requires"] = list(read.get("requires") or [])
            selected_sources.append(item)
        elif read.get("action"):
            actions.append({
                "step_id": read.get("step_id"),
                "title": read.get("title") or f"Read via {read['action']}",
                "action": read["action"],
                "arguments": dict(read.get("arguments") or {}),
                "requires": list(read.get("requires") or []),
            })
    if not selected_sources:
        # The existing planner requires an authorized source even for an
        # action read; use the context's first source as the declared scope.
        first = (context.get("sources") or [None])[0]
        if first:
            source = source_ids.get(str(first.get("source_id") or ""))
            if source is not None:
                selected_sources = [dict(source)]
    return {
        "valid": True,
        "errors": [],
        "plan_kwargs": {
            "sources": selected_sources,
            "actions": actions,
            "facts": list(facts or []),
            "clarification": normalized.get("clarification"),
            "proposal": normalized,
        },
    }


def employee_job_view(
    assignment: Mapping[str, Any],
    *,
    record: Optional[Mapping[str, Any]] = None,
    open_obligations: Optional[Sequence[Mapping[str, Any]]] = None,
    routing: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """The bounded business view used by the normal job surface."""
    steps = list(assignment.get("steps") or [])
    try:
        from core.task_outcome_contract import build_assignment_outcome
        business_outcome = build_assignment_outcome(
            dict(assignment), dict(record or {}))
    except Exception:  # noqa: BLE001 — a read view must not crash
        business_outcome = None
    routing_notice = business_routing_notice(routing)
    if str(assignment.get("status") or "") in ("completed", "cancelled"):
        # The route outcome is still in the audit history, but a finished or
        # cancelled job must not show an "incomplete configuration" notice.
        routing_notice = None
    return {
        "objective": assignment.get("objective"),
        "identity": {
            "employee_id": assignment.get("employee_id"),
            "workspace_id": assignment.get("workspace_id"),
            "tenant_id": assignment.get("tenant_id"),
            "execution_owner": "assignment",
        },
        "criteria": list(assignment.get("completion_criteria") or []),
        "facts": list(assignment.get("facts") or []),
        "sources": [
            _source_view(source) for source in scoped_source_views(assignment)
        ],
        "steps": [
            {
                "step_id": step.get("step_id"),
                "title": step.get("title"),
                "status": step.get("status"),
                "required": bool(step.get("required", True)),
                "effect": step.get("effect"),
                "requires": list(step.get("requires") or []),
                "readiness": step.get("readiness"),
                "readiness_blocker": step.get("readiness_blocker"),
                "result_summary": (
                    (step.get("result") or {}).get("summary")
                    if isinstance(step.get("result"), dict) else None),
            }
            for step in steps
        ],
        "open_obligations": [
            dict(item) for item in (open_obligations or [])
            if isinstance(item, Mapping)
        ],
        "business_requirements": business_requirement_views(assignment),
        "waiting": [
            {
                "step_id": step.get("step_id"),
                "fact": (step.get("waiting") or {}).get("fact"),
                "subject": (step.get("waiting") or {}).get("subject"),
                "party": (step.get("waiting") or {}).get("party"),
                "detail": (step.get("waiting") or {}).get("detail"),
                "blocks": (step.get("waiting") or {}).get("blocks"),
                "expected_answer_type": (step.get("waiting") or {}).get(
                    "expected_answer_type"),
                "correlation_id": (step.get("waiting") or {}).get(
                    "correlation_id"),
                "since": (step.get("waiting") or {}).get("since"),
            }
            for step in steps
            if str(step.get("status") or "") == "waiting"
            and isinstance(step.get("waiting"), Mapping)
            and (step.get("waiting") or {}).get("correlation_id")
        ],
        "ready_work": [
            {
                "operation": item.get("operation"),
                "label": item.get("label") or item.get("operation"),
            }
            for item in operation_capabilities(assignment)
            if str(item.get("status") or "") == "ready"
        ],
        "budget": dict(assignment.get("budget") or {}),
        "status": assignment.get("status"),
        "task_version": (
            record.get("task_version") if isinstance(record, Mapping)
            else None),
        "plan_revision": assignment.get("plan_revision"),
        "business_outcome": business_outcome,
        "routing_notice": routing_notice,
    }
