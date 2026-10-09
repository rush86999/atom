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


# SEPARATOR CONVENTIONS (owner directive 2026-10-07): thousands
# separators are commas-or-underscores with groups of exactly 3 after
# the first 1-3 digits; a decimal point is '.'. A comma immediately
# followed by 1-2 digits then a non-digit boundary (e.g. "12,34") is a
# DECIMAL COMMA — accepted ONLY when unambiguous (exactly two decimals,
# no thousands grouping) and normalized. Anything else is rejected.
_GRP_RE = re.compile(r"^[+-]?\d{1,3}(?:[,_]\d{3})+$")
_DEC_COMMA_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*(?:,\d{1,2})?$")
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


def _normalize_separators(s: str) -> Optional[str]:
    """Normalize a numeric string to plain dot-decimal. Conventions:
    thousands = ',' or '_' in exact groups of 3; decimal = '.'; a
    decimal COMMA is accepted only unambiguously (no dot present, the
    comma group is 1-2 digits, and remaining groups are exact 3s).
    Ambiguous shapes ('12,34' with a dot also present, '1,23,456',
    '12,345,67') are rejected."""
    t = s.strip()
    if "," not in t and "_" not in t:
        return t
    # dot present: commas/underscores must be pure thousands grouping
    if "." in t:
        whole, _, frac = t.partition(".")
        if not frac or not frac.isdigit() or not _GRP_RE.match(whole):
            return None
        return whole.replace(",", "").replace("_", "") + "." + frac
    # no dot: exact grouping, or a single trailing decimal-comma group
    if _GRP_RE.match(t):
        return t.replace(",", "").replace("_", "")
    parts = t.split(",")
    if (len(parts) >= 2 and 1 <= len(parts[-1]) <= 2
            and parts[-1].isdigit()
            and 1 <= len(parts[0].lstrip("+-")) <= 3
            and parts[0].lstrip("+-").isdigit()
            and all(len(x) == 3 and x.isdigit() for x in parts[1:-1])):
        return t.replace(",", ".")
    return None


def _valid_calendar_date(s: str) -> bool:
    """Regex shape plus calendar reality: 2026-99-99 is not a date."""
    import datetime as _dt

    try:
        _dt.date.fromisoformat(s[:10])
    except ValueError:
        return False
    return True


def _detect_currency(raw: str,
                     spec: FieldSpec) -> tuple:
    """Returns (currency-or-None, symbol-or-None). A bare $/€/£ is a
    SYMBOL, not an established currency — preserved separately.
    Declared vs explicit conflict (spec CAD, source USD) is a conflict.
    """
    sym = None
    for ch in "$€£":
        if ch in raw:
            sym = ch
            break
    explicit = None
    m = re.search(r"\b(cad|usd|eur|gbp)\b", raw, re.IGNORECASE)
    if m:
        explicit = m.group(1).upper()
    if spec.currency:
        declared = spec.currency.upper()
        if explicit and explicit != declared:
            raise ValueError(
                f"currency conflict for {spec.key!r}: field declares "
                f"{declared}, source says {explicit}")
        return declared, sym
    # no declaration: only an explicit code establishes currency
    return explicit, sym


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
        norm = _normalize_separators(s)
        if norm is None:
            return None
        try:
            return {"value": Decimal(norm), "raw": s}
        except InvalidOperation:
            return None
    if t == "money":
        m = _MONEY_RE.match(s)
        if m:
            num = _normalize_separators(m.group(1))
            if num is None:
                return None
            cur, symbol = _detect_currency(m.group(0), spec)
            return {"value": Decimal(num), "currency": cur,
                    "currency_symbol": symbol, "raw": s}
        return None
    if t == "duration":
        m = _DURATION_RE.match(s)
        if m:
            return {"value": Decimal(m.group(1)),
                    "unit": m.group(2).lower().rstrip("s"), "raw": s}
        return None
    if t == "date":
        if _DATE_RE.match(s) and _valid_calendar_date(s):
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


# IDENTIFIER-COLUMN SAFEGUARD (worker parity, round 56): a header
# naming an identifier never binds a valued field — "Price Code" carries
# a code, not a price.
IDENTIFIER_COLUMN_RE = re.compile(
    r"code|no\.?|#|part|model|id\b|serial|sku|ref", re.IGNORECASE)


def binding_passes(header: str, raw_value: Any,
                   spec: FieldSpec) -> Optional[Dict[str, Any]]:
    """One candidate column: header must match a label, must NOT be an
    identifier column, and the value must parse as the declared type.
    Neither label-match nor numeric shape alone binds."""
    hl = str(header or "").lower()
    if IDENTIFIER_COLUMN_RE.search(hl):
        return None
    if not any(str(l).lower() in hl for l in spec.labels):
        return None
    return parse_typed(raw_value, spec)


# The pricing APPLICATION adapter: the historical default contract.
PRICING_FIELD = FieldSpec(
    key="price", labels=("price", "cost", "list", "net", "cad"),
    value_type="money", basis="pricing")
