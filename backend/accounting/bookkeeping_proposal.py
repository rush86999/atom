"""Deterministic supplier-invoice bookkeeping proposals.

This module deliberately stops before posting.  It turns extracted document
facts into a reviewed proposal with explicit obligations, exact decimal
amounts, stable duplicate identity and balanced journal lines.  The authorized
provider write is a separate registered action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class ProposalError(ValueError):
    pass


def decimal_amount(value: Any, field_name: str) -> Decimal:
    """Parse an original decimal string/integer minor unit, never a float."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ProposalError(f"{field_name} must be a decimal amount")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ProposalError(f"{field_name} is empty")
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise ProposalError(f"{field_name} is not a decimal: {value!r}") from exc
    raise ProposalError(
        f"{field_name} must be a decimal string or integer minor units, "
        f"not {type(value).__name__}")


def parse_document_date(value: Any, field_name: str) -> str:
    if not value:
        raise ProposalError(f"{field_name} is missing")
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError as exc:
            raise ProposalError(f"{field_name} is not an ISO date: {value!r}") from exc


def duplicate_identity(provider: str, organization_id: str,
                       entity_type: str, external_id: str) -> str:
    """Exact duplicate identity; never substring matching."""
    parts = [provider, organization_id, entity_type, external_id]
    if not all(str(part or "").strip() for part in parts):
        raise ProposalError("duplicate identity requires provider, organization, entity type and external id")
    return "|".join(str(part).strip() for part in parts)


def _same_vendor(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if a.get("id") and b.get("id"):
        return str(a["id"]) == str(b["id"])
    return False


def resolve_vendor(candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve exactly one vendor identity; same-name distinct IDs ambiguous."""
    normalized = [
        {"id": str(item.get("id") or "").strip(),
         "name": str(item.get("name") or "").strip()}
        for item in candidates or [] if isinstance(item, dict)
    ]
    normalized = [item for item in normalized if item["id"] or item["name"]]
    if not normalized:
        raise ProposalError("vendor identity is missing")
    ids = {item["id"] for item in normalized if item["id"]}
    if len(ids) > 1:
        raise ProposalError("vendor identity is ambiguous: multiple provider IDs match")
    first = normalized[0]
    if not first["id"]:
        raise ProposalError("vendor identity requires a stable provider ID")
    return first


def _line_amount(line: Dict[str, Any]) -> Decimal:
    if line.get("amount") not in (None, ""):
        return decimal_amount(line["amount"], "line.amount")
    qty = decimal_amount(line.get("quantity"), "line.quantity")
    unit = decimal_amount(line.get("unit_price"), "line.unit_price")
    return qty * unit


def build_proposal(
    *,
    provider: str,
    organization_id: str,
    entity_type: str,
    external_id: str,
    vendor_candidates: Sequence[Dict[str, Any]],
    currency: Any,
    document_date: Any,
    due_date: Any = None,
    lines: Sequence[Dict[str, Any]] = (),
    tax_total: Any = "0.00",
    document_total: Any,
    payment: Optional[Dict[str, Any]] = None,
    credit_total: Any = "0.00",
) -> Dict[str, Any]:
    """Build one deterministic proposal or return explicit obligations.

    Raises :class:`ProposalError` for invalid arithmetic.  Missing facts return
    ``status='needs_clarification'`` with stable obligation codes so the
    employee can ask only for what is absent.
    """
    obligations: List[Dict[str, str]] = []
    currency_text = str(currency or "").strip().upper()
    if not currency_text:
        obligations.append({"code": "missing_currency",
                            "question": "Which currency is on the supplier document?"})
    if not document_date:
        obligations.append({"code": "missing_date",
                            "question": "What is the supplier document date?"})
    if not external_id or not str(external_id).strip():
        obligations.append({"code": "missing_external_id",
                            "question": "Which provider invoice/reference ID identifies this document?"})
    if obligations:
        return {"status": "needs_clarification", "obligations": obligations,
                "duplicate_key": None}

    try:
        vendor = resolve_vendor(vendor_candidates)
    except ProposalError as exc:
        code = ("ambiguous_vendor"
                if "ambiguous" in str(exc).lower() else "missing_vendor")
        return {
            "status": "needs_clarification",
            "obligations": [{
                "code": code,
                "question": (
                    "Which vendor identity governs this document?"
                    if code == "ambiguous_vendor"
                    else "Which vendor issued this supplier document?"),
            }],
            "duplicate_key": None,
        }
    doc_date = parse_document_date(document_date, "document_date")
    due = parse_document_date(due_date, "due_date") if due_date else None
    tax = decimal_amount(tax_total, "tax_total")
    credit = decimal_amount(credit_total, "credit_total")
    total = decimal_amount(document_total, "document_total")
    if total < 0 or tax < 0 or credit < 0:
        raise ProposalError("amounts cannot be negative")

    normalized_lines: List[Dict[str, Any]] = []
    line_sum = Decimal("0.00")
    for line in lines or []:
        amount = _line_amount(line)
        if amount < 0:
            raise ProposalError("line amounts cannot be negative")
        line_sum += amount
        normalized_lines.append({
            **{k: v for k, v in line.items()
               if k not in ("amount", "quantity", "unit_price")},
            "amount": str(amount.quantize(Decimal("0.01"))),
        })

    expected = line_sum + tax - credit
    if expected.quantize(Decimal("0.01")) != total.quantize(Decimal("0.01")):
        raise ProposalError(
            f"document total {total} does not match line subtotal {line_sum} "
            f"+ tax {tax} - credit {credit} = {expected}")

    # A payment is evidence accompanying the document, never a posting state.
    # It must be a real amount within the document and the same currency; a
    # supplier bill is still a bill, not a completed payment.
    normalized_payment: Dict[str, Any] = {}
    if payment:
        if not isinstance(payment, dict):
            raise ProposalError("payment must be an object")
        paid = decimal_amount(payment.get("amount"), "payment.amount")
        if paid <= 0:
            raise ProposalError("payment amount must be positive")
        if paid > total:
            raise ProposalError(
                f"payment {paid} exceeds document total {total}")
        payment_currency = str(payment.get("currency") or "").strip().upper()
        if payment_currency and payment_currency != currency_text:
            raise ProposalError(
                f"payment currency {payment_currency} does not match "
                f"document currency {currency_text}")
        normalized_payment = {
            **payment,
            "amount": str(paid.quantize(Decimal("0.01"))),
            "currency": payment_currency or currency_text,
            "posted": False,
            "note": "payment evidence only; posting a payment is a separate action",
        }
        if payment.get("date"):
            normalized_payment["date"] = parse_document_date(
                payment["date"], "payment.date")

    missing_accounts = [
        index for index, line in enumerate(normalized_lines)
        if not (str(line.get("account_id") or "").strip()
                or str(line.get("item_id") or "").strip())
    ]
    if missing_accounts:
        obligations.append({
            "code": "missing_account",
            "question": (
                "Which account or item applies to line(s) "
                + ", ".join(str(index + 1) for index in missing_accounts)
                + "? The proposal cannot post an unmapped line."),
        })
        return {
            "status": "needs_clarification",
            "provider": provider,
            "organization_id": organization_id,
            "entity_type": entity_type,
            "external_id": str(external_id).strip(),
            "duplicate_key": duplicate_identity(
                provider, organization_id, entity_type, external_id),
            "obligations": obligations,
            "lines": normalized_lines,
        }

    duplicate_key = duplicate_identity(
        provider, organization_id, entity_type, external_id)
    # The proposal is deliberately not posted.  A separate authorized action
    # performs the provider write and readback.
    return {
        "status": "proposed",
        "provider": provider,
        "organization_id": organization_id,
        "entity_type": entity_type,
        "external_id": str(external_id).strip(),
        "duplicate_key": duplicate_key,
        "vendor": vendor,
        "currency": currency_text,
        "document_date": doc_date,
        "due_date": due,
        "lines": normalized_lines,
        "line_subtotal": str(line_sum.quantize(Decimal("0.01"))),
        "tax_total": str(tax.quantize(Decimal("0.01"))),
        "credit_total": str(credit.quantize(Decimal("0.01"))),
        "document_total": str(total.quantize(Decimal("0.01"))),
        "payment": normalized_payment,
        "obligations": [],
        "requires_authority": True,
        "posting": None,
    }


def balanced_journal(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate debit/credit entries and return them ordered as supplied."""
    out: List[Dict[str, Any]] = []
    debit = Decimal("0.00")
    credit = Decimal("0.00")
    for entry in entries or []:
        side = str(entry.get("side") or "").lower()
        if side not in ("debit", "credit"):
            raise ProposalError("journal side must be debit or credit")
        amount = decimal_amount(entry.get("amount"), "journal.amount")
        if amount <= 0:
            raise ProposalError("journal amounts must be positive")
        out.append({**entry, "amount": str(amount.quantize(Decimal("0.01")))})
        if side == "debit":
            debit += amount
        else:
            credit += amount
    if debit != credit:
        raise ProposalError(f"journal is unbalanced: debit {debit} != credit {credit}")
    return out
