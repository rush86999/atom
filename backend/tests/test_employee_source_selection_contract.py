"""Independent procurement evidence selection — deterministic contracts.

The broad authorized pool remains visible as evidence, but role candidates are
filtered by the unresolved requirement's exact invoice/PO identity. Wrong-PO
and obsolete candidates cannot become the typed role; a pool without the
required invoice is a targeted missing-record obligation; duplicate
identity-matching candidates that disagree are ambiguous.
"""
from __future__ import annotations

import pytest

from core.assignment_plan import new_assignment, new_step
from core.employee_business_outcomes import normalize_business_requirement
from core.employee_proposal import operation_capabilities
from core.employee_work_compiler import (
    WorkRequestCompileError, compile_work_request_patch,
)
from core.employee_work_requests import InvoiceReconciliationRequest


def _read(step_id, resource_id, data, version="v1"):
    step = new_step(
        step_id=step_id, title=f"Read {resource_id}",
        operation_type="retrieve", adapter="document.text",
        inputs={"resource_binding": {
            "resource_id": resource_id, "source_version": version}},
        effect="read_only")
    step["status"] = "applied"
    step["result"] = {
        "resource_id": resource_id, "source_version": version,
        "coverage": {"complete": True, "known": True, "truncated": False},
        "verification": {
            "status": "verified", "resource_id": resource_id,
            "version": version, "coverage": {"complete": True}},
        "data": data,
    }
    return step


def _requirement(identity=None):
    return normalize_business_requirement({
        "requirement_id": "result-invoice-sel",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "purchase order PO-SEL-520",
        "subject_identity": identity or {
            "invoice_id": "INV-SEL-77", "po_id": "PO-SEL-520"},
        "fact": "receiving",
        "correlation_id": "await-sel-1",
    })


def _assignment(*, include_correct_invoice=True, duplicate_correct=False):
    steps = [
        _read("source-po", "doc-po", {
            "po_id": "PO-SEL-520", "vendor_id": "V-63"}),
        _read("source-receiving", "doc-recv", {
            "po_id": "PO-SEL-520", "received_quantity": 6}),
        _read("source-invoice-wrong", "doc-inv-wrong", {
            "invoice_id": "INV-SEL-76", "po_id": "PO-SEL-999",
            "quantity": 2, "unit_price": 40.00, "freight": 5.00,
            "currency": "USD"}),
        _read("source-invoice-obsolete", "doc-inv-old", {
            "invoice_id": "INV-SEL-70", "po_id": "PO-SEL-520",
            "quantity": 6, "unit_price": 17.00, "freight": 8.00,
            "currency": "USD"}),
    ]
    if include_correct_invoice:
        steps.append(_read("source-invoice-correct", "doc-inv", {
            "invoice_id": "INV-SEL-77", "po_id": "PO-SEL-520",
            "quantity": 6, "unit_price": 18.50, "freight": 10.00,
            "currency": "USD"}))
    if duplicate_correct:
        steps.append(_read("source-invoice-copy", "doc-inv-copy", {
            "invoice_id": "INV-SEL-77", "po_id": "PO-SEL-520",
            "quantity": 6, "unit_price": 19.25, "freight": 10.00,
            "currency": "USD"}))
    return new_assignment(
        objective=(
            "Reconcile supplier invoice INV-SEL-77 for purchase order "
            "PO-SEL-520 against the matching purchase order and receiving "
            "record."),
        employee_id="employee-1", workspace_id="ws-sel", tenant_id="t-sel",
        steps=steps, authorized_actions=["retrieve", "calculate"],
        business_requirements=[_requirement()])


def _invoice_capability(assignment):
    return next(
        item for item in operation_capabilities(assignment)
        if item["operation"] == "invoice_reconciliation")


def test_objective_identity_hints_are_unambiguous_only():
    from core.employee_proposal import objective_identity_hints

    assert objective_identity_hints(
        "Reconcile INV-SEL-77 for PO-SEL-520") == {
            "invoice_id": "INV-SEL-77", "po_id": "PO-SEL-520"}
    assert objective_identity_hints(
        "Reconcile INV-SEL-77 or INV-SEL-78 for PO-SEL-520") == {
            "po_id": "PO-SEL-520"}


def test_provenance_identity_hint_filters_without_a_requirement():
    assignment = _assignment()
    assignment["business_requirements"] = []
    assignment.setdefault("provenance", {})["objective_identities"] = {
        "invoice_id": "INV-SEL-77", "po_id": "PO-SEL-520"}
    capability = _invoice_capability(assignment)
    assert capability["status"] == "ready"
    assert capability["roles"]["invoice"] == ["source-invoice-correct"]


def test_exact_identity_filters_wrong_po_and_obsolete_candidates():
    capability = _invoice_capability(_assignment())
    assert capability["status"] == "ready"
    assert capability["roles"]["invoice"] == ["source-invoice-correct"]
    assert capability["roles"]["purchase_order"] == ["source-po"]
    assert capability["roles"]["receiving"] == ["source-receiving"]
    assert capability["ambiguous_roles"] == []
    # The distractors remain visible as accepted evidence, not as role choices.
    assert {item["step_id"] for item in capability["evidence"]} >= {
        "source-invoice-wrong", "source-invoice-obsolete"}


def test_missing_required_invoice_is_a_targeted_obligation():
    capability = _invoice_capability(_assignment(include_correct_invoice=False))
    assert capability["status"] == "missing"
    assert "invoice" in capability["missing"]
    assert capability["roles"]["invoice"] == []
    assert "INV-SEL-77" in capability["question_hint"]
    assert "PO-SEL-520" in capability["question_hint"]


def test_duplicate_identity_matching_invoices_are_ambiguous():
    capability = _invoice_capability(
        _assignment(duplicate_correct=True))
    assert capability["status"] == "ambiguous"
    assert "invoice" in capability["ambiguous_roles"]
    assert set(capability["roles"]["invoice"]) == {
        "source-invoice-correct", "source-invoice-copy"}


def test_compiler_rejects_a_wrong_invoice_even_when_bound_explicitly():
    assignment = _assignment()
    request = InvoiceReconciliationRequest(
        operation="invoice_reconciliation",
        invoice_step_id="source-invoice-wrong",
        purchase_order_step_id="source-po",
        receiving_step_id="source-receiving",
    )
    with pytest.raises(
            WorkRequestCompileError,
            match="required invoice identity|purchase order"):
        compile_work_request_patch(request, assignment, context={})

    valid = InvoiceReconciliationRequest(
        operation="invoice_reconciliation",
        invoice_step_id="source-invoice-correct",
        purchase_order_step_id="source-po",
        receiving_step_id="source-receiving",
    )
    patch = compile_work_request_patch(valid, assignment, context={})
    assert patch["add_steps"][0]["adapter"] == "invoice.reconcile"
    assert patch["add_steps"][0]["inputs"]["invoice_fields"]
