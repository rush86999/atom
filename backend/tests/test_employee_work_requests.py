"""Typed business work requests compile to supported assignment steps."""
from __future__ import annotations

from decimal import Decimal

import pytest

import core.assignment_invoice  # noqa: F401,E402
import core.assignment_quote  # noqa: F401,E402
import core.quote_rows  # noqa: F401,E402
from core.assignment_plan import new_assignment, new_step, step_by_id
from core.employee_adaptation import (
    AdaptationProposal,
    _adaptation_errors,
    adopt_adaptation,
)
from core.employee_proposal import build_employee_context, context_from_record
from core.employee_work_compiler import (
    WorkRequestCompileError,
    compile_work_request_patch,
)
from core.employee_work_requests import (
    InvoiceReconciliationRequest,
    MoneyTerm,
    QuoteCalculationRequest,
    TaxTerm,
)
from tests.test_assignment_executor import _run, env  # noqa: F401


def _quote_evidence():
    read = new_step(
        step_id="read", title="Read held-out price rows",
        operation_type="retrieve", adapter="workbook.read",
        inputs={}, effect="read_only")
    read["status"] = "applied"
    read["operation_id"] = "op-read"
    read["result"] = {
        "rows": [
            {"Item": "A", "Qty": 2, "Price": 100, "Currency": "USD"},
            {"Item": "B", "Qty": 3, "Price": 50, "Currency": "USD"},
        ],
        "schema": [{"column": "Item"}, {"column": "Qty"},
                   {"column": "Price"}, {"column": "Currency"}],
        "coverage": {"complete": True, "known": True, "truncated": False},
        "source_version": "heldout-v1",
    }
    return read


def _quote_request():
    return QuoteCalculationRequest(
        operation="quote_calculation",
        source_step_id="read",
        require_verified_source=False,
        columns={"item_id": "Item", "quantity": "Qty",
                 "unit_price": "Price", "currency": "Currency"},
        currency="USD",
        freight=MoneyTerm(value="20.00",
                          authority_ref="held-out agreement"),
        tax=TaxTerm(basis="none"),
        reason="compute the exact quote from accepted rows and terms")


def test_quote_request_compiles_and_executes_from_full_evidence(env):
    read = _quote_evidence()
    plan = new_assignment(
        objective="Quote the held-out request",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", steps=[read],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = env["executor"].create_assignment(
        "conv-work-quote", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    context = context_from_record(env["lifecycle"].get_task(run_id))
    assert context["stage"] == "follow_up"
    assert context["rules"]["evidence_only"] is False
    assert context["work_request_schemas"]
    assignment = env["lifecycle"].get_assignment(run_id)
    patch = compile_work_request_patch(
        _quote_request(), assignment, context=context)
    assert patch["add_steps"][0]["inputs"]["rows"] == "${read.rows}"
    assert patch["add_steps"][1]["inputs"]["line_items"] == (
        f"${{{patch['add_steps'][0]['step_id']}.line_items}}")

    proposal = AdaptationProposal(
        decision="replan", reason="compute the exact quote",
        observation_ids=["evidence-read-1"],
        work_request=_quote_request())
    adopted = adopt_adaptation(env["lifecycle"], run_id, proposal)
    assert adopted["status"] == "applied"
    status = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    calc = step_by_id(assignment, patch["add_steps"][1]["step_id"])
    assert calc["status"] == "applied"
    assert Decimal(str(calc["result"]["value"])) == Decimal("370.00")
    assert status["assignment"]["status"] == "completed"


def test_quote_mapping_rejects_unknown_column_and_bad_terms():
    read = _quote_evidence()
    assignment = new_assignment(
        objective="Quote", steps=[read],
        authorized_actions=["retrieve", "calculate"])
    bad = _quote_request().model_copy(update={
        "columns": {"item_id": "Item", "quantity": "MissingQty",
                    "unit_price": "Price"}})
    with pytest.raises(WorkRequestCompileError, match="MissingQty"):
        compile_work_request_patch(bad, assignment, context={})

    missing_freight_authority = _quote_request().model_copy(update={
        "freight": MoneyTerm(value="20.00", authority_ref="   ")})
    with pytest.raises(WorkRequestCompileError, match="authority"):
        compile_work_request_patch(
            missing_freight_authority, assignment, context={})

    missing_source = _quote_request().model_copy(update={
        "source_step_id": "absent"})
    with pytest.raises(WorkRequestCompileError, match="absent"):
        compile_work_request_patch(missing_source, assignment, context={})


def _invoice_evidence():
    po = new_step(
        step_id="po", title="Read PO", operation_type="retrieve",
        adapter="document.read", inputs={}, effect="read_only")
    po.update(status="applied", operation_id="op-po", result={
        "data": {"po_id": "PO-1", "vendor_id": "V-9"}})
    invoice = new_step(
        step_id="invoice", title="Read invoice", operation_type="retrieve",
        adapter="document.read", inputs={}, effect="read_only")
    invoice.update(status="applied", operation_id="op-invoice", result={
        "data": {"invoice_id": "INV-1", "po_id": "PO-1", "quantity": "2",
                 "unit_price": "120.00", "freight": "30.00",
                 "currency": "USD"}})
    receiving = new_step(
        step_id="receiving", title="Read receiving",
        operation_type="retrieve", adapter="workbook.read",
        inputs={}, effect="read_only")
    receiving.update(status="applied", operation_id="op-receiving", result={
        "data": {"po_id": "PO-1", "received_quantity": "2"}})
    return po, invoice, receiving


def _invoice_request():
    return InvoiceReconciliationRequest(
        operation="invoice_reconciliation",
        invoice_step_id="invoice",
        purchase_order_step_id="po",
        receiving_step_id="receiving",
        require_verified_evidence=False,
        reason="reconcile the corrected invoice against receiving")


def test_invoice_request_compiles_and_reconciles_full_evidence(env):
    po, invoice, receiving = _invoice_evidence()
    plan = new_assignment(
        objective="Prepare the supported bill",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", steps=[po, invoice, receiving],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = env["executor"].create_assignment(
        "conv-work-invoice", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    context = context_from_record(env["lifecycle"].get_task(run_id))
    proposal = AdaptationProposal(
        decision="replan", reason="reconcile accepted invoice evidence",
        observation_ids=["invoice-read-1"],
        work_request=_invoice_request())
    adopted = adopt_adaptation(env["lifecycle"], run_id, proposal)
    assert adopted["status"] == "applied"
    status = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    reconcile = next(
        step for step in assignment["steps"]
        if step["adapter"] == "invoice.reconcile")
    assert reconcile["status"] == "applied"
    assert Decimal(str(reconcile["result"]["value"])) == Decimal("270.00")
    assert status["assignment"]["status"] == "completed"


def test_work_request_rejects_model_authored_steps_and_bad_references():
    read = _quote_evidence()
    assignment = new_assignment(
        objective="Quote", steps=[read],
        authorized_actions=["retrieve", "calculate"])
    proposal = AdaptationProposal(
        decision="replan", reason="bad mixed proposal",
        observation_ids=["o1"], work_request=_quote_request(),
        new_steps=[{
            "step_id": "forged", "title": "Forged", "operation_type":
            "calculate", "adapter": "quote.calculate", "inputs": {}}])
    context = build_employee_context(
        objective="Quote", sources=[], stage="follow_up",
        existing_step_ids=["read"])
    errors = _adaptation_errors(proposal, assignment, context)
    assert any("cannot be combined" in error for error in errors)

    forged = _quote_request().model_copy(update={"source_step_id": "forged"})
    with pytest.raises(WorkRequestCompileError, match="forged"):
        compile_work_request_patch(forged, assignment, context=context)


def test_context_previews_are_labeled_and_discovery_is_not_followup():
    discovery = build_employee_context(
        objective="Quote", sources=[{"resource_id": "prices",
                                     "row_count": 50}],
        stage="discovery")
    assert discovery["rules"]["evidence_only"] is True
    assert discovery["work_request_schemas"] == []
    assert discovery["sources"][0]["preview"]["sampled"] is True
    assert discovery["sources"][0]["preview"]["total_count"] == 50
    assert discovery["sources"][0]["preview"]["shown_count"] == 0
    assert discovery["sources"][0]["preview"]["omitted_count"] == 50

    follow = build_employee_context(
        objective="Quote", stage="follow_up",
        evidence_results=[{
            "step_id": "read", "rows": [
                {"Item": str(index)} for index in range(25)],
            "total_count": 25, "schema": [{"name": "Item"}]}])
    assert follow["rules"]["evidence_only"] is False
    assert follow["rules"]["can_propose_supported_work"] is True
    assert follow["work_request_schemas"]
    preview = follow["evidence_results"][0]["preview"]
    assert preview["sampled"] is True
    assert preview["total_count"] == 25
    assert preview["shown_count"] == 20
    assert preview["omitted_count"] == 5
