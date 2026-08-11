"""Coverage wave 50 — api/rpc_routes.py (0% → 90%+).

List actions + call action: success (params forwarded, context carries token
identity), unknown action 404 (both registry-miss and ActionNotFoundError),
execution error 500 (no detail leak), 401 unauth. Real action registry mocked.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.rpc_routes import router
from core.auth import get_current_user
from core.database import get_db


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[get_db] = lambda: Mock()
    return TestClient(app)


class TestListActions:
    def test_lists_actions(self, client):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_all_definitions.return_value = [
                SimpleNamespace(name="a1", description="d1",
                                parameters_schema={"type": "object"}),
            ]
            resp = client.get("/api/rpc/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["data"][0]["name"] == "a1"

    def test_empty(self, client):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_all_definitions.return_value = []
            resp = client.get("/api/rpc/actions")
        assert resp.json()["data"] == []

    def test_unauth_401(self):
        app = FastAPI()
        app.include_router(router)
        assert TestClient(app).get("/api/rpc/actions").status_code == 401


class TestCallAction:
    def test_success_forwarding_params_and_context(self, client):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            reg.execute_action = AsyncMock(return_value={"ok": 1})
            resp = client.post("/api/rpc/documents.search", json={"params": {"q": "x"}})
        assert resp.status_code == 200
        assert resp.json()["data"] == {"ok": 1}
        assert resp.json()["action"] == "documents.search"
        args = reg.execute_action.call_args.args
        assert args[1] == {"q": "x"}          # params forwarded
        assert args[2]["user_id"] == "u1"     # token identity, not body

    def test_unknown_action_404_registry(self, client):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = None
            resp = client.post("/api/rpc/ghost", json={"params": {}})
        assert resp.status_code == 404

    def test_action_not_found_error_404(self, client):
        from core.action_registry import ActionNotFoundError
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            reg.execute_action = AsyncMock(side_effect=ActionNotFoundError("ghost"))
            resp = client.post("/api/rpc/ghost", json={"params": {}})
        assert resp.status_code == 404

    def test_execution_error_500_no_leak(self, client):
        with patch("api.rpc_routes.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            reg.execute_action = AsyncMock(side_effect=RuntimeError("secret detail"))
            resp = client.post("/api/rpc/a1", json={"params": {}})
        assert resp.status_code == 500
        assert "secret detail" not in resp.text
        assert "failed" in resp.json()["detail"]

    def test_unauth_401(self):
        app = FastAPI()
        app.include_router(router)
        assert TestClient(app).post("/api/rpc/a1", json={"params": {}}).status_code == 401
