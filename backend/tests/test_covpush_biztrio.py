"""Coverage-push tests for QuickBooks / Asana / HubSpot integration services.

TDD bug fixes landed in this file:
- asana create_task crashes when API response omits/mulls projects (url building)
- hubspot execute_entity_operation mangles plural entity names ("companies" -> "companie")
- hubspot sync_to_postgres_cache silently writes zero metrics when unauthenticated
- hubspot get_analytics crashes on a single deal with null properties
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
import requests

from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter

from integrations.atom_quickbooks_integration_service import (
    AccountType,
    AtomQuickBooksIntegrationService,
    FinancialReportType,
    PaymentStatus,
    TransactionType,
)
from integrations.asana_service import AsanaService
from integrations.hubspot_service import HubSpotService


# ============================================================================
# Shared fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def _patch_gateways(monkeypatch):
    """Keep the shared circuit-breaker/rate-limiter singletons inert."""
    monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(rate_limiter, "is_rate_limited", AsyncMock(return_value=(False, 30)))


# ============================================================================
# QuickBooks integration service
# ============================================================================

import integrations.atom_quickbooks_integration_service as qb_mod


def make_qb(config: dict = None) -> AtomQuickBooksIntegrationService:
    cfg = {
        "enable_stripe_integration": False,
        "auto_categorization": False,
        "fraud_detection": False,
        "financial_analytics": False,
        "expense_tracking": False,
        "tax_calculation": False,
        "real_time_sync": False,
        "quickbooks_access_token": "test-token",
        "quickbooks_company_id": "123",
        "quickbooks_environment": "sandbox",
    }
    if config:
        cfg.update(config)
    return AtomQuickBooksIntegrationService(config=cfg)


def mock_http_client(status: int = 200, body: dict = None, method: str = "post"):
    """Patch httpx.AsyncClient with a context manager returning a mock client."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = "boom"
    resp.json.return_value = body if body is not None else {}
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=resp))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    patcher = patch.object(qb_mod.httpx, "AsyncClient", return_value=cm)
    return patcher, client, resp


def install_ai_symbols(monkeypatch):
    """Make the AI classes resolvable (module lacks them when enterprise imports fail)."""
    monkeypatch.setattr(qb_mod, "AIRequest", lambda **kw: kw, raising=False)
    monkeypatch.setattr(qb_mod, "AITaskType", SimpleNamespace(CONTENT_ANALYSIS="ca"), raising=False)
    monkeypatch.setattr(qb_mod, "AIModelType", SimpleNamespace(GPT_4="gpt4"), raising=False)
    monkeypatch.setattr(qb_mod, "AIServiceType", SimpleNamespace(OPENAI="openai"), raising=False)


class TestQuickbooksInit:
    def test_init_defaults(self):
        svc = AtomQuickBooksIntegrationService()
        assert svc.is_initialized is False
        assert svc.quickbooks_config["environment"] == "sandbox"
        assert svc.quickbooks_config["base_url"].startswith("https://sandbox-quickbooks")
        assert svc.stripe_integration is None
        assert svc.analytics_metrics["total_transactions"] == 0
        assert svc.webhook_handlers == {}
        assert svc.payment_workflows == {}
        assert svc.expense_rules == {}
        assert svc.tax_rates == {}
        assert "company_info" in svc.api_endpoints

    def test_init_production_url(self):
        svc = AtomQuickBooksIntegrationService(config={"quickbooks_environment": "production"})
        assert svc.quickbooks_config["base_url"] == "https://quickbooks.api.intuit.com/v3"

    def test_init_stripe_enabled_import_error(self):
        svc = AtomQuickBooksIntegrationService(config={"enable_stripe_integration": True})
        assert svc.stripe_integration is None

    def test_init_custom_services(self):
        security = Mock()
        automation = Mock()
        ai = Mock()
        svc = AtomQuickBooksIntegrationService(config={
            "security_service": security,
            "automation_service": automation,
            "ai_service": ai,
        })
        assert svc.enterprise_security is security
        assert svc.enterprise_automation is automation
        assert svc.ai_service is ai
        assert set(svc.platform_integrations) == {
            "slack", "teams", "google_chat", "discord", "telegram", "whatsapp", "zoom"
        }

    def test_initialize_success(self):
        svc = make_qb()
        for name in (
            "_test_quickbooks_connection", "_initialize_stripe_connection", "_setup_webhooks",
            "_setup_payment_workflows", "_setup_expense_tracking", "_setup_tax_calculation",
            "_setup_enterprise_features", "_setup_security_and_compliance",
            "_load_existing_financial_data", "_start_real_time_sync",
        ):
            setattr(svc, name, AsyncMock(return_value=None))
        assert asyncio.run(svc.initialize()) is True
        assert svc.is_initialized is True

    def test_initialize_failure(self):
        svc = make_qb()
        svc._test_quickbooks_connection = AsyncMock(side_effect=RuntimeError("nope"))
        assert asyncio.run(svc.initialize()) is False
        assert svc.is_initialized is False

    def test_initialize_stripe_connection_skipped(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        svc._test_quickbooks_connection = AsyncMock(return_value=None)
        svc._initialize_stripe_connection = AsyncMock(return_value=None)
        for name in (
            "_setup_webhooks", "_setup_payment_workflows", "_setup_expense_tracking",
            "_setup_tax_calculation", "_setup_enterprise_features",
            "_setup_security_and_compliance", "_load_existing_financial_data",
        ):
            setattr(svc, name, AsyncMock(return_value=None))
        assert asyncio.run(svc.initialize()) is True
        svc._initialize_stripe_connection.assert_awaited_once()


class TestQuickbooksSetup:
    async def _run_setup(self):
        svc = make_qb()
        await svc._setup_webhooks()
        await svc._setup_payment_workflows()
        await svc._setup_expense_tracking()
        await svc._setup_tax_calculation()
        await svc._setup_enterprise_features()
        await svc._setup_security_and_compliance()
        await svc._load_existing_financial_data()
        await svc._start_real_time_sync()
        await svc._initialize_stripe_connection()
        assert svc.webhook_handlers == {}
        assert svc.payment_workflows == {}
        assert svc.expense_rules == {}
        assert svc.tax_rates == {}

    def test_all_setup_helpers(self):
        asyncio.run(self._run_setup())


class TestQuickbooksInvoice:
    def test_create_invoice_success(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(200, {"Invoice": {"Id": "INV-1", "TotalAmt": 100.0}})
        with patcher:
            svc._cache_invoice = AsyncMock()
            svc._trigger_payment_workflows = AsyncMock()
            result = asyncio.run(svc.create_invoice({
                "customer_id": "C1",
                "amount": 100.0,
                "issue_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "due_date": datetime(2026, 1, 15, tzinfo=timezone.utc),
                "line_items": [],
                "notes": "note",
                "custom_fields": [{"DefinitionId": "1", "StringValue": "x"}],
            }, platform="slack"))
        assert result["success"] is True
        assert result["invoice_id"] == "INV-1"
        assert svc.analytics_metrics["total_invoices"] == 1
        assert svc.analytics_metrics["average_invoice_amount"] == 100.0
        assert svc.performance_metrics["api_response_time"] >= 0
        svc._trigger_payment_workflows.assert_awaited_once()

    def test_create_invoice_with_stripe_and_platform(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        svc._create_stripe_payment_intent = AsyncMock(return_value={"id": "pi_1"})
        notify = AsyncMock()
        svc._notify_platform_invoice_created = notify
        patcher, client, resp = mock_http_client(200, {"Invoice": {"Id": "INV-2", "TotalAmt": 50.0}})
        with patcher:
            result = asyncio.run(svc.create_invoice({"amount": 50.0}, platform="slack"))
        assert result["success"] is True
        svc._create_stripe_payment_intent.assert_awaited_once()
        notify.assert_awaited_once()

    def test_create_invoice_security_check_failed(self):
        svc = make_qb({"enable_enterprise_features": True})
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "blocked"})
        result = asyncio.run(svc.create_invoice({"amount": 1.0}))
        assert result["success"] is False
        assert result["error"] == "blocked"

    def test_create_invoice_ai_analysis(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"suggested_pricing_adjustment": 5.0, "optimization_tips": ["tip"]}
        ))
        svc = make_qb({"auto_categorization": True, "ai_service": ai})
        patcher, client, resp = mock_http_client(200, {"Invoice": {"Id": "I", "TotalAmt": 1}})
        with patcher:
            result = asyncio.run(svc.create_invoice({"amount": 10.0}))
        assert result["success"] is True
        assert svc.performance_metrics["categorization_time"] >= 0

    def test_create_invoice_circuit_breaker_open(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(return_value=False))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_invoice({}))
        assert exc.value.status_code == 503

    def test_create_invoice_rate_limited(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0)))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_invoice({}))
        assert exc.value.status_code == 429

    def test_create_invoice_api_error(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(400)
        with patcher:
            result = asyncio.run(svc.create_invoice({"amount": 1.0}))
        assert result["success"] is False
        assert "400" in result["error"]

    def test_create_invoice_exception(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(200)
        client.post = AsyncMock(side_effect=RuntimeError("network down"))
        with patcher:
            result = asyncio.run(svc.create_invoice({"amount": 1.0}))
        assert result["success"] is False


class TestQuickbooksPayment:
    def test_create_payment_success(self):
        svc = make_qb({"fraud_detection": True})
        patcher, client, resp = mock_http_client(200, {"Payment": {"Id": "P-1"}})
        with patcher:
            svc._cache_payment = AsyncMock()
            svc._trigger_payment_workflows = AsyncMock()
            result = asyncio.run(svc.create_payment({
                "customer_id": "C1",
                "amount": 200.0,
                "date": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "currency": "USD",
                "payment_method_id": "PM1",
                "invoice_id": "INV-1",
                "notes": "n",
            }, platform="teams"))
        assert result["success"] is True
        assert result["payment_id"] == "P-1"
        assert svc.analytics_metrics["total_payments"] == 1
        assert svc.analytics_metrics["payment_success_rate"] == 100.0

    def test_create_payment_fraud_detected(self):
        svc = make_qb({"fraud_detection": True})
        svc._perform_fraud_detection = AsyncMock(
            return_value={"is_fraudulent": True, "reason": "High amount"})
        result = asyncio.run(svc.create_payment({"amount": 100000.0}))
        assert result["success"] is False
        assert "Fraud detected" in result["error"]

    def test_create_payment_stripe_processing_failure(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        svc._process_stripe_payment = AsyncMock(
            return_value={"success": False, "error": "Stripe down"})
        result = asyncio.run(svc.create_payment({
            "amount": 10.0, "stripe_payment_intent_id": "pi_x"}))
        assert result["success"] is False
        assert result["error"] == "Stripe down"

    def test_create_payment_stripe_charge_id(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        svc._process_stripe_payment = AsyncMock(
            return_value={"success": True, "charge_id": "ch_1"})
        patcher, client, resp = mock_http_client(200, {"Payment": {"Id": "P-2"}})
        with patcher:
            result = asyncio.run(svc.create_payment({
                "amount": 10.0, "stripe_payment_intent_id": "pi_x"}))
        assert result["success"] is True
        svc._process_stripe_payment.assert_awaited_once()

    def test_create_payment_api_failure_updates_rate(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(500)
        with patcher:
            result = asyncio.run(svc.create_payment({"amount": 5.0}))
        assert result["success"] is False
        assert svc.analytics_metrics["payment_success_rate"] == 0.0

    def test_create_payment_circuit_breaker_open(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(return_value=False))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_payment({}))
        assert exc.value.status_code == 503

    def test_create_payment_exception(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(200)
        client.post = AsyncMock(side_effect=TimeoutError("timed out"))
        with patcher:
            result = asyncio.run(svc.create_payment({}))
        assert result["success"] is False


class TestQuickbooksExpense:
    def test_create_expense_success_with_attachments(self):
        svc = make_qb({"auto_categorization": True})
        svc._categorize_expense = AsyncMock(return_value="Software")
        patcher, client, resp = mock_http_client(200, {
            "Purchase": {"Id": "E-1", "TxnDate": "2026-01-10", "TotalAmt": 25.0}})
        with patcher:
            svc._cache_expense = AsyncMock()
            svc._trigger_payment_workflows = AsyncMock()
            result = asyncio.run(svc.create_expense({
                "account_id": "A1",
                "amount": 25.0,
                "date": datetime(2026, 1, 10, tzinfo=timezone.utc),
                "currency": "USD",
                "payment_method_id": "PM",
                "vendor_id": "V1",
                "description": "office chair",
                "class_id": "CL1",
                "notes": "n",
                "receipt_attachments": [{"id": "r1"}, {"id": "r2"}],
            }, platform="slack"))
        assert result["success"] is True
        assert result["expense_id"] == "E-1"
        assert svc.analytics_metrics["total_expenses"] == 1
        assert svc.analytics_metrics["expense_trends"]["2026-01"] == [25.0]

    def test_create_expense_security_failed(self):
        svc = make_qb({"enable_enterprise_features": True})
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "no"})
        result = asyncio.run(svc.create_expense({"amount": 1.0}))
        assert result["success"] is False

    def test_create_expense_api_error(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(400)
        with patcher:
            result = asyncio.run(svc.create_expense({"amount": 1.0}))
        assert result["success"] is False

    def test_create_expense_rate_limited(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0)))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_expense({}))
        assert exc.value.status_code == 429

    def test_create_expense_exception(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(200)
        client.post = AsyncMock(side_effect=OSError("fail"))
        with patcher:
            result = asyncio.run(svc.create_expense({}))
        assert result["success"] is False


class TestQuickbooksCustomer:
    def test_create_customer_success(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(200, {"Customer": {"Id": "CUST-1"}})
        with patcher:
            result = asyncio.run(svc.create_customer("Acme", "a@b.com"))
        assert result["success"] is True
        assert result["customer_id"] == "CUST-1"

    def test_create_customer_api_error(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(422)
        with patcher:
            result = asyncio.run(svc.create_customer("Acme", "a@b.com"))
        assert result["success"] is False
        assert result["error"] == "boom"

    def test_create_customer_circuit_breaker_open(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(return_value=False))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_customer("Acme", "a@b.com"))
        assert exc.value.status_code == 503

    def test_create_customer_rate_limited(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0)))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_customer("Acme", "a@b.com"))
        assert exc.value.status_code == 429

    def test_create_customer_exception(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(200)
        client.post = AsyncMock(side_effect=RuntimeError("x"))
        with patcher:
            result = asyncio.run(svc.create_customer("Acme", "a@b.com"))
        assert result["success"] is False


class TestQuickbooksReports:
    def _run(self, report_type):
        svc = make_qb({"financial_analytics": True})
        return asyncio.run(svc.generate_financial_report(
            report_type,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 31, tzinfo=timezone.utc),
        ))

    @pytest.mark.parametrize("report_type", [
        FinancialReportType.PROFIT_AND_LOSS,
        FinancialReportType.BALANCE_SHEET,
        FinancialReportType.CASH_FLOW,
        FinancialReportType.TRIAL_BALANCE,
        FinancialReportType.AGED_RECEIVABLES,
        FinancialReportType.AGED_PAYABLES,
        FinancialReportType.SALES_REPORT,
        FinancialReportType.EXPENSE_REPORT,
        FinancialReportType.TAX_REPORT,
    ])
    def test_all_report_types(self, report_type):
        result = self._run(report_type)
        assert result["success"] is True
        assert result["report"]["report_type"] is report_type
        assert result["report"]["data"]["report_type"] == report_type.value
        assert result["report"]["insights"] == []
        assert svc_perf_ok(result)

    def test_unsupported_report_type(self):
        svc = make_qb()
        result = asyncio.run(svc.generate_financial_report(
            "nonsense", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc)))
        assert result["success"] is False
        assert "Unsupported report type" in result["error"]

    def test_report_with_ai_insights(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"insights": ["grow"], "recommendations": ["sell"]}))
        svc = make_qb({"financial_analytics": True, "ai_service": ai})
        result = asyncio.run(svc.generate_financial_report(
            FinancialReportType.PROFIT_AND_LOSS,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 31, tzinfo=timezone.utc),
        ))
        assert result["success"] is True
        assert result["report"]["insights"] == ["grow"]
        assert result["report"]["recommendations"] == ["sell"]

    def test_report_circuit_breaker_open(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(return_value=False))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.generate_financial_report(
                FinancialReportType.PROFIT_AND_LOSS,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 31, tzinfo=timezone.utc)))
        assert exc.value.status_code == 503

    def test_report_rate_limited(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0)))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.generate_financial_report(
                FinancialReportType.PROFIT_AND_LOSS,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 31, tzinfo=timezone.utc)))
        assert exc.value.status_code == 429


def svc_perf_ok(result):
    return result["generation_time"] >= 0


class TestQuickbooksAIPaths:
    def test_analyze_invoice_ai_success(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"suggested_discount": 2.0, "customer_payment_risk": "high",
                                  "estimated_payment_time": 45, "optimization_tips": ["t"]}))
        svc = make_qb({"ai_service": ai})
        result = asyncio.run(svc._analyze_invoice_with_ai({"amount": 10}))
        assert result["suggested_discount"] == 2.0
        assert result["customer_payment_risk"] == "high"

    def test_analyze_invoice_ai_not_ok(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False, output_data=None))
        svc = make_qb({"ai_service": ai})
        result = asyncio.run(svc._analyze_invoice_with_ai({"amount": 10}))
        assert result["optimal_payment_terms"] == "30"
        assert result["invoice_optimization_tips"] == []

    def test_analyze_invoice_ai_exception(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("ai down"))
        svc = make_qb({"ai_service": ai})
        result = asyncio.run(svc._analyze_invoice_with_ai({"amount": 10}))
        assert result["estimated_payment_time"] == 30

    def test_analyze_invoice_no_ai_symbols(self):
        svc = make_qb()
        result = asyncio.run(svc._analyze_invoice_with_ai({"amount": 10}))
        assert result["optimal_payment_terms"] == "30"

    def test_categorize_expense_success(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"suggested_category": "Software"}))
        svc = make_qb({"ai_service": ai})
        assert asyncio.run(svc._categorize_expense({"amount": 10})) == "Software"

    def test_categorize_expense_not_ok(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False, output_data=None))
        svc = make_qb({"ai_service": ai})
        assert asyncio.run(svc._categorize_expense({"amount": 10})) == "Other"

    def test_categorize_expense_exception(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        svc = make_qb({"ai_service": ai})
        assert asyncio.run(svc._categorize_expense({"amount": 10})) == "Other"

    def test_generate_financial_insights_no_service(self):
        svc = make_qb()
        result = asyncio.run(svc._generate_financial_insights({}, FinancialReportType.TAX_REPORT))
        assert result == {"insights": [], "recommendations": []}

    def test_generate_financial_insights_success(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"insights": ["i"], "recommendations": ["r"]}))
        svc = make_qb({"ai_service": ai})
        result = asyncio.run(svc._generate_financial_insights({}, FinancialReportType.SALES_REPORT))
        assert result["insights"] == ["i"]

    def test_generate_financial_insights_exception(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        svc = make_qb({"ai_service": ai})
        result = asyncio.run(svc._generate_financial_insights({}, FinancialReportType.TAX_REPORT))
        assert result == {"insights": [], "recommendations": []}


class TestQuickbooksSecurityAndStripe:
    def test_security_check_with_service(self):
        svc = make_qb({"security_service": Mock()})
        assert asyncio.run(svc._perform_security_check({"a": 1})) == {"passed": True}

    def test_security_check_without_service(self):
        svc = make_qb()
        assert asyncio.run(svc._perform_security_check({"a": 1})) == {"passed": True}

    def test_create_stripe_payment_intent_no_integration(self):
        svc = make_qb()
        assert asyncio.run(svc._create_stripe_payment_intent({"TotalAmt": 5})) is None

    def test_create_stripe_payment_intent_no_callable(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        svc.stripe_integration.create_payment_intent = None
        assert asyncio.run(svc._create_stripe_payment_intent({"TotalAmt": 5})) is None

    def test_create_stripe_payment_intent_success(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        svc.stripe_integration.create_payment_intent = AsyncMock(return_value={"id": "pi_1"})
        result = asyncio.run(svc._create_stripe_payment_intent({"TotalAmt": 42, "Id": "I1"}))
        assert result == {"id": "pi_1"}

    def test_create_stripe_payment_intent_exception(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        svc.stripe_integration.create_payment_intent = AsyncMock(side_effect=RuntimeError("x"))
        assert asyncio.run(svc._create_stripe_payment_intent({"TotalAmt": 42})) is None

    def test_process_stripe_payment_no_integration(self):
        svc = make_qb()
        result = asyncio.run(svc._process_stripe_payment({"stripe_payment_intent_id": "pi_1"}))
        assert result["success"] is False
        assert "not available" in result["error"]

    def test_process_stripe_payment_missing_intent(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        result = asyncio.run(svc._process_stripe_payment({}))
        assert result["success"] is False
        assert "Missing" in result["error"]

    def test_process_stripe_payment_success(self):
        svc = make_qb()
        svc.stripe_integration = Mock()
        result = asyncio.run(svc._process_stripe_payment({"stripe_payment_intent_id": "pi_9"}))
        assert result["success"] is True
        assert result["charge_id"] == "ch_pi_9"

    def test_process_stripe_payment_exception(self):
        class EvilFormat:
            def __format__(self, spec):
                raise RuntimeError("fmt boom")

        svc = make_qb()
        svc.stripe_integration = Mock()
        result = asyncio.run(svc._process_stripe_payment({"stripe_payment_intent_id": EvilFormat()}))
        assert result["success"] is False
        assert result["error"] == "fmt boom"


class TestQuickbooksNotifications:
    def test_notify_platform_not_connected(self, caplog):
        svc = make_qb()
        asyncio.run(svc._notify_platform_event("invoice_created", "slack", {"Id": "1"}))
        assert "not connected" in caplog.text

    def test_notify_platform_no_hook(self, caplog):
        svc = make_qb()

        class NoHook:
            pass

        svc.platform_integrations["slack"] = NoHook()
        asyncio.run(svc._notify_platform_event("invoice_created", "slack", {"Id": "1"}))
        assert "no notify_event hook" in caplog.text

    def test_notify_platform_success(self):
        svc = make_qb()
        integration = Mock()
        integration.notify_event = AsyncMock(return_value=None)
        svc.platform_integrations["slack"] = integration
        asyncio.run(svc._notify_platform_event("invoice_created", "slack", {"Id": "1"}))
        integration.notify_event.assert_awaited_once()

    def test_notify_platform_exception(self):
        svc = make_qb()
        integration = Mock()
        integration.notify_event = AsyncMock(side_effect=RuntimeError("x"))
        svc.platform_integrations["slack"] = integration
        asyncio.run(svc._notify_platform_event("invoice_created", "slack", {"Id": "1"}))

    def test_invoice_payment_expense_notify_wrappers(self):
        svc = make_qb()
        svc._notify_platform_event = AsyncMock()
        asyncio.run(svc._notify_platform_invoice_created({"Id": "1"}, "slack"))
        asyncio.run(svc._notify_platform_payment_created({"Id": "1"}, "slack"))
        asyncio.run(svc._notify_platform_expense_created({"Id": "1"}, "slack"))
        assert svc._notify_platform_event.await_count == 3


class TestQuickbooksConnectionAndCache:
    def test_test_connection_success(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(200, method="get")
        with patcher:
            assert asyncio.run(svc._test_quickbooks_connection()) is True

    def test_test_connection_failure(self):
        svc = make_qb()
        patcher, client, resp = mock_http_client(500, method="get")
        with patcher:
            with pytest.raises(Exception):
                asyncio.run(svc._test_quickbooks_connection())

    def test_get_auth_headers_with_token(self):
        svc = make_qb()
        headers = asyncio.run(svc._get_auth_headers())
        assert headers["Authorization"] == "Bearer test-token"

    def test_get_auth_headers_no_token(self):
        svc = make_qb({"quickbooks_access_token": None})
        with pytest.raises(Exception):
            asyncio.run(svc._get_auth_headers())

    def test_cache_invoice_with_cache(self):
        svc = make_qb()
        cache = Mock()
        cache.set = AsyncMock()
        svc.cache = cache
        asyncio.run(svc._cache_invoice({"Id": "I1"}))
        cache.set.assert_awaited_once()

    def test_cache_invoice_without_cache(self):
        svc = make_qb()
        asyncio.run(svc._cache_invoice({"Id": "I1"}))

    def test_cache_invoice_exception(self):
        svc = make_qb()
        cache = Mock()
        cache.set = AsyncMock(side_effect=RuntimeError("x"))
        svc.cache = cache
        asyncio.run(svc._cache_invoice({"Id": "I1"}))

    def test_cache_payment_and_expense(self):
        svc = make_qb()
        cache = Mock()
        cache.set = AsyncMock()
        svc.cache = cache
        asyncio.run(svc._cache_payment({"Id": "P1"}))
        asyncio.run(svc._cache_expense({"Id": "E1"}))
        assert cache.set.await_count == 2

    def test_trigger_workflows_no_automation(self):
        svc = make_qb()
        asyncio.run(svc._trigger_payment_workflows({"Id": "1"}, "created"))

    def test_trigger_workflows_with_automation(self):
        automation = Mock()
        automation._handle_event_trigger = AsyncMock()
        svc = make_qb({"automation_service": automation})
        asyncio.run(svc._trigger_payment_workflows({"Id": "1"}, "created"))
        automation._handle_event_trigger.assert_awaited_once()

    def test_trigger_workflows_exception(self):
        automation = Mock()
        automation._handle_event_trigger = AsyncMock(side_effect=RuntimeError("x"))
        svc = make_qb({"automation_service": automation})
        asyncio.run(svc._trigger_payment_workflows({"Id": "1"}, "created"))


class TestQuickbooksFraudAndStatus:
    def test_fraud_detection_high_amount(self):
        svc = make_qb()
        result = asyncio.run(svc._perform_fraud_detection({
            "amount": 50000,
            "date": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        }))
        assert result["is_fraudulent"] is False
        assert result["risk_score"] == 30
        assert "High amount" in result["risk_factors"]

    def test_fraud_detection_unusual_time(self):
        svc = make_qb()
        result = asyncio.run(svc._perform_fraud_detection({
            "amount": 10,
            "date": datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc),
        }))
        assert result["risk_score"] == 20

    def test_fraud_detection_rapid_sequence_fraudulent(self):
        svc = make_qb()
        result = asyncio.run(svc._perform_fraud_detection({
            "amount": 50000,
            "date": datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc),
            "rapid_sequence": True,
        }))
        assert result["is_fraudulent"] is True
        assert result["risk_score"] == 90

    def test_fraud_detection_clean(self):
        svc = make_qb()
        result = asyncio.run(svc._perform_fraud_detection({
            "amount": 10,
            "date": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        }))
        assert result["is_fraudulent"] is False
        assert result["risk_score"] == 0

    def test_get_service_status(self):
        svc = make_qb()
        status = asyncio.run(svc.get_service_status())
        assert status["service"] == "quickbooks_integration"
        assert status["status"] == "inactive"
        svc.is_initialized = True
        status = asyncio.run(svc.get_service_status())
        assert status["status"] == "active"

    def test_close_success(self):
        svc = make_qb()
        asyncio.run(svc.close())

    def test_close_circuit_breaker_open(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(return_value=False))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.close())
        assert exc.value.status_code == 503

    def test_close_rate_limited(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0)))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.close())
        assert exc.value.status_code == 429


class TestQuickbooksGaps:
    def test_initialize_all_flags_on(self):
        svc = make_qb({
            "expense_tracking": True, "tax_calculation": True, "real_time_sync": True,
            "enable_stripe_integration": True,
        })
        for name in (
            "_test_quickbooks_connection", "_initialize_stripe_connection", "_setup_webhooks",
            "_setup_payment_workflows", "_setup_expense_tracking", "_setup_tax_calculation",
            "_setup_enterprise_features", "_setup_security_and_compliance",
            "_load_existing_financial_data", "_start_real_time_sync",
        ):
            setattr(svc, name, AsyncMock(return_value=None))
        assert asyncio.run(svc.initialize()) is True
        svc._setup_expense_tracking.assert_awaited_once()
        svc._setup_tax_calculation.assert_awaited_once()
        svc._start_real_time_sync.assert_awaited_once()

    def test_create_payment_rate_limited(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0)))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_payment({}))
        assert exc.value.status_code == 429

    def test_create_payment_security_check_failed(self):
        svc = make_qb({"enable_enterprise_features": True})
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "blocked"})
        result = asyncio.run(svc.create_payment({"amount": 1.0}))
        assert result["success"] is False
        assert result["error"] == "blocked"

    def test_create_expense_circuit_breaker_open(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(return_value=False))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_expense({}))
        assert exc.value.status_code == 503

    def test_security_check_exception_branch(self):
        class EvilTruthy:
            def __bool__(self):
                raise RuntimeError("boom")

        svc = make_qb()
        svc.enterprise_security = EvilTruthy()
        result = asyncio.run(svc._perform_security_check({"a": 1}))
        assert result["passed"] is False
        assert result["reason"] == "boom"

    def test_cache_expense_exception(self):
        svc = make_qb()
        cache = Mock()
        cache.set = AsyncMock(side_effect=RuntimeError("x"))
        svc.cache = cache
        asyncio.run(svc._cache_expense({"Id": "E1"}))

    def test_fraud_detection_exception(self):
        svc = make_qb()
        result = asyncio.run(svc._perform_fraud_detection({"amount": "not-a-number"}))
        assert result["is_fraudulent"] is False
        assert result["risk_score"] == 0

    def test_get_service_status_with_start_time(self):
        svc = make_qb()
        svc._start_time = time.time() - 100
        status = asyncio.run(svc.get_service_status())
        assert status["status"] == "inactive"
        assert status["uptime"] > 99

    def test_close_generic_exception(self, monkeypatch):
        svc = make_qb()
        monkeypatch.setattr(circuit_breaker, "is_enabled", AsyncMock(side_effect=RuntimeError("x")))
        asyncio.run(svc.close())


    def test_generate_financial_insights_not_ok(self, monkeypatch):
        install_ai_symbols(monkeypatch)
        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False, output_data=None))
        svc = make_qb({"ai_service": ai})
        result = asyncio.run(svc._generate_financial_insights({}, FinancialReportType.SALES_REPORT))
        assert result == {"insights": [], "recommendations": []}

    def test_report_generic_exception(self):
        svc = make_qb()
        svc._generate_profit_loss_report = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(svc.generate_financial_report(
            FinancialReportType.PROFIT_AND_LOSS,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 31, tzinfo=timezone.utc),
        ))
        assert result["success"] is False

    def test_initialize_stripe_integration_success(self, monkeypatch):
        import types
        fake_module = types.ModuleType("atom_stripe_integration")
        fake_module.atom_stripe_integration = Mock()
        monkeypatch.setitem(sys.modules, "atom_stripe_integration", fake_module)
        svc = make_qb({"enable_stripe_integration": True})
        assert svc.stripe_integration is fake_module.atom_stripe_integration

    def test_cache_payment_exception(self):
        svc = make_qb()
        cache = Mock()
        cache.set = AsyncMock(side_effect=RuntimeError("x"))
        svc.cache = cache
        asyncio.run(svc._cache_payment({"Id": "P1"}))

    def test_get_service_status_exception(self):
        svc = make_qb()
        svc.quickbooks_config = None
        status = asyncio.run(svc.get_service_status())
        assert "error" in status


class TestQuickbooksModuleLevel:
    def test_global_instance(self):
        assert qb_mod.atom_quickbooks_integration_service is not None
        assert qb_mod.atom_quickbooks_integration_service.quickbooks_config["environment"] == "sandbox"
        assert qb_mod.AtomQuickbooksIntegrationService is AtomQuickBooksIntegrationService


# ============================================================================
# Asana service
# ============================================================================

import integrations.asana_service as asana_mod


class FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")


def make_asana(config: dict = None) -> AsanaService:
    cfg = {"access_token": "asana-token"}
    if config:
        cfg.update(config)
    return AsanaService(config=cfg)


@pytest.fixture
def asana_service():
    return make_asana()


@pytest.fixture
def fake_requests(monkeypatch):
    def _install(handler):
        def fake_request(method, url, **kwargs):
            return handler(method, url, kwargs)
        monkeypatch.setattr(asana_mod.requests, "request", fake_request)
    return _install


class TestAsanaInit:
    def test_init_with_token(self):
        svc = make_asana()
        assert svc.access_token == "asana-token"
        assert svc.api_base_url == "https://app.asana.com/api/1.0"
        assert svc.timeout == 30
        assert svc.max_retries == 3

    def test_init_without_token(self):
        svc = make_asana({"access_token": None})
        assert svc.access_token is None


class TestAsanaMakeRequest:
    def test_success_200(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": {"gid": "1"}}))
        result = asana_service._make_request("GET", "/users/me", "tok")
        assert result["data"]["gid"] == "1"

    def test_success_201(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(201, {"data": {"gid": "2"}}))
        result = asana_service._make_request("POST", "/tasks", "tok")
        assert result["data"]["gid"] == "2"

    def test_401_raises_permission(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(401))
        with pytest.raises(PermissionError):
            asana_service._make_request("GET", "/users/me", "tok")

    def test_429_retry_then_success(self, asana_service, fake_requests, monkeypatch):
        calls = []

        def handler(m, u, k):
            calls.append(1)
            if len(calls) < 2:
                return FakeResp(429)
            return FakeResp(200, {"data": []})

        monkeypatch.setattr("time.sleep", lambda s: None)
        fake_requests(handler)
        result = asana_service._make_request("GET", "/x", "tok")
        assert result == {"data": []}
        assert len(calls) == 2

    def test_429_exhausted(self, asana_service, fake_requests, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda s: None)
        fake_requests(lambda m, u, k: FakeResp(429))
        with pytest.raises(ConnectionError):
            asana_service._make_request("GET", "/x", "tok")

    def test_other_status_raises(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(400))
        with pytest.raises(requests.exceptions.HTTPError):
            asana_service._make_request("GET", "/x", "tok")

    def test_network_error_retries_then_success(self, asana_service, fake_requests):
        calls = []

        def handler(m, u, k):
            calls.append(1)
            if len(calls) < 3:
                raise requests.exceptions.ConnectionError("boom")
            return FakeResp(200, {"data": []})

        fake_requests(handler)
        result = asana_service._make_request("GET", "/x", "tok")
        assert result == {"data": []}
        assert len(calls) == 3

    def test_network_error_exhausted(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: (_ for _ in ()).throw(
            requests.exceptions.ConnectionError("boom")))
        with pytest.raises(requests.exceptions.ConnectionError):
            asana_service._make_request("GET", "/x", "tok")

    def test_paginated_request_two_pages(self, asana_service, fake_requests):
        pages = [
            FakeResp(200, {"data": [{"gid": "1"}], "next_page": {"offset": "abc"}}),
            FakeResp(200, {"data": [{"gid": "2"}], "next_page": None}),
        ]
        seen_offsets = []

        def handler(m, u, k):
            seen_offsets.append(k.get("params", {}).get("offset"))
            return pages.pop(0)

        fake_requests(handler)
        result = asana_service._make_paginated_request("/projects", "tok", {"limit": 50})
        assert [p["gid"] for p in result] == ["1", "2"]
        assert seen_offsets == [None, "abc"]

    def test_paginated_request_single_page(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [{"gid": "1"}]}))
        result = asana_service._make_paginated_request("/projects", "tok")
        assert [p["gid"] for p in result] == ["1"]


class TestAsanaReads:
    def test_get_user_profile_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": {
            "gid": "u1", "name": "A", "email": "a@b.c", "photo": "p", "workspaces": [{"gid": "w1"}]
        }}))
        result = asyncio.run(asana_service.get_user_profile("tok"))
        assert result["ok"] is True
        assert result["user"]["gid"] == "u1"

    def test_get_user_profile_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(401))
        result = asyncio.run(asana_service.get_user_profile("tok"))
        assert result["ok"] is False

    def test_get_workspaces_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "w1", "name": "W", "is_organization": True},
            {"gid": "w2", "name": "W2"},
        ]}))
        result = asyncio.run(asana_service.get_workspaces("tok"))
        assert result["ok"] is True
        assert result["workspaces"][0]["is_organization"] is True
        assert result["workspaces"][1]["is_organization"] is False

    def test_get_workspaces_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.get_workspaces("tok"))
        assert result["ok"] is False

    def test_get_projects_by_workspace(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "p1", "name": "P", "workspace": {"gid": "w1"}, "team": {"gid": "t1"}}
        ]}))
        result = asyncio.run(asana_service.get_projects("tok", workspace_gid="w1"))
        assert result["ok"] is True
        assert result["projects"][0]["workspace_gid"] == "w1"

    def test_get_projects_by_team(self, asana_service, fake_requests):
        captured = {}

        def handler(m, u, k):
            captured.update(k.get("params", {}))
            return FakeResp(200, {"data": []})

        fake_requests(handler)
        result = asyncio.run(asana_service.get_projects("tok", team_gid="t9"))
        assert result["ok"] is True
        assert captured["team"] == "t9"

    def test_get_projects_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.get_projects("tok"))
        assert result["ok"] is False

    def test_get_tasks_with_filters(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "t1", "name": "T", "assignee": {"gid": "u1", "name": "U"},
             "projects": [{"gid": "p1"}], "completed": True}
        ]}))
        result = asyncio.run(asana_service.get_tasks(
            "tok", project_gid="p1", assignee="u1", completed_since="2026-01-01"))
        assert result["ok"] is True
        assert result["tasks"][0]["assignee"] == "u1"
        assert result["tasks"][0]["assignee_name"] == "U"

    def test_get_tasks_workspace_no_assignee(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "t1", "name": "T", "assignee": None}
        ]}))
        result = asyncio.run(asana_service.get_tasks("tok", workspace_gid="w1"))
        assert result["tasks"][0]["assignee"] is None

    def test_get_tasks_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.get_tasks("tok"))
        assert result["ok"] is False

    def test_get_teams_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "t1", "name": "Team", "organization": {"gid": "o1"}}
        ]}))
        result = asyncio.run(asana_service.get_teams("tok", "w1"))
        assert result["ok"] is True
        assert result["teams"][0]["organization"] == "o1"

    def test_get_teams_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.get_teams("tok", "w1"))
        assert result["ok"] is False

    def test_get_users_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "u1", "name": "U", "email": "e", "photo": "p"}
        ]}))
        result = asyncio.run(asana_service.get_users("tok", "w1"))
        assert result["users"][0]["gid"] == "u1"

    def test_get_users_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.get_users("tok", "w1"))
        assert result["ok"] is False

    def test_search_tasks_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "t1", "name": "T", "projects": [{"gid": "p1"}]}
        ]}))
        result = asyncio.run(asana_service.search_tasks("tok", "w1", "query"))
        assert result["ok"] is True
        assert result["query"] == "query"
        assert result["workspace"] == "w1"

    def test_search_tasks_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.search_tasks("tok", "w1", "q"))
        assert result["ok"] is False

    def test_get_task_stories_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "s1", "text": "hi", "type": "comment", "created_by": {"gid": "u1", "name": "U"}}
        ]}))
        result = asyncio.run(asana_service.get_task_stories("tok", "t1"))
        assert result["stories"][0]["created_by_name"] == "U"

    def test_get_task_stories_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.get_task_stories("tok", "t1"))
        assert result["ok"] is False


class TestAsanaTaskMutation:
    def test_create_task_success_full(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(201, {"data": {
            "gid": "t1", "name": "T", "notes": "n", "completed": False,
            "due_on": "2026-02-01", "assignee": {"gid": "u1"},
            "projects": [{"gid": "p1"}], "created_at": "c", "modified_at": "m"
        }}))
        result = asyncio.run(asana_service.create_task("tok", {
            "name": "T", "description": "n", "due_on": "2026-02-01",
            "assignee": "u1", "projects": ["p1"], "workspace": "w1",
        }))
        assert result["ok"] is True
        assert result["task"]["url"] == "https://app.asana.com/0/p1/t1"

    def test_create_task_missing_name(self, asana_service):
        result = asyncio.run(asana_service.create_task("tok", {}))
        assert result["ok"] is False
        assert "Missing required field: name" in result["error"]

    def test_create_task_exception(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: (_ for _ in ()).throw(requests.exceptions.Timeout("slow")))
        result = asyncio.run(asana_service.create_task("tok", {"name": "T"}))
        assert result["ok"] is False

    def test_update_task_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": {
            "gid": "t1", "name": "T2", "completed": True, "assignee": {"gid": "u1"}
        }}))
        result = asyncio.run(asana_service.update_task("tok", "t1", {"name": "T2"}))
        assert result["ok"] is True
        assert result["task"]["name"] == "T2"

    def test_update_task_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(400))
        result = asyncio.run(asana_service.update_task("tok", "t1", {}))
        assert result["ok"] is False

    def test_add_task_comment_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(201, {"data": {
            "gid": "s1", "text": "nice", "created_at": "c"
        }}))
        result = asyncio.run(asana_service.add_task_comment("tok", "t1", "nice"))
        assert result["ok"] is True
        assert result["story"]["gid"] == "s1"

    def test_add_task_comment_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(500))
        result = asyncio.run(asana_service.add_task_comment("tok", "t1", "x"))
        assert result["ok"] is False


class TestAsanaCreateProject:
    def test_create_project_success_with_kwargs(self, asana_service, fake_requests):
        captured = {}

        def handler(m, u, k):
            captured.update(k.get("json") or {})
            return FakeResp(201, {"data": {
                "gid": "p1", "name": "P", "workspace": {"gid": "w1"}, "team": {"gid": "t1"}
            }})

        fake_requests(handler)
        result = asyncio.run(asana_service.create_project(
            access_token="tok", workspace_gid="w1", name="P",
            notes="n", team_gid="t1", color="light-green", public=True,
            custom_field_values={"field": "value"},
        ))
        assert result["ok"] is True
        assert result["project"]["workspace_gid"] == "w1"
        assert result["project"]["team_gid"] == "t1"
        assert captured["data"]["custom_field_values"] == {"field": "value"}
        assert captured["data"]["public"] is True

    def test_create_project_uses_instance_token(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(201, {"data": {"gid": "p1"}}))
        result = asyncio.run(asana_service.create_project(name="P"))
        assert result["ok"] is True

    def test_create_project_no_token(self):
        svc = make_asana({"access_token": None})
        result = asyncio.run(svc.create_project(name="P"))
        assert result["ok"] is False
        assert "No access token" in result["error"]

    def test_create_project_rate_limit_retry(self, asana_service, fake_requests):
        calls = []

        def handler(m, u, k):
            calls.append(1)
            if len(calls) == 1:
                raise requests.exceptions.HTTPError("429 rate limit exceeded",
                    response=FakeResp(429))
            return FakeResp(201, {"data": {"gid": "p1"}})

        fake_requests(handler)
        result = asyncio.run(asana_service.create_project(access_token="tok", name="P"))
        assert result["ok"] is True
        assert len(calls) == 2

    def test_create_project_rate_limit_string(self, asana_service, fake_requests):
        calls = []

        def handler(m, u, k):
            calls.append(1)
            if len(calls) == 1:
                raise requests.exceptions.HTTPError("rate limit hit")
            return FakeResp(201, {"data": {"gid": "p1"}})

        fake_requests(handler)
        result = asyncio.run(asana_service.create_project(access_token="tok", name="P"))
        assert result["ok"] is True

    def test_create_project_other_exception(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: (_ for _ in ()).throw(ValueError("bad")))
        result = asyncio.run(asana_service.create_project(access_token="tok", name="P"))
        assert result["ok"] is False


class TestAsanaHealthAndOps:
    def test_health_check_no_token(self):
        svc = make_asana({"access_token": None})
        result = svc.health_check()
        assert result["healthy"] is False
        assert "No access token" in result["message"]

    def test_health_check_success(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": {"name": "U", "email": "e"}}))
        result = asana_service.health_check()
        assert result["healthy"] is True
        assert result["user"]["name"] == "U"

    def test_health_check_error(self, asana_service, fake_requests):
        fake_requests(lambda m, u, k: FakeResp(401))
        result = asana_service.health_check()
        assert result["healthy"] is False
        assert result["status"] == "disconnected"

    def test_get_capabilities(self, asana_service):
        caps = asana_service.get_capabilities()
        assert caps["supports_webhooks"] is True
        assert len(caps["operations"]) == 5

    def test_get_operations(self, asana_service):
        ops = asana_service.get_operations()
        assert ops[0]["name"] == "create_task"
        assert ops[0]["complexity"] == 3

    def test_execute_operation_tenant_mismatch(self):
        svc = make_asana({"access_token": "t"})
        result = asyncio.run(svc.execute_operation("create_task", {}, {"tenant_id": "other"}))
        assert result["success"] is False
        assert "mismatch" in result["error"].lower()

    def test_execute_operation_unknown(self, asana_service):
        result = asyncio.run(asana_service.execute_operation("nope", {}))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_execute_operation_create_task(self, asana_service):
        asana_service._op_create_task = AsyncMock(return_value={"gid": "t1"})
        result = asyncio.run(asana_service.execute_operation("create_task", {}, {"tenant_id": "default"}))
        assert result["success"] is True
        assert result["result"] == {"gid": "t1"}

    def test_execute_operation_exception(self, asana_service):
        asana_service._op_get_tasks = AsyncMock(side_effect=RuntimeError("x"))
        result = asyncio.run(asana_service.execute_operation("get_tasks", {}))
        assert result["success"] is False

    def test_op_create_task_no_token(self):
        svc = make_asana({"access_token": None})
        with pytest.raises(ValueError):
            asyncio.run(svc._op_create_task({}, None))

    def test_op_create_task_failure(self, asana_service):
        asana_service.create_task = AsyncMock(return_value={"ok": False, "error": "nope"})
        with pytest.raises(Exception):
            asyncio.run(asana_service._op_create_task({}, None))

    def test_op_get_tasks_success(self, asana_service):
        asana_service.get_tasks = AsyncMock(return_value={"ok": True, "tasks": [{"gid": "1"}]})
        result = asyncio.run(asana_service._op_get_tasks({"project_gid": "p1"}, None))
        assert result == [{"gid": "1"}]

    def test_op_get_tasks_failure(self, asana_service):
        asana_service.get_tasks = AsyncMock(return_value={"ok": False, "error": "x"})
        with pytest.raises(Exception):
            asyncio.run(asana_service._op_get_tasks({}, None))

    def test_op_update_task_success(self, asana_service):
        asana_service.update_task = AsyncMock(return_value={"ok": True, "task": {"gid": "1"}})
        result = asyncio.run(asana_service._op_update_task({"task_gid": "t1", "name": "X"}, None))
        assert result["gid"] == "1"

    def test_op_update_task_failure(self, asana_service):
        asana_service.update_task = AsyncMock(return_value={"ok": False})
        with pytest.raises(Exception):
            asyncio.run(asana_service._op_update_task({"task_gid": "t1"}, None))

    def test_op_get_projects_success(self, asana_service):
        asana_service.get_projects = AsyncMock(return_value={"ok": True, "projects": []})
        result = asyncio.run(asana_service._op_get_projects({"workspace_gid": "w1"}, None))
        assert result == []

    def test_op_get_projects_failure(self, asana_service):
        asana_service.get_projects = AsyncMock(return_value={"ok": False})
        with pytest.raises(Exception):
            asyncio.run(asana_service._op_get_projects({}, None))

    def test_op_add_comment_success(self, asana_service):
        asana_service.add_task_comment = AsyncMock(return_value={"ok": True, "story": {"gid": "s1"}})
        result = asyncio.run(asana_service._op_add_comment({"task_gid": "t1", "text": "hi"}, None))
        assert result["gid"] == "s1"

    def test_op_add_comment_failure(self, asana_service):
        asana_service.add_task_comment = AsyncMock(return_value={"ok": False})
        with pytest.raises(Exception):
            asyncio.run(asana_service._op_add_comment({"task_gid": "t1"}, None))


class TestAsanaSync:
    def test_sync_to_postgres_cache_success(self, asana_service, fake_requests, monkeypatch):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": [
            {"gid": "p1", "workspace": {"gid": "w1"}}
        ]}))
        db = MagicMock()
        existing = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = existing
        session_local = MagicMock(return_value=db)
        monkeypatch.setattr("core.database.SessionLocal", session_local)
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        asana_service.get_tasks = AsyncMock(return_value={"ok": True, "tasks": [
            {"gid": "t1", "completed": True}, {"gid": "t2", "completed": False}
        ]})
        result = asyncio.run(asana_service.sync_to_postgres_cache("w1"))
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        existing.value = 1.0
        existing.last_synced_at = None
        db.commit.assert_called_once()
        db.close.assert_called_once()

    def test_sync_to_postgres_cache_new_metrics(self, asana_service, fake_requests, monkeypatch):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": []}))
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        session_local = MagicMock(return_value=db)
        monkeypatch.setattr("core.database.SessionLocal", session_local)
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        asana_service.get_tasks = AsyncMock(return_value={"ok": True, "tasks": []})
        result = asyncio.run(asana_service.sync_to_postgres_cache("w1"))
        assert result["success"] is True
        assert db.add.call_count == 3

    def test_sync_to_postgres_cache_no_token(self):
        svc = make_asana({"access_token": None})
        result = asyncio.run(svc.sync_to_postgres_cache("w1"))
        assert result["success"] is False

    def test_sync_to_postgres_cache_no_gid(self):
        svc = make_asana({"access_token": "t", "workspace_gid": None})
        result = asyncio.run(svc.sync_to_postgres_cache(None))
        assert result["success"] is False

    def test_sync_to_postgres_cache_db_error(self, asana_service, fake_requests, monkeypatch):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": []}))
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db down")
        session_local = MagicMock(return_value=db)
        monkeypatch.setattr("core.database.SessionLocal", session_local)
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        asana_service.get_tasks = AsyncMock(return_value={"ok": True, "tasks": []})
        result = asyncio.run(asana_service.sync_to_postgres_cache("w1"))
        assert result["success"] is False
        db.rollback.assert_called_once()

    def test_full_sync(self, asana_service):
        asana_service.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = asyncio.run(asana_service.full_sync("w1"))
        assert result["success"] is True
        assert result["workspace_gid"] == "w1"
        assert result["postgres_cache"]["success"] is True


class TestAsanaGaps:
    def test_call_make_request_coroutine_result(self, asana_service):
        async def async_make_request(*args, **kwargs):
            return {"data": {"gid": "p1"}}

        asana_service._make_request = async_make_request
        result = asyncio.run(asana_service.create_project(access_token="tok", name="P"))
        assert result["ok"] is True
        assert result["project"]["gid"] == "p1"

    def test_create_project_rate_limit_retry_direct(self, asana_service):
        err = requests.exceptions.HTTPError("429 rate limit exceeded", response=FakeResp(429))
        asana_service._call_make_request = AsyncMock(
            side_effect=[err, {"data": {"gid": "p1"}}])
        result = asyncio.run(asana_service.create_project(access_token="tok", name="P"))
        assert result["ok"] is True
        assert asana_service._call_make_request.await_count == 2

    def test_sync_to_postgres_cache_session_error(self, asana_service, fake_requests, monkeypatch):
        fake_requests(lambda m, u, k: FakeResp(200, {"data": []}))
        monkeypatch.setattr("core.database.SessionLocal", Mock(side_effect=RuntimeError("conn")))
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        asana_service.get_tasks = AsyncMock(return_value={"ok": True, "tasks": []})
        result = asyncio.run(asana_service.sync_to_postgres_cache("w1"))
        assert result["success"] is False

    def test_op_create_task_success(self, asana_service):
        asana_service.create_task = AsyncMock(return_value={"ok": True, "task": {"gid": "t1"}})
        result = asyncio.run(asana_service._op_create_task({"name": "T"}, None))
        assert result == {"gid": "t1"}

    @pytest.mark.parametrize("op,params", [
        ("get_tasks", {"project_gid": "p1"}),
        ("update_task", {"task_gid": "t1"}),
        ("get_projects", {"workspace_gid": "w1"}),
        ("add_comment", {"task_gid": "t1", "text": "hi"}),
    ])
    def test_op_methods_no_token(self, op, params):
        svc = make_asana({"access_token": None})
        with pytest.raises(ValueError):
            asyncio.run(getattr(svc, f"_op_{op}")(params, None))


# ============================================================================
# HubSpot service
# ============================================================================

import integrations.hubspot_service as hs_mod


def make_hubspot(config: dict = None) -> HubSpotService:
    cfg = {"access_token": "hs-token"}
    if config:
        cfg.update(config)
    return HubSpotService(config=cfg)


@pytest.fixture
def hs_service():
    return make_hubspot()


def install_http(service, method, status=200, body=None, side_effect=None):
    resp = httpx.Response(status, json=body if body is not None else {},
                          request=httpx.Request("GET", "http://test"))
    if side_effect is not None:
        setattr(service.http, method, AsyncMock(side_effect=side_effect))
    else:
        setattr(service.http, method, AsyncMock(return_value=resp))
    return resp


class TestHubspotInit:
    def test_init(self):
        svc = make_hubspot({"access_token": "a", "refresh_token": "r"})
        assert svc.base_url == "https://api.hubapi.com"
        assert svc.access_token == "a"
        assert svc.refresh_token == "r"
        assert svc.http is not None
        asyncio.run(svc.close())

    def test_get_capabilities(self, hs_service):
        caps = hs_service.get_capabilities()
        assert caps["supports_webhooks"] is True

    def test_health_check(self, hs_service):
        result = asyncio.run(hs_service.health_check())
        assert result["ok"] is True
        assert result["status"] == "healthy"

    def test_get_operations(self, hs_service):
        ops = hs_service.get_operations()
        assert ops[0]["name"] == "create_contact"


class TestHubspotExecute:
    def test_execute_operation_tenant_mismatch(self):
        svc = make_hubspot()
        result = asyncio.run(svc.execute_operation("create_contact", {}, {"tenant_id": "other"}))
        assert result["success"] is False
        assert "Tenant mismatch" in result["error"]

    def test_execute_operation_unsupported(self, hs_service):
        result = asyncio.run(hs_service.execute_operation("nope", {}))
        assert result["success"] is False

    def test_execute_operation_search_content(self, hs_service):
        hs_service.search_content = AsyncMock(return_value={"total": 1})
        result = asyncio.run(hs_service.execute_operation("search_content", {"query": "q"}))
        assert result["success"] is True
        assert result["result"]["total"] == 1

    def test_execute_operation_entity_aliases(self, hs_service):
        hs_service.execute_entity_operation = AsyncMock(return_value={"success": True})
        for op in ("create_contact", "get_contacts", "list_contacts", "get_companies", "get_deals"):
            result = asyncio.run(hs_service.execute_operation(op, {}))
            assert result["success"] is True

    def test_execute_operation_exception(self, hs_service):
        hs_service.execute_entity_operation = AsyncMock(side_effect=RuntimeError("x"))
        result = asyncio.run(hs_service.execute_operation("create_contact", {}))
        assert result["success"] is False

    def test_execute_entity_operation_create_contact(self, hs_service):
        hs_service.create_contact = AsyncMock(return_value={"id": "1"})
        result = asyncio.run(hs_service.execute_entity_operation("create", "contact", {"email": "e@e.e"}))
        assert result["success"] is True
        assert result["result"]["id"] == "1"

    def test_execute_entity_operation_get_contact(self, hs_service):
        hs_service.get_contact = AsyncMock(return_value={"id": "1"})
        result = asyncio.run(hs_service.execute_entity_operation("get", "contacts", {"contact_id": "1"}))
        assert result["success"] is True

    def test_execute_entity_operation_list_contact(self, hs_service):
        hs_service.get_contacts = AsyncMock(return_value=[])
        result = asyncio.run(hs_service.execute_entity_operation("list", "contact", {}))
        assert result["success"] is True

    def test_execute_entity_operation_company_ops(self, hs_service):
        hs_service.create_company = AsyncMock(return_value={})
        hs_service.get_company = AsyncMock(return_value={})
        hs_service.get_companies = AsyncMock(return_value=[])
        assert asyncio.run(hs_service.execute_entity_operation("create", "company", {"name": "A"}))["success"]
        assert asyncio.run(hs_service.execute_entity_operation("get", "company", {"company_id": "1"}))["success"]
        assert asyncio.run(hs_service.execute_entity_operation("list", "company", {}))["success"]

    def test_execute_entity_operation_plural_companies(self, hs_service):
        hs_service.get_companies = AsyncMock(return_value=[{"id": "c1"}])
        result = asyncio.run(hs_service.execute_entity_operation("list", "companies", {}))
        assert result["success"] is True
        assert result["result"] == [{"id": "c1"}]

    def test_execute_entity_operation_ies_plural(self, hs_service):
        result = asyncio.run(hs_service.execute_entity_operation("list", "policies", {}))
        assert result["success"] is False
        assert "not supported" in result["error"]

    def test_execute_entity_operation_deal_ops(self, hs_service):
        hs_service.create_deal = AsyncMock(return_value={})
        hs_service.get_deal = AsyncMock(return_value={})
        hs_service.get_deals = AsyncMock(return_value=[])
        assert asyncio.run(hs_service.execute_entity_operation("create", "deal", {"name": "D", "amount": 1}))["success"]
        assert asyncio.run(hs_service.execute_entity_operation("get", "deal", {"deal_id": "1"}))["success"]
        assert asyncio.run(hs_service.execute_entity_operation("list", "deal", {}))["success"]

    def test_execute_entity_operation_unknown_entity(self, hs_service):
        result = asyncio.run(hs_service.execute_entity_operation("list", "ticket", {}))
        assert result["success"] is False
        assert "not supported" in result["error"]

    def test_execute_entity_operation_not_implemented(self, hs_service):
        result = asyncio.run(hs_service.execute_entity_operation("delete", "contact", {}))
        assert result["success"] is False
        assert "not implemented" in result["error"]

    def test_execute_entity_operation_exception(self, hs_service):
        hs_service.create_contact = AsyncMock(side_effect=RuntimeError("x"))
        result = asyncio.run(hs_service.execute_entity_operation("create", "contact", {}))
        assert result["success"] is False
        assert "x" in result["error"]

    def test_execute_entity_operation_context_token(self, hs_service):
        hs_service.create_contact = AsyncMock(return_value={})
        asyncio.run(hs_service.execute_entity_operation(
            "create", "contact", {"email": "e@e.e"}, {"token": "ctx-token"}))
        hs_service.create_contact.assert_awaited_once()
        kwargs = hs_service.create_contact.await_args.kwargs
        assert kwargs["token"] == "ctx-token"


class TestHubspotAuthAndLists:
    def test_authenticate_success(self, hs_service):
        resp = httpx.Response(200, json={"access_token": "new-token"},
                              request=httpx.Request("POST", "http://t"))
        hs_service.http.post = AsyncMock(return_value=resp)
        token_data = asyncio.run(hs_service.authenticate("cid", "sec", "uri", "code"))
        assert token_data["access_token"] == "new-token"
        assert hs_service.access_token == "new-token"

    def test_authenticate_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("POST", "http://t"))
        hs_service.http.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("POST", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(hs_service.authenticate("c", "s", "u", "code"))
        assert exc.value.status_code == 400

    def test_authenticate_unexpected_error(self, hs_service):
        hs_service.http.post = AsyncMock(side_effect=RuntimeError("x"))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(hs_service.authenticate("c", "s", "u", "code"))
        assert exc.value.status_code == 500

    def test_get_contacts_success(self, hs_service):
        install_http(hs_service, "get", 200, {"results": [{"id": "1"}, {"id": "2"}]})
        result = asyncio.run(hs_service.get_contacts(limit=10, offset=20))
        assert len(result) == 2

    def test_get_contacts_no_token(self, hs_service, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_contacts())
        assert exc.value.status_code == 401

    def test_get_contacts_http_error(self, hs_service):
        resp = httpx.Response(500, request=httpx.Request("GET", "http://t"))
        hs_service.http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "500", request=httpx.Request("GET", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(hs_service.get_contacts())
        assert exc.value.status_code == 400

    def test_get_companies_success(self, hs_service):
        install_http(hs_service, "get", 200, {"results": [{"id": "c1"}]})
        result = asyncio.run(hs_service.get_companies(offset=0))
        assert result[0]["id"] == "c1"

    def test_get_companies_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("GET", "http://t"))
        hs_service.http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("GET", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.get_companies())

    def test_get_deals_success(self, hs_service):
        install_http(hs_service, "get", 200, {"results": [{"id": "d1"}]})
        result = asyncio.run(hs_service.get_deals())
        assert result[0]["id"] == "d1"

    def test_get_deals_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("GET", "http://t"))
        hs_service.http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("GET", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.get_deals())

    def test_get_campaigns_success(self, hs_service):
        install_http(hs_service, "get", 200, {"campaigns": [{"id": "cam1"}]})
        result = asyncio.run(hs_service.get_campaigns(offset=5))
        assert result[0]["id"] == "cam1"

    def test_get_campaigns_http_error(self, hs_service):
        resp = httpx.Response(500, request=httpx.Request("GET", "http://t"))
        hs_service.http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "500", request=httpx.Request("GET", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.get_campaigns())


class TestHubspotSearchCreate:
    def test_search_content_success(self, hs_service):
        install_http(hs_service, "post", 200, {"total": 3})
        result = asyncio.run(hs_service.search_content("acme"))
        assert result["total"] == 3

    def test_search_content_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.search_content("q"))
        assert exc.value.status_code == 401

    def test_search_content_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("POST", "http://t"))
        hs_service.http.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("POST", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.search_content("q"))

    def test_create_contact_success(self, hs_service):
        install_http(hs_service, "post", 201, {"id": "c1"})
        result = asyncio.run(hs_service.create_contact("e@e.e", "F", "L", "Co", "123"))
        assert result["id"] == "c1"

    def test_create_contact_minimal(self, hs_service):
        captured = {}
        resp = httpx.Response(201, json={"id": "c2"}, request=httpx.Request("POST", "http://t"))

        async def fake_post(integration, url, **kwargs):
            captured.update(kwargs)
            return resp

        hs_service.http.post = fake_post
        result = asyncio.run(hs_service.create_contact("only@e.e"))
        assert result["id"] == "c2"
        assert captured["json"] == {"properties": {"email": "only@e.e"}}

    def test_create_contact_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("POST", "http://t"))
        hs_service.http.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("POST", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.create_contact("e@e.e"))

    def test_create_company_success(self, hs_service):
        install_http(hs_service, "post", 201, {"id": "co1"})
        result = asyncio.run(hs_service.create_company("Acme", "acme.com"))
        assert result["id"] == "co1"

    def test_create_company_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("POST", "http://t"))
        hs_service.http.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("POST", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.create_company("Acme"))

    def test_create_deal_success_with_association(self, hs_service):
        captured = {}
        resp = httpx.Response(201, json={"id": "d1"}, request=httpx.Request("POST", "http://t"))

        async def fake_post(integration, url, **kwargs):
            captured.update(kwargs)
            return resp

        hs_service.http.post = fake_post
        result = asyncio.run(hs_service.create_deal("Deal", 100.0, company_id="co1"))
        assert result["id"] == "d1"
        assert captured["json"]["associations"][0]["to"]["id"] == "co1"
        assert captured["json"]["properties"]["amount"] == "100.0"

    def test_create_deal_without_association(self, hs_service):
        install_http(hs_service, "post", 201, {"id": "d2"})
        result = asyncio.run(hs_service.create_deal("Deal", 50.0))
        assert result["id"] == "d2"

    def test_create_deal_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("POST", "http://t"))
        hs_service.http.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("POST", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.create_deal("Deal", 1))


class TestHubspotObjectOps:
    def test_get_object_success(self, hs_service):
        install_http(hs_service, "get", 200, {"id": "o1"})
        assert asyncio.run(hs_service.get_object("contacts", "o1"))["id"] == "o1"

    def test_get_object_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_object("contacts", "o1"))
        assert exc.value.status_code == 401

    def test_get_object_http_error(self, hs_service):
        resp = httpx.Response(404, request=httpx.Request("GET", "http://t"))
        hs_service.http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.get_object("contacts", "o1"))

    def test_get_contact_company_deal_wrappers(self, hs_service):
        hs_service.get_object = AsyncMock(return_value={"id": "1"})
        assert asyncio.run(hs_service.get_contact("1"))["id"] == "1"
        assert asyncio.run(hs_service.get_company("1"))["id"] == "1"
        assert asyncio.run(hs_service.get_deal("1"))["id"] == "1"
        assert hs_service.get_object.await_count == 3

    def test_update_object_success(self, hs_service):
        install_http(hs_service, "patch", 200, {"id": "o1"})
        result = asyncio.run(hs_service.update_object("contacts", "o1", {"phone": "5"}))
        assert result["id"] == "o1"

    def test_update_object_http_error(self, hs_service):
        resp = httpx.Response(400, request=httpx.Request("PATCH", "http://t"))
        hs_service.http.patch = AsyncMock(side_effect=httpx.HTTPStatusError(
            "400", request=httpx.Request("PATCH", "http://t"), response=resp))
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(hs_service.update_object("contacts", "o1", {}))

    def test_update_contact_deal_wrappers(self, hs_service):
        hs_service.update_object = AsyncMock(return_value={"id": "1"})
        assert asyncio.run(hs_service.update_contact("c1", {}))["id"] == "1"
        assert asyncio.run(hs_service.update_deal("d1", {}))["id"] == "1"
        assert hs_service.update_object.await_count == 2

    def test_get_properties_success(self, hs_service):
        install_http(hs_service, "get", 200, {"results": [{"name": "email"}]})
        result = asyncio.run(hs_service.get_properties("contacts"))
        assert result[0]["name"] == "email"

    def test_get_properties_error(self, hs_service):
        hs_service.http.get = AsyncMock(side_effect=RuntimeError("x"))
        assert asyncio.run(hs_service.get_properties("contacts")) == []

    def test_get_properties_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        assert asyncio.run(svc.get_properties("contacts")) == []


class TestHubspotAnalytics:
    def test_get_analytics_success(self, hs_service):
        install_http(hs_service, "get", 200, {"results": [
            {"properties": {"amount": "100"}},
            {"properties": {"amount": "50"}},
        ]})
        install_http(hs_service, "post", 200, {"total": 42})
        result = asyncio.run(hs_service.get_analytics())
        assert result["total_revenue"] == 150.0
        assert result["deal_count"] == 2
        assert result["contact_count"] == 42

    def test_get_analytics_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        result = asyncio.run(svc.get_analytics())
        assert result == {"error": "Not authenticated"}

    def test_get_analytics_exception(self, hs_service):
        hs_service.get_deals = AsyncMock(side_effect=RuntimeError("x"))
        result = asyncio.run(hs_service.get_analytics())
        assert "error" in result

    def test_full_sync(self, hs_service):
        hs_service.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = asyncio.run(hs_service.full_sync("w1"))
        assert result["success"] is True
        assert result["postgres_cache"]["success"] is True

    def test_sync_to_postgres_cache_success(self, hs_service, monkeypatch):
        hs_service.get_analytics = AsyncMock(return_value={
            "contact_count": 10, "deal_count": 3, "total_revenue": 500.0})
        db = MagicMock()
        existing = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = existing
        monkeypatch.setattr("core.database.SessionLocal", MagicMock(return_value=db))
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        result = asyncio.run(hs_service.sync_to_postgres_cache("w1"))
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        db.commit.assert_called_once()
        db.close.assert_called_once()

    def test_sync_to_postgres_cache_new_rows(self, hs_service, monkeypatch):
        hs_service.get_analytics = AsyncMock(return_value={
            "contact_count": 1, "deal_count": 1, "total_revenue": 1.0})
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr("core.database.SessionLocal", MagicMock(return_value=db))
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        result = asyncio.run(hs_service.sync_to_postgres_cache("w1"))
        assert result["metrics_synced"] == 3
        assert db.add.call_count == 3

    def test_sync_to_postgres_cache_db_error(self, hs_service, monkeypatch):
        hs_service.get_analytics = AsyncMock(return_value={"contact_count": 1})
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db down")
        monkeypatch.setattr("core.database.SessionLocal", MagicMock(return_value=db))
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        result = asyncio.run(hs_service.sync_to_postgres_cache("w1"))
        assert result["success"] is False
        db.rollback.assert_called_once()

    def test_sync_to_postgres_cache_outer_error(self, hs_service, monkeypatch):
        hs_service.get_analytics = AsyncMock(side_effect=RuntimeError("x"))
        monkeypatch.setattr("core.database.SessionLocal", MagicMock())
        monkeypatch.setattr("core.models.IntegrationMetric", Mock)
        result = asyncio.run(hs_service.sync_to_postgres_cache("w1"))
        assert result["success"] is False


class TestHubspotGaps:
    def test_init_without_config(self):
        svc = HubSpotService()
        assert svc.access_token is None
        asyncio.run(svc.close())

    def test_get_companies_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_companies())
        assert exc.value.status_code == 401

    def test_get_companies_with_offset(self, hs_service):
        captured = {}
        resp = httpx.Response(200, json={"results": []}, request=httpx.Request("GET", "http://t"))

        async def fake_get(integration, url, **kwargs):
            captured.update(kwargs)
            return resp

        hs_service.http.get = fake_get
        assert asyncio.run(hs_service.get_companies(offset=10)) == []
        assert captured["params"]["after"] == 10

    def test_get_deals_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_deals())
        assert exc.value.status_code == 401

    def test_get_deals_with_offset(self, hs_service):
        captured = {}
        resp = httpx.Response(200, json={"results": []}, request=httpx.Request("GET", "http://t"))

        async def fake_get(integration, url, **kwargs):
            captured.update(kwargs)
            return resp

        hs_service.http.get = fake_get
        assert asyncio.run(hs_service.get_deals(offset=5)) == []
        assert captured["params"]["after"] == 5

    def test_get_campaigns_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_campaigns())
        assert exc.value.status_code == 401

    def test_create_contact_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(svc.create_contact("e@e.e"))

    def test_create_company_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(svc.create_company("Acme"))

    def test_create_deal_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(svc.create_deal("Deal", 1))

    def test_update_object_no_token(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        svc = make_hubspot({"access_token": None})
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            asyncio.run(svc.update_object("contacts", "c1", {}))

    def test_execute_entity_operation_company_not_implemented(self, hs_service):
        result = asyncio.run(hs_service.execute_entity_operation("delete", "company", {}))
        assert result["success"] is False
        assert "not implemented" in result["error"]

    def test_execute_entity_operation_deal_not_implemented(self, hs_service):
        result = asyncio.run(hs_service.execute_entity_operation("delete", "deal", {}))
        assert result["success"] is False
        assert "not implemented" in result["error"]


class TestHubspotSingleton:
    def test_get_hubspot_service_no_env(self, monkeypatch):
        monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
        import integrations.hubspot_service as mod
        mod._hubspot_service_singleton = None
        assert mod.get_hubspot_service() is None

    def test_get_hubspot_service_with_env(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "env-token")
        import integrations.hubspot_service as mod
        mod._hubspot_service_singleton = None
        svc = mod.get_hubspot_service()
        assert svc is not None
        assert svc.access_token == "env-token"
        assert mod.get_hubspot_service() is svc
        mod._hubspot_service_singleton = None
