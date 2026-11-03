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


def _quote_column_values(
    rows: Sequence[Mapping[str, Any]], column: str,
) -> List[str]:
    return [
        str(row.get(column)).strip()
        for row in rows
        if row.get(column) not in (None, "")
    ]


def _is_numeric_values(values: Sequence[str]) -> bool:
    if not values:
        return False
    try:
        return all(Decimal(value).is_finite() for value in values)
    except (InvalidOperation, ValueError):
        return False


def _resolve_quote_columns(
    requested: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    available: Sequence[str],
    *,
    currency: str,
) -> Dict[str, str]:
    """Resolve semantic quote roles from value shape when the model swaps them.

    The model still chooses the operation and the evidence step. This helper
    repairs only mechanical column roles (text item, numeric quantity/price)
    when its mapping is type-incompatible and a unique value-shape assignment
    exists. Ambiguous shapes are refused for one bounded model repair.
    """
    columns = {
        str(key): str(value) for key, value in dict(requested or {}).items()
        if value not in (None, "")
    }
    available = [str(item) for item in available]
    rows = [row for row in rows if isinstance(row, Mapping)]
    by_column = {
        column: _quote_column_values(rows, column) for column in available
    }
    numeric = [
        column for column, values in by_column.items()
        if _is_numeric_values(values)
    ]
    text = [
        column for column, values in by_column.items()
        if values and not _is_numeric_values(values)
    ]

    # Item identity must be a non-empty text/identity column when one exists.
    # Currency-code columns are units, not item identities.
    identity_text = [
        column for column in text
        if not all(
            len(value) == 3 and value.isalpha()
            for value in by_column[column])
    ]
    item = columns.get("item_id")
    if item not in available or not by_column.get(item):
        item = None
    if (item in numeric or item in text and identity_text
            and item not in identity_text):
        item = identity_text[0] if len(identity_text) == 1 else item

    # A mapped currency column is observed evidence. Never discard it to
    # make the request default apply; preserve it so the caller can refuse a
    # conflict or the calculator can reject it before arithmetic.
    currency_column = columns.get("currency")
    if currency_column not in available:
        currency_column = None

    candidates = [
        column for column in numeric
        if column != item and column != currency_column
    ]
    quantity = columns.get("quantity")
    price = columns.get("unit_price")
    if quantity not in candidates:
        quantity = None
    if price not in candidates or price == quantity:
        price = None
    if (quantity is None or price is None) and len(candidates) == 2:
        first, second = candidates

        def _integer_ratio(column: str) -> float:
            values = by_column[column]
            if not values:
                return 0.0
            return sum(
                1 for value in values
                if Decimal(value) == Decimal(value).to_integral_value()
            ) / len(values)

        def _mean(column: str) -> Decimal:
            values = by_column[column]
            if not values:
                return Decimal("0")
            return sum((Decimal(value) for value in values), Decimal("0")) / Decimal(
                len(values))

        first_integer = _integer_ratio(first)
        second_integer = _integer_ratio(second)
        if first_integer > second_integer:
            quantity, price = first, second
        elif second_integer > first_integer:
            quantity, price = second, first
        elif _mean(first) <= _mean(second):
            quantity, price = first, second
        else:
            quantity, price = second, first
    if quantity is None or price is None:
        raise WorkRequestCompileError(
            "quote mapping cannot be resolved to distinct numeric quantity "
            "and unit-price columns; name the semantic columns explicitly")
    columns["item_id"] = item or columns.get("item_id")
    columns["quantity"] = quantity
    columns["unit_price"] = price
    if currency_column:
        columns["currency"] = currency_column
    elif "currency" in columns:
        columns.pop("currency", None)
    return {
        key: value for key, value in columns.items()
        if value not in (None, "") and key in {
            "item_id", "quantity", "unit_price", "currency", "description",
            "unit", "pack_size", "price_basis", "category", "discount",
        }
    }


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
    sample_rows = [
        row for row in (result.get("rows") or [])
        if isinstance(row, Mapping)
    ][:25]
    resolved_columns = _resolve_quote_columns(
        columns, sample_rows, list(available), currency=request.currency)
    if resolved_columns != columns:
        columns = resolved_columns
    currency_column = columns.get("currency")
    if currency_column:
        currency_values = [
            str(row.get(currency_column)).strip()
            for row in sample_rows
            if row.get(currency_column) not in (None, "")
        ]
        if not currency_values:
            raise WorkRequestCompileError(
                f"quote mapping 'currency' column {currency_column!r} has no "
                "explicit values in the accepted rows")
        malformed = sorted({
            value for value in currency_values
            if len(value) != 3 or not value.isalpha()
        })
        if malformed:
            raise WorkRequestCompileError(
                f"quote currency column {currency_column!r} contains "
                f"malformed value(s) {malformed}; no default substitution")
        conflicts = sorted({
            value.upper() for value in currency_values
            if value.upper() != str(request.currency).strip().upper()
        })
        if conflicts:
            raise WorkRequestCompileError(
                f"source currency {conflicts!r} conflicts with the requested "
                f"quote currency {request.currency!r}; implicit FX or default "
                "substitution is not allowed")
    for semantic, column in columns.items():
        if semantic in ("quantity", "unit_price", "discount"):
            for index, row in enumerate(sample_rows):
                value = row.get(column)
                if semantic == "discount" and value in (None, ""):
                    continue
                try:
                    number = Decimal(str(value))
                except (InvalidOperation, ValueError) as exc:
                    raise WorkRequestCompileError(
                        f"quote mapping {semantic!r} column {column!r} is not "
                        f"numeric in accepted row {index + 1}") from exc
                if not number.is_finite():
                    raise WorkRequestCompileError(
                        f"quote mapping {semantic!r} column {column!r} is not "
                        f"finite in accepted row {index + 1}")
        if semantic in ("unit", "pack_size", "price_basis"):
            empty = [
                index + 1 for index, row in enumerate(sample_rows)
                if str(row.get(column) or "").strip() == ""
            ]
            if empty:
                raise WorkRequestCompileError(
                    f"quote mapping {semantic!r} column {column!r} is empty "
                    f"in accepted row(s) {empty}; no default substitution")
    if "item_id" in columns:
        for index, row in enumerate(sample_rows):
            if str(row.get(columns["item_id"]) or "").strip() == "":
                raise WorkRequestCompileError(
                    f"quote mapping 'item_id' column "
                    f"{columns['item_id']!r} is empty in accepted row "
                    f"{index + 1}")
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
    if columns != (
            request.columns.model_dump(exclude_none=True)
            if hasattr(request.columns, "model_dump")
            else dict(request.columns or {})):
        patch["observations"].append({
            "kind": "resolved_quote_columns",
            "columns": dict(columns),
        })
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
                # Marks this as a compiled typed request so removing the
                # receipt cannot silently downgrade it to a legacy caller.
                "term_binding_required": True,
            },
            "effect": "local",
            "requires": [],
            "required": True,
        },
    ]
    return patch


def _invoice_evidence_shape(
    assignment: Mapping[str, Any],
    step_id: str,
    mapping: Mapping[str, Any],
    defaults: Mapping[str, str],
    required_keys: Sequence[str],
    label: str,
) -> Dict[str, Any]:
    step = step_by_id(assignment, step_id)
    result = (step or {}).get("result")
    data = result.get("data") if isinstance(result, Mapping) else None
    if not isinstance(data, Mapping):
        raise WorkRequestCompileError(
            f"{label} step {step_id!r} has no structured evidence data")
    fields = {
        key: str(mapping.get(key) or defaults[key])
        for key in defaults if key in defaults
    }
    missing = [
        key for key in required_keys
        if not fields.get(key)
        or fields[key] not in data
        or data.get(fields[key]) in (None, "")
    ]
    if missing:
        raise WorkRequestCompileError(
            f"{label} step {step_id!r} is missing required field(s) "
            f"{sorted(missing)}; bind the step that contains this record")
    return dict(data)


def _invoice_role_candidates(
    assignment: Mapping[str, Any],
    fields: Mapping[str, str],
    required_keys: Sequence[str],
) -> List[str]:
    candidates = []
    for step in assignment.get("steps") or []:
        if not isinstance(step, Mapping) or step.get("status") != "applied":
            continue
        result = step.get("result")
        data = result.get("data") if isinstance(result, Mapping) else None
        if not isinstance(data, Mapping):
            continue
        if all(
            fields.get(key) and fields[key] in data
            and data.get(fields[key]) not in (None, "")
            for key in required_keys
        ):
            candidates.append(str(step.get("step_id") or ""))
    return [item for item in candidates if item]


def _bind_invoice_role(
    assignment: Mapping[str, Any],
    bound: str,
    fields: Mapping[str, str],
    required_keys: Sequence[str],
    label: str,
) -> str:
    candidates = _invoice_role_candidates(
        assignment, fields, required_keys)
    if bound in candidates:
        return bound
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise WorkRequestCompileError(
            f"no accepted evidence step contains the {label} fields "
            f"{list(required_keys)}; add or read the correct source")
    raise WorkRequestCompileError(
        f"{label} binding is ambiguous across accepted steps {candidates}; "
        "name the exact step")


INVOICE_FIELD_DEFAULTS = {
    "po_id": "po_id", "invoice_id": "invoice_id",
    "quantity": "quantity", "unit_price": "unit_price",
    "freight": "freight", "currency": "currency",
    "version": "version", "resource_id": "resource_id",
}
PURCHASE_ORDER_FIELD_DEFAULTS = {
    "po_id": "po_id", "vendor_id": "vendor_id",
}
RECEIVING_FIELD_DEFAULTS = {
    "po_id": "po_id", "received_quantity": "received_quantity",
    "version": "version",
}
INVOICE_ROLE_REQUIREMENTS = {
    "invoice": ("invoice_id", "po_id", "quantity", "unit_price"),
    "purchase_order": ("po_id", "vendor_id"),
    "receiving": ("po_id", "received_quantity"),
}


def _invoice_patch(
    request: InvoiceReconciliationRequest,
    assignment: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    invoice_fields = dict(
        request.invoice_fields) or dict(INVOICE_FIELD_DEFAULTS)
    po_fields = dict(
        request.purchase_order_fields) or dict(
            PURCHASE_ORDER_FIELD_DEFAULTS)
    receiving_fields = dict(
        request.receiving_fields) or dict(RECEIVING_FIELD_DEFAULTS)
    invoice_step_id = _bind_invoice_role(
        assignment, request.invoice_step_id, invoice_fields,
        INVOICE_ROLE_REQUIREMENTS["invoice"], "invoice")
    purchase_order_step_id = _bind_invoice_role(
        assignment, request.purchase_order_step_id, po_fields,
        INVOICE_ROLE_REQUIREMENTS["purchase_order"], "purchase order")
    receiving_step_id = _bind_invoice_role(
        assignment, request.receiving_step_id, receiving_fields,
        INVOICE_ROLE_REQUIREMENTS["receiving"], "receiving")
    for step_id in (
            invoice_step_id, purchase_order_step_id, receiving_step_id):
        _step_result(assignment, step_id)
        _require_verified(assignment, step_id)
    invoice_data = _invoice_evidence_shape(
        assignment, invoice_step_id, invoice_fields, invoice_fields,
        INVOICE_ROLE_REQUIREMENTS["invoice"], "invoice")
    po_data = _invoice_evidence_shape(
        assignment, purchase_order_step_id, po_fields, po_fields,
        INVOICE_ROLE_REQUIREMENTS["purchase_order"], "purchase order")
    receiving_data = _invoice_evidence_shape(
        assignment, receiving_step_id, receiving_fields,
        receiving_fields, INVOICE_ROLE_REQUIREMENTS["receiving"], "receiving")
    po_identity = str(po_data.get(po_fields["po_id"]) or "").strip()
    for label, data, fields in (
            ("invoice", invoice_data, invoice_fields),
            ("receiving", receiving_data, receiving_fields)):
        identity = str(data.get(fields["po_id"]) or "").strip()
        if po_identity and identity and identity != po_identity:
            raise WorkRequestCompileError(
                f"{label} belongs to purchase order {identity!r}, not the "
                f"accepted purchase order {po_identity!r}")
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
    patch["observations"].append({
        "kind": "resolved_invoice_evidence",
        "invoice_step_id": invoice_step_id,
        "purchase_order_step_id": purchase_order_step_id,
        "receiving_step_id": receiving_step_id,
    })
    patch["add_steps"] = [{
        "step_id": reconcile_id,
        "title": "Reconcile invoice against purchase and receiving evidence",
        "operation_type": "calculate",
        "adapter": "invoice.reconcile",
        "depends_on": list(dict.fromkeys([
            invoice_step_id, purchase_order_step_id, receiving_step_id,
            *([request.vendor_step_id] if request.vendor_step_id else []),
            *([request.coa_step_id] if request.coa_step_id else []),
            *([request.period_step_id] if request.period_step_id else []),
        ])),
        "inputs": {
            "invoice": f"${{{invoice_step_id}.data}}",
            "purchase_order": f"${{{purchase_order_step_id}.data}}",
            "receiving": f"${{{receiving_step_id}.data}}",
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
                invoice_step_id, purchase_order_step_id, receiving_step_id)
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
