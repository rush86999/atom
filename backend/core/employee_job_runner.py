"""Continue an objective-started employee job after its evidence reads.

The initial employee proposal owns discovery: it chooses authorized evidence
reads. Once those reads are applied, this module hands the *observed evidence*
back to the same adaptation consumer. The model chooses supported business work
(or a targeted clarification); the existing compiler and AssignmentExecutor
remain the only owners of execution mechanics and effects.

No second lifecycle, queue or planner is introduced. The caller executes the
returned status, and every adoption is bound to the current task version and
the exact evidence observation that caused it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional


_VERBS = {
    "retrieve", "calculate", "present", "outbound", "send", "edit", "delete",
}
_TERMINAL = {"completed", "cancelled", "failed"}


def _json_identity(value: Any) -> str:
    try:
        text = json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _consumed_observation_ids(assignment: Mapping[str, Any]) -> set:
    consumed = set()
    for history in assignment.get("patch_history") or []:
        if not isinstance(history, Mapping):
            continue
        for observed in history.get("observations") or []:
            if isinstance(observed, Mapping):
                value = (
                    observed.get("observation_id") or observed.get("id"))
            else:
                value = observed
            if value not in (None, ""):
                consumed.add(str(value))
    return consumed


def _is_business_step(step: Mapping[str, Any]) -> bool:
    adapter = str(step.get("adapter") or "")
    return adapter.startswith((
        "quote.", "invoice.", "action.", "assignment.", "deliverable.",
        "document.write", "presentation.", "outbound.",
    ))


def _evidence_observation(
    step: Mapping[str, Any], result: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """Hand accepted evidence to adaptation by its result contract.

    Tabular rows, structured objects and textual documents are registered
    evidence shapes. Business header names are deliberately not a filter: the
    model may map an unfamiliar table (Product/Units/ApprovedCost) onto the
    supported quote fields, and the compiler validates the concrete mapping.
    Terms/policy reads still reach the model as evidence; they simply do not
    make a capability ready by themselves.
    """
    if _is_business_step(step):
        return None
    rows = result.get("rows")
    data = result.get("data")
    text = result.get("text")
    shape = ""
    columns: List[str] = []
    data_keys: List[str] = []
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping):
        shape = "tabular"
        columns = sorted(str(key) for key in rows[0])[:40]
    elif isinstance(data, Mapping) and data:
        shape = "structured"
        data_keys = sorted(str(key) for key in data)[:40]
    elif str(text or "").strip():
        shape = "text"
    if not shape:
        return None
    step_id = str(step.get("step_id") or "")
    operation_id = str(step.get("operation_id") or "")
    version = str(
        result.get("source_version") or result.get("version")
        or (result.get("verification") or {}).get("version") or "")
    observation_id = "evidence-" + _json_identity({
        "step_id": step_id,
        "operation_id": operation_id,
        "version": version,
        "result": {
            "rows": rows,
            "data": data,
            "text": text,
            "coverage": result.get("coverage"),
        },
    })
    return {
        "observation_id": observation_id,
        "kind": "evidence_result",
        "step_id": step_id,
        "shape": shape,
        "columns": columns,
        "data_keys": data_keys,
        "resource_id": str(result.get("resource_id") or ""),
        "source_refs": [{
            "resource_id": str(result.get("resource_id") or ""),
            "version": version,
        }] if result.get("resource_id") or version else [],
        "reason": (
            "the authorized evidence read completed and its accepted result "
            "is available for semantic mapping or missing-prerequisite "
            "diagnosis"),
    }


def evidence_observations(record: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Unconsumed accepted evidence results on the current assignment."""
    assignment = record.get("assignment") or {}
    consumed = _consumed_observation_ids(assignment)
    observations = []
    for step in assignment.get("steps") or []:
        if not isinstance(step, Mapping) or step.get("status") != "applied":
            continue
        result = step.get("result")
        if not isinstance(result, Mapping) or not result:
            continue
        observation = _evidence_observation(step, result)
        if observation is None:
            continue
        if observation["observation_id"] in consumed:
            continue
        observations.append(observation)
    return observations


def action_views(assignment: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Authorized registered external actions, without expanding authority."""
    from core.action_registry import action_registry
    from core.assignment_planner import _registered_action_effect

    views = []
    for raw in assignment.get("authorized_actions") or []:
        name = str(raw or "").strip()
        if not name or name in _VERBS:
            continue
        action = action_registry.get_action(name)
        if action is None:
            continue
        views.append({
            "action": name,
            "effect": _registered_action_effect(action),
            "description": getattr(action, "description", "") or "",
        })
    return views


def missing_prerequisite_question(
    target: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """One actionable obligation from the capability's declared missing roles.

    Accepts the assignment or the bounded reasoning context. This is the
    deterministic no-progress floor, not model discovery: it runs only when
    the model retains/fails while a declared capability is missing a
    prerequisite, so the job cannot silently abandon the objective.
    """
    if "missing_prerequisites" in target:
        missing = [
            dict(item) for item in (
                target.get("missing_prerequisites") or [])
            if isinstance(item, Mapping)
        ]
    else:
        from core.employee_proposal import operation_capabilities

        missing = [
            {
                "operation": item.get("operation"),
                "label": item.get("label") or item.get("operation"),
                "status": item.get("status"),
                "missing": list(item.get("missing") or []),
                "question_hint": item.get("question_hint") or "",
                "known_identities": dict(
                    item.get("known_identities") or {}),
                "evidence": list(item.get("evidence") or []),
            }
            for item in operation_capabilities(target)
            if str(item.get("status") or "") in ("missing", "ambiguous")
        ]
    if not missing:
        return None
    chosen = next(
        (item for item in missing
         if item.get("known_identities") and item.get("question_hint")),
        missing[0],
    )
    roles = list(chosen.get("missing") or [])
    hint = str(chosen.get("question_hint") or "").strip()
    if not hint:
        hint = (
            "Which authorized source contains the missing "
            + ", ".join(roles)
            + " evidence needed for this objective?")
    known = dict(chosen.get("known_identities") or {})
    subject = (
        known.get("purchase_order.po_id")
        or known.get("receiving.po_id")
        or known.get("invoice.po_id"))
    evidence_steps = [
        str(item.get("step_id"))
        for item in chosen.get("evidence") or []
        if isinstance(item, Mapping) and item.get("step_id")
    ]
    return {
        "kind": "missing_evidence",
        "item": chosen.get("label") or chosen.get("operation"),
        "question": hint,
        "concept": chosen.get("operation"),
        "operation": chosen.get("operation"),
        "missing_roles": roles,
        "subject": subject or None,
        "known_identities": known,
        "evidence_step_ids": evidence_steps,
        "reason": (
            "the accepted evidence does not satisfy the required role(s): "
            + ", ".join(roles)),
        "next_action": (
            "Authorize or name the source that contains the missing "
            "business record."),
        "next_retrieval": hint,
        "inputs": {
            "operation": chosen.get("operation"),
            "missing": roles,
            "known_identities": known,
            "evidence_step_ids": evidence_steps,
        },
    }
