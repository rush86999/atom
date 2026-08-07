"""Unified integration dispatcher — native/piece/MCP resolution + execution.

Verifies the auto-resolve order (native → piece → mcp → not_found), credential
threading for native, the friendly→package piece-name fix, the MCP scope-gate
namespace, and failure isolation. All backends are mocked — no real services.
"""
import pytest

import core.mini_app_integration_dispatch as disp


# ---------------------------------------------------------------------------
# _to_piece_name
# ---------------------------------------------------------------------------
class TestPieceName:
    def test_friendly_to_package(self):
        assert disp._to_piece_name("slack") == "@activepieces/piece-slack"

    def test_already_package_passthrough(self):
        assert disp._to_piece_name("@activepieces/piece-slack") == "@activepieces/piece-slack"


# ---------------------------------------------------------------------------
# resolve_backend — ordering
# ---------------------------------------------------------------------------
class TestResolveOrder:
    @pytest.mark.asyncio
    async def test_native_wins(self, monkeypatch):
        # notion is a real native connector in DEFAULT_SERVICE_REGISTRY
        monkeypatch.setattr(disp, "_resolve_native", lambda s: s == "notion")
        monkeypatch.setattr(disp, "_resolve_piece", _always_true)  # piece also "exists"
        backend, server_id = await disp.resolve_backend("notion", "search")
        assert backend == "native" and server_id is None

    @pytest.mark.asyncio
    async def test_piece_when_native_absent(self, monkeypatch):
        monkeypatch.setattr(disp, "_resolve_native", lambda s: False)
        monkeypatch.setattr(disp, "_resolve_piece", _always_true)
        backend, _ = await disp.resolve_backend("someapp", "do_thing")
        assert backend == "piece"

    @pytest.mark.asyncio
    async def test_mcp_when_neither_native_nor_piece(self, monkeypatch):
        monkeypatch.setattr(disp, "_resolve_native", lambda s: False)
        monkeypatch.setattr(disp, "_resolve_piece", _always_false)
        monkeypatch.setattr(disp, "_resolve_mcp", lambda s, a: "ext-server")
        backend, server_id = await disp.resolve_backend("custom", "query")
        assert backend == "mcp" and server_id == "ext-server"

    @pytest.mark.asyncio
    async def test_not_found(self, monkeypatch):
        monkeypatch.setattr(disp, "_resolve_native", lambda s: False)
        monkeypatch.setattr(disp, "_resolve_piece", _always_false)
        monkeypatch.setattr(disp, "_resolve_mcp", lambda s, a: None)
        backend, server_id = await disp.resolve_backend("unknown", "x")
        assert backend is None and server_id is None


# ---------------------------------------------------------------------------
# dispatch — execution per backend
# ---------------------------------------------------------------------------
class TestDispatchExecute:
    @pytest.mark.asyncio
    async def test_native_executes_with_credentials(self, monkeypatch, db_session):
        """Native path loads IntegrationToken, constructs service WITH config."""
        from core.models import IntegrationToken
        db_session.add(IntegrationToken(
            tenant_id="t1", provider="notion", access_token="secret-token", status="active",
        ))
        db_session.commit()

        constructed_with = {}

        class FakeInstance:
            def execute_operation(self, operation, params, context=None):
                return {"op": operation, "got_token": self.token}

            token = None

        def fake_get_class(service):
            class S(FakeInstance):
                pass
            return S

        async def fake_execute_native(service, action, params, tenant_id, db):
            # Simulate the real execute_native: construct with config
            row = disp._load_token_row(tenant_id, service, db)
            config = disp._creds_dict(row) if row else {}
            cls = fake_get_class(service)
            inst = cls()
            inst.token = config.get("access_token")
            data = inst.execute_operation(action, params, context={"tenant_id": tenant_id})
            return {"ok": True, "data": data, "backend": "native"}

        monkeypatch.setattr(disp, "execute_native", fake_execute_native)
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve("native"))
        result = await disp.dispatch("notion", "search", {"query": "x"}, tenant_id="t1", db=db_session)
        assert result["ok"] is True
        assert result["data"]["got_token"] == "secret-token"
        assert result["backend"] == "native"

    @pytest.mark.asyncio
    async def test_piece_translates_package_name(self, monkeypatch, db_session):
        """Piece path translates 'slack' → '@activepieces/piece-slack'."""
        seen_integration_id = {}

        class FakeExt:
            async def execute_integration_action(self, integration_id, action_id, params, credentials):
                seen_integration_id["v"] = integration_id
                return {"data": {"sent": True}}

        monkeypatch.setattr("core.external_integration_service.ExternalIntegrationService", FakeExt)
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve("piece"))
        result = await disp.dispatch("slack", "send_message", {}, tenant_id="t1", db=db_session)
        assert result["ok"] is True
        assert seen_integration_id["v"] == "@activepieces/piece-slack"

    @pytest.mark.asyncio
    async def test_mcp_executes_via_call_external_tool(self, monkeypatch):
        called = {}

        async def fake_call(server_id, tool_name, args):
            called.update(server_id=server_id, tool_name=tool_name, args=args)
            return {"rows": [1, 2]}

        class FakeMcp:
            async def call_external_tool(self, server_id, tool_name, args):
                return await fake_call(server_id, tool_name, args)

        monkeypatch.setattr("core.mcp_service.mcp_service", FakeMcp())
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve("mcp", "ext-server"))
        result = await disp.dispatch("custom", "query", {"sql": "1"}, tenant_id="t1", db=None)
        assert result["ok"] is True
        assert called["server_id"] == "ext-server"
        assert result["backend"] == "mcp"

    @pytest.mark.asyncio
    async def test_not_found_returns_error(self, monkeypatch):
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve(None))
        result = await disp.dispatch("unknown", "x", {}, tenant_id="t1", db=None)
        assert result["ok"] is False and result["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_failure_isolated(self, monkeypatch, db_session):
        """A backend throwing → {ok:False}, dispatch doesn't raise."""
        async def boom(*a, **kw):
            raise RuntimeError("backend exploded")
        monkeypatch.setattr(disp, "execute_native", boom)
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve("native"))
        result = await disp.dispatch("notion", "search", {}, tenant_id="t1", db=db_session)
        assert result["ok"] is False and result["error"] == "failed"


# ---------------------------------------------------------------------------
# Scope gate (via _make_callback_handler)
# ---------------------------------------------------------------------------
class TestScopeGate:
    @pytest.mark.asyncio
    async def test_mcp_requires_mcp_scope_not_integrations(self, monkeypatch, db_session):
        """MCP access needs 'mcp.<server_id>', NOT 'integrations.<server_id>'."""
        import core.mini_app_service as svc
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve("mcp", "my-server"))
        handler = svc._make_callback_handler(db_session, "t1", ("integrations.my-server",), None, None)
        result = await handler({"kind": "fetch_integration", "service": "custom", "action": "query"})
        assert result["ok"] is False and result["error"] == "scope_denied"

    @pytest.mark.asyncio
    async def test_mcp_allowed_with_correct_scope(self, monkeypatch, db_session):
        import core.mini_app_service as svc
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve("mcp", "my-server"))
        monkeypatch.setattr(disp, "dispatch", _fake_dispatch_ok)
        handler = svc._make_callback_handler(db_session, "t1", ("mcp.my-server",), None, None)
        result = await handler({"kind": "fetch_integration", "service": "custom", "action": "query"})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_native_allowed_with_integrations_scope(self, monkeypatch, db_session):
        import core.mini_app_service as svc
        monkeypatch.setattr(disp, "resolve_backend", _async_resolve("native"))
        monkeypatch.setattr(disp, "dispatch", _fake_dispatch_ok)
        handler = svc._make_callback_handler(db_session, "t1", ("integrations.notion",), None, None)
        result = await handler({"kind": "fetch_integration", "service": "notion", "action": "search"})
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
async def _always_true(*a, **kw):
    return True


async def _always_false(*a, **kw):
    return False


def _async_resolve(backend, server_id=None):
    async def _r(service, action):
        return (backend, server_id)
    return _r


async def _fake_dispatch_ok(service, action, params, *, tenant_id, db):
    return {"ok": True, "data": {"result": "ok"}, "backend": "mcp"}
