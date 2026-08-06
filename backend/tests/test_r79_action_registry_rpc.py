"""Round 79 — action-registry duplicate semantics + authenticated RPC edges.

Covers:
- duplicate registration overwrite semantics (last registration wins, single entry)
- the register_action decorator returns the original function
- authenticated RPC: unknown action -> 404
- the dispatch context's user_id is the authenticated actor — a client-supplied
  ``params.user_id`` can never impersonate another actor
- action exceptions -> generic 500 (no exception detail leaked)
"""
from unittest.mock import MagicMock

import pytest

from core.action_registry import (
    ActionNotFoundError,
    action_registry,
    register_action,
)


class TestDuplicateRegistration:
    @pytest.mark.asyncio
    async def test_duplicate_registration_overwrites_and_keeps_single_entry(self):
        async def first(args, context):
            return {"handler": "first"}

        async def second(args, context):
            return {"handler": "second"}

        action_registry.register("test.r79.overwrite", first)
        action_registry.register("test.r79.overwrite", second)

        assert action_registry.list_actions().count("test.r79.overwrite") == 1
        result = await action_registry.execute_action("test.r79.overwrite", {}, {})
        assert result == {"handler": "second"}

    @pytest.mark.asyncio
    async def test_decorator_reregistration_overwrites(self):
        @register_action("test.r79.dec.overwrite")
        async def v1(args, context):
            return {"v": 1}

        @register_action("test.r79.dec.overwrite")
        async def v2(args, context):
            return {"v": 2}

        result = await action_registry.execute_action("test.r79.dec.overwrite", {}, {})
        assert result == {"v": 2}

    def test_register_decorator_returns_original_function(self):
        async def fn(args, context):
            return {}

        returned = register_action("test.r79.returns.original")(fn)
        assert returned is fn

    def test_registered_action_keeps_given_description(self):
        action = action_registry.register(
            "test.r79.desc", lambda args, context: {}, description="my desc"
        )
        assert action.description == "my desc"


class TestRpcRouteAuthenticated:
    @pytest.fixture
    def client(self, worker_database):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.rpc_routes import router
        from core.auth import get_current_user
        from core.database import get_db

        user = MagicMock()
        user.id = "r79-user-1"

        app = FastAPI()
        app.include_router(router)

        async def _override_current_user():
            return user

        SessionLocal = worker_database

        def _override_get_db():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_current_user] = _override_current_user
        app.dependency_overrides[get_db] = _override_get_db
        yield TestClient(app)
        app.dependency_overrides.clear()

    def test_unknown_action_returns_404(self, client):
        resp = client.post("/api/rpc/no.such.action", json={"params": {}})
        assert resp.status_code == 404
        assert "not registered" in resp.json()["detail"]

    def test_known_action_dispatches(self, client):
        @register_action("test.r79.rpc.ok")
        async def _ok(args, context):
            return {"echo": args.get("msg")}

        resp = client.post("/api/rpc/test.r79.rpc.ok", json={"params": {"msg": "hi"}})
        assert resp.status_code == 200
        assert resp.json()["data"]["echo"] == "hi"

    def test_params_user_id_cannot_impersonate_actor(self, client):
        """The dispatch context must carry the authenticated user — a client
        body-supplied user_id is data, not identity (R54 principle)."""
        @register_action("test.r79.rpc.actor")
        async def _actor(args, context):
            return {
                "context_user_id": context.get("user_id"),
                "params_user_id": args.get("user_id"),
            }

        resp = client.post(
            "/api/rpc/test.r79.rpc.actor",
            json={"params": {"user_id": "attacker-id"}},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["context_user_id"] == "r79-user-1"
        assert body["params_user_id"] == "attacker-id"  # data only, not identity

    def test_action_exception_returns_generic_500_without_leak(self, client):
        @register_action("test.r79.rpc.explode")
        async def _explode(args, context):
            raise ValueError("secret-internal-detail")

        resp = client.post("/api/rpc/test.r79.rpc.explode", json={"params": {}})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Action 'test.r79.rpc.explode' failed"
        assert "secret-internal-detail" not in resp.text

    def test_list_actions_includes_registered_names(self, client):
        resp = client.get("/api/rpc/actions")
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()["data"]]
        assert "test.r79.rpc.ok" in names
        assert "mini_app_scaffold" in names
