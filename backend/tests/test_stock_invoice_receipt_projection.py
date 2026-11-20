"""Focused tests for the owner-only stock invoice receipt projection."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from core.workflow_endpoints import (
    STOCK_INVOICE_WORKFLOW_ID,
    _stock_invoice_receipt_projection,
)


def _user(**overrides):
    values = {
        "id": "user-1",
        "tenant_id": "tenant-1",
        "workspace_id": "workspace-1",
        "is_active": True,
        "status": "active",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _row(**overrides):
    created = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    values = {
        "execution_id": "execution-1",
        "workflow_id": STOCK_INVOICE_WORKFLOW_ID,
        "user_id": "user-1",
        "owner_id": "user-1",
        "tenant_id": "tenant-1",
        "workspace_id": "workspace-1",
        "status": "PENDING",
        "created_at": created,
        "updated_at": created,
        "completed_at": None,
        "input_data": json.dumps({
            "_atom_execution_scope": {
                "tenant_id": "tenant-1",
                "workspace_id": "workspace-1",
                "user_id": "user-1",
            },
            "private_input": "do-not-expose",
        }),
        "context": json.dumps({"private_context": "do-not-expose"}),
        "outputs": json.dumps({"private_output": "do-not-expose"}),
        "error": "private-error",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _assert_safe(receipt):
    assert set(receipt) <= {
        "execution_id",
        "workflow_id",
        "status",
        "created_at",
        "updated_at",
        "completed_at",
        "run_id",
    }
    for forbidden in (
        "input_data", "context", "outputs", "error", "steps", "results",
        "trigger_data", "operation_id",
    ):
        assert forbidden not in receipt
    assert "do-not-expose" not in json.dumps(receipt)


def test_stock_projection_returns_only_fixed_receipt(monkeypatch):
    monkeypatch.setattr(
        "core.workflow_endpoints._stock_linked_run_id",
        lambda db, row, scope: "run-1",
    )

    receipt = _stock_invoice_receipt_projection(_user(), _row())

    assert receipt == {
        "execution_id": "execution-1",
        "workflow_id": STOCK_INVOICE_WORKFLOW_ID,
        "status": "pending",
        "created_at": "2026-01-02T03:04:05+00:00",
        "updated_at": "2026-01-02T03:04:05+00:00",
        "completed_at": None,
        "run_id": "run-1",
    }
    _assert_safe(receipt)


def test_stock_projection_omits_unvalidated_run_reference(monkeypatch):
    monkeypatch.setattr(
        "core.workflow_endpoints._stock_linked_run_id",
        lambda db, row, scope: None,
    )

    receipt = _stock_invoice_receipt_projection(_user(), _row())

    assert receipt is not None
    assert "run_id" not in receipt
    _assert_safe(receipt)


def test_stock_projection_refuses_missing_scope_or_inactive_actor():
    for user in (
        _user(id=None),
        _user(tenant_id=None),
        _user(workspace_id=None),
        _user(is_active=False),
        _user(status="disabled"),
    ):
        assert _stock_invoice_receipt_projection(user, _row()) is None


def test_stock_projection_allows_exact_literal_default_tenant_and_workspace():
    row = _row(
        tenant_id="default",
        workspace_id="default",
        input_data=json.dumps({
            "_atom_execution_scope": {
                "tenant_id": "default",
                "workspace_id": "default",
                "user_id": "user-1",
            },
        }),
    )

    receipt = _stock_invoice_receipt_projection(
        _user(tenant_id="default", workspace_id="default"), row)

    assert receipt is not None
    assert receipt["execution_id"] == "execution-1"
    _assert_safe(receipt)
    assert _stock_invoice_receipt_projection(
        _user(tenant_id="default", workspace_id="workspace-1"), row) is None


def test_stock_projection_allows_exact_literal_default_owner_scope():
    row = _row(
        user_id="default",
        owner_id="default",
        tenant_id="default",
        workspace_id="default",
        input_data=json.dumps({
            "_atom_execution_scope": {
                "tenant_id": "default",
                "workspace_id": "default",
                "user_id": "default",
            },
        }),
    )

    receipt = _stock_invoice_receipt_projection(
        _user(id="default", tenant_id="default", workspace_id="default"),
        row,
    )

    assert receipt is not None
    assert receipt["execution_id"] == "execution-1"
    _assert_safe(receipt)
    assert _stock_invoice_receipt_projection(
        _user(id="default", tenant_id="default", workspace_id="default"),
        _row(),
    ) is None


def test_stock_projection_refuses_foreign_row_columns():
    for row in (
        _row(user_id="other-user"),
        _row(owner_id="other-user"),
        _row(tenant_id="other-tenant"),
        _row(workspace_id="other-workspace"),
        _row(workflow_id="another-workflow"),
    ):
        assert _stock_invoice_receipt_projection(_user(), row) is None


def test_stock_projection_refuses_malformed_stored_scope():
    for input_data in (
        None,
        "not-json",
        json.dumps({}),
        json.dumps({"_atom_execution_scope": "not-an-object"}),
        json.dumps({
            "_atom_execution_scope": {
                "tenant_id": "tenant-1",
                "workspace_id": "workspace-1",
            },
        }),
        json.dumps({
            "_atom_execution_scope": {
                "tenant_id": "tenant-1",
                "workspace_id": "other-workspace",
                "user_id": "user-1",
            },
        }),
    ):
        assert _stock_invoice_receipt_projection(
            _user(), _row(input_data=input_data)) is None
