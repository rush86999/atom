"""Coverage wave W76B — 6 never-covered / partially-covered modules to >=95% each.

Targets:
1. core/security/auth_rate_limit.py     (84% before — XFF trust branch + limiter 429 raises)
2. api/agent_control_routes.py          (90% before — bottlenecks + fleet health paths)
3. api/agent_status_endpoints.py        (100% before — regression re-run standalone)
4. api/custom_components.py             (55% before — all 10 endpoint bodies)
5. api/dependencies.py                  (47% before — get_current_user / get_tenant_id)
6. api/device_websocket.py              (38% before — manager + endpoint + command helpers)

Pattern (per W75B/W73A convention): FastAPI TestClient + dependency_overrides,
patches on real module names (no `backend.` prefix), zero DB / network / LLM
spend. The device WebSocket endpoint is not mounted on any app router, so it is
exercised by direct asyncio calls with a mocked WebSocket + mocked db session
(the branch-heavy message loop is uncontrollable through a real transport).
"""
import asyncio
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.agent_control_routes import router as agent_control_router
from api.agent_status_endpoints import router as agent_status_router
from api.custom_components import router as components_router
from core.admin_endpoints import get_super_admin
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.custom_components_service import ComponentSecurityError
from core.database import get_db
from core.models import DelegationChain, DeviceNode, User


# ============================================================================
# Shared user fixtures
# ============================================================================
@pytest.fixture
def admin_user():
    user = MagicMock()
    user.id = "admin-w76b"
    user.email = "admin@test.local"
    user.role = "super_admin"
    user.status = "active"
    user.workspace_id = "default"
    user.tenant_id = "tenant-1"
    return user


@pytest.fixture
def member_user():
    user = MagicMock()
    user.id = "member-w76b"
    user.email = "member@test.local"
    user.role = "member"
    user.status = "active"
    user.workspace_id = "default"
    user.tenant_id = "tenant-1"
    return user


def _override(original, value):
    async def _dep():
        return value
    return {original: _dep}


def _never_used_db():
    """get_db override for 401 tests: real auth rejects before touching the DB."""
    mock_db = Mock()

    def _gen():
        try:
            yield mock_db
        finally:
            pass

    return _gen()


# ============================================================================
# 1. core/security/auth_rate_limit.py
# ============================================================================
class TestAuthRateLimiterClientIp:
    _DEFAULT = object()

    def _request(self, client=_DEFAULT, headers=None):
        if client is self._DEFAULT:
            client = SimpleNamespace(host="203.0.113.9")
        return SimpleNamespace(client=client, headers=headers or {})

    def test_default_tcp_peer(self):
        from core.security.auth_rate_limit import AuthRateLimiter
        limiter = AuthRateLimiter()
        assert limiter._client_ip(self._request()) == "203.0.113.9"

    def test_no_client_falls_back_unknown(self):
        from core.security.auth_rate_limit import AuthRateLimiter
        limiter = AuthRateLimiter()
        assert limiter._client_ip(self._request(client=None)) == "unknown"

    def test_xff_trusted_last_entry(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "1")
        limiter = AuthRateLimiter()
        req = self._request(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
        assert limiter._client_ip(req) == "5.6.7.8"

    def test_xff_trusted_no_header_falls_back_peer(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "1")
        limiter = AuthRateLimiter()
        assert limiter._client_ip(self._request()) == "203.0.113.9"

    def test_xff_not_trusted_by_default(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.delenv("TRUST_X_FORWARDED_FOR", raising=False)
        limiter = AuthRateLimiter()
        req = self._request(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
        assert limiter._client_ip(req) == "203.0.113.9"


class TestAuthRateLimiterCheck:
    def _request(self, ip="203.0.113.9"):
        return SimpleNamespace(client=SimpleNamespace(host=ip), headers={})

    def test_allowed_under_limit_with_remaining(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
        limiter = AuthRateLimiter(limit=10, window_seconds=60)
        allowed, remaining = limiter.check(self._request())
        assert allowed is True
        assert remaining == 9

    def test_exact_limit_reached(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        assert limiter.check(self._request())[0] is True
        assert limiter.check(self._request())[0] is True
        allowed, remaining = limiter.check(self._request())
        assert allowed is False
        assert remaining == 0

    def test_limit_per_ip_isolated(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
        limiter = AuthRateLimiter(limit=1, window_seconds=60)
        assert limiter.check(self._request("10.0.0.1"))[0] is True
        assert limiter.check(self._request("10.0.0.1"))[0] is False
        assert limiter.check(self._request("10.0.0.2"))[0] is True

    def test_window_expiry_drops_old_timestamps(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
        now = 1_000_000.0
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        with patch("core.security.auth_rate_limit.time.time", return_value=now):
            limiter.check(self._request())
        with patch("core.security.auth_rate_limit.time.time", return_value=now + 61):
            allowed, remaining = limiter.check(self._request())
        assert allowed is True
        assert remaining == 1

    def test_testing_flag_bypasses(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.setenv("TESTING", "1")
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        allowed, remaining = limiter.check(self._request())
        assert allowed is True
        assert remaining == 2

    def test_bypass_rate_limit_flag_bypasses(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.setenv("BYPASS_RATE_LIMIT", "1")
        monkeypatch.delenv("TESTING", raising=False)
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        allowed, remaining = limiter.check(self._request())
        assert allowed is True
        assert remaining == 2

    def test_reset_ip_clears_counter(self, monkeypatch):
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
        limiter = AuthRateLimiter(limit=1, window_seconds=60)
        assert limiter.check(self._request())[0] is True
        assert limiter.check(self._request())[0] is False
        limiter.reset_ip("203.0.113.9")
        assert limiter.check(self._request())[0] is True

    def test_reset_ip_missing_no_error(self):
        from core.security.auth_rate_limit import AuthRateLimiter
        limiter = AuthRateLimiter()
        limiter.reset_ip("nobody-ip")

    def test_blocked_remembers_only_recent(self, monkeypatch):
        """After a block the stored hits are pruned to in-window entries."""
        from core.security.auth_rate_limit import AuthRateLimiter
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
        now = 1_000_000.0
        limiter = AuthRateLimiter(limit=1, window_seconds=60)
        with patch("core.security.auth_rate_limit.time.time", return_value=now):
            limiter.check(self._request())  # hit at t=0
        with patch("core.security.auth_rate_limit.time.time", return_value=now + 30):
            assert limiter.check(self._request())[0] is False  # in-window -> block
            assert len(limiter._hits["203.0.113.9"]) == 1
        with patch("core.security.auth_rate_limit.time.time", return_value=now + 120):
            assert limiter.check(self._request())[0] is True  # expired -> allowed


class TestAuthRateLimitDependencies:
    def _request(self, ip="198.51.100.7"):
        return SimpleNamespace(client=SimpleNamespace(host=ip), headers={})

    def _exhaust(self, limiter, ip):
        for _ in range(limiter.limit):
            limiter.check(self._request(ip))

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
        yield

    def test_login_allowed(self, monkeypatch):
        from core.security import auth_rate_limit
        ip = f"10.1.1.{uuid.uuid4().int % 200 + 1}"
        auth_rate_limit._login_limiter.reset_ip(ip)
        auth_rate_limit.login_rate_limit(self._request(ip))

    def test_login_exceeded_429(self):
        from core.security import auth_rate_limit
        ip = f"10.1.2.{uuid.uuid4().int % 200 + 1}"
        auth_rate_limit._login_limiter.reset_ip(ip)
        self._exhaust(auth_rate_limit._login_limiter, ip)
        with pytest.raises(HTTPException) as exc:
            auth_rate_limit.login_rate_limit(self._request(ip))
        assert exc.value.status_code == 429
        assert exc.value.headers == {"Retry-After": "60"}

    def test_register_allowed(self):
        from core.security import auth_rate_limit
        ip = f"10.1.3.{uuid.uuid4().int % 200 + 1}"
        auth_rate_limit._register_limiter.reset_ip(ip)
        auth_rate_limit.register_rate_limit(self._request(ip))

    def test_register_exceeded_429(self):
        from core.security import auth_rate_limit
        ip = f"10.1.4.{uuid.uuid4().int % 200 + 1}"
        auth_rate_limit._register_limiter.reset_ip(ip)
        self._exhaust(auth_rate_limit._register_limiter, ip)
        with pytest.raises(HTTPException) as exc:
            auth_rate_limit.register_rate_limit(self._request(ip))
        assert exc.value.status_code == 429
        assert exc.value.headers == {"Retry-After": "300"}

    def test_refresh_allowed(self):
        from core.security import auth_rate_limit
        ip = f"10.1.5.{uuid.uuid4().int % 200 + 1}"
        auth_rate_limit._refresh_limiter.reset_ip(ip)
        auth_rate_limit.refresh_rate_limit(self._request(ip))

    def test_refresh_exceeded_429(self):
        from core.security import auth_rate_limit
        ip = f"10.1.6.{uuid.uuid4().int % 200 + 1}"
        auth_rate_limit._refresh_limiter.reset_ip(ip)
        self._exhaust(auth_rate_limit._refresh_limiter, ip)
        with pytest.raises(HTTPException) as exc:
            auth_rate_limit.refresh_rate_limit(self._request(ip))
        assert exc.value.status_code == 429
        assert exc.value.headers == {"Retry-After": "60"}


# ============================================================================
# 2. api/agent_control_routes.py
# ============================================================================
@pytest.fixture
def daemon_manager():
    mock = MagicMock()
    mock.is_running = MagicMock(return_value=False)
    mock.get_pid = MagicMock(return_value=12345)
    mock.start_daemon = MagicMock(return_value=12345)
    mock.stop_daemon = MagicMock(return_value=None)
    mock.get_status = MagicMock(return_value={
        "running": True, "pid": 12345, "uptime_seconds": 3600,
        "memory_mb": 256.5, "cpu_percent": 5.2, "status": "running",
    })
    return mock


@pytest.fixture
def agent_control_client(admin_user):
    app = FastAPI()
    app.include_router(agent_control_router)
    app.dependency_overrides[get_super_admin] = _override(get_super_admin, admin_user)[get_super_admin]

    mock_db = Mock()

    def _gen():
        try:
            yield mock_db
        finally:
            pass

    app.dependency_overrides[get_db] = _gen
    client = TestClient(app)
    client._app = app
    client._mock_db = mock_db
    return client


class TestAgentControlStart:
    def test_start_success(self, agent_control_client, daemon_manager):
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.post("/api/agent/start", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True and data["pid"] == 12345
        assert data["status"] == "started"
        assert data["dashboard_url"] == "http://0.0.0.0:8000"
        daemon_manager.start_daemon.assert_called_once_with(
            port=8000, host="0.0.0.0", workers=1, host_mount=False, dev=False
        )

    def test_start_already_running_400(self, agent_control_client, daemon_manager):
        daemon_manager.is_running.return_value = True
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.post("/api/agent/start", json={})
        assert resp.status_code == 400
        assert "already running" in resp.json()["detail"]
        daemon_manager.start_daemon.assert_not_called()

    def test_start_runtime_error_500(self, agent_control_client, daemon_manager):
        daemon_manager.start_daemon.side_effect = RuntimeError("boom")
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.post("/api/agent/start", json={})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"

    def test_start_io_error_500(self, agent_control_client, daemon_manager):
        daemon_manager.start_daemon.side_effect = IOError("disk")
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.post("/api/agent/start", json={})
        assert resp.status_code == 500

    def test_start_requires_auth_401(self):
        app = FastAPI()
        app.include_router(agent_control_router)
        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).post("/api/agent/start", json={})
        assert resp.status_code == 401

    def test_start_requires_admin_403(self, member_user):
        app = FastAPI()
        app.include_router(agent_control_router)
        app.dependency_overrides[get_current_user] = _override(get_current_user, member_user)[get_current_user]
        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).post("/api/agent/start", json={})
        assert resp.status_code == 403


class TestAgentControlStop:
    def test_stop_success(self, agent_control_client, daemon_manager):
        daemon_manager.is_running.return_value = True
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.post("/api/agent/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True and data["status"] == "stopped"
        daemon_manager.stop_daemon.assert_called_once()

    def test_stop_not_running_400(self, agent_control_client, daemon_manager):
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.post("/api/agent/stop")
        assert resp.status_code == 400
        assert "not running" in resp.json()["detail"]

    def test_stop_generic_exception_500(self, agent_control_client, daemon_manager):
        daemon_manager.is_running.return_value = True
        daemon_manager.stop_daemon.side_effect = RuntimeError("boom")
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.post("/api/agent/stop")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestAgentControlRestart:
    def test_restart_was_running(self, agent_control_client, daemon_manager):
        daemon_manager.is_running.return_value = True
        with patch("api.agent_control_routes.DaemonManager", daemon_manager), \
             patch("time.sleep", return_value=None):
            resp = agent_control_client.post("/api/agent/restart", json={"port": 9000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True and data["status"] == "restarted"
        assert data["was_running"] is True
        assert data["dashboard_url"] == "http://0.0.0.0:9000"
        daemon_manager.stop_daemon.assert_called_once()
        daemon_manager.start_daemon.assert_called_once()

    def test_restart_was_not_running(self, agent_control_client, daemon_manager):
        with patch("api.agent_control_routes.DaemonManager", daemon_manager), \
             patch("time.sleep", return_value=None):
            resp = agent_control_client.post("/api/agent/restart", json={})
        assert resp.status_code == 200
        assert resp.json()["was_running"] is False
        daemon_manager.stop_daemon.assert_not_called()

    def test_restart_exception_500(self, agent_control_client, daemon_manager):
        daemon_manager.start_daemon.side_effect = RuntimeError("boom")
        with patch("api.agent_control_routes.DaemonManager", daemon_manager), \
             patch("time.sleep", return_value=None):
            resp = agent_control_client.post("/api/agent/restart", json={})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestAgentControlStatus:
    def test_status_success(self, agent_control_client, daemon_manager):
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.get("/api/agent/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"]["running"] is True
        assert data["status"]["pid"] == 12345

    def test_status_exception_500(self, agent_control_client, daemon_manager):
        daemon_manager.get_status.side_effect = RuntimeError("boom")
        with patch("api.agent_control_routes.DaemonManager", daemon_manager):
            resp = agent_control_client.get("/api/agent/status")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestAgentControlExecute:
    def test_execute_placeholder(self, agent_control_client):
        resp = agent_control_client.post("/api/agent/execute", json={"command": "agent.chat('hi')"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "not yet implemented" in data["result"]
        assert "note" in data

    def test_execute_invalid_timeout_422(self, agent_control_client):
        resp = agent_control_client.post("/api/agent/execute", json={"command": "x", "timeout": 0})
        assert resp.status_code == 422

    def test_execute_missing_command_422(self, agent_control_client):
        resp = agent_control_client.post("/api/agent/execute", json={})
        assert resp.status_code == 422


class TestAgentControlBottlenecks:
    URL = "/api/agent/chain-1/bottlenecks"

    def test_success_with_mixed_severities(self, agent_control_client):
        chain = MagicMock()
        agent_control_client._mock_db.query.return_value.filter.return_value.first.return_value = chain
        service = Mock()
        service.analyze_bottlenecks.return_value = [
            {"severity": "critical", "issue": "depth"},
            {"severity": "warning", "issue": "cost"},
            {"severity": "info", "issue": "latency"},
        ]
        with patch("analytics.fleet_optimization_service.FleetOptimizationService", return_value=service):
            resp = agent_control_client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["chain_id"] == "chain-1"
        assert body["summary"] == {"total_issues": 3, "critical_issues": 1, "warnings": 1}
        service.analyze_bottlenecks.assert_called_once_with("chain-1")

    def test_success_empty_report(self, agent_control_client):
        chain = MagicMock()
        agent_control_client._mock_db.query.return_value.filter.return_value.first.return_value = chain
        service = Mock()
        service.analyze_bottlenecks.return_value = []
        with patch("analytics.fleet_optimization_service.FleetOptimizationService", return_value=service):
            resp = agent_control_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["summary"] == {"total_issues": 0, "critical_issues": 0, "warnings": 0}

    def test_chain_not_found_404(self, agent_control_client):
        agent_control_client._mock_db.query.return_value.filter.return_value.first.return_value = None
        resp = agent_control_client.get(self.URL)
        assert resp.status_code == 404
        assert "Delegation chain not found" in resp.json()["detail"]


class TestAgentControlFleetHealth:
    URL = "/api/agent/fleet/health"

    def test_success_with_tenant(self, agent_control_client):
        service = Mock()
        service.get_fleet_health_summary.return_value = {"healthy": 3, "degraded": 1}
        with patch("analytics.fleet_optimization_service.FleetOptimizationService", return_value=service):
            resp = agent_control_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json() == {"healthy": 3, "degraded": 1}
        service.get_fleet_health_summary.assert_called_once_with("tenant-1")

    def test_success_no_tenant(self, agent_control_client, admin_user):
        admin_user.tenant_id = None
        service = Mock()
        service.get_fleet_health_summary.return_value = {"healthy": 0}
        with patch("analytics.fleet_optimization_service.FleetOptimizationService", return_value=service):
            resp = agent_control_client.get(self.URL)
        assert resp.status_code == 200
        service.get_fleet_health_summary.assert_called_once_with(None)


# ============================================================================
# 3. api/agent_status_endpoints.py
# ============================================================================
@pytest.fixture
def agent_status_client(member_user, tmp_path):
    import api.agent_status_endpoints as mod
    app = FastAPI()
    app.include_router(agent_status_router)
    app.dependency_overrides[get_current_user] = _override(get_current_user, member_user)[get_current_user]
    client = TestClient(app)
    client._app = app
    status_file = tmp_path / "agent_status.json"
    with patch.object(mod, "AGENT_STATUS_FILE", status_file):
        client._status_file = status_file
        yield client


class TestAgentStatusLoadSave:
    def test_load_missing_file(self, agent_status_client):
        import api.agent_status_endpoints as mod
        assert mod.load_agent_status() == {"agents": {}, "tasks": {}}

    def test_load_valid_json(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({"agents": {"a": {}}, "tasks": {}}))
        import api.agent_status_endpoints as mod
        data = mod.load_agent_status()
        assert data == {"agents": {"a": {}}, "tasks": {}}

    def test_load_corrupt_json(self, agent_status_client):
        agent_status_client._status_file.write_text("{not json!!")
        import api.agent_status_endpoints as mod
        assert mod.load_agent_status() == {"agents": {}, "tasks": {}}

    def test_save_writes_file(self, agent_status_client):
        import api.agent_status_endpoints as mod
        mod.save_agent_status({"agents": {}, "tasks": {"t1": {}}})
        assert json.loads(agent_status_client._status_file.read_text())["tasks"]["t1"] == {}

    def test_save_error_logged(self, agent_status_client, caplog):
        import api.agent_status_endpoints as mod
        with patch("builtins.open", side_effect=OSError("disk full")), \
             caplog.at_level("ERROR", logger="api.agent_status_endpoints"):
            mod.save_agent_status({"agents": {}})
        assert "Error saving agent status" in caplog.text


class TestAgentStatusGet:
    def test_get_task_found(self, agent_status_client):
        task = {"task_id": "t1", "agent_id": "a1", "status": "running", "progress": 0.5}
        agent_status_client._status_file.write_text(json.dumps({"tasks": {"t1": task}}))
        resp = agent_status_client.get("/api/agent-status/agent/status/t1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "t1" and body["status"] == "running"
        assert body["progress"] == 0.5

    def test_get_task_not_found_default(self, agent_status_client):
        resp = agent_status_client.get("/api/agent-status/agent/status/nope")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "nope"
        assert body["agent_id"] == "unknown"
        assert body["status"] == "not_found"
        assert body["error_message"] == "Task not found"

    def test_get_all_tasks(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "tasks": {"t1": {"task_id": "t1", "agent_id": "a1", "status": "completed"},
                      "t2": {"task_id": "t2", "agent_id": "a1", "status": "failed"}}
        }))
        resp = agent_status_client.get("/api/agent-status/agent/status")
        assert resp.status_code == 200
        assert {t["task_id"] for t in resp.json()} == {"t1", "t2"}

    def test_get_all_tasks_empty(self, agent_status_client):
        resp = agent_status_client.get("/api/agent-status/agent/status")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_auth_401(self):
        app = FastAPI()
        app.include_router(agent_status_router)
        resp = TestClient(app).get("/api/agent-status/agent/status/x")
        assert resp.status_code == 401


class TestAgentStatusAgents:
    def test_get_all_agents(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "agents": {"a1": {"agent_id": "a1", "name": "N", "type": "general", "status": "idle"}}
        }))
        resp = agent_status_client.get("/api/agent-status/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["agent_id"] == "a1" and body[0]["name"] == "N"

    def test_get_all_agents_empty(self, agent_status_client):
        resp = agent_status_client.get("/api/agent-status/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_agent_existing(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "agents": {"a1": {"agent_id": "a1", "name": "Known", "type": "special",
                              "status": "busy", "capabilities": ["x"]}}
        }))
        resp = agent_status_client.get("/api/agent-status/agents/a1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == "a1" and body["name"] == "Known"

    def test_get_agent_creates_default_and_saves(self, agent_status_client):
        resp = agent_status_client.get("/api/agent-status/agents/new-agent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == "new-agent"
        assert body["status"] == "idle"
        assert "text_processing" in body["capabilities"]
        saved = json.loads(agent_status_client._status_file.read_text())
        assert "new-agent" in saved["agents"]

    def test_heartbeat_creates_and_updates(self, agent_status_client):
        resp = agent_status_client.post(
            "/api/agent-status/agent/a9/heartbeat",
            json={"name": "Heartbeat Agent", "type": "mobile", "status": "busy",
                  "current_task": "t1", "capabilities": ["camera"], "health_score": 0.9},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        saved = json.loads(agent_status_client._status_file.read_text())
        agent = saved["agents"]["a9"]
        assert agent["name"] == "Heartbeat Agent"
        assert agent["status"] == "busy"
        assert agent["health_score"] == 0.9

    def test_heartbeat_defaults(self, agent_status_client):
        resp = agent_status_client.post("/api/agent-status/agent/a10/heartbeat", json={})
        assert resp.status_code == 200
        saved = json.loads(agent_status_client._status_file.read_text())
        agent = saved["agents"]["a10"]
        assert agent["name"] == "Agent a10"
        assert agent["type"] == "general"
        assert agent["status"] == "idle"
        assert agent["health_score"] == 1.0


class TestAgentStatusTasks:
    def test_update_task_status_running_sets_started_at(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "tasks": {"t1": {"task_id": "t1", "agent_id": "a1", "status": "pending"}}
        }))
        resp = agent_status_client.post(
            "/api/agent-status/agent/task/t1/update", json={"status": "running", "progress": 0.25}
        )
        assert resp.status_code == 200
        saved = json.loads(agent_status_client._status_file.read_text())
        task = saved["tasks"]["t1"]
        assert task["status"] == "running"
        assert task["started_at"] is not None
        assert task["progress"] == 0.25

    def test_update_task_status_completed_sets_completed_at(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "tasks": {"t1": {"task_id": "t1", "agent_id": "a1", "status": "running",
                             "started_at": "2026-01-01T00:00:00"}}
        }))
        resp = agent_status_client.post(
            "/api/agent-status/agent/task/t1/update",
            json={"status": "completed", "error_message": None, "result": {"ok": True}},
        )
        assert resp.status_code == 200
        saved = json.loads(agent_status_client._status_file.read_text())
        task = saved["tasks"]["t1"]
        assert task["status"] == "completed"
        assert task["completed_at"] is not None
        assert task["result"] == {"ok": True}

    def test_update_task_status_not_found_404(self, agent_status_client):
        resp = agent_status_client.post(
            "/api/agent-status/agent/task/ghost/update", json={"status": "running"}
        )
        assert resp.status_code == 404

    def test_update_task_no_optional_fields(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "tasks": {"t1": {"task_id": "t1", "agent_id": "a1", "status": "pending"}}
        }))
        resp = agent_status_client.post(
            "/api/agent-status/agent/task/t1/update", json={"progress": 1.0}
        )
        assert resp.status_code == 200
        saved = json.loads(agent_status_client._status_file.read_text())
        assert saved["tasks"]["t1"]["status"] == "pending"
        assert saved["tasks"]["t1"]["progress"] == 1.0

    def test_create_task_running_sets_started_at(self, agent_status_client):
        resp = agent_status_client.post(
            "/api/agent-status/agent/task",
            json={"task_id": "t-new", "agent_id": "a1", "status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["task_id"] == "t-new"
        saved = json.loads(agent_status_client._status_file.read_text())
        assert saved["tasks"]["t-new"]["started_at"] is not None

    def test_create_task_pending_keeps_none_dates(self, agent_status_client):
        resp = agent_status_client.post(
            "/api/agent-status/agent/task",
            json={"task_id": "t-pend", "agent_id": "a1", "status": "pending"},
        )
        assert resp.status_code == 200
        saved = json.loads(agent_status_client._status_file.read_text())
        assert saved["tasks"]["t-pend"]["started_at"] is None
        assert saved["tasks"]["t-pend"]["completed_at"] is None

    def test_delete_task_success(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "tasks": {"t1": {"task_id": "t1", "agent_id": "a1", "status": "pending"}}
        }))
        resp = agent_status_client.delete("/api/agent-status/agent/task/t1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Task deleted successfully"
        assert "t1" not in json.loads(agent_status_client._status_file.read_text())["tasks"]

    def test_delete_task_not_found_404(self, agent_status_client):
        resp = agent_status_client.delete("/api/agent-status/agent/task/ghost")
        assert resp.status_code == 404

    def test_metrics_with_data(self, agent_status_client):
        agent_status_client._status_file.write_text(json.dumps({
            "agents": {"a1": {"status": "busy"}, "a2": {"status": "running"},
                       "a3": {"status": "idle"}},
            "tasks": {"t1": {"status": "completed"}, "t2": {"status": "completed"},
                      "t3": {"status": "failed"}, "t4": {"status": "pending"}},
        }))
        resp = agent_status_client.get("/api/agent-status/agent/metrics")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agents"] == {"total": 3, "active": 2, "idle": 1}
        assert data["tasks"] == {"total": 4, "completed": 2, "failed": 1, "pending": 1}
        assert data["success_rate"] == 0.5

    def test_metrics_empty(self, agent_status_client):
        resp = agent_status_client.get("/api/agent-status/agent/metrics")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agents"]["total"] == 0
        assert data["tasks"]["total"] == 0
        assert data["success_rate"] == 0.0


# ============================================================================
# 4. api/custom_components.py
# ============================================================================
@pytest.fixture
def components_client(member_user):
    app = FastAPI()
    app.include_router(components_router)
    app.dependency_overrides[get_current_user] = _override(get_current_user, member_user)[get_current_user]

    mock_db = Mock()

    def _gen():
        try:
            yield mock_db
        finally:
            pass

    app.dependency_overrides[get_db] = _gen
    client = TestClient(app)
    client._app = app
    return client


class TestCreateComponent:
    URL = "/api/components/create"

    def _payload(self):
        return {"name": "Chart", "html_content": "<div></div>", "category": "charts",
                "props_schema": {"type": "object"}, "default_props": {"title": "T"},
                "dependencies": ["https://cdn.example.com/lib.js"], "is_public": True,
                "agent_id": "ag-1", "css_content": ".c{}", "js_content": "console.log(1)",
                "description": "desc"}

    def test_success(self, components_client):
        service = Mock()
        service.create_component.return_value = {"id": "c1", "slug": "chart", "version": 1}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.post(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == "c1"
        service.create_component.assert_called_once()
        assert service.create_component.call_args.kwargs["user_id"] == "u1"

    def test_service_error_422(self, components_client):
        service = Mock()
        service.create_component.return_value = {"error": "name taken"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.post(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 422

    def test_security_error_403(self, components_client):
        service = Mock()
        service.create_component.side_effect = ComponentSecurityError("bad script", "Chart")
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.post(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 403

    def test_missing_user_id_422(self, components_client):
        resp = components_client.post(self.URL, json=self._payload())
        assert resp.status_code == 422

    def test_missing_name_422(self, components_client):
        resp = components_client.post(self.URL, params={"user_id": "u1"},
                                      json={"html_content": "<div></div>"})
        assert resp.status_code == 422


class TestListComponents:
    URL = "/api/components"

    def test_success_with_filters(self, components_client):
        service = Mock()
        service.list_components.return_value = {"components": [{"id": "c1"}, {"id": "c2"}]}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get(
                self.URL, params={"user_id": "u1", "category": "charts", "is_public": True, "limit": 25}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert "Retrieved 2 components" in body["message"]
        service.list_components.assert_called_once_with(
            user_id="u1", category="charts", is_public=True, limit=25
        )

    def test_success_empty(self, components_client):
        service = Mock()
        service.list_components.return_value = {"components": []}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_limit_validation_422(self, components_client):
        resp = components_client.get(self.URL, params={"limit": 500})
        assert resp.status_code == 422


class TestGetComponent:
    def test_by_id_success(self, components_client):
        service = Mock()
        service.get_component.return_value = {"id": "c1", "html_content": "<div/>"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/c1", params={"user_id": "u1"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "c1"
        service.get_component.assert_called_once_with(component_id="c1", user_id="u1")

    def test_by_id_not_found_404(self, components_client):
        service = Mock()
        service.get_component.return_value = {"error": "missing"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/nope", params={"user_id": "u1"})
        assert resp.status_code == 404

    def test_by_slug_success(self, components_client):
        service = Mock()
        service.get_component.return_value = {"id": "c1", "slug": "my-chart"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/by-slug/my-chart")
        assert resp.status_code == 200
        service.get_component.assert_called_once_with(slug="my-chart", user_id=None)

    def test_by_slug_not_found_404(self, components_client):
        service = Mock()
        service.get_component.return_value = {"error": "missing"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/by-slug/ghost")
        assert resp.status_code == 404


class TestUpdateComponent:
    URL = "/api/components/c1"

    def _payload(self):
        return {"name": "New", "html_content": "<p/>", "change_description": "rename",
                "agent_id": "ag-2", "is_public": False, "dependencies": ["https://cdn.example.com/b.js"]}

    def test_success(self, components_client):
        service = Mock()
        service.update_component.return_value = {"id": "c1", "version": 2}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.put(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["version"] == 2
        assert service.update_component.call_args.kwargs["change_description"] == "rename"

    def test_service_error_422(self, components_client):
        service = Mock()
        service.update_component.return_value = {"error": "no permission"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.put(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 422

    def test_security_error_403(self, components_client):
        service = Mock()
        service.update_component.side_effect = ComponentSecurityError("bad js")
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.put(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 403

    def test_missing_user_id_422(self, components_client):
        resp = components_client.put(self.URL, json=self._payload())
        assert resp.status_code == 422

    def test_empty_body_ok(self, components_client):
        service = Mock()
        service.update_component.return_value = {"id": "c1", "version": 3}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.put(self.URL, params={"user_id": "u1"}, json={})
        assert resp.status_code == 200


class TestDeleteComponent:
    URL = "/api/components/c1"

    def test_success(self, components_client):
        service = Mock()
        service.delete_component.return_value = {"success": True, "id": "c1"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.delete(self.URL, params={"user_id": "u1"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_error_422(self, components_client):
        service = Mock()
        service.delete_component.return_value = {"error": "not owner"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.delete(self.URL, params={"user_id": "u1"})
        assert resp.status_code == 422

    def test_missing_user_id_422(self, components_client):
        resp = components_client.delete(self.URL)
        assert resp.status_code == 422


class TestComponentVersions:
    def test_success(self, components_client):
        service = Mock()
        service.get_component_versions.return_value = {"versions": [{"version": 1}]}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/c1/versions", params={"user_id": "u1"})
        assert resp.status_code == 200
        assert resp.json()["versions"][0]["version"] == 1

    def test_error_422(self, components_client):
        service = Mock()
        service.get_component_versions.return_value = {"error": "denied"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/c1/versions", params={"user_id": "u1"})
        assert resp.status_code == 422

    def test_missing_user_id_422(self, components_client):
        resp = components_client.get("/api/components/c1/versions")
        assert resp.status_code == 422


class TestComponentRollback:
    def test_success(self, components_client):
        service = Mock()
        service.rollback_component.return_value = {"id": "c1", "version": 1, "rolled_back": True}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.post(
                "/api/components/c1/rollback", params={"user_id": "u1"}, json={"target_version": 1}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["rolled_back"] is True
        service.rollback_component.assert_called_once_with(component_id="c1", target_version=1, user_id="u1")

    def test_error_422(self, components_client):
        service = Mock()
        service.rollback_component.return_value = {"error": "no such version"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.post(
                "/api/components/c1/rollback", params={"user_id": "u1"}, json={"target_version": 9}
            )
        assert resp.status_code == 422

    def test_missing_target_version_422(self, components_client):
        resp = components_client.post("/api/components/c1/rollback", params={"user_id": "u1"}, json={})
        assert resp.status_code == 422


class TestRecordComponentUsage:
    URL = "/api/components/c1/record-usage"

    def _payload(self):
        return {"canvas_id": "cv-1", "session_id": "s-1", "agent_id": "ag-1",
                "props_passed": {"x": 1}, "rendering_time_ms": 42, "error_message": None,
                "governance_check_passed": True, "agent_maturity_level": "SUPERVISED"}

    def test_success(self, components_client):
        service = Mock()
        service.record_component_usage.return_value = {"usage_id": "u-1"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.post(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["usage_id"] == "u-1"
        assert service.record_component_usage.call_args.kwargs["canvas_id"] == "cv-1"
        assert service.record_component_usage.call_args.kwargs["rendering_time_ms"] == 42

    def test_error_422(self, components_client):
        service = Mock()
        service.record_component_usage.return_value = {"error": "component not found"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.post(self.URL, params={"user_id": "u1"}, json=self._payload())
        assert resp.status_code == 422

    def test_missing_canvas_id_422(self, components_client):
        resp = components_client.post(self.URL, params={"user_id": "u1"}, json={})
        assert resp.status_code == 422


class TestGetComponentStats:
    def test_success(self, components_client):
        service = Mock()
        service.get_component_usage_stats.return_value = {"total_renders": 10, "success_rate": 0.9}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/c1/stats", params={"user_id": "u1"})
        assert resp.status_code == 200
        assert resp.json()["total_renders"] == 10

    def test_error_422(self, components_client):
        service = Mock()
        service.get_component_usage_stats.return_value = {"error": "denied"}
        with patch("api.custom_components.CustomComponentsService", return_value=service):
            resp = components_client.get("/api/components/c1/stats", params={"user_id": "u1"})
        assert resp.status_code == 422

    def test_requires_auth_401(self):
        app = FastAPI()
        app.include_router(components_router)
        resp = TestClient(app).get("/api/components/c1/stats", params={"user_id": "u1"})
        assert resp.status_code == 401


# ============================================================================
# 5. api/dependencies.py
# ============================================================================
class TestApiDependencies:
    async def _call_get_current_user(self, header_value=None):
        from api.dependencies import get_current_user
        request = MagicMock()
        request.headers.get.return_value = header_value
        return await get_current_user(request=request, db="db-stub")

    def test_get_current_user_bearer_token(self):
        core_user = MagicMock()
        with patch("api.dependencies.get_current_user_core", new=AsyncMock(return_value=core_user)) as m:
            user = asyncio.run(self._call_get_current_user("Bearer abc.def.ghi"))
        assert user is core_user
        m.assert_awaited_once_with(ANY, token="abc.def.ghi", db="db-stub")

    def test_get_current_user_non_bearer_header(self):
        with patch("api.dependencies.get_current_user_core", new=AsyncMock(return_value=object())) as m:
            asyncio.run(self._call_get_current_user("Token xyz"))
        m.assert_awaited_once()
        assert m.await_args.kwargs["token"] is None

    def test_get_current_user_no_header(self):
        with patch("api.dependencies.get_current_user_core", new=AsyncMock(return_value=object())) as m:
            asyncio.run(self._call_get_current_user(None))
        m.assert_awaited_once()
        assert m.await_args.kwargs["token"] is None

    def test_get_tenant_id_present(self):
        from api.dependencies import get_tenant_id
        user = MagicMock()
        user.tenant_id = "tenant-42"
        result = asyncio.run(get_tenant_id(Mock(), user))
        assert result == "tenant-42"

    def test_get_tenant_id_none_raises_400(self):
        from api.dependencies import get_tenant_id
        user = MagicMock()
        user.tenant_id = None
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_tenant_id(Mock(), user))
        assert exc.value.status_code == 400
        assert "does not belong to a tenant" in exc.value.detail

    def test_end_to_end_via_testclient_401(self):
        from api.dependencies import get_current_user
        from api.dependencies import get_tenant_id

        app = FastAPI()

        @app.get("/dep-test")
        async def _route(tenant: str = Depends(get_tenant_id)):
            return {"tenant": tenant}

        app.dependency_overrides[get_db] = _never_used_db
        resp = TestClient(app).get("/dep-test")
        assert resp.status_code == 401

    def test_end_to_end_with_valid_user(self):
        from api.dependencies import get_tenant_id
        from api.dependencies import get_current_user as api_get_current_user

        app = FastAPI()

        @app.get("/dep-test")
        async def _route(tenant: str = Depends(get_tenant_id)):
            return {"tenant": tenant}

        user = MagicMock()
        user.tenant_id = "t-7"

        async def _override_user():
            return user

        app.dependency_overrides[api_get_current_user] = _override_user
        resp = TestClient(app).get("/dep-test")
        assert resp.status_code == 200
        assert resp.json() == {"tenant": "t-7"}

    def test_tenant_dependency_400_envelope(self):
        from api.dependencies import get_tenant_id
        from api.dependencies import get_current_user as api_get_current_user

        app = FastAPI()

        @app.get("/dep-test")
        async def _route(tenant: str = Depends(get_tenant_id)):
            return {"tenant": tenant}

        user = MagicMock()
        user.tenant_id = None

        async def _override_user():
            return user

        app.dependency_overrides[api_get_current_user] = _override_user
        resp = TestClient(app).get("/dep-test")
        assert resp.status_code == 400


# ============================================================================
# 6. api/device_websocket.py
# ============================================================================
def _make_ws():
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_db(user=None, device=None):
    db = MagicMock()
    user_q = MagicMock()
    user_q.filter.return_value.first.return_value = user
    device_q = MagicMock()
    device_q.filter.return_value.first.return_value = device

    def _query(model):
        if model is User:
            return user_q
        return device_q

    db.query.side_effect = _query
    return db


def _db_context(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx


class TestDeviceConnectionManager:
    def test_init(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        assert manager.active_connections == {}
        assert manager.device_info == {}
        assert manager.user_devices == {}
        assert manager.pending_commands == {}

    @pytest.mark.asyncio
    async def test_connect_new_user(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {"capabilities": ["camera"], "user_id": "u1"})
        assert manager.active_connections["d1"] is ws
        assert manager.user_devices["u1"] == {"d1"}
        assert manager.pending_commands["d1"] == []
        ws.accept.assert_awaited_once()
        ws.send_json.assert_awaited_once()
        sent = ws.send_json.await_args.args[0]
        assert sent["type"] == "connected"
        assert sent["device_node_id"] == "d1"

    @pytest.mark.asyncio
    async def test_connect_existing_user_and_pending(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws1, ws2 = _make_ws(), _make_ws()
        await manager.connect(ws1, "d1", "u1", {})
        manager.pending_commands["d1"] = [{"cmd": 1}]
        await manager.connect(ws2, "d2", "u1", {})
        assert manager.user_devices["u1"] == {"d1", "d2"}
        assert manager.pending_commands["d2"] == []

    def test_disconnect_removes_all(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        manager.active_connections["d1"] = _make_ws()
        manager.device_info["d1"] = {"user_id": "u1"}
        manager.pending_commands["d1"] = []
        manager.user_devices["u1"] = {"d1", "d2"}
        manager.disconnect("d1", "u1")
        assert "d1" not in manager.active_connections
        assert "d1" not in manager.device_info
        assert "d1" not in manager.pending_commands
        assert manager.user_devices["u1"] == {"d2"}

    def test_disconnect_unknown_no_error(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        manager.disconnect("ghost", "u1")

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        with pytest.raises(ValueError, match="not connected"):
            await manager.send_command("d1", "camera_snap", {})

    @pytest.mark.asyncio
    async def test_send_command_success_generates_id(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {})
        sent_command = {}

        async def _receive(timeout=None):
            return {"command_id": sent_command["command_id"], "data": "shot.jpg"}

        ws.receive_json.side_effect = _receive

        def _send(msg):
            sent_command.update(msg)

        ws.send_json.side_effect = _send
        response = await manager.send_command("d1", "camera_snap", {"mode": "hi"})
        assert response["data"] == "shot.jpg"
        assert sent_command["type"] == "command"
        assert sent_command["command"] == "camera_snap"

    @pytest.mark.asyncio
    async def test_send_command_success_with_provided_id(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {})
        ws.receive_json.return_value = {"command_id": "cid-1", "ok": True}
        response = await manager.send_command("d1", "loc", {}, command_id="cid-1")
        assert response["ok"] is True

    @pytest.mark.asyncio
    async def test_send_command_mismatch_raises(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {})
        ws.receive_json.return_value = {"command_id": "different", "ok": True}
        with pytest.raises(ValueError, match="Command ID mismatch"):
            await manager.send_command("d1", "loc", {}, command_id="cid-1")

    @pytest.mark.asyncio
    async def test_send_command_websocket_disconnect(self):
        from api.device_websocket import DeviceConnectionManager, WebSocketDisconnect
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {"user_id": "u1"})
        ws.receive_json.side_effect = WebSocketDisconnect
        with pytest.raises(ValueError, match="disconnected during command"):
            await manager.send_command("d1", "camera_snap", {})
        assert "d1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_command_generic_exception_reraises(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {})
        ws.receive_json.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await manager.send_command("d1", "camera_snap", {})

    @pytest.mark.asyncio
    async def test_broadcast_unknown_user_noop(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        await manager.broadcast_to_user_devices("ghost", {"msg": 1})

    @pytest.mark.asyncio
    async def test_broadcast_success(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {})
        await manager.broadcast_to_user_devices("u1", {"msg": 1})
        ws.send_json.assert_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_send_failure_logged(self, caplog):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "d1", "u1", {})
        ws.send_json.side_effect = RuntimeError("send failed")
        with caplog.at_level("ERROR", logger="api.device_websocket"):
            await manager.broadcast_to_user_devices("u1", {"msg": 1})
        assert "Error broadcasting" in caplog.text

    def test_is_device_connected(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        assert manager.is_device_connected("d1") is False
        manager.active_connections["d1"] = _make_ws()
        assert manager.is_device_connected("d1") is True

    def test_get_device_info(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        assert manager.get_device_info("d1") is None
        manager.device_info["d1"] = {"name": "phone"}
        assert manager.get_device_info("d1") == {"name": "phone"}

    def test_get_user_devices(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        assert manager.get_user_devices("u1") == []
        manager.user_devices["u1"] = {"d1", "d2"}
        assert set(manager.get_user_devices("u1")) == {"d1", "d2"}

    def test_get_all_connected_devices(self):
        from api.device_websocket import DeviceConnectionManager
        manager = DeviceConnectionManager()
        manager.device_info["d1"] = {"name": "phone"}
        result = manager.get_all_connected_devices()
        assert result == [{"device_node_id": "d1", "name": "phone"}]


class TestDeviceWebsocketEndpoint:
    REGISTER = {"type": "register", "device_node_id": "dev-1",
                "device_info": {"name": "Phone", "capabilities": ["camera"],
                                "platform": "ios", "platform_version": "17",
                                "hardware_info": {"ram": 4}, "node_type": "mobile_ios",
                                "architecture": "arm64",
                                "capabilities_detailed": {"camera": {}}}}

    def _run(self, ws, db, payload=None, register_msg=None):
        import api.device_websocket as mod
        with patch.object(mod, "decode_token", return_value=payload), \
             patch.object(mod, "get_db_session", _db_context(db)):
            return asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))

    def test_disabled_flag_closes_1003(self):
        import api.device_websocket as mod
        ws = _make_ws()
        with patch.object(mod, "DEVICE_WEBSOCKET_ENABLED", False):
            asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))
        ws.close.assert_awaited_once_with(code=1003, reason="Device WebSocket disabled")

    def test_invalid_token_no_sub(self):
        ws = _make_ws()
        db = _make_db(user=MagicMock(id="u1"))
        self._run(ws, db, payload={"foo": "bar"})
        ws.close.assert_awaited_once_with(code=1008, reason="Invalid token")
        ws.accept.assert_not_awaited()

    def test_user_not_found(self):
        ws = _make_ws()
        db = _make_db(user=None)
        self._run(ws, db, payload={"sub": "ghost"})
        ws.close.assert_awaited_once_with(code=1008, reason="User not found")

    def test_registration_timeout(self):
        ws = _make_ws()
        db = _make_db(user=MagicMock(id="u1"))
        ws.receive_json.side_effect = asyncio.TimeoutError
        self._run(ws, db, payload={"sub": "u1"})
        ws.close.assert_awaited_once_with(code=1008, reason="Registration timeout")

    def test_non_register_message(self):
        ws = _make_ws()
        db = _make_db(user=MagicMock(id="u1"))
        ws.receive_json.return_value = {"type": "heartbeat"}
        self._run(ws, db, payload={"sub": "u1"})
        ws.close.assert_awaited_once_with(code=1002, reason="Expected register message")

    def test_missing_device_node_id(self):
        ws = _make_ws()
        db = _make_db(user=MagicMock(id="u1"))
        ws.receive_json.return_value = {"type": "register", "device_info": {}}
        self._run(ws, db, payload={"sub": "u1"})
        ws.close.assert_awaited_once_with(code=1002, reason="device_node_id required")

    def test_full_flow_existing_device(self):
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        ws = _make_ws()
        device = MagicMock()
        device.status = "offline"
        db = _make_db(user=MagicMock(id="u1"), device=device)
        t0 = datetime(2026, 1, 1, 0, 0, 0)
        t1 = t0 + timedelta(seconds=100)

        msgs = [dict(self.REGISTER),
                {"type": "result", "command_id": "c1"},
                {"type": "heartbeat"},
                {"type": "error", "error": "boom"},
                {"type": "weird"},
                asyncio.TimeoutError,
                asyncio.TimeoutError]
        ws.receive_json.side_effect = msgs
        fake_values = [t0] * 8 + [t1]
        fake_now = {"i": 0}

        class _FakeDT:
            @classmethod
            def now(cls):
                v = fake_values[min(fake_now["i"], len(fake_values) - 1)]
                fake_now["i"] += 1
                return v

        with patch.object(mod, "decode_token", return_value={"sub": "u1"}), \
             patch.object(mod, "get_db_session", _db_context(db)), \
             patch.object(mod, "get_device_connection_manager", return_value=manager), \
             patch.object(mod, "datetime", _FakeDT), \
             patch.object(mod, "DEVICE_HEARTBEAT_INTERVAL", 0.01), \
             patch.object(mod, "DEVICE_CONNECTION_TIMEOUT", 50):
            asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))

        assert device.status == "offline"  # cleanup ran
        assert device.last_seen is not None  # update branch touched
        sent_types = [c.args[0]["type"] for c in ws.send_json.await_args_list]
        assert "connected" in sent_types
        assert "registered" in sent_types
        assert "heartbeat_ack" in sent_types
        assert "heartbeat_probe" in sent_types
        assert "dev-1" not in manager.active_connections

    def test_full_flow_new_device_created(self):
        import api.device_websocket as mod
        from api.device_websocket import WebSocketDisconnect
        manager = mod.DeviceConnectionManager()
        ws = _make_ws()
        db = _make_db(user=MagicMock(id="u1"), device=None)
        ws.receive_json.side_effect = [dict(self.REGISTER), WebSocketDisconnect()]

        with patch.object(mod, "decode_token", return_value={"sub": "u1"}), \
             patch.object(mod, "get_db_session", _db_context(db)), \
             patch.object(mod, "get_device_connection_manager", return_value=manager):
            asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))

        assert db.add.called  # new DeviceNode was added
        created = db.add.call_args.args[0]
        assert created.device_id == "dev-1"
        assert created.status == "online"
        assert created.platform == "ios"
        assert created.capabilities == ["camera"]

    def test_heartbeat_probe_send_failure_breaks(self):
        """Probe branch: send_json raising while sending heartbeat_probe ends the loop."""
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        ws = _make_ws()
        device = MagicMock()
        db = _make_db(user=MagicMock(id="u1"), device=device)
        ws.receive_json.side_effect = [dict(self.REGISTER), asyncio.TimeoutError]
        ws.send_json.side_effect = [None, None, RuntimeError("ws gone")]
        with patch.object(mod, "decode_token", return_value={"sub": "u1"}), \
             patch.object(mod, "get_db_session", _db_context(db)), \
             patch.object(mod, "get_device_connection_manager", return_value=manager), \
             patch.object(mod, "DEVICE_HEARTBEAT_INTERVAL", 0.01):
            asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))
        sent_types = [c.args[0]["type"] for c in ws.send_json.await_args_list]
        assert "heartbeat_probe" in sent_types
        assert device.status == "offline"
        assert "dev-1" not in manager.active_connections

    def test_websocket_disconnect_in_loop(self):
        import api.device_websocket as mod
        from api.device_websocket import WebSocketDisconnect
        manager = mod.DeviceConnectionManager()
        ws = _make_ws()
        device = MagicMock()
        db = _make_db(user=MagicMock(id="u1"), device=device)
        ws.receive_json.side_effect = [dict(self.REGISTER), WebSocketDisconnect()]
        with patch.object(mod, "decode_token", return_value={"sub": "u1"}), \
             patch.object(mod, "get_db_session", _db_context(db)), \
             patch.object(mod, "get_device_connection_manager", return_value=manager):
            asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))
        assert device.status == "offline"
        assert "dev-1" not in manager.active_connections

    def test_generic_exception_in_loop(self, caplog):
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        ws = _make_ws()
        device = MagicMock()
        db = _make_db(user=MagicMock(id="u1"), device=device)
        ws.receive_json.side_effect = [dict(self.REGISTER), RuntimeError("boom")]
        with caplog.at_level("ERROR", logger="api.device_websocket"):
            with patch.object(mod, "decode_token", return_value={"sub": "u1"}), \
                 patch.object(mod, "get_db_session", _db_context(db)), \
                 patch.object(mod, "get_device_connection_manager", return_value=manager):
                asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))
        assert "WebSocket error" in caplog.text
        assert device.status == "offline"

    def test_cleanup_skipped_when_never_registered(self):
        """Auth failure paths must not touch manager.disconnect."""
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        ws = _make_ws()
        db = _make_db(user=MagicMock(id="u1"))
        ws.receive_json.side_effect = asyncio.TimeoutError
        with patch.object(mod, "decode_token", return_value={"sub": "u1"}), \
             patch.object(mod, "get_db_session", _db_context(db)), \
             patch.object(mod, "get_device_connection_manager", return_value=manager):
            asyncio.run(mod.websocket_device_endpoint(websocket=ws, token="tok"))
        assert manager.active_connections == {}
        db.commit.assert_not_called()


class TestSendDeviceCommand:
    @pytest.mark.asyncio
    async def test_device_known_but_disconnected(self):
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        db = MagicMock()
        device = MagicMock()
        device.status = "offline"
        db.query.return_value.filter.return_value.first.return_value = device
        with patch.object(mod, "get_device_connection_manager", return_value=manager):
            with pytest.raises(ValueError, match="not connected"):
                await mod.send_device_command("dev-1", "camera_snap", {}, db)

    @pytest.mark.asyncio
    async def test_device_unknown(self):
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(mod, "get_device_connection_manager", return_value=manager):
            with pytest.raises(ValueError, match="not found in database"):
                await mod.send_device_command("dev-9", "camera_snap", {}, db)

    async def _connected(self, response=None, exc=None):
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        ws = _make_ws()
        await manager.connect(ws, "dev-1", "u1", {})
        if exc:
            manager.send_command = AsyncMock(side_effect=exc)
        else:
            manager.send_command = AsyncMock(return_value=response)
        with patch.object(mod, "get_device_connection_manager", return_value=manager):
            return await mod.send_device_command("dev-1", "camera_snap", {}, MagicMock())

    @pytest.mark.asyncio
    async def test_result_success(self):
        result = await self._connected({"type": "result", "success": True,
                                        "data": {"path": "x.jpg"}, "file_path": "/tmp/x.jpg"})
        assert result["success"] is True
        assert result["data"] == {"path": "x.jpg"}
        assert result["file_path"] == "/tmp/x.jpg"

    @pytest.mark.asyncio
    async def test_result_failure(self):
        result = await self._connected({"type": "result", "success": False, "error": "denied"})
        assert result["success"] is False
        assert result["error"] == "denied"

    @pytest.mark.asyncio
    async def test_error_response(self):
        result = await self._connected({"type": "error", "error": "boom"})
        assert result["success"] is False
        assert result["error"] == "boom"

    @pytest.mark.asyncio
    async def test_error_response_no_message(self):
        result = await self._connected({"type": "error"})
        assert result["error"] == "Unknown error"

    @pytest.mark.asyncio
    async def test_unexpected_response_type(self):
        result = await self._connected({"type": "garbage"})
        assert result["success"] is False
        assert "Unexpected response type" in result["error"]

    @pytest.mark.asyncio
    async def test_value_error_propagated(self):
        with pytest.raises(ValueError, match="disconnected"):
            await self._connected(exc=ValueError("Device dev-1 disconnected during command"))

    @pytest.mark.asyncio
    async def test_generic_exception_propagated(self):
        with pytest.raises(RuntimeError, match="boom"):
            await self._connected(exc=RuntimeError("boom"))


class TestDeviceWebsocketHelpers:
    def test_get_connected_devices_info(self):
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        manager.device_info["d1"] = {"name": "phone"}
        with patch.object(mod, "get_device_connection_manager", return_value=manager):
            assert mod.get_connected_devices_info() == [{"device_node_id": "d1", "name": "phone"}]

    def test_is_device_online(self):
        import api.device_websocket as mod
        manager = mod.DeviceConnectionManager()
        manager.active_connections["d1"] = _make_ws()
        with patch.object(mod, "get_device_connection_manager", return_value=manager):
            assert mod.is_device_online("d1") is True
            assert mod.is_device_online("d2") is False

    def test_get_device_connection_manager_singleton(self):
        import api.device_websocket as mod
        with patch.object(mod, "_device_connection_manager", None):
            m1 = mod.get_device_connection_manager()
            m2 = mod.get_device_connection_manager()
            assert m1 is m2
