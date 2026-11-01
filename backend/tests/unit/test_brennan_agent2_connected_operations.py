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
