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
            "observation_ids": ["evidence-receiving"],
            "work_request": {
                "operation": "invoice_reconciliation",
                "invoice_fields": {},
                "purchase_order_fields": {},
                "receiving_fields": {},
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
