"""Focused controls for the read-only invoice.lookup assignment adapter."""
from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional

import pytest

from accounting.invoice_evidence import InvoiceEvidenceError
from core.assignment_executor import NeedsContext
from core.assignment_invoice import (
    _INVOICE_LOOKUP_FACTS,
    _invoice_lookup,
)


EXACT_NUMBER = " INV 42/\u00c4 "


def _facts() -> dict:
    return {
        "invoice_id": "inv-42",
        "invoice_number": EXACT_NUMBER,
        "status": "open",
        "amount": "1250.00",
        "currency": "USD",
        "due_date": "2026-10-01T00:00:00+00:00",
        "as_of": "2026-11-19T00:00:00+00:00",
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "workspace_name": "Books",
        "source": "local_ledger",
        "source_table": "accounting_invoices",
        "recorded_paid": False,
        "is_overdue": True,
        "days_overdue": 49,
        "days_until_due": 0,
        "aging_bucket": "overdue_60",
        # The helper strips this.  The adapter must never publish it either.
        "customer_id": "customer-secret",
    }


def _context(**overrides: Any) -> dict:
    context = {
        "employee_id": "actor-1",
        "tenant_id": "tenant-1",
        "workspace_id": "ws-1",
        "step": {"operation_id": "op-lookup"},
    }
    context.update(overrides)
    return context


class _Session:
    def __enter__(self) -> "_Session":
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        return False


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: Optional[Mapping[str, Any]] = None,
    error: Optional[Exception] = None,
) -> list[dict]:
    calls: list[dict] = []

    def fake_read(db: Any, **kwargs: Any) -> dict:
        calls.append(dict(kwargs))
        if error is not None:
            raise error
        return dict(result if result is not None else _facts())

    import accounting.invoice_evidence as evidence
    import core.database as database

    monkeypatch.setattr(evidence, "read_invoice_evidence", fake_read)
    monkeypatch.setattr(database, "get_db_session", lambda: _Session())
    return calls


def _gap(error: NeedsContext) -> Mapping[str, Any]:
    return error.gap


def test_lookup_preserves_exact_number_and_ignores_input_scope(monkeypatch):
    calls = _install(monkeypatch)

    result = asyncio.run(_invoice_lookup(
        {
            "invoice_number": EXACT_NUMBER,
            "actor_id": "caller-actor",
            "tenant_id": "caller-tenant",
            "workspace_id": "caller-workspace",
            "operation_id": "caller-operation",
        },
        _context(),
    ))

    assert calls == [{
        "actor_id": "actor-1",
        "tenant_id": "tenant-1",
        "workspace_id": "ws-1",
        "invoice_number": EXACT_NUMBER,
    }]
    assert result["status"] == "applied"
    assert result["invoice_number"] == EXACT_NUMBER
    assert result["data"]["invoice_number"] == EXACT_NUMBER


def test_lookup_result_is_bounded_scoped_facts_without_claims(monkeypatch):
    _install(monkeypatch)

    result = asyncio.run(_invoice_lookup(
        {"invoice_number": EXACT_NUMBER}, _context()))

    data = result["data"]
    assert data["status"] == "open"
    assert data["recorded_paid"] is False
    assert data["is_overdue"] is True
    assert data["days_overdue"] == 49
    assert data["aging_bucket"] == "overdue_60"
    assert data["workspace_id"] == "ws-1"
    assert data["tenant_id"] == "tenant-1"
    assert "customer_id" not in data
    assert set(data) <= set(_INVOICE_LOOKUP_FACTS)
    assert result["invoice"] == data
    assert result["operation_id"] == "op-lookup"
    assert result["provider_state"] == "read_only"
    assert result["send_performed"] is False
    assert result["payment"] is False
    assert result["settled"] is False
    assert result["evidence_refs"] == [{
        "kind": "invoice",
        "resource_id": "inv-42",
        "invoice_number": EXACT_NUMBER,
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "source": "local_ledger",
        "source_table": "accounting_invoices",
        "status": "open",
        "recorded_paid": False,
    }]
    assert result["verification"]["coverage"] == {
        "complete": True, "truncated": False}


def test_lookup_requires_persisted_scope_not_input_overrides(monkeypatch):
    calls = _install(monkeypatch)
    context = _context()
    context.pop("tenant_id")

    with pytest.raises(NeedsContext) as raised:
        asyncio.run(_invoice_lookup(
            {
                "invoice_number": EXACT_NUMBER,
                "tenant_id": "caller-tenant",
            },
            context,
        ))

    gap = _gap(raised.value)
    assert gap["concept"] == "authenticated_scope"
    assert gap["kind"] == "missing_evidence"
    assert "missing=tenant_id" in gap["checked_evidence"]
    assert calls == []


def test_lookup_requires_persisted_operation_id(monkeypatch):
    calls = _install(monkeypatch)

    with pytest.raises(NeedsContext) as raised:
        asyncio.run(_invoice_lookup(
            {
                "invoice_number": EXACT_NUMBER,
                "operation_id": "caller-operation",
            },
            _context(step={}),
        ))

    gap = _gap(raised.value)
    assert gap["concept"] == "execution_identity"
    assert gap["kind"] == "missing_evidence"
    assert gap["checked_evidence"] == ["operation_id=missing"]
    assert calls == []


def test_lookup_maps_known_evidence_denial_to_safe_missing_evidence(
    monkeypatch,
):
    _install(monkeypatch, error=InvoiceEvidenceError(
        "invoice not found in this workspace",
        reason="invoice_not_found",
        invoice_number=EXACT_NUMBER,
        workspace_id="ws-1",
    ))

    with pytest.raises(NeedsContext) as raised:
        asyncio.run(_invoice_lookup(
            {"invoice_number": EXACT_NUMBER}, _context()))

    gap = _gap(raised.value)
    assert gap["concept"] == "invoice_evidence"
    assert gap["kind"] == "missing_evidence"
    assert "invoice_not_found" in gap["reason"]
    assert gap["checked_evidence"] == ["refused=invoice_not_found"]


def test_lookup_lets_infrastructure_faults_propagate(monkeypatch):
    _install(monkeypatch, error=RuntimeError("ledger unavailable"))

    with pytest.raises(RuntimeError, match="ledger unavailable"):
        asyncio.run(_invoice_lookup(
            {"invoice_number": EXACT_NUMBER}, _context()))
