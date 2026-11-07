"""Contract-based evidence eligibility and missing-prerequisite obligations."""
from __future__ import annotations

import asyncio

from core.assignment_plan import new_assignment, new_step
from core.employee_adaptation import WorkAdaptationProposal, propose_adaptation
from core.employee_job_runner import (
    evidence_observations, missing_prerequisite_question,
)
from core.employee_proposal import context_from_record, operation_capabilities


def _verified(step_id, adapter, result):
    step = new_step(
        step_id=step_id, title=step_id, operation_type="retrieve",
        adapter=adapter, inputs={}, effect="read_only")
    step.update(status="applied", operation_id=f"op-{step_id}", result=result)
    return step


def _record(*steps):
    assignment = new_assignment(
        objective="Reconcile the supplier invoice for PO-7",
        workspace_id="ws", tenant_id="tenant",
        steps=list(steps), authorized_actions=["retrieve", "calculate"])
    return {"task_version": 1, "assignment": assignment}


def _structured(step_id, data):
    return _verified(step_id, "document.read", {
        "data": data,
        "resource_id": step_id,
        "source_version": "v1",
        "coverage": {"complete": True, "known": True, "truncated": False},
        "verification": {
            "status": "verified", "resource_id": step_id, "version": "v1"},
    })


def _tabular():
    return _verified("prices", "workbook.read", {
        "rows": [{"Product": "A", "Units": 2, "ApprovedCost": "100.00"}],
        "schema": [{"column": key} for key in (
            "Product", "Units", "ApprovedCost")],
        "resource_id": "prices", "source_version": "v1",
        "coverage": {"complete": True, "known": True, "truncated": False},
        "verification": {
            "status": "verified", "resource_id": "prices", "version": "v1"},
    })


def test_unfamiliar_headers_are_tabular_evidence_without_aliases():
    record = _record(_tabular())
    observations = evidence_observations(record)
    assert observations and observations[0]["shape"] == "tabular"
    assert observations[0]["columns"] == [
        "ApprovedCost", "Product", "Units"]
    capabilities = operation_capabilities(record["assignment"])
    quote = next(
        item for item in capabilities
        if item["operation"] == "quote_calculation")
    assert quote["status"] == "ready"
    context = context_from_record(record)
    assert any(
        item["operation"] == "quote_calculation"
        and item["status"] == "ready"
        for item in context["available_business_operations"])


def test_missing_invoice_keeps_capability_and_names_po_identity():
    record = _record(
        _structured("purchase-order", {
            "po_id": "PO-7", "vendor_id": "V-9"}),
        _structured("receiving", {
            "po_id": "PO-7", "received_quantity": "2"}),
    )
    context = context_from_record(record)
    invoice = next(
        item for item in context["available_business_operations"]
        if item["operation"] == "invoice_reconciliation")
    assert invoice["status"] == "missing"
    assert invoice["missing"] == ["invoice"]
    assert "PO-7" in invoice["question_hint"]
    # The capability stays visible with its missing role, but it is not
    # advertised as executable work until the prerequisite is present.
    assert not any(
        schema["operation"] == "invoice_reconciliation"
        for schema in context["work_request_schemas"])
    assert context["missing_prerequisites"]
    assert context["rules"]["allowed_work_requests"] == []
    assert context["rules"]["allowed_proposal_kinds"] == [
        "clarify", "retain"]


class _RetainingLLM:
    def __init__(self):
        self.calls = 0

    async def generate_structured_response(self, **kwargs):
        self.calls += 1
        model = kwargs.get("response_model")
        if getattr(model, "__name__", "") == "CompactWaitChoiceProposal":
            return model(
                decision="retain", reason="wait for the user",
                observation_ids=["evidence-po"])
        return WorkAdaptationProposal(
            decision="retain", reason="wait for the user",
            observation_ids=["evidence-po"])


def test_retain_with_missing_prerequisite_is_repaired_and_obligated():
    record = _record(
        _structured("purchase-order", {
            "po_id": "PO-7", "vendor_id": "V-9"}),
        _structured("receiving", {
            "po_id": "PO-7", "received_quantity": "2"}),
    )
    context = context_from_record(record)
    llm = _RetainingLLM()
    result = asyncio.run(propose_adaptation(
        context,
        [{"observation_id": "evidence-po", "kind": "evidence_result",
          "step_id": "purchase-order"}],
        assignment=record["assignment"], llm_service=llm,
        deadline=__import__("time").monotonic() + 5))
    # The bounded wait-choice compact attempt runs first, then the full
    # proposal and one repair. The retain is a declared no-progress outcome;
    # the repair must name the missing prerequisite instead.
    assert llm.calls == 3
    assert result["source"] == "deterministic"
    assert any("missing prerequisite" in item for item in result["errors"])
    question = missing_prerequisite_question(context)
    assert question
    assert "invoice" in question["question"]
    assert "PO-7" in question["question"]
    assert question["concept"] == "invoice_reconciliation"
    assert question["inputs"]["missing"] == ["invoice"]


def test_clarification_role_scope_uses_only_explicit_typed_roles():
    from core.employee_job_runner import scoped_missing_roles

    chosen = {"operation": "invoice_reconciliation",
              "missing": ["invoice", "receiving"]}
    # Prose names the capability ("invoice reconciliation") while the typed
    # request asks for receiving; the typed role wins.
    scoped = scoped_missing_roles(chosen, {
        "question": (
            "Which source has the receiving record for this invoice "
            "reconciliation?"),
        "missing_roles": ["receiving"],
    })
    assert scoped == ["receiving"]
    # Ambiguous/undeclared scope does not narrow: under-settle, never settle
    # an undeclared obligation.
    assert scoped_missing_roles(chosen, {
        "question": "Which source has the receiving record?",
    }) == ["invoice", "receiving"]
    assert scoped_missing_roles(chosen, {
        "question": "Which source has the invoice?",
        "missing_roles": ["invoice", "approval"],
    }) == ["invoice", "receiving"]


def test_clarification_rejects_undeclared_role_scope():
    from core.employee_adaptation import _adaptation_errors
    from core.employee_proposal import ClarificationProposal

    context = {
        "missing_prerequisites": [{
            "operation": "invoice_reconciliation",
            "missing": ["invoice", "receiving"],
        }],
    }
    invalid = WorkAdaptationProposal(
        decision="clarify",
        clarification=ClarificationProposal(
            question="Which source has the approval?",
            missing_roles=["approval"]),
    )
    errors = _adaptation_errors(invalid, {}, context)
    assert any("missing_roles" in error for error in errors), errors
    valid = WorkAdaptationProposal(
        decision="clarify",
        clarification=ClarificationProposal(
            question="Which source has the invoice?",
            missing_roles=["invoice"]),
    )
    assert _adaptation_errors(valid, {}, context) == []


def test_empty_clarification_is_not_accepted_as_progress():
    from core.employee_adaptation import _adaptation_errors
    from core.employee_adaptation import AdaptationProposal

    proposal = AdaptationProposal(
        decision="clarify", reason="nothing", observation_ids=["o1"])
    errors = _adaptation_errors(proposal, {}, {})
    assert any("specific clarification question" in item for item in errors)
