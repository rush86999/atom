"""Deterministic business readiness for assignment steps.

This is a pure evaluation over the durable assignment view: it does not own
state, call tools or authorize effects. The executor re-evaluates before
scheduling; an effect's own lifecycle still owns dispatch authorization.
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any, Dict, Iterable, List, Optional

EVIDENCE_STATES = (
    "established", "missing", "incomplete", "stale", "conflicting",
    "unavailable",
)
PREDICATE_KINDS = ("fact", "receipt", "authority", "time", "all", "any", "not")
_MAX_DEPTH = 8
_MAX_PREDICATES = 40


def _text(value: Any, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]


def _truth(value: Any) -> str:
    return "true" if value is True else "false" if value is False else "unknown"


def _combine_and(values: Iterable[str]) -> str:
    values = list(values)
    if any(value == "false" for value in values):
        return "false"
    if any(value == "unknown" for value in values):
        return "unknown"
    return "true"


def _combine_or(values: Iterable[str]) -> str:
    values = list(values)
    if any(value == "true" for value in values):
        return "true"
    if any(value == "unknown" for value in values):
        return "unknown"
    return "false"


def _parse_time(value: Any) -> Optional[_dt.datetime]:
    try:
        parsed = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_dt.timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def normalize_requirements(value: Any, *, depth: int = 0) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("step requirements must be a list")
    if len(value) > _MAX_PREDICATES:
        raise ValueError("too many step requirements")
    if depth > _MAX_DEPTH:
        raise ValueError("step requirement nesting is too deep")
    out: List[Dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each requirement must be an object")
        kind = _text(raw.get("kind"), 20).lower()
        if kind not in PREDICATE_KINDS:
            raise ValueError(f"unsupported requirement kind {kind!r}")
        item = {"kind": kind}
        if kind == "fact":
            fact_id = _text(raw.get("fact_id"), 120)
            if not fact_id:
                raise ValueError("fact requirement needs fact_id")
            item["fact_id"] = fact_id
            if "equals" in raw:
                item["equals"] = raw.get("equals")
        elif kind == "receipt":
            step_id = _text(raw.get("step_id"), 80)
            if not step_id:
                raise ValueError("receipt requirement needs step_id")
            item["step_id"] = step_id
            item["require"] = _text(raw.get("require"), 40) or "applied"
        elif kind == "authority":
            allow = raw.get("allow")
            if allow is not None:
                if not isinstance(allow, list) or not all(
                        isinstance(entry, str) for entry in allow):
                    raise ValueError("authority allow must be a string list")
                item["allow"] = [_text(entry, 40) for entry in allow]
            else:
                item["allow"] = ["authorized", "read_only"]
        elif kind == "time":
            if not raw.get("not_after"):
                raise ValueError("time requirement needs not_after")
            item["not_after"] = str(raw["not_after"])
        elif kind in ("all", "any"):
            item["of"] = normalize_requirements(
                raw.get("of") or [], depth=depth + 1)
        elif kind == "not":
            child = normalize_requirements(
                [raw.get("of")] if isinstance(raw.get("of"), dict)
                else raw.get("of") or [], depth=depth + 1)
            if len(child) != 1:
                raise ValueError("not requires exactly one child requirement")
            item["of"] = child[0]
        out.append(item)
    return out


def normalize_facts(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("assignment facts must be a list")
    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each fact must be an object")
        fact_id = _text(raw.get("fact_id"), 120)
        if not fact_id or fact_id in seen:
            raise ValueError(f"invalid or duplicate fact_id {fact_id!r}")
        seen.add(fact_id)
        state = _text(raw.get("evidence_state"), 20) or "unknown"
        if state not in EVIDENCE_STATES:
            raise ValueError(f"unknown evidence_state {state!r}")
        fact = {
            "fact_id": fact_id,
            "subject": dict(raw.get("subject") or {}),
            "field_id": _text(raw.get("field_id"), 120) or None,
            "value": raw.get("value"),
            "value_type": _text(raw.get("value_type"), 40) or None,
            "evidence_state": state,
            "source_refs": [
                dict(item) for item in (raw.get("source_refs") or [])
                if isinstance(item, dict)][:20],
            "authority_ref": _text(raw.get("authority_ref"), 200) or None,
            "validity": dict(raw.get("validity") or {}),
        }
        out.append(fact)
    return out


def _fact_truth(fact: Optional[Dict[str, Any]], requirement: Dict[str, Any],
                now: _dt.datetime) -> str:
    if fact is None:
        return "unknown"
    if fact.get("evidence_state") != "established":
        return "unknown"
    validity = fact.get("validity") or {}
    expires = validity.get("expires_at") if isinstance(validity, dict) else None
    if expires:
        parsed = _parse_time(expires)
        if parsed is None or now >= parsed:
            return "unknown"
    if "equals" not in requirement:
        return "true"
    expected = requirement.get("equals")
    actual = fact.get("value")
    if isinstance(expected, bool) or isinstance(actual, bool):
        return _truth(actual is expected)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not (math.isfinite(float(expected)) and math.isfinite(float(actual))):
            return "unknown"
        return _truth(float(actual) == float(expected))
    return _truth(actual == expected)


def _predicate(
    predicate: Dict[str, Any],
    assignment: Dict[str, Any],
    *,
    task_authorization: str,
    now: _dt.datetime,
) -> Dict[str, Any]:
    kind = predicate.get("kind")
    blockers: List[Dict[str, Any]] = []
    supporting: List[str] = []
    if kind == "fact":
        fact_id = predicate.get("fact_id")
        fact = next((item for item in assignment.get("facts") or []
                     if item.get("fact_id") == fact_id), None)
        truth = _fact_truth(fact, predicate, now)
        if truth != "true":
            blockers.append({
                "kind": "qualification",
                "fact_id": fact_id,
                "reason": (
                    "missing" if fact is None else
                    "unknown" if truth == "unknown" else "false"),
            })
        else:
            supporting.extend(
                str(ref.get("resource_id") or "")
                for ref in (fact.get("source_refs") or [])
                if ref.get("resource_id"))
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": supporting}

    if kind == "receipt":
        dependency = next((step for step in assignment.get("steps") or []
                           if step.get("step_id") == predicate.get("step_id")),
                          None)
        if dependency is None or dependency.get("status") != "applied":
            return {"truth": "unknown",
                    "blockers": [{
                        "kind": "predecessor",
                        "step_id": predicate.get("step_id"),
                        "reason": "not_applied",
                    }], "supporting_refs": []}
        result = dependency.get("result")
        if result is None:
            return {"truth": "unknown",
                    "blockers": [{
                        "kind": "predecessor",
                        "step_id": predicate.get("step_id"),
                        "reason": "applied_without_result",
                    }], "supporting_refs": []}
        verification = (result.get("verification")
                        if isinstance(result, dict) else None)
        if isinstance(verification, dict) and str(
                verification.get("status") or "").lower() in (
                    "incomplete", "unknown", "unverified"):
            return {"truth": "unknown",
                    "blockers": [{
                        "kind": "predecessor",
                        "step_id": predicate.get("step_id"),
                        "reason": "material_verification_incomplete",
                    }], "supporting_refs": []}
        return {"truth": "true", "blockers": [],
                "supporting_refs": [str(predicate.get("step_id"))]}

    if kind == "authority":
        allow = [str(item).lower() for item in predicate.get("allow") or []]
        current = str(task_authorization or "read_only").lower()
        truth = _truth(current in allow)
        if truth != "true":
            blockers.append({
                "kind": "authority", "reason": "current_authority_insufficient",
                "current": current, "required": allow,
            })
        else:
            supporting.append(f"authority:{current}")
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": supporting}

    if kind == "time":
        deadline = _parse_time(predicate.get("not_after"))
        truth = "unknown" if deadline is None else _truth(now < deadline)
        if truth != "true":
            blockers.append({"kind": "time", "reason": "deadline_passed"})
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": []}

    if kind in ("all", "any"):
        child_results = [
            _predicate(item, assignment,
                       task_authorization=task_authorization, now=now)
            for item in predicate.get("of") or []
        ]
        truth = (_combine_and(item["truth"] for item in child_results)
                 if kind == "all"
                 else _combine_or(item["truth"] for item in child_results))
        blockers = [blocker for item in child_results
                    for blocker in item["blockers"]]
        supporting = [ref for item in child_results
                      for ref in item["supporting_refs"]]
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": supporting}

    if kind == "not":
        child = _predicate(
            predicate.get("of") or {}, assignment,
            task_authorization=task_authorization, now=now)
        if child["truth"] == "true":
            return {"truth": "false",
                    "blockers": [{"kind": "condition_false",
                                  "reason": "negated_condition_true"}],
                    "supporting_refs": child["supporting_refs"]}
        if child["truth"] == "false":
            return {"truth": "true", "blockers": [],
                    "supporting_refs": child["supporting_refs"]}
        return {"truth": "unknown", "blockers": child["blockers"],
                "supporting_refs": child["supporting_refs"]}
    return {"truth": "unknown", "blockers": [{
        "kind": "requirement", "reason": "unsupported_predicate"}],
        "supporting_refs": []}


def evaluate_step_readiness(
    step: Dict[str, Any],
    assignment: Dict[str, Any],
    *,
    task_authorization: str = "read_only",
    now: Optional[_dt.datetime] = None,
) -> Dict[str, Any]:
    """Return a typed three-valued readiness decision for one step."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    predicates = normalize_requirements(step.get("requires") or [])
    if not predicates:
        return {
            "step_id": step.get("step_id"), "truth": "true",
            "eligible": True, "blockers": [], "supporting_refs": [],
        }
    results = [
        _predicate(item, assignment,
                   task_authorization=task_authorization, now=now)
        for item in predicates
    ]
    truth = _combine_and(item["truth"] for item in results)
    blockers = [blocker for item in results for blocker in item["blockers"]]
    supporting = [ref for item in results for ref in item["supporting_refs"]]
    return {
        "step_id": step.get("step_id"),
        "truth": truth,
        "eligible": truth == "true",
        "blockers": blockers[:40],
        "supporting_refs": supporting[:40],
        "checked_task_version": None,
        "checked_plan_revision": assignment.get("plan_revision"),
    }
