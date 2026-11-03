"""Observation-driven adaptation proposals over the existing plan patch.

The reasoning layer chooses retain / clarify / invalidate / replan / reconcile
from an observation and the bounded employee context. Deterministic code
computes the actual affected closure, binds the live base revisions and adopts
the change through ``employee_patch.apply_plan_patch``. No provider call or
model inference occurs inside the CAS callback.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.assignment_plan import downstream_step_ids, step_by_id
from core.employee_patch import (
    PlanPatchError,
    StepPatch,
    StepUpdate,
    apply_plan_patch,
)
from core.employee_proposal import ClarificationProposal

ADAPTATION_SCHEMA = "atom-employee-adaptation-1"


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1, max_length=120)
    kind: Literal[
        "source_version", "quantity", "qualification", "external_response",
        "uncertain_effect", "user_correction", "expiry", "revocation",
    ]
    subject_id: str = Field(default="", max_length=200)
    resource_id: str = Field(default="", max_length=200)
    step_id: str = Field(default="", max_length=80)
    fact_id: str = Field(default="", max_length=120)
    value: Any = None
    evidence_state: str = Field(default="established", max_length=20)
    source_refs: List[Dict[str, Any]] = Field(default_factory=list)
    reason: str = Field(default="", max_length=500)


class AdaptationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[
        "retain", "clarify", "invalidate", "replan", "reconcile"]
    reason: str = Field(default="", max_length=800)
    observation_ids: List[str] = Field(default_factory=list)
    step_ids: List[str] = Field(default_factory=list)
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    new_steps: List[StepPatch] = Field(default_factory=list)
    update_steps: List[StepUpdate] = Field(default_factory=list)
    clarification: Optional[ClarificationProposal] = None


def _observation(observation: Any) -> Observation:
    if isinstance(observation, BaseModel):
        observation = observation.model_dump()
    try:
        return Observation.model_validate(dict(observation or {}))
    except Exception as exc:  # noqa: BLE001
        raise PlanPatchError(f"invalid observation: {exc}") from exc


def _dependent_steps(assignment: Mapping[str, Any], fact_id: str) -> List[str]:
    roots = []
    for step in assignment.get("steps") or []:
        for requirement in step.get("requires") or []:
            if (requirement.get("kind") == "fact"
                    and requirement.get("fact_id") == fact_id):
                roots.append(step.get("step_id"))
    return downstream_step_ids(assignment, roots) if roots else []


def deterministic_adaptation(
    observation: Any,
    assignment: Mapping[str, Any],
) -> Dict[str, Any]:
    """A safe, evidence-local proposal; never invents a business fact."""
    obs = _observation(observation)
    base = {
        "observation_ids": [obs.observation_id],
        "reason": obs.reason,
    }
    if obs.kind == "uncertain_effect":
        return {
            "decision": "reconcile",
            **base,
            "reason": (
                obs.reason or
                "A possible effect must be reconciled against its original "
                "operation; do not resend."),
        }
    if obs.kind == "external_response":
        return {
            "decision": "retain",
            **base,
            "reason": (
                obs.reason or
                "The correlated response is consumed by the existing "
                "operation; no plan change is needed."),
        }
    if obs.kind == "qualification":
        if obs.evidence_state != "established" or obs.value is None:
            return {
                "decision": "clarify",
                **base,
                "clarification": {
                    "question": (
                        f"What is the established value for "
                        f"{obs.fact_id or 'the qualification'}?"),
                    "concept": obs.fact_id or "qualification",
                    "unblocks": "Dependent commercial work.",
                },
            }
        affected = _dependent_steps(assignment, obs.fact_id)
        return {
            "decision": "invalidate" if affected else "retain",
            **base,
            "step_ids": affected,
            "facts": [{
                "fact_id": obs.fact_id,
                "subject": {"kind": "business_entity", "id": obs.subject_id}
                if obs.subject_id else {},
                "field_id": obs.fact_id,
                "value": obs.value,
                "value_type": (
                    "boolean" if isinstance(obs.value, bool) else None),
                "evidence_state": "established",
                "source_refs": list(obs.source_refs),
                "validity": {"policy": "current"},
            }],
            "reason": obs.reason or (
                "Qualification evidence changed; only dependent work is "
                "reopened."),
        }
    if obs.kind in ("source_version", "quantity", "user_correction"):
        if obs.step_id and step_by_id(dict(assignment), obs.step_id):
            affected = downstream_step_ids(assignment, [obs.step_id])
            return {
                "decision": "invalidate",
                **base,
                "step_ids": affected,
                "reason": obs.reason or (
                    f"{obs.kind} changed; only the affected branch and its "
                    f"descendants are reopened."),
            }
        return {
            "decision": "clarify",
            **base,
            "clarification": {
                "question": (
                    f"Which work item does the {obs.kind} change affect?"),
                "concept": obs.kind,
                "unblocks": "Reopening only the affected branch.",
            },
        }
    if obs.kind in ("expiry", "revocation"):
        affected = [
            step.get("step_id") for step in assignment.get("steps") or []
            if step.get("status") in ("pending", "waiting", "approved",
                                      "awaiting_approval")
        ]
        return {
            "decision": "invalidate" if affected else "retain",
            **base,
            "step_ids": affected,
            "reason": obs.reason or (
                "Current authority/evidence expired; unstarted dependent "
                "work is blocked."),
        }
    return {
        "decision": "retain",
        **base,
        "reason": obs.reason or "No material plan change is justified.",
    }


def _adaptation_prompt(
    context: Mapping[str, Any], observations: List[Mapping[str, Any]],
) -> str:
    return (
        "You are the accountable employee's adaptation reasoner. Choose the "
        "bounded response to the observation(s).\n"
        "Rules:\n"
        "- retain: no material change.\n"
        "- clarify: one targeted business fact/choice is missing.\n"
        "- invalidate/replan: reopen only work affected by the observation; "
        "preserve unrelated completed receipts.\n"
        "- reconcile: a possible external effect needs the existing operation "
        "reconciled; never resend.\n"
        "- Do not invent source/action IDs or authority; do not remove "
        "criteria or budget.\n"
        "- Return JSON only: {decision, reason, observation_ids, step_ids, "
        "facts, new_steps, clarification}.\n\n"
        "CONTEXT:\n" + json.dumps(context, sort_keys=True, default=str)
        + "\n\nOBSERVATIONS:\n"
        + json.dumps(observations, sort_keys=True, default=str)
    )


async def propose_adaptation(
    context: Mapping[str, Any],
    observations: List[Mapping[str, Any]],
    *,
    assignment: Mapping[str, Any],
    llm_service: Any = None,
) -> Dict[str, Any]:
    """Propose a response; a provider failure falls back deterministically."""
    if llm_service is not None and observations:
        try:
            from core.llm.pinned_planning import pinned_structured_call
            result = await pinned_structured_call(
                llm_service,
                prompt=_adaptation_prompt(context, observations),
                response_model=AdaptationProposal,
                system_instruction=(
                    "You propose bounded, read-only employee plan changes. "
                    "You never execute or grant authority. Return JSON only."),
                call_kwargs=None,
                extra_kwargs={
                    "output_mode": "json",
                    "cascade": False,
                    "allow_moa": False,
                    "max_tokens": 1800,
                },
                log_label="employee adaptation",
                task_type="planning",
                workspace_id=context.get("identity", {}).get("workspace_id"),
                tenant_id=context.get("identity", {}).get("tenant_id"),
            )
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            try:
                normalized = (
                    result.model_dump()
                    if isinstance(result, BaseModel) else dict(result))
                proposal = AdaptationProposal.model_validate(normalized)
                return {
                    "proposal": proposal.model_dump(),
                    "source": "model",
                    "technical_fallback": False,
                    "errors": [],
                }
            except Exception as exc:  # noqa: BLE001
                checked_errors = [str(exc)]
        else:
            checked_errors = ["model returned no proposal"]
    else:
        checked_errors = []
    fallback = deterministic_adaptation(observations[0], assignment)
    return {
        "proposal": fallback,
        "source": "deterministic",
        "technical_fallback": bool(llm_service and observations),
        "errors": checked_errors,
    }


def adopt_adaptation(
    lifecycle: Any,
    run_id: str,
    proposal: Any,
    *,
    rationale: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate one proposal against current state and adopt its patch."""
    if isinstance(proposal, BaseModel):
        proposal = proposal.model_dump()
    try:
        normalized = AdaptationProposal.model_validate(dict(proposal or {}))
    except Exception as exc:  # noqa: BLE001
        raise PlanPatchError(f"invalid adaptation proposal: {exc}") from exc
    decision = normalized.decision
    if decision in ("retain", "reconcile"):
        return {
            "status": decision,
            "decision": decision,
            "reason": normalized.reason,
            "assignment": lifecycle.get_assignment(run_id),
        }
    if decision == "clarify":
        return {
            "status": "clarification_required",
            "decision": decision,
            "reason": normalized.reason,
            "clarification": (
                normalized.clarification.model_dump()
                if normalized.clarification else None),
        }
    record = lifecycle.get_task(run_id)
    if record is None:
        raise PlanPatchError(f"no task record on run {run_id}")
    assignment = record.get("assignment") or {}
    observation_ids = [str(item) for item in normalized.observation_ids]
    if not observation_ids:
        raise PlanPatchError(
            "an invalidate/replan adaptation requires observation ids")
    consumed = set()
    for history_item in assignment.get("patch_history") or []:
        for observed in history_item.get("observations") or []:
            if isinstance(observed, dict):
                observed_id = (
                    observed.get("observation_id") or observed.get("id"))
            else:
                observed_id = observed
            if observed_id:
                consumed.add(str(observed_id))
    if all(item in consumed for item in observation_ids):
        # A replayed page/event must not reopen completed work or create a
        # second plan revision. The first adoption remains authoritative.
        return {
            "status": "already_applied",
            "decision": decision,
            "reason": "observation already consumed by an earlier patch",
            "assignment": assignment,
        }
    if any(item in consumed for item in observation_ids):
        raise PlanPatchError(
            "adaptation mixes already-consumed and new observation ids")
    affected: List[str] = []
    for step_id in normalized.step_ids:
        if step_by_id(assignment, step_id) is None:
            raise PlanPatchError(f"unknown step {step_id!r}")
        affected.extend(downstream_step_ids(assignment, [step_id]))
    affected = list(dict.fromkeys(affected))
    observation_digest = hashlib.sha256(
        "\n".join(sorted(observation_ids)).encode("utf-8")).hexdigest()[:16]
    patch = {
        "patch_id": f"adapt-{observation_digest}",
        "base_task_version": int(record.get("task_version") or 0),
        "base_plan_revision": int(assignment.get("plan_revision") or 1),
        "reason": normalized.reason or "observation-driven reassessment",
        "observations": [
            {"observation_id": item} for item in normalized.observation_ids
        ] or [{"kind": "observation"}],
        "invalidate_steps": affected,
        "add_facts": list(normalized.facts),
        "add_steps": [
            item.model_dump() for item in normalized.new_steps
        ],
        "update_steps": [
            item.model_dump() for item in normalized.update_steps
        ],
    }
    result = apply_plan_patch(
        lifecycle, run_id, patch,
        rationale=rationale or (
            f"adaptation {patch['patch_id']}: {normalized.reason[:300]}"))
    return {
        **result,
        "decision": decision,
        "reason": normalized.reason,
        "affected_steps": affected,
    }
