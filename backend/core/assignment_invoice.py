"""Deterministic invoice reconciliation over accepted evidence payloads.

This is a bookkeeping capability, not a provider action: it compares the
invoice, purchase order and receiving observations and either returns a
material total receipt or opens one targeted obligation. It never creates or
posts a bill.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, Optional

from core.assignment_executor import (
    NeedsContext,
    register_assignment_adapter,
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _payload(value: Any, key: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    nested = value.get(key)
    if isinstance(nested, Mapping):
        return dict(nested)
    return dict(value)


def _mapped(payload: Mapping[str, Any], fields: Mapping[str, str],
            canonical: str) -> Any:
    key = str((fields or {}).get(canonical) or canonical)
    if key in payload:
        return payload.get(key)
    return payload.get(canonical)


def _decimal(value: Any, field: str) -> Decimal:
    text = _text(value)
    if not text:
        raise NeedsContext({
            "concept": "invoice_field",
            "reason": f"the evidence has no {field}",
            "question": f"What is the authoritative {field}?",
            "next_retrieval": "read the authoritative invoice/receiving record",
            "kind": "missing_evidence",
        })
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise NeedsContext({
            "concept": "invoice_field",
            "reason": f"the evidence {field} is not a decimal",
            "question": f"What is the authoritative {field}?",
            "kind": "missing_evidence",
        }) from exc
    if not number.is_finite() or number < 0:
        raise NeedsContext({
            "concept": "invoice_field",
            "reason": f"the evidence {field} is not a finite nonnegative value",
            "question": f"What is the authoritative {field}?",
            "kind": "missing_evidence",
        })
    return number


async def _invoice_reconcile(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    invoice = _payload(inputs.get("invoice"), "invoice")
    purchase = _payload(inputs.get("purchase_order"), "purchase_order")
    receiving = _payload(inputs.get("receiving"), "receiving")
    fields = {
        "invoice": inputs.get("invoice_fields") or {},
        "purchase": inputs.get("purchase_order_fields") or {},
        "receiving": inputs.get("receiving_fields") or {},
    }
    invoice_qty = _decimal(
        _mapped(invoice, fields["invoice"], "quantity"), "invoice quantity")
    received_qty = _decimal(
        _mapped(receiving, fields["receiving"], "received_quantity"),
        "received quantity")
    unit_price = _decimal(
        _mapped(invoice, fields["invoice"], "unit_price"), "invoice unit price")
    freight = _decimal(
        _mapped(invoice, fields["invoice"], "freight"), "invoice freight")
    currency = _text(
        _mapped(invoice, fields["invoice"], "currency")
        or inputs.get("currency")).upper()
    if not currency:
        raise NeedsContext({
            "concept": "currency",
            "reason": "the invoice does not state an explicit currency",
            "question": "Which currency governs this invoice?",
            "kind": "business_decision",
        })
    po_id = _text(_mapped(purchase, fields["purchase"], "po_id"))
    invoice_po = _text(_mapped(invoice, fields["invoice"], "po_id"))
    receiving_po = _text(
        _mapped(receiving, fields["receiving"], "po_id"))
    if invoice_po and po_id and invoice_po != po_id:
        raise NeedsContext({
            "concept": "invoice_identity",
            "reason": "invoice evidence belongs to a different purchase order",
            "question": "Which invoice belongs to this purchase order?",
            "checked_evidence": [f"po={po_id}", f"invoice_po={invoice_po}"],
            "kind": "missing_evidence",
        })
    if po_id and receiving_po and po_id != receiving_po:
        raise NeedsContext({
            "concept": "receiving_identity",
            "reason": "receiving evidence belongs to a different purchase order",
            "question": "Which receiving record belongs to this purchase order?",
            "checked_evidence": [f"po={po_id}", f"receiving_po={receiving_po}"],
            "kind": "missing_evidence",
        })
    if invoice_qty != received_qty:
        raise NeedsContext({
            "concept": "invoice_quantity",
            "reason": (
                f"invoice quantity {invoice_qty} differs from received "
                f"quantity {received_qty}"),
            "question": (
                "The invoice does not match received quantities. Provide the "
                "authoritative corrected invoice."),
            "next_retrieval": "request the supplied corrected invoice version",
            "kind": "missing_evidence",
            "waiting": {
                "state": "waiting_for_external",
                "party": "supplier",
                "resume_on": "corrected_invoice",
                "detail": "invoice/receiving quantity mismatch",
                "correlation_id": (
                    f"invoice-correction:"
                    f"{_text(_mapped(invoice, fields['invoice'], 'invoice_id')) or po_id}"),
            },
        })
    total = (invoice_qty * unit_price + freight).quantize(Decimal("0.01"))
    invoice_id = (
        _text(_mapped(invoice, fields["invoice"], "invoice_id")) or po_id)
    vendor_id = _text(_mapped(purchase, fields["purchase"], "vendor_id"))
    account = _text(_mapped(invoice, fields["invoice"], "account"))
    period = _text(_mapped(invoice, fields["invoice"], "period"))
    bill = {
        "vendor_id": vendor_id,
        "po_id": po_id,
        "invoice_id": invoice_id,
        "quantity": str(invoice_qty),
        "unit_price": str(unit_price),
        "freight": str(freight),
        "currency": currency,
        "total": str(total),
    }
    if account:
        bill["account"] = account
    if period:
        bill["period"] = period
    return {
        "status": "applied",
        "summary": (
            f"reconciled invoice total {total} {currency} against received "
            f"quantity {received_qty}"),
        "value": str(total),
        "unit": currency,
        "currency": currency,
        "invoice_quantity": str(invoice_qty),
        "received_quantity": str(received_qty),
        "purchase_order_id": po_id or None,
        "receiving_purchase_order_id": receiving_po or None,
        "verification": {
            "status": "verified",
            "resource_id": _text(_mapped(invoice, fields["invoice"],
                                        "resource_id")) or invoice_id,
            "version": _text(_mapped(invoice, fields["invoice"], "version")),
            "coverage": {"complete": True, "truncated": False},
        },
        "data": {
            "total": str(total),
            "currency": currency,
            "quantity": str(invoice_qty),
            "unit_price": str(unit_price),
            "freight": str(freight),
            "vendor_id": vendor_id,
            "po_id": po_id,
            "invoice_id": invoice_id,
            "invoice_version": _text(
                _mapped(invoice, fields["invoice"], "version")),
            "receiving_version": _text(
                _mapped(receiving, fields["receiving"], "version")),
            "bill": bill,
        },
        "evidence_refs": [
            {"kind": "bookkeeping_reconciliation",
             "resource_id": _text(
                 _mapped(invoice, fields["invoice"], "resource_id"))
             or "invoice",
             "version": _text(
                 _mapped(invoice, fields["invoice"], "version"))},
        ],
    }


register_assignment_adapter(
    "invoice.reconcile",
    description="Reconcile invoice, purchase order and receiving evidence",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "required_inputs": [
                  "invoice", "purchase_order", "receiving",
                  "invoice_fields", "purchase_order_fields",
                  "receiving_fields"],
              "allow_standing_authorization": False},
)(_invoice_reconcile)
