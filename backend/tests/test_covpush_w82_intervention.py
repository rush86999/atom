# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/active_intervention_service.

All provider availability flags and singletons are patched at the module
level (stripe_service / gmail_service / outlook_service) — no network, no
real integrations, no LLM spend.

Coverage targets:
- execute_intervention: handler dispatch + unknown-action ValueError.
- _handle_draft_retention_email: gmail success (draft id), gmail no-draft,
  gmail exception, outlook success, outlook missing user_id, outlook
  exception, no provider available.
- _handle_cancel_subscription: missing subscription_id, missing stripe_token,
  stripe success, BUG W82-1 (stripe API error must NOT be reported as
  COMPLETED — fail-open), stripe unavailable.
- _handle_bulk_remind_invoices: empty invoices, no valid recipients, gmail
  success / no-result / exception, outlook success / missing user_id /
  send-failed / exception, no provider available.
- Singleton: module-level `active_intervention_service` is an
  ActiveInterventionService instance.
"""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.active_intervention_service import (
    ActiveInterventionService,
    active_intervention_service,
)


@pytest.fixture()
def service():
    return ActiveInterventionService()


class TestExecuteIntervention:
    @pytest.mark.asyncio
    async def test_dispatches_to_handler(self, service):
        handler = AsyncMock(return_value={"status": "COMPLETED"})
        with patch.object(service, "_handle_draft_retention_email", new=handler):
            result = await service.execute_intervention(
                "iv-1", "draft_retention_email", {"client_name": "Acme"}
            )
        assert result == {"status": "COMPLETED"}
        handler.assert_awaited_once_with({"client_name": "Acme"})

    @pytest.mark.asyncio
    async def test_unknown_action_raises(self, service):
        with pytest.raises(ValueError, match="No handler for action"):
            await service.execute_intervention("iv-1", "delete_everything", {})


class TestDraftRetentionEmail:
    @pytest.mark.asyncio
    async def test_gmail_success(self, service):
        gmail = MagicMock()
        gmail.draft_message.return_value = {"id": "draft-123"}
        with patch("core.active_intervention_service.GMAIL_AVAILABLE", True), \
             patch("core.active_intervention_service.gmail_service", gmail, create=True):
            result = await service._handle_draft_retention_email(
                {"client_name": "Acme", "admin_email": "admin@atom.ai"}
            )
        assert result["status"] == "COMPLETED"
        assert result["draft_id"] == "draft-123"
        assert result["provider"] == "gmail"
        gmail.draft_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_gmail_no_draft(self, service):
        gmail = MagicMock()
        gmail.draft_message.return_value = None
        with patch("core.active_intervention_service.GMAIL_AVAILABLE", True), \
             patch("core.active_intervention_service.gmail_service", gmail, create=True):
            result = await service._handle_draft_retention_email({})
        assert result["status"] == "FAILED"
        assert "no draft ID" in result["message"]

    @pytest.mark.asyncio
    async def test_gmail_exception(self, service):
        gmail = MagicMock()
        gmail.draft_message.side_effect = RuntimeError("SMTP down")
        with patch("core.active_intervention_service.GMAIL_AVAILABLE", True), \
             patch("core.active_intervention_service.gmail_service", gmail, create=True):
            result = await service._handle_draft_retention_email({})
        assert result["status"] == "FAILED"
        assert "SMTP down" in result["message"]

    @pytest.mark.asyncio
    async def test_outlook_missing_user_id(self, service):
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", True):
            result = await service._handle_draft_retention_email(
                {"client_name": "Acme", "provider": "outlook"}
            )
        assert result["status"] == "FAILED"
        assert "user_id" in result["message"]
        assert result["provider"] == "outlook"

    @pytest.mark.asyncio
    async def test_outlook_success(self, service):
        outlook = MagicMock()
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", True), \
             patch("core.active_intervention_service.outlook_service", outlook):
            result = await service._handle_draft_retention_email(
                {"client_name": "Acme", "provider": "outlook", "user_id": "u-1"}
            )
        assert result["status"] == "COMPLETED"
        assert result["user_id"] == "u-1"

    @pytest.mark.asyncio
    async def test_no_provider_available(self, service):
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", False), \
             patch("core.active_intervention_service.GMAIL_AVAILABLE", False):
            result = await service._handle_draft_retention_email({})
        assert result["status"] == "FAILED"
        assert "No email provider" in result["message"]

    @pytest.mark.asyncio
    async def test_defaults(self, service):
        gmail = MagicMock()
        gmail.draft_message.return_value = {"id": "d1"}
        with patch("core.active_intervention_service.GMAIL_AVAILABLE", True), \
             patch("core.active_intervention_service.gmail_service", gmail, create=True):
            result = await service._handle_draft_retention_email({})
        assert result["status"] == "COMPLETED"
        call_kwargs = gmail.draft_message.call_args.kwargs
        assert call_kwargs["to"] == "admin@example.com"


class TestCancelSubscription:
    @pytest.mark.asyncio
    async def test_missing_subscription_id(self, service):
        result = await service._handle_cancel_subscription({"stripe_token": "tok"})
        assert result["status"] == "FAILED"
        assert "subscription_id" in result["message"]

    @pytest.mark.asyncio
    async def test_missing_stripe_token(self, service):
        result = await service._handle_cancel_subscription({"subscription_id": "sub_1"})
        assert result["status"] == "FAILED"
        assert "stripe_token" in result["message"]

    @pytest.mark.asyncio
    async def test_stripe_success(self, service):
        stripe = MagicMock()
        stripe.cancel_subscription.return_value = {"id": "sub_1", "status": "canceled"}
        with patch("core.active_intervention_service.STRIPE_AVAILABLE", True), \
             patch("core.active_intervention_service.stripe_service", stripe):
            result = await service._handle_cancel_subscription(
                {"subscription_id": "sub_1", "stripe_token": "sk_test"}
            )
        assert result["status"] == "COMPLETED"
        assert result["stripe_response"]["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_stripe_api_error_not_reported_as_completed(self, service):
        """BUG W82-1: a Stripe API error was reported as COMPLETED with a
        'Simulated Stripe cancellation' message (fail-open for a financial
        operation — a subscription that was NOT canceled is reported to the
        user/agent as success)."""
        stripe = MagicMock()
        stripe.cancel_subscription.side_effect = RuntimeError("card_declined")
        with patch("core.active_intervention_service.STRIPE_AVAILABLE", True), \
             patch("core.active_intervention_service.stripe_service", stripe):
            result = await service._handle_cancel_subscription(
                {"subscription_id": "sub_1", "stripe_token": "sk_test"}
            )
        assert result["status"] == "FAILED"
        assert "Simulated" not in result["message"]
        assert "card_declined" in result["message"]

    @pytest.mark.asyncio
    async def test_stripe_unavailable(self, service):
        with patch("core.active_intervention_service.STRIPE_AVAILABLE", False):
            result = await service._handle_cancel_subscription(
                {"subscription_id": "sub_1", "stripe_token": "sk_test"}
            )
        assert result["status"] == "FAILED"
        assert "unavailable" in result["message"]


class TestBulkRemindInvoices:
    @pytest.mark.asyncio
    async def test_empty_invoices(self, service):
        result = await service._handle_bulk_remind_invoices({"invoices": []})
        assert result["status"] == "COMPLETED"
        assert "No overdue invoices" in result["message"]

    @pytest.mark.asyncio
    async def test_no_valid_recipients(self, service):
        result = await service._handle_bulk_remind_invoices(
            {"invoices": [{"id": "I-1", "amount": 5}]}
        )
        assert result["status"] == "FAILED"
        assert "No valid recipient emails" in result["message"]

    @pytest.mark.asyncio
    async def test_gmail_success(self, service):
        gmail = MagicMock()
        gmail.send_message.return_value = {"id": "msg-1"}
        with patch("core.active_intervention_service.GMAIL_AVAILABLE", True), \
             patch("core.active_intervention_service.gmail_service", gmail, create=True):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [
                    {"email": "a@x.com", "id": "INV-1", "amount": 100},
                    {"email": "b@x.com", "id": "INV-2", "amount": 200},
                ]}
            )
        assert result["status"] == "COMPLETED"
        assert result["recipient_count"] == 2
        call_kwargs = gmail.send_message.call_args.kwargs
        assert call_kwargs["bcc"] == "a@x.com, b@x.com"

    @pytest.mark.asyncio
    async def test_gmail_no_result(self, service):
        gmail = MagicMock()
        gmail.send_message.return_value = None
        with patch("core.active_intervention_service.GMAIL_AVAILABLE", True), \
             patch("core.active_intervention_service.gmail_service", gmail, create=True):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [{"email": "a@x.com"}]}
            )
        assert result["status"] == "FAILED"
        assert "no result" in result["message"]

    @pytest.mark.asyncio
    async def test_gmail_exception(self, service):
        gmail = MagicMock()
        gmail.send_message.side_effect = RuntimeError("burst limit")
        with patch("core.active_intervention_service.GMAIL_AVAILABLE", True), \
             patch("core.active_intervention_service.gmail_service", gmail, create=True):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [{"email": "a@x.com"}]}
            )
        assert result["status"] == "FAILED"
        assert "burst limit" in result["message"]

    @pytest.mark.asyncio
    async def test_outlook_missing_user_id(self, service):
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", True):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [{"email": "a@x.com"}], "provider": "outlook"}
            )
        assert result["status"] == "FAILED"
        assert result["provider"] == "outlook"

    @pytest.mark.asyncio
    async def test_outlook_success(self, service):
        outlook = MagicMock()
        outlook.send_email_enhanced = AsyncMock(return_value=True)
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", True), \
             patch("core.active_intervention_service.outlook_service", outlook):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [{"email": "a@x.com"}], "provider": "outlook", "user_id": "u-9"}
            )
        assert result["status"] == "COMPLETED"
        assert result["recipient_count"] == 1
        assert result["user_id"] == "u-9"

    @pytest.mark.asyncio
    async def test_outlook_send_failed(self, service):
        outlook = MagicMock()
        outlook.send_email_enhanced = AsyncMock(return_value=False)
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", True), \
             patch("core.active_intervention_service.outlook_service", outlook):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [{"email": "a@x.com"}], "provider": "outlook", "user_id": "u-9"}
            )
        assert result["status"] == "FAILED"
        assert "Outlook send failed" in result["message"]

    @pytest.mark.asyncio
    async def test_outlook_exception(self, service):
        outlook = MagicMock()
        outlook.send_email_enhanced = AsyncMock(side_effect=RuntimeError("graph down"))
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", True), \
             patch("core.active_intervention_service.outlook_service", outlook):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [{"email": "a@x.com"}], "provider": "outlook", "user_id": "u-9"}
            )
        assert result["status"] == "FAILED"
        assert "graph down" in result["message"]

    @pytest.mark.asyncio
    async def test_no_provider_available(self, service):
        with patch("core.active_intervention_service.OUTLOOK_AVAILABLE", False), \
             patch("core.active_intervention_service.GMAIL_AVAILABLE", False):
            result = await service._handle_bulk_remind_invoices(
                {"invoices": [{"email": "a@x.com"}]}
            )
        assert result["status"] == "FAILED"
        assert "No email provider" in result["message"]


class TestSingleton:
    def test_module_singleton_is_service(self):
        assert isinstance(active_intervention_service, ActiveInterventionService)


class TestImportBranches:
    """Import-time availability branches (HAS_STRIPE / GMAIL_AVAILABLE /
    OUTLOOK_AVAILABLE) via module reload with a stubbed __import__.
    sys.modules is restored afterwards so no state leaks into other tests."""

    def test_all_import_variants(self):
        import builtins
        import importlib
        import sys
        import types

        orig_module = sys.modules["core.active_intervention_service"]
        real_import = builtins.__import__

        def _make_provider_module(name, attrs):
            mod = types.ModuleType(name)
            for k, v in attrs.items():
                setattr(mod, k, v)
            return mod

        def fake_import(name, *args, **kwargs):
            if name == "integrations.stripe_service":
                return _make_provider_module(name, {"stripe_service": object()})
            if name == "integrations.gmail_service":
                return _make_provider_module(name, {"gmail_service": object()})
            if name == "integrations.outlook_service_enhanced":
                raise ImportError("simulated missing outlook")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=fake_import):
                reloaded = importlib.reload(orig_module)
            assert reloaded.HAS_STRIPE is True
            assert reloaded.STRIPE_AVAILABLE is True
            assert reloaded.GMAIL_AVAILABLE is True
            assert reloaded.OUTLOOK_AVAILABLE is False
        finally:
            sys.modules["core.active_intervention_service"] = orig_module
