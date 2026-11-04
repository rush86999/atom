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

from pydantic import BaseModel, ConfigDict, Field, create_model

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
from core.employee_work_requests import (
    AwaitEvidenceRequest,
    InvoiceReconciliationRequest,
    QuoteCalculationRequest,
    WorkRequest,
    request_digest,
)

ADAPTATION_SCHEMA = "atom-employee-adaptation-1"


class _BudgetExhausted(Exception):
    """The shared call budget was already spent before a stage dispatched.

    This is deliberately distinct from a dispatched stage that timed out: a
    skipped stage is not another model semantic failure and must not be counted
    as one in the attempt journal or the campaign diagnosis.
    """


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1, max_length=120)
    kind: Literal[
        "source_version", "quantity", "qualification", "external_response",
        "evidence_result", "uncertain_effect", "user_correction", "expiry",
        "revocation", "waiting_state",
    ]
    subject_id: str = Field(default="", max_length=200)
    resource_id: str = Field(default="", max_length=200)
    step_id: str = Field(default="", max_length=80)
    fact_id: str = Field(default="", max_length=120)
    value: Any = None
    evidence_state: str = Field(default="established", max_length=20)
    source_refs: List[Dict[str, Any]] = Field(default_factory=list)
    reason: str = Field(default="", max_length=500)
    shape: str = Field(default="", max_length=40)
    columns: List[str] = Field(default_factory=list)
    data_keys: List[str] = Field(default_factory=list)
    verified: Optional[bool] = None


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
    if normalized.decision == "clarify":
        clarification = normalized.clarification
        if clarification is None or not str(
                clarification.question or "").strip():
            return [
                "clarify requires one specific clarification question the "
                "user can answer"]
        return []
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
    if normalized.work_request is not None and normalized.decision not in (
            "replan", "work_request"):
        return [
            "a typed work_request requires decision 'replan' or "
            "'work_request'; 'reconcile' is only for an existing uncertain "
            "effect"]
    if normalized.decision != "replan":
        return []
    if normalized.work_request is not None:
        operation = str(getattr(
            normalized.work_request, "operation", "") or "")
        if operation and operation != "await_evidence" and not context.get(
                "waiting"):
            # A missing external record the OBJECTIVE explicitly names must
            # become a durable wait before unrelated work, or the job could
            # silently complete a partial objective. The model still chooses
            # the fact/subject/source; only the ordering is policy.
            objective_tokens = set(
                " ".join(str(context.get("objective") or "").lower()
                         .replace("_", " ").split()).split())
            for item in context.get("missing_prerequisites") or []:
                if not isinstance(item, Mapping):
                    continue
                for role in item.get("missing") or []:
                    role_tokens = set(
                        " ".join(str(role or "").lower().replace("_", " ")
                                 .split()).split())
                    if role_tokens & objective_tokens:
                        return [
                            "the objective explicitly requires the missing "
                            f"'{role}' evidence; choose await_evidence for "
                            "that external fact before unrelated work"]
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


# The compact invoice request keeps only the model-owned choice: the
# operation, the accepted role step IDs and the currency. Field maps and the
# evidence array stay compiler-owned (defaults are resolved from the accepted
# evidence). This also keeps a small model from copying JSON-schema `$ref`
# artifacts into the evidence array or sending a cell value where a column
# name belongs. The subset is still a valid InvoiceReconciliationRequest.
_COMPACT_INVOICE_REQUEST = create_model(
    "CompactInvoiceReconciliationRequest",
    __config__=ConfigDict(extra="forbid"),
    operation=(Literal["invoice_reconciliation"], "invoice_reconciliation"),
    invoice_step_id=(Optional[str], None),
    purchase_order_step_id=(Optional[str], None),
    receiving_step_id=(Optional[str], None),
    currency=(Optional[str], None),
    reason=(str, ""),
)

_COMPACT_REQUEST_MODELS = {
    "invoice_reconciliation": _COMPACT_INVOICE_REQUEST,
    "quote_calculation": QuoteCalculationRequest,
}


def _compact_evidence(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Relevant accepted evidence, bounded; execution still uses full rows."""
    return {
        "step_id": item.get("step_id"),
        "title": item.get("title"),
        "adapter": item.get("adapter"),
        "status": item.get("status"),
        "summary": item.get("summary"),
        "business_role": item.get("business_role"),
        "schema": list(item.get("schema") or [])[:20],
        "data_keys": list(item.get("data_keys") or [])[:30],
        "data_preview": dict(item.get("data_preview") or {}),
        "verification": dict(item.get("verification") or {}),
        "coverage": dict(item.get("coverage") or {}),
    }


def _compact_single_request_context(
    context: Mapping[str, Any],
    observations: List[Mapping[str, Any]],
    *,
    require_unresolved_requirement: bool = False,
) -> Optional[Dict[str, Any]]:
    """Narrow typed continuation when exactly one operation is ready.

    The model still chooses replan/retain/clarify and returns the typed
    request. This removes the all-purpose union schema and unrelated
    completed-branch details before the first call, not after the budget is
    already exhausted.
    """
    rules = context.get("rules") or {}
    allowed = [
        str(item) for item in rules.get("allowed_work_requests") or []
        if str(item).strip()
    ]
    if len(allowed) != 1:
        return None
    operation = allowed[0]
    request_model = _COMPACT_REQUEST_MODELS.get(operation)
    if request_model is None:
        return None
    entry = next((
        item for item in context.get("available_business_operations") or []
        if isinstance(item, Mapping)
        and str(item.get("operation") or "") == operation
        and str(item.get("status") or "") == "ready"), None)
    if entry is None:
        return None
    requirement = next((
        item for item in context.get("business_requirements") or []
        if isinstance(item, Mapping)
        and str(item.get("operation") or "") == operation
        and str(item.get("status") or "") != "satisfied"), None)
    if require_unresolved_requirement and requirement is None:
        # Compact-first is for the continuation of an unresolved scoped
        # requirement, not for every single-ready proposal.
        return None
    relevant_ids = {
        str(item.get("step_id"))
        for item in entry.get("evidence") or []
        if isinstance(item, Mapping) and item.get("step_id")
    }
    relevant_roles = {"invoice", "purchase_order", "receiving", "quote_rows"}
    evidence = []
    for item in context.get("evidence_results") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("step_id") or "") in relevant_ids or str(
                item.get("business_role") or "") in relevant_roles:
            evidence.append(_compact_evidence(item))
    compact_observations = [
        dict(item) for item in observations
        if isinstance(item, Mapping)
        and (
            item.get("kind") == "waiting_state"
            or str(item.get("step_id") or "") in relevant_ids)
    ]
    response_model = create_model(
        "CompactEmployeeWorkProposal",
        __config__=ConfigDict(extra="forbid"),
        decision=(Literal["replan", "retain", "clarify"], ...),
        reason=(str, ""),
        observation_ids=(List[str], Field(default_factory=list)),
        work_request=(Optional[request_model], None),
        clarification=(Optional[ClarificationProposal], None),
    )
    payload = {
        "objective": str(context.get("objective") or "")[:1000],
        "operation": operation,
        "requirement": requirement,
        "evidence": evidence[:8],
        "roles": entry.get("roles") or {},
        "allowed_step_ids": sorted(relevant_ids),
        "known_identities": entry.get("known_identities") or {},
        "teaching_terms": (
            (context.get("teaching") or {}).get("terms") or {}),
        "decisions": ["replan", "retain", "clarify"],
    }
    operation_rule = ""
    if operation == "invoice_reconciliation":
        operation_rule = (
            "Use the accepted invoice, purchase-order and receiving step IDs "
            "from the context. Do not supply field maps or an evidence "
            "array; the compiler resolves the accepted default field names "
            "and binds the role step IDs.\n"
        )
    prompt = (
        "You choose one bounded employee response. The only allowed operation "
        f"is {operation}.\n"
        "Choose replan only when the accepted evidence and taught terms "
        "support that operation; return one typed work_request matching the "
        "provided schema and accepted step IDs/identities. Choose retain when "
        "no material work is justified, or clarify when one specific fact is "
        "missing. Do not invent rows, prices, totals, identities or "
        "authority; do not return a different operation.\n"
        + operation_rule
        + "CONTEXT:\n" + json.dumps(payload, sort_keys=True, default=str)
        + "\n\nOBSERVATIONS:\n"
        + json.dumps(compact_observations[:8], sort_keys=True, default=str)
    )
    return {
        "operation": operation,
        "prompt": prompt,
        "response_model": response_model,
        "observation_ids": [
            str(item.get("observation_id")) for item in compact_observations
            if item.get("observation_id")
        ],
    }


def _compact_single_request_prompt(
    context: Mapping[str, Any],
    observations: Optional[List[Mapping[str, Any]]] = None,
) -> str:
    """Compatibility wrapper for the bounded one-operation prompt."""
    compact = _compact_single_request_context(
        context, list(observations or []))
    return compact["prompt"] if compact else ""


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
            "- If context.waiting is present, that dependent scope is blocked "
            "by an external fact and the wait is already durable. Never return "
            "await_evidence again in this state. Choose replan with one ready "
            "operation from context.ready_operations (independent work) and "
            "name the fact it must not depend on; choose retain only when "
            "ready_operations is empty.\n"
            "- To wait for a material external fact, choose replan with an "
            "await_evidence work_request: name the business fact, its "
            "subject, the authorized source/channel expected to answer, the "
            "typed answer and the dependent work it blocks. Set "
            "blocks_operation to the supported operation whose verified "
            "result depends on that fact (for example "
            "invoice_reconciliation); this becomes a durable result "
            "requirement. The compiler derives the durable wait and "
            "correlation; never author step, operation or correlation ids.\n"
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
            "'missing' or 'ambiguous' name their prerequisites. If the "
            "objective explicitly requests that dependent work and the "
            "missing item is an external business record/fact that only an "
            "authorized source can supply, choose replan with an "
            "await_evidence request for that fact (use the operation's "
            "known_identities for the subject and its missing field for the "
            "fact) before unrelated work. In 'blocks', name the blocked "
            "operation label exactly as listed (for example 'invoice "
            "reconciliation') and set blocks_operation to its exact "
            "supported operation id; do not claim an unrelated operation is "
            "blocked. Never wait for a term or value the agent can choose, "
            "and never propose the blocked work_request until the fact "
            "arrives. Do not return retain while the objective is unresolved.\n"
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
            "the evidence schema; never use cell values. Map each semantic "
            "field to a DIFFERENT column with matching meaning: item_id is "
            "the descriptive item/product column, quantity is a numeric "
            "units/qty column, unit_price is a numeric price/cost column. "
            "Inspect the evidence schema and sample rows; never reuse one "
            "column for two fields or map a text column to quantity/price.\n"
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


def _routing_snapshot() -> Dict[str, Any]:
    try:
        from core.llm.model_provenance import get_route_attribution

        attribution = get_route_attribution()
        if not attribution.get("mode"):
            attribution["mode"] = "deterministic"
        return attribution
    except Exception:  # noqa: BLE001 — diagnostics are optional
        return {"mode": "deterministic"}


def _record_routing_failure(code: str) -> None:
    """Attach a business-safe failure code at the employee boundary.

    A deadline that expires around the pinned-call wrapper never reaches the
    provider's own error classification. The employee still needs to explain
    why no model response was used, without exposing a raw exception.
    """
    try:
        from core.llm.model_provenance import set_routing_error

        set_routing_error(
            code, "the employee reasoning step produced no usable response")
    except Exception:  # noqa: BLE001 — diagnostics are optional
        pass


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
    stage_no_results: Dict[str, List[Dict[str, Any]]] = {}

    def _remaining() -> Optional[float]:
        if deadline is None:
            return None
        return max(0.0, float(deadline) - time.monotonic())

    def _observer(stage_name: str):
        def observe(event: str, **fields: Any) -> None:
            if event == "no_result":
                stage_no_results.setdefault(stage_name, []).append(dict(
                    fields.get("failure") or {}))
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
        failures = [
            *(stage_failures.get(stage_name) or []),
            *(stage_no_results.get(stage_name) or []),
        ]
        if not failures:
            return None
        kinds = []
        for item in failures:
            kind = item.get("kind") or "provider_failure"
            if kind not in kinds:
                kinds.append(kind)
        summary = "no parsed proposal: " + ", ".join(kinds)
        details = [
            str(item.get("detail") or "").strip()
            for item in failures
            if str(item.get("detail") or "").strip()
        ]
        if details:
            summary += " — " + details[-1][:300]
        return summary

    def _record_skipped(stage_name: str, label: str) -> None:
        if journal is not None:
            journal.record(
                "skipped_due_to_budget", call_stage=stage_name, label=label,
                attempt=0, route="deadline", seconds=0.0)

    async def _call(
        prompt: str, label: str, stage_name: str, *,
        model: Any = None, max_tokens: int = 1800,
        capability_profile: Optional[str] = None,
    ) -> Any:
        remaining = _remaining()
        if remaining is not None and remaining <= 0:
            _record_skipped(stage_name, label)
            raise _BudgetExhausted(stage_name)
        call = pinned_structured_call(
            llm_service,
            prompt=prompt,
            response_model=model or response_model,
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
                "max_tokens": max_tokens,
            },
            log_label=label,
            task_type="planning",
            capability_profile=capability_profile,
            workspace_id=context.get("identity", {}).get("workspace_id"),
            tenant_id=context.get("identity", {}).get("tenant_id"),
            attempt_observer=_observer(stage_name),
        )
        if remaining is None:
            return await call
        try:
            return await asyncio.wait_for(call, timeout=remaining)
        except asyncio.TimeoutError as exc:
            _record_routing_failure("deadline_cancelled")
            if journal is not None:
                journal.failure(
                    exc, call_stage=stage_name, label=label, attempt=0,
                    route="deadline", seconds=time.monotonic() - deadline
                    if deadline is not None else 0.0)
            raise

    def _normalize(result: Any, model: Any = None) -> Dict[str, Any]:
        selected_model = model or response_model
        normalized_model = selected_model.model_validate(
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
            # Single-ready-operation continuation: use the narrow typed
            # request/schema BEFORE the all-purpose adaptation prompt. This is
            # a model choice, not a deterministic work selection.
            compact = _compact_single_request_context(
                context, observations,
                require_unresolved_requirement=True)
            if compact is not None:
                checked_errors: List[str] = []
                failure_stage = None
                result = None
                try:
                    result = await _call(
                        compact["prompt"], "employee adaptation compact",
                        "compact", model=compact["response_model"],
                        max_tokens=1200,
                        capability_profile=(
                            "employee_adaptive_planning_compact"))
                except _BudgetExhausted:
                    failure_stage = "compact"
                    checked_errors = ["skipped_due_to_budget: compact"]
                except asyncio.TimeoutError:
                    _record_routing_failure("deadline_cancelled")
                    failure_stage = "compact"
                    checked_errors = ["deadline_exceeded: compact"]
                except Exception as exc:  # noqa: BLE001
                    failure_stage = "compact"
                    checked_errors = [f"compact call: {exc}"]
                if result is None and not checked_errors:
                    summary = _failure_summary("compact")
                    checked_errors = [summary] if summary else [
                        "model returned no proposal"]
                    failure_stage = "compact"
                if result is not None:
                    try:
                        normalized = _normalize(
                            result, compact["response_model"])
                        proposal = AdaptationProposal.model_validate(normalized)
                        errors = _adaptation_errors(
                            proposal, assignment, context)
                        if not errors:
                            return {
                                "proposal": proposal.model_dump(),
                                "source": "model_compact",
                                "technical_fallback": False,
                                "errors": [],
                                "attempt_id": getattr(
                                    journal, "attempt_id", None),
                                "routing": _routing_snapshot(),
                                "prompt_mode": "compact",
                            }
                        remaining = _remaining()
                        if remaining is not None and remaining <= 0:
                            _record_skipped(
                                "compact_repair",
                                "employee adaptation compact repair")
                            checked_errors = errors + [
                                "skipped_due_to_budget: compact_repair"]
                            failure_stage = "compact"
                        else:
                            repair_prompt = (
                                compact["prompt"]
                                + "\n\nYour previous proposal was invalid:\n"
                                + json.dumps(
                                    normalized, sort_keys=True, default=str
                                )[:4000]
                                + "\nValidation errors:\n- "
                                + "\n- ".join(errors[:20]))
                            try:
                                repaired = await _call(
                                    repair_prompt,
                                    "employee adaptation compact repair",
                                    "compact_repair",
                                    model=compact["response_model"],
                                    max_tokens=1200,
                                    capability_profile=(
                                        "employee_adaptive_planning_compact"))
                            except _BudgetExhausted:
                                repaired = None
                                failure_stage = "compact_repair"
                                errors = errors + [
                                    "skipped_due_to_budget: compact_repair"]
                            except asyncio.TimeoutError:
                                repaired = None
                                failure_stage = "compact_repair"
                                errors = errors + [
                                    "deadline_exceeded: compact_repair"]
                            except Exception as exc:  # noqa: BLE001
                                repaired = None
                                failure_stage = "compact_repair"
                                errors = errors + [f"compact repair: {exc}"]
                            if repaired is not None:
                                try:
                                    repaired_norm = _normalize(
                                        repaired, compact["response_model"])
                                    repaired_prop = (
                                        AdaptationProposal.model_validate(
                                            repaired_norm))
                                    repair_errors = _adaptation_errors(
                                        repaired_prop, assignment, context)
                                    if not repair_errors:
                                        return {
                                            "proposal": repaired_prop.model_dump(),
                                            "source": "model_compact",
                                            "technical_fallback": False,
                                            "errors": [],
                                            "attempt_id": getattr(
                                                journal, "attempt_id", None),
                                            "routing": _routing_snapshot(),
                                            "prompt_mode": "compact",
                                            "repair": {
                                                "first_errors": errors,
                                                "recovered": True,
                                            },
                                        }
                                    errors = repair_errors
                                except Exception as exc:  # noqa: BLE001
                                    errors = errors + [
                                        f"compact repair validation: {exc}"]
                            checked_errors = errors
                    except Exception as exc:  # noqa: BLE001
                        checked_errors = [
                            f"compact proposal validation: {exc}"]
                        failure_stage = "compact"
                fallback = deterministic_adaptation(
                    observations[0], assignment)
                if journal is not None:
                    journal.record(
                        "attempt-summary", source="deterministic",
                        failure_stage=failure_stage,
                        errors=checked_errors,
                        prompt_mode="compact")
                return {
                    "proposal": fallback,
                    "source": "deterministic",
                    "technical_fallback": bool(llm_service and observations),
                    "errors": checked_errors,
                    "failure_stage": failure_stage,
                    "attempt_id": getattr(journal, "attempt_id", None),
                    "prompt_mode": "compact",
                }
            checked_errors: List[str] = []
            failure_stage = None
            try:
                result = await _call(
                    _adaptation_prompt(
                        context, observations, response_model=response_model),
                    "employee adaptation", "initial")
            except _BudgetExhausted:
                result = None
                failure_stage = "initial"
                checked_errors = ["skipped_due_to_budget: initial"]
            except asyncio.TimeoutError:
                _record_routing_failure("deadline_cancelled")
                result = None
                failure_stage = "initial"
                checked_errors = ["deadline_exceeded: initial"]
            except Exception as exc:  # noqa: BLE001
                result = None
                failure_stage = "initial"
                checked_errors = [f"initial call: {exc}"]
            if result is None:
                compact_prompt = _compact_single_request_prompt(context)
                if compact_prompt:
                    try:
                        result = await _call(
                            compact_prompt,
                            "employee adaptation compact", "compact",
                            capability_profile=(
                                "employee_adaptive_planning_compact"))
                    except _BudgetExhausted:
                        failure_stage = "compact"
                        checked_errors = checked_errors + [
                            "skipped_due_to_budget: compact"]
                    except asyncio.TimeoutError:
                        _record_routing_failure("deadline_cancelled")
                        failure_stage = "compact"
                        checked_errors = checked_errors + [
                            "deadline_exceeded: compact"]
                    except Exception as exc:  # noqa: BLE001
                        failure_stage = "compact"
                        checked_errors = checked_errors + [
                            f"compact call: {exc}"]
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
                            "routing": _routing_snapshot(),
                        }
                    remaining = _remaining()
                    if remaining is not None and remaining <= 0:
                        _record_skipped(
                            "repair", "employee adaptation repair")
                        checked_errors = errors + [
                            "skipped_due_to_budget: repair"]
                        failure_stage = "repair"
                    else:
                        try:
                            repaired = await _call(
                                _adaptation_retry_prompt(
                                    context, observations, normalized, errors),
                                "employee adaptation repair", "repair")
                        except _BudgetExhausted:
                            repaired = None
                            failure_stage = "repair"
                            errors = errors + [
                                "skipped_due_to_budget: repair"]
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
                                        "routing": _routing_snapshot(),
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
        "routing": _routing_snapshot(),
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
