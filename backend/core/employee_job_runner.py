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
    """Only evidence that can actually support a supported business operation.

    Terms/policy reads and already-calculated business results are not new
    evidence; including them would invite the model to re-propose completed
    work. Quote rows and invoice/PO/receiving receipts are included.
    """
    if _is_business_step(step):
        return None
    rows = result.get("rows")
    data = result.get("data")
    row_keys = set()
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping):
        row_keys = set(rows[0])
    data_keys = set(data) if isinstance(data, Mapping) else set()
    quote_shape = bool(
        row_keys & {"Item", "Qty", "Price", "item_id", "quantity",
                    "unit_price"})
    invoice_shape = bool(
        data_keys & {"invoice_id", "purchase_order_id", "po_id",
                     "received_quantity", "vendor_id", "invoice_number"})
    if not (quote_shape or invoice_shape):
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
            "coverage": result.get("coverage"),
        },
    })
    return {
        "observation_id": observation_id,
        "kind": "evidence_result",
        "step_id": step_id,
        "resource_id": str(result.get("resource_id") or ""),
        "source_refs": [{
            "resource_id": str(result.get("resource_id") or ""),
            "version": version,
        }] if result.get("resource_id") or version else [],
        "reason": (
            "the authorized evidence read completed and its accepted result "
            "can support supported business work"),
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
