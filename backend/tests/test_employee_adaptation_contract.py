"""Production-boundary contract and capture controls for adaptation calls."""
from __future__ import annotations

import asyncio
import time

import pytest
from pydantic import ValidationError

from core.assignment_plan import new_assignment
from core.employee_adaptation import (
    AdaptationProposal,
    WorkAdaptationProposal,
    propose_adaptation,
)
from core.employee_attempt_journal import AttemptJournal
from core.employee_proposal import ClarificationProposal
from core.employee_work_requests import (
    MoneyTerm,
    QuoteCalculationRequest,
    TaxTerm,
    work_request_schemas,
)


def _context(step_id="read"):
    return {
        "identity": {"workspace_id": "ws_assign", "tenant_id": "tenant_assign"},
        "work_request_schemas": work_request_schemas(),
        "available_business_operations": [
            "quote_calculation", "invoice_reconciliation"],
        "rules": {"evidence_only": False},
    }


def _assignment():
    return new_assignment(
        objective="Quote the accepted population",
        workspace_id="ws_assign", tenant_id="tenant_assign")


class CapturingLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def generate_structured_response(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class MalformedCompletion(Exception):
    def __init__(self, raw: str, validation_error: Exception | None = None):
        super().__init__("InstructorRetryException: validation error")
        message = type("Message", (), {"content": raw})
        choice = type("Choice", (), {"message": message})
        completion = type("Completion", (), {"choices": [choice]})
        failed = type(
            "FailedAttempt", (),
            {"completion": completion, "exception": validation_error})
        self.failed_attempts = [failed]
        self.last_completion = completion


def _validation_error():
    try:
        QuoteCalculationRequest.model_validate({
            "operation": "quote_calculation",
            "source_step_id": "",
        })
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a validation error")


def test_final_transport_request_uses_the_selected_schema():
    llm = CapturingLLM([
        WorkAdaptationProposal(
            decision="clarify", reason="currency is missing",
            clarification=ClarificationProposal(
                question="Which currency governs the quote?",
                concept="currency", unblocks="quote calculation")),
    ])
    result = asyncio.run(propose_adaptation(
        _context(), [{"observation_id": "o-1",
                      "kind": "evidence_result"}],
        assignment=_assignment(), llm_service=llm))
    assert result["source"] == "model"
    assert result["proposal"]["decision"] == "clarify"
    kwargs = llm.calls[0]
    assert kwargs["response_model"] is WorkAdaptationProposal
    prompt = kwargs["prompt"]
    assert "Return JSON only with this shape: {decision, reason, " \
           "observation_ids, work_request, clarification}." in prompt
    assert "step_ids" not in prompt
    assert "new_steps" not in prompt
    assert "quote_calculation" in prompt
    assert "invoice_reconciliation" in prompt
    schema = kwargs["response_model"].model_json_schema()
    assert set(schema["properties"]) == {
        "decision", "reason", "observation_ids", "work_request",
        "clarification"}
    assert "work_request" in schema["properties"]


def test_raw_malformed_completion_is_preserved_under_one_attempt():
    raw = '{"decision":"replan","new_steps":[{"step_id":"quote-total"}]}'
    exc = MalformedCompletion(raw, _validation_error())
    journal = AttemptJournal()
    result = asyncio.run(propose_adaptation(
        _context(), [{"observation_id": "o-2",
                      "kind": "evidence_result"}],
        assignment=_assignment(), llm_service=CapturingLLM([exc]),
        attempt_journal=journal))
    assert result["source"] == "deterministic"
    assert result["failure_stage"] == "initial"
    assert any("malformed_structured_output" in str(e)
               for e in result["errors"])
    attempt_ids = {event["attempt_id"] for event in journal.events}
    assert len(attempt_ids) == 1
    dispatch = [e for e in journal.events if e["event"] == "dispatch"]
    assert dispatch and dispatch[0]["response_model"] == (
        "WorkAdaptationProposal")
    assert "step_ids" not in dispatch[0]["prompt"]
    failure = [e for e in journal.events if e["event"] == "failure"]
    assert failure
    assert failure[0]["kind"] == "malformed_structured_output"
    assert failure[0]["call_stage"] == "initial"
    assert any(raw in item for item in failure[0]["raw_completions"])
    assert failure[0]["validation_errors"]


def test_bounded_repair_shares_deadline_and_selected_schema():
    llm = CapturingLLM([
        WorkAdaptationProposal(
            decision="replan", reason="calculate the quote",
            observation_ids=["o-3"],
            work_request=QuoteCalculationRequest(
                operation="quote_calculation", source_step_id="absent",
                columns={"item_id": "Item", "quantity": "Qty",
                         "unit_price": "Price"},
                currency="USD",
                freight=MoneyTerm(value="0.00", authority_ref="freight"),
                tax=TaxTerm(basis="none", authority_ref="tax_basis"))),
        WorkAdaptationProposal(
            decision="clarify", reason="the evidence step is missing",
            clarification=ClarificationProposal(
                question="Which accepted evidence step has the prices?")),
    ])
    journal = AttemptJournal()
    result = asyncio.run(propose_adaptation(
        _context(), [{"observation_id": "o-3",
                      "kind": "evidence_result"}],
        assignment=_assignment(), llm_service=llm,
        deadline=time.monotonic() + 5.0,
        attempt_journal=journal))
    assert result["source"] == "model_repaired"
    assert len(llm.calls) == 2
    assert all(call["response_model"] is WorkAdaptationProposal
               for call in llm.calls)
    assert "Your previous proposal was invalid" in llm.calls[1]["prompt"]
    dispatches = [e for e in journal.events if e["event"] == "dispatch"]
    assert [e["call_stage"] for e in dispatches] == ["initial", "repair"]
    assert len({e["attempt_id"] for e in journal.events}) == 1


def test_exhausted_deadline_is_typed_and_does_not_start_repair():
    class SlowLLM:
        def __init__(self):
            self.calls = 0

        async def generate_structured_response(self, **kwargs):
            self.calls += 1
            await asyncio.sleep(5)
            return None

    from core.llm.model_provenance import (
        clear_route_attribution, get_route_attribution,
    )

    clear_route_attribution()
    llm = SlowLLM()
    journal = AttemptJournal()

    async def _bounded_attempt():
        attempted = await propose_adaptation(
            _context(), [{"observation_id": "o-4",
                          "kind": "evidence_result"}],
            assignment=_assignment(), llm_service=llm,
            deadline=time.monotonic() + 0.05,
            attempt_journal=journal)
        return attempted, get_route_attribution()

    result, routing = asyncio.run(_bounded_attempt())
    assert result["source"] == "deterministic"
    assert result["failure_stage"] == "initial"
    assert "deadline_exceeded: initial" in result["errors"]
    assert llm.calls == 1
    dispatches = [e for e in journal.events if e["event"] == "dispatch"]
    assert len(dispatches) == 1
    failures = [e for e in journal.events if e["event"] == "failure"]
    assert failures and failures[-1]["kind"] == "deadline_cancelled"
    # The wrapper deadline is still attributable: requested stays visible,
    # nothing is reported as served, and the failure has a business-safe code.
    assert routing["mode"] == "unpinned"
    assert routing["served_route"] is None
    assert routing["error"]["code"] == "deadline_cancelled"
    assert "employee reasoning step" in routing["error"]["detail"]


def test_legacy_context_keeps_legacy_schema_separate():
    llm = CapturingLLM([
        AdaptationProposal(
            decision="retain", reason="no material change",
            observation_ids=["o-5"]),
    ])
    result = asyncio.run(propose_adaptation(
        {"identity": {"workspace_id": "ws_assign"}},
        [{"observation_id": "o-5", "kind": "evidence_result"}],
        assignment=_assignment(), llm_service=llm))
    assert result["source"] == "model"
    assert llm.calls[0]["response_model"] is AdaptationProposal


def test_compact_single_request_prompt_is_bounded_to_one_operation():
    from core.employee_adaptation import _compact_single_request_prompt

    context = {
        "objective": "Reconcile the invoice after receiving",
        "existing_step_ids": ["source-2", "source-3", "source-4"],
        "teaching": {"terms": {"currency": "USD"}},
        "work_request_schemas": work_request_schemas(),
        "available_business_operations": [{
            "operation": "invoice_reconciliation",
            "status": "ready",
            "evidence": [{"step_id": "source-2"},
                         {"step_id": "source-3"},
                         {"step_id": "source-4"}],
            "roles": {"invoice": ["source-2"],
                      "purchase_order": ["source-3"],
                      "receiving": ["source-4"]},
            "known_identities": {"invoice.po_id": "PO-8841"},
        }],
        "rules": {
            "allowed_work_requests": ["invoice_reconciliation"],
        },
    }
    prompt = _compact_single_request_prompt(context)
    assert "only allowed operation is invoice_reconciliation" in prompt
    assert "source-2" in prompt and "source-4" in prompt
    assert "quote_calculation" not in prompt
    assert len(prompt) < 14000

    context["rules"]["allowed_work_requests"].append("quote_calculation")
    assert _compact_single_request_prompt(context) == ""


def test_exhausted_budget_skips_compact_without_a_dispatch():
    context = {
        "identity": {"workspace_id": "ws_assign", "tenant_id": "tenant_assign"},
        "objective": "Reconcile PO-HX-7001 with the accepted receiving record",
        "teaching": {"terms": {"currency": "USD"}},
        "rules": {"allowed_work_requests": ["invoice_reconciliation"]},
        "available_business_operations": [{
            "operation": "invoice_reconciliation",
            "status": "ready",
            "evidence": [
                {"step_id": "invoice"}, {"step_id": "purchase-order"},
                {"step_id": "receiving"}],
            "roles": {"invoice": ["invoice"],
                      "purchase_order": ["purchase-order"],
                      "receiving": ["receiving"]},
            "known_identities": {"invoice.po_id": "PO-HX-7001"},
        }],
        "evidence_results": [
            {"step_id": "invoice", "business_role": "invoice",
             "data_keys": ["po_id", "quantity"]},
            {"step_id": "purchase-order", "business_role": "purchase_order",
             "data_keys": ["po_id"]},
            {"step_id": "receiving", "business_role": "receiving",
             "data_keys": ["received_quantity"]},
        ],
        "business_requirements": [{
            "requirement_id": "result-invoice-1",
            "operation": "invoice_reconciliation",
            "status": "unresolved",
        }],
    }
    journal = AttemptJournal()
    llm = CapturingLLM([])
    result = asyncio.run(propose_adaptation(
        context, [{"observation_id": "o-skip", "kind": "evidence_result",
                   "step_id": "receiving"}],
        assignment=_assignment(), llm_service=llm,
        deadline=time.monotonic() - 1.0,
        attempt_journal=journal))
    assert result["source"] == "deterministic"
    assert result["failure_stage"] == "compact"
    assert "skipped_due_to_budget: compact" in result["errors"]
    assert not llm.calls, "an exhausted budget must not dispatch the model"
    skipped = [e for e in journal.events
               if e["event"] == "skipped_due_to_budget"]
    assert skipped and skipped[0]["call_stage"] == "compact"
    assert not [e for e in journal.events if e["event"] == "failure"]


def test_typed_work_request_rejects_a_reconcile_decision():
    from core.employee_adaptation import _adaptation_errors
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    proposal = AdaptationProposal(
        decision="reconcile",
        reason="wrong decision for new typed work",
        work_request=QuoteCalculationRequest(
            operation="quote_calculation",
            source_step_id="read",
            columns=QuoteColumns(
                item_id="Item", quantity="Qty", unit_price="Price"),
            currency="USD",
            freight=MoneyTerm(value="20.00", authority_ref="freight"),
            tax=TaxTerm(basis="none", authority_ref="tax_basis"),
        ),
    )
    errors = _adaptation_errors(proposal, _assignment(), _context())
    assert any("work_request requires decision 'replan'" in error
               for error in errors)
