"""Map runtime spreadsheet rows into quote line items.

This is a deterministic data-shaping capability, not pricing logic: it maps
column names, validates required values and normalizes an explicit percentage
or amount discount into the line-item contract consumed by ``quote.calculate``.
No customer, SKU, price or business rule is embedded here.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence

from core.assignment_executor import (
    NeedsContext,
    register_assignment_adapter,
)

MAX_ROWS = 500


def _text(value: Any) -> str:
    # Preserve zero, False and other falsy executable values as text; only
    # None/absent is missing. `0 or ""` would turn a zero discount into a gap.
    return "" if value is None else str(value).strip()


def _decimal(value: Any, field: str, row_number: int) -> Decimal:
    text = _text(value)
    if not text:
        raise NeedsContext({
            "concept": "quote_row",
            "reason": f"row {row_number} has no {field}",
            "question": f"What {field} applies to row {row_number}?",
            "affected_subjects": [f"row {row_number}"],
            "kind": "missing_evidence",
        })
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise NeedsContext({
            "concept": "quote_row",
            "reason": f"row {row_number} {field} is not a decimal",
            "question": f"What {field} applies to row {row_number}?",
            "affected_subjects": [f"row {row_number}"],
            "kind": "missing_evidence",
        }) from exc
    if not number.is_finite():
        raise NeedsContext({
            "concept": "quote_row",
            "reason": f"row {row_number} {field} is not finite",
            "question": f"What {field} applies to row {row_number}?",
            "affected_subjects": [f"row {row_number}"],
            "kind": "missing_evidence",
        })
    return number


def lines_from_rows(
    *,
    rows: Sequence[Dict[str, Any]],
    columns: Optional[Dict[str, str]] = None,
    defaults: Optional[Dict[str, Any]] = None,
    discount_mode: str = "percent",
    discount_authority: str = "row-evidence",
    source_ref: Optional[Dict[str, Any]] = None,
    source_identity: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return normalized line items; refuse rows with missing identity/value.

    ``source_identity`` is the accepted read receipt's resource/version/hash.
    A caller-supplied ``source_ref`` that conflicts with it is refused rather
    than copied into pricing evidence.
    """
    columns = dict(columns or {})
    defaults = dict(defaults or {})
    mode = str(discount_mode or "percent").strip().lower()
    if mode not in ("percent", "amount"):
        raise NeedsContext({
            "concept": "quote_row",
            "reason": f"unsupported discount mode {discount_mode!r}",
            "question": "Is the row discount a percentage or an amount?",
            "kind": "business_decision",
        })
    identity_scope = dict(source_identity or source_ref or {})
    if source_identity and source_ref:
        for field in ("resource_id", "version", "sha256"):
            supplied = _text(source_ref.get(field))
            accepted = _text(source_identity.get(field))
            if supplied and accepted and supplied != accepted:
                raise NeedsContext({
                    "concept": "source_identity_conflict",
                    "reason": (
                        f"the supplied {field} conflicts with the accepted "
                        "read receipt"),
                    "question": (
                        f"Which source {field} governs these rows?"),
                    "checked_evidence": [f"supplied={supplied}",
                                         f"receipt={accepted}"],
                    "kind": "missing_evidence",
                })
    lines: List[Dict[str, Any]] = []
    for index, row in enumerate(list(rows or [])[:MAX_ROWS], start=1):
        if not isinstance(row, dict):
            continue
        def value(field: str) -> Any:
            key = columns.get(field, field)
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
            return defaults.get(field)
        item_id = _text(value("item_id"))
        if not item_id:
            raise NeedsContext({
                "concept": "quote_row",
                "reason": f"row {index} has no item identity",
                "question": f"Which item does row {index} describe?",
                "affected_subjects": [f"row {index}"],
                "kind": "missing_evidence",
            })
        quantity = _decimal(value("quantity"), "quantity", index)
        unit_price = _decimal(value("unit_price"), "unit_price", index)
        if quantity <= 0:
            raise NeedsContext({
                "concept": "quote_row",
                "reason": f"row {index} quantity must be positive",
                "question": f"What quantity applies to {item_id}?",
                "affected_subjects": [item_id],
                "kind": "missing_evidence",
            })
        if unit_price < 0:
            raise NeedsContext({
                "concept": "quote_row",
                "reason": f"row {index} price must not be negative",
                "question": f"What price applies to {item_id}?",
                "affected_subjects": [item_id],
                "kind": "missing_evidence",
            })
        line = {
            "item_id": item_id,
            "description": _text(value("description")) or item_id,
            "quantity": str(quantity),
            "unit": _text(value("unit")) or "each",
            "pack_size": _text(value("pack_size")) or "1",
            "unit_price": str(unit_price),
            "price_basis": _text(value("price_basis")) or "contract",
            "currency": _text(value("currency")).upper(),
            "category": _text(value("category")),
            "source_ref": {
                **identity_scope,
                "resource_id": identity_scope.get("resource_id")
                or row.get("resource_id"),
                "version": identity_scope.get("version")
                or row.get("version"),
                "row": row.get("__row"),
            },
            "evidence": [{
                **identity_scope,
                "resource_id": identity_scope.get("resource_id")
                or row.get("resource_id"),
                "version": identity_scope.get("version")
                or row.get("version"),
                "row": row.get("__row"),
            }],
        }
        if not line["currency"]:
            raise NeedsContext({
                "concept": "quote_row",
                "reason": f"row {index} has no explicit currency",
                "question": f"What currency applies to {item_id}?",
                "affected_subjects": [item_id],
                "kind": "missing_evidence",
            })
        raw_discount = value("discount")
        if raw_discount not in (None, ""):
            discount = _decimal(raw_discount, "discount", index)
            if discount < 0:
                raise NeedsContext({
                    "concept": "quote_row",
                    "reason": f"row {index} discount must not be negative",
                    "question": f"What discount applies to {item_id}?",
                    "affected_subjects": [item_id],
                    "kind": "missing_evidence",
                })
            if mode == "percent":
                rate = discount / Decimal("100")
            else:
                gross = quantity * unit_price
                if gross == 0:
                    raise NeedsContext({
                        "concept": "quote_row",
                        "reason": (
                            f"row {index} amount discount has a zero gross"),
                        "question": f"What discount applies to {item_id}?",
                        "affected_subjects": [item_id],
                        "kind": "missing_evidence",
                    })
                rate = discount / gross
            if rate != 0:
                line["discount_rate"] = str(rate)
                line["discount_authority"] = discount_authority
        lines.append(line)
    if not lines:
        raise NeedsContext({
            "concept": "quote_rows",
            "reason": "the returned source contained no usable quote rows",
            "question": "Which authorized price rows apply to this quote?",
            "kind": "missing_evidence",
        })
    return lines


@register_assignment_adapter(
    "quote.lines_from_rows",
    description="Map runtime rows to quote line items with explicit columns",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "allow_standing_authorization": False},
)
async def _lines_from_rows(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    lines = lines_from_rows(
        rows=inputs.get("rows") or [],
        columns=inputs.get("columns") or {},
        defaults=inputs.get("defaults") or {},
        discount_mode=str(inputs.get("discount_mode") or "percent"),
        discount_authority=str(
            inputs.get("discount_authority") or "row-evidence"),
        source_ref=inputs.get("source_ref") or {},
        source_identity=inputs.get("source_identity") or {},
    )
    return {
        "status": "applied",
        "summary": f"mapped {len(lines)} quote row(s)",
        "line_items": lines,
        "selected_count": len(lines),
        "truncated": len(inputs.get("rows") or []) > MAX_ROWS,
    }


def estimate_lines_from_calculated_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    account_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Flatten calculated rows into provider estimate line items.

    Source references, evidence, discount-rule snapshots and gross/net
    intermediates stay in the calculation receipt; the provider payload keeps
    only fields the estimate operation accepts.
    """
    account_map = dict(account_map or {})
    lines: List[Dict[str, Any]] = []
    for raw in list(rows or [])[:MAX_ROWS]:
        if not isinstance(raw, dict):
            continue
        item_id = _text(raw.get("item_id"))
        line = {
            "item_id": item_id,
            "name": _text(raw.get("description")) or item_id or "Quote line",
            "quantity": _text(raw.get("quantity")),
            "rate": _text(raw.get("unit_price")),
        }
        if raw.get("unit"):
            line["unit"] = _text(raw.get("unit"))
        if account_map.get(item_id):
            line["account_id"] = account_map[item_id]
        rate = _text(raw.get("discount_rate"))
        if rate:
            try:
                points = Decimal(rate) * Decimal("100")
            except (InvalidOperation, ValueError):
                points = Decimal("0")
            if points != 0:
                line["discount_percent"] = str(points)
        lines.append(line)
    if not lines:
        raise NeedsContext({
            "concept": "quote_rows",
            "reason": "the calculated quote has no line items to send",
            "question": "Which calculated lines should be sent to the provider?",
            "kind": "missing_evidence",
        })
    return lines


@register_assignment_adapter(
    "quote.estimate_lines",
    description="Flatten calculated rows into provider estimate line items",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "allow_standing_authorization": False},
)
async def _estimate_lines(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    lines = estimate_lines_from_calculated_rows(
        inputs.get("rows") or [],
        account_map=inputs.get("account_map") or {},
    )
    return {
        "status": "applied",
        "summary": f"prepared {len(lines)} estimate line(s)",
        "line_items": lines,
        "selected_count": len(lines),
    }
