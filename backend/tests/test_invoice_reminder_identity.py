"""Identity-constraint controls for the local invoice reminder preparation."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext

import pytest

from accounting import invoice_evidence
from core import assignment_executor, assignment_invoice, database
from core.assignment_executor import NeedsContext
from core.canvas_email_service import EmailCanvasService


def _context() -> dict:
    return {
        "employee_id": "actor-1",
        "tenant_id": "tenant-1",
        "workspace_id": "workspace-1",
        "step": {"operation_id": "operation-1"},
    }


def _install(monkeypatch, *, resolved_id: str, resolved_number: str) -> dict:
    calls = {"lookups": [], "drafts": []}

    def prepare_invoice_reminder(
            db, *, actor_id, tenant_id, workspace_id, invoice_number):
        calls["lookups"].append({
            "actor_id": actor_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "invoice_number": invoice_number,
        })
        return {
            "to": ["customer@example.invalid"],
            "cc": [],
            "subject": f"Payment reminder for invoice {resolved_number}",
            "body": "Hello,\n\nPlease arrange payment.\n\nThank you.",
            "evidence": {
                "source": "local_ledger",
                "source_table": "accounting_invoices",
                "invoice_id": resolved_id,
                "invoice_number": resolved_number,
                "workspace_id": workspace_id,
                "tenant_id": tenant_id,
                "amount": "10.00",
                "currency": "USD",
                "due_date": "2026-01-01T00:00:00+00:00",
            },
        }

    monkeypatch.setattr(
        invoice_evidence, "prepare_invoice_reminder",
        prepare_invoice_reminder)
    monkeypatch.setattr(
        database, "get_db_session", lambda: nullcontext(object()))

    async def email_draft(reminder, context):
        calls["drafts"].append(reminder)
        return {"status": "failed", "action_result": "proven_not_applied"}

    monkeypatch.setattr(assignment_executor, "_email_draft", email_draft)
    return calls


def _prepare(inputs: dict) -> dict:
    return asyncio.run(
        assignment_invoice._invoice_prepare_reminder(inputs, _context()))


def _allow_persistence(monkeypatch) -> None:
    def create_email_draft(self, *, operation_id, **kwargs):
        return {
            "success": True,
            "status": "created",
            "canvas_id": "canvas-1",
            "audit_id": "audit-1",
            "operation_id": operation_id,
            "verification": {"status": "verified"},
            "receipt": {"operation_id": operation_id},
        }

    monkeypatch.setattr(
        EmailCanvasService, "create_email_draft", create_email_draft)

    async def email_draft(reminder, context):
        return {
            "status": "applied",
            "draft": {"draft_revision": "revision-1"},
            "artifact": {},
            "evidence_refs": [],
        }

    monkeypatch.setattr(assignment_executor, "_email_draft", email_draft)


def test_absent_constraint_keeps_standalone_trimming(monkeypatch):
    calls = _install(
        monkeypatch, resolved_id="inv-1", resolved_number="INV-1")

    result = _prepare({"invoice_number": " INV-1 "})

    assert calls["lookups"] == [{
        "actor_id": "actor-1",
        "tenant_id": "tenant-1",
        "workspace_id": "workspace-1",
        "invoice_number": "INV-1",
    }]
    assert len(calls["drafts"]) == 1
    assert result["status"] == "failed"


def test_matching_constraint_preserves_exact_invoice_number(monkeypatch):
    calls = _install(
        monkeypatch, resolved_id="inv-1", resolved_number=" INV-1 ")
    _allow_persistence(monkeypatch)

    result = _prepare({
        "invoice_number": " INV-1 ",
        "expected_invoice_id": "inv-1",
    })

    assert calls["lookups"][0]["invoice_number"] == " INV-1 "
    assert result["status"] == "applied"
    assert result["evidence"][0]["invoice_number"] == " INV-1 "
    assert " INV-1 " in result["summary"]


def test_mismatched_constraint_never_drafts(monkeypatch):
    calls = _install(
        monkeypatch, resolved_id="inv-1", resolved_number="INV-1")

    with pytest.raises(NeedsContext) as caught:
        _prepare({
            "invoice_number": "INV-1",
            "expected_invoice_id": "inv-2",
        })

    assert len(calls["lookups"]) == 1
    assert calls["drafts"] == []
    assert "inv-1" not in str(caught.value)
    assert "INV-1" not in str(caught.value)


@pytest.mark.parametrize(
    "expected_invoice_id",
    [None, "", "   ", 123, True, b"inv-1"],
)
def test_invalid_constraint_never_looks_up_or_drafts(
        monkeypatch, expected_invoice_id):
    calls = _install(
        monkeypatch, resolved_id="inv-1", resolved_number="INV-1")

    with pytest.raises(NeedsContext):
        _prepare({
            "invoice_number": "INV-1",
            "expected_invoice_id": expected_invoice_id,
        })

    assert calls["lookups"] == []
    assert calls["drafts"] == []
