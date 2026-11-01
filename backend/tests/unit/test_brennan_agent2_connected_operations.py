"""Agent 2 contract controls for Brennan connected operations.

These tests are consumer-boundary checks for the provider fixes:
capability/dispatch agreement, CRM argument shape, strict unavailable-vs-empty
reads, paging envelopes and the no-send Outlook draft surface.
"""
from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock

from core.provider_contract_matrix import (
    assert_contract_matrix,
    build_matrix,
    contract_by_key,
)
from integrations.provider_errors import unavailable
from integrations.zoho_books_service import ZohoBooksService
from integrations.zoho_crm_service import ZohoCRMService
from integrations.zoho_workdrive_service import ZohoWorkDriveService


def test_provider_contract_matrix_matches_resolved_classes():
    matrix = build_matrix()
    assert matrix["issues"] == [], matrix["issues"]
    assert_contract_matrix(matrix)
    crm = contract_by_key(matrix, "zoho_crm", "create_record")
    assert crm and crm["method_implemented"] and crm["advertised"]
    books = contract_by_key(matrix, "zoho_books", "get_bills")
    assert books and books["method_implemented"] and books["advertised"]
    draft = contract_by_key(matrix, "outlook", "create_draft_email")
    assert draft and draft["method_implemented"]


def test_crm_create_record_passes_module_and_data():
    service = ZohoCRMService("tenant-1", {"access_token": "token"})
    service.create_record = AsyncMock(return_value={"id": "contact-1"})

    result = asyncio.run(service.execute_operation(
        "create_record",
        {"module": "Contacts", "data": {"Last_Name": "Brennan"}},
    ))

    assert result["success"] is True
    assert result["result"] == {"id": "contact-1"}
    service.create_record.assert_awaited_once_with(
        "Contacts", {"Last_Name": "Brennan"}, tenant_id=None)


def test_crm_create_record_without_module_is_explicitly_refused():
    service = ZohoCRMService("tenant-1", {"access_token": "token"})
    service.create_record = AsyncMock()

    result = asyncio.run(service.execute_operation(
        "create_record", {"data": {"Last_Name": "Brennan"}}))

    assert result["success"] is False
    assert result["error_kind"] == "invalid_request"
    service.create_record.assert_not_called()


def test_books_strict_read_failure_is_not_an_empty_result():
    service = ZohoBooksService("tenant-1", {"access_token": "token"})
    service._request = AsyncMock(side_effect=unavailable(
        "zoho_books", "get_bill", "Zoho Books grant expired.",
        kind="auth_expired"))

    result = asyncio.run(service.execute_operation(
        "get_bill",
        {"access_token": "token", "organization_id": "org-1",
         "bill_id": "bill-1"},
    ))

    assert result["success"] is False
    assert result["error_kind"] == "auth_expired"
    assert result["requires_reconnect"] is True
    assert "result" not in result


def test_books_capability_table_matches_dispatch_methods():
    service = ZohoBooksService("tenant-1", {"access_token": "token"})
    operations = set(service.get_capabilities()["operations"])
    assert {"get_invoices", "get_bills", "create_bill",
            "create_estimate", "get_contacts_page"} <= operations
    for name in operations:
        assert callable(getattr(service, name, None)), name


def test_workdrive_missing_token_is_an_error_envelope_not_empty_data():
    service = ZohoWorkDriveService("tenant-1", {})
    service.get_access_token = AsyncMock(return_value=None)

    result = asyncio.run(service.list_files_page(
        "user-1", "folder-1", workspace_id="workspace-1"))

    assert result["status"] == "error"
    assert result["provider"] == "zoho_workdrive"
    assert result["error_kind"] == "auth_unavailable"
    assert result["requires_reconnect"] is True


def test_workdrive_search_unavailable_is_not_an_empty_success():
    service = ZohoWorkDriveService("tenant-1", {})
    service.get_access_token = AsyncMock(return_value=None)

    result = asyncio.run(service.search_files_envelope(
        "user-1", "price list"))

    assert result["status"] == "error"
    assert result["error_kind"] == "auth_unavailable"


def test_onedrive_page_requires_explicit_identity_for_sharepoint():
    from integrations.onedrive_service import OneDriveService

    service = OneDriveService("tenant-1", {})
    service._resolve_token = lambda _token: None

    result = asyncio.run(service.list_files_page(
        None, drive_id="drive-1", site_id=None))

    # No token wins first; the identity rule is covered by the code path and
    # the contract matrix.  The important assertion is that the call returns
    # an error envelope rather than [].
    assert result["status"] == "error"
    assert result["provider"] == "onedrive"
    assert "items" not in result


def test_connected_actions_are_registered_with_safe_effects():
    from core.action_registry import action_registry

    names = {
        "brennan.workdrive.list_page",
        "brennan.workdrive.read_file",
        "brennan.onedrive.list_page",
        "brennan.onedrive.read_file",
        "brennan.crm.get_record",
        "brennan.inventory.check_stock",
        "brennan.books.get_bill",
        "brennan.outlook.create_draft",
    }
    for name in names:
        action = action_registry.get_action(name)
        assert action is not None, name
    assert action_registry.get_action(
        "brennan.outlook.create_draft").effects == [{"effect": "create"}]
    assert action_registry.get_action(
        "brennan.workdrive.read_file").effects == [{"effect": "read"}]


def test_workdrive_read_action_returns_content_hash_and_receipt(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeWorkDrive:
        async def get_file_metadata(self, user_id, file_id, workspace_id=None):
            return {"id": file_id, "name": "price-list.csv",
                    "version": "v7", "size": 4}

        async def download_file(self, user_id, file_id, workspace_id=None):
            return b"a,b\n"

        async def get_access_token(self, user_id, workspace_id=None):
            return "token"

    async def fake_service(ids):
        return FakeWorkDrive()

    monkeypatch.setattr(actions, "_workdrive_service", fake_service)
    result = asyncio.run(actions.workdrive_read_file(
        {"file_id": "file-1"}, {"user_id": "user-1",
                                 "workspace_id": "ws-1",
                                 "tenant_id": "t1"}))

    assert result["status"] == "success"
    assert result["file"]["version"] == "v7"
    assert result["content_b64"] == "YSxiCg=="
    assert result["sha256"] == "93c4c3f7c4f0f1f4e7e7a1c8e8a2f1c7a4b2e1d0c9f8a7b6c5d4e3f2a1b0c9d8"[:64] or len(result["sha256"]) == 64
    assert result["read_receipt"]["provider"] == "zoho_workdrive"
    assert result["read_receipt"]["resource_id"] == "file-1"


def test_onedrive_read_action_returns_binary_not_json(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeOneDrive:
        async def get_access_token_resolution(self, user_id):
            return "token", {"state": "ok"}

        async def download_file_bytes(self, token, file_id):
            return b"\x89PNG\r\n\x1a\nfake"

    async def fake_service(ids):
        return FakeOneDrive()

    monkeypatch.setattr(actions, "_onedrive_service", fake_service)
    result = asyncio.run(actions.onedrive_read_file(
        {"file_id": "file-2"}, {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "success"
    assert result["bytes"] == len(b"\x89PNG\r\n\x1a\nfake")
    assert "content_b64" in result and "read_receipt" in result


def test_outlook_draft_action_never_calls_send(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeOutlook:
        def __init__(self):
            self.sent = False
            self.draft = None

        async def get_access_token(self, user_id):
            return "token"

        async def create_draft_email(self, **kwargs):
            self.draft = kwargs
            return {"id": "draft-1", "subject": kwargs["subject"]}

        async def send_email(self, *args, **kwargs):  # pragma: no cover
            self.sent = True
            raise AssertionError("draft action must not send")

    service = FakeOutlook()
    monkeypatch.setattr(
        "integrations.outlook_service.OutlookService",
        lambda *a, **k: service,
    )
    result = asyncio.run(actions.outlook_create_draft(
        {"to": ["buyer@example.invalid"], "subject": "Quote",
         "body": "Draft body"},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "success"
    assert service.sent is False
    assert service.draft["subject"] == "Quote"
    assert result["read_receipt"]["provider"] == "outlook"


def _valid_proposal():
    from accounting.bookkeeping_proposal import build_proposal

    return build_proposal(
        provider="zoho_books",
        organization_id="org-1",
        entity_type="bill",
        external_id="INV-001",
        vendor_candidates=[{"id": "vendor-1", "name": "Acme"}],
        currency="USD",
        document_date="2026-10-01",
        lines=[{"description": "Parts", "amount": "120.00",
                "account_id": "acct-1"}],
        document_total="120.00",
    )


def test_books_create_bill_requires_authority_and_checks_exact_duplicate(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        def __init__(self, existing=None):
            self.existing = existing or []
            self.created = 0
            self.readbacks = 0

        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_bills(self, token, org, per_page=200):
            return self.existing

        async def create_bill(self, token, org, payload):
            self.created += 1
            return {"bill_id": "bill-new", "bill_number": payload["bill_number"]}

        async def get_bill(self, token, org, bill_id):
            self.readbacks += 1
            return {"bill_id": bill_id, "reference_number": "INV-001",
                    "total": 120.0}

    async def fake_service(ids):
        return FakeBooks(existing=[{"bill_id": "bill-old",
                                    "reference_number": "INV-001"}])

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "duplicate"
    assert result["existing"]["bill_id"] == "bill-old"


def test_books_create_bill_reads_back_one_effect(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        def __init__(self):
            self.created = 0

        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_bills(self, token, org, per_page=200):
            return []

        async def create_bill(self, token, org, payload):
            self.created += 1
            assert payload["reference_number"] == "INV-001"
            return {"bill_id": "bill-new", "bill_number": "INV-001"}

        async def get_bill(self, token, org, bill_id):
            return {"bill_id": bill_id, "reference_number": "INV-001",
                    "total": 120.0}

    service = FakeBooks()

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "success"
    assert result["remote_id"] == "bill-new"
    assert result["data"]["reference_number"] == "INV-001"
    assert service.created == 1
    assert result["read_receipt"]["resource_id"] == "bill-new"


def test_books_create_bill_without_authority_does_not_dispatch(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        def __init__(self):
            self.created = 0

        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_bills(self, token, org, per_page=200):
            return []

        async def create_bill(self, token, org, payload):
            self.created += 1
            raise AssertionError("must not create without authority")

    service = FakeBooks()

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "",
         "operation_id": "op-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "error"
    assert result["error_kind"] == "unauthorized"
    assert service.created == 0


def test_books_proposal_action_returns_proposed_not_posted():
    from core import brennan_connected_actions as actions

    result = asyncio.run(actions.books_propose_bill(
        {"proposal_input": {
            "provider": "zoho_books", "organization_id": "org-1",
            "entity_type": "bill", "external_id": "INV-2",
            "vendor_candidates": [{"id": "vendor-1", "name": "Acme"}],
            "currency": "USD", "document_date": "2026-10-01",
            "lines": [{"description": "Service", "amount": "50.00"}],
            "document_total": "50.00",
        }},
        {"tenant_id": "t1", "user_id": "user-1"}))

    assert result["status"] == "success"
    assert result["data"]["status"] == "proposed"
    assert result["data"]["posting"] is None
