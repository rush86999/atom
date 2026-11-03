"""Observation-driven adaptation proposals over the existing plan patch.

The reasoning layer chooses retain / clarify / invalidate / replan / reconcile
from an observation and the bounded employee context. Deterministic code
computes the actual affected closure, binds the live base revisions and adopts
the change through ``employee_patch.apply_plan_patch``. No provider call or
model inference occurs inside the CAS callback.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.assignment_plan import downstream_step_ids, step_by_id
from core.employee_patch import (
    PlanPatchError,
    StepPatch,
    StepUpdate,
    apply_plan_patch,
    validate_plan_patch,
)
from core.employee_proposal import ClarificationProposal
from core.employee_work_compiler import (
    WorkRequestCompileError,
    compile_work_request_patch,
)
from core.employee_work_requests import WorkRequest, request_digest

ADAPTATION_SCHEMA = "atom-employee-adaptation-1"


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1, max_length=120)
    kind: Literal[
        "source_version", "quantity", "qualification", "external_response",
        "evidence_result", "uncertain_effect", "user_correction", "expiry",
        "revocation",
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
        "retain", "clarify", "invalidate", "replan", "reconcile",
        "work_request"]
    reason: str = Field(default="", max_length=800)
    observation_ids: List[str] = Field(default_factory=list)
    step_ids: List[str] = Field(default_factory=list)
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    new_steps: List[StepPatch] = Field(default_factory=list)
    update_steps: List[StepUpdate] = Field(default_factory=list)
    work_request: Optional[WorkRequest] = None
    clarification: Optional[ClarificationProposal] = None


class WorkAdaptationProposal(BaseModel):
    """Follow-up proposal for supported business work.

    This schema intentionally does not expose StepPatch/new_steps: the
    compiler supplies execution mechanics on this path.
    """

    model_config = ConfigDict(extra="forbid")

    decision: Literal["retain", "clarify", "replan", "reconcile"]
    reason: str = Field(default="", max_length=800)
    observation_ids: List[str] = Field(default_factory=list)
    work_request: Optional[WorkRequest] = None
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
    if obs.kind == "evidence_result":
        return {
            "decision": "retain",
            **base,
            "reason": (
                obs.reason or
                "Evidence was read; the deterministic floor does not invent "
                "a next work plan from content."),
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


def _adaptation_patch_proposal(
    normalized: AdaptationProposal,
    assignment: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    observations = [
        {"observation_id": item} for item in normalized.observation_ids
    ] or [{"kind": "observation"}]
    return {
        "patch_id": "adaptation-validation",
        "base_task_version": int(context.get("task_version") or 0),
        "base_plan_revision": int(
            context.get("plan_revision")
            or assignment.get("plan_revision") or 1),
        "reason": normalized.reason or "model adaptation proposal",
        "observations": observations,
        "invalidate_steps": list(normalized.step_ids),
        "add_facts": list(normalized.facts),
        "add_steps": [
            item.model_dump() for item in normalized.new_steps
        ],
        "update_steps": [
            item.model_dump() for item in normalized.update_steps
        ],
    }


def _adaptation_errors(
    normalized: AdaptationProposal,
    assignment: Mapping[str, Any],
    context: Mapping[str, Any],
) -> List[str]:
    if normalized.decision == "retain" and context.get(
            "missing_prerequisites"):
        missing = "; ".join(
            f"{item.get('label') or item.get('operation')} needs "
            f"{', '.join(item.get('missing') or [])}"
            for item in context.get("missing_prerequisites") or []
            if isinstance(item, Mapping))
        return [
            "retain leaves the objective unsatisfied with a missing "
            f"prerequisite: {missing}. Choose clarify and ask for the named "
            "missing evidence, or propose supported work that does not need "
            "it."]
    if normalized.decision != "replan":
        return []
    if normalized.work_request is not None:
        if normalized.new_steps or normalized.update_steps or normalized.facts:
            return [
                "work_request cannot be combined with model-authored steps "
                "or facts; the compiler supplies execution mechanics"]
        try:
            compile_work_request_patch(
                normalized.work_request, assignment, context=context)
        except WorkRequestCompileError as exc:
            return [str(exc)]
        except Exception as exc:  # noqa: BLE001 - schema boundary
            return [f"work_request compile: {exc}"]
        return []
    record = {
        "task_version": int(context.get("task_version") or 0),
        "assignment": dict(assignment),
        "operations": [],
    }
    checked = validate_plan_patch(
        _adaptation_patch_proposal(normalized, assignment, context), record)
    return list(checked.get("errors") or [])


def _adaptation_retry_prompt(
    context: Mapping[str, Any], observations: List[Mapping[str, Any]],
    invalid_output: Any, errors: List[str],
) -> str:
    typed = bool(context.get("work_request_schemas"))
    correction = (
        "Return one corrected JSON proposal matching the response schema. "
        "On the supported path return a complete typed work_request or one "
        "clarification; execution mechanics remain compiler-owned."
        if typed else
        "Return one corrected JSON proposal. Do not repeat existing step IDs; "
        "use unique IDs and complete adapter inputs."
    )
    return (
        _adaptation_prompt(context, observations)
        + "\n\nYour previous proposal was invalid:\n"
        + json.dumps(invalid_output, sort_keys=True, default=str)[:4000]
        + "\nValidation errors:\n- " + "\n- ".join(errors[:20])
        + "\n" + correction
    )


def _response_model_for(context: Mapping[str, Any]) -> Any:
    return (
        WorkAdaptationProposal
        if context.get("work_request_schemas") else AdaptationProposal)


def _adaptation_prompt(
    context: Mapping[str, Any], observations: List[Mapping[str, Any]],
    response_model: Any = None,
) -> str:
    model = response_model or _response_model_for(context)
    fields = list(getattr(model, "model_fields", {}) or {})
    shape = "{" + ", ".join(fields) + "}"
    typed = model is WorkAdaptationProposal
    decisions = (
        "- retain: no material change.\n"
        "- clarify: one targeted business fact/choice is missing.\n"
        "- reconcile: a possible external effect needs the existing operation "
        "reconciled; never resend.\n"
    )
    if not typed:
        decisions += (
            "- invalidate/replan: reopen only work affected by the "
            "observation; preserve unrelated completed receipts.\n")
    business_rule = (
        (
            "- For an evidence_result, if a listed "
            "context.available_business_operations is supported by the "
            "accepted evidence and taught terms, choose replan and return "
            "that work_request. Do not return retain merely because evidence "
            "was read. If no listed operation is supported, choose clarify "
            "when one fact is missing, otherwise retain. On a replan, return "
            "one work_request from context.work_request_schemas.\n"
            if typed else (
                "- The accepted evidence does not yet support a listed "
                "business operation. If the objective still requires a "
                "specific missing business record or source, choose clarify "
                "and ask for that exact evidence; do not retain while the "
                "objective remains unresolved and one authorized source "
                "could supply it.\n"
                if context.get("stage") == "follow_up" else "")
        )
        + (
            "- context.available_business_operations entries with status "
            "'missing' or 'ambiguous' name their prerequisites. Choose "
            "clarify and ask for the named missing evidence; do not propose "
            "that work_request until the prerequisite is supplied, and do "
            "not return retain while the objective is unresolved.\n"
            if context.get("missing_prerequisites") else "")
    )
    return (
        "You are the accountable employee's adaptation reasoner. Choose the "
        "bounded response to the observation(s).\n"
        "Rules:\n"
        + business_rule
        + decisions
        + "- Bind evidence by existing durable step_id. Do not invent rows, "
        "prices, totals, facts or authority.\n"
        + (
            "- quote_calculation.columns values are exact column NAMES from "
            "the evidence schema (for example 'Item', 'Qty', 'Price'), never "
            "cell values such as 'A', '2' or '100'.\n"
            "- freight/tax/currency authority_ref is the taught TERM KEY "
            "(for example 'freight', 'tax_basis'), never the term value or a "
            "free-form label; the compiler resolves and compares it.\n"
            "- For invoice_reconciliation, bind invoice/purchase order/"
            "receiving step IDs to context.evidence_results entries whose "
            "business_role is invoice/purchase_order/receiving. Never bind "
            "by numeric step order alone.\n"
            if typed else ""
        )
        + "- Do not invent source/action IDs or authority; do not remove "
        "criteria or budget.\n"
        + (
            "- The compiler supplies execution mechanics. Do not author "
            "executable step JSON, step IDs, adapters, references or inputs "
            "on this supported path.\n"
            if typed else
            "- New step IDs must not repeat existing_step_ids; use the "
            "adapter_views.input_schema and ${step.field} result references.\n"
        )
        + f"- Return JSON only with this shape: {shape}.\n"
        f"- The response schema is {getattr(model, '__name__', 'the response')}"
        "; fields outside that schema are rejected.\n\n"
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
    provider_model: Optional[Sequence[str]] = None,
    deadline: Optional[float] = None,
    attempt_journal: Any = None,
) -> Dict[str, Any]:
    """Propose a response; a provider failure falls back deterministically.

    ``deadline`` is an absolute ``time.monotonic()`` value shared by the
    initial call and its one bounded repair. A repair never gets a fresh
    budget, and a timeout is returned as a typed stage failure instead of
    ``None`` hiding which boundary died.
    """
    response_model = _response_model_for(context)
    journal = attempt_journal
    if journal is None:
        try:
            from core.employee_attempt_journal import AttemptJournal

            journal = AttemptJournal()
        except Exception:  # noqa: BLE001 — diagnostics are optional
            journal = None
    stage_failures: Dict[str, List[Dict[str, Any]]] = {}

    def _remaining() -> Optional[float]:
        if deadline is None:
            return None
        return max(0.0, float(deadline) - time.monotonic())

    def _observer(stage_name: str):
        def observe(event: str, **fields: Any) -> None:
            if event == "failure":
                exc = fields.get("exception")
                try:
                    from core.employee_attempt_journal import failure_kind

                    kind = failure_kind(exc) if exc is not None else None
                except Exception:  # noqa: BLE001
                    kind = None
                stage_failures.setdefault(stage_name, []).append({
                    "kind": kind,
                    "error_type": type(exc).__name__ if exc else None,
                    "label": fields.get("label"),
                    "attempt": fields.get("attempt"),
                })
            if journal is None:
                return
            payload = dict(fields)
            if event == "failure":
                exc = payload.pop("exception", None)
                if exc is not None:
                    journal.failure(exc, call_stage=stage_name, **payload)
                return
            journal.record(event, call_stage=stage_name, **payload)
        return observe

    def _failure_summary(stage_name: str) -> Optional[str]:
        failures = stage_failures.get(stage_name) or []
        if not failures:
            return None
        kinds = []
        for item in failures:
            kind = item.get("kind") or "provider_failure"
            if kind not in kinds:
                kinds.append(kind)
        return "no parsed proposal: " + ", ".join(kinds)

    async def _call(prompt: str, label: str, stage_name: str) -> Any:
        remaining = _remaining()
        if remaining is not None and remaining <= 0:
            error = TimeoutError(f"{stage_name} deadline exhausted")
            if journal is not None:
                journal.failure(
                    error, call_stage=stage_name, label=label, attempt=0,
                    route="deadline", seconds=0.0)
            raise error
        call = pinned_structured_call(
            llm_service,
            prompt=prompt,
            response_model=response_model,
            system_instruction=(
                "You choose bounded business work and plan changes. You "
                "never execute, author execution plumbing or grant "
                "authority. Return JSON only."),
            call_kwargs=(
                {"provider_model": tuple(provider_model)}
                if provider_model else None),
            extra_kwargs={
                "output_mode": "json",
                "cascade": False,
                "allow_moa": False,
                "max_tokens": 1800,
            },
            log_label=label,
            task_type="planning",
            workspace_id=context.get("identity", {}).get("workspace_id"),
            tenant_id=context.get("identity", {}).get("tenant_id"),
            attempt_observer=_observer(stage_name),
        )
        if remaining is None:
            return await call
        try:
            return await asyncio.wait_for(call, timeout=remaining)
        except asyncio.TimeoutError as exc:
            if journal is not None:
                journal.failure(
                    exc, call_stage=stage_name, label=label, attempt=0,
                    route="deadline", seconds=time.monotonic() - deadline
                    if deadline is not None else 0.0)
            raise

    def _normalize(result: Any) -> Dict[str, Any]:
        normalized_model = response_model.model_validate(
            result.model_dump() if isinstance(result, BaseModel) else dict(result))
        normalized = normalized_model.model_dump()
        # Internal conversion happens only after the SELECTED response model
        # has validated the payload.
        return AdaptationProposal.model_validate(normalized).model_dump()

    if llm_service is not None and observations:
        try:
            from core.llm.pinned_planning import pinned_structured_call
        except Exception:  # noqa: BLE001
            pinned_structured_call = None  # type: ignore[assignment]
        if pinned_structured_call is None:
            checked_errors = ["planner transport unavailable"]
            failure_stage = "transport"
        else:
            checked_errors: List[str] = []
            failure_stage = None
            try:
                result = await _call(
                    _adaptation_prompt(
                        context, observations, response_model=response_model),
                    "employee adaptation", "initial")
            except asyncio.TimeoutError:
                result = None
                failure_stage = "initial"
                checked_errors = ["deadline_exceeded: initial"]
            except Exception as exc:  # noqa: BLE001
                result = None
                failure_stage = "initial"
                checked_errors = [f"initial call: {exc}"]
            if result is not None:
                try:
                    normalized = _normalize(result)
                    proposal = AdaptationProposal.model_validate(normalized)
                    errors = _adaptation_errors(proposal, assignment, context)
                    first_errors = list(errors)
                    if not errors:
                        return {
                            "proposal": proposal.model_dump(),
                            "source": "model",
                            "technical_fallback": False,
                            "errors": [],
                            "attempt_id": getattr(journal, "attempt_id", None),
                        }
                    remaining = _remaining()
                    if remaining is not None and remaining <= 0:
                        checked_errors = errors + [
                            "deadline_exceeded: repair"]
                        failure_stage = "repair"
                    else:
                        try:
                            repaired = await _call(
                                _adaptation_retry_prompt(
                                    context, observations, normalized, errors),
                                "employee adaptation repair", "repair")
                        except asyncio.TimeoutError:
                            repaired = None
                            failure_stage = "repair"
                            errors = errors + [
                                "deadline_exceeded: repair"]
                        except Exception as exc:  # noqa: BLE001
                            repaired = None
                            failure_stage = "repair"
                            errors = errors + [f"repair call: {exc}"]
                        if repaired is not None:
                            try:
                                repaired_norm = _normalize(repaired)
                                repaired_prop = AdaptationProposal.model_validate(
                                    repaired_norm)
                                repair_errors = _adaptation_errors(
                                    repaired_prop, assignment, context)
                                if not repair_errors:
                                    return {
                                        "proposal": repaired_prop.model_dump(),
                                        "source": "model_repaired",
                                        "technical_fallback": False,
                                        "errors": [],
                                        "attempt_id": getattr(
                                            journal, "attempt_id", None),
                                        "repair": {
                                            "first_errors": first_errors,
                                            "recovered": True,
                                        },
                                    }
                                errors = repair_errors
                            except Exception as exc:  # noqa: BLE001
                                errors = errors + [
                                    f"repair validation: {exc}"]
                        elif _failure_summary("repair"):
                            errors = errors + [_failure_summary("repair")]
                        checked_errors = errors
                except Exception as exc:  # noqa: BLE001
                    checked_errors = [f"proposal validation: {exc}"]
                    failure_stage = failure_stage or "validation"
            elif not checked_errors:
                summary = _failure_summary("initial")
                checked_errors = [summary] if summary else [
                    "model returned no proposal"]
                if summary:
                    failure_stage = "initial"
            if journal is not None:
                journal.record(
                    "attempt-summary", source="deterministic",
                    failure_stage=failure_stage, errors=checked_errors)
    else:
        checked_errors = []
        failure_stage = None
    fallback = deterministic_adaptation(observations[0], assignment)
    return {
        "proposal": fallback,
        "source": "deterministic",
        "technical_fallback": bool(llm_service and observations),
        "errors": checked_errors,
        "failure_stage": failure_stage,
        "attempt_id": getattr(journal, "attempt_id", None),
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
    if normalized.work_request is not None:
        if decision not in ("replan", "work_request"):
            raise PlanPatchError(
                "a work_request requires decision 'replan' or 'work_request'")
        observation_digest = hashlib.sha256(
            "\n".join(sorted(observation_ids)).encode("utf-8")
        ).hexdigest()[:16]
        compile_context = {
            "task_version": int(record.get("task_version") or 0),
            "plan_revision": int(assignment.get("plan_revision") or 1),
            "authorized_actions": list(
                assignment.get("authorized_actions") or []),
            "action_views": [],
        }
        try:
            patch = compile_work_request_patch(
                normalized.work_request, assignment,
                context=compile_context)
        except WorkRequestCompileError as exc:
            raise PlanPatchError(str(exc)) from exc
        request_id = request_digest(normalized.work_request)
        patch["observations"] = [
            {"observation_id": item} for item in observation_ids
        ] + list(patch.get("observations") or [])
        patch["patch_id"] = f"{patch.get('patch_id')}-{observation_digest}"
        result = apply_plan_patch(
            lifecycle, run_id, patch,
            rationale=rationale or (
                f"adapted work {request_id}: {normalized.reason[:300]}"))
        return {
            **result,
            "decision": decision,
            "reason": normalized.reason,
            "work_request": normalized.work_request.model_dump(),
            "compiled": {
                "request_digest": request_id,
                "step_ids": [
                    item.get("step_id") for item in patch.get("add_steps") or []
                ],
            },
            "affected_steps": [],
        }
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
