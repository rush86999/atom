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


def _handler():
    from tests.test_structured_dispatch_policy import _handler as factory

    return factory("ws-ctrl", "tenant-ctrl")


def _service(handler):
    service = LLMService.__new__(LLMService)
    service._get_handler = lambda **_kw: handler
    service.continuous_learning = None
    service._workspace_id = "ws-ctrl"
    service._tenant_id = "tenant-ctrl"
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
