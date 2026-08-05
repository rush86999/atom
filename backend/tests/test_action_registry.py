"""
P1 — Unified Action Registry tests.

Closes the Cloudflare OS foundation gap: a single decorator-based action
registry that BOTH the agent MCP dispatch (``integrations/mcp_service.py``)
AND a new frontend RPC endpoint (``api/rpc_routes.py``) route through. This
gives Phase 2/3/9 a single enforcement point and resolves the latent
``ImportError`` at ``integrations/mcp_service.py:840,1105`` where
``from core.action_registry import action_registry`` references a module that
did not exist.

The interface here is derived directly from the call sites in
``integrations/mcp_service.py``:
- ``action_registry.get_all_definitions()`` -> iterable of objects with
  ``.name``, ``.description``, ``.parameters_schema`` (a dict with
  ``properties`` and ``required`` keys).
- ``action_registry.get_action(name)`` -> action | None
- ``await action_registry.execute_action(name, args, context)`` -> result
"""
import pytest
from unittest.mock import AsyncMock, patch


# ============================================================================
# Registry mechanics
# ============================================================================

class TestRegistryMechanics:
    def test_register_and_get_action(self):
        from core.action_registry import action_registry, register_action, ActionDefinition

        @register_action("test.echo.v1")
        async def _echo(args, context):
            return {"echo": args.get("msg")}

        action = action_registry.get_action("test.echo.v1")
        assert action is not None
        assert isinstance(action, ActionDefinition)
        assert action.name == "test.echo.v1"

    def test_get_action_unknown_returns_none(self):
        from core.action_registry import action_registry
        assert action_registry.get_action("does.not.exist") is None

    def test_get_all_definitions_returns_registered(self):
        from core.action_registry import action_registry, register_action

        @register_action("test.list.a")
        async def _a(args, context):
            return {"ok": True}

        names = {d.name for d in action_registry.get_all_definitions()}
        assert "test.list.a" in names

    @pytest.mark.asyncio
    async def test_execute_action_round_trip(self):
        from core.action_registry import action_registry, register_action

        @register_action("test.exec.v1")
        async def _exec(args, context):
            return {"doubled": args.get("n", 0) * 2}

        result = await action_registry.execute_action("test.exec.v1", {"n": 21}, {})
        assert result == {"doubled": 42}

    @pytest.mark.asyncio
    async def test_execute_action_unknown_raises_action_not_found(self):
        from core.action_registry import action_registry, ActionNotFoundError
        with pytest.raises(ActionNotFoundError):
            await action_registry.execute_action("nope.nope.nope", {}, {})

    def test_list_actions_returns_registered_names(self):
        from core.action_registry import action_registry, register_action

        @register_action("test.list.actions.method")
        async def _x(args, context):
            return {}

        names = action_registry.list_actions()
        assert isinstance(names, list)
        assert "test.list.actions.method" in names
        assert "documents.search" in names

    def test_registered_action_has_schema_shape(self):
        """Action definitions must expose the schema shape mcp_service.py:843
        relies on: parameters_schema with 'properties' (dict) and 'required' (list)."""
        from core.action_registry import action_registry, register_action

        @register_action(
            "test.schema.v1",
            parameters_schema={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        )
        async def _s(args, context):
            return {}

        action = action_registry.get_action("test.schema.v1")
        assert isinstance(action.parameters_schema.get("properties"), dict)
        assert isinstance(action.parameters_schema.get("required"), list)
        assert "q" in action.parameters_schema["properties"]


# ============================================================================
# Seed actions exist (shared by frontend + agent)
# ============================================================================

class TestSeedActions:
    def test_seed_actions_registered(self):
        from core.action_registry import action_registry
        names = {d.name for d in action_registry.get_all_definitions()}
        # The 5 seed actions shared by frontend + agent dispatch.
        for expected in ("documents.search", "canvas.read", "canvas.update",
                         "tasks.create", "agents.list"):
            assert expected in names, f"Seed action {expected} not registered"


# ============================================================================
# RPC route — auth + dispatch
# ============================================================================

class TestRpcRouteUnauthenticated:
    """The RPC surface must enforce auth: no token -> 401/403 on every route."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.rpc_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_list_actions_unauthenticated_rejected(self, client):
        resp = client.get("/api/rpc/actions")
        assert resp.status_code in (401, 403)

    def test_call_action_unauthenticated_rejected(self, client):
        resp = client.post("/api/rpc/agents.list", json={"params": {}})
        assert resp.status_code in (401, 403)

    def test_call_unknown_action_unauthenticated_rejected(self, client):
        # Auth runs before the endpoint body, so an unknown action with no
        # token is rejected on auth (401/403), not 404.
        resp = client.post("/api/rpc/does.not.exist", json={})
        assert resp.status_code in (401, 403)


class TestRpcRouteAuthenticated:
    """Authenticated RPC: lists the 5 seed actions and dispatches registered actions."""

    @pytest.fixture
    def client(self, worker_database):
        from unittest.mock import MagicMock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.rpc_routes import router
        from core.auth import get_current_user
        from core.database import get_db

        # Stub authenticated user (avoids the conftest admin_user fixture,
        # which references a now-removed User.username column).
        user = MagicMock()
        user.id = "rpc-user-1"

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

    def test_list_actions_returns_five_seed_actions(self, client):
        resp = client.get("/api/rpc/actions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        names = [a["name"] for a in body["data"]]
        for expected in ("documents.search", "canvas.read", "canvas.update",
                         "tasks.create", "agents.list"):
            assert expected in names, f"Seed action {expected} missing from RPC list"

    def test_call_action_dispatches_through_registry(self, client):
        from core.action_registry import action_registry, register_action

        @register_action("test.rpc.echo")
        async def _echo(args, context):
            return {"echo": args.get("msg"), "user_id": context.get("user_id")}

        resp = client.post("/api/rpc/test.rpc.echo", json={"params": {"msg": "hello"}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["echo"] == "hello"
        assert body["data"]["user_id"] is not None


# ============================================================================
# Integration: mcp_service.call_tool routes registered actions through registry
# ============================================================================

class TestMcpServiceDispatchIntegration:
    @pytest.mark.asyncio
    async def test_call_tool_routes_action_through_registry(self):
        """integrations/mcp_service.call_tool must dispatch a registered action
        via the registry (the import at L1105 must resolve and run)."""
        from core.action_registry import action_registry, register_action
        from integrations.mcp_service import MCPService

        @register_action("test.mcp.dispatch")
        async def _dispatch(args, context):
            return {"dispatched": True, "args": args}

        svc = MCPService()
        result = await svc.call_tool("test.mcp.dispatch", {"hello": "world"}, {})
        assert result.get("dispatched") is True
        assert result.get("args") == {"hello": "world"}

    def test_action_registry_module_importable(self):
        """The previously-latent import must now resolve cleanly."""
        from core.action_registry import action_registry  # noqa: F401
