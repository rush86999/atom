"""Deterministic, taught-rule assessment for rule-expressible policies.

This module is deliberately separate from model-dependent judgment. When a
canvas manifest declares ``assessment_mode="deterministic"`` and a
``decision_rules`` list, the platform evaluates those rules against the
authoritative rows and certifies the resulting decisions without dispatching a
model. The rules are part of the versioned capability manifest, so the same
source/policy/revision binding and human-review gates apply.

A rule is::

    {"decision": "APPROVE",
     "when": [{"field": "Status", "op": "eq", "value": "Open"},
              {"field": "Amount", "op": "gte", "value": 100}],
     "basis": "Open and Amount >= 100"}

Rules are evaluated in order; the first fully matching rule wins. A condition
that references a blank/unparseable value cannot match. If no rule matches,
the fallback is REVIEW with a durable unresolved requirement, never a guessed
decision.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence

OPS = {
    "eq", "ne", "gt", "gte", "lt", "lte", "in", "contains",
    "blank", "not_blank",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _decimal(value: Any) -> Optional[Decimal]:
    text = _text(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def validate_decision_rules(
    rules: Any, *, columns: Sequence[str], decisions: Sequence[str],
) -> List[Dict[str, Any]]:
    """Validate and normalize rules against the bound columns/decisions."""
    if not isinstance(rules, list) or not rules:
        raise ValueError("decision_rules must be a non-empty list")
    allowed_decisions = {str(item).strip().upper() for item in decisions}
    allowed_fields = {str(item) for item in columns}
    cleaned: List[Dict[str, Any]] = []
    for index, raw in enumerate(rules):
        if not isinstance(raw, dict):
            raise ValueError(f"decision_rules[{index}] must be an object")
        decision = _text(raw.get("decision")).upper()
        if decision not in allowed_decisions:
            raise ValueError(
                f"decision_rules[{index}].decision '{decision}' is not in "
                "decision_options")
        conditions = raw.get("when")
        if not isinstance(conditions, list) or not conditions:
            raise ValueError(
                f"decision_rules[{index}].when must be a non-empty list")
        clean_conditions = []
        for cond in conditions:
            if not isinstance(cond, dict):
                raise ValueError(
                    f"decision_rules[{index}].when entries must be objects")
            field = _text(cond.get("field"))
            op = _text(cond.get("op")).lower()
            if field not in allowed_fields:
                raise ValueError(
                    f"decision_rules[{index}] references unbound field "
                    f"'{field}'")
            if op not in OPS:
                raise ValueError(
                    f"decision_rules[{index}] has unsupported op '{op}'")
            if op not in ("blank", "not_blank") and "value" not in cond:
                raise ValueError(
                    f"decision_rules[{index}] op '{op}' needs a value")
            clean_conditions.append({
                "field": field, "op": op,
                "value": cond.get("value"),
            })
        cleaned.append({
            "decision": decision,
            "when": clean_conditions,
            "basis": _text(raw.get("basis")) or (
                f"Matched taught rule {index + 1} for {decision}"),
        })
    return cleaned


def _condition_matches(
    cells: Dict[str, Any], condition: Dict[str, Any],
) -> Dict[str, Any]:
    """Return matched/missing for one condition (missing means no match)."""
    field = condition["field"]
    op = condition["op"]
    value = cells.get(field)
    text = _text(value)
    expected = condition.get("value")
    if op == "blank":
        return {"matched": text == "", "missing": False}
    if op == "not_blank":
        return {"matched": text != "", "missing": False}
    if text == "":
        return {"matched": False, "missing": True}
    if op in ("gt", "gte", "lt", "lte"):
        left = _decimal(value)
        right = _decimal(expected)
        if left is None or right is None:
            return {"matched": False, "missing": True}
        matched = {
            "gt": left > right, "gte": left >= right,
            "lt": left < right, "lte": left <= right,
        }[op]
        return {"matched": matched, "missing": False}
    if op == "in":
        values = expected if isinstance(expected, (list, tuple, set)) else [expected]
        matched = text.casefold() in {
            _text(item).casefold() for item in values}
        return {"matched": matched, "missing": False}
    if op == "contains":
        return {
            "matched": _text(expected).casefold() in text.casefold(),
            "missing": False,
        }
    if op == "ne":
        if _decimal(value) is not None and _decimal(expected) is not None:
            return {"matched": _decimal(value) != _decimal(expected),
                    "missing": False}
        return {"matched": text.casefold() != _text(expected).casefold(),
                "missing": False}
    # eq
    if _decimal(value) is not None and _decimal(expected) is not None:
        return {"matched": _decimal(value) == _decimal(expected),
                "missing": False}
    return {"matched": text.casefold() == _text(expected).casefold(),
            "missing": False}


def evaluate_row(
    cells: Dict[str, Any],
    rules: Sequence[Dict[str, Any]],
    *,
    fallback: str = "REVIEW",
) -> Dict[str, Any]:
    """Evaluate one authoritative row; never invents a decision."""
    missing_fields: List[str] = []
    for rule in rules:
        matched = True
        rule_missing: List[str] = []
        for condition in rule.get("when") or []:
            result = _condition_matches(cells, condition)
            if result.get("missing"):
                rule_missing.append(str(condition.get("field")))
            if not result.get("matched"):
                matched = False
        if matched:
            gap_fields = [
                str(condition.get("field"))
                for condition in rule.get("when") or []
                if condition.get("op") == "blank"
            ]
            unresolved = [
                f"Confirm {field} before deciding."
                for field in gap_fields
            ]
            return {
                "decision": rule["decision"],
                "basis": [rule.get("basis") or rule["decision"]],
                "matched_rule": rule,
                "unresolved": unresolved,
                "missing_fields": gap_fields,
            }
        for field in rule_missing:
            if field not in missing_fields:
                missing_fields.append(field)
    reason = (
        "Missing value for " + ", ".join(missing_fields) + "."
        if missing_fields else
        "No taught rule covers this record; review required."
    )
    return {
        "decision": fallback,
        "basis": [reason],
        "matched_rule": None,
        "unresolved": [reason],
        "missing_fields": missing_fields,
    }
