"""Joint Agent 1 + Agent 2 controlled quote campaign.

Agent 1's independent decimal calculator produces the total; Agent 2's
registered connected actions post the estimate and create the Outlook draft.
No provider is contacted: the adapter services are controlled fakes, and no
send path exists in the draft action.
"""
from __future__ import annotations

import asyncio

import pytest

from core.action_registry import action_registry
from core.quote_evidence import compute_quote_totals


def test_joint_quote_total_posts_and_drafts_without_sending(monkeypatch):
    from core import connected_actions as actions

    lines = [
        {"sku": "A", "quantity": "2", "unit_price": "100.00",
         "currency": "USD", "discount_percent": "0"},
        {"sku": "B", "quantity": "3", "unit_price": "50.00",
         "currency": "USD", "discount_percent": "5"},
    ]
    totals = compute_quote_totals(lines, freight="20.00", tax="none")
    assert totals["total"] == "362.50"
    assert totals["currency"] == "USD"

    captured = {}

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_estimates_page(self, token, org, page=1, per_page=200):
            return [], {"has_more": False, "page": page}

        async def create_estimate(self, token, org, data):
            captured["estimate_payload"] = data
            return {"estimate_id": "est-joint", "estimate_number": "EST-1"}

        async def get_estimate(self, token, org, estimate_id):
            data = captured["estimate_payload"]
            return {
                "estimate_id": estimate_id,
                "estimate_number": "EST-1",
                "reference_number": data["reference_number"],
                "customer_id": data["customer_id"],
                "date": data["date"],
                "currency_code": data["currency_code"],
                "total": totals["total"],
                "sub_total": totals["subtotal"],
                "tax_total": totals["tax"],
                "line_items": data["line_items"],
            }

    async def fake_books(ids):
        return FakeBooks()

    monkeypatch.setattr(actions, "_books_service", fake_books)

    estimate_data = {
        "customer_id": "customer-1",
        "reference_number": "RFQ-JOINT-1",
        "date": "2026-11-01",
        "currency_code": totals["currency"],
        "total": totals["total"],
        "sub_total": totals["subtotal"],
        "tax_total": totals["tax"],
        "line_items": [
            {"name": line["sku"], "quantity": line["quantity"],
             "rate": line["unit_price"],
             "discount": f"{line['discount_percent']}%"}
            for line in totals["lines"]
        ],
    }
    posted = asyncio.run(action_registry.execute_action(
        "connected.books.create_estimate",
        {"organization_id": "org-joint", "estimate_data": estimate_data,
         "authority_reference": "grant-joint-quote-1",
         "operation_id": "op-joint-quote-1"},
        {"user_id": "user-1", "tenant_id": "t1", "workspace_id": "ws-1"}))
    assert posted["action_result"] == "applied"
    assert posted["data"]["total"] == "362.50"

    class FakeOutlook:
        def __init__(self):
            self.sent = False
            self.draft = None

        async def _get_access_token(self, user_id):
            return "token"

        async def create_draft_email(self, **kwargs):
            self.draft = kwargs
            return {"id": "draft-joint", "subject": kwargs["subject"]}

        async def send_email(self, *args, **kwargs):  # pragma: no cover
            self.sent = True
            raise AssertionError("draft action must not send")

    outlook = FakeOutlook()
    monkeypatch.setattr(
        "integrations.outlook_service.OutlookService",
        lambda *a, **k: outlook)
    draft = asyncio.run(action_registry.execute_action(
        "connected.outlook.create_draft",
        {"to": ["buyer@example.invalid"],
         "subject": "Quote RFQ-JOINT-1",
         "body": f"Quoted total: {posted['data']['total']} USD",
         "operation_id": "op-joint-draft-1"},
        {"user_id": "user-1", "tenant_id": "t1", "workspace_id": "ws-1"}))

    assert draft["action_result"] == "applied"
    assert outlook.sent is False
    assert "362.50" in outlook.draft["body"]
    assert draft["read_receipt"]["provider"] == "outlook"


def test_executor_adapter_preserves_connected_action_outcome():
    import uuid

    from core.assignment_executor import _action_registry_adapter

    async def outcome_action(args, context):
        outcome = args["outcome"]
        status = {
            "applied": "success",
            "proven_not_applied": "error",
            "conflict": "conflict",
            "uncertain": "uncertain",
        }[outcome]
        result = {"status": status, "action_result": outcome,
                  "remote_id": "remote-1"}
        if outcome == "proven_not_applied":
            result["error_kind"] = "invalid_request"
        return result

    name = f"test.joint.outcome.{uuid.uuid4().hex[:8]}"
    action_registry.register(name, outcome_action,
                             description="controlled outcome",
                             effects=[{"effect": "record_created"}])

    async def run(outcome):
        return await _action_registry_adapter(
            {"action": name, "arguments": {"outcome": outcome}},
            {"tenant_id": "t1", "workspace_id": "ws-1",
             "employee_id": "u1", "run_id": "run-1",
             "assignment_id": "assignment-1", "agent_id": "agent-1"})

    applied = asyncio.run(run("applied"))
    duplicate = asyncio.run(run("proven_not_applied"))
    conflict = asyncio.run(run("conflict"))
    uncertain = asyncio.run(run("uncertain"))

    assert applied["status"] == "applied"
    assert duplicate["status"] == "failed"
    assert conflict["status"] == "uncertain"
    assert uncertain["status"] == "uncertain"
