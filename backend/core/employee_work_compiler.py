"""Deterministic compilation of typed employee work requests.

Business requests become existing assignment-plan patches: unique step IDs,
adapters, dependencies, result references, effect classes and readiness
predicates are issued here. The model never writes execution mechanics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import ValidationError

from core.assignment_plan import canonical_sha256, step_by_id
from core.assignment_readiness import evaluate_step_readiness
from core.employee_money_terms import (
    ROLE_CURRENCY,
    ROLE_FREIGHT_AMOUNT,
    ROLE_TAX_AMOUNT,
    ROLE_TAX_EXEMPTION,
    ROLE_TAX_RATE,
    TermContractError,
    canonical_role,
    resolve_accepted_term,
    role_dimension,
    validate_role_value,
)
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
    if step.get("status") != "applied":
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


def _term_candidate(
    assignment: Mapping[str, Any], context: Mapping[str, Any],
    authority_ref: str, label: str,
) -> Dict[str, Any]:
    """Resolve one term id against the job's accepted teaching/facts."""
    teaching = (
        assignment.get("teaching_snapshot")
        or context.get("teaching") or {})
    facts = assignment.get("facts") or context.get("facts") or []
    try:
        return resolve_accepted_term(
            authority_ref, teaching=teaching, facts=facts,
            assignment=assignment, now=datetime.now(timezone.utc))
    except TermContractError as exc:
        raise WorkRequestCompileError(f"{label} {exc}") from exc


def _require_role(
    term: Mapping[str, Any], roles: Any, label: str,
) -> str:
    """Compare normalized roles, never raw alias spellings.

    ``resolve_accepted_term`` already canonicalizes the term's declared role
    (for example ``freight_amount``/``shipping`` -> freight). Normalizing the
    expected set the same way means a valid alias can never be rejected just
    because the two sides spell the same business role differently.
    """
    allowed = (roles,) if isinstance(roles, str) else tuple(roles or ())
    canonical_allowed = {
        canonical for canonical in (
            canonical_role(role) for role in allowed)
        if canonical
    }
    actual = canonical_role(term.get("role"))
    if actual is None or actual not in canonical_allowed:
        raise WorkRequestCompileError(
            f"{label} term {term.get('term_id')!r} has semantic role "
            f"{term.get('role')!r}; expected one of "
            f"{sorted(canonical_allowed)!r}. A money term cannot authorize "
            "a different field.")
    return actual


def _resolved_money(
    assignment: Mapping[str, Any], context: Mapping[str, Any],
    authority_ref: str, label: str, currency: str, roles: Any,
) -> Dict[str, Any]:
    term = _term_candidate(assignment, context, authority_ref, label)
    canonical = _require_role(term, roles, label)
    ref = str(term.get("term_id") or "")
    term_currency = str(term.get("currency") or "").strip().upper()
    if term_currency and str(currency or "").strip().upper() != term_currency:
        raise WorkRequestCompileError(
            f"{label} authority {ref!r} is denominated in {term_currency!r}, "
            f"not the quote currency {currency!r}")
    try:
        value = validate_role_value(canonical, term.get("value"))
    except TermContractError as exc:
        raise WorkRequestCompileError(f"{label} {exc}") from exc
    term["value"] = str(value)
    term["currency"] = term_currency or str(currency or "").strip().upper()
    term["role"] = canonical
    term["dimension"] = role_dimension(canonical)
    return term


def _resolved_currency(
    assignment: Mapping[str, Any], context: Mapping[str, Any],
    authority_ref: str, label: str,
) -> Dict[str, Any]:
    term = _term_candidate(assignment, context, authority_ref, label)
    canonical = _require_role(term, (ROLE_CURRENCY,), label)
    try:
        value = validate_role_value(ROLE_CURRENCY, term.get("value"))
    except TermContractError as exc:
        raise WorkRequestCompileError(f"{label} {exc}") from exc
    term["value"] = value
    term["currency"] = value
    term["role"] = canonical
    term["dimension"] = "currency"
    return term


def _resolved_exemption(
    assignment: Mapping[str, Any], context: Mapping[str, Any],
    authority_ref: str, label: str,
) -> Dict[str, Any]:
    term = _term_candidate(assignment, context, authority_ref, label)
    canonical = _require_role(term, (ROLE_TAX_EXEMPTION,), label)
    try:
        value = validate_role_value(
            ROLE_TAX_EXEMPTION, term.get("value"))
    except TermContractError as exc:
        raise WorkRequestCompileError(f"{label} {exc}") from exc
    term["value"] = value
    term["currency"] = ""
    term["role"] = canonical
    term["dimension"] = "exemption"
    return term


def _same_money(left: Any, right: Any) -> bool:
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError):
        return False


def _quote_patch(
    request: QuoteCalculationRequest,
    assignment: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    result = _step_result(assignment, request.source_step_id)
    # Governed business operations always require verified evidence; this is
    # a server policy, not a model-selectable option.
    _require_verified(assignment, request.source_step_id)
    available = set(_columns(result))
    columns = (
        request.columns.model_dump(exclude_none=True)
        if hasattr(request.columns, "model_dump")
        else dict(request.columns or {}))
    required = {"item_id", "quantity", "unit_price"}
    missing = sorted(key for key in required if not columns.get(key))
    if missing:
        raise WorkRequestCompileError(
            f"quote mapping is missing required fields {missing}")
    allowed = {
        "item_id", "quantity", "unit_price", "currency", "description",
        "unit", "pack_size", "price_basis", "category", "discount",
    }
    for key, column in columns.items():
        if key not in allowed:
            raise WorkRequestCompileError(
                f"unsupported quote field mapping {key!r}")
        if available and str(column) not in available:
            raise WorkRequestCompileError(
                f"quote mapping {key!r} names column {column!r} absent from "
                f"the accepted source schema")
    if not request.currency.strip():
        raise WorkRequestCompileError("quote currency must be explicit")
    currency_term = _resolved_currency(
        assignment, context, "currency", "quote currency")
    if str(request.currency).strip().upper() != currency_term["value"]:
        raise WorkRequestCompileError(
            f"quote currency {request.currency!r} does not match the "
            f"accepted teaching currency {currency_term['value']!r}")
    freight = _resolved_money(
        assignment, context, request.freight.authority_ref, "quote freight",
        request.currency, (ROLE_FREIGHT_AMOUNT,))
    if not _same_money(request.freight.value, freight["value"]):
        raise WorkRequestCompileError(
            f"quote freight {request.freight.value!r} does not match the "
            f"accepted term {freight['value']!r}")
    if request.freight.currency and str(
            request.freight.currency).strip().upper() != str(
            request.currency).strip().upper():
        raise WorkRequestCompileError(
            "quote freight currency must match the quote currency")
    if request.tax.basis == "none":
        tax = _resolved_exemption(
            assignment, context, request.tax.authority_ref,
            "quote tax none")
        tax_input = {"basis": "none"}
    elif request.tax.basis == "rate":
        tax = _resolved_money(
            assignment, context, request.tax.authority_ref,
            "quote tax rate", request.currency, (ROLE_TAX_RATE,))
        if not str(request.tax.value).strip():
            raise WorkRequestCompileError(
                "quote tax rate requires the taught rate value")
        if not _same_money(request.tax.value, tax["value"]):
            raise WorkRequestCompileError(
                f"quote tax rate {request.tax.value!r} does not match the "
                f"accepted term {tax['value']!r}")
        tax_input = {"basis": "rate", "rate": tax["value"],
                     "authority_ref": request.tax.authority_ref}
    else:
        tax = _resolved_money(
            assignment, context, request.tax.authority_ref,
            "quote tax amount", request.currency, (ROLE_TAX_AMOUNT,))
        if not str(request.tax.value).strip():
            raise WorkRequestCompileError(
                "quote tax amount requires the taught amount value")
        if not _same_money(request.tax.value, tax["value"]):
            raise WorkRequestCompileError(
                f"quote tax amount {request.tax.value!r} does not match the "
                f"accepted term {tax['value']!r}")
        tax_input = {"basis": "amount", "amount": tax["value"],
                     "authority_ref": request.tax.authority_ref}
    term_receipt = {
        "currency": dict(currency_term),
        "freight": dict(freight),
        "tax": dict(tax),
    }
    map_id = _unique_id(assignment, "quote-lines")
    calc_id = _unique_id(assignment, "quote-total")
    patch = _base_patch(assignment, request, context)
    map_inputs = {
        "rows": f"${{{request.source_step_id}.rows}}",
        "columns": columns,
        "defaults": {"currency": request.currency},
    }
    patch["add_steps"] = [
        {
            "step_id": map_id,
            "title": "Map accepted evidence to quote lines",
            "operation_type": "calculate",
            "adapter": "quote.lines_from_rows",
            "depends_on": [request.source_step_id],
            "inputs": map_inputs,
            "effect": "local",
            "requires": [{
                "kind": "receipt", "step_id": request.source_step_id,
                "require": "verified"}],
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
                "currency": currency_term["value"],
                "freight": freight["value"],
                "tax": tax_input,
                "term_receipt": term_receipt,
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
        _require_verified(assignment, step_id)
    if request.bill_action:
        from core.action_registry import action_registry
        from core.assignment_planner import _registered_action_effect
        action = action_registry.get_action(request.bill_action)
        if action is None:
            raise WorkRequestCompileError(
                f"bill action {request.bill_action!r} is not registered")
        if _registered_action_effect(action) != "external":
            raise WorkRequestCompileError(
                f"bill action {request.bill_action!r} is not an external "
                "mutation capability")
        if "outbound" not in set(
                assignment.get("authorized_actions") or []):
            raise WorkRequestCompileError(
                "bill creation requires outbound authority")
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
        ],
        "required": True,
    }]
    if request.bill_action:
        bill_id = _unique_id(assignment, "create-bill")
        patch["add_steps"].append({
            "step_id": bill_id,
            "title": "Create the supported reviewed bill",
            "operation_type": "outbound",
            "adapter": "action.registry",
            "depends_on": [reconcile_id],
            "inputs": {
                "action": request.bill_action,
                "arguments": f"${{{reconcile_id}.data.bill}}",
            },
            "effect": "external",
            "requires": [{
                "kind": "receipt", "step_id": reconcile_id,
                "require": "verified"}],
            "approval_required": True,
            "approval_purpose": (
                "Create one bill after reconciliation to accepted purchase "
                "and receiving evidence"),
            "required": True,
        })
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
