"""
Coverage wave 9b — api/admin/system_health_routes.py (85% -> 100%).
Covers the LanceDB import-failure, redis-check exception, and
vector-check exception branches.
"""
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.cache import cache


@pytest.fixture
def client():
    from api.admin.system_health_routes import router

    app = FastAPI()
    app.include_router(router)

    admin = MagicMock(id="admin-1", role="super_admin", status="active")

    def override_admin():
        return admin

    db = MagicMock()
    db.execute.return_value = None

    def override_db():
        yield db

    app.dependency_overrides[get_super_admin] = override_admin
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), db


from core.admin_endpoints import get_super_admin
from core.database import get_db


class TestSystemHealthBranches:
    def test_redis_check_exception_degraded(self, client):
        c, db = client
        redis_mock = MagicMock()
        redis_mock.ping.side_effect = RuntimeError("redis down")
        with patch.object(cache, "redis_client", redis_mock, create=True):
            resp = c.get("/api/admin/health/api/admin/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["redis"] == "degraded"

    def test_vector_check_exception_degraded(self, client):
        c, db = client
        with patch("api.admin.system_health_routes.HAS_LANCEDB", True), patch(
            "api.admin.system_health_routes.LanceDBHandler",
            side_effect=RuntimeError("lancedb down"),
        ):
            resp = c.get("/api/admin/health/api/admin/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["vector_store"] == "degraded"

    def test_vector_check_disconnected_degraded(self, client):
        c, db = client
        handler = MagicMock()
        handler.test_connection.return_value = {"connected": False, "message": "no table"}
        with patch("api.admin.system_health_routes.HAS_LANCEDB", True), patch(
            "api.admin.system_health_routes.LanceDBHandler", return_value=handler
        ):
            resp = c.get("/api/admin/health/api/admin/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["vector_store"] == "degraded"

    def test_lancedb_import_failure_maintenance(self, client):
        """HAS_LANCEDB=False (import failed) → vector_store = maintenance."""
        c, db = client
        with patch("api.admin.system_health_routes.HAS_LANCEDB", False):
            resp = c.get("/api/admin/health/api/admin/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["services"]["vector_store"] == "maintenance"

    def test_module_import_failure_sets_flag(self, monkeypatch):
        """Reload the module with a broken lancedb import → HAS_LANCEDB False."""
        import api.admin.system_health_routes as shr

        orig_module = sys.modules.get("core.lancedb_handler")
        monkeypatch.setitem(sys.modules, "core.lancedb_handler", None)
        try:
            reloaded = importlib.reload(shr)
            assert reloaded.HAS_LANCEDB is False
        finally:
            if orig_module is not None:
                sys.modules["core.lancedb_handler"] = orig_module
            else:
                sys.modules.pop("core.lancedb_handler", None)
            importlib.reload(shr)
