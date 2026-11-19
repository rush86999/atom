"""Coverage wave 90 — api/risk_routes.py (0% → 95%+).

Covers all three endpoints in BOTH modes: FINANCIAL_FORENSICS_MOCK=true
(module reload → canned intel) and live mode (services fully mocked).
Auth 401 verified on every endpoint. MOCK_MODE is read at import time,
so the module is reloaded inside the env patch.
"""
import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user

import api.risk_routes as rr


class FakeUser:
    id = "u-1"
    tenant_id = "tenant-u-1"
    workspace_id = "workspace-u-1"


class UnboundUser:
    """Authenticated, but with no persisted scope binding."""

    id = "u-unbound"


class BootstrapUser:
    """Server-owned Personal Edition bootstrap account (NULL scope)."""

    id = "u-bootstrap"
    email = "admin@example.com"
    role = "workspace_admin"
    tenant_id = None
    workspace_id = None


def _build_client(raise_exc=True, user=None):
    app = FastAPI()
    app.include_router(rr.router)
    app.dependency_overrides[get_current_user] = lambda: user or FakeUser()
    return TestClient(app, raise_server_exceptions=raise_exc)


@pytest.fixture
def client():
    return _build_client()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(rr.router)
    return TestClient(app)


@pytest.fixture
def mock_mode_client():
    """Reload risk_routes with FINANCIAL_FORENSICS_MOCK=true."""
    with patch.dict("os.environ", {"FINANCIAL_FORENSICS_MOCK": "true"}):
        mod = importlib.reload(rr)
    try:
        yield _build_client()
    finally:
        with patch.dict("os.environ", {"FINANCIAL_FORENSICS_MOCK": "false"}):
            importlib.reload(rr)


class TestAuth:
    def test_customer_protection_requires_auth(self, anon_client):
        assert anon_client.get("/api/risk/customer-protection").status_code == 401

    def test_early_warning_requires_auth(self, anon_client):
        assert anon_client.get("/api/risk/early-warning").status_code == 401

    def test_fraud_requires_auth(self, anon_client):
        assert anon_client.get("/api/risk/fraud").status_code == 401


class TestMockMode:
    def test_customer_protection_mock_intel(self, mock_mode_client):
        resp = mock_mode_client.get("/api/risk/customer-protection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_mock"] is True
        assert len(data["churn_risk"]) == 2
        assert data["churn_risk"][0]["risk_level"] == "HIGH"
        assert len(data["vip_opportunities"]) == 2

    def test_early_warning_mock_intel(self, mock_mode_client):
        resp = mock_mode_client.get("/api/risk/early-warning")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_mock"] is True
        assert len(data["ar_alerts"]) == 2
        assert data["ar_alerts"][0]["days_overdue"] == 52

    def test_fraud_mock_intel(self, mock_mode_client):
        resp = mock_mode_client.get("/api/risk/fraud")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_mock"] is True
        assert data["anomalies"][0]["type"] == "LARGE_OUTFLOW"


class TestLiveMode:
    @pytest.fixture
    def err_client(self):
        return _build_client(raise_exc=False)

    def test_customer_protection_live(self, client):
        svc = AsyncMock()
        svc.predict_churn_risk.return_value = [{"deal_id": "d1", "risk_level": "MEDIUM"}]
        with patch.object(rr, "CustomerProtectionService", return_value=svc):
            resp = client.get("/api/risk/customer-protection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_mock"] is False
        assert data["churn_risk"] == [{"deal_id": "d1", "risk_level": "MEDIUM"}]
        assert data["vip_opportunities"] == []
        svc.predict_churn_risk.assert_awaited_once_with("tenant-u-1")

    def test_customer_protection_live_service_failure(self, err_client):
        svc = AsyncMock()
        svc.predict_churn_risk.side_effect = RuntimeError("boom")
        with patch.object(rr, "CustomerProtectionService", return_value=svc):
            resp = err_client.get("/api/risk/customer-protection")
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_early_warning_live(self, client):
        svc = AsyncMock()
        svc.detect_ar_delays.return_value = [{"id": "inv-1", "amount": 500}]
        with patch.object(rr, "EarlyWarningService", return_value=svc):
            resp = client.get("/api/risk/early-warning")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_mock"] is False
        assert data["ar_alerts"] == [{"id": "inv-1", "amount": 500}]
        svc.detect_ar_delays.assert_awaited_once_with("workspace-u-1")

    def test_early_warning_live_service_failure(self, err_client):
        svc = AsyncMock()
        svc.detect_ar_delays.side_effect = RuntimeError("boom")
        with patch.object(rr, "EarlyWarningService", return_value=svc):
            resp = err_client.get("/api/risk/early-warning")
        assert resp.status_code == 500

    def test_fraud_live(self, client):
        svc = AsyncMock()
        svc.detect_anomalies.return_value = [{"id": "tx-1", "severity": "HIGH"}]
        with patch.object(rr, "FraudDetectionService", return_value=svc):
            resp = client.get("/api/risk/fraud")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_mock"] is False
        assert data["anomalies"] == [{"id": "tx-1", "severity": "HIGH"}]
        svc.detect_anomalies.assert_awaited_once_with("tenant-u-1")

    def test_fraud_live_service_failure(self, err_client):
        svc = AsyncMock()
        svc.detect_anomalies.side_effect = RuntimeError("boom")
        with patch.object(rr, "FraudDetectionService", return_value=svc):
            resp = err_client.get("/api/risk/fraud")
        assert resp.status_code == 500


class TestScopeBinding:
    def test_unbound_principal_fails_closed(self):
        client = _build_client(user=UnboundUser())
        with patch.object(rr, "is_bootstrap_identity", return_value=False):
            resp = client.get("/api/risk/customer-protection")
        assert resp.status_code == 403

    def test_bootstrap_uses_personal_defaults(self):
        svc = AsyncMock()
        svc.predict_churn_risk.return_value = []
        client = _build_client(user=BootstrapUser())
        with patch("core.personal_scope.is_bootstrap_identity", return_value=True), \
                patch.object(rr, "is_bootstrap_identity", return_value=True), \
                patch.object(rr, "CustomerProtectionService", return_value=svc):
            resp = client.get("/api/risk/customer-protection")
        assert resp.status_code == 200
        svc.predict_churn_risk.assert_awaited_once_with("default")


class _RecordingQuery:
    def __init__(self, model):
        self.model = model
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def limit(self, _limit):
        return self

    def all(self):
        return []


class _RecordingDB:
    def __init__(self):
        self.queries = []

    def query(self, model):
        query = _RecordingQuery(model)
        self.queries.append(query)
        return query


def _has_scope_filter(query, column_name, expected_value):
    for criterion in query.filters:
        left = getattr(criterion, "left", None)
        right = getattr(criterion, "right", None)
        if (
            getattr(left, "name", None) == column_name
            and getattr(right, "value", None) == expected_value
        ):
            return True
    return False


class TestScopedQueries:
    def test_subscription_query_is_tenant_scoped(self):
        from core.risk_prevention import CustomerProtectionService

        db = _RecordingDB()
        asyncio.run(CustomerProtectionService(db).predict_churn_risk("tenant-q"))
        assert _has_scope_filter(db.queries[0], "tenant_id", "tenant-q")

    def test_invoice_query_is_workspace_scoped(self):
        from core.risk_prevention import EarlyWarningService

        db = _RecordingDB()
        asyncio.run(EarlyWarningService(db).detect_ar_delays("workspace-q"))
        assert _has_scope_filter(db.queries[0], "workspace_id", "workspace-q")

    def test_ecommerce_order_query_is_tenant_scoped(self):
        from core.risk_prevention import FraudDetectionService

        db = _RecordingDB()
        asyncio.run(FraudDetectionService(db).detect_anomalies("tenant-q"))
        assert _has_scope_filter(db.queries[0], "tenant_id", "tenant-q")

    def test_empty_scope_does_not_query(self):
        from core.risk_prevention import EarlyWarningService

        db = _RecordingDB()
        assert asyncio.run(EarlyWarningService(db).detect_ar_delays("")) == []
        assert db.queries == []
