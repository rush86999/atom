"""Registered bookkeeping campaign: evidence -> proposal -> one create -> readback."""
from __future__ import annotations

import asyncio

import pytest

from core.action_registry import action_registry
from core import connected_actions as actions


class FakeBooks:
    def __init__(self, *, contacts=None, accounts=None, bills=None,
                 create_error=None, readback="full", sweep_error=None):
        self.contacts = contacts or []
        self.accounts = accounts or [
            {"account_id": "acct-1", "account_name": "Parts"},
            {"account_id": "acct-2", "account_name": "Freight"},
        ]
        self.bills = list(bills or [])
        self.create_error = create_error
        self.readback = readback
        self.sweep_error = sweep_error
        self.created = 0
        self.readbacks = 0
        self.payload = None

    async def _get_active_token(self, *args, **kwargs):
        return "token"

    async def get_contacts_page(self, token, org, page=1, per_page=200,
                                contact_type=None):
        return list(self.contacts), {"has_more": False}

    async def get_chart_of_accounts_page(self, token, org, page=1,
                                         per_page=200):
        return list(self.accounts), {"has_more": False}

    async def get_bills_page(self, token, org, page=1, per_page=200):
        if self.sweep_error:
            raise self.sweep_error
        return list(self.bills), {"has_more": False}

    async def create_bill(self, token, org, payload):
        if self.create_error:
            raise self.create_error
        self.created += 1
        self.payload = payload
        return {"bill_id": "bill-1", "bill_number": payload["bill_number"]}

    async def get_bill(self, token, org, bill_id):
        self.readbacks += 1
        payload = self.payload or {}
        if self.readback == "sparse":
            return {"bill_id": bill_id, "total": "120.00"}
        line_items = payload.get("line_items") or []
        if self.readback == "wrong":
            line_items = [{"line_item_id": "l1", "name": "Wrong",
                           "quantity": "1", "rate": "999.00",
                           "account_id": "acct-1"}]
        return {
            "bill_id": bill_id,
            "bill_number": payload.get("bill_number"),
            "reference_number": payload.get("reference_number"),
            "vendor_id": payload.get("vendor_id"),
            "date": payload.get("date"),
            "due_date": payload.get("due_date"),
            "currency_code": payload.get("currency_code"),
            "total": "120.00",
            "sub_total": "120.00",
            "tax_total": "0.00",
            "discount_total": "0.00",
            "line_items": line_items,
        }


def _proposal(**over):
    value = {
        "provider": "zoho_books", "organization_id": "org-1",
        "entity_type": "bill", "external_id": "INV-REG-1",
        "vendor_candidates": [{"id": "vendor-1", "name": "Acme"}],
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
    }
    value.update(over)
    return value


def _install(monkeypatch, service):
    async def fake_service(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_service)
    return service


def _propose(payload):
    return asyncio.run(action_registry.execute_action(
        "connected.books.propose_bill",
        {"proposal_input": payload},
        {"tenant_id": "t1", "workspace_id": "ws-1", "user_id": "u1"}))


def _create(proposal, **over):
    args = {
        "proposal": proposal, "authority_reference": "grant-book-1",
        "operation_id": "op-reg-1",
    }
    args.update(over)
    return asyncio.run(action_registry.execute_action(
        "connected.books.create_bill", args,
        {"tenant_id": "t1", "workspace_id": "ws-1", "user_id": "u1"}))


def test_registered_bookkeeping_happy_path_one_create_and_readback(monkeypatch):
    service = _install(monkeypatch, FakeBooks(
        contacts=[{"contact_id": "vendor-1", "contact_name": "Acme"}]))
    vendor = asyncio.run(action_registry.execute_action(
        "connected.books.resolve_vendor",
        {"name": "Acme", "organization_id": "org-1"},
        {"tenant_id": "t1", "workspace_id": "ws-1", "user_id": "u1"}))
    assert vendor["match_status"] == "resolved"
    accounts = asyncio.run(action_registry.execute_action(
        "connected.books.list_accounts", {"organization_id": "org-1"},
        {"tenant_id": "t1", "workspace_id": "ws-1", "user_id": "u1"}))
    assert {item["account_id"] for item in accounts["accounts"]} == {
        "acct-1", "acct-2"}

    proposal = _propose(_proposal())
    assert proposal["data"]["status"] == "proposed"
    assert proposal["data"]["payment"]["posted"] is False
    assert proposal["data"]["posting"] is None

    result = _create(proposal["data"])
    assert result["action_result"] == "applied"
    assert result["verification"]["status"] == "verified"
    assert result["remote_id"] == "bill-1"
    assert service.created == 1
    assert service.readbacks == 1


def test_missing_or_ambiguous_vendor_never_creates(monkeypatch):
    service = _install(monkeypatch, FakeBooks())
    missing = _propose(_proposal(vendor_candidates=[]))
    assert missing["data"]["status"] == "needs_clarification"
    ambiguous = _propose(_proposal(vendor_candidates=[
        {"id": "vendor-1", "name": "Acme"},
        {"id": "vendor-2", "name": "Acme"},
    ]))
    assert ambiguous["data"]["status"] == "needs_clarification"
    assert service.created == 0


def test_closed_period_and_changed_payload_never_create(monkeypatch):
    service = _install(monkeypatch, FakeBooks())
    proposal = _propose(_proposal())["data"]
    closed = _create(proposal, closed_through="2026-12-31")
    assert closed["action_result"] == "proven_not_applied"
    changed = _create(proposal, payload_sha256="0" * 64)
    assert changed["action_result"] == "conflict"
    assert service.created == 0


def test_incomplete_duplicate_sweep_never_creates(monkeypatch):
    from integrations.provider_errors import unavailable

    service = _install(monkeypatch, FakeBooks(sweep_error=unavailable(
        "zoho_books", "get_bills", "duplicate sweep unavailable")))
    result = _create(_propose(_proposal())["data"])
    assert result["action_result"] == "proven_not_applied"
    assert service.created == 0


def test_incomplete_readback_is_uncertain_without_second_create(monkeypatch):
    service = _install(monkeypatch, FakeBooks(readback="sparse"))
    result = _create(_propose(_proposal())["data"])
    assert result["action_result"] == "uncertain"
    assert result["verification"]["status"] == "incomplete"
    assert result["remote_id"] == "bill-1"
    assert service.created == 1
    assert service.readbacks == 2


def test_mismatched_readback_is_conflict_without_second_create(monkeypatch):
    service = _install(monkeypatch, FakeBooks(readback="wrong"))
    result = _create(_propose(_proposal())["data"])
    assert result["action_result"] == "conflict"
    assert result["verification"]["status"] == "mismatch"
    assert result["remote_id"] == "bill-1"
    assert service.created == 1
    assert service.readbacks == 1
