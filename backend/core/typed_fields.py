"""Typed requested-field specifications (domain-independent job
completion guide, 2026-10-07, step 2).

A requested field's TYPE comes from the JOB's contract, not from the
data's shape. Pricing is one application adapter, not a universal rule:
the monetary regexes in research_continuation never decide what a field
IS. Initial supported types: decimal, money, integer, duration, date,
boolean, text. Anything else is explicitly unsupported — this is not a
universal data interpreter.

Pure helpers, no IO: unit-testable without fixtures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

SUPPORTED_TYPES = frozenset({
    "decimal", "money", "integer", "duration", "date", "boolean", "text"})


@dataclass(frozen=True)
class FieldSpec:
    """One requested field: stable key, accepted source labels, value
    type, optional unit/currency/basis, teaching provenance."""
    key: str
    labels: tuple
    value_type: str = "text"
    unit: Optional[str] = None
    currency: Optional[str] = None
    basis: Optional[str] = None
    lesson_id: Optional[str] = None

    def __post_init__(self):
        if self.value_type not in SUPPORTED_TYPES:
            raise ValueError(
                f"unsupported field type {self.value_type!r} for "
                f"{self.key!r} — supported: {sorted(SUPPORTED_TYPES)}")


_INT_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d{1,3}(?:[,_]\d{3})+|\d+)"
                         r"(?:[.,]\d+)?$")
_MONEY_RE = re.compile(
    r"^[$€£\s]*([+-]?(?:\d{1,3}(?:[,_]\d{3})+|\d+)(?:[.,]\d+)?)"
    r"\s*(?:[$€£]|cad|usd|eur|gbp)?\s*$", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"^(\d+(?:\.\d+)?)\s*(hours?|hrs?|days?|weeks?|minutes?|mins?)$",
    re.IGNORECASE)
_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?$")
_BOOL_TRUE = frozenset({"true", "yes", "1", "y"})
_BOOL_FALSE = frozenset({"false", "no", "0", "n"})


def parse_typed(raw: str, spec: FieldSpec) -> Optional[Dict[str, Any]]:
    """Parse a raw source string against the field's declared type.
    Returns {"value": …, "unit"/"currency": …, "raw": …} or None when
    the raw value cannot satisfy the type. A matching number alone
    never binds — the caller resolves the source column first; this
    helper only parses what was explicitly resolved to the field."""
    s = str(raw if raw is not None else "").strip()
    if not s:
        return None
    t = spec.value_type
    if t == "text":
        return {"value": s, "raw": s}
    if t == "boolean":
        low = s.lower()
        if low in _BOOL_TRUE:
            return {"value": True, "raw": s}
        if low in _BOOL_FALSE:
            return {"value": False, "raw": s}
        return None
    if t == "integer":
        if _INT_RE.match(s):
            return {"value": int(s), "raw": s}
        return None
    if t == "decimal":
        if _DECIMAL_RE.match(s.replace(",", "")):
            try:
                return {"value": Decimal(s.replace(",", "")), "raw": s}
            except InvalidOperation:
                return None
        return None
    if t == "money":
        m = _MONEY_RE.match(s)
        if m:
            cur = spec.currency
            if not cur:
                cm = re.search(r"cad|usd|eur|gbp|[$€£]", s, re.IGNORECASE)
                cur = cm.group(0).upper() if cm else None
            return {"value": Decimal(m.group(1).replace(",", "")),
                    "currency": cur, "raw": s}
        return None
    if t == "duration":
        m = _DURATION_RE.match(s)
        if m:
            return {"value": Decimal(m.group(1)),
                    "unit": m.group(2).lower().rstrip("s"), "raw": s}
        return None
    if t == "date":
        if _DATE_RE.match(s):
            return {"value": s, "raw": s}
        return None
    return None


def resolve_column(headers: List[str], spec: FieldSpec) -> List[str]:
    """Columns whose headers match the field's accepted labels. Order
    preserved (all candidates retained — ambiguity is the caller's)."""
    out = []
    labels = [str(l).lower() for l in spec.labels]
    for h in headers or []:
        hl = str(h).lower()
        if any(l in hl for l in labels):
            out.append(h)
    return out


def binding_passes(header: str, raw_value: Any,
                   spec: FieldSpec) -> Optional[Dict[str, Any]]:
    """One candidate column: header must match a label AND the value
    must parse as the declared type. Neither alone binds."""
    hl = str(header or "").lower()
    if not any(str(l).lower() in hl for l in spec.labels):
        return None
    return parse_typed(raw_value, spec)


# The pricing APPLICATION adapter: the historical default contract.
PRICING_FIELD = FieldSpec(
    key="price", labels=("price", "cost", "list", "net", "cad"),
    value_type="money", basis="pricing")
