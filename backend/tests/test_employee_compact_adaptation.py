"""Compact single-operation adaptation context before the full prompt."""
from __future__ import annotations

import asyncio
import json

from core.assignment_plan import new_assignment, new_step
from core.employee_adaptation import (
    _compact_single_request_context, propose_adaptation,
)
from core.employee_business_outcomes import (
    normalize_business_requirement,
)


def _assignment():
    def applied(step_id, adapter, data):
        step = new_step(
            step_id=step_id, title=step_id, operation_type="retrieve",
            adapter=adapter,
            inputs={"resource_binding": {
                "resource_id": step_id, "source_version": "v1",
                "representation": "document_text",
                "coverage": {
                    "known": True, "source_row_count": 1,
                    "materialized_row_count": 1,
                    "expected_count": 1, "observed_count": 1,
                    "truncated": False}}},
            effect="read_only")
        step.update(status="applied", operation_id=f"op-{step_id}", result={
            "summary": f"read {step_id}",
            "verification": {
                "status": "verified", "resource_id": step_id,
                "version": "v1"},
            "resource_id": step_id,
            "source_version": "v1",
            "coverage": {
                "known": True, "source_row_count": 1,
                "materialized_row_count": 1,
                "expected_count": 1, "observed_count": 1,
                "truncated": False},
            "data": data,
        })
        return step

    return new_assignment(
        objective="Reconcile INV-4491 for PO-7302 and publish the review",
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1",
        steps=[
            applied("invoice", "document.read", {
                "invoice_id": "INV-4491", "po_id": "PO-7302",
                "quantity": "3", "unit_price": "42.50",
                "freight": "12.75", "currency": "USD", "version": "inv-h1"}),
            applied("purchase-order", "document.read", {
                "po_id": "PO-7302", "vendor_id": "V-41"}),
            applied("receiving", "document.read", {
                "po_id": "PO-7302", "received_quantity": "3"}),
        ],
        business_requirements=[normalize_business_requirement({
            "requirement_id": "result-invoice-7302",
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "subject": "purchase order PO-7302",
            "subject_identity": {"po_id": "PO-7302", "invoice_id": "INV-4491"},
            "fact": "receiving",
            "correlation_id": "await-heldout",
            "receipt_adapter": "invoice.reconcile",
        })],
    )


def _context():
    assignment = _assignment()
    steps = assignment["steps"]
    evidence = [{
        "step_id": step["step_id"],
        "adapter": step["adapter"],
        "status": step["status"],
        "summary": step["result"]["summary"],
        "business_role": {
            "invoice": "invoice", "purchase-order": "purchase_order",
            "receiving": "receiving",
        }[step["step_id"]],
        "data_keys": sorted(step["result"]["data"]),
        "data_preview": dict(step["result"]["data"]),
        "verification": step["result"]["verification"],
    } for step in steps]
    return {
        "objective": assignment["objective"],
        "identity": {"workspace_id": "ws-1", "tenant_id": "tenant-1"},
        "teaching": {"terms": {
            "currency": "USD", "freight": "7.50", "tax_basis": "none"}},
        "rules": {
            "allowed_work_requests": ["invoice_reconciliation"],
            "allowed_proposal_kinds": ["replan", "clarify"],
        },
        "available_business_operations": [{
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": "ready",
            "missing": [],
            "evidence": [{
                "step_id": step["step_id"], "shape": "structured",
                "columns": [], "verified": True, "title": step["step_id"],
            } for step in steps],
            "roles": {"invoice": ["invoice"],
                      "purchase_order": ["purchase-order"],
                      "receiving": ["receiving"]},
            "known_identities": {
                "invoice.invoice_id": "INV-4491",
                "invoice.po_id": "PO-7302",
                "purchase_order.po_id": "PO-7302",
                "purchase_order.vendor_id": "V-41"},
        }],
        "evidence_results": evidence,
        "business_requirements": [{
            "requirement_id": "result-invoice-7302",
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "subject": "purchase order PO-7302",
            "subject_identity": {
                "po_id": "PO-7302", "invoice_id": "INV-4491"},
            "fact": "receiving",
            "status": "unresolved",
            "next_action": (
                "The external fact is recorded; invoice reconciliation "
                "still needs completion."),
        }],
        "observations": [{
            "observation_id": "evidence-receiving", "kind": "evidence_result",
            "step_id": "receiving", "shape": "structured",
        }],
    }


def test_compact_context_is_single_operation_and_keeps_scope():
    compact = _compact_single_request_context(
        _context(), [{
            "observation_id": "evidence-receiving",
            "kind": "evidence_result", "step_id": "receiving"}])
    assert compact is not None
    assert compact["operation"] == "invoice_reconciliation"
    assert "purchase order PO-7302" in compact["prompt"]
    assert "PO-7302" in compact["prompt"]
    assert "INV-4491" in compact["prompt"]
    assert '"subject_identity":' in compact["prompt"]
    assert "receiving" in compact["prompt"]
    assert "retain" in compact["prompt"] and "clarify" in compact["prompt"]
    # No all-purpose union schema or unrelated business operation is offered.
    assert "await_evidence" not in compact["prompt"]
    assert "quote_calculation" not in compact["prompt"]
    # No fixture expected totals or unrelated quote rows are injected.
    assert "370.00" not in compact["prompt"]
    assert "96.30" not in compact["prompt"]
    assert compact["response_model"].__name__ == (
        "CompactEmployeeWorkProposal")
    # The prompt names the instance shape and explicitly refuses a schema
    # echo; the live local model copied instructor's injected JSON schema
    # until this guard was present.
    assert "Return JSON only with this shape" in compact["prompt"]
    assert "work_request fields:" in compact["prompt"]
    assert "Never output $defs" in compact["prompt"]
    # The narrow model accepts the typed invoice request and rejects another
    # operation's request.
    from pydantic import ValidationError

    compact["response_model"].model_validate({
        "decision": "replan",
        "reason": "reconcile",
        "observation_ids": ["evidence-receiving"],
        "work_request": {"operation": "invoice_reconciliation"},
    })
    try:
        compact["response_model"].model_validate({
            "decision": "replan",
            "work_request": {
                "operation": "quote_calculation",
                "source_step_id": "receiving",
                "columns": {"item_id": "Item", "quantity": "Qty",
                            "unit_price": "Price"},
                "currency": "USD",
                "freight": {"value": "7.50", "authority_ref": "freight"},
            },
        })
    except ValidationError:
        pass
    else:  # pragma: no cover — the narrow schema must reject it
        raise AssertionError("compact schema accepted an unrelated operation")


def test_compact_schema_echo_is_rejected_and_a_valid_instance_is_kept():
    from pydantic import ValidationError

    compact = _compact_single_request_context(
        _context(), [{
            "observation_id": "evidence-receiving",
            "kind": "evidence_result", "step_id": "receiving"}])
    assert compact is not None
    # Exactly the payload the served model returned when it copied
    # instructor's injected schema instead of an instance.
    schema_echo = compact["response_model"].model_json_schema()
    assert {"$defs", "properties", "required", "title", "type"} <= set(
        schema_echo)
    try:
        compact["response_model"].model_validate(schema_echo)
    except ValidationError as exc:
        assert any(
            error["type"] == "extra_forbidden" for error in exc.errors())
        assert any(
            error["loc"] == ("decision",) for error in exc.errors())
    else:  # pragma: no cover — a schema echo must never be accepted
        raise AssertionError("compact schema accepted its own JSON schema")

    accepted = compact["response_model"].model_validate({
        "decision": "replan",
        "reason": "accepted invoice, purchase order and receiving evidence",
        "observation_ids": ["evidence-receiving"],
        "work_request": {
            "operation": "invoice_reconciliation",
            "invoice_step_id": "invoice",
            "purchase_order_step_id": "purchase-order",
            "receiving_step_id": "receiving",
            "currency": "USD",
        },
        "clarification": None,
    })
    assert accepted.work_request.receiving_step_id == "receiving"
    assert accepted.work_request.purchase_order_step_id == "purchase-order"


def test_compact_context_allows_the_independent_quote_while_waiting():
    context = {
        "objective": "Quote the price list while the receiving record is owed",
        "identity": {"workspace_id": "ws-1", "tenant_id": "tenant-1"},
        "teaching": {"terms": {
            "currency": "USD", "freight": "9.00", "tax_basis": "none"}},
        "rules": {"allowed_work_requests": [
            "quote_calculation", "await_evidence"]},
        "waiting": [{
            "step_id": "await", "fact": "receiving",
            "subject": "purchase order PO-QH-8100",
            "blocks": "invoice reconciliation",
        }],
        "available_business_operations": [{
            "operation": "quote_calculation",
            "label": "quote calculation",
            "status": "ready",
            "missing": [],
            "evidence": [{
                "step_id": "price-rows", "shape": "tabular",
                "verified": True, "title": "Read price-book-fresh.xlsx",
                "columns": ["Currency", "Item", "Price", "Qty"],
            }],
            "roles": {},
            "known_identities": {},
        }],
        "evidence_results": [{
            "step_id": "price-rows", "business_role": "quote_rows",
            "data_keys": [], "data_preview": {},
            "schema": [{"column": "Item"}, {"column": "Qty"},
                       {"column": "Price"}, {"column": "Currency"}],
        }],
        "business_requirements": [],
    }
    compact = _compact_single_request_context(
        context, [{
            "observation_id": "waiting-1", "kind": "waiting_state",
            "step_id": "await"}],
        require_unresolved_requirement=True)
    assert compact is not None
    assert compact["operation"] == "quote_calculation"
    assert "column NAMES" in compact["prompt"]
    assert "quote_calculation" in compact["prompt"]
    assert "invoice_reconciliation" not in compact["prompt"]


def test_compact_invoice_schema_keeps_compiler_owned_fields_out():
    compact = _compact_single_request_context(
        _context(), [{
            "observation_id": "evidence-receiving",
            "kind": "evidence_result", "step_id": "receiving"}])
    assert compact is not None
    work_schema = compact["response_model"].model_json_schema()[
        "$defs"][compact["response_model"].model_fields[
            "work_request"].annotation.__args__[0].__name__]
    properties = set(work_schema["properties"])
    # Role IDs and currency remain model-owned; field maps and the evidence
    # array are compiler-owned defaults for this narrow continuation.
    assert {"invoice_step_id", "purchase_order_step_id",
            "receiving_step_id", "currency"} <= properties
    assert "receiving_fields" not in properties
    assert "invoice_fields" not in properties
    assert "evidence" not in properties
    accepted = compact["response_model"].model_validate({
        "decision": "replan",
        "work_request": {
            "operation": "invoice_reconciliation",
            "invoice_step_id": "invoice",
            "purchase_order_step_id": "purchase-order",
            "receiving_step_id": "receiving",
            "currency": "USD",
        },
    })
    from core.employee_work_requests import InvoiceReconciliationRequest

    full = InvoiceReconciliationRequest.model_validate(
        accepted.work_request.model_dump())
    assert full.receiving_step_id == "receiving"
    assert full.receiving_fields == {}


def test_compact_path_is_called_before_the_full_adaptation_prompt(monkeypatch):
    context = _context()
    assignment = _assignment()
    calls = []

    async def fake_pinned(_llm, *, prompt, response_model, **kwargs):
        calls.append({
            "prompt": prompt, "model": response_model.__name__,
            "max_tokens": (kwargs.get("extra_kwargs") or {}).get("max_tokens"),
        })
        return response_model.model_validate({
            "decision": "replan",
            "reason": "the receiving fact is accepted",
            "work_request": {
                "operation": "invoice_reconciliation",
                "invoice_step_id": "invoice",
                "purchase_order_step_id": "purchase-order",
                "receiving_step_id": "receiving",
                "currency": "USD",
            },
        })

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        context, [{
            "observation_id": "evidence-receiving",
            "kind": "evidence_result", "step_id": "receiving"}],
        assignment=assignment, llm_service=FakeLLM()))
    assert result["source"] == "model_compact", result
    assert result["prompt_mode"] == "compact"
    assert len(calls) == 1
    assert calls[0]["model"] == "CompactEmployeeWorkProposal"
    assert calls[0]["max_tokens"] == 1200
    assert "WorkAdaptationProposal" not in calls[0]["prompt"]
    assert (result["proposal"].get("work_request") or {}).get(
        "operation") == "invoice_reconciliation"
    assert (result["proposal"].get("work_request") or {}).get(
        "invoice_step_id") == "invoice"
    assert (result["proposal"].get("work_request") or {}).get(
        "purchase_order_step_id") == "purchase-order"
    assert (result["proposal"].get("work_request") or {}).get(
        "receiving_step_id") == "receiving"
    # Opaque observation ids are bound from the compact call's own context;
    # the model is not asked to repeat lifecycle plumbing.
    assert result["proposal"]["observation_ids"] == ["evidence-receiving"]


def test_compact_no_result_is_reported_as_a_compact_failure(monkeypatch):
    async def fake_pinned(_llm, **_kwargs):
        return None

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        _context(), [{
            "observation_id": "evidence-receiving",
            "kind": "evidence_result", "step_id": "receiving"}],
        assignment=_assignment(), llm_service=FakeLLM()))
    assert result["source"] == "deterministic"
    assert result["prompt_mode"] == "compact"
    assert result["failure_stage"] == "compact"
    assert any("no proposal" in error or "no parsed" in error
               for error in result["errors"])


def test_compact_path_allows_truthful_retain(monkeypatch):
    context = _context()

    async def fake_pinned(_llm, *, response_model, **_kwargs):
        return response_model.model_validate({
            "decision": "retain",
            "reason": "the accepted evidence is not sufficient",
            "observation_ids": ["evidence-receiving"],
        })

    class FakeLLM:
        pass

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)
    result = asyncio.run(propose_adaptation(
        context, [{
            "observation_id": "evidence-receiving",
            "kind": "evidence_result", "step_id": "receiving"}],
        assignment=_assignment(), llm_service=FakeLLM()))
    assert result["source"] == "model_compact"
    assert result["proposal"]["decision"] == "retain"
