"""Desired-state verification for commercial provider readbacks.

Effect observation and desired-state verification are separate facts:

* the provider returned a remote object id (the create may have applied), and
* the readback matches every material field the caller authorized.

A created object with a sparse readback is **incomplete verification**, not
proof that the effect did not apply.  A created object with different lines,
customer, currency or totals is a **mismatch** and must never trigger a second
create.  This module contains only normalization/comparison; it does not call a
provider or create anything.

Provider-managed fields (generated ids/numbers/timestamps) are recorded but not
required to equal caller input.  Material fields are compared as normalized
Decimals, ISO dates, exact provider identities and canonical line multisets.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROVIDER_MANAGED_FIELDS = (
    "estimate_id", "estimate_number", "bill_id", "bill_number",
    "line_item_id", "created_time", "created_at", "last_modified_time",
    "last_modified_at", "updated_at", "total", "sub_total", "tax_total",
    "discount_total",
)

NORMALIZATION = {
    "decimals": "Decimal(str(value)); numeric equality ignores trailing zeros",
    "dates": "ISO-8601 date (time component and Z are dropped)",
    "currency": "upper-case ISO code",
    "identifiers": "exact provider/customer/item ids; no substring matching",
    "lines": "canonical multiset keyed by stable item identity; order is ignored",
    "text": "trim and collapse whitespace; case preserved for names/terms",
    "discount": "explicit percentage or amount; equivalent amount/percent formulas accepted",
}


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _date_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _currency(value: Any) -> str:
    return str(value or "").strip().upper()


def _get(record: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _identity(line: Dict[str, Any]) -> Tuple[str, str]:
    item_id = _get(line, "item_id", "sku", "product_id")
    if item_id not in (None, ""):
        return "item", str(item_id).strip()
    name = _text(_get(line, "name", "description"))
    if name:
        return "name", name.casefold()
    return "missing", ""


def _line_quantity(line: Dict[str, Any]) -> Optional[Decimal]:
    return _decimal(_get(line, "quantity", "qty"))


def _line_rate(line: Dict[str, Any]) -> Optional[Decimal]:
    return _decimal(_get(line, "rate", "unit_price", "price"))


def _discount_descriptor(line: Dict[str, Any]) -> Tuple[Optional[str], Optional[Decimal]]:
    """Return (mode, value); mode is percent, amount, or ambiguous."""
    if _get(line, "discount_percent", "discount_rate") is not None:
        return "percent", _decimal(
            _get(line, "discount_percent", "discount_rate"))
    amount = _get(line, "discount_amount")
    if amount is not None:
        return "amount", _decimal(amount)
    raw = _get(line, "discount")
    if raw in (None, ""):
        return None, None
    text = str(raw).strip()
    if text.endswith("%"):
        return "percent", _decimal(text)
    mode = str(_get(line, "discount_type") or "").strip().lower()
    if mode in ("percent", "percentage"):
        return "percent", _decimal(text)
    if mode in ("amount", "fixed"):
        return "amount", _decimal(text)
    return "ambiguous", _decimal(text)


def _tax_descriptor(line: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tax_id": _text(_get(line, "tax_id")),
        "tax_name": _text(_get(line, "tax_name")),
        "percent": _decimal(_get(line, "tax_percentage", "tax_rate")),
        "amount": _decimal(_get(line, "tax_amount")),
    }


def _line_total(line: Dict[str, Any]) -> Optional[Decimal]:
    return _decimal(_get(line, "item_total", "line_total", "total", "amount"))


def _observed_lines(readback: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = _get(readback, "line_items", "lines", "items") or []
    return [row for row in rows if isinstance(row, dict)]


def _add_missing(report: Dict[str, Any], field: str) -> None:
    if field not in report["missing_fields"]:
        report["missing_fields"].append(field)


def _add_mismatch(report: Dict[str, Any], field: str, expected: Any,
                  observed: Any) -> None:
    message = (
        f"{field} changed: authorized {expected!r}, provider readback "
        f"{observed!r}")
    report["mismatches"].append({
        "field": field, "expected": expected, "observed": observed,
        "message": message,
    })


def _compare_scalar(report: Dict[str, Any], field: str, expected: Any,
                    observed: Any, *, normalizer=None) -> None:
    if expected in (None, ""):
        return
    report["checked_fields"].append(field)
    if observed in (None, ""):
        _add_missing(report, field)
        return
    left = normalizer(expected) if normalizer else expected
    right = normalizer(observed) if normalizer else observed
    if left != right:
        _add_mismatch(report, field, expected, observed)


def _compare_decimal(report: Dict[str, Any], field: str, expected: Any,
                     observed: Any) -> None:
    if expected in (None, ""):
        return
    report["checked_fields"].append(field)
    if observed in (None, ""):
        _add_missing(report, field)
        return
    left, right = _decimal(expected), _decimal(observed)
    if left is None or right is None or left != right:
        _add_mismatch(report, field, expected, observed)


def _compare_date(report: Dict[str, Any], field: str, expected: Any,
                  observed: Any) -> None:
    if expected in (None, ""):
        return
    report["checked_fields"].append(field)
    if observed in (None, ""):
        _add_missing(report, field)
        return
    left, right = _date_text(expected), _date_text(observed)
    if left is None or right is None or left != right:
        _add_mismatch(report, field, expected, observed)


def _compare_discount(report: Dict[str, Any], field: str,
                      expected_line: Dict[str, Any],
                      observed_line: Dict[str, Any]) -> None:
    exp_mode, exp_value = _discount_descriptor(expected_line)
    if exp_mode is None:
        return
    report["checked_fields"].append(field)
    obs_mode, obs_value = _discount_descriptor(observed_line)
    if obs_mode is None or obs_value is None:
        _add_missing(report, field)
        return
    if exp_mode == "ambiguous" or obs_mode == "ambiguous":
        _add_missing(report, field + "_mode")
        return
    if exp_mode == obs_mode:
        if exp_value != obs_value:
            _add_mismatch(report, field, exp_value, obs_value)
        return
    # Percentage vs amount can be economically equivalent for this line.
    quantity = _line_quantity(expected_line)
    rate = _line_rate(expected_line)
    gross = (quantity * rate) if quantity is not None and rate is not None else None
    if gross is None:
        _add_missing(report, field + "_basis")
        return
    exp_amount = (gross * exp_value / Decimal("100")
                  if exp_mode == "percent" else exp_value)
    obs_amount = (gross * obs_value / Decimal("100")
                  if obs_mode == "percent" else obs_value)
    if exp_amount != obs_amount:
        _add_mismatch(report, field, exp_value, obs_value)


def _compare_tax(report: Dict[str, Any], field: str,
                 expected_line: Dict[str, Any],
                 observed_line: Dict[str, Any]) -> None:
    expected = _tax_descriptor(expected_line)
    if not any(value not in (None, "") for value in expected.values()):
        return
    observed = _tax_descriptor(observed_line)
    if expected["tax_id"]:
        _compare_scalar(report, field + ".tax_id", expected["tax_id"],
                        observed["tax_id"], normalizer=_text)
    if expected["percent"] is not None:
        _compare_decimal(report, field + ".percent", expected["percent"],
                         observed["percent"])
    if expected["amount"] is not None:
        _compare_decimal(report, field + ".amount", expected["amount"],
                         observed["amount"])


def _compare_line(report: Dict[str, Any], index: int, expected: Dict[str, Any],
                  observed: Dict[str, Any]) -> None:
    prefix = f"line_items[{index}]"
    _compare_decimal(report, prefix + ".quantity", _line_quantity(expected),
                     _line_quantity(observed))
    _compare_decimal(report, prefix + ".rate", _line_rate(expected),
                     _line_rate(observed))
    expected_unit = _text(_get(expected, "unit", "uom"))
    if expected_unit:
        _compare_scalar(report, prefix + ".unit", expected_unit,
                        _text(_get(observed, "unit", "uom")),
                        normalizer=_text)
    expected_pack = _text(_get(expected, "pack_size", "pack"))
    if expected_pack:
        _compare_scalar(report, prefix + ".pack", expected_pack,
                        _text(_get(observed, "pack_size", "pack")),
                        normalizer=_text)
    expected_account = _text(_get(expected, "account_id"))
    if expected_account:
        _compare_scalar(report, prefix + ".account_id", expected_account,
                        _text(_get(observed, "account_id")),
                        normalizer=_text)
    _compare_discount(report, prefix + ".discount", expected, observed)
    _compare_tax(report, prefix + ".tax", expected, observed)
    expected_total = _line_total(expected)
    if expected_total is not None:
        observed_total = _line_total(observed)
        if observed_total is None:
            _add_missing(report, prefix + ".total")
        elif expected_total != observed_total:
            _add_mismatch(report, prefix + ".total", expected_total,
                          observed_total)


def _compare_lines(report: Dict[str, Any], expected_lines: Sequence[Dict[str, Any]],
                   observed_lines: Sequence[Dict[str, Any]]) -> None:
    report["checked_fields"].append("line_items")
    if not expected_lines:
        return
    if not observed_lines:
        _add_missing(report, "line_items")
        return
    remaining = list(observed_lines)
    for index, expected in enumerate(expected_lines):
        exp_kind, exp_key = _identity(expected)
        if exp_kind == "missing":
            _add_missing(report, f"line_items[{index}].identity")
            continue
        candidates = []
        for observed in remaining:
            obs_kind, obs_key = _identity(observed)
            if obs_kind == exp_kind and obs_key == exp_key:
                candidates.append(observed)
        if not candidates:
            _add_mismatch(report, f"line_items[{index}].identity",
                          f"{exp_kind}:{exp_key}", "no matching line")
            continue
        # Pick the candidate with the fewest differences, preserving
        # multiplicity for duplicate lines.
        def score(candidate: Dict[str, Any]) -> int:
            probe = _new_report()
            _compare_line(probe, index, expected, candidate)
            return len(probe["mismatches"]) + len(probe["missing_fields"])

        chosen = min(candidates, key=score)
        remaining.remove(chosen)
        _compare_line(report, index, expected, chosen)
    for extra in remaining:
        kind, key = _identity(extra)
        _add_mismatch(report, "line_items.extra", "no extra line",
                      f"{kind}:{key}")


def _new_report() -> Dict[str, Any]:
    return {
        "effect": "observed",
        "status": "verified",
        "checked_fields": [],
        "missing_fields": [],
        "mismatches": [],
        "provider_managed_fields": list(PROVIDER_MANAGED_FIELDS),
        "normalization": dict(NORMALIZATION),
    }


def _finish(report: Dict[str, Any], readback: Dict[str, Any]) -> Dict[str, Any]:
    if report["mismatches"]:
        report["status"] = "mismatch"
    elif report["missing_fields"]:
        report["status"] = "incomplete"
    else:
        report["status"] = "verified"
    report["observed_remote_id"] = str(
        _get(readback, "estimate_id", "bill_id", "id") or "")
    report["conflicts"] = [
        item["message"] for item in report["mismatches"]]
    return report


def verify_estimate_readback(
    estimate_data: Dict[str, Any], readback: Dict[str, Any],
    *, organization_id: str = "",
) -> Dict[str, Any]:
    """Verify an estimate readback against the complete authorized request."""
    report = _new_report()
    expected = {
        "customer_id": _get(estimate_data, "customer_id"),
        "currency_code": _get(estimate_data, "currency_code", "currency"),
        "date": _get(estimate_data, "date", "estimate_date"),
        "reference_number": _get(estimate_data, "reference_number"),
        "total": _get(estimate_data, "total", "grand_total"),
        "sub_total": _get(estimate_data, "sub_total", "subtotal"),
        "tax_total": _get(estimate_data, "tax_total"),
        "discount_total": _get(estimate_data, "discount_total"),
        "terms": _get(estimate_data, "terms", "delivery_terms"),
    }
    observed = {
        "customer_id": _get(readback, "customer_id"),
        "currency_code": _get(readback, "currency_code", "currency"),
        "date": _get(readback, "date", "estimate_date"),
        "reference_number": _get(readback, "reference_number"),
        "total": _get(readback, "total", "grand_total"),
        "sub_total": _get(readback, "sub_total", "subtotal"),
        "tax_total": _get(readback, "tax_total", "tax_amount"),
        "discount_total": _get(readback, "discount_total"),
        "terms": _get(readback, "terms"),
    }
    _compare_scalar(report, "customer_id", expected["customer_id"],
                    observed["customer_id"], normalizer=_text)
    _compare_scalar(report, "currency_code", expected["currency_code"],
                    observed["currency_code"], normalizer=_currency)
    _compare_date(report, "date", expected["date"], observed["date"])
    _compare_scalar(report, "reference_number",
                    expected["reference_number"],
                    observed["reference_number"], normalizer=_text)
    _compare_decimal(report, "total", expected["total"], observed["total"])
    _compare_decimal(report, "sub_total", expected["sub_total"],
                     observed["sub_total"])
    _compare_decimal(report, "tax_total", expected["tax_total"],
                     observed["tax_total"])
    _compare_decimal(report, "discount_total", expected["discount_total"],
                     observed["discount_total"])
    _compare_scalar(report, "terms", expected["terms"], observed["terms"],
                    normalizer=_text)
    observed_org = _get(readback, "organization_id")
    if organization_id and observed_org not in (None, ""):
        _compare_scalar(report, "organization_id", organization_id,
                        observed_org, normalizer=_text)
    expected_lines = _get(estimate_data, "line_items", "lines") or []
    _compare_lines(report, [row for row in expected_lines
                            if isinstance(row, dict)],
                   _observed_lines(readback))
    return _finish(report, readback)


def verify_bill_readback(
    proposal: Dict[str, Any], payload: Dict[str, Any],
    readback: Dict[str, Any], *, organization_id: str = "",
) -> Dict[str, Any]:
    """Verify a bill readback against the exact authorized provider payload."""
    report = _new_report()
    expected = {
        "vendor_id": _get(payload, "vendor_id"),
        "currency_code": _get(payload, "currency_code"),
        "date": _get(payload, "date"),
        "due_date": _get(payload, "due_date"),
        "reference_number": _get(payload, "reference_number",
                                 "bill_number"),
        "total": _get(proposal, "document_total"),
        "sub_total": _get(proposal, "line_subtotal"),
        "tax_total": _get(proposal, "tax_total"),
        "discount_total": _get(proposal, "credit_total"),
    }
    observed = {
        "vendor_id": _get(readback, "vendor_id"),
        "currency_code": _get(readback, "currency_code", "currency"),
        "date": _get(readback, "date", "bill_date"),
        "due_date": _get(readback, "due_date"),
        "reference_number": _get(readback, "reference_number"),
        "total": _get(readback, "total", "grand_total"),
        "sub_total": _get(readback, "sub_total", "subtotal"),
        "tax_total": _get(readback, "tax_total", "tax_amount"),
        "discount_total": _get(readback, "discount_total"),
    }
    _compare_scalar(report, "vendor_id", expected["vendor_id"],
                    observed["vendor_id"], normalizer=_text)
    _compare_scalar(report, "currency_code", expected["currency_code"],
                    observed["currency_code"], normalizer=_currency)
    _compare_date(report, "date", expected["date"], observed["date"])
    _compare_date(report, "due_date", expected["due_date"],
                  observed["due_date"])
    _compare_scalar(report, "reference_number",
                    expected["reference_number"],
                    observed["reference_number"], normalizer=_text)
    _compare_decimal(report, "total", expected["total"], observed["total"])
    _compare_decimal(report, "sub_total", expected["sub_total"],
                     observed["sub_total"])
    _compare_decimal(report, "tax_total", expected["tax_total"],
                     observed["tax_total"])
    if _decimal(expected["discount_total"]) not in (None, Decimal("0")):
        _compare_decimal(report, "discount_total", expected["discount_total"],
                         observed["discount_total"])
    observed_org = _get(readback, "organization_id")
    if organization_id and observed_org not in (None, ""):
        _compare_scalar(report, "organization_id", organization_id,
                        observed_org, normalizer=_text)
    expected_lines = _get(payload, "line_items", "lines") or []
    _compare_lines(report, [row for row in expected_lines
                            if isinstance(row, dict)],
                   _observed_lines(readback))
    return _finish(report, readback)
