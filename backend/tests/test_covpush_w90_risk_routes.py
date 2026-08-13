"""Coverage wave 90 — api/risk_routes.py (0% → 95%+).

Covers all three endpoints in BOTH modes: FINANCIAL_FORENSICS_MOCK=true
(module reload → canned intel) and live mode (services fully mocked).
Auth 401 verified on every endpoint. MOCK_MODE is read at import time,
so the module is reloaded inside the env patch.
"""
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user

import api.risk_routes as rr


class FakeUser:
    id = "u-1"


def _build_client(raise_exc=True):
    app = FastAPI()
    app.include_router(rr.router)
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
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
        svc.predict_churn_risk.assert_awaited_once_with("default")

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
        svc.detect_ar_delays.assert_awaited_once_with("default")

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
        svc.detect_anomalies.assert_awaited_once_with("default")

    def test_fraud_live_service_failure(self, err_client):
        svc = AsyncMock()
        svc.detect_anomalies.side_effect = RuntimeError("boom")
        with patch.object(rr, "FraudDetectionService", return_value=svc):
            resp = err_client.get("/api/risk/fraud")
        assert resp.status_code == 500
