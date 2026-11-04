"""BYOK auto-selection through the real employee/LLMService consumer path.

These controls deliberately call ``propose_employee_work`` and
``propose_adaptation`` with a real ``LLMService`` forwarding to a real
``BYOKHandler``. The handler ranks the configured pool and dispatches the
selected client; only the provider transport is doubled.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import pytest

from core.employee_adaptation import propose_adaptation
from core.employee_proposal import (
    build_employee_context,
    propose_employee_work,
)
from core.employee_work_requests import (
    MoneyTerm, QuoteCalculationRequest, TaxTerm,
)
from core.llm.byok_handler import QueryComplexity
from core.llm_service import LLMService


def _service(handler):
    service = LLMService.__new__(LLMService)
    service._get_handler = lambda **_kw: handler
    service.continuous_learning = None
    service._workspace_id = "ws-ctrl"
    service._tenant_id = "tenant-ctrl"
    return service


def _handler_fixture():
    from contextlib import nullcontext
    from tests.test_structured_dispatch_policy import _handler

    return nullcontext(_handler())


def _configure_pool(handler, monkeypatch, *, cheap_fails=False,
                    pricey_fails=False):
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
        "provider_id": "prov-pricey",
        "provider_type": "ollama",
        "supports_tools": True,
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
    handler._claim_model_attempt = (
        lambda *args, **kwargs: "test-token")
    handler._release_model_attempt = (
        lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "core.llm.byok_handler.load_feedback_evidence",
        lambda *args, **kwargs: {})


def _fake_instructor(selected, proposal, fail_models=()):
    from core.employee_proposal import EmployeeWorkProposal

    def _from_openai(client, **_kwargs):
        selected.append(client)

        def create(**kwargs):
            model = str(kwargs.get("model") or "")
            if any(name in model for name in fail_models):
                raise ValueError("controlled provider failure")
            return proposal

        return NS(chat=NS(completions=NS(create=create)))
    return _from_openai


def _proposal_context():
    return build_employee_context(
        objective="Read the authorized evidence",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl",
        sources=[{
            "kind": "document", "representation": "document_text",
            "resource_id": "doc-1", "file_name": "note.txt",
        }],
        stage="discovery")


def _proposal():
    from core.employee_proposal import EmployeeWorkProposal

    return EmployeeWorkProposal(
        proposal_kind="evidence_read",
        reason="read the authorized note",
        evidence_reads=[{
            "step_id": "evidence-1", "title": "Read note",
            "source_id": "doc-1",
        }])


def test_employee_proposal_auto_selects_cheaper_capable_route(monkeypatch):
    selected = []
    with _handler_fixture() as handler:
        _configure_pool(handler, monkeypatch)
        service = _service(handler)
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _fake_instructor(selected, _proposal())):
            result = asyncio.run(propose_employee_work(
                _proposal_context(), llm_service=service))
    assert result["source"] == "model", result
    assert result["routing"]["served_route"] == {
        "provider": "local_ctrl1234", "model": "llama3.1:8b"}
    assert result["routing"]["profile"]["name"] == (
        "employee_evidence_selection")
    assert selected and selected[0] is handler.clients["local_ctrl1234"]


def test_employee_proposal_measured_failure_excludes_cheap_route(monkeypatch):
    selected = []
    with _handler_fixture() as handler:
        _configure_pool(handler, monkeypatch)
        # The scoped feedback consumer says this exact route has a measured
        # semantic failure rate above the profile threshold.
        failure = {
            "local_ctrl1234/llama3.1:8b": {
                "samples": 5, "successes": 1, "retries": 0,
                "unsafe_failures": 0, "semantic_failures": 4,
                "failure_kinds": {"semantic_failure"},
                "last_failure_kind": "semantic_failure",
            },
        }
        monkeypatch.setattr(
            "core.llm.byok_handler.load_feedback_evidence",
            lambda *args, **kwargs: failure)
        service = _service(handler)
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _fake_instructor(selected, _proposal())):
            result = asyncio.run(propose_employee_work(
                _proposal_context(), llm_service=service))
    assert result["source"] == "model", result
    assert result["routing"]["served_route"] == {
        "provider": "local_pricey", "model": "pricey-model"}
    assert selected and selected[0] is handler.clients["local_pricey"]


def test_employee_proposal_failed_costlier_route_does_not_displace_cheap(
        monkeypatch):
    selected = []
    with _handler_fixture() as handler:
        _configure_pool(handler, monkeypatch)
        failure = {
            "local_pricey/pricey-model": {
                "samples": 5, "successes": 0, "retries": 0,
                "unsafe_failures": 0, "semantic_failures": 5,
                "failure_kinds": {"semantic_failure"},
                "last_failure_kind": "semantic_failure",
            },
        }
        monkeypatch.setattr(
            "core.llm.byok_handler.load_feedback_evidence",
            lambda *args, **kwargs: failure)
        service = _service(handler)
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _fake_instructor(selected, _proposal())):
            result = asyncio.run(propose_employee_work(
                _proposal_context(), llm_service=service))
    assert result["source"] == "model", result
    assert result["routing"]["served_route"] == {
        "provider": "local_ctrl1234", "model": "llama3.1:8b"}
    # Same-route repair/retry is bounded; the failed costlier route is never
    # dispatched in its place.
    assert 1 <= len(selected) <= 2
    assert all(
        client is handler.clients["local_ctrl1234"] for client in selected)


def test_employee_proposal_scope_failure_never_borrows_another_scope():
    from core.llm_service import LLMScopeUnresolvedError

    class UnresolvedScope:
        async def generate_structured_response(self, **_kwargs):
            raise LLMScopeUnresolvedError("tenant-gone", "unknown_tenant")

    result = asyncio.run(propose_employee_work(
        _proposal_context(), llm_service=UnresolvedScope()))
    assert result["source"] == "deterministic"
    assert result["technical_fallback"] is True
    assert result["errors"]
    assert result["proposal"]["proposal_kind"] == "evidence_read"


def test_employee_adaptation_no_eligible_route_keeps_unresolved_receipts(
        monkeypatch):
    from core.assignment_plan import new_assignment

    context = {
        "identity": {"workspace_id": "ws-ctrl", "tenant_id": "tenant-ctrl"},
        "work_request_schemas": [{
            "operation": "invoice_reconciliation", "schema": {},
        }],
        "available_business_operations": [{
            "operation": "invoice_reconciliation", "status": "ready",
            "evidence": [{"step_id": "read", "shape": "structured"}],
            "roles": {"invoice": ["read"], "purchase_order": ["read"],
                      "receiving": ["read"]},
            "known_identities": {"invoice.po_id": "PO-X"},
        }],
        "rules": {"allowed_work_requests": []},
        "objective": "Reconcile the authorized invoice",
        "business_requirements": [{
            "requirement_id": "result-invoice", "operation":
            "invoice_reconciliation", "status": "unresolved",
        }],
    }
    assignment = new_assignment(
        objective="Reconcile the authorized invoice",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl",
        authorized_actions=["retrieve", "calculate"])
    with _handler_fixture() as handler:
        _configure_pool(handler, monkeypatch)
        both_failed = {
            "local_ctrl1234/llama3.1:8b": {
                "samples": 5, "successes": 0, "retries": 0,
                "unsafe_failures": 0, "semantic_failures": 5,
                "failure_kinds": {"semantic_failure"},
                "last_failure_kind": "semantic_failure",
            },
            "local_pricey/pricey-model": {
                "samples": 5, "successes": 0, "retries": 0,
                "unsafe_failures": 0, "semantic_failures": 5,
                "failure_kinds": {"semantic_failure"},
                "last_failure_kind": "semantic_failure",
            },
        }
        monkeypatch.setattr(
            "core.llm.byok_handler.load_feedback_evidence",
            lambda *args, **kwargs: both_failed)
        service = _service(handler)
        result = asyncio.run(propose_adaptation(
            context, [{"observation_id": "evidence-1",
                       "kind": "evidence_result", "step_id": "read"}],
            assignment=assignment, llm_service=service))
    assert result["source"] == "deterministic"
    assert result["technical_fallback"] is True
    assert result["proposal"]["decision"] == "retain"
    assert "work_request" not in result["proposal"] or not result[
        "proposal"].get("work_request")
    assert result["errors"]
    assert result["routing"]["error"]["code"] in (
        "no_suitable_configured_model", "provider_failure")


def test_employee_proposal_no_eligible_route_keeps_deterministic_receipts(
        monkeypatch):
    with _handler_fixture() as handler:
        _configure_pool(handler, monkeypatch)
        both_failed = {
            "local_ctrl1234/llama3.1:8b": {
                "samples": 5, "successes": 0, "retries": 0,
                "unsafe_failures": 0, "semantic_failures": 5,
                "failure_kinds": {"semantic_failure"},
                "last_failure_kind": "semantic_failure",
            },
            "local_pricey/pricey-model": {
                "samples": 5, "successes": 0, "retries": 0,
                "unsafe_failures": 0, "semantic_failures": 5,
                "failure_kinds": {"semantic_failure"},
                "last_failure_kind": "semantic_failure",
            },
        }
        monkeypatch.setattr(
            "core.llm.byok_handler.load_feedback_evidence",
            lambda *args, **kwargs: both_failed)
        service = _service(handler)
        result = asyncio.run(propose_employee_work(
            _proposal_context(), llm_service=service))
    assert result["source"] == "deterministic"
    assert result["technical_fallback"] is True
    assert result["errors"]
    assert result["proposal"]["proposal_kind"] == "evidence_read"


def test_employee_wait_choice_uses_the_dedicated_profile(monkeypatch):
    from core.assignment_plan import new_assignment
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_attempt_journal import AttemptJournal
    from core.employee_proposal import ClarificationProposal
    from core.employee_work_requests import work_request_schemas

    selected = []
    proposal = WorkAdaptationProposal(
        decision="clarify",
        reason="the receiving record is missing",
        observation_ids=["evidence-1"],
        clarification=ClarificationProposal(
            question="Which authorized source contains the receiving record "
                     "for PO-SEL-520?",
            concept="receiving", unblocks="invoice reconciliation"))
    context = {
        "identity": {"workspace_id": "ws-ctrl", "tenant_id": "tenant-ctrl"},
        "objective": "Reconcile INV-SEL-77 for PO-SEL-520",
        "work_request_schemas": work_request_schemas(),
        "available_business_operations": [{
            "operation": "invoice_reconciliation",
            "status": "missing",
            "missing": ["receiving"],
            "evidence": [],
            "roles": {}, "known_identities": {"invoice.po_id": "PO-SEL-520"},
        }],
        "missing_prerequisites": [{
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": "missing",
            "missing": ["receiving"],
        }],
        "rules": {"allowed_proposal_kinds": ["clarify", "replan"]},
        "teaching": {"terms": {"currency": "USD"}},
    }
    assignment = new_assignment(
        objective="Reconcile INV-SEL-77 for PO-SEL-520",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl",
        authorized_actions=["retrieve", "calculate"])
    with _handler_fixture() as handler:
        _configure_pool(handler, monkeypatch)
        service = _service(handler)
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _fake_instructor(selected, proposal)):
            result = asyncio.run(propose_adaptation(
                context, [{"observation_id": "evidence-1",
                           "kind": "evidence_result", "step_id": "read"}],
                assignment=assignment, llm_service=service))
    assert result["source"] == "model", result
    assert result["routing"]["profile"]["name"] == "employee_wait_choice"
    assert result["routing"]["served_route"] == {
        "provider": "local_ctrl1234", "model": "llama3.1:8b"}


def test_employee_adaptation_auto_route_records_served_route(monkeypatch):
    from core.assignment_plan import new_assignment
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_attempt_journal import AttemptJournal

    selected = []
    proposal = WorkAdaptationProposal(
        decision="replan",
        reason="calculate the quote from accepted rows",
        observation_ids=["evidence-1"],
        work_request=QuoteCalculationRequest(
            operation="quote_calculation",
            source_step_id="read",
            columns={
                "item_id": "Item", "quantity": "Qty",
                "unit_price": "Price", "currency": "Currency"},
            currency="USD",
            freight=MoneyTerm(value="0.00", authority_ref="freight"),
            tax=TaxTerm(basis="none", authority_ref="tax_basis"),
        ))
    context = {
        "identity": {"workspace_id": "ws-ctrl", "tenant_id": "tenant-ctrl"},
        "work_request_schemas": [{
            "operation": "quote_calculation",
            "schema": {},
        }],
        "available_business_operations": [{
            "operation": "quote_calculation", "status": "ready",
            "evidence": [{"step_id": "read", "shape": "tabular"}],
            "roles": {}, "known_identities": {},
        }],
        "rules": {"allowed_work_requests": ["quote_calculation"]},
        "teaching": {"terms": {
            "currency": "USD", "freight": "0.00",
            "tax_basis": "none"}},
        "business_requirements": [{
            "requirement_id": "result-quote", "operation":
            "quote_calculation", "status": "unresolved",
        }],
        "objective": "Quote the accepted rows",
    }
    assignment = new_assignment(
        objective="Quote the accepted rows", workspace_id="ws-ctrl",
        tenant_id="tenant-ctrl", authorized_actions=["retrieve", "calculate"])
    with _handler_fixture() as handler:
        _configure_pool(handler, monkeypatch)
        service = _service(handler)
        journal = AttemptJournal()
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _fake_instructor(selected, proposal)):
            result = asyncio.run(propose_adaptation(
                context, [{"observation_id": "evidence-1",
                           "kind": "evidence_result", "step_id": "read"}],
                assignment=assignment, llm_service=service,
                attempt_journal=journal))
    parsed = [event for event in journal.events
              if event.get("event") == "parsed"]
    assert parsed, journal.events
    assert parsed[-1]["routing"]["served_route"] == {
        "provider": "local_ctrl1234", "model": "llama3.1:8b"}
    # The fake proposal is compact-incompatible (no unresolved requirement
    # match), so the full path is used; the important assertion is that the
    # real handler selected the cheaper route.
    assert result["routing"]["profile"]["name"] in (
        "employee_adaptive_planning",
        "employee_adaptive_planning_compact")
    assert result["routing"]["served_route"] == {
        "provider": "local_ctrl1234", "model": "llama3.1:8b"}
    assert selected and selected[0] is handler.clients["local_ctrl1234"]
