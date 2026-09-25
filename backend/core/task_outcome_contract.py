"""Versioned task-outcome and learning-event contracts."""

from __future__ import annotations

import copy
import re
import time
from typing import Any, Callable, Dict, List, Optional

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
LEARNING_LAYERS = ("general_capability", "user_business_configuration", "task_evidence")


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
                    "verifier": _bounded_text(item.get("verifier"), 120),
                    "evidence_refs": [
                        _copy_ref(ref) for ref in (item.get("evidence_refs") or [])
                        if isinstance(ref, dict)
                    ],
                }
            )
    return results


def _normalise_objective_state(value: Any) -> Dict[str, Any]:
    state = _copy_dict(value)
    return {
        "goal": _bounded_text(state.get("goal") or state.get("objective"), 4000),
        "target_entities": [
            _bounded_text(item, 300)
            for item in state.get("target_entities") or []
            if str(item).strip()
        ],
        "requested_attributes": [
            _bounded_text(item, 200)
            for item in state.get("requested_attributes") or []
            if str(item).strip()
        ],
        "source_constraints": _copy_dict(state.get("source_constraints")),
        "authorized_actions": [
            _bounded_text(item, 120)
            for item in state.get("authorized_actions") or []
            if str(item).strip()
        ],
    }


def _normalise_gap(value: Any) -> Dict[str, Any]:
    gap = _copy_dict(value)
    return {
        "criterion_id": _bounded_text(
            gap.get("criterion_id") or gap.get("entity_id"), 300
        ),
        "status": _bounded_text(
            gap.get("status") or "unknown", 120
        ),
        "reasons": [
            _bounded_text(item, 200)
            for item in gap.get("reasons") or ([gap.get("reason")] if gap.get("reason") else [])
            if str(item).strip()
        ],
        "next_evidence_needed": _bounded_text(
            gap.get("next_evidence_needed"), 500
        ),
    }


def _normalise_implication(value: Any) -> Dict[str, Any]:
    implication = _copy_dict(value)
    return {
        "statement": _bounded_text(implication.get("statement"), 1000),
        "verification": _bounded_text(
            implication.get("verification") or "unknown", 120
        ),
        "evidence_refs": [
            _copy_ref(ref)
            for ref in implication.get("evidence_refs") or []
            if isinstance(ref, dict)
        ],
    }


def _normalise_action(value: Any) -> Dict[str, Any]:
    action = _copy_dict(value)
    return {
        "action_type": _bounded_text(
            action.get("action_type") or action.get("type") or "unknown", 120
        ),
        "criterion_id": _bounded_text(
            action.get("criterion_id") or action.get("entity_id"), 300
        ),
        "status": _bounded_text(action.get("status") or "unknown", 120),
        "authorized": action.get("authorized") is True,
        "applied": action.get("applied") is True,
        "evidence_refs": [
            _copy_ref(ref)
            for ref in (
                action.get("evidence_refs")
                or [
                    {
                        "kind": "observation",
                        "source": {"observation_id": evidence_id},
                    }
                    for evidence_id in action.get("evidence_ids") or []
                ]
            )
            if isinstance(ref, dict)
        ],
    }


def _normalise_evidence_ledger(value: Any) -> Dict[str, Any]:
    ledger = _copy_dict(value)
    return {
        key: ledger[key]
        for key in (
            "known",
            "missing",
            "conflicting",
            "incomparable",
            "unverified",
            "covered",
            "total",
        )
        if key in ledger
    }


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
    objective_state: Optional[Dict[str, Any]] = None,
    evidence_ledger: Optional[Dict[str, Any]] = None,
    gaps: Optional[List[Dict[str, Any]]] = None,
    implications: Optional[List[Dict[str, Any]]] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    calculation: Optional[Dict[str, Any]] = None,
    mutation: Optional[Dict[str, Any]] = None,
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
        "objective_state": _normalise_objective_state(
            objective_state or {"goal": objective}
        ),
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
        "evidence_ledger": _normalise_evidence_ledger(evidence_ledger),
        "gaps": [_normalise_gap(item) for item in (gaps or []) if isinstance(item, dict)],
        "implications": [
            _normalise_implication(item)
            for item in (implications or [])
            if isinstance(item, dict)
        ],
        "actions": [
            _normalise_action(item)
            for item in (actions or [])
            if isinstance(item, dict)
        ],
        "calculation": _copy_dict(calculation),
        "mutation": _copy_dict(mutation),
        "delivery": delivery_data,
        "user_corrections": [_copy_dict(item) for item in (user_corrections or [])],
        "limitations": list(limitations or []),
        "latency_s": latency_s,
        "cost_usd": cost_usd,
        "scope": _copy_dict(scope),
        "policy_version": policy_version,
        "candidate_versions": _copy_dict(candidate_versions),
        "learning_layers": {
            "general_capability": {
                "policy_version": policy_version,
                "candidate_versions": _copy_dict(candidate_versions),
            },
            "user_business_configuration": {
                "scope": _copy_dict(scope),
            },
            "task_evidence": {
                "requested": _copy_dict(requested),
                "evidence_refs": [
                    _copy_ref(ref) for ref in (evidence_refs or [])
                    if isinstance(ref, dict)
                ],
                "evidence_ledger": _normalise_evidence_ledger(
                    evidence_ledger
                ),
                "gap_count": len(gaps or []),
                "corrections": list(user_corrections or []),
            },
        },
        "failure_layer": failure_layer,
        "failure_owner": failure_owner,
    }
    diagnosis = diagnose_failure(outcome)
    if diagnosis is not None:
        outcome["failure"] = diagnosis
    outcome["success_kinds"] = derive_success_kinds(outcome)
    return outcome


# ---------------------------------------------------------------------------
# TASK-NEUTRAL ACCEPTANCE-CRITERIA VERIFIERS (2026-09-24 review):
# completion depends on the task's DECLARED criteria, evaluated through
# this shared interface. Retrieval's evidence-identity rule is ONE
# registered verifier, not the contract's definition of success;
# calculation, scheduling, and mutation register their own.
# ---------------------------------------------------------------------------
CriteriaVerifier = Callable[[Dict[str, Any]], "bool | None"]

_VERIFIERS: Dict[str, CriteriaVerifier] = {}


def register_criteria_verifier(kind: str, fn: CriteriaVerifier) -> None:
    """Register the verifier for one criterion kind. A verifier returns
    True (criteria met, with evidence), False (explicitly not met), or
    None (UNKNOWN — insufficient evidence; unknown must stay unknown)."""
    _VERIFIERS[str(kind)] = fn


# TRUSTED ORIGINS (2026-09-24 review, carried into evaluation): naming
# a registered verifier in a payload must NOT be sufficient — the
# contract RE-COMPUTES the verdict from raw evidence and honors
# pre-computed results only when they AGREE, and expected/recomputed
# bases must declare origins this code recognizes.
TRUSTED_EXPECTED_ORIGINS = frozenset({
    "user_request",          # the requested result, from the user's words
    "verified_evidence",     # a value read from verified evidence
})
TRUSTED_RECOMPUTED_ORIGINS = frozenset({
    "deterministic_recompute",  # recomputed by deterministic code
})


def _cross_check_results(outcome: Dict[str, Any]) -> "bool | None":
    """Honor pre-computed criterion_results ONLY when a fresh verifier
    run over the SAME raw evidence agrees (code-enforced provenance — a
    payload claiming 'met' with a verifier name is cross-checked, not
    trusted)."""
    criteria = outcome.get("completion_criteria") or []
    kinds = [
        str(c.get("kind") if isinstance(c, dict) else c).strip().lower()
        for c in criteria
        if (c.get("kind") if isinstance(c, dict) else c)
    ]
    kinds = [k for k in kinds if k]
    results = [
        r for r in (outcome.get("criterion_results") or [])
        if isinstance(r, dict)
        and r.get("verifier") and str(r.get("verifier")) in _VERIFIERS
    ]
    if not results:
        return None
    for kind in kinds:
        fn = _VERIFIERS.get(kind)
        if fn is None:
            continue
        fresh = fn(outcome)
        claimed = [
            r.get("met") for r in results
            if str(r.get("verifier")) == kind or not kinds
        ]
        if claimed and fresh is not None and any(
                c != fresh for c in claimed if c is not None):
            return False  # payload disagrees with the recompute -> not met
    return None  # agreement established; final verdict from fresh runs


def criteria_verdict(outcome: Dict[str, Any]) -> "tuple[str, bool | None]":
    """(basis, verdict) for the outcome's declared criteria. Unknown
    criteria kinds and absent criteria return None — never a guess."""
    criteria = outcome.get("completion_criteria") or []
    kinds = {
        str(c.get("kind") if isinstance(c, dict) else c).strip().lower()
        for c in criteria
        if (c.get("kind") if isinstance(c, dict) else c)
    }
    results = [
        r for r in (outcome.get("criterion_results") or [])
        if isinstance(r, dict)
    ]
    # TRUSTED PROVENANCE ONLY (2026-09-24 review): pre-computed results
    # count only when a REGISTERED verifier produced them; a model
    # assertion of 'met' is an unverified claim -> unknown, never True.
    trusted = [
        r for r in results
        if r.get("verifier") and str(r.get("verifier")) in _VERIFIERS
    ]
    untrusted = len(results) - len(trusted)
    verdicts: list = []
    if trusted:
        # CODE-ENFORCED PROVENANCE: a fresh verifier run must agree with
        # the claimed results — naming a verifier is not sufficient.
        cross = _cross_check_results(outcome)
        if cross is False:
            return "provenance_mismatch", False
        if any(r.get("met") is False for r in trusted):
            return "criteria_not_met", False
        verdicts.append(
            True if (all(r.get("met") is True for r in trusted)
                     and not untrusted) else None
        )
    elif results:
        verdicts.append(None)
    if not kinds:
        return (
            ("criteria_not_declared", None)
            if not results
            else ("criteria_met", True)
            if verdicts[0] is True
            else ("criteria_unknown", None)
        )
    for kind in sorted(kinds):
        fn = _VERIFIERS.get(kind)
        if fn is None:
            if any(
                str(result.get("verifier") or "") == kind
                for result in trusted
            ):
                continue
            return f"no_verifier:{kind}", None
        verdicts.append(fn(outcome))
    if any(v is False for v in verdicts):
        return "criteria_not_met", False
    if any(v is None for v in verdicts):
        return "criteria_unknown", None
    return "criteria_met", True


def _retrieval_verifier(outcome: Dict[str, Any]) -> "bool | None":
    """Retrieval criteria: verified tool evidence whose identity
    addresses the request (file/resource/hash), as before — now one
    verifier among equals."""
    tools = [
        t for t in (outcome.get("tool_outcomes") or [])
        if isinstance(t, dict)
    ]
    if not tools:
        return None
    if any(t.get("verified") is False for t in tools):
        return False
    if not any(t.get("verified") is True for t in tools):
        return None
    return _has_verified_evidence(outcome, tools)


register_criteria_verifier("retrieval", _retrieval_verifier)
register_criteria_verifier("source_scoped_retrieval", _retrieval_verifier)


def _calculation_verifier(outcome: Dict[str, Any]) -> "bool | None":
    """Calculation criteria: a declared computed result whose inputs are
    traceable to verified evidence (both present -> True; declared but
    untraceable -> False; nothing declared -> None)."""
    calc = (outcome.get("calculation") or {})
    if not calc.get("computed"):
        return None
    computed = calc.get("computed")
    checks: list = []
    expected = calc.get("expected")
    if expected is not None:
        if calc.get("expected_origin") not in TRUSTED_EXPECTED_ORIGINS:
            return None  # untrusted expected basis — not checkable
        checks.append(str(computed) == str(expected))
    recomputed = calc.get("recomputed")
    if recomputed is not None:
        if calc.get("recomputed_origin") not in (
                TRUSTED_RECOMPUTED_ORIGINS):
            return None  # untrusted recomputation — not checkable
        checks.append(str(computed) == str(recomputed))
    if not checks:
        return None  # nothing checkable — unknown stays unknown
    return all(checks)


register_criteria_verifier("calculation", _calculation_verifier)


def _source_comparison_verifier(outcome: Dict[str, Any]) -> "bool | None":
    results = [
        result for result in (outcome.get("criterion_results") or [])
        if isinstance(result, dict)
        and result.get("verifier") == "source_comparison"
    ]
    if not results:
        return None
    if any(result.get("met") is False for result in results):
        return False
    if all(result.get("met") is True for result in results):
        return True
    return None


register_criteria_verifier("source_comparison", _source_comparison_verifier)


def _mutation_verifier(outcome: Dict[str, Any]) -> "bool | None":
    """Mutation criteria (edits, writes, scheduling): the declared
    change was confirmed by READBACK after the write."""
    mutation = (outcome.get("mutation") or {})
    matched = mutation.get("readback_matched")
    if isinstance(matched, bool):
        return bool(matched)
    requested = mutation.get("requested")
    if not requested:
        return None
    fields = (requested.get("fields") if isinstance(requested, dict)
              else None) or {}
    readback_fields = (mutation.get("readback") or {}).get("fields") or {}
    if not fields:
        return None
    for name, expected in fields.items():
        if name not in readback_fields:
            return False
        if str(readback_fields[name]) != str(expected):
            return False
    return True


register_criteria_verifier("mutation", _mutation_verifier)
register_criteria_verifier("scheduling", _mutation_verifier)


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
    _cv_basis, _cv_verdict = criteria_verdict(outcome)
    if _cv_basis.startswith("no_verifier:") or _cv_basis == "criteria_unknown":
        return {
            "task_success": None,
            "tool_success": None,
            "delivery_success": delivery_value,
            "task_success_basis": _cv_basis,
        }
    _cv_basis, _cv_verdict = criteria_verdict(outcome)
    criteria_failed = _cv_verdict is False
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
    elif criteria_failed:
        task_success = False
        basis = _cv_basis
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
    elif _cv_verdict is True:
        task_success = True
        basis = _cv_basis
    elif not _has_verified_evidence(outcome, tools):
        task_success = None
        basis = "insufficient_evidence"
    elif _cv_basis not in ("criteria_not_declared",):
        task_success = None
        basis = _cv_basis
    else:
        task_success = True
        basis = "verified_evidence"

    return {
        "task_success": task_success,
        "tool_success": tool_success,
        "delivery_success": delivery_value,
        "task_success_basis": basis,
    }


def diagnose_task_failure(outcome: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Diagnose a known unsuccessful task without guessing from silence."""
    if not isinstance(outcome, dict) or outcome.get("objective_met") is not False:
        return None
    if outcome.get("user_corrections"):
        return None
    text = str(outcome.get("objective") or "").lower()
    evidence = outcome.get("evidence_refs") or []
    constraints = outcome.get("source_constraints") or {}
    tools = outcome.get("tool_outcomes") or []
    if constraints and not evidence:
        layer, owner = "identity", "configuration"
    elif re.search(r"\b(compare|comparison|difference|versus|vs\.?|reconcile)\b", text):
        layer, owner = "comparison", "capability"
    elif re.search(r"\b(extract|parse|field|column|row|value)\b", text) and tools:
        layer, owner = "extraction", "task_data"
    elif re.search(r"\b(find|search|look\s+up|retrieve|read|fetch)\b", text):
        layer, owner = "discovery", "capability"
    elif tools:
        layer, owner = "execution", "capability"
    else:
        layer, owner = "intent", "capability"
    return {
        "layer": layer,
        "owner": owner,
        "basis": "inferred_from_failed_objective",
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
    inferred = diagnose_task_failure(outcome)
    if inferred is not None:
        return inferred
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
