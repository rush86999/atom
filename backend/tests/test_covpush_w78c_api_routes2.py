# -*- coding: utf-8 -*-
"""Coverage wave 78c — 8 API route modules (each >=95% standalone).

Targets (before % measured with existing suites 2026-08-14):
- api/gatekeeper_routes.py        (92% — missing required_scopes/require_approval_for/mutations overrides)
- api/gateway_key_routes.py       (100% — regression re-run standalone)
- api/health_monitoring_routes.py (97% — missing HTTPException re-raise + external-data benchmark branches)
- api/health_routes.py            (95% — /health/stage-router never exercised)
- api/integration_dashboard_routes.py (88% — 8 endpoint exception branches)
- api/integrations_catalog_routes.py (100% — regression re-run standalone)
- api/learning_routes.py          (100% — regression re-run standalone)
- api/mcp_client_routes.py        (92% — missing stdio config + client.close failure branches)

No LLM spend, no network, no real DB: FastAPI TestClient + dependency_overrides +
service/mock patches on REAL module names (no `backend.` prefix). 401 tests run
the real auth dependency chain (no token -> 401); 403 tests override
get_current_user with a member and let the real require_permission/RBACService
dependency reject.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


# ============================================================================
# Shared helpers
# ============================================================================

def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _anon_client(router):
    return TestClient(_app(router), raise_server_exceptions=False)


def _auth_client(router, user=None, db=None):
    app = _app(router)
    if user is not None:
        app.dependency_overrides[get_db] = lambda: None
        app.dependency_overrides[auth_get_current_user] = lambda: user
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


class SuperAdmin:
    id = "admin-w78c"
    role = "super_admin"
    tenant_id = "t-1"
    status = "active"
    email = "admin@test.local"


class Member:
    id = "member-w78c"
    role = "member"
    tenant_id = "t-1"
    status = "active"
    email = "member@test.local"


def _yield_session(session):
    yield session


def await_coroutine(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# api/gatekeeper_routes.py — P3 outbound gatekeeper config API
# ============================================================================

class TestGatekeeperRoutes:
    def _client(self, user=SuperAdmin()):
        from api.gatekeeper_routes import router
        return _auth_client(router, user=user)

    def test_get_config_success(self):
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch("middleware.governance_middleware.governance_middleware") as gm:
            gm._config = {"slack": {"rate_limit": 100}}
            r = self._client().get("/api/gatekeeper/config")
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["data"]["slack"]["rate_limit"] == 100

    def test_update_config_all_fields_sets_sets(self):
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch("middleware.governance_middleware.governance_middleware") as gm:
            gm.configure = MagicMock()
            r = self._client().put(
                "/api/gatekeeper/config/slack",
                json={
                    "rate_limit": 120,
                    "masked_fields": ["token", "secret"],
                    "required_scopes": ["read", "write"],
                    "require_approval_for": ["send_message"],
                    "mutations": ["update", "delete"],
                },
            )
        assert r.status_code == 200
        gm.configure.assert_called_once()
        service, override = gm.configure.call_args[0]
        assert service == "slack"
        assert override["rate_limit"] == 120
        assert override["masked_fields"] == {"token", "secret"}
        assert override["required_scopes"] == {"read", "write"}
        assert override["require_approval_for"] == {"send_message"}
        assert override["mutations"] == {"update", "delete"}
        body = r.json()["data"]
        assert body["policy"]["masked_fields"] == ["secret", "token"]
        assert body["policy"]["mutations"] == ["delete", "update"]

    def test_update_config_partial_only_rate_limit(self):
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch("middleware.governance_middleware.governance_middleware") as gm:
            gm.configure = MagicMock()
            r = self._client().put("/api/gatekeeper/config/slack", json={"rate_limit": 5})
        assert r.status_code == 200
        service, override = gm.configure.call_args[0]
        assert override == {"rate_limit": 5}

    def test_update_config_empty_body_no_overrides(self):
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch("middleware.governance_middleware.governance_middleware") as gm:
            gm.configure = MagicMock()
            r = self._client().put("/api/gatekeeper/config/slack", json={})
        assert r.status_code == 200
        service, override = gm.configure.call_args[0]
        assert override == {}

    def test_config_requires_auth_401(self):
        from api.gatekeeper_routes import router
        client = _anon_client(router)
        assert client.get("/api/gatekeeper/config").status_code == 401
        assert client.put("/api/gatekeeper/config/slack", json={"rate_limit": 1}).status_code == 401

    def test_config_forbidden_for_member_403(self):
        from api.gatekeeper_routes import router
        client = _auth_client(router, user=Member())
        assert client.get("/api/gatekeeper/config").status_code == 403
        assert client.put("/api/gatekeeper/config/slack", json={"rate_limit": 1}).status_code == 403


# ============================================================================
# api/gateway_key_routes.py — P0 LLM gateway keys
# ============================================================================

class TestGatewayKeyRoutes:
    @pytest.fixture
    def client(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from core.database import Base

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = Session()

        from api.gateway_key_routes import router
        from core.models import User

        app = _app(router)

        def _user():
            return User(
                id="u-w78c", email="u@x.com", first_name="U", last_name="X",
                role="admin", status="active", tenant_id="t-1",
            )

        app.dependency_overrides[auth_get_current_user] = _user
        app.dependency_overrides[get_db] = lambda: session
        yield TestClient(app, raise_server_exceptions=False), session
        session.close()
        engine.dispose()

    def test_create_returns_plaintext_once(self, client):
        from core.models import GatewayApiKey
        c, session = client
        r = c.post("/api/gateway/keys", json={"name": "prod"})
        assert r.status_code == 201
        data = r.json()
        assert data["key"].startswith("atom_sk_")
        assert data["key_prefix"].startswith("atom_sk_")
        row = session.query(GatewayApiKey).filter_by(id=data["id"]).first()
        assert row.key_hash != data["key"]
        assert len(row.key_hash) == 64  # raw sha256 hexdigest, no prefix
        assert row.key_prefix == data["key_prefix"]

    def test_create_custom_fields(self, client):
        from core.models import GatewayApiKey
        c, session = client
        expires = datetime.now(timezone.utc) + timedelta(days=1)
        r = c.post("/api/gateway/keys", json={
            "name": "temp", "rate_limit_per_minute": 7, "expires_at": expires.isoformat(),
        })
        assert r.status_code == 201
        row = session.query(GatewayApiKey).filter_by(id=r.json()["id"]).first()
        assert row.rate_limit_per_minute == 7
        assert row.expires_at is not None
        assert row.name == "temp"

    def test_create_validation_422(self, client):
        c, _ = client
        assert c.post("/api/gateway/keys", json={"rate_limit_per_minute": 0}).status_code == 422
        assert c.post("/api/gateway/keys", json={"rate_limit_per_minute": 10001}).status_code == 422
        assert c.post("/api/gateway/keys", json={"name": "x" * 300}).status_code == 422

    def test_list_keys_empty(self, client):
        c, _ = client
        r = c.get("/api/gateway/keys")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_list_keys_serializes_rows(self, client):
        c, session = client
        c.post("/api/gateway/keys", json={"name": "a"})
        expires = datetime.now(timezone.utc) + timedelta(days=2)
        c.post("/api/gateway/keys", json={"name": "b", "expires_at": expires.isoformat()})
        r = c.get("/api/gateway/keys")
        assert r.status_code == 200
        rows = r.json()["data"]
        assert len(rows) == 2
        by_name = {row["name"]: row for row in rows}
        assert by_name["a"]["expires_at"] is None
        assert by_name["a"]["last_used"] is None
        assert by_name["b"]["expires_at"] is not None
        assert by_name["b"]["key_prefix"].startswith("atom_sk_")
        assert by_name["b"]["is_active"] is True

    def test_revoke_key_success(self, client):
        c, session = client
        kid = c.post("/api/gateway/keys", json={"name": "x"}).json()["id"]
        r = c.delete(f"/api/gateway/keys/{kid}")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_revoke_key_missing_404(self, client):
        c, _ = client
        assert c.delete("/api/gateway/keys/nope").status_code == 404

    def test_revoke_key_other_user_404(self, client):
        from api.gateway_key_routes import router
        from core.models import User
        c, session = client
        kid = c.post("/api/gateway/keys", json={"name": "mine"}).json()["id"]
        app = _app(router)

        def _other():
            return User(
                id="other", email="o@x.com", first_name="O", last_name="Y",
                role="admin", status="active",
            )

        app.dependency_overrides[auth_get_current_user] = _other
        app.dependency_overrides[get_db] = lambda: session
        other_client = TestClient(app, raise_server_exceptions=False)
        assert other_client.delete(f"/api/gateway/keys/{kid}").status_code == 404

    def test_rotate_key_success_inherits_fields(self, client):
        from core.models import GatewayApiKey
        c, session = client
        expires = datetime.now(timezone.utc) + timedelta(days=3)
        kid = c.post("/api/gateway/keys", json={
            "name": "rot", "rate_limit_per_minute": 9, "expires_at": expires.isoformat(),
        }).json()["id"]
        r = c.post(f"/api/gateway/keys/{kid}/rotate")
        assert r.status_code == 200
        data = r.json()
        assert data["key"].startswith("atom_sk_")
        old = session.query(GatewayApiKey).filter_by(id=kid).first()
        assert old.is_active is False
        assert old.revoked_at is not None
        assert old.last_rotated is not None
        new_row = session.query(GatewayApiKey).filter_by(id=data["id"]).first()
        assert new_row.name == "rot"
        assert new_row.rate_limit_per_minute == 9
        assert new_row.expires_at is not None
        assert new_row.user_id == "u-w78c"

    def test_rotate_key_missing_404(self, client):
        c, _ = client
        assert c.post("/api/gateway/keys/nope/rotate").status_code == 404

    def test_all_routes_require_auth_401(self):
        from api.gateway_key_routes import router
        client = _anon_client(router)
        assert client.post("/api/gateway/keys", json={"name": "x"}).status_code == 401
        assert client.get("/api/gateway/keys").status_code == 401
        assert client.delete("/api/gateway/keys/k").status_code == 401
        assert client.post("/api/gateway/keys/k/rotate").status_code == 401


# ============================================================================
# api/health_monitoring_routes.py
# ============================================================================

class TestHealthMonitoringRoutes:
    def _c(self, db=None):
        from api.health_monitoring_routes import router
        return _auth_client(router, user=SuperAdmin(), db=db or MagicMock())

    def _svc(self):
        return AsyncMock()

    def test_agent_health_success(self):
        svc = self._svc()
        svc.get_agent_health.return_value = {
            "agent_id": "a-1", "agent_name": "Helper", "status": "active",
            "current_operation": None, "operations_completed": 10, "success_rate": 0.9,
            "confidence_score": 0.8, "last_active": "2026-01-01T00:00:00Z",
            "health_trend": "stable", "metrics": {},
        }
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/agent/a-1")
        assert r.status_code == 200
        assert r.json()["agent_name"] == "Helper"

    def test_agent_health_not_found_404(self):
        svc = self._svc()
        svc.get_agent_health.return_value = {"status": "error", "error": "Agent not found"}
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/agent/ghost")
        assert r.status_code == 404

    def test_agent_health_generic_exception_500(self):
        svc = self._svc()
        svc.get_agent_health.side_effect = RuntimeError("boom")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/agent/a-1")
        assert r.status_code == 500

    def test_integrations_health_success(self):
        svc = self._svc()
        svc.get_all_integrations_health.return_value = [{
            "integration_id": "i-1", "integration_name": "Slack", "status": "healthy",
            "last_used": "2026-01-01", "latency_ms": 12.5, "error_rate": 0.0,
            "health_trend": "stable", "connection_status": "connected",
        }]
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/integrations")
        assert r.status_code == 200
        assert r.json()[0]["integration_name"] == "Slack"

    def test_integrations_health_http_exception_re_raised(self):
        svc = self._svc()
        svc.get_all_integrations_health.side_effect = HTTPException(status_code=404, detail="x")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/integrations")
        assert r.status_code == 404

    def test_integrations_health_generic_exception_500(self):
        svc = self._svc()
        svc.get_all_integrations_health.side_effect = RuntimeError("boom")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/integrations")
        assert r.status_code == 500

    def test_system_metrics_success(self):
        svc = self._svc()
        svc.get_system_metrics.return_value = {
            "cpu_usage": 0.3, "memory_usage": 0.5, "active_operations": 2,
            "queue_depth": 0, "total_agents": 3, "active_agents": 1,
            "total_integrations": 2, "healthy_integrations": 2, "alerts": {},
        }
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/system")
        assert r.status_code == 200
        assert r.json()["cpu_usage"] == 0.3

    def test_system_metrics_http_exception_re_raised(self):
        svc = self._svc()
        svc.get_system_metrics.side_effect = HTTPException(status_code=400, detail="bad")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/system")
        assert r.status_code == 400

    def test_system_metrics_generic_exception_500(self):
        svc = self._svc()
        svc.get_system_metrics.side_effect = RuntimeError("boom")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/system")
        assert r.status_code == 500

    def test_alerts_filter_and_sort(self):
        svc = self._svc()
        svc.get_active_alerts.return_value = [
            {"alert_id": "a2", "severity": "info", "message": "m2", "source_type": "s",
             "source_id": "1", "timestamp": "t", "action_required": False, "acknowledged": False},
            {"alert_id": "a1", "severity": "critical", "message": "m1", "source_type": "s",
             "source_id": "1", "timestamp": "t", "action_required": True, "acknowledged": False},
            {"alert_id": "a3", "severity": "warning", "message": "m3", "source_type": "s",
             "source_id": "1", "timestamp": "t", "action_required": False, "acknowledged": False},
        ]
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/alerts")
        assert [a["alert_id"] for a in r.json()] == ["a1", "a3", "a2"]

        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r2 = self._c().get("/api/health/alerts?severity=critical")
        assert [a["alert_id"] for a in r2.json()] == ["a1"]

        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r3 = self._c().get("/api/health/alerts?severity=unknown")
        assert r3.json() == []

    def test_alerts_generic_exception_500(self):
        svc = self._svc()
        svc.get_active_alerts.side_effect = RuntimeError("boom")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/alerts")
        assert r.status_code == 500

    def test_acknowledge_alert_success(self):
        svc = self._svc()
        svc.acknowledge_alert.return_value = True
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().post(
                "/api/health/alerts/al-1/acknowledge",
                json={"acknowledged": True, "notes": "fixed"},
            )
        assert r.status_code == 200
        svc.acknowledge_alert.assert_awaited_once_with("al-1", "admin-w78c")

    def test_acknowledge_alert_not_found_404(self):
        svc = self._svc()
        svc.acknowledge_alert.return_value = False
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().post("/api/health/alerts/al-x/acknowledge", json={"acknowledged": True})
        assert r.status_code == 404

    def test_acknowledge_alert_generic_exception_500(self):
        svc = self._svc()
        svc.acknowledge_alert.side_effect = RuntimeError("boom")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().post("/api/health/alerts/al-1/acknowledge", json={"acknowledged": True})
        assert r.status_code == 500

    def test_health_history_success(self):
        svc = self._svc()
        svc.get_health_history.return_value = [{"ts": "t1"}, {"ts": "t2"}]
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/history/agent?entity_id=a-1&days=7")
        assert r.status_code == 200
        body = r.json()
        assert body["health_type"] == "agent"
        assert body["entity_id"] == "a-1"
        assert body["days"] == 7
        assert body["data_points"] == 2
        svc.get_health_history.assert_awaited_once_with(
            health_type="agent", entity_id="a-1", days=7)

    def test_health_history_generic_exception_500(self):
        svc = self._svc()
        svc.get_health_history.side_effect = RuntimeError("boom")
        with patch("api.health_monitoring_routes.get_health_monitoring_service", return_value=svc):
            r = self._c().get("/api/health/history/system")
        assert r.status_code == 500

    def test_external_data_health_healthy(self):
        pricing = MagicMock()
        pricing.last_fetch = datetime.now(timezone.utc)
        pricing.pricing_cache = {"gpt-4o": {"input": 1.0}}
        pricing._is_cache_valid.return_value = True
        benchmark = MagicMock()
        benchmark.last_fetch = datetime.now(timezone.utc)
        benchmark.benchmark_cache = {"gpt-4o": {"score": 80.0}}
        benchmark._is_cache_valid.return_value = True
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=pricing), \
             patch("core.dynamic_benchmark_fetcher.get_benchmark_fetcher", return_value=benchmark):
            r = self._c().get("/api/health/external-data")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["pricing"]["model_count"] == 1
        assert body["pricing"]["cache_age_hours"] is not None
        assert body["benchmarks"]["cache_age_hours"] is not None
        assert body["warnings"] == []

    def test_external_data_health_benchmark_stale_and_empty_cache(self):
        pricing = MagicMock()
        pricing.last_fetch = datetime.now(timezone.utc) - timedelta(hours=48)
        pricing.pricing_cache = {}
        pricing._is_cache_valid.return_value = False
        benchmark = MagicMock()
        benchmark.last_fetch = datetime.now(timezone.utc) - timedelta(hours=4)
        benchmark.benchmark_cache = {}
        benchmark._is_cache_valid.return_value = False
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=pricing), \
             patch("core.dynamic_benchmark_fetcher.get_benchmark_fetcher", return_value=benchmark):
            r = self._c().get("/api/health/external-data")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "degraded"
        assert body["benchmarks"]["cache_age_hours"] is not None
        assert any("Benchmark data is stale" in w for w in body["warnings"])
        assert any("Pricing data is stale" in w for w in body["warnings"])
        assert "Benchmark cache is empty" in body["warnings"]
        assert "Pricing cache is empty" in body["warnings"]

    def test_external_data_health_error_500(self):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", side_effect=RuntimeError("boom")):
            r = self._c().get("/api/health/external-data")
        assert r.status_code == 500

    def test_health_check_success(self):
        r = self._c().get("/api/health/health")
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["data"]["status"] == "healthy"

    def test_requires_auth_401(self):
        from api.health_monitoring_routes import router
        client = _anon_client(router)
        assert client.get("/api/health/agent/a-1").status_code == 401
        assert client.get("/api/health/integrations").status_code == 401
        assert client.get("/api/health/system").status_code == 401
        assert client.get("/api/health/alerts").status_code == 401
        assert client.post("/api/health/alerts/a/acknowledge", json={"acknowledged": True}).status_code == 401
        assert client.get("/api/health/history/agent").status_code == 401


# ============================================================================
# api/health_routes.py — /health/{live,ready,metrics} + stage-router
# ============================================================================

class TestHealthRoutes:
    @pytest.fixture
    def client(self):
        from api.health_routes import router
        app = _app(router)
        return TestClient(app, raise_server_exceptions=False), app

    def test_liveness(self, client):
        c, _ = client
        r = c.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"
        assert "timestamp" in r.json()

    def test_readiness_all_healthy(self, client):
        from api import health_routes as hr
        c, _ = client
        with patch.object(hr, "_check_database", new=AsyncMock(return_value={
            "healthy": True, "message": "ok", "latency_ms": 1.0})), \
             patch.object(hr, "_check_disk_space", new=AsyncMock(return_value={
                "healthy": True, "message": "10GB free", "free_gb": 10.0})):
            r = c.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"
        assert set(r.json()["checks"]) == {"database", "disk"}

    def test_readiness_db_failure_503(self, client):
        from api import health_routes as hr
        c, _ = client
        with patch.object(hr, "_check_database", new=AsyncMock(return_value={
            "healthy": False, "message": "db down", "latency_ms": 0})), \
             patch.object(hr, "_check_disk_space", new=AsyncMock(return_value={
                "healthy": True, "message": "ok", "free_gb": 10.0})):
            r = c.get("/health/ready")
        assert r.status_code == 503
        assert r.json()["detail"]["status"] == "not_ready"

    def test_readiness_disk_failure_503(self, client):
        from api import health_routes as hr
        c, _ = client
        with patch.object(hr, "_check_database", new=AsyncMock(return_value={
            "healthy": True, "message": "ok", "latency_ms": 1.0})), \
             patch.object(hr, "_check_disk_space", new=AsyncMock(return_value={
                "healthy": False, "message": "low", "free_gb": 0.5})):
            r = c.get("/health/ready")
        assert r.status_code == 503
        assert r.json()["detail"]["checks"]["disk"]["healthy"] is False

    async def test_check_database_success(self):
        from api.health_routes import _check_database
        session = Mock()
        session.execute.return_value.fetchone.return_value = (1,)
        with patch("core.database.SessionLocal", return_value=session):
            result = await _check_database()
        assert result["healthy"] is True
        session.close.assert_called_once()

    async def test_check_database_timeout(self):
        from api.health_routes import _check_database
        session = Mock()
        with patch("core.database.SessionLocal", return_value=session), \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            result = await _check_database()
        assert result["healthy"] is False
        assert "timeout" in result["message"].lower()

    async def test_check_database_sqlalchemy_error(self):
        from sqlalchemy.exc import SQLAlchemyError
        from api.health_routes import _check_database
        session = Mock()
        session.execute.side_effect = SQLAlchemyError("broken")
        with patch("core.database.SessionLocal", return_value=session):
            result = await _check_database()
        assert result["healthy"] is False
        assert result["message"] == "Database error"

    async def test_check_database_generic_error(self):
        from api.health_routes import _check_database
        with patch("core.database.SessionLocal", side_effect=RuntimeError("boom")):
            result = await _check_database()
        assert result["healthy"] is False
        assert result["message"] == "Unexpected database error"

    async def test_execute_db_query_success(self):
        from api.health_routes import _execute_db_query_session
        session = Mock()
        session.execute.return_value.fetchone.return_value = (1,)
        assert await _execute_db_query_session(session) is True

    async def test_execute_db_query_exception_reraises(self):
        from api.health_routes import _execute_db_query_session
        session = Mock()
        session.execute.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await _execute_db_query_session(session)

    def _db_fixture(self, session_ok=True):
        db = MagicMock()
        session = Mock()
        if session_ok:
            session.execute.return_value.fetchone.return_value = (1,)
        else:
            session.execute.side_effect = RuntimeError("boom")
        db.__next__.return_value = session
        return db, session

    def test_database_connectivity_healthy(self, client):
        from core.database import get_db
        from api import health_routes as hr
        c, app = client
        db, session = self._db_fixture()
        app.dependency_overrides[get_db] = lambda: db
        pool = Mock()
        pool.size.return_value, pool.checkedin.return_value = 5, 5
        pool.checkedout.return_value, pool.overflow.return_value = 0, 0
        pool.max_overflow = 10
        with patch.object(hr, "engine") as eng:
            eng.pool = pool
            r = c.get("/health/db")
        assert r.status_code == 200
        body = r.json()
        assert body["database"]["connected"] is True
        assert body["database"]["pool_status"]["size"] == 5
        session.close.assert_called_once()

    def test_database_connectivity_slow_query_warning(self, client):
        from core.database import get_db
        from api import health_routes as hr
        c, app = client
        db, session = self._db_fixture()
        app.dependency_overrides[get_db] = lambda: db
        pool = Mock()
        pool.size.return_value, pool.checkedin.return_value = 5, 5
        pool.checkedout.return_value, pool.overflow.return_value = 0, 0
        pool.max_overflow = 10
        with patch.object(hr, "engine") as eng, \
             patch.object(hr.time, "time", side_effect=[0.0] + [0.2] * 100):
            eng.pool = pool
            r = c.get("/health/db")
        assert r.status_code == 200
        assert "warning" in r.json()["database"]

    def test_database_connectivity_failure_503(self, client):
        from core.database import get_db
        c, app = client
        db, session = self._db_fixture(session_ok=False)
        app.dependency_overrides[get_db] = lambda: db
        r = c.get("/health/db")
        assert r.status_code == 503
        assert r.json()["detail"]["database"]["connected"] is False
        session.close.assert_called_once()

    async def test_disk_space_healthy(self):
        from api.health_routes import _check_disk_space
        disk = SimpleNamespace(free=20 * 1024 ** 3)
        with patch("psutil.disk_usage", return_value=disk):
            result = await _check_disk_space()
        assert result["healthy"] is True
        assert result["free_gb"] == 20.0

    async def test_disk_space_low(self):
        from api.health_routes import _check_disk_space
        disk = SimpleNamespace(free=0.5 * 1024 ** 3)
        with patch("psutil.disk_usage", return_value=disk):
            result = await _check_disk_space()
        assert result["healthy"] is False
        assert "Low disk space" in result["message"]

    async def test_disk_space_exception(self):
        from api.health_routes import _check_disk_space
        with patch("psutil.disk_usage", side_effect=RuntimeError("boom")):
            result = await _check_disk_space()
        assert result["healthy"] is False
        assert result["message"] == "Disk check error"

    def test_stage_router_status_success(self, client):
        c, _ = client
        with patch("core.llm.stage_router.stage_router_status", return_value={
            "phase": "collecting", "next_action": "collect more",
        }):
            r = c.get("/health/stage-router")
        assert r.status_code == 200
        assert r.json()["phase"] == "collecting"

    def test_stage_router_status_error(self, client):
        c, _ = client
        with patch("core.llm.stage_router.stage_router_status", side_effect=RuntimeError("boom")):
            r = c.get("/health/stage-router")
        assert r.status_code == 200
        body = r.json()
        assert body["phase"] == "error"
        assert body["error"] == "internal"

    def test_prometheus_metrics_format(self, client):
        c, _ = client
        with patch("api.health_routes.generate_latest", return_value=b"# HELP x\n# TYPE x gauge\nx 1\n"):
            r = c.get("/health/metrics")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")

    def test_sync_prometheus_metrics_format(self, client):
        c, _ = client
        with patch("prometheus_client.generate_latest", return_value=b"# HELP y\n"):
            r = c.get("/metrics/sync")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")

    def _sync_setup(self, health, http_status):
        monitor = Mock()
        monitor.check_health.return_value = health
        monitor.get_http_status.return_value = http_status
        db = MagicMock()
        session = Mock()
        db.__next__.return_value = session
        return monitor, db, session

    def test_sync_health_healthy(self, client):
        from api import health_routes as hr
        c, _ = client
        monitor, db, session = self._sync_setup({"status": "healthy"}, 200)
        with patch("core.sync_health_monitor.get_sync_health_monitor", return_value=monitor), \
             patch.object(hr, "get_db", return_value=db):
            r = c.get("/health/sync")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"
        session.close.assert_called_once()

    def test_sync_health_unhealthy(self, client):
        from api import health_routes as hr
        c, _ = client
        monitor, db, session = self._sync_setup({"status": "unhealthy"}, 503)
        with patch("core.sync_health_monitor.get_sync_health_monitor", return_value=monitor), \
             patch.object(hr, "get_db", return_value=db):
            r = c.get("/health/sync")
        assert r.status_code == 503
        assert r.json()["status"] == "unhealthy"
        session.close.assert_called_once()


# ============================================================================
# api/integration_dashboard_routes.py
# ============================================================================

class TestIntegrationDashboardRoutes:
    def _c(self):
        from api.integration_dashboard_routes import router
        return _auth_client(router, user=SuperAdmin())

    def _dashboard(self, **attrs):
        d = MagicMock()
        for k, v in attrs.items():
            setattr(d, k, v)
        return d

    def test_metrics_success(self):
        d = self._dashboard()
        d.get_metrics.return_value = {"slack": {"messages_fetched": 10}}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/metrics")
        assert r.status_code == 200
        assert r.json()["data"]["slack"]["messages_fetched"] == 10

    def test_metrics_specific_integration(self):
        d = self._dashboard()
        d.get_metrics.return_value = {"slack": {}}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/metrics?integration=slack")
        assert r.status_code == 200
        d.get_metrics.assert_called_once_with("slack")

    def test_metrics_exception_500(self):
        d = self._dashboard()
        d.get_metrics.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/metrics")
        assert r.status_code == 500

    def test_health_success(self):
        d = self._dashboard()
        d.get_health.return_value = {"slack": {"status": "healthy"}}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/health")
        assert r.status_code == 200
        assert r.json()["data"]["slack"]["status"] == "healthy"

    def test_health_exception_500(self):
        d = self._dashboard()
        d.get_health.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/health")
        assert r.status_code == 500

    def test_overall_status_success(self):
        d = self._dashboard()
        d.get_overall_status.return_value = {
            "overall_status": "healthy", "total_integrations": 2,
            "healthy_count": 2, "degraded_count": 0, "error_count": 0, "disabled_count": 0,
            "total_messages_fetched": 100, "total_messages_processed": 90,
            "total_messages_failed": 1, "overall_success_rate": 0.9,
            "integrations": {"slack": {}},
        }
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/status/overall")
        assert r.status_code == 200
        assert r.json()["overall_status"] == "healthy"

    def test_overall_status_exception_500(self):
        d = self._dashboard()
        d.get_overall_status.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/status/overall")
        assert r.status_code == 500

    def test_alerts_success_and_severity_filter(self):
        alert = {
            "integration": "slack", "severity": "critical", "type": "t",
            "message": "m", "value": 1.0, "threshold": 0.5, "timestamp": "ts",
        }
        d = self._dashboard()
        d.get_alerts.return_value = [alert, {**alert, "severity": "warning"}]
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/alerts")
        assert r.status_code == 200
        assert len(r.json()) == 2

        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r2 = self._c().get("/api/integrations/dashboard/alerts?severity=critical")
        assert len(r2.json()) == 1
        assert r2.json()[0]["severity"] == "critical"

    def test_alerts_exception_500(self):
        d = self._dashboard()
        d.get_alerts.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/alerts")
        assert r.status_code == 500

    def test_alerts_count_success(self):
        d = self._dashboard()
        d.get_alerts.return_value = [
            {"severity": "critical"}, {"severity": "critical"}, {"severity": "warning"},
        ]
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/alerts/count")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["total"] == 3
        assert body["data"]["critical"] == 2
        assert body["data"]["warning"] == 1

    def test_alerts_count_exception_500(self):
        d = self._dashboard()
        d.get_alerts.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/alerts/count")
        assert r.status_code == 500

    def test_statistics_summary_success(self):
        d = self._dashboard()
        d.get_statistics_summary.return_value = {"recent_activity": []}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/statistics/summary")
        assert r.status_code == 200
        assert r.json()["data"]["recent_activity"] == []

    def test_statistics_summary_exception_500(self):
        d = self._dashboard()
        d.get_statistics_summary.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/statistics/summary")
        assert r.status_code == 500

    def test_configuration_success(self):
        d = self._dashboard()
        d.get_configuration.return_value = {"slack": {"enabled": True}}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/configuration")
        assert r.status_code == 200
        assert r.json()["data"]["slack"]["enabled"] is True

    def test_configuration_exception_500(self):
        d = self._dashboard()
        d.get_configuration.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/configuration")
        assert r.status_code == 500

    def test_update_configuration_health_and_config(self):
        d = self._dashboard()
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post(
                "/api/integrations/dashboard/configuration/slack",
                json={
                    "enabled": True, "configured": True, "has_valid_token": True,
                    "has_required_permissions": True, "config": {"token": "x"},
                },
            )
        assert r.status_code == 200
        d.update_health.assert_called_once()
        d.update_configuration.assert_called_once_with("slack", {"token": "x"})

    def test_update_configuration_no_fields(self):
        d = self._dashboard()
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post(
                "/api/integrations/dashboard/configuration/slack", json={"config": {}})
        assert r.status_code == 200
        d.update_health.assert_not_called()
        d.update_configuration.assert_not_called()

    def test_update_configuration_exception_500(self):
        d = self._dashboard()
        d.update_configuration.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post(
                "/api/integrations/dashboard/configuration/slack",
                json={"config": {"token": "x"}},
            )
        assert r.status_code == 500

    def test_update_configuration_requires_auth_401(self):
        from api.integration_dashboard_routes import router
        client = _anon_client(router)
        assert client.post(
            "/api/integrations/dashboard/configuration/slack",
            json={"enabled": True},
        ).status_code == 401

    def test_reset_metrics_all(self):
        d = self._dashboard()
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post("/api/integrations/dashboard/metrics/reset", json={})
        assert r.status_code == 200
        assert "all integrations" in r.json()["message"]
        d.reset_metrics.assert_called_once_with(None)

    def test_reset_metrics_single(self):
        d = self._dashboard()
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post("/api/integrations/dashboard/metrics/reset", json={"integration": "slack"})
        assert r.status_code == 200
        assert "slack" in r.json()["message"]
        d.reset_metrics.assert_called_once_with("slack")

    def test_reset_metrics_exception_500(self):
        d = self._dashboard()
        d.reset_metrics.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post("/api/integrations/dashboard/metrics/reset", json={})
        assert r.status_code == 500

    def test_reset_metrics_requires_auth_401(self):
        from api.integration_dashboard_routes import router
        client = _anon_client(router)
        assert client.post("/api/integrations/dashboard/metrics/reset", json={}).status_code == 401

    def test_list_integrations_success(self):
        d = self._dashboard()
        d.get_health.return_value = {"slack": {"status": "healthy", "enabled": True, "configured": True}}
        d.get_metrics.return_value = {"slack": {"messages_fetched": 5, "last_fetch_time": "t1"}}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/integrations")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["count"] == 1
        assert body["integrations"][0]["name"] == "slack"
        assert body["integrations"][0]["messages_fetched"] == 5

    def test_list_integrations_exception_500(self):
        d = self._dashboard()
        d.get_health.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/integrations")
        assert r.status_code == 500

    def test_integration_details_success(self):
        d = self._dashboard()
        d.get_health.return_value = {"status": "healthy"}
        d.get_metrics.return_value = {"messages_fetched": 3}
        d.get_configuration.return_value = {"enabled": True}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/integrations/slack/details")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["integration"] == "slack"
        assert body["health"]["status"] == "healthy"

    def test_integration_details_not_found_404(self):
        d = self._dashboard()
        d.get_health.return_value = {}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/integrations/ghost/details")
        assert r.status_code == 404

    def test_integration_details_exception_500(self):
        d = self._dashboard()
        d.get_health.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/integrations/slack/details")
        assert r.status_code == 500

    def test_check_integration_health_success(self):
        d = self._dashboard()
        d.get_health.return_value = {"status": "healthy"}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post("/api/integrations/dashboard/health/slack/check")
        assert r.status_code == 200
        d.update_health.assert_called_once_with("slack")

    def test_check_integration_health_exception_500(self):
        d = self._dashboard()
        d.update_health.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().post("/api/integrations/dashboard/health/slack/check")
        assert r.status_code == 500

    def test_performance_success(self):
        d = self._dashboard()
        d.get_metrics.return_value = {"slack": {
            "avg_fetch_time_ms": 1.0, "p99_fetch_time_ms": 2.0,
            "avg_process_time_ms": 3.0, "p99_process_time_ms": 4.0,
            "fetch_size_bytes": 100, "attachment_count": 2,
        }}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/performance")
        assert r.status_code == 200
        perf = r.json()["data"]["slack"]
        assert perf["avg_fetch_time_ms"] == 1.0
        assert perf["attachment_count"] == 2

    def test_performance_defaults(self):
        d = self._dashboard()
        d.get_metrics.return_value = {"slack": {}}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/performance")
        assert r.status_code == 200
        assert r.json()["data"]["slack"]["avg_fetch_time_ms"] == 0

    def test_performance_exception_500(self):
        d = self._dashboard()
        d.get_metrics.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/performance")
        assert r.status_code == 500

    def test_data_quality_success(self):
        d = self._dashboard()
        d.get_metrics.return_value = {"slack": {
            "messages_fetched": 10, "messages_processed": 9, "messages_failed": 1,
            "messages_duplicate": 0, "success_rate": 90.0, "duplicate_rate": 0.0,
        }}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/data-quality")
        assert r.status_code == 200
        q = r.json()["data"]["slack"]
        assert q["success_rate"] == 90.0

    def test_data_quality_defaults(self):
        d = self._dashboard()
        d.get_metrics.return_value = {"slack": {}}
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/data-quality")
        assert r.status_code == 200
        q = r.json()["data"]["slack"]
        assert q["success_rate"] == 100.0
        assert q["duplicate_rate"] == 0.0

    def test_data_quality_exception_500(self):
        d = self._dashboard()
        d.get_metrics.side_effect = RuntimeError("boom")
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            r = self._c().get("/api/integrations/dashboard/data-quality")
        assert r.status_code == 500


# ============================================================================
# api/integrations_catalog_routes.py
# ============================================================================

class TestIntegrationsCatalogRoutes:
    def _client(self, db):
        from api.integrations_catalog_routes import router
        return _auth_client(router, user=SuperAdmin(), db=db)

    def _piece(self, **kw):
        base = dict(
            id="slack", name="Slack", description="chat", category="comms",
            icon="slack", color="#000", auth_type="oauth2",
            triggers=[], actions=[], popular=True, native_id=None,
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def _query(self, pieces):
        q = MagicMock()
        q.all.return_value = pieces
        q.filter.return_value = q
        return q

    def test_catalog_list(self):
        db = MagicMock()
        db.query.return_value = self._query([self._piece()])
        r = self._client(db).get("/api/v1/integrations/catalog")
        assert r.status_code == 200
        assert r.json()[0]["id"] == "slack"
        assert r.json()[0]["authType"] == "oauth2"

    def test_catalog_category_filter(self):
        db = MagicMock()
        q = self._query([self._piece()])
        db.query.return_value = q
        r = self._client(db).get("/api/v1/integrations/catalog", params={"category": "comms"})
        assert r.status_code == 200
        assert q.filter.call_args is not None

    def test_catalog_popular_filter(self):
        db = MagicMock()
        q = self._query([self._piece()])
        db.query.return_value = q
        r = self._client(db).get("/api/v1/integrations/catalog", params={"popular": "true"})
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_catalog_search_filter(self):
        db = MagicMock()
        q = self._query([self._piece(name="Slack")])
        db.query.return_value = q
        r = self._client(db).get("/api/v1/integrations/catalog", params={"search": "slack"})
        assert r.status_code == 200
        assert r.json()[0]["name"] == "Slack"

    def test_catalog_empty(self):
        db = MagicMock()
        db.query.return_value = self._query([])
        r = self._client(db).get("/api/v1/integrations/catalog")
        assert r.status_code == 200
        assert r.json() == []

    def test_catalog_details_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._piece()
        r = self._client(db).get("/api/v1/integrations/catalog/slack")
        assert r.status_code == 200
        assert r.json()["id"] == "slack"

    def test_catalog_details_not_found_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._client(db).get("/api/v1/integrations/catalog/nope")
        assert r.status_code == 404

    def test_catalog_service_error_500(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        r = self._client(db).get("/api/v1/integrations/catalog")
        assert r.status_code == 500


# ============================================================================
# api/learning_routes.py
# ============================================================================

class TestLearningRoutes:
    def _client(self, user=SuperAdmin()):
        from api.learning_routes import router
        from core.security_dependencies import get_current_user as sdep_uc
        app = _app(router)
        app.dependency_overrides[sdep_uc] = lambda: user
        app.dependency_overrides[get_db] = lambda: MagicMock()
        return TestClient(app, raise_server_exceptions=False)

    def _svc(self, **attrs):
        svc = MagicMock()
        for k, v in attrs.items():
            setattr(svc, k, v)
        return svc

    def test_progress_found(self):
        svc = self._svc()
        svc.get_learning_progress.return_value = {"agent_id": "a-1", "success_rate": 0.8}
        with patch("api.learning_routes.ContinuousLearningService", return_value=svc):
            r = self._client().get("/api/learning/progress/a-1")
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["data"]["success_rate"] == 0.8
        svc.get_learning_progress.assert_called_once_with(tenant_id="t-1", agent_id="a-1")

    def test_progress_not_found_404(self):
        svc = self._svc()
        svc.get_learning_progress.return_value = None
        with patch("api.learning_routes.ContinuousLearningService", return_value=svc):
            r = self._client().get("/api/learning/progress/ghost")
        assert r.status_code == 404

    def test_adaptations_success(self):
        svc = self._svc()
        svc.generate_adaptations.return_value = ["adapt-1"]
        with patch("api.learning_routes.ContinuousLearningService", return_value=svc):
            r = self._client().get("/api/learning/adaptations/a-1")
        assert r.status_code == 200
        assert r.json()["data"]["adaptations"] == ["adapt-1"]
        svc.generate_adaptations.assert_called_once_with(tenant_id="t-1", agent_id="a-1")

    def test_tenant_summary_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        client = self._client()
        client.app.dependency_overrides[get_db] = lambda: db
        svc = self._svc()
        with patch("api.learning_routes.ContinuousLearningService", return_value=svc):
            r = client.get("/api/learning/tenant/summary")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["count"] == 0
        assert body["agents"] == []

    def test_tenant_summary_aggregates_per_agent(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("a-1",), ("a-2",),
        ]
        client = self._client()
        client.app.dependency_overrides[get_db] = lambda: db
        svc = self._svc()
        svc.get_learning_progress.return_value = {"success_rate": 0.9}
        with patch("api.learning_routes.ContinuousLearningService", return_value=svc):
            r = client.get("/api/learning/tenant/summary")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["count"] == 2
        assert body["agents"] == [{"success_rate": 0.9}, {"success_rate": 0.9}]
        assert svc.get_learning_progress.call_count == 2

    def test_requires_auth_401(self):
        from api.learning_routes import router
        client = _anon_client(router)
        assert client.get("/api/learning/progress/a-1").status_code == 401
        assert client.get("/api/learning/adaptations/a-1").status_code == 401
        assert client.get("/api/learning/tenant/summary").status_code == 401


# ============================================================================
# api/mcp_client_routes.py — P6 MCP client
# ============================================================================

class TestMCPClientRoutes:
    def _client(self, user=SuperAdmin()):
        from api.mcp_client_routes import router
        return _auth_client(router, user=user)

    def test_list_servers_filters_builtins(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "tools_cache", {
                 "ext-1": ["t1", "t2"], "google-search": [], "local-tools": [],
                 "brightdata": [],
             }), \
             patch.object(mcp_service, "external_clients", {"ext-1": object()}):
            r = self._client().get("/api/mcp/servers")
        assert r.status_code == 200
        body = r.json()
        ids = [s["server_id"] for s in body["data"]]
        assert ids == ["ext-1"]
        assert body["data"][0]["tool_count"] == 2
        assert body["data"][0]["connected"] is True

    def test_register_server_http_success(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "register_server", new_callable=AsyncMock) as reg, \
             patch.object(mcp_service, "tools_cache", {"ext": ["t1"]}), \
             patch.object(mcp_service, "external_clients", {"ext": object()}):
            r = self._client().post(
                "/api/mcp/servers",
                json={"name": "ext", "transport": "http", "url": "http://x", "headers": {"A": "B"}},
            )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["tool_count"] == 1
        assert data["connected"] is True
        reg.assert_awaited_once()
        name, cfg = reg.call_args[0]
        assert name == "ext"
        assert cfg == {"transport": "http", "url": "http://x", "headers": {"A": "B"}}

    def test_register_server_stdio_config(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "register_server", new_callable=AsyncMock) as reg, \
             patch.object(mcp_service, "tools_cache", {}), \
             patch.object(mcp_service, "external_clients", {}):
            r = self._client().post(
                "/api/mcp/servers",
                json={
                    "name": "ext-stdio", "transport": "stdio",
                    "command": "node", "args": ["server.js"], "env": {"TOKEN": "x"},
                },
            )
        assert r.status_code == 200
        name, cfg = reg.call_args[0]
        assert cfg["command"] == "node"
        assert cfg["args"] == ["server.js"]
        assert cfg["env"] == {"TOKEN": "x"}

    def test_register_server_failure_502(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "register_server", new_callable=AsyncMock) as reg:
            reg.side_effect = RuntimeError("connect failed")
            r = self._client().post(
                "/api/mcp/servers",
                json={"name": "bad", "transport": "http", "url": "http://x"},
            )
        assert r.status_code == 502

    def test_unregister_server_success(self):
        from core.mcp_service import mcp_service
        client_obj = MagicMock()
        client_obj.close = AsyncMock()
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "external_clients", {"ext-1": client_obj}), \
             patch.object(mcp_service, "tools_cache", {"ext-1": []}), \
             patch.object(mcp_service, "servers", {"ext-1": {"name": "x"}}):
            r = self._client().delete("/api/mcp/servers/ext-1")
        assert r.status_code == 200
        client_obj.close.assert_awaited_once()
        assert "ext-1" not in mcp_service.external_clients
        assert "ext-1" not in mcp_service.tools_cache
        assert "ext-1" not in mcp_service.servers

    def test_unregister_server_close_error(self):
        from core.mcp_service import mcp_service
        client_obj = MagicMock()
        client_obj.close = AsyncMock(side_effect=RuntimeError("close failed"))
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "external_clients", {"ext-1": client_obj}), \
             patch.object(mcp_service, "tools_cache", {}), \
             patch.object(mcp_service, "servers", {}):
            r = self._client().delete("/api/mcp/servers/ext-1")
        assert r.status_code == 200
        client_obj.close.assert_awaited_once()
        assert "ext-1" not in mcp_service.external_clients

    def test_unregister_missing_server(self):
        from core.mcp_service import mcp_service
        with patch("core.rbac_service.RBACService.check_permission", return_value=True), \
             patch.object(mcp_service, "external_clients", {}), \
             patch.object(mcp_service, "tools_cache", {}), \
             patch.object(mcp_service, "servers", {}):
            r = self._client().delete("/api/mcp/servers/ghost")
        assert r.status_code == 200

    def test_all_routes_require_auth_401(self):
        from api.mcp_client_routes import router
        client = _anon_client(router)
        assert client.get("/api/mcp/servers").status_code == 401
        assert client.post("/api/mcp/servers", json={"name": "x"}).status_code == 401
        assert client.delete("/api/mcp/servers/x").status_code == 401

    def test_forbidden_for_member_403(self):
        from api.mcp_client_routes import router
        client = _auth_client(router, user=Member())
        assert client.get("/api/mcp/servers").status_code == 403
        assert client.post("/api/mcp/servers", json={"name": "x"}).status_code == 403
        assert client.delete("/api/mcp/servers/x").status_code == 403
