# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/financial_ops_routes.py (Phase 37 financial ops).

Governance decorator patched to identity; engine singletons
(cost_detector / budget_guardrails / invoice_reconciler) mocked — zero
network, zero DB writes.

Covers all 7 endpoints x {success, 401 unauth (C1 router-level gate),
422 validation (bad ISO dates, non-positive amounts), service failure}.

Security regression surface checked this wave: the router-level
`dependencies=[Depends(get_current_user)]` (C1 fix) means EVERY endpoint —
including the read-only savings-report/reconcile and the governance-decorated
POSTs — rejects anonymous callers with 401.
"""
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.financial_ops_routes as for_
from core.auth import get_current_user

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def bypass_governance():
    """require_governance is a real decorator wired to the maturity engine;
    bypass it so the endpoint bodies are exercised directly."""
    with patch.object(for_, "require_governance", side_effect=lambda **kw: (lambda f: f)):
        yield


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(for_.router)
    app.dependency_overrides[get_current_user] = lambda: Mock(id="user-1")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def anon_client():
    app = FastAPI()
    app.include_router(for_.router)
    return TestClient(app)


ENDPOINTS = [
    ("post", "/api/financial-ops/cost/subscriptions",
     {"id": "s1", "name": "SaaS X", "monthly_cost": 100.0,
      "last_used": "2026-08-01", "user_count": 5}),
    ("get", "/api/financial-ops/cost/savings-report", None),
    ("post", "/api/financial-ops/budget/limits",
     {"category": "marketing", "monthly_limit": 1000.0}),
    ("post", "/api/financial-ops/budget/check",
     {"category": "marketing", "amount": 50.0}),
    ("post", "/api/financial-ops/invoices",
     {"id": "inv-1", "vendor": "ACME", "amount": 100.0,
      "date": "2026-08-01"}),
    ("post", "/api/financial-ops/contracts",
     {"id": "ct-1", "vendor": "ACME", "monthly_amount": 100.0,
      "start_date": "2026-01-01", "end_date": "2026-12-31"}),
    ("get", "/api/financial-ops/invoices/reconcile", None),
]


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path,body", ENDPOINTS)
    def test_anonymous_requests_rejected(self, anon_client, method, path, body):
        kwargs = {"json": body} if body is not None else {}
        resp = getattr(anon_client, method)(path, **kwargs)
        assert resp.status_code == 401


class TestCostSubscriptions:
    def test_add_subscription_success(self, client):
        with patch("core.financial_ops_engine.cost_detector") as detector, \
             patch("core.financial_ops_engine.SaaSSubscription") as sub_cls:
            resp = client.post("/api/financial-ops/cost/subscriptions", json={
                "id": "s1", "name": "SaaS X", "monthly_cost": 100.0,
                "last_used": "2026-08-01T00:00:00", "user_count": 5,
                "active_users": 3, "category": "software",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"status": "added", "id": "s1"}
        detector.add_subscription.assert_called_once()
        _, kwargs = sub_cls.call_args
        assert kwargs["id"] == "s1"
        assert kwargs["monthly_cost"] == 100.0
        assert kwargs["active_users"] == 3

    def test_add_subscription_invalid_date_422(self, client):
        resp = client.post("/api/financial-ops/cost/subscriptions", json={
            "id": "s1", "name": "SaaS X", "monthly_cost": 100.0,
            "last_used": "not-a-date", "user_count": 5,
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        err = resp.json()["detail"]["error"]
        assert err["code"] == "VALIDATION_ERROR"
        assert err["details"]["field"] == "last_used"

    def test_add_subscription_missing_fields_422(self, client):
        resp = client.post("/api/financial-ops/cost/subscriptions",
                           json={"id": "s1"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_get_savings_report_success(self, client):
        with patch("core.financial_ops_engine.cost_detector") as detector:
            detector.get_savings_report.return_value = {
                "total_monthly_savings": 500.0, "items": []}
            resp = client.get("/api/financial-ops/cost/savings-report",
                              headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["total_monthly_savings"] == 500.0


class TestBudgetGuardrails:
    def test_set_budget_limit_success(self, client):
        with patch("core.financial_ops_engine.budget_guardrails") as guardrails, \
             patch("core.financial_ops_engine.BudgetLimit") as limit_cls:
            resp = client.post("/api/financial-ops/budget/limits", json={
                "category": "marketing", "monthly_limit": 1000.0,
                "deal_stage_required": "commit", "milestone_required": "m1",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"status": "set", "category": "marketing"}
        guardrails.set_limit.assert_called_once()
        _, kwargs = limit_cls.call_args
        assert kwargs["monthly_limit"] == 1000.0
        assert kwargs["deal_stage_required"] == "commit"

    def test_set_budget_limit_zero_422(self, client):
        resp = client.post("/api/financial-ops/budget/limits", json={
            "category": "marketing", "monthly_limit": 0.0,
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_set_budget_limit_negative_422(self, client):
        resp = client.post("/api/financial-ops/budget/limits", json={
            "category": "marketing", "monthly_limit": -10.0,
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_check_spend_success(self, client):
        with patch("core.financial_ops_engine.budget_guardrails") as guardrails:
            guardrails.check_spend.return_value = {
                "status": "approved", "category": "marketing"}
            resp = client.post("/api/financial-ops/budget/check", json={
                "category": "marketing", "amount": 50.0,
                "deal_stage": "commit", "milestone": "m1",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        guardrails.check_spend.assert_called_once_with(
            "marketing", 50.0, "commit", "m1")

    def test_check_spend_zero_amount_422(self, client):
        resp = client.post("/api/financial-ops/budget/check", json={
            "category": "marketing", "amount": 0.0,
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_check_spend_negative_amount_422(self, client):
        resp = client.post("/api/financial-ops/budget/check", json={
            "category": "marketing", "amount": -5.0,
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422


class TestInvoiceReconciliation:
    def test_add_invoice_success(self, client):
        with patch("core.financial_ops_engine.invoice_reconciler") as reconciler, \
             patch("core.financial_ops_engine.Invoice") as inv_cls:
            resp = client.post("/api/financial-ops/invoices", json={
                "id": "inv-1", "vendor": "ACME", "amount": 100.0,
                "date": "2026-08-01", "contract_id": "ct-1",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"status": "added", "id": "inv-1"}
        reconciler.add_invoice.assert_called_once()
        assert inv_cls.call_args.kwargs["contract_id"] == "ct-1"

    def test_add_invoice_invalid_date_422(self, client):
        resp = client.post("/api/financial-ops/invoices", json={
            "id": "inv-1", "vendor": "ACME", "amount": 100.0, "date": "bad",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_add_invoice_non_positive_amount_422(self, client):
        resp = client.post("/api/financial-ops/invoices", json={
            "id": "inv-1", "vendor": "ACME", "amount": 0.0, "date": "2026-08-01",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_add_contract_success(self, client):
        with patch("core.financial_ops_engine.invoice_reconciler") as reconciler, \
             patch("core.financial_ops_engine.Contract") as contract_cls:
            resp = client.post("/api/financial-ops/contracts", json={
                "id": "ct-1", "vendor": "ACME", "monthly_amount": 100.0,
                "start_date": "2026-01-01", "end_date": "2026-12-31",
            }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"status": "added", "id": "ct-1"}
        reconciler.add_contract.assert_called_once()

    def test_add_contract_invalid_date_422(self, client):
        resp = client.post("/api/financial-ops/contracts", json={
            "id": "ct-1", "vendor": "ACME", "monthly_amount": 100.0,
            "start_date": "bad", "end_date": "2026-12-31",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_add_contract_non_positive_amount_422(self, client):
        resp = client.post("/api/financial-ops/contracts", json={
            "id": "ct-1", "vendor": "ACME", "monthly_amount": -1.0,
            "start_date": "2026-01-01", "end_date": "2026-12-31",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_reconcile_success(self, client):
        with patch("core.financial_ops_engine.invoice_reconciler") as reconciler:
            reconciler.reconcile.return_value = {
                "matched": 1, "unmatched": 0}
            resp = client.get("/api/financial-ops/invoices/reconcile",
                              headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["matched"] == 1
