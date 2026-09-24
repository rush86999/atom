"""Versioned task-outcome and learning-event contracts."""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional

CONTRACT_VERSION = 2
FAILURE_LAYERS = frozenset(
    {
        "intent",
        "discovery",
        "identity",
        "extraction",
        "comparison",
        "execution",
        "delivery",
        "unknown",
    }
)
FAILURE_OWNERS = frozenset(
    {"capability", "configuration", "task_data", "model", "delivery", "unknown"}
)


def _tri_state(value: Any) -> Optional[bool]:
    if value is True or value is False:
        return value
    return None


def _bounded_text(value: Any, limit: int) -> str:
    return str(value or "")[:limit]


def _copy_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _copy_ref(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    keys = (
        "kind",
        "file_name",
        "resource_id",
        "content_hash",
        "evidence_kind",
        "addresses_requested",
        "criterion_ids",
        "source",
    )
    return {key: value[key] for key in keys if key in value}


def _normalise_tool(value: Any) -> Dict[str, Any]:
    tool = _copy_dict(value)
    return {
        "tool": _bounded_text(tool.get("tool") or "unknown", 120),
        "verified": _tri_state(tool.get("verified")),
        "outcome": _bounded_text(tool.get("outcome"), 500),
        "required": bool(tool.get("required", True)),
        "evidence_refs": [
            _copy_ref(ref) for ref in (tool.get("evidence_refs") or [])
            if isinstance(ref, dict)
        ],
        "criterion_ids": list(tool.get("criterion_ids") or []),
        "failure_layer": tool.get("failure_layer"),
        "failure_owner": tool.get("failure_owner"),
    }


def _criterion_results(value: Any) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for item in value or []:
        if isinstance(item, dict):
            results.append(
                {
                    "criterion": _bounded_text(item.get("criterion"), 500),
                    "met": _tri_state(item.get("met")),
                    "evidence_refs": [
                        _copy_ref(ref) for ref in (item.get("evidence_refs") or [])
                        if isinstance(ref, dict)
                    ],
                }
            )
    return results


def build_task_outcome(
    *,
    objective: str,
    completion_criteria: Optional[List[Any]] = None,
    requested: Optional[Dict[str, Any]] = None,
    source_constraints: Optional[Dict[str, Any]] = None,
    authorized_actions: Optional[List[str]] = None,
    tool_outcomes: Optional[List[Dict[str, Any]]] = None,
    evidence_refs: Optional[List[Dict[str, Any]]] = None,
    delivery: Optional[Dict[str, Any]] = None,
    user_corrections: Optional[List[Dict[str, Any]]] = None,
    limitations: Optional[List[str]] = None,
    latency_s: Optional[float] = None,
    cost_usd: Optional[float] = None,
    objective_met: Optional[bool] = None,
    criterion_results: Optional[List[Dict[str, Any]]] = None,
    failure_layer: Optional[str] = None,
    failure_owner: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    execution_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    policy_version: Optional[str] = None,
    candidate_versions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one task outcome without treating delivery as task success."""
    delivery_data = _copy_dict(delivery)
    if "delivered" in delivery_data:
        delivery_data["delivered"] = _tri_state(delivery_data.get("delivered"))
    outcome: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "recorded_at": time.time(),
        "execution_id": execution_id,
        "turn_id": turn_id,
        "objective": _bounded_text(objective, 4000),
        "objective_met": _tri_state(objective_met),
        "completion_criteria": list(completion_criteria or []),
        "criterion_results": _criterion_results(criterion_results),
        "requested": _copy_dict(requested),
        "source_constraints": _copy_dict(source_constraints),
        "authorized_actions": list(authorized_actions or []),
        "tool_outcomes": [_normalise_tool(tool) for tool in (tool_outcomes or [])],
        "evidence_refs": [
            _copy_ref(ref) for ref in (evidence_refs or [])
            if isinstance(ref, dict)
        ],
        "delivery": delivery_data,
        "user_corrections": [_copy_dict(item) for item in (user_corrections or [])],
        "limitations": list(limitations or []),
        "latency_s": latency_s,
        "cost_usd": cost_usd,
        "scope": _copy_dict(scope),
        "policy_version": policy_version,
        "candidate_versions": _copy_dict(candidate_versions),
        "failure_layer": failure_layer,
        "failure_owner": failure_owner,
    }
    diagnosis = diagnose_failure(outcome)
    if diagnosis is not None:
        outcome["failure"] = diagnosis
    outcome["success_kinds"] = derive_success_kinds(outcome)
    return outcome


def _has_verified_evidence(outcome: Dict[str, Any], tools: List[Dict[str, Any]]) -> bool:
    evidence = outcome.get("evidence_refs") or []
    if any(
        ref.get("addresses_requested") is not False
        and (
            ref.get("addresses_requested") is True
            or ref.get("content_hash")
            or ref.get("resource_id")
            or ref.get("file_name")
        )
        for ref in evidence
        if isinstance(ref, dict)
    ):
        return True
    if any(
        tool.get("verified") is True
        and any(
            ref.get("addresses_requested") is not False
            for ref in tool.get("evidence_refs") or []
            if isinstance(ref, dict)
        )
        for tool in tools
    ):
        return True
    return any(
        item.get("met") is True
        and any(
            ref.get("addresses_requested") is not False
            for ref in item.get("evidence_refs") or []
            if isinstance(ref, dict)
        )
        for item in (outcome.get("criterion_results") or [])
        if isinstance(item, dict)
    )


def derive_success_kinds(outcome: Dict[str, Any]) -> Dict[str, Any]:
    """Return independent tri-state task, tool, and delivery results."""
    if not isinstance(outcome, dict):
        return {
            "task_success": None,
            "tool_success": None,
            "delivery_success": None,
            "task_success_basis": "invalid_contract",
        }

    tools = [item for item in (outcome.get("tool_outcomes") or []) if isinstance(item, dict)]
    delivery_value = _tri_state((outcome.get("delivery") or {}).get("delivered"))
    if tools:
        verified = [item.get("verified") for item in tools]
        if any(value is False for value in verified):
            tool_success: Optional[bool] = False
        elif all(value is True for value in verified):
            tool_success = True
        else:
            tool_success = None
    else:
        tool_success = None

    objective_value = _tri_state(outcome.get("objective_met"))
    corrections = outcome.get("user_corrections") or []
    if corrections:
        task_success: Optional[bool] = False
        basis = "user_correction"
    elif objective_value is False:
        task_success = False
        basis = "objective_not_met"
    elif delivery_value is False:
        task_success = False
        basis = "delivery_failed"
    elif objective_value is None:
        task_success = None
        basis = "objective_unknown"
    elif delivery_value is not True:
        task_success = None
        basis = "delivery_unknown"
    elif tools and tool_success is False:
        task_success = False
        basis = "tool_failed"
    elif tools and tool_success is not True:
        task_success = None
        basis = "tool_unknown"
    elif not _has_verified_evidence(outcome, tools):
        task_success = None
        basis = "insufficient_evidence"
    else:
        task_success = True
        basis = "verified_evidence"

    return {
        "task_success": task_success,
        "tool_success": tool_success,
        "delivery_success": delivery_value,
        "task_success_basis": basis,
    }


def diagnose_failure(outcome: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Classify only explicit failed or unknown terminal signals."""
    if not isinstance(outcome, dict):
        return None
    delivery = outcome.get("delivery") or {}
    if delivery.get("delivered") is False:
        return {
            "layer": "delivery",
            "owner": "delivery",
            "basis": "delivery_not_confirmed",
        }

    for tool in outcome.get("tool_outcomes") or []:
        if not isinstance(tool, dict) or tool.get("verified") is not False:
            continue
        layer = tool.get("failure_layer")
        owner = tool.get("failure_owner")
        if layer not in FAILURE_LAYERS:
            layer = "execution"
        if owner not in FAILURE_OWNERS:
            owner = "capability"
        return {
            "layer": layer,
            "owner": owner,
            "basis": "tool_verification_failed",
        }

    if outcome.get("objective_met") is not True and outcome.get("failure_layer"):
        layer = outcome.get("failure_layer")
        owner = outcome.get("failure_owner")
        if layer in FAILURE_LAYERS and owner in FAILURE_OWNERS:
            return {
                "layer": layer,
                "owner": owner,
                "basis": "explicit_terminal_signal",
            }
    return None


def merge_feedback_into_outcome(
    outcome: Dict[str, Any], feedback: Dict[str, Any]
) -> Dict[str, Any]:
    """Attach classified feedback without changing task evidence or policy."""
    merged = copy.deepcopy(outcome) if isinstance(outcome, dict) else {}
    corrections = list(merged.get("user_corrections") or [])
    classifications = list(merged.get("feedback_classifications") or [])
    if feedback.get("kind") in {"factual_correction", "preference", "execution_failure"}:
        corrections.append(
            {
                "kind": feedback.get("kind"),
                "confidence": feedback.get("confidence"),
                "supporting_text": _bounded_text(feedback.get("supporting_text"), 500),
                "destination": feedback.get("destination"),
                "evidence_refs": [
                    _copy_ref(ref) for ref in (feedback.get("evidence_refs") or [])
                    if isinstance(ref, dict)
                ],
                "recorded_at": time.time(),
            }
        )
    classifications.append(
        {
            "kind": feedback.get("kind"),
            "destination": feedback.get("destination"),
            "scope": feedback.get("scope", "turn"),
            "confidence": feedback.get("confidence"),
            "requires_review": bool(feedback.get("requires_review")),
            "recorded_at": time.time(),
        }
    )
    merged["user_corrections"] = corrections
    merged["feedback_classifications"] = classifications
    feedback_failure = {
        "factual_correction": ("extraction", "task_data"),
        "preference": ("configuration", "configuration"),
        "execution_failure": ("execution", "capability"),
        "strategy_improvement": ("intent", "capability"),
        "permission_instruction": ("intent", "configuration"),
    }.get(str(feedback.get("kind") or ""))
    if feedback_failure and not merged.get("failure"):
        merged["failure"] = {
            "layer": feedback_failure[0],
            "owner": feedback_failure[1],
            "basis": "classified_user_feedback",
        }
    merged["success_kinds"] = derive_success_kinds(merged)
    return merged


def attach_to_execution(
    execution_id: Optional[str], outcome: Dict[str, Any]
) -> bool:
    """Persist the outcome and its independent success kinds atomically."""
    if not execution_id:
        return False
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            row = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
            if row is None:
                return False
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            metadata["task_outcome"] = outcome
            metadata["task_success_kinds"] = outcome.get("success_kinds") or derive_success_kinds(outcome)
            metadata["learning_event"] = {
                "event_type": "task_outcome",
                "contract_version": outcome.get("contract_version", CONTRACT_VERSION),
                "execution_id": execution_id,
            }
            row.metadata_json = metadata
            db.commit()
        return True
    except Exception:
        return False


def attach_feedback_to_execution(
    execution_id: Optional[str],
    feedback: Dict[str, Any],
    *,
    user_id: Optional[str] = None,
) -> bool:
    """Join a classified correction to the originating execution."""
    if not execution_id:
        return False
    try:
        from core.database import get_db_session
        from core.models import AgentExecution

        with get_db_session() as db:
            row = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
            if row is None:
                return False
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            outcome = metadata.get("task_outcome")
            if not isinstance(outcome, dict):
                return False
            scoped_user = (outcome.get("scope") or {}).get("user_id")
            if user_id and scoped_user and str(scoped_user) != str(user_id):
                return False
            metadata["task_outcome"] = merge_feedback_into_outcome(outcome, feedback)
            metadata["task_success_kinds"] = metadata["task_outcome"]["success_kinds"]
            row.metadata_json = metadata
            db.commit()
        return True
    except Exception:
        return False
