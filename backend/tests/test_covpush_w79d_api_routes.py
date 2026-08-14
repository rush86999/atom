# -*- coding: utf-8 -*-
"""Coverage wave W79D — 8 API modules to >=95% statement coverage standalone.

Targets (before -> after, measured with pre-existing suites):
1. api/financial_ops_routes.py        100% -> 100%
2. api/operations_api.py              100% -> 100% (+ POST /api/operations/simulate
   auth regression: anonymous calls must 401 after the get_current_user fix
   landed in a6a6d62ee)
3. api/reconciliation_routes.py        98% -> 100% (ledger governance-denied 403
   + ledger internal-error 500 were the gaps)
4. api/rpc_routes.py                  100% -> 100% (P1 Unified Action Registry)
5. api/supervised_queue_routes.py      92% -> 100% (agent-name lookup in
   get_user_queue, get_user_queue 500 handler, get_queue_entry success)
6. api/tools.py                       100% -> 100%
7. api/user_management_routes.py      100% -> 100%
8. api/websocket_routes.py             60% -> 100% (missing-token close, connect
   loop ping/pong, disconnect paths, default-endpoint delegation)

Conventions (W89/W50/W79C): FastAPI TestClient + dependency_overrides, patches
on real module names (no `backend.` prefix), zero network / LLM spend, no real
DB (in-memory SQLite for user_management; mocked sessions elsewhere).

NOTE on websocket_routes: the pre-existing suite (tests/api/test_websocket_routes.py)
asserts websocket.accept() was called, but the endpoint uses
notification_manager.connect — those tests are broken at HEAD and are NOT
touched here; this file covers the endpoint correctly.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

import api.operations_api as ops_api_module
import api.tools as tools_module
from api.financial_ops_routes import router as finops_router
from api.operations_api import router as ops_router
from api.reconciliation_routes import router as recon_router
from api.rpc_routes import router as rpc_router
from api.supervised_queue_routes import router as sq_router
from api.websocket_routes import (
    router as ws_router,
    websocket_endpoint,
    websocket_endpoint_default,
)
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import UserSession

AUTH = {"Authorization": "Bearer test-token"}


def _app(router, user=None, db=None):
    app = FastAPI()
    app.include_router(router)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    if db is not None:
        def _override_db():
            yield db
        app.dependency_overrides[get_db] = _override_db
    return app


def _client(router, user=None, db=None):
    return TestClient(_app(router, user=user, db=db), raise_server_exceptions=False)


def _user(user_id="user-1", role="member", status="active"):
    return SimpleNamespace(id=user_id, role=role, status=status,
                           first_name="Jane", last_name="Doe")


# ============================================================================
# 1. api/financial_ops_routes.py
# ============================================================================
FIN_ENDPOINTS = [
    ("post", "/api/financial-ops/cost/subscriptions",
     {"id": "s1", "name": "SaaS X", "monthly_cost": 100.0,
      "last_used": "2026-08-01", "user_count": 5}),
    ("get", "/api/financial-ops/cost/savings-report", None),
    ("post", "/api/financial-ops/budget/limits",
     {"category": "marketing", "monthly_limit": 1000.0}),
    ("post", "/api/financial-ops/budget/check",
     {"category": "marketing", "amount": 50.0}),
    ("post", "/api/financial-ops/invoices",
     {"id": "inv-1", "vendor": "ACME", "amount": 100.0, "date": "2026-08-01"}),
    ("post", "/api/financial-ops/contracts",
     {"id": "ct-1", "vendor": "ACME", "monthly_amount": 100.0,
      "start_date": "2026-01-01", "end_date": "2026-12-31"}),
    ("get", "/api/financial-ops/invoices/reconcile", None),
]


@pytest.fixture()
def finops_client():
    with patch("api.financial_ops_routes.require_governance",
               side_effect=lambda **kw: (lambda f: f)):
        yield _client(finops_router, user=_user())


@pytest.fixture()
def finops_anon_client():
    with patch("api.financial_ops_routes.require_governance",
               side_effect=lambda **kw: (lambda f: f)):
        yield _client(finops_router)


class TestFinOpsAuth:
    @pytest.mark.parametrize("method,path,body", FIN_ENDPOINTS)
    def test_anonymous_requests_rejected(self, finops_anon_client, method, path, body):
        kwargs = {"json": body} if body is not None else {}
        assert getattr(finops_anon_client, method)(path, **kwargs).status_code == 401


class TestFinOpsSubscriptions:
    def test_add_subscription_success(self, finops_client):
        with patch("core.financial_ops_engine.cost_detector") as detector, \
                patch("core.financial_ops_engine.SaaSSubscription") as sub_cls:
            resp = finops_client.post("/api/financial-ops/cost/subscriptions", json={
                "id": "s1", "name": "SaaS X", "monthly_cost": 100.0,
                "last_used": "2026-08-01T00:00:00", "user_count": 5,
                "active_users": 3, "category": "software"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == {"status": "added", "id": "s1"}
        detector.add_subscription.assert_called_once()
        assert sub_cls.call_args.kwargs["monthly_cost"] == 100.0
        assert sub_cls.call_args.kwargs["active_users"] == 3

    def test_add_subscription_invalid_date_422(self, finops_client):
        resp = finops_client.post("/api/financial-ops/cost/subscriptions", json={
            "id": "s1", "name": "SaaS X", "monthly_cost": 100.0,
            "last_used": "not-a-date", "user_count": 5}, headers=AUTH)
        assert resp.status_code == 422
        err = resp.json()["detail"]["error"]
        assert err["code"] == "VALIDATION_ERROR"
        assert err["details"]["field"] == "last_used"

    def test_add_subscription_missing_fields_422(self, finops_client):
        resp = finops_client.post("/api/financial-ops/cost/subscriptions",
                                  json={"id": "s1"}, headers=AUTH)
        assert resp.status_code == 422

    def test_get_savings_report_success(self, finops_client):
        with patch("core.financial_ops_engine.cost_detector") as detector:
            detector.get_savings_report.return_value = {
                "total_monthly_savings": 500.0, "items": []}
            resp = finops_client.get("/api/financial-ops/cost/savings-report", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["total_monthly_savings"] == 500.0


class TestFinOpsBudgets:
    def test_set_budget_limit_success(self, finops_client):
        with patch("core.financial_ops_engine.budget_guardrails") as guardrails, \
                patch("core.financial_ops_engine.BudgetLimit") as limit_cls:
            resp = finops_client.post("/api/financial-ops/budget/limits", json={
                "category": "marketing", "monthly_limit": 1000.0,
                "deal_stage_required": "commit", "milestone_required": "m1"},
                headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == {"status": "set", "category": "marketing"}
        guardrails.set_limit.assert_called_once()
        assert limit_cls.call_args.kwargs["monthly_limit"] == 1000.0

    @pytest.mark.parametrize("limit", [0.0, -10.0])
    def test_set_budget_limit_invalid_422(self, finops_client, limit):
        resp = finops_client.post("/api/financial-ops/budget/limits", json={
            "category": "marketing", "monthly_limit": limit}, headers=AUTH)
        assert resp.status_code == 422

    def test_check_spend_success(self, finops_client):
        with patch("core.financial_ops_engine.budget_guardrails") as guardrails:
            guardrails.check_spend.return_value = {
                "status": "approved", "category": "marketing"}
            resp = finops_client.post("/api/financial-ops/budget/check", json={
                "category": "marketing", "amount": 50.0,
                "deal_stage": "commit", "milestone": "m1"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        guardrails.check_spend.assert_called_once_with("marketing", 50.0, "commit", "m1")

    @pytest.mark.parametrize("amount", [0.0, -5.0])
    def test_check_spend_invalid_422(self, finops_client, amount):
        resp = finops_client.post("/api/financial-ops/budget/check", json={
            "category": "marketing", "amount": amount}, headers=AUTH)
        assert resp.status_code == 422


class TestFinOpsInvoices:
    def test_add_invoice_success(self, finops_client):
        with patch("core.financial_ops_engine.invoice_reconciler") as reconciler, \
                patch("core.financial_ops_engine.Invoice") as inv_cls:
            resp = finops_client.post("/api/financial-ops/invoices", json={
                "id": "inv-1", "vendor": "ACME", "amount": 100.0,
                "date": "2026-08-01", "contract_id": "ct-1"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == {"status": "added", "id": "inv-1"}
        reconciler.add_invoice.assert_called_once()
        assert inv_cls.call_args.kwargs["contract_id"] == "ct-1"

    def test_add_invoice_invalid_date_422(self, finops_client):
        resp = finops_client.post("/api/financial-ops/invoices", json={
            "id": "inv-1", "vendor": "ACME", "amount": 100.0, "date": "bad"},
            headers=AUTH)
        assert resp.status_code == 422

    def test_add_invoice_non_positive_amount_422(self, finops_client):
        resp = finops_client.post("/api/financial-ops/invoices", json={
            "id": "inv-1", "vendor": "ACME", "amount": 0.0, "date": "2026-08-01"},
            headers=AUTH)
        assert resp.status_code == 422

    def test_add_contract_success(self, finops_client):
        with patch("core.financial_ops_engine.invoice_reconciler") as reconciler, \
                patch("core.financial_ops_engine.Contract") as contract_cls:
            resp = finops_client.post("/api/financial-ops/contracts", json={
                "id": "ct-1", "vendor": "ACME", "monthly_amount": 100.0,
                "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == {"status": "added", "id": "ct-1"}
        reconciler.add_contract.assert_called_once()
        assert contract_cls.call_args.kwargs["monthly_amount"] == 100.0

    def test_add_contract_invalid_date_422(self, finops_client):
        resp = finops_client.post("/api/financial-ops/contracts", json={
            "id": "ct-1", "vendor": "ACME", "monthly_amount": 100.0,
            "start_date": "bad", "end_date": "2026-12-31"}, headers=AUTH)
        assert resp.status_code == 422

    def test_add_contract_non_positive_amount_422(self, finops_client):
        resp = finops_client.post("/api/financial-ops/contracts", json={
            "id": "ct-1", "vendor": "ACME", "monthly_amount": -1.0,
            "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=AUTH)
        assert resp.status_code == 422

    def test_reconcile_success(self, finops_client):
        with patch("core.financial_ops_engine.invoice_reconciler") as reconciler:
            reconciler.reconcile.return_value = {"matched": 1, "unmatched": 0}
            resp = finops_client.get("/api/financial-ops/invoices/reconcile", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["matched"] == 1


# ============================================================================
# 2. api/operations_api.py
# ============================================================================
class TestOperationsApi:
    @pytest.fixture()
    def client(self):
        with patch("api.operations_api.require_governance",
                   side_effect=lambda **kw: (lambda f: f)):
            yield _client(ops_router, user=_user())

    def test_dashboard_success(self, client):
        with patch.object(ops_api_module.business_health_service,
                          "get_daily_priorities",
                          new=AsyncMock(return_value={"priorities": []})), \
                patch.object(ops_api_module.business_health_service,
                             "get_health_metrics",
                             return_value={"score": 80}):
            resp = client.get("/api/operations/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["metrics"] == {"score": 80}

    def test_dashboard_error_500(self, client):
        with patch.object(ops_api_module.business_health_service,
                          "get_daily_priorities",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.get("/api/operations/dashboard")
        assert resp.status_code == 500

    def test_dashboard_anonymous_401(self):
        assert _client(ops_router).get("/api/operations/dashboard").status_code == 401

    def test_simulate_success(self, client):
        with patch.object(ops_api_module.business_health_service, "simulate_decision",
                          new=AsyncMock(return_value={"outcome": "profitable"})):
            resp = client.post("/api/operations/simulate", json={
                "decision_type": "pricing", "parameters": {"price": 10}})
        assert resp.status_code == 200
        assert resp.json()["data"] == {"outcome": "profitable"}

    def test_simulate_error_500(self, client):
        with patch.object(ops_api_module.business_health_service, "simulate_decision",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.post("/api/operations/simulate", json={
                "decision_type": "pricing", "parameters": {}})
        assert resp.status_code == 500

    def test_simulate_missing_fields_422(self, client):
        resp = client.post("/api/operations/simulate", json={})
        assert resp.status_code == 422

    def test_simulate_anonymous_401_regression(self):
        """Regression: POST /api/operations/simulate must reject anonymous
        callers with 401 (auth dependency added in a6a6d62ee)."""
        with patch("api.operations_api.require_governance",
                   side_effect=lambda **kw: (lambda f: f)):
            resp = _client(ops_router).post("/api/operations/simulate", json={
                "decision_type": "pricing", "parameters": {}})
        assert resp.status_code == 401


# ============================================================================
# 3. api/reconciliation_routes.py
# ============================================================================
def _recon_client(user=None, db=None):
    return _client(recon_router, user=user or _user(), db=db or Mock())


def _patch_recon_engine(**attrs):
    engine = MagicMock()
    for k, v in attrs.items():
        setattr(engine, k, v)
    return patch("core.reconciliation_engine.reconciliation_engine", engine), engine


def _recon_payload(**over):
    body = {"id": "e-1", "source": "bank", "date": "2026-01-01",
            "amount": 100.5, "description": "deposit"}
    body.update(over)
    return body


def _patch_governance(agent, allowed=True, reason=None):
    resolver = AsyncMock()
    resolver.resolve_agent_for_request.return_value = (SimpleNamespace(id=agent), {})
    governance = MagicMock()
    governance.can_perform_action.return_value = {"allowed": allowed, "reason": reason}
    return patch("core.agent_context_resolver.AgentContextResolver",
                 return_value=resolver), patch(
        "core.agent_governance_service.AgentGovernanceService", return_value=governance)


class TestReconAuth:
    @pytest.mark.parametrize("method,path,kwargs", [
        ("post", "/reconciliation/bank-entries",
         {"json": _recon_payload()}),
        ("post", "/reconciliation/ledger-entries",
         {"json": _recon_payload(source="ledger")}),
        ("post", "/reconciliation/reconcile", {}),
        ("get", "/reconciliation/anomalies", {}),
        ("post", "/reconciliation/detect-anomalies", {}),
        ("post", "/reconciliation/anomalies/an-1/resolve", {}),
    ])
    def test_anonymous_401(self, method, path, kwargs):
        assert getattr(_client(recon_router), method)(path, **kwargs).status_code == 401


class TestReconBankEntries:
    def test_add_bank_entry_success(self):
        p, engine = _patch_recon_engine()
        with p:
            resp = _recon_client().post("/reconciliation/bank-entries",
                                        json=_recon_payload())
        assert resp.status_code == 200
        assert resp.json()["status"] == "added"
        engine.add_bank_entry.assert_called_once()

    def test_add_bank_entry_invalid_date_422(self):
        p, engine = _patch_recon_engine()
        with p:
            resp = _recon_client().post("/reconciliation/bank-entries",
                                        json=_recon_payload(date="not-a-date"))
        assert resp.status_code == 422
        engine.add_bank_entry.assert_not_called()

    def test_add_bank_entry_agent_governance_denied_403(self):
        pr, pg = _patch_governance("a-1", allowed=False, reason="maturity too low")
        with pr, pg:
            resp = _recon_client().post("/reconciliation/bank-entries",
                                        json=_recon_payload(agent_id="a-1"))
        assert resp.status_code == 403
        assert "maturity too low" in resp.text

    def test_add_bank_entry_agent_governance_allowed(self):
        p, engine = _patch_recon_engine()
        pr, pg = _patch_governance("a-1", allowed=True)
        with pr, pg, p:
            resp = _recon_client().post("/reconciliation/bank-entries",
                                        json=_recon_payload(agent_id="a-1"))
        assert resp.status_code == 200

    def test_add_bank_entry_internal_error_500(self):
        p, engine = _patch_recon_engine()
        engine.add_bank_entry.side_effect = RuntimeError("boom")
        with p:
            resp = _recon_client().post("/reconciliation/bank-entries",
                                        json=_recon_payload())
        assert resp.status_code == 500


class TestReconLedgerEntries:
    def test_add_ledger_entry_success(self):
        p, engine = _patch_recon_engine()
        with p:
            resp = _recon_client().post("/reconciliation/ledger-entries",
                                        json=_recon_payload(source="ledger"))
        assert resp.status_code == 200
        assert resp.json()["status"] == "added"
        engine.add_ledger_entry.assert_called_once()

    def test_add_ledger_entry_invalid_date_422(self):
        p, engine = _patch_recon_engine()
        with p:
            resp = _recon_client().post("/reconciliation/ledger-entries",
                                        json=_recon_payload(source="ledger", date="bad"))
        assert resp.status_code == 422
        engine.add_ledger_entry.assert_not_called()

    def test_add_ledger_entry_agent_governance_denied_403(self):
        pr, pg = _patch_governance("a-1", allowed=False)
        with pr, pg:
            resp = _recon_client().post("/reconciliation/ledger-entries",
                                        json=_recon_payload(source="ledger", agent_id="a-1"))
        assert resp.status_code == 403

    def test_add_ledger_entry_internal_error_500(self):
        p, engine = _patch_recon_engine()
        engine.add_ledger_entry.side_effect = RuntimeError("boom")
        with p:
            resp = _recon_client().post("/reconciliation/ledger-entries",
                                        json=_recon_payload(source="ledger"))
        assert resp.status_code == 500


class TestReconReconcile:
    def test_run_reconciliation_success(self):
        p, engine = _patch_recon_engine()
        engine.reconcile.return_value = {"matched": 2, "unmatched": 1}
        with p:
            resp = _recon_client().post("/reconciliation/reconcile")
        assert resp.status_code == 200
        assert resp.json() == {"matched": 2, "unmatched": 1}

    def test_run_reconciliation_error_500(self):
        p, engine = _patch_recon_engine()
        engine.reconcile.side_effect = RuntimeError("boom")
        with p:
            resp = _recon_client().post("/reconciliation/reconcile")
        assert resp.status_code == 500


class TestReconAnomalies:
    def test_get_anomalies_success(self):
        anomaly = SimpleNamespace(
            id="an-1", anomaly_type=SimpleNamespace(value="amount_mismatch"),
            severity="high", description="desc", confidence=0.75,
            suggested_action="review")
        p, engine = _patch_recon_engine()
        engine.get_anomalies.return_value = [anomaly]
        with p:
            resp = _recon_client().get("/reconciliation/anomalies?unresolved_only=true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["anomalies"][0]["type"] == "amount_mismatch"
        assert body["anomalies"][0]["confidence"] == 75.0
        engine.get_anomalies.assert_called_once_with(True)

    def test_get_anomalies_empty(self):
        p, engine = _patch_recon_engine()
        engine.get_anomalies.return_value = []
        with p:
            resp = _recon_client().get("/reconciliation/anomalies")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_get_anomalies_error_500(self):
        p, engine = _patch_recon_engine()
        engine.get_anomalies.side_effect = RuntimeError("boom")
        with p:
            resp = _recon_client().get("/reconciliation/anomalies")
        assert resp.status_code == 500

    def test_detect_anomalies_success(self):
        p, engine = _patch_recon_engine()
        engine.detect_anomalies.return_value = [1, 2, 3]
        with p:
            resp = _recon_client().post("/reconciliation/detect-anomalies")
        assert resp.status_code == 200
        assert resp.json() == {"detected": 3}

    def test_detect_anomalies_error_500(self):
        p, engine = _patch_recon_engine()
        engine.detect_anomalies.side_effect = RuntimeError("boom")
        with p:
            resp = _recon_client().post("/reconciliation/detect-anomalies")
        assert resp.status_code == 500

    def test_resolve_anomaly_success(self):
        p, engine = _patch_recon_engine()
        engine.resolve_anomaly.return_value = True
        with p:
            resp = _recon_client().post("/reconciliation/anomalies/an-1/resolve")
        assert resp.status_code == 200
        assert resp.json() == {"status": "resolved", "id": "an-1"}
        engine.resolve_anomaly.assert_called_once_with("an-1")

    def test_resolve_anomaly_not_found_404(self):
        p, engine = _patch_recon_engine()
        engine.resolve_anomaly.return_value = False
        with p:
            resp = _recon_client().post("/reconciliation/anomalies/ghost/resolve")
        assert resp.status_code == 404

    def test_resolve_anomaly_error_500(self):
        p, engine = _patch_recon_engine()
        engine.resolve_anomaly.side_effect = RuntimeError("boom")
        with p:
            resp = _recon_client().post("/reconciliation/anomalies/an-1/resolve")
        assert resp.status_code == 500


# ============================================================================
# 4. api/rpc_routes.py (P1 Unified Action Registry)
# ============================================================================
class TestRpcListActions:
    def _client(self):
        app = FastAPI()
        app.include_router(rpc_router)
        app.dependency_overrides[get_current_user] = lambda: _user()
        app.dependency_overrides[get_db] = lambda: Mock()
        return TestClient(app, raise_server_exceptions=False)

    def test_lists_actions(self):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_all_definitions.return_value = [
                SimpleNamespace(name="a1", description="d1",
                                parameters_schema={"type": "object"}),
            ]
            resp = self._client().get("/api/rpc/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["data"][0]["name"] == "a1"

    def test_empty(self):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_all_definitions.return_value = []
            resp = self._client().get("/api/rpc/actions")
        assert resp.json()["data"] == []
        assert resp.json()["count"] == 0

    def test_unauth_401(self):
        app = FastAPI()
        app.include_router(rpc_router)
        assert TestClient(app).get("/api/rpc/actions").status_code == 401


class TestRpcCallAction:
    def _client(self):
        app = FastAPI()
        app.include_router(rpc_router)
        app.dependency_overrides[get_current_user] = lambda: _user("u1")
        app.dependency_overrides[get_db] = lambda: Mock()
        return TestClient(app, raise_server_exceptions=False)

    def test_success_forwards_params_and_context(self):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            reg.execute_action = AsyncMock(return_value={"ok": 1})
            resp = self._client().post("/api/rpc/documents.search",
                                       json={"params": {"q": "x"}})
        assert resp.status_code == 200
        assert resp.json()["data"] == {"ok": 1}
        assert resp.json()["action"] == "documents.search"
        args = reg.execute_action.call_args.args
        assert args[1] == {"q": "x"}
        assert args[2]["user_id"] == "u1"
        assert "user" in args[2]
        assert "db" in args[2]

    def test_default_params_empty(self):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            reg.execute_action = AsyncMock(return_value=None)
            resp = self._client().post("/api/rpc/a1", json={})
        assert resp.status_code == 200
        assert reg.execute_action.call_args.args[1] == {}

    def test_unknown_action_404_registry_miss(self):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = None
            resp = self._client().post("/api/rpc/ghost", json={"params": {}})
        assert resp.status_code == 404

    def test_action_not_found_error_404(self):
        from core.action_registry import ActionNotFoundError
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            reg.execute_action = AsyncMock(side_effect=ActionNotFoundError("ghost"))
            resp = self._client().post("/api/rpc/ghost", json={"params": {}})
        assert resp.status_code == 404

    def test_execution_error_500_no_detail_leak(self):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            reg.execute_action = AsyncMock(side_effect=RuntimeError("secret detail"))
            resp = self._client().post("/api/rpc/a1", json={"params": {}})
        assert resp.status_code == 500
        assert "secret detail" not in resp.text
        assert "failed" in resp.json()["detail"]

    def test_unauth_401(self):
        app = FastAPI()
        app.include_router(rpc_router)
        assert TestClient(app).post("/api/rpc/a1", json={"params": {}}).status_code == 401


# ============================================================================
# 5. api/supervised_queue_routes.py
# ============================================================================
def _queue_entry(execution_result=None, last_error=None):
    entry = Mock()
    entry.id = "queue_001"
    entry.agent_id = "agent_001"
    entry.user_id = "user_001"
    entry.trigger_type = "scheduled"
    entry.status = MagicMock()
    entry.status.value = "pending"
    entry.priority = 5
    entry.attempts = 0
    entry.expires_at = datetime.now() + timedelta(hours=1)
    entry.execution_result = execution_result
    entry.last_error = last_error
    entry.created_at = datetime.now()
    entry.updated_at = datetime.now()
    return entry


@pytest.fixture()
def sq_client():
    return _client(sq_router, user=_user("me", "member", "active"), db=Mock())


class TestSupervisedQueueAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/supervised-queue/users/u1"),
        ("delete", "/api/supervised-queue/q1?user_id=u1"),
        ("post", "/api/supervised-queue/process"),
        ("get", "/api/supervised-queue/stats"),
        ("post", "/api/supervised-queue/mark-expired"),
        ("get", "/api/supervised-queue/q1"),
    ])
    def test_anonymous_401(self, method, path):
        assert getattr(_client(sq_router), method)(path).status_code == 401


class TestSupervisedQueueUserQueue:
    def test_get_user_queue_with_agent_name(self, sq_client):
        service = Mock()
        service.db = Mock()
        agent = Mock()
        agent.name = "Test Agent"
        service.db.query.return_value.filter.return_value.first.return_value = agent
        service.get_user_queue = AsyncMock(return_value=[_queue_entry()])
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/users/user_001?status=pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 1
        assert body["entries"][0]["agent_name"] == "Test Agent"
        assert body["entries"][0]["status"] == "pending"
        service.get_user_queue.assert_awaited_once()

    def test_get_user_queue_agent_missing_and_execution_result(self, sq_client):
        service = Mock()
        service.db = Mock()
        service.db.query.return_value.filter.return_value.first.return_value = None
        service.get_user_queue = AsyncMock(return_value=[
            _queue_entry(execution_result={"execution_id": "exec-1"}, last_error="err")])
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/users/user_001")
        assert resp.status_code == 200
        entry = resp.json()["entries"][0]
        assert entry["agent_name"] is None
        assert entry["execution_id"] == "exec-1"
        assert entry["error_message"] == "err"

    def test_get_user_queue_agent_lookup_exception(self, sq_client):
        service = Mock()
        service.db = Mock()
        service.db.query.side_effect = RuntimeError("db boom")
        service.get_user_queue = AsyncMock(return_value=[_queue_entry()])
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/users/user_001")
        assert resp.status_code == 200
        assert resp.json()["entries"][0]["agent_name"] is None

    def test_get_user_queue_no_db_attr(self, sq_client):
        service = Mock(spec=["get_user_queue"])
        service.get_user_queue = AsyncMock(return_value=[_queue_entry()])
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/users/user_001")
        assert resp.status_code == 200
        assert resp.json()["entries"][0]["agent_name"] is None

    def test_get_user_queue_empty(self, sq_client):
        service = Mock()
        service.get_user_queue = AsyncMock(return_value=[])
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/users/user_123")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0

    def test_get_user_queue_invalid_status_400(self, sq_client):
        service = Mock()
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/users/user_001?status=bogus")
        assert resp.status_code == 400
        service.get_user_queue.assert_not_called()

    def test_get_user_queue_service_error_500(self, sq_client):
        service = Mock()
        service.get_user_queue = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/users/user_001")
        assert resp.status_code == 500
        assert "Internal error" in resp.text


class TestSupervisedQueueCancel:
    def test_cancel_success(self, sq_client):
        service = Mock()
        service.cancel_queue_entry = AsyncMock(return_value=True)
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.delete("/api/supervised-queue/queue_001?user_id=user_001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "cancelled" in body["message"]
        service.cancel_queue_entry.assert_awaited_once_with("queue_001", "user_001")

    def test_cancel_not_found_404(self, sq_client):
        service = Mock()
        service.cancel_queue_entry = AsyncMock(return_value=False)
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.delete("/api/supervised-queue/nonexistent?user_id=user_001")
        assert resp.status_code == 404

    def test_cancel_service_error_500(self, sq_client):
        service = Mock()
        service.cancel_queue_entry = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.delete("/api/supervised-queue/queue_001?user_id=user_001")
        assert resp.status_code == 500


class TestSupervisedQueueProcess:
    def test_process_success_default_limit(self, sq_client):
        service = Mock()
        service.process_pending_queues = AsyncMock(return_value=[])
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.post("/api/supervised-queue/process")
        assert resp.status_code == 200
        assert resp.json()["processed_count"] == 0
        service.process_pending_queues.assert_awaited_once_with(limit=10)

    def test_process_with_entries_and_custom_limit(self, sq_client):
        service = Mock()
        service.process_pending_queues = AsyncMock(
            return_value=[_queue_entry(execution_result={"execution_id": "e1"})])
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.post("/api/supervised-queue/process?limit=50")
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed_count"] == 1
        assert body["entries"][0]["execution_id"] == "e1"
        assert body["entries"][0]["agent_name"] is None

    @pytest.mark.parametrize("limit", [0, 101])
    def test_process_limit_validation_422(self, sq_client, limit):
        resp = sq_client.post(f"/api/supervised-queue/process?limit={limit}")
        assert resp.status_code == 422

    def test_process_service_error_500(self, sq_client):
        service = Mock()
        service.process_pending_queues = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.post("/api/supervised-queue/process")
        assert resp.status_code == 500


class TestSupervisedQueueStats:
    STATS = {"pending": 5, "executing": 2, "completed": 10,
             "failed": 1, "cancelled": 0, "total": 18}

    def test_stats_all(self, sq_client):
        service = Mock()
        service.get_queue_stats = AsyncMock(return_value=dict(self.STATS))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/stats")
        assert resp.status_code == 200
        assert resp.json()["total"] == 18
        service.get_queue_stats.assert_awaited_once_with(None)

    def test_stats_user_id_clamped_to_current_user(self, sq_client):
        service = Mock()
        service.get_queue_stats = AsyncMock(return_value=dict(self.STATS))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/stats?user_id=someone-else")
        assert resp.status_code == 200
        service.get_queue_stats.assert_awaited_once_with("me")

    def test_stats_own_user_id_passthrough(self, sq_client):
        service = Mock()
        service.get_queue_stats = AsyncMock(return_value=dict(self.STATS))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/stats?user_id=me")
        assert resp.status_code == 200
        service.get_queue_stats.assert_awaited_once_with("me")

    def test_stats_service_error_500(self, sq_client):
        service = Mock()
        service.get_queue_stats = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.get("/api/supervised-queue/stats")
        assert resp.status_code == 500


class TestSupervisedQueueMarkExpired:
    def test_mark_expired_success(self, sq_client):
        service = Mock()
        service.mark_expired_queues = AsyncMock(return_value=3)
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.post("/api/supervised-queue/mark-expired")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "3" in body["message"]

    def test_mark_expired_zero(self, sq_client):
        service = Mock()
        service.mark_expired_queues = AsyncMock(return_value=0)
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.post("/api/supervised-queue/mark-expired")
        assert resp.status_code == 200
        assert "0" in resp.json()["message"]

    def test_mark_expired_service_error_500(self, sq_client):
        service = Mock()
        service.mark_expired_queues = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.supervised_queue_routes.SupervisedQueueService",
                   return_value=service):
            resp = sq_client.post("/api/supervised-queue/mark-expired")
        assert resp.status_code == 500


class TestSupervisedQueueEntry:
    def test_get_queue_entry_success_with_agent(self, sq_client):
        from core.models import AgentRegistry, SupervisedExecutionQueue
        entry = _queue_entry()
        agent = Mock()
        agent.name = "Agent One"
        db = Mock()
        db.query.side_effect = lambda model: _query_first(model, entry, agent)
        client = _client(sq_router, user=_user(), db=db)
        resp = client.get("/api/supervised-queue/queue_001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "queue_001"
        assert body["agent_name"] == "Agent One"

    def test_get_queue_entry_without_agent(self, sq_client):
        from core.models import AgentRegistry, SupervisedExecutionQueue
        entry = _queue_entry()
        db = Mock()
        db.query.side_effect = lambda model: _query_first(model, entry, None)
        client = _client(sq_router, user=_user(), db=db)
        resp = client.get("/api/supervised-queue/queue_001")
        assert resp.status_code == 200
        assert resp.json()["agent_name"] is None

    def test_get_queue_entry_not_found_404(self, sq_client):
        from core.models import SupervisedExecutionQueue
        db = Mock()
        db.query.side_effect = lambda model: _query_first(model, None, None)
        client = _client(sq_router, user=_user(), db=db)
        resp = client.get("/api/supervised-queue/nope")
        assert resp.status_code == 404


def _query_first(model, entry, agent):
    q = Mock()
    first = q.filter.return_value.first
    if model.__name__ == "SupervisedExecutionQueue":
        first.return_value = entry
    else:
        first.return_value = agent
    return q


# ============================================================================
# 6. api/tools.py
# ============================================================================
@pytest.fixture()
def tool_registry():
    tool = MagicMock()
    tool.to_dict.return_value = {"name": "present_chart", "category": "canvas"}
    reg = MagicMock()
    reg.list_all.return_value = ["present_chart"]
    reg.list_by_category.return_value = ["present_chart"]
    reg.list_by_maturity.return_value = ["present_chart"]
    reg.get.return_value = tool
    reg.search.return_value = [tool]
    reg.get_stats.return_value = {
        "total": 1, "categories": {"canvas": 1},
        "complexity": {"low": 1}, "maturity": {"autonomous": 1},
    }
    return reg


def _tools_client(registry, user=None):
    from tools.registry import get_tool_registry
    app = _app(tools_module.router, user=user or _user())
    app.dependency_overrides[get_tool_registry] = lambda: registry
    return TestClient(app, raise_server_exceptions=False)


def _tools_anon_client(registry):
    """Client with NO get_current_user override — tools endpoints must 401."""
    from tools.registry import get_tool_registry
    app = FastAPI()
    app.include_router(tools_module.router)
    app.dependency_overrides[get_tool_registry] = lambda: registry
    return TestClient(app, raise_server_exceptions=False)


class TestToolsList:
    def test_list_all(self, tool_registry):
        resp = _tools_client(tool_registry).get("/api/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["count"] == 1
        assert body["data"]["tools"][0]["name"] == "present_chart"
        tool_registry.list_all.assert_called_once()

    def test_list_by_category(self, tool_registry):
        _tools_client(tool_registry).get("/api/tools", params={"category": "canvas"})
        tool_registry.list_by_category.assert_called_once_with("canvas")

    def test_list_by_maturity(self, tool_registry):
        _tools_client(tool_registry).get("/api/tools", params={"maturity": "AUTONOMOUS"})
        tool_registry.list_by_maturity.assert_called_once_with("AUTONOMOUS")

    def test_list_skips_missing_metadata(self, tool_registry):
        tool_registry.get.return_value = None
        resp = _tools_client(tool_registry).get("/api/tools")
        assert resp.status_code == 200
        assert resp.json()["data"]["tools"] == []

    def test_list_error_500(self, tool_registry):
        tool_registry.list_all.side_effect = RuntimeError("boom")
        resp = _tools_client(tool_registry).get("/api/tools")
        assert resp.status_code == 500

    def test_anonymous_401(self, tool_registry):
        assert _tools_anon_client(tool_registry).get("/api/tools").status_code == 401


class TestToolsCategories:
    def test_categories_sorted_by_count(self, tool_registry):
        tool_registry.get_stats.return_value = {
            "total": 3, "categories": {"a": 1, "b": 3, "c": 2},
            "complexity": {}, "maturity": {}}
        resp = _tools_client(tool_registry).get("/api/tools/categories")
        assert resp.status_code == 200
        cats = resp.json()["data"]["categories"]
        assert [c["name"] for c in cats] == ["b", "c", "a"]
        assert resp.json()["data"]["count"] == 3

    def test_categories_empty(self, tool_registry):
        tool_registry.get_stats.return_value = {
            "total": 0, "categories": {}, "complexity": {}, "maturity": {}}
        resp = _tools_client(tool_registry).get("/api/tools/categories")
        assert resp.status_code == 200
        assert resp.json()["data"]["categories"] == []

    def test_categories_error_500(self, tool_registry):
        tool_registry.get_stats.side_effect = RuntimeError("boom")
        assert _tools_client(tool_registry).get("/api/tools/categories").status_code == 500

    def test_anonymous_401(self, tool_registry):
        assert _tools_anon_client(tool_registry).get(
            "/api/tools/categories").status_code == 401


class TestToolsSearch:
    def test_search_success(self, tool_registry):
        resp = _tools_client(tool_registry).get("/api/tools/search", params={"query": "chart"})
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 1
        tool_registry.search.assert_called_once_with("chart")

    def test_search_short_query_422(self, tool_registry):
        resp = _tools_client(tool_registry).get("/api/tools/search", params={"query": "x"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_search_empty_query_422(self, tool_registry):
        resp = _tools_client(tool_registry).get("/api/tools/search", params={"query": ""})
        assert resp.status_code == 422

    def test_search_missing_query_422(self, tool_registry):
        assert _tools_client(tool_registry).get("/api/tools/search").status_code == 422

    def test_search_error_500(self, tool_registry):
        tool_registry.search.side_effect = RuntimeError("boom")
        resp = _tools_client(tool_registry).get("/api/tools/search", params={"query": "chart"})
        assert resp.status_code == 500

    def test_anonymous_401(self, tool_registry):
        assert _tools_anon_client(tool_registry).get(
            "/api/tools/search", params={"query": "chart"}).status_code == 401


class TestToolsStats:
    def test_stats_success(self, tool_registry):
        resp = _tools_client(tool_registry).get("/api/tools/stats")
        assert resp.status_code == 200
        assert resp.json()["data"]["stats"]["total"] == 1

    def test_stats_error_500(self, tool_registry):
        tool_registry.get_stats.side_effect = RuntimeError("boom")
        assert _tools_client(tool_registry).get("/api/tools/stats").status_code == 500

    def test_anonymous_401(self, tool_registry):
        assert _tools_anon_client(tool_registry).get("/api/tools/stats").status_code == 401


class TestToolsGetTool:
    def test_get_tool_success(self, tool_registry):
        resp = _tools_client(tool_registry).get("/api/tools/present_chart")
        assert resp.status_code == 200
        assert resp.json()["data"]["tool"]["name"] == "present_chart"
        tool_registry.get.assert_called_once_with("present_chart")

    def test_get_tool_not_found_404(self, tool_registry):
        tool_registry.get.return_value = None
        resp = _tools_client(tool_registry).get("/api/tools/nope")
        assert resp.status_code == 404

    def test_get_tool_error_500(self, tool_registry):
        tool_registry.get.side_effect = RuntimeError("boom")
        assert _tools_client(tool_registry).get("/api/tools/x").status_code == 500

    def test_anonymous_401(self, tool_registry):
        assert _tools_anon_client(tool_registry).get("/api/tools/x").status_code == 401


class TestToolsCategoryRoute:
    def test_category_non_empty(self, tool_registry):
        resp = _tools_client(tool_registry).get("/api/tools/category/canvas")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["count"] == 1
        assert body["category"] == "canvas"

    def test_category_empty(self, tool_registry):
        tool_registry.list_by_category.return_value = []
        resp = _tools_client(tool_registry).get("/api/tools/category/empty")
        assert resp.status_code == 200
        assert resp.json()["data"]["tools"] == []

    def test_category_error_500(self, tool_registry):
        tool_registry.list_by_category.side_effect = RuntimeError("boom")
        assert _tools_client(tool_registry).get("/api/tools/category/canvas").status_code == 500

    def test_anonymous_401(self, tool_registry):
        assert _tools_anon_client(tool_registry).get(
            "/api/tools/category/canvas").status_code == 401


# ============================================================================
# 7. api/user_management_routes.py
# ============================================================================
@pytest.fixture()
def mem_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1"):
    from core.models import User
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="Jane",
        last_name="Doe",
        role="admin",
        status="active",
        tenant_id="t1",
        last_login=datetime(2026, 8, 1, 12, 0, 0),
    )
    db.add(user)
    db.commit()
    return user


def _make_session(db, session_id, user_id="user-1", *, session_token=None,
                  is_active=True, expires_days=7, last_active_days=1,
                  device_type="mobile", browser="Safari", os="iOS"):
    from core.models import UserSession
    session = UserSession(
        id=session_id,
        user_id=user_id,
        session_token=session_token or f"tok-{session_id}",
        is_active=is_active,
        device_type=device_type,
        browser=browser,
        os=os,
        ip_address="127.0.0.1",
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
        last_active_at=datetime.now(timezone.utc) - timedelta(days=last_active_days),
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_days),
    )
    db.add(session)
    db.commit()
    return session


@pytest.fixture()
def um_client(mem_db):
    from api.user_management_routes import router as um_router
    user = _make_user(mem_db)

    def _override_db():
        yield mem_db

    def _override_user():
        return user

    app = FastAPI()
    app.include_router(um_router)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def um_anon_client(mem_db):
    from api.user_management_routes import router as um_router

    def _override_db():
        yield mem_db

    app = FastAPI()
    app.include_router(um_router)
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


class TestUserMgmtAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/users/me"),
        ("get", "/api/users/sessions"),
        ("delete", "/api/users/sessions/s-1"),
        ("delete", "/api/users/sessions"),
    ])
    def test_anonymous_401(self, um_anon_client, method, path):
        assert getattr(um_anon_client, method)(path).status_code == 401


class TestUserMgmtMe:
    def test_me_success(self, um_client):
        resp = um_client.get("/api/users/me", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "user-1"
        assert body["name"] == "Jane Doe"
        assert body["email_verified"] is None
        assert body["tenant_id"] == "t1"
        assert body["last_login"] is not None

    def test_me_name_falls_back_to_email(self, mem_db):
        from api.user_management_routes import router as um_router
        user = _make_user(mem_db, "nameless")
        user.first_name = ""
        user.last_name = ""
        mem_db.commit()

        def _override_db():
            yield mem_db

        app = FastAPI()
        app.include_router(um_router)
        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: user
        resp = TestClient(app).get("/api/users/me")
        assert resp.json()["name"] == "nameless@example.com"


class TestUserMgmtListSessions:
    def test_list_sessions_with_current_token(self, um_client, mem_db):
        _make_session(mem_db, "s-1", session_token="test-token")
        _make_session(mem_db, "s-2", session_token="tok-other")
        resp = um_client.get("/api/users/sessions", headers=AUTH)
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 2
        by_id = {s["id"]: s for s in sessions}
        assert by_id["s-1"]["is_current"] is True
        assert by_id["s-2"]["is_current"] is False
        assert by_id["s-1"]["device_type"] == "mobile"

    def test_list_sessions_cookie_fallback(self, um_client, mem_db):
        _make_session(mem_db, "s-1", session_token="cookie-tok")
        resp = um_client.get("/api/users/sessions",
                             headers={"Cookie": "next-auth.session-token=cookie-tok"})
        assert resp.json()[0]["is_current"] is True

    def test_list_sessions_secure_cookie_fallback(self, um_client, mem_db):
        _make_session(mem_db, "s-1", session_token="secure-tok")
        resp = um_client.get("/api/users/sessions",
                             headers={"Cookie": "__Secure-next-auth.session-token=secure-tok"})
        assert resp.json()[0]["is_current"] is True

    def test_list_sessions_no_token_no_current(self, um_client, mem_db):
        _make_session(mem_db, "s-1")
        resp = um_client.get("/api/users/sessions")
        assert resp.status_code == 200
        assert resp.json()[0]["is_current"] is False

    def test_list_sessions_filters_inactive_expired_and_foreign(self, um_client, mem_db):
        _make_session(mem_db, "s-active")
        _make_session(mem_db, "s-inactive", is_active=False)
        _make_session(mem_db, "s-expired", expires_days=-2)
        _make_session(mem_db, "s-other", user_id="someone-else")
        sessions = um_client.get("/api/users/sessions").json()
        assert len(sessions) == 1
        assert sessions[0]["id"] == "s-active"

    def test_list_sessions_empty(self, um_client):
        assert um_client.get("/api/users/sessions").json() == []


class TestUserMgmtRevoke:
    def test_revoke_session_success(self, um_client, mem_db):
        _make_session(mem_db, "s-1")
        resp = um_client.delete("/api/users/sessions/s-1", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Session revoked successfully"
        session = mem_db.query(UserSession).filter(
            UserSession.id == "s-1").first()
        assert session.is_active is False

    def test_revoke_session_missing_404(self, um_client):
        resp = um_client.delete("/api/users/sessions/nope", headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_revoke_session_other_users_404_idor(self, um_client, mem_db):
        _make_session(mem_db, "s-other", user_id="someone-else")
        resp = um_client.delete("/api/users/sessions/s-other", headers=AUTH)
        assert resp.status_code == 404
        session = mem_db.query(UserSession).filter(
            UserSession.id == "s-other").first()
        assert session.is_active is True

    def test_revoke_all_except_current(self, um_client, mem_db):
        _make_session(mem_db, "s-current", session_token="test-token")
        _make_session(mem_db, "s-1", session_token="tok-1")
        _make_session(mem_db, "s-2", session_token="tok-2")
        resp = um_client.delete("/api/users/sessions", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["message"] == "All sessions revoked successfully"
        active = mem_db.query(UserSession).filter(
            UserSession.is_active == True  # noqa: E712
        ).all()
        assert [s.id for s in active] == ["s-current"]

    def test_revoke_all_without_token_revokes_everything(self, um_client, mem_db):
        _make_session(mem_db, "s-1", session_token="tok-1")
        _make_session(mem_db, "s-2", session_token="tok-2")
        resp = um_client.delete("/api/users/sessions")
        assert resp.status_code == 200
        active = mem_db.query(UserSession).filter(
            UserSession.is_active == True  # noqa: E712
        ).count()
        assert active == 0

    def test_revoke_all_empty(self, um_client):
        resp = um_client.delete("/api/users/sessions", headers=AUTH)
        assert resp.status_code == 200


# ============================================================================
# 8. api/websocket_routes.py
# ============================================================================
def _ws_app():
    app = FastAPI()
    app.include_router(ws_router)
    return TestClient(app)


class TestWebSocketEndpoint:
    def test_missing_token_closes_1008(self):
        with pytest.raises(WebSocketDisconnect) as exc:
            with _ws_app().websocket_connect("/ws/ws1") as ws:
                ws.receive_text()
        assert exc.value.code == 1008

    def test_invalid_token_closes_1008(self):
        with patch("api.websocket_routes.SessionLocal"), \
                patch("api.websocket_routes.get_current_user_ws",
                      new=AsyncMock(return_value=None)):
            with pytest.raises(WebSocketDisconnect) as exc:
                with _ws_app().websocket_connect("/ws/ws1?token=bad") as ws:
                    ws.receive_text()
        assert exc.value.code == 1008

    def test_default_workspace_route_via_asgi(self):
        """Real ASGI path for /ws: delegates to the parametrized endpoint with
        workspace 'default' (no token -> server closes 1008, no hang)."""
        with pytest.raises(WebSocketDisconnect) as exc:
            with _ws_app().websocket_connect("/ws") as ws:
                ws.receive_text()
        assert exc.value.code == 1008

    def _mock_ws(self, receive_side_effect):
        ws = MagicMock()
        ws.query_params = {"token": "tok"}
        ws.receive_text = AsyncMock(side_effect=receive_side_effect)
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        nm = MagicMock()
        nm.connect = AsyncMock()
        nm.disconnect = MagicMock()
        return ws, nm

    async def test_ping_pong_loop(self):
        ws, nm = self._mock_ws(["ping", WebSocketDisconnect(code=1000)])
        with patch("api.websocket_routes.SessionLocal"), \
                patch("api.websocket_routes.get_current_user_ws",
                      new=AsyncMock(return_value=_user("u1"))), \
                patch("api.websocket_routes.notification_manager", new=nm):
            await websocket_endpoint(ws, "w1")
        ws.send_text.assert_awaited_once_with("pong")
        nm.connect.assert_called_once_with(ws, "w1")
        nm.disconnect.assert_called_once_with(ws, "w1")

    async def test_non_ping_message_no_pong(self):
        ws, nm = self._mock_ws(["client message", WebSocketDisconnect(code=1000)])
        with patch("api.websocket_routes.SessionLocal"), \
                patch("api.websocket_routes.get_current_user_ws",
                      new=AsyncMock(return_value=_user("u1"))), \
                patch("api.websocket_routes.notification_manager", new=nm):
            await websocket_endpoint(ws, "w1")
        ws.send_text.assert_not_called()

    async def test_generic_exception_disconnects(self):
        ws, nm = self._mock_ws(RuntimeError("boom"))
        with patch("api.websocket_routes.SessionLocal"), \
                patch("api.websocket_routes.get_current_user_ws",
                      new=AsyncMock(return_value=_user("u1"))), \
                patch("api.websocket_routes.notification_manager", new=nm):
            await websocket_endpoint(ws, "w1")
        nm.connect.assert_called_once_with(ws, "w1")
        nm.disconnect.assert_called_once_with(ws, "w1")

    async def test_websocket_disconnect_exception(self):
        ws, nm = self._mock_ws(WebSocketDisconnect(code=1000))
        with patch("api.websocket_routes.SessionLocal"), \
                patch("api.websocket_routes.get_current_user_ws",
                      new=AsyncMock(return_value=_user("u1"))), \
                patch("api.websocket_routes.notification_manager", new=nm):
            await websocket_endpoint(ws, "w1")
        nm.connect.assert_called_once_with(ws, "w1")
        nm.disconnect.assert_called_once_with(ws, "w1")

    async def test_websocket_endpoint_default_delegates(self):
        ws = MagicMock()
        with patch("api.websocket_routes.websocket_endpoint",
                   new=AsyncMock()) as we:
            await websocket_endpoint_default(ws)
        we.assert_awaited_once_with(ws, "default")

    async def test_no_token_direct(self):
        ws = MagicMock()
        ws.query_params = {}
        ws.close = AsyncMock()
        with patch("api.websocket_routes.SessionLocal"):
            await websocket_endpoint(ws, "w1")
        ws.close.assert_called_once_with(code=1008, reason="Missing authentication token")
