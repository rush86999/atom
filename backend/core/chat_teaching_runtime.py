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


def extract_method_row(message: str, method: Any) -> Dict[str, Any]:
    """Backward-compatible projection of the validated operand extraction."""
    from core.method_operands import extract_operands

    extracted = extract_operands(message, method)
    return {
        "row": extracted.get("row") or {},
        "operands": {
            row["concept"]: {
                "value": row["raw_value"],
                "unit": row.get("normalized_unit") or row.get("required_unit"),
                "column": row.get("column"),
            }
            for row in extracted.get("validated_inputs") or []
        },
        "missing": [
            q.get("column") or q.get("concept")
            for q in extracted.get("questions") or []
            if q.get("reason") == "missing"
        ],
        "status": extracted.get("status"),
        "questions": extracted.get("questions") or [],
        "validated_inputs": extracted.get("validated_inputs") or [],
    }


def execute_method_lesson(
    entry: Dict[str, Any],
    message: str,
    *,
    task_context: Optional[Dict[str, Any]] = None,
    workspace_id: Optional[str] = None,
    operand_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract, validate and execute one method, returning a receipt.

    This function proves arithmetic only. It never returns a whole-task
    completed verdict; the caller submits the receipt to the obligation /
    finalization path.
    """
    from core.conversation_learning import apply_lesson_method, method_from_lesson
    from core.method_operands import extract_operands

    method = method_from_lesson(entry)
    if method is None:
        return {"status": "not_executable", "reason": "lesson_has_no_method"}
    extracted = extract_operands(
        message, method, overrides=operand_overrides or {})
    if extracted.get("status") != "ready":
        return {
            "status": extracted.get("status") or "needs_clarification",
            "questions": list(extracted.get("questions") or []),
            "validated_inputs": list(
                extracted.get("validated_inputs") or []),
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
    validated_inputs = [
        {
            **row,
            "value": (str(row.get("value"))
                      if row.get("value") is not None else None),
        }
        for row in (extracted.get("validated_inputs") or [])
    ]
    operands = {
        row["concept"]: {
            "value": row["raw_value"],
            "unit": row.get("normalized_unit") or row.get("required_unit"),
            "column": row.get("column"),
            "unit_status": row.get("unit_status"),
            "unit_authority": row.get("unit_authority"),
            "span": row.get("span"),
        }
        for row in validated_inputs
    }
    operand_text = ", ".join(
        f"{row['concept']}={row['raw_value']}"
        + (f" {row.get('normalized_unit')}" if row.get("normalized_unit")
           else "")
        for row in validated_inputs
    )
    value = str(result.get("value") or "")
    places = getattr(method, "rounding", {}).get("places")
    if places is not None:
        try:
            value = f"{Decimal(value):.{int(places)}f}"
        except (InvalidOperation, ValueError, TypeError):
            pass
    unit = str(result.get("unit") or "")
    receipt = {
        "status": "applied",
        "operation": result.get("operation"),
        "validated_inputs": validated_inputs,
        "value": value,
        "unit": unit,
        "lesson_ref": {"id": lesson_id, "revision": revision},
        "input_evidence": [
            {
                "concept": row["concept"],
                "column": row.get("column"),
                "raw_value": row.get("raw_value"),
                "raw_unit": row.get("raw_unit"),
                "normalized_unit": row.get("normalized_unit"),
                "required_unit": row.get("required_unit"),
                "unit_status": row.get("unit_status"),
                "unit_authority": row.get("unit_authority"),
                "span": row.get("span"),
                "source": row.get("source"),
            }
            for row in validated_inputs
        ],
        "covered_obligations": ["calculation"],
        "input_totals": dict(result.get("input_totals") or {}),
        "assumptions": list(result.get("assumptions") or []),
    }
    content = (
        f"Calculation receipt from lesson {lesson_id} rev {revision}: "
        f"{result.get('operation')}({operand_text}) = {value}"
        + (f" {unit}" if unit else "")
        + ". The arithmetic was run by the deterministic calculator; "
        "this receipt covers the calculation only."
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
        "validated_inputs": validated_inputs,
        "calculation_receipt": receipt,
        "method": method,
        "deterministic_delivery": True,
    }
