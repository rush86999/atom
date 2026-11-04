"""Persist evaluated business outcomes into scoped routing feedback.

The transport path already records an outcome row when a model call returns
(``BYOKHandler._record_outcome_feedback``). That row answers "did the call
produce parseable output?" — it cannot answer "was the employee's proposal or
business result correct?". This module is the consumer-side bridge: the
employee validation/compile/execution boundary evaluates the work with its
own deterministic rules and annotates the SAME generation row with a
``failure_kind`` and a business verdict.

Hard rules (owner/verifier priority 2026-11-04):

* A deterministic fallback is never recorded as model success.
* A transport/schema/timeout failure is not re-labelled as a semantic
  business failure; the handler already recorded it and this module skips it.
* Missing evidence is not automatically a model failure. Only a deterministic
  rejection (invalid proposal, invalid plan reference, wrong field mapping) or
  an explicit business result verdict is recorded.
* The feedback row carries the exact profile/version/workspace/tenant and
  provider/model of the served attempt, so the capability selector can scope
  the evidence. Unknown scope/profile is skipped, never guessed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

#: Results that represent a model-owned proposal. A deterministic fallback is
#: never in this set, even when it was produced after a model rejection.
MODEL_SOURCES = frozenset({"model", "model_repaired", "model_compact"})

#: Route-boundary failures. The handler's outcome row already distinguishes
#: these; the business consumer must not turn them into semantic judgements.
AVAILABILITY_ERRORS = frozenset({
    "provider_failure",
    "deadline_cancelled",
    "no_suitable_configured_model",
    "malformed_structured_output",
    "scope_unresolved",
    "pin_failed",
})

#: Deterministic business failure kinds understood by the capability
#: evidence loader (``capability_profiles.parse_evidence_rows``).
EVIDENCE_SELECTION_FAILURE = "wrong_evidence_selection"
INVALID_PLAN_FAILURE = "invalid_plan_reference"
WRONG_MAPPING_FAILURE = "wrong_field_mapping"
BUSINESS_RESULT_FAILURE = "unsatisfactory_business_result"
GENERIC_SEMANTIC_FAILURE = "semantic_failure"


def _routing(result: Mapping[str, Any]) -> Mapping[str, Any]:
    routing = result.get("routing")
    return routing if isinstance(routing, Mapping) else {}


def _served_route(routing: Mapping[str, Any]) -> Optional[tuple[str, str]]:
    served = routing.get("served_route")
    if not isinstance(served, Mapping):
        return None
    provider = str(served.get("provider") or "").strip()
    model = str(served.get("model") or "").strip()
    if not provider or not model:
        return None
    return provider, model


def _profile(routing: Mapping[str, Any]) -> tuple[str, str]:
    profile = routing.get("profile")
    if not isinstance(profile, Mapping):
        return "", ""
    return (
        str(profile.get("name") or "").strip(),
        str(profile.get("version") or "").strip(),
    )


def _availability_error(routing: Mapping[str, Any]) -> bool:
    error = routing.get("error")
    if not isinstance(error, Mapping):
        return False
    return str(error.get("code") or "") in AVAILABILITY_ERRORS


def attempt_context(
    result: Mapping[str, Any],
    *,
    require_model_source: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return the attributable served attempt, or ``None``.

    ``routing_result_id`` is the generation identity published by the handler
    when it wrote the outcome row. Without it an evaluation cannot annotate
    the real attempt; inserting an unattributed judgement would poison the
    profile evidence, so the caller gets ``None``.
    """
    if not isinstance(result, Mapping):
        return None
    if require_model_source and str(result.get("source") or "") not in (
            MODEL_SOURCES):
        return None
    routing = _routing(result)
    if _availability_error(routing):
        return None
    route = _served_route(routing)
    if route is None:
        return None
    profile_name, profile_version = _profile(routing)
    if not profile_name:
        return None
    routing_result_id = str(
        result.get("routing_result_id")
        or routing.get("routing_result_id")
        or "").strip()
    if not routing_result_id:
        return None
    return {
        "routing_result_id": routing_result_id,
        "provider": route[0],
        "model": route[1],
        "profile": profile_name,
        "profile_version": profile_version,
        "routing": routing,
    }


def classify_evidence_errors(errors: Any) -> str:
    """Map deterministic evidence-selection errors to a failure kind.

    Only the consumer's own validation/compiler errors reach here. Unknown
    wording falls back to the generic semantic failure rather than inventing a
    more specific claim.
    """
    text = " ".join(str(item) for item in (errors or [])).lower()
    if any(token in text for token in (
            "unknown source_id", "not in the retained authorized scope",
            "selected source", "source_id or action", "unknown action")):
        return EVIDENCE_SELECTION_FAILURE
    if any(token in text for token in (
            "duplicate evidence step_id", "stable step_id",
            "at most", "must choose a source read or an action",
            "proposal schema", "requirements")):
        return INVALID_PLAN_FAILURE
    return GENERIC_SEMANTIC_FAILURE


def classify_adaptation_errors(errors: Any) -> str:
    """Map deterministic adaptation validation errors to a failure kind.

    Plan/decision errors are checked before field-mapping wording: the live
    ``work_request requires decision 'replan'`` refusal is an invalid plan,
    not a column/role mapping defect.
    """
    text = " ".join(str(item) for item in (errors or [])).lower()
    if any(token in text for token in (
            "unknown step", "invalid plan", "requires observation",
            "already-consumed", "mixes", "requires decision",
            "step_id", "plan patch")):
        return INVALID_PLAN_FAILURE
    if any(token in text for token in (
            "wrong field", "field mapping", "column", "role mapping",
            "source_step_id", "unit_price", "item_id")):
        return WRONG_MAPPING_FAILURE
    return GENERIC_SEMANTIC_FAILURE


def classify_business_outcome(
    outcome: Mapping[str, Any],
) -> tuple[Optional[str], str, str]:
    """Evaluate a task outcome without inventing a judgement.

    Returns ``(evaluation, failure_kind, detail)`` where evaluation is
    ``"satisfied"``, ``"failed"`` or ``None`` (unknown/unattributable).
    ``objective_met`` is tri-state: only True/False are resolved. A False
    verdict is recorded only when the outcome's own failure diagnosis names
    the model's capability layer; configuration/delivery failures stay
    unknown for routing evidence.
    """
    if not isinstance(outcome, Mapping):
        return None, "", "no outcome"
    verdict = outcome.get("objective_met")
    if verdict is True:
        return "satisfied", "", "objective_met=true"
    if verdict is not False:
        return None, "", "objective unresolved"
    failure = outcome.get("failure")
    if not isinstance(failure, Mapping):
        return None, "", "objective failed without a capability diagnosis"
    owner = str(failure.get("owner") or "")
    layer = str(failure.get("layer") or "")
    basis = str(failure.get("basis") or "")
    if owner != "capability":
        return None, "", f"{layer}/{owner} is not a model-capability failure"
    if layer not in ("comparison", "extraction", "discovery", "execution",
                     "intent"):
        return None, "", f"{layer}/{owner} is not a model-capability failure"
    return (
        "failed",
        BUSINESS_RESULT_FAILURE,
        f"{layer}/{owner}: {basis}".strip(),
    )


async def _persist(feedback: Any) -> bool:
    """Write one feedback annotation, never raising into the consumer."""
    try:
        from core.llm.learning_router_registry import (
            get_learning_router_instance,
        )

        router = get_learning_router_instance(observe_only=True)
        if router is not None:
            await router.record_feedback(feedback)
            return True
        from core.learning_llm_router import LearningBasedRouter

        writer = LearningBasedRouter.__new__(LearningBasedRouter)
        writer._persist_feedback(feedback, {})
        return True
    except Exception as exc:  # noqa: BLE001 — evidence must not break work
        logger.debug("business routing feedback skipped: %s", exc)
        return False


async def record_attempt_evaluation(
    result: Mapping[str, Any],
    *,
    stage: str,
    evaluation: str,
    failure_kind: str = "",
    detail: str = "",
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    extra_features: Optional[Mapping[str, Any]] = None,
    require_model_source: bool = False,
) -> Optional[Dict[str, Any]]:
    """Annotate the served attempt's outcome row with a business verdict.

    ``evaluation`` is ``"satisfied"`` or ``"failed"``. A rejection of an
    invalid model proposal is a ``"failed"`` evaluation even when the consumer
    then used a deterministic fallback: the model output is the thing judged,
    and the fallback is never credited. A satisfied business result requires a
    model-owned source (``require_model_source=True``) so deterministic work
    cannot become model success.
    """
    if evaluation not in ("satisfied", "failed"):
        return None
    context = attempt_context(
        result, require_model_source=require_model_source)
    if context is None:
        return None
    from core.llm.fabrication_accounting import (
        BUSINESS_SATISFIED_VERDICT,
        BUSINESS_VERDICT_RULE,
    )
    from core.learning_llm_router import RoutingFeedback

    satisfied = evaluation == "satisfied"
    verdict = BUSINESS_SATISFIED_VERDICT if satisfied else (
        failure_kind or GENERIC_SEMANTIC_FAILURE)
    features: Dict[str, Any] = {
        "business_outcome": evaluation,
        "business_stage": str(stage or "")[:80],
        "business_rule": BUSINESS_VERDICT_RULE,
    }
    if detail:
        features["business_detail"] = str(detail)[:500]
    for key, value in (extra_features or {}).items():
        features[str(key)] = value
    feedback = RoutingFeedback(
        routing_result_id=context["routing_result_id"],
        tenant_id=str(tenant_id or "default"),
        model_id=context["model"],
        # Match the transport outcome row's adapted vocabulary ("planning"
        # maps to "general" in ``_adapt_task_type``); profile scoping lives in
        # the capability/profile features, not this bucket key.
        task_type="general",
        success=satisfied,
        quality_satisfied=satisfied,
        cost_within_budget=True,
        user_satisfaction=0.9 if satisfied else 0.15,
        actual_cost=None,
        actual_latency_ms=None,
        provider_id=context["provider"],
        verdict=verdict,
        verdict_rule=BUSINESS_VERDICT_RULE,
        capability_profile=context["profile"],
        capability_profile_version=context["profile_version"],
        workspace_id=str(workspace_id or ""),
        failure_kind="" if satisfied else (
            failure_kind or GENERIC_SEMANTIC_FAILURE),
        evidence_features=features,
    )
    if not await _persist(feedback):
        return None
    return {
        "recorded": True,
        "evaluation": evaluation,
        "failure_kind": feedback.failure_kind,
        "profile": context["profile"],
        "profile_version": context["profile_version"],
        "provider": context["provider"],
        "model": context["model"],
        "routing_result_id": context["routing_result_id"],
    }


async def record_business_outcome(
    result: Mapping[str, Any],
    *,
    stage: str,
    outcome: Mapping[str, Any],
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    extra_features: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Record an explicit task outcome against the model attempt that produced it."""
    evaluation, failure_kind, detail = classify_business_outcome(outcome)
    if evaluation is None:
        return None
    return await record_attempt_evaluation(
        result,
        stage=stage,
        evaluation=evaluation,
        failure_kind=failure_kind,
        detail=detail,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        extra_features=extra_features,
        require_model_source=True,
    )
