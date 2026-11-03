"""Proof, term-scope and adoption controls for typed work requests."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from core.assignment_plan import (
    new_assignment,
    new_step,
    new_teaching_snapshot,
    step_by_id,
)
from core.employee_adaptation import AdaptationProposal, adopt_adaptation
from core.employee_patch import PlanPatchError
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
from tests.test_employee_work_requests import (
    _invoice_request,
    _quote_evidence,
    _quote_request,
    _verified_quote_evidence,
)
from tests.test_assignment_executor import env  # noqa: F401


def _teaching(**terms):
    snapshot = new_teaching_snapshot(revision="bindings-terms-1")
    snapshot["terms"] = terms
    return snapshot


def _assignment(read, *, facts=None, terms=None):
    return new_assignment(
        objective="Bind typed work to accepted evidence and terms",
        workspace_id="ws_assign", tenant_id="tenant_assign",
        teaching_snapshot=_teaching(
            **(terms or {"currency": "USD", "freight": "0.00",
                         "tax_basis": "none"})),
        steps=[read], facts=facts or [],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])


@pytest.mark.parametrize("field,value", [
    ("require_verified_source", False),
    ("require_verified_source", True),
    ("require_verified_source", None),
    ("require_verified_evidence", 0),
    ("require_verified_evidence", "false"),
    ("unknown_field", "x"),
])
def test_model_payload_cannot_carry_proof_switches(field, value):
    payload = _quote_request().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        QuoteCalculationRequest.model_validate(payload)

    invoice_payload = _invoice_request().model_dump()
    invoice_payload[field] = value
    with pytest.raises(ValidationError):
        InvoiceReconciliationRequest.model_validate(invoice_payload)


def test_unverified_and_skipped_evidence_are_not_proof():
    read = _quote_evidence()
    assignment = _assignment(read)
    with pytest.raises(WorkRequestCompileError, match="verified proof"):
        compile_work_request_patch(_quote_request(), assignment, context={})

    read["status"] = "skipped"
    read["result"].update({
        "verification": {
            "status": "verified", "resource_id": "heldout-prices",
            "version": "heldout-v1"},
    })
    skipped_assignment = _assignment(read)
    with pytest.raises(WorkRequestCompileError, match="not applied"):
        compile_work_request_patch(
            _quote_request(), skipped_assignment, context={})


def test_compiled_steps_keep_mandatory_verified_receipts():
    assignment = new_assignment(
        objective="verified quote", workspace_id="ws_assign",
        tenant_id="tenant_assign", teaching_snapshot=_teaching(
            currency="USD", freight="20.00", tax_basis="none"),
        steps=[_verified_quote_evidence()],
        authorized_actions=["retrieve", "calculate"])
    patch = compile_work_request_patch(_quote_request(), assignment, context={})
    assert patch["add_steps"][0]["requires"] == [{
        "kind": "receipt", "step_id": "read", "require": "verified"}]
    assert patch["add_steps"][1]["requires"] == []


def test_executor_negative_preserves_independent_progress(env):
    read = _quote_evidence()
    independent = new_step(
        step_id="independent", title="Already completed independent work",
        operation_type="retrieve", adapter="workbook.read", inputs={},
        effect="read_only")
    independent["status"] = "applied"
    independent["operation_id"] = "op-independent"
    independent["result"] = {"rows": [{"Item": "X", "Qty": 1,
                                       "Price": 1, "Currency": "USD"}]}
    plan = _assignment(read)
    plan["steps"] = [independent, read]
    record = env["executor"].create_assignment(
        "conv-proof-negative", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    before = env["lifecycle"].get_assignment(run_id)
    with pytest.raises(PlanPatchError, match="verified proof"):
        adopt_adaptation(
            env["lifecycle"], run_id,
            AdaptationProposal(
                decision="replan", reason="unverified work",
                observation_ids=["proof-negative-1"],
                work_request=_quote_request()))
    after = env["lifecycle"].get_assignment(run_id)
    assert after["plan_revision"] == before["plan_revision"]
    assert [s["step_id"] for s in after["steps"]] == ["independent", "read"]
    assert step_by_id(after, "independent")["status"] == "applied"
    assert env["lifecycle"].get_task(run_id).get("task_version") == (
        record["task_version"])


def test_valid_twin_still_compiles_and_completes(env):
    assignment = new_assignment(
        objective="verified twin", workspace_id="ws_assign",
        tenant_id="tenant_assign", teaching_snapshot=_teaching(
            currency="USD", freight="20.00", tax_basis="none"),
        steps=[_verified_quote_evidence()],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = env["executor"].create_assignment(
        "conv-proof-positive", assignment["objective"], assignment=assignment)
    run_id = record["run_id"]
    adopted = adopt_adaptation(
        env["lifecycle"], run_id,
        AdaptationProposal(
            decision="replan", reason="verified work",
            observation_ids=["proof-positive-1"],
            work_request=_quote_request()))
    assert adopted["status"] == "applied"


def _term_request(**updates):
    return _quote_request().model_copy(update=updates)


def test_term_must_resolve_scope_revision_currency_and_value():
    read = _verified_quote_evidence()
    assignment = _assignment(
        read, terms={"currency": "USD", "freight": "20.00",
                     "tax_basis": "none"})

    with pytest.raises(WorkRequestCompileError, match="not an accepted"):
        compile_work_request_patch(
            _term_request(freight=MoneyTerm(
                value="20.00", authority_ref="missing")),
            assignment, context={})

    with pytest.raises(WorkRequestCompileError, match="does not match"):
        compile_work_request_patch(
            _term_request(freight=MoneyTerm(
                value="21.00", authority_ref="freight")),
            assignment, context={})

    with pytest.raises(WorkRequestCompileError, match="currency"):
        compile_work_request_patch(
            _term_request(currency="EUR"), assignment, context={})

    with pytest.raises(WorkRequestCompileError, match="tax|not an accepted"):
        compile_work_request_patch(
            _term_request(tax=TaxTerm(
                basis="none", authority_ref="missing-tax")),
            assignment, context={})

    wrong_none = _assignment(
        read, terms={"currency": "USD", "freight": "20.00",
                     "tax_basis": "0.07"})
    with pytest.raises(WorkRequestCompileError, match="not supported"):
        compile_work_request_patch(_quote_request(), wrong_none, context={})

    zero = _assignment(
        read, terms={"currency": "USD", "freight": "0.00",
                     "tax_basis": "0.00"})
    patch = compile_work_request_patch(
        _term_request(freight=MoneyTerm(
            value="0.00", authority_ref="freight")),
        zero, context={})
    assert patch["add_steps"][1]["inputs"]["freight"] == "0.00"


def test_rate_and_amount_tax_modes_bind_their_taught_term():
    read = _verified_quote_evidence()
    rate_assignment = _assignment(
        read, terms={"currency": "USD", "freight": "20.00",
                     "tax_rate": "0.07"})
    patch = compile_work_request_patch(
        _term_request(tax=TaxTerm(
            basis="rate", value="0.07", authority_ref="tax_rate")),
        rate_assignment, context={})
    assert patch["add_steps"][1]["inputs"]["tax"]["rate"] == "0.07"

    amount_assignment = _assignment(
        read, terms={"currency": "USD", "freight": "20.00",
                     "tax_amount": "5.00"})
    patch = compile_work_request_patch(
        _term_request(tax=TaxTerm(
            basis="amount", value="5.00", authority_ref="tax_amount")),
        amount_assignment, context={})
    assert patch["add_steps"][1]["inputs"]["tax"]["amount"] == "5.00"

    with pytest.raises(WorkRequestCompileError, match="does not match"):
        compile_work_request_patch(
            _term_request(tax=TaxTerm(
                basis="rate", value="0.08", authority_ref="tax_rate")),
            rate_assignment, context={})


def test_fact_term_scope_revision_dates_and_currency():
    read = _verified_quote_evidence()
    base_fact = {
        "fact_id": "freight", "value": "20.00",
        "evidence_state": "established",
        "source_refs": [{"resource_id": "agreement-1", "version": "v1"}],
        "authority_ref": "freight",
        "validity": {"currency": "USD"},
    }
    assignment = _assignment(read, terms={"currency": "USD",
                                          "tax_basis": "none"},
                             facts=[base_fact])
    patch = compile_work_request_patch(_quote_request(), assignment, context={})
    assert patch["add_steps"][1]["inputs"]["term_receipt"]["freight"][
        "source"] == "fact"

    expired = dict(base_fact, validity={
        "currency": "USD", "expires_at": "2020-01-01T00:00:00+00:00"})
    with pytest.raises(WorkRequestCompileError, match="expired"):
        compile_work_request_patch(
            _quote_request(), _assignment(
                read, terms={"currency": "USD", "tax_basis": "none"},
                facts=[expired]), context={})

    future = dict(base_fact, validity={
        "currency": "USD", "effective_from": "2999-01-01T00:00:00+00:00"})
    with pytest.raises(WorkRequestCompileError, match="not yet effective"):
        compile_work_request_patch(
            _quote_request(), _assignment(
                read, terms={"currency": "USD", "tax_basis": "none"},
                facts=[future]), context={})

    wrong_scope = dict(base_fact, validity={
        "currency": "USD", "scope": {"workspace_id": "other-ws"}})
    with pytest.raises(WorkRequestCompileError, match="scope"):
        compile_work_request_patch(
            _quote_request(), _assignment(
                read, terms={"currency": "USD", "tax_basis": "none"},
                facts=[wrong_scope]), context={})

    wrong_revision = dict(base_fact, validity={
        "currency": "USD", "teaching_revision": "old-teaching"})
    with pytest.raises(WorkRequestCompileError, match="teaching revision"):
        compile_work_request_patch(
            _quote_request(), _assignment(
                read, terms={"currency": "USD", "tax_basis": "none"},
                facts=[wrong_revision]), context={})

    wrong_currency = dict(base_fact, validity={"currency": "EUR"})
    with pytest.raises(WorkRequestCompileError, match="denominated"):
        compile_work_request_patch(
            _quote_request(), _assignment(
                read, terms={"currency": "USD", "tax_basis": "none"},
                facts=[wrong_currency]), context={})

    invalid_date = dict(base_fact, validity={
        "currency": "USD", "expires_at": "not-a-date"})
    with pytest.raises(WorkRequestCompileError, match="invalid validity"):
        compile_work_request_patch(
            _quote_request(), _assignment(
                read, terms={"currency": "USD", "tax_basis": "none"},
                facts=[invalid_date]), context={})


def test_term_provenance_is_revalidated_at_consumption():
    import asyncio

    from core.assignment_executor import NeedsContext
    from core.assignment_quote import _quote_calculate

    assignment = _assignment(
        _verified_quote_evidence(),
        terms={"currency": "USD", "freight": "20.00", "tax_basis": "none"})
    patch = compile_work_request_patch(_quote_request(), assignment, context={})
    inputs = patch["add_steps"][1]["inputs"]
    inputs["line_items"] = [{
        "item_id": "A", "quantity": "2", "unit_price": "100",
        "unit": "each", "pack_size": "1", "price_basis": "list",
        "currency": "USD"}]

    result = asyncio.run(_quote_calculate(dict(inputs), {}))
    assert result["value"] == "220.00"
    assert result["term_receipt"]["freight"]["value"] == "20.00"

    forged = dict(inputs, freight="19.00")
    with pytest.raises(NeedsContext):
        asyncio.run(_quote_calculate(forged, {}))

    stripped = dict(inputs)
    stripped.pop("term_receipt", None)
    result = asyncio.run(_quote_calculate(stripped, {}))
    # Direct callers that predate typed work keep their contract; the typed
    # compiler always supplies the receipt, and a forged one is refused.
    assert result["value"] == "220.00"
