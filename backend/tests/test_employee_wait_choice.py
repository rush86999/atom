"""Bounded wait-choice consumer: wait, independent work, clarify, safe no-result."""
from __future__ import annotations

import asyncio
import copy

import pytest
from pydantic import ValidationError

from core.assignment_plan import new_assignment, new_step
from core.employee_adaptation import (
    AdaptationProposal,
    _compact_wait_choice_context,
    _expand_compact_wait_payload,
    propose_adaptation,
)


def _read(step_id, data=None, text=None):
    result = {
        "summary": f"read {step_id}",
        "verification": {
            "status": "verified",
            "resource_id": step_id,
            "version": "v1",
        },
        "coverage": {"complete": True, "known": True, "truncated": False},
        "data": data or {},
        "text": text,
    }
    step = new_step(
        step_id=step_id, title=f"Read {step_id}",
        operation_type="retrieve", adapter="document.text",
        inputs={"resource_binding": {
            "resource_id": step_id,
            "source_version": "v1",
            "original_file_name": f"{step_id}.json",
        }},
        effect="read_only")
    step["status"] = "applied"
    step["result"] = result
    return step


def _assignment():
    return new_assignment(
        objective=(
            "Reconcile supplier invoice INV-WAIT-77 for purchase order "
            "PO-WAIT-520 against the matching purchase order and receiving "
            "record."),
        employee_id="employee-wait", workspace_id="ws-wait",
        tenant_id="tenant-wait",
        steps=[
            _read("source-po", {
                "po_id": "PO-WAIT-520", "vendor_id": "V-63"}),
            _read("source-recv", {
                "po_id": "PO-WAIT-520", "received_quantity": "6"}),
        ],
        authorized_actions=["retrieve", "calculate"])


def _context(*, ready_quote=False):
    context = {
        "identity": {"workspace_id": "ws-wait", "tenant_id": "tenant-wait"},
        "objective": (
            "Reconcile supplier invoice INV-WAIT-77 for purchase order "
            "PO-WAIT-520 against the matching purchase order and receiving "
            "record."),
        "teaching": {"terms": {"currency": "USD"}},
        "missing_prerequisites": [{
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": "missing",
            "missing": ["invoice"],
            "question_hint": (
                "Which authorized source contains invoice INV-WAIT-77 for "
                "purchase order PO-WAIT-520?"),
            "known_identities": {"purchase_order.po_id": "PO-WAIT-520"},
        }],
        "available_business_operations": [
            {
                "operation": "quote_calculation",
                "label": "quote calculation",
                "status": "ready" if ready_quote else "unavailable",
                "missing": [] if ready_quote else [],
                "evidence": [],
                "roles": {},
                "known_identities": {},
            },
            {
                "operation": "invoice_reconciliation",
                "label": "invoice reconciliation",
                "status": "missing",
                "missing": ["invoice"],
                "evidence": [],
                "roles": {},
                "known_identities": {"purchase_order.po_id": "PO-WAIT-520"},
            },
        ],
        "sources": [{
            "source_id": "doc-po",
            "file_name": "po-wait-520.json",
            "kind": "document",
            "read": True,
            "source_version": "ev4:po",
        }, {
            "source_id": "doc-invoice",
            "file_name": "supplier-invoice-inv-wait-77.json",
            "kind": "document",
            "read": True,
            "source_version": "ev4:invoice",
        }],
        "evidence_results": [{
            "step_id": "source-po",
            "business_role": "purchase_order",
            "data_keys": ["po_id"],
            "data_preview": {"po_id": "PO-WAIT-520"},
        }],
        "rules": {
            "allowed_work_requests": [],
            "allowed_proposal_kinds": ["clarify", "replan", "retain"],
        },
    }
    return context


def _observations():
    return [{
        "observation_id": "evidence-po-wait",
        "kind": "evidence_result",
        "step_id": "source-po",
        "shape": "structured",
        "data_keys": ["po_id"],
    }]


def test_compact_wait_context_accepts_a_wait_and_fills_compiler_mechanics():
    compact = _compact_wait_choice_context(_context(), _observations())
    assert compact is not None
    assert "wait" in compact["prompt"].lower()
    assert "INV-WAIT-77" in compact["prompt"]
    assert "PO-WAIT-520" in compact["prompt"]
    assert "Never output $defs" in compact["prompt"]
    assert compact["response_model"].__name__ == "CompactWaitChoiceProposal"

    instance = compact["response_model"].model_validate({
        "decision": "replan",
        "reason": "the purchase order is accepted but the invoice is missing",
        "observation_ids": ["evidence-po-wait"],
        "fact": "the current supplier invoice for PO-WAIT-520",
        "subject": "purchase order PO-WAIT-520",
        "expected_from": "authorized procurement source",
        "expected_answer_type": "text",
        # blocks_operation intentionally omitted: the compiler derives it
    })
    expanded = _expand_compact_wait_payload(
        instance.model_dump(), _context())
    proposal = AdaptationProposal.model_validate(expanded)
    assert proposal.decision == "replan"
    assert proposal.work_request is not None
    assert proposal.work_request.operation == "await_evidence"
    assert proposal.work_request.blocks == "invoice reconciliation"
    assert proposal.work_request.blocks_operation == "invoice_reconciliation"
    assert proposal.work_request.fact


def test_compact_wait_subject_is_bound_to_a_known_identity_when_model_labels_it():
    compact = _compact_wait_choice_context(_context(), _observations())
    assert compact is not None
    instance = compact["response_model"].model_validate({
        "decision": "replan",
        "fact": "the current supplier invoice for PO-WAIT-520",
        "subject": "invoice reconciliation",
        "expected_from": "authorized procurement source",
        "expected_answer_type": "text",
    })
    proposal = AdaptationProposal.model_validate(
        _expand_compact_wait_payload(instance.model_dump(), _context()))
    assert proposal.work_request is not None
    assert proposal.work_request.subject == "purchase order PO-WAIT-520"
    assert proposal.work_request.blocks == "invoice reconciliation"


def test_genuine_missing_fact_can_wait_when_default_policy_is_clarify(
        monkeypatch):
    context = _context()
    context["missing_prerequisites"][0].update(
        status="missing", missing=["invoice"])
    for source in context["sources"]:
        source["read"] = True
    # The full context builder's no-ready-work default; the typed wait
    # contract is still valid for a genuinely absent external fact.
    context["rules"]["allowed_proposal_kinds"] = ["clarify", "retain"]
    context["rules"]["allowed_work_requests"] = []

    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=_fail_wait_policy(monkeypatch, {
            "decision": "replan",
            "reason": "the invoice is a future external record",
            "fact": "the current supplier invoice for PO-WAIT-520",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            "blocks_operation": "invoice_reconciliation",
        })))
    assert result["source"] == "model_wait_choice", result
    assert result["proposal"]["decision"] == "replan"
    assert result["proposal"]["work_request"]["operation"] == "await_evidence"
    assert result["errors"] == []


def test_wait_is_refused_when_authorized_unread_evidence_remains(
        monkeypatch):
    context = _context()
    next(
        source for source in context["sources"]
        if source["source_id"] == "doc-invoice")["read"] = False

    async def fake_pinned(_llm, *, response_model, **_kwargs):
        return response_model.model_validate({
            "decision": "replan",
            "fact": "the current supplier invoice for PO-WAIT-520",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            "blocks_operation": "invoice_reconciliation",
        })

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=FakeLLM()))
    assert result["source"] == "deterministic", result
    assert result["proposal"]["decision"] in ("clarify", "retain")
    assert result["proposal"].get("work_request") is None
    assert any("unread_authorized_evidence" in item
               for item in result["errors"])


def test_explicit_wrong_blocked_operation_is_refused(monkeypatch):
    context = _context()
    context["missing_prerequisites"][0]["status"] = "missing"
    context["missing_prerequisites"][0]["missing"] = ["invoice"]

    async def fake_pinned(_llm, *, response_model, **_kwargs):
        return response_model.model_validate({
            "decision": "replan",
            "fact": "the current supplier invoice for PO-WAIT-520",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            "blocks_operation": "quote_calculation",
        })

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=FakeLLM()))
    assert result["source"] == "deterministic", result
    assert result["proposal"].get("work_request") is None
    assert any("blocked_operation" in item for item in result["errors"])


def _fail_wait_policy(monkeypatch, payload):
    async def fake_pinned(_llm, *, response_model, **_kwargs):
        return response_model.model_validate(payload)

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    return FakeLLM()


def test_all_read_ambiguity_with_clarify_only_policy_cannot_become_a_wait(
        monkeypatch):
    context = _context()
    context["missing_prerequisites"][0].update(
        status="ambiguous", missing=[])
    for source in context["sources"]:
        source["read"] = True
    context["rules"]["allowed_proposal_kinds"] = ["clarify", "retain"]
    context["rules"]["allowed_work_requests"] = []

    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=_fail_wait_policy(monkeypatch, {
            "decision": "replan",
            "reason": "await the current invoice",
            "fact": "the current supplier invoice",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            "blocks_operation": "invoice_reconciliation",
        })))
    assert result["source"] == "deterministic", result
    assert result["proposal"]["decision"] in ("clarify", "retain")
    assert result["proposal"].get("work_request") is None
    assert result["failure_stage"] == "wait_choice_policy"
    assert any("replan_not_allowed" in item for item in result["errors"])
    assert any("ambiguous_record" in item for item in result["errors"])


def test_missing_prerequisite_without_a_named_role_requires_clarification(
        monkeypatch):
    context = _context()
    context["missing_prerequisites"][0].update(status="missing", missing=[])
    for source in context["sources"]:
        source["read"] = True
    context["rules"]["allowed_proposal_kinds"] = ["clarify", "retain"]

    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=_fail_wait_policy(monkeypatch, {
            "decision": "replan",
            "fact": "the current supplier invoice",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            "blocks_operation": "invoice_reconciliation",
        })))
    assert result["source"] == "deterministic", result
    assert result["proposal"]["decision"] == "clarify"
    assert result["proposal"]["clarification"]["question"]
    assert result["proposal"].get("work_request") is None
    assert any("unnamed_missing_role" in item for item in result["errors"])


def test_genuine_missing_external_record_can_wait_after_all_sources_are_read(
        monkeypatch):
    context = _context()
    context["missing_prerequisites"][0].update(
        status="missing", missing=["invoice"])
    for source in context["sources"]:
        source["read"] = True
    context["rules"]["allowed_proposal_kinds"] = [
        "clarify", "replan", "retain"]
    assert not [
        item for item in context["available_business_operations"]
        if item["status"] == "ready"]

    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=_fail_wait_policy(monkeypatch, {
            "decision": "replan",
            "reason": "the invoice is a future external record",
            "fact": "the current supplier invoice for PO-WAIT-520",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            "blocks_operation": "invoice_reconciliation",
        })))
    assert result["source"] == "model_wait_choice", result
    assert result["proposal"]["decision"] == "replan"
    assert result["proposal"]["work_request"]["operation"] == "await_evidence"
    assert result["errors"] == []


def test_genuine_wait_remains_valid_while_ready_independent_work_exists(
        monkeypatch):
    context = _context(ready_quote=True)
    context["missing_prerequisites"][0].update(
        status="missing", missing=["invoice"])
    for source in context["sources"]:
        source["read"] = True
    context["rules"]["allowed_proposal_kinds"] = [
        "clarify", "replan", "retain"]
    context["rules"]["allowed_work_requests"] = [
        "quote_calculation", "await_evidence"]

    async def fake_pinned(_llm, *, response_model, **_kwargs):
        assert response_model.__name__ == "AdaptationProposal"
        return response_model.model_validate({
            "decision": "replan",
            "reason": "wait for the invoice while the quote remains available",
            "observation_ids": ["evidence-po-wait"],
            "work_request": {
                "operation": "await_evidence",
                "fact": "the current supplier invoice for PO-WAIT-520",
                "subject": "purchase order PO-WAIT-520",
                "expected_from": "authorized procurement source",
                "expected_answer_type": "text",
                "blocks": "invoice reconciliation",
                "blocks_operation": "invoice_reconciliation",
            },
        })

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=FakeLLM()))
    assert result["source"] in ("model", "model_wait_choice"), result
    assert result["proposal"]["decision"] == "replan"
    assert result["proposal"]["work_request"]["operation"] == "await_evidence"
    assert result["proposal"]["work_request"]["blocks_operation"] == (
        "invoice_reconciliation")
    assert not any(
        "ready_independent_work" in item for item in result["errors"])


def test_model_clarification_is_accepted_without_a_wait(monkeypatch):
    result = asyncio.run(propose_adaptation(
        _context(), _observations(), assignment=_assignment(),
        llm_service=_fail_wait_policy(monkeypatch, {
            "decision": "clarify",
            "reason": "the invoice must be named or authorized",
            "clarification_question": (
                "Which authorized source contains invoice INV-WAIT-77?"),
            "clarification_unblocks": "invoice reconciliation",
        })))
    assert result["source"] == "model_wait_choice", result
    assert result["proposal"]["decision"] == "clarify"
    assert result["proposal"]["clarification"]["question"]
    assert result["proposal"].get("work_request") is None
    assert result["errors"] == []


def test_wait_without_a_named_blocked_operation_is_refused_when_multiple_exist(
        monkeypatch):
    context = _context()
    context["missing_prerequisites"].append({
        "operation": "quote_calculation",
        "label": "quote calculation",
        "status": "missing",
        "missing": ["tabular price rows"],
        "question_hint": "Which source contains the price rows?",
        "known_identities": {},
    })
    context["rules"]["allowed_proposal_kinds"] = [
        "clarify", "replan", "retain"]

    result = asyncio.run(propose_adaptation(
        context, _observations(), assignment=_assignment(),
        llm_service=_fail_wait_policy(monkeypatch, {
            "decision": "replan",
            "fact": "a missing external record",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
            # blocks_operation intentionally omitted
        })))
    assert result["source"] == "deterministic", result
    assert result["proposal"].get("work_request") is None
    assert any(
        "ambiguous_blocked_operation" in item for item in result["errors"])


def test_compact_wait_context_preserves_a_ready_independent_operation():
    assert _compact_wait_choice_context(
        _context(ready_quote=True), _observations()) is None


def test_compact_wait_context_allows_clarify_and_retain():
    compact = _compact_wait_choice_context(_context(), _observations())
    assert compact is not None
    clarify = compact["response_model"].model_validate({
        "decision": "clarify",
        "reason": "the invoice must be authorized or named",
        "observation_ids": ["evidence-po-wait"],
        "clarification_question": (
            "Which authorized source contains invoice INV-WAIT-77 for "
            "PO-WAIT-520?"),
        "clarification_unblocks": "invoice reconciliation",
    })
    proposal = AdaptationProposal.model_validate(
        _expand_compact_wait_payload(clarify.model_dump(), _context()))
    assert proposal.decision == "clarify"
    assert proposal.clarification is not None
    assert "INV-WAIT-77" in proposal.clarification.question
    retain = compact["response_model"].model_validate({
        "decision": "retain",
        "reason": "no material work is justified yet",
        "observation_ids": ["evidence-po-wait"],
    })
    retained = AdaptationProposal.model_validate(
        _expand_compact_wait_payload(retain.model_dump(), _context()))
    assert retained.decision == "retain"
    assert retained.work_request is None


def test_captured_empty_blocks_instance_is_rejected_by_the_existing_contract():
    """The recorded model produced this near-valid wait instance."""
    captured = {
        "decision": "replan",
        "reason": "the missing record is not yet accepted",
        "observation_ids": ["evidence-po-wait"],
        "step_ids": [],
        "facts": [{
            "fact": "The current supplier invoice for PO-WAIT-520 is missing",
            "subject": "purchase_order",
            "expected_from": "authorized procurement pool",
            "expected_answer_type": "text",
            "blocks": "",
        }],
        "new_steps": [],
        "update_steps": [],
        "work_request": {
            "operation": "await_evidence",
            "fact": "The current supplier invoice for PO-WAIT-520 is missing",
            "subject": "purchase_order",
            "expected_from": "authorized procurement pool",
            "expected_answer_type": "text",
            "blocks": "",
        },
        "clarification": None,
    }
    with pytest.raises(ValidationError):
        AdaptationProposal.model_validate(captured)
    # The compact instance supplies the same business choice and lets the
    # compiler fill the mechanical blocked-operation label.
    expanded = _expand_compact_wait_payload({
        "decision": "replan",
        "fact": captured["work_request"]["fact"],
        "subject": captured["work_request"]["subject"],
        "expected_from": captured["work_request"]["expected_from"],
        "expected_answer_type": "text",
        "observation_ids": ["evidence-po-wait"],
    }, _context())
    proposal = AdaptationProposal.model_validate(expanded)
    assert proposal.work_request is not None
    assert proposal.work_request.blocks == "invoice reconciliation"


def test_no_result_retains_applied_receipt_and_unresolved_requirement(
        monkeypatch):
    from core.employee_business_outcomes import (
        business_requirement_views, normalize_business_requirement,
    )

    assignment = _assignment()
    assignment["business_requirements"] = [normalize_business_requirement({
        "requirement_id": "result-invoice-wait",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "purchase order PO-WAIT-520",
        "subject_identity": {
            "po_id": "PO-WAIT-520", "invoice_id": "INV-WAIT-77"},
        "fact": "invoice",
        "correlation_id": "await-wait-choice",
    })]
    before = copy.deepcopy(assignment)

    async def fake_pinned(_llm, **_kwargs):
        return None

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        _context(), _observations(), assignment=assignment,
        llm_service=FakeLLM()))
    assert result["source"] == "deterministic"
    assert result["proposal"].get("work_request") is None
    assert assignment == before
    assert business_requirement_views(assignment)[0]["status"] == (
        "unresolved")
    assert all(
        step.get("status") == "applied"
        for step in assignment["steps"] if step.get("step_id") in {
            "source-po", "source-recv"})


def test_wait_choice_uses_compact_model_before_the_full_prompt(monkeypatch):
    calls = []

    async def fake_pinned(_llm, *, response_model, **kwargs):
        calls.append((response_model.__name__, kwargs))
        if response_model.__name__ == "AdaptationProposal":
            return None
        assert response_model.__name__ == "CompactWaitChoiceProposal"
        return response_model.model_validate({
            "decision": "replan",
            "reason": "the PO is accepted; the invoice is the missing record",
            "observation_ids": [],
            "fact": "the current supplier invoice for PO-WAIT-520",
            "subject": "purchase order PO-WAIT-520",
            "expected_from": "authorized procurement source",
            "expected_answer_type": "text",
        })

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        _context(), _observations(), assignment=_assignment(),
        llm_service=FakeLLM()))
    assert result["source"] == "model_wait_choice", result
    assert result["prompt_mode"] == "wait_choice"
    assert result["proposal"]["decision"] == "replan"
    assert result["proposal"]["work_request"]["operation"] == "await_evidence"
    assert result["proposal"]["work_request"]["blocks"]
    assert result["proposal"]["observation_ids"] == ["evidence-po-wait"]
    assert [name for name, _ in calls] == ["CompactWaitChoiceProposal"]


def test_wait_choice_no_result_is_deterministic_and_does_not_invent_work(
        monkeypatch):
    async def fake_pinned(_llm, **_kwargs):
        return None

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        _context(), _observations(), assignment=_assignment(),
        llm_service=FakeLLM()))
    assert result["source"] == "deterministic"
    assert result["proposal"]["decision"] in ("retain", "clarify")
    assert result["proposal"].get("work_request") is None
    assert result["proposal"].get("new_steps") in (None, [])
    assert result["errors"]


def test_compact_wait_context_marks_an_all_read_ambiguity_for_clarification():
    context = _context()
    context["missing_prerequisites"][0]["status"] = "ambiguous"
    for source in context["sources"]:
        source["read"] = True
    compact = _compact_wait_choice_context(context, _observations())
    assert compact is not None
    assert '"all_authorized_sources_read": true' in compact["prompt"]
    assert "do not wait for a source that is already in scope" in (
        compact["prompt"].lower())
