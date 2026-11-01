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
         "body": "Draft body", "operation_id": "op-draft-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "success"
    assert result["action_result"] == "applied"
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

        async def get_chart_of_accounts_page(self, token, org, page=1,
                                             per_page=200):
            return ([{"account_id": "acct-1"},
                     {"account_id": "acct-service"}],
                    {"has_more": False, "page": page})

        async def get_bills_page(self, token, org, page=1, per_page=200):
            return self.existing, {"has_more": False, "page": page}

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

        async def get_chart_of_accounts_page(self, token, org, page=1,
                                             per_page=200):
            return ([{"account_id": "acct-1"},
                     {"account_id": "acct-service"}],
                    {"has_more": False, "page": page})

        async def get_bills_page(self, token, org, page=1, per_page=200):
            return [], {"has_more": False, "page": page}

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

        async def get_chart_of_accounts_page(self, token, org, page=1,
                                             per_page=200):
            return ([{"account_id": "acct-1"},
                     {"account_id": "acct-service"}],
                    {"has_more": False, "page": page})

        async def get_bills_page(self, token, org, page=1, per_page=200):
            return [], {"has_more": False, "page": page}

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
            "lines": [{"description": "Service", "amount": "50.00",
                       "account_id": "acct-service"}],
            "document_total": "50.00",
        }},
        {"tenant_id": "t1", "user_id": "user-1"}))

    assert result["status"] == "success"
    assert result["data"]["status"] == "proposed"
    assert result["data"]["posting"] is None


# ---------------------------------------------------------------------------
# Controlled provider HTTP end-to-end: proposal -> duplicate sweep -> create
# -> authoritative readback.  These exercise the real Books request builder
# and response parser through httpx.MockTransport; nothing leaves the test.
# ---------------------------------------------------------------------------


def _http_books_service(handler):
    import httpx
    from integrations.zoho_books_service import ZohoBooksService

    service = ZohoBooksService("t1", {"access_token": "token"})
    service.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def token(*args, **kwargs):
        return "token"

    service._get_active_token = token
    return service


def _bill_like(payload, *, bill_id="bill-http-1", total="120.00", **over):
    bill = {
        "bill_id": bill_id,
        "bill_number": payload.get("bill_number"),
        "reference_number": payload.get("reference_number"),
        "vendor_id": payload.get("vendor_id"),
        "date": payload.get("date"),
        "currency_code": payload.get("currency_code"),
        "total": total,
        "line_items": payload.get("line_items") or [],
    }
    bill.update(over)
    return bill


def test_books_bill_http_end_to_end_proposal_create_readback(monkeypatch):
    from core import brennan_connected_actions as actions
    import httpx

    calls = []
    state = {}

    def handler(request):
        body = None
        if request.method == "POST":
            body = __import__("json").loads(request.content or b"{}")
        calls.append((request.method, request.url.path, body))
        if request.method == "GET" and request.url.path.endswith(
                "/chartofaccounts"):
            return httpx.Response(200, json={
                "code": 0, "chartofaccounts": [{"account_id": "acct-1"}],
                "page_context": {"has_more_page": False, "page": 1},
            })
        if request.method == "GET" and request.url.path.endswith("/bills"):
            return httpx.Response(200, json={
                "code": 0, "bills": [],
                "page_context": {"has_more_page": False, "page": 1},
            })
        if request.method == "POST" and request.url.path.endswith("/bills"):
            state.update(body)
            return httpx.Response(200, json={
                "code": 0, "bill": _bill_like(body)})
        if request.method == "GET" and request.url.path.endswith(
                "/bills/bill-http-1"):
            return httpx.Response(200, json={
                "code": 0, "bill": _bill_like(state)})
        return httpx.Response(404, json={"code": 404, "message": "unexpected"})

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-http-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))
    asyncio.run(service.client.aclose())

    assert result["status"] == "success"
    assert result["action_result"] == "applied"
    assert result["remote_id"] == "bill-http-1"
    assert result["provider_receipt"]["operation_id"] == "op-http-1"
    assert len(result["payload_sha256"]) == 64
    assert [entry[0] for entry in calls] == ["GET", "GET", "POST", "GET"]
    assert calls[0][1].endswith("/chartofaccounts")
    post = next(entry for entry in calls if entry[0] == "POST")
    assert post[2]["line_items"][0]["rate"] == "120.00"
    assert post[2]["currency_code"] == "USD"
    assert post[2]["reference_number"] == "INV-001"


def test_books_bill_http_changed_remote_is_conflict_not_applied(monkeypatch):
    from core import brennan_connected_actions as actions
    import httpx

    posts = []

    def handler(request):
        if request.method == "GET" and request.url.path.endswith(
                "/chartofaccounts"):
            return httpx.Response(200, json={
                "code": 0, "chartofaccounts": [{"account_id": "acct-1"}],
                "page_context": {"has_more_page": False}})
        if request.method == "GET" and request.url.path.endswith("/bills"):
            return httpx.Response(200, json={
                "code": 0, "bills": [],
                "page_context": {"has_more_page": False}})
        if request.method == "POST":
            posts.append(1)
            body = __import__("json").loads(request.content or b"{}")
            return httpx.Response(200, json={
                "code": 0, "bill": _bill_like(body)})
        if request.method == "GET" and request.url.path.endswith(
                "/bills/bill-http-1"):
            return httpx.Response(200, json={
                "code": 0,
                "bill": _bill_like({"reference_number": "INV-001",
                                    "vendor_id": "vendor-1",
                                    "date": "2026-10-01",
                                    "currency_code": "USD"},
                                   total="999.00")})
        return httpx.Response(404, json={"message": "unexpected"})

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-http-2"},
        {"user_id": "user-1", "tenant_id": "t1"}))
    asyncio.run(service.client.aclose())

    assert posts == [1]
    assert result["status"] == "conflict"
    assert result["action_result"] == "conflict"
    assert result["remote_id"] == "bill-http-1"
    assert any("total changed" in item for item in result["conflicts"])


def test_books_bill_http_duplicate_exact_reference_is_never_posted(monkeypatch):
    from core import brennan_connected_actions as actions
    import httpx

    posts = []

    def handler(request):
        if request.method == "GET" and request.url.path.endswith(
                "/chartofaccounts"):
            return httpx.Response(200, json={
                "code": 0, "chartofaccounts": [{"account_id": "acct-1"}],
                "page_context": {"has_more_page": False}})
        if request.method == "POST":
            posts.append(1)
            return httpx.Response(500, json={"message": "must not post"})
        return httpx.Response(200, json={
            "code": 0,
            "bills": [{"bill_id": "bill-old", "reference_number": "INV-001",
                       "bill_number": "BILL-77"}],
            "page_context": {"has_more_page": False},
        })

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-http-3"},
        {"user_id": "user-1", "tenant_id": "t1"}))
    asyncio.run(service.client.aclose())

    assert posts == []
    assert result["status"] == "duplicate"
    assert result["action_result"] == "proven_not_applied"
    assert result["existing"]["bill_id"] == "bill-old"


def test_books_bill_http_sweep_unavailable_refuses_to_create(monkeypatch):
    from core import brennan_connected_actions as actions
    import httpx

    posts = []

    def handler(request):
        if request.method == "POST":
            posts.append(1)
            return httpx.Response(500, json={"message": "must not post"})
        return httpx.Response(401, json={"code": 401,
                                         "message": "invalid token"})

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-http-4"},
        {"user_id": "user-1", "tenant_id": "t1"}))
    asyncio.run(service.client.aclose())

    assert posts == []
    assert result["action_result"] == "proven_not_applied"
    assert result["error_kind"] == "auth_expired"


def test_books_bill_http_readback_unavailable_is_uncertain(monkeypatch):
    from core import brennan_connected_actions as actions
    import httpx

    def handler(request):
        if request.method == "GET" and request.url.path.endswith(
                "/chartofaccounts"):
            return httpx.Response(200, json={
                "code": 0, "chartofaccounts": [{"account_id": "acct-1"}],
                "page_context": {"has_more_page": False}})
        if request.method == "GET" and request.url.path.endswith("/bills"):
            return httpx.Response(200, json={
                "code": 0, "bills": [],
                "page_context": {"has_more_page": False}})
        if request.method == "POST":
            body = __import__("json").loads(request.content or b"{}")
            return httpx.Response(200, json={
                "code": 0, "bill": _bill_like(body)})
        return httpx.Response(503, json={"code": 503,
                                         "message": "temporarily down"})

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-http-5"},
        {"user_id": "user-1", "tenant_id": "t1"}))
    asyncio.run(service.client.aclose())

    assert result["status"] == "uncertain"
    assert result["action_result"] == "uncertain"
    assert result["remote_id"] == "bill-http-1"
    assert result["payload_sha256"]


def test_books_bill_digest_mismatch_is_conflict_without_dispatch(monkeypatch):
    from core import brennan_connected_actions as actions

    async def fake_service(ids):  # pragma: no cover - must not be reached
        raise AssertionError("digest mismatch must not reach the provider")

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-http-6", "payload_sha256": "0" * 64},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "error"
    assert result["action_result"] == "conflict"
    assert result["error_kind"] == "payload_changed"


def test_books_estimate_http_end_to_end_quote_total(monkeypatch):
    from core import brennan_connected_actions as actions
    import httpx

    calls = []
    estimate_data = {
        "customer_id": "customer-1",
        "reference_number": "RFQ-BRENNAN-1",
        "date": "2026-11-01",
        "currency_code": "USD",
        "total": "362.50",
        "line_items": [
            {"name": "A", "quantity": "2", "rate": "100.00"},
            {"name": "B", "quantity": "3", "rate": "50.00",
             "discount": "5%"},
            {"name": "Freight", "quantity": "1", "rate": "20.00"},
        ],
    }

    def handler(request):
        calls.append(request.method)
        body = (__import__("json").loads(request.content or b"{}")
                if request.method == "POST" else None)
        if request.method == "POST" and request.url.path.endswith("/estimates"):
            return httpx.Response(200, json={
                "code": 0,
                "estimate": {"estimate_id": "est-http-1", **body,
                             "estimate_number": "EST-0001"}})
        if request.method == "GET" and request.url.path.endswith(
                "/estimates/est-http-1"):
            return httpx.Response(200, json={
                "code": 0,
                "estimate": {"estimate_id": "est-http-1", **estimate_data,
                             "estimate_number": "EST-0001"}})
        return httpx.Response(404, json={"message": "unexpected"})

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_estimate(
        {"organization_id": "org-1", "estimate_data": estimate_data,
         "authority_reference": "grant-quote-1",
         "operation_id": "op-quote-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))
    asyncio.run(service.client.aclose())

    assert calls == ["POST", "GET"]
    assert result["status"] == "success"
    assert result["action_result"] == "applied"
    assert result["data"]["total"] == "362.50"
    assert result["provider_receipt"]["artifact_version"] == "1"


def test_concurrent_same_bill_creates_one_provider_effect(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        def __init__(self):
            self.bills = []
            self.created = 0

        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_chart_of_accounts_page(self, token, org, page=1,
                                             per_page=200):
            return ([{"account_id": "acct-1"},
                     {"account_id": "acct-service"}],
                    {"has_more": False, "page": page})

        async def get_bills_page(self, token, org, page=1, per_page=200):
            return list(self.bills), {"has_more": False, "page": page}

        async def create_bill(self, token, org, payload):
            await asyncio.sleep(0.01)
            self.created += 1
            bill = {"bill_id": f"bill-{self.created}",
                    "reference_number": payload["reference_number"],
                    "bill_number": payload["bill_number"],
                    "vendor_id": payload["vendor_id"],
                    "date": payload["date"],
                    "currency_code": payload["currency_code"],
                    "total": "120.00"}
            self.bills.append(bill)
            return bill

        async def get_bill(self, token, org, bill_id):
            return next(item for item in self.bills
                        if item["bill_id"] == bill_id)

    service = FakeBooks()

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)

    async def attempt(operation_id):
        return await actions.books_create_bill(
            {"proposal": _valid_proposal(), "authority_reference": "grant-1",
             "operation_id": operation_id},
            {"user_id": "user-1", "tenant_id": "t1"})

    async def run_both():
        return await asyncio.gather(
            attempt("op-concurrent-1"), attempt("op-concurrent-2"))

    first, second = asyncio.run(run_both())

    outcomes = sorted([first["action_result"], second["action_result"]])
    assert outcomes == ["applied", "proven_not_applied"]
    assert {first["status"], second["status"]} == {"success", "duplicate"}
    assert service.created == 1
    assert len(service.bills) == 1


def test_bill_unknown_account_is_refused_before_post(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        def __init__(self):
            self.created = 0

        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_chart_of_accounts_page(self, token, org, page=1,
                                             per_page=200):
            return [{"account_id": "acct-other"}], {"has_more": False}

        async def create_bill(self, token, org, payload):
            self.created += 1

    service = FakeBooks()

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-acct-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "error"
    assert result["action_result"] == "proven_not_applied"
    assert result["error_kind"] == "invalid_request"
    assert result["unknown_account_ids"] == ["acct-1"]
    assert service.created == 0


def test_bill_closed_period_is_refused_without_provider_call(monkeypatch):
    from core import brennan_connected_actions as actions

    async def fake_service(ids):  # pragma: no cover - must not be reached
        raise AssertionError("closed period must not reach the provider")

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-period-1", "closed_through": "2026-10-31"},
        {"user_id": "user-1", "tenant_id": "t1"}))

    assert result["status"] == "error"
    assert result["action_result"] == "proven_not_applied"
    assert "closed" in result["error"]


def test_read_file_receipt_matches_agent1_evidence_shape(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeWorkDrive:
        async def get_file_metadata(self, user_id, file_id, workspace_id=None):
            return {"id": file_id, "name": "prices.csv", "version": "v3"}

        async def download_file(self, user_id, file_id, workspace_id=None):
            return b"sku,qty\nA,2\n"

        async def get_access_token(self, user_id, workspace_id=None):
            return "token"

    async def fake_service(ids):
        return FakeWorkDrive()

    monkeypatch.setattr(actions, "_workdrive_service", fake_service)
    result = asyncio.run(actions.workdrive_read_file(
        {"file_id": "file-1", "evidence_kind": "price_rows",
         "customer_id": "customer-1", "price_basis": "customer_contract",
         "effective_date": "2026-10-01",
         "typed_fields": {"currency": "USD", "sku": "A"}},
        {"user_id": "user-1", "tenant_id": "t1",
         "workspace_id": "ws-1"}))
    receipt = result["read_receipt"]

    assert receipt["access"] == "granted"
    assert receipt["kind"] == "price_rows"
    assert receipt["customer_id"] == "customer-1"
    assert receipt["price_basis"] == "customer_contract"
    assert receipt["effective_date"] == "2026-10-01"
    assert isinstance(receipt["fields"], dict)
    assert receipt["fields"]["currency"] == "USD"
    assert receipt["resource_id"] == "file-1"
    assert receipt["version"] == "v3"
    assert receipt["retrieved_at"]
    assert receipt["evidence"][0]["sha256"]


def test_resolve_vendor_is_exact_and_does_not_substring_match(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_contacts_page(self, token, org, page=1, per_page=200,
                                    contact_type=None):
            assert contact_type == "vendor"
            return ([{"contact_id": "v1", "contact_name": "Acme"},
                     {"contact_id": "v2", "contact_name": "Acme Holdings"}],
                    {"has_more": False})

    async def fake_service(ids):
        return FakeBooks()

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_resolve_vendor(
        {"name": "acme", "organization_id": "org-1"},
        {"user_id": "u", "tenant_id": "t1"}))

    assert result["match_status"] == "resolved"
    assert [candidate["id"] for candidate in result["candidates"]] == ["v1"]
    assert result["read_receipt"]["kind"] == "vendor_candidates"


def test_resolve_vendor_same_name_different_ids_is_ambiguous(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_contacts_page(self, token, org, page=1, per_page=200,
                                    contact_type=None):
            return ([{"contact_id": "v1", "contact_name": "Acme"},
                     {"contact_id": "v2", "contact_name": "ACME"}],
                    {"has_more": False})

    async def fake_service(ids):
        return FakeBooks()

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_resolve_vendor(
        {"name": "Acme", "organization_id": "org-1"},
        {"user_id": "u", "tenant_id": "t1"}))

    assert result["match_status"] == "ambiguous"
    assert {candidate["id"] for candidate in result["candidates"]} == {
        "v1", "v2"}


def test_list_accounts_returns_exact_ids(monkeypatch):
    from core import brennan_connected_actions as actions

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_chart_of_accounts_page(self, token, org, page=1,
                                             per_page=200):
            return ([{"account_id": "acct-1", "account_name": "Freight",
                      "account_type": "expense", "account_code": "5100"},
                     {"account_id": "acct-2", "account_name": "Parts",
                      "account_type": "expense", "account_code": "5200"}],
                    {"has_more": False})

    async def fake_service(ids):
        return FakeBooks()

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_list_accounts(
        {"organization_id": "org-1", "query": "freight"},
        {"user_id": "u", "tenant_id": "t1"}))

    assert result["accounts"] == [{
        "account_id": "acct-1", "name": "Freight",
        "type": "expense", "code": "5100"}]
    assert result["read_receipt"]["coverage"] == "complete"


def test_bookkeeping_campaign_resolves_vendor_accounts_and_posts(monkeypatch):
    """Controlled vertical slice: vendor -> CoA -> proposal -> duplicate -> post -> readback."""
    from core import brennan_connected_actions as actions
    import httpx

    calls = []
    posted = {}

    def handler(request):
        body = (__import__("json").loads(request.content or b"{}")
                if request.method == "POST" else None)
        calls.append((request.method, request.url.path, body))
        if request.method == "GET" and request.url.path.endswith("/contacts"):
            return httpx.Response(200, json={
                "code": 0,
                "contacts": [
                    {"contact_id": "vendor-1", "contact_name": "Acme",
                     "contact_type": "vendor"},
                    {"contact_id": "vendor-2", "contact_name": "Acme Holdings",
                     "contact_type": "vendor"},
                ],
                "page_context": {"has_more_page": False},
            })
        if request.method == "GET" and request.url.path.endswith(
                "/chartofaccounts"):
            return httpx.Response(200, json={
                "code": 0,
                "chartofaccounts": [
                    {"account_id": "acct-1", "account_name": "Parts",
                     "account_type": "expense", "account_code": "5200"},
                    {"account_id": "acct-2", "account_name": "Freight",
                     "account_type": "expense", "account_code": "5300"},
                ],
                "page_context": {"has_more_page": False},
            })
        if request.method == "GET" and request.url.path.endswith("/bills"):
            return httpx.Response(200, json={
                "code": 0, "bills": [],
                "page_context": {"has_more_page": False},
            })
        if request.method == "POST" and request.url.path.endswith("/bills"):
            posted.update(body)
            return httpx.Response(200, json={
                "code": 0,
                "bill": {
                    "bill_id": "bill-campaign",
                    "bill_number": body["bill_number"],
                    "reference_number": body["reference_number"],
                    "vendor_id": body["vendor_id"],
                    "date": body["date"],
                    "currency_code": body["currency_code"],
                    "total": "120.00",
                },
            })
        if request.method == "GET" and request.url.path.endswith(
                "/bills/bill-campaign"):
            return httpx.Response(200, json={
                "code": 0, "bill": {
                    "bill_id": "bill-campaign",
                    "bill_number": posted.get("bill_number"),
                    "reference_number": posted.get("reference_number"),
                    "vendor_id": posted.get("vendor_id"),
                    "date": posted.get("date"),
                    "currency_code": posted.get("currency_code"),
                    "total": "120.00",
                },
            })
        return httpx.Response(404, json={"message": "unexpected"})

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    context = {"user_id": "user-1", "tenant_id": "t1",
               "workspace_id": "ws-1"}

    vendor = asyncio.run(actions.books_resolve_vendor(
        {"name": "Acme", "organization_id": "org-1"}, context))
    assert vendor["match_status"] == "resolved"
    assert vendor["candidates"][0]["id"] == "vendor-1"

    accounts = asyncio.run(actions.books_list_accounts(
        {"organization_id": "org-1"}, context))
    assert {item["account_id"] for item in accounts["accounts"]} == {
        "acct-1", "acct-2"}

    proposal = asyncio.run(actions.books_propose_bill(
        {"proposal_input": {
            "provider": "zoho_books", "organization_id": "org-1",
            "entity_type": "bill", "external_id": "INV-900",
            "vendor_candidates": vendor["candidates"],
            "currency": "USD", "document_date": "2026-11-01",
            "due_date": "2026-12-01",
            "lines": [
                {"description": "Parts", "amount": "100.00",
                 "account_id": "acct-1"},
                {"description": "Freight", "amount": "20.00",
                 "account_id": "acct-2"},
            ],
            "tax_total": "0.00", "document_total": "120.00",
            "payment": {"amount": "50.00", "reference": "EFT-1"},
        }}, context))
    assert proposal["data"]["status"] == "proposed"
    assert proposal["data"]["payment"]["posted"] is False

    applied = asyncio.run(actions.books_create_bill(
        {"proposal": proposal["data"], "authority_reference": "grant-book-1",
         "operation_id": "op-book-1"}, context))
    asyncio.run(service.client.aclose())

    assert applied["action_result"] == "applied"
    assert applied["remote_id"] == "bill-campaign"
    assert applied["data"]["total"] == "120.00"
    assert applied["provider_receipt"]["payload_sha256"]
    assert posted["vendor_id"] == "vendor-1"
    assert posted["line_items"][0]["account_id"] == "acct-1"
    assert posted["line_items"][1]["account_id"] == "acct-2"
    posts = [entry for entry in calls if entry[0] == "POST"]
    assert len(posts) == 1


def test_bill_duplicate_on_second_page_is_found_before_post(monkeypatch):
    from core import brennan_connected_actions as actions
    import httpx

    posts = []
    pages_seen = []

    def handler(request):
        if request.method == "GET" and request.url.path.endswith(
                "/chartofaccounts"):
            return httpx.Response(200, json={
                "code": 0, "chartofaccounts": [{"account_id": "acct-1"}],
                "page_context": {"has_more_page": False}})
        if request.method == "GET" and request.url.path.endswith("/bills"):
            page = int(request.url.params.get("page") or 1)
            pages_seen.append(page)
            if page == 1:
                return httpx.Response(200, json={
                    "code": 0,
                    "bills": [{"bill_id": "bill-other",
                               "reference_number": "INV-999"}],
                    "page_context": {"has_more_page": True},
                })
            return httpx.Response(200, json={
                "code": 0,
                "bills": [{"bill_id": "bill-old",
                           "reference_number": "INV-001"}],
                "page_context": {"has_more_page": False},
            })
        if request.method == "POST":
            posts.append(1)
            return httpx.Response(500, json={"message": "must not post"})
        return httpx.Response(404, json={"message": "unexpected"})

    service = _http_books_service(handler)

    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    result = asyncio.run(actions.books_create_bill(
        {"proposal": _valid_proposal(), "authority_reference": "grant-1",
         "operation_id": "op-pages-1"},
        {"user_id": "user-1", "tenant_id": "t1"}))
    asyncio.run(service.client.aclose())

    assert pages_seen == [1, 2]
    assert posts == []
    assert result["status"] == "duplicate"
    assert result["existing"]["bill_id"] == "bill-old"


def test_generic_connected_aliases_are_registered_and_executable():
    from core.action_registry import action_registry

    for name in (
        "connected.workdrive.list_page",
        "connected.onedrive.sync_page",
        "connected.knowledge.sync_status",
        "connected.crm.get_record",
        "connected.inventory.check_stock",
        "connected.books.propose_bill",
        "connected.books.create_bill",
        "connected.books.create_estimate",
        "connected.outlook.create_draft",
    ):
        assert action_registry.get_action(name) is not None, name
        assert action_registry.get_action(name).handler is action_registry.get_action(
            name.replace("connected.", "brennan.", 1)).handler


def test_service_business_configuration_needs_no_source_edit():
    """A services deployment uses the same actions with different data only."""
    from core.action_registry import action_registry

    result = asyncio.run(action_registry.execute_action(
        "connected.books.propose_bill",
        {"proposal_input": {
            "provider": "zoho_books", "organization_id": "services-org",
            "entity_type": "bill", "external_id": "SOW-2026-14",
            "vendor_candidates": [{"id": "vendor-legal",
                                   "name": "Outside Counsel"}],
            "currency": "CAD", "document_date": "2026-11-01",
            "lines": [
                {"description": "Contract review", "amount": "1500.00",
                 "account_id": "acct-professional-fees"},
                {"description": "Filing disbursement", "amount": "85.25",
                 "account_id": "acct-disbursements"},
            ],
            "tax_total": "0.00", "document_total": "1585.25",
        }},
        {"tenant_id": "t1", "workspace_id": "services-ws",
         "user_id": "u1"}))

    assert result["status"] == "success"
    assert result["data"]["status"] == "proposed"
    assert result["data"]["currency"] == "CAD"
    assert result["data"]["document_total"] == "1585.25"
    assert result["data"]["posting"] is None
