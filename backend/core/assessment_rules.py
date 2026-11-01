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

_TRUE = "true"
_FALSE = "false"
_UNKNOWN = "unknown"

OPS = {
    "eq", "ne", "gt", "gte", "lt", "lte", "in", "contains",
    "blank", "not_blank",
}




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



def _is_absent(value: Any) -> bool:
    """Absent or blank only. Numeric zero is a real value, not a blank."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _decimal(value: Any) -> "tuple[Optional[Decimal], bool]":
    """Return (value, invalid). Non-finite/malformed input is invalid."""
    if _is_absent(value):
        return None, False
    try:
        parsed = Decimal(_text(value))
    except (InvalidOperation, ValueError):
        return None, True
    if not parsed.is_finite():
        return None, True
    return parsed, False


def _condition(cells: Dict[str, Any], condition: Dict[str, Any]) -> Dict[str, Any]:
    """Three-valued condition: true, false or unknown.

    Unknown means the row cannot decide the condition: a missing field, or a
    malformed/non-finite value. It is never collapsed into false, because a
    false would let a lower-priority rule win confidently.
    """
    field = condition["field"]
    op = condition["op"]
    present = not _is_absent(cells.get(field))
    value = cells.get(field)
    expected = condition.get("value")

    if op == "blank":
        return {"state": _FALSE if present else _TRUE, "field": field,
                "reason": f"{field} is blank"}
    if op == "not_blank":
        return {"state": _TRUE if present else _FALSE, "field": field,
                "reason": f"{field} is blank"}
    if not present:
        return {"state": _UNKNOWN, "field": field,
                "reason": f"missing value for {field}"}

    if op in ("gt", "gte", "lt", "lte"):
        left, left_bad = _decimal(value)
        right, right_bad = _decimal(expected)
        if left_bad or right_bad or left is None or right is None:
            return {"state": _UNKNOWN, "field": field,
                    "reason": f"invalid numeric value for {field}"}
        matched = {
            "gt": left > right, "gte": left >= right,
            "lt": left < right, "lte": left <= right,
        }[op]
        return {"state": _TRUE if matched else _FALSE, "field": field}

    if op == "in":
        values = expected if isinstance(expected, (list, tuple, set)) else [expected]
        matched = _text(value).casefold() in {
            _text(item).casefold() for item in values}
        return {"state": _TRUE if matched else _FALSE, "field": field}

    if op == "contains":
        matched = _text(expected).casefold() in _text(value).casefold()
        return {"state": _TRUE if matched else _FALSE, "field": field}

    # eq / ne
    right, _right_bad = _decimal(expected)
    if right is not None:
        left, left_bad = _decimal(value)
        if left_bad or left is None:
            return {"state": _UNKNOWN, "field": field,
                    "reason": f"invalid numeric value for {field}"}
        equal = left == right
    else:
        equal = _text(value).casefold() == _text(expected).casefold()
    if op == "ne":
        equal = not equal
    return {"state": _TRUE if equal else _FALSE, "field": field}


def _rule_state(
    cells: Dict[str, Any], rule: Dict[str, Any],
) -> "tuple[str, List[Dict[str, Any]]]":
    """A rule is false if any condition is false, else unknown if any is."""
    unknown: List[Dict[str, Any]] = []
    for condition in rule.get("when") or []:
        result = _condition(cells, condition)
        if result["state"] == _FALSE:
            return _FALSE, []
        if result["state"] == _UNKNOWN:
            unknown.append(result)
    if unknown:
        return _UNKNOWN, unknown
    return _TRUE, []


def evaluate_row(
    cells: Dict[str, Any],
    rules: Sequence[Dict[str, Any]],
    *,
    fallback: str = "REVIEW",
) -> Dict[str, Any]:
    """Evaluate one authoritative row; never invents a decision.

    Rules are ordered. A definitively matching rule decides only when no
    higher-priority rule is still unknown with a DIFFERENT decision; otherwise
    the result is clarification, because the earlier rule may apply.
    """
    earlier_unknown: Optional["tuple[Dict[str, Any], List[Dict[str, Any]]]"] = None
    for rule in rules:
        state, unknown = _rule_state(cells, rule)
        if state == _UNKNOWN:
            if earlier_unknown is None:
                earlier_unknown = (rule, unknown)
            continue
        if state == _FALSE:
            continue
        if earlier_unknown is not None:
            earlier_rule, earlier_fields = earlier_unknown
            if earlier_rule["decision"] != rule["decision"]:
                return {
                    "decision": fallback,
                    "basis": [
                        f"Rule {earlier_rule['decision']} may apply; a later "
                        f"rule would give {rule['decision']}."
                    ],
                    "matched_rule": None,
                    "unresolved": [
                        f"Confirm {item['field']} before deciding."
                        for item in earlier_fields
                    ],
                    "missing_fields": [
                        item["field"] for item in earlier_fields],
                    "ambiguous_with": earlier_rule["decision"],
                }
        gap_fields = [
            str(condition["field"])
            for condition in rule.get("when") or []
            if condition["op"] == "blank"
        ]
        return {
            "decision": rule["decision"],
            "basis": [rule.get("basis") or rule["decision"]],
            "matched_rule": rule,
            "unresolved": [
                f"Confirm {field} before deciding." for field in gap_fields],
            "missing_fields": gap_fields,
        }

    if earlier_unknown is not None:
        rule, unknown = earlier_unknown
        return {
            "decision": fallback,
            "basis": [
                "Cannot evaluate the "
                f"{rule['decision']} rule: "
                + "; ".join(item["reason"] for item in unknown) + "."
            ],
            "matched_rule": None,
            "unresolved": [
                f"Confirm {item['field']} before deciding."
                for item in unknown
            ],
            "missing_fields": [item["field"] for item in unknown],
        }

    reason = "No taught rule covers this record; review required."
    return {
        "decision": fallback,
        "basis": [reason],
        "matched_rule": None,
        "unresolved": [reason],
        "missing_fields": [],
    }
