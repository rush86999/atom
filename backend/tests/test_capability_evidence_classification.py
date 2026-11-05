"""Capability-evidence classification for pending vs resolved business work.

Grounding is evidence support, not a useful business decision. An unresolved
wait must not earn a capability-success sample merely because grounding_ok or
grounding_passed landed on the same generation. Real negative judgements stay
observable, and legacy rows without a business-outcome marker keep their
established compatibility semantics.
"""
from __future__ import annotations

import asyncio

import pytest

from core.llm.capability_profiles import (
    get_profile,
    load_feedback_evidence,
    reset_capability_evidence_cache,
)
from core.llm.fabrication_accounting import account_generations
from tests.test_employee_business_feedback import (  # noqa: F401
    feedback_db,
    fresh_router,
    _insert_outcome_row,
    _row_by_id,
    _synthetic_result,
)

PROFILE = "employee_wait_choice"
ROUTE = "local_ctrl1234/llama3.1:8b"


def _legacy_verdict(generation, verdict, *, quality=True, satisfaction=0.9):
    from core.learning_llm_router import (
        LearningBasedRouter,
        RoutingFeedback,
    )

    writer = LearningBasedRouter.__new__(LearningBasedRouter)
    return writer._persist_feedback(
        RoutingFeedback(
            routing_result_id=generation,
            tenant_id="tenant-ctrl",
            model_id="llama3.1:8b",
            task_type="general",
            success=True,
            quality_satisfied=quality,
            cost_within_budget=True,
            user_satisfaction=satisfaction,
        ),
        {"verdict": verdict})


def _pending(feedback_db, generation):
    from core.employee_routing_feedback import record_business_outcome

    row_id = _insert_outcome_row(
        feedback_db, generation, profile=PROFILE)
    result = _synthetic_result(generation, profile=PROFILE)
    result["source"] = "model_wait_choice"
    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice",
        outcome={"objective_met": None},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["status"] == "annotated", recorded
    return row_id, result


def _evidence():
    reset_capability_evidence_cache()
    return load_feedback_evidence(
        get_profile(PROFILE), workspace_id="ws-ctrl",
        tenant_id="tenant-ctrl")


def _route(evidence):
    return evidence.get(ROUTE, {})


def _accounting(feedback_db, row_id):
    return account_generations([_row_by_id(feedback_db, row_id)]).as_dict()


@pytest.mark.parametrize("verdict", ["grounding_ok", "grounding_passed"])
def test_pending_plus_grounding_is_unknown_not_success(
        feedback_db, fresh_router, verdict):
    generation = f"pending-{verdict}"
    row_id, _ = _pending(feedback_db, generation)
    assert _legacy_verdict(generation, verdict) == "annotated"

    row = _row_by_id(feedback_db, row_id)
    features = row.prompt_features or {}
    assert features["business_outcome"] == "unresolved"
    assert features["verdict"] == verdict
    assert features["evaluation_revision"] >= 1

    route = _route(_evidence())
    assert route.get("samples", 0) == 0, route
    assert route.get("successes", 0) == 0, route
    assert route.get("quality_successes", 0) == 0, route

    accounting = _accounting(feedback_db, row_id)
    assert accounting["grounded_ok"] == 1, accounting
    assert accounting["fabricated"] == 0, accounting


def test_pending_plus_fabrication_remains_observable(
        feedback_db, fresh_router):
    generation = "pending-fabrication"
    row_id, _ = _pending(feedback_db, generation)
    assert _legacy_verdict(
        generation, "unsupported_figures",
        quality=False, satisfaction=0.1) == "annotated"

    route = _route(_evidence())
    assert route.get("samples", 0) == 1, route
    assert route.get("successes", 0) == 0, route

    accounting = _accounting(feedback_db, row_id)
    assert accounting["fabricated"] == 1, accounting
    assert accounting["grounded_ok"] == 0, accounting


def test_pending_plus_business_failure_remains_observable(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_attempt_evaluation

    generation = "pending-business-failure"
    row_id, result = _pending(feedback_db, generation)
    recorded = asyncio.run(record_attempt_evaluation(
        result, stage="employee_wait_choice",
        evaluation="failed", failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["status"] == "annotated", recorded

    route = _route(_evidence())
    assert route.get("samples", 0) == 1, route
    assert route.get("successes", 0) == 0, route
    assert route.get("semantic_failures", 0) == 1, route


def test_validated_wait_decision_is_a_scoped_success(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_business_outcome

    generation = "validated-wait-decision"
    row_id = _insert_outcome_row(
        feedback_db, generation, profile=PROFILE)
    result = _synthetic_result(generation, profile=PROFILE)
    result.update({
        "source": "model_wait_choice",
        "business_decision_validated": True,
        "business_decision": "wait",
    })
    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice",
        outcome={"objective_met": None},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["status"] == "annotated", recorded

    route = _route(_evidence())
    assert route.get("samples", 0) == 1, route
    assert route.get("successes", 0) == 1, route
    row = _row_by_id(feedback_db, row_id)
    assert (row.prompt_features or {})["business_outcome_scope"] == "decision"


def test_satisfied_business_result_is_a_success(feedback_db, fresh_router):
    from core.employee_routing_feedback import record_business_outcome

    generation = "satisfied-business-result"
    row_id = _insert_outcome_row(
        feedback_db, generation, profile=PROFILE)
    result = _synthetic_result(generation, profile=PROFILE)
    result["source"] = "model_wait_choice"
    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice",
        outcome={"objective_met": True},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["status"] == "annotated", recorded

    route = _route(_evidence())
    assert route.get("samples", 0) == 1, route
    assert route.get("successes", 0) == 1, route
    row = _row_by_id(feedback_db, row_id)
    assert (row.prompt_features or {})["business_outcome_scope"] == "result"


def test_legacy_row_without_business_marker_keeps_compatibility(
        feedback_db, fresh_router):
    generation = "legacy-grounding-no-business-marker"
    row_id = _insert_outcome_row(
        feedback_db, generation, profile=PROFILE)
    assert _legacy_verdict(generation, "grounding_ok") == "annotated"

    row = _row_by_id(feedback_db, row_id)
    assert "business_outcome" not in (row.prompt_features or {})
    route = _route(_evidence())
    assert route.get("samples", 0) == 1, route
    assert route.get("successes", 0) == 1, route
    accounting = _accounting(feedback_db, row_id)
    assert accounting["grounded_ok"] == 1, accounting
