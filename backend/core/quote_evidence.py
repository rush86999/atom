"""Quote evidence requirements and planning for durable assignments.

The employee derives what a quote needs BEFORE retrieval, validates typed read
receipts against those requirements, and only then builds an executor plan.
No provider call, filesystem path, customer name or pricing rule is hardcoded:
receipts carry identities, versions and typed fields; the fixture in tests is
only an initial business configuration.

Boundary shape follows the shared Brennan contract:
  read receipt -> selected/excluded evidence -> obligations/conflicts ->
  bounded evidence packet -> quote plan.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.assignment_plan import new_teaching_snapshot
from core.assignment_planner import AssignmentPlanError, plan_assignment

QUOTE_REQUIREMENTS: Sequence[Dict[str, Any]] = (
    {"key": "customer_identity", "label": "Customer and contact identity",
     "kind": "subject"},
    {"key": "line_items", "label": "Product/SKU, quantity, unit and pack",
     "kind": "lines"},
    {"key": "price_basis", "label": "Governing price basis and agreement",
     "kind": "document"},
    {"key": "currency", "label": "Currency", "kind": "field"},
    {"key": "effective_date", "label": "Price effective date", "kind": "field"},
    {"key": "discount_policy", "label": "Discount or margin policy",
     "kind": "policy"},
    {"key": "freight", "label": "Freight treatment", "kind": "field"},
    {"key": "tax_treatment", "label": "Tax treatment", "kind": "field"},
    {"key": "delivery_terms", "label": "Delivery terms", "kind": "field"},
    {"key": "validity", "label": "Quote validity", "kind": "field"},
    {"key": "output_document", "label": "Canonical quote document",
     "kind": "output", "required": False},
    {"key": "external_actions", "label": "Intended external actions",
     "kind": "authority", "required": False},
)


def _bounded(value: Any, limit: int = 500) -> str:
    return str(value or "")[:limit]


def derive_quote_requirements(
    objective: str,
    *,
    teaching: Optional[Dict[str, Any]] = None,
    requested: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Derive typed evidence requirements from the objective and teaching.

    Teaching can add a qualification/effective-date constraint or a document
    protocol, but never removes a required quote fact.
    """
    requested = dict(requested or {})
    teaching = dict(teaching or {})
    requirements: List[Dict[str, Any]] = []
    for item in QUOTE_REQUIREMENTS:
        row = {
            "key": item["key"], "label": item["label"], "kind": item["kind"],
            "required": bool(item.get("required", True)),
            "status": "required",
            "reason": f"the accepted objective '{_bounded(objective, 200)}' "
                      f"requires {item['label'].lower()}",
        }
        requirements.append(row)
    context = {}
    for candidate in (teaching.get("matched_context"),
                      teaching.get("applicable_conditions")):
        if isinstance(candidate, dict):
            context.update(candidate)
    if context.get("qualification"):
        requirements.append({
            "key": "qualification", "label": "Required qualification",
            "kind": "context", "required": True, "status": "required",
            "allowed_values": [context["qualification"]],
            "reason": "applicable teaching is bound to this qualification",
        })
    if context.get("effective_date") or requested.get("effective_date"):
        # The effective date requirement is already present; record the
        # requested value as context, never as evidence.
        for row in requirements:
            if row["key"] == "effective_date":
                row["requested_value"] = str(
                    requested.get("effective_date")
                    or context.get("effective_date"))
    if requested.get("customer_id"):
        for row in requirements:
            if row["key"] == "customer_identity":
                row["requested_value"] = str(requested["customer_id"])
    return requirements


def _decimal(value: Any) -> Optional[Decimal]:
    try:
        if value is None or str(value).strip() == "":
            return None
        number = Decimal(str(value))
        if not number.is_finite():
            return None
        return number
    except (InvalidOperation, ValueError):
        return None


def _access_ok(receipt: Dict[str, Any]) -> bool:
    return str(receipt.get("access") or "granted").lower() in (
        "granted", "authorized", "ok", "readable")


def _receipt_ref(receipt: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": receipt.get("provider"),
        "account_id": receipt.get("account_id") or receipt.get("org_id"),
        "resource_id": receipt.get("resource_id"),
        "version": receipt.get("version"),
        "retrieved_at": receipt.get("retrieved_at"),
        "citations": list(receipt.get("citations") or [])[:20],
        "coverage": receipt.get("coverage") or {},
    }


def _obligation(key: str, question: str, reason: str,
                *, candidates: Optional[List[Dict[str, Any]]] = None
                ) -> Dict[str, Any]:
    return {
        "key": key, "status": "open", "question": question,
        "reason": reason, "candidates": list(candidates or [])[:10],
    }


def _conflict(key: str, reason: str,
              candidates: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "key": key, "status": "conflict", "reason": reason,
        "candidates": [_receipt_ref(item) for item in candidates][:10],
    }


def validate_quote_evidence(
    requirements: Sequence[Dict[str, Any]],
    receipts: Sequence[Dict[str, Any]],
    *,
    teaching: Optional[Dict[str, Any]] = None,
    requested: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate typed receipts against quote requirements.

    The oracle is the requirement list and the receipt identities, not a
    top-k ranking. A search hit is not a fact; a filename is not identity; a
    supplier cost sheet is not a customer selling-price agreement.
    """
    requested = dict(requested or {})
    teaching = dict(teaching or {})
    rows = [dict(item) for item in receipts or [] if isinstance(item, dict)]
    obligations: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    selected: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    untrusted: List[Dict[str, Any]] = []
    packet: Dict[str, Any] = {}

    readable: List[Dict[str, Any]] = []
    for item in rows:
        if not _access_ok(item):
            excluded.append({
                **_receipt_ref(item), "reason": "unauthorized_or_unreadable"})
            # An unrelated denied source does not block ready work when the
            # required evidence is satisfied by an authorized source. Missing
            # requirements below still produce a typed obligation.
            continue
        readable.append(item)

    # Customer identity: exact ID wins; two same-name different IDs conflict.
    customer_id = str(requested.get("customer_id") or "").strip()
    customers = [item for item in readable
                 if str(item.get("kind") or "").lower() in (
                     "customer", "contact", "crm_record")
                 and str(item.get("record_type") or "customer").lower()
                 in ("customer", "contact")]
    if customer_id:
        customers = [item for item in customers
                     if str(item.get("customer_id") or "") == customer_id]
    if not customers:
        obligations.append(_obligation(
            "customer_identity", "Which customer and contact is this quote for?",
            "no authorized customer record matched"))
    else:
        ids = {str(item.get("customer_id") or "") for item in customers}
        if len(ids) > 1:
            conflicts.append(_conflict(
                "customer_identity",
                "several customer identities share the requested name",
                customers[:5]))
        else:
            selected.extend(customers[:1])
            packet["customer"] = _receipt_ref(customers[0])
            packet["customer"]["name"] = customers[0].get("customer_name")

    # Governing agreement: same customer, effective date, explicit basis.
    agreements = [item for item in readable
                  if str(item.get("kind") or "").lower() in (
                      "pricing_agreement", "agreement", "price_agreement")]
    current = [item for item in agreements
               if not customer_id
               or str(item.get("customer_id") or customer_id) == customer_id]
    supplier_costs = [
        item for item in current
        if str(item.get("price_basis") or "").lower() in (
            "supplier_cost", "cost")]
    for item in supplier_costs:
        excluded.append({
            **_receipt_ref(item),
            "reason": "supplier_cost_is_not_a_customer_selling_basis",
        })
    current = [
        item for item in current
        if str(item.get("price_basis") or "").lower() not in (
            "supplier_cost", "cost")]
    requested_date = str(requested.get("effective_date") or "")
    dated = [item for item in current
             if not requested_date
             or not item.get("effective_date")
             or str(item["effective_date"]) <= requested_date]
    dated = dated or current
    if not dated:
        supplier_only = any(
            str(item.get("price_basis") or "").lower() in (
                "supplier_cost", "cost") for item in readable)
        obligations.append(_obligation(
            "price_basis",
            "Which customer agreement or list price governs this quote?",
            "a supplier cost sheet is not a customer selling-price basis"
            if supplier_only else "no governing agreement matched"))
    else:
        latest = max(str(item.get("effective_date") or "") for item in dated)
        top = [item for item in dated
               if str(item.get("effective_date") or "") == latest]
        distinct = {(str(item.get("resource_id") or ""),
                     str(item.get("version") or "")) for item in top}
        if len(distinct) > 1:
            conflicts.append(_conflict(
                "price_basis",
                "equally current agreements disagree; confirm which governs",
                top[:5]))
        else:
            agreement = top[0]
            basis = str(agreement.get("price_basis") or "").lower()
            if basis not in ("customer_contract", "list", "selling",
                             "contract", "customer"):
                obligations.append(_obligation(
                    "price_basis",
                    "Confirm the price basis for this customer.",
                    f"agreement basis '{basis or 'missing'}' is not a "
                    "customer selling basis"))
            else:
                selected.append(agreement)
                packet["agreement"] = _receipt_ref(agreement)
                packet["agreement"]["price_basis"] = basis
                excluded.extend({
                    **_receipt_ref(item),
                    "reason": "not_the_governing_version",
                } for item in current if item is not agreement)
            for field in ("currency", "effective_date", "discount_policy",
                          "freight", "tax_treatment", "delivery_terms",
                          "validity"):
                value = agreement.get("fields", {}).get(field) \
                    if isinstance(agreement.get("fields"), dict) else None
                if value in (None, ""):
                    value = agreement.get(field)
                if value not in (None, ""):
                    packet[field] = value

    # Line rows: group by SKU, detect pack/unit conflicts before arithmetic.
    line_receipts = [item for item in readable
                     if str(item.get("kind") or "").lower() in (
                         "price_rows", "workbook_rows", "product")]
    line_rows: List[Dict[str, Any]] = []
    for item in line_receipts:
        for row in item.get("rows") or []:
            line_rows.append({**dict(row), "_receipt": item})
    if not line_rows:
        obligations.append(_obligation(
            "line_items", "Which products, quantities, units and prices apply?",
            "no authorized line rows were read"))
    else:
        by_sku: Dict[str, List[Dict[str, Any]]] = {}
        for row in line_rows:
            by_sku.setdefault(str(row.get("sku") or "").strip(), []).append(row)
        lines: List[Dict[str, Any]] = []
        for sku, group in by_sku.items():
            if not sku:
                obligations.append(_obligation(
                    "line_items", "Which SKU is missing from the line?",
                    "a line has no stable SKU"))
                continue
            packs = {(str(row.get("pack") or ""),
                      str(row.get("unit") or "")) for row in group}
            if len(packs) > 1:
                conflicts.append(_conflict(
                    "line_items",
                    f"SKU {sku} has different packaging/units; confirm before "
                    "arithmetic", [row["_receipt"] for row in group[:5]]))
                continue
            prices = {
                (str(row.get("unit_price") or "").strip(),
                 str(row.get("currency") or "").strip().upper(),
                 str(row.get("discount_percent") or "").strip())
                for row in group
            }
            if len(prices) > 1:
                conflicts.append(_conflict(
                    "line_items",
                    f"SKU {sku} has conflicting prices or currencies across "
                    "authorized sources; confirm before arithmetic",
                    [row["_receipt"] for row in group[:5]]))
                continue
            row = group[0]
            qty = _decimal(row.get("quantity"))
            price = _decimal(row.get("unit_price"))
            currency = str(row.get("currency") or "").strip().upper()
            if qty is None or qty <= 0 or price is None or price < 0:
                obligations.append(_obligation(
                    "line_items", f"What quantity and unit price apply to {sku}?",
                    "quantity/price missing, non-finite or invalid"))
                continue
            if not currency:
                obligations.append(_obligation(
                    "currency", f"What currency applies to {sku}?",
                    "currency was not present in the read evidence"))
                continue
            lines.append({
                "sku": sku,
                "quantity": str(qty),
                "unit": str(row.get("unit") or ""),
                "pack": str(row.get("pack") or ""),
                "unit_price": str(price),
                "currency": currency,
                "discount_percent": str(row.get("discount_percent") or "0"),
                "price_basis": str(row.get("price_basis")
                                   or packet.get("agreement", {}).get(
                                       "price_basis") or ""),
                "effective_date": str(row.get("effective_date")
                                      or packet.get("effective_date") or ""),
                "category": str(row.get("category") or ""),
                "description": str(row.get("description") or ""),
                "citation": row.get("citation") or {},
                "resource_id": (row["_receipt"].get("resource_id")),
                "version": row["_receipt"].get("version"),
            })
        if lines:
            packet["lines"] = lines
            packet["line_receipts"] = [
                _receipt_ref(item) for item in line_receipts[:5]]
            currencies = {line["currency"] for line in lines}
            if len(currencies) > 1:
                conflicts.append(_conflict(
                    "currency",
                    "line items use different currencies; no exchange rate "
                    "was supplied", []))
            bases = {line["price_basis"] for line in lines if line["price_basis"]}
            if len(bases) > 1:
                conflicts.append(_conflict(
                    "price_basis",
                    "line items mix price bases; confirm the governing basis",
                    []))
    if "currency" not in packet and packet.get("lines"):
        packet["currency"] = packet["lines"][0]["currency"]

    # Explicit tax: absence is an obligation, never an implicit zero.
    tax = packet.get("tax_treatment")
    if tax in (None, ""):
        obligations.append(_obligation(
            "tax_treatment",
            "Is tax applicable, and at what rate or exemption?",
            "tax treatment was not explicitly read"))
    elif str(tax).lower() not in ("none", "exempt", "0", "zero"):
        try:
            rate = Decimal(str(tax))
            if not rate.is_finite():
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            obligations.append(_obligation(
                "tax_treatment", "What tax rate applies?",
                f"tax treatment '{_bounded(tax, 80)}' is not a rate or none"))
    if packet.get("freight") in (None, ""):
        obligations.append(_obligation(
            "freight", "What freight amount/terms apply?",
            "freight was not explicitly read"))
    if packet.get("delivery_terms") in (None, ""):
        obligations.append(_obligation(
            "delivery_terms", "What delivery term applies?",
            "delivery terms were not explicitly read"))
    if packet.get("validity") in (None, ""):
        obligations.append(_obligation(
            "validity", "How long is the quote valid?",
            "validity was not explicitly read"))
    if packet.get("discount_policy") in (None, "") and packet.get("lines"):
        has_line_discount = any(
            _decimal(line.get("discount_percent")) not in (None, Decimal("0"))
            for line in packet["lines"])
        if not has_line_discount:
            obligations.append(_obligation(
                "discount_policy", "What discount policy applies?",
                "no discount policy or explicit line discount was read"))

    # Embedded instructions are evidence text only, never authority/teaching.
    for item in readable:
        content = str(item.get("content") or "")
        lowered = content.lower()
        if any(marker in lowered for marker in (
                "ignore previous", "ignore all", "system prompt",
                "send without approval", "grant permission")):
            untrusted.append({
                **_receipt_ref(item),
                "reason": "embedded_instruction_not_authority",
                "excerpt": content[:300],
            })
            if item not in excluded:
                excluded.append({
                    **_receipt_ref(item),
                    "reason": "embedded_instruction_kept_as_evidence_only",
                })

    conflict_keys = {item["key"] for item in conflicts}
    obligation_keys = {item["key"] for item in obligations
                       if item["key"] not in conflict_keys}
    status = ("conflict" if conflicts
              else "needs_clarification" if obligations else "ready")
    requirement_rows = []
    for item in requirements:
        row = dict(item)
        if item["key"] in ("output_document", "external_actions"):
            row["status"] = "requested"
            requirement_rows.append(row)
            continue
        if item["key"] in conflict_keys:
            row["status"] = "conflict"
        elif item["key"] in obligation_keys:
            row["status"] = "missing"
        elif item["key"] == "customer_identity" and packet.get("customer"):
            row["status"] = "satisfied"
        elif item["key"] == "line_items" and packet.get("lines"):
            row["status"] = "satisfied"
        elif item["key"] == "price_basis" and packet.get("agreement"):
            row["status"] = "satisfied"
        elif packet.get(item["key"]) not in (None, ""):
            row["status"] = "satisfied"
        else:
            row["status"] = "missing"
            if item["key"] not in obligation_keys:
                obligations.append(_obligation(
                    item["key"], f"Provide {item['label'].lower()}.",
                    "requirement was not satisfied by the read evidence"))
        requirement_rows.append(row)
    return {
        "schema": "quote-evidence-1",
        "status": status,
        "requirements": requirement_rows,
        "obligations": obligations,
        "conflicts": conflicts,
        "selected": [_receipt_ref(item) for item in selected],
        "excluded": excluded,
        "untrusted_instructions": untrusted,
        "evidence_packet": packet,
        "selected_count": len(selected),
    }


def compute_quote_totals(
    lines: Sequence[Dict[str, Any]],
    *,
    freight: Any,
    tax: Any = "0",
) -> Dict[str, Any]:
    """Independent Decimal quote arithmetic; never generated by the artifact."""
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    normalized = []
    for line in lines:
        qty = _decimal(line.get("quantity"))
        price = _decimal(line.get("unit_price"))
        discount = _decimal(line.get("discount_percent")) or Decimal("0")
        if qty is None or price is None or not qty.is_finite() \
                or not price.is_finite() or not discount.is_finite():
            raise ValueError("line quantity/price/discount must be finite")
        gross = qty * price
        cut = gross * discount / Decimal("100")
        net = gross - cut
        subtotal += gross
        discount_total += cut
        normalized.append({
            "sku": line.get("sku"), "quantity": str(qty),
            "unit_price": str(price), "discount_percent": str(discount),
            "gross": str(gross), "discount": str(cut), "net": str(net),
        })
    freight_value = _decimal(freight)
    if freight_value is None or not freight_value.is_finite() or freight_value < 0:
        raise ValueError("freight must be a non-negative finite amount")
    tax_value = _decimal(tax)
    if tax_value is None:
        if str(tax).lower() in ("none", "exempt", "zero"):
            tax_value = Decimal("0")
        else:
            raise ValueError("tax must be an amount or explicitly none")
    total = subtotal - discount_total + freight_value + tax_value
    quant = Decimal("0.01")
    return {
        "schema": "quote-totals-1",
        "lines": normalized,
        "subtotal": str(subtotal.quantize(quant, rounding=ROUND_HALF_UP)),
        "discount_total": str(
            discount_total.quantize(quant, rounding=ROUND_HALF_UP)),
        "freight": str(freight_value.quantize(quant, rounding=ROUND_HALF_UP)),
        "tax": str(tax_value.quantize(quant, rounding=ROUND_HALF_UP)),
        "total": str(total.quantize(quant, rounding=ROUND_HALF_UP)),
        "currency": (lines[0].get("currency") if lines else None),
    }


def plan_quote_assignment(
    *,
    objective: str,
    validation: Dict[str, Any],
    source: Dict[str, Any],
    teaching: Optional[Dict[str, Any]] = None,
    employee_id: str = "",
    workspace_id: str = "",
    tenant_id: str = "",
    document_path: str,
    email_draft_path: Optional[str] = None,
    email_to: Optional[Sequence[str]] = None,
    subject: Optional[str] = None,
    discount_rules: Optional[Sequence[Dict[str, Any]]] = None,
    actions: Optional[Sequence[Dict[str, Any]]] = None,
    evidence_reads: Optional[Sequence[Dict[str, Any]]] = None,
    scale: int = 2,
    rounding_authority: str = "agreement:round-half-up-2dp",
) -> Dict[str, Any]:
    """Build a durable quote plan from ready evidence via quote.calculate.

    The quote profile is a composition: evidence selection + typed line items +
    the reusable line-item calculation + document/email deliverables. The
    executor and calculator contain no customer or Brennan vocabulary.
    """
    if validation.get("status") != "ready":
        return {
            "status": validation.get("status"),
            "validation": validation,
            "plan": None,
        }
    packet = dict(validation.get("evidence_packet") or {})
    lines = list(packet.get("lines") or [])
    if not lines:
        raise AssignmentPlanError("ready quote evidence has no lines")
    totals = compute_quote_totals(
        lines, freight=packet.get("freight"),
        tax=packet.get("tax_treatment"))
    currency = str(packet.get("currency") or "").strip().upper()
    if not currency:
        raise AssignmentPlanError(
            "ready quote evidence has no explicit currency")
    line_items: List[Dict[str, Any]] = []
    for line in lines:
        basis = str(line.get("price_basis") or "").strip().lower()
        basis = {"customer_contract": "contract",
                 "customer": "contract"}.get(basis, basis)
        if basis not in ("list", "contract", "selling", "quoted"):
            raise AssignmentPlanError(
                f"line {line.get('sku')} has no supported selling price basis")
        unit = str(line.get("unit") or "").strip()
        if not unit:
            raise AssignmentPlanError(
                f"line {line.get('sku')} has no selling unit")
        item = {
            "item_id": str(line["sku"]),
            "description": str(line.get("description") or ""),
            "quantity": str(line["quantity"]),
            "unit": unit,
            "pack_size": str(line.get("pack") or "1"),
            "unit_price": str(line["unit_price"]),
            "price_basis": basis,
            "currency": str(line.get("currency") or currency).upper(),
            "category": str(line.get("category") or ""),
            "source_ref": {
                "resource_id": line.get("resource_id"),
                "version": line.get("version"),
                "citation": line.get("citation") or {},
            },
            "evidence": [line.get("citation") or {}],
        }
        discount = _decimal(line.get("discount_percent")) or Decimal("0")
        if discount != 0:
            item["discount_rate"] = str(discount / Decimal("100"))
            agreement = packet.get("agreement") or {}
            item["discount_authority"] = (
                f"{agreement.get('resource_id') or 'evidence'}:"
                f"{agreement.get('version') or 'v1'}")
        line_items.append(item)
    tax_raw = packet.get("tax_treatment")
    if str(tax_raw).lower() in ("none", "exempt", "zero", "0"):
        tax = {"basis": "none"}
    else:
        tax_value = _decimal(tax_raw)
        if tax_value is None:
            raise AssignmentPlanError("tax treatment is not an explicit amount/rate")
        tax = ({"basis": "rate", "rate": str(tax_value)}
               if Decimal("0") <= tax_value <= Decimal("1")
               else {"basis": "amount", "amount": str(tax_value)})
    rules = list(discount_rules or packet.get("discount_rules") or [])
    calculation = {
        "line_items": line_items,
        "currency": currency,
        "freight": str(packet.get("freight")),
        "tax": tax,
        "discount_rules": rules,
        "as_of": str(packet.get("effective_date") or ""),
        "rounding": "half_up",
        "scale": int(scale),
        "rounding_authority": rounding_authority,
    }
    teaching_snapshot = teaching or new_teaching_snapshot(revision="untrained")
    deliverables = [{
        "kind": "document", "path": document_path,
        "title": subject or objective,
        "description": "Customer quote document",
    }]
    if email_draft_path:
        deliverables.append({
            "kind": "email_draft", "step_id": "email-draft",
            "to": list(email_to or []), "subject": subject or objective,
            "body": "", "description": "Outlook quote draft",
        })
    plan = plan_assignment(
        objective=objective,
        sources=[source],
        deliverables=deliverables,
        calculation=calculation,
        evidence_reads=list(evidence_reads or []),
        teaching_snapshot=teaching_snapshot,
        actions=actions,
        authorized_actions=(
            ["retrieve", "calculate", "present"]
            + (["outbound"] if actions else [])
            + (["edit"] if email_draft_path else [])),
        employee_id=employee_id, workspace_id=workspace_id,
        tenant_id=tenant_id,
        provenance={
            "quote_evidence": validation,
            "quote_totals": totals,
            "output_document": document_path,
            "email_draft": email_draft_path,
        },
    )
    return {"status": "ready", "validation": validation,
            "totals": totals, "plan": plan}
