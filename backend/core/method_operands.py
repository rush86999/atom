"""Bounded operand extraction and validation for taught chat methods.

This module is deliberately narrow: it accepts the method's declared labels
followed by an explicit number and optional unit. It does not try to solve
arbitrary natural language. Every candidate keeps its raw value, raw unit,
span and source so the caller can ask for clarification instead of choosing a
first/last/nearest value.

No currency conversion is implemented here. An explicit unit that differs
from the method's required unit is incompatible; an unknown unit is
unresolved. The caller must clarify both.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)*")
_STRICT_COMMA_RE = re.compile(r"^[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?$")
_CONNECTOR_WORDS = {
    "and", "or", "then", "with", "at", "for", "plus", "also", "to", "vs",
    "versus", "but", "while", "after", "before", "per", "each",
}
_UNIT_ALIASES: Dict[str, set] = {
    "USD": {"usd", "$", "us$", "dollar", "dollars", "us dollar",
            "us dollars", "american dollar", "american dollars"},
    "CAD": {"cad", "c$", "can$", "canadian dollar", "canadian dollars"},
    "EUR": {"eur", "€", "euro", "euros"},
    "GBP": {"gbp", "£", "pound", "pounds", "sterling"},
    "AUD": {"aud", "a$", "australian dollar", "australian dollars"},
    "INR": {"inr", "₹", "rupee", "rupees"},
    "units": {"unit", "units", "pc", "pcs", "piece", "pieces", "ea", "each"},
    "%": {"%", "percent", "percentage"},
    "kg": {"kg", "kilogram", "kilograms"},
    "g": {"g", "gram", "grams"},
    "lb": {"lb", "lbs", "pound", "pounds"},
    "oz": {"oz", "ounce", "ounces"},
    "hour": {"hour", "hours", "hr", "hrs"},
    "day": {"day", "days"},
    "week": {"week", "weeks"},
    "month": {"month", "months"},
    "year": {"year", "years"},
    "lot": {"lot", "lots"},
    "each": {"each"},
}
_KNOWN_CURRENCY_CODES = {
    "USD", "CAD", "EUR", "GBP", "AUD", "INR", "JPY", "CNY", "CHF", "NZD",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _labels_for(item: Any) -> List[str]:
    labels: List[str] = []
    for raw in (
            getattr(item, "column", ""),
            getattr(item, "concept", ""),
            str(getattr(item, "concept", "") or "").replace("_", " ")):
        label = _clean(raw)
        if label and label.casefold() not in {x.casefold() for x in labels}:
            labels.append(label)
    return labels


def _parse_decimal(raw: str) -> Optional[Decimal]:
    text = str(raw or "").strip()
    if not text:
        return None
    if "," in text and not _STRICT_COMMA_RE.match(text):
        return None
    try:
        return Decimal(text.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def normalize_unit(raw_unit: str, expected_unit: str = "") -> Dict[str, Any]:
    """Normalize one explicit unit without inventing a conversion."""
    text = _clean(raw_unit)
    expected = _clean(expected_unit)
    if not text:
        if expected:
            return {
                "normalized_unit": expected,
                "unit_status": "compatible",
                "unit_authority": "method_declared",
                "raw_unit": "",
            }
        return {
            "normalized_unit": "",
            "unit_status": "unresolved",
            "unit_authority": "",
            "raw_unit": "",
        }
    low = text.casefold()
    # "pound" is context-dependent; the method's declared unit decides.
    if low in {"pound", "pounds"} and expected.casefold() in {"gbp", "lb", "lbs"}:
        normalized = expected
    else:
        normalized = ""
        for canonical, aliases in _UNIT_ALIASES.items():
            if low in aliases:
                normalized = canonical
                break
    if not normalized:
        code = text.upper()
        if re.fullmatch(r"[A-Z]{3}", code) and code in _KNOWN_CURRENCY_CODES:
            normalized = code
        else:
            return {
                "normalized_unit": "",
                "unit_status": "unknown",
                "unit_authority": "user_message",
                "raw_unit": text,
            }
    if not expected:
        return {
            "normalized_unit": normalized,
            "unit_status": "unresolved",
            "unit_authority": "user_message",
            "raw_unit": text,
        }
    if normalized.casefold() == expected.casefold():
        status = "compatible"
    else:
        status = "incompatible"
    return {
        "normalized_unit": normalized,
        "unit_status": status,
        "unit_authority": "user_message",
        "raw_unit": text,
    }


def _unit_token(tail: str) -> str:
    """The explicit unit token immediately after a number, or ''.

    Connectors are not units. ``per unit`` / ``each unit`` carry the unit
    after the connector.
    """
    text = str(tail or "")
    match = re.match(
        r"\s*(?:(?P<pre>per|each)\s+)?"
        r"(?P<unit>[A-Za-z%$€£][A-Za-z0-9%$€£/._-]*(?:\s+[A-Za-z]+)?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    pre = str(match.group("pre") or "").casefold()
    token = _clean(match.group("unit")).strip(".,;:!?")
    if not token:
        return ""
    first = token.split()[0].casefold()
    if not pre and first in _CONNECTOR_WORDS:
        return ""
    # Stop a multi-word unit at a connector/label-looking word.
    words = token.split()
    if len(words) > 1 and words[1].casefold() in _CONNECTOR_WORDS:
        token = words[0]
    return token


def _candidate_from_parts(
    *,
    concept: str,
    column: str,
    label: str,
    raw_value: str,
    prefix_unit: str,
    suffix_unit: str,
    span: List[int],
    expected_unit: str,
    source: str = "user_message",
) -> Dict[str, Any]:
    value = _parse_decimal(raw_value)
    prefix = normalize_unit(prefix_unit, expected_unit)
    suffix = normalize_unit(suffix_unit, expected_unit)
    raw_units = [item for item in (prefix_unit, suffix_unit) if item]
    raw_unit = " ".join(raw_units)
    if prefix_unit and suffix_unit:
        p_norm = prefix.get("normalized_unit") or ""
        s_norm = suffix.get("normalized_unit") or ""
        if p_norm and s_norm and p_norm.casefold() != s_norm.casefold():
            unit = {
                "normalized_unit": p_norm,
                "unit_status": "incompatible",
                "unit_authority": "user_message",
                "raw_unit": raw_unit,
            }
        elif p_norm or s_norm:
            unit = prefix if prefix.get("unit_status") != "unknown" else suffix
            unit["raw_unit"] = raw_unit
        else:
            unit = {
                "normalized_unit": "",
                "unit_status": "unknown",
                "unit_authority": "user_message",
                "raw_unit": raw_unit,
            }
    elif prefix_unit:
        unit = prefix
    elif suffix_unit:
        unit = suffix
    else:
        unit = normalize_unit("", expected_unit)
    return {
        "concept": concept,
        "column": column,
        "label": label,
        "raw_value": raw_value,
        "value": value,
        "raw_unit": unit["raw_unit"],
        "normalized_unit": unit["normalized_unit"],
        "required_unit": _clean(expected_unit),
        "unit_status": unit["unit_status"],
        "unit_authority": unit["unit_authority"],
        "span": [int(span[0]), int(span[1])],
        "source": source,
        "malformed": value is None,
    }


def _candidate_for_match(
    message: str,
    match: re.Match,
    *,
    concept: str,
    column: str,
    label: str,
    expected_unit: str,
) -> Dict[str, Any]:
    raw_value = match.group("number")
    prefix_unit = str(match.groupdict().get("prefix") or "")
    tail_start = match.end("number")
    tail = message[tail_start:tail_start + 60]
    suffix_unit = _unit_token(tail)
    span_end = tail_start + len(suffix_unit)
    return _candidate_from_parts(
        concept=concept, column=column, label=label,
        raw_value=raw_value, prefix_unit=prefix_unit,
        suffix_unit=suffix_unit, span=[match.start(), span_end],
        expected_unit=expected_unit,
    )


def extract_candidates(
    message: str,
    item: Any,
    *,
    expected_unit: str = "",
) -> List[Dict[str, Any]]:
    """All explicit candidates for one declared method input."""
    text = str(message or "")
    concept = _clean(getattr(item, "concept", ""))
    column = _clean(getattr(item, "column", ""))
    expected = _clean(expected_unit or getattr(item, "unit", ""))
    out: List[Dict[str, Any]] = []
    seen = set()
    for label in _labels_for(item):
        pattern = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(label) +
            r"\s*(?:=|:)?\s*(?P<prefix>[$€£])?\s*"
            r"(?P<number>" + _NUMBER_RE.pattern + r")",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            candidate = _candidate_for_match(
                text, match, concept=concept, column=column,
                label=label, expected_unit=expected)
            key = (candidate["span"][0], candidate["span"][1],
                   candidate["raw_value"], candidate["raw_unit"].casefold())
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
    out.sort(key=lambda row: row["span"][0])
    return out


def _dedupe_equal(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(candidates) <= 1:
        return candidates
    values = {str(row.get("raw_value")) for row in candidates}
    units = {str(row.get("normalized_unit") or "").casefold()
             for row in candidates}
    statuses = {str(row.get("unit_status")) for row in candidates}
    if len(values) == 1 and len(units) <= 1 and "unknown" not in statuses \
            and "incompatible" not in statuses:
        return [candidates[0]]
    return candidates


def validate_candidates(
    candidates: List[Dict[str, Any]],
    item: Any,
) -> Dict[str, Any]:
    """Validate one input's candidates against the accepted method."""
    concept = _clean(getattr(item, "concept", "")) or _clean(
        getattr(item, "column", ""))
    column = _clean(getattr(item, "column", "")) or concept
    required_unit = _clean(getattr(item, "unit", ""))
    candidates = _dedupe_equal(list(candidates or []))
    if not candidates:
        return {
            "status": "missing",
            "concept": concept,
            "column": column,
            "required_unit": required_unit,
            "question": {
                "concept": concept,
                "column": column,
                "reason": "missing",
                "candidates": [],
                "required_unit": required_unit,
            },
        }
    malformed = [row for row in candidates if row.get("malformed")]
    if malformed:
        return {
            "status": "malformed",
            "concept": concept,
            "column": column,
            "required_unit": required_unit,
            "question": {
                "concept": concept,
                "column": column,
                "reason": "malformed_value",
                "candidates": candidates,
                "required_unit": required_unit,
            },
        }
    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "concept": concept,
            "column": column,
            "required_unit": required_unit,
            "question": {
                "concept": concept,
                "column": column,
                "reason": "ambiguous_value",
                "candidates": candidates,
                "required_unit": required_unit,
            },
        }
    candidate = dict(candidates[0])
    unit_status = str(candidate.get("unit_status") or "")
    if unit_status == "incompatible":
        return {
            "status": "unit_incompatible",
            "concept": concept,
            "column": column,
            "required_unit": required_unit,
            "question": {
                "concept": concept,
                "column": column,
                "reason": "incompatible_unit",
                "candidates": candidates,
                "required_unit": required_unit,
            },
        }
    if unit_status == "unknown":
        return {
            "status": "unit_unknown",
            "concept": concept,
            "column": column,
            "required_unit": required_unit,
            "question": {
                "concept": concept,
                "column": column,
                "reason": "unknown_unit",
                "candidates": candidates,
                "required_unit": required_unit,
            },
        }
    if unit_status == "unresolved":
        return {
            "status": "unit_unresolved",
            "concept": concept,
            "column": column,
            "required_unit": required_unit,
            "question": {
                "concept": concept,
                "column": column,
                "reason": "unit_unresolved",
                "candidates": candidates,
                "required_unit": required_unit,
            },
        }
    return {
        "status": "ready",
        "concept": concept,
        "column": column,
        "required_unit": required_unit,
        "validated": candidate,
    }


def extract_operands(
    message: str,
    method: Any,
    *,
    overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract and validate every declared input, or return typed questions."""
    overrides = overrides or {}
    validated: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []
    row: Dict[str, Any] = {}
    for item in getattr(method, "inputs", []) or []:
        concept = _clean(getattr(item, "concept", "")) or _clean(
            getattr(item, "column", ""))
        column = _clean(getattr(item, "column", "")) or concept
        override = overrides.get(concept) or overrides.get(column)
        if isinstance(override, dict):
            candidate = dict(override)
            candidate.setdefault("concept", concept)
            candidate.setdefault("column", column)
            candidate.setdefault("required_unit", _clean(
                getattr(item, "unit", "")))
            candidate.setdefault("source", "user_confirmation")
            candidates = [candidate]
        else:
            candidates = extract_candidates(
                message, item, expected_unit=getattr(item, "unit", ""))
        result = validate_candidates(candidates, item)
        if result["status"] == "ready":
            candidate = dict(result["validated"])
            validated.append(candidate)
            row[column] = candidate["raw_value"]
            continue
        questions.append(result["question"])
    if questions:
        status = "needs_clarification"
        if any(q.get("reason") == "ambiguous_value" for q in questions):
            status = "ambiguous_operands"
        elif any(q.get("reason") in ("incompatible_unit", "unknown_unit",
                                     "unit_unresolved") for q in questions):
            status = "unit_conflict"
        return {
            "status": status,
            "validated_inputs": validated,
            "questions": questions,
            "row": row,
        }
    return {
        "status": "ready",
        "validated_inputs": validated,
        "questions": [],
        "row": row,
    }


def parse_operand_answer(
    message: str,
    question: Dict[str, Any],
    *,
    allow_bare: bool = True,
) -> Dict[str, Any]:
    """Parse one answer through the SAME candidate-validation contract.

    Labeled answers use ``extract_candidates``; a bare answer collects every
    numeric token with its prefix/suffix unit. Multiple candidates,
    malformed tokens and incompatible/unknown units stay unresolved.
    """
    from types import SimpleNamespace

    text = str(message or "").strip()
    concept = _clean(question.get("concept"))
    column = _clean(question.get("column"))
    required = _clean(question.get("required_unit"))
    text = re.sub(
        r"^\s*(?:use|actually|correction|instead|please\s+use|"
        r"i\s+confirm|confirmed)\s*[:=-]?\s*",
        "", text, flags=re.IGNORECASE)
    item = SimpleNamespace(
        concept=concept, column=column, unit=required)
    labels = [label for label in (column, concept,
                                  concept.replace("_", " ")) if label]
    label_present = any(
        re.search(r"(?<![A-Za-z0-9_])" + re.escape(label),
                  text, re.IGNORECASE)
        for label in labels)
    if label_present:
        candidates = extract_candidates(
            text, item, expected_unit=required)
    elif allow_bare:
        candidates = []
        for match in re.finditer(
                r"(?P<prefix>[$€£])?\s*(?P<number>" +
                _NUMBER_RE.pattern + r")",
                text):
            raw_value = match.group("number")
            tail = text[match.end("number"):]
            suffix_unit = _unit_token(tail)
            candidates.append(_candidate_from_parts(
                concept=concept, column=column, label=column or concept,
                raw_value=raw_value,
                prefix_unit=str(match.group("prefix") or ""),
                suffix_unit=suffix_unit,
                span=[match.start(), match.end("number") + len(suffix_unit)],
                expected_unit=required,
                source="user_confirmation",
            ))
    else:
        candidates = []
    if not candidates:
        return {
            "status": "unresolved",
            "question": question,
            "reason": "no_explicit_value",
        }
    result = validate_candidates(candidates, item)
    if result.get("status") == "ready":
        candidate = dict(result.get("validated") or {})
        candidate["source"] = "user_confirmation"
        return {
            "status": "confirmed",
            "question": question,
            "candidate": candidate,
        }
    status = result.get("status") or "unresolved"
    reason = {
        "unit_incompatible": "incompatible_unit",
        "unit_unknown": "unknown_unit",
        "unit_unresolved": "unit_unresolved",
        "ambiguous": "ambiguous_value",
        "malformed": "malformed_value",
    }.get(status, status)
    return {
        "status": status,
        "question": question,
        "candidate": candidates[0] if candidates else None,
        "candidates": candidates,
        "reason": reason,
    }
