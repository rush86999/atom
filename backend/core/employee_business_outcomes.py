"""Durable business-result requirements for employee jobs.

A wait has two independent facts: the missing evidence arrived, and the
dependent business result was actually verified. This module keeps the second
fact as an assignment-level requirement (not another workflow engine) and
derives its status from applied step receipts.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


BUSINESS_RESULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "quote_calculation": {
        "adapter": "quote.calculate",
        "label": "quote calculation",
        "subject_fields": (),
    },
    "invoice_reconciliation": {
        "adapter": "invoice.reconcile",
        "label": "invoice reconciliation",
        "subject_fields": ("po_id", "invoice_id"),
    },
}


def result_profile(operation: Any) -> Optional[Dict[str, Any]]:
    return BUSINESS_RESULT_PROFILES.get(str(operation or "").strip())


def _bounded(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _normal(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def normalize_business_requirement(raw: Any) -> Dict[str, Any]:
    """Validate one durable result requirement against supported profiles."""
    if not isinstance(raw, Mapping):
        raise ValueError("a business requirement must be an object")
    operation = _bounded(raw.get("operation"), 80)
    profile = result_profile(operation)
    if profile is None:
        raise ValueError(
            f"unsupported business requirement operation {operation!r}")
    requirement_id = _bounded(raw.get("requirement_id"), 120)
    if not requirement_id:
        raise ValueError("a business requirement needs a durable id")
    adapter = _bounded(raw.get("receipt_adapter"), 80) or profile["adapter"]
    if adapter != profile["adapter"]:
        raise ValueError(
            f"business requirement {requirement_id} names the wrong receipt "
            f"adapter")
    return {
        "requirement_id": requirement_id,
        "operation": operation,
        "label": _bounded(raw.get("label"), 200) or profile["label"],
        "subject": _bounded(raw.get("subject"), 200),
        "fact": _bounded(raw.get("fact"), 120),
        "correlation_id": _bounded(raw.get("correlation_id"), 120),
        "receipt_adapter": adapter,
        "subject_fields": list(profile["subject_fields"]),
        "required": True,
    }


def normalize_business_requirements(
    values: Optional[Iterable[Any]],
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for raw in values or []:
        item = normalize_business_requirement(raw)
        if item["requirement_id"] in seen:
            raise ValueError(
                f"duplicate business requirement {item['requirement_id']}")
        seen.add(item["requirement_id"])
        normalized.append(item)
    return normalized


def requirement_id_for(
    *, operation: str, subject: str, correlation_id: str,
) -> str:
    digest = hashlib.sha256(json.dumps({
        "operation": operation,
        "subject": _normal(subject),
        "correlation_id": correlation_id,
    }, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    return f"result-{operation}-{digest}"[:120]


def business_result_from_step(step: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """One verified business result from an applied step, if the step is one."""
    if str(step.get("status") or "") != "applied":
        return None
    adapter = str(step.get("adapter") or "")
    operation = next((
        name for name, profile in BUSINESS_RESULT_PROFILES.items()
        if profile["adapter"] == adapter), "")
    if not operation:
        return None
    result = step.get("result") if isinstance(step.get("result"), Mapping) else {}
    value = result.get("value")
    if value in (None, ""):
        return None
    verification = result.get("verification")
    if isinstance(verification, Mapping):
        status = str(verification.get("status") or "").lower()
        if status and status not in ("verified", "confirmed", "applied"):
            return None
    data = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    identity = {
        field: _normal(data.get(field))
        for field in BUSINESS_RESULT_PROFILES[operation]["subject_fields"]
        if data.get(field) not in (None, "")
    }
    return {
        "operation": operation,
        "adapter": adapter,
        "step_id": step.get("step_id"),
        "operation_id": step.get("operation_id"),
        "verified": True,
        "value": value,
        "unit": result.get("unit"),
        "subject_identity": identity,
        "source_version": result.get("source_version"),
        "verification": dict(verification) if isinstance(
            verification, Mapping) else None,
    }


def business_results_from_assignment(
    assignment: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for step in assignment.get("steps") or []:
        if isinstance(step, Mapping):
            result = business_result_from_step(step)
            if result is not None:
                results.append(result)
    return results


def requirement_satisfied(
    requirement: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> bool:
    operation = str(requirement.get("operation") or "")
    subject = _normal(requirement.get("subject"))
    for result in results:
        if not isinstance(result, Mapping):
            continue
        if str(result.get("operation") or "") != operation:
            continue
        if result.get("verified") is not True:
            continue
        identity = result.get("subject_identity")
        fields = requirement.get("subject_fields") or []
        if subject and fields:
            if not isinstance(identity, Mapping) or not identity:
                # A scoped requirement cannot be satisfied by a receipt with
                # no matching business identity.
                continue
            candidates = [
                str(value) for value in identity.values() if str(value)
            ]
            if not candidates or not any(
                candidate in subject or subject in candidate
                for candidate in candidates
            ):
                continue
        return True
    return False


def business_requirement_views(
    assignment: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    requirements = assignment.get("business_requirements") or []
    results = business_results_from_assignment(assignment)
    views: List[Dict[str, Any]] = []
    for raw in requirements:
        if not isinstance(raw, Mapping):
            continue
        satisfied = requirement_satisfied(raw, results)
        waiting = next((
            step for step in assignment.get("steps") or []
            if isinstance(step, Mapping)
            and str(step.get("adapter") or "") == "assignment.wait"
            and str(step.get("status") or "") == "waiting"
            and str((step.get("waiting") or {}).get("correlation_id") or "")
            == str(raw.get("correlation_id") or "")
        ), None)
        if satisfied:
            next_action = None
        elif waiting is not None:
            next_action = (
                f"Answer the authorized request for "
                f"{raw.get('fact') or 'the missing evidence'}.")
        elif raw.get("fact"):
            next_action = (
                "The external fact is recorded; "
                f"{raw.get('label') or raw.get('operation')} still needs "
                "completion.")
        else:
            next_action = (
                f"Complete the {raw.get('label') or raw.get('operation')}.")
        views.append({
            "requirement_id": raw.get("requirement_id"),
            "operation": raw.get("operation"),
            "label": raw.get("label"),
            "subject": raw.get("subject"),
            "fact": raw.get("fact"),
            "correlation_id": raw.get("correlation_id"),
            "status": "satisfied" if satisfied else "unresolved",
            "next_action": next_action,
        })
    return views
