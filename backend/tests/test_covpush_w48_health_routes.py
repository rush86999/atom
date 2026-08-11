"""Coverage wave 48 — api/health_routes.py (36% → 90%+).

Liveness/readiness probes, DB connectivity (timeout/SQLAlchemy/generic
failures, slow-query warning), disk space (healthy/low/exception), Prometheus
metrics, sync health (healthy/unhealthy), sync metrics. DB + psutil +
sync-monitor mocked — no real dependencies.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

import api.health_routes as hr
from api.health_routes import (
    _check_database,
    _check_disk_space,
    _execute_db_query_session,
    router,
)


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), app


@pytest.fixture
def db_override(app_ref=None):
    def _install(app, db_mock):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_mock
    return _install


class TestLiveness:
    def test_liveness(self, client):
        c, app = client
        resp = c.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"


class TestReadiness:
    def test_ready_all_healthy(self, client):
        c, app = client
        with patch.object(hr, "_check_database", new=AsyncMock(return_value={
            "healthy": True, "message": "ok", "latency_ms": 1.0})), \
             patch.object(hr, "_check_disk_space", new=AsyncMock(return_value={
                "healthy": True, "message": "10GB free", "free_gb": 10.0})):
            resp = c.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
        assert set(resp.json()["checks"]) == {"database", "disk"}

    def test_not_ready_db_failure(self, client):
        c, app = client
        with patch.object(hr, "_check_database", new=AsyncMock(return_value={
            "healthy": False, "message": "db down", "latency_ms": 0})), \
             patch.object(hr, "_check_disk_space", new=AsyncMock(return_value={
                "healthy": True, "message": "ok", "free_gb": 10.0})):
            resp = c.get("/health/ready")
        assert resp.status_code == 503
        assert resp.json()["detail"]["status"] == "not_ready"

    def test_not_ready_disk_failure(self, client):
        c, app = client
        with patch.object(hr, "_check_database", new=AsyncMock(return_value={
            "healthy": True, "message": "ok", "latency_ms": 1.0})), \
             patch.object(hr, "_check_disk_space", new=AsyncMock(return_value={
                "healthy": False, "message": "low", "free_gb": 0.5})):
            resp = c.get("/health/ready")
        assert resp.status_code == 503


class TestCheckDatabase:
    async def test_success(self):
        session = Mock()
        session.execute.return_value.fetchone.return_value = (1,)
        with patch("core.database.SessionLocal", return_value=session):
            result = await _check_database()
        assert result["healthy"] is True
        session.close.assert_called_once()

    async def test_timeout(self):
        session = Mock()
        with patch("core.database.SessionLocal", return_value=session), \
             patch("asyncio.wait_for", side_effect=asyncio_timeout()):
            result = await _check_database()
        assert result["healthy"] is False
        assert "timeout" in result["message"]

    async def test_sqlalchemy_error(self):
        session = Mock()
        session.execute.side_effect = SQLAlchemyError("db broken")
        with patch("core.database.SessionLocal", return_value=session):
            result = await _check_database()
        assert result["healthy"] is False
        assert result["message"] == "Database error"

    async def test_generic_error(self):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("boom")):
            result = await _check_database()
        assert result["healthy"] is False
        assert "Unexpected" in result["message"]


def asyncio_timeout():
    import asyncio
    return asyncio.TimeoutError()


class TestExecuteDbQuery:
    async def test_success(self):
        session = Mock()
        session.execute.return_value.fetchone.return_value = (1,)
        assert await _execute_db_query_session(session) is True

    async def test_exception_reraises(self):
        session = Mock()
        session.execute.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await _execute_db_query_session(session)


class TestDatabaseConnectivity:
    def _db(self):
        db = MagicMock()
        session = Mock()
        session.execute.return_value.fetchone.return_value = (1,)
        db.__next__.return_value = session
        return db, session

    def test_healthy(self, client):
        from core.database import get_db
        c, app = client
        db, session = self._db()
        app.dependency_overrides[get_db] = lambda: db
        pool = Mock()
        pool.size.return_value, pool.checkedin.return_value = 5, 5
        pool.checkedout.return_value, pool.overflow.return_value = 0, 0
        pool.max_overflow = 10
        with patch("api.health_routes.engine") as eng:
            eng.pool = pool
            resp = c.get("/health/db")
        assert resp.status_code == 200
        assert resp.json()["database"]["connected"] is True
        assert resp.json()["database"]["pool_status"]["size"] == 5
        session.close.assert_called_once()

    def test_slow_query_warning(self, client):
        from core.database import get_db
        c, app = client
        db, session = self._db()
        app.dependency_overrides[get_db] = lambda: db
        pool = Mock()
        pool.size.return_value, pool.checkedin.return_value = 5, 5
        pool.checkedout.return_value, pool.overflow.return_value = 0, 0
        pool.max_overflow = 10
        with patch("api.health_routes.engine") as eng, \
             patch("api.health_routes.time.time", side_effect=[0.0] + [0.2] * 100):
            eng.pool = pool
            resp = c.get("/health/db")
        assert resp.status_code == 200
        assert "warning" in resp.json()["database"]

    def test_failure_503(self, client):
        from core.database import get_db
        c, app = client
        db = MagicMock()
        session = Mock()
        session.execute.side_effect = RuntimeError("boom")
        db.__next__.return_value = session
        app.dependency_overrides[get_db] = lambda: db
        resp = c.get("/health/db")
        assert resp.status_code == 503
        assert resp.json()["detail"]["database"]["connected"] is False


class TestDiskSpace:
    async def test_healthy(self):
        disk = SimpleNamespace(free=20 * 1024 ** 3)
        with patch("psutil.disk_usage", return_value=disk):
            result = await _check_disk_space()
        assert result["healthy"] is True
        assert result["free_gb"] == 20.0

    async def test_low_disk(self):
        disk = SimpleNamespace(free=0.5 * 1024 ** 3)
        with patch("psutil.disk_usage", return_value=disk):
            result = await _check_disk_space()
        assert result["healthy"] is False
        assert "Low disk space" in result["message"]

    async def test_exception(self):
        with patch("psutil.disk_usage", side_effect=RuntimeError("boom")):
            result = await _check_disk_space()
        assert result["healthy"] is False
        assert result["message"] == "Disk check error"


class TestPrometheusMetrics:
    def test_metrics_endpoint(self, client):
        c, app = client
        with patch("api.health_routes.generate_latest", return_value=b"# HELP x\n"):
            resp = c.get("/health/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_sync_metrics_endpoint(self, client):
        c, app = client
        with patch("prometheus_client.generate_latest", return_value=b"# HELP y\n"):
            resp = c.get("/metrics/sync")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]


class TestSyncHealth:
    def _sync_setup(self, health, http_status):
        monitor = Mock()
        monitor.check_health.return_value = health
        monitor.get_http_status.return_value = http_status
        db = MagicMock()
        session = Mock()
        db.__next__.return_value = session
        return monitor, db, session

    def test_sync_healthy(self, client):
        c, app = client
        monitor, db, session = self._sync_setup({"status": "healthy"}, 200)
        with patch("core.sync_health_monitor.get_sync_health_monitor", return_value=monitor), \
             patch("api.health_routes.get_db", return_value=db):
            resp = c.get("/health/sync")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
        session.close.assert_called_once()

    def test_sync_unhealthy(self, client):
        c, app = client
        monitor, db, session = self._sync_setup({"status": "unhealthy"}, 503)
        with patch("core.sync_health_monitor.get_sync_health_monitor", return_value=monitor), \
             patch("api.health_routes.get_db", return_value=db):
            resp = c.get("/health/sync")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"
