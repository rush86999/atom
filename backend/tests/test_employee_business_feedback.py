"""End-to-end business feedback: evaluated work changes the next route.

These controls use the REAL employee consumer, ``LLMService`` and
``BYOKHandler`` with a scratch SQLite feedback table. Only the provider
transport is doubled. The sequence is the verifier's requested one:

  consumer evaluates a model proposal as business-invalid
  -> the generation's feedback row is annotated with a failure_kind
  -> a fresh routing decision reads that scoped evidence
  -> the failed route is excluded and one eligible alternative is served.

The tests also pin the boundaries: a deterministic fallback is never credited
as model success, and wrong workspace/tenant/profile-version evidence stays
isolated (missing quality remains unknown).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import pytest

from core.employee_proposal import (
    EmployeeWorkProposal,
    build_employee_context,
    propose_employee_work,
)
from core.llm.capability_profiles import (
    get_profile,
    load_feedback_evidence,
    reset_capability_evidence_cache,
    select_profile_candidates,
)
from core.llm_service import LLMService


@pytest.fixture()
def feedback_db(tmp_path, monkeypatch):
    """Scratch SQLite with the full model metadata, isolated per test."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database as database
    from core.database import Base

    db_path = tmp_path / "business-feedback.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    reset_capability_evidence_cache()
    yield {"engine": engine, "Session": Session, "path": db_path}
    reset_capability_evidence_cache()
    engine.dispose()


@pytest.fixture()
def fresh_router(feedback_db, monkeypatch):
    """A real LearningBasedRouter writing to the scratch DB."""
    from core.learning_llm_router import LearningBasedRouter
    from core.llm import learning_router_registry as registry

    router = object.__new__(LearningBasedRouter)
    LearningBasedRouter.__init__(router, feedback_db["Session"]())
    monkeypatch.setattr(
        registry, "get_learning_router_instance",
        lambda *args, **kwargs: router)
    return router


def _handler(workspace_id="ws-ctrl", tenant_id="tenant-ctrl"):
    from tests.test_structured_dispatch_policy import _handler as factory

    return factory(workspace_id, tenant_id)


def _service(handler):
    service = LLMService.__new__(LLMService)
    service._get_handler = lambda **_kw: handler
    service.continuous_learning = None
    service._workspace_id = "ws-ctrl"
    service._tenant_id = "tenant-ctrl"
    return service


def _service_for(handler, workspace_id, tenant_id):
    service = _service(handler)
    service._workspace_id = workspace_id
    service._tenant_id = tenant_id
    return service


def _configure_pool(handler, monkeypatch):
    """Two capable local routes: cheap first, costlier alternative."""
    from core.dynamic_pricing_fetcher import get_pricing_fetcher
    from tests.test_structured_dispatch_policy import _seed_pool

    _seed_pool(handler, monkeypatch, with_local=True)
    fetcher = get_pricing_fetcher()
    fetcher.pricing_cache["llama3.1:8b"].update({
        "input_cost_per_token": 1e-7,
        "output_cost_per_token": 1e-7,
        "supports_structured": True,
    })
    fetcher.pricing_cache["pricey-model"] = {
        "litellm_provider": "pricey",
        "input_cost_per_token": 2e-6,
        "output_cost_per_token": 2e-6,
        "max_input_tokens": 131072,
        "supports_tools": True,
        "supports_structured": True,
    }
    handler.clients["local_pricey"] = MagicMock(name="pricey-client")
    handler._local_routes["pricey-model"] = {
        "provider_key": "local_pricey",
        "workspace_id": handler.workspace_id,
        "provider_id": "local_pricey",
        "provider_type": "ollama",
        "supports_tools": True,
        "supports_structured": True,
        "supports_vision": False,
        "supports_reasoning": False,
        "quality_score": 0.9,
        "context_window": 131072,
    }

    def _effective_cost(model, provider, estimated_tokens,
                        turn_index=0, **_kw):
        entry = fetcher.pricing_cache.get(model) or {}
        return float(
            entry.get("input_cost_per_token") or 0.0) * estimated_tokens

    handler.cache_router.calculate_effective_cost = MagicMock(
        side_effect=_effective_cost)
    handler._claim_model_attempt = lambda *a, **k: "test-token"
    handler._release_model_attempt = lambda *a, **k: True


def _context():
    return build_employee_context(
        objective="Read the authorized evidence",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl",
        sources=[{
            "kind": "document", "representation": "document_text",
            "resource_id": "doc-1", "file_name": "note.txt",
        }],
        stage="discovery")


def _valid_proposal():
    return EmployeeWorkProposal(
        proposal_kind="evidence_read",
        reason="read the authorized note",
        evidence_reads=[{
            "step_id": "evidence-1", "title": "Read note",
            "source_id": "doc-1",
        }])


def _invalid_proposal():
    """Schema-valid, but names a source outside the authorized scope."""
    return EmployeeWorkProposal(
        proposal_kind="evidence_read",
        reason="select a source",
        evidence_reads=[{
            "step_id": "evidence-1", "title": "Read note",
            "source_id": "not-authorized-doc",
        }])


def _route_aware_instructor(selected, *, invalid_client, valid_proposal):
    def _from_openai(client, **_kwargs):
        selected.append(client)

        def create(**_kwargs):
            if client is invalid_client:
                return _invalid_proposal()
            return valid_proposal

        return NS(chat=NS(completions=NS(create=create)))

    return _from_openai


def _rows(db):
    from core.models import LLMRoutingFeedback

    with db["Session"]() as session:
        return (
            session.query(LLMRoutingFeedback)
            .order_by(LLMRoutingFeedback.created_at.asc())
            .all()
        )


def _row_by_id(db, row_id):
    from core.models import LLMRoutingFeedback

    with db["Session"]() as session:
        return session.query(LLMRoutingFeedback).filter(
            LLMRoutingFeedback.id == row_id).first()


def _insert_outcome_row(
    db, generation, *, provider="local_ctrl1234",
    model="llama3.1:8b", workspace="ws-ctrl", tenant="tenant-ctrl",
    profile="employee_evidence_selection", version="2026-11-04.1",
    success=True, cost=0.0123, latency=45.6,
):
    """Insert the transport-shaped outcome row a business write must bind to."""
    from core.models import LLMRoutingFeedback

    with db["Session"]() as session:
        row = LLMRoutingFeedback(
            routing_result_id=generation,
            tenant_id=tenant,
            task_type="general",
            model_id=model,
            success=success,
            quality_satisfied=success,
            cost_within_budget=True,
            user_satisfaction=0.8 if success else 0.15,
            actual_cost=cost,
            actual_latency_ms=latency,
            prompt_features={
                "route_provider": provider,
                "capability_profile": profile,
                "profile_version": version,
                "workspace_id": workspace,
            },
        )
        session.add(row)
        session.commit()
        return row.id


def _synthetic_result(
    generation, *, provider="local_ctrl1234", model="llama3.1:8b",
    profile="employee_evidence_selection", version="2026-11-04.1",
):
    return {
        "source": "model",
        "routing_result_id": generation,
        "routing": {
            "mode": "unpinned",
            "served_route": {"provider": provider, "model": model},
            "profile": {"name": profile, "version": version},
            "routing_result_id": generation,
            "error": None,
        },
    }


_FAILED_OUTCOME = {
    "objective_met": False,
    "failure": {
        "owner": "capability",
        "layer": "discovery",
        "basis": "controlled business failure",
    },
}


def _run_context_floor_scenario():
    """Run the independent routing control with its own fresh patches."""
    from tests.test_workload_capability_routing import (
        test_actual_request_size_beats_the_coarse_complexity_context_floor,
    )

    mp = pytest.MonkeyPatch()
    try:
        test_actual_request_size_beats_the_coarse_complexity_context_floor(mp)
    finally:
        mp.undo()


def test_context_floor_before_feedback_tests():
    """Baseline: the routing control passes before this file's fixtures run."""
    _run_context_floor_scenario()


def test_evaluated_bad_work_persists_and_changes_next_routing_decision(
        feedback_db, fresh_router, monkeypatch):
    handler = _handler()
    _configure_pool(handler, monkeypatch)
    service = _service(handler)
    context = _context()
    invalid_client = handler.clients["local_ctrl1234"]

    # Three served generations whose proposals the consumer rejects with its
    # deterministic contract. Each is a real model attempt, not a transport
    # failure, and each must annotate its own outcome row.
    for round_index in range(3):
        selected = []
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _route_aware_instructor(
                    selected, invalid_client=invalid_client,
                    valid_proposal=_valid_proposal())):
            result = asyncio.run(propose_employee_work(
                context, llm_service=service))
        assert result["source"] == "deterministic", result
        assert result["routing"]["served_route"] == {
            "provider": "local_ctrl1234", "model": "llama3.1:8b"}
        evaluation = result.get("evaluation") or {}
        assert evaluation.get("recorded") is True, evaluation
        assert evaluation.get("failure_kind") == "wrong_evidence_selection"
        assert evaluation.get("profile") == "employee_evidence_selection"
        assert selected and selected[0] is invalid_client

    rows = _rows(feedback_db)
    assert len(rows) == 3, [
        (row.model_id, row.prompt_features) for row in rows]
    for row in rows:
        features = row.prompt_features or {}
        assert row.model_id == "llama3.1:8b"
        assert row.success is False
        assert row.quality_satisfied is False
        assert features["route_provider"] == "local_ctrl1234"
        assert features["capability_profile"] == "employee_evidence_selection"
        assert features["profile_version"] == "2026-11-04.1"
        assert features["workspace_id"] == "ws-ctrl"
        assert features["failure_kind"] == "wrong_evidence_selection"
        assert features["business_outcome"] == "failed"
        assert features["business_stage"] == "employee_evidence_selection"

    # A fresh routing decision reads the persisted evidence. The cheap route
    # is now excluded; the costlier capable route is the one eligible choice.
    reset_capability_evidence_cache()
    selected = []
    with patch(
            "core.llm.byok_handler.instructor.from_openai",
            _route_aware_instructor(
                selected, invalid_client=invalid_client,
                valid_proposal=_valid_proposal())):
        result = asyncio.run(propose_employee_work(
            context, llm_service=service))
    assert result["source"] == "model", result
    assert result["routing"]["served_route"] == {
        "provider": "local_pricey", "model": "pricey-model"}
    assert selected and all(
        client is handler.clients["local_pricey"] for client in selected)
    # Same-route repair/retry is bounded; the excluded cheap route is never
    # re-dispatched and there is no multi-route sweep.
    assert 1 <= len(selected) <= 2


def test_evaluated_business_failure_changes_next_routing_decision(
        feedback_db, fresh_router, monkeypatch):
    """The business-result path (objective_met=False) also steers routing.

    This is the post-execution shape: the model produced a valid proposal, the
    consumer adopted and ran it, and the task outcome's own failure diagnosis
    says the capability layer failed. The route must lose the next decision.
    """
    from core.employee_routing_feedback import record_business_outcome

    handler = _handler()
    _configure_pool(handler, monkeypatch)
    service = _service(handler)
    context = _context()
    invalid_client = handler.clients["local_ctrl1234"]
    failed_outcome = {
        "objective_met": False,
        "failure": {
            "owner": "capability",
            "layer": "discovery",
            "basis": "controlled_business_failure",
        },
    }
    for _ in range(3):
        selected = []
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _route_aware_instructor(
                    selected, invalid_client=None,
                    valid_proposal=_valid_proposal())):
            result = asyncio.run(propose_employee_work(
                context, llm_service=service))
        assert result["source"] == "model", result
        assert result["routing"]["served_route"] == {
            "provider": "local_ctrl1234", "model": "llama3.1:8b"}
        recorded = asyncio.run(record_business_outcome(
            result, stage="employee_adaptation",
            outcome=failed_outcome,
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
        assert recorded and recorded["evaluation"] == "failed"
        assert recorded["failure_kind"] == "unsatisfactory_business_result"

    rows = _rows(feedback_db)
    assert len(rows) == 3
    for row in rows:
        features = row.prompt_features or {}
        assert row.success is False
        assert row.quality_satisfied is False
        assert features["failure_kind"] == "unsatisfactory_business_result"
        assert features["business_outcome"] == "failed"

    reset_capability_evidence_cache()
    selected = []
    with patch(
            "core.llm.byok_handler.instructor.from_openai",
            _route_aware_instructor(
                selected, invalid_client=invalid_client,
                valid_proposal=_valid_proposal())):
        result = asyncio.run(propose_employee_work(
            context, llm_service=service))
    assert result["source"] == "model", result
    assert result["routing"]["served_route"] == {
        "provider": "local_pricey", "model": "pricey-model"}
    assert selected and all(
        client is handler.clients["local_pricey"] for client in selected)


def test_strict_qualification_pin_fails_instead_of_escaping(
        feedback_db, fresh_router, monkeypatch):
    """An exact pin is not silently replaced by the healthy alternative."""
    from core.llm.capability_profiles import (
        capability_decisions,
        reset_capability_journal_memory,
    )

    handler = _handler()
    _configure_pool(handler, monkeypatch)
    service = _service(handler)
    context = _context()
    invalid_client = handler.clients["local_ctrl1234"]
    for _ in range(3):
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _route_aware_instructor(
                    [], invalid_client=invalid_client,
                    valid_proposal=_valid_proposal())):
            asyncio.run(propose_employee_work(
                context, llm_service=service))

    reset_capability_evidence_cache()
    reset_capability_journal_memory()
    result = asyncio.run(service.generate_structured_response(
        prompt="Return a bounded employee proposal.",
        response_model=EmployeeWorkProposal,
        capability_profile="employee_evidence_selection",
        task_type="planning",
        provider_model=("local_ctrl1234", "llama3.1:8b"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl",
        max_tokens=1800,
    ))
    assert result is None, "the strict pin must fail, not escape"
    pins = [
        item for item in capability_decisions(
            limit=50, workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
        if item.get("event") == "pin"
        and item.get("route") == ["local_ctrl1234", "llama3.1:8b"]
    ]
    assert pins and pins[-1]["eligible"] is False
    assert "measured_failure_rate" in (
        pins[-1].get("reasons") or [])


def test_business_evidence_is_scoped_by_workspace_tenant_and_profile_version(
        feedback_db, fresh_router, monkeypatch):
    handler = _handler()
    _configure_pool(handler, monkeypatch)
    service = _service(handler)
    context = _context()
    invalid_client = handler.clients["local_ctrl1234"]
    for _ in range(3):
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _route_aware_instructor(
                    [], invalid_client=invalid_client,
                    valid_proposal=_valid_proposal())):
            asyncio.run(propose_employee_work(
                context, llm_service=service))

    profile = get_profile("employee_evidence_selection")
    reset_capability_evidence_cache()
    same_scope = load_feedback_evidence(
        profile, workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    assert same_scope["local_ctrl1234/llama3.1:8b"]["samples"] == 3
    assert same_scope["local_ctrl1234/llama3.1:8b"][
        "semantic_failures"] == 3

    reset_capability_evidence_cache()
    other_workspace = load_feedback_evidence(
        profile, workspace_id="ws-other", tenant_id="tenant-ctrl")
    assert "local_ctrl1234/llama3.1:8b" not in other_workspace

    reset_capability_evidence_cache()
    other_tenant = load_feedback_evidence(
        profile, workspace_id="ws-ctrl", tenant_id="tenant-other")
    assert "local_ctrl1234/llama3.1:8b" not in other_tenant

    # A different profile VERSION is a different contract: the old failure
    # must not poison the new qualification.
    from dataclasses import replace

    old_profile = replace(profile, version="2026-11-03.9")
    reset_capability_evidence_cache()
    old_version = load_feedback_evidence(
        old_profile, workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    assert "local_ctrl1234/llama3.1:8b" not in old_version

    # Missing quality is unknown, not failure: with the wrong-scope evidence
    # only, the cheap route remains eligible beside the costlier one.
    candidates = [
        {"provider": "local_ctrl1234", "model": "llama3.1:8b",
         "quality": 90, "cost": 1.0, "context_window": 32768,
         "supports_structured": True},
        {"provider": "local_pricey", "model": "pricey-model",
         "quality": 90, "cost": 2.0, "context_window": 32768,
         "supports_structured": True},
    ]
    selection = select_profile_candidates(
        profile, candidates, evidence=other_workspace)
    assert selection["outcome"] == "selected"
    assert [item["model"] for item in selection["ranked"]] == [
        "llama3.1:8b", "pricey-model"]


def test_satisfied_business_outcome_annotates_the_same_generation(
        feedback_db, fresh_router, monkeypatch):
    from core.employee_routing_feedback import record_business_outcome

    handler = _handler()
    _configure_pool(handler, monkeypatch)
    service = _service(handler)
    selected = []
    with patch(
            "core.llm.byok_handler.instructor.from_openai",
            _route_aware_instructor(
                selected, invalid_client=None,
                valid_proposal=_valid_proposal())):
        result = asyncio.run(propose_employee_work(
            _context(), llm_service=service))
    assert result["source"] == "model", result
    assert len(_rows(feedback_db)) == 1

    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_evidence_selection",
        outcome={"objective_met": True},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded and recorded["evaluation"] == "satisfied"
    rows = _rows(feedback_db)
    assert len(rows) == 1, "the evaluation annotates, never duplicates"
    features = rows[0].prompt_features or {}
    assert rows[0].success is True
    assert rows[0].quality_satisfied is True
    assert features["business_outcome"] == "satisfied"
    assert features["failure_kind"] == ""
    assert features["verdict"] == "business_satisfied"
    assert features["verdict_rule"] == "business_outcome_v1"


def test_compact_evaluation_stays_in_the_compact_profile(
        feedback_db, fresh_router):
    """A compact reconciliation is never an evidence-selection sample."""
    from core.employee_routing_feedback import record_attempt_evaluation
    from core.models import LLMRoutingFeedback

    with feedback_db["Session"]() as session:
        session.add(LLMRoutingFeedback(
            routing_result_id="compact-generation-1",
            tenant_id="tenant-ctrl",
            task_type="general",
            model_id="llama3.1:8b",
            success=True,
            quality_satisfied=True,
            cost_within_budget=True,
            user_satisfaction=0.8,
            actual_cost=0.0,
            actual_latency_ms=12.0,
            prompt_features={
                "route_provider": "local_ctrl1234",
                "capability_profile": "employee_adaptive_planning_compact",
                "profile_version": "2026-11-04.1",
                "workspace_id": "ws-ctrl",
            },
        ))
        session.commit()

    result = {
        "source": "model_compact",
        "routing_result_id": "compact-generation-1",
        "routing": {
            "mode": "unpinned",
            "served_route": {
                "provider": "local_ctrl1234", "model": "llama3.1:8b"},
            "profile": {
                "name": "employee_adaptive_planning_compact",
                "version": "2026-11-04.1",
            },
            "error": None,
        },
    }
    recorded = asyncio.run(record_attempt_evaluation(
        result, stage="employee_adaptation_compact",
        evaluation="satisfied",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded and recorded["profile"] == (
        "employee_adaptive_planning_compact")
    rows = _rows(feedback_db)
    assert len(rows) == 1
    features = rows[0].prompt_features or {}
    assert features["capability_profile"] == (
        "employee_adaptive_planning_compact")
    assert features["business_stage"] == "employee_adaptation_compact"
    assert features["capability_profile"] != "employee_evidence_selection"
    assert features["business_outcome"] == "satisfied"


def test_wait_choice_origin_needs_an_explicit_verdict_and_is_never_auto_success(
        feedback_db, fresh_router):
    """A parsed wait is a model origin, not a business verdict."""
    from core.employee_routing_feedback import record_business_outcome

    generation = "wait-choice-generation-1"
    row_id = _insert_outcome_row(
        feedback_db, generation, profile="employee_wait_choice")
    result = _synthetic_result(
        generation, profile="employee_wait_choice")
    result["source"] = "model_wait_choice"

    # Parsing the model's wait/adoption proposal is not a business success:
    # the attempt is explicitly annotated "unresolved" and excluded from
    # capability evidence. Its transport success flag is not a verdict.
    unevaluated = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice", outcome={},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert unevaluated and unevaluated["recorded"] is True, unevaluated
    assert unevaluated["evaluation"] == "unresolved"
    assert unevaluated["profile"] == "employee_wait_choice"
    pending = _row_by_id(feedback_db, row_id)
    assert pending.success is True
    assert (pending.prompt_features or {})["business_outcome"] == (
        "unresolved")

    evaluated = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice", outcome=_FAILED_OUTCOME,
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert evaluated and evaluated["recorded"] is True, evaluated
    assert evaluated["profile"] == "employee_wait_choice"
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    assert row.quality_satisfied is False
    features = row.prompt_features or {}
    assert features["business_outcome"] == "failed"
    assert features["business_stage"] == "employee_wait_choice"
    assert features["failure_kind"] == "unsatisfactory_business_result"


def test_deterministic_fallback_is_never_credited_as_model_success(
        feedback_db, fresh_router, monkeypatch):
    from core.employee_routing_feedback import record_business_outcome

    handler = _handler()
    _configure_pool(handler, monkeypatch)
    service = _service(handler)
    invalid_client = handler.clients["local_ctrl1234"]
    with patch(
            "core.llm.byok_handler.instructor.from_openai",
            _route_aware_instructor(
                [], invalid_client=invalid_client,
                valid_proposal=_valid_proposal())):
        result = asyncio.run(propose_employee_work(
            _context(), llm_service=service))
    assert result["source"] == "deterministic"
    before = _rows(feedback_db)
    assert len(before) == 1
    assert before[0].success is False

    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_evidence_selection",
        outcome={"objective_met": True},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded is None
    after = _rows(feedback_db)
    assert len(after) == 1
    assert after[0].success is False
    assert (after[0].prompt_features or {})["business_outcome"] == "failed"


def test_business_write_binding_refuses_wrong_or_missing_receipt_fields(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_attempt_evaluation

    cases = [
        ("wrong_workspace", {"workspace_id": "ws-other"},
         "refused_workspace"),
        ("wrong_tenant", {"tenant_id": "tenant-other"},
         "refused_tenant"),
        ("wrong_provider", {"provider": "other-provider"},
         "refused_provider"),
        ("wrong_model", {"model": "other-model"}, "refused_model"),
        ("wrong_profile", {"profile": "other_profile"},
         "refused_profile"),
        ("wrong_version", {"version": "2026-11-03.9"},
         "refused_profile_version"),
        ("missing_workspace", {"workspace_id": ""},
         "refused_missing_scope"),
        ("missing_tenant", {"tenant_id": ""}, "refused_missing_scope"),
    ]
    for name, overrides, expected_status in cases:
        generation = f"binding-{name}"
        row_id = _insert_outcome_row(feedback_db, generation)
        result = _synthetic_result(
            generation,
            provider=overrides.get("provider", "local_ctrl1234"),
            model=overrides.get("model", "llama3.1:8b"),
            profile=overrides.get("profile", "employee_evidence_selection"),
            version=overrides.get("version", "2026-11-04.1"))
        recorded = asyncio.run(record_attempt_evaluation(
            result, stage="employee_evidence_selection",
            evaluation="failed",
            failure_kind="wrong_evidence_selection",
            workspace_id=overrides.get("workspace_id", "ws-ctrl"),
            tenant_id=overrides.get("tenant_id", "tenant-ctrl")))
        assert recorded["recorded"] is False, (name, recorded)
        assert recorded["status"] == expected_status, (name, recorded)
        # A fresh session sees the original success row unchanged.
        row = _row_by_id(feedback_db, row_id)
        assert row.success is True, name
        assert row.quality_satisfied is True, name
        assert (row.prompt_features or {}).get("business_outcome") is None


def test_business_write_binding_annotates_exactly_the_receipt(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_business_outcome

    generation = "binding-correct"
    row_id = _insert_outcome_row(feedback_db, generation)
    recorded = asyncio.run(record_business_outcome(
        _synthetic_result(generation),
        stage="employee_evidence_selection",
        outcome=_FAILED_OUTCOME,
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["recorded"] is True
    assert recorded["status"] == "annotated"
    rows = _rows(feedback_db)
    assert len(rows) == 1
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    assert row.quality_satisfied is False
    # Cost/latency are transport facts and must survive the annotation.
    assert row.actual_cost == 0.0123
    assert row.actual_latency_ms == 45.6
    features = row.prompt_features or {}
    assert features["failure_kind"] == "unsatisfactory_business_result"
    assert features["business_outcome"] == "failed"
    assert features["route_provider"] == "local_ctrl1234"


def test_business_write_binding_refuses_unknown_generation(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_attempt_evaluation

    before = len(_rows(feedback_db))
    recorded = asyncio.run(record_attempt_evaluation(
        _synthetic_result("generation-does-not-exist"),
        stage="employee_evidence_selection",
        evaluation="failed",
        failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["recorded"] is False
    assert recorded["status"] == "skipped_missing_generation"
    assert len(_rows(feedback_db)) == before, "no orphan business row"


def test_business_write_binding_selects_the_exact_provider_for_same_model(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_attempt_evaluation

    generation = "binding-same-model-two-providers"
    row_a = _insert_outcome_row(
        feedback_db, generation, provider="provider-a")
    row_b = _insert_outcome_row(
        feedback_db, generation, provider="provider-b")
    recorded = asyncio.run(record_attempt_evaluation(
        _synthetic_result(generation, provider="provider-b"),
        stage="employee_evidence_selection",
        evaluation="failed",
        failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["recorded"] is True
    assert _row_by_id(feedback_db, row_a).success is True
    assert _row_by_id(feedback_db, row_b).success is False


def test_business_write_binding_duplicate_is_idempotent(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_attempt_evaluation

    generation = "binding-duplicate"
    row_id = _insert_outcome_row(feedback_db, generation)
    result = _synthetic_result(generation)
    first = asyncio.run(record_attempt_evaluation(
        result, stage="employee_evidence_selection",
        evaluation="failed", failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    second = asyncio.run(record_attempt_evaluation(
        result, stage="employee_evidence_selection",
        evaluation="failed", failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert first["recorded"] is True
    assert second["recorded"] is False
    assert second["status"] == "skipped_verdict"
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    assert (row.prompt_features or {})["failure_kind"] == (
        "wrong_evidence_selection")


def test_business_write_binding_stronger_concurrent_evaluation_wins(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_attempt_evaluation

    generation = "binding-concurrent"
    row_id = _insert_outcome_row(feedback_db, generation)
    result = _synthetic_result(generation)

    async def _both():
        weak = record_attempt_evaluation(
            result, stage="employee_evidence_selection",
            evaluation="satisfied",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
        strong = record_attempt_evaluation(
            result, stage="employee_evidence_selection",
            evaluation="failed", failure_kind="wrong_evidence_selection",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
        return await asyncio.gather(weak, strong)

    asyncio.run(_both())
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    features = row.prompt_features or {}
    assert features["failure_kind"] == "wrong_evidence_selection"
    assert features["verdict"] == "wrong_evidence_selection"


def test_parsed_wait_choice_is_pending_not_business_success(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_business_outcome

    generation = "wait-pending"
    row_id = _insert_outcome_row(
        feedback_db, generation, profile="employee_wait_choice")
    result = _synthetic_result(
        generation, profile="employee_wait_choice")
    result["source"] = "model_wait_choice"
    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice",
        outcome={"objective_met": None},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["recorded"] is True
    row = _row_by_id(feedback_db, row_id)
    # Transport success stays; the business decision is explicitly pending.
    assert row.success is True
    assert row.quality_satisfied is True
    features = row.prompt_features or {}
    assert features["business_outcome"] == "unresolved"
    assert "business_satisfied" not in str(features.get("verdict"))
    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_wait_choice"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    assert "local_ctrl1234/llama3.1:8b" not in evidence, (
        "a parsed wait must not count as a satisfactory sample")


def test_validated_wait_choice_is_a_scoped_positive_decision(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import record_business_outcome

    generation = "wait-validated"
    row_id = _insert_outcome_row(
        feedback_db, generation, profile="employee_wait_choice")
    result = _synthetic_result(
        generation, profile="employee_wait_choice")
    result.update({
        "source": "model_wait_choice",
        "business_decision_validated": True,
        "business_decision": "wait",
    })
    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice",
        outcome={"objective_met": None},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["recorded"] is True
    row = _row_by_id(feedback_db, row_id)
    features = row.prompt_features or {}
    assert features["business_outcome"] == "satisfied"
    assert features["business_decision"] == "wait"
    assert features["business_outcome_scope"] == "decision"
    assert features["failure_kind"] == ""
    assert features["verdict"] == "business_satisfied"
    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_wait_choice"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    route = evidence["local_ctrl1234/llama3.1:8b"]
    assert route["samples"] == 1
    assert route["successes"] == 1


def test_rejected_wait_choice_is_semantic_failure_not_fallback_credit(
        feedback_db, fresh_router):
    from core.employee_routing_feedback import (
        classify_adaptation_errors,
        record_attempt_evaluation,
    )

    generation = "wait-rejected"
    row_id = _insert_outcome_row(
        feedback_db, generation, profile="employee_wait_choice")
    result = _synthetic_result(
        generation, profile="employee_wait_choice")
    result["source"] = "deterministic"
    errors = [
        "unnecessary wait: the current record is already available "
        "in the accepted pool"]
    recorded = asyncio.run(record_attempt_evaluation(
        result, stage="employee_wait_choice",
        evaluation="failed",
        failure_kind=classify_adaptation_errors(errors),
        detail="; ".join(errors),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    assert recorded["recorded"] is True
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    features = row.prompt_features or {}
    assert features["failure_kind"] == "invalid_plan_reference"
    assert features["business_outcome"] == "failed"
    assert features["business_stage"] == "employee_wait_choice"


def test_business_verdicts_do_not_enter_the_fabrication_numerator():
    from core.llm.fabrication_accounting import (
        BUSINESS_VERDICTS,
        FABRICATION_VERDICTS,
    )

    assert not (BUSINESS_VERDICTS & FABRICATION_VERDICTS)


def test_real_model_wait_choice_is_pending_not_business_success(
        feedback_db, fresh_router, monkeypatch):
    """The real compact wait consumer produces a receipt; parsed != success."""
    from core.employee_adaptation import (
        _compact_wait_choice_context,
        propose_adaptation,
    )
    from core.employee_routing_feedback import record_business_outcome
    from tests.test_employee_wait_choice import (
        _assignment as wait_assignment,
        _context as wait_context,
        _observations as wait_observations,
    )

    context = wait_context()
    observations = wait_observations()
    compact = _compact_wait_choice_context(context, observations)
    assert compact is not None
    wait_proposal = compact["response_model"].model_validate({
        "decision": "replan",
        "reason": "the invoice is a future external record",
        "fact": "the current supplier invoice for PO-WAIT-520",
        "subject": "purchase order PO-WAIT-520",
        "expected_from": "authorized procurement source",
        "expected_answer_type": "text",
        "blocks_operation": "invoice_reconciliation",
    })

    handler = _handler("ws-wait", "tenant-wait")
    _configure_pool(handler, monkeypatch)
    service = _service_for(handler, "ws-wait", "tenant-wait")

    def _from_openai(client, **_kwargs):
        def create(**_kwargs):
            return wait_proposal

        return NS(chat=NS(completions=NS(create=create)))

    with patch("core.llm.byok_handler.instructor.from_openai", _from_openai):
        result = asyncio.run(propose_adaptation(
            context, observations, assignment=wait_assignment(),
            llm_service=service))
    assert result["source"] == "model_wait_choice", result
    assert result["routing_result_id"], result
    assert result["routing"]["profile"]["name"] == "employee_wait_choice"

    recorded = asyncio.run(record_business_outcome(
        result, stage="employee_wait_choice",
        outcome={"objective_met": None},
        workspace_id="ws-wait", tenant_id="tenant-wait"))
    assert recorded["recorded"] is True
    rows = _rows(feedback_db)
    assert len(rows) == 1
    row = rows[0]
    assert row.success is True  # transport fact
    features = row.prompt_features or {}
    assert features["capability_profile"] == "employee_wait_choice"
    assert features["business_outcome"] == "unresolved"
    assert "business_satisfied" not in str(features.get("verdict"))

    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_wait_choice"),
        workspace_id="ws-wait", tenant_id="tenant-wait")
    assert "local_ctrl1234/llama3.1:8b" not in evidence, (
        "the parsed wait must not count as a satisfactory sample")


def test_real_rejected_wait_choice_is_semantic_failure_not_fallback_credit(
        feedback_db, fresh_router, monkeypatch):
    """The real wait policy guard's rejection annotates the model generation."""
    from core.employee_adaptation import (
        _compact_wait_choice_context,
        propose_adaptation,
    )
    from tests.test_employee_wait_choice import (
        _assignment as wait_assignment,
        _context as wait_context,
        _observations as wait_observations,
    )

    context = wait_context()
    context["missing_prerequisites"][0].update(
        status="ambiguous", missing=[])
    for source in context["sources"]:
        source["read"] = True
    context["rules"]["allowed_proposal_kinds"] = ["clarify", "retain"]
    context["rules"]["allowed_work_requests"] = []
    observations = wait_observations()
    compact = _compact_wait_choice_context(context, observations)
    assert compact is not None
    forbidden_wait = compact["response_model"].model_validate({
        "decision": "replan",
        "reason": "await the current invoice",
        "fact": "the current supplier invoice",
        "subject": "purchase order PO-WAIT-520",
        "expected_from": "authorized procurement source",
        "expected_answer_type": "text",
        "blocks_operation": "invoice_reconciliation",
    })

    handler = _handler("ws-wait", "tenant-wait")
    _configure_pool(handler, monkeypatch)
    service = _service_for(handler, "ws-wait", "tenant-wait")

    def _from_openai(client, **_kwargs):
        def create(**_kwargs):
            return forbidden_wait

        return NS(chat=NS(completions=NS(create=create)))

    with patch("core.llm.byok_handler.instructor.from_openai", _from_openai):
        result = asyncio.run(propose_adaptation(
            context, observations, assignment=wait_assignment(),
            llm_service=service))
    assert result["source"] == "deterministic", result
    assert result["failure_stage"] == "wait_choice_policy", result
    assert result["routing_result_id"], result
    evaluation = result.get("evaluation") or {}
    assert evaluation.get("recorded") is True, evaluation
    assert evaluation.get("failure_kind") == "invalid_plan_reference"

    rows = _rows(feedback_db)
    assert len(rows) == 1
    row = rows[0]
    assert row.success is False
    features = row.prompt_features or {}
    assert features["capability_profile"] == "employee_wait_choice"
    assert features["failure_kind"] == "invalid_plan_reference"
    assert features["business_outcome"] == "failed"


def test_context_floor_after_feedback_tests():
    """The feedback fixtures must not poison a later independent routing test."""
    _run_context_floor_scenario()
