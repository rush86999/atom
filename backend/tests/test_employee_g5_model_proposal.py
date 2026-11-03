"""G5 seam: served-model work_request compiled through the existing patch."""
from __future__ import annotations

import asyncio
from decimal import Decimal

from core.assignment_plan import (
    new_assignment, new_step, new_teaching_snapshot, step_by_id,
)
import core.assignment_quote  # noqa: F401,E402
import core.quote_rows  # noqa: F401,E402
from core.employee_adaptation import (
    WorkAdaptationProposal,
    adopt_adaptation,
    propose_adaptation,
)
from core.employee_proposal import context_from_record
from core.employee_work_requests import (
    MoneyTerm, QuoteCalculationRequest, TaxTerm,
)
from tests.test_assignment_executor import env  # noqa: F401


def _run(coro):
    return asyncio.run(coro)


def _assignment_with_evidence(env):
    read = new_step(
        step_id="read", title="Read held-out quote rows",
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
        "resource_id": "heldout:prices",
        "verification": {
            "status": "verified", "resource_id": "heldout:prices",
            "version": "heldout-v1",
            "coverage": {"complete": True, "truncated": False}},
    }
    teaching = new_teaching_snapshot(revision="g5-seam-terms-1")
    teaching["terms"] = {
        "currency": "USD", "freight": "20.00", "tax_basis": "none",
    }
    plan = new_assignment(
        objective="Quote the held-out customer request",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", teaching_snapshot=teaching,
        steps=[read], authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = env["executor"].create_assignment(
        "conv-g5-model", "Quote the held-out customer request",
        assignment=plan)
    return record["run_id"]


def _work_request():
    return QuoteCalculationRequest(
        operation="quote_calculation",
        source_step_id="read",
        columns={"item_id": "Item", "quantity": "Qty",
                 "unit_price": "Price", "currency": "Currency"},
        currency="USD",
        freight=MoneyTerm(value="20.00", authority_ref="freight"),
        tax=TaxTerm(basis="none", authority_ref="tax_basis"),
        reason="compute the exact total from the accepted rows")


def test_model_proposed_work_request_is_compiled_and_executed(env):
    run_id = _assignment_with_evidence(env)
    record = env["lifecycle"].get_task(run_id)
    context = context_from_record(
        record,
        adapter_views=[
            {"adapter": "quote.lines_from_rows", "effect": "local",
             "operation_type": "calculate",
             "required_actions": ["calculate"]},
            {"adapter": "quote.calculate", "effect": "local",
             "operation_type": "calculate",
             "required_actions": ["calculate"]},
        ])
    assert context["work_request_schemas"]
    assert context["stage"] == "follow_up"

    class FakeLLM:
        def __init__(self):
            self.kwargs = {}

        async def generate_structured_response(self, **kwargs):
            self.kwargs = kwargs
            return WorkAdaptationProposal(
                decision="replan",
                reason=(
                    "The accepted rows and taught terms support an exact "
                    "quote calculation."),
                observation_ids=["evidence-read-1"],
                work_request=_work_request())

    fake = FakeLLM()
    proposal = _run(propose_adaptation(
        context,
        [{"observation_id": "evidence-read-1",
          "kind": "evidence_result",
          "step_id": "read",
          "reason": "the authorized read completed"}],
        assignment=record["assignment"], llm_service=fake))
    assert proposal["source"] == "model"
    assert fake.kwargs["response_model"] is WorkAdaptationProposal
    assert fake.kwargs["output_mode"] == "json"
    assert fake.kwargs["cascade"] is False
    assert fake.kwargs["allow_moa"] is False
    prompt = fake.kwargs["prompt"]
    shape = prompt.split("Return JSON only with this shape: ", 1)[1].split(
        ".\n", 1)[0]
    assert "step_ids" not in shape and "facts" not in shape
    assert "work_request_schemas" in prompt
    assert '"operation": "quote_calculation"' in prompt

    adopted = adopt_adaptation(
        env["lifecycle"], run_id, proposal["proposal"])
    assert adopted["status"] == "applied"
    assert adopted["work_request"]["operation"] == "quote_calculation"
    status = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    calculated = step_by_id(
        assignment, adopted["compiled"]["step_ids"][1])
    assert calculated["status"] == "applied"
    assert Decimal(str(calculated["result"]["value"])) == Decimal("370.00")
    assert status["assignment"]["status"] == "completed"


def test_followup_transport_contract_and_repair_feedback(env):
    run_id = _assignment_with_evidence(env)
    record = env["lifecycle"].get_task(run_id)
    context = context_from_record(record)

    class RepairingFake:
        def __init__(self):
            self.calls = []

        async def generate_structured_response(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return WorkAdaptationProposal(
                    decision="replan",
                    reason="first attempt binds a missing evidence step",
                    observation_ids=["evidence-read-1"],
                    work_request=_work_request().model_copy(
                        update={"source_step_id": "absent"}))
            return WorkAdaptationProposal(
                decision="replan",
                reason="repaired request binds the accepted read",
                observation_ids=["evidence-read-1"],
                work_request=_work_request())

    fake = RepairingFake()
    proposal = _run(propose_adaptation(
        context,
        [{"observation_id": "evidence-read-1",
          "kind": "evidence_result", "step_id": "read"}],
        assignment=record["assignment"], llm_service=fake))
    assert proposal["source"] == "model_repaired", proposal
    assert len(fake.calls) == 2
    assert all(
        call["response_model"] is WorkAdaptationProposal
        for call in fake.calls)
    first, second = fake.calls
    shape = first["prompt"].split(
        "Return JSON only with this shape: ", 1)[1].split(".\n", 1)[0]
    assert "step_ids" not in shape and "facts" not in shape
    assert '"operation": "quote_calculation"' in first["prompt"]
    assert '"operation": "invoice_reconciliation"' in first["prompt"]
    assert "previous proposal was invalid" in second["prompt"]
    assert "absent" in second["prompt"]
    assert proposal["repair"]["first_errors"]
