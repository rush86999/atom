"""Final coverage push - quickbooks / atom_ai / pdf gaps."""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ============================================================================
# atom_quickbooks_integration_service
# ============================================================================


class TestQuickBooksCov:
    def _svc(self, **kw):
        import integrations.atom_quickbooks_integration_service as qb
        cfg = {"quickbooks_access_token": "tok", "quickbooks_company_id": "c1",
               "enable_stripe_integration": False, "auto_categorization": False,
               "fraud_detection": False, "enable_enterprise_features": False,
               "real_time_sync": True, "expense_tracking": True, "tax_calculation": True,
               "financial_analytics": False}
        cfg.update(kw)
        return qb.AtomQuickBooksIntegrationService(config=cfg)

    def _resp(self, payload, status=200):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = payload
        r.text = "err"
        return r

    async def test_initialize(self):
        svc = self._svc()
        with patch.object(svc, "_test_quickbooks_connection", AsyncMock()), \
             patch.object(svc, "_initialize_stripe_connection", AsyncMock()), \
             patch.object(svc, "_setup_webhooks", AsyncMock()), \
             patch.object(svc, "_setup_payment_workflows", AsyncMock()), \
             patch.object(svc, "_setup_expense_tracking", AsyncMock()), \
             patch.object(svc, "_setup_tax_calculation", AsyncMock()), \
             patch.object(svc, "_setup_enterprise_features", AsyncMock()), \
             patch.object(svc, "_setup_security_and_compliance", AsyncMock()), \
             patch.object(svc, "_load_existing_financial_data", AsyncMock()), \
             patch.object(svc, "_start_real_time_sync", AsyncMock()):
            assert await svc.initialize() is True
            assert svc.is_initialized
        svc2 = self._svc()
        with patch.object(svc2, "_test_quickbooks_connection", AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc2.initialize() is False
        svc3 = self._svc(real_time_sync=False, expense_tracking=False, tax_calculation=False)
        with patch.object(svc3, "_test_quickbooks_connection", AsyncMock()):
            assert await svc3.initialize() is True

    async def test_setup_methods(self):
        svc = self._svc()
        await svc._setup_webhooks()
        assert svc.webhook_handlers == {}
        await svc._setup_payment_workflows()
        await svc._setup_expense_tracking()
        await svc._setup_tax_calculation()
        await svc._setup_enterprise_features()
        await svc._setup_security_and_compliance()
        await svc._load_existing_financial_data()
        await svc._start_real_time_sync()
        await svc._initialize_stripe_connection()

    async def test_circuit_and_rate_paths(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc()
        with patch.object(qb.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            result = await svc.create_invoice({"amount": 1})
            assert result["success"] is False
            result = await svc.create_payment({"amount": 1})
            assert result["success"] is False
            result = await svc.create_expense({"amount": 1})
            assert result["success"] is False
            result = await svc.create_customer("N", "e@e.com")
            assert result["success"] is False
            result = await svc.generate_financial_report(
                qb.FinancialReportType.PROFIT_AND_LOSS, datetime.now(timezone.utc), datetime.now(timezone.utc))
            assert result["success"] is False
            await svc.close()
        with patch.object(qb.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            result = await svc.create_invoice({"amount": 1})
            assert result["success"] is False
            result = await svc.create_payment({"amount": 1})
            assert result["success"] is False
            result = await svc.create_expense({"amount": 1})
            assert result["success"] is False
            result = await svc.create_customer("N", "e")
            assert result["success"] is False
            await svc.close()

    async def test_create_invoice_full(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc(enable_enterprise_features=True, auto_categorization=True,
                        enable_stripe_integration=True)
        svc.enterprise_security = MagicMock()
        svc.stripe_integration = MagicMock()
        svc.stripe_integration.create_payment_intent = AsyncMock(return_value={"id": "pi1"})
        platform = MagicMock()
        platform.notify_event = AsyncMock()
        svc.platform_integrations["slack"] = platform
        svc._analyze_invoice_with_ai = AsyncMock(return_value={"ai": 1})
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        svc._cache_invoice = AsyncMock()
        svc._trigger_payment_workflows = AsyncMock()
        resp = self._resp({"Invoice": {"Id": "inv1", "TotalAmt": 100.0}})
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await svc.create_invoice({"customer_id": "c1", "amount": 100.0,
                                               "line_items": [], "issue_date": datetime.now(timezone.utc),
                                               "due_date": datetime.now(timezone.utc)}, "slack")
        assert result["success"] is True
        assert svc.stripe_integration.create_payment_intent.called
        assert platform.notify_event.called
        resp2 = self._resp({}, status=400)
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp2)
            result = await svc.create_invoice({"customer_id": "c1", "amount": 1})
        assert result["success"] is False
        # security failure
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "no"})
        result = await svc.create_invoice({"customer_id": "c1", "amount": 1})
        assert result["success"] is False

    async def test_create_payment_full(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc(enable_enterprise_features=True, fraud_detection=True,
                        enable_stripe_integration=True)
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        svc._perform_fraud_detection = AsyncMock(return_value={"is_fraudulent": False, "risk_score": 0})
        svc._process_stripe_payment = AsyncMock(return_value={"success": True, "charge_id": "ch1"})
        svc.stripe_integration = MagicMock()
        svc._cache_payment = AsyncMock()
        svc._trigger_payment_workflows = AsyncMock()
        resp = self._resp({"Payment": {"Id": "p1"}})
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await svc.create_payment({"customer_id": "c1", "amount": 50.0,
                                               "stripe_payment_intent_id": "pi1"})
        assert result["success"] is True
        # fraud
        svc._perform_fraud_detection = AsyncMock(return_value={"is_fraudulent": True, "reason": "fraud"})
        result = await svc.create_payment({"customer_id": "c1", "amount": 50.0})
        assert result["success"] is False
        svc._perform_fraud_detection = AsyncMock(return_value={"is_fraudulent": False})
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "no"})
        result = await svc.create_payment({"customer_id": "c1", "amount": 50.0})
        assert result["success"] is False
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        # stripe failure
        svc._process_stripe_payment = AsyncMock(return_value={"success": False, "error": "x"})
        result = await svc.create_payment({"customer_id": "c1", "amount": 50.0,
                                           "stripe_payment_intent_id": "pi1"})
        assert result["success"] is False
        svc._process_stripe_payment = AsyncMock(return_value={"success": True})
        # API failure
        resp2 = self._resp({}, status=400)
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp2)
            result = await svc.create_payment({"customer_id": "c1", "amount": 50.0})
        assert result["success"] is False

    async def test_create_expense_full(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc(enable_enterprise_features=True, auto_categorization=True)
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        svc._categorize_expense = AsyncMock(return_value="Software")
        svc._cache_expense = AsyncMock()
        svc._trigger_payment_workflows = AsyncMock()
        platform = MagicMock()
        platform.notify_event = AsyncMock()
        svc.platform_integrations["slack"] = platform
        resp = self._resp({"Purchase": {"Id": "e1", "TotalAmt": 10.0, "TxnDate": "2024-01-01"}})
        data = {"account_id": "a1", "amount": 10.0, "vendor_id": "v1", "class_id": "cl1",
                "receipt_attachments": [{"id": "r1"}]}
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await svc.create_expense(data, "slack")
        assert result["success"] is True
        assert result["expense_id"] == "e1"
        assert platform.notify_event.called
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "no"})
        result = await svc.create_expense({"amount": 1})
        assert result["success"] is False
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        resp2 = self._resp({}, status=400)
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp2)
            result = await svc.create_expense({"amount": 1})
        assert result["success"] is False

    async def test_create_customer_full(self):
        svc = self._svc()
        resp = self._resp({"Customer": {"Id": "cu1"}})
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await svc.create_customer("N", "e@e.com")
        assert result["success"] is True
        resp2 = self._resp({}, status=400)
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp2)
            result = await svc.create_customer("N", "e")
        assert result["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=RuntimeError("x"))
            result = await svc.create_customer("N", "e")
        assert result["success"] is False

    async def test_reports_with_ai_insights(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc(financial_analytics=True)
        ai = MagicMock()
        resp = MagicMock()
        resp.ok = True
        resp.output_data = {"insights": ["i"], "recommendations": ["r"]}
        ai.process_ai_request = AsyncMock(return_value=resp)
        svc.ai_service = ai
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc.generate_financial_report(
                qb.FinancialReportType.PROFIT_AND_LOSS, datetime.now(timezone.utc), datetime.now(timezone.utc))
        assert result["success"] is True
        assert result["report"]["insights"] == ["i"]
        ai.process_ai_request.side_effect = RuntimeError("x")
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc.generate_financial_report(
                qb.FinancialReportType.SALES_REPORT, datetime.now(timezone.utc), datetime.now(timezone.utc))
        assert result["success"] is True
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            insights = await svc._generate_financial_insights({}, qb.FinancialReportType.PROFIT_AND_LOSS)
        assert insights["insights"] == []

    async def test_ai_analysis_methods(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc()
        ai = MagicMock()
        resp = MagicMock()
        resp.ok = True
        resp.output_data = {"suggested_pricing_adjustment": 1.0, "optimal_payment_terms": "45",
                            "suggested_discount": 0.5, "customer_payment_risk": "high",
                            "optimization_tips": ["t"], "estimated_payment_time": 20}
        ai.process_ai_request = AsyncMock(return_value=resp)
        svc.ai_service = ai
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc._analyze_invoice_with_ai({})
        assert result["optimal_payment_terms"] == "45"
        ai.process_ai_request.return_value = MagicMock(ok=False, output_data=None)
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc._analyze_invoice_with_ai({})
        assert result["optimal_payment_terms"] == "30"
        ai.process_ai_request.side_effect = RuntimeError("x")
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc._categorize_expense({})
        assert result == "Other"
        ai.process_ai_request.side_effect = None
        ai.process_ai_request.return_value = MagicMock(ok=True, output_data={"suggested_category": "Travel"})
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc._categorize_expense({})
        assert result == "Travel"
        ai.process_ai_request.return_value = MagicMock(ok=False, output_data=None)
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc._categorize_expense({})
        assert result == "Other"

    async def test_connection_and_headers(self):
        svc = self._svc()
        headers = await svc._get_auth_headers()
        assert headers["Authorization"] == "Bearer tok"
        svc2 = self._svc(quickbooks_access_token=None)
        with pytest.raises(Exception):
            await svc2._get_auth_headers()
        resp = self._resp({"CompanyInfo": {}})
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
            assert await svc._test_quickbooks_connection() is True
        resp2 = self._resp({}, status=401)
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp2)
            with pytest.raises(Exception):
                await svc._test_quickbooks_connection()
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.get = AsyncMock(side_effect=RuntimeError("x"))
            with pytest.raises(Exception):
                await svc._test_quickbooks_connection()

    async def test_cache_and_workflows(self):
        svc = self._svc()
        cache = MagicMock()
        cache.set = AsyncMock()
        svc.cache = cache
        await svc._cache_invoice({"Id": "i1"})
        await svc._cache_payment({"Id": "p1"})
        await svc._cache_expense({"Id": "e1"})
        assert cache.set.call_count == 3
        cache.set = AsyncMock(side_effect=RuntimeError("x"))
        await svc._cache_invoice({"Id": "i1"})
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation._handle_event_trigger = AsyncMock()
        await svc._trigger_payment_workflows({}, "created")
        svc.enterprise_automation._handle_event_trigger = AsyncMock(side_effect=RuntimeError("x"))
        await svc._trigger_payment_workflows({}, "created")
        svc.enterprise_automation = None
        await svc._trigger_payment_workflows({}, "created")

    async def test_fraud_detection(self):
        svc = self._svc()
        result = await svc._perform_fraud_detection({"amount": 50000, "rapid_sequence": True,
                                                      "date": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc)})
        assert result["is_fraudulent"] is True
        result = await svc._perform_fraud_detection({"amount": 100,
                                                      "date": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)})
        assert result["is_fraudulent"] is False
        result = await svc._perform_fraud_detection({"amount": 100,
                                                      "date": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc)})
        assert result["is_fraudulent"] is False
        result = await svc._perform_fraud_detection({"amount": 100, "rapid_sequence": True,
                                                      "date": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc)})
        assert result["is_fraudulent"] is True

    async def test_status_and_close(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc()
        status = await svc.get_service_status()
        assert status["service"] == "quickbooks_integration"
        assert status["status"] == "inactive"
        svc.is_initialized = True
        status = await svc.get_service_status()
        assert status["status"] == "active"
        await svc.close()
        with patch.object(qb.rate_limiter, "is_rate_limited", side_effect=RuntimeError("x")):
            await svc.close()

    async def test_module_instance(self):
        import integrations.atom_quickbooks_integration_service as qb
        assert qb.AtomQuickbooksIntegrationService is qb.AtomQuickBooksIntegrationService
        status = await qb.atom_quickbooks_integration_service.get_service_status()
        assert status["service"] == "quickbooks_integration"

    async def test_new_report_methods(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        assert (await svc._generate_balance_sheet_report(start, end))["report_type"] == "balance_sheet"
        assert (await svc._generate_cash_flow_report(start, end))["report_type"] == "cash_flow"
        assert (await svc._generate_trial_balance_report(start, end))["report_type"] == "trial_balance"
        assert (await svc._generate_aged_receivables_report(start, end))["report_type"] == "aged_receivables"
        assert (await svc._generate_aged_payables_report(start, end))["report_type"] == "aged_payables"
        assert (await svc._generate_sales_report(start, end))["report_type"] == "sales_report"
        assert (await svc._generate_expense_report(start, end))["report_type"] == "expense_report"
        assert (await svc._generate_tax_report(start, end))["report_type"] == "tax_report"
        assert (await svc._generate_profit_loss_report(start, end))["report_type"] == "profit_and_loss"

    async def test_stripe_helpers(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc()
        assert await svc._create_stripe_payment_intent({}) is None
        svc.stripe_integration = MagicMock()
        assert await svc._create_stripe_payment_intent({}) is None
        svc.stripe_integration.create_payment_intent = AsyncMock(return_value={"id": "x"})
        assert (await svc._create_stripe_payment_intent({"TotalAmt": 5}))["id"] == "x"
        svc.stripe_integration.create_payment_intent = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc._create_stripe_payment_intent({}) is None
        result = await svc._process_stripe_payment({})
        assert result["success"] is False
        svc.stripe_integration = None
        result = await svc._process_stripe_payment({"stripe_payment_intent_id": "pi"})
        assert result["success"] is False
        svc.stripe_integration = MagicMock()
        result = await svc._process_stripe_payment({"stripe_payment_intent_id": "pi"})
        assert result["success"] is True
        await svc._notify_platform_invoice_created({}, "missing_platform")
        await svc._notify_platform_payment_created({}, "missing_platform")
        await svc._notify_platform_expense_created({}, "missing_platform")
        platform = MagicMock()
        platform.notify_event = AsyncMock(side_effect=RuntimeError("x"))
        svc.platform_integrations["slack"] = platform
        await svc._notify_platform_event("evt", "slack", {})
        platform2 = MagicMock()
        svc.platform_integrations["teams"] = platform2
        await svc._notify_platform_event("evt", "teams", {})
        await svc._perform_security_check({"amount": 1})

    async def test_import_error_fallbacks(self):
        import integrations.atom_quickbooks_integration_service as qb
        assert qb.atom_enterprise_security_service is None
        assert qb.atom_workflow_automation_service is None
        assert qb.ai_enhanced_service is None
        assert qb.atom_slack_integration is None


class TestQuickBooksFinalGaps:
    def _svc(self, **kw):
        import integrations.atom_quickbooks_integration_service as qb
        cfg = {"quickbooks_access_token": "tok", "enable_stripe_integration": False,
               "auto_categorization": False, "fraud_detection": False,
               "enable_enterprise_features": False, "financial_analytics": False}
        cfg.update(kw)
        return qb.AtomQuickBooksIntegrationService(config=cfg)

    async def test_initialize_with_stripe(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc(enable_stripe_integration=True)
        svc.stripe_integration = MagicMock()
        with patch.object(svc, "_test_quickbooks_connection", AsyncMock()), \
             patch.object(svc, "_initialize_stripe_connection", AsyncMock()), \
             patch.object(svc, "_setup_webhooks", AsyncMock()), \
             patch.object(svc, "_setup_payment_workflows", AsyncMock()), \
             patch.object(svc, "_setup_expense_tracking", AsyncMock()), \
             patch.object(svc, "_setup_tax_calculation", AsyncMock()), \
             patch.object(svc, "_setup_enterprise_features", AsyncMock()), \
             patch.object(svc, "_setup_security_and_compliance", AsyncMock()), \
             patch.object(svc, "_load_existing_financial_data", AsyncMock()), \
             patch.object(svc, "_start_real_time_sync", AsyncMock()):
            assert await svc.initialize() is True

    async def test_stripe_init_method(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc()
        with patch.dict(sys.modules, {"atom_stripe_integration": MagicMock(atom_stripe_integration="S")}):
            svc._initialize_stripe_integration()
        assert svc.stripe_integration == "S"
        svc._initialize_stripe_integration()

    async def test_auth_headers_error(self):
        svc = self._svc(quickbooks_access_token=None)
        with pytest.raises(Exception):
            await svc._get_auth_headers()

    async def test_cache_error_branches(self):
        svc = self._svc()
        cache = MagicMock()
        cache.set = AsyncMock(side_effect=RuntimeError("x"))
        svc.cache = cache
        await svc._cache_invoice({"Id": "1"})
        await svc._cache_payment({"Id": "1"})
        await svc._cache_expense({"Id": "1"})

    async def test_workflow_trigger_error(self):
        svc = self._svc()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation._handle_event_trigger = AsyncMock(side_effect=RuntimeError("x"))
        await svc._trigger_payment_workflows({}, "evt")

    async def test_report_ai_error_branches(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc(financial_analytics=True)
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        svc.ai_service = ai
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            insights = await svc._generate_financial_insights({}, qb.FinancialReportType.PROFIT_AND_LOSS)
        assert insights == {"insights": [], "recommendations": []}
        ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=True, output_data={"insights": ["i"]}))
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            insights = await svc._generate_financial_insights({}, qb.FinancialReportType.PROFIT_AND_LOSS)
        assert insights["insights"] == ["i"]

    async def test_analyze_invoice_error(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = self._svc()
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        svc.ai_service = ai
        with patch.object(qb, "AIRequest", MagicMock(), create=True), \
             patch.object(qb, "AITaskType", MagicMock(), create=True), \
             patch.object(qb, "AIModelType", MagicMock(), create=True), \
             patch.object(qb, "AIServiceType", MagicMock(), create=True):
            result = await svc._analyze_invoice_with_ai({})
        assert result["optimal_payment_terms"] == "30"
