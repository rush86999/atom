"""Typed business work requests compile to supported assignment steps."""
from __future__ import annotations

from decimal import Decimal

import pytest

import core.assignment_invoice  # noqa: F401,E402
import core.assignment_quote  # noqa: F401,E402
import core.quote_rows  # noqa: F401,E402
from core.assignment_plan import (
    new_assignment, new_step, new_teaching_snapshot, step_by_id,
)
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


def _verified_quote_evidence():
    read = _quote_evidence()
    read["result"].update({
        "resource_id": "heldout-prices",
        "verification": {
            "status": "verified", "resource_id": "heldout-prices",
            "version": "heldout-v1",
            "coverage": {"complete": True, "known": True,
                         "truncated": False}},
    })
    return read


def _terms_teaching():
    snapshot = new_teaching_snapshot(revision="heldout-terms-1")
    snapshot["terms"] = {
        "currency": "USD", "freight": "20.00", "tax_basis": "none",
        "rounding_authority": "held-out agreement",
    }
    return snapshot


def _quote_request():
    return QuoteCalculationRequest(
        operation="quote_calculation",
        source_step_id="read",
        columns={"item_id": "Item", "quantity": "Qty",
                 "unit_price": "Price", "currency": "Currency"},
        currency="USD",
        freight=MoneyTerm(value="20.00", authority_ref="freight"),
        tax=TaxTerm(basis="none", authority_ref="tax_basis"),
        reason="compute the exact quote from accepted rows and terms")


def test_quote_request_compiles_and_executes_from_full_evidence(env):
    read = _verified_quote_evidence()
    plan = new_assignment(
        objective="Quote the held-out request",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", steps=[read],
        teaching_snapshot=_terms_teaching(),
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
    read = _verified_quote_evidence()
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
        "data": {"po_id": "PO-1", "vendor_id": "V-9"},
        "source_version": "po-v1",
        "coverage": {"complete": True, "known": True, "truncated": False}})
    invoice = new_step(
        step_id="invoice", title="Read invoice", operation_type="retrieve",
        adapter="document.read", inputs={}, effect="read_only")
    invoice.update(status="applied", operation_id="op-invoice", result={
        "data": {"invoice_id": "INV-1", "po_id": "PO-1", "quantity": "2",
                 "unit_price": "120.00", "freight": "30.00",
                 "currency": "USD"},
        "source_version": "inv-v1",
        "coverage": {"complete": True, "known": True, "truncated": False}})
    receiving = new_step(
        step_id="receiving", title="Read receiving",
        operation_type="retrieve", adapter="workbook.read",
        inputs={}, effect="read_only")
    receiving.update(status="applied", operation_id="op-receiving", result={
        "data": {"po_id": "PO-1", "received_quantity": "2"},
        "source_version": "rec-v1",
        "coverage": {"complete": True, "known": True, "truncated": False}})
    return po, invoice, receiving


def _verified_invoice_evidence():
    po, invoice, receiving = _invoice_evidence()
    for step, resource, version in (
            (po, "po-1", "po-v1"),
            (invoice, "invoice-1", "inv-v1"),
            (receiving, "receiving-1", "rec-v1")):
        step["result"]["resource_id"] = resource
        step["result"]["verification"] = {
            "status": "verified", "resource_id": resource,
            "version": version,
            "coverage": {"complete": True, "truncated": False}}
    return po, invoice, receiving


def _verified_invoice_evidence():
    po, invoice, receiving = _invoice_evidence()
    for step, resource_id, version in (
            (po, "po-1", "po-v1"),
            (invoice, "invoice-1", "inv-v1"),
            (receiving, "receiving-1", "rec-v1")):
        step["result"].update({
            "resource_id": resource_id,
            "source_version": version,
            "coverage": {"complete": True, "known": True,
                         "truncated": False},
            "verification": {
                "status": "verified", "resource_id": resource_id,
                "version": version, "coverage": {"complete": True}},
        })
    return po, invoice, receiving


def _invoice_request():
    return InvoiceReconciliationRequest(
        operation="invoice_reconciliation",
        invoice_step_id="invoice",
        purchase_order_step_id="po",
        receiving_step_id="receiving",
        reason="reconcile the corrected invoice against receiving")


def test_invoice_request_compiles_and_reconciles_full_evidence(env):
    po, invoice, receiving = _verified_invoice_evidence()
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
    read = _verified_quote_evidence()
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


def _term_assignment(read, *, terms=None, facts=None):
    teaching = new_teaching_snapshot(revision="term-test")
    if terms is not None:
        teaching["terms"] = terms
    return new_assignment(
        objective="Quote with bound terms", workspace_id="ws_assign",
        tenant_id="tenant_assign", teaching_snapshot=teaching,
        steps=[read], facts=facts or [],
        authorized_actions=["retrieve", "calculate"])


def test_money_terms_must_resolve_and_match_the_proposed_value():
    read = _verified_quote_evidence()
    assignment = _term_assignment(read, terms={
        "currency": "USD", "freight": "20.00", "tax_basis": "none"})
    missing = _quote_request().model_copy(update={
        "freight": MoneyTerm(value="20.00", authority_ref="missing-term")})
    with pytest.raises(WorkRequestCompileError, match="authority|resolve"):
        compile_work_request_patch(missing, assignment, context={})

    wrong_value = _quote_request().model_copy(update={
        "freight": MoneyTerm(value="21.00", authority_ref="freight")})
    with pytest.raises(WorkRequestCompileError, match="does not match"):
        compile_work_request_patch(wrong_value, assignment, context={})

    wrong_currency = _quote_request().model_copy(update={"currency": "EUR"})
    with pytest.raises(WorkRequestCompileError, match="currency"):
        compile_work_request_patch(wrong_currency, assignment, context={})

    missing_tax = _quote_request().model_copy(update={
        "tax": TaxTerm(basis="none", authority_ref="missing-tax")})
    with pytest.raises(WorkRequestCompileError, match="tax|authority|resolve"):
        compile_work_request_patch(missing_tax, assignment, context={})

    amount_tax = _quote_request().model_copy(update={
        "freight": MoneyTerm(value="0.00", authority_ref="freight"),
        "tax": TaxTerm(basis="amount", value="5.00",
                       authority_ref="tax_amount")})
    amount_assignment = _term_assignment(read, terms={
        "currency": "USD", "freight": "0.00", "tax_amount": "5.00"})
    assert compile_work_request_patch(
        amount_tax, amount_assignment, context={})["add_steps"]


def test_expired_fact_term_is_not_authority():
    read = _verified_quote_evidence()
    assignment = _term_assignment(read, terms={"currency": "USD"}, facts=[{
        "fact_id": "freight", "authority_ref": "freight",
        "value": "20.00", "evidence_state": "established",
        "source_refs": [{"resource_id": "agreement-1", "version": "v1"}],
        "validity": {"expires_at": "2020-01-01T00:00:00+00:00"},
    }])
    with pytest.raises(WorkRequestCompileError, match="expired"):
        compile_work_request_patch(_quote_request(), assignment, context={})


def _quote_assignment(teaching, read=None):
    return new_assignment(
        objective="Quote from accepted evidence",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", steps=[read or _verified_quote_evidence()],
        teaching_snapshot=teaching,
        authorized_actions=["retrieve", "calculate"])


def test_quote_money_terms_must_resolve_and_match_accepted_values():
    teaching = _terms_teaching()
    assignment = _quote_assignment(teaching)

    unknown = _quote_request().model_copy(update={
        "freight": MoneyTerm(value="20.00",
                             authority_ref="held-out agreement")})
    with pytest.raises(WorkRequestCompileError, match="authority|accepted"):
        compile_work_request_patch(unknown, assignment, context={})

    wrong_amount = _quote_request().model_copy(update={
        "freight": MoneyTerm(value="99.00", authority_ref="freight")})
    with pytest.raises(WorkRequestCompileError, match="does not match"):
        compile_work_request_patch(wrong_amount, assignment, context={})

    wrong_currency = _quote_request().model_copy(update={"currency": "CAD"})
    with pytest.raises(WorkRequestCompileError, match="currency"):
        compile_work_request_patch(wrong_currency, assignment, context={})

    no_tax_support = _terms_teaching()
    no_tax_support["terms"] = {
        "currency": "USD", "freight": "20.00",
        "tax_basis": "rate", "tax_rate": "0.10",
    }
    assignment = _quote_assignment(no_tax_support)
    with pytest.raises(WorkRequestCompileError, match="tax"):
        compile_work_request_patch(_quote_request(), assignment, context={})

    zero_teaching = _terms_teaching()
    zero_teaching["terms"] = {
        "currency": "USD", "freight": "0.00", "tax_basis": "none",
    }
    zero = _quote_request().model_copy(update={
        "freight": MoneyTerm(value="0.00", authority_ref="freight")})
    patch = compile_work_request_patch(
        zero, _quote_assignment(zero_teaching), context={})
    assert patch["add_steps"][1]["inputs"]["freight"] == "0.00"


def test_work_request_rejects_unverified_or_skipped_evidence():
    unverified = _quote_evidence()
    assignment = _quote_assignment(_terms_teaching(), read=unverified)
    with pytest.raises(WorkRequestCompileError, match="verified"):
        compile_work_request_patch(_quote_request(), assignment, context={})

    skipped = _verified_quote_evidence()
    skipped["status"] = "skipped"
    assignment = _quote_assignment(_terms_teaching(), read=skipped)
    with pytest.raises(WorkRequestCompileError, match="applied"):
        compile_work_request_patch(_quote_request(), assignment, context={})

    po, invoice, receiving = _invoice_evidence()
    invoice_assignment = new_assignment(
        objective="Reconcile", steps=[po, invoice, receiving],
        workspace_id="ws_assign", tenant_id="tenant_assign",
        authorized_actions=["retrieve", "calculate"])
    with pytest.raises(WorkRequestCompileError, match="verified"):
        compile_work_request_patch(
            _invoice_request(), invoice_assignment, context={})


def test_invoice_request_can_compile_one_approved_bill_action(env):
    from core.action_registry import action_registry

    calls = []

    async def create_bill(arguments, context):
        calls.append(dict(arguments))
        return {
            "status": "applied", "action_result": "applied",
            "provider_state": "accepted", "provider_ref": "bill-1",
            "remote_id": "bill-1",
            "verification": {"status": "verified"},
            "data": {"bill_id": "bill-1", "total": arguments.get("total")},
        }

    action_registry.register(
        "books.create_bill", create_bill,
        effects=[{"effect": "create", "object": "bill"}])
    po, invoice, receiving = _verified_invoice_evidence()
    teaching = new_teaching_snapshot(revision="invoice-terms-1")
    plan = new_assignment(
        objective="Prepare the supported bill",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", steps=[po, invoice, receiving],
        teaching_snapshot=teaching,
        authorized_actions=["retrieve", "calculate", "outbound"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = env["executor"].create_assignment(
        "conv-invoice-bill", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    assignment = env["lifecycle"].get_assignment(run_id)
    context = {
        "task_version": int(record["task_version"]),
        "plan_revision": int(assignment["plan_revision"]),
        "action_views": [{"action": "books.create_bill",
                          "effect": "external"}],
        "authorized_actions": ["outbound"],
    }
    request = _invoice_request().model_copy(update={
        "bill_action": "books.create_bill"})
    patch = compile_work_request_patch(
        request, assignment, context=context)
    assert patch["add_steps"][-1]["adapter"] == "action.registry"
    assert patch["add_steps"][-1]["effect"] == "external"
    assert patch["add_steps"][-1]["approval_required"] is True

    adopted = adopt_adaptation(
        env["lifecycle"], run_id,
        AdaptationProposal(
            decision="replan", reason="prepare one supported bill",
            observation_ids=["invoice-bill-1"], work_request=request))
    assert adopted["status"] == "applied"
    waiting = _run(env["executor"].execute(run_id))
    assert waiting["assignment"]["status"] == "waiting", waiting
    env["executor"].approve_step(
        run_id, patch["add_steps"][-1]["step_id"], approved_by="owner")
    completed = _run(env["executor"].execute(run_id))
    assert completed["assignment"]["status"] == "completed", completed
    assert len(calls) == 1
    assert calls[0]["total"] == "270.00"
    assert calls[0]["vendor_id"] == "V-9"


def test_invoice_role_bindings_resolve_from_evidence_shape():
    """The model names the operation; the compiler resolves mechanical roles.

    Accepting a model's arbitrary step ordering would bind invoice data as a
    purchase order. The compiler resolves each role from the accepted
    structured fields and records the corrected binding.
    """
    po, invoice, receiving = _verified_invoice_evidence()
    assignment = new_assignment(
        objective="Reconcile the invoice",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", steps=[po, invoice, receiving],
        authorized_actions=["retrieve", "calculate"])
    request = _invoice_request().model_copy(update={
        "invoice_step_id": "po",
        "purchase_order_step_id": "receiving",
        "receiving_step_id": "invoice",
    })
    patch = compile_work_request_patch(request, assignment, context={})
    reconcile = patch["add_steps"][0]
    assert reconcile["inputs"]["invoice"] == "${invoice.data}"
    assert reconcile["inputs"]["purchase_order"] == "${po.data}"
    assert reconcile["inputs"]["receiving"] == "${receiving.data}"
    assert reconcile["depends_on"] == ["invoice", "po", "receiving"]
    assert {
        "kind": "resolved_invoice_evidence",
        "invoice_step_id": "invoice",
        "purchase_order_step_id": "po",
        "receiving_step_id": "receiving",
    } in patch["observations"]
