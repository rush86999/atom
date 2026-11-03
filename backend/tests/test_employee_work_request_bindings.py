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
    assert not env["lifecycle"].get_task(run_id).get("operations")


def test_valid_twin_still_compiles_and_completes(env):
    import asyncio

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
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed"
    final = env["lifecycle"].get_assignment(run_id)
    calc = step_by_id(final, adopted["compiled"]["step_ids"][1])
    assert Decimal(str(calc["result"]["value"])) == Decimal("370.00")


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
    with pytest.raises(
            WorkRequestCompileError, match="no-tax decision|not supported"):
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


def test_role_comparison_is_normalized_and_cross_field_is_refused():
    read = _verified_quote_evidence()
    aliased = _assignment(read, terms={
        "currency": "USD",
        "freight": {"value": "20.00", "role": "freight_amount"},
        "tax_basis": "none",
    })
    patch = compile_work_request_patch(_quote_request(), aliased, context={})
    receipt = patch["add_steps"][1]["inputs"]["term_receipt"]
    assert receipt["freight"]["role"] == "freight_amount"

    # A tax-rate term is a fraction, not money; it cannot authorize freight
    # even when its numeric value happens to equal a plausible freight amount.
    wrong_field = _assignment(read, terms={
        "currency": "USD", "tax_rate": "0.07", "tax_basis": "none"})
    with pytest.raises(WorkRequestCompileError, match="freight"):
        compile_work_request_patch(
            _term_request(freight=MoneyTerm(
                value="0.07", authority_ref="tax_rate")),
            wrong_field, context={})

    # Nor can a freight amount authorize the tax rate.
    with pytest.raises(WorkRequestCompileError, match="tax rate"):
        compile_work_request_patch(
            _term_request(tax=TaxTerm(
                basis="rate", value="0.07", authority_ref="freight")),
            _assignment(read, terms={
                "currency": "USD", "freight": "20.00",
                "tax_rate": "0.07"}), context={})


@pytest.mark.parametrize("mutation", [
    "expired",
    "stale",
    "wrong_scope",
    "value_changed",
])
def test_executor_rechecks_the_term_after_restart(env, mutation):
    import asyncio

    from core.assignment_executor import AssignmentExecutor

    fact = {
        "fact_id": "freight", "value": "20.00",
        "evidence_state": "established",
        "source_refs": [{"resource_id": "agreement-1", "version": "v1"}],
        "authority_ref": "freight",
        "validity": {
            "currency": "USD",
            "expires_at": "2999-01-01T00:00:00+00:00",
        },
    }
    assignment = _assignment(
        _verified_quote_evidence(),
        terms={"currency": "USD", "tax_basis": "none"},
        facts=[fact])
    record = env["executor"].create_assignment(
        f"conv-term-{mutation}", assignment["objective"],
        assignment=assignment)
    run_id = record["run_id"]
    adopted = adopt_adaptation(
        env["lifecycle"], run_id,
        AdaptationProposal(
            decision="replan", reason="compile against the accepted term",
            observation_ids=[f"term-{mutation}-1"],
            work_request=_quote_request()))
    assert adopted["status"] == "applied", adopted
    calc_id = adopted["compiled"]["step_ids"][1]

    def drift(record, current):
        for item in current.get("facts") or []:
            if item.get("fact_id") != "freight":
                continue
            if mutation == "expired":
                item["validity"]["expires_at"] = (
                    "2020-01-01T00:00:00+00:00")
            elif mutation == "stale":
                item["evidence_state"] = "stale"
            elif mutation == "wrong_scope":
                item["validity"]["scope"] = {"workspace_id": "other-ws"}
            else:
                item["value"] = "25.00"
        return current, None

    env["lifecycle"].mutate_assignment(
        run_id, drift, rationale=f"test term {mutation}")
    # A fresh executor is the restart boundary: no in-memory authority from
    # compilation survives, only the current persisted assignment does.
    restarted = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"].clone())
    result = asyncio.run(restarted.execute(run_id))
    final = env["lifecycle"].get_assignment(run_id)
    assert step_by_id(final, calc_id)["status"] != "applied"
    assert result["assignment"]["status"] != "completed"
    assert result["assignment"]["status"] in ("blocked", "waiting"), result


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

    context = {
        "assignment": assignment,
        "teaching": assignment.get("teaching_snapshot") or {},
        "facts": assignment.get("facts") or [],
    }
    result = asyncio.run(_quote_calculate(dict(inputs), context))
    assert result["value"] == "220.00"
    assert result["term_receipt"]["freight"]["value"] == "20.00"

    forged = dict(inputs, freight="19.00")
    with pytest.raises(NeedsContext):
        asyncio.run(_quote_calculate(forged, context))

    stripped = dict(inputs)
    stripped.pop("term_receipt", None)
    result = asyncio.run(_quote_calculate(stripped, {}))
    # Direct callers that predate typed work keep their contract; the typed
    # compiler always supplies the receipt, and a forged one is refused.
    assert result["value"] == "220.00"


def test_money_term_roles_are_not_interchangeable():
    read = _verified_quote_evidence()
    assignment = _assignment(
        read, terms={
            "currency": "USD", "freight": "20.00", "tax_rate": "0.07",
            "tax_amount": "5.00", "tax_basis": "none"})

    cases = [
        _term_request(freight=MoneyTerm(
            value="0.07", authority_ref="tax_rate")),
        _term_request(freight=MoneyTerm(
            value="5.00", authority_ref="tax_amount")),
        _term_request(tax=TaxTerm(
            basis="rate", value="0.07", authority_ref="freight")),
        _term_request(tax=TaxTerm(
            basis="amount", value="5.00", authority_ref="freight")),
        _term_request(tax=TaxTerm(
            basis="none", authority_ref="tax_rate")),
        _term_request(freight=MoneyTerm(
            value="USD", authority_ref="currency")),
    ]
    for request in cases:
        with pytest.raises(WorkRequestCompileError, match="role"):
            compile_work_request_patch(request, assignment, context={})


def test_explicit_role_metadata_and_aliases_are_trusted():
    read = _verified_quote_evidence()
    teaching = new_teaching_snapshot(revision="role-meta-1")
    teaching["terms"] = {
        "currency": {"value": "USD", "role": "currency"},
        "delivery": {
            "value": "20.00", "role": "freight_amount", "currency": "USD"},
        "tax_basis": {"value": "none", "role": "tax_exemption"},
    }
    assignment = new_assignment(
        objective="role metadata", workspace_id="ws_assign",
        tenant_id="tenant_assign", teaching_snapshot=teaching,
        steps=[read], authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])
    request = _term_request(freight=MoneyTerm(
        value="20.00", authority_ref="delivery"))
    patch = compile_work_request_patch(request, assignment, context={})
    receipt = patch["add_steps"][1]["inputs"]["term_receipt"]
    assert receipt["freight"]["role"] == "freight_amount"
    assert receipt["freight"]["dimension"] == "money"
    assert receipt["tax"]["role"] == "tax_exemption"

    teaching["terms"]["delivery"] = {
        "value": "20.00", "role": "mystery_role"}
    broken = new_assignment(
        objective="unknown role", workspace_id="ws_assign",
        tenant_id="tenant_assign", teaching_snapshot=teaching,
        steps=[read], authorized_actions=["retrieve", "calculate"])
    with pytest.raises(
            WorkRequestCompileError, match="unknown semantic role"):
        compile_work_request_patch(request, broken, context={})


def test_fact_role_must_be_declared_and_match_the_field():
    read = _verified_quote_evidence()
    fact = {
        "fact_id": "delivery", "value": "20.00",
        "evidence_state": "established",
        "source_refs": [{"resource_id": "agreement-1", "version": "v1"}],
        "authority_ref": "delivery",
        "validity": {"currency": "USD", "role": "freight_amount"},
    }
    assignment = _assignment(
        read, terms={"currency": "USD", "tax_basis": "none"},
        facts=[fact])
    request = _term_request(freight=MoneyTerm(
        value="20.00", authority_ref="delivery"))
    patch = compile_work_request_patch(request, assignment, context={})
    assert patch["add_steps"][1]["inputs"]["term_receipt"][
        "freight"]["source"] == "fact"

    untyped = dict(fact, fact_id="delivery", authority_ref="delivery",
                   validity={"currency": "USD"})
    with pytest.raises(
            WorkRequestCompileError, match="no declared semantic role"):
        compile_work_request_patch(
            request, _assignment(
                read, terms={"currency": "USD", "tax_basis": "none"},
                facts=[untyped]), context={})


def test_expiry_between_compile_and_consumption_refuses():
    import asyncio

    from datetime import datetime, timezone
    from unittest.mock import patch

    from core.assignment_executor import NeedsContext
    from core.assignment_quote import _quote_calculate

    fact = {
        "fact_id": "freight", "value": "20.00",
        "evidence_state": "established",
        "source_refs": [{"resource_id": "agreement-1", "version": "v1"}],
        "authority_ref": "freight",
        "validity": {
            "currency": "USD", "expires_at": "2020-01-01T00:00:00+00:00"},
    }
    assignment = _assignment(
        _verified_quote_evidence(),
        terms={"currency": "USD", "tax_basis": "none"}, facts=[fact])

    class Earlier(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2019, 1, 1, tzinfo=timezone.utc)

    with patch('core.employee_work_compiler.datetime', Earlier):
        inputs = compile_work_request_patch(
            _term_request(), assignment, context={})["add_steps"][1][
                "inputs"]
    inputs["line_items"] = [{
        "item_id": "A", "quantity": "2", "unit_price": "100",
        "unit": "each", "pack_size": "1", "price_basis": "list",
        "currency": "USD"}]
    context = {
        "assignment": assignment,
        "teaching": assignment.get("teaching_snapshot") or {},
        "facts": assignment.get("facts") or [],
    }
    with pytest.raises(NeedsContext):
        asyncio.run(_quote_calculate(inputs, context))


def test_source_replacement_and_teaching_revision_refuse_at_consumption():
    import asyncio
    import copy

    from core.assignment_executor import NeedsContext
    from core.assignment_quote import _quote_calculate

    fact = {
        "fact_id": "freight", "value": "20.00",
        "evidence_state": "established",
        "source_refs": [{"resource_id": "agreement-1", "version": "v1"}],
        "authority_ref": "freight",
        "validity": {"currency": "USD", "expires_at": "2999-01-01T00:00:00+00:00"},
    }
    assignment = _assignment(
        _verified_quote_evidence(),
        terms={"currency": "USD", "tax_basis": "none"}, facts=[fact])
    inputs = compile_work_request_patch(
        _term_request(), assignment, context={})["add_steps"][1]["inputs"]
    inputs["line_items"] = [{
        "item_id": "A", "quantity": "2", "unit_price": "100",
        "unit": "each", "pack_size": "1", "price_basis": "list",
        "currency": "USD"}]

    replaced = copy.deepcopy(assignment)
    replaced["facts"][0]["source_refs"] = [
        {"resource_id": "agreement-1", "version": "v2"}]
    with pytest.raises(NeedsContext):
        asyncio.run(_quote_calculate(inputs, {
            "assignment": replaced,
            "teaching": replaced.get("teaching_snapshot") or {},
            "facts": replaced.get("facts") or [],
        }))

    newer_teaching = copy.deepcopy(assignment)
    newer_teaching["teaching_snapshot"]["revision"] = "new-lesson-2"
    with pytest.raises(NeedsContext):
        asyncio.run(_quote_calculate(inputs, {
            "assignment": newer_teaching,
            "teaching": newer_teaching.get("teaching_snapshot") or {},
            "facts": newer_teaching.get("facts") or [],
        }))


def test_binding_survives_a_restart_context_round_trip():
    import asyncio
    import json

    from core.assignment_quote import _quote_calculate

    assignment = _assignment(
        _verified_quote_evidence(),
        terms={"currency": "USD", "freight": "20.00", "tax_basis": "none"})
    inputs = compile_work_request_patch(
        _term_request(), assignment, context={})["add_steps"][1]["inputs"]
    inputs["line_items"] = [{
        "item_id": "A", "quantity": "2", "unit_price": "100",
        "unit": "each", "pack_size": "1", "price_basis": "list",
        "currency": "USD"}]
    restored = json.loads(json.dumps(assignment, default=str))
    result = asyncio.run(_quote_calculate(inputs, {
        "assignment": restored,
        "teaching": restored.get("teaching_snapshot") or {},
        "facts": restored.get("facts") or [],
    }))
    assert result["value"] == "220.00"


def test_executor_blocks_expired_term_between_compile_and_dispatch(env):
    import asyncio

    fact = {
        "fact_id": "freight", "value": "20.00",
        "evidence_state": "established",
        "source_refs": [{"resource_id": "agreement-1", "version": "v1"}],
        "authority_ref": "freight",
        "validity": {"currency": "USD", "expires_at": "2999-01-01T00:00:00+00:00"},
    }
    assignment = _assignment(
        _verified_quote_evidence(),
        terms={"currency": "USD", "tax_basis": "none"}, facts=[fact])
    record = env["executor"].create_assignment(
        "conv-term-expiry", assignment["objective"], assignment=assignment)
    run_id = record["run_id"]
    adopted = adopt_adaptation(
        env["lifecycle"], run_id,
        AdaptationProposal(
            decision="replan", reason="valid term at compile",
            observation_ids=["term-expiry-1"], work_request=_term_request()))
    assert adopted["status"] == "applied"

    def expire(record, current):
        updated = dict(current)
        updated["facts"] = [{
            **fact,
            "validity": {
                "currency": "USD",
                "expires_at": "2020-01-01T00:00:00+00:00"},
        }]
        return updated, {}

    env["lifecycle"].mutate_assignment(
        run_id, expire, rationale="authority expired before dispatch")
    result = asyncio.run(env["executor"].execute(run_id))
    final = env["lifecycle"].get_assignment(run_id)
    calc = step_by_id(final, adopted["compiled"]["step_ids"][1])
    assert calc["status"] != "applied"
    assert not (calc.get("result") or {}).get("value")
    assert result["assignment"]["status"] != "completed"
