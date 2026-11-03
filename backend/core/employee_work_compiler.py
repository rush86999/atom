"""Deterministic compilation of typed employee work requests.

Business requests become existing assignment-plan patches: unique step IDs,
adapters, dependencies, result references, effect classes and readiness
predicates are issued here. The model never writes execution mechanics.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from pydantic import ValidationError

from core.assignment_plan import canonical_sha256, step_by_id
from core.assignment_readiness import evaluate_step_readiness
from core.employee_work_requests import (
    InvoiceReconciliationRequest,
    QuoteCalculationRequest,
)


class WorkRequestCompileError(ValueError):
    pass


def _step_result(assignment: Mapping[str, Any], step_id: str) -> Dict:
    step = step_by_id(dict(assignment), step_id)
    if step is None:
        raise WorkRequestCompileError(f"unknown evidence step {step_id!r}")
    if step.get("status") not in ("applied", "skipped"):
        raise WorkRequestCompileError(
            f"evidence step {step_id!r} is {step.get('status')}, not applied")
    result = step.get("result")
    if not isinstance(result, dict) or not result:
        raise WorkRequestCompileError(
            f"evidence step {step_id!r} has no durable result")
    return result


def _columns(result: Mapping[str, Any]) -> List[str]:
    columns = []
    for item in result.get("schema") or []:
        if isinstance(item, Mapping):
            name = item.get("column") or item.get("name")
            if name and str(name) not in columns:
                columns.append(str(name))
    for row in result.get("rows") or []:
        if isinstance(row, Mapping):
            for key in row:
                if str(key) not in columns:
                    columns.append(str(key))
    return columns


def _require_verified(assignment: Mapping[str, Any], step_id: str) -> None:
    probe = {
        "step_id": "__request_probe__",
        "requires": [{"kind": "receipt", "step_id": step_id,
                      "require": "verified"}],
    }
    decision = evaluate_step_readiness(
        probe, dict(assignment), task_authorization="read_only")
    if not decision.get("eligible"):
        raise WorkRequestCompileError(
            f"evidence step {step_id!r} does not carry verified proof: "
            + "; ".join(
                str(item.get("reason") or item.get("kind"))
                for item in decision.get("blockers") or []))


def _unique_id(assignment: Mapping[str, Any], base: str) -> str:
    existing = {
        str(step.get("step_id") or "")
        for step in assignment.get("steps") or []
    }
    if base not in existing:
        return base
    index = 2
    while f"{base}-{index}" in existing:
        index += 1
    return f"{base}-{index}"


def _evidence_ids(request: Any) -> List[str]:
    if isinstance(request, QuoteCalculationRequest):
        return [request.source_step_id]
    if isinstance(request, InvoiceReconciliationRequest):
        return [
            item for item in (
                request.invoice_step_id,
                request.purchase_order_step_id,
                request.receiving_step_id,
                request.vendor_step_id,
                request.coa_step_id,
                request.period_step_id,
            ) if item
        ]
    return []


def _base_patch(
    assignment: Mapping[str, Any], request: Any, context: Mapping[str, Any],
) -> Dict[str, Any]:
    digest = canonical_sha256(request.model_dump())
    return {
        "patch_id": f"work-{digest[:20]}",
        "base_task_version": int(context.get("task_version") or 0),
        "base_plan_revision": int(
            context.get("plan_revision")
            or assignment.get("plan_revision") or 1),
        "reason": f"Compiled {request.operation} request from typed work",
        "observations": [
            {"kind": "work_request", "operation": request.operation},
            *[
                {"kind": "evidence", "step_id": step_id}
                for step_id in _evidence_ids(request)
            ],
        ],
        "invalidate_steps": [],
        "remove_steps": [],
        "add_steps": [],
        "add_facts": [],
        "set_requires": {},
    }


def _quote_patch(
    request: QuoteCalculationRequest,
    assignment: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    result = _step_result(assignment, request.source_step_id)
    if request.require_verified_source:
        _require_verified(assignment, request.source_step_id)
    available = set(_columns(result))
    required = {"item_id", "quantity", "unit_price"}
    missing = sorted(key for key in required if not request.columns.get(key))
    if missing:
        raise WorkRequestCompileError(
            f"quote mapping is missing required fields {missing}")
    allowed = {
        "item_id", "quantity", "unit_price", "currency", "description",
        "unit", "pack_size", "price_basis", "category", "discount",
    }
    for key, column in request.columns.items():
        if key not in allowed:
            raise WorkRequestCompileError(
                f"unsupported quote field mapping {key!r}")
        if available and str(column) not in available:
            raise WorkRequestCompileError(
                f"quote mapping {key!r} names column {column!r} absent from "
                f"the accepted source schema")
    if not request.currency.strip():
        raise WorkRequestCompileError("quote currency must be explicit")
    if not request.freight.authority_ref.strip():
        raise WorkRequestCompileError(
            "quote freight requires a taught/authorized authority")
    if request.tax.basis == "rate" and (
            not request.tax.value.strip()
            or not request.tax.authority_ref.strip()):
        raise WorkRequestCompileError(
            "quote tax rate requires a value and authority")
    map_id = _unique_id(assignment, "quote-lines")
    calc_id = _unique_id(assignment, "quote-total")
    patch = _base_patch(assignment, request, context)
    map_inputs = {
        "rows": f"${{{request.source_step_id}.rows}}",
        "columns": dict(request.columns),
        "defaults": {"currency": request.currency},
    }
    tax_input = (
        {"basis": "none"} if request.tax.basis == "none"
        else {"basis": request.tax.basis, "value": request.tax.value,
              "authority_ref": request.tax.authority_ref}
    )
    patch["add_steps"] = [
        {
            "step_id": map_id,
            "title": "Map accepted evidence to quote lines",
            "operation_type": "calculate",
            "adapter": "quote.lines_from_rows",
            "depends_on": [request.source_step_id],
            "inputs": map_inputs,
            "effect": "local",
            "requires": (
                [{"kind": "receipt", "step_id": request.source_step_id,
                  "require": "verified"}]
                if request.require_verified_source else []),
            "required": True,
        },
        {
            "step_id": calc_id,
            "title": "Calculate the evidence-backed quote total",
            "operation_type": "calculate",
            "adapter": "quote.calculate",
            "depends_on": [map_id],
            "inputs": {
                "line_items": f"${{{map_id}.line_items}}",
                "currency": request.currency,
                "freight": request.freight.value,
                "tax": tax_input,
            },
            "effect": "local",
            "requires": [],
            "required": True,
        },
    ]
    return patch


def _invoice_patch(
    request: InvoiceReconciliationRequest,
    assignment: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    for step_id in (
            request.invoice_step_id, request.purchase_order_step_id,
            request.receiving_step_id):
        _step_result(assignment, step_id)
        if request.require_verified_evidence:
            _require_verified(assignment, step_id)
    reconcile_id = _unique_id(assignment, "invoice-reconcile")
    patch = _base_patch(assignment, request, context)
    patch["add_steps"] = [{
        "step_id": reconcile_id,
        "title": "Reconcile invoice against purchase and receiving evidence",
        "operation_type": "calculate",
        "adapter": "invoice.reconcile",
        "depends_on": list(dict.fromkeys([
            request.invoice_step_id, request.purchase_order_step_id,
            request.receiving_step_id,
            *([request.vendor_step_id] if request.vendor_step_id else []),
            *([request.coa_step_id] if request.coa_step_id else []),
            *([request.period_step_id] if request.period_step_id else []),
        ])),
        "inputs": {
            "invoice": f"${{{request.invoice_step_id}.data}}",
            "purchase_order": (
                f"${{{request.purchase_order_step_id}.data}}"),
            "receiving": f"${{{request.receiving_step_id}.data}}",
            "invoice_fields": dict(request.invoice_fields) or {
                "po_id": "po_id", "invoice_id": "invoice_id",
                "quantity": "quantity", "unit_price": "unit_price",
                "freight": "freight", "currency": "currency",
                "version": "version", "resource_id": "resource_id",
            },
            "purchase_order_fields": (
                dict(request.purchase_order_fields) or {
                    "po_id": "po_id", "vendor_id": "vendor_id"}),
            "receiving_fields": (
                dict(request.receiving_fields) or {
                    "po_id": "po_id",
                    "received_quantity": "received_quantity",
                    "version": "version"}),
            "currency": request.currency or "",
        },
        "effect": "local",
        "requires": [
            {"kind": "receipt", "step_id": step_id, "require": "verified"}
            for step_id in (
                request.invoice_step_id, request.purchase_order_step_id,
                request.receiving_step_id)
        ] if request.require_verified_evidence else [],
        "required": True,
    }]
    return patch


def compile_work_request_patch(
    request: Any,
    assignment: Mapping[str, Any],
    *,
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compile one typed request into a plan patch.

    Raises ``WorkRequestCompileError`` for an invalid request/reference or a
    source that does not carry the required proof.
    """
    context = dict(context or {})
    if isinstance(request, QuoteCalculationRequest):
        return _quote_patch(request, assignment, context)
    if isinstance(request, InvoiceReconciliationRequest):
        return _invoice_patch(request, assignment, context)
    try:
        if isinstance(request, Mapping):
            operation = str(request.get("operation") or "")
            if operation == "quote_calculation":
                return _quote_patch(
                    QuoteCalculationRequest.model_validate(dict(request)),
                    assignment, context)
            if operation == "invoice_reconciliation":
                return _invoice_patch(
                    InvoiceReconciliationRequest.model_validate(
                        dict(request)), assignment, context)
        raise WorkRequestCompileError(
            "unsupported work request operation; expected quote_calculation "
            "or invoice_reconciliation")
    except ValidationError as exc:
        raise WorkRequestCompileError(f"invalid work request: {exc}") from exc
