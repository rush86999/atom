"""Reviewed-decision binding for goal-run human approvals.

A held goal decision is not just "whatever is pending now". The human reviews
one concrete decision at one point in the run, so the public approval request
must carry the identity and canonical binding of that exact reviewed material.
The service recomputes the binding from authoritative persisted state before
claiming; a stale or fabricated payload can never approve a newer decision.

The binding deliberately includes run scope, plan/cursor, evolving
parameters, progress counters and the decision payload. A changed plan,
parameter, generation, checkpoint or scope invalidates the review and requires
a refresh/new review. It is stored beside the pending decision and in the
HITL row params, not in a second operation engine.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any, Dict, Mapping, Optional, Tuple

DECISION_BINDING_SCHEMA = "atom-goal-run-decision-1"
BINDING_FIELDS = ("decision_id", "decision_generation", "decision_binding")


def _value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, default=str)


def reviewed_decision_material(
    decision: Mapping[str, Any],
) -> Dict[str, Any]:
    """Decision payload without the binding envelope itself."""
    return {
        str(key): value
        for key, value in dict(decision or {}).items()
        if key not in BINDING_FIELDS
    }


def decision_binding(
    run: Any,
    decision: Mapping[str, Any],
    *,
    decision_id: str,
    generation: int,
) -> str:
    """Canonical hash over the run state and the exact decision reviewed."""
    material = {
        "schema": DECISION_BINDING_SCHEMA,
        "decision_id": str(decision_id),
        "decision_generation": int(generation),
        "run": {
            "id": str(_value(run, "id", "") or ""),
            "tenant_id": str(_value(run, "tenant_id", "") or ""),
            "workspace_id": str(_value(run, "workspace_id", "") or ""),
            "goal_id": str(_value(run, "goal_id", "") or ""),
            "agent_id": str(_value(run, "agent_id", "") or ""),
            "role": str(_value(run, "role", "") or ""),
            "supervision_mode": str(
                _value(run, "supervision_mode", "") or ""),
            "created_by": str(_value(run, "created_by", "") or ""),
        },
        "state": {
            "status": str(_value(run, "status", "") or ""),
            "plan": _value(run, "plan", []) or [],
            "cursor": _value(run, "cursor", None),
            "parameters": _value(run, "parameters", {}) or {},
            "waiting_on": _value(run, "waiting_on", None),
            "replan_count": int(_value(run, "replan_count", 0) or 0),
            "steps_executed": int(_value(run, "steps_executed", 0) or 0),
        },
        "decision": reviewed_decision_material(decision),
    }
    return hashlib.sha256(
        _canonical(material).encode("utf-8")).hexdigest()


def install_pending_decision(
    run: Any,
    decision: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return the pending-decision payload with a fresh exact binding.

    ``run`` must already be in its held state (``paused_hitl``) and must carry
    the generation this decision will occupy. The caller persists the returned
    payload and sets ``human_interventions`` to ``decision_generation``.
    """
    generation = int(_value(run, "human_interventions", 0) or 0) + 1
    decision_id = str(uuid.uuid4())
    payload = reviewed_decision_material(decision)
    payload.update({
        "decision_id": decision_id,
        "decision_generation": generation,
        "decision_binding": decision_binding(
            run, payload, decision_id=decision_id, generation=generation),
    })
    return payload


def validate_pending_decision(
    run: Any,
    pending: Mapping[str, Any],
    *,
    expected_decision_id: Optional[str],
    expected_decision_binding: Optional[str],
) -> Tuple[bool, str]:
    """Validate a client-supplied review against authoritative current state.

    Returns ``(False, reason)`` when the request is unbound or stale. A
    payload-provided hash is never trusted on its own: the expected hash is
    compared to a fresh recomputation over the current run/pending material.
    """
    if not expected_decision_id or not expected_decision_binding:
        return False, "decision_review_required"
    current_id = str(pending.get("decision_id") or "")
    if not current_id or not hmac.compare_digest(
            current_id, str(expected_decision_id)):
        return False, "stale_decision_review"
    try:
        generation = int(pending.get("decision_generation") or 0)
    except (TypeError, ValueError):
        return False, "stale_decision_review"
    current_generation = int(_value(run, "human_interventions", 0) or 0)
    if generation != current_generation:
        return False, "stale_decision_review"
    expected = decision_binding(
        run, pending, decision_id=current_id, generation=generation)
    if not hmac.compare_digest(expected, str(expected_decision_binding)):
        return False, "stale_decision_review"
    return True, ""
