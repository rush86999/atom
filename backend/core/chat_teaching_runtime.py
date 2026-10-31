"""Deterministic chat execution for conversation-derived methods.

The method is the validated, executable part of a promoted lesson. Chat must
not narrate a different multiplier than the method declares. This module
extracts the method's declared operands from the user's message and runs the
existing ``apply_lesson_method`` allowlist — the same Decimal arithmetic the
assignment path uses. Narration is rendered from that result; the model is not
asked to redo the calculation.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_UNIT_RE = re.compile(r"[A-Za-z%$€£][A-Za-z0-9%$€£/._-]{0,19}")


_CALC_SHAPE_RE = re.compile(
    r"\b(?:calculate|calculation|compute|price|pricing|total|cost|"
    r"multiply|multiplier|discount|rate|amount|qty|quantity)\b",
    re.IGNORECASE,
)


def looks_like_calculation(message: str) -> bool:
    text = str(message or "")
    return bool(_CALC_SHAPE_RE.search(text) and re.search(r"\d", text))


def _number_after(message: str, label: str) -> Optional[str]:
    if not label:
        return None
    pattern = re.compile(
        r"(?<![A-Za-z0-9_])" + re.escape(str(label)) +
        r"\s*(?:=|:)?\s*(?:[$€£]\s*)?(" + _NUMBER_RE.pattern + r")",
        re.IGNORECASE,
    )
    match = pattern.search(str(message or ""))
    if not match:
        return None
    return match.group(1).replace(",", "")


def _unit_after(message: str, label: str, expected: str = "") -> str:
    if not label:
        return ""
    pattern = re.compile(
        r"(?<![A-Za-z0-9_])" + re.escape(str(label)) +
        r"\s*(?:=|:)?\s*(?:[$€£]\s*)?(?:[-+]?\d[\d,]*(?:\.\d+)?)"
        r"\s*(" + _UNIT_RE.pattern + r")?",
        re.IGNORECASE,
    )
    match = pattern.search(str(message or ""))
    if not match:
        return ""
    token = str(match.group(1) or "").strip()
    if not token:
        return ""
    # "Qty 2 and Price 7.50" must not read "and" as the unit. Only accept a
    # token that is the method's declared unit or a small generic unit
    # vocabulary; everything else is left to the method's own unit.
    known = {
        "unit", "units", "kg", "lb", "lbs", "g", "oz", "usd", "eur", "gbp",
        "dollar", "dollars", "hour", "hours", "day", "days", "week", "weeks",
        "month", "months", "year", "years", "%", "$", "€", "£",
    }
    if expected and token.casefold() == str(expected).casefold():
        return token
    if token.casefold() in known:
        return token
    return ""


def extract_method_row(message: str, method: Any) -> Dict[str, Any]:
    """Extract the method's declared inputs from a normal chat message.

    Only explicit ``label value`` / ``label: value`` shapes are accepted.
    Missing or ambiguous operands block execution instead of guessing.
    """
    row: Dict[str, Any] = {}
    operands: Dict[str, Any] = {}
    missing: List[str] = []
    for item in getattr(method, "inputs", []) or []:
        concept = str(getattr(item, "concept", "") or "")
        column = str(getattr(item, "column", "") or "")
        value = None
        used_label = ""
        for label in (column, concept):
            value = _number_after(message, label)
            if value is not None:
                used_label = label
                break
        if value is None:
            missing.append(column or concept or "input")
            continue
        unit = str(getattr(item, "unit", "") or "")
        declared_unit = _unit_after(message, used_label, unit)
        if declared_unit and unit and declared_unit.casefold() != unit.casefold():
            # A unit the method does not declare is a real ambiguity, not
            # something to coerce silently.
            missing.append(f"{column or concept}:unit")
            continue
        row[column or concept] = value
        operands[concept or column] = {
            "value": value,
            "unit": unit,
            "column": column or concept,
        }
    return {"row": row, "operands": operands, "missing": missing}


def execute_method_lesson(
    entry: Dict[str, Any],
    message: str,
    *,
    task_context: Optional[Dict[str, Any]] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one applicable method lesson through the existing allowlist."""
    from core.conversation_learning import apply_lesson_method, method_from_lesson

    method = method_from_lesson(entry)
    if method is None:
        return {"status": "not_executable", "reason": "lesson_has_no_method"}
    extracted = extract_method_row(message, method)
    if extracted.get("missing"):
        return {
            "status": "needs_inputs",
            "missing": list(extracted["missing"]),
            "method": method,
        }
    result = apply_lesson_method(
        entry, [extracted["row"]],
        context=task_context, workspace_id=workspace_id)
    if result.get("status") != "applied":
        return {"status": "blocked", "reason": result.get("reason"),
                "detail": result, "method": method}
    lesson_id = str(entry.get("id") or "")
    revision = int(entry.get("revision") or 1)
    operands = extracted.get("operands") or {}
    operand_text = ", ".join(
        f"{concept}={item.get('value')}"
        + (f" {item.get('unit')}" if item.get("unit") else "")
        for concept, item in operands.items()
    )
    value = str(result.get("value") or "")
    places = getattr(method, "rounding", {}).get("places")
    if places is not None:
        try:
            value = f"{Decimal(value):.{int(places)}f}"
        except (InvalidOperation, ValueError, TypeError):
            pass
    unit = str(result.get("unit") or "")
    content = (
        f"Using the taught method from lesson {lesson_id} rev {revision}: "
        f"{result.get('operation')}({operand_text}) = {value}"
        + (f" {unit}" if unit else "")
        + ". This result comes from the deterministic calculator, not "
        "free-form estimation."
    )
    return {
        "status": "applied",
        "content": content,
        "lesson_id": lesson_id,
        "lesson_revision": revision,
        "operation": result.get("operation"),
        "operands": operands,
        "value": value,
        "unit": unit,
        "input_totals": dict(result.get("input_totals") or {}),
        "assumptions": list(result.get("assumptions") or []),
        "method": method,
        "deterministic_delivery": True,
        "_recorded_outcome": {"state": "completed", "work_turn": True},
    }
